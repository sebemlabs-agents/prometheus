# Mudanças do prometheus

> ## ⚠️ REGRA DE PUBLICAÇÃO — leia antes de dar push
>
> **O pacote fixa `version` no `plugin.json`. Todo push publicado tem que subir esse número.**
>
> O Claude só entrega uma cópia nova quando a versão **muda**. Se o número ficar parado, o
> aluno não recebe nada — nem skill nova, nem correção de segurança — e o botão "Atualizar"
> dele fica cinza, mesmo com o GitHub vários commits à frente.
>
> **Isso já aconteceu neste pacote:** ficou em `0.1.0` por cinco mudanças seguidas.
>
> Por um tempo a versão foi omitida de propósito, justamente para fugir desse risco — sem
> `version`, o Claude usa o commit e tudo chega sozinho. Em 22/10/2026 o Marvin decidiu o
> contrário, para o aluno conseguir **ver na tela** em que versão está. O preço dessa escolha
> é esta regra, e ela não é opcional.
>
> Checklist do release:
> 1. subir `version` em `.claude-plugin/plugin.json` **e** `.codex-plugin/plugin.json`
> 2. **nunca** declarar `version` no `marketplace.json` — declarar nos dois faz o Claude usar
>    o do `plugin.json` sem avisar, e o `claude plugin validate` acusa a divergência
> 3. `claude plugin validate .`
> 4. anotar a mudança aqui embaixo
> 5. publicar pelo Cypher Guard

## 1.8.3 — 7 de novembro de 2026

**As descrições das três skills de conexão agora têm cabeçalhos YAML válidos.**

Meli, Olist e Shopee tinham dois-pontos no texto da descrição sem as aspas exigidas
pelo formato. Um leitor YAML estrito rejeitava essas três skills, embora a validação
do catálogo pelo Claude Code passasse. As descrições agora estão entre aspas, sem
mudar o texto nem as instruções das skills.

Um teste novo verifica os cabeçalhos reais das nove skills para evitar a repetição.
Sua dependência de YAML é exclusiva dos testes; o participante não precisa instalar
nada a mais. A correção do verificador de atualizações da versão 1.8.2 foi preservada.

O defeito de formato foi comprovado e corrigido. A relação com a mensagem de falha
de sincronização na interface ainda precisa ser validada em uma conta afetada.

## 1.8.2 — 6 de novembro de 2026

**Quem instalou pelo aplicativo ouvia que não tinha instalado nada.**

O `atualizacao.py` só sabia olhar o registro do terminal (`~/.claude/settings.json` e
`known_marketplaces.json`). Quem instalou pela tela do Claude — vitrine da conta ou envio de
`.zip` — tem o pacote registrado em outro lugar: `~/.claude/plugins/synced/<conta>/`, com um
`.marketplaces.json` e o pacote dentro de uma pasta de **UUID**, onde o nome de verdade só
aparece no `plugin.json` de dentro.

Resultado: o script respondia **"O pacote prometheus não está instalado nesta máquina"** para
quem estava com ele instalado e funcionando. No meio de um evento, essa frase manda a pessoa
desinstalar e instalar de novo o que já estava certo.

Agora o script enxerga os dois caminhos:

- **terminal:** continua igual — lê e liga sozinho.
- **aplicativo:** reconhece, diz que quem controla é a tela e aponta o caminho exato
  (Configurações → Plugins → prometheus → "Sincronizar automaticamente"). Não existe arquivo
  local de `autoUpdate` nesse caminho; prometer que liga seria mentira.

Quem tem os dois recebe a resposta do terminal, que é a que o script consegue mudar.

Além disso, as três saídas agora dizem **em que versão a pessoa está** — lido do
`installed_plugins.json`, da cópia da vitrine ou da pasta do aplicativo, nessa ordem. Era a
informação que faltava para saber se uma correção publicada chegou.

Nada mudou nas skills nem na conexão de conta.

## 1.8.1 — 6 de novembro de 2026

