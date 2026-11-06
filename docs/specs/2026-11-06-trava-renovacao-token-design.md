# Trava de renovacao de token no pacote Elo — desenho [LST-17861]

Frente: a renovacao automatica do token da Shopee nao funcionava, e o
`meli.py` renovava sem exclusao entre processos. Os dois foram consertados com a
mesma peca. Revisao do plano em
`2026-11-06-trava-renovacao-token-gate-codex.md` (veredito BLOQUEIA; os seis
apontamentos entraram).

## Por que isso importa agora

Imersao IA #4, 11–12/11/2026, ~100 vendedores. O bloco do Dia 2 e exatamente o
cenario da corrida: **rotina agendada rodando junto com uso manual, na mesma
pasta**. Antes desta frente, duas execucoes simultaneas liam o mesmo refresh de
uso unico, uma consumia, a outra levava erro — e a conexao morria horas depois,
parecendo falha de rede.

Observado na pratica pelo Marvin na conta de teste da imersao: o Mercado Livre
renovava, a Shopee nao.

## O que estava errado

**Shopee** — a renovacao estava escrita e **desligada**:

- `renovar()` existia e ninguem chamava;
- `expires_at` era gravado e nunca lido;
- `api()` usava o token do disco sem olhar a validade.

Access token de 4 h: passadas as 4 h a conexao morria, com o refresh de 30 dias
intacto no disco.

**Mercado Livre** — renovava certo, mas **sem exclusao entre processos**: o
trecho ler→renovar→gravar podia acontecer duas vezes ao mesmo tempo na mesma
pasta.

**Os dois** — `salvar_tokens` aceitava refresh vazio como `""` e **inventava** a
validade quando ela nao vinha. Uma resposta incompleta trocava uma conexao que
renova por uma que nao renova, em silencio.

## O desenho

### 1. A trava (`seguro.trava`)

Exclusao **entre processos** para o trecho ler→renovar→gravar. Tres decisoes que
parecem detalhe e nao sao (todas vindas do gate):

- **arquivo proprio**, nunca o arquivo de segredo: o segredo e substituido por
  `os.replace` na gravacao atomica, e travar o proprio arquivo perderia a trava
  junto com o inode, no meio do trecho protegido;
- **nunca apagada** ao liberar: apagar abre janela para outro processo criar um
  inode novo e entrar junto;
- **sem vencimento**: vencer enquanto o primeiro ainda espera a resposta do
  provedor e o mesmo que nao ter trava.

`fcntl.flock` no POSIX, `msvcrt.locking` em regiao de posicao e tamanho
constantes no Windows. Reentrante no mesmo processo, porque `renovar()` e o
caminho forcado passam pela mesma trava. Timeout levanta `TravaOcupada` com
instrucao — **nunca** segue sem protecao.

Quem espera e entra depois **rele** a credencial: normalmente ja encontra o par
renovado por quem estava dentro.

### 2. Nao consumir o refresh sem poder guardar o par novo

O conserto nao pode piorar o que estava ruim. Hoje a Shopee morre em 4 h mas o
refresh fica intacto; com a renovacao ligada, o refresh passa a ser consumido.

- `seguro.pode_gravar` confere a pasta **antes** de chamar o provedor, sem tocar
  no arquivo atual;
- `seguro.gravar_insistindo` insiste na **gravacao** (o par ja existe, perde-lo
  mata a conexao) e **nunca** na chamada (refresh e de uso unico);
- `fsync` antes do `replace`: substituicao atomica garante que o destino nunca
  fica truncado, mas nao garante que o conteudo novo chegou ao disco.

### 3. Validar o par antes de substituir (`_validar_par`)

Token de acesso nao vazio, prazo numerico positivo, e refresh nao vazio. O
refresh so e dispensado na **autorizacao inicial**, onde uma conta sem acesso
continuo ainda da leitura por algumas horas e recusar deixaria a pessoa sem nada
— e onde o `autorizar.py` / `autorizar_shopee.py` ja avisa.

### 4. Presenca nao e prova

"Veio o refresh" significa configuracao disponivel. **Renovacao comprovada**
exige chamada concluida, corpo validado e par gravado.

- `check` (somente leitura) mostra o estado da renovacao;
- `renovar` **prova**, pelo mesmo caminho protegido, e e o que fecha a janela
  perigosa: hoje a primeira renovacao de verdade acontece horas depois da
  conexao. Um Client Secret ou Partner Key colado com um espaco a mais so falha
  ali. Rodado no fim do Dia 1, com monitores na sala, isso vira problema de Dia
  1 em vez de problema de Dia 2.
- Falha em rotina agendada: saida nao zero, instrucao acionavel, sem traceback e
  sem segredo.

## O que NAO entrou, de proposito

**Marcador de tentativa antes da chamada.** O gate sugeriu; nao entrou. Se o
processo morrer antes de enviar, isso manda o vendedor reconectar a toa, e o
desfecho final e o mesmo sem ele (a renovacao seguinte falha e pede reconexao).
Decisao registrada, nao esquecimento.

## Limites conhecidos

- **Windows nao foi exercitado.** `fcntl` e `msvcrt` sao caminhos distintos; a
  implementacao segue a regra da regiao constante, mas os testes rodaram no
  macOS.
- Nao existe recuperacao automatica para todo desfecho incerto sem suporte do
  provedor. O que o desenho garante: exclusao, nao repetir refresh incerto,
  proteger o par recebido e dizer com clareza quando precisa reautorizar.
- O pacote segue **somente leitura**: `api()` recusa qualquer metodo que nao
  seja GET, antes de tocar em token, arquivo ou rede — e isso continua testado.

## Provas

Suite do pacote: **418 passando**. Entre os testes novos:

- exclusao entre **dois processos de verdade** (o filho sinaliza quando entra na
  trava, em vez de o teste supor por tempo);
- trava em arquivo separado, nao apagada, liberada mesmo com excecao, reentrante,
  e timeout que nao segue sem protecao;
- Shopee renovando quando o prazo acabou, nao renovando quando ainda vale, e
  pedindo reautorizacao sem chamar a API quando nao ha refresh;
- recusa de resposta incompleta sem substituir a credencial boa, nos dois canais;
- renovacao que nao repete a chamada ao provedor;
- `pode_gravar` falso impede consumir o refresh;
- gravacao que insiste sem repetir a chamada;
- `check` e `renovar` sem imprimir credencial, com saida nao zero na falha.
