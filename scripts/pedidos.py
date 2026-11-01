#!/usr/bin/env python3
"""O que a loja vendeu na janela. SOMENTE LEITURA.

Tres coisas, e so:
  - faturamento da janela
  - os ultimos pedidos
  - a tarifa que veio em cada item do pedido

NAO calcula margem, NAO julga nada. Grava o arquivo no contrato; quem cruza e o
Claude, quem mostra e o painel.

Uso:
    python3 pedidos.py                ultimos 60 dias
    python3 pedidos.py --janela 90

Armadilhas que este script evita de proposito:
  - falha de rede NAO vira "zero vendas": erro na primeira pagina para tudo.
  - pagina que escorrega nao duplica pedido: tudo e deduplicado por id.
  - pedido pago sem valor nao some calado: fica de fora da soma, aparece no aviso,
    e o resumo se declara incompleto.
  - moedas diferentes nao se somam.
  - a tarifa do item NAO e somada: ainda nao foi confirmado contra pedido real se
    ela e por unidade ou pela linha inteira, e somar errado da um numero plausivel.

Compatibilidade: Python 3.8+.
"""
import datetime as dt
import math
import sys

import contrato
import meli

JANELA_PADRAO = 60
POR_PAGINA = 50
MAX_PAGINAS = 20
FUSO = dt.timezone(dt.timedelta(hours=-3))

# Enquanto a unidade da tarifa nao for confirmada contra pedido real, o total nao
# existe. A spec diz como confirmar: mesmo anuncio em quantidades diferentes, mais
# a tarifa publicada para uma unidade naquele preco.
# Medido contra conta real em 31/10/2026: a tarifa que a API manda e POR UNIDADE.
# O mesmo anuncio a R$ 10,63 vendido em quantidade 1, 2, 6, 10 e 15 teve tarifa de
# 1,75 / 1,75 / 1,67 / 1,67 / 1,67 — se fosse da linha, a de 15 seria quinze vezes
# maior. Entao o total da linha e tarifa x quantidade. Tratar como total da linha
# dividiria a comissao pela quantidade, e o numero continuaria plausivel.
AVISO_TARIFA = (
    "a comissão é a informada no pedido no momento da coleta, por unidade, "
    "multiplicada pela quantidade. Ajuste, estorno ou taxa cobrada fora do pedido "
    "não aparecem aqui"
)


def _iso(momento):
    return momento.strftime("%Y-%m-%dT%H:%M:%S.000-03:00")


def _numero(valor):
    """So aceita numero de verdade. Qualquer outra coisa vira None, nunca zero.

    Recusa bool de proposito: `True` viraria R$ 1,00 sem ninguem perceber.
    Recusa infinito e NaN: alem de errado, NaN nem e JSON valido.
    Recusa texto numerico: o contrato manda dinheiro como numero, e aceitar
    "100" aqui esconderia que a resposta veio fora do formato.
    """
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    numero = float(valor)
    if not math.isfinite(numero):
        return None
    return numero


def _inteiro(valor):
    """Quantidade so vale se for inteira e POSITIVA. 1.9 nao vira 1.

    Zero e negativo nao sao quantidade de venda. Aceitar zero faria a tarifa da
    linha virar 0,00 sem lacuna nenhuma; aceitar negativo reduziria o total.
    A finitude e conferida ANTES do int(), porque int(inf) e int(nan) levantam.
    """
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor if valor > 0 else None
    if isinstance(valor, float):
        if not math.isfinite(valor) or valor != int(valor) or valor <= 0:
            return None
        return int(valor)
    return None


def _produto(a, b):
    """a x b, ou None quando algum lado falta ou o resultado estoura."""
    if a is None or b is None:
        return None
    resultado = a * b
    if not math.isfinite(resultado):
        return None
    return round(resultado, 2)


