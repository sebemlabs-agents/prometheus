"""Testes da base do pacote: cliente so-leitura, pasta, contrato e painel.

Rodar:  python3 -m pytest tests -q        (na raiz do repositorio)
"""
import datetime as dt
import io
import json
import urllib.error
import os
import sys
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import contrato  # noqa: E402
import meli  # noqa: E402
import painel  # noqa: E402
import pasta as pasta_mod  # noqa: E402
import seguro  # noqa: E402
import atualizacao  # noqa: E402
import pedidos  # noqa: E402
import promocoes  # noqa: E402
import planilha  # noqa: E402


CONTA = {"id": 123456789, "apelido": "LOJA EXEMPLO", "site": "MLB"}
PERIODO = {"de": "2026-07-19", "ate": "2026-10-17"}


# ---------------------------------------------------------------- so leitura

def test_cliente_recusa_metodo_que_nao_e_get():
    with pytest.raises(PermissionError):
        meli.request("POST", "/items/MLB123")


@pytest.mark.parametrize("metodo", ["PUT", "DELETE", "PATCH", "post", "put"])
def test_recusa_todos_os_metodos_de_escrita(metodo):
    with pytest.raises(PermissionError):
        meli.request(metodo, "/items/MLB123")


def test_mensagem_de_recusa_diz_que_nada_foi_alterado():
    with pytest.raises(PermissionError) as erro:
        meli.request("DELETE", "/items/MLB123")
    assert "nada e alterado" in str(erro.value).lower()


def test_check_nunca_devolve_valor_de_credencial(tmp_path, monkeypatch):
    arq = tmp_path / "credenciais.txt"
    arq.write_text(
        "MELI_APP_ID=1234567890\nMELI_CLIENT_SECRET=segredo-que-nao-pode-vazar\n"
        "MELI_REDIRECT_URI=https://radar-meli.invalid/callback\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(meli, "ENV_FILE", arq)
    monkeypatch.setattr(meli, "TOKENS_FILE", tmp_path / "tokens.json")
    situacao = meli.situacao_credenciais()
    bruto = json.dumps(situacao, ensure_ascii=False)
    assert "segredo-que-nao-pode-vazar" not in bruto
    assert "1234567890" not in bruto
    assert situacao["chaves"]["MELI_CLIENT_SECRET"] == "preenchido"


def test_credenciais_vazias_sao_reportadas_sem_derrubar(tmp_path, monkeypatch):
    arq = tmp_path / "credenciais.txt"
    arq.write_text("MELI_APP_ID=\nMELI_CLIENT_SECRET=\nMELI_REDIRECT_URI=\n", encoding="utf-8")
    monkeypatch.setattr(meli, "ENV_FILE", arq)
    monkeypatch.setattr(meli, "TOKENS_FILE", tmp_path / "tokens.json")
    monkeypatch.delenv("MELI_APP_ID", raising=False)
    monkeypatch.delenv("MELI_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("MELI_REDIRECT_URI", raising=False)
    assert meli.situacao_credenciais()["chaves"]["MELI_APP_ID"] == "VAZIO"
    with pytest.raises(meli.CredenciaisIncompletas):
        meli.carregar_env()


def test_erro_de_conta_de_operador_vira_mensagem_em_portugues():
    msg = meli.traduzir_erro(400, '{"error":"invalid_operator_user_id"}')
    assert "administradora" in msg.lower()


def test_erro_de_redirect_uri_explica_o_que_conferir():
    msg = meli.traduzir_erro(400, '{"message":"your client callback has to match with the redirect_uri param"}')
    assert "caractere por caractere" in msg.lower()


# -------------------------------------------------------------------- pasta

def test_recusa_pasta_dentro_de_servico_de_sincronizacao(tmp_path):
    alvo = tmp_path / "Dropbox" / "radar-meli"
    alvo.mkdir(parents=True)
    with pytest.raises(pasta_mod.PastaSincronizada, match="sincroniz"):
        pasta_mod.preparar(alvo)


@pytest.mark.parametrize(
    "trecho", ["Dropbox", "OneDrive", "Google Drive", "iCloud Drive", "CloudStorage"]
)
def test_detecta_os_servicos_mais_comuns(tmp_path, trecho):
    alvo = tmp_path / trecho / "pasta"
    alvo.mkdir(parents=True)
    assert pasta_mod.servico_de_sincronizacao(alvo) is not None


def test_pasta_comum_passa(tmp_path):
    alvo = tmp_path / "Documentos" / "radar-meli"
    alvo.mkdir(parents=True)
    assert pasta_mod.servico_de_sincronizacao(alvo) is None


def test_preparar_cria_apoio_e_nunca_perde_credenciais(tmp_path):
    """Trocado de igualdade exata para preservacao em 22/10/2026.

    O arquivo PODE ganhar bloco novo quando o pacote ganha canal novo — senao
    quem ja conectou nunca recebe as linhas da Shopee. O que nao pode, nunca, e
    perder ou alterar o que a pessoa preencheu."""
    cred = tmp_path / "credenciais.txt"
    cred.write_text("MELI_APP_ID=ja-estava-aqui\n", encoding="utf-8")
    r = pasta_mod.preparar(tmp_path)
    linhas = cred.read_text(encoding="utf-8").splitlines()
    assert "MELI_APP_ID=ja-estava-aqui" in linhas
    assert len([l for l in linhas if l.startswith("MELI_APP_ID=")]) == 1
    assert (tmp_path / ".gitignore").exists()
    assert "credenciais.txt" not in r["criados"]


# ------------------------------------------ permissao: so prometer o verificado
#
# No Windows o os.chmod do Python honra apenas o atributo de somente-leitura e
# ignora o resto em silencio, sem levantar erro. O pacote imprimia "Permissao
# fechada em: ..." numa maquina onde nada tinha sido fechado. Estes testes
# existem para que o relato seja medido, nunca presumido.
#
# Em 22/10/2026 o arquivo de segredo passou a nascer ja restrito (mkstemp +
# substituicao atomica), para fechar a janela entre gravar e proteger. Com
# isso, neutralizar o chmod deixou de simular o Windows: o que caracteriza o
# Windows e a RESTRICAO NAO SER CONFIRMAVEL. E isso que _simula_windows faz.
# As afirmacoes dos testes continuam as mesmas: so prometer o verificado.

def _lista(r, chave):
    return [i["arquivo"] if isinstance(i, dict) else i for i in r.get(chave, [])]


def _simula_windows(monkeypatch):
    """chmod nao levanta erro, e a restricao nao pode ser confirmada."""
    monkeypatch.setattr(pasta_mod.os, "chmod", lambda *a, **k: None)
    monkeypatch.setattr(pasta_mod, "fechado", lambda *a, **k: False)
    monkeypatch.setattr(seguro, "fechado", lambda *a, **k: False)


def test_so_lista_como_protegido_o_que_de_fato_esta_fechado(tmp_path):
    (tmp_path / "credenciais.txt").write_text("MELI_APP_ID=\n", encoding="utf-8")
    (tmp_path / "tokens.json").write_text("{}", encoding="utf-8")
    r = pasta_mod.preparar(tmp_path)
    for nome in _lista(r, "protegidos"):
        modo = (tmp_path / nome).stat().st_mode
        assert modo & 0o077 == 0, "%s foi dado como protegido sem estar" % nome


def test_arquivo_que_nao_pudo_ser_fechado_entra_em_nao_protegidos(tmp_path, monkeypatch):
    """Simula o Windows: a restricao nao pode ser confirmada."""
    (tmp_path / "credenciais.txt").write_text("MELI_APP_ID=\n", encoding="utf-8")
    _simula_windows(monkeypatch)
    r = pasta_mod.preparar(tmp_path)
    assert "credenciais.txt" not in _lista(r, "protegidos")
    assert "credenciais.txt" in _lista(r, "nao_protegidos")


def test_nao_protegido_vem_com_motivo_de_um_conjunto_fechado(tmp_path, monkeypatch):
    (tmp_path / "tokens.json").write_text("{}", encoding="utf-8")
    _simula_windows(monkeypatch)
    r = pasta_mod.preparar(tmp_path)
    assert r["nao_protegidos"], "esperava relato de arquivo nao protegido"
    for item in r["nao_protegidos"]:
        assert item["motivo"] in pasta_mod.MOTIVOS_SEM_PROTECAO


def test_cli_nao_afirma_que_fechou_quando_nao_fechou(tmp_path, monkeypatch, capsys):
    (tmp_path / "credenciais.txt").write_text("MELI_APP_ID=\n", encoding="utf-8")
    _simula_windows(monkeypatch)
    monkeypatch.setattr(pasta_mod, "BASE", tmp_path)
    monkeypatch.setattr(pasta_mod.sys, "argv", ["pasta.py"])
    pasta_mod._main()
    saida = capsys.readouterr().out
    assert "Permissao fechada em: credenciais.txt" not in saida
    assert "credenciais.txt" in saida


def test_arquivo_ausente_nao_vira_relato(tmp_path):
    """Pasta nova: ainda nao existe tokens.json, e isso nao e falha de protecao."""
    r = pasta_mod.preparar(tmp_path)
    assert "tokens.json" not in _lista(r, "nao_protegidos")
    assert "tokens.json" not in _lista(r, "protegidos")


def test_protegidos_nao_passa_vazio(tmp_path):
    """Controle positivo: em sistema POSIX a restricao tem de funcionar de fato.

    Sem isto o teste de coerencia passaria com a lista vazia, validando nada."""
    if os.name != "posix":
        pytest.skip("controle positivo so vale onde o modo POSIX e aplicado")
    (tmp_path / "credenciais.txt").write_text("MELI_APP_ID=\n", encoding="utf-8")
    r = pasta_mod.preparar(tmp_path)
    assert "credenciais.txt" in _lista(r, "protegidos")
    assert not r["nao_protegidos"]


def test_relato_cobre_a_pasta_e_nao_so_os_arquivos(tmp_path):
    """Arquivo fechado dentro de pasta aberta nao protege nada."""
    r = pasta_mod.preparar(tmp_path)
    assert "pasta_fechada" in r


def test_salvar_tokens_relata_quando_nao_pudo_proteger(tmp_path, monkeypatch):
    """tokens.json e gravado depois do pasta.py — a verificacao tem de ir junto."""
    monkeypatch.setattr(meli, "TOKENS_FILE", tmp_path / "tokens.json")
    _simula_windows(monkeypatch)
    r = meli.salvar_tokens({"access_token": "x", "refresh_token": "y",
                            "expires_in": 21600, "user_id": 123})
    assert r is not None, "salvar_tokens tem de relatar o resultado da protecao"
    assert r.get("protegido") is False
    assert r.get("motivo") in pasta_mod.MOTIVOS_SEM_PROTECAO


def test_gitignore_cobre_os_arquivos_sensiveis(tmp_path):
    pasta_mod.preparar(tmp_path)
    gi = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    for nome in ("credenciais.txt", "tokens.json", ".oauth_state", "RETORNO.txt"):
        assert nome in gi


# ------------------------------------------------------------------ contrato

def test_periodo_sem_pedidos_marca_faltando_em_vez_de_zero(tmp_path):
    dado = contrato.gravar(
        "prometheus-promocoes", CONTA, PERIODO, resumo={}, itens=[],
        faltando=["pedidos"],
        lacunas={"pedidos": "nao houve pedido pago neste periodo"},
        pasta=tmp_path,
    )
    assert dado["itens"] == []
    assert "pedidos" in dado["faltando"]
    assert dado["resumo"] == {}


def test_lacuna_sem_explicacao_e_recusada(tmp_path):
    with pytest.raises(contrato.ContratoInvalido, match="sem explicacao"):
        contrato.gravar(
            "prometheus-promocoes", CONTA, PERIODO, resumo={}, itens=[],
            faltando=["custo"], pasta=tmp_path,
        )


def test_dinheiro_como_texto_e_recusado(tmp_path):
    with pytest.raises(contrato.ContratoInvalido, match="dinheiro"):
        contrato.gravar(
            "prometheus-promocoes", CONTA, PERIODO, resumo={},
            itens=[{"mlb": "MLB1", "preco": "1.234,56"}], pasta=tmp_path,
        )


def test_resumo_aninhado_e_recusado(tmp_path):
    with pytest.raises(contrato.ContratoInvalido, match="aninhado"):
        contrato.gravar(
            "prometheus-promocoes", CONTA, PERIODO,
            resumo={"totais": {"a": 1}}, itens=[], pasta=tmp_path,
        )


def test_fonte_invalida_e_recusada(tmp_path):
    with pytest.raises(contrato.ContratoInvalido, match="fonte"):
        contrato.gravar(
            "prometheus-promocoes", CONTA, PERIODO, resumo={}, itens=[],
            fonte="producao", pasta=tmp_path,
        )


def test_conta_sem_id_e_recusada_quando_le_a_conta(tmp_path):
    with pytest.raises(contrato.ContratoInvalido, match="conta"):
        contrato.gravar(
            "prometheus-promocoes", {"apelido": "X"}, PERIODO, resumo={}, itens=[],
            fonte="api", pasta=tmp_path,
        )


def test_gravar_e_carregar_fecham_o_ciclo(tmp_path):
    contrato.gravar(
        "prometheus-promocoes", CONTA, PERIODO,
        resumo={"promocoes_na_janela": 4}, itens=[{"nome": "SETEMBRO"}],
        pasta=tmp_path,
    )
    lido = contrato.carregar("prometheus-promocoes", pasta=tmp_path)
    assert lido["resumo"]["promocoes_na_janela"] == 4
    assert lido["contrato"] == contrato.CONTRATO
    assert contrato.carregar("prometheus-inexistente", pasta=tmp_path) is None


def test_gerado_em_tem_fuso(tmp_path):
    dado = contrato.gravar("prometheus-promocoes", CONTA, PERIODO, {}, [], pasta=tmp_path)
    assert dado["gerado_em"][-5] in "+-"


def test_carregar_todos_ignora_versao_desconhecida(tmp_path):
    contrato.gravar("prometheus-promocoes", CONTA, PERIODO, {}, [], pasta=tmp_path)
    (tmp_path / "prometheus-doutro-mundo.json").write_text(
        json.dumps({"contrato": "99", "skill": "prometheus-doutro-mundo"}), encoding="utf-8"
    )
    achados = contrato.carregar_todos(tmp_path)
    assert [d["skill"] for d in achados] == ["prometheus-promocoes"]


def test_skill_local_nao_precisa_de_conta(tmp_path):
    """Skill que nao le a conta (conteudo de produto) nao tem conta pra nomear."""
    dado = contrato.gravar(
        "prometheus-planilha", None, None, resumo={"produtos": 1},
        itens=[{"titulo": "Serra circular"}], fonte="local", pasta=tmp_path,
    )
    assert dado["fonte"] == "local"
    assert dado["conta"]["id"] is None


def test_fonte_api_continua_exigindo_conta(tmp_path):
    with pytest.raises(contrato.ContratoInvalido, match="conta"):
        contrato.gravar(
            "prometheus-promocoes", {"apelido": "X"}, PERIODO, resumo={}, itens=[],
            fonte="api", pasta=tmp_path,
        )


# -------------------------------------------------------------------- painel

def test_painel_mostra_lacuna_quando_campo_esta_em_faltando(tmp_path):
    dado = contrato.montar(
        "prometheus-promocoes", CONTA, PERIODO, resumo={}, itens=[],
        faltando=["custo"],
        lacunas={"custo": "o custo deste SKU nao veio na sua planilha"},
    )
    html = painel.render([dado])
    assert "não veio da API" in html
    assert "nao veio na sua planilha" in html


def test_painel_marca_demonstracao_de_forma_visivel(tmp_path):
    dado = contrato.montar("prometheus-promocoes", CONTA, PERIODO, {}, [], fonte="demo")
    html = painel.render([dado])
    assert "dados de demonstração" in html
    assert "em-demo" in html


def test_painel_nao_marca_demonstracao_quando_fonte_e_api(tmp_path):
    dado = contrato.montar("prometheus-promocoes", CONTA, PERIODO, {}, [])
    html = painel.render([dado])
    assert "dados de demonstração" not in html


def test_painel_desenha_so_as_skills_presentes():
    a = contrato.montar("prometheus-promocoes", CONTA, PERIODO, {"x": 1}, [])
    html = painel.render([a])
    assert "Promoções terminando" in html
    assert "Devoluções" not in html


def test_painel_vazio_explica_em_vez_de_quebrar():
    html = painel.render([])
    assert "Nenhuma skill rodou ainda" in html


def test_painel_mostra_null_como_nao_veio_nao_como_zero():
    dado = contrato.montar(
        "prometheus-promocoes", CONTA, PERIODO, {},
        [{"mlb": "MLB1", "preco": 149.90, "custo": None, "margem": None}],
    )
    html = painel.render([dado])
    assert "não veio" in html
    assert ">0<" not in html


def test_painel_escapa_conteudo_da_api():
    dado = contrato.montar(
        "prometheus-promocoes", {"id": 1, "apelido": "<script>alert(1)</script>", "site": "MLB"},
        PERIODO, {}, [{"nome": "<img onerror=x>"}],
    )
    html = painel.render([dado])
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_idade_do_dado_aparece():
    antigo = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() - 7200))
    dado = contrato.montar("prometheus-promocoes", CONTA, PERIODO, {}, [])
    dado["gerado_em"] = antigo
    assert "há 2 h" in painel.render([dado])


