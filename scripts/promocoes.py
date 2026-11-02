#!/usr/bin/env python3
"""Fila diaria de decisao sobre promocoes do Mercado Livre. SOMENTE LEITURA.

Le as campanhas da conta, separa as que terminam dentro da janela e diz, para
cada uma: quantos dias faltam, quantos anuncios estao dentro, o desconto minimo
exigido e se voce ja aderiu.

Nao adere a promocao, nao muda preco, nao altera anuncio. Toda chamada passa
pelo meli.request, que recusa qualquer metodo que nao seja GET antes de a
requisicao sair do computador.

Uso:
    python3 promocoes.py                 janela de 7 dias
    python3 promocoes.py --janela 14
    python3 promocoes.py --rapido        nao varre a lista de anuncios

O que ele NAO sabe, e diz na cara: se a promocao vai ser renovada, qual a sua
margem depois do desconto, e o desconto exigido anuncio a anuncio.

Compatibilidade: Python 3.8+.
"""
import datetime as dt
import math
import sys

import contrato
import meli

JANELA_PADRAO = 7
MAX_PAGINAS = 20
# Medido contra conta real em 02/11/2026: este endereco aceita ate 50 por pagina.
# Com 100 ele devolve 400, e a skill inteira parava sem dizer a causa.
POR_PAGINA = 50
FUSO = dt.timezone(dt.timedelta(hours=-3))

# Escopo amplo: valem para o catalogo elegivel, entao a lista muda sozinha.
AMPLO = ("DEAL", "MARKETPLACE_CAMPAIGN", "PRICE_MATCHING", "PRICE_MATCHING_MELI_ALL",
         "SMART", "PRE_NEGOTIATED")

ADERIDO = ("started", "active")
ELEGIVEL = ("candidate", "pending")

# Estado que nao esta em nenhuma das duas listas NAO vira elegivel por descarte:
# campanha encerrada apareceria como oportunidade, e o vendedor correria atras de
# uma porta fechada.


def quando(iso):
    """ISO do Mercado Livre -> datetime no fuso de Sao Paulo, ou None."""
    if not iso:
        return None
    texto = str(iso).strip().replace("Z", "+00:00")
    try:
        d = dt.datetime.fromisoformat(texto)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(FUSO)


def _num(v):
    """Percentual pode vir como texto, None, ou numero. Nunca invente zero.

    Recusa bool: `True` viraria 1%. Recusa infinito e NaN, inclusive escritos por
    extenso ("NaN", "Infinity"), que o float() aceita sem reclamar.
    """
    if v is None or v == "" or isinstance(v, bool):
        return None
    try:
        n = round(float(v), 2)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def itens_da_promocao(pid, tipo, buscar=True):
    """Devolve o retrato dos anuncios de uma promocao.

    ELEGIVEL E DENTRO SAO COISAS DIFERENTES, e confundir os dois e o erro mais
    caro aqui: o Mercado Livre lista como `candidate` o anuncio que PODE entrar,
    e como `started` o que JA esta dentro. Somar os dois e dizer "anuncios na
    promocao" faz o vendedor achar que aderiu quando nao aderiu.

    Traz tambem quanto do desconto o Meli banca (`meli_percentage`) e quanto sai
    do bolso do vendedor (`seller_percentage`) — e a informacao que decide se
    vale aderir, porque promocao com rebate protege margem.

    Truncado devolve None em tudo: contagem pela metade apresentada como total
    e pior que contagem nenhuma.
    """
    if not buscar:
        return {"elegiveis": None, "aderidos": None, "truncado": False,
                "meli_banca": None, "voce_banca": None}
    base = "/seller-promotions/promotions/%s/items" % pid
    # Medido contra conta real em 02/11/2026: este endereco aceita ate 50 por
    # pagina. Com 100 ele devolve 400, e a skill inteira parava sem dizer a causa.
    params = {"app_version": "v2", "promotion_type": tipo, "limit": POR_PAGINA}
    elegiveis = 0
    aderidos = 0
    desconhecidos = 0
    meli_pct = []
    seller_pct = []
    visto = None
    for _ in range(MAX_PAGINAS):
        p = dict(params)
        if visto:
            p["search_after"] = visto
        corpo = meli.request("GET", base, p)
        achados = corpo.get("results") if isinstance(corpo, dict) else None
        paginacao = (corpo.get("paging") or {}) if isinstance(corpo, dict) else {}
        if not isinstance(achados, list):
            # Medido contra conta real em 02/11/2026: campanha SEM anuncio nenhum
            # devolve `results: null` com `paging.total: 0` — nao devolve lista
            # vazia. Entao `null` sozinho nao prova resposta quebrada, mas tambem
            # nao prova campanha vazia: quem desempata e o total.
            if paginacao.get("total") == 0 and not elegiveis and not aderidos:
                return {"elegiveis": 0, "aderidos": 0, "truncado": False,
                        "meli_banca": None, "voce_banca": None}
            # Sem o total dizendo zero, e resposta que nao deu para ler, e
            # contagem parcial nao pode sair como completa.
            return _vazio()
        for item in achados:
            estado = (item.get("status") or "").lower()
            if estado in ADERIDO:
                aderidos += 1
            elif estado in ELEGIVEL:
                elegiveis += 1
            else:
                desconhecidos += 1
            m, s = _num(item.get("meli_percentage")), _num(item.get("seller_percentage"))
            meli_pct.append(m)
            seller_pct.append(s)
        visto = (corpo.get("paging") or {}).get("searchAfter")
        if not visto:
            # O cursor e quem diz se acabou. Pagina curta com cursor ainda tem
            # proxima: inferir fim pelo tamanho da pagina perdia o resto.
            if desconhecidos:
                return _vazio()
            return {"elegiveis": elegiveis, "aderidos": aderidos, "truncado": False,
                    "meli_banca": _mediana(meli_pct), "voce_banca": _mediana(seller_pct)}
    return _vazio(truncado=True)


