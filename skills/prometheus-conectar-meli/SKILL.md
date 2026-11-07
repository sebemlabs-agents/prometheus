---
name: prometheus-conectar-meli
description: "Conecta a conta do Mercado Livre do usuário em somente leitura, na pasta dele, e deixa o pacote Elo pronto para usar. Conduz a criação do aplicativo no DevCenter, a autorização OAuth sem expor segredo no chat, a confirmação da conta e o primeiro painel. Use sempre que o usuário pedir para conectar, reconectar, instalar ou configurar o Mercado Livre, o pacote Elo ou qualquer skill prometheus-*, ou quando outra skill do pacote falhar por falta de conexão — mesmo que ele não diga \"conectar\". Use também quando ele relatar QUALQUER erro, travamento ou dúvida sobre o pacote, em qualquer momento depois da instalação: \"deu erro\", \"não funciona\", \"parou\", \"python não encontrado\", \"invalid_grant\", \"a pasta foi recusada\", \"o painel não abre\", \"perdi o acesso\". Use também quando ele perguntar se está atualizado, por que uma correção não chegou, ou como ligar a atualização automática do pacote. A tabela de sintomas reais está em references/problemas.md."
---

# Conectar o Mercado Livre — pacote Elo

> **Deu erro em qualquer ponto — agora ou semanas depois?** Abra
> `references/problemas.md` **antes de improvisar**. É uma tabela de sintoma → causa → o que
> fazer, com os erros reais que já aconteceram em máquina de verdade. Improvisar aqui gasta o
> tempo do usuário e costuma errar: as mensagens do Mercado Livre não dizem a causa real.


Esta skill tem uma missão só: levar o usuário de "nunca conectei nada" até **os números da
própria loja na tela**, em cerca de 10 minutos, pelo mesmo caminho que todas as outras
pessoas seguem.

O caminho é fixo de propósito. Na edição anterior deste material, cada pessoa escolhia a URL
de retorno e o Mercado Livre respondia com uma mensagem que não diz onde está o erro — e um
bloco de 75 minutos virou atendimento um a um. Aqui a URL vem escrita no pacote e o usuário
copia. **Não invente endereço, não sugira variação, não improvise ordem de passos.**

## Como abrir com o usuário

Antes do primeiro comando, diga três coisas — curto, sem lista técnica. É o que faz ele
seguir sem medo, e é a única parte que não dá para recuperar depois:

1. **O que vai acontecer:** criar um aplicativo no site de desenvolvedores do Mercado Livre,
   autorizar, e ver os números dele na tela. Cerca de 10 minutos.
2. **O que isto nunca faz:** não altera preço, estoque, anúncio nem pedido; não adere a
   promoção; não responde cliente. Só lê.
3. **A promessa que ele pode cobrar:** *"eu nunca vou te pedir senha, código ou chave aqui no
   chat. Tudo isso fica em arquivos na sua pasta. Se em algum momento alguém te pedir isso
   por mensagem, desconfie."*

A terceira é a mais importante e a que mais se esquece. Ela entrega ao usuário um critério
para julgar sozinho, hoje e com qualquer outra ferramenta — vale mais que a explicação do
protocolo.

Avise também, quando ele parecer perdido, que **travar é normal**: a parte do DevCenter é
chata para todo mundo na primeira vez.

## Regras que valem o tempo todo

Estas regras existem porque a credencial dá acesso à conta de venda da pessoa:

- **Somente leitura.** O `meli.py` levanta `PermissionError` para qualquer método que não
  seja `GET`, antes de a chamada sair do computador. Nunca tente contornar, nem se o usuário
  pedir para aderir a uma promoção ou mudar um preço. Quando ele pedir, explique que a
  decisão é dele e se faz no painel do Mercado Livre — e, se útil, entregue o texto pronto
  para ele colar lá.
