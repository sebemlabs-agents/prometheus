# prometheus

Pacote de skills que conecta a sua conta do Mercado Livre **em somente leitura** e transforma
os dados em decisão: promoções terminando, dinheiro a receber, conteúdo de produto e mais.

Feito para o **Claude**, instalado com um comando ou pelo menu. **Roda no Codex também** —
com duas diferenças: lá não existe menu, e a atualização é manual
(`codex plugin marketplace upgrade`). A automática é só do Claude.

## O que este pacote nunca faz

- Não altera preço, estoque, anúncio nem pedido.
- Não adere a promoção, não responde pergunta, não envia mensagem.
- Não guarda a sua credencial em servidor nenhum: ela fica na sua máquina, numa pasta sua.
- Não pede e não aceita segredo pelo chat.

A garantia não é promessa: o cliente HTTP do pacote recusa qualquer chamada que não seja
leitura **antes de ela sair do seu computador**.

## Começar

### 1. Instalar o pacote

**Pelo aplicativo, sem terminal** — é o caminho com menos atrito:

1. **Configurações → Plugins**
2. Botão **+ Adicionar**, no canto superior direito → **Adicionar marketplace**
3. Escolher **Adicionar de um repositório** e colar, nesta forma curta:
   `sebemlabs-agents/prometheus`

   > Use a forma curta, não a URL inteira. Se a máquina já tiver esse catálogo
   > registrado pela forma curta, colar a URL completa é recusado como fonte
   > diferente, com a mensagem `Falha ao adicionar marketplace`.
4. O `prometheus` passa a aparecer na lista. Abrir e instalar, escolhendo o escopo
   (**para você** serve: vale em qualquer pasta desta máquina).

**Pelo terminal**, se preferir — um comando registra o catálogo e instala:

```bash
claude plugin install prometheus --marketplace sebemlabs-agents/prometheus
```

Precisa do Claude Code **2.1.292 ou mais novo** (`claude --version`). Em versão anterior, são
dois comandos:

```bash
claude plugin marketplace add sebemlabs-agents/prometheus
claude plugin install prometheus@prometheus
```

No **Codex**:

```bash
codex plugin marketplace add sebemlabs-agents/prometheus
codex plugin add prometheus@prometheus
```

### 1b. Deixar o pacote se atualizar sozinho

O pacote ganha skills novas e correções com o tempo. Mas **atualização automática vem
desligada** em catálogo que não é da Anthropic — é uma proteção do Claude, não um descuido
nosso. Sem ligar, você fica na versão do dia em que instalou.

Não precisa procurar menu nem decorar comando. **Peça ao Claude:**

> liga a atualização automática do prometheus

A skill de conexão cuida disso, pergunta antes de mexer e guarda cópia da sua configuração.
Para saber como está a qualquer momento: *"o prometheus está atualizando sozinho?"*

### 2. Criar a pasta onde tudo vai morar

Uma pasta nova, só para isto, **fora** de Dropbox, iCloud, Google Drive e OneDrive — o pacote
verifica isso e para se a pasta sincronizar, porque a sua credencial não pode ir para a nuvem
sem você saber.

Sugestão: uma pasta chamada `prometheus`.

- **Mac:** em Documentos serve.
- **Windows:** **não use Documentos** — ela quase sempre está dentro do OneDrive e o pacote
  recusa. Use `C:\Users\<seu nome>\prometheus`.

Conecte essa pasta ao Claude.

### 3. Pedir a conexão

Peça ao assistente, nestas palavras ou parecidas:

> **conecta minha conta do Mercado Livre**

A skill `prometheus-conectar-meli` conduz o resto: cria o aplicativo no DevCenter do Mercado Livre,
faz a autorização sem nenhum segredo passar pelo chat, confirma qual conta conectou e gera o
primeiro painel. Leva cerca de **10 minutos**.

Depois disso, peça o que quiser: *"quais promoções estão acabando?"*, *"quanto o Meli me
deve?"*, *"atualiza o painel"*.

## O que vem dentro

| Skill | O que entrega |
|---|---|
| `prometheus-conectar-meli` | acesso só-leitura à sua conta, na sua pasta |
| `prometheus-conectar-shopee` | o mesmo para a Shopee — precisa de um domínio HTTPS seu |
| `prometheus-conectar-olist` | importa do ERP o **custo** dos produtos — o que o marketplace não tem |
| `prometheus-painel` | o painel local com os blocos das skills que você rodou |
| `prometheus-pedidos` | quanto você vendeu, os últimos pedidos, e a comissão que veio em cada item |
| `prometheus-promocoes` | a fila do que termina nos próximos dias, com anúncios dentro e desconto mínimo |
| `prometheus-planilha` | lê qualquer CSV ou XLSX seu e cruza com o painel — sem formato obrigatório |

Mais skills entram pelo mesmo caminho: cada uma grava um arquivo no formato do
[CONTRATO.md](./CONTRATO.md) e aparece como um bloco no painel.

## Requisitos

- **Python 3.8 ou mais novo.** No Mac normalmente já vem: confira com `python3 --version`.
  **No Windows o comando é `py -3`** (`py -3 --version`); se não existir, instale do site
  oficial marcando **"Add python.exe to PATH"**.
- **Conta administradora** de vendedor no Mercado Livre. Conta de operador ou colaborador não
  consegue autorizar — o Mercado Livre recusa.
- Uma pasta sua, fora de serviço de sincronização.

Nenhuma dependência é instalada: os scripts são Python puro.

## Guias em PDF

- **[Guia do participante](./docs/playbook-participante.html)** — para quem vai conectar
  sozinho, de forma assíncrona: pré-requisitos, os três passos, o que fazer quando trava e
  como desligar depois.
- **[Playbook de condução](./docs/playbook-conexao.html)** — para quem acompanha alguém
  conectando pela primeira vez: onde observar, onde ficar calado, o que cronometrar e a ficha
  de observação.

Os dois geram PDF com `Google Chrome --headless --print-to-pdf`.

## Se algo der errado

A skill traz a tabela de problemas com os erros reais e o que fazer em cada um —
`skills/prometheus-conectar-meli/references/problemas.md`. Os três mais comuns:

- **A URL de retorno precisa ser idêntica** à cadastrada no DevCenter, caractere por caractere.
- **Conta de operador não autoriza.** Use a conta administradora da loja.
- **`api.mercadolibre.com` precisa estar liberado** nos domínios permitidos do Claude. Em
  conta de empresa, quem libera é o administrador.

## Para desenvolver

```
python3 -m pytest tests -q
```

## Licença

MIT — Marciano Chula / Elo. Ver [LICENSE](./LICENSE).
