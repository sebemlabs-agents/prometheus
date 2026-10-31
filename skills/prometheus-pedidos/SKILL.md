---
name: prometheus-pedidos
description: Lê os pedidos do Mercado Livre e mostra quanto a loja vendeu na janela, os últimos pedidos e a tarifa que veio em cada item. Somente leitura. Use quando o usuário perguntar sobre vendas, faturamento, quanto vendeu, últimos pedidos, ticket médio, "como foi o mês", "quanto eu faturei", ou pedir para atualizar o painel. Precisa da conta conectada pela skill prometheus-conectar-meli.
---

# Vendas e faturamento — pacote Prometheus

Responde o básico, e responde direito: **quanto entrou, em quantos pedidos, e o que cada
venda levou de tarifa.**

```
python3 pedidos.py
python3 pedidos.py --janela 90
```

Grava `prometheus-pedidos.json` na pasta e aparece como bloco no painel.

## O que esta skill NÃO faz

Ela não calcula margem, não diz se o faturamento está bom e não sugere nada. **Ela abre a
torneira; quem cruza é você, na conversa, com os arquivos na frente.** Para margem, peça o
cruzamento com o custo — que vem da Olist ou da planilha.

## Três coisas para dizer ao usuário antes que ele pergunte

### 1. Faturamento e "o que o comprador pagou" são números diferentes

O painel mostra os dois. O primeiro é a venda: preço × quantidade. O segundo é o desembolso
do comprador, que pode incluir frete e descontos. **Não afirme o que explica a diferença** —
só conferindo pedido a pedido dá para dizer se é frete, desconto ou devolução.

### 2. A tarifa aparece por item, e não é somada — de propósito

Cada item mostra a tarifa que veio no pedido. **O total não existe ainda**, e o painel diz
por quê: falta confirmar, contra pedido real, se o valor que a API manda é **por unidade ou
pela linha inteira**. Somar errado dá um número plausível e errado, que é o pior tipo.

Se o usuário perguntar o total de comissão, explique isso em uma frase e ofereça o cálculo
na conversa, deixando claro qual hipótese você usou.

### 3. É o estado de agora, não um histórico

Pedido pago hoje e cancelado amanhã sai da soma na próxima leitura. O arquivo é sobrescrito;
o pacote não guarda retrato anterior.

## Quando o resumo se declara incompleto

`completo: false` quer dizer que o número abaixo é **subtotal**, não total. Acontece quando
algum pedido pago veio sem valor, quando a coleta parou no meio, ou quando o teto de páginas
foi atingido. **Leia o aviso em voz alta para o usuário** em vez de apresentar o número como
se estivesse fechado.

Se a janela tiver mais de uma moeda, o faturamento vem vazio com a explicação: somar moedas
diferentes produz um número que não existe.

## Quando dá erro

Falha de rede e falha de autorização **nunca** viram "zero vendas" — o programa para e diz.
Se ele parar dizendo que não há autorização, a skill `prometheus-conectar-meli` resolve, e a
tabela de sintomas dela está em `references/problemas.md`.
