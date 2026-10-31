# Contrato de dados do pacote Elo — versão 1

- **Ticket:** LST-17589
- **Versão do contrato:** `1`
- **Data:** 2026-10-17
- **Plano:** [Tarefa 0](../superpowers/plans/2026-10-16-pacote-prometheus-imersao-4.md)
- **Destino:** vai para a raiz do repositório `prometheus` como `CONTRATO.md` quando ele nascer.

---

## Por que isto existe antes do código

Seis skills vão gravar dados e **um** painel vai ler. Se cada skill inventar o formato, o
painel vira remendo e cada skill nova custa o dobro. Este arquivo é a única coisa do pacote
que todas as partes precisam respeitar — e é por isso que ele vem antes de qualquer linha de
Python.

Regra de ouro: **a skill coleta e grava; o painel lê e formata.** A skill nunca gera HTML, o
painel nunca chama a API.

---

## 1. Onde o arquivo mora

Um arquivo por skill, na pasta do próprio vendedor:

```
<pasta-do-vendedor>/
├── prometheus-pedidos.json
├── prometheus-promocoes.json
├── prometheus-devolucoes.json
└── painel.html            ← gerado a partir dos .json presentes
```

O painel lê todos os `prometheus-*.json` da pasta. **Skill ausente não é erro**: o painel
simplesmente não desenha aquele bloco. Isso é o que permite entregar quatro skills no evento
e mais quatro depois, sem mexer no painel.

---

## 2. O envelope

Todo arquivo tem exatamente esta forma. Os campos marcados como obrigatórios existem sempre,
mesmo vazios.

```json
{
  "contrato": "1",
  "skill": "prometheus-promocoes",
  "gerado_em": "2026-10-17T14:32:05-03:00",
  "fonte": "api",
  "conta": {
    "id": 123456789,
    "apelido": "LOJA EXEMPLO",
    "site": "MLB"
  },
  "periodo": { "de": "2026-07-19", "ate": "2026-10-17" },
  "moeda": "BRL",
  "resumo": {
    "promocoes_na_janela": 4,
    "anuncios_afetados": 37
  },
  "itens": [],
  "paginacao": { "pagina": 1, "paginas": 1, "por_pagina": 50 },
  "faltando": ["faturamento_afetado"],
  "lacunas": {
    "faturamento_afetado": "a consulta por anúncio estourou o tempo; rode sem --rapido para obter"
  },
  "avisos": ["3 anúncios encerrados foram ignorados"]
}
```

### Campo por campo

| Campo | Obrigatório | O que é |
|---|---|---|
| `contrato` | sim | versão deste contrato, sempre string. O painel recusa versão que não conhece em vez de desenhar errado. |
| `skill` | sim | nome da skill, igual ao nome do arquivo sem extensão. |
| `gerado_em` | sim | ISO 8601 **com fuso** (`-03:00`). O painel mostra a idade do dado; dado de ontem apresentado como de hoje é decisão errada. |
| `fonte` | sim | `"api"`, `"demo"`, `"local"` ou `"export"`. Ver seção 4. |
| `conta` | quando `fonte` é `"api"` | `id` e `apelido` vêm da própria API. É o que permite a pessoa confirmar que é a loja certa. Com `fonte: "local"` não existe conta para nomear, e os campos vêm `null`. |
| `periodo` | sim | datas `AAAA-MM-DD`. Quando a skill não tem recorte de período, use `null` nos dois. |
| `moeda` | sim quando houver valor | `"BRL"`. |
| `resumo` | sim | totais do período, pares chave-valor rasos. Ver seção 3. |
| `itens` | sim | a lista. Forma própria de cada skill, documentada na própria skill. Pode ser `[]`. |
| `paginacao` | quando a skill pagina | `pagina`, `paginas`, `por_pagina`. |
| `faltando` | sim | **lista de strings** com os nomes dos campos que não vieram. `[]` quando nada falta. |
| `lacunas` | quando `faltando` não está vazio | objeto que mapeia cada nome de `faltando` para a explicação em português, pronta para aparecer na tela. |
| `avisos` | sim | lista de strings sobre o que aconteceu na coleta e não é lacuna (itens pulados, limites atingidos). `[]` quando não houver. |

---

## 3. As quatro regras que fazem o painel ser honesto

### 3.1 Resumo antes de detalhe

`resumo` traz os totais já calculados. O painel e o Claude leem dali em vez de somar linha
por linha — some o erro de soma e some o custo de contexto.

### 3.2 Dado ausente é `null`, nunca `0`

Num item, campo desconhecido é `null`. **Zero é um valor**, e num campo de margem ele inverte
o sinal da decisão. Além disso, o nome do campo entra em `faltando` e ganha explicação em
`lacunas`.

```json
{ "mlb": "MLB123", "preco": 149.90, "custo": null, "margem": null }
```

### 3.3 Toda lacuna é dizível

Se um nome está em `faltando`, existe a chave correspondente em `lacunas` com um texto que
pode ser mostrado ao vendedor sem tradução. Não serve `"erro na API"`; serve
`"o custo deste SKU não veio na sua planilha"`.

### 3.4 Dinheiro é número, não texto