**A lista de plugins voltou a ter um pacote só: o de leitura.**

O `prometheus-acoes` — o pacote que **muda coisa** na conta — saiu da vitrine do marketplace.
Ele continua existindo no repositório e volta para a lista depois da imersão de 11 e 12 de
novembro.

Por que: com os dois lado a lado, quem abria a lista via o de Ações marcado como novidade e
instalava ele achando que era o de conexão — ficando **sem** as skills de conectar a conta, que
são o que importa. Numa sala com cem pessoas, isso é erro garantido, e o texto do próprio
pacote já dizia que instalar as ações **é uma decisão** — decisão não pode ser um clique a mais
numa lista durante um evento.

Nada mudou no pacote de leitura além do número da versão. E a trava do pacote de ações nunca
dependeu disso: ele recusa qualquer escrita antes de sair da máquina quando falta a permissão
daquela superfície — por isso ninguém que instalou por engano conseguiu alterar nada numa conta
autorizada só para leitura.

## 1.8.0 — 6 de novembro de 2026

**A conexão da Shopee parava de funcionar em quatro horas, e agora não para mais.**

A renovação automática dela estava escrita no pacote e **nunca era chamada**. O acesso da Shopee
vale 4 horas; passado esse tempo a conexão simplesmente morria, com a chave de renovação — que vale
30 dias — intacta e sem uso. Quem conectou a Shopee e voltou no dia seguinte achava que tinha
perdido a conexão.

**E as duas conexões ganharam uma trava.** A chave de renovação do Mercado Livre e a da Shopee são
de **uso único**: cada renovação devolve uma nova e invalida a anterior. Se duas coisas renovam ao
mesmo tempo na mesma pasta — uma rotina agendada e você mexendo à mão, por exemplo — as duas usam a
mesma chave, uma funciona e a outra morre. O sintoma aparece horas depois e parece queda de
internet. Agora a renovação acontece uma de cada vez, e quem chega depois aproveita o resultado de
quem chegou primeiro, em vez de tentar de novo.

**Dá para provar que a renovação funciona, sem esperar horas:**

```
python3 meli.py renovar
python3 shopee.py renovar
```

Isso existe porque "a chave de renovação chegou" **não** quer dizer que a renovação funciona. Se o
Client Secret ou a Partner Key foi colada com um espaço a mais, a chave fica lá, bonita, e só falha
na primeira renovação de verdade — horas depois, quando você não está olhando. O comando faz a
renovação na hora e responde `renovacao funcionou`. O `check` dos dois canais também passou a
mostrar o estado (`renovacao automatica: ligada`).

**Resposta incompleta não derruba mais uma conexão boa.** O pacote aceitava uma resposta sem a chave
de renovação e inventava o prazo de validade. Com isso, uma resposta pela metade trocava uma conexão
que se renova por uma que não se renova, sem avisar ninguém. Agora ele confere antes de guardar: se a
resposta não serve, **não grava nada** e a conexão atual continua valendo.

**E o pacote não queima a chave sem ter onde guardar o resultado.** Antes de renovar, ele confere se
consegue gravar na pasta. Se não conseguir, não renova e diz o que fazer — porque renovar e perder o
resultado derrubaria o acesso de verdade, em vez de ele apenas expirar.

Nada disso muda o que você já usa: leitura com acesso no prazo segue exatamente como era, sem passar
por trava nenhuma. O arquivo da conexão não mudou de formato, então a versão anterior e esta leem o
mesmo arquivo.

**Continua valendo o principal: o pacote só lê.** Qualquer tentativa de alterar algo na conta é
recusada antes de sair do computador.

Em pasta de rede ou sistema que não sabe travar arquivo, a trava se desliga sozinha avisando, e o
pacote funciona como antes dela existir. No Windows o caminho da trava é outro e ainda não foi
exercitado numa máquina Windows.

## prometheus-acoes 1.0.0 — 2 de novembro de 2026

