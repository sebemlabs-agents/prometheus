#!/usr/bin/env python3
"""As reclamacoes abertas da conta, por motivo e por etapa. SOMENTE LEITURA.

Responde a pergunta de quem abre o computador com medo: o que esta aberto
contra mim agora, por que, e o que ja escalou para a mediacao do Mercado Livre.

Uso:
    python3 devolucoes.py

Armadilhas desta superficie, todas medidas contra conta real em 02/11/2026:
  - o endereco EXIGE o filtro de situacao. Sem `status`, devolve 400.
  - a resposta vem em `data`, nao em `results`.
  - o filtro de data e IGNORADO EM SILENCIO: pedir com e sem ele devolve o
    mesmo total. Entao o recorte por data e feito aqui, sobre o que chegou.
  - o motivo vem como codigo (`PDD9939`). O texto em portugues esta noutro
    endereco, um por codigo.
  - E O MAIS CARO: nesse endereco, `detail` NAO e o motivo — e a resposta do
    comprador a uma pergunta anterior. Quatro motivos diferentes compartilham
    `detail: "Chegou bem"`: produto quebrado, produto que nao funciona, faltaram
    acessorios e faltou item. Usar `detail` junta tudo num balde que nao diz nada
    e apaga a causa raiz. O motivo de verdade esta em `name`.

Compatibilidade: Python 3.8+.
"""
import datetime as dt
import re
import sys

import contrato
import meli

POR_PAGINA = 50
MAX_PAGINAS = 10
# Teto de conversas lidas numa rodada: e uma chamada por reclamacao, e numa
# conta grande isso vira centenas. Acima disso o sinal vem com lacuna declarada.
MAX_CONVERSAS = 50
FUSO = dt.timezone(dt.timedelta(hours=-3))

# Etapas conhecidas, em ordem de gravidade. Etapa fora desta lista NAO e
# encaixada na mais branda por descarte: vira desconhecida e aparece como tal.
ETAPAS = {
    "claim": "reclamação aberta com você",
    "recontact": "esperando novo contato",
    "dispute": "em mediação do Mercado Livre",
}
PIOR = "dispute"

# O motivo de verdade vem em `name`, em ingles de maquina. Traduzido aqui porque
# e isso que o vendedor le — e porque agrupar por causa e o que permite consertar
# a causa. Codigo que nao estiver nesta tabela aparece cru e entra num aviso: e
# assim que a gente descobre motivo novo.
MOTIVOS = {
    "repentant_buyer": "arrependeu-se da compra",
    "broken_item": "produto chegou quebrado",
    "not_working_item": "produto não funciona",
    "missing_accessories": "faltaram acessórios",
    "missing_item": "faltou item do pedido",
    "damaged_package_broken_item": "embalagem danificada e produto quebrado",
    "different_than_published": "diferente do que o anúncio diz",
    "different_item_other": "recebeu outro produto",
    "estimated_delivery_out_of_time": "prazo de entrega estourou",
    "delivered_but_not_receive_package": "consta entregue, comprador diz que não recebeu",
    "undelivered_other": "não entregue, outro motivo",
}

# `flow` separa problema de PRODUTO de problema de ENTREGA. Sao consertos
# diferentes: um e fornecedor e embalagem, o outro e logistica.
FAMILIAS = {
    "post_purchase_delivered": "produto",
    "mediations_undelivered": "entrega",
}

# Quem e quem num desfecho: `complainant` e o comprador, `respondent` e o
# vendedor — ou seja, voce.
PAPEIS = {"complainant": "o comprador", "respondent": "você"}
FECHADO_POR = {"mediator": "mediador do Mercado Livre",
               "complainant": "o comprador", "respondent": "você"}
TIPOS = {"mediations": "mediação", "returns": "devolução"}

# Quem pode falar na conversa. O MEDIADOR e um terceiro papel, e numa conta com
# muita disputa ele fala bastante. Deixar ele de fora da lista fazia a conversa
# inteira virar indeterminada. Mediador falando por ultimo NAO vira "esperando
# voce": pode ser pedido de documento, pode ser decisao final, e afirmar seria
# chute.
FALANTES = {"complainant": "o comprador", "respondent": "você",
            "mediator": "o mediador do Mercado Livre"}

