#!/usr/bin/env python3
"""Aderir um anuncio a uma campanha do Mercado Livre, e sair dela.

    python3 promover.py aderir MLB123 P-MLB456          # confere. NAO envia.
    python3 promover.py aderir MLB123 P-MLB456 --fazer 7F3A
    python3 promover.py sair   MLB123 P-MLB456          # confere a saida
    python3 promover.py sair   MLB123 P-MLB456 --fazer 7F3A
    python3 promover.py reconciliar MLB123              # fecha acao sem resposta

Um anuncio por vez. Nao existe --todos, e receber uma lista e recusa: sessenta
pessoas com um comando de lote e um palco apressado e catalogo inteiro em
promocao por acidente.

Duas coisas que esta ferramenta nao faz, e nao e descuido:

- **nao calcula preco.** Manda o valor que a propria API propos para aquele
  candidato. `max_discounted_price` nao serve de trava: medido na casa, 7% foi
  aceito onde o "maximo" dizia 10%.
- **nao chama de desfazer o que nao desfaz.** Sair da campanha e compensacao:
  devolve o anuncio a candidato e o preco ao anterior, se nada mais mudou nesse
  meio-tempo.

Compatibilidade: Python 3.8+.
"""
import sys

import escrever
import meli

# So o caminho que ja roda em producao nesta casa. Tipo nao medido e recusado
# COM NOME, porque semelhanca de contrato nao e prova: o primitivo herdado
# manda SELLER_CAMPAIGN e nao manda identificador de oferta, e nada que a gente
# leu prova que os outros tipos aceitam o mesmo corpo.
TIPOS_SUPORTADOS = ("SELLER_CAMPAIGN",)

DENTRO = ("started", "active")
FORA = ("candidate", "pending")


class NaoDaParaFazer(RuntimeError):
    """Falta condicao para a acao. A mensagem diz qual."""


class LeituraFalhou(RuntimeError):
    """A resposta nao deu para ler. Nao e lista vazia: e ausencia de resposta."""


def _num(v):
    if isinstance(v, bool) or v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) != float("inf") else None


def preco_vivo(mlb):
    """O preco PRATICADO hoje. Vem do anuncio, nunca do candidato da promocao.

    Medido em 02/11/2026, mesmo anuncio: no candidato, `price` e o preco NA
    CAMPANHA (2640,00) e `original_price` e o praticado (3299,97). No anuncio,
    `price` e o praticado (3299,97) e `original_price` vem nulo. Mesmo nome,
    significados invertidos — e trocar um pelo outro poe o numero errado numa
    decisao de baixar preco."""
    corpo = meli.api("/items/" + mlb, {"attributes": "id,price,status,sub_status"})
    if not isinstance(corpo, dict):
        return None, None
    return _num(corpo.get("price")), (corpo.get("status") or None)


def candidatos(mlb):
    """As promocoes deste anuncio. Resposta ilegivel LEVANTA, nao devolve vazio.

    Devolver lista vazia aqui dizia "ele nao esta em campanha nenhuma" quando a
    verdade era "nao consegui ler" — e era com essa frase que a reconciliacao
    fechava uma pendencia sem saber nada."""
    corpo = meli.api("/seller-promotions/items/" + mlb, {"app_version": "v2"})
    achados = None
    if isinstance(corpo, list):
        achados = corpo
    elif isinstance(corpo, dict):
        if isinstance(corpo.get("results"), list):
            achados = corpo["results"]
        elif (corpo.get("paging") or {}).get("total") == 0:
            return []
    if achados is None:
        raise LeituraFalhou(
            "Nao consegui ler as promocoes do anuncio %s: a resposta nao veio "
            "no formato esperado." % mlb)
    # Lista nao basta: uma lista com registro sem `id` e sem `status` nao e
    # "nenhuma campanha", e nao conhecer o estado de um registro faz a
    # reconciliacao concluir "fora" sobre algo que ela nao leu.
    for c in achados:
        if not isinstance(c, dict) or not c.get("id") or not c.get("status"):
            raise LeituraFalhou(
                "A lista de promocoes do anuncio %s veio com registro sem "
                "identificador ou sem estado. Nao sei dizer em que campanha ele "
                "esta." % mlb)
    return achados


