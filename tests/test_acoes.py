"""Testes do modulo de escrita (pacote prometheus-acoes).

Rodar:  python3 -m pytest tests -q        (na raiz do repositorio)

A matriz que estes testes cobrem esta na spec, em
elo/docs/imersao-v2/spec-escrita.md, secao "Como se prova que isto funciona".
"""
import json
import re
import os
import urllib.error
import io
import sys
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ / "acoes" / "scripts"))

import meli  # noqa: E402
import escrever  # noqa: E402
import promover  # noqa: E402
import responder  # noqa: E402

CONTA = 169750742
OFERTAS = "urn:ml:mktp:offers:/read-write"
PERGUNTAS = "urn:ml:mktp:comunication:/read-write"


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    """Pasta de trabalho isolada, com escopo completo concedido."""
    monkeypatch.setattr(escrever, "BASE", tmp_path)
    monkeypatch.setattr(escrever, "TOKENS", tmp_path / "tokens.json")
    monkeypatch.setattr(escrever, "RECIBO", tmp_path / "acoes.txt")
    monkeypatch.setattr(escrever, "INTENCOES", tmp_path / "intencoes.json")
    (tmp_path / "tokens.json").write_text(json.dumps({
        "user_id": CONTA,
        "access_token": "TOKEN-SECRETO",
        "refresh_token": "RENOVA-SECRETO",
        "scope": "read write offline_access %s %s" % (OFERTAS, PERGUNTAS),
    }), encoding="utf-8")
    monkeypatch.setattr(escrever.meli, "get_access_token", lambda: "TOKEN-SECRETO")
    monkeypatch.setattr(escrever, "esperar", lambda s: None)
    return tmp_path


def _resposta(corpo, status=201):
    class R:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps(corpo).encode()
    return R()


def _http(status, corpo):
    return urllib.error.HTTPError(
        "https://api.mercadolibre.com/x", status, "erro", {},
        io.BytesIO(json.dumps(corpo).encode()))


# ------------------------------------------------- a trava antiga continua la

def test_a_trava_de_leitura_nao_foi_tocada():
    with pytest.raises(PermissionError):
        meli.request("POST", "/seller-promotions/items/MLB1")


def test_nenhum_leitor_importa_o_modulo_de_escrita():
    for nome in ("pedidos", "promocoes", "devolucoes", "anuncios", "painel",
                 "planilha", "meli", "pasta", "contrato"):
        fonte = (RAIZ / "scripts" / (nome + ".py")).read_text(encoding="utf-8")
        assert "import escrever" not in fonte, nome
        assert "import promover" not in fonte, nome


# ------------------------------------------- a porta so faz o que esta na lista

def test_acao_que_nao_existe_e_recusada(pasta):
    with pytest.raises(escrever.AcaoRecusada):
        escrever.enviar("apagar_anuncio", "/items/MLB1")


def test_caminho_fora_do_padrao_da_acao_e_recusado(pasta):
    with pytest.raises(escrever.AcaoRecusada):
        escrever.enviar("aderir", "/items/MLB123")


def test_endereco_completo_no_lugar_do_caminho_e_recusado(pasta):
    with pytest.raises(escrever.AcaoRecusada):
        escrever.enviar("aderir", "https://outro.example/seller-promotions/items/MLB1")


def test_a_porta_monta_o_endereco_no_host_fixo_e_em_https(pasta, monkeypatch):
    vistos = []

    def falso(req, timeout=30):
        vistos.append(req.full_url)
        return _resposta({"ok": True})

    monkeypatch.setattr(escrever.seguro, "abrir", falso)
    escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                    corpo={"promotion_id": "P-1"})
    assert vistos[0].startswith("https://api.mercadolibre.com/")


def test_redirecionamento_nao_entrega_o_token(pasta, monkeypatch):
    def falso(req, timeout=30):
        raise escrever.seguro.RedirecionamentoRecusado("302")

    monkeypatch.setattr(escrever.seguro, "abrir", falso)
    with pytest.raises(escrever.seguro.RedirecionamentoRecusado):
        escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                        corpo={"promotion_id": "P-1"})


def test_mensagem_de_erro_nunca_carrega_o_token(pasta, monkeypatch):
    monkeypatch.setattr(escrever.seguro, "abrir",
                        lambda req, timeout=30: (_ for _ in ()).throw(
                            _http(400, {"message": "falhou com TOKEN-SECRETO"})))
    with pytest.raises(escrever.ErroNaEscrita) as e:
        escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                        corpo={"promotion_id": "P-1"})
    assert "TOKEN-SECRETO" not in str(e.value)


# ------------------------------------------------------------------ permissao

def test_sem_o_escopo_da_superficie_nao_sai_nada(pasta):
    (pasta / "tokens.json").write_text(json.dumps({
        "user_id": CONTA, "scope": "read write urn:ml:mktp:offers:/read-only"}),
        encoding="utf-8")
    with pytest.raises(escrever.SemPermissao):
        escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                        corpo={"promotion_id": "P-1"})


def test_escopo_de_escrita_de_outra_superficie_nao_serve(pasta):
    """O furo da v1 da spec: qualquer /read-write satisfazia o gate."""
    (pasta / "tokens.json").write_text(json.dumps({
        "user_id": CONTA, "scope": "read write urn:ml:mktp:ads:/read-write"}),
        encoding="utf-8")
    with pytest.raises(escrever.SemPermissao):
        escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                        corpo={"promotion_id": "P-1"})


def test_escopo_de_promocao_nao_autoriza_responder_pergunta(pasta):
    (pasta / "tokens.json").write_text(json.dumps({
        "user_id": CONTA, "scope": "read write " + OFERTAS}), encoding="utf-8")
    with pytest.raises(escrever.SemPermissao):
        escrever.enviar("responder", "/answers", corpo={"question_id": 1, "text": "x"})


def test_403_de_politica_manda_reautorizar(pasta, monkeypatch):
    monkeypatch.setattr(escrever.seguro, "abrir",
                        lambda req, timeout=30: (_ for _ in ()).throw(_http(403, {
                            "cause": [{"error_code": "PA_UNAUTHORIZED_RESULT_FROM_POLICIES"}]})))
    with pytest.raises(escrever.SemPermissao) as e:
        escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                        corpo={"promotion_id": "P-1"})
    assert "autoriz" in str(e.value).lower()