- **Segredo nunca passa pelo chat.** App ID, Client Secret, código de autorização, tokens e a
  URL de retorno ficam só em arquivos da pasta. **Não leia** `credenciais.txt`, `.env`,
  `tokens.json`, `RETORNO.txt`, `ABRIR_NO_NAVEGADOR.txt` nem `.oauth_state` por nenhuma
  ferramenta — nem `cat`, nem leitor de arquivo, nem cópia para o seu contexto. Para saber se
  estão preenchidos, use `python3 meli.py check`, que responde apenas "preenchido" ou
  "VAZIO". Se o usuário colar um segredo no chat mesmo assim, avise que o certo é renovar o
  Client Secret no DevCenter depois.
- **Confirme a conta antes de analisar qualquer coisa.** Depois de conectar, rode
  `python3 meli.py me`, mostre apelido e id, e pergunte se é a conta certa.
- **Dado ausente não é zero.** Se a API não trouxe um número, diga que não veio. Separe o que
  é fato da API, o que é cálculo e o que é desconhecido.
- **A decisão é do vendedor.** Prioridade e percentual sugerido são apoio. Margem depende do
  custo de cada produto, que a API não tem.

## Onde os comandos rodam

Os scripts ficam numa pasta do computador dela conectada ao Claude, e os comandos rodam de
dentro dela. **Quem escolhe o lugar e cria a pasta é você, na etapa 0** — não peça para ela
criar nem escolher, porque o lugar errado (dentro de um serviço de sincronização) manda o
token da conta de venda para a nuvem sem ela perceber.

Use uma pasta só para isto; não misture com outros arquivos.

---

## Instalação — siga em ordem, confirmando cada etapa

### 0. Preparar a máquina — você executa, ela não digita

**Esta etapa é uma tabela fixa. Siga na ordem, use o comando exato, não invente
variação e não pule.** O aluno não digita nada aqui: quem roda é você. Quando a tabela
não cobre o que apareceu na tela, isso é "causa não determinada" (ver o fim desta
etapa) — nunca palpite.

#### 0.1 Achar o Python

Teste **nesta ordem** e **pare no primeiro que responder 3.8 ou mais novo**:

```
python3 --version
py -3 --version
python --version
```

**Daqui em diante use sempre o que funcionou**, em todos os comandos desta skill. Neste
arquivo está escrito `python3`; troque pelo da máquina dela.

Achou um válido? Pule para 0.3.

Se vier **3.7 ou anterior**: não tente rodar o pacote. O pacote aceita **3.8 ou mais
novo** e, quando precisa instalar de zero, instala a **3.12**. Diga que a versão é antiga,
sem tratar como erro dela, e siga para 0.2 como se não existisse.

#### 0.2 Instalar, com autorização antes do primeiro efeito

**Pergunte antes de instalar qualquer coisa.** Diga, em uma frase: que vai instalar o
Python, **de onde**, que é só para a conta dela, e que **isso altera o PATH da máquina**.
Ela aprova ou recusa. **Recusou, siga para 0.6** — sem insistir, sem repetir o pedido.

Com o sim, o comando é um só, por sistema:

| Sistema | Comando |
|---|---|
| **Windows** | `winget install --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements` |
| **macOS** | normalmente já vem. Se não veio, use o plano B abaixo |

As duas flags de acordo não são enfeite: sem elas o `winget` abre uma pergunta no primeiro
uso e **fica parado esperando uma resposta que ela não vê**.

##### Plano B — quando o `winget` não existe

Confira antes com `winget --version`. Em Windows 10 mais antigo, em edição LTSC ou em máquina
sem a Loja, **ele simplesmente não está lá** — e isso não é erro dela.

Nesse caso **você não instala; ela instala, com dois cliques.** É o mesmo arquivo que o
`winget` baixaria, do site de quem faz o Python:

1. Mande o endereço `python.org/downloads` e peça para ela baixar a versão **3.12**.
2. **O passo que mais gente pula:** na primeira tela do instalador, marcar
   **"Add python.exe to PATH"** antes de clicar em instalar. Sem isso o Python existe e nada
   o encontra. Diga isso **antes** de ela abrir o arquivo, não depois.
