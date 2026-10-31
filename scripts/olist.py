#!/usr/bin/env python3
"""Importa da Olist (Tiny) o que o marketplace nao tem: o CUSTO do produto.

Por que isto e importacao e nao conexao viva — e o motivo mudou em 22/10/2026,
quando as integracoes de producao do Marvin contradisseram a documentacao:

A renovacao da Olist NAO morre em um dia. Cada renovacao devolve um refresh
novo e reinicia o prazo (rotacao), e nas integracoes que rodam de verdade a
conexao se mantem por semanas. O que importa aqui e outra coisa: este pacote
e um programa de mesa, nao um cron. Ele so roda quando a pessoa abre. Se ela
passar um tempo sem abrir, a conexao vence — e custo de produto nao muda todo
dia.

Entao a gente puxa o custo, grava na pasta, e o painel usa o arquivo. O cruzamento
de margem continua funcionando dias depois, com a conexao ja vencida. Isso tambem poupa
o limite de chamadas, que e da CONTA e nao do aplicativo: varrer catalogo aqui
atrapalharia as outras integracoes dela.

SOMENTE LEITURA: api() levanta PermissionError para qualquer metodo que nao
seja GET, antes de a chamada sair do computador.

Compatibilidade: Python 3.8+, sem dependencia externa.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import seguro

BASE = Path(__file__).resolve().parent
TOKENS_FILE = BASE / "tokens-olist.json"
CUSTOS_FILE = BASE / "prometheus-custos.json"

CONTAS = "https://accounts.tiny.com.br/realms/tiny/protocol/openid-connect"
AUTORIZAR = CONTAS + "/auth"
TOKEN = CONTAS + "/token"
API = "https://api.tiny.com.br/public-api/v3"

# O access_token observado nas integracoes de producao vem com expires_in de
# 21600 (6 horas). Renova 5 minutos antes.
MARGEM_SEG = 300


class SemAutorizacao(RuntimeError):
    """Ainda nao foi importado nada da Olist nesta pasta."""


class PrecisaReconectar(RuntimeError):
    """A renovacao venceu. Quem decide isso e o servidor, nao um prazo nosso."""


class ErroDaAPI(RuntimeError):
    """A Olist respondeu com erro."""


def link_de_autorizacao(client_id, redirect_uri, state=None):
    """OAuth2 padrao, no Keycloak da Tiny. Escopo minimo: openid.

    O `state` vincula o retorno a ESTA tentativa: sem ele, qualquer `?code=`
    colado seria aceito como resposta ao nosso pedido."""
    dados = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "openid",
        "response_type": "code",
    }
    if state:
        dados["state"] = state
    return "%s?%s" % (AUTORIZAR, urllib.parse.urlencode(dados))


def ler_retorno(endereco, cadastrado=None, state_esperado=None):
    """Tira o code do endereco colado, conferindo de onde ele veio.

    Duas conferencias, e as duas tambem pegam o erro comum do dia a dia (colar
    a URL da aba errada): o endereco tem de ser o cadastrado no aplicativo, e
    o `state` tem de ser o da tentativa que esta em andamento."""
    if cadastrado:
        seguro.conferir_origem(endereco, cadastrado)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(endereco).query)
    if state_esperado:
        veio = (q.get("state") or [""])[0]
        if veio != state_esperado:
            raise ValueError(
                "Esse endereco e de outra tentativa de conexao, nao da que esta "
                "em andamento. Refaca o passo 1:  python3 autorizar_olist.py"
            )
    code = (q.get("code") or [""])[0]
    if not code:
        raise ValueError(
            "Nao achei o code nesse endereco. Cole a barra INTEIRA do navegador "
            "depois de autorizar — ela tem ?code=..."
        )
    return code


def _form(dados):
    req = urllib.request.Request(
        TOKEN,
        data=urllib.parse.urlencode(dados).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with seguro.abrir(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", "replace")
        if "invalid_grant" in corpo:
            raise PrecisaReconectar(_recado_de_reconexao())
        raise ErroDaAPI("A Olist recusou a troca de token (HTTP %s)." % e.code)


def _recado_de_reconexao():
    return (
        "A conexao com a Olist venceu e precisa ser refeita. Nao se perdeu nada: "
        "o custo que ja foi importado continua na pasta e o painel segue "
        "funcionando. Para trazer custo novo, reconecte com:\n"
        "  python3 autorizar_olist.py"
    )


def salvar_tokens(dado, refresh_anterior=None):
    """Guarda o acesso ja com a permissao fechada, por substituicao atomica.

    Dois cuidados que a Olist exige e os outros canais nao:

    - ROTACAO: cada renovacao devolve um refresh novo e invalida o anterior.
      Se a resposta vier sem refresh, guardar vazio apagaria a conexao de quem
      estava funcionando — entao mantemos o anterior.
    - PRAZO: a Olist nem sempre informa quanto tempo a renovacao ainda vale.
      Quando ela nao informa, nao inventamos data: quem decide se a renovacao
      morreu e o servidor, na hora de usar. Inventar um prazo curto faria o
      pacote recusar renovar uma conexao que ainda estava boa.
    """
    agora = int(time.time())
    conteudo = {
        "access_token": dado["access_token"],
        "refresh_token": dado.get("refresh_token") or (refresh_anterior or ""),
        "expires_at": agora + int(dado.get("expires_in", 21600)),
        "atualizado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if dado.get("refresh_expires_in"):
        conteudo["refresh_expires_at"] = agora + int(dado["refresh_expires_in"])
    estado = seguro.gravar_protegido(
        TOKENS_FILE, json.dumps(conteudo, indent=2, ensure_ascii=False) + "\n")
    conteudo.update(estado)
    return conteudo


def trocar_code_por_token(code, client_id, client_secret, redirect_uri):
    return salvar_tokens(_form({
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "code": code,
    }))


def _carregar():
    if not TOKENS_FILE.exists():
        raise SemAutorizacao(
            "Ainda nao conectei a Olist nesta pasta. Rode: python3 autorizar_olist.py")
    return json.loads(TOKENS_FILE.read_text(encoding="utf-8"))


def token_valido(client_id, client_secret):
    """Devolve um access_token util, renovando se precisar.

    Só desiste sem tentar quando o proprio servidor informou um prazo de
    renovacao e esse prazo passou. Na ausencia de prazo, tenta renovar: o
    `invalid_grant` e a unica resposta autoritativa sobre a conexao ter
    morrido, e e traduzido em recado de reconexao."""
    t = _carregar()
    agora = int(time.time())
    if t["expires_at"] - MARGEM_SEG > agora:
        return t["access_token"]
    prazo = t.get("refresh_expires_at")
    if prazo and prazo <= agora:
        raise PrecisaReconectar(_recado_de_reconexao())
    if not t.get("refresh_token"):
        raise PrecisaReconectar(_recado_de_reconexao())
    novo = _form({
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": t["refresh_token"],
    })
    return salvar_tokens(novo, refresh_anterior=t["refresh_token"])["access_token"]


def api(metodo, caminho, token=None, **parametros):
    """Chamada a API. SO GET — qualquer outro metodo para aqui."""
    if metodo.upper() != "GET":
        raise PermissionError(
            "Este pacote e somente leitura: recusei %s em %s antes de a chamada "
            "sair do seu computador. Alterar produto, pedido ou preco se faz no "
            "proprio ERP, por voce." % (metodo.upper(), caminho)
        )
    url = API + caminho
    if parametros:
        url += "?" + urllib.parse.urlencode(parametros)
    req = urllib.request.Request(
        url, headers={"Authorization": "Bearer %s" % token, "Accept": "application/json"})
    try:
        # Sem seguir redirecionamento: um 302 reenviaria o Bearer para outro host.
        with seguro.abrir(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise ErroDaAPI(
                "A Olist recusou (401). Na documentacao dela isso quase nunca e "
                "chave errada: e o USUARIO logado sem permissao no modulo que a "
                "API pediu. Confira o perfil do usuario, nao a credencial.")
        if e.code == 429:
            raise ErroDaAPI(
                "Passou do limite de chamadas. O limite e por CONTA e nao por "
                "aplicativo: todas as integracoes dela dividem a mesma cota. "
                "Espere um pouco e puxe menos produtos de uma vez.")
        raise ErroDaAPI("A Olist respondeu HTTP %s." % e.code)


def custo_do_produto(id_produto, token):
    """Le o custo no DETALHE do produto: GET /produtos/{id}.

    Caminho descoberto contra o servidor em 22/10/2026, e o anterior estava
    errado de um jeito que nenhum teste pegava: `/produtos/{id}/preco` existe,
    mas e endpoint de GRAVAR preco. Em GET ele responde 400 com "O metodo GET
    nao e compativel com o recurso solicitado". A skill inteira prometia um
    custo que nunca chegaria.

    O detalhe traz os dois de uma vez, numa chamada so — o que importa quando
    o limite de chamadas e da conta inteira:
      precos.precoCusto, precos.precoCustoMedio
      custos[] com o historico por data"""
    d = api("GET", "/produtos/%s" % id_produto, token=token)
    precos = d.get("precos") or {}
    historico = d.get("custos") or []
    return {
        "id_produto": id_produto,
        "sku": d.get("sku"),
        "preco_custo": precos.get("precoCusto"),
        "custo_medio": precos.get("precoCustoMedio"),
        "preco_venda": precos.get("preco"),
        "custo_mais_recente_em": (historico[-1].get("data") if historico else None),
    }


def gravar_custos(itens):
    """Grava o custo importado na pasta, no contrato de dados do pacote.

    capturado_em e a hora da importacao — e o que diz a idade do custo. Sem
    isso o painel apresentaria custo de semanas atras como se fosse de hoje."""
    agora = time.strftime("%Y-%m-%dT%H:%M:%S%z") or time.strftime("%Y-%m-%dT%H:%M:%S")
    doc = {
        "contrato": "1",
        "skill": "prometheus-conectar-olist",
        "fonte": "olist",
        "gerado_em": agora,
        "capturado_em": agora,
        "itens": list(itens),
    }
    CUSTOS_FILE.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"arquivo": str(CUSTOS_FILE), "itens": len(doc["itens"])}


def custos_guardados():
    """O custo por SKU, para cruzar com a venda. None quando nunca foi importado."""
    if not CUSTOS_FILE.exists():
        return None
    return json.loads(CUSTOS_FILE.read_text(encoding="utf-8"))
