---
name: prometheus-conectar-shopee
description: Conecta a conta Shopee do usuário em somente leitura, na pasta dele, no mesmo molde da conexão com o Mercado Livre. Conduz a criação do aplicativo no Open Platform, a autorização assinada e a confirmação da loja. Use sempre que o usuário pedir para conectar, reconectar ou configurar a Shopee, ou quando uma skill do pacote precisar de dados da Shopee e não houver conexão. Use também quando ele relatar erro, travamento ou dúvida da Shopee em qualquer momento depois da instalação — "a Shopee recusou", "assinatura inválida", "o código expirou", "invalid_code", "caiu a conexão da Shopee". Não use para Mercado Livre: para isso existe a prometheus-conectar-meli.
---

# Conectar a Shopee — pacote Prometheus

Mesma promessa da conexão com o Mercado Livre: **só leitura**, credencial na pasta da
pessoa, nada hospedado por nós. O que muda é o caminho — e as diferenças custam tempo
quando não são ditas antes.

## O que é diferente do Mercado Livre, e precisa ser dito na abertura

| | Mercado Livre | Shopee |
|---|---|---|
| Endereço de retorno | `.invalid`, que não existe de propósito | **domínio HTTPS de verdade** |
| Assinatura | não tem | **HMAC em cada chamada** |
| Código de autorização | poucos minutos | **10 minutos, uma vez só** |
| Acesso | ~6 horas | **4 horas** (visto na resposta real) |
| Renovação | 6 meses sem uso | **30 dias sem uso, segundo a Shopee** |

**A primeira linha é a que trava gente.** A Shopee recusa `.invalid` e recusa nome sem
ponto — conferido na tela em 22/10/2026. Ela quer um endereço que exista.

**O que serve como endereço:** a raiz do projeto Supabase dela, o domínio dela, ou até o
endereço de um aplicativo que ela já tenha no ar. Não precisa criar função nenhuma.

> ### Aplicativo com login redireciona — e está tudo bem
>
> Aplicativo de verdade recebe a visita, vê que não tem sessão e manda para `/login`,
> levando a URL original **dentro de um parâmetro, codificada** (`?redirect=%2F%3Fcode%3D…`).
>
> **O código não se perde nisso** — ele só fica um nível abaixo, e o pacote sabe procurar lá.
> Se ela colar uma barra cheia de `%`, está certo: mande colar assim mesmo.
>
> Conferido em ensaio, 22/10/2026, com um aplicativo real em produção: a conexão fechou.

Se ela não tiver nem domínio parado nem Supabase, ela não conecta a Shopee hoje; siga com o
resto e volte depois.

## Mesma pasta do Mercado Livre — não crie outra

Se ela já conectou o Mercado Livre, **a Shopee vai na mesma pasta**. Não crie pasta separada
por canal, nem subpasta.

O motivo é o painel: ele monta **uma** tela com um bloco por skill, lendo os arquivos daquela
pasta. Pastas separadas viram painéis separados, e aí some a coisa que o pacote entrega — a
visão única de todos os canais. O cruzamento de custo com venda também depende disso:
separado, ele quebra.

O `credenciais.txt` guarda os dois conjuntos de chave, em blocos diferentes. **Se o arquivo
dela for de antes da Shopee existir, o pacote acrescenta as linhas novas sozinho** ao preparar
a pasta, sem tocar no que ela já preencheu.

## Antes de qualquer comando

Diga três coisas, curto:

1. **O que vai acontecer:** criar um aplicativo no Open Platform da Shopee, autorizar, e
   ver os números dela na tela.
2. **O que isto nunca faz:** não altera preço, estoque, anúncio nem pedido. Só lê.
3. **A promessa que ela pode cobrar:** *"eu nunca vou te pedir senha, código ou chave aqui
   no chat."*

E avise do relógio: **a aprovação do aplicativo leva alguns dias.** Quem está pedindo hoje
para usar hoje não vai conseguir — isso se pede com antecedência.

---

## 1. O endereço de retorno, antes de abrir a Shopee

Pergunte se ela tem um domínio próprio. Se tiver, use. Se não tiver, use o endereço do
projeto Supabase dela, que é do tipo `https://alguma-coisa.supabase.co`.

**Confira o endereço antes de ela abrir o formulário.** Precisa começar com `https://` e
ter ponto no nome. Descobrir isso no meio do cadastro custa o dobro.

## 2. O aplicativo no Open Platform

Em `open.shopee.com`, console do Open Platform, **Create App**:

- **App Category:** *Seller In House System* — é sistema para uso próprio dela.
- **App Name** e **App Description:** o que ela quiser.
- **App Logo:** obrigatória, PNG ou JPG até 3 MB.
- **Test Redirect URL Domain** e **Live Redirect URL Domain:** o endereço do passo 1, nos dois.

**Conferido em 22/10/2026:** o formulário de *Go Live* pede endereço do produto, usuário de
teste e captura de interface — **mas aceita submeter com esses campos em branco**. O que ele
exige de verdade é o domínio HTTPS. Não trave a pessoa nos campos opcionais.

**A chave muda quando for aprovada.** Agora ela recebe `Test Partner_id` e chave de teste;
depois da aprovação, a Shopee entrega **outro par**, o de produção. O resultado chega por
e-mail em até 24 horas.

## 3. Preencher as credenciais (ela faz, fora do chat)