# ---------------------------------------------------------------- atualizacao

def _base_falsa(tmp_path, auto=None, com_settings=True, registrado=True):
    base = tmp_path / ".claude"
    (base / "plugins").mkdir(parents=True)
    cfg = {"extraKnownMarketplaces": {}}
    if registrado and com_settings:
        entrada = {"source": {"source": "github", "repo": "sebemlabs-agents/prometheus"}}
        if auto is not None:
            entrada["autoUpdate"] = auto
        cfg["extraKnownMarketplaces"]["prometheus"] = entrada
    cfg["outraCoisa"] = {"preservar": True}
    (base / "settings.json").write_text(json.dumps(cfg), encoding="utf-8")
    conhecidos = {}
    if registrado:
        conhecidos["prometheus"] = {"source": {}, "installLocation": "/x"}
        if auto is not None:
            conhecidos["prometheus"]["autoUpdate"] = auto
    (base / "plugins" / "known_marketplaces.json").write_text(
        json.dumps(conhecidos), encoding="utf-8")
    return base


def test_atualizacao_desligada_por_padrao(tmp_path):
    assert atualizacao.estado(_base_falsa(tmp_path)) == "desligada"


def test_atualizacao_le_ligada(tmp_path):
    assert atualizacao.estado(_base_falsa(tmp_path, auto=True)) == "ligada"


def test_atualizacao_le_desligada_explicita(tmp_path):
    assert atualizacao.estado(_base_falsa(tmp_path, auto=False)) == "desligada"


def test_atualizacao_sem_catalogo_diz_nao_instalado(tmp_path):
    assert atualizacao.estado(_base_falsa(tmp_path, registrado=False)) == "nao instalado"


def test_ligar_muda_os_dois_arquivos(tmp_path):
    base = _base_falsa(tmp_path)
    mudou = atualizacao.ligar(base)
    assert set(mudou) == {"settings.json", "known_marketplaces.json"}
    assert atualizacao.estado(base) == "ligada"


def test_ligar_preserva_o_resto_das_configuracoes(tmp_path):
    base = _base_falsa(tmp_path)
    atualizacao.ligar(base)
    cfg = json.loads((base / "settings.json").read_text(encoding="utf-8"))
    assert cfg["outraCoisa"] == {"preservar": True}
    assert cfg["extraKnownMarketplaces"]["prometheus"]["source"]["repo"] == \
        "sebemlabs-agents/prometheus"


def test_ligar_faz_copia_de_seguranca(tmp_path):
    base = _base_falsa(tmp_path)
    atualizacao.ligar(base)
    assert (base / "settings.json.bak-elo").exists()


def test_ligar_duas_vezes_nao_reescreve(tmp_path):
    base = _base_falsa(tmp_path)
    atualizacao.ligar(base)
    assert atualizacao.ligar(base) == []


def test_ligar_recusa_quando_nao_instalado(tmp_path):
    with pytest.raises(atualizacao.SemClaude):
        atualizacao.ligar(_base_falsa(tmp_path, registrado=False))


def test_estado_aceita_known_marketplaces_aninhado(tmp_path):
    base = _base_falsa(tmp_path, com_settings=False)
    k = base / "plugins" / "known_marketplaces.json"
    k.write_text(json.dumps({"marketplaces": {"prometheus": {"autoUpdate": True}}}),
                 encoding="utf-8")
    assert atualizacao.estado(base) == "ligada"


# ---------------------------------------------------- URL de retorno propria

def test_apelido_tira_acento_e_simbolo():
    assert pasta_mod.apelido("Açaí do João & Cia") == "acai-do-joao-cia"


def test_apelido_nao_deixa_hifen_duplo_nem_nas_pontas():
    a = pasta_mod.apelido("  --Loja   Sebem!!  ")
    assert a == "loja-sebem"


def test_apelido_recusa_nome_sem_letra_nem_numero():
    with pytest.raises(ValueError):
        pasta_mod.apelido(" --- ")


def test_apelido_limita_o_tamanho():
    assert len(pasta_mod.apelido("x" * 120)) <= 40


def test_uri_sem_nome_usa_a_padrao():
    assert pasta_mod.uri_de(None) == pasta_mod.URI_PADRAO


def test_uri_com_nome_e_https_e_invalid():
    u = pasta_mod.uri_de("Loja Sebem")
    assert u == "https://loja-sebem.invalid/callback"
    assert u.startswith("https://") and ".invalid/" in u


def test_preparar_grava_a_uri_da_pessoa(tmp_path):
    r = pasta_mod.preparar(tmp_path, nome="Loja Sebem")
    texto = (tmp_path / "credenciais.txt").read_text(encoding="utf-8")
    assert "MELI_REDIRECT_URI=https://loja-sebem.invalid/callback" in texto
    assert r["uri"] == "https://loja-sebem.invalid/callback"


def test_preparar_sem_nome_mantem_a_padrao(tmp_path):
    pasta_mod.preparar(tmp_path)
    texto = (tmp_path / "credenciais.txt").read_text(encoding="utf-8")
    assert "MELI_REDIRECT_URI=%s" % pasta_mod.URI_PADRAO in texto