def test_outro_403_nao_manda_reautorizar_por_chute(pasta, monkeypatch):
    monkeypatch.setattr(escrever.seguro, "abrir",
                        lambda req, timeout=30: (_ for _ in ()).throw(_http(403, {
                            "cause": [{"error_code": "ALGO_QUE_NAO_CONHECO"}]})))
    with pytest.raises(escrever.ErroNaEscrita) as e:
        escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                        corpo={"promotion_id": "P-1"})
    assert not isinstance(e.value, escrever.SemPermissao)
    assert "ALGO_QUE_NAO_CONHECO" in str(e.value)


# -------------------------------------------------------- intencao e conferencia

def _intencao(pasta, **extra):
    base = {"conta": CONTA, "acao": "aderir", "anuncio": "MLB123",
            "campanha": "P-1", "tipo": "SELLER_CAMPAIGN",
            "valores": {"preco_hoje": 100.0, "preco_na_campanha": 80.0}}
    base.update(extra)
    return escrever.guardar_intencao(base)


def test_codigo_vencido_e_recusado(pasta, monkeypatch):
    cod = _intencao(pasta)
    depois = time.time() + 601
    monkeypatch.setattr(escrever.time, "time", lambda: depois)
    with pytest.raises(escrever.ConferenciaInvalida):
        escrever.consumir_intencao(cod)


def test_codigo_vale_uma_vez(pasta):
    cod = _intencao(pasta)
    escrever.consumir_intencao(cod)
    with pytest.raises(escrever.ConferenciaInvalida):
        escrever.consumir_intencao(cod)


def test_codigo_de_outra_conta_nao_serve(pasta):
    cod = _intencao(pasta, conta=999)
    with pytest.raises(escrever.ConferenciaInvalida):
        escrever.consumir_intencao(cod)


def test_codigo_desconhecido_e_recusado(pasta):
    with pytest.raises(escrever.ConferenciaInvalida):
        escrever.consumir_intencao("ZZZZ")


def test_valores_diferentes_geram_codigos_diferentes(pasta):
    a = _intencao(pasta)
    b = _intencao(pasta, valores={"preco_hoje": 100.0, "preco_na_campanha": 79.0})
    assert a != b


# ------------------------------------------------------------------- recibo

def test_acao_sem_recibo_nao_acontece(pasta, monkeypatch):
    travada = pasta / "travada"
    travada.mkdir()
    (travada / "acoes.txt").write_text("", encoding="utf-8")
    os.chmod(travada / "acoes.txt", 0o400)
    monkeypatch.setattr(escrever, "RECIBO", travada / "acoes.txt")
    chamou = []
    monkeypatch.setattr(escrever.seguro, "abrir",
                        lambda req, timeout=30: chamou.append(1) or _resposta({}))
    with pytest.raises(escrever.ReciboImpossivel):
        escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                        corpo={"promotion_id": "P-1"}, anuncio="MLB123")
    assert not chamou


def test_pasta_de_recibo_que_nao_existe_tambem_recusa(pasta, monkeypatch):
    monkeypatch.setattr(escrever, "RECIBO", pasta / "nao-existe" / "acoes.txt")
    chamou = []
    monkeypatch.setattr(escrever.seguro, "abrir",
                        lambda req, timeout=30: chamou.append(1) or _resposta({}))
    with pytest.raises(escrever.ReciboImpossivel):
        escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                        corpo={"promotion_id": "P-1"}, anuncio="MLB123")
    assert not chamou


def test_a_tentativa_e_escrita_antes_do_envio(pasta, monkeypatch):
    def falso(req, timeout=30):
        assert "tentando" in (pasta / "acoes.txt").read_text(encoding="utf-8")
        return _resposta({"ok": True})

    monkeypatch.setattr(escrever.seguro, "abrir", falso)
    escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                    corpo={"promotion_id": "P-1"}, anuncio="MLB123")


def test_tentativa_sem_resultado_tranca_o_anuncio(pasta, monkeypatch):
    monkeypatch.setattr(escrever.seguro, "abrir",
                        lambda req, timeout=30: (_ for _ in ()).throw(
                            urllib.error.URLError("sem rede")))
    with pytest.raises(escrever.RespostaIncerta):
        escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                        corpo={"promotion_id": "P-1"}, anuncio="MLB123")
    assert escrever.pendencias("MLB123")
    with pytest.raises(escrever.ItemTrancado):
        escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                        corpo={"promotion_id": "P-1"}, anuncio="MLB123")


def test_pendencia_de_outro_anuncio_nao_tranca_este(pasta, monkeypatch):
    escrever.abrir_tentativa("aderir", "MLB999", "nota")
    monkeypatch.setattr(escrever.seguro, "abrir",
                        lambda req, timeout=30: _resposta({"ok": True}))
    escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                    corpo={"promotion_id": "P-1"}, anuncio="MLB123")


def test_teto_conta_o_conjunto_de_arquivos(pasta, monkeypatch):
    (pasta / "acoes.txt").write_text("x" * 10, encoding="utf-8")
    (pasta / "acoes-2026.txt").write_text("y" * 10, encoding="utf-8")
    monkeypatch.setattr(escrever, "TETO", 15)
    with pytest.raises(escrever.ReciboNoTeto):
        escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                        corpo={"promotion_id": "P-1"}, anuncio="MLB123")


def test_o_recibo_nunca_guarda_texto_de_cliente(pasta, monkeypatch):
    monkeypatch.setattr(escrever.seguro, "abrir",
                        lambda req, timeout=30: _resposta({"ok": True}))
    escrever.enviar("responder", "/answers",
                    corpo={"question_id": 42, "text": "segredo do comprador"},
                    anuncio="pergunta-42")
    assert "segredo do comprador" not in (pasta / "acoes.txt").read_text(encoding="utf-8")


# ------------------------------------------------- o fornecedor mentindo

def test_escrita_nao_repete_em_429(pasta, monkeypatch):
    tentativas = []

    def falso(req, timeout=30):
        tentativas.append(1)
        raise _http(429, {"message": "calma"})

    monkeypatch.setattr(escrever.seguro, "abrir", falso)
    with pytest.raises(escrever.ErroNaEscrita):
        escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                        corpo={"promotion_id": "P-1"}, anuncio="MLB123")
    assert len(tentativas) == 1


def test_erro_500_e_incerto_e_tranca_o_item(pasta, monkeypatch):
    """O servidor recebeu e quebrou: isso nao prova que nao aplicou."""
    tentativas = []

    def falso(req, timeout=30):
        tentativas.append(1)
        raise _http(500, {"message": "quebrou"})

    monkeypatch.setattr(escrever.seguro, "abrir", falso)
    with pytest.raises(escrever.RespostaIncerta):
        escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                        corpo={"promotion_id": "P-1"}, anuncio="MLB123")
    assert len(tentativas) == 1
    assert escrever.pendencias("MLB123")


