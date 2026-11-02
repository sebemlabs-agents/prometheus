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