**Um segundo pacote, e ele muda coisa na conta.** `prometheus` continua só leitura. Quem
quiser que o pacote aja instala `prometheus-acoes` — e instalar é uma decisão, não um detalhe.

Duas ações, uma por vez, sempre num anúncio só:

- **`prometheus-aderir-promocao`** — adere um anúncio a uma campanha, e sai dela. Muda o
  **preço de venda**.
- **`prometheus-responder-pergunta`** — publica um **texto público** na página do anúncio.

**A trava do pacote de leitura não foi tocada.** `meli.py` continua recusando qualquer coisa
que não seja consulta, antes de sair da máquina, e nenhum leitor importa o módulo de escrita —
teste garante. Os scripts de escrita **não moram** no pacote de leitura: quem instalou só o
`prometheus` não consegue escrever nem copiando arquivo.

O que a porta de escrita faz de diferente de um `urlopen`:

- **lista fechada de ações**, cada uma com o seu método, o padrão de caminho que aceita e o
  **nome exato** do escopo granular de que precisa. Ter "alguma" permissão de escrita não serve:
  `ads:/read-write` não autoriza mexer em promoção;
- **sem redirecionamento** (`seguro.abrir`): seguir um 302 entregaria o token ao destino de
  outra pessoa;
- **recibo antes do envio**, em `acoes.txt`. Não deu para gravar, a ação não acontece;
- **escrita não repete.** Uma exceção, e só ela: `OFFER_SIBLING_CREATION_IN_PROCESS`, em que o
  próprio Meli diz que não aplicou — aí espera 20s, **relê** e repete uma vez;
- **resposta perdida tranca o anúncio** até alguém reconciliar por leitura. Repetir às cegas é
  o jeito de aplicar duas vezes.

Conferir vem antes de fazer, e a conferência **vence**: o código vale 10 minutos, uma vez, só
naquela conta — e o `--fazer` **relê o estado vivo e compara** antes de enviar.

Três coisas que o dado real ensinou e que estão no código:

- **o preço de hoje vem do anúncio, não do candidato.** No candidato da promoção, `price` é o
  preço *na campanha*; no anúncio, `price` é o *praticado*. Mesmo nome, significados invertidos;
- **`201` não é prova.** A ferramenta espera ~15s e relê, conferindo estado **e** preço. `200`
  numa saída com `errors` no corpo não é saída, e `404` é resultado a reconciliar;
- **só `SELLER_CAMPAIGN`** tem adesão provada aqui. Outro tipo é recusado **com nome**. Sair
  funciona em qualquer tipo — o caminho de volta não fica fechado.

Spec, com a matriz de 30 garantias: `elo/docs/imersao-v2/spec-escrita.md`.

## 1.7.0 — 2 de novembro de 2026

**Agora dá para trocar a URL de retorno depois, sem refazer a pasta.**

```
python3 pasta.py --trocar-uri https://seu-endereco/
```

Antes não havia caminho para isso: o arquivo de credenciais só recebia a URL quando era
criado, e o assistente não pode abrir esse arquivo. Quem errou o endereço, quem quer usar
outra página de retorno ou quem mexeu nas permissões ficava sem saída. O comando mexe **só
naquela linha** — o resto do arquivo, que tem segredo, não é tocado — e grava com a mesma
proteção de sempre.

**O `check` passou a mostrar a URL de retorno**, em vez de dizer só "preenchido". Ela não é
segredo — viaja na barra do navegador — e **o erro número um desta conexão é ela não bater
com a cadastrada no DevCenter**. Não dá para comparar o que não se vê. App ID e Client Secret
continuam invisíveis.

**Duas coisas que a gente mediu e que o pacote passou a dizer com todas as letras:**

- **Trocar a URL de retorno não derruba a conexão.** Ela só é usada no momento de autorizar.
- **Mudar permissão no DevCenter exige autorizar de novo.** O escopo fica gravado no acesso;
  sem reautorizar, a chamada volta `403` sem explicar por quê. Isso foi medido nas duas
  direções, com a mesma chamada antes e depois.