def test_corrida_de_oferta_e_sinalizada_para_quem_chama_decidir(pasta, monkeypatch):
    monkeypatch.setattr(escrever.seguro, "abrir",
                        lambda req, timeout=30: (_ for _ in ()).throw(_http(400, {
                            "cause": [{"error_code": "OFFER_SIBLING_CREATION_IN_PROCESS"}]})))
    with pytest.raises(escrever.OfertaEmProcesso):
        escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                        corpo={"promotion_id": "P-1"}, anuncio="MLB123")


def test_200_com_erros_no_corpo_nao_e_sucesso(pasta, monkeypatch):
    monkeypatch.setattr(escrever.seguro, "abrir",
                        lambda req, timeout=30: _resposta({"errors": [{"x": 1}]}, 200))
    with pytest.raises(escrever.ErroNaEscrita):
        escrever.enviar("sair", "/seller-promotions/items/MLB123",
                        params={"promotion_type": "SELLER_CAMPAIGN"}, anuncio="MLB123")


# =========================================================== acao 1: promover

CAND = {
    "id": "P-MLB1", "type": "SELLER_CAMPAIGN", "name": "OUTUBRO",
    "status": "candidate", "price": 80.0, "original_price": 100.0,
    "suggested_discounted_price": 80.0, "ref_id": "CANDIDATE-MLB123-9",
    "meli_percentage": 5.0, "seller_percentage": 15.0,
}


@pytest.fixture
def conta_api(pasta, monkeypatch):
    """Conta falsa: preco praticado 100 no anuncio, candidato a 80 na campanha."""
    estado = {"item": {"id": "MLB123", "price": 100.0, "status": "active"},
              "cands": [dict(CAND)], "envios": [], "esperas": []}

    def api(caminho, params=None):
        if caminho.startswith("/items/"):
            return dict(estado["item"])
        if caminho.startswith("/seller-promotions/items/"):
            return {"results": [dict(c) for c in estado["cands"]]}
        raise AssertionError("leitura inesperada: " + caminho)

    monkeypatch.setattr(promover.meli, "api", api)
    monkeypatch.setattr(escrever, "esperar", lambda s: estado["esperas"].append(s))

    def abrir(req, timeout=30):
        estado["envios"].append({"url": req.full_url, "metodo": req.method,
                                 "corpo": json.loads(req.data) if req.data else None})
        # O falso modela o fornecedor de verdade: quem muda o estado e o envio,
        # nao o teste. Mexer no estado antes do --fazer seria a releitura
        # recusando com razao, e o teste nao provaria nada.
        if estado.get("efeito"):
            estado["efeito"](estado)
        return _resposta(estado.get("resposta", {"ok": True}))

    monkeypatch.setattr(escrever.seguro, "abrir", abrir)
    return estado


def test_promover_preco_de_hoje_vem_do_anuncio_nao_do_candidato(conta_api, capsys):
    """O furo que a revisao pegou: no candidato, `price` e o preco NA campanha."""
    promover.conferir("aderir", "MLB123", "P-MLB1")
    saida = capsys.readouterr().out
    assert "hoje R$ 100,00" in saida
    assert "na campanha R$ 80,00" in saida


def test_promover_sem_preco_praticado_nao_compara(conta_api, capsys):
    conta_api["item"] = {"id": "MLB123", "status": "active"}
    promover.conferir("aderir", "MLB123", "P-MLB1")
    assert "NAO vou comparar" in capsys.readouterr().out


def test_promover_tipo_nao_medido_e_recusado_com_nome(conta_api):
    conta_api["cands"][0]["type"] = "SMART"
    with pytest.raises(promover.NaoDaParaFazer) as e:
        promover.conferir("aderir", "MLB123", "P-MLB1")
    assert "SMART" in str(e.value) and "MEDIDO" in str(e.value).upper()


def test_promover_sair_funciona_em_tipo_nao_medido(conta_api):
    """Sair e o caminho de volta: fechar junto com a entrada prende gente."""
    conta_api["cands"][0].update({"type": "SMART", "status": "started"})
    assert promover.conferir("sair", "MLB123", "P-MLB1")


def test_promover_recusa_aderir_no_que_ja_esta_dentro(conta_api):
    conta_api["cands"][0]["status"] = "started"
    with pytest.raises(promover.NaoDaParaFazer) as e:
        promover.conferir("aderir", "MLB123", "P-MLB1")
    assert "DENTRO" in str(e.value)


def test_promover_sem_preco_proposto_nao_inventa(conta_api):
    del conta_api["cands"][0]["suggested_discounted_price"]
    del conta_api["cands"][0]["price"]
    with pytest.raises(promover.NaoDaParaFazer) as e:
        promover.conferir("aderir", "MLB123", "P-MLB1")
    assert "inventa" in str(e.value)


def test_promover_anuncio_fora_da_campanha_diz_isso(conta_api):
    with pytest.raises(promover.NaoDaParaFazer):
        promover.conferir("aderir", "MLB123", "P-OUTRA")


def test_promover_manda_o_preco_da_fonte_e_o_tipo_lido(conta_api):
    cod = promover.conferir("aderir", "MLB123", "P-MLB1")
    promover.fazer(cod)
    envio = conta_api["envios"][0]
    assert envio["metodo"] == "POST"
    assert envio["corpo"] == {"promotion_id": "P-MLB1",
                              "promotion_type": "SELLER_CAMPAIGN",
                              "deal_price": 80.0}


def test_promover_preco_mudou_entre_conferir_e_fazer_recusa(conta_api):
    cod = promover.conferir("aderir", "MLB123", "P-MLB1")
    conta_api["item"]["price"] = 120.0
    with pytest.raises(promover.NaoDaParaFazer) as e:
        promover.fazer(cod)
    assert "preco praticado" in str(e.value)
    assert not conta_api["envios"]


def test_promover_campanha_mudou_de_preco_entre_conferir_e_fazer_recusa(conta_api):
    cod = promover.conferir("aderir", "MLB123", "P-MLB1")
    conta_api["cands"][0]["suggested_discounted_price"] = 70.0
    with pytest.raises(promover.NaoDaParaFazer):
        promover.fazer(cod)
    assert not conta_api["envios"]


def test_promover_oferta_mudou_entre_conferir_e_fazer_recusa(conta_api):
    cod = promover.conferir("aderir", "MLB123", "P-MLB1")
    conta_api["cands"][0]["ref_id"] = "CANDIDATE-OUTRA"
    with pytest.raises(promover.NaoDaParaFazer):
        promover.fazer(cod)
    assert not conta_api["envios"]


def _entrou(e):
    e["cands"][0]["status"] = "started"
    e["item"]["price"] = 80.0