def achar(lista, campanha):
    for c in lista:
        if isinstance(c, dict) and str(c.get("id") or "") == campanha:
            return c
    return None


def _preco_proposto(cand):
    """O que a API propos para este candidato. Nada calculado aqui."""
    for chave in ("suggested_discounted_price", "price"):
        v = _num(cand.get(chave))
        if v is not None:
            return v, chave
    return None, None


def _retrato(mlb, campanha):
    """O estado vivo que decide a acao. Usado no conferir E no fazer."""
    praticado, situacao = preco_vivo(mlb)
    cand = achar(candidatos(mlb), campanha)
    return {"praticado": praticado, "situacao": situacao, "candidato": cand}


# ----------------------------------------------------------------- conferir

def conferir(acao, mlb, campanha):
    r = _retrato(mlb, campanha)
    cand = r["candidato"]
    if cand is None:
        raise NaoDaParaFazer(
            "O anuncio %s nao aparece na campanha %s. Confira os dois "
            "identificadores, ou veja a fila com: python3 promocoes.py"
            % (mlb, campanha))

    tipo = (cand.get("type") or "").upper()
    # A recusa por tipo nao medido vale para a ADESAO, que mexe no preco de
    # venda. SAIR e o caminho de volta: ele devolve preco em vez de baixar, e o
    # contrato do DELETE esta medido nos varios tipos (inclusive a excecao de
    # LIGHTNING e PRICE_DISCOUNT, abaixo). Fechar a saida junto com a entrada
    # deixaria gente presa numa campanha que este pacote nem aderiu.
    if acao == "aderir" and tipo not in TIPOS_SUPORTADOS:
        raise NaoDaParaFazer(
            "A campanha %s e do tipo %s, e esse tipo ainda NAO FOI MEDIDO por "
            "este pacote.\nO unico caminho de adesao provado aqui e %s. Mandar "
            "um corpo parecido para um tipo diferente e adivinhar com o preco "
            "de venda de alguem.\nPara este caso, use o painel do Mercado Livre."
            % (campanha, tipo or "desconhecido", ", ".join(TIPOS_SUPORTADOS)))

    estado = (cand.get("status") or "").lower()
    if acao == "aderir" and estado not in FORA:
        raise NaoDaParaFazer(
            "Este anuncio ja esta DENTRO da campanha (estado %r). Nao ha o que "
            "aderir." % (cand.get("status") or ""))
    if acao == "sair" and estado not in DENTRO:
        raise NaoDaParaFazer(
            "Este anuncio nao esta dentro da campanha (estado %r). Nao ha de "
            "onde sair." % (cand.get("status") or ""))

    proposto, de_onde = _preco_proposto(cand)
    if acao == "aderir" and proposto is None:
        raise NaoDaParaFazer(
            "A API nao devolveu preco proposto para este candidato, e este "
            "pacote nao inventa preco. Sem numero da fonte, nao envio.")

    valores = {
        "preco_hoje": r["praticado"],
        # Referencia da campanha: e o unico numero que diz a que preco o anuncio
        # deveria voltar quando ele sai. Sem isso, "saiu" nao da para conferir.
        "preco_de_referencia": _num(cand.get("original_price")),
        "preco_na_campanha": proposto if acao == "aderir" else None,
        "meli_banca_pct": _num(cand.get("meli_percentage")),
        "voce_banca_pct": _num(cand.get("seller_percentage")),
    }
    intencao = {
        "conta": escrever.conta_do_token(),
        "acao": acao,
        "anuncio": mlb,
        "campanha": campanha,
        "tipo": tipo,
        "oferta": cand.get("ref_id") or cand.get("offer_id"),
        "estado_lido": estado,
        "valores": valores,
        "preco_de_onde": de_onde,
    }
    codigo = escrever.guardar_intencao(intencao)
    _mostrar(acao, mlb, campanha, cand, valores, codigo)
    return codigo