def test_preparar_nunca_altera_credenciais_ja_preenchidas(tmp_path):
    """Nem mesmo quando a pessoa roda de novo com outro nome de loja: a URL de
    retorno que ela ja cadastrou nao pode ser trocada pelas costas."""
    (tmp_path / "credenciais.txt").write_text("MELI_APP_ID=123\n", encoding="utf-8")
    pasta_mod.preparar(tmp_path, nome="Outra Loja")
    linhas = (tmp_path / "credenciais.txt").read_text(encoding="utf-8").splitlines()
    assert "MELI_APP_ID=123" in linhas
    assert not [l for l in linhas if l.startswith("MELI_REDIRECT_URI=https://outra-loja")]


# -------------------------------------------------- dinheiro legivel no painel

def test_numero_poe_separador_de_milhar():
    assert painel._numero(1234567.89) == "1.234.567,89"
    assert painel._numero(999.5) == "999,50"


def test_dinheiro_sai_com_simbolo_e_duas_casas():
    assert painel._valor(48213.9, "a_receber") == "R$ 48.213,90"
    assert painel._valor(3120.44, "valor") == "R$ 3.120,44"


def test_dinheiro_negativo_poe_o_sinal_antes_do_simbolo():
    assert painel._valor(-50.0, "saldo") == "-R$ 50,00"


def test_inteiro_de_dinheiro_tambem_vira_reais():
    assert painel._valor(1200, "total") == "R$ 1.200,00"


def test_percentual_nao_vira_dinheiro():
    assert painel._valor(12.5, "desconto_minimo") == "12,5%"
    assert painel._valor(15.0, "minimo") == "15%"


def test_numero_comum_fica_sem_simbolo():
    assert painel._valor(37, "anuncios_afetados") == "37"


def test_ausente_continua_dizendo_que_nao_veio():
    assert "não veio" in painel._valor(None, "custo")


def test_zero_de_dinheiro_nao_vira_ausente():
    assert painel._valor(0.0, "valor") == "R$ 0,00"


# ------------------------------------------------------------- prometheus-promocoes

class _ApiFalsa:
    """Responde no lugar do Mercado Livre. Registra o que foi pedido."""

    def __init__(self, promocoes, itens_por_promocao=None):
        self.promocoes = promocoes
        self.itens = itens_por_promocao or {}
        self.chamadas = []

    def __call__(self, metodo, path, params=None):
        self.chamadas.append((metodo, path, params))
        assert metodo == "GET", "a skill nao pode fazer nada alem de GET"
        if "/seller-promotions/users/" in path:
            return {"results": self.promocoes}
        if "/items" in path:
            pid = path.split("/promotions/")[1].split("/")[0]
            return {"results": self.itens.get(pid, []), "paging": {}}
        raise AssertionError("endpoint inesperado: %s" % path)


def _promo(pid, nome, dias, **extra):
    fim = dt.datetime(2026, 10, 19, 12, 0, tzinfo=promocoes.FUSO) + dt.timedelta(days=dias)
    d = {"id": pid, "name": nome, "type": "DEAL", "status": "started",
         "finish_date": fim.isoformat()}
    d.update(extra)
    return d


@pytest.fixture
def api(monkeypatch):
    def instalar(promos, itens=None):
        falsa = _ApiFalsa(promos, itens)
        monkeypatch.setattr(promocoes.meli, "request", falsa)
        monkeypatch.setattr(promocoes.meli, "conta_conectada",
                            lambda: {"id": 1, "apelido": "LOJA", "site": "MLB"})
        return falsa
    return instalar


HOJE = dt.date(2026, 10, 19)


def test_promocoes_so_traz_o_que_termina_na_janela(api):
    api([_promo("a", "Acaba amanha", 1), _promo("b", "Acaba em 30", 30)])
    d = promocoes.coletar(rapido=True, hoje=HOJE)
    assert [i["promocao"] for i in d["itens"]] == ["Acaba amanha"]


def test_promocoes_ignora_campanha_ja_encerrada(api):
    api([_promo("a", "Ontem", -1)])
    assert promocoes.coletar(rapido=True, hoje=HOJE)["itens"] == []


def test_promocoes_ignora_status_que_nao_vale(api):
    api([dict(_promo("a", "Cancelada", 2), status="finished")])
    assert promocoes.coletar(rapido=True, hoje=HOJE)["itens"] == []


def test_promocoes_sem_data_de_termino_vira_aviso(api):
    api([dict(_promo("a", "Sem fim", 2), finish_date=None)])
    d = promocoes.coletar(rapido=True, hoje=HOJE)
    assert d["itens"] == []
    assert any("sem data de término" in a for a in d["avisos"])


def test_promocoes_ordena_pelo_que_termina_antes(api):
    api([_promo("a", "Depois", 5), _promo("b", "Antes", 1)])
    d = promocoes.coletar(rapido=True, hoje=HOJE)
    assert [i["promocao"] for i in d["itens"]] == ["Antes", "Depois"]


def test_promocoes_conta_anuncios_e_aderidos(api):
    api([_promo("a", "Com itens", 2)],
        {"a": [{"status": "started"}, {"status": "candidate"}, {"status": "started"}]})
    d = promocoes.coletar(hoje=HOJE)
    assert d["itens"][0]["anuncios_dentro"] == 3
    assert d["itens"][0]["anuncios_aderidos"] == 2


def test_promocoes_modo_rapido_declara_a_lacuna(api):
    api([_promo("a", "X", 2)])
    d = promocoes.coletar(rapido=True, hoje=HOJE)
    assert d["itens"][0]["anuncios_dentro"] is None
    assert "anuncios_dentro" in d["faltando"]
    assert "anuncios_dentro" in d["lacunas"]


def test_promocoes_modo_rapido_nao_chama_a_lista_de_itens(api):
    falsa = api([_promo("a", "X", 2)])
    promocoes.coletar(rapido=True, hoje=HOJE)
    assert not any("/items" in c[1] for c in falsa.chamadas)


def test_promocoes_percentual_ausente_nao_vira_zero(api):
    api([dict(_promo("a", "Sem percentual", 2), fixed_percentage=None)])
    d = promocoes.coletar(rapido=True, hoje=HOJE)
    assert d["itens"][0]["desconto_minimo"] is None
    assert "desconto_minimo" in d["faltando"]


def test_promocoes_percentual_como_texto_vira_numero(api):
    api([dict(_promo("a", "X", 2), fixed_percentage="15.5")])
    d = promocoes.coletar(rapido=True, hoje=HOJE)
    assert d["itens"][0]["desconto_minimo"] == 15.5


def test_promocoes_sempre_declara_margem_e_renovacao_como_desconhecidas(api):
    api([_promo("a", "X", 2)])
    d = promocoes.coletar(rapido=True, hoje=HOJE)
    assert "margem_apos_desconto" in d["faltando"]
    assert "vai_ser_renovada" in d["faltando"]


def test_promocoes_resumo_conta_as_que_apertam(api):
    api([_promo("a", "Hoje", 0), _promo("b", "Em 3", 3), _promo("c", "Em 6", 6)])
    d = promocoes.coletar(rapido=True, hoje=HOJE)
    assert d["resumo"]["promocoes_na_janela"] == 3
    assert d["resumo"]["termina_em_3_dias"] == 2


def test_promocoes_janela_vazia_nao_e_erro(api):
    api([])
    d = promocoes.coletar(rapido=True, hoje=HOJE)
    assert d["itens"] == [] and d["resumo"]["promocoes_na_janela"] == 0


def test_promocoes_escopo_amplo_vira_aviso(api):
    api([_promo("a", "Campanha ampla", 2)])
    d = promocoes.coletar(rapido=True, hoje=HOJE)
    assert any("escopo amplo" in a for a in d["avisos"])


def test_promocoes_passa_no_contrato(api, tmp_path):
    api([_promo("a", "X", 2)], {"a": [{"status": "started"}]})
    d = promocoes.coletar(hoje=HOJE)
    gravado = contrato.gravar("prometheus-promocoes", conta=d["conta"], periodo=d["periodo"],
                              resumo=d["resumo"], itens=d["itens"],
                              faltando=d["faltando"], lacunas=d["lacunas"],
                              avisos=d["avisos"], pasta=tmp_path)
    assert gravado["contrato"] == "1"
    assert (tmp_path / "prometheus-promocoes.json").exists()


# ------------------------------------------------- planilha: CSV e XLSX crus

def _csv(tmp_path, linhas, codec="utf-8"):
    p = tmp_path / "x.csv"
    p.write_bytes("\n".join(linhas).encode(codec))
    return p


def test_planilha_csv_com_ponto_e_virgula_e_latin1(tmp_path):
    p = _csv(tmp_path, ["SKU;Descrição", "A1;Assador Giratório"], codec="latin-1")
    d = planilha.ler(p)
    assert d["colunas"] == ["SKU", "Descrição"]
    assert d["linhas"][0]["Descrição"] == "Assador Giratório"


def test_planilha_csv_com_virgula(tmp_path):
    p = _csv(tmp_path, ["sku,nome", "A1,Chapa"])
    assert planilha.ler(p)["colunas"] == ["sku", "nome"]


def test_planilha_numero_brasileiro_vira_numero():
    assert planilha.numero_br("1.234,56") == 1234.56
    assert planilha.numero_br("R$ 987,00") == 987.0
    assert planilha.numero_br("(50,00)") == -50.0


def test_planilha_numero_americano_tambem():
    assert planilha.numero_br("1,234.56") == 1234.56


def test_planilha_texto_que_nao_e_numero_fica_texto():
    assert planilha.numero_br("ABC-1") is None
    assert planilha.numero_br("") is None


def test_planilha_data_brasileira_vira_iso(tmp_path):
    p = _csv(tmp_path, ["quando", "15/03/2026"])
    assert planilha.ler(p)["linhas"][0]["quando"] == "2026-03-15"


def test_planilha_celula_vazia_fica_none(tmp_path):
    p = _csv(tmp_path, ["a;b", "1;"])
    assert planilha.ler(p)["linhas"][0]["b"] is None


def test_planilha_linha_curta_nao_quebra(tmp_path):
    p = _csv(tmp_path, ["a;b;c", "1;2"])
    assert planilha.ler(p)["linhas"][0]["c"] is None


def test_planilha_coluna_sem_nome_ganha_um(tmp_path):
    p = _csv(tmp_path, ["a;;c", "1;2;3"])
    assert planilha.ler(p)["colunas"][1] == "coluna_2"


def test_planilha_coluna_repetida_nao_se_sobrescreve(tmp_path):
    p = _csv(tmp_path, ["total;total", "1;2"])
    cols = planilha.ler(p)["colunas"]
    assert cols[0] != cols[1]
    assert len(set(cols)) == 2


def test_planilha_perfil_descreve_tipo_e_exemplos(tmp_path):
    p = _csv(tmp_path, ["custo;nome", "10,50;Chapa", ";Assador"])
    perfil = {c["coluna"]: c for c in planilha.perfil(planilha.ler(p))}
    assert perfil["custo"]["tipo"] == "número"
    assert perfil["custo"]["vazias"] == 1
    assert perfil["nome"]["exemplos"][0] == "Chapa"


def test_planilha_coluna_toda_vazia_e_dita(tmp_path):
    p = _csv(tmp_path, ["a;b", "1;"])
    perfil = {c["coluna"]: c for c in planilha.perfil(planilha.ler(p))}
    assert perfil["b"]["tipo"] == "sempre vazia"


