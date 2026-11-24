# Pedir (ou reaproveitar) a aplicação no DevCenter do Mercado Livre

Leia este arquivo quando o usuário ainda não tem App ID e Client Secret, ou quando já tem uma
aplicação e precisa reaproveitá-la.

> **Mudou em 16/11/2026 — quem nunca criou aplicação não cria mais sozinho.** O botão
> *Criar nova aplicação* sumiu do DevCenter para essa pessoa. O caminho oficial é um
> **formulário**: ela manda o pedido, o Mercado Livre analisa e, se aprovar, **cria a aplicação
> na conta dela** — em **até 10 dias** (prazo do guia oficial, 23/11/2026). **Enviar não garante aprovação**. Por isso este
> arquivo agora tem duas partes: **pedir** (hoje) e **configurar** (depois da aprovação).
> Quem já tem aplicação não passa pelo formulário.

**Ele faz os cliques, você explica.** Nunca peça para ele colar App ID ou Client Secret no chat: esses valores vão direto no `credenciais.txt`, que ele
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
- Se os dados do titular estiverem **pendentes de validação** no Mercado Livre, o pedido pode
  não ser aprovado. Peça para regularizar antes de pedir. Se não der, vá para o modo demonstração
  e ele resolve depois. Pedido **já enviado** não é demonstração: em análise, espera; recusado, para
  e orienta.
- **Quem nunca criou aplicação: peça hoje.** A análise leva até 10 dias e nada do DevCenter
  em diante funciona antes dela. O resto (pasta, `credenciais.txt`, URL de retorno) dá para
  deixar pronto enquanto espera.

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

### Quem nunca criou aplicação: peça pelo formulário

Só para quem **nunca criou** nenhuma, **nem no passado**: lista vazia hoje não prova isso, então
pergunte. **O formulário não avisa na tela** que a conta não se encaixa: ele aceita o envio, e a
conferência só acontece depois. Ele também **não atende aplicações MCP**; este pacote não é uma,
lê direto a API do Mercado Livre. Se o projeto da pessoa for um servidor MCP, este caminho não
serve: diga isso antes de ela preencher, e não prometa alternativa.

Ele é do Google
Forms, está **em inglês** e o endereço é `https://forms.gle/2Q39SStHLJNQLjuK9` (título
*Application Creation Request — Mercado Libre*). Não é pelo DevCenter.

1. **Pegue o apelido da conta.** Em *Meu perfil → Dados da conta* do Mercado Livre, o campo
   **Apelido** (*username*) — não o e-mail e não o nome da loja. Tem de ser da **conta dona
   da operação**: a aplicação nasce nela.
2. **Preencha**, na ordem em que as perguntas aparecem (conferido na tela em 24/11/2026):
   - **What is the username of that account?** — o apelido, exatamente como está.
   - **What is the intended use of the application?** (a primeira) — **Personal use** (a
     aplicação só vai ler a conta dela). *Business or third-party use* é para quem deixa
     outras pessoas conectarem contas: não é o caso.
   - **What is the intended use of the application?** (a segunda — o título se repete, mas
     agora são as **funções**) — **Manage sales**, a indicada na imersão (pedidos são a base do
     pacote). Diga à pessoa, de forma leve e direta:
     - **Processo novo** (16/11/2026): **ainda não sabemos** se a função escolhida limita os
       escopos depois da aprovação. Indicamos *Manage sales* por ser a aposta mais versátil, **não
       porque alguém confirmou** que ela libera mais.
     - **Na imersão o foco é *Manage sales*:** é nela que damos suporte, em uma linha só.
     - **Quem tem um projeto em mente** (automação de promoções, repasses, criar anúncios…)
       pode escolher outra: *Manage or optimize prices*, *Financial and Fiscal*, *Manage
       product listings*. Escolher outra vertente pode limitar o suporte que conseguimos dar,
       e **seguir com ela é responsabilidade da pessoa**. Não trave nem insista.
     - Depois da aprovação, a gente confere o que ficou liberado (parte abaixo).
   - **Describe what the application will do.** — aceita português. Sugira: `Painel de
     leitura dos meus próprios dados de vendedor — pedidos, anúncios e promoções da minha
     conta. Não publica e não altera anúncio nem preço.`
   - **What is the application's redirect URL?** — **cole** a do `credenciais.txt`. Nada de
     digitar.
   - **Share a demo link…** — opcional. Deixe vazio.
