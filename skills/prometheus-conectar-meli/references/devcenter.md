# Criar (ou reaproveitar) a aplicação no DevCenter do Mercado Livre

Leia este arquivo quando o usuário ainda não tem App ID e Client Secret, ou quando já tem uma
aplicação e precisa reaproveitá-la. **Ele faz os cliques, você explica.** Nunca peça para ele
colar App ID ou Client Secret no chat: esses valores vão direto no `credenciais.txt`, que ele
mesmo preenche.

Fonte: documentação oficial do Mercado Livre — "Autenticação e Autorização" e "Permissões
funcionais" (developers.mercadolivre.com.br).

---

## Antes de começar

- Use a **conta dona da operação** — a conta administradora que vende. A aplicação fica presa
  à conta que a criou, e o Mercado Livre recomenda que seja a do titular.
- Conta de **operador ou colaborador não consegue autorizar**: devolve
  `invalid_operator_user_id`. Se o usuário não sabe qual tem, pergunte quem acessa o
  financeiro da loja — normalmente é a administradora.
- Se os dados do titular estiverem **pendentes de validação** no Mercado Livre, a criação pode
  não concluir. Nesse caso vá para o modo demonstração e ele resolve depois.

---

## Passo a passo

### Antes: gerar a URL de retorno desta pessoa

**Faça isto antes de abrir o DevCenter.** Pergunte o nome da loja e rode:

```
python3 pasta.py --nome "Loja do Fulano"
```

Ele grava em `credenciais.txt` a URL de retorno **dela**, por exemplo
`https://loja-do-fulano.invalid/callback`, e imprime a mesma na tela.

Por que não uma URL igual para todo mundo: numa sala, URL idêntica em dezenas de telas é
impossível de conferir — ninguém sabe se o que está no DevCenter é o que está no arquivo. Com
o nome da loja dentro do endereço, a pessoa bate o olho e reconhece a dela.

**E ninguém digita.** Ela copia do `credenciais.txt` e cola no DevCenter. Esta é a regra que
mais importa deste arquivo: **digitação é o erro número um desta etapa**, e foi o que
transformou um bloco de 75 minutos da edição anterior em atendimento um a um.

Se a pessoa **já tem um domínio próprio** e prefere usar, pode: qualquer `https` serve, desde
que fique idêntico nos dois lugares. O domínio não precisa — e não deve — receber nada: a
página dando erro é o comportamento correto.

### No DevCenter

1. Acesse `https://developers.mercadolivre.com.br/devcenter` e faça login **com a conta
   administradora**.

   > **Quem nunca criou aplicação costuma não ser redirecionado para lugar nenhum** — a página
   > simplesmente não leva à criação. Já aconteceu em imersões anteriores. Tenha o endereço
   > direto de criação à mão e mande para ela quando isso acontecer, em vez de ficar
   > procurando botão junto.
2. **Criar aplicação.** Preencha:
   - **Nome:** o que ela reconheça na lista daqui a seis meses. Sugira o padrão
     `Painel <nome da loja>` — por exemplo `Painel Loja do Fulano`.
   - **Nome curto:** o apelido que o `pasta.py` gerou, por exemplo `loja-do-fulano`. Fica
     igual à URL de retorno, e isso faz a tela inteira conferir sozinha.
   - **Descrição:** sugira `Leitura dos meus próprios dados de venda para análise interna.
     Não publica, não altera anúncio nem preço.` — ela ajusta se quiser.
   - **Logo:** **obrigatória**, e o formulário **recusa WebP** — tem de ser PNG. Avise antes:
     salvar imagem do navegador costuma vir em WebP, e descobrir isso no meio do fluxo custa
     uma conversão com a pessoa esperando.

   **Sugira, não imponha.** Se ela quiser outro nome, tudo bem; o que não pode variar é a URL
   de retorno, que tem de ser idêntica ao arquivo.

3. **URIs de redirect** (a tela usa o plural, e tem um botão *Adicionar URI de redirect*):
   cole a que está no `credenciais.txt`. **Nada de digitar.**

4. **Ligue, uma por uma** — e confira cada uma antes de salvar, porque faltar qualquer delas
   só aparece como erro lá na frente, sem dizer o que faltou:

   **Conferido na tela em 22/10/2026**, com os nomes exatos das seções. As versões
   anteriores deste guia erravam aqui.

   Em **Fluxos OAuth** — três caixas lado a lado:

   - [ ] **Authorization Code** — **marcar.** É o fluxo que o pacote usa; costuma já vir
         marcado
   - [ ] **Refresh Token** — **marcar.** Sem ele a conexão cai em poucas horas e pede login
         de novo
   - [ ] **Client Credentials** — **NÃO marcar.** Este guia já mandou marcar, e estava
         errado: é outro fluxo, que o pacote não usa. O App ID e a chave secreta aparecem
         de qualquer jeito

   Em **PKCE necessário** — seção própria, logo abaixo:

   - [ ] **pkce** — **marcar.** É esse o nome na caixa

   Em **Negócios** — "escolha as unidades de negócio que você quer integrar":

   - [ ] **Mercado Livre** — **marcar**
   - [ ] **VIS** — **NÃO marcar.** É `VIS`, não "Visa", e fica colado no de cima

   > Os rótulos mudam de tempos em tempos. Se o que estiver na frente dela não bater com esta
   > lista, vá pelo sentido — e **não siga com alguma delas em dúvida**: é mais barato
   > conferir agora que depurar `403` depois.

