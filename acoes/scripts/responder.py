#!/usr/bin/env python3
"""Responder uma pergunta de pre-venda no Mercado Livre.

    python3 responder.py                               # lista as sem resposta
    python3 responder.py 13657433363 --texto "..."     # confere. NAO publica.
    python3 responder.py --fazer 7F3A                  # publica
    python3 responder.py reconciliar 13657433363       # fecha acao sem resposta

**Isto publica texto na pagina do anuncio, e nao existe apagar.** E a unica
acao deste pacote sem caminho de volta — nem compensacao. Por isso:

- quem escreve o texto e a pessoa. Se a conversa sugerir uma resposta, a
  sugestao vai para a tela e ela edita antes de qualquer envio;
- o codigo de confirmacao e derivado do TEXTO EXATO: editar depois de conferir
  invalida o codigo;
- o recibo guarda o numero da pergunta e o tamanho da resposta. **Nunca o
  texto do cliente nem o seu.**

Compatibilidade: Python 3.8+.
"""
import sys

import escrever
import meli

LIMITE = 2000      # teto deste pacote, para o erro aparecer aqui e nao la


class NaoDaParaResponder(RuntimeError):
    """Falta condicao. A mensagem diz qual."""


def pendentes(limite=20):
    corpo = meli.api("/my/received_questions/search",
                     {"status": "UNANSWERED", "api_version": "4",
                      "limit": limite})
    perguntas = corpo.get("questions") if isinstance(corpo, dict) else None
    return perguntas if isinstance(perguntas, list) else []


def uma(ident):
    return meli.api("/questions/%s" % ident, {"api_version": "4"})


def por_que_nao(p, conta):
    """O motivo de NAO poder responder, ou None quando pode.

    Os estados sao os mesmos que o Echo usa em producao: ter resposta, sair de
    UNANSWERED, estar em espera, ter sido apagada do anuncio ou marcada como
    suspeita tiram a pergunta da fila. E `seller_id` precisa ser a conta
    conectada — pergunta de outra conta nao se responde daqui."""
    if not isinstance(p, dict):
        return "nao consegui ler a pergunta"
    if p.get("answer"):
        return "esta pergunta ja foi respondida"
    if (p.get("status") or "").upper() != "UNANSWERED":
        return "o estado dela e %r, e so UNANSWERED aceita resposta" % p.get("status")
    if p.get("hold"):
        return "ela esta em espera (hold) no Mercado Livre"
    if p.get("deleted_from_listing"):
        return "ela foi apagada do anuncio"
    if p.get("suspected_spam"):
        return "o Mercado Livre marcou como suspeita de spam"
    if conta is not None and p.get("seller_id") not in (None, conta):
        return ("ela e da conta %s, e a conectada aqui e %s"
                % (p.get("seller_id"), conta))
    return None


def conferir(ident, texto):
    conta = escrever.conta_do_token()
    p = uma(ident)
    motivo = por_que_nao(p, conta)
    if motivo:
        raise NaoDaParaResponder("Nao da para responder: %s." % motivo)

    texto = (texto or "").strip()
    if not texto:
        raise NaoDaParaResponder(
            "Falta o texto da resposta. Quem escreve e voce: use --texto \"...\"")
    if len(texto) > LIMITE:
        raise NaoDaParaResponder(
            "O texto tem %d caracteres, e este pacote para em %d. Encurte."
            % (len(texto), LIMITE))

    intencao = {
        "conta": conta,
        "acao": "responder",
        "pergunta": int(p.get("id")),
        "anuncio": p.get("item_id"),
        # o texto entra na intencao porque o codigo e derivado DELE: editar
        # depois de conferir tem de invalidar o codigo.
        "texto": texto,
    }
    codigo = escrever.guardar_intencao(intencao)
    print("Conta     %s" % conta)
    print("Anuncio   %s" % p.get("item_id"))
    print("Pergunta  %s" % (p.get("text") or "").strip())
    print("")
    print("Sua resposta, exatamente como vai aparecer:")
    print("")
    for linha in texto.splitlines() or [""]:
        print("    " + linha)
    print("")
    print("ATENCAO   publicar NAO se desfaz. Nao existe apagar resposta.")
    print("")
    print("Nada foi publicado. Para publicar, dentro de 10 minutos:")
    print("  python3 responder.py %s --fazer %s" % (p.get("id"), codigo))
    return codigo


