#!/usr/bin/env python3
"""Cliente somente leitura da API do Mercado Livre, com renovacao automatica de token.

CLI:
    python3 meli.py check               # diz se as credenciais estao preenchidas
                                        # (sem mostrar nenhum valor)
    python3 meli.py me                  # GET /users/me — confirma qual conta conectou
    python3 meli.py get /users/me       # GET em qualquer path

Nenhum comando imprime token, Client Secret ou App ID. Esses valores nunca
devem aparecer em chat, print ou log.

Biblioteca:
    from meli import api, conta_conectada
    eu = api("/users/me")

SOMENTE LEITURA: api() levanta PermissionError para qualquer metodo que nao
seja GET, antes de a chamada sair do computador. Nenhum script deste pacote
consegue aderir a promocao, mudar preco, estoque, anuncio ou campanha, nem
responder pergunta ou enviar mensagem — mesmo que alguem peca.

Compatibilidade: Python 3.8+ (macOS ainda sai com 3.9).
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pasta  # mesma pasta dos scripts; usa fechado()
import seguro

BASE = Path(__file__).resolve().parent
# aceita credenciais.txt (visivel no Finder) ou .env
ENV_FILE = next(
    (BASE / n for n in ("credenciais.txt", ".env") if (BASE / n).exists()),
    BASE / "credenciais.txt",
)
TOKENS_FILE = BASE / "tokens.json"
API = "https://api.mercadolibre.com"
MARGEM_SEG = 600  # renova 10 min antes de expirar

CHAVES = ("MELI_APP_ID", "MELI_CLIENT_SECRET", "MELI_REDIRECT_URI")


class CredenciaisIncompletas(RuntimeError):
    """credenciais.txt nao existe ou tem campo vazio."""


class SemAutorizacao(RuntimeError):
    """Ainda nao foi feita a autorizacao (nao existe tokens.json)."""


class ErroDaAPI(RuntimeError):
    """A API respondeu com erro. Guarda o codigo HTTP em .status."""

    def __init__(self, status, mensagem):
        super().__init__(mensagem)
        self.status = status


def _ler_arquivo_env():
    vals = {}
    if not ENV_FILE.exists():
        return vals
    for linha in ENV_FILE.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        k, v = linha.split("=", 1)
        vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


def carregar_env():
    """Credenciais do arquivo da pasta (ou do ambiente). Levanta
    CredenciaisIncompletas quando falta algo, sem revelar valor nenhum."""
    cfg = _ler_arquivo_env()
    for k in CHAVES:
        cfg[k] = os.environ.get(k) or cfg.get(k, "")
    faltando = [k for k in CHAVES if not cfg[k]]
    if faltando:
        raise CredenciaisIncompletas(
            "Faltam valores em %s: %s. Abra o arquivo, preencha depois do '=' e salve."
            % (ENV_FILE.name, ", ".join(faltando))
        )
    return cfg


def situacao_credenciais():
    """Para o comando check: diz apenas 'preenchido' ou 'VAZIO' por chave.
    Nunca devolve o valor."""
    vals = _ler_arquivo_env()
    estado = {}
    for k in CHAVES:
        estado[k] = "preenchido" if (os.environ.get(k) or vals.get(k)) else "VAZIO"
    return {
        "arquivo": ENV_FILE.name,
        "arquivo_existe": ENV_FILE.exists(),
        "chaves": estado,
        "tokens": TOKENS_FILE.exists(),
    }


def post_form(url, dados):
    corpo = urllib.parse.urlencode(dados).encode()
    req = urllib.request.Request(
        url,
        data=corpo,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        # Sem seguir redirecionamento: o corpo leva Client Secret e um 302
        # reenviaria o segredo para um host que nao escolhemos.
        with seguro.abrir(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        bruto = e.read().decode("utf-8", "replace")
        raise ErroDaAPI(e.code, traduzir_erro(e.code, bruto))


def traduzir_erro(status, bruto):
    """Mensagem em portugues para os erros que mais aparecem, em vez de
    despejar o JSON do Mercado Livre na cara da pessoa."""
    texto = (bruto or "").lower()
    if "invalid_operator_user_id" in texto:
        return ("Essa conta e de operador/colaborador. A autorizacao precisa ser feita "
                "com a conta ADMINISTRADORA da loja.")
    if "invalid_grant" in texto:
        return ("A autorizacao expirou ou ja foi usada. Rode a conexao de novo: "
                "python3 autorizar.py")
    if "invalid_client" in texto:
        return ("App ID ou Client Secret nao conferem. Confira os dois no DevCenter e "
                "no arquivo de credenciais.")
    if "redirect_uri" in texto:
        return ("A URL de retorno nao e identica a cadastrada na aplicacao. Ela precisa "
                "bater caractere por caractere.")
    if status == 403:
        return ("Sem permissao (403). Falta marcar uma permissao funcional no DevCenter, "
                "ou o IP esta bloqueado.")
    if status == 429:
        return "Muitas chamadas seguidas (429). Espere alguns segundos e tente de novo."
    if status == 401:
        return "Acesso expirado (401). Rode de novo: python3 autorizar.py"
    return "O Mercado Livre respondeu com erro %s." % status


def salvar_tokens(resp):
    dados = {
        "access_token": resp["access_token"],
        "refresh_token": resp.get("refresh_token", ""),
        "user_id": resp.get("user_id"),
        "scope": resp.get("scope", ""),
        "expires_at": int(time.time()) + int(resp.get("expires_in", 21600)),
        "atualizado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    # Este e o arquivo mais sensivel da pasta, e ele nasce DEPOIS que o
    # pasta.py rodou — a verificacao tem de acontecer aqui. Gravacao atomica
    # com a permissao fechada desde a abertura: gravar primeiro e fechar
    # depois deixava o token legivel por outros usuarios da maquina nesse
    # intervalo. Mesma regra de sempre: medir o resultado, nunca confiar na
    # chamada.
    dados.update(seguro.gravar_protegido(
        TOKENS_FILE, json.dumps(dados, indent=2, ensure_ascii=False) + "\n"))
    return dados


def trocar_code_por_token(code, code_verifier=None):
    cfg = carregar_env()
    dados = {
        "grant_type": "authorization_code",
        "client_id": cfg["MELI_APP_ID"],
        "client_secret": cfg["MELI_CLIENT_SECRET"],
        "code": code,
        "redirect_uri": cfg["MELI_REDIRECT_URI"],
    }
    if code_verifier:
        dados["code_verifier"] = code_verifier
    return salvar_tokens(post_form(API + "/oauth/token", dados))


def get_access_token(forcar=False):
    """access_token valido, renovando pelo refresh_token quando preciso.

    O refresh_token do Mercado Livre e de USO UNICO: cada renovacao devolve um
    novo, que substitui o anterior em disco. Gravar errado aqui derruba a
    conexao algumas horas depois, por isso salvar_tokens roda antes de a
    funcao devolver o token."""
    if not TOKENS_FILE.exists():
        raise SemAutorizacao(
            "Ainda nao conectei nenhuma conta. Rode primeiro: python3 autorizar.py"
        )
    t = json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
    if not forcar and t.get("expires_at", 0) - MARGEM_SEG > time.time():
        return t["access_token"]
    if not t.get("refresh_token"):
        raise SemAutorizacao(
            "A conexao nao tem renovacao automatica. Refaca: python3 autorizar.py"
        )
    cfg = carregar_env()
    novo = post_form(
        API + "/oauth/token",
        {
            "grant_type": "refresh_token",
            "client_id": cfg["MELI_APP_ID"],
            "client_secret": cfg["MELI_CLIENT_SECRET"],
            "refresh_token": t["refresh_token"],
        },
    )
    return salvar_tokens(novo)["access_token"]


# Repetir so faz sentido para limite de chamadas e falha passageira do servidor.
# 401 e 403 nao melhoram com insistencia, e 404 muito menos.
REPETIVEIS = (429, 500, 502, 503, 504)
ESPERAS = (2.0, 5.0, 12.0)


def request(metodo, path, params=None):
    """Porta unica de saida para a API. Recusa tudo que nao for leitura."""
    if str(metodo).upper() != "GET":
        raise PermissionError(
            "Recusado: este pacote so faz leitura (GET). Metodo pedido: %s. "
            "Nada e alterado na sua conta." % metodo
        )
    url = API + path
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    headers = {
        "Authorization": "Bearer " + get_access_token(),
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, method="GET", headers=headers)
    # O limite de chamadas e da CONTA, nao do aplicativo: se a pessoa tem outra
    # integracao rodando, o 429 chega sem ela ter feito nada demais. Desistir na
    # primeira negativa faria uma skill inteira parar no meio por causa de um
    # segundo de espera. So GET chega aqui, entao repetir e seguro.
    for tentativa in range(len(ESPERAS) + 1):
        try:
            with seguro.abrir(req, timeout=60) as r:
                bruto = r.read().decode("utf-8", "replace")
                return json.loads(bruto) if bruto.strip() else {}
        except urllib.error.HTTPError as e:
            if e.code not in REPETIVEIS or tentativa >= len(ESPERAS):
                bruto = e.read().decode("utf-8", "replace")
                raise ErroDaAPI(e.code, traduzir_erro(e.code, bruto))
            espera = ESPERAS[tentativa]
            pedido = e.headers.get("Retry-After") if e.headers else None
            if pedido:
                try:
                    # O servidor sabe melhor que a gente quanto esperar.
                    espera = max(espera, min(60.0, float(pedido)))
                except (TypeError, ValueError):
                    pass
            e.close()
            time.sleep(espera)


def api(path, params=None):
    """Leitura autenticada. path comeca com '/'."""
    return request("GET", path, params=params)


def conta_conectada():
    """Identificacao da conta, no formato do contrato de dados:
    {'id': ..., 'apelido': ..., 'site': ...}

    O id vem do tokens.json quando esta la (gravado na autorizacao); se nao
    estiver, pergunta a API. Nada fica fixo no codigo, entao os mesmos scripts
    servem para qualquer conta."""
    eu = api("/users/me")
    return {
        "id": int(eu["id"]),
        "apelido": eu.get("nickname") or "",
        "site": eu.get("site_id") or "MLB",
    }


def _main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd = args[0]
    if cmd == "check":
        s = situacao_credenciais()
        if not s["arquivo_existe"]:
            print("NAO ENCONTRADO: %s" % s["arquivo"])
            return 1
        for k, v in s["chaves"].items():
            print("%-22s %s" % (k, v))
        print("%-22s %s" % ("conexao", "feita" if s["tokens"] else "ainda nao (rode autorizar.py)"))
        return 1 if "VAZIO" in s["chaves"].values() else 0
    if cmd == "me":
        c = conta_conectada()
        print(json.dumps(c, indent=2, ensure_ascii=False))
        return 0
    if cmd == "get":
        if len(args) < 2:
            print("Uso: python3 meli.py get /algum/path")
            return 2
        print(json.dumps(api(args[1]), indent=2, ensure_ascii=False))
        return 0
    print("Comando desconhecido: %s (use check | me | get)" % cmd)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(_main())
    except (CredenciaisIncompletas, SemAutorizacao, ErroDaAPI, PermissionError) as e:
        sys.exit(str(e))
