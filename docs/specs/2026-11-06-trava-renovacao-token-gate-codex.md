# Gate do plano — trava de renovacao de token no pacote Elo [LST-17861]

Revisor: Codex (cross-vendor), `codex exec --sandbox read-only`, com o
`cypher-checklist.md`, os gotchas da superficie e o codigo relevante anexados ao
pedido. Data: 05/11/2026, noite. Veredito: **BLOQUEIA** — e os apontamentos
mudaram o desenho em seis pontos.

## O defeito que originou a frente, medido

`scripts/shopee.py`:

- `renovar(partner_key)` existia, completa e documentada — e **nenhum chamador
  existia**. Grep em `scripts/*.py`, `acoes/scripts/*.py` e nas `SKILL.md`: nada.
- `salvar_tokens` **gravava** `expires_at`, e essa era a **unica** ocorrencia de
  `expires_at` no arquivo: ninguem lia.
- `api()` fazia `t = _carregar()` e usava `t["access_token"]` direto.

Resultado: o access_token da Shopee dura 4 horas (`expire_in: 14400`); passadas
as 4h a conexao morria e o vendedor tinha de reautorizar, com o refresh_token de
30 dias intacto no disco. No `meli.py`, ao lado, toda chamada passa por
`get_access_token()`, que confere o prazo e renova.

## O que o gate mudou no plano

| # | Apontamento | O que entrou no codigo |
|---|---|---|
| 1 | a trava e o minimo defensavel, em arquivo **proprio** (o segredo e substituido por `os.replace`; travar o proprio arquivo perde a trava junto com o inode), **permanente** (apagar abre janela) e **sem vencimento** (vencer durante o HTTP e o mesmo que nao ter trava), cobrindo reler→decidir→chamar→validar→gravar, com **todos** os escritores participando | `seguro.trava` (`fcntl.flock` no POSIX, `msvcrt.locking` em regiao constante no Windows, reentrante no mesmo processo), usada por `meli.get_access_token`, `shopee.credencial_valida` e `shopee.renovar` |
| 2 | comparar o refresh so e condicional de verdade **sob a trava**; quem espera deve **reler** e normalmente aproveita o par recem-renovado | releitura dentro da trava nos dois clientes, com teste proprio |
| 3 | POST de desfecho incerto **nao pode** ser repetido automaticamente | uma tentativa por renovacao, testado nos dois |
| 4 | o conserto pode **piorar**: hoje o refresh fica intacto, depois passa a ser consumido e pode se perder por falha de disco | `seguro.pode_gravar` antes de consumir o refresh, `seguro.gravar_insistindo` (insiste na **gravacao**, nunca na chamada) e `fsync` antes do `replace` |
| 5 | `salvar_tokens` aceitava refresh vazio como `""` e **inventava** a validade padrao: resposta incompleta trocava credencial boa por uma sem renovacao, calada | `_validar_par` nos dois clientes, com `exigir_refresh=False` **somente** na autorizacao inicial (loja sem acesso continuo ainda da leitura por algumas horas) |
| 6 | o diagnostico deve distinguir **presenca** de **prova**; `check` somente leitura; falha em rotina agendada com saida nao zero e sem traceback | `estado_da_renovacao()` nos dois, `meli.py renovar` e `shopee.py renovar`, que provam de verdade pelo mesmo caminho protegido |

Tambem apontado e atendido: em `api()`, access_token e identificacao da loja tem
de sair da **mesma leitura coerente** — `credencial_valida()` devolve o
dicionario inteiro, em vez de so o token novo com `shop_id` de uma leitura
anterior.

## Decisao consciente: o marcador de tentativa NAO entrou

O gate sugeriu gravar um marcador protegido **antes** de cada chamada, para a
execucao seguinte saber que uma renovacao ficou pelo meio e interromper novas
renovacoes daquele par.

Nao entrou. Se o processo morrer **antes** de enviar, o marcador manda o vendedor
reconectar a toa — e o desfecho final e o mesmo sem ele: a renovacao seguinte
falha com `invalid_grant` e pede reconexao. Para maquina de vendedor, com ~100
pessoas numa imersao, o falso alarme custa mais do que o diagnostico ganha.
Registrado como **escolha**, nao como esquecimento.

## Correcao que o gate fez numa afirmacao da spec

A spec dizia que uma renovacao rejeitada poderia gravar um "par morto". Nao
procede: `salvar_tokens` so roda se `_post` devolver. A corrida basta para causar
estrago, mas aquele desfecho especifico foi afirmado sem prova.

## Trechos da revisao, como voltou

> **O fio proposto resolve a expiracao, mas ainda nao e suficiente para
> publicar.** Com execucoes simultaneas previstas, eu bloquearia a versao sem
> exclusao entre processos e sem tratamento explicito do desfecho incerto da
> renovacao.

> Use um arquivo de lock separado, estavel, por arquivo de credenciais. **Nao
> trave o proprio JSON**, pois ele e substituido na gravacao atomica. Nao apague
> o arquivo de lock ao liberar e nao implemente vencimento que permita outro
> processo entrar enquanto o primeiro ainda faz HTTP.

> **Todos os escritores precisam participar:** renovacao automatica, comando
> forcado e autorizacao inicial. Colocar lock somente em `get_access_token()`
> deixa `renovar()` direto como desvio.

> Hoje o refresh fica sem uso. Com a alteracao, ele pode ser consumido e o novo
> par desaparecer por falha de disco, permissao ou encerramento do processo.
> **Esse risco existe mesmo com lock perfeito.**

> `salvar_tokens` aceita refresh ausente como `""` e inventa validade padrao. Na
> renovacao, uma resposta incompleta pode substituir a credencial existente por
> uma conexao sem renovacao.

> "Refresh presente" significa configuracao disponivel. "Renovacao comprovada"
> exige POST concluido, corpo validado, par persistido e releitura bem-sucedida.

> Pela checklist, a superficie tocada e **credencial/secret e armazenamento
> local**. (…) A mesma rede da imersao nao cria essa corrida: o fator relevante e
> compartilhar o arquivo local. O risco existente no Meli merece correcao
> propria, mas nao justifica reproduzi-lo.

Veredito: `VEREDITO: BLOQUEIA`.

## Limite desta revisao

O Codex analisou o plano e os trechos de codigo, **sem executar testes**. As
provas de execucao sao separadas: suite do pacote **418 passando**, incluindo
exclusao entre **dois processos de verdade** — e o teste espera o processo filho
**sinalizar** que entrou na trava, em vez de supor por tempo (a primeira versao
do teste falhava de forma intermitente justamente por isso).

## Pendencia que o gate levantou e ficou aberta

Teste real nos **dois sistemas operacionais**: `fcntl` e `msvcrt` sao caminhos
distintos, e no Windows a regiao travada precisa de posicao e tamanho constantes
(esta implementado assim, mas so foi exercitado no macOS).
