#!/usr/bin/env python3
"""A porta de escrita do Prometheus. Separada da leitura de proposito.

O pacote de leitura (`prometheus`) tem uma trava em `meli.py request()` que
recusa qualquer metodo que nao seja GET. **Esta trava nao e tocada.** Quem
escreve e este arquivo, que tem porta propria, e os leitores nunca o importam.

O que esta porta faz de diferente de um urlopen solto, e por que:

1. **Lista fechada de acoes.** Nao existe `enviar(metodo, caminho)` livre: cada
   acao declara o seu metodo, o padrao de caminho que aceita e o escopo exato de
   que precisa. Caminho fora do padrao nao sai, nem montado na mao.

2. **Escopo por superficie, pelo nome.** Ter "alguma" permissao de escrita nao
   serve: `urn:ml:mktp:ads:/read-write` nao autoriza mexer em promocao. Medido
   em 02/11/2026: o escopo largo (`write`) nao governa; governam os granulares.

3. **Sem redirecionamento.** Vai `Authorization: Bearer` aqui. Seguir um 302
   entregaria o token ao destino de outra pessoa. `seguro.abrir` recusa.

4. **Recibo antes do envio.** A linha "tentando" e gravada ANTES de a chamada
   sair. Se nao der para gravar, a acao nao acontece. Resultado conhecido fecha
   a linha; resposta perdida deixa a linha aberta — e linha aberta **tranca**
   aquele anuncio ate alguem reconciliar por leitura.

5. **Escrita nao repete.** O cliente de leitura repete em 429 e 500, e esta
   certo para GET. Aqui esta errado: a chamada pode ter aplicado antes de a
   resposta se perder. Uma excecao, e so ela:
   `OFFER_SIBLING_CREATION_IN_PROCESS`, em que o proprio Mercado Livre diz que
   NAO aplicou (medido na casa em 26/08/2026: ~1 em 7). Mesmo assim quem repete
   e quem chama, depois de reler.

Compatibilidade: Python 3.8+.
"""
import contextlib
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import meli    # do pacote de leitura: so o token vem dele
import seguro

BASE = Path(__file__).resolve().parent
TOKENS = BASE / "tokens.json"
RECIBO = BASE / "acoes.txt"
INTENCOES = BASE / "intencoes.json"

HOST = "api.mercadolibre.com"
API = "https://" + HOST

# A conferencia vale 10 minutos. Depois disso o mundo mudou o bastante para
# a tela que a pessoa leu nao valer mais como descricao do que vai acontecer.
VALIDADE = 600
# Medido pelo Sentinela em 26/08/2026: a propagacao passa de 5s. Janela de
# releitura curta reportou "nao deu certo" duas vezes num write que tinha dado.
ESPERA_PROPAGACAO = 15
# Recibo e barato (~200 bytes por acao) e nao se apaga. O teto existe para o
# arquivo nunca virar problema calado: no teto a acao e recusada, nunca cortada.
TETO = 5 * 1024 * 1024

ERRO_CORRIDA = "OFFER_SIBLING_CREATION_IN_PROCESS"
ERRO_POLITICA = "PA_UNAUTHORIZED_RESULT_FROM_POLICIES"

# Escopos granulares, descobertos na conta real em 02/11/2026.
OFERTAS = "urn:ml:mktp:offers:/read-write"
COMUNICACAO = "urn:ml:mktp:comunication:/read-write"  # a grafia e do Meli

_ITEM = r"MLB\d+"

ACOES = {
    "aderir": {
        "metodo": "POST",
        "caminho": re.compile(r"^/seller-promotions/items/%s$" % _ITEM),
        "escopo": OFERTAS,
        "muda": "o preco de venda de um anuncio",
    },
    "sair": {
        "metodo": "DELETE",
        "caminho": re.compile(r"^/seller-promotions/items/%s$" % _ITEM),
        "escopo": OFERTAS,
        "muda": "tira um anuncio de uma campanha",
    },
    "responder": {
        "metodo": "POST",
        "caminho": re.compile(r"^/answers$"),
        "escopo": COMUNICACAO,
        "muda": "publica um texto publico na pagina do anuncio",
    },
}