def _saiu(e):
    e["cands"][0]["status"] = "candidate"
    e["item"]["price"] = 100.0


def test_promover_espera_a_propagacao_antes_de_confirmar(conta_api):
    cod = promover.conferir("aderir", "MLB123", "P-MLB1")
    conta_api["efeito"] = _entrou
    assert promover.fazer(cod) == 0
    assert escrever.ESPERA_PROPAGACAO in conta_api["esperas"]


def test_promover_201_com_preco_antigo_nao_vira_deu_certo(conta_api, capsys):
    """Medido na casa: o Meli devolve 201 e ignora o valor. 201 nao e prova."""
    cod = promover.conferir("aderir", "MLB123", "P-MLB1")
    assert promover.fazer(cod) == 1          # nada mudou na releitura
    assert "NAO CONFIRMEI" in capsys.readouterr().out


def test_promover_confirmacao_exige_preco_e_estado(conta_api):
    """Estado certo e preco antigo: o Meli diz que entrou e cobra o de antes."""
    cod = promover.conferir("aderir", "MLB123", "P-MLB1")
    conta_api["efeito"] = lambda e: e["cands"][0].update({"status": "started"})
    assert promover.fazer(cod) == 1


def test_promover_recibo_guarda_como_compensar(conta_api, pasta):
    cod = promover.conferir("aderir", "MLB123", "P-MLB1")
    conta_api["efeito"] = _entrou
    promover.fazer(cod)
    assert "compensar: python3 promover.py sair MLB123 P-MLB1" in \
        (pasta / "acoes.txt").read_text(encoding="utf-8")


def test_promover_corrida_de_oferta_repete_exatamente_uma_vez(conta_api, monkeypatch):
    cod = promover.conferir("aderir", "MLB123", "P-MLB1")
    chamadas = []

    def abrir(req, timeout=30):
        chamadas.append(1)
        if len(chamadas) == 1:
            raise _http(400, {"cause": [{"error_code": escrever.ERRO_CORRIDA}]})
        return _resposta({"ok": True})

    monkeypatch.setattr(escrever.seguro, "abrir", abrir)
    promover.fazer(cod)
    assert len(chamadas) == 2


def test_promover_corrida_que_insiste_nao_ganha_terceira_chance(conta_api, monkeypatch):
    cod = promover.conferir("aderir", "MLB123", "P-MLB1")
    chamadas = []

    def abrir(req, timeout=30):
        chamadas.append(1)
        raise _http(400, {"cause": [{"error_code": escrever.ERRO_CORRIDA}]})

    monkeypatch.setattr(escrever.seguro, "abrir", abrir)
    with pytest.raises(escrever.OfertaEmProcesso):
        promover.fazer(cod)
    assert len(chamadas) == 2


def test_promover_saida_com_404_vai_para_a_releitura(conta_api, monkeypatch, capsys):
    conta_api["cands"][0]["status"] = "started"
    conta_api["item"]["price"] = 80.0
    cod = promover.conferir("sair", "MLB123", "P-MLB1")

    def abrir(req, timeout=30):
        _saiu(conta_api)
        raise _http(404, {"message": "nao esta la"})

    monkeypatch.setattr(escrever.seguro, "abrir", abrir)
    assert promover.fazer(cod) == 0
    assert "404" in capsys.readouterr().out


def test_promover_saida_manda_promotion_id_e_oferta(conta_api):
    conta_api["cands"][0]["status"] = "started"
    cod = promover.conferir("sair", "MLB123", "P-MLB1")
    conta_api["efeito"] = _saiu
    promover.fazer(cod)
    url = conta_api["envios"][0]["url"]
    assert conta_api["envios"][0]["metodo"] == "DELETE"
    assert "promotion_id=P-MLB1" in url and "offer_id=CANDIDATE" in url


def test_promover_lightning_sai_so_com_o_tipo(conta_api):
    conta_api["cands"][0].update({"type": "LIGHTNING", "status": "started"})
    cod = promover.conferir("sair", "MLB123", "P-MLB1")
    conta_api["efeito"] = _saiu
    promover.fazer(cod)
    url = conta_api["envios"][0]["url"]
    assert "promotion_type=LIGHTNING" in url
    assert "promotion_id" not in url and "offer_id" not in url


def test_promover_anuncio_que_desaparece_na_saida_e_ambiguo(conta_api, capsys):
    conta_api["cands"][0]["status"] = "started"
    cod = promover.conferir("sair", "MLB123", "P-MLB1")
    conta_api["efeito"] = lambda e: e.__setitem__("cands", [])
    assert promover.fazer(cod) == 1
    assert "nao sei dizer" in capsys.readouterr().out


def test_promover_reconciliar_fecha_a_pendencia_pela_leitura(conta_api, pasta):
    escrever.abrir_tentativa("aderir", "MLB123", "nota")
    assert escrever.pendencias("MLB123")
    promover.reconciliar("MLB123")
    assert not escrever.pendencias("MLB123")


def test_promover_cli_recusa_lista_de_anuncios(conta_api, capsys):
    assert promover._main(["aderir", "MLB1,MLB2", "P-MLB1"]) == 2
    assert "lista" in capsys.readouterr().out


def test_promover_cli_nao_tem_todos(conta_api, capsys):
    assert promover._main(["aderir", "MLB123", "P-MLB1", "--todos"]) == 2
    assert "--todos" in capsys.readouterr().out


def test_promover_cli_sem_fazer_nao_envia(conta_api):
    promover._main(["aderir", "MLB123", "P-MLB1"])
    assert not conta_api["envios"]


# ========================================================== acao 2: responder

PERGUNTA = {
    "id": 13657433363, "item_id": "MLB4610563840", "seller_id": CONTA,
    "status": "UNANSWERED", "text": "Cabe em quarto pequeno?", "answer": None,
    "hold": False, "deleted_from_listing": False,
}


@pytest.fixture
def perguntas_api(pasta, monkeypatch):
    estado = {"p": dict(PERGUNTA), "envios": [], "efeito": None}

    def api(caminho, params=None):
        if caminho.startswith("/questions/"):
            return dict(estado["p"])
        if caminho == "/my/received_questions/search":
            return {"total": 1, "questions": [dict(estado["p"])]}
        raise AssertionError("leitura inesperada: " + caminho)

    monkeypatch.setattr(responder.meli, "api", api)
    monkeypatch.setattr(escrever, "esperar", lambda s: None)

    def abrir(req, timeout=30):
        estado["envios"].append(json.loads(req.data) if req.data else None)
        if estado["efeito"]:
            estado["efeito"](estado)
        return _resposta({"ok": True})

    monkeypatch.setattr(escrever.seguro, "abrir", abrir)
    return estado