# O arquivo deste leitor vira painel PUBLICADO. Entao nada que veio do servidor
# entra nele sem passar por lista branca: valor desconhecido vira vazio e conta
# num aviso, nunca e interpolado. Um campo que deveria trazer um papel pode
# trazer um nome, e aí o nome seria publicado.
_CODIGO = re.compile(r"^[A-Z]{2,5}[0-9]{3,8}$")
DESFECHOS = {
    "item_returned": "produto devolvido",
    "refund": "dinheiro devolvido ao comprador",
    "partial_refund": "devolução parcial do dinheiro",
    "product_delivered": "produto entregue",
}


def _desfecho(bruto, desconhecidos):
    """Achata o desfecho em campos NOMEADOS, so com valores que a gente conhece.

    Valor fora da lista branca vira vazio e entra na contagem de desconhecidos.
    Interpolar o que veio do servidor publicaria o que estiver la — e o que
    deveria ser um papel pode ser um nome.
    """
    vazio = {"desfecho": None, "quem_ganhou": None, "fechada_por": None}
    if not isinstance(bruto, dict):
        return vazio
    ganhadores = bruto.get("benefited")
    quem = None
    if isinstance(ganhadores, list) and ganhadores:
        traduzidos = [PAPEIS.get(g) for g in ganhadores if isinstance(g, str)]
        if traduzidos and all(traduzidos):
            quem = " e ".join(traduzidos)
        else:
            desconhecidos.add("quem_ganhou")
    razao = bruto.get("reason")
    desfecho = DESFECHOS.get(razao) if isinstance(razao, str) else None
    if razao is not None and desfecho is None:
        desconhecidos.add("desfecho")
    fechada = FECHADO_POR.get(bruto.get("closed_by"))
    if bruto.get("closed_by") is not None and fechada is None:
        desconhecidos.add("fechada_por")
    return {"desfecho": desfecho, "quem_ganhou": quem, "fechada_por": fechada}


def _motivo(codigo, cache):
    """Codigo -> (motivo em portugues, familia, nome cru). Uma chamada por codigo.

    NUNCA usa `detail`: ele e a resposta do comprador a uma pergunta anterior, e
    quatro causas diferentes compartilham a mesma frase.
    """
    if codigo in cache:
        return cache[codigo]
    resultado = (None, None, None)
    try:
        d = meli.api("/post-purchase/v1/claims/reasons/%s" % codigo)
        if isinstance(d, dict):
            cru = d.get("name")
            resultado = (MOTIVOS.get(cru), FAMILIAS.get(d.get("flow")), cru)
    except meli.ErroDaAPI:
        pass
    cache[codigo] = resultado
    return resultado


def _conversa(cid):
    """Sinal da conversa, SEM NENHUM TEXTO.

    O texto da mensagem do comprador nao entra no arquivo de proposito: este
    arquivo alimenta o painel, e o painel vira link que a pessoa compartilha com
    a equipe. Dado pessoal de comprador em tela publicada e vazamento.

    O que fica e o que da para agir: quem falou por ultimo, ha quantos dias, e se
    veio anexo. Para ler o que o comprador escreveu, a skill busca na hora, na
    conversa, e nao grava.
    """
    try:
        d = meli.api("/post-purchase/v1/claims/%s/messages" % cid)
    except meli.ErroDaAPI:
        return None
    if not isinstance(d, list):
        return None
    msgs = [m for m in d if isinstance(m, dict)]
    if not msgs:
        return {"mensagens": 0, "esperando_voce": False, "ultima_fala": None,
                "ultima_do_comprador_ha_dias": None, "tem_anexo": False}
    datadas = [(m, _instante(m.get("date_created"))) for m in msgs]
    if any(quando is None for _, quando in datadas):
        # Sem saber a ordem, nao da para dizer quem falou por ultimo.
        return {"mensagens": len(msgs), "esperando_voce": None, "ultima_fala": None,
                "ultima_do_comprador_ha_dias": None,
                "tem_anexo": any(m.get("attachments") for m in msgs)}
    datadas.sort(key=lambda par: par[1])
    ultima, quando = datadas[-1]
    papel = ultima.get("sender_role")
    if papel not in FALANTES:
        return {"mensagens": len(msgs), "esperando_voce": None, "ultima_fala": None,
                "ultima_do_comprador_ha_dias": None,
                "tem_anexo": any(m.get("attachments") for m, _ in datadas)}
    do_comprador = papel == "complainant"
    return {
        "mensagens": len(datadas),
        "esperando_voce": do_comprador,
        "ultima_fala": FALANTES[papel],
        "ultima_do_comprador_ha_dias": None,
        "tem_anexo": any(m.get("attachments") for m, _ in datadas),
        "_ultima_data": ultima.get("date_created") if do_comprador else None,
    }