3. **Enviar.** O rodapé do formulário diz o que acontece: o Mercado Livre confere a conta e,
   se aprovar, **a aplicação é criada e aparece no DevCenter** do país da conta (para o Brasil,
   `developers.mercadolivre.com.br/devcenter`, logado com a mesma conta do pedido).
4. **Anote a data de hoje e pare aqui.** Não é erro: a análise leva **até 10 dias** e
   **pode não ser aprovada**. Peça para ela guardar a data e a conta usada no pedido.
5. **Quando a pessoa voltar** ("o ML aprovou", "apareceu a aplicação", ou só retomando a
   conversa): **não recomece.** Pergunte a data do pedido, peça que abra o DevCenter com a
   mesma conta e confira se a aplicação **apareceu na lista**. Apareceu: confirme que
   ela **nasceu desse pedido** (não existia antes e traz a URL do `credenciais.txt`) e que nenhum
   sistema a usa. Em dúvida, ou se um ERP usa, vá para "Reaproveitar". Confirmado: siga para "No DevCenter
   (depois da aprovação)" abaixo e depois para as credenciais (etapa 4 do `SKILL.md`). Não
   apareceu: dentro de 10 dias, só aguardar; passou, conferir se a
   conta e o apelido estavam certos. Não conhecemos canal oficial de acompanhamento: não mande
   reenviar por conta própria nem prometa prazo novo. **Recusado:** pare e
   oriente ("Se o pedido foi recusado", logo abaixo).

Enquanto espera, **dá para deixar pronto tudo o que não depende da aprovação**: a pasta, o
`credenciais.txt` e a URL de retorno.

### Se o pedido foi recusado

**Pare a conexão aqui.** Não há modo demonstração nem aplicação emprestada. Diga que a decisão é
do Mercado Livre e oriente, sem adivinhar o motivo:

1. Se o Mercado Livre disse o motivo, siga o que ele pediu. Se não disse, peça para a pessoa
   perguntar ao suporte do Mercado Livre, logada na conta do pedido.
2. Confira com ela o que se sabe: a conta é a **dona da operação**, os dados do titular **não estão
   pendentes** e ela **nunca criou aplicação**. Se já criou e ela ainda existe, vá para
   "Reaproveitar".
3. Não mande reenviar o pedido sem corrigir o motivo ou sem o Mercado Livre orientar, e não
   prometa que um novo pedido passa.
4. A pasta e o `credenciais.txt` ficam guardados: quando houver aplicação, ela volta e a conexão
   continua dali.

### No DevCenter (depois da aprovação)

1. Acesse `https://developers.mercadolivre.com.br/devcenter` e faça login **com a mesma conta
   do pedido**. A aplicação **já vem criada** — não há o que preencher de Nome, Descrição ou
   Logo.

   > Se a lista estiver vazia: ou o pedido ainda não foi aprovado, ou ela entrou com outra
   > conta. Confira a conta antes de qualquer outra coisa.
2. **Abra a aplicação** (Editar aplicação). O Mercado Livre pede o login de novo; é normal. Pode
   aparecer um **erro de callback**: também é esperado.

   **A aplicação abre em duas partes.** Uma mostra o **App ID** e a **chave secreta**; URL de
   retorno, interruptores e permissões ficam **depois do botão Continuar**, no fim da página.
   Copie os dois valores direto para o `credenciais.txt` (**nunca para o chat**), role até o fim e
   clique em **Continuar**. Se o que você procura não está na tela, está do outro lado desse botão.
3. **URIs de redirect** (a tela usa o plural, e tem um botão *Adicionar URI de redirect*):
   a que ela pôs no formulário **já deve estar lá**. Compare com o `credenciais.txt` —
   idêntica, inclusive a barra final — e, se faltar, cole a do arquivo. **Nada de digitar.**

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

   > **Quem pediu pelo formulário:** se algum desses recursos **não aparece**, ou só aparece
   > como *Sem acesso* e não deixa mudar, pode ser a função escolhida no pedido limitando os
   > escopos (ainda não sabemos). **Não é erro da pessoa.** Anote qual recurso faltou, diga que
   > vamos descobrir como ampliar. Dá para seguir com o resto, mas **avise o que fica de fora**:
   > sem *Publicação e sincronização* não há anúncios; sem *Vendas e envios*, não há pedidos; sem
   > *Promoções, cupons e descontos*, não há promoções. Essas skills vão dar `403`. Sem *Usuários*,
   > **pare**: não dá para confirmar a conta. Não diga que a conexão ficou completa.

6. **Tópicos e notificações:** não precisa marcar nada. Se o formulário exigir uma URL,
   use a mesma `.invalid`.