def _publicou(texto="ok"):
    return lambda e: e["p"].update({"answer": {"text": texto},
                                    "status": "ANSWERED"})


def test_responder_conferir_mostra_o_texto_e_avisa_que_nao_desfaz(perguntas_api, capsys):
    responder.conferir(PERGUNTA["id"], "Cabe sim, 60cm de largura.")
    saida = capsys.readouterr().out
    assert "Cabe sim, 60cm de largura." in saida
    assert "NAO se desfaz" in saida
    assert not perguntas_api["envios"]


def test_responder_ja_respondida_e_recusada(perguntas_api):
    perguntas_api["p"]["answer"] = {"text": "ja respondi"}
    with pytest.raises(responder.NaoDaParaResponder) as e:
        responder.conferir(PERGUNTA["id"], "oi")
    assert "ja foi respondida" in str(e.value)


def test_responder_em_espera_e_recusada(perguntas_api):
    perguntas_api["p"]["hold"] = True
    with pytest.raises(responder.NaoDaParaResponder) as e:
        responder.conferir(PERGUNTA["id"], "oi")
    assert "espera" in str(e.value)


def test_responder_apagada_do_anuncio_e_recusada(perguntas_api):
    perguntas_api["p"]["deleted_from_listing"] = True
    with pytest.raises(responder.NaoDaParaResponder):
        responder.conferir(PERGUNTA["id"], "oi")


def test_responder_suspeita_de_spam_e_recusada(perguntas_api):
    perguntas_api["p"]["suspected_spam"] = True
    with pytest.raises(responder.NaoDaParaResponder):
        responder.conferir(PERGUNTA["id"], "oi")


def test_responder_estado_que_nao_e_unanswered_e_recusado(perguntas_api):
    perguntas_api["p"]["status"] = "CLOSED_UNANSWERED"
    with pytest.raises(responder.NaoDaParaResponder):
        responder.conferir(PERGUNTA["id"], "oi")


def test_responder_pergunta_de_outra_conta_e_recusada(perguntas_api):
    perguntas_api["p"]["seller_id"] = 999
    with pytest.raises(responder.NaoDaParaResponder) as e:
        responder.conferir(PERGUNTA["id"], "oi")
    assert "999" in str(e.value)


def test_responder_sem_texto_nao_publica_nada(perguntas_api):
    with pytest.raises(responder.NaoDaParaResponder) as e:
        responder.conferir(PERGUNTA["id"], "   ")
    assert "Quem escreve e voce" in str(e.value)


def test_responder_texto_longo_demais_para_aqui(perguntas_api):
    with pytest.raises(responder.NaoDaParaResponder):
        responder.conferir(PERGUNTA["id"], "x" * (responder.LIMITE + 1))


def test_responder_texto_editado_depois_de_conferir_invalida_o_codigo(perguntas_api):
    a = responder.conferir(PERGUNTA["id"], "resposta A")
    b = responder.conferir(PERGUNTA["id"], "resposta B")
    assert a != b
    escrever.consumir_intencao(b)
    with pytest.raises(escrever.ConferenciaInvalida):
        escrever.consumir_intencao(b)


def test_responder_publica_o_texto_conferido(perguntas_api):
    cod = responder.conferir(PERGUNTA["id"], "Cabe sim.")
    perguntas_api["efeito"] = _publicou("Cabe sim.")
    assert responder.fazer(cod) == 0
    assert perguntas_api["envios"] == [
        {"question_id": PERGUNTA["id"], "text": "Cabe sim."}]


def test_responder_respondida_entre_conferir_e_fazer_nao_publica(perguntas_api):
    cod = responder.conferir(PERGUNTA["id"], "Cabe sim.")
    perguntas_api["p"]["answer"] = {"text": "alguem respondeu antes"}
    with pytest.raises(responder.NaoDaParaResponder):
        responder.fazer(cod)
    assert not perguntas_api["envios"]


def test_responder_sem_confirmacao_nao_manda_reenviar(perguntas_api, capsys):
    cod = responder.conferir(PERGUNTA["id"], "Cabe sim.")
    assert responder.fazer(cod) == 1          # a releitura nao achou resposta
    saida = capsys.readouterr().out
    assert "NAO CONFIRMEI" in saida
    assert "NAO reenvie" in saida


def test_responder_diferenca_de_espaco_ainda_e_a_sua_resposta(perguntas_api):
    """A unica normalizacao admitida e a demonstrada: espaco."""
    cod = responder.conferir(PERGUNTA["id"], "Cabe sim.")
    perguntas_api["efeito"] = _publicou("  Cabe   sim.  ")
    assert responder.fazer(cod) == 0


def test_responder_resposta_de_outro_nao_vira_confirmacao_sua(perguntas_api, capsys):
    """Outra integracao respondeu na mesma janela: dizer 'feito' aqui seria
    assinar o texto de outra pessoa."""
    cod = responder.conferir(PERGUNTA["id"], "Cabe sim, 60 cm.")
    perguntas_api["efeito"] = _publicou("Nao temos esse produto.")
    assert responder.fazer(cod) == 1
    assert "NAO e a sua" in capsys.readouterr().out


def test_responder_codigo_de_outra_pergunta_nao_publica(perguntas_api):
    cod = responder.conferir(PERGUNTA["id"], "Cabe sim.")
    with pytest.raises(responder.NaoDaParaResponder) as e:
        responder.fazer(cod, 999999)
    assert "999999" in str(e.value)
    assert not perguntas_api["envios"]


def test_responder_sem_confirmar_deixa_a_pergunta_trancada(perguntas_api):
    cod = responder.conferir(PERGUNTA["id"], "Cabe sim.")
    assert responder.fazer(cod) == 1
    assert escrever.pendencias("pergunta-%s" % PERGUNTA["id"])


def test_responder_recibo_nao_guarda_o_texto(perguntas_api, pasta):
    cod = responder.conferir(PERGUNTA["id"], "segredo que ninguem deve guardar")
    perguntas_api["efeito"] = _publicou("ok")
    responder.fazer(cod)
    recibo = (pasta / "acoes.txt").read_text(encoding="utf-8")
    assert "segredo que ninguem deve guardar" not in recibo
    assert "pergunta-%s" % PERGUNTA["id"] in recibo


def test_responder_codigo_de_promocao_nao_serve_aqui(perguntas_api):
    cod = escrever.guardar_intencao(
        {"conta": CONTA, "acao": "aderir", "anuncio": "MLB1"})
    with pytest.raises(escrever.ConferenciaInvalida):
        responder.fazer(cod)


