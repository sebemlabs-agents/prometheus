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


def _num(v, minimo=None, maximo=None):
    """Numero finito dentro do dominio esperado. Fora dele e DESCONHECIDO.

    Visita negativa existia na resposta de teste e gerava conversao de -10%.
    Numero fora do dominio nao e dado: e sinal de que a leitura nao vale.
    """
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    if f != f or f in (float("inf"), float("-inf")):
        return None
    if minimo is not None and f < minimo:
        return None
    if maximo is not None and f > maximo:
        return None
    return f


def _inteiro(v, minimo=None):
    if isinstance(v, bool) or not isinstance(v, int):
        return None
    if minimo is not None and v < minimo:
        return None
    return v


class ArquivoDePedidosNaoServe(Exception):
    """O arquivo existe mas nao da para confiar nele para esta conta/janela."""


def _conferir_pedidos(d, conta, hoje):
    """O arquivo e de ARQUIVO: pode ser velho, de outra conta, ou de demonstracao.

    Consumir sem conferir faz o resultado sair assinado com a conta conectada
    carregando numero que nao e dela. Entao: contrato conhecido, mesma conta,
    fonte real, e janela que termina hoje — porque as visitas so se pedem numa
    janela que termina agora.
    """
    if not isinstance(d, dict):
        raise ArquivoDePedidosNaoServe("o arquivo de pedidos não pôde ser lido")
    if str(d.get("contrato")) != str(contrato.CONTRATO):
        raise ArquivoDePedidosNaoServe(
            "o arquivo de pedidos é de uma versão de contrato que este leitor não "
            "conhece. Rode: python3 pedidos.py")
    if d.get("skill") != "prometheus-pedidos":
        raise ArquivoDePedidosNaoServe("o arquivo de pedidos não é do leitor de pedidos")
    if d.get("fonte") != "api":
        raise ArquivoDePedidosNaoServe(
            "o arquivo de pedidos não veio da API (é demonstração ou planilha), "
            "e misturar isso com visitas reais daria um número que não existe")
    dono = (d.get("conta") or {}).get("id")
    if dono != conta.get("id"):
        raise ArquivoDePedidosNaoServe(
            "o arquivo de pedidos é de outra conta. Rode: python3 pedidos.py")
    periodo = d.get("periodo") or {}
    try:
        de = dt.date.fromisoformat(periodo.get("de"))
        ate = dt.date.fromisoformat(periodo.get("ate"))
    except (TypeError, ValueError):
        raise ArquivoDePedidosNaoServe(
            "o arquivo de pedidos não diz o período que cobre. Rode: python3 pedidos.py")
    if ate != hoje:
        raise ArquivoDePedidosNaoServe(
            "o arquivo de pedidos é de %s e as visitas só podem ser pedidas numa "
            "janela que termina hoje — dividir venda de um período por visita de "
            "outro daria um número sem sentido. Rode: python3 pedidos.py" % ate)
    if de > ate:
        raise ArquivoDePedidosNaoServe("o período do arquivo de pedidos está invertido")
    return periodo, (ate - de).days + 1


def _vendas_da_janela(conta, hoje):
    """Le e CONFERE o arquivo do leitor de pedidos."""
    d = contrato.carregar("prometheus-pedidos")
    if not d:
        return None, None, None, None
    periodo, dias = _conferir_pedidos(d, conta, hoje)
    por_anuncio = {}
    linhas_incompletas = 0
    for pedido in (d.get("itens") or []):
        for linha in (pedido.get("linhas") or []):
            mlb = linha.get("mlb")
            unidades = _inteiro(linha.get("unidades"), minimo=1)
            preco = _num(linha.get("preco_unitario"), minimo=0)
            if not mlb:
                linhas_incompletas += 1
                continue
            atual = por_anuncio.setdefault(mlb, {"unidades": 0, "faturamento": 0.0,
                                                 "titulo": linha.get("titulo"),
                                                 "completo": True})
            if unidades is None or preco is None:
                # Linha incompleta NAO some: ela marca o anuncio como subtotal, se
                # nao o faturamento de uma linha passa a representar o do anuncio
                # inteiro — e isso tambem muda o ranking dos maiores.
                atual["completo"] = False
                linhas_incompletas += 1
                continue
            atual["unidades"] += unidades
            atual["faturamento"] = round(atual["faturamento"] + preco * unidades, 2)
    # Lacuna do produtor e lacuna aqui: faturamento parcial la nao vira total aqui.
    pedidos_completo = bool((d.get("resumo") or {}).get("completo", True))
    return por_anuncio, periodo, dias, {"linhas_incompletas": linhas_incompletas,
                                        "pedidos_completo": pedidos_completo}


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