3. Deixe a instalação como vem — **"Install Now"**, que instala só para a conta dela e não
   pede senha de administrador. Não mande marcar "Install for all users".
4. Terminou, volte para 0.3.

Se a máquina for **Windows em ARM**, o botão grande do site entrega a versão errada: ela
precisa da linha **arm64** na lista de downloads da 3.12.

**Vale uma tentativa, como todo o resto.** Não deu, é 0.6 — e nunca outro gerenciador de
pacotes, outro site ou versão "portátil".

**Nunca** peça senha de administrador, **nunca** use instalador alternativo, **nunca**
oriente a desligar antivírus, controle de aplicativo ou qualquer proteção, e **nunca**
tente outro canal quando um for bloqueado. Se o caminho exige qualquer uma dessas
coisas, é 0.6.

#### 0.3 Achar o Python recém-instalado (o passo que todo mundo erra)

**No Windows, o PATH novo não vale para um terminal que já estava aberto.** O comando
vai continuar dizendo que não existe, e isso não significa que a instalação falhou.

Não reinicie nada e não peça para ela fechar o Claude. Procure pelo caminho absoluto:

```
py -3 --version
%LOCALAPPDATA%\Programs\Python\Python312\python.exe --version
%LOCALAPPDATA%\Programs\Python\Python312-arm64\python.exe --version
```

**A terceira linha é para Windows em ARM**, onde a pasta leva o sufixo `-arm64`. A maioria
das máquinas é x64 e para na segunda; se nenhuma das duas responder, tente a de ARM antes
de concluir que a instalação falhou.

Quando uma responder, **use o caminho absoluto dela em todos os comandos seguintes**.

#### 0.4 Criar a pasta no lugar certo

Você escolhe o lugar, não ela. **Pergunte o nome da loja** (vira a URL de retorno) e crie:

| Sistema | Pasta |
|---|---|
| **Windows** | `C:\Users\<nome>\prometheus` |
| **macOS** | `~/prometheus` |

**No Windows não use `Documentos`**: ela costuma estar dentro do OneDrive, e o pacote vai
recusar — corretamente, porque o token da conta de venda dela não pode ir para a nuvem.

#### 0.5 Conectar a pasta ao Claude

Este é o único passo da etapa 0 que depende dela, e é **um clique, não um comando**: o
Claude precisa de acesso à pasta para rodar os scripts. Peça a permissão e espere ela
aprovar.

#### 0.6 Quando não deu — três saídas, decididas pelo que você viu

**Nunca culpe o TI dela sem prova, e nunca peça ajuda a quem não pode ajudar.**

| O que apareceu na tela | O que é | O que fazer |
|---|---|---|
| Uma janela aberta esperando confirmação, ou instalação em andamento | **ação dela** | peça **uma vez**, dizendo o clique exato |
| Negativa explícita de permissão de administrador, ou bloqueio nomeado por política da empresa | **depende do TI dela** | siga para o modo demonstração (etapa 7) dizendo que depende do administrador |
| **Qualquer outra coisa** | **causa não determinada** | siga para o modo demonstração dizendo apenas *"não deu para instalar aqui"* — sem atribuir a ninguém |

**Pediu ajuda uma vez e não resolveu → modo demonstração.** Uma tentativa, uma ação
concreta, e segue. **Não abra uma segunda rodada de conserto de Python.** Numa sala com
muita gente, insistir num caso trava o monitor e para a fila inteira — foi o que aconteceu
na edição anterior, com outro assunto.

Antes de seguir para a demonstração, **deixe a volta marcada** (etapa 7): o que faltou fica
registrado, e conectar depois é retomar, não começar de novo.

### 1. Preparar a pasta (e a verificação que mais importa)

Copie para a pasta do usuário todos os arquivos de `scripts/` deste pacote, com os mesmos
nomes. Depois rode:

**Atenção no Windows:** a pasta `Documentos` costuma estar **dentro do OneDrive**, e o passo
abaixo vai recusar — corretamente. Peça uma pasta na raiz do perfil, como
`C:\Users\<nome>\prometheus`, antes de copiar qualquer coisa.

Pergunte **o nome da loja** antes de rodar — ele vira a URL de retorno própria dela:

```
python3 pasta.py --nome "Loja do Fulano"
```

Ele faz quatro coisas: **recusa a pasta se ela estiver dentro de Dropbox, iCloud, Google
Drive ou OneDrive**, cria `credenciais.txt` se ainda não existir (nunca sobrescreve), instala
`.gitignore` e fecha a permissão dos arquivos sensíveis.

Se ele parar por sincronização, **pare também**. Não contorne. Peça para o usuário criar uma
pasta fora do serviço de sincronização e comece de novo ali. O token da conta dele não pode
ir para a nuvem sem ele saber.

Em seguida valide que os scripts estão inteiros:

```
python3 -m py_compile *.py
```

### 2. Conferir o acesso à API

```
python3 -c "import http.client as h; c=h.HTTPSConnection('api.mercadolibre.com',timeout=15); c.request('GET','/sites/MLB'); print('ok', c.getresponse().status)"
```

Usa o mesmo caminho de rede que os scripts vão usar, e funciona igual no Mac e no Windows —
`curl` e `grep` não existem no Windows por padrão.

**Qualquer `ok` serve, inclusive `ok 403`.** Sem login o Meli responde 403, e isso prova que
a resposta veio dele: o caminho está aberto, siga.

**Não deu `ok`? Não conclua que o administrador precisa liberar.** Erro de rede não prova
bloqueio administrativo, e culpar o TI dela sem prova manda a pessoa para uma conversa que não
resolve nada. Olhe o que a mensagem diz:

| O que apareceu | O que é | O que fazer |
|---|---|---|
| Fala em nome que não resolve, DNS ou host desconhecido | a máquina não achou o endereço | pode ser a rede dela, não permissão. Vale conferir se a internet está de pé e tentar de novo |
| Fala em certificado | quase sempre um proxy da empresa no meio do caminho | aí sim é conversa com o TI, **mas é sobre o proxy**, não sobre liberar domínio no Claude |
| Demorou e parou (timeout) | rede lenta, ou o Mercado Livre fora do ar | tente de novo uma vez antes de qualquer conclusão |
| Diz explicitamente que o domínio não é permitido | aí é o Claude | Configurações → Capabilities → domínios permitidos. **Em conta de empresa quem libera é o administrador**, e isso pode não sair na hora |
| **Qualquer outra coisa** | **não deu para saber** | não atribua a ninguém |

Em todos os casos em que não resolver na hora: **modo demonstração** (etapa 7), com a volta
marcada. Ela constrói tudo igual e conecta depois.

### 3. O aplicativo no DevCenter

Pergunte se o usuário já tem aplicação no DevCenter do Mercado Livre.

- **Não tem, ou não sabe:** siga `references/devcenter.md` com ele. Ele faz os cliques, você
  explica.
- **Já tem** (porque integra ERP, por exemplo): vá na seção "Reaproveitar uma aplicação que já
  existe" do mesmo arquivo. A regra é **adicionar** a URL de retorno e as permissões, nunca
  substituir — trocar a URL de um aplicativo em produção derruba a integração do ERP dele.

Os três pontos que mais dão erro: a URL de redirecionamento idêntica à do `credenciais.txt`
(**ela copia do arquivo, nunca digita**), os interruptores de authorization code, refresh
token, PKCE e credenciais de API, e as quatro permissões funcionais.

**Avise antes do que vem depois de salvar:** ela vai cair numa página do Mercado Livre, vai
precisar abrir a aplicação e clicar em editar, logar de novo, e passar por uma tela de erro de
callback clicando em continuar lá embaixo — só então aparecem App ID e chave secreta. Quem não
é avisado acha que quebrou.