def test_responder_cli_sem_argumento_lista(perguntas_api, capsys):
    assert responder._main([]) == 0
    assert str(PERGUNTA["id"]) in capsys.readouterr().out


def test_responder_cli_recusa_mais_de_uma_pergunta(perguntas_api, capsys):
    assert responder._main(["1", "2", "--texto", "x"]) == 2
    assert "uma resposta por vez" in capsys.readouterr().out.lower()


def test_responder_reconciliar_fecha_pela_leitura(perguntas_api):
    escrever.abrir_tentativa("responder", "pergunta-%s" % PERGUNTA["id"], "x")
    assert escrever.pendencias("pergunta-%s" % PERGUNTA["id"])
    perguntas_api["p"]["answer"] = {"text": "estava publicada"}
    responder.reconciliar(PERGUNTA["id"])
    assert not escrever.pendencias("pergunta-%s" % PERGUNTA["id"])


# ================================================== o pacote, como ele e servido

def test_o_marketplace_oferece_os_dois_pacotes_separados():
    d = json.loads((RAIZ / ".claude-plugin" / "marketplace.json")
                   .read_text(encoding="utf-8"))
    por_nome = {p["name"]: p for p in d["plugins"]}
    assert por_nome["prometheus"]["source"] == "./"
    assert por_nome["prometheus-acoes"]["source"] == "./acoes"


def test_o_marketplace_nao_carrega_versao():
    """Regra da casa: versao vive nos manifestos, nunca aqui. Versao no
    marketplace.json faz a atualizacao nao chegar em quem ja instalou."""
    bruto = (RAIZ / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    assert '"version"' not in bruto


def test_o_pacote_de_acoes_tem_manifesto_proprio_com_versao():
    d = json.loads((RAIZ / "acoes" / ".claude-plugin" / "plugin.json")
                   .read_text(encoding="utf-8"))
    assert d["name"] == "prometheus-acoes"
    assert re.match(r"^\d+\.\d+\.\d+$", d["version"])
    assert d["skills"] == "./skills"


def test_os_scripts_de_escrita_nao_moram_no_pacote_de_leitura():
    """Quem instalou so o prometheus nao tem como escrever, nem copiando."""
    for nome in ("escrever.py", "promover.py", "responder.py"):
        assert not (RAIZ / "scripts" / nome).exists(), nome


def test_cada_skill_de_acao_diz_no_nome_o_que_ela_faz():
    pasta_skills = RAIZ / "acoes" / "skills"
    nomes = sorted(p.name for p in pasta_skills.iterdir() if p.is_dir())
    assert nomes == ["prometheus-aderir-promocao", "prometheus-responder-pergunta"]
    for nome in nomes:
        texto = (pasta_skills / nome / "SKILL.md").read_text(encoding="utf-8")
        assert texto.startswith("---\n")
        assert "name: %s\n" % nome in texto
        # A descricao e o que o modelo le para escolher a skill: ela precisa
        # dizer que MUDA coisa, nao so o que ela consulta.
        descricao = texto.split("description:", 1)[1].split("\n", 1)[0]
        assert any(p in descricao for p in ("MUDA", "PUBLICA")), nome


def test_os_dois_manifestos_do_pacote_de_acoes_concordam_na_versao():
    """A regra que ja custou cinco mudancas paradas na 0.1.0: versao divergente
    entre os manifestos faz a atualizacao nao chegar em quem instalou."""
    a = json.loads((RAIZ / "acoes" / ".claude-plugin" / "plugin.json")
                   .read_text(encoding="utf-8"))
    b = json.loads((RAIZ / "acoes" / ".codex-plugin" / "plugin.json")
                   .read_text(encoding="utf-8"))
    assert a["version"] == b["version"]
    assert a["name"] == b["name"]


# ======================= o que a lente de seguranca pegou (02/11, rodada 2)

def test_transporte_aceito_nao_fecha_a_tentativa(pasta, monkeypatch):
    """201 nao e resultado: fechar aqui destravaria o item na propagacao, que e
    exatamente a janela em que o 201 ja mentiu nesta casa."""
    monkeypatch.setattr(escrever.seguro, "abrir",
                        lambda req, timeout=30: _resposta({"ok": True}))
    r = escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                        corpo={"promotion_id": "P-1"}, anuncio="MLB123")
    assert escrever.pendencias("MLB123")
    escrever.confirmado(r["recibo"], "conferido")
    assert not escrever.pendencias("MLB123")


def test_o_id_da_tentativa_nao_e_curto_demais(pasta):
    ident = escrever.abrir_tentativa("aderir", "MLB1", "x")
    assert len(ident) >= 12


def test_pendencia_sobrevive_ao_arquivamento_do_recibo(pasta, monkeypatch):
    """Renomear o recibo nao pode destravar um anuncio incerto."""
    escrever.abrir_tentativa("aderir", "MLB123", "x")
    (pasta / "acoes.txt").rename(pasta / "acoes-2026.txt")
    assert escrever.pendencias("MLB123")


def test_recibo_ilegivel_recusa_em_vez_de_dizer_que_nao_tem_nada(pasta, monkeypatch):
    escrever.abrir_tentativa("aderir", "MLB123", "x")
    os.chmod(pasta / "acoes.txt", 0o000)
    try:
        with pytest.raises(escrever.ReciboIlegivel):
            escrever.pendencias("MLB123")
    finally:
        os.chmod(pasta / "acoes.txt", 0o600)


def test_duas_execucoes_no_mesmo_item_nao_correm_juntas(pasta):
    with escrever.trava("MLB123"):
        with pytest.raises(escrever.ItemTrancado):
            with escrever.trava("MLB123"):
                pass
    with escrever.trava("MLB123"):      # liberou no fim do bloco
        pass


def test_a_trava_e_por_item(pasta):
    with escrever.trava("MLB123"):
        with escrever.trava("MLB999"):
            pass


def test_conferir_de_novo_revoga_a_conferencia_anterior(pasta):
    base = {"conta": CONTA, "acao": "responder", "pergunta": 42}
    velho = escrever.guardar_intencao(dict(base, texto="rascunho ruim"))
    novo = escrever.guardar_intencao(dict(base, texto="texto certo"))
    with pytest.raises(escrever.ConferenciaInvalida):
        escrever.consumir_intencao(velho)
    assert escrever.consumir_intencao(novo)["texto"] == "texto certo"


def test_conferencia_de_outro_alvo_nao_e_revogada(pasta):
    a = escrever.guardar_intencao({"conta": CONTA, "acao": "responder", "pergunta": 1})
    escrever.guardar_intencao({"conta": CONTA, "acao": "responder", "pergunta": 2})
    assert escrever.consumir_intencao(a)


