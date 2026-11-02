#!/usr/bin/env python3
"""Conversao, estoque e saude dos anuncios que vendem. SOMENTE LEITURA.

Responde a pergunta que o painel do Mercado Livre nao responde por anuncio:
de quem olhou, quantos compraram.

Por que so os que vendem: esta conta tem milhares de anuncios ativos, e as
visitas custam UMA CHAMADA POR ANUNCIO. Varrer tudo nao cabe numa coleta que a
pessoa roda ao vivo. Entao a gente olha os que mais faturaram na janela — que
sao os que doem quando convertem mal — e DIZ quantos ficaram de fora.

Depende do leitor de pedidos ter rodado: e dele que vem quem vendeu e quanto.

Uso:
    python3 anuncios.py
    python3 anuncios.py --quantos 60

Compatibilidade: Python 3.8+.
"""
import datetime as dt
import sys

import contrato
import meli

QUANTOS_PADRAO = 40
POR_LOTE = 20
FUSO = dt.timezone(dt.timedelta(hours=-3))

ATRIBUTOS = ("id,title,price,available_quantity,sold_quantity,status,"
             "sub_status,health,listing_type_id")

# So situacao conhecida vai para o arquivo: ele vira painel compartilhado, e
# valor que veio do servidor e que a gente nao reconhece nao e publicado.
SITUACOES = {"active": "ativo", "paused": "pausado", "closed": "encerrado",
             "under_review": "em revisão", "inactive": "inativo"}
SUB_SITUACOES = {
    "deleted": "apagado",
    "freeze": "congelado pelo Mercado Livre",
    "suspended": "suspenso",
    "out_of_stock": "sem estoque",
    "waiting_for_patch": "esperando correção",
    "picture_download_pending": "imagem pendente",
}


def _num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def _inteiro(v):
    if isinstance(v, bool) or not isinstance(v, int):
        return None
    return v


def _vendas_da_janela():
    """Le o arquivo do leitor de pedidos. Devolve (por_anuncio, periodo, dias)."""
    d = contrato.carregar("prometheus-pedidos")
    if not d:
        return None, None, None
    por_anuncio = {}
    for pedido in (d.get("itens") or []):
        for linha in (pedido.get("linhas") or []):
            mlb = linha.get("mlb")
            unidades = _inteiro(linha.get("unidades"))
            preco = _num(linha.get("preco_unitario"))
            if not mlb or unidades is None or preco is None:
                continue
            atual = por_anuncio.setdefault(mlb, {"unidades": 0, "faturamento": 0.0,
                                                 "titulo": linha.get("titulo")})
            atual["unidades"] += unidades
            atual["faturamento"] = round(atual["faturamento"] + preco * unidades, 2)
    periodo = d.get("periodo") or {}
    dias = None
    try:
        de = dt.date.fromisoformat(periodo.get("de"))
        ate = dt.date.fromisoformat(periodo.get("ate"))
        dias = (ate - de).days + 1
    except (TypeError, ValueError):
        dias = None
    return por_anuncio, periodo, dias


def _dados_dos_anuncios(ids):
    """Lote de /items. Devolve (por_id, nao_lidos). Erro no 1o lote sobe."""
    por_id = {}
    nao_lidos = 0
    for inicio in range(0, len(ids), POR_LOTE):
        lote = ids[inicio:inicio + POR_LOTE]
        try:
            resposta = meli.request("GET", "/items",
                                    {"ids": ",".join(lote), "attributes": ATRIBUTOS})
        except meli.ErroDaAPI:
            if inicio == 0:
                raise
            nao_lidos += len(lote)
            continue
        if not isinstance(resposta, list):
            if inicio == 0:
                raise meli.ErroDaAPI(
                    502, "a resposta do Mercado Livre veio fora do formato esperado")
            nao_lidos += len(lote)
            continue
        for entrada in resposta:
            if not isinstance(entrada, dict) or entrada.get("code") != 200:
                nao_lidos += 1
                continue
            corpo = entrada.get("body")
            if isinstance(corpo, dict) and corpo.get("id"):
                por_id[corpo["id"]] = corpo
    return por_id, nao_lidos


def _visitas(mlb, dias):
    """Visitas na janela, ou None. None NAO e zero: zero significa ninguem olhou."""
    try:
        d = meli.api("/items/%s/visits/time_window" % mlb,
                     {"last": dias, "unit": "day"})
    except meli.ErroDaAPI:
        return None
    if not isinstance(d, dict):
        return None
    return _inteiro(d.get("total_visits"))


