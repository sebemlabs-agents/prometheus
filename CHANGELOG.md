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