def _dinheiro(v):
    if v is None:
        return "nao sei"
    return ("R$ %0.2f" % v).replace(".", ",")


def _mostrar(acao, mlb, campanha, cand, valores, codigo):
    print("Conta     %s" % escrever.conta_do_token())
    print("Anuncio   %s" % mlb)
    print("Campanha  %s (%s)" % (cand.get("name") or campanha, cand.get("type")))
    hoje, novo = valores["preco_hoje"], valores["preco_na_campanha"]
    if acao == "aderir":
        if hoje is None or novo is None:
            # Meia conta numa decisao de preco e pior que conta nenhuma.
            print("Preco     NAO vou comparar: falta o preco %s."
                  % ("praticado" if hoje is None else "proposto"))
        else:
            queda = (1 - novo / hoje) * 100 if hoje else None
            print("Preco     hoje %s   ->   na campanha %s%s" % (
                _dinheiro(hoje), _dinheiro(novo),
                ("   (-%0.1f%%)" % queda).replace(".", ",") if queda else ""))
    else:
        print("Preco     hoje %s (na campanha). Sair devolve ao anterior, se "
              "nada mais mudou." % _dinheiro(hoje))
    m, s = valores["meli_banca_pct"], valores["voce_banca_pct"]
    if m is not None or s is not None:
        print("Desconto  o Meli banca %s%% - voce banca %s%%" % (
            ("%0.1f" % m).replace(".", ",") if m is not None else "?",
            ("%0.1f" % s).replace(".", ",") if s is not None else "?"))
    if acao == "aderir":
        print("Compensar python3 promover.py sair %s %s" % (mlb, campanha))
    else:
        print("ATENCAO   sair e compensacao, nao desfazer: o preco volta ao "
              "anterior so se nada mais mudou nesse meio-tempo.")
    print("")
    print("Nada foi enviado. Para fazer de verdade, dentro de 10 minutos:")
    print("  python3 promover.py %s %s %s --fazer %s" % (acao, mlb, campanha, codigo))


# -------------------------------------------------------------------- fazer

def _conferir_de_novo(intencao):
    """O codigo prova que a pessoa leu AQUILO. Isto prova que AQUILO ainda vale.

    O Mercado Livre nao tem escrita condicional: entre esta releitura e o envio
    sobra uma janela de milissegundos que nao da para fechar. A spec diz isso em
    voz alta em vez de fingir que fechou."""
    r = _retrato(intencao["anuncio"], intencao["campanha"])
    cand = r["candidato"]
    if cand is None:
        raise NaoDaParaFazer(
            "O anuncio saiu da campanha entre a conferencia e agora. Confira de novo.")
    agora = {
        "praticado": r["praticado"],
        "estado": (cand.get("status") or "").lower(),
        "tipo": (cand.get("type") or "").upper(),
        "oferta": cand.get("ref_id") or cand.get("offer_id"),
    }
    proposto, _ = _preco_proposto(cand)
    mudou = []
    if agora["praticado"] != intencao["valores"]["preco_hoje"]:
        mudou.append("o preco praticado (era %s, agora %s)" % (
            _dinheiro(intencao["valores"]["preco_hoje"]), _dinheiro(agora["praticado"])))
    if intencao["acao"] == "aderir" and proposto != intencao["valores"]["preco_na_campanha"]:
        mudou.append("o preco da campanha (era %s, agora %s)" % (
            _dinheiro(intencao["valores"]["preco_na_campanha"]), _dinheiro(proposto)))
    if agora["estado"] != intencao["estado_lido"]:
        mudou.append("o estado do anuncio na campanha (era %s, agora %s)" % (
            intencao["estado_lido"], agora["estado"]))
    if agora["tipo"] != intencao["tipo"]:
        mudou.append("o tipo da campanha")
    if agora["oferta"] != intencao["oferta"]:
        mudou.append("a oferta")
    if mudou:
        raise NaoDaParaFazer(
            "Mudou %s entre a conferencia e agora. Nao envio o que voce nao "
            "leu: confira de novo." % "; ".join(mudou))
    return cand, r


