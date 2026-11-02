---
name: prometheus-anuncios
description: Mostra a conversão dos anúncios que vendem — de quem olhou, quantos compraram — mais estoque, situação e alertas do anúncio. Somente leitura. Use quando o usuário falar em conversão, visitas, "por que não vende", "tem visita e não converte", estoque, anúncio pausado, campeão parado, ou pedir para atualizar o painel. Precisa do leitor de pedidos ter rodado antes.
---

# Conversão por anúncio — pacote Prometheus

```
python3 pedidos.py     # precisa vir antes
python3 anuncios.py
python3 anuncios.py --quantos 60
```

## A pergunta que esta skill responde, e que o painel do Meli não responde por anúncio

**De quem olhou, quantos compraram.** O painel do Mercado Livre mostra a conversão da conta
inteira. Aqui ela é por anúncio — e é aí que aparece o anúncio que recebe muita visita e
vende pouco.

Quando a conversão de um campeão de faturamento está abaixo da mediana da própria loja,
**o problema não é tráfego**: é preço, foto, título, descrição, frete ou reputação. É a
conversa mais útil que esta skill abre.

## Por que ela olha só os que vendem

Uma conta ativa tem milhares de anúncios, e **as visitas custam uma chamada por anúncio**.
Varrer tudo não cabe numa coleta que a pessoa roda ao vivo.

Então a skill pega os que **mais faturaram na janela** — que são os que doem quando convertem
mal — e **diz quantos ficaram de fora**. Se o usuário quiser mais, `--quantos` aumenta.
Nunca diga que a lista é a loja inteira.

## Como a conversão é contada, e por que isso importa

Venda dividida por visita, **no mesmo período do arquivo de pedidos**, contada **por unidade
vendida**. A janela vem de lá, não é escolhida aqui — se as duas não batessem, o número não
significaria nada.

**Visita ausente não vira conversão zero.** Zero de conversão quer dizer que gente olhou e
ninguém comprou; ausência quer dizer que não deu para saber. São coisas diferentes e o painel
mostra diferente.

## O que esta skill não sabe

**Se a venda é lucrativa.** Conversão alta com margem negativa é pior que conversão baixa. A
API não tem o custo por SKU — cruze com a planilha ou com a Olist antes de recomendar baixar
preço.

## Situação e alertas

Anúncio pausado, sem estoque ou com alerta do Mercado Livre aparece marcado. **Situação que
este pacote não conhece fica vazia em vez de ser publicada crua** — o arquivo vira painel, e
painel se compartilha.