def test_planilha_guarda_quando_o_arquivo_foi_capturado(tmp_path):
    d = planilha.ler(_csv(tmp_path, ["a", "1"]))
    assert d["capturado_em"]


def test_planilha_xls_antigo_explica_o_que_fazer(tmp_path):
    p = tmp_path / "velho.xls"
    p.write_bytes(b"qualquer coisa")
    with pytest.raises(planilha.PlanilhaIlegivel) as e:
        planilha.ler(p)
    assert "salve como" in str(e.value)


def test_planilha_extensao_desconhecida_recusa(tmp_path):
    p = tmp_path / "x.pdf"
    p.write_bytes(b"...")
    with pytest.raises(planilha.PlanilhaIlegivel):
        planilha.ler(p)


def test_planilha_arquivo_que_nao_existe(tmp_path):
    with pytest.raises(FileNotFoundError):
        planilha.ler(tmp_path / "nao-existe.csv")


def test_planilha_csv_vazio_recusa(tmp_path):
    with pytest.raises(planilha.PlanilhaIlegivel):
        planilha.ler(_csv(tmp_path, []))


def test_coluna_para_indice():
    assert planilha.coluna_para_indice("A1") == 0
    assert planilha.coluna_para_indice("Z9") == 25
    assert planilha.coluna_para_indice("AA1") == 26
    assert planilha.coluna_para_indice("BC12") == 54


def _xlsx(tmp_path):
    import zipfile
    ss = ('<?xml version="1.0"?><sst xmlns="http://schemas.openxmlformats.org/'
          'spreadsheetml/2006/main"><si><t>SKU</t></si><si><t>Custo</t></si>'
          '<si><t>Quando</t></si><si><t>X-1</t></si></sst>')
    styles = ('<?xml version="1.0"?><styleSheet xmlns="http://schemas.openxmlformats.org/'
              'spreadsheetml/2006/main"><numFmts><numFmt numFmtId="165" '
              'formatCode="dd/mm/yyyy"/></numFmts><cellXfs><xf numFmtId="0"/>'
              '<xf numFmtId="165"/></cellXfs></styleSheet>')
    wb = ('<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/'
          'spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/'
          'officeDocument/2006/relationships"><sheets><sheet name="Dados" sheetId="1" '
          'r:id="rId1"/><sheet name="Outra" sheetId="2" r:id="rId2"/></sheets></workbook>')
    rels = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/'
            'package/2006/relationships"><Relationship Id="rId1" '
            'Target="worksheets/sheet1.xml"/><Relationship Id="rId2" '
            'Target="worksheets/sheet2.xml"/></Relationships>')
    s1 = ('<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/'
          'spreadsheetml/2006/main"><sheetData>'
          '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c>'
          '<c r="C1" t="s"><v>2</v></c></row>'
          '<row r="2"><c r="A2" t="s"><v>3</v></c><c r="B2"><v>1234.56</v></c>'
          '<c r="C2" s="1"><v>46096</v></c></row>'
          '<row r="3"><c r="A3" t="inlineStr"><is><t>X-2</t></is></c>'
          '<c r="B3"><v>99</v></c></row></sheetData></worksheet>')
    s2 = ('<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/'
          'spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr">'
          '<is><t>obs</t></is></c></row></sheetData></worksheet>')
    p = tmp_path / "x.xlsx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", rels)
        z.writestr("xl/sharedStrings.xml", ss)
        z.writestr("xl/styles.xml", styles)
        z.writestr("xl/worksheets/sheet1.xml", s1)
        z.writestr("xl/worksheets/sheet2.xml", s2)
    return p


def test_xlsx_le_strings_compartilhadas_e_embutidas(tmp_path):
    d = planilha.ler(_xlsx(tmp_path))
    assert d["colunas"] == ["SKU", "Custo", "Quando"]
    assert [l["SKU"] for l in d["linhas"]] == ["X-1", "X-2"]


def test_xlsx_numero_continua_numero(tmp_path):
    d = planilha.ler(_xlsx(tmp_path))
    assert d["linhas"][0]["Custo"] == 1234.56


def test_xlsx_serial_com_formato_de_data_vira_data(tmp_path):
    d = planilha.ler(_xlsx(tmp_path))
    assert d["linhas"][0]["Quando"] == "2026-03-15"


def test_xlsx_lista_as_abas_e_le_a_primeira(tmp_path):
    d = planilha.ler(_xlsx(tmp_path))
    assert d["abas"] == ["Dados", "Outra"] and d["aba"] == "Dados"


def test_xlsx_aba_inexistente_diz_quais_existem(tmp_path):
    with pytest.raises(planilha.PlanilhaIlegivel) as e:
        planilha.ler(_xlsx(tmp_path), aba=9)
    assert "Dados" in str(e.value) and "Outra" in str(e.value)


def test_xlsx_que_nao_e_zip_explica(tmp_path):
    p = tmp_path / "falso.xlsx"
    p.write_bytes(b"isto nao e um zip")
    with pytest.raises(planilha.PlanilhaIlegivel) as e:
        planilha.ler(p)
    assert ".xls" in str(e.value)


# ------------------------------------------------ contrato: origem 'export'

def test_contrato_aceita_fonte_export(tmp_path):
    d = contrato.gravar("prometheus-promocoes", conta=None, periodo=None, resumo={"n": 1},
                        itens=[{"sku": "A"}], fonte="export",
                        capturado_em="2026-10-12T09:00:00-03:00", pasta=tmp_path)
    assert d["fonte"] == "export"
    assert d["capturado_em"] == "2026-10-12T09:00:00-03:00"


def test_contrato_capturado_em_e_opcional(tmp_path):
    d = contrato.gravar("prometheus-promocoes", conta={"id": 1, "apelido": "L", "site": "MLB"},
                        periodo=None, resumo={}, itens=[], pasta=tmp_path)
    assert d["capturado_em"] is None


def test_painel_marca_dado_de_planilha_e_a_idade_do_arquivo(tmp_path):
    contrato.gravar("prometheus-promocoes", conta=None, periodo=None, resumo={"n": 1},
                    itens=[{"sku": "A"}], fonte="export",
                    capturado_em="2026-10-12T09:00:00-03:00", pasta=tmp_path)
    html = painel.render(contrato.carregar_todos(tmp_path))
    assert "de planilha" in html
    assert "arquivo de" in html


# ------------------------------------------------------------------ shopee
#
# A Shopee assina cada chamada com HMAC-SHA256 sobre partner_id + caminho +
# timestamp. Errar a base da assinatura e o erro mais caro: ela recusa sem
# dizer por que. Host BR confirmado no Horus: openplatform.shopee.com.br

import shopee  # noqa: E402


def test_assinatura_e_hmac_do_partner_key_sobre_id_caminho_e_hora():
    import hmac, hashlib
    esperado = hmac.new(b"chave-secreta", b"123/api/v2/shop/auth_partner1700000000",
                        hashlib.sha256).hexdigest()
    assert shopee.assinar(123, "/api/v2/shop/auth_partner", 1700000000,
                          "chave-secreta") == esperado


def test_link_de_autorizacao_leva_assinatura_e_retorno():
    from urllib.parse import urlparse, parse_qs
    url = shopee.link_de_autorizacao(123, "chave", "https://x.supabase.co",
                                     agora=1700000000)
    q = parse_qs(urlparse(url).query)
    assert urlparse(url).netloc == "openplatform.shopee.com.br"
    assert q["partner_id"] == ["123"]
    assert q["timestamp"] == ["1700000000"]
    assert q["redirect"] == ["https://x.supabase.co"]
    assert q["sign"] == [shopee.assinar(123, shopee.CAMINHO_AUTH, 1700000000, "chave")]


def test_recusa_retorno_que_nao_e_https():
    """A Shopee exige dominio HTTPS real — .invalid foi recusado no teste de 22/10."""
    for ruim in ("http://x.supabase.co", "sebem.invalid", "https://sebemequipamentos"):
        with pytest.raises(ValueError):
            shopee.link_de_autorizacao(123, "chave", ruim)


def test_recusa_dominio_reservado_mesmo_com_https_e_ponto():
    """O habito do Meli e escrever .invalid. Ele passa no teste de forma e falha
    na Shopee, com mensagem que nao diz a causa — entao paramos aqui."""
    for ruim in ("https://sebem.invalid/callback", "https://loja.test",
                 "https://x.example", "https://algo.localhost"):
        with pytest.raises(ValueError, match="(?i)invalid|reservado"):
            shopee.link_de_autorizacao(123, "chave", ruim)


def test_le_codigo_e_loja_do_endereco_colado():
    code, shop = shopee.ler_retorno(
        "https://x.supabase.co/?code=6851496f48775a69&shop_id=433434010")
    assert code == "6851496f48775a69"
    assert shop == 433434010


def test_retorno_sem_code_explica_em_vez_de_quebrar():
    with pytest.raises(ValueError, match="code"):
        shopee.ler_retorno("https://x.supabase.co/")


def test_cliente_recusa_qualquer_metodo_que_nao_seja_get():
    for metodo in ("POST", "PUT", "DELETE", "patch"):
        with pytest.raises(PermissionError):
            shopee.api(metodo, "/api/v2/order/get_order_list")


def test_gitignore_e_protecao_cobrem_os_arquivos_da_shopee(tmp_path):
    """O token da Shopee e tao sensivel quanto o do Meli — e nasce depois."""
    for nome in ("tokens-shopee.json", "ABRIR_SHOPEE.txt", "RETORNO_SHOPEE.txt"):
        (tmp_path / nome).write_text("x", encoding="utf-8")
        assert nome in pasta_mod.ARQUIVOS_SENSIVEIS
    pasta_mod.preparar(tmp_path)
    gi = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    for nome in ("tokens-shopee.json", "ABRIR_SHOPEE.txt", "RETORNO_SHOPEE.txt"):
        assert nome in gi


def test_credenciais_trazem_o_bloco_da_shopee(tmp_path):
    pasta_mod.preparar(tmp_path)
    texto = (tmp_path / "credenciais.txt").read_text(encoding="utf-8")
    for chave in ("SHOPEE_PARTNER_ID", "SHOPEE_PARTNER_KEY", "SHOPEE_REDIRECT_URI"):
        assert chave in texto
    assert "nao aceita .invalid" in texto.lower() or "NAO aceita .invalid" in texto


def test_credenciais_antigo_ganha_bloco_novo_sem_perder_o_que_tinha(tmp_path):
    """Quem conectou o Meli antes da Shopee existir precisa receber as linhas
    novas ao atualizar — senao a skill manda preencher o que nao esta la."""
    cred = tmp_path / "credenciais.txt"
    cred.write_text("MELI_APP_ID=123\nMELI_CLIENT_SECRET=abc\n", encoding="utf-8")
    pasta_mod.preparar(tmp_path)
    texto = cred.read_text(encoding="utf-8")
    assert "MELI_APP_ID=123" in texto, "nao pode perder o que a pessoa preencheu"
    assert "MELI_CLIENT_SECRET=abc" in texto
    for chave in ("SHOPEE_PARTNER_ID", "SHOPEE_PARTNER_KEY", "SHOPEE_REDIRECT_URI"):
        assert chave in texto