def _confirmar(intencao, cand_antes):
    """Nenhum codigo HTTP conta como prova. Quem confirma e a releitura."""
    escrever.esperar(escrever.ESPERA_PROPAGACAO)
    r = _retrato(intencao["anuncio"], intencao["campanha"])
    cand = r["candidato"]
    estado = (cand.get("status") or "").lower() if cand else ""
    if intencao["acao"] == "aderir":
        esperado = intencao["valores"]["preco_na_campanha"]
        if estado in DENTRO and r["praticado"] == esperado:
            return True, "dentro da campanha, preco %s" % _dinheiro(r["praticado"])
        return False, ("estado %r, preco praticado %s (esperava dentro, a %s)"
                       % (estado, _dinheiro(r["praticado"]), _dinheiro(esperado)))
    if cand is None:
        # Medido: sair NAO remove da lista, o estado volta para `candidate`.
        # Candidato ausente num tipo que a gente nao mediu e ambiguo — e
        # ambiguo nao vira "deu certo".
        return False, ("o anuncio desapareceu da lista da campanha; nao sei "
                       "dizer se saiu. Preco praticado %s" % _dinheiro(r["praticado"]))
    oferta = cand.get("ref_id") or cand.get("offer_id")
    if estado != "candidate":
        # `pending` nao e saida: e o meio do caminho. Contar como saida diria
        # "pronto, voltou" para quem ainda esta vendendo com desconto.
        return False, "estado %r (esperava candidato de novo), preco %s" % (
            estado, _dinheiro(r["praticado"]))
    if intencao.get("oferta") and oferta != intencao["oferta"]:
        return False, ("ele esta candidato, mas numa oferta diferente da que eu "
                       "tirei (%s). Confira no painel." % oferta)
    referencia = intencao["valores"].get("preco_de_referencia")
    if referencia is not None and r["praticado"] == referencia:
        return True, "fora da campanha, preco de volta a %s" % _dinheiro(referencia)
    # Saiu da campanha mas o preco nao bateu com a referencia: o estado esta
    # certo e o dinheiro nao esta provado. Nao afirmar os dois.
    return False, ("saiu da campanha, mas o preco praticado e %s e eu esperava "
                   "%s. O estado voltou; o preco eu nao confirmo."
                   % (_dinheiro(r["praticado"]),
                      _dinheiro(referencia) if referencia is not None
                      else "o anterior, que a API nao me deu"))


def fazer(codigo, acao_pedida=None, mlb_pedido=None, campanha_pedida=None):
    """Executa a conferencia guardada — e so ela.

    O codigo e amarrado a um alvo. Se a linha de comando pedir outro, recusa: a
    frase que a pessoa aprovou na tela descrevia uma operacao, e seria essa que
    ela pensa estar autorizando."""
    alvo = mlb_pedido or codigo
    with escrever.trava(alvo):
        return _fazer(codigo, acao_pedida, mlb_pedido, campanha_pedida)