## 1.6.2 — 2 de novembro de 2026

**Só texto: o pacote passou a dizer o que é.**

> Prometeu roubou o fogo dos deuses e entregou aos homens. Aqui o fogo está com os robôs: os
> seus dados de Mercado Livre, Shopee e Olist, do outro lado da API, que hoje você só enxerga
> pelo painel de quem fez o painel.

A descrição antiga listava função. Esta diz por que o pacote existe — e deixa escrito o que
vem depois: **ações aprovadas por você, rotinas e agentes.** Quando chegarem, vêm marcadas; as
skills de leitura nunca escrevem.

Nenhuma mudança de comportamento, nenhum teste alterado.

## 1.6.1 — 2 de novembro de 2026

**A janela padrão das vendas passou de 60 para 30 dias, e o teto de leitura dobrou.**

Achado num ensaio cronometrado contra uma conta de verdade: com 60 dias, uma conta ativa
estourava o teto de páginas. O resultado vinha marcado como incompleto — corretamente — e os
dois melhores números, **comissão e ticket médio, desapareciam**, porque viravam subtotal e
subtotal não é apresentado como total.

Ou seja: a primeira coisa que um vendedor ativo veria ao rodar a skill era um faturamento
parcial e uma comissão vazia. O programa estava certo; **o padrão é que estava errado.**

Na mesma conta, com o padrão novo: 717 pedidos, nada faltando, comissão fechando em cima.
Quem quiser mais janela continua pedindo com `--janela`.

**Também:** um alerta de anúncio que aparecia na conta real e o pacote não conhecia
(`forbidden`, bloqueio do Mercado Livre) entrou na tradução — antes ele deixava o contador de
alertas vazio.

## 1.6.0 — 2 de novembro de 2026

**Skill nova: `prometheus-anuncios`.** A pergunta que o painel do Mercado Livre não responde
por anúncio: **de quem olhou, quantos compraram.**

Lá a conversão é da conta inteira. Aqui é anúncio a anúncio — e é assim que aparece o anúncio
que recebe muita visita e vende pouco. Quando um campeão de faturamento converte abaixo da
mediana da própria loja, **o problema não é tráfego**: é preço, foto, título, frete ou
reputação.

**Ela olha só os que vendem, e diz quantos ficaram de fora.** Uma conta ativa tem milhares de
anúncios e as visitas custam uma chamada por anúncio — varrer tudo não cabe numa coleta que
você roda ao vivo. Então ela pega os que mais faturaram na janela, que são os que doem quando
convertem mal. `--quantos` aumenta a lista.

**A janela vem do arquivo de pedidos**, não é escolhida aqui — e o programa **recusa rodar**
se esse arquivo for de outra conta, de demonstração, ou de um dia que não seja hoje. Dividir
venda de um período por visita de outro dá um número que não significa nada.

**Visita ausente não vira conversão zero.** Zero quer dizer que gente olhou e ninguém
comprou; ausência quer dizer que não deu para saber.

**O que ela não sabe:** se a venda é lucrativa. Conversão alta com margem negativa é pior que
conversão baixa. Cruze com a planilha ou com a Olist antes de baixar preço.

## 1.5.0 — 2 de novembro de 2026

**Skill nova: `prometheus-devolucoes`.** As reclamações abertas da sua conta — por causa, por
etapa, e quais estão esperando você responder. Em mediação, silêncio do vendedor costuma
decidir a favor do comprador, então esse é o número que abre o bloco.

**A armadilha que ela resolve.** A API manda, junto do motivo, um campo que parece ser a
descrição e não é: ele traz a resposta do comprador a uma pergunta anterior. **Quatro causas
completamente diferentes compartilham a frase "Chegou bem"** — produto quebrado, produto que
não funciona, faltaram acessórios e faltou item. Quem agrupa por ali vê um balde que não diz
nada e perde justamente a informação que permite consertar. O pacote usa a causa real.