Valores monetários são número decimal com até duas casas, em reais, ponto como separador
(`149.90`). Nunca string, nunca vírgula, nunca centavos inteiros. Quem formata para a tela é
o painel.

Datas e horas: ISO 8601. Período em `AAAA-MM-DD`; instantes com fuso. Exibição em
America/São Paulo é responsabilidade do painel.

---

## 4. De onde o dado veio

O campo `fonte` diz isso, e tem três valores:

- **`"api"`** — leitura da conta real. Exige `conta.id`.
- **`"demo"`** — dados de demonstração preparados, para quem não conseguiu conectar.
- **`"local"`** — produzido na própria máquina, sem ler conta nenhuma. É o caso de uma skill
  de conteúdo de produto: não há conta para nomear, e inventar uma seria mentira no painel.
- **`"export"`** — veio de uma planilha que a pessoa baixou: exportação de marketplace,
  relatório de ERP, custo feito à mão. Exige `capturado_em`.

### Dado de planilha tem duas idades

`gerado_em` é quando o pacote processou. `capturado_em` é **quando o arquivo foi baixado da
origem**, e vem da data de modificação do próprio arquivo.

Confundir as duas é o erro silencioso desta fonte: o painel diria "atualizado agora" sobre uma
exportação de semana passada, e alguém decidiria com número velho achando que era de hoje.

**Obrigação do painel:** com `fonte: "export"`, mostrar a idade do arquivo ao lado da idade do
processamento, e marcar o bloco como vindo de planilha.

### Modo demonstração

Quando a skill roda com dados preparados em vez da conta real, `fonte` vale `"demo"`.

**Obrigação do painel:** exibir isso de forma visível e permanente no bloco — não um rodapé
discreto. Quem está em demonstração precisa saber a cada olhada, e quem vê a tela dessa
pessoa também.

É isso que permite o caminho único de quem não conseguiu criar a aplicação: a pessoa constrói
tudo, acompanha a sala inteira, e o painel dela nunca mente sobre a origem do número.

---

## 5. Como a skill grava, como o painel lê

Duas funções, em `scripts/contrato.py`, usadas por todas as skills:

```python
gravar(
    skill: str,
    conta: dict,
    periodo: dict | None,
    resumo: dict,
    itens: list,
    faltando: list[str] | None = None,
    lacunas: dict | None = None,
    avisos: list[str] | None = None,
    fonte: str = "api",
    paginacao: dict | None = None,
) -> dict          # grava prometheus-<skill>.json na pasta e devolve o que gravou

carregar(skill: str) -> dict | None    # None quando o arquivo não existe
```

`gravar` valida antes de escrever e levanta erro quando:

- `faltando` tem um nome sem entrada correspondente em `lacunas`;
- `fonte` não é um dos quatro valores conhecidos;
- algum valor monetário chegou como string;
- `resumo` tem valor aninhado (tem de ser raso).

Falhar na escrita é melhor que gravar um arquivo que o painel desenha errado.

---

## 6. Validação do contrato por skill

Cada skill tem um teste que valida o próprio arquivo contra este contrato. Antes de escrever
a primeira skill, escrever o exemplo de `itens` de cada uma das oito — se alguma não couber
no envelope, **o envelope muda agora**, não depois de três skills prontas.

Linhas de exemplo já previstas:

| Skill | Um item é |
|---|---|
| `prometheus-promocoes` | uma promoção na janela: nome, término, dias restantes, anúncios dentro, percentual mínimo |
| `prometheus-pedidos` | um pedido: data, valor pago, situação, e a comissão real de cada item |
| `prometheus-visitas` | um anúncio: visitas na janela, vendas na janela, conversão |
| `prometheus-devolucoes` | uma devolução: status, motivo, se retornou, valor, situação do repasse |
| `prometheus-recebiveis` | uma data de liberação: valor líquido, origem, situação |
| `prometheus-concorrencia` | um produto analisado: concorrentes da primeira página, preço, reputação, Full, posição do meu |
| `prometheus-anuncios` | um anúncio: preço, estoque, saúde, quantidade vendida |
| `prometheus-saude` | um sinal: o que mudou, desde quando, e o que isso ameaça |
| `prometheus-conectar-meli` | não grava itens; grava o recibo de conexão em `resumo` |

---

## 7. O que este contrato não resolve

- **Não é formato de troca com terceiro.** É interno ao pacote. Se algum dia virar exportação,
  isso é outra versão.
- **Não guarda histórico.** Cada execução sobrescreve o arquivo da skill. Histórico é o
  degrau 3, e é lá que o formato ganha carimbo de tempo por linha.
- **Não carrega segredo.** Nenhum campo deste contrato contém App ID, Client Secret, token ou
  URL de autorização. Se aparecer, é bug de segurança, não de formato.

---

## 8. Mudar o contrato

Mudança compatível (campo novo opcional): mantém `contrato: "1"`.

Mudança incompatível (campo obrigatório novo, renomear, trocar tipo): sobe para `"2"`, e o
painel passa a aceitar as duas versões por um ciclo. Com oito skills e gente usando em casa,
quebrar formato silenciosamente é a pior coisa que o pacote pode fazer.