def test_intencao_vencida_sai_do_disco(pasta, monkeypatch):
    escrever.guardar_intencao({"conta": CONTA, "acao": "responder", "pergunta": 7,
                               "texto": "rascunho que nao deve ficar"})
    depois = time.time() + escrever.VALIDADE + 1
    monkeypatch.setattr(escrever.time, "time", lambda: depois)
    escrever._ler_intencoes()
    assert "rascunho que nao deve ficar" not in \
        (pasta / "intencoes.json").read_text(encoding="utf-8")


def test_token_no_campo_error_tambem_e_limpo(pasta, monkeypatch):
    monkeypatch.setattr(escrever.seguro, "abrir",
                        lambda req, timeout=30: (_ for _ in ()).throw(
                            _http(400, {"error": "TOKEN-SECRETO vazou aqui"})))
    with pytest.raises(escrever.ErroNaEscrita) as e:
        escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                        corpo={"promotion_id": "P-1"}, anuncio="MLB123")
    assert "TOKEN-SECRETO" not in str(e.value)
    assert "TOKEN-SECRETO" not in (pasta / "acoes.txt").read_text(encoding="utf-8")


def test_token_no_fim_de_mensagem_longa_nao_escapa_pelo_corte(pasta, monkeypatch):
    """Limpar depois de truncar deixaria meio token na mensagem."""
    longa = "x" * 290 + " TOKEN-SECRETO " + "y" * 50
    monkeypatch.setattr(escrever.seguro, "abrir",
                        lambda req, timeout=30: (_ for _ in ()).throw(
                            _http(400, {"message": longa})))
    with pytest.raises(escrever.ErroNaEscrita) as e:
        escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                        corpo={"promotion_id": "P-1"}, anuncio="MLB123")
    assert "TOKEN-SECRET" not in str(e.value)


def test_codigo_de_erro_fora_de_formato_nao_e_tratado_como_codigo(pasta, monkeypatch):
    monkeypatch.setattr(escrever.seguro, "abrir",
                        lambda req, timeout=30: (_ for _ in ()).throw(
                            _http(400, {"cause": [{"error_code": "TOKEN-SECRETO " * 20}]})))
    with pytest.raises(escrever.ErroNaEscrita) as e:
        escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                        corpo={"promotion_id": "P-1"}, anuncio="MLB123")
    assert "TOKEN-SECRETO" not in str(e.value)


def test_promover_codigo_de_aderir_nao_executa_com_sair_na_linha(conta_api):
    """O comando que a pessoa digita tem de descrever o que vai acontecer."""
    cod = promover.conferir("aderir", "MLB123", "P-MLB1")
    with pytest.raises(promover.NaoDaParaFazer) as e:
        promover.fazer(cod, "sair", "MLB123", "P-MLB1")
    assert "acao" in str(e.value)
    assert not conta_api["envios"]


def test_promover_codigo_de_outro_anuncio_nao_executa(conta_api):
    cod = promover.conferir("aderir", "MLB123", "P-MLB1")
    with pytest.raises(promover.NaoDaParaFazer):
        promover.fazer(cod, "aderir", "MLB999", "P-MLB1")
    assert not conta_api["envios"]


def test_promover_codigo_de_outra_campanha_nao_executa(conta_api):
    cod = promover.conferir("aderir", "MLB123", "P-MLB1")
    with pytest.raises(promover.NaoDaParaFazer):
        promover.fazer(cod, "aderir", "MLB123", "P-OUTRA")
    assert not conta_api["envios"]


def test_promover_adesao_confirmada_destrava_o_anuncio(conta_api):
    cod = promover.conferir("aderir", "MLB123", "P-MLB1")
    conta_api["efeito"] = _entrou
    assert promover.fazer(cod) == 0
    assert not escrever.pendencias("MLB123")


def test_promover_adesao_nao_confirmada_deixa_trancado(conta_api):
    cod = promover.conferir("aderir", "MLB123", "P-MLB1")
    assert promover.fazer(cod) == 1
    assert escrever.pendencias("MLB123")


def test_promover_saida_com_preco_que_nao_volta_nao_e_confirmada(conta_api, capsys):
    conta_api["cands"][0]["status"] = "started"
    conta_api["item"]["price"] = 80.0
    cod = promover.conferir("sair", "MLB123", "P-MLB1")
    # saiu da campanha, mas o preco promocional ficou
    conta_api["efeito"] = lambda e: e["cands"][0].update({"status": "candidate"})
    assert promover.fazer(cod) == 1
    assert "o preco eu nao confirmo" in capsys.readouterr().out


def test_promover_saida_em_pending_nao_conta_como_saida(conta_api, capsys):
    conta_api["cands"][0]["status"] = "started"
    conta_api["item"]["price"] = 80.0
    cod = promover.conferir("sair", "MLB123", "P-MLB1")
    conta_api["efeito"] = lambda e: e["cands"][0].update({"status": "pending"})
    assert promover.fazer(cod) == 1
    assert "esperava candidato" in capsys.readouterr().out


def test_promover_saida_em_outra_oferta_nao_e_confirmada(conta_api, capsys):
    conta_api["cands"][0]["status"] = "started"
    conta_api["item"]["price"] = 80.0
    cod = promover.conferir("sair", "MLB123", "P-MLB1")

    def outra(e):
        e["cands"][0].update({"status": "candidate", "ref_id": "CANDIDATE-OUTRA"})
        e["item"]["price"] = 100.0

    conta_api["efeito"] = outra
    assert promover.fazer(cod) == 1
    assert "oferta diferente" in capsys.readouterr().out


# ================= o que a verificacao da lente pegou (02/11, rodada 3)

def test_fechamento_em_arquivo_arquivado_nao_ressuscita_pendencia(pasta):
    """A regressao que a correcao anterior criou: casar abertura e fechamento na
    ordem dos arquivos fazia um item resolvido voltar trancado."""
    ident = escrever.abrir_tentativa("aderir", "MLB123", "x")
    (pasta / "acoes.txt").rename(pasta / "acoes-z.txt")      # a abertura foi para o fim
    escrever.fechar_tentativa(ident, "reconciliado", "lido")  # o fechamento, para acoes.txt
    assert not escrever.pendencias("MLB123")


def test_o_arquivo_de_intencoes_tem_trava_propria(pasta):
    """Travar por item nao protege um arquivo que e um so para a pasta."""
    with escrever.trava("intencoes"):
        with pytest.raises(escrever.ItemTrancado):
            escrever.guardar_intencao({"conta": CONTA, "acao": "aderir",
                                       "anuncio": "MLB1"})