Cada reclamação também é marcada como problema de **produto** ou de **entrega**. São consertos
diferentes: um é fornecedor, embalagem e descrição do anúncio; o outro é logística e prazo.

**O texto das mensagens não é gravado, de propósito.** O arquivo vira painel, e painel se
compartilha com a equipe — mensagem de comprador num link compartilhado é dado pessoal
exposto. O que fica é o sinal: quantas mensagens, **quem falou por último** — o comprador,
você, ou o mediador do Mercado Livre —, há quantos dias, e se a conversa tem anexo. Para ler
o que o comprador escreveu, peça a conversa daquela reclamação e ela aparece na tela, sem
ser gravada.

**O que esta skill não sabe:** a sua taxa de reclamação. Ela exige o histórico fechado
inteiro, que numa conta ativa passa de milhares de registros — pesado demais para uma coleta
ao vivo. O que está aqui é o que está **aberto agora**.

**Regra que ficou mais dura em todo o pacote:** valor que veio da API e que o programa não
reconhece **não é publicado**. Fica vazio, com aviso. Um campo que deveria trazer um papel
pode trazer um nome, e o arquivo vira tela compartilhada.

## 1.4.0 — 2 de novembro de 2026

**A fila de promoções passa a dizer a verdade sobre o que está dentro.** A skill existia desde
a 1.0, mas nunca tinha sido chamada contra a API de verdade. Contra uma conta real, quatro
coisas apareceram de uma vez:

- **Ela parava sem dizer a causa.** Pedia 100 anúncios por página e o Mercado Livre recusa
  acima de 50. Qualquer pessoa que rodasse a skill via só "erro 400".
- **Elegível e aderido estavam somados no mesmo número.** O Mercado Livre chama de
  *elegível* o anúncio que **pode** entrar na campanha, e de *aderido* o que **já está
  dentro**. Somar os dois e escrever "38 anúncios na promoção" faz você achar que aderiu
  quando não aderiu — e a campanha termina com você de fora. Agora são dois números
  separados, sempre, e a tela usa as duas palavras.
- **Campanha encerrada podia aparecer como oportunidade**, porque qualquer estado
  desconhecido caía no balde de "elegível".
- **Campanha sem anúncio virava lacuna em vez de zero.**

**Novo: quanto do desconto o Mercado Livre banca.** Cada campanha traz a mediana do que o
Meli subsidia e do que sai do seu bolso. É o que decide se vale aderir — campanha com rebate
protege margem e ainda dá exposição. Mediana, não média, para um anúncio fora da curva não
deslocar o número.

**O que esta skill continua não sabendo:** se o desconto cabe na sua margem. A API não tem o
seu custo por SKU. Peça o cruzamento com a planilha ou com a Olist.

Campanha grande demais para contar inteira vem **vazia com a explicação**, nunca com um
número parcial.

## 1.3.0 — 31 de outubro de 2026

**Skill nova: `prometheus-pedidos`.** Quanto a loja vendeu na janela, os últimos pedidos, e a
comissão que veio em cada item. É o primeiro leitor do pacote no desenho novo: **a skill abre
a torneira, o Claude cruza, o painel mostra.**

Validada contra conta real antes de entrar — e foi a validação que ensinou o que importa:

- **A comissão do pedido é por unidade, não pela linha.** Medido: o mesmo anúncio vendido em
  quantidade 1, 2, 6, 10 e 15 manteve a tarifa praticamente igual. Tratar como total da linha
  dividiria a comissão pela quantidade, e o número continuaria plausível — o pior tipo de
  erro. Na janela inteira a comissão fecha em 12,4% do faturamento.
- **O número diz como foi contado.** Junto dos valores vai a regra: situação contada, qual
  data foi usada, o intervalo, e a unidade. O painel do Mercado Livre usa outro recorte e
  costuma dar um número maior — com a regra escrita, dá para comparar em vez de discutir.
- **Faturamento e desembolso do comprador são números diferentes**, e aparecem separados.
- **Nada do comprador é gravado.** O arquivo guarda só o que o contrato pede.

