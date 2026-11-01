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

### 2. A comissão é por unidade, e não é a conta final

Cada item traz a tarifa **de uma unidade**; o total da linha é ela vezes a quantidade. Isso
foi **medido** contra conta real, não suposto: o mesmo anúncio vendido em quantidade 1, 2, 6,
10 e 15 manteve a tarifa quase igual. Na janela inteira a comissão deu **12,4% do
faturamento**, que é a faixa do Mercado Livre.

**O que ela não cobre, e precisa ser dito:** ajuste, estorno e taxa cobrada fora do pedido.
É a comissão informada no pedido no momento da coleta — não a fatura.

### 3. O número diz como foi contado

Junto dos valores vai a regra: situação contada, qual data foi usada, o intervalo e a unidade
(um por pedido). **O painel do Mercado Livre conta de outro jeito e costuma dar um número
maior** — numa conta real deu 814 vendas contra 720 pedidos pagos aqui, com preço médio por
venda praticamente igual.

Quando o usuário estranhar a diferença, **não diga que um dos dois está errado.** Mostre a
regra de contagem que está no arquivo e explique que são recortes diferentes. Se ele quiser
chegar ao fundo, a conferência é pedido a pedido, nunca pelo total.

### 4. É o estado de agora, não um histórico

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

Se o Mercado Livre reclamar de excesso de chamadas, o programa **espera e tenta de novo
sozinho**, até três vezes, respeitando o tempo que o servidor pedir. O limite é da conta, não
do aplicativo: quem tem outra integração rodando pode esbarrar nele sem ter feito nada. Se
ainda assim parar, espere um minuto e rode de novo.
Se ele parar dizendo que não há autorização, a skill `prometheus-conectar-meli` resolve, e a
tabela de sintomas dela está em `references/problemas.md`.