def test_reconciliar_usa_a_mesma_trava_da_execucao(conta_api):
    """Travas diferentes deixavam a reconciliacao fechar tentativa em propagacao."""
    with escrever.trava("MLB123"):
        with pytest.raises(escrever.ItemTrancado):
            promover.reconciliar("MLB123")


def test_reconciliar_que_nao_consegue_ler_nao_fecha_nada(conta_api):
    escrever.abrir_tentativa("aderir", "MLB123", "x")
    conta_api["item"] = {}
    assert promover.reconciliar("MLB123") == 1
    assert escrever.pendencias("MLB123")


def test_reconciliar_nao_grava_ok_no_recibo(conta_api, pasta):
    """`ok` e resultado conferido pela pos-condicao. O que a leitura encontrou
    depois e outra coisa, e o recibo nao pode dar o mesmo nome aos dois."""
    escrever.abrir_tentativa("aderir", "MLB123", "x")
    promover.reconciliar("MLB123")
    linhas = [l for l in (pasta / "acoes.txt").read_text(encoding="utf-8").splitlines()
              if "tentando" not in l]
    assert any("reconciliado" in l for l in linhas)
    assert not any(" ok " in l for l in linhas)


def test_reconciliar_resposta_nao_afirma_que_e_a_sua(perguntas_api, capsys):
    escrever.abrir_tentativa("responder", "pergunta-%s" % PERGUNTA["id"], "x")
    perguntas_api["p"]["answer"] = {"text": "resposta de alguem"}
    responder.reconciliar(PERGUNTA["id"])
    saida = capsys.readouterr().out
    assert "NAO consigo afirmar" in saida
    assert not escrever.pendencias("pergunta-%s" % PERGUNTA["id"])


def test_token_dentro_do_formato_de_codigo_e_descartado(pasta, monkeypatch):
    """NOT_BUY_BOX_WINNER e um token se parecem o bastante: o formato sozinho
    nao distingue, entao quem decide e a limpeza."""
    monkeypatch.setattr(escrever.seguro, "abrir",
                        lambda req, timeout=30: (_ for _ in ()).throw(
                            _http(400, {"error": "TOKEN-SECRETO",
                                        "message": "recusado"})))
    with pytest.raises(escrever.ErroNaEscrita) as e:
        escrever.enviar("aderir", "/seller-promotions/items/MLB123",
                        corpo={"promotion_id": "P-1"}, anuncio="MLB123")
    assert "TOKEN-SECRETO" not in str(e.value)
    assert "TOKEN-SECRETO" not in (pasta / "acoes.txt").read_text(encoding="utf-8")


def test_promover_leitura_ilegivel_nao_vira_fora_da_campanha(conta_api, monkeypatch):
    """Resposta que nao deu para ler dizia 'ele nao esta em campanha nenhuma'."""
    monkeypatch.setattr(promover.meli, "api",
                        lambda c, p=None: {"message": "erro de leitura"})
    with pytest.raises(promover.LeituraFalhou):
        promover.candidatos("MLB123")


def test_promover_reconciliar_com_leitura_ilegivel_nao_fecha(conta_api, monkeypatch, capsys):
    escrever.abrir_tentativa("aderir", "MLB123", "x")

    def api(caminho, params=None):
        if caminho.startswith("/items/"):
            return {"id": "MLB123", "price": 100.0, "status": "active"}
        return {"message": "erro de leitura"}

    monkeypatch.setattr(promover.meli, "api", api)
    assert promover.reconciliar("MLB123") == 1
    assert escrever.pendencias("MLB123")
    assert "continua ABERTA" in capsys.readouterr().out


def test_promover_campanha_vazia_de_verdade_nao_e_leitura_falha(conta_api, monkeypatch):
    """`results` nulo com total zero e campanha vazia mesmo: isso nao levanta."""
    monkeypatch.setattr(promover.meli, "api",
                        lambda c, p=None: {"results": None, "paging": {"total": 0}})
    assert promover.candidatos("MLB123") == []


def test_responder_reconciliar_com_leitura_ilegivel_nao_fecha(perguntas_api, capsys):
    escrever.abrir_tentativa("responder", "pergunta-%s" % PERGUNTA["id"], "x")
    perguntas_api["p"] = {"message": "erro de leitura"}
    assert responder.reconciliar(PERGUNTA["id"]) == 1
    assert escrever.pendencias("pergunta-%s" % PERGUNTA["id"])
    saida = capsys.readouterr().out
    assert "continua ABERTA" in saida
    assert "ainda nao publicada" not in saida


def test_qualquer_comando_das_acoes_limpa_rascunho_vencido(pasta, monkeypatch):
    """A promessa da skill valia so para comando que lia intencoes."""
    escrever.guardar_intencao({"conta": CONTA, "acao": "responder", "pergunta": 9,
                               "texto": "rascunho vencido"})
    depois = time.time() + escrever.VALIDADE + 1
    monkeypatch.setattr(escrever.time, "time", lambda: depois)
    escrever.manutencao()
    assert "rascunho vencido" not in (pasta / "intencoes.json").read_text(encoding="utf-8")


def test_promover_lista_com_registro_sem_estado_nao_e_nenhuma_campanha(conta_api, monkeypatch):
    """Lista nao basta: registro sem id nem estado nao prova ausencia."""
    monkeypatch.setattr(promover.meli, "api",
                        lambda c, p=None: [{"message": "erro sem estado"}])
    with pytest.raises(promover.LeituraFalhou):
        promover.candidatos("MLB123")


def test_promover_reconciliar_com_registro_quebrado_nao_fecha(conta_api, monkeypatch):
    escrever.abrir_tentativa("aderir", "MLB123", "x")

    def api(caminho, params=None):
        if caminho.startswith("/items/"):
            return {"id": "MLB123", "price": 100.0, "status": "active"}
        return [{"message": "erro sem estado"}]

    monkeypatch.setattr(promover.meli, "api", api)
    assert promover.reconciliar("MLB123") == 1
    assert escrever.pendencias("MLB123")


def test_limpar_apaga_tambem_a_conferencia_valida(pasta, capsys):
    """"Apagar na hora" tem de apagar na hora, senao a skill promete demais."""
    cod = escrever.guardar_intencao({"conta": CONTA, "acao": "responder",
                                     "pergunta": 5, "texto": "rascunho"})
    import sys as _sys
    guardado = _sys.argv
    _sys.argv = ["escrever.py", "limpar"]
    try:
        escrever._main()
    finally:
        _sys.argv = guardado
    with pytest.raises(escrever.ConferenciaInvalida):
        escrever.consumir_intencao(cod)
    assert "rascunho" not in (pasta / "intencoes.json").read_text(encoding="utf-8")
