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
LACUNA_TARIFA = (
    "ainda não dá para somar a tarifa: falta confirmar, num pedido de verdade, se o "
    "valor que a API manda é por unidade ou pela linha inteira. Cada item mostra o "
    "valor que veio, sem somar"
)


def _iso(momento):
    return momento.strftime("%Y-%m-%dT%H:%M:%S.000-03:00")


def _numero(valor):
    """Devolve float ou None. Texto e vazio viram None, nunca zero."""
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _linhas(pedido):
    saida = []
    for linha in (pedido.get("order_items") or []):
        anuncio = linha.get("item") or {}
        unidades = linha.get("quantity")
        saida.append({
            "mlb": anuncio.get("id") or linha.get("item_id"),
            "titulo": anuncio.get("title"),
            "unidades": int(unidades) if unidades is not None else None,
            "preco_unitario": _numero(linha.get("unit_price")),
            "tarifa": _numero(linha.get("sale_fee")),
        })
    return saida


def _buscar(conta, de, ate, teto):
    """Devolve (pedidos deduplicados, parcial, aviso). Erro na 1a pagina sobe."""
    vistos = {}
    aviso = None
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
        achados = corpo.get("results") or []
        for pedido in achados:
            chave = pedido.get("id")
            if chave is not None and chave not in vistos:
                vistos[chave] = pedido
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

    vistos, parcial, aviso_coleta = _buscar(conta, de, ate, teto)

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
    valor_nao_pago = 0.0
    sem_valor = 0
    sem_itens = 0
    unidade_desconhecida = False

    for pedido in vistos.values():
        situacao = (pedido.get("status") or "").lower()
        valor = _numero(pedido.get("total_amount"))
        if situacao != "paid":
            nao_pagos += 1
            valor_nao_pago += valor or 0.0
            continue

        pagos += 1
        moeda = pedido.get("currency_id")
        if moeda:
            moedas.add(moeda)
        if valor is None:
            sem_valor += 1
        else:
            faturamento += valor
        pago = _numero(pedido.get("paid_amount"))
        if pago is not None:
            pago_total += pago

        linhas = _linhas(pedido)
        if not linhas:
            sem_itens += 1
        for linha in linhas:
            if linha["unidades"] is None:
                unidade_desconhecida = True
            else:
                unidades += linha["unidades"]

        itens.append({
            "id": pedido.get("id"),
            "data": (pedido.get("date_created") or "")[:19] or None,
            "situacao": situacao,
            "valor": valor,
            "pago": pago,
            "moeda": moeda,
            "unidades": None if unidade_desconhecida else sum(
                l["unidades"] or 0 for l in linhas),
            "linhas": linhas,
        })

    itens.sort(key=lambda i: i["data"] or "", reverse=True)

    faltando = []
    lacunas = {}

    # A tarifa aparece item a item, mas nao e somada. Ver LACUNA_TARIFA.
    faltando.append("comissao_total")
    lacunas["comissao_total"] = LACUNA_TARIFA

    varias_moedas = len(moedas) > 1
    if varias_moedas:
        faturamento = None
        pago_total = None
        faltando.append("faturamento")
        lacunas["faturamento"] = (
            "a janela tem mais de uma moeda (%s), e somar moedas diferentes daria um "
            "número que não existe" % ", ".join(sorted(moedas))
        )
    else:
        faturamento = round(faturamento, 2)
        pago_total = round(pago_total, 2)

    if unidade_desconhecida:
        faltando.append("unidades")
        lacunas["unidades"] = (
            "algum item veio sem quantidade, então o total de unidades ficaria menor "
            "do que foi vendido de verdade"
        )

    if sem_valor:
        avisos.append("%d pedido(s) pago(s) vieram sem valor e ficaram de fora da soma: "
                      "o faturamento abaixo é um subtotal" % sem_valor)
    if nao_pagos:
        avisos.append("%d pedido(s) não pagos (cancelado ou inválido) ficaram de fora, "
                      "somando R$ %.2f" % (nao_pagos, valor_nao_pago))
    if sem_itens:
        avisos.append("%d pedido(s) vieram sem item nenhum" % sem_itens)

    completo = not parcial and not sem_valor

    ticket = None
    if faturamento is not None and pagos and completo:
        ticket = round(faturamento / pagos, 2)

    resumo = {
        "pedidos_pagos": pagos,
        "unidades": None if unidade_desconhecida else unidades,
        "faturamento": faturamento,
        "pago_pelo_comprador": pago_total,
        "ticket_medio": ticket,
        "comissao_total": None,
        "completo": completo,
    }

    return {
        "conta": conta,
        "periodo": {"de": primeiro.isoformat(), "ate": hoje.isoformat()},
        "moeda": (sorted(moedas)[0] if len(moedas) == 1 else "BRL"),
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
        rotulo = "Faturamento" if r["completo"] else "Faturamento (subtotal)"
        print("%-24s R$ %s" % (rotulo, "?" if r["faturamento"] is None
                               else "%.2f" % r["faturamento"]))
        print("%-24s %d" % ("Pedidos pagos", r["pedidos_pagos"]))
        if r["ticket_medio"] is not None:
            print("%-24s R$ %.2f" % ("Ticket medio", r["ticket_medio"]))
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