def _linhas(pedido):
    saida = []
    for linha in (pedido.get("order_items") or []):
        anuncio = linha.get("item") or {}
        unidades = _inteiro(linha.get("quantity"))
        tarifa = _numero(linha.get("sale_fee"))
        saida.append({
            "mlb": anuncio.get("id") or linha.get("item_id"),
            "titulo": anuncio.get("title"),
            "unidades": unidades,
            "preco_unitario": _numero(linha.get("unit_price")),
            "tarifa_por_unidade": tarifa,
            "tarifa_da_linha": _produto(tarifa, unidades),
        })
    return saida


def moeda_segura_pre(moedas, sem_moeda):
    """Somar so vale com a janela inteira numa moeda conhecida."""
    return len(moedas) <= 1 and not sem_moeda


def _buscar(conta, de, ate, teto, sem_id):
    """Devolve (pedidos deduplicados, parcial, aviso). Erro na 1a pagina sobe."""
    vistos = {}
    for pagina in range(teto):
        try:
            corpo = meli.request("GET", "/orders/search", {
                "seller": conta["id"],
                "order.date_created.from": de,
                "order.date_created.to": ate,
                "sort": "date_desc",
                "limit": POR_PAGINA,
                "offset": pagina * POR_PAGINA,
            })
        except meli.ErroDaAPI:
            if pagina == 0:
                # Nada chegou. Deixar passar viraria "zero vendas" na tela, que e
                # a mentira mais cara que este leitor pode contar.
                raise
            return vistos, True, ("a coleta ficou parcial: a página %d não veio, "
                                  "e o que está abaixo é só o que chegou antes"
                                  % (pagina + 1))
        achados = corpo.get("results") if isinstance(corpo, dict) else None
        if not isinstance(achados, list):
            # Resposta fora do formato NAO e "nenhuma venda". Lista vazia de
            # verdade e; ausencia de lista e resposta que nao deu para ler.
            if pagina == 0:
                raise meli.ErroDaAPI(
                    502, "a resposta do Mercado Livre veio fora do formato esperado")
            return vistos, True, ("a coleta ficou parcial: a página %d veio fora do "
                                  "formato e foi descartada" % (pagina + 1))
        for pedido in achados:
            if not isinstance(pedido, dict):
                sem_id[0] += 1
                continue
            chave = pedido.get("id")
            if chave is None:
                sem_id[0] += 1
                continue
            vistos.setdefault(chave, pedido)
        if len(achados) < POR_PAGINA:
            return vistos, False, None
    return vistos, True, ("a coleta está incompleta: o teto de %d páginas foi atingido. "
                          "Quantos pedidos ficaram de fora não dá para afirmar"
                          % teto)