def _vazio(truncado=False):
    return {"elegiveis": None, "aderidos": None, "truncado": True,
            "meli_banca": None, "voce_banca": None}


def _mediana(valores):
    """Mediana, nao media: um anuncio com desconto fora da curva nao desloca.

    `valores` traz UM item por anuncio, com None onde o percentual nao veio.
    Faltando qualquer um, a mediana sai vazia: mediana de parte da campanha
    apresentada como mediana da campanha e numero errado com cara de certo.
    """
    if not valores or any(v is None for v in valores):
        return None
    ordenados = sorted(valores)
    meio = len(ordenados) // 2
    if len(ordenados) % 2:
        return round(ordenados[meio], 2)
    return round((ordenados[meio - 1] + ordenados[meio]) / 2.0, 2)


def coletar(janela=JANELA_PADRAO, rapido=False, hoje=None):
    """Monta o dado no formato do contrato. Nao grava — quem grava e o main."""
    conta = meli.conta_conectada()
    hoje = hoje or dt.datetime.now(FUSO).date()

    corpo = meli.request("GET", "/seller-promotions/users/%s" % conta["id"],
                         {"app_version": "v2"})
    todas = corpo.get("results") or []

    itens = []
    sem_data = 0
    truncou = False
    for p in todas:
        if (p.get("status") or "").lower() not in ("started", "pending"):
            continue
        fim = quando(p.get("finish_date"))
        if not fim:
            sem_data += 1
            continue
        dias = (fim.date() - hoje).days
        if dias < 0 or dias > janela:
            continue

        r = itens_da_promocao(p.get("id"), p.get("type"), buscar=not rapido)
        truncou = truncou or r["truncado"]

        itens.append({
            "promocao": p.get("name") or p.get("type") or "sem nome",
            "tipo": p.get("type"),
            "termina": fim.date().isoformat(),
            "dias_restantes": dias,
            "anuncios_elegiveis": r["elegiveis"],
            "anuncios_aderidos": r["aderidos"],
            "meli_banca_pct": r["meli_banca"],
            "voce_banca_pct": r["voce_banca"],
            "desconto_minimo": _num(p.get("fixed_percentage")),
            "escopo_amplo": (p.get("type") or "") in AMPLO,
        })

    itens.sort(key=lambda i: (i["dias_restantes"], i["promocao"]))

    faltando, lacunas, avisos = [], {}, []

    if rapido:
        for campo in ("anuncios_elegiveis", "anuncios_aderidos"):
            faltando.append(campo)
            lacunas[campo] = (
                "não varremos a lista de anúncios nesta execução — rode sem "
                "--rapido para contar elegíveis e aderidos")
    elif truncou:
        # Contagem pela metade apresentada como total e pior que contagem
        # nenhuma: quem le "1000 anuncios" decide achando que sabe.
        for campo in ("anuncios_elegiveis", "anuncios_aderidos"):
            if campo not in faltando:
                faltando.append(campo)
            lacunas[campo] = (
                "alguma campanha passou do teto de %d páginas e a contagem dela "
                "ficaria menor do que a realidade, então ela vem vazia em vez de "
                "um número que parece certo" % MAX_PAGINAS)
        avisos.append(
            "campanha grande demais para contar inteira nesta execução; as "
            "contagens dela vêm vazias, não zeradas")
    if sem_data:
        avisos.append("%d promoção(ões) sem data de término foram ignoradas" % sem_data)
    if any(i["desconto_minimo"] is None for i in itens):
        faltando.append("desconto_minimo")
        lacunas["desconto_minimo"] = (
            "esta campanha não publica um percentual fixo; o desconto exigido "
            "aparece anúncio a anúncio, no painel do Mercado Livre")

    faltando.append("margem_apos_desconto")
    lacunas["margem_apos_desconto"] = (
        "a API do Mercado Livre não tem o seu custo por SKU, então ninguém aqui "
        "sabe se o desconto cabe na sua margem — essa conta é sua")
    faltando.append("vai_ser_renovada")
    lacunas["vai_ser_renovada"] = (
        "a API não diz se a campanha será renovada, estendida ou reaberta; "
        "só o seu gerente de conta confirma")

    if any(i["escopo_amplo"] for i in itens):
        avisos.append(
            "há campanha de escopo amplo: a lista de elegíveis muda sozinha "
            "conforme o Mercado Livre reavalia a elegibilidade")

    # ELEGIVEL nao e DENTRO. Somar os dois e dizer "anuncios na promocao" faz o
    # vendedor achar que aderiu quando so esta habilitado a aderir.
    avisos.append(
        "elegível e aderido são coisas diferentes: elegível é o anúncio que PODE "
        "entrar na campanha, aderido é o que JÁ está dentro")

    eleg = [i["anuncios_elegiveis"] for i in itens]
    ader = [i["anuncios_aderidos"] for i in itens]
    resumo = {
        "promocoes_na_janela": len(itens),
        "termina_em_3_dias": sum(1 for i in itens if i["dias_restantes"] <= 3),
        "anuncios_elegiveis": None if any(v is None for v in eleg) else sum(eleg),
        "anuncios_ja_aderidos": None if any(v is None for v in ader) else sum(ader),
    }

    return {
        "conta": conta,
        "periodo": {"de": hoje.isoformat(),
                    "ate": (hoje + dt.timedelta(days=janela)).isoformat()},
        "resumo": resumo,
        "itens": itens,
        "faltando": faltando,
        "lacunas": lacunas,
        "avisos": avisos,
    }