class AcaoRecusada(PermissionError):
    """Acao ou caminho fora da lista fechada. Nao saiu da maquina."""


class SemPermissao(RuntimeError):
    """Falta o escopo granular daquela superficie. Precisa reautorizar."""


class ErroNaEscrita(RuntimeError):
    """O Mercado Livre respondeu erro. Guarda .status e .codigo."""

    def __init__(self, mensagem, status=None, codigo=None):
        super().__init__(mensagem)
        self.status = status
        self.codigo = codigo


class OfertaEmProcesso(ErroNaEscrita):
    """Transitorio: o Meli ainda processa a oferta anterior. NAO aplicou."""


class RespostaIncerta(RuntimeError):
    """A resposta se perdeu. Pode ter aplicado. Nao repetir: reconciliar."""


class ItemTrancado(RuntimeError):
    """Existe tentativa sem resultado conhecido neste anuncio."""


class ReciboImpossivel(RuntimeError):
    """Nao deu para gravar o recibo. Acao sem recibo nao acontece."""


class ReciboIlegivel(RuntimeError):
    """Nao deu para ler o recibo. Nao sei se ha pendencia: nao agir."""


class ReciboNoTeto(RuntimeError):
    """O conjunto de recibos chegou ao teto."""


class ConferenciaInvalida(RuntimeError):
    """O codigo nao existe, venceu, ja foi usado, ou e de outra conta."""


def esperar(segundos):
    """Isolado para o teste poder adiantar o relogio sem esperar de verdade."""
    time.sleep(segundos)


# --------------------------------------------------------------- permissao

def _tokens():
    if not TOKENS.exists():
        raise SemPermissao(
            "Nenhuma conta conectada nesta pasta. Rode primeiro a skill "
            "prometheus-conectar-meli."
        )
    return json.loads(TOKENS.read_text(encoding="utf-8"))


def escopos_concedidos():
    """Os NOMES dos escopos que a ultima autorizacao concedeu. Nunca o token."""
    return sorted(set((_tokens().get("scope") or "").split()))


def conta_do_token():
    return _tokens().get("user_id")


def exigir_permissao(acao):
    """Recusa antes de qualquer coisa sair quando falta o escopo DAQUELA
    superficie. Escopo guardado em disco e evidencia, nao prova — ele conta o
    que a ultima autorizacao concedeu. Por isso o 403 de politica, no meio do
    caminho, tambem e tratado (ver _erro_da_resposta)."""
    exigido = ACOES[acao]["escopo"]
    if exigido not in escopos_concedidos():
        raise SemPermissao(
            "Falta a permissao de escrita desta superficie (%s).\n"
            "Mudar a permissao no DevCenter NAO vale para a conexao que ja "
            "existe: e preciso autorizar de novo.\n"
            "1) No DevCenter, marque Leitura e escrita no recurso certo.\n"
            "2) Rode: python3 autorizar.py" % exigido
        )


# ------------------------------------------------------------------- recibo

# "reconciliado" e diferente de "ok" de proposito: ok e resultado conferido pela
# pos-condicao da acao; reconciliado e o que a leitura encontrou depois. Dar o
# mesmo nome aos dois fazia o recibo afirmar mais do que foi provado.
_RESULTADOS = ("ok", "erro", "recusado", "reconciliado")


def _tamanho_do_conjunto():
    total = 0
    try:
        for p in RECIBO.parent.glob(RECIBO.stem + "*" + RECIBO.suffix):
            total += p.stat().st_size
    except OSError:
        return 0
    return total