def test_nao_duplica_bloco_quando_roda_de_novo(tmp_path):
    pasta_mod.preparar(tmp_path)
    pasta_mod.preparar(tmp_path)
    texto = (tmp_path / "credenciais.txt").read_text(encoding="utf-8")
    assert texto.count("SHOPEE_PARTNER_ID") == 1


def test_nao_mexe_em_bloco_que_a_pessoa_ja_preencheu(tmp_path):
    cred = tmp_path / "credenciais.txt"
    cred.write_text("SHOPEE_PARTNER_ID=999\nSHOPEE_PARTNER_KEY=k\nSHOPEE_REDIRECT_URI=https://x.supabase.co\n",
                    encoding="utf-8")
    pasta_mod.preparar(tmp_path)
    texto = cred.read_text(encoding="utf-8")
    assert "SHOPEE_PARTNER_ID=999" in texto
    assert texto.count("SHOPEE_PARTNER_ID") == 1


# ------------------------------------------------------------------- olist
#
# OAuth2 padrao (Keycloak da Tiny). O que muda o desenho: o access_token vale 4
# horas e o refresh vale 1 DIA. Conexao viva morreria entre um uso e outro,
# entao a skill IMPORTA o custo para a pasta e o painel usa o arquivo.

import olist  # noqa: E402


def test_link_de_autorizacao_e_o_keycloak_da_tiny():
    from urllib.parse import urlparse, parse_qs
    u = olist.link_de_autorizacao("meu-id", "https://x.supabase.co")
    p = urlparse(u)
    assert p.netloc == "accounts.tiny.com.br"
    assert p.path == "/realms/tiny/protocol/openid-connect/auth"
    q = parse_qs(p.query)
    assert q["client_id"] == ["meu-id"]
    assert q["redirect_uri"] == ["https://x.supabase.co"]
    assert q["response_type"] == ["code"]
    assert q["scope"] == ["openid"]


def test_le_o_code_do_endereco_colado():
    assert olist.ler_retorno("https://x.supabase.co/?code=abc123&state=y") == "abc123"


def test_retorno_sem_code_explica():
    with pytest.raises(ValueError, match="code"):
        olist.ler_retorno("https://x.supabase.co/")


def test_cliente_olist_recusa_metodo_que_nao_seja_get():
    for metodo in ("POST", "PUT", "DELETE", "patch"):
        with pytest.raises(PermissionError):
            olist.api(metodo, "/produtos/1/preco")


def test_refresh_vencido_diz_para_reconectar_em_vez_de_erro_cru(tmp_path, monkeypatch):
    """1 dia e pouco: vai acontecer com quase todo mundo. A mensagem tem de
    dizer o que fazer, nao devolver o erro cru do servidor."""
    import json, time
    f = tmp_path / "tokens-olist.json"
    f.write_text(json.dumps({
        "access_token": "x", "refresh_token": "y",
        "expires_at": int(time.time()) - 10,
        "refresh_expires_at": int(time.time()) - 10,
    }), encoding="utf-8")
    monkeypatch.setattr(olist, "TOKENS_FILE", f)
    with pytest.raises(olist.PrecisaReconectar, match="(?i)reconect"):
        olist.token_valido("id", "segredo")


def test_custo_importado_vira_arquivo_na_pasta(tmp_path, monkeypatch):
    """O painel le o arquivo, nao a API: a margem funciona dias depois, com a
    conexao ja vencida."""
    import json
    monkeypatch.setattr(olist, "CUSTOS_FILE", tmp_path / "prometheus-custos.json")
    r = olist.gravar_custos([{"sku": "ABC", "preco_custo": 12.5, "custo_medio": 11.0}])
    assert r["itens"] == 1
    d = json.loads((tmp_path / "prometheus-custos.json").read_text(encoding="utf-8"))
    assert d["fonte"] == "olist"
    assert d["itens"][0]["sku"] == "ABC"
    assert "capturado_em" in d


def test_credenciais_ganham_o_bloco_do_olist(tmp_path):
    pasta_mod.preparar(tmp_path)
    texto = (tmp_path / "credenciais.txt").read_text(encoding="utf-8")
    for chave in ("OLIST_CLIENT_ID", "OLIST_CLIENT_SECRET", "OLIST_REDIRECT_URI"):
        assert chave in texto


def test_pasta_antiga_ganha_os_dois_blocos_novos(tmp_path):
    """Quem conectou so o Meli recebe Shopee E Olist ao atualizar."""
    cred = tmp_path / "credenciais.txt"
    cred.write_text("MELI_APP_ID=123\n", encoding="utf-8")
    r = pasta_mod.preparar(tmp_path)
    assert set(r["acrescentados"]) == {"SHOPEE_PARTNER_ID", "OLIST_CLIENT_ID"}
    texto = cred.read_text(encoding="utf-8")
    assert "MELI_APP_ID=123" in texto
    assert texto.count("OLIST_CLIENT_ID") == 1


def test_arquivos_do_olist_sao_tratados_como_sensiveis(tmp_path):
    for nome in ("tokens-olist.json", "ABRIR_OLIST.txt", "RETORNO_OLIST.txt"):
        assert nome in pasta_mod.ARQUIVOS_SENSIVEIS
    pasta_mod.preparar(tmp_path)
    gi = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    for nome in ("tokens-olist.json", "ABRIR_OLIST.txt", "RETORNO_OLIST.txt"):
        assert nome in gi


# =============================================================================
# Revisao cross-vendor de 22/10/2026 (lente Cypher). Cada teste abaixo trava um
# apontamento que BLOQUEOU o merge das conexoes Shopee e Olist. O que eles
# protegem nao e um detalhe de implementacao: e a promessa de que o segredo do
# vendedor nao escapa e de que o pacote nao escreve na conta dele.
# =============================================================================

def test_segredo_nasce_fechado_sem_janela_de_exposicao(tmp_path):
    """Gravar e depois fechar deixava o token legivel por um instante.

    Em maquina compartilhada esse instante basta. Aqui o arquivo tem de chegar
    ao destino JA restrito."""
    if os.name != "posix":
        pytest.skip("o modo POSIX so e aplicado onde existe")
    destino = tmp_path / "tokens.json"
    r = seguro.gravar_protegido(destino, '{"access_token":"x"}')
    assert r["protegido"] is True
    assert destino.stat().st_mode & 0o077 == 0


def test_gravacao_interrompida_nao_destroi_o_arquivo_anterior(tmp_path, monkeypatch):
    """Truncar e reescrever perdia tudo se a maquina caisse no meio."""
    destino = tmp_path / "credenciais.txt"
    destino.write_bytes(b"MELI_APP_ID=123456\n")
    monkeypatch.setattr(seguro.os, "replace",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("caiu")))
    with pytest.raises(OSError):
        seguro.gravar_protegido(destino, "conteudo novo")
    assert destino.read_bytes() == b"MELI_APP_ID=123456\n"
    assert not list(tmp_path.glob(".tmp-*")), "sobrou temporario com segredo na pasta"


def test_nenhuma_chamada_com_credencial_segue_redirecionamento():
    """urllib reenvia o Authorization no 302 — para um host que nao escolhemos.

    Teste de varredura: qualquer urlopen cru que volte ao pacote reabre o furo,
    inclusive num script novo que ninguem lembrou de revisar."""
    cruas = []
    for arq in sorted((RAIZ / "scripts").glob("*.py")):
        if arq.name == "seguro.py":
            continue
        for n, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), 1):
            if "urlopen(" in linha and not linha.strip().startswith("#"):
                cruas.append("%s:%s" % (arq.name, n))
    assert not cruas, "urlopen cru (segue redirecionamento) em: %s" % ", ".join(cruas)


def test_redirecionamento_e_recusado_com_recado_de_gente():
    h = seguro._SemRedirecionamento()
    with pytest.raises(seguro.RedirecionamentoRecusado) as e:
        h.redirect_request(None, None, 302, "Found", {}, "https://outro-host.com/")
    assert "nao e erro seu" in str(e.value)


def test_retorno_de_outro_endereco_e_recusado_sem_ecoar_o_code():
    """O `?code=` nao pode aparecer na mensagem: ela vai para a tela e o log."""
    with pytest.raises(seguro.RetornoDeOutroEndereco) as e:
        seguro.conferir_origem("https://site-errado.com/cb?code=CODIGO_SECRETO",
                               "https://meu.supabase.co/cb")
    assert "CODIGO_SECRETO" not in str(e.value)
    assert "site-errado.com" in str(e.value)


def test_barra_final_e_porta_padrao_nao_quebram_o_retorno():
    """Rigor que recusa retorno valido viraria conexao travada na sala."""
    assert seguro.conferir_origem("https://meu.supabase.co/cb?code=1",
                                  "https://meu.supabase.co/cb/")
    assert seguro.conferir_origem("https://meu.supabase.co:443/cb?code=1",
                                  "https://meu.supabase.co/cb")


def test_shopee_so_faz_post_nos_dois_caminhos_da_conexao():
    """A promessa de somente leitura vale pouco se existir um POST generico."""
    with pytest.raises(PermissionError) as e:
        shopee._post("/api/v2/product/update_price", {"price": 1}, 1, "chave")
    assert "somente leitura" in str(e.value)
    assert set(shopee.CAMINHOS_DE_POST) == {shopee.CAMINHO_TOKEN, shopee.CAMINHO_REFRESH}


def test_shopee_nao_repete_a_resposta_dela_na_mensagem_de_erro():
    """Se a Shopee devolver pedaco da chamada no texto, repetir e vazar."""
    msg = shopee._explicar({"error": "unknown_x",
                            "message": "access_token=SEGREDO sign=ABCDEF"})
    assert "SEGREDO" not in msg and "ABCDEF" not in msg
    assert "unknown_x" in msg


def test_shopee_recusa_retorno_com_usuario_e_senha_embutidos():
    """netloc carrega usuario:senha; a conferencia tem de ler o hostname."""
    with pytest.raises(ValueError) as e:
        shopee.conferir_retorno("https://usuario:SENHA123@loja.com/cb")
    assert "SENHA123" not in str(e.value)


def test_shopee_nao_se_engana_com_dominio_reservado_disfarcado():
    """https://ok.com@x.invalid/ tem netloc 'ok.com@x.invalid' e hostname x.invalid."""
    with pytest.raises(ValueError):
        shopee.conferir_retorno("https://ok.com@radar.invalid/cb")


def test_shopee_confere_que_o_retorno_veio_do_endereco_cadastrado():
    with pytest.raises(seguro.RetornoDeOutroEndereco):
        shopee.ler_retorno("https://outro.com/cb?code=X&shop_id=9",
                           "https://meu.supabase.co/cb")
    code, loja = shopee.ler_retorno("https://meu.supabase.co/cb?code=X&shop_id=9",
                                    "https://meu.supabase.co/cb")
    assert (code, loja) == ("X", 9)


# ------------------------------------------------- Olist: o prazo que nao era

def test_olist_nao_inventa_prazo_de_renovacao(tmp_path, monkeypatch):
    """A doc dizia 1 dia; as integracoes de producao do Marvin contradizem.

    Inventar prazo curto fazia o pacote RECUSAR renovar uma conexao que ainda
    estava boa. Sem informacao do servidor, nao se grava data."""
    monkeypatch.setattr(olist, "TOKENS_FILE", tmp_path / "tokens-olist.json")
    r = olist.salvar_tokens({"access_token": "A", "refresh_token": "R",
                             "expires_in": 21600})
    assert "refresh_expires_at" not in r


