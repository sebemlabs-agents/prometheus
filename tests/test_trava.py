"""Testes da trava de renovacao de token e da validacao do par recebido.

Por que isto existe [LST-17861]: o refresh token do Mercado Livre e o da Shopee
sao de USO UNICO e giram a cada renovacao. Duas execucoes na mesma pasta leem o
mesmo refresh, uma consome, a outra leva erro — e a conexao morre horas depois,
parecendo falha de rede. No Dia 2 da imersao esse cenario e a aula: rotina
agendada rodando junto com uso manual, na mesma pasta.

Rodar:  python3 -m pytest tests -q        (na raiz do repositorio)
"""
import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import meli  # noqa: E402
import seguro  # noqa: E402
import shopee  # noqa: E402


# ------------------------------------------------------------------- a trava

def test_trava_usa_arquivo_separado_e_nao_o_proprio_segredo(tmp_path):
    """O arquivo de segredo e SUBSTITUIDO na gravacao atomica (os.replace).

    Travar o proprio arquivo perderia a trava junto com o inode no meio do
    trecho protegido. Apontamento do gate."""
    cred = tmp_path / "tokens.json"
    cred.write_text("{}", encoding="utf-8")
    inode_antes = cred.stat().st_ino
    with seguro.trava(cred):
        seguro.gravar_protegido(cred, '{"a": 1}\n')
    assert cred.stat().st_ino != inode_antes, "a gravacao atomica troca o arquivo"
    assert seguro.caminho_da_trava(cred) != cred
    assert seguro.caminho_da_trava(cred).exists()


def test_trava_nao_e_apagada_ao_liberar(tmp_path):
    """Apagar o arquivo de trava abre janela: outro processo cria um novo inode
    e entra junto. Apontamento do gate."""
    cred = tmp_path / "tokens.json"
    with seguro.trava(cred):
        pass
    assert seguro.caminho_da_trava(cred).exists()


def test_trava_libera_mesmo_quando_o_bloco_estoura(tmp_path):
    cred = tmp_path / "tokens.json"
    with pytest.raises(ValueError):
        with seguro.trava(cred):
            raise ValueError("falhou no meio")
    with seguro.trava(cred, timeout=2):
        pass


def test_trava_e_reentrante_no_mesmo_processo(tmp_path):
    """renovar() e o caminho forcado passam pela mesma trava; aninhar nao pode
    travar o proprio processo."""
    cred = tmp_path / "tokens.json"
    with seguro.trava(cred):
        with seguro.trava(cred):
            assert True


