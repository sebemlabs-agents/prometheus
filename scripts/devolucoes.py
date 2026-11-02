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
DESFECHOS = {
    "item_returned": "produto devolvido",
    "refund": "dinheiro devolvido ao comprador",
    "partial_refund": "devolução parcial do dinheiro",
    "product_delivered": "produto entregue",
}


def _desfecho(bruto):
    """Achata o desfecho em campos nomeados, sem guardar a resposta crua.

    Guardar o objeto da API inteiro no arquivo carrega estrutura e termo que
    ninguem pediu — e o arquivo vira painel compartilhado.
    """
    if not isinstance(bruto, dict):
        return {"desfecho": None, "quem_ganhou": None, "fechada_por": None}
    ganhadores = bruto.get("benefited")
    quem = None
    if isinstance(ganhadores, list) and ganhadores:
        quem = " e ".join(PAPEIS.get(str(g), str(g)) for g in ganhadores)
    razao = bruto.get("reason")
    return {
        "desfecho": DESFECHOS.get(razao, razao),
        "quem_ganhou": quem,
        "fechada_por": "mediador do Mercado Livre"
                       if bruto.get("closed_by") == "mediator" else bruto.get("closed_by"),
    }


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
        return {"mensagens": 0, "esperando_voce": False,
                "ultima_do_comprador_ha_dias": None, "tem_anexo": False}
    ordenadas = sorted(msgs, key=lambda m: str(m.get("date_created") or ""))
    ultima = ordenadas[-1]
    do_comprador = (ultima.get("sender_role") or "").lower() == "complainant"
    return {
        "mensagens": len(ordenadas),
        "esperando_voce": do_comprador,
        "ultima_do_comprador_ha_dias": None,
        "tem_anexo": any(m.get("attachments") for m in ordenadas),
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


def _idade(iso, hoje):
    if not iso:
        return None
    try:
        quando = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (hoje - quando.astimezone(FUSO).date()).days


def coletar(hoje=None):
    """Monta o dado no formato do contrato. Nao grava — quem grava e o main."""
    conta = meli.conta_conectada()
    hoje = hoje or dt.datetime.now(FUSO).date()

    abertas, truncado = _buscar_abertas()

    cache = {}
    itens = []
    conversas_lidas = 0
    sem_conversa = 0
    sem_motivo = 0
    motivos_novos = set()
    etapa_desconhecida = 0
    for c in abertas:
        codigo = c.get("reason_id")
        texto, familia, cru = _motivo(codigo, cache) if codigo else (None, None, None)
        if texto is None:
            sem_motivo += 1
            if cru:
                motivos_novos.add(cru)
        etapa = (c.get("stage") or "").lower()
        if etapa not in ETAPAS:
            etapa_desconhecida += 1
        conversa = None
        if conversas_lidas < MAX_CONVERSAS:
            conversa = _conversa(c.get("id"))
            conversas_lidas += 1
            if conversa is None:
                sem_conversa += 1
            elif conversa.get("_ultima_data"):
                conversa["ultima_do_comprador_ha_dias"] = _idade(
                    conversa.pop("_ultima_data"), hoje)
            if conversa is not None:
                conversa.pop("_ultima_data", None)

        itens.append({
            "id": c.get("id"),
            "pedido": c.get("resource_id"),
            "tipo": c.get("type"),
            "etapa": etapa or None,
            "etapa_em_portugues": ETAPAS.get(etapa),
            "motivo_codigo": codigo,
            "motivo": texto or cru,
            "motivo_traduzido": texto is not None,
            "familia": familia,
            "aberta_ha_dias": _idade(c.get("date_created"), hoje),
            **_desfecho(c.get("resolution")),
            "mensagens": (conversa or {}).get("mensagens"),
            "esperando_sua_resposta": (conversa or {}).get("esperando_voce"),
            "comprador_esperando_ha_dias": (conversa or {}).get("ultima_do_comprador_ha_dias"),
            "tem_anexo": (conversa or {}).get("tem_anexo"),
        })

    itens.sort(key=lambda i: (-(i["aberta_ha_dias"] or 0),))

    faltando, lacunas, avisos = [], {}, []

    if truncado:
        faltando.extend(["abertas", "em_mediacao"])
        for campo in ("abertas", "em_mediacao"):
            lacunas[campo] = (
                "há mais reclamações abertas do que coube em %d páginas, então a "
                "contagem viria menor do que a realidade" % MAX_PAGINAS)
        abertas_n = None
        mediacao_n = None
    else:
        abertas_n = len(itens)
        mediacao_n = sum(1 for i in itens if i["etapa"] == PIOR)

    if sem_motivo:
        novos = ", ".join(sorted(motivos_novos)[:5]) or "sem nome"
        avisos.append("%d reclamação(ões) têm um motivo que este pacote ainda não traduz "
                      "(%s); elas aparecem com o nome cru, nunca agrupadas com outro "
                      "motivo" % (sem_motivo, novos))
    if etapa_desconhecida:
        avisos.append("%d reclamação(ões) estão numa etapa que este pacote ainda não "
                      "conhece; elas aparecem com o nome cru em vez de traduzido"
                      % etapa_desconhecida)

    # A taxa exige o historico fechado inteiro, e sao quase oito mil registros:
    # cento e sessenta paginas numa coleta que a pessoa roda ao vivo. Nao cabe, e
    # inventar um denominador seria pior que nao ter a taxa.
    faltando.append("taxa_de_reclamacao")
    lacunas["taxa_de_reclamacao"] = (
        "a taxa precisa do histórico fechado, que nesta conta passa de sete mil "
        "registros — pesado demais para uma coleta ao vivo. O que está aqui é o "
        "que está aberto agora"
    )
    faltando.append("valor_e_repasse")
    lacunas["valor_e_repasse"] = (
        "quanto cada reclamação custou e como ficou o repasse não vem neste "
        "endereço; é leitura do pedido, pedido a pedido"
    )

    if sem_conversa:
        avisos.append("%d conversa(s) não deram para ler; essas reclamações aparecem "
                      "sem o sinal de quem falou por último" % sem_conversa)
    if conversas_lidas >= MAX_CONVERSAS and len(itens) > MAX_CONVERSAS:
        faltando.append("esperando_sua_resposta")
        lacunas["esperando_sua_resposta"] = (
            "lemos a conversa das %d reclamações mais antigas; nas demais não dá "
            "para dizer quem falou por último sem uma chamada por reclamação"
            % MAX_CONVERSAS)

    avisos.append(
        "o texto das mensagens NÃO é gravado: este arquivo vira painel, e painel "
        "se compartilha. Para ler o que o comprador escreveu, peça a conversa de "
        "uma reclamação específica"
    )

    avisos.append(
        "isto é o que está ABERTO agora, não o que aconteceu num período: "
        "reclamação encerrada ontem não aparece aqui"
    )

    resumo = {
        "abertas": abertas_n,
        "em_mediacao": mediacao_n,
        "mais_antiga_em_dias": max((i["aberta_ha_dias"] or 0 for i in itens), default=0)
                               if itens else 0,
        "motivos_distintos": len({i["motivo_codigo"] for i in itens if i["motivo_codigo"]}),
        "problema_de_produto": sum(1 for i in itens if i["familia"] == "produto"),
        "problema_de_entrega": sum(1 for i in itens if i["familia"] == "entrega"),
        "esperando_sua_resposta": sum(1 for i in itens if i.get("esperando_sua_resposta")),
        "com_foto_do_comprador": sum(1 for i in itens if i.get("tem_anexo")),
    }

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
        print("%-26s %d dia(s)" % ("A mais antiga", r["mais_antiga_em_dias"]))
        print("")
        print("%-26s %d de produto · %d de entrega" % (
            "Onde esta o problema", r["problema_de_produto"], r["problema_de_entrega"]))
        print("%-26s %d" % ("Esperando sua resposta", r["esperando_sua_resposta"]))
        print("%-26s %d" % ("Com foto do comprador", r["com_foto_do_comprador"]))
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