### 4. Preencher as credenciais (o usuário faz, fora do chat)

Peça para ele abrir `credenciais.txt` na pasta (TextEdit no Mac, Bloco de Notas no Windows),
colar o **App ID** e o **Client Secret** depois do `=` nas duas linhas indicadas, salvar e
avisar aqui. Então rode:

```
python3 meli.py check
```

Ele responde apenas "preenchido" ou "VAZIO" por campo, sem mostrar valor.

### 5. Conectar a conta

1. `python3 autorizar.py` — grava `ABRIR_NO_NAVEGADOR.txt`. **Não mostre o conteúdo.**
2. Crie um arquivo vazio `RETORNO.txt` na pasta, para o usuário só precisar abrir e colar.
3. Explique a ele: abrir `ABRIR_NO_NAVEGADOR.txt`, copiar o endereço, colar no navegador
   **logado na conta administradora do Mercado Livre**, e autorizar. O navegador vai mostrar
   erro de página — **isso é esperado**, o endereço não existe de propósito e o código fica só
   na barra dele. Copiar a URL inteira da barra, colar em `RETORNO.txt`, salvar, avisar.
   Peça para fazer sem demora: o código vale poucos minutos.
4. `python3 autorizar.py --arquivo RETORNO.txt` — troca o código pelo acesso, esvazia os
   temporários e diz se a renovação automática ficou ligada.
5. `python3 meli.py me` — confirme com ele que o apelido é o da conta dele.

Se a conta for de outro país, o passo 1 aceita o site: `python3 autorizar.py --site MLA`.

**Se a pessoa travar na hora de copiar o código**, existe uma página de socorro:
`https://prometheus.sebemlabs.com.br/`. Ela mostra a URL pronta com botão de copiar, em vez
da página de erro. **Não é o caminho padrão** — o padrão é a `.invalid`, que é o que a
gravação do nivelamento mostra. Para usar a página:

1. a pessoa **acrescenta** essa URL no DevCenter, sem tirar a `.invalid`;
2. `python3 pasta.py --trocar-uri https://prometheus.sebemlabs.com.br/`;
3. refaz a etapa 5.

**Medido em 02/11/2026, e vale dizer para ela:** trocar a URL de retorno **não** derruba a
conexão que já existe — a URL só é usada no momento de autorizar. Já mudar **permissão** no
DevCenter exige autorizar de novo: o escopo fica gravado no acesso, e sem reautorizar a
chamada volta `403 PolicyAgent`.

Qualquer erro aqui: `references/problemas.md`.

### 6. O primeiro painel

```
python3 painel.py
```

Gera `painel.html` na pasta. Nesta etapa ele vem vazio, explicando que nenhuma skill rodou
ainda — e isso é esperado.

**Entregue o link no chat, clicável.** O script imprime uma linha `Abrir: file:///...` —
repasse esse endereço para o usuário, para ele abrir com um clique. Ninguém deve ter de
caçar arquivo dentro de pasta: é atrito gratuito, e numa sala de quarenta pessoas é
atendimento um a um. Faça o mesmo toda vez que gerar o painel de novo.

A partir daqui, qualquer skill `prometheus-*` que ele rodar grava um arquivo na pasta e aparece como
um bloco no painel. **Skill ausente não é erro.**

### 7. Quando não dá para conectar

Se o usuário não conseguir criar a aplicação — limite da conta, dados do titular pendentes de
validação, conta de operador, domínio bloqueado pelo administrador, ou aplicativo de produção
que ele não quer mexer — **não insista e não trave a conversa**. Ele segue no modo
demonstração: as skills rodam com dados preparados, o painel marca isso de forma visível e
permanente, e ele constrói tudo igual. Depois cria a aplicação com calma.

Nunca apresente dado de demonstração como se fosse da conta dele.

