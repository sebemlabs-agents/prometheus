---
name: prometheus-conectar-olist
description: "Conecta o ERP Olist (Tiny) em somente leitura e importa o CUSTO dos produtos para a pasta do usuário — o dado que nenhum marketplace entrega e sem o qual a margem não fecha. Use quando o usuário pedir para conectar a Olist ou o Tiny, quando ele disser que usa o ERP, ou quando uma skill precisar de custo e não houver planilha. Use também quando ele relatar erro, conexão vencida ou dúvida da Olist — \"a Olist pediu para reconectar\", \"deu 401\", \"estourou o limite\", \"invalid_grant\". Não use para Mercado Livre nem Shopee: cada um tem a sua skill."
---

# Conectar a Olist — o custo que falta na margem

Esta skill existe por um motivo específico: **marketplace nenhum entrega o custo do
produto.** É por isso que o pacote pede uma planilha de custo. Quem tem o ERP não
precisa dela — o custo vem da fonte, com histórico.

## O desenho é diferente das outras duas conexões, e o motivo importa

Aqui a gente **importa** o custo em vez de manter conexão viva: conecta, puxa o custo para
a pasta, e o painel passa a ler o arquivo. Dois motivos:

- **Este pacote é programa de mesa, não servidor.** Ele só roda quando ela abre. Uma
  integração de verdade renova o acesso sozinha de hora em hora; o pacote não tem como —
  e conexão que só renova quando alguém abre o computador vence sozinha.
- **O limite de chamadas é da CONTA, não do aplicativo.** Todas as integrações dela
  dividem a mesma cota. Varrer catálogo aqui atrapalha o ERP dela de verdade.

E custo de produto não muda todo dia. Com o custo na pasta, **a margem continua
funcionando dias depois, com a conexão já vencida.**

> ### O prazo, e por que duas pessoas dão respostas diferentes
>
> Medido contra o servidor em 22/10/2026: o acesso vale **4 horas** e a renovação vem com
> **24 horas** declaradas. Mas **cada uso da renovação reinicia esse relógio.**
>
> É por isso que quem roda integração o dia todo jura que nunca vence — e está certo — e
> quem abre o programa de vez em quando vê vencer, e também está certo. **Este pacote é do
> segundo tipo:** ele só roda quando ela abre.
>
> Não decore esses números: o pacote lê o que o servidor manda na hora e te diz. Decore a
> regra — **quando pedir para reconectar, é normal e não se perdeu nada.**

## Dois pré-requisitos que podem barrar

- Plano **Construa ou superior**. Abaixo disso não existe API v3 na conta.
- Extensão **Gestão de Aplicativos** instalada.

Se ela não tiver, não insista: siga com a planilha de custo, que resolve o mesmo problema.

---

## 1. O aplicativo no ERP

No ERP dela: **menu > configurações > aba geral > Aplicativos > + novo aplicativo**.

- **Nome:** o que ela reconheça depois.
- **URLs de Redirecionamento:** o mesmo endereço que ela usou nos outros canais — domínio
  dela ou o do projeto Supabase.
- **Permissões:** marque os módulos e escolha **Leitura**. Nunca "incluir e editar", nunca
  "excluir" — o pacote não escreve.

> **As chaves não aparecem ao salvar.** Ela precisa **entrar de novo no aplicativo e
> editar** para ver Client ID e Client Secret, na seção *Chaves de acesso*. É o mesmo
> tropeço do Mercado Livre — avise antes.

**Máximo 5 aplicativos por conta.** Se ela já integra outras plataformas, pode estar no
limite.

## 2. Preencher as credenciais (ela faz, fora do chat)

Em `credenciais.txt`, as três linhas:

```
OLIST_CLIENT_ID=
OLIST_CLIENT_SECRET=
OLIST_REDIRECT_URI=
```

## 3. Conectar e importar

```
python3 autorizar_olist.py
```

Abre `ABRIR_OLIST.txt`, ela cola no navegador **logado no ERP**, autoriza, copia a barra
inteira para `RETORNO_OLIST.txt`. Então:

```
python3 autorizar_olist.py --arquivo RETORNO_OLIST.txt
```

## 4. Puxar o custo — dos produtos que interessam, não de todos

**O limite de chamadas é por CONTA e não por aplicativo.** Quem já tem outras integrações
divide a mesma cota com elas — varrer o catálogo daqui atrapalha o ERP dela de verdade, e
demora.

Então puxe o custo **dos produtos que estão sendo analisados** — os que apareceram na fila
de promoções, os que ela perguntou. Não varra o catálogo.

O custo sai do **detalhe do produto** (`GET /produtos/{id}`), que traz preço de custo,
custo médio e o histórico por data **numa chamada só** — e isso importa, porque o limite é
da conta inteira.

O custo importado vira `prometheus-custos.json` na pasta, com `capturado_em` — que é a
idade do dado. **Sempre diga essa idade quando usar o custo numa conta de margem.** Custo
de três semanas atrás apresentado como de hoje é decisão errada com cara de certa.

---

## Erros reais e o que fazer

| Sintoma | Causa | O que fazer |
|---|---|---|
| "Precisa reconectar" | a renovação venceu | **não é defeito.** O custo já importado continua na pasta; reconecte só para trazer custo novo |
| `401` | **não é chave errada** | é o usuário logado sem permissão no módulo. Confira o perfil do usuário, não a credencial |
| `429` ou travou | passou do limite de chamadas | o limite é da conta inteira, dividido com as outras integrações dela. Espere e puxe menos produtos |
| Não acha as chaves depois de salvar | elas não aparecem ao salvar | entre de novo no aplicativo e clique em editar |
| Parou de funcionar depois de mexer nas permissões | a Olist invalida a chave | é documentado: ao mudar permissão, gere chave nova e atualize o `credenciais.txt` |

## Regras que valem o tempo todo

- **Somente leitura.** O `olist.py` levanta `PermissionError` para qualquer método que não
  seja `GET`. Alterar produto ou pedido se faz no próprio ERP, por ela.
- **Segredo nunca passa pelo chat.** Não leia `credenciais.txt`, `tokens-olist.json`,
  `ABRIR_OLIST.txt` nem `RETORNO_OLIST.txt`.
- **Custo tem idade.** Use o `capturado_em` do arquivo, sempre.
- **Dado ausente não é zero.** Produto sem custo cadastrado no ERP fica sem margem, com a
  linha em branco — nunca com zero.