**Correção que vale para todas as skills:** o limite de chamadas do Mercado Livre
derrubava a coleta no meio. O limite é da **conta**, não do aplicativo — quem tem outra
integração rodando esbarra nele sem ter feito nada. Agora o pacote espera e tenta de novo
sozinho, respeitando o tempo que o servidor pedir, e nunca insiste em erro de autorização.

**O que este leitor nunca apresenta como total:** coleta que não veio inteira, soma com
moedas diferentes, ou agregado com parcela faltando. Nesses casos o número vem vazio, com a
explicação do lado — porque subtotal com cara de total é o jeito mais caro de errar.

## 1.2.0 — 31 de outubro de 2026

**Saem quatro skills.** O pacote passa a entregar só o que foi provado contra servidor real.
A decisão é anterior ao código: **a skill abre a torneira, o Claude cruza, o painel mostra.**
Uma skill que calcula margem, julga promoção ou escreve texto está opinando dentro do Python,
onde ninguém confere — e o contrato de dados já dizia isso desde o começo: *a skill coleta e
grava, o painel lê e formata.*

- **`prometheus-criativos` sai.** Não lia dado nenhum: era um prompt embrulhado em Python. O
  Claude faz isso melhor com o produto real na mão, sem skill no meio.
- **`prometheus-margem` sai.** Era o cruzamento de dois arquivos que já existem — preço do
  anúncio e custo da planilha ou da Olist. Cruzar é trabalho do Claude. **O custo continua
  sendo importado normalmente** pela conexão da Olist e pela planilha; só a conta saiu de
  dentro do pacote.
- **`prometheus-caixa` sai, e volta.** O calendário de liberação é informação séria demais
  para ir sem validação contra a API de verdade. Volta como `prometheus-recebiveis`, leitor
  puro, depois de conferido numa conta real.
- **`prometheus-spec` sai.** Escrevia um plano para subir o painel que ninguém executava.

**Fica:** as três conexões (Mercado Livre, Shopee e Olist), a leitura de planilha e o painel.
São as que atravessaram em máquina limpa contra servidor real.

**Vem a seguir**, cada uma validada com chamada de verdade antes de entrar: pedidos (com a
comissão real item por item), promoções, devoluções, anúncios e visitas — a conversão que o
vendedor não vê no painel do Mercado Livre.

Nada do que você já conectou muda: credencial, pasta e tokens continuam onde estavam.

## 1.1.1 — 22 de outubro de 2026

Saiu de um ensaio da conexão Shopee feito na véspera da gravação, com conta e
aplicativo reais. Três coisas que a documentação não contava:

- **A barra de retorno pode vir cheia de `%`, e está certa.** Aplicativo com login
  redireciona a visita sem sessão e leva a URL original dentro de um parâmetro,
  codificada. O código está lá, um nível abaixo — o pacote passou a procurar nos dois
  níveis. Antes ele dizia "não achei o code" para quem tinha autorizado certinho, e a
  pessoa não tinha como adivinhar o motivo. A skill agora manda o assistente **não**
  chamar isso de erro, **não** tentar consertar o endereço e **não** pedir nova
  autorização: o código é de uso único, e refazer gasta o que estava bom.
- **A conferência de retorno passou a comparar domínio, não caminho.** Exigir o caminho
  idêntico fazia o pacote recusar retorno legítimo de qualquer aplicativo que redireciona.
  A proteção que importa é o domínio.
- **A Shopee avisa com clareza quando o endereço não bate com o console.** A skill dizia o
  contrário, que ela recusava em silêncio. Corrigido, com o que fazer.

## 1.1.0 — 22 de outubro de 2026

- **Conexão com a Shopee.** Mesmo molde do Mercado Livre, só leitura. O endereço de retorno
  tem que ser um domínio HTTPS de verdade — a Shopee recusa `.invalid`, que é o truque do
  Meli, e o pacote avisa isso antes de a pessoa abrir o formulário.