def coletar(janela=JANELA_PADRAO, hoje=None, teto=MAX_PAGINAS):
    """Monta o dado no formato do contrato. Nao grava — quem grava e o main."""
    conta = meli.conta_conectada()
    hoje = hoje or dt.datetime.now(FUSO).date()
    primeiro = hoje - dt.timedelta(days=janela - 1)

    # A janela e fixada ANTES da primeira chamada: pagina que anda com o relogio
    # devolve pedido repetido e pedido pulado.
    de = _iso(dt.datetime.combine(primeiro, dt.time.min, tzinfo=FUSO))
    ate = _iso(dt.datetime.combine(hoje, dt.time.max, tzinfo=FUSO))

    sem_id = [0]
    vistos, parcial, aviso_coleta = _buscar(conta, de, ate, teto, sem_id)

    avisos = []
    if aviso_coleta:
        avisos.append(aviso_coleta)

    itens = []
    moedas = set()
    faturamento = 0.0
    pago_total = 0.0
    unidades = 0
    pagos = 0
    nao_pagos = 0
    sem_valor = 0
    sem_pago = 0
    sem_itens = 0
    sem_moeda = 0
    unidade_desconhecida = False
    comissao = 0.0
    tarifa_desconhecida = False

    for pedido in vistos.values():
        situacao = (pedido.get("status") or "").lower()
        valor = _numero(pedido.get("total_amount"))
        if situacao != "paid":
            # Nao somamos o valor dos nao pagos: eles podem estar em outra moeda,
            # e um total que mistura moeda nao quer dizer nada.
            nao_pagos += 1
            continue

        pagos += 1
        moeda = pedido.get("currency_id")
        if isinstance(moeda, str) and moeda:
            moedas.add(moeda)
        else:
            moeda = None
            sem_moeda += 1
        if valor is None:
            sem_valor += 1
        else:
            faturamento += valor
        pago = _numero(pedido.get("paid_amount"))
        if pago is None:
            sem_pago += 1
        else:
            pago_total += pago

        linhas = _linhas(pedido)
        if not linhas:
            sem_itens += 1
        # Um pedido com quantidade faltando nao pode estragar a contagem do
        # pedido seguinte: o indicador e POR PEDIDO, e so depois sobe para o resumo.
        for linha in linhas:
            if linha["tarifa_da_linha"] is None:
                tarifa_desconhecida = True
            else:
                comissao += linha["tarifa_da_linha"]
        if not linhas:
            tarifa_desconhecida = True

        falta_aqui = (not linhas) or any(l["unidades"] is None for l in linhas)
        if falta_aqui:
            unidade_desconhecida = True
        else:
            unidades += sum(l["unidades"] for l in linhas)

        itens.append({
            "id": pedido.get("id"),
            "data": (pedido.get("date_created") or "")[:19] or None,
            "situacao": situacao,
            "valor": valor,
            "pago": pago,
            "moeda": moeda,
            "unidades": None if falta_aqui else sum(l["unidades"] for l in linhas),
            "linhas": linhas,
        })

    itens.sort(key=lambda i: i["data"] or "", reverse=True)

    faltando = []
    lacunas = {}
    completo = not parcial and not sem_valor and not sem_id[0]

    # Comissao so e total quando a coleta inteira veio. Pagina que falhou, teto
    # atingido ou registro descartado deixam linhas de fora, e um numero nessas
    # condicoes seria consumido como total da janela.
    if not completo:
        tarifa_desconhecida = True
    if not math.isfinite(comissao):
        tarifa_desconhecida = True

    if tarifa_desconhecida or not moeda_segura_pre(moedas, sem_moeda):
        comissao_total = None
        faltando.append("comissao_total")
        lacunas["comissao_total"] = (
            "a coleta não veio inteira ou algum item veio sem tarifa ou sem "
            "quantidade, então esta soma seria menor do que a comissão real"
            if tarifa_desconhecida else
            "a janela tem mais de uma moeda, e somar comissão de moedas diferentes "
            "daria um número que não existe"
        )
    else:
        comissao_total = round(comissao, 2)
        avisos.append(AVISO_TARIFA)

    # Somar so vale quando TODA a janela esta numa moeda conhecida. Moeda ausente
    # conta como desconhecida: somar com os reais daria um numero que nao existe.
    moeda_segura = moeda_segura_pre(moedas, sem_moeda)
    if not moeda_segura:
        faturamento = None
        pago_total = None
        faltando.append("faturamento")
        if sem_moeda:
            lacunas["faturamento"] = (
                "%d pedido(s) vieram sem dizer a moeda, e somar valor de moeda "
                "desconhecida com real daria um número que não existe" % sem_moeda
            )
        else:
            lacunas["faturamento"] = (
                "a janela tem mais de uma moeda (%s), e somar moedas diferentes daria "
                "um número que não existe" % ", ".join(sorted(moedas))
            )
    else:
        faturamento = round(faturamento, 2)
        pago_total = round(pago_total, 2)

    if pago_total is not None and sem_pago:
        # Faltou o desembolso de alguem: a soma viraria subtotal com cara de total.
        pago_total = None
        faltando.append("pago_pelo_comprador")
        lacunas["pago_pelo_comprador"] = (
            "%d pedido(s) pago(s) não trouxeram quanto o comprador desembolsou, "
            "então esta soma seria menor do que a realidade" % sem_pago
        )

    if unidade_desconhecida:
        faltando.append("unidades")
        lacunas["unidades"] = (
            "algum item veio sem quantidade, então o total de unidades ficaria menor "
            "do que foi vendido de verdade"
        )

    # Numero sem regra de contagem nao da para conferir com nada. O painel do
    # Mercado Livre conta de outro jeito, e sem dizer o criterio ninguem sabe se
    # a diferenca e erro ou recorte. Entao o recorte vai escrito, sempre.
    avisos.append(
        "contagem: pedidos com situação paga, pela data em que o pedido foi criado, "
        "entre %s e %s, contados um por pedido. O painel do Mercado Livre usa outro "
        "recorte e costuma dar um número diferente" % (primeiro.isoformat(), hoje.isoformat())
    )

    if sem_valor:
        avisos.append("%d pedido(s) pago(s) vieram sem valor e ficaram de fora da soma: "
                      "o faturamento abaixo é um subtotal" % sem_valor)
    if nao_pagos:
        avisos.append("%d pedido(s) não pagos (cancelado ou inválido) ficaram de fora "
                      "da soma" % nao_pagos)
    if sem_id[0]:
        avisos.append("%d registro(s) vieram sem identificação e foram descartados: "
                      "a contagem abaixo pode estar menor do que a real" % sem_id[0])
    if sem_itens:
        avisos.append("%d pedido(s) vieram sem item nenhum" % sem_itens)

    ticket = None
    if faturamento is not None and pagos and completo:
        ticket = round(faturamento / pagos, 2)

    resumo = {
        "pedidos_pagos": pagos,
        "unidades": None if unidade_desconhecida else unidades,
        "faturamento": faturamento,
        "pago_pelo_comprador": pago_total,
        "ticket_medio": ticket,
        "comissao_total": comissao_total,
        "completo": completo,
    }

    return {
        "conta": conta,
        "periodo": {"de": primeiro.isoformat(), "ate": hoje.isoformat()},
        "moeda": (sorted(moedas)[0] if len(moedas) == 1 else None),
        "resumo": resumo,
        "itens": itens,
        "faltando": faltando,
        "lacunas": lacunas,
        "avisos": avisos,
    }