def _fazer(codigo, acao_pedida, mlb_pedido, campanha_pedida):
    intencao = escrever.consumir_intencao(codigo)
    acao, mlb = intencao["acao"], intencao["anuncio"]
    for nome, pedido, guardado in (("acao", acao_pedida, acao),
                                   ("anuncio", mlb_pedido, mlb),
                                   ("campanha", campanha_pedida, intencao["campanha"])):
        if pedido is not None and pedido != guardado:
            raise NaoDaParaFazer(
                "Este codigo foi conferido para %s %r, e o comando pediu %r. "
                "Nao executo uma operacao diferente da que apareceu na tela."
                % (nome, guardado, pedido))
    cand, _ = _conferir_de_novo(intencao)

    caminho = "/seller-promotions/items/" + mlb
    if acao == "aderir":
        corpo = {"promotion_id": intencao["campanha"],
                 "promotion_type": intencao["tipo"],
                 "deal_price": intencao["valores"]["preco_na_campanha"]}
        chamar = lambda: escrever.enviar("aderir", caminho, corpo=corpo, anuncio=mlb)
    else:
        # LIGHTNING e PRICE_DISCOUNT saem SO com promotion_type: PRICE_DISCOUNT
        # nao tem promotion_id no payload vivo, e mandar o parametro vazio fazia
        # a saida falhar antes de gerar recibo. Medido pelo Sentinela.
        params = {"promotion_type": intencao["tipo"], "app_version": "v2"}
        if intencao["tipo"] not in ("LIGHTNING", "PRICE_DISCOUNT"):
            params["promotion_id"] = intencao["campanha"]
            if intencao.get("oferta"):
                params["offer_id"] = intencao["oferta"]
        chamar = lambda: escrever.enviar("sair", caminho, params=params, anuncio=mlb)

    try:
        envio = chamar()
    except escrever.OfertaEmProcesso:
        # OfertaEmProcesso E uma ErroNaEscrita, entao esta clausula tem de vir
        # ANTES da de baixo — senao a mais geral engole a mais especifica e a
        # unica repeticao permitida nunca acontece.
        #
        # O proprio Meli disse que NAO aplicou. Aqui repetir e seguro — e
        # necessario: ~1 em 7. Mas releia antes, senao a segunda tentativa manda
        # um valor que pode nao valer mais.
        print("O Mercado Livre ainda processava a oferta anterior. Esperando "
              "20 segundos e tentando mais uma vez, uma so.")
        escrever.esperar(20)
        _conferir_de_novo(intencao)
        envio = chamar()
    except escrever.ErroNaEscrita as e:
        # 404 na saida nao e sucesso ("ja nao estava la") nem fracasso: e
        # resultado a reconciliar. Quem decide e a releitura, logo abaixo.
        if not (acao == "sair" and getattr(e, "status", None) == 404):
            raise
        print("O Mercado Livre respondeu 404 na saida. Isso costuma significar "
              "que ele ja nao estava na campanha — mas quem decide e a "
              "leitura, nao o codigo de resposta.")
        envio = None

    ok, detalhe = _confirmar(intencao, cand)
    if ok:
        # So agora a tentativa fecha. Enquanto nao fecha, o anuncio esta trancado.
        if envio:
            escrever.confirmado(envio["recibo"], detalhe)
        print("\nFeito e CONFERIDO: %s" % detalhe)
        if acao == "aderir":
            escrever.anotar("compensar: python3 promover.py sair %s %s"
                            % (mlb, intencao["campanha"]))
        return 0
    print("\nENVIADO, MAS NAO CONFIRMEI: %s" % detalhe)
    print("Isto nao e 'deu errado' — e 'nao sei'. O Mercado Livre as vezes "
          "responde sucesso e aplica outra coisa.")
    print("Confira o estado real:  python3 promover.py reconciliar %s" % mlb)
    return 1


# -------------------------------------------------------------- reconciliar

def reconciliar(mlb):
    """Fecha acao sem resposta conhecida, pelo estado vivo — nunca por palpite."""
    # A MESMA trava da execucao, nao uma propria: com travas diferentes, a
    # reconciliacao podia rodar no meio de um envio e fechar uma tentativa que
    # ainda estava propagando.
    with escrever.trava(mlb):
        return _reconciliar(mlb)