def _buscar_abertas():
    """Devolve (lista, truncado). Erro na 1a pagina sobe."""
    vistas = {}
    for pagina in range(MAX_PAGINAS):
        try:
            corpo = meli.request("GET", "/post-purchase/v1/claims/search", {
                # Sem `status` o endereco devolve 400. Nao e opcional.
                "status": "opened",
                "limit": POR_PAGINA,
                "offset": pagina * POR_PAGINA,
            })
        except meli.ErroDaAPI:
            if pagina == 0:
                raise
            return list(vistas.values()), True
        achados = corpo.get("data") if isinstance(corpo, dict) else None
        if not isinstance(achados, list):
            if pagina == 0:
                raise meli.ErroDaAPI(
                    502, "a resposta do Mercado Livre veio fora do formato esperado")
            return list(vistas.values()), True
        for item in achados:
            if isinstance(item, dict) and item.get("id") is not None:
                vistas.setdefault(item["id"], item)
        if len(achados) < POR_PAGINA:
            return list(vistas.values()), False
    return list(vistas.values()), True


def _instante(iso):
    """Texto ISO -> datetime com fuso, ou None. Comparar data como TEXTO inverte
    a ordem quando os fusos diferem: 12:00Z e depois de 10:00-03:00 no relogio,
    mas antes na string."""
    if not iso:
        return None
    try:
        quando = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if quando.tzinfo is None:
        return None
    return quando


def _idade(iso, hoje):
    quando = _instante(iso)
    if quando is None:
        return None
    return (hoje - quando.astimezone(FUSO).date()).days