def exigir_espaco():
    if _tamanho_do_conjunto() >= TETO:
        raise ReciboNoTeto(
            "O recibo de acoes chegou a %d MB. Recibo nao se apaga e nao se "
            "corta: renomeie %s (ex.: acoes-2026.txt) e rode de novo."
            % (TETO // (1024 * 1024), RECIBO.name)
        )


def _anexar(linha, ja_enviou=False):
    try:
        # De proposito NAO cria a pasta: o recibo mora na pasta da pessoa, que
        # ja existe. Pasta faltando e caminho errado, e caminho errado nao pode
        # virar rotina silenciosa.
        with open(RECIBO, "a", encoding="utf-8") as f:
            f.write(linha.rstrip("\n") + "\n")
            f.flush()
            os.fsync(f.fileno())
    except OSError as e:
        if ja_enviou:
            # Mentir aqui seria pior que o problema: a chamada JA saiu.
            raise ReciboImpossivel(
                "A acao JA FOI ENVIADA, mas nao deu para registrar o resultado "
                "em %s (%s). Anote por fora e confira o estado real na conta."
                % (RECIBO, e.__class__.__name__))
        raise ReciboImpossivel(
            "Nao deu para escrever o recibo em %s (%s). Acao sem recibo nao "
            "acontece: nada foi enviado." % (RECIBO, e.__class__.__name__)
        )


def abrir_tentativa(acao, anuncio, nota):
    """Grava a linha 'tentando' ANTES do envio e devolve o id dela."""
    # 12 hex, nao 4: com 4 sao 65 mil identificadores, e duas tentativas com o
    # mesmo id fazem o fechamento de uma apagar a PENDENCIA da outra — ou seja,
    # destravam um anuncio que ninguem conferiu.
    ident = hashlib.sha256(
        ("%s|%s|%.6f|%s" % (acao, anuncio, time.time(), os.urandom(8).hex()))
        .encode()).hexdigest()[:12]
    _anexar("%s  #%s  tentando   %-9s %-16s %s" % (
        time.strftime("%Y-%m-%dT%H:%M:%S"), ident, acao, anuncio, nota))
    return ident


def fechar_tentativa(ident, resultado, nota="", ja_enviou=True):
    _anexar("%s  #%s  %-10s %s" % (
        time.strftime("%Y-%m-%dT%H:%M:%S"), ident, resultado, _sem_segredo(nota)),
        ja_enviou=ja_enviou)


def anotar(texto):
    """Linha livre no recibo — usada para gravar como compensar o que foi feito."""
    _anexar("%s  %s" % (" " * 19, texto))


def _arquivos_de_recibo():
    return sorted(RECIBO.parent.glob(RECIBO.stem + "*" + RECIBO.suffix))


def pendencias(anuncio=None):
    """Tentativas sem resultado conhecido. Linha aberta tranca o anuncio.

    Interrupcao no meio — terminal fechado, luz caindo, disco cheio — nao fica
    invisivel: fica trancada, e o destravamento e por leitura.

    Le o CONJUNTO de recibos, nao so o arquivo atual: renomear acoes.txt para
    acoes-2026.txt nao pode fazer uma pendencia desaparecer da consulta — seria
    destravar um anuncio incerto arrumando a pasta.

    Recibo ilegivel RECUSA. Devolver lista vazia aqui transformaria "nao sei" em
    "nao tem nada pendente", que e a pior leitura possivel."""
    abertas = {}
    fechadas = set()
    linhas = []
    for caminho in _arquivos_de_recibo():
        try:
            linhas.extend(caminho.read_text(encoding="utf-8").splitlines())
        except OSError as e:
            raise ReciboIlegivel(
                "Nao deu para ler o recibo %s (%s). Sem poder ler, nao sei se "
                "existe acao pendente — e nao vou agir no escuro."
                % (caminho.name, e.__class__.__name__))
    for linha in linhas:
        partes = linha.split()
        if len(partes) < 3 or not partes[1].startswith("#"):
            continue
        ident, estado = partes[1][1:], partes[2]
        # Junta ABERTURAS e FECHAMENTOS em conjuntos e so no fim subtrai. Casar
        # na ordem de leitura parecia natural e tinha um buraco: com o recibo
        # arquivado, o fechamento pode estar em acoes.txt e a abertura em
        # acoes-z.txt — lido depois. A pendencia ressuscitava, e um anuncio
        # resolvido voltava trancado.
        if estado == "tentando":
            abertas[ident] = {"id": ident, "acao": partes[3] if len(partes) > 3 else "",
                              "anuncio": partes[4] if len(partes) > 4 else "",
                              "quando": partes[0]}
        elif estado in _RESULTADOS:
            fechadas.add(ident)
    todas = [v for k, v in abertas.items() if k not in fechadas]
    if anuncio is None:
        return todas
    return [p for p in todas if p["anuncio"] == anuncio]


def exigir_item_livre(anuncio):
    presas = pendencias(anuncio)
    if presas:
        raise ItemTrancado(
            "Existe uma acao neste anuncio (%s) sem resultado conhecido, de %s.\n"
            "Pode ter aplicado. Repetir as cegas e o jeito de aplicar duas vezes.\n"
            "Confira o estado real primeiro: python3 promocoes.py  (ou o leitor "
            "da acao) e depois reconcilie com:\n"
            "  python3 promover.py reconciliar %s" % (anuncio, presas[0]["quando"], anuncio)
        )


# ---------------------------------------------------------------- intencao

@contextlib.contextmanager
def trava(alvo):
    """Exclusao mutua ENTRE PROCESSOS para um anuncio ou pergunta.

    Ler-alterar-gravar um arquivo nao e atomico so porque a substituicao e: dois
    terminais podiam consumir o mesmo codigo, reler o mesmo estado e enviar duas
    escritas. Esta trava cobre consumir + reler + abrir a tentativa."""
    nome = re.sub(r"[^A-Za-z0-9_.-]", "_", str(alvo))[:60]
    caminho = RECIBO.parent / (".em-andamento-%s" % nome)
    try:
        fd = os.open(str(caminho), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ItemTrancado(
            "Ja existe uma execucao em andamento para %s nesta pasta.\n"
            "Espere ela terminar. Se voce tem certeza de que nao ha nenhuma "
            "(terminal fechado no meio), apague o arquivo:\n  %s" % (alvo, caminho))
    except OSError as e:
        raise ReciboImpossivel(
            "Nao deu para criar a trava de execucao em %s (%s). Sem trava, duas "
            "execucoes podem enviar duas vezes: nao envio."
            % (caminho.parent, e.__class__.__name__))
    try:
        os.write(fd, ("%d %s\n" % (os.getpid(),
                                   time.strftime("%Y-%m-%dT%H:%M:%S"))).encode())
        os.close(fd)
        yield
    finally:
        try:
            os.unlink(str(caminho))
        except OSError:
            pass


@contextlib.contextmanager
def trava_das_intencoes():
    """O arquivo de intencoes e UM para a pasta inteira.

    Travar por item nao protege ele: dois processos em anuncios diferentes
    liam {A,B}, cada um consumia o seu e gravava — o segundo a gravar
    ressuscitava o codigo que o primeiro tinha queimado."""
    with trava("intencoes"):
        yield


def _ler_intencoes():
    if not INTENCOES.exists():
        return {}
    try:
        dados = json.loads(INTENCOES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    agora = time.time()
    vivas = {k: v for k, v in dados.items() if v.get("vence_em", 0) > agora}
    if len(vivas) != len(dados):
        # Vencida tem de SAIR DO DISCO, nao so ser ignorada na leitura: a
        # intencao de responder carrega o rascunho da resposta, e "expira" que
        # nao apaga nada e so uma filtragem com nome bonito.
        try:
            _gravar_intencoes(vivas)
        except OSError as e:
            # Silenciar isso faria o rascunho ficar no disco contrariando o que
            # a skill promete. Avisar e o minimo honesto.
            print("AVISO: nao deu para apagar conferencia vencida de %s (%s). "
                  "O rascunho continua no arquivo. Rode: python3 escrever.py limpar"
                  % (INTENCOES.name, e.__class__.__name__), file=sys.stderr)
    return vivas


def _gravar_intencoes(dados):
    seguro.gravar_protegido(
        INTENCOES, json.dumps(dados, indent=2, ensure_ascii=False) + "\n")


def _mesmo_alvo(a, b):
    return (a.get("conta") == b.get("conta")
            and a.get("acao") == b.get("acao")
            and a.get("anuncio") == b.get("anuncio")
            and a.get("campanha") == b.get("campanha")
            and a.get("pergunta") == b.get("pergunta"))


def guardar_intencao(dados):
    with trava_das_intencoes():
        return _guardar_intencao(dados)


def _guardar_intencao(dados):
    """Guarda o que a pessoa acabou de conferir e devolve o codigo.

    O codigo nao prova que o mundo nao mudou — prova que a pessoa leu AQUILO.
    Quem prova que aquilo ainda e verdade e a releitura, em `--fazer`.

    Conferir de novo REVOGA a conferencia anterior do mesmo alvo. Sem isso, quem
    corrigisse o texto de uma resposta ficaria com dois codigos validos por dez
    minutos — e o antigo publicaria justamente o texto descartado."""
    atuais = {k: v for k, v in _ler_intencoes().items()
              if not _mesmo_alvo(v, dados)}
    for _ in range(20):
        codigo = hashlib.sha256(
            (json.dumps(dados, sort_keys=True, ensure_ascii=False)
             + os.urandom(6).hex()).encode()).hexdigest()[:4].upper()
        if codigo not in atuais:
            break
    else:
        raise ConferenciaInvalida("nao consegui gerar um codigo novo")
    registro = dict(dados)
    registro["vence_em"] = time.time() + VALIDADE
    atuais[codigo] = registro
    _gravar_intencoes(atuais)
    return codigo


def consumir_intencao(codigo):
    with trava_das_intencoes():
        return _consumir_intencao(codigo)


def _consumir_intencao(codigo):
    """Le, confere e QUEIMA o codigo. Vale uma vez, 10 minutos, naquela conta."""
    atuais = _ler_intencoes()
    registro = atuais.pop((codigo or "").strip().upper(), None)
    if registro is None:
        raise ConferenciaInvalida(
            "Codigo %r nao serve: nao existe, ja foi usado, ou venceu (vale 10 "
            "minutos). Confira de novo para ver o que mudou." % codigo
        )
    _gravar_intencoes(atuais)
    if registro.get("conta") != conta_do_token():
        raise ConferenciaInvalida(
            "Este codigo foi conferido para outra conta. Confira de novo."
        )
    return registro


# -------------------------------------------------------------------- envio

def _sem_segredo(texto):
    """Tira do texto qualquer credencial da pasta, sem precisar saber qual veio.

    Limpa ANTES de truncar: cortar primeiro pode deixar meio token na mensagem,
    e meio token ainda e informacao que nao deveria sair daqui."""
    if not texto:
        return texto
    texto = str(texto)
    sujos = []
    try:
        t = _tokens()
        sujos = [t.get("access_token"), t.get("refresh_token")]
    except Exception:
        pass
    try:
        cfg = meli.carregar_env()
        sujos += [cfg.get("MELI_CLIENT_SECRET"), cfg.get("MELI_APP_ID")]
    except Exception:
        pass
    for s in sujos:
        if s and len(str(s)) >= 8:
            texto = texto.replace(str(s), "***")
    return texto


def _codigo_do_erro(corpo):
    if not isinstance(corpo, dict):
        return None
    causa = corpo.get("cause")
    if isinstance(causa, list) and causa and isinstance(causa[0], dict):
        return causa[0].get("error_code") or causa[0].get("code")
    if isinstance(causa, dict):
        return causa.get("error_code") or causa.get("code")
    return corpo.get("error")


# Codigo de erro e identificador, nao texto livre: o Meli manda coisas como
# NOT_BUY_BOX_WINNER. Qualquer coisa fora desse formato nao e codigo — e pode
# ser a nossa propria chamada voltando no corpo do erro.
_FORMATO_CODIGO = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")


def _erro_da_resposta(status, bruto):
    try:
        corpo = json.loads(bruto) if bruto.strip() else {}
    except ValueError:
        corpo = {}
    codigo = _codigo_do_erro(corpo)
    if codigo is not None and not _FORMATO_CODIGO.match(str(codigo)):
        codigo = None
    if codigo is not None and _sem_segredo(str(codigo)) != str(codigo):
        # O "codigo" trazia uma credencial da pasta. Entao nao e codigo: e a
        # nossa propria chamada voltando no corpo do erro. O formato sozinho nao
        # distingue — NOT_BUY_BOX_WINNER e um token se parecem o bastante.
        codigo = None
    mensagem = corpo.get("message") if isinstance(corpo, dict) else None
    detalhe = _sem_segredo(str(mensagem or bruto))[:300]

    if codigo == ERRO_CORRIDA:
        return OfertaEmProcesso(
            "O Mercado Livre ainda esta processando a oferta anterior deste "
            "anuncio, e por isso NAO aplicou. Espere cerca de 20 segundos, "
            "confira de novo e repita uma vez.", status, codigo)
    if codigo == ERRO_POLITICA:
        return SemPermissao(
            "O Mercado Livre recusou por permissao (%s).\n"
            "Mudar a permissao no DevCenter nao vale para a conexao que ja "
            "existe: autorize de novo com python3 autorizar.py" % codigo)
    # 403 que nao e o de politica NAO manda reautorizar por chute: refazer a
    # autorizacao e um processo inteiro, e mandar a pessoa nele a troco de
    # adivinhacao custa caro.
    conhecidos = {
        "ERROR_CREDIBILITY_DISCOUNTED_PRICE":
            "O Mercado Livre achou este desconto nao crivel para este anuncio.",
        "NOT_BUY_BOX_WINNER":
            "Este anuncio nao e o vencedor da oferta, e por isso nao esta elegivel.",
        "OFFICIAL_STORE_MISMATCH":
            "Esta campanha pertence a outra loja oficial.",
        "START_DATE":
            "Esta campanha nao esta no ar nesta data.",
    }
    if codigo in conhecidos:
        return ErroNaEscrita(conhecidos[codigo], status, codigo)
    return ErroNaEscrita(
        "O Mercado Livre respondeu erro %s%s. %s" % (
            status, (" (%s)" % codigo) if codigo else "", detalhe),
        status, codigo)


def enviar(acao, caminho, params=None, corpo=None, anuncio=None):
    """A unica saida de escrita do pacote. Tudo passa por aqui.

    A ordem e deliberada: o que recusa sem custo vem antes do que gasta, e o
    recibo vem antes do envio."""
    regra = ACOES.get(acao)
    if regra is None:
        raise AcaoRecusada(
            "Acao %r nao existe neste pacote. As que existem: %s."
            % (acao, ", ".join(sorted(ACOES)))
        )
    if not isinstance(caminho, str) or not regra["caminho"].match(caminho):
        raise AcaoRecusada(
            "Recusado: %r nao e um caminho que a acao %r aceita. A lista de "
            "caminhos e fechada, de proposito — nada sai da maquina por aqui."
            % (caminho, acao)
        )
    exigir_permissao(acao)

    etiqueta = anuncio or caminho.rsplit("/", 1)[-1] or acao
    exigir_item_livre(etiqueta)
    exigir_espaco()

    url = API + caminho
    if params:
        url += "?" + urllib.parse.urlencode(params)
    nota = json.dumps(
        {k: v for k, v in (corpo or {}).items() if k != "text"},
        sort_keys=True, ensure_ascii=False) if corpo else (
        json.dumps(params or {}, sort_keys=True, ensure_ascii=False))
    ident = abrir_tentativa(acao, etiqueta, nota)

    token = meli.get_access_token()
    dados = json.dumps(corpo).encode() if corpo is not None else None
    cabecalhos = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    if dados is not None:
        cabecalhos["Content-Type"] = "application/json"
    req = urllib.request.Request(
        url, data=dados, method=regra["metodo"], headers=cabecalhos)

    try:
        with seguro.abrir(req, timeout=60) as r:
            bruto = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        bruto = e.read().decode("utf-8", "replace")
        e.close()
        if e.code >= 500:
            # O servidor recebeu e quebrou. Isso NAO prova que nao aplicou, e
            # resultado sem prova de nao-aplicacao continua incerto: a linha
            # fica aberta e o item trancado.
            raise RespostaIncerta(
                "O Mercado Livre respondeu erro %s (do lado dele). A chamada "
                "chegou, entao PODE ter sido aplicada.\n"
                "Nao vou repetir. Confira o estado real e reconcilie: "
                "python3 promover.py reconciliar %s" % (e.code, etiqueta))
        erro = _erro_da_resposta(e.code, bruto)
        fechar_tentativa(
            ident, "recusado" if isinstance(erro, SemPermissao) else "erro",
            "%s %s" % (e.code, getattr(erro, "codigo", "") or ""))
        raise erro
    except seguro.RedirecionamentoRecusado:
        # O token NAO foi reenviado e a chamada nao chegou ao destino verdadeiro:
        # aqui da para fechar com certeza.
        fechar_tentativa(ident, "erro", "redirecionamento recusado")
        raise
    except Exception as e:
        # Resposta perdida: pode ter aplicado. A linha fica ABERTA de proposito —
        # e ela que tranca o item ate alguem reconciliar por leitura.
        raise RespostaIncerta(
            "A resposta se perdeu (%s). A acao PODE ter sido aplicada.\n"
            "Nao vou repetir: repetir as cegas e o jeito de aplicar duas vezes.\n"
            "Confira o estado real e reconcilie: python3 promover.py reconciliar %s"
            % (e.__class__.__name__, etiqueta))

    try:
        resposta = json.loads(bruto) if bruto.strip() else {}
    except ValueError:
        resposta = {}
    # 2xx nao e confirmacao: a exclusao em promocoes responde 200 e ainda traz
    # falhas no corpo (medido pelo Sentinela). Quem confirma e a releitura.
    erros = resposta.get("errors") if isinstance(resposta, dict) else None
    if isinstance(erros, list) and erros:
        fechar_tentativa(ident, "erro", "2xx com errors no corpo")
        raise ErroNaEscrita(
            "O Mercado Livre respondeu sucesso no transporte, mas com falhas no "
            "corpo. Nao conte como feito: confira o estado real.")
    # De proposito NAO fecha a tentativa aqui. Transporte aceito nao e resultado
    # confirmado, e fechar agora destravaria o item durante a propagacao — a
    # janela em que o 201 ja mentiu tres vezes nesta casa. Quem fecha e quem
    # confirma, chamando confirmado(). Enquanto nao fechar, o item fica trancado.
    return {"resposta": resposta, "recibo": ident, "etiqueta": etiqueta}


def confirmado(ident, nota):
    """Fecha a tentativa DEPOIS de a releitura provar o resultado."""
    fechar_tentativa(ident, "ok", nota)


# --------------------------------------------------------------------- CLI

def _main():
    if len(sys.argv) > 1 and sys.argv[1] == "permissao":
        nomes = escopos_concedidos()
        print("Escopos que a autorizacao desta pasta concedeu:\n")
        for n in nomes:
            print("  " + n)
        print("\nO que cada acao exige:")
        for nome, regra in sorted(ACOES.items()):
            tem = "OK " if regra["escopo"] in nomes else "FALTA"
            print("  %-10s %-5s %s   (%s)" % (nome, tem, regra["escopo"], regra["muda"]))
        presas = pendencias()
        print("\nAcoes sem resultado conhecido: %d" % len(presas))
        for p in presas:
            print("  %s  %s  %s" % (p["quando"], p["acao"], p["anuncio"]))
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == "limpar":
        with trava_das_intencoes():
            antes = len(_ler_intencoes())
        print("Conferencias ainda validas: %d. As vencidas foram apagadas." % antes)
        return 0
    print(__doc__.strip().splitlines()[0])
    print("\nUso:  python3 escrever.py permissao")
    print("      python3 escrever.py limpar      (apaga conferencia vencida)")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