def _reconciliar(mlb):
    presas = escrever.pendencias(mlb)
    try:
        praticado, situacao = preco_vivo(mlb)
        promos = candidatos(mlb)
    except (LeituraFalhou, meli.ErroDaAPI) as e:
        print("Nao consegui ler o estado deste anuncio: %s" % e)
        print("\nA acao pendente continua ABERTA de proposito. Fechar sem ler "
              "seria trocar 'nao sei' por 'resolvido'. Tente de novo em instantes.")
        return 1
    print("Anuncio   %s (%s)" % (mlb, situacao or "situacao desconhecida"))
    print("Preco     praticado hoje: %s" % _dinheiro(praticado))
    dentro = [c for c in promos if (c.get("status") or "").lower() in DENTRO]
    if dentro:
        print("Campanhas em que ele esta DENTRO:")
        for c in dentro:
            print("  %s  %s" % (c.get("id"), c.get("name") or c.get("type")))
    else:
        print("Ele nao esta dentro de nenhuma campanha.")
    if not presas:
        print("\nNao havia acao pendente para este anuncio.")
        return 0
    if praticado is None and situacao is None:
        print("\nO anuncio nao devolveu preco nem situacao. A acao pendente "
              "continua aberta de proposito.")
        return 1
    for p in presas:
        escrever.fechar_tentativa(
            p["id"], "reconciliado", "a leitura encontrou: preco %s, %s" % (
                _dinheiro(praticado),
                "dentro de %d campanha(s)" % len(dentro) if dentro else "fora"))
    print("\n%d acao(oes) pendente(s) fechada(s) PELO QUE A LEITURA ENCONTROU "
          "(acima), nao por eu saber se a chamada aplicou. O anuncio "
          "destravou." % len(presas))
    return 0


# --------------------------------------------------------------------- CLI

def _main(argv=None):
    escrever.manutencao()
    a = list(argv if argv is not None else sys.argv[1:])
    if not a:
        print(__doc__.strip())
        return 0
    if a[0] == "reconciliar":
        if len(a) != 2:
            return _erro("reconciliar leva um anuncio so.")
        return reconciliar(a[1])
    if a[0] not in ("aderir", "sair"):
        return _erro("nao conheco %r. Use aderir, sair ou reconciliar." % a[0])

    acao = a[0]
    fazer_codigo = None
    if "--fazer" in a:
        i = a.index("--fazer")
        if i + 1 >= len(a):
            return _erro("--fazer precisa do codigo que a conferencia mostrou.")
        fazer_codigo = a[i + 1]
        del a[i:i + 2]
    if any(x.startswith("--") for x in a[1:]):
        return _erro("nao conheco essa opcao. Nao existe --todos neste pacote: "
                     "uma acao por anuncio, de proposito.")
    if len(a) != 3:
        return _erro("preciso de um anuncio e uma campanha, nessa ordem. "
                     "Lista nao serve: uma acao por anuncio, de proposito.")
    mlb, campanha = a[1], a[2]
    if "," in mlb or " " in mlb:
        return _erro("isso parece uma lista de anuncios. Uma acao por anuncio.")

    if fazer_codigo:
        return fazer(fazer_codigo, acao, mlb, campanha)
    conferir(acao, mlb, campanha)
    return 0


def _erro(msg):
    print("PARADO: " + msg)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(_main())
    except (NaoDaParaFazer, LeituraFalhou, escrever.SemPermissao,
            escrever.ConferenciaInvalida,
            escrever.ItemTrancado, escrever.ReciboImpossivel,
            escrever.ReciboIlegivel, escrever.ReciboNoTeto,
            escrever.RespostaIncerta, escrever.ErroNaEscrita,
            escrever.AcaoRecusada) as e:
        sys.exit("PARADO: %s" % e)
    except (meli.SemAutorizacao, meli.CredenciaisIncompletas, meli.ErroDaAPI) as e:
        sys.exit("PARADO: %s" % e)