def _igual(a, b):
    """Mesmo texto, desconsiderando espaco. Normalizacao demonstrada e so essa."""
    return " ".join((a or "").split()) == " ".join((b or "").split())


def _confirmar(intencao):
    """Quem confirma e a releitura, nunca o codigo de resposta.

    E confirma o TEXTO: achar "alguma resposta publicada" nao prova que foi a
    sua. Outra integracao pode ter respondido na mesma janela, e dizer "feito"
    ali seria assinar o texto de outro."""
    escrever.esperar(escrever.ESPERA_PROPAGACAO)
    p = uma(intencao["pergunta"])
    resposta = (p or {}).get("answer") if isinstance(p, dict) else None
    publicado = (resposta or {}).get("text") if isinstance(resposta, dict) else None
    if not publicado:
        return False, None, "ainda aparece sem resposta"
    if _igual(publicado, intencao["texto"]):
        return True, publicado, ""
    return False, publicado, ("ha uma resposta publicada que NAO e a sua "
                              "(%d caracteres, a sua tinha %d). Pode ter sido "
                              "outra integracao, ou outra pessoa"
                              % (len(publicado), len(intencao["texto"])))


def fazer(codigo, pergunta_pedida=None):
    alvo = "pergunta-%s" % (pergunta_pedida or codigo)
    with escrever.trava(alvo):
        return _fazer(codigo, pergunta_pedida)


def _fazer(codigo, pergunta_pedida):
    intencao = escrever.consumir_intencao(codigo)
    if intencao.get("acao") != "responder":
        raise escrever.ConferenciaInvalida(
            "Este codigo e de outra acao. Confira de novo.")
    ident = intencao["pergunta"]
    if pergunta_pedida is not None and str(pergunta_pedida) != str(ident):
        raise NaoDaParaResponder(
            "Este codigo foi conferido para a pergunta %s, e o comando pediu "
            "%s. Nao publico numa pergunta diferente da que apareceu na tela."
            % (ident, pergunta_pedida))

    # Reler antes de publicar: pode ter sido respondida, posta em espera ou
    # apagada entre a conferencia e agora.
    motivo = por_que_nao(uma(ident), intencao["conta"])
    if motivo:
        raise NaoDaParaResponder(
            "Entre a conferencia e agora, %s. Nao publiquei nada." % motivo)

    envio = escrever.enviar(
        "responder", "/answers",
        corpo={"question_id": ident, "text": intencao["texto"]},
        anuncio="pergunta-%s" % ident)

    ok, publicado, porque = _confirmar(intencao)
    if ok:
        escrever.confirmado(envio["recibo"], "resposta publicada e conferida")
        print("\nPublicado e CONFERIDO.")
        return 0
    print("\nENVIADO, MAS NAO CONFIRMEI: %s." % porque)
    print("NAO reenvie: reenviar as cegas publica duas respostas na mesma "
          "pagina. Confira o estado real:")
    print("  python3 responder.py reconciliar %s" % ident)
    return 1


def reconciliar(ident):
    # A MESMA trava da execucao: travas diferentes deixavam a reconciliacao
    # fechar uma tentativa ainda em propagacao.
    with escrever.trava("pergunta-%s" % ident):
        return _reconciliar(ident)