def test_olist_tenta_renovar_quando_o_servidor_nao_deu_prazo(tmp_path, monkeypatch):
    monkeypatch.setattr(olist, "TOKENS_FILE", tmp_path / "tokens-olist.json")
    olist.salvar_tokens({"access_token": "VELHO", "refresh_token": "R",
                         "expires_in": 0})
    chamou = {}

    def _falso(dados):
        chamou["grant"] = dados["grant_type"]
        return {"access_token": "NOVO", "refresh_token": "R2", "expires_in": 21600}

    monkeypatch.setattr(olist, "_form", _falso)
    assert olist.token_valido("cid", "sec") == "NOVO"
    assert chamou["grant"] == "refresh_token"


def test_olist_respeita_o_prazo_quando_o_servidor_informa(tmp_path, monkeypatch):
    """Quando a Olist diz o prazo, a gente obedece — sem chamar o servidor em vao."""
    monkeypatch.setattr(olist, "TOKENS_FILE", tmp_path / "tokens-olist.json")
    olist.salvar_tokens({"access_token": "A", "refresh_token": "R",
                         "expires_in": 0, "refresh_expires_in": 1})
    time.sleep(1.1)
    monkeypatch.setattr(olist, "_form",
                        lambda d: pytest.fail("nao devia chamar o servidor"))
    with pytest.raises(olist.PrecisaReconectar):
        olist.token_valido("cid", "sec")


def test_olist_rotacao_nao_apaga_o_refresh_de_quem_funcionava(tmp_path, monkeypatch):
    """Cada renovacao devolve refresh novo. Resposta sem refresh nao pode zerar."""
    monkeypatch.setattr(olist, "TOKENS_FILE", tmp_path / "tokens-olist.json")
    r = olist.salvar_tokens({"access_token": "B", "expires_in": 21600},
                            refresh_anterior="R_BOM")
    assert r["refresh_token"] == "R_BOM"


def test_olist_vincula_o_retorno_a_tentativa_em_andamento():
    link = olist.link_de_autorizacao("cid", "https://meu.supabase.co/cb", "ST1")
    assert "state=ST1" in link
    with pytest.raises(ValueError):
        olist.ler_retorno("https://meu.supabase.co/cb?code=X&state=OUTRO",
                          "https://meu.supabase.co/cb", "ST1")
    assert olist.ler_retorno("https://meu.supabase.co/cb?code=X&state=ST1",
                             "https://meu.supabase.co/cb", "ST1") == "X"


def test_a_skill_da_olist_explica_por_que_o_prazo_parece_contraditorio():
    """Numero sem a nuance e o que gera a briga.

    Medido no servidor em 22/10/2026: acesso de 4 horas, renovacao com 24
    horas declaradas. E cada uso da renovacao REINICIA o relogio - por isso
    quem roda integracao o dia todo jura que nunca vence, e quem abre o
    programa de vez em quando ve vencer. As duas experiencias sao reais.

    A skill pode dar o numero, desde que diga quando foi medido e que explique
    o reinicio. Sem isso, alguem na sala com Olist rodando contradiz o palco -
    e os dois estao certos."""
    texto = (RAIZ / "skills" / "prometheus-conectar-olist" / "SKILL.md").read_text(
        encoding="utf-8")
    assert "reinicia" in texto.lower(), "falta explicar que o prazo reinicia a cada uso"
    assert "22/10/2026" in texto, "numero sem data de medicao vira chute em tres meses"
    minusculo = texto.lower()
    for errado in ("vence em 1 dia", "o refresh dura apenas 1 dia",
                   "30 chamadas por minuto"):
        assert errado not in minusculo, "a skill voltou a afirmar '%s'" % errado


def test_o_codigo_da_olist_nao_afirma_prazo_de_renovacao():
    """No codigo o prazo so pode vir do servidor, nunca de constante nossa."""
    texto = (RAIZ / "scripts" / "olist.py").read_text(encoding="utf-8")
    assert "86400" not in texto
    for frase in ("refresh de 1 dia", "vale 1 DIA", "vale um dia"):
        assert frase not in texto


# ------------------------------------------- migracao: bytes do usuario intactos

def test_migracao_preserva_fim_de_linha_do_windows(tmp_path):
    """Ler como texto e regravar convertia CRLF, mudando bytes que ela digitou."""
    cred = tmp_path / "credenciais.txt"
    cred.write_bytes(b"MELI_APP_ID=123\r\nMELI_CLIENT_SECRET=abc\r\n")
    pasta_mod.completar_credenciais(cred)
    bruto = cred.read_bytes()
    assert bruto.startswith(b"MELI_APP_ID=123\r\nMELI_CLIENT_SECRET=abc\r\n")
    assert b"SHOPEE_PARTNER_ID" in bruto and b"OLIST_CLIENT_ID" in bruto


def test_migracao_nao_mexe_em_arquivo_que_ja_tem_tudo(tmp_path):
    cred = tmp_path / "credenciais.txt"
    pasta_mod.preparar(tmp_path)
    antes = cred.read_bytes()
    assert pasta_mod.completar_credenciais(cred) == []
    assert cred.read_bytes() == antes


# ---------------------------- segunda rodada da revisao: o que ficou parcial

def test_endereco_malformado_nao_devolve_o_proprio_texto_no_erro():
    """O .port do urllib levanta ValueError com o texto colado na mensagem.

    Quem chama imprime a excecao — e numa gravacao de tela isso poe o `?code=`
    em video. O erro tem de ser nosso, sem interpolar nada."""
    with pytest.raises(ValueError) as e:
        seguro.conferir_origem("https://host:NAOEPORTA/cb?code=CODIGO_SECRETO",
                               "https://meu.supabase.co/cb")
    assert "CODIGO_SECRETO" not in str(e.value)
    assert "NAOEPORTA" not in str(e.value)


def test_so_codigo_com_forma_de_codigo_e_repetido():
    """Filtrar caractere nao bastava: um token minusculado passava pelo filtro.

    A conferencia e no valor CRU e exige snake_case — forma que credencial
    nao tem."""
    assert "error_param" in shopee._explicar({"error": "error_param"})
    # Formas que uma credencial tem: base64, o mesmo base64 minusculado (que
    # era o furo), maiusculas, palavra longa sem sublinhado, e cauda comprida.
    for falso in ("eyJhbGciOiJSUzI1NiJ9abc", "eyjhbgcioijsuzi1nij9abc",
                  "ZXVTT1VVTVRPS0VOREVURVNURQ", "abcdefghijklmnopqrst", "a" * 40):
        msg = shopee._explicar({"error": falso})
        assert falso not in msg and falso.lower() not in msg, \
            "ecoou %r na mensagem de erro" % falso


def test_shopee_exige_tentativa_em_andamento_nesta_maquina():
    """A Shopee nao tem state; o vinculo com a tentativa e local.

    Sem isso, a mesma URL de retorno serviria duas vezes — e o refresh da
    Shopee e de uso unico: a segunda troca derruba a conexao que funcionou."""
    import autorizar_shopee as a
    assert a.PEDIDO.name == ".oauth_state_shopee"
    assert a.VALIDADE_PEDIDO > 0
    assert a._pedido_em_andamento() is None, "sem arquivo, nao ha tentativa"


def test_pedido_vencido_nao_vale_como_tentativa(tmp_path, monkeypatch):
    import autorizar_shopee as a
    pedido = tmp_path / ".oauth_state_shopee"
    monkeypatch.setattr(a, "PEDIDO", pedido)
    monkeypatch.setattr(a, "VALIDADE_PEDIDO", 60)
    pedido.write_text(json.dumps({"em": int(time.time()) - 600,
                                  "redirect": "https://x.co/cb"}), encoding="utf-8")
    assert a._pedido_em_andamento() is None
    pedido.write_text(json.dumps({"em": int(time.time()),
                                  "redirect": "https://x.co/cb"}), encoding="utf-8")
    assert a._pedido_em_andamento()["redirect"] == "https://x.co/cb"


def test_os_vinculos_de_tentativa_sao_tratados_como_sensiveis(tmp_path):
    for nome in (".oauth_state", ".oauth_state_olist", ".oauth_state_shopee"):
        assert nome in pasta_mod.ARQUIVOS_SENSIVEIS
    pasta_mod.preparar(tmp_path)
    gi = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    for nome in (".oauth_state_olist", ".oauth_state_shopee"):
        assert nome in gi


