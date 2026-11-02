---
name: prometheus-devolucoes
description: Mostra as reclamações e devoluções abertas do Mercado Livre — por causa, por etapa, e quais estão esperando a resposta do vendedor. Somente leitura. Use quando o usuário falar em reclamação, devolução, mediação, disputa, "o que está aberto contra mim", "o comprador abriu", "estou perdendo mediação", ou pedir para atualizar o painel. Precisa da conta conectada pela skill prometheus-conectar-meli.
---

# Reclamações abertas — pacote Prometheus

```
python3 devolucoes.py
```

Grava `prometheus-devolucoes.json` na pasta e aparece como bloco no painel.

## O que esta skill mostra, e por que nessa ordem

**Quantas estão abertas, quantas já estão em mediação do Mercado Livre, e quantas esperam a
sua resposta.** Essa última é a mais urgente: em mediação, silêncio do vendedor costuma
decidir a favor do comprador.

Depois, **a causa** — agrupada de um jeito que serve para consertar, não só para contar.

## A armadilha que o pacote resolve, e que você deve explicar

A API manda, junto do motivo, um campo que **parece** ser a descrição e não é: ele traz a
resposta do comprador a uma pergunta anterior. **Quatro causas completamente diferentes
compartilham a mesma frase "Chegou bem"**: produto quebrado, produto que não funciona,
faltaram acessórios e faltou item do pedido.

Quem agrupa por essa frase vê um balde enorme que não diz nada — e perde exatamente a
informação que permite agir. O pacote usa a causa real e traduz. **Se o usuário comparar com
o painel do Mercado Livre e estranhar, é isso.**

## Produto ou entrega

Cada reclamação é marcada como problema de **produto** ou de **entrega**. São consertos
diferentes: um é fornecedor, embalagem e descrição do anúncio; o outro é logística e prazo.
Quando a maioria cai de um lado só, isso é a conversa a ter — e é assim que se corta custo de
devolução, achando a causa em vez de tratar caso a caso.

## O texto das mensagens não é gravado — de propósito

O arquivo vira painel, e painel se compartilha com a equipe. Mensagem de comprador num link
compartilhado é vazamento de dado pessoal.

O que fica no arquivo é o sinal, sem texto: **quantas mensagens, quem falou por último, há
quantos dias o comprador espera, e se ele mandou foto.** Foto costuma ser prova anexada, e
pesa na mediação.

**Quando o usuário quiser ler o que o comprador escreveu**, busque a conversa **daquela
reclamação** na hora, mostre na tela e **não grave**:

```
python3 meli.py get /post-purchase/v1/claims/<id>/messages
```

## O que esta skill não sabe

- **A taxa de reclamação.** Ela exige o histórico fechado inteiro, que numa conta ativa passa
  de milhares de registros — pesado demais para uma coleta que a pessoa roda ao vivo. O que
  está aqui é **o que está aberto agora**, não o que aconteceu num período.
- **Quanto cada reclamação custou** e como ficou o repasse. Isso é leitura do pedido, pedido
  a pedido.

Diga isso quando ele perguntar "qual é a minha taxa?" — em vez de inventar um denominador.

## Quando dá erro

O endereço de reclamações **exige** o filtro de situação; o pacote sempre manda. Falha de
rede e de autorização param o programa em vez de virar "nenhuma reclamação" — zero aqui
significa zero de verdade.