def coletar(quantos=QUANTOS_PADRAO, hoje=None):
    """Monta o dado no formato do contrato. Nao grava — quem grava e o main."""
    conta = meli.conta_conectada()
    hoje = hoje or dt.datetime.now(FUSO).date()

    vendas, periodo, dias = _vendas_da_janela()
    if vendas is None:
        raise meli.ErroDaAPI(
            0, "rode primeiro o leitor de pedidos: e dele que vem quem vendeu "
               "na janela. Comando: python3 pedidos.py")
    if not dias:
        raise meli.ErroDaAPI(
            0, "o arquivo de pedidos nao diz o periodo que cobre, entao nao da "
               "para pedir as visitas da mesma janela. Rode python3 pedidos.py de novo")

    ordenados = sorted(vendas.items(), key=lambda par: -par[1]["faturamento"])
    escolhidos = ordenados[:quantos]
    deixados = len(ordenados) - len(escolhidos)

    dados, nao_lidos = _dados_dos_anuncios([mlb for mlb, _ in escolhidos])

    itens = []
    sem_visita = 0
    sem_dado = 0
    for mlb, venda in escolhidos:
        anuncio = dados.get(mlb) or {}
        if not anuncio:
            sem_dado += 1
        visitas = _visitas(mlb, dias)
        if visitas is None:
            sem_visita += 1
        unidades = venda["unidades"]
        conversao = None
        if visitas:
            conversao = round(100.0 * unidades / visitas, 2)
        situacao = SITUACOES.get(anuncio.get("status"))
        sub = [SUB_SITUACOES[s] for s in (anuncio.get("sub_status") or [])
               if s in SUB_SITUACOES]
        estoque = _inteiro(anuncio.get("available_quantity"))
        itens.append({
            "mlb": mlb,
            "titulo": anuncio.get("title") or venda.get("titulo"),
            "faturamento": venda["faturamento"],
            "vendas": unidades,
            "visitas": visitas,
            "conversao_pct": conversao,
            "preco": _num(anuncio.get("price")),
            "estoque": estoque,
            "situacao": situacao,
            "alertas": sub,
            "saude": _num(anuncio.get("health")),
        })

    faltando, lacunas, avisos = [], {}, []

    def falta(campo, porque):
        if campo not in faltando:
            faltando.append(campo)
        lacunas[campo] = porque

    cobertura = not sem_visita and not sem_dado and not nao_lidos
    conversoes = [i["conversao_pct"] for i in itens if i["conversao_pct"] is not None]
    if not cobertura or not conversoes:
        falta("conversao_mediana",
              "nem todos os anúncios desta lista tiveram visitas ou dados lidos, "
              "então uma mediana aqui falaria por quem não foi medido")
        mediana = None
    else:
        ordem = sorted(conversoes)
        meio = len(ordem) // 2
        mediana = (ordem[meio] if len(ordem) % 2
                   else round((ordem[meio - 1] + ordem[meio]) / 2.0, 2))

    if deixados:
        avisos.append("esta leitura olhou os %d anúncios que mais faturaram na janela; "
                      "outros %d venderam e ficaram de fora" % (len(escolhidos), deixados))
    if sem_visita:
        avisos.append("%d anúncio(s) não tiveram as visitas lidas; a conversão deles "
                      "fica vazia, não zerada" % sem_visita)
    if nao_lidos or sem_dado:
        avisos.append("%d anúncio(s) não tiveram os dados lidos; preço, estoque e "
                      "situação deles ficam vazios" % max(nao_lidos, sem_dado))

    falta("custo_e_margem",
          "a API não tem o seu custo por SKU, então conversão boa não quer dizer "
          "venda lucrativa; cruze com a planilha ou com a Olist")

    avisos.append("conversão aqui é venda dividida por visita no mesmo período do "
                  "arquivo de pedidos (%s a %s), contada por unidade vendida"
                  % (periodo.get("de"), periodo.get("ate")))

    itens.sort(key=lambda i: (i["conversao_pct"] is None, i["conversao_pct"] or 0))

    resumo = {
        "anuncios_olhados": len(itens),
        "conversao_mediana_pct": mediana,
        "sem_estoque": sum(1 for i in itens if i["estoque"] == 0),
        "pausados": sum(1 for i in itens if i["situacao"] == "pausado"),
        "com_alerta": sum(1 for i in itens if i["alertas"]),
        "janela_em_dias": dias,
    }

    return {
        "conta": conta,
        "periodo": periodo,
        "resumo": resumo,
        "itens": itens,
        "faltando": faltando,
        "lacunas": lacunas,
        "avisos": avisos,
    }


def _main():
    args = sys.argv[1:]
    quantos = QUANTOS_PADRAO
    if "--quantos" in args:
        pos = args.index("--quantos")
        if pos + 1 < len(args):
            try:
                quantos = max(1, min(200, int(args[pos + 1])))
            except ValueError:
                print("--quantos precisa de um numero. Usando %d." % QUANTOS_PADRAO)

    d = coletar(quantos=quantos)
    contrato.gravar("prometheus-anuncios", conta=d["conta"], periodo=d["periodo"],
                    resumo=d["resumo"], itens=d["itens"], faltando=d["faltando"],
                    lacunas=d["lacunas"], avisos=d["avisos"])
    r = d["resumo"]
    print("Loja: %s" % d["conta"].get("apelido"))
    print("Janela: %s dias" % r["janela_em_dias"])
    print("")
    print("%-26s %d" % ("Anuncios olhados", r["anuncios_olhados"]))
    if r["conversao_mediana_pct"] is not None:
        print("%-26s %.2f%%" % ("Conversao mediana", r["conversao_mediana_pct"]))
    print("%-26s %d" % ("Sem estoque", r["sem_estoque"]))
    print("%-26s %d" % ("Pausados", r["pausados"]))
    print("")
    print("Os que mais recebem visita e menos vendem:")
    for i in d["itens"][:6]:
        if i["conversao_pct"] is None:
            continue
        print("  %-14s %5s visitas · %2d venda(s) · %4.2f%% · R$ %9.2f" % (
            i["mlb"], i["visitas"], i["vendas"], i["conversao_pct"], i["faturamento"]))
    for aviso in d["avisos"]:
        print("  aviso: %s" % aviso)
    print("\nVeja no painel:  python3 painel.py")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(_main())
    except (meli.SemAutorizacao, meli.CredenciaisIncompletas) as e:
        sys.exit("PARADO: %s" % e)
    except meli.ErroDaAPI as e:
        sys.exit("PARADO: %s" % e)