7. **Salvar.** **Às vezes dá erro na primeira tentativa.** Clicar de novo costuma
   resolver — avise antes, senão ela acha que preencheu algo errado e começa a desfazer.

### Depois de salvar — a parte que surpreende todo mundo

Ao **salvar**, ela costuma ser **redirecionada para uma página do Mercado Livre**, não para o
DevCenter. Não é erro. Se ainda não copiou o **App ID** e a **chave secreta**, ou precisar vê-los
de novo, é o mesmo caminho: lista → editar → login → os dois valores (se um erro de callback estiver
na frente, role até o fim e siga por ele).

**Na lista, a aplicação aparece como "Aplicativo não certificada", com uma nota de segurança e
um convite a "terminar de configurar a segurança".** Não é erro e não precisa ser resolvido: é
o DevCenter pedindo certificação, que serve a quem publica aplicativo para terceiros. Diga isso
antes que ela leia sozinha e ache que parou no meio.

Confirme que os dois valores estão no `credenciais.txt`. **Não no chat.**

---

## Reaproveitar uma aplicação que já existe

Caso comum: o usuário já integra Bling, Olist, Tiny ou outro sistema, e já tem aplicação.

**A regra é adicionar, nunca substituir.**

1. Abra a aplicação existente no DevCenter.
2. Na URL de redirecionamento, **acrescente** a URL que o `pasta.py` gerou para ela à lista,
   mantendo a que já está lá.
3. Nas permissões, **mexa só nas que estão em *Sem acesso*** entre as quatro acima, e ponha
   *Leitura*. **O que já está em *Leitura e escrita* fica como está:** baixar para *Leitura* quebra
   o sistema que usa essa aplicação.
   Nos interruptores, ligue *Authorization Code* e *Refresh Token* se faltarem e **não desligue
   nenhum** — o "NÃO marcar" da lista acima vale só para aplicação nova. Se *pkce* estiver
   desligado, **não ligue sem confirmar** com quem cuida do sistema: ligado, ele passa a ser
   exigido de todos, e o ERP pode parar de autorizar.
4. **Salve** e confira, reabrindo, que a URL antiga e os acessos antigos continuam lá.
5. Ela copia o App ID e o Client Secret para o `credenciais.txt`. **Não para o chat.**

A URL e as permissões ficam depois do botão **Continuar**, como na aplicação aprovada.

**Diga antes de autorizar:** se a aplicação tem *Leitura e escrita*, o acesso gerado pode carregar
escrita também. **O pacote só faz leitura** (o `meli.py` recusa o resto), mas isso é trava do
pacote, não do Mercado Livre. Se ela não quiser, modo demonstração.

**Se a tela não permitir mais de uma URL de redirecionamento, pare.** Trocar a URL de uma
aplicação que sustenta o ERP dele derruba a integração em produção, no meio de uma conversa.

Sobre **criar uma aplicação nova para quem já tem outra**: em 20/10/2026 isso funcionava (três
aplicações na mesma conta). **Desde 16/11/2026 não vale mais:** o formulário não atende quem já
criou aplicação, e o DevCenter manda falar com o time OpenPlatform do Mercado Livre, que não tem canal
público. Portanto **não prometa** uma aplicação nova a quem já tem — o caminho é o
reaproveitamento acima, e, se a tela não aceitar mais de uma URL, o modo demonstração.

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
| Pediu pelo formulário, mas já tinha criado aplicação antes | o pedido é só para quem nunca criou, e a tela não avisa | use a que já existe (seção "Reaproveitar"); se não sobrou nenhuma, veja "Se o pedido foi recusado" (ou espere, se ainda está em análise) |
| "your client callback has to match with the redirect_uri param" | a URL do `credenciais.txt` não é idêntica à cadastrada | compare caractere por caractere, inclusive barra final |
| `invalid_operator_user_id` | autorizou com conta de operador | repita com a conta administradora |
| `403 PA_UNAUTHORIZED_RESULT_FROM_POLICIES` | falta permissão funcional | confira as quatro, dê *Leitura* só às que estão em *Sem acesso*, sem baixar nenhuma, salve e autorize de novo. Se o recurso não aparece ou não deixa mudar, veja o aviso das Permissões |
| "Sorry, the application cannot connect to your account" | URL divergente, conta de colaborador, ou dados do titular pendentes de validação | confira os três, nessa ordem |
| Client Secret renovado no DevCenter | o valor antigo parou de valer | atualize o `credenciais.txt` e autorize de novo |