def _visitas(mlb, dias, de):
    """Visitas na janela, ou None. None NAO e zero: zero significa ninguem olhou.

    Confere o periodo que a resposta diz ter coberto: pedir `last=N` devolve uma
    janela movel que termina HOJE, e se ela nao cobrir o inicio da janela de
    vendas, a divisao mistura periodos.
    """
    try:
        d = meli.api("/items/%s/visits/time_window" % mlb,
                     {"last": dias, "unit": "day"})
    except meli.ErroDaAPI:
        return None
    if not isinstance(d, dict):
        return None
    inicio = str(d.get("date_from") or "")[:10]
    if inicio and de and inicio > de:
        return None
    return _inteiro(d.get("total_visits"), minimo=0)


def coletar(quantos=QUANTOS_PADRAO, hoje=None):
    """Monta o dado no formato do contrato. Nao grava — quem grava e o main."""
    conta = meli.conta_conectada()
    hoje = hoje or dt.datetime.now(FUSO).date()

    vendas, periodo, dias, origem = _vendas_da_janela(conta, hoje)
    if vendas is None:
        raise ArquivoDePedidosNaoServe(
            "rode primeiro o leitor de pedidos: é dele que vem quem vendeu na "
            "janela. Comando: python3 pedidos.py")

    ordenados = sorted(vendas.items(), key=lambda par: -par[1]["faturamento"])
    escolhidos = ordenados[:quantos]
    deixados = len(ordenados) - len(escolhidos)

    dados, nao_lidos = _dados_dos_anuncios([mlb for mlb, _ in escolhidos])

    itens = []
    sem_visita = 0
    sem_dado = 0
    sem_estoque_conhecido = 0
    sem_situacao = 0
    sub_desconhecido = 0
    parciais = 0
    for mlb, venda in escolhidos:
        anuncio = dados.get(mlb) or {}
        if not anuncio:
            sem_dado += 1
        visitas = _visitas(mlb, dias, periodo.get("de"))
        if visitas is None:
            sem_visita += 1
        unidades = venda["unidades"]
        conversao = None
        if visitas:
            conversao = round(100.0 * unidades / visitas, 2)
        situacao = SITUACOES.get(anuncio.get("status"))
        if anuncio and situacao is None:
            sem_situacao += 1
        crus = anuncio.get("sub_status")
        sub = None
        if isinstance(crus, list):
            sub = [SUB_SITUACOES[s] for s in crus if s in SUB_SITUACOES]
            if len(sub) != len(crus):
                sub_desconhecido += 1
                sub = None
        estoque = _inteiro(anuncio.get("available_quantity"), minimo=0)
        if anuncio and estoque is None:
            sem_estoque_conhecido += 1
        if not venda["completo"]:
            parciais += 1
        itens.append({
            "mlb": mlb,
            "titulo": anuncio.get("title") or venda.get("titulo"),
            "faturamento": venda["faturamento"],
            "faturamento_parcial": not venda["completo"],
            "vendas": unidades,
            "visitas": visitas,
            "conversao_pct": conversao,
            "preco": _num(anuncio.get("price"), minimo=0),
            "estoque": estoque,
            "situacao": situacao,
            "alertas": sub,
            "saude": _num(anuncio.get("health"), minimo=0, maximo=1),
        })

    faltando, lacunas, avisos = [], {}, []

    def falta(campo, porque):
        if campo not in faltando:
            faltando.append(campo)
        lacunas[campo] = porque

    # A mediana so vale se TODO anuncio da lista tiver conversao. Deixar de fora
    # quem teve zero visita faria a mediana falar por quem nao foi medido.
    conversoes = [i["conversao_pct"] for i in itens]
    if itens and all(c is not None for c in conversoes):
        ordem = sorted(conversoes)
        meio = len(ordem) // 2
        mediana = (ordem[meio] if len(ordem) % 2
                   else round((ordem[meio - 1] + ordem[meio]) / 2.0, 2))
    else:
        mediana = None
        falta("conversao_mediana",
              "nem todos os anúncios desta lista têm conversão (faltou visita, "
              "ou ninguém visitou), então uma mediana aqui falaria por quem não "
              "foi medido")

    if parciais or not origem["pedidos_completo"]:
        falta("faturamento",
              "o arquivo de pedidos tem linhas incompletas ou a coleta dele não "
              "veio inteira, então o faturamento por anúncio é subtotal — e a "
              "ordem dos maiores também pode mudar quando o que falta chegar")

    if sem_estoque_conhecido or sem_dado or nao_lidos:
        falta("sem_estoque",
              "nem todo anúncio teve o estoque lido, então contar os zerados "
              "daria um número menor do que a realidade")
    if sem_situacao or sem_dado or nao_lidos:
        falta("pausados",
              "nem todo anúncio teve a situação lida ou reconhecida, então contar "
              "os pausados daria um número menor do que a realidade")
    if sub_desconhecido or sem_dado or nao_lidos:
        falta("com_alerta",
              "algum anúncio veio com um alerta que este pacote não conhece; "
              "contar só os conhecidos esconderia o resto")

    if deixados:
        avisos.append("esta leitura olhou os %d anúncios que mais faturaram na janela; "
                      "outros %d venderam e ficaram de fora" % (len(escolhidos), deixados))
    if sem_visita:
        avisos.append("%d anúncio(s) não tiveram as visitas lidas, ou as visitas não "
                      "cobriam a janela inteira; a conversão deles fica vazia, não "
                      "zerada" % sem_visita)
    if nao_lidos or sem_dado:
        avisos.append("%d anúncio(s) não tiveram os dados lidos; preço, estoque e "
                      "situação deles ficam vazios" % max(nao_lidos, sem_dado))
    if sub_desconhecido:
        avisos.append("%d anúncio(s) têm um alerta que este pacote ainda não conhece; "
                      "o campo fica vazio em vez de publicar o que veio da API"
                      % sub_desconhecido)

    falta("custo_e_margem",
          "a API não tem o seu custo por SKU, então conversão boa não quer dizer "
          "venda lucrativa; cruze com a planilha ou com a Olist")

    avisos.append("conversão aqui é venda dividida por visita no mesmo período do "
                  "arquivo de pedidos (%s a %s), contada por unidade vendida"
                  % (periodo.get("de"), periodo.get("ate")))

    itens.sort(key=lambda i: (i["conversao_pct"] is None, i["conversao_pct"] or 0))

    def conta_se(condicao, campo):
        return None if campo in faltando else sum(1 for i in itens if condicao(i))

    resumo = {
        "anuncios_olhados": len(itens),
        "conversao_mediana_pct": mediana,
        "sem_estoque": conta_se(lambda i: i["estoque"] == 0, "sem_estoque"),
        "pausados": conta_se(lambda i: i["situacao"] == "pausado", "pausados"),
        "com_alerta": conta_se(lambda i: bool(i["alertas"]), "com_alerta"),
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
    for rotulo, chave in (("Sem estoque", "sem_estoque"), ("Pausados", "pausados")):
        print("%-26s %s" % (rotulo, "?" if r[chave] is None else r[chave]))
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
    except ArquivoDePedidosNaoServe as e:
        sys.exit("PARADO: %s" % e)
    except meli.ErroDaAPI as e:
        sys.exit("PARADO: %s" % e)