def _main():
    args = sys.argv[1:]
    janela = JANELA_PADRAO
    if "--janela" in args:
        pos = args.index("--janela")
        if pos + 1 < len(args):
            try:
                janela = max(1, min(180, int(args[pos + 1])))
            except ValueError:
                print("--janela precisa de um numero de dias. Usando %d." % JANELA_PADRAO)

    d = coletar(janela=janela)
    contrato.gravar("prometheus-pedidos", conta=d["conta"], periodo=d["periodo"],
                    resumo=d["resumo"], itens=d["itens"], faltando=d["faltando"],
                    lacunas=d["lacunas"], avisos=d["avisos"], moeda=d["moeda"])

    r = d["resumo"]
    print("Loja: %s" % d["conta"].get("apelido"))
    print("Janela: %s a %s" % (d["periodo"]["de"], d["periodo"]["ate"]))
    print("")
    if not r["pedidos_pagos"]:
        print("Nenhum pedido pago na janela.")
        print("Gravado assim mesmo: janela vazia tambem e informacao.")
    else:
        simbolo = d["moeda"] or "?"
        rotulo = "Faturamento" if r["completo"] else "Faturamento (subtotal)"
        print("%-24s %s %s" % (rotulo, simbolo, "sem numero - veja a lacuna"
                               if r["faturamento"] is None
                               else "%.2f" % r["faturamento"]))
        print("%-24s %d" % ("Pedidos pagos", r["pedidos_pagos"]))
        if r["ticket_medio"] is not None:
            print("%-24s %s %.2f" % ("Ticket medio", simbolo, r["ticket_medio"]))
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