def test_tudo_que_e_sensivel_tambem_fica_fora_do_git(tmp_path):
    """As duas listas divergiam: canal novo entrava numa e faltava na outra.

    Quem versionasse a pasta commitava o segredo do canal esquecido."""
    pasta_mod.preparar(tmp_path)
    gi = (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()
    for nome in pasta_mod.ARQUIVOS_SENSIVEIS:
        assert nome in gi, "%s e sensivel mas nao esta no .gitignore" % nome


def test_tentativa_e_gasta_antes_da_troca_e_nao_depois(tmp_path, monkeypatch):
    """Consumir depois deixava duas execucoes simultaneas trocarem o mesmo code.

    O refresh destes canais e de uso unico: a segunda troca derrubaria a
    conexao que a primeira acabou de criar."""
    import autorizar_shopee as a
    pedido = tmp_path / ".oauth_state_shopee"
    monkeypatch.setattr(a, "PEDIDO", pedido)
    pedido.write_text("{}", encoding="utf-8")
    a._consumir(pedido, "python3 autorizar_shopee.py")
    assert not pedido.exists(), "a tentativa tem de ser gasta"
    # Segunda execucao: nao acha tentativa e para, em vez de trocar de novo.
    with pytest.raises(SystemExit) as e:
        a._consumir(pedido, "python3 autorizar_shopee.py")
    assert "passo 1" in str(e.value)


def test_falha_ao_gastar_a_tentativa_para_o_fluxo(tmp_path, monkeypatch):
    """Sem conseguir gastar, nao da para garantir uso unico — entao para."""
    import autorizar_olist as a
    estado = tmp_path / ".oauth_state_olist"
    estado.write_text("{}", encoding="utf-8")

    class _Travado(type(estado)):
        def unlink(self, *a, **k):
            raise OSError("travado")

    with pytest.raises(SystemExit) as e:
        a._consumir(_Travado(estado), "python3 autorizar_olist.py")
    assert "uma unica vez" in str(e.value)


def test_code_sobrevive_ao_redirecionamento_do_app_da_pessoa(tmp_path):
    """Ensaio de 22/10/2026, com aplicativo real em producao.

    O app recebeu a visita sem sessao, mandou para /login e levou a URL
    original DENTRO de um parametro, percent-encoded. O code estava la, um
    nivel abaixo - e o pacote dizia "nao achei o code" para alguem que tinha
    autorizado certinho. Quem nao sabe o que e percent-encoding nao tem como
    adivinhar isso, e desistiria da conexao."""
    nivel_de_cima = "https://loja.vercel.app/?code=ABC123&shop_id=99"
    aninhado = "https://loja.vercel.app/login?redirect=%2F%3Fcode%3DABC123%26shop_id%3D99"
    assert shopee.ler_retorno(nivel_de_cima) == ("ABC123", 99)
    assert shopee.ler_retorno(aninhado) == ("ABC123", 99)


def test_redirecionamento_para_outro_caminho_do_mesmo_dominio_e_aceito():
    """O dominio e onde mora a protecao; o caminho muda a cada redirect.

    Exigir caminho identico fazia o pacote recusar retorno legitimo de
    qualquer aplicativo com login - conferido no mesmo ensaio."""
    assert shopee.ler_retorno(
        "https://loja.vercel.app/login?code=X&shop_id=7",
        "https://loja.vercel.app/") == ("X", 7)
    with pytest.raises(seguro.RetornoDeOutroEndereco):
        shopee.ler_retorno("https://outro-dominio.com/?code=X",
                           "https://loja.vercel.app/")


def test_custo_vem_do_detalhe_do_produto_e_nao_do_endpoint_de_gravar(monkeypatch):
    """Descoberto contra o servidor em 22/10/2026, na vespera da gravacao.

    O codigo lia /produtos/{id}/preco. Esse recurso existe, mas e de GRAVAR
    preco: em GET responde 400, "O metodo GET nao e compativel com o recurso
    solicitado". A skill prometia o custo que fecha a margem e entregava erro
    em 100% das vezes - e nenhum teste pegava, porque nenhum chamava a API.

    O detalhe do produto traz custo, custo medio e historico numa chamada so,
    o que importa porque o limite de chamadas e da conta inteira."""
    chamadas = []

    def falso(metodo, caminho, token=None, **p):
        chamadas.append(caminho)
        return {"sku": "ABC",
                "precos": {"preco": 100, "precoCusto": 50, "precoCustoMedio": 48},
                "custos": [{"data": "2026-01-01", "precoCusto": 40},
                           {"data": "2026-10-01", "precoCusto": 50}]}

    monkeypatch.setattr(olist, "api", falso)
    r = olist.custo_do_produto(77, token="t")
    assert chamadas == ["/produtos/77"], "tem de ler o detalhe, numa chamada so"
    assert not any("/preco" in c for c in chamadas), "endpoint de gravar preco de novo"
    assert r["preco_custo"] == 50 and r["custo_medio"] == 48
    assert r["custo_mais_recente_em"] == "2026-10-01"


def test_produto_sem_custo_cadastrado_fica_sem_margem_e_nao_com_zero(monkeypatch):
    """Dado ausente nao e zero: margem calculada com custo zero parece otima."""
    monkeypatch.setattr(olist, "api",
                        lambda *a, **k: {"sku": "X", "precos": {}, "custos": []})
    r = olist.custo_do_produto(1, token="t")
    assert r["preco_custo"] is None and r["custo_medio"] is None
    assert r["custo_mais_recente_em"] is None


# --------------------------------- negativos dos afrouxamentos da 1.1.1

CADASTRADO = "https://loja-dela.app/"


def test_code_aninhado_so_vale_quando_aponta_para_o_mesmo_lugar():
    """O afrouxamento que fez a conexao funcionar tambem abria uma porta.

    Procurar o code dentro de qualquer parametro aceitava
    `https://loja-dela.app/login?x=https%3A%2F%2Fatacante%2F%3Fcode%3D...`:
    a origem de FORA estava certa, e so a de dentro e que nao. Bastava
    convencer a pessoa a colar essa barra.

    Vale o nivel de dentro quando ele e relativo (o caso real do ensaio) ou
    quando aponta para o proprio dominio cadastrado."""
    assert shopee.ler_retorno(
        "https://loja-dela.app/login?redirect=%2F%3Fcode%3DBOM%26shop_id%3D7",
        CADASTRADO) == ("BOM", 7)
    assert shopee.ler_retorno(
        "https://loja-dela.app/login?r=https%3A%2F%2Floja-dela.app%2F%3Fcode%3DBOM",
        CADASTRADO) == ("BOM", None)
    with pytest.raises(ValueError):
        shopee.ler_retorno(
            "https://loja-dela.app/login?x=https%3A%2F%2Fatacante.example%2F%3Fcode%3DMAU",
            CADASTRADO)


def test_sem_endereco_cadastrado_nao_colhe_code_de_outro_host():
    """Sem com o que comparar, o nivel de dentro com host nao e confiavel."""
    with pytest.raises(ValueError):
        shopee.ler_retorno(
            "https://qualquer.app/login?x=https%3A%2F%2Fatacante.example%2F%3Fcode%3DMAU")


def test_o_vinculo_da_shopee_com_a_tentativa_e_local_e_de_uso_unico():
    """A Shopee nao tem `state`. O vinculo existe, mas e local e nao
    criptografico — limitacao conhecida, registrada na 1.1.1."""
    import autorizar_shopee as a
    assert a.PEDIDO.name == ".oauth_state_shopee"
    assert a.VALIDADE_PEDIDO > 0
    assert hasattr(a, "_consumir")


# ------------------------------------------------------------- prometheus-pedidos

class _PedidosFalsos:
    """Responde /orders/search por pagina. Registra o que foi pedido."""

    def __init__(self, paginas, erro_na_pagina=None):
        self.paginas = paginas
        self.erro_na_pagina = erro_na_pagina
        self.chamadas = []

    def __call__(self, metodo, path, params=None):
        self.chamadas.append((metodo, path, dict(params or {})))
        assert metodo == "GET", "o leitor nao pode fazer nada alem de GET"
        assert path == "/orders/search", "endpoint inesperado: %s" % path
        n = int((params or {}).get("offset", 0)) // 50
        if self.erro_na_pagina is not None and n == self.erro_na_pagina:
            raise pedidos.meli.ErroDaAPI(502, "o servidor caiu")
        pagina = self.paginas[n] if n < len(self.paginas) else []
        return {"results": pagina, "paging": {"total": sum(len(p) for p in self.paginas)}}


def _pedido(pid, valor=100.0, pago=None, situacao="paid", linhas=None, moeda="BRL", **extra):
    d = {
        "id": pid,
        "date_created": "2026-10-18T10:00:00.000-03:00",
        "status": situacao,
        "total_amount": valor,
        "paid_amount": valor if pago is None else pago,
        "currency_id": moeda,
        "buyer": {"id": 999, "nickname": "COMPRADOR", "first_name": "Fulano"},
        "order_items": [dict({"item": {"id": "MLB1", "title": "Serra"},
                              "quantity": 1, "unit_price": valor,
                              "sale_fee": round(valor * 0.14, 2)
                              if isinstance(valor, float) else None}, **(l or {}))
                        for l in (linhas if linhas is not None else [{}])],
    }
    d.update(extra)
    return d


@pytest.fixture
def pedidos_api(monkeypatch):
    def instalar(paginas, erro_na_pagina=None):
        falsa = _PedidosFalsos(paginas, erro_na_pagina)
        monkeypatch.setattr(pedidos.meli, "request", falsa)
        monkeypatch.setattr(pedidos.meli, "conta_conectada",
                            lambda: {"id": 7, "apelido": "LOJA", "site": "MLB"})
        return falsa
    return instalar


def test_pedidos_soma_so_o_que_esta_pago(pedidos_api):
    pedidos_api([[_pedido("a", 100.0), _pedido("b", 50.0, situacao="cancelled")]])
    d = pedidos.coletar(hoje=HOJE)
    assert d["resumo"]["faturamento"] == 100.0
    assert d["resumo"]["pedidos_pagos"] == 1


def test_pedidos_cancelado_nao_some_calado(pedidos_api):
    pedidos_api([[_pedido("a", 100.0), _pedido("b", 50.0, situacao="cancelled")]])
    d = pedidos.coletar(hoje=HOJE)
    assert any("cancel" in a.lower() for a in d["avisos"])


def test_pedidos_deduplica_por_id(pedidos_api):
    pedidos_api([[_pedido("a", 100.0)] * 50, [_pedido("a", 100.0)]])
    d = pedidos.coletar(hoje=HOJE)
    assert d["resumo"]["pedidos_pagos"] == 1
    assert d["resumo"]["faturamento"] == 100.0


def test_pedidos_pago_sem_valor_nao_soma_e_marca_parcial(pedidos_api):
    pedidos_api([[_pedido("a", 100.0), _pedido("b", None)]])
    d = pedidos.coletar(hoje=HOJE)
    assert d["resumo"]["faturamento"] == 100.0
    assert d["resumo"]["completo"] is False
    assert any("sem valor" in a.lower() for a in d["avisos"])


def test_pedidos_linha_sem_tarifa_vira_null_no_item(pedidos_api):
    pedidos_api([[_pedido("a", 100.0, linhas=[{"sale_fee": None}])]])
    d = pedidos.coletar(hoje=HOJE)
    assert d["itens"][0]["linhas"][0]["tarifa_por_unidade"] is None
    assert d["itens"][0]["linhas"][0]["tarifa_da_linha"] is None
    assert d["resumo"]["comissao_total"] is None
    assert "comissao_total" in d["faltando"]


def test_pedidos_tarifa_e_por_unidade_entao_multiplica_pela_quantidade(pedidos_api):
    # Medido contra conta real: o mesmo anuncio em quantidades diferentes manteve a
    # tarifa quase igual. Tratar como total da linha dividiria a comissao pela
    # quantidade, e o numero continuaria plausivel.
    pedidos_api([[_pedido("a", 100.0, linhas=[{"quantity": 10, "unit_price": 10.0,
                                               "sale_fee": 1.67}])]])
    d = pedidos.coletar(hoje=HOJE)
    linha = d["itens"][0]["linhas"][0]
    assert linha["tarifa_por_unidade"] == 1.67
    assert linha["tarifa_da_linha"] == 16.7
    assert d["resumo"]["comissao_total"] == 16.7


def test_pedidos_diz_o_que_a_comissao_nao_cobre(pedidos_api):
    pedidos_api([[_pedido("a", 100.0)]])
    d = pedidos.coletar(hoje=HOJE)
    assert any("estorno" in a for a in d["avisos"])


def test_pedidos_comissao_nao_soma_entre_moedas(pedidos_api):
    pedidos_api([[_pedido("a", 100.0), _pedido("b", 50.0, moeda="USD")]])
    d = pedidos.coletar(hoje=HOJE)
    assert d["resumo"]["comissao_total"] is None


def test_pedidos_duas_moedas_nao_somam(pedidos_api):
    pedidos_api([[_pedido("a", 100.0), _pedido("b", 50.0, moeda="USD")]])
    d = pedidos.coletar(hoje=HOJE)
    assert d["resumo"]["faturamento"] is None
    assert "faturamento" in d["faltando"]
    assert "moeda" in d["lacunas"]["faturamento"].lower()


def test_pedidos_sem_itens_vira_aviso(pedidos_api):
    pedidos_api([[_pedido("a", 100.0, linhas=[])]])
    d = pedidos.coletar(hoje=HOJE)
    assert any("sem item" in a.lower() for a in d["avisos"])


def test_pedidos_vazio_nao_e_falha_e_zero_e_zero_mesmo(pedidos_api):
    pedidos_api([[]])
    d = pedidos.coletar(hoje=HOJE)
    assert d["resumo"]["pedidos_pagos"] == 0
    assert d["resumo"]["faturamento"] == 0.0
    assert d["resumo"]["completo"] is True


def test_pedidos_falha_na_primeira_pagina_nao_devolve_zero_vendas(pedidos_api):
    pedidos_api([[_pedido("a")]], erro_na_pagina=0)
    with pytest.raises(pedidos.meli.ErroDaAPI):
        pedidos.coletar(hoje=HOJE)


def test_pedidos_falha_no_meio_vira_coleta_parcial(pedidos_api):
    pedidos_api([[_pedido(str(i)) for i in range(50)], [_pedido("x")]], erro_na_pagina=1)
    d = pedidos.coletar(hoje=HOJE)
    assert d["resumo"]["completo"] is False
    assert any("parcial" in a.lower() for a in d["avisos"])


def test_pedidos_nao_guarda_dado_do_comprador(pedidos_api):
    pedidos_api([[_pedido("a", 100.0)]])
    bruto = json.dumps(pedidos.coletar(hoje=HOJE), ensure_ascii=False)
    assert "COMPRADOR" not in bruto
    assert "Fulano" not in bruto


def test_pedidos_so_pede_pela_conta_autenticada(pedidos_api):
    falsa = pedidos_api([[_pedido("a")]])
    pedidos.coletar(hoje=HOJE)
    assert all(c[2]["seller"] == 7 for c in falsa.chamadas)


def test_pedidos_fixa_a_janela_antes_da_primeira_chamada(pedidos_api):
    falsa = pedidos_api([[_pedido(str(i)) for i in range(50)], [_pedido("x")]])
    pedidos.coletar(hoje=HOJE)
    janelas = {(c[2]["order.date_created.from"], c[2]["order.date_created.to"])
               for c in falsa.chamadas}
    assert len(janelas) == 1


def test_pedidos_teto_de_paginas_avisa_sem_dizer_quantos_ficaram(pedidos_api):
    cheias = [[_pedido("p%d-%d" % (n, i)) for i in range(50)] for n in range(30)]
    pedidos_api(cheias)
    d = pedidos.coletar(hoje=HOJE)
    assert d["resumo"]["completo"] is False
    texto = " ".join(d["avisos"]).lower()
    assert "incompleta" in texto


def test_pedidos_resposta_sem_results_na_primeira_pagina_nao_e_zero_vendas(monkeypatch):
    monkeypatch.setattr(pedidos.meli, "request", lambda *a, **k: {"paging": {}})
    monkeypatch.setattr(pedidos.meli, "conta_conectada",
                        lambda: {"id": 7, "apelido": "LOJA", "site": "MLB"})
    with pytest.raises(pedidos.meli.ErroDaAPI):
        pedidos.coletar(hoje=HOJE)


def test_pedidos_registro_sem_id_e_descartado_mas_dito(pedidos_api):
    pedidos_api([[_pedido("a", 100.0), dict(_pedido("b", 50.0), id=None)]])
    d = pedidos.coletar(hoje=HOJE)
    assert d["resumo"]["completo"] is False
    assert any("sem identificação" in a for a in d["avisos"])


def test_pedidos_sem_moeda_nao_soma_com_real(pedidos_api):
    pedidos_api([[_pedido("a", 100.0), dict(_pedido("b", 50.0), currency_id=None)]])
    d = pedidos.coletar(hoje=HOJE)
    assert d["resumo"]["faturamento"] is None
    assert "sem dizer a moeda" in d["lacunas"]["faturamento"]


def test_pedidos_janela_so_em_dolar_nao_vira_reais(pedidos_api):
    pedidos_api([[_pedido("a", 100.0, moeda="USD")]])
    d = pedidos.coletar(hoje=HOJE)
    assert d["moeda"] == "USD"
    assert d["resumo"]["faturamento"] == 100.0


def test_pedidos_sem_pago_pelo_comprador_vira_null_e_nao_subtotal(pedidos_api):
    pedidos_api([[_pedido("a", 100.0), dict(_pedido("b", 50.0), paid_amount=None)]])
    d = pedidos.coletar(hoje=HOJE)
    assert d["resumo"]["pago_pelo_comprador"] is None
    assert "pago_pelo_comprador" in d["faltando"]


def test_pedidos_quantidade_faltando_nao_contamina_o_pedido_seguinte(pedidos_api):
    pedidos_api([[_pedido("a", 100.0, linhas=[{"quantity": None}]),
                  _pedido("b", 100.0, linhas=[{"quantity": 3}])]])
    d = pedidos.coletar(hoje=HOJE)
    por_id = {i["id"]: i for i in d["itens"]}
    assert por_id["a"]["unidades"] is None
    assert por_id["b"]["unidades"] == 3
    assert d["resumo"]["unidades"] is None


def test_pedidos_booleano_nao_vira_dinheiro(pedidos_api):
    pedidos_api([[_pedido("a", True)]])
    d = pedidos.coletar(hoje=HOJE)
    assert d["itens"][0]["valor"] is None
    assert d["resumo"]["completo"] is False


def test_pedidos_texto_numerico_nao_vira_dinheiro(pedidos_api):
    pedidos_api([[_pedido("a", "100.00")]])
    d = pedidos.coletar(hoje=HOJE)
    assert d["itens"][0]["valor"] is None


def test_pedidos_quantidade_quebrada_nao_e_truncada(pedidos_api):
    pedidos_api([[_pedido("a", 100.0, linhas=[{"quantity": 1.9}])]])
    d = pedidos.coletar(hoje=HOJE)
    assert d["itens"][0]["linhas"][0]["unidades"] is None


def test_pedidos_envelope_do_contrato_aceita_o_que_o_leitor_monta(pedidos_api):
    pedidos_api([[_pedido("a", 100.0), dict(_pedido("b", 50.0), currency_id=None)]])
    d = pedidos.coletar(hoje=HOJE)
    envelope = contrato.montar("prometheus-pedidos", d["conta"], d["periodo"],
                               d["resumo"], d["itens"], faltando=d["faltando"],
                               lacunas=d["lacunas"], avisos=d["avisos"],
                               moeda=d["moeda"])
    assert envelope["skill"] == "prometheus-pedidos"
    json.dumps(envelope, allow_nan=False)


# ------------------------------------------------ limite de chamadas: repetir

class _RespostaFalsa:
    def __init__(self, corpo):
        self._corpo = corpo.encode("utf-8")

    def read(self):
        return self._corpo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _erro_http(codigo, retry_after=None):
    import email.message
    cabecalhos = email.message.Message()
    if retry_after is not None:
        cabecalhos["Retry-After"] = str(retry_after)
    return urllib.error.HTTPError("https://api.mercadolibre.com/x", codigo,
                                  "nao", cabecalhos, io.BytesIO(b"{}"))


@pytest.fixture
def api_instavel(monkeypatch):
    def instalar(sequencia):
        estado = {"n": 0, "esperas": []}

        def abrir(req, timeout=None):
            item = sequencia[estado["n"]]
            estado["n"] += 1
            if isinstance(item, int):
                raise _erro_http(item)
            return _RespostaFalsa(item)

        monkeypatch.setattr(meli.seguro, "abrir", abrir)
        monkeypatch.setattr(meli, "get_access_token", lambda: "token-de-teste")
        monkeypatch.setattr(meli.time, "sleep", lambda s: estado["esperas"].append(s))
        return estado
    return instalar


def test_limite_de_chamadas_e_repetido_em_vez_de_derrubar_a_skill(api_instavel):
    estado = api_instavel([429, 429, '{"results": [1]}'])
    assert meli.request("GET", "/orders/search") == {"results": [1]}
    assert estado["esperas"] == [2.0, 5.0]


def test_falha_passageira_do_servidor_tambem_e_repetida(api_instavel):
    api_instavel([502, '{"ok": true}'])
    assert meli.request("GET", "/orders/search") == {"ok": True}


def test_nao_adianta_repetir_sem_autorizacao(api_instavel):
    estado = api_instavel([401, '{"nunca": "chega"}'])
    with pytest.raises(meli.ErroDaAPI):
        meli.request("GET", "/orders/search")
    assert estado["esperas"] == []


def test_desiste_depois_das_tentativas_combinadas(api_instavel):
    api_instavel([429, 429, 429, 429])
    with pytest.raises(meli.ErroDaAPI):
        meli.request("GET", "/orders/search")


def test_respeita_a_espera_que_o_servidor_pediu(monkeypatch):
    esperas = []
    chamadas = {"n": 0}

    def abrir(req, timeout=None):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            raise _erro_http(429, retry_after=30)
        return _RespostaFalsa('{"ok": true}')

    monkeypatch.setattr(meli.seguro, "abrir", abrir)
    monkeypatch.setattr(meli, "get_access_token", lambda: "t")
    monkeypatch.setattr(meli.time, "sleep", lambda s: esperas.append(s))
    assert meli.request("GET", "/x") == {"ok": True}
    assert esperas == [30.0]


def test_pedidos_diz_como_contou(pedidos_api):
    pedidos_api([[_pedido("a", 100.0)]])
    d = pedidos.coletar(hoje=HOJE)
    texto = " ".join(d["avisos"])
    assert "contagem:" in texto
    assert "data em que o pedido foi criado" in texto
    assert "um por pedido" in texto


def test_pedidos_quantidade_zero_nao_vira_comissao_zero(pedidos_api):
    pedidos_api([[_pedido("a", 100.0, linhas=[{"quantity": 0, "sale_fee": 1.67}])]])
    d = pedidos.coletar(hoje=HOJE)
    assert d["itens"][0]["linhas"][0]["unidades"] is None
    assert d["itens"][0]["linhas"][0]["tarifa_da_linha"] is None
    assert d["resumo"]["comissao_total"] is None


def test_pedidos_quantidade_negativa_nao_reduz_o_total(pedidos_api):
    pedidos_api([[_pedido("a", 100.0, linhas=[{"quantity": -3, "sale_fee": 1.67}])]])
    d = pedidos.coletar(hoje=HOJE)
    assert d["itens"][0]["linhas"][0]["unidades"] is None
    assert d["resumo"]["comissao_total"] is None


def test_pedidos_quantidade_infinita_nao_derruba_a_coleta(pedidos_api):
    pedidos_api([[_pedido("a", 100.0, linhas=[{"quantity": float("inf")}]),
                  _pedido("b", 100.0, linhas=[{"quantity": float("nan")}])]])
    d = pedidos.coletar(hoje=HOJE)
    assert all(l["unidades"] is None for i in d["itens"] for l in i["linhas"])


def test_pedidos_multiplicacao_que_estoura_vira_null(pedidos_api):
    pedidos_api([[_pedido("a", 100.0, linhas=[{"quantity": 2, "sale_fee": 1e308}])]])
    d = pedidos.coletar(hoje=HOJE)
    assert d["itens"][0]["linhas"][0]["tarifa_da_linha"] is None
    assert d["resumo"]["comissao_total"] is None


def test_pedidos_comissao_nao_e_total_quando_a_coleta_foi_parcial(pedidos_api):
    pedidos_api([[_pedido(str(i)) for i in range(50)], [_pedido("x")]], erro_na_pagina=1)
    d = pedidos.coletar(hoje=HOJE)
    assert d["resumo"]["completo"] is False
    assert d["resumo"]["comissao_total"] is None
    assert "comissao_total" in d["faltando"]


def test_pedidos_comissao_nao_e_total_quando_houve_registro_descartado(pedidos_api):
    pedidos_api([[_pedido("a", 100.0), dict(_pedido("b", 50.0), id=None)]])
    d = pedidos.coletar(hoje=HOJE)
    assert d["resumo"]["comissao_total"] is None