def _reconciliar(ident):
    presas = escrever.pendencias("pergunta-%s" % ident)
    p = uma(ident)
    resposta = (p or {}).get("answer") if isinstance(p, dict) else None
    tem = bool((resposta or {}).get("text") if isinstance(resposta, dict) else None)
    print("Pergunta  %s" % ident)
    print("Estado    %s" % ((p or {}).get("status") or "nao sei"))
    print("Resposta  %s" % ("JA publicada" if tem else "ainda nao publicada"))
    if tem:
        print("Texto     %s" % " ".join(
            ((resposta or {}).get("text") or "").split())[:200])
    if not presas:
        print("\nNao havia acao pendente para esta pergunta.")
        return 0
    if not isinstance(p, dict) or not p:
        print("\nNao consegui ler a pergunta. A acao pendente continua aberta "
              "de proposito. Tente de novo em instantes.")
        return 1
    for x in presas:
        escrever.fechar_tentativa(
            x["id"], "reconciliado",
            "a leitura encontrou: resposta %s" % ("publicada" if tem else "nao publicada"))
    if tem:
        # Nao da para afirmar que a resposta publicada e a sua: a intencao, que
        # guardava o texto, foi consumida no envio. Dizer "feito" aqui seria
        # assinar um texto que pode ser de outra integracao.
        print("\nHa uma resposta publicada nesta pergunta. NAO consigo afirmar "
              "que e a sua — leia acima e confira na pagina do anuncio.")
    else:
        print("\nNao ha resposta publicada: a sua nao saiu.")
    print("%d acao(oes) pendente(s) fechada(s) pelo que a leitura encontrou."
          % len(presas))
    return 0


def listar():
    perguntas = pendentes()
    conta = escrever.conta_do_token()
    if not perguntas:
        print("Nenhuma pergunta sem resposta.")
        return 0
    print("%d pergunta(s) sem resposta:\n" % len(perguntas))
    for p in perguntas:
        motivo = por_que_nao(p, conta)
        marca = "  " if motivo is None else "! "
        print("%s%-14s %-14s %s" % (marca, p.get("id"), p.get("item_id"),
                                    (p.get("text") or "").strip()[:60]))
        if motivo:
            print("                 (nao da para responder: %s)" % motivo)
    print("\nPara responder uma:  python3 responder.py <numero> --texto \"...\"")
    return 0


def _main(argv=None):
    a = list(argv if argv is not None else sys.argv[1:])
    if not a:
        return listar()
    if a[0] == "reconciliar":
        if len(a) != 2:
            return _erro("reconciliar leva um numero de pergunta so.")
        return reconciliar(a[1])
    codigo = None
    if "--fazer" in a:
        i = a.index("--fazer")
        if i + 1 >= len(a):
            return _erro("--fazer precisa do codigo que a conferencia mostrou.")
        codigo = a[i + 1]
        del a[i:i + 2]
    if codigo and len(a) == 1:
        # O numero da pergunta vem junto de proposito: o codigo sozinho nao
        # deixa voce ver, na propria linha, em qual pergunta vai publicar.
        return fazer(codigo, a[0])
    if codigo:
        return _erro("para publicar: python3 responder.py <numero> --fazer <codigo>")

    texto = None
    if "--texto" in a:
        i = a.index("--texto")
        if i + 1 >= len(a):
            return _erro("--texto precisa do texto da resposta.")
        texto = a[i + 1]
        del a[i:i + 2]
    if len(a) != 1:
        return _erro("preciso de um numero de pergunta so. Uma resposta por vez.")
    conferir(a[0], texto)
    return 0


def _erro(msg):
    print("PARADO: " + msg)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(_main())
    except (NaoDaParaResponder, escrever.SemPermissao,
            escrever.ConferenciaInvalida, escrever.ItemTrancado,
            escrever.ReciboImpossivel, escrever.ReciboIlegivel,
            escrever.ReciboNoTeto, escrever.RespostaIncerta,
            escrever.ErroNaEscrita, escrever.AcaoRecusada) as e:
        sys.exit("PARADO: %s" % e)
    except (meli.SemAutorizacao, meli.CredenciaisIncompletas, meli.ErroDaAPI) as e:
        sys.exit("PARADO: %s" % e)