def coletar(hoje=None):
    """Monta o dado no formato do contrato. Nao grava — quem grava e o main."""
    conta = meli.conta_conectada()
    hoje = hoje or dt.datetime.now(FUSO).date()

    abertas, truncado = _buscar_abertas()

    cache = {}
    itens = []
    desconhecidos = set()
    sem_motivo = 0
    codigos_novos = set()
    sem_idade = 0
    sem_familia = 0
    for c in abertas:
        codigo = c.get("reason_id")
        if not (isinstance(codigo, str) and _CODIGO.match(codigo)):
            codigo = None
        texto, familia, _ = _motivo(codigo, cache) if codigo else (None, None, None)
        if texto is None:
            sem_motivo += 1
            if codigo:
                codigos_novos.add(codigo)
        if familia is None:
            sem_familia += 1
        etapa = c.get("stage") if c.get("stage") in ETAPAS else None
        idade = _idade(c.get("date_created"), hoje)
        if idade is None:
            sem_idade += 1
        itens.append({
            "id": c.get("id"),
            "pedido": c.get("resource_id"),
            "tipo": TIPOS.get(c.get("type")),
            "etapa": etapa,
            "etapa_em_portugues": ETAPAS.get(etapa),
            "motivo_codigo": codigo,
            "motivo": texto,
            "motivo_traduzido": texto is not None,
            "familia": familia,
            "aberta_ha_dias": idade,
            **_desfecho(c.get("resolution"), desconhecidos),
        })

    # Ordenar ANTES de ler conversa: a lacuna promete "as mais antigas", entao
    # tem de ser as mais antigas mesmo. Sem idade vai para o fim.
    itens.sort(key=lambda i: (i["aberta_ha_dias"] is None, -(i["aberta_ha_dias"] or 0)))

    conversas_lidas = 0
    sem_conversa = 0
    indeterminadas = 0
    for item in itens:
        if conversas_lidas >= MAX_CONVERSAS:
            item.update({"mensagens": None, "esperando_sua_resposta": None,
                         "ultima_fala": None,
                         "comprador_esperando_ha_dias": None, "conversa_com_anexo": None})
            continue
        conversa = _conversa(item["id"])
        conversas_lidas += 1
        if conversa is None:
            sem_conversa += 1
            item.update({"mensagens": None, "esperando_sua_resposta": None,
                         "ultima_fala": None,
                         "comprador_esperando_ha_dias": None, "conversa_com_anexo": None})
            continue
        if conversa.get("_ultima_data"):
            conversa["ultima_do_comprador_ha_dias"] = _idade(
                conversa.pop("_ultima_data"), hoje)
        conversa.pop("_ultima_data", None)
        if conversa["esperando_voce"] is None:
            indeterminadas += 1
        item.update({
            "mensagens": conversa["mensagens"],
            "esperando_sua_resposta": conversa["esperando_voce"],
            "ultima_fala": conversa["ultima_fala"],
            "comprador_esperando_ha_dias": conversa["ultima_do_comprador_ha_dias"],
            "conversa_com_anexo": conversa["tem_anexo"],
        })

    faltando, lacunas, avisos = [], {}, []

    def falta(campo, porque):
        if campo not in faltando:
            faltando.append(campo)
        lacunas[campo] = porque

    # Truncado contamina TODO indicador que depende de ter visto a lista inteira,
    # nao so a contagem de abertas.
    if truncado:
        for campo in ("abertas", "em_mediacao", "motivos_distintos",
                      "problema_de_produto", "problema_de_entrega",
                      "mais_antiga_em_dias"):
            falta(campo, "não deu para ler a lista inteira de reclamações nesta "
                         "execução, então qualquer total aqui viria menor do que a "
                         "realidade")

    # Cobertura de conversa: um sinal lido pela metade apresentado como total faz
    # a pessoa achar que respondeu todo mundo.
    cobertura_cheia = (not sem_conversa and not indeterminadas
                       and conversas_lidas >= len(itens))
    if not cobertura_cheia:
        for campo in ("esperando_sua_resposta", "conversas_com_anexo"):
            falta(campo, "não deu para ler a conversa de todas as reclamações "
                         "(lemos as %d mais antigas, e algumas não puderam ser "
                         "lidas), então este número viria menor do que a realidade"
                         % MAX_CONVERSAS)

    if sem_motivo:
        codigos = ", ".join(sorted(codigos_novos)[:5]) or "sem código"
        avisos.append("%d reclamação(ões) têm um motivo que este pacote ainda não "
                      "traduz (%s); elas não são agrupadas com nenhum outro motivo"
                      % (sem_motivo, codigos))
    if desconhecidos:
        avisos.append("algum desfecho veio com valor que este pacote não conhece; "
                      "esses campos ficaram vazios em vez de publicar o que veio da "
                      "API")
    if sem_conversa:
        avisos.append("%d conversa(s) não deram para ler" % sem_conversa)
    if indeterminadas:
        avisos.append("%d conversa(s) não deixaram claro quem falou por último"
                      % indeterminadas)
    if sem_idade:
        avisos.append("%d reclamação(ões) vieram sem data de abertura" % sem_idade)

    falta("taxa_de_reclamacao",
          "a taxa precisa do histórico fechado, que nesta conta passa de sete mil "
          "registros — pesado demais para uma coleta ao vivo. O que está aqui é o "
          "que está aberto agora")
    falta("valor_e_repasse",
          "quanto cada reclamação custou e como ficou o repasse não vem neste "
          "endereço; é leitura do pedido, pedido a pedido")

    avisos.append(
        "o texto das mensagens NÃO é gravado: este arquivo vira painel, e painel "
        "se compartilha. Para ler o que o comprador escreveu, peça a conversa de "
        "uma reclamação específica")
    avisos.append(
        "isto é o que está ABERTO agora, não o que aconteceu num período: "
        "reclamação encerrada ontem não aparece aqui")

    def conta_se(condicao, campo):
        return None if campo in faltando else sum(1 for i in itens if condicao(i))

    idades = [i["aberta_ha_dias"] for i in itens]
    resumo = {
        "abertas": None if "abertas" in faltando else len(itens),
        "em_mediacao": conta_se(lambda i: i["etapa"] == PIOR, "em_mediacao"),
        "mais_antiga_em_dias": (None if ("mais_antiga_em_dias" in faltando
                                         or any(v is None for v in idades))
                                else max(idades, default=0)),
        "motivos_distintos": (None if "motivos_distintos" in faltando
                              else len({i["motivo_codigo"] for i in itens
                                        if i["motivo_codigo"]})),
        "problema_de_produto": (None if (sem_familia or "problema_de_produto" in faltando)
                                else sum(1 for i in itens if i["familia"] == "produto")),
        "problema_de_entrega": (None if (sem_familia or "problema_de_entrega" in faltando)
                                else sum(1 for i in itens if i["familia"] == "entrega")),
        "esperando_sua_resposta": conta_se(lambda i: i.get("esperando_sua_resposta"),
                                           "esperando_sua_resposta"),
        "conversas_com_anexo": conta_se(lambda i: i.get("conversa_com_anexo"),
                                        "conversas_com_anexo"),
        "mediador_falou_por_ultimo": conta_se(
            lambda i: i.get("ultima_fala") == FALANTES["mediator"],
            "esperando_sua_resposta"),
    }
    if sem_familia and not truncado:
        falta("problema_de_produto",
              "%d reclamação(ões) têm um motivo que o pacote ainda não sabe "
              "classificar entre produto e entrega" % sem_familia)
        falta("problema_de_entrega", lacunas["problema_de_produto"])

    return {
        "conta": conta,
        "periodo": {"de": None, "ate": hoje.isoformat()},
        "resumo": resumo,
        "itens": itens,
        "faltando": faltando,
        "lacunas": lacunas,
        "avisos": avisos,
    }