- **Conexão com a Olist (Tiny).** Importa o **custo** dos produtos, que é o dado que nenhum
  marketplace entrega e sem o qual a margem não fecha.
- **Quem instalou antes recebe os canais novos.** O `credenciais.txt` que já existia passa a
  ganhar as linhas novas sozinho, sem perder nem reordenar o que a pessoa já preencheu.
- **Nove correções de segurança**, de uma revisão cross-vendor que bloqueou a entrega três
  vezes. As duas que mais importam: a Shopee tinha um POST genérico assinado, que furava a
  promessa de somente-leitura; e o arquivo de token nascia aberto e só era fechado depois,
  dando uma janela em que outro usuário da máquina conseguia ler. Três delas valiam também
  para a conexão do Mercado Livre que já estava nas máquinas.
- **Os nomes das telas do DevCenter** agora são os que aparecem de verdade — "URIs de
  redirect", "Permissões", "PKCE necessário" —, conferidos em vídeo.

## Outubro de 2026

- **Funciona no Windows.** A skill descobre como o Python se chama na máquina (`python3`,
  `py -3`, `python`) antes do primeiro comando; a checagem de rede deixou de usar `curl` e
  `grep`, que não existem lá; e o guia avisa que `Documentos` costuma ficar dentro do
  OneDrive, onde o pacote recusa gravar.
- **Skill nova: `prometheus-criativos`.** Produto cru vira título, descrição, benefícios e objeções.
  Não precisa de conexão nem de chave de API.
- **A tabela de problemas ficou alcançável a qualquer momento**, não só durante a instalação.
- **Descrição única e verdadeira** nos três manifestos: descreve o que o pacote faz hoje, em
  vez de prometer skills que ainda não existem.
- **Guias com as duas telas de instalação** do aplicativo, e sem pedir checagem de Python
  antes de começar.

## O começo

- Conexão só-leitura com o Mercado Livre (`prometheus-conectar-meli`), painel local (`prometheus-painel`),
  contrato de dados e 43 testes.

## 19 de outubro, tarde

- **`prometheus-promocoes`**: a fila do que termina na janela, com anúncios dentro, desconto mínimo
  e o que já foi aderido. Recorte do radar que roda na operação, trazido para o contrato.
- **`prometheus-caixa`**: o calendário de liberação das vendas — quanto cai e quando. Não é o saldo
  da carteira, e a skill diz isso antes de mostrar número.
- **`prometheus-spec`**: lê o painel local e escreve o plano para subir para Supabase e Vercel, com
  o esquema tirado dos dados reais, segurança de linha ligada e nenhuma política — a tabela
  nasce trancada de propósito.
- **Correção silenciosa que teria estragado o primeiro teste:** skill nova chega pela
  atualização, mas o script dela não aparece sozinho na pasta de quem já instalou. As skills
  agora conferem e copiam de `${CLAUDE_PLUGIN_ROOT}/scripts/` antes do primeiro comando.
- **`prometheus-planilha`**: lê qualquer CSV ou XLSX — exportação de marketplace, relatório de ERP,
  custo feito à mão — descreve as colunas e deixa o mapeamento com quem entende a planilha.
  Sem formato obrigatório, sem dependência instalada. O contrato ganha a origem `export`, e
  com ela `capturado_em`: dado de arquivo tem duas idades, e o painel mostra as duas.
- **`prometheus-margem`**: a dor número um declarada nas mentorias. Preço menos comissão, frete,
  custo e imposto. Componente ausente não vira zero — a linha fica sem margem e diz qual
  faltou; zero declarado é diferente de vazio. Média ponderada pelo preço, e os negativos
  aparecem primeiro.
- **Pendência resolvida:** não existe limite de uma aplicação por titular no DevCenter.
  Verificado em conta de vendedor brasileira com três aplicações simultâneas. Quem já tem
  aplicação de ERP passa a ter o caminho seguro como primeira opção: criar uma nova, sem
  encostar na que sustenta a integração em produção.