5. **Permissões** — é assim que a tela chama; este guia dizia "permissões funcionais".
   **Não são caixas: é uma lista de recursos com um menu em cada um**, que abre em *Sem
   acesso*, *Leitura* e *Leitura e escrita*. **Escolha Leitura** nos que interessam — o pacote
   nunca escreve. Os que importam:
   - Usuários (normalmente já vem ligada)
   - Publicação e sincronização — a lista de anúncios
   - Vendas e envios — os pedidos
   - Promoções, cupons e descontos

   Faltar uma produz `HTTP 403 PA_UNAUTHORIZED_RESULT_FROM_POLICIES`, que **não diz qual
   faltou**. Por isso as quatro vão marcadas desde o começo.

6. **Tópicos e notificações:** não precisa marcar nada. Se o formulário exigir uma URL,
   use a mesma `.invalid`.

7. **Salvar.** **Às vezes dá erro na primeira tentativa.** Clicar de novo costuma
   resolver — avise antes, senão ela acha que preencheu algo errado e começa a desfazer.

### Depois de salvar — a parte que surpreende todo mundo

A pessoa **não** cai numa tela com App ID e chave secreta à mão. O caminho real é este, e
avisar antes evita a sensação de que algo deu errado:

1. Ela é **redirecionada para uma página do Mercado Livre**, não para o DevCenter.
2. Para ver os valores, precisa **abrir a aplicação na lista e clicar em editar**.
3. Nesse momento o Mercado Livre costuma **pedir o login de novo**. É normal; é a conta dela
   mesma.
4. A primeira tela pode mostrar **um erro de callback**. Também é esperado — é a `.invalid`
   fazendo o trabalho dela. **Role até o fim da página e clique em continuar** para chegar nos
   campos.
5. Ali estão o **App ID (client id)** e a **chave secreta (client secret)**.

Sempre que ela precisar ver os valores de novo, é esse mesmo caminho: lista → editar →
login → continuar.

**Na lista, a aplicação aparece como "Aplicativo não certificada", com uma nota de segurança e
um convite a "terminar de configurar a segurança".** Não é erro e não precisa ser resolvido: é
o DevCenter pedindo certificação, que serve a quem publica aplicativo para terceiros. Diga isso
antes que ela leia sozinha e ache que parou no meio.

8. Ela copia os dois valores para o `credenciais.txt`. **Não para o chat.**

---

## Reaproveitar uma aplicação que já existe

Caso comum: o usuário já integra Bling, Olist, Tiny ou outro sistema, e já tem aplicação.

**A regra é adicionar, nunca substituir.**

1. Abra a aplicação existente no DevCenter.
2. Na URL de redirecionamento, **acrescente** a URL que o `pasta.py` gerou para ela à lista,
   mantendo a que já está lá.
3. Nas permissões funcionais, **marque as que faltam** das quatro acima, sem desmarcar nada.
4. Pegue o App ID e o Client Secret dessa aplicação.

**Se a tela não permitir mais de uma URL de redirecionamento, pare.** Trocar a URL de uma
aplicação que sustenta o ERP dele derruba a integração em produção, no meio de uma conversa.

Nesse caso a saída é simples: **crie uma aplicação nova.** Não há limite de uma por titular, e
uma aplicação nova não encosta na que já existe.

Sobre o limite de aplicações por titular: **não existe limite de uma.** Verificado em
20/10/2026 numa conta de vendedor brasileira com **três aplicações** criadas ao mesmo tempo.

Isso importa em dois momentos. Quem já tem aplicação de ERP **não precisa** mexer nela: pode
criar uma nova só para isto, e a integração em produção dele fica intocada — é o caminho mais
seguro e deve ser o primeiro que você oferece. E quem errar na criação pode simplesmente criar
outra, em vez de tentar consertar a que ficou torta.

O reaproveitamento descrito acima continua valendo para quem **preferir** usar a aplicação que
já tem, mas deixou de ser a única saída.

---

## Acesso contínuo

A rotina diária precisa de renovação automática. Depois da autorização, o `autorizar.py` diz
se o Mercado Livre devolveu o refresh token. Se avisar que não veio, confira nas configurações
da aplicação se há opção de acesso offline e autorize de novo.

**"Veio o refresh" não prova que a renovação funciona.** Um Client Secret colado com um espaço
a mais deixa o refresh lá, bonito, e falha na primeira renovação de verdade — que só acontece
umas seis horas depois. Confirme na hora, com a pessoa ainda na sua frente:

```
python3 meli.py renovar
```

Ela deve responder `renovacao funcionou`. Se responder que o Mercado Livre recusou, refaça a
autorização agora — é muito mais barato que descobrir isso no dia seguinte. O
`python3 meli.py check` também passou a mostrar o estado (`renovacao automatica: ligada`).

O refresh token do Mercado Livre é de **uso único**: cada renovação devolve um novo, que
substitui o anterior. O `meli.py` já cuida disso — por isso não se deve copiar `tokens.json`
para outra máquina nem rodar a mesma credencial em dois lugares ao mesmo tempo. Dois
consumidores renovando a mesma credencial derrubam um ao outro, e o sintoma aparece horas
depois, parecendo falha de rede.

---

## Erros comuns nesta etapa

| O que aparece | O que é | O que fazer |
|---|---|---|
| "your client callback has to match with the redirect_uri param" | a URL do `credenciais.txt` não é idêntica à cadastrada | compare caractere por caractere, inclusive barra final |
| `invalid_operator_user_id` | autorizou com conta de operador | repita com a conta administradora |
| `403 PA_UNAUTHORIZED_RESULT_FROM_POLICIES` | falta permissão funcional | marque as quatro, salve e autorize de novo |
| "Sorry, the application cannot connect to your account" | URL divergente, conta de colaborador, ou dados do titular pendentes de validação | confira os três, nessa ordem |
| Client Secret renovado no DevCenter | o valor antigo parou de valer | atualize o `credenciais.txt` e autorize de novo |