### 8. Deixar o pacote se atualizar sozinho

**Faça isto em toda instalação.** Catálogo que não é da Anthropic nasce com a atualização
automática **desligada** — então, sem este passo, nenhuma correção que eu publicar chega
nesta máquina, e a pessoa fica para sempre na versão do dia em que instalou. É o problema
mais silencioso do pacote: nada quebra, ela só fica para trás sem saber.

Veja como está:

```
python3 atualizacao.py
```

Se responder **DESLIGADA**, explique em uma frase — *"o pacote recebe skills novas e
correções; quer que isso chegue sozinho?"* — e **pergunte antes**, porque é uma configuração
do Claude dela, não do pacote. Com o sim:

```
python3 atualizacao.py --ligar
```

Guarda cópia dos arquivos antes de mexer, não toca em nenhuma outra configuração, e vale a
partir da próxima vez que ela abrir o Claude. Se ela disser não, respeite e avise que, nesse
caso, é ela quem precisa pedir a atualização de vez em quando.

**Se ela perguntar isso depois, em qualquer conversa** — "estou atualizado?", "como ligo a
atualização automática?", "por que não chegou a correção?" —, é este mesmo comando. Rode você,
não mande ela digitar.

### 9. Fechar com o recibo

Termine com um resumo curto, que é o que faz a pessoa sentir que está pronto:

- a loja conectada, por **apelido e id** — para ela confirmar que é a conta certa;
- até quando o acesso vale e se a renovação automática está ligada;
- se o pacote vai se atualizar sozinho, conforme a etapa 8;
- a pasta onde tudo mora;
- **o que isto nunca faz:** não altera preço, estoque, anúncio nem pedido, não adere a
  promoção, não responde pergunta, não envia mensagem;
- **onde desligar:** a administração de permissões no painel de aplicações do Mercado Livre.
  Saber revogar é o que gera confiança, mais que qualquer explicação de protocolo.

Lembre também que `credenciais.txt` e `tokens.json` não devem ser apagados nem
compartilhados — e que a pasta não deve ser movida para dentro de um serviço de sincronização.

---

## O que dizer sobre expiração

Não prometa que o acesso nunca cai, porque cai: o refresh token expira depois de 6 meses sem
uso, o aplicativo para se ficar 4 meses sem nenhuma chamada, e a autorização é invalidada se
a pessoa trocar a senha, renovar o Client Secret ou revogar a permissão.

O que se promete é outra coisa: **quando cair, reconectar é um comando** — repetir a etapa 5.

**Diga os três prazos em português, no recibo**, porque é o que tira o medo de "vou ter que
refazer isso toda hora":

- o acesso vale **6 horas** e **se renova sozinho**, sem login — é para isso que serve a
  renovação automática que o `autorizar.py` confirma;
- a renovação vale por **6 meses sem uso**; usando a rotina, ela não expira;
- a aplicação dorme depois de **4 meses sem nenhuma chamada**.

Se o `autorizar.py` disser que a renovação automática **não** ficou ligada, não siga como se
estivesse tudo bem: volte ao DevCenter e confira o interruptor de refresh token e o acesso
offline. Sem isso ela vai ter que refazer a autorização a cada poucas horas, e vai desistir.

## Comandos do dia a dia

| O usuário diz | Rode |
|---|---|
| "está conectado?" | `python3 meli.py check` e `python3 meli.py me` |
| "quero trocar a URL de retorno" | `python3 pasta.py --trocar-uri <url>` |
| "mudei as permissões no DevCenter" | `python3 autorizar.py` — **escopo novo só vale depois de autorizar de novo** |
| "qual conta está conectada?" | `python3 meli.py me` |
| "atualiza o painel" | `python3 painel.py` |
| "reconectar", erro 401 ou 403, `invalid_grant` | etapa 5 de novo (e a 4, se o Secret mudou) |
| "quero ver um dado cru da API" | `python3 meli.py get /algum/path` |