def _main():
    d = coletar()
    contrato.gravar("prometheus-devolucoes", conta=d["conta"], periodo=d["periodo"],
                    resumo=d["resumo"], itens=d["itens"], faltando=d["faltando"],
                    lacunas=d["lacunas"], avisos=d["avisos"])
    r = d["resumo"]
    print("Loja: %s" % d["conta"].get("apelido"))
    print("")
    if r["abertas"] == 0:
        print("Nenhuma reclamacao aberta agora.")
    else:
        print("%-26s %s" % ("Reclamacoes abertas", "?" if r["abertas"] is None else r["abertas"]))
        print("%-26s %s" % ("Em mediacao do Meli", "?" if r["em_mediacao"] is None else r["em_mediacao"]))
        if r["mais_antiga_em_dias"] is not None:
            print("%-26s %d dia(s)" % ("A mais antiga", r["mais_antiga_em_dias"]))
        print("")
        if r["problema_de_produto"] is not None:
            print("%-26s %d de produto · %d de entrega" % (
                "Onde esta o problema", r["problema_de_produto"], r["problema_de_entrega"]))
        print("%-26s %s" % ("Esperando sua resposta",
                            "?" if r["esperando_sua_resposta"] is None
                            else r["esperando_sua_resposta"]))
        print("%-26s %s" % ("Mediador falou por ultimo",
                            "?" if r["mediador_falou_por_ultimo"] is None
                            else r["mediador_falou_por_ultimo"]))
        print("%-26s %s" % ("Conversas com anexo",
                            "?" if r["conversas_com_anexo"] is None
                            else r["conversas_com_anexo"]))
        print("")
        por_motivo = {}
        for i in d["itens"]:
            chave = i["motivo"] or i["motivo_codigo"] or "sem motivo"
            por_motivo[chave] = por_motivo.get(chave, 0) + 1
        for motivo, n in sorted(por_motivo.items(), key=lambda x: -x[1])[:8]:
            print("  %2dx %s" % (n, motivo[:66]))
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