def test_trava_exclui_outro_processo_de_verdade(tmp_path):
    """Dois processos: o segundo nao entra enquanto o primeiro esta dentro.

    Teste com processo separado porque e exatamente isso que o lock de arquivo
    promete e o que um teste de mesmo processo NAO prova."""
    cred = tmp_path / "tokens.json"
    marca = tmp_path / "entrou.txt"
    prog = textwrap.dedent(
        """
        import sys, time
        from pathlib import Path
        sys.path.insert(0, %r)
        import seguro
        cred, marca = Path(sys.argv[1]), Path(sys.argv[2])
        with seguro.trava(cred):
            print("DENTRO", flush=True)
            time.sleep(3)
            marca.write_text("primeiro saiu", encoding="utf-8")
        """
    ) % str(RAIZ / "scripts")
    script = tmp_path / "primeiro.py"
    script.write_text(prog, encoding="utf-8")
    p = subprocess.Popen([sys.executable, str(script), str(cred), str(marca)],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        # Espera o filho DIZER que entrou, em vez de supor por tempo: sob
        # pytest a subida do interpretador pode passar de um segundo.
        linha = p.stdout.readline()
        assert "DENTRO" in linha, "o filho nao entrou na trava: %r" % linha
        time.sleep(1)
        inicio = time.time()
        with seguro.trava(cred, timeout=20):
            espera = time.time() - inicio
            assert marca.exists(), "entrou antes do primeiro sair"
        assert espera >= 1.0, "nao esperou pela trava (espera=%.2fs)" % espera
    finally:
        p.wait(timeout=20)


def test_trava_com_timeout_falha_com_mensagem_clara_e_sem_seguir(tmp_path):
    """Timeout nao pode continuar sem protecao. Apontamento do gate."""
    cred = tmp_path / "tokens.json"
    prog = textwrap.dedent(
        """
        import sys, time
        from pathlib import Path
        sys.path.insert(0, %r)
        import seguro
        with seguro.trava(Path(sys.argv[1])):
            print("DENTRO", flush=True)
            time.sleep(6)
        """
    ) % str(RAIZ / "scripts")
    script = tmp_path / "segura.py"
    script.write_text(prog, encoding="utf-8")
    p = subprocess.Popen([sys.executable, str(script), str(cred)],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        linha = p.stdout.readline()
        assert "DENTRO" in linha, "o filho nao entrou na trava: %r" % linha
        with pytest.raises(seguro.TravaOcupada) as e:
            with seguro.trava(cred, timeout=2):
                pytest.fail("nao devia ter entrado")
        assert "outra" in str(e.value).lower() or "ocupad" in str(e.value).lower()
    finally:
        p.wait(timeout=20)


# -------------------------------------------- validacao do par antes de gravar

def _resp(**over):
    base = {
        "access_token": "AT-novo",
        "refresh_token": "RT-novo",
        "expires_in": 21600,
        "scope": "offline_access read",
        "user_id": 123,
    }
    base.update(over)
    return base


@pytest.mark.parametrize(
    "ruim",
    [
        {"refresh_token": ""},          # sem renovacao: hoje entrava como ""
        {"refresh_token": None},
        {"access_token": ""},
        {"expires_in": 0},
        {"expires_in": -10},
        {"expires_in": "muito"},
    ],
)
def test_meli_recusa_substituir_credencial_por_resposta_incompleta(tmp_path, monkeypatch, ruim):
    """`salvar_tokens` aceitava refresh vazio e INVENTAVA validade padrao: uma
    resposta incompleta trocava uma credencial boa por uma sem renovacao, calada.
    Apontamento do gate."""
    arq = tmp_path / "tokens.json"
    bom = {"access_token": "AT-bom", "refresh_token": "RT-bom",
           "expires_at": int(time.time()) + 3600, "user_id": 123}
    arq.write_text(json.dumps(bom), encoding="utf-8")
    monkeypatch.setattr(meli, "TOKENS_FILE", arq)
    with pytest.raises(meli.RespostaInvalida):
        meli.salvar_tokens(_resp(**ruim))
    assert json.loads(arq.read_text(encoding="utf-8")) == bom, "credencial boa foi trocada"


def test_meli_aceita_resposta_completa(tmp_path, monkeypatch):
    arq = tmp_path / "tokens.json"
    monkeypatch.setattr(meli, "TOKENS_FILE", arq)
    dados = meli.salvar_tokens(_resp())
    assert dados["refresh_token"] == "RT-novo"
    assert dados["expires_at"] > time.time()


@pytest.mark.parametrize(
    "ruim",
    [{"refresh_token": ""}, {"access_token": ""}, {"expire_in": 0}, {"expire_in": "muito"}],
)
def test_shopee_recusa_substituir_credencial_por_resposta_incompleta(tmp_path, monkeypatch, ruim):
    arq = tmp_path / "tokens-shopee.json"
    bom = {"access_token": "AT-bom", "refresh_token": "RT-bom", "shop_id": 7,
           "partner_id": 9, "expires_at": int(time.time()) + 3600}
    arq.write_text(json.dumps(bom), encoding="utf-8")
    monkeypatch.setattr(shopee, "TOKENS_FILE", arq)
    dado = {"access_token": "AT-novo", "refresh_token": "RT-novo", "expire_in": 14400}
    dado.update(ruim)
    with pytest.raises(shopee.RespostaInvalida):
        shopee.salvar_tokens(dado, 9, 7)
    assert json.loads(arq.read_text(encoding="utf-8")) == bom, "credencial boa foi trocada"


# --------------------------------------------- a Shopee passa a renovar mesmo

def _shopee_pronta(tmp_path, monkeypatch, segundos_de_validade):
    arq = tmp_path / "tokens-shopee.json"
    arq.write_text(json.dumps({
        "access_token": "AT-velho", "refresh_token": "RT-velho",
        "shop_id": 7, "partner_id": 9,
        "expires_at": int(time.time()) + segundos_de_validade,
    }), encoding="utf-8")
    monkeypatch.setattr(shopee, "TOKENS_FILE", arq)
    monkeypatch.setenv("SHOPEE_PARTNER_KEY", "chave-de-teste")
    return arq


def test_shopee_renova_quando_o_prazo_acabou(tmp_path, monkeypatch):
    """O defeito medido: renovar() existia e NINGUEM chamava; expires_at era
    gravado e nunca lido. A conexao morria em 4h com o refresh intacto."""
    arq = _shopee_pronta(tmp_path, monkeypatch, -60)
    chamadas = []

    def falso_post(caminho, corpo, partner_id, partner_key):
        chamadas.append(caminho)
        return {"access_token": "AT-novo", "refresh_token": "RT-novo", "expire_in": 14400}

    monkeypatch.setattr(shopee, "_post", falso_post)
    assert shopee.access_token_valido() == "AT-novo"
    assert len(chamadas) == 1, "devia ter renovado exatamente uma vez"
    assert json.loads(arq.read_text(encoding="utf-8"))["refresh_token"] == "RT-novo"


def test_shopee_nao_renova_quando_o_token_ainda_vale(tmp_path, monkeypatch):
    _shopee_pronta(tmp_path, monkeypatch, 3600)
    monkeypatch.setattr(shopee, "_post", lambda *a, **k: pytest.fail("nao devia renovar"))
    assert shopee.access_token_valido() == "AT-velho"


def test_shopee_sem_refresh_pede_reautorizacao_sem_chamar_a_api(tmp_path, monkeypatch):
    arq = _shopee_pronta(tmp_path, monkeypatch, -60)
    d = json.loads(arq.read_text(encoding="utf-8"))
    d["refresh_token"] = ""
    arq.write_text(json.dumps(d), encoding="utf-8")
    monkeypatch.setattr(shopee, "_post", lambda *a, **k: pytest.fail("nao devia chamar"))
    with pytest.raises(shopee.SemAutorizacao) as e:
        shopee.access_token_valido()
    assert "autorizar_shopee" in str(e.value)


def test_shopee_api_usa_o_token_renovado_e_a_loja_da_mesma_leitura(tmp_path, monkeypatch):
    """O gate pediu: access_token e identificacao da loja tem de sair da MESMA
    leitura coerente, senao uma reautorizacao concorrente mistura os dois."""
    _shopee_pronta(tmp_path, monkeypatch, -60)
    monkeypatch.setattr(shopee, "_post", lambda *a, **k: {
        "access_token": "AT-novo", "refresh_token": "RT-novo", "expire_in": 14400})
    vistos = {}

    class RespostaFalsa:
        def __enter__(self_inner):
            return self_inner

        def __exit__(self_inner, *a):
            return False

        def read(self_inner):
            return json.dumps({"response": {}}).encode("utf-8")

    def falso_abrir(req, timeout=30):
        vistos["url"] = req.full_url
        return RespostaFalsa()

    monkeypatch.setattr(shopee.seguro, "abrir", falso_abrir)
    shopee.api("GET", "/api/v2/shop/get_shop_info")
    assert "AT-novo" in vistos["url"]
    assert "shop_id=7" in vistos["url"]


def test_shopee_recusa_escrita_antes_de_qualquer_efeito(tmp_path, monkeypatch):
    """O gate pediu explicitamente: a recusa de metodo != GET continua ANTES de
    tocar em token, arquivo ou rede."""
    _shopee_pronta(tmp_path, monkeypatch, -60)
    monkeypatch.setattr(shopee, "_post", lambda *a, **k: pytest.fail("nao devia renovar"))
    monkeypatch.setattr(shopee.seguro, "abrir", lambda *a, **k: pytest.fail("nao devia sair"))
    with pytest.raises(PermissionError):
        shopee.api("POST", "/api/v2/product/update_item")


# ------------------------------------------- renovacao nao repete a chamada

def test_meli_nao_repete_o_post_quando_a_renovacao_falha(tmp_path, monkeypatch):
    """Refresh e de uso unico: repetir manda um token possivelmente queimado."""
    arq = tmp_path / "tokens.json"
    arq.write_text(json.dumps({
        "access_token": "AT", "refresh_token": "RT",
        "expires_at": int(time.time()) - 60, "user_id": 1}), encoding="utf-8")
    monkeypatch.setattr(meli, "TOKENS_FILE", arq)
    monkeypatch.setattr(meli, "carregar_env", lambda: {
        "MELI_APP_ID": "1", "MELI_CLIENT_SECRET": "s", "MELI_REDIRECT_URI": "u"})
    chamadas = []

    def falso_post(url, dados):
        chamadas.append(url)
        raise meli.ErroDaAPI(503, "rede caiu")

    monkeypatch.setattr(meli, "post_form", falso_post)
    with pytest.raises(meli.ErroDaAPI):
        meli.get_access_token()
    assert len(chamadas) == 1, "repetiu o POST de renovacao"


def test_meli_renovacao_acontece_dentro_da_trava(tmp_path, monkeypatch):
    """Sem a trava em volta de ler->renovar->gravar, a comparacao do refresh nao
    e condicional de verdade: sobra corrida entre comparar e escrever."""
    arq = tmp_path / "tokens.json"
    arq.write_text(json.dumps({
        "access_token": "AT", "refresh_token": "RT",
        "expires_at": int(time.time()) - 60, "user_id": 1}), encoding="utf-8")
    monkeypatch.setattr(meli, "TOKENS_FILE", arq)
    monkeypatch.setattr(meli, "carregar_env", lambda: {
        "MELI_APP_ID": "1", "MELI_CLIENT_SECRET": "s", "MELI_REDIRECT_URI": "u"})
    dentro = {}

    def falso_post(url, dados):
        dentro["travado"] = seguro.trava_em_uso(arq)
        return _resp()

    monkeypatch.setattr(meli, "post_form", falso_post)
    meli.get_access_token()
    assert dentro["travado"] is True, "o POST de renovacao rodou fora da trava"


def test_meli_quem_esperou_a_trava_aproveita_o_par_novo(tmp_path, monkeypatch):
    """Quem aguardou rele o arquivo e normalmente ja encontra o par renovado,
    em vez de mandar o refresh que leu antes. Apontamento do gate."""
    arq = tmp_path / "tokens.json"
    arq.write_text(json.dumps({
        "access_token": "AT-velho", "refresh_token": "RT-velho",
        "expires_at": int(time.time()) - 60, "user_id": 1}), encoding="utf-8")
    monkeypatch.setattr(meli, "TOKENS_FILE", arq)
    monkeypatch.setattr(meli, "carregar_env", lambda: {
        "MELI_APP_ID": "1", "MELI_CLIENT_SECRET": "s", "MELI_REDIRECT_URI": "u"})

    # simula: outro processo renovou enquanto este esperava a trava
    def falso_post(url, dados):
        pytest.fail("devia ter aproveitado o par novo, nao renovado de novo")

    def renovado_por_outro(caminho, timeout=30):
        d = json.loads(arq.read_text(encoding="utf-8"))
        d.update({"access_token": "AT-de-outro", "refresh_token": "RT-de-outro",
                  "expires_at": int(time.time()) + 21600})
        arq.write_text(json.dumps(d), encoding="utf-8")
        return seguro._trava_real(caminho, timeout)

    monkeypatch.setattr(meli, "post_form", falso_post)
    monkeypatch.setattr(seguro, "trava", renovado_por_outro)
    assert meli.get_access_token() == "AT-de-outro"


# ------------------- nao consumir o refresh sem poder guardar o par novo
#
# Apontamento do gate: hoje a Shopee morre em 4h mas o refresh fica INTACTO. Com
# a renovacao ligada, o refresh passa a ser consumido — e se a gravacao falhar, a
# credencial morre de verdade. O conserto nao pode piorar o que estava ruim.

def test_meli_nao_renova_se_a_pasta_nao_aceita_gravacao(tmp_path, monkeypatch):
    arq = tmp_path / "tokens.json"
    arq.write_text(json.dumps({
        "access_token": "AT", "refresh_token": "RT",
        "expires_at": int(time.time()) - 60, "user_id": 1}), encoding="utf-8")
    monkeypatch.setattr(meli, "TOKENS_FILE", arq)
    monkeypatch.setattr(meli, "carregar_env", lambda: {
        "MELI_APP_ID": "1", "MELI_CLIENT_SECRET": "s", "MELI_REDIRECT_URI": "u"})
    monkeypatch.setattr(meli, "post_form", lambda *a, **k: pytest.fail(
        "nao devia consumir o refresh sem poder gravar o par novo"))
    monkeypatch.setattr(seguro, "pode_gravar", lambda destino: False)
    with pytest.raises(meli.SemAutorizacao) as e:
        meli.get_access_token()
    assert "gravar" in str(e.value).lower()
    assert json.loads(arq.read_text(encoding="utf-8"))["refresh_token"] == "RT"


def test_pode_gravar_nao_toca_no_arquivo_atual(tmp_path):
    arq = tmp_path / "tokens.json"
    arq.write_text("conteudo original", encoding="utf-8")
    inode = arq.stat().st_ino
    assert seguro.pode_gravar(arq) is True
    assert arq.read_text(encoding="utf-8") == "conteudo original"
    assert arq.stat().st_ino == inode


def test_pode_gravar_diz_nao_quando_a_pasta_recusa(tmp_path, monkeypatch):
    def recusa(*a, **k):
        raise OSError(13, "Permission denied")
    monkeypatch.setattr(seguro.tempfile, "mkstemp", recusa)
    assert seguro.pode_gravar(tmp_path / "tokens.json") is False


def test_gravacao_insiste_sem_repetir_a_chamada_ao_provedor(tmp_path, monkeypatch):
    """Recebido um par valido, vale insistir na GRAVACAO. Repetir o POST, nunca."""
    arq = tmp_path / "tokens.json"
    tentativas = []
    original = seguro.gravar_protegido

    def falha_uma_vez(destino, conteudo):
        tentativas.append(1)
        if len(tentativas) == 1:
            raise OSError(5, "Input/output error")
        return original(destino, conteudo)

    monkeypatch.setattr(seguro, "gravar_protegido", falha_uma_vez)
    seguro.gravar_insistindo(arq, '{"a": 1}\n', tentativas=3, espera=0.01)
    assert len(tentativas) == 2
    assert json.loads(arq.read_text(encoding="utf-8")) == {"a": 1}


def test_gravacao_desiste_e_avisa_depois_das_tentativas(tmp_path, monkeypatch):
    def sempre_falha(destino, conteudo):
        raise OSError(5, "Input/output error")
    monkeypatch.setattr(seguro, "gravar_protegido", sempre_falha)
    with pytest.raises(OSError):
        seguro.gravar_insistindo(tmp_path / "x.json", "{}", tentativas=2, espera=0.01)


# --------------------------- diagnostico: presenca nao e prova de renovacao

def test_check_do_meli_diz_o_estado_da_renovacao(tmp_path, monkeypatch, capsys):
    env = tmp_path / "credenciais.txt"
    env.write_text("MELI_APP_ID=1\nMELI_CLIENT_SECRET=s\nMELI_REDIRECT_URI=u\n", encoding="utf-8")
    arq = tmp_path / "tokens.json"
    arq.write_text(json.dumps({
        "access_token": "AT", "refresh_token": "RT",
        "expires_at": int(time.time()) + 3600, "user_id": 1}), encoding="utf-8")
    monkeypatch.setattr(meli, "ENV_FILE", env)
    monkeypatch.setattr(meli, "TOKENS_FILE", arq)
    monkeypatch.setattr(sys, "argv", ["meli.py", "check"])
    meli._main()
    saida = capsys.readouterr().out
    assert "renovacao automatica" in saida
    assert "ligada" in saida
    assert "RT" not in saida and "AT" not in saida, "check nunca imprime credencial"


def test_check_do_meli_avisa_quando_nao_ha_renovacao(tmp_path, monkeypatch, capsys):
    env = tmp_path / "credenciais.txt"
    env.write_text("MELI_APP_ID=1\nMELI_CLIENT_SECRET=s\nMELI_REDIRECT_URI=u\n", encoding="utf-8")
    arq = tmp_path / "tokens.json"
    arq.write_text(json.dumps({
        "access_token": "AT", "refresh_token": "",
        "expires_at": int(time.time()) + 3600}), encoding="utf-8")
    monkeypatch.setattr(meli, "ENV_FILE", env)
    monkeypatch.setattr(meli, "TOKENS_FILE", arq)
    monkeypatch.setattr(sys, "argv", ["meli.py", "check"])
    meli._main()
    saida = capsys.readouterr().out.lower()
    assert "nao veio" in saida or "sem renovacao" in saida


def test_renovar_do_meli_prova_de_verdade_e_nao_imprime_segredo(tmp_path, monkeypatch, capsys):
    """"Veio o refresh" nao prova que a renovacao funciona: Client Secret colado
    com um espaco a mais so falha na primeira renovacao, horas depois."""
    arq = tmp_path / "tokens.json"
    arq.write_text(json.dumps({
        "access_token": "AT-velho", "refresh_token": "RT-velho",
        "expires_at": int(time.time()) + 3600, "user_id": 1}), encoding="utf-8")
    monkeypatch.setattr(meli, "TOKENS_FILE", arq)
    monkeypatch.setattr(meli, "carregar_env", lambda: {
        "MELI_APP_ID": "1", "MELI_CLIENT_SECRET": "s", "MELI_REDIRECT_URI": "u"})
    monkeypatch.setattr(meli, "post_form", lambda *a, **k: _resp())
    monkeypatch.setattr(sys, "argv", ["meli.py", "renovar"])
    assert meli._main() == 0
    saida = capsys.readouterr().out
    assert "renovacao funcionou" in saida.lower() or "funcionou" in saida.lower()
    assert "AT-novo" not in saida and "RT-novo" not in saida
    assert json.loads(arq.read_text(encoding="utf-8"))["refresh_token"] == "RT-novo"


def test_renovar_do_meli_falha_com_saida_nao_zero_e_sem_traceback(tmp_path, monkeypatch, capsys):
    """Falha em rotina agendada precisa dar saida nao zero e instrucao, nunca
    traceback com credencial. Apontamento do gate."""
    arq = tmp_path / "tokens.json"
    arq.write_text(json.dumps({
        "access_token": "AT", "refresh_token": "RT",
        "expires_at": int(time.time()) + 3600, "user_id": 1}), encoding="utf-8")
    monkeypatch.setattr(meli, "TOKENS_FILE", arq)
    monkeypatch.setattr(meli, "carregar_env", lambda: {
        "MELI_APP_ID": "1", "MELI_CLIENT_SECRET": "s", "MELI_REDIRECT_URI": "u"})

    def falha(*a, **k):
        raise meli.ErroDaAPI(400, "invalid_grant")

    monkeypatch.setattr(meli, "post_form", falha)
    monkeypatch.setattr(sys, "argv", ["meli.py", "renovar"])
    assert meli._main() != 0
    saida = capsys.readouterr().out
    assert "autorizar.py" in saida


def test_check_da_shopee_diz_o_estado_da_renovacao(tmp_path, monkeypatch, capsys):
    arq = tmp_path / "tokens-shopee.json"
    arq.write_text(json.dumps({
        "access_token": "AT", "refresh_token": "RT", "shop_id": 7,
        "partner_id": 9, "expires_at": int(time.time()) + 3600}), encoding="utf-8")
    monkeypatch.setattr(shopee, "TOKENS_FILE", arq)
    monkeypatch.setattr(sys, "argv", ["shopee.py", "check"])
    shopee._main()
    saida = capsys.readouterr().out
    assert "renovacao automatica" in saida and "ligada" in saida
    assert "RT" not in saida and "AT" not in saida


def test_renovar_da_shopee_prova_de_verdade(tmp_path, monkeypatch, capsys):
    arq = tmp_path / "tokens-shopee.json"
    arq.write_text(json.dumps({
        "access_token": "AT-velho", "refresh_token": "RT-velho", "shop_id": 7,
        "partner_id": 9, "expires_at": int(time.time()) + 3600}), encoding="utf-8")
    monkeypatch.setattr(shopee, "TOKENS_FILE", arq)
    monkeypatch.setenv("SHOPEE_PARTNER_KEY", "chave")
    monkeypatch.setattr(shopee, "_post", lambda *a, **k: {
        "access_token": "AT-novo", "refresh_token": "RT-novo", "expire_in": 14400})
    monkeypatch.setattr(sys, "argv", ["shopee.py", "renovar"])
    assert shopee._main() == 0
    saida = capsys.readouterr().out
    assert "funcionou" in saida.lower()
    assert "AT-novo" not in saida and "RT-novo" not in saida