def _main():
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    janela = JANELA_PADRAO
    if "--janela" in args:
        pos = args.index("--janela")
        if pos + 1 < len(args):
            try:
                janela = max(1, min(60, int(args[pos + 1])))
            except ValueError:
                print("--janela precisa de um numero de dias. Usando %d." % JANELA_PADRAO)

    d = coletar(janela=janela, rapido="--rapido" in args)
    contrato.gravar("prometheus-promocoes", conta=d["conta"], periodo=d["periodo"],
                    resumo=d["resumo"], itens=d["itens"], faltando=d["faltando"],
                    lacunas=d["lacunas"], avisos=d["avisos"])

    n = d["resumo"]["promocoes_na_janela"]
    if not n:
        print("Nenhuma promocao terminando nos proximos %d dias." % janela)
        print("Gravado assim mesmo: o painel mostra a janela vazia, que tambem e informacao.")
    else:
        print("%d promocao(oes) terminando em ate %d dias." % (n, janela))
        for i in d["itens"][:5]:
            partes = []
            if i["anuncios_aderidos"] is not None:
                partes.append("%d ja dentro" % i["anuncios_aderidos"])
            if i["anuncios_elegiveis"] is not None:
                partes.append("%d elegivel(is)" % i["anuncios_elegiveis"])
            if i["meli_banca_pct"] is not None:
                partes.append("Meli banca %.1f%%" % i["meli_banca_pct"])
            print("  %-30s termina em %d dia(s)%s" % (
                i["promocao"][:30], i["dias_restantes"],
                (" · " + " · ".join(partes)) if partes else ""))
    print("\nVeja no painel:  python3 painel.py")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(_main())
    except (meli.SemAutorizacao, meli.CredenciaisIncompletas) as e:
        sys.exit("PARADO: %s" % e)
    except meli.ErroDaAPI as e:
        sys.exit("PARADO: %s" % e)
