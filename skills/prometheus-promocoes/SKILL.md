---
name: prometheus-promocoes
description: Monta a fila diária de decisão sobre promoções do Mercado Livre — o que termina nos próximos dias, quantos anúncios estão dentro, o desconto mínimo exigido e o que você já aderiu. Somente leitura. Use quando o usuário perguntar sobre promoções, campanhas, descontos, ofertas, "o que está acabando", "em que promoção eu entrei", "vale a pena aderir", ou quando pedir para atualizar o painel. Precisa da conta conectada pela skill prometheus-conectar-meli.
---

# Promoções terminando — pacote Elo

Entra a conta conectada, sai **a fila do que decidir hoje**: campanhas terminando, quantos
anúncios estão elegíveis, quantos já estão dentro, quanto do desconto o Mercado Livre banca,
e o desconto mínimo quando a campanha publica um.

Esta skill **não adere a promoção, não muda preço e não altera anúncio**. Ela mostra; quem
decide é o vendedor, no painel do Mercado Livre. Se ele pedir para aderir, explique isso e,
se ajudar, entregue a lista pronta para ele levar.

## Elegível e aderido não são a mesma coisa — e confundir é o erro caro

O Mercado Livre lista como **elegível** o anúncio que *pode* entrar na campanha, e como
**aderido** o que *já está dentro*. Somar os dois e dizer "38 anúncios na promoção" faz o
vendedor achar que aderiu quando não aderiu — e a campanha termina com ele de fora.

O painel mostra os dois separados, sempre. **Quando falar com o usuário, use as duas
palavras.** "Trinta e oito elegíveis, nenhum dentro, termina hoje" é uma frase que faz ele
agir; "38 anúncios" não é.

## Quanto do desconto o Mercado Livre banca

Cada campanha traz a mediana de **quanto o Meli subsidia** e **quanto sai do bolso do
vendedor**. É o que decide se vale aderir: campanha com rebate alto protege margem e ainda
dá exposição.

Mediana, não média, de propósito: um anúncio com desconto fora da curva não desloca o número.

**O que o pacote não sabe, e não vai fingir que sabe:** se o desconto cabe na margem dele. A
API não tem o custo por SKU. Se ele pedir essa conta, peça o custo — da Olist ou da planilha —
e faça o cruzamento na conversa, dizendo de onde veio cada número.

## Campanha grande demais vem vazia, não truncada

Quando uma campanha passa do teto de páginas, as contagens dela vêm **vazias com a
explicação**, nunca com um número parcial. Contagem pela metade apresentada como total é pior
que contagem nenhuma: quem lê "1000 anúncios" decide achando que sabe.

## Por que isto existe

Foi a dor mais pedida nas mentorias: sete mentorados diferentes, em seis meses. Um deles
perdeu **mais de metade das oportunidades** de promoção num único evento, com duas pessoas
cuidando disso à mão. Outro quer aderir com regra de margem em mais de mil anúncios.

O problema não é falta de informação — está tudo no painel do Mercado Livre. É que **ninguém
olha todo dia**, e campanha que termina não avisa.

## Antes de rodar — os scripts da pasta

O pacote cresce: skills novas trazem scripts novos, e **a pasta do usuário não se atualiza
sozinha**. Antes do primeiro comando desta skill, confira se o script existe na pasta dele.
Se não existir, copie de `${CLAUDE_PLUGIN_ROOT}/scripts/` para lá — todos os `.py`, de uma vez.

**Nunca sobrescreva `credenciais.txt`, `tokens.json` nem os arquivos da pasta dele.** Só os
scripts do pacote.

É um passo chato e invisível, e é exatamente por isso que ele some: sem os scripts novos, a
skill nova falha dizendo que o arquivo não existe, e parece que a atualização não funcionou.

## Rodar

```
python3 promocoes.py
```

Janela padrão de 7 dias. Para mudar: `--janela 14`. Para uma leitura rápida, sem varrer a
lista de anúncios de cada campanha: `--rapido` — e aí o número de anúncios vem vazio, dito
como lacuna em vez de inventado.

Depois: `python3 painel.py`, e **entregue o link no chat** para ele abrir com um clique.

## Como apresentar o resultado

**Ordem é por urgência, não por tamanho.** O que termina amanhã vem primeiro, mesmo que pegue
poucos anúncios. Prazo não se recupera; tamanho se compensa na próxima.

Para cada campanha, diga nesta ordem: **quanto tempo falta**, **quantos anúncios pega**,
**quanto exige de desconto**, e **se ele já está dentro**. Pare aí.

**O que você não deve fazer:** recomendar aderir. Você não tem o custo por SKU dele, então
não sabe se o desconto cabe na margem — e um desconto que não cabe é prejuízo com volume.
Diga o que é fato, aponte o que falta, e devolva a decisão.

Se ele perguntar "vale a pena?", a resposta honesta é: *"com o custo deste produto eu te digo;
sem ele, eu só sei o desconto exigido."* É o gancho natural para a planilha de custo.

## O que esta skill nunca vai saber

Diga isso quando for relevante, sem ser perguntado. É o que separa uma ferramenta de um
chute:

- **Se a campanha vai ser renovada ou estendida.** A API não informa. Só o gerente de conta.
- **A margem depois do desconto.** Depende do custo por SKU, que o Mercado Livre não tem.
- **O desconto exigido anúncio a anúncio** em campanhas sem percentual fixo. Aparece item a
  item no painel dele.

Campanha de **escopo amplo** tem um detalhe que confunde: a lista de anúncios dentro muda
sozinha, conforme o Mercado Livre reavalia a elegibilidade. O número de hoje não é promessa
para amanhã. A skill avisa quando é o caso.

## Janela vazia também é resposta

Quando nada termina na janela, grave assim mesmo e diga com todas as letras: **"nenhuma
promoção terminando nos próximos 7 dias"**. O painel mostra a janela vazia.

Isso é o oposto de silêncio: é a confirmação de que olhou. Uma rotina que só fala quando tem
problema é uma rotina em que se pode confiar — e é exatamente o que torna isto agendável.

## Virar rotina

Esta skill foi feita para rodar sozinha todo dia de manhã. Quando ele perguntar como, ou
quando a fila fizer sentido para ele, ofereça: agendar a execução diária e olhar o painel
antes de abrir o Mercado Livre.

É a passagem de "eu pergunto" para "chega pronto" — e é o degrau onde a maioria para de
esquecer de promoção.

## Se der erro

`references/problemas.md` da skill de conexão, que vale para todo o pacote. Os dois mais
comuns aqui: **403** por falta da permissão de promoções no DevCenter, e **conta não
conectada** — nesse caso, chame a `prometheus-conectar-meli` em vez de tentar contornar.