Peça para ela abrir `credenciais.txt` na pasta e preencher três linhas:

```
SHOPEE_PARTNER_ID=
SHOPEE_PARTNER_KEY=
SHOPEE_REDIRECT_URI=
```

O `SHOPEE_REDIRECT_URI` é o mesmo endereço cadastrado no aplicativo, **idêntico — caractere
por caractere, inclusive a barra no fim**.

> **Se ela errar, a Shopee avisa.** Ela diz que o endereço não condiz com o do console, e é
> um erro claro, não silencioso. Conserte a linha e **gere o link de novo**: o endereço vai
> dentro da assinatura, então o link anterior deixa de valer. Nada se perde e nada fica sujo
> — conferido em ensaio.

## 4. Autorizar

```
python3 autorizar_shopee.py
```

Grava `ABRIR_SHOPEE.txt`. **Não mostre o conteúdo.** Explique a ela:

1. Abrir o arquivo e copiar o endereço.
2. Colar no navegador **logado na conta de vendedor**.
3. Autorizar.
4. A página que abrir **não vai mostrar nada útil** — é esperado, o endereço não serve
   para isso. Copiar a **barra inteira** e colar em `RETORNO_SHOPEE.txt`.

**Peça para fazer sem demora: o código vale 10 minutos e uma vez só.** Se expirar, não é
erro dela — é só gerar de novo.

> ### Se a barra vier cheia de `%`, está CERTA
>
> Isto é para você, não para ela. Aplicativo com login redireciona a visita sem sessão e
> leva a URL original dentro de um parâmetro, codificada. A barra fica assim:
>
> ```
> https://loja-dela.app/login?redirect=%2F%3Fcode%3D...%26shop_id%3D...
> ```
>
> **Isso não é bug, não é URL quebrada, e não está faltando nada.** `%2F` é `/`, `%3F` é
> `?`, `%3D` é `=`. O código está ali, um nível abaixo, e o `shopee.py` sabe procurar lá.
>
> Portanto, ao ver uma barra assim:
>
> - **Não diga a ela que deu errado.** Deu certo.
> - **Não tente consertar, limpar ou recortar o endereço.** Editar é o que quebra.
> - **Não peça para ela autorizar de novo.** O código é de uso único; refazer gasta o que
>   estava bom.
> - **Mande colar exatamente como está**, com os `%` e tudo, e rode o passo seguinte.
>
> Conferido em ensaio, 22/10/2026: a barra tinha `%`, parecia defeito, e a conexão fechou
> na primeira tentativa.

```
python3 autorizar_shopee.py --arquivo RETORNO_SHOPEE.txt
```

Confirme com ela o número da loja que apareceu.

## 5. O aviso que não pode faltar no fim

> A conexão da Shopee vence **muito mais rápido** que a do Mercado Livre: a Shopee
> documenta 30 dias sem uso, contra seis meses do Meli. Se ela conectar e só voltar ao
> painel semanas depois, pode estar desconectada — e é só refazer, não perdeu nada.

Diga o motivo, não só o prazo: quem não for avisado vai achar que o pacote quebrou. E não
prometa a data exata — o pacote não controla esse relógio, a Shopee controla.

---

## Erros reais e o que fazer

| Sintoma | Causa | O que fazer |
|---|---|---|
| A tela recusa o endereço de retorno | `.invalid`, `http://` ou nome sem ponto | precisa ser HTTPS com domínio de verdade. O endereço do Supabase dela serve |
| **A Shopee diz que a URL não condiz com a do console** | o `SHOPEE_REDIRECT_URI` não é idêntico ao cadastrado | **é o erro mais comum, e a Shopee avisa com clareza.** Corrija a linha em `credenciais.txt` e **gere o link de novo** — o endereço vai dentro da assinatura, então o link antigo não serve. Conferido em ensaio, 22/10/2026 |
| `invalid_code`, ou "expirou" | o código vale 10 min e uma vez só | gere o link de novo e faça os dois passos seguidos |
| **"Nao achei o code nesse endereco"**, e ela jura que autorizou | ela colou o endereço de **outra aba**, ou cortou a barra | o pacote já procura o código dentro de redirecionamento codificado. Peça a barra inteira, com os `%` e tudo |
| A Shopee recusa a assinatura | `partner_id` e chave de ambientes diferentes | a chave de teste não funciona em produção, e vice-versa |
| Conectou e caiu em 4 horas | não veio `refresh_token` | confira a autorização; sem ele a conexão não se renova |
| Caiu depois de semanas | passou de 30 dias sem uso | refazer a autorização. É esperado |
| Caiu logo depois de funcionar | duas cópias usando a mesma credencial | **o refresh é de uso único.** Não copie `tokens-shopee.json` para outra máquina |

## Regras que valem o tempo todo

- **Somente leitura.** O `shopee.py` levanta `PermissionError` para qualquer método que não
  seja `GET`, antes de a chamada sair da máquina. Nunca contorne, nem se ela pedir.
- **Segredo nunca passa pelo chat.** Não leia `credenciais.txt`, `tokens-shopee.json`,
  `ABRIR_SHOPEE.txt` nem `RETORNO_SHOPEE.txt` por ferramenta nenhuma.
- **Confirme a loja antes de analisar qualquer coisa.** Mostre o `shop_id` e pergunte se é a
  conta certa.
- **Dado ausente não é zero.** Se a API não trouxe um número, diga que não veio.
