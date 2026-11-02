---
name: prometheus-responder-pergunta
description: PUBLICA UM TEXTO PÚBLICO na página de um anúncio do Mercado Livre, respondendo a pergunta de pré-venda. Não existe apagar. Use quando o usuário pedir para responder pergunta, responder cliente, ver perguntas sem resposta, ou disser "responde essa" depois de ver a lista. Exige permissão de escrita no aplicativo dele e a conta conectada pela skill prometheus-conectar-meli.
---

# Responder uma pergunta

Esta skill **publica texto na página do anúncio, para qualquer pessoa ler**, e **não existe
apagar resposta**. É a única ação deste pacote sem caminho de volta — nem compensação. Trate
com o cuidado de quem está falando em nome da loja de outra pessoa.

## O fluxo

Ver o que está esperando:

```bash
python3 responder.py
```

Conferir uma resposta — **não publica**:

```bash
python3 responder.py 13657433363 --texto "Cabe sim: 60 cm de largura."
```

Isso imprime a pergunta, a resposta **exatamente como vai aparecer**, o aviso de que publicar
não se desfaz, e um código que vale 10 minutos, uma vez. Publicar:

```bash
python3 responder.py --fazer 7F3A
```

## Quem escreve o texto é ele. Sempre

Você pode **sugerir** uma resposta — e deve, quando ajuda. Mas:

- mostre a sugestão na conversa e **espere ele aprovar ou editar**;
- o código de confirmação é derivado do **texto exato**. Mudou uma palavra depois de conferir,
  o código não serve mais: confira de novo. Isso é de propósito;
- **nunca publique texto que ele não leu**, nem "melhore" o texto dele entre a conferência e o
  envio;
- não prometa prazo, frete, desconto ou característica que você não leu no anúncio. Resposta
  pública que promete o que a loja não cumpre é problema do vendedor, não seu.

## O que ela recusa, e por quê

Só é respondível a pergunta em que **tudo** vale: sem resposta, no estado `UNANSWERED`, não em
espera, não apagada do anúncio, não marcada como suspeita, e **da conta conectada aqui**.
Qualquer um desses falhando, ela recusa dizendo qual. Não tente outro caminho: o estado é do
Mercado Livre, e ele tem razões que a gente não vê.

Sem a permissão de escrita de comunicação (`urn:ml:mktp:comunication:/read-write`), recusa
antes de qualquer coisa sair da máquina. Mudar a permissão no DevCenter **não vale** para a
conexão que já existe: ele precisa rodar `python3 autorizar.py` de novo. Para ver o que a
autorização concedeu: `python3 escrever.py permissao`.

## Depois de enviar

A ferramenta espera a propagação e **relê a pergunta**. Só diz `Publicado e CONFERIDO` quando a
resposta aparece lá.

Se vier `ENVIADO, MAS NAO CONFIRMEI`: **não reenvie**. Reenviar às cegas publica duas respostas
na mesma página, e aí são duas que não se apagam. Rode:

```bash
python3 responder.py reconciliar 13657433363
```

## O que não vai para o disco

O recibo guarda o número da pergunta e o tamanho da resposta — **nunca o texto do cliente nem o
dele**. Mesma regra dos leitores: texto de conversa se lê na conversa, não em arquivo nosso.

## O que esta skill não faz

**Não apaga pergunta.** Apagar seria a falsa volta — e a resposta publicada continuaria
existindo do mesmo jeito. Se ele pedir, explique isso e mande para o painel do Mercado Livre.

Também não escreve em reclamação nem em devolução: lá o que está em jogo é mediação, não
operação.

## Antes de rodar — os scripts da pasta

Precisa de `escrever.py` e `responder.py`, deste pacote: se não estiverem na pasta dele, copie
de `${CLAUDE_PLUGIN_ROOT}/scripts/`. E de `meli.py` e `seguro.py`, do pacote **prometheus**; se
faltarem, conecte primeiro com `prometheus-conectar-meli`.

**Nunca sobrescreva `credenciais.txt`, `tokens.json`, `acoes.txt` nem `intencoes.json`.**
