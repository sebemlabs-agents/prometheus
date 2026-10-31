---
name: prometheus-planilha
description: Lê qualquer planilha CSV ou XLSX do usuário — exportação de marketplace, relatório de ERP, planilha de custo feita à mão — descreve as colunas e cruza com os dados do painel. Não exige formato nenhum. Use quando o usuário mencionar planilha, arquivo, exportação, relatório baixado, XLSX, CSV, Excel, "eu tenho uma planilha com", "exportei do sistema", "minha planilha de custo", ou quando faltar um dado que nenhuma API tem — custo por SKU, dados de outro marketplace, números de ERP.
---

# Ler a planilha dele — pacote Elo

O pacote lê o Mercado Livre pela API. **Tudo que não está lá chega por planilha**: o custo de
cada produto, os dados de outro marketplace, o que o ERP dele calcula.

Não existe formato padrão, e não adianta pedir um. Cada marketplace exporta de um jeito, cada
ERP nomeia as colunas do seu jeito, e a planilha de custo que ele fez em casa tem a cara dele.
**Quem faz o mapeamento é você**, lendo os cabeçalhos e os exemplos. É exatamente o trabalho
que você faz bem e que um formato rígido faria mal.

## Antes de rodar — os scripts da pasta

O pacote cresce e a pasta do usuário não se atualiza sozinha. Se `planilha.py` não estiver na
pasta dele, copie todos os `.py` de `${CLAUDE_PLUGIN_ROOT}/scripts/` para lá, **sem
sobrescrever `credenciais.txt` nem `tokens.json`**.

## Passo 1 — olhar antes de decidir

```
python3 planilha.py custos.xlsx
```

Sai a lista de colunas, o tipo de cada uma, quantas vieram vazias e exemplos reais. Para ler
por programa: `--json`. Para outra aba: `--aba 2`. Para mais exemplos: `--linhas 10`.

**Não pule este passo.** Mapear coluna pelo nome que você imagina que ela tem é a forma mais
rápida de produzir um número errado com cara de certo.

Ele já resolve sozinho: ponto-e-vírgula, acento em arquivo antigo, `1.234,56` virando número,
`15/03/2026` virando data, coluna sem nome, coluna repetida, linha mais curta que o cabeçalho.
Não precisa pedir para ele "arrumar a planilha antes".

## Passo 2 — mapear com ele, não por ele

Mostre o que você entendeu e **confirme antes de calcular**:

> "Achei 4 colunas. Entendi que `Cód. Produto` é o seu SKU, `Vlr. Custo` é o custo unitário e
> `Imposto %` é a alíquota. A coluna `Obs` eu ignoro. Confere?"

Quando a coluna for ambígua, **pergunte em vez de escolher**. "Valor" pode ser preço de venda,
custo ou valor total do pedido — e as três dão contas diferentes.

Se faltar a coluna que o cálculo precisa, diga qual falta e o que dá para fazer sem ela. Não
estime, não complete, não assuma zero.

## Passo 3 — cruzar com o que já está no painel

É aqui que a planilha vira resposta. Os arquivos `prometheus-*.json` da pasta têm os dados do Mercado
Livre; a planilha tem o que falta. A chave do cruzamento quase sempre é o **SKU** ou o
**MLB**.

Ao cruzar, **diga quantos casaram e quantos não casaram**. Um cruzamento que achou 40 de 300
não é um resultado: é um aviso de que a chave está errada, ou de que a planilha é de outro
período.

Cruzamentos que fazem sentido:

- **custo por SKU** com os anúncios → margem de contribuição real
- **exportação de pedidos de outro marketplace** → o mesmo painel, com os dois canais
- **relatório de estoque do ERP** com as vendas → cobertura em dias

## Passo 4 — gravar no painel

Quando o cruzamento virar algo que ele vai olhar de novo, grave no contrato do pacote para
aparecer como bloco:

```python
contrato.gravar("prometheus-planilha", conta=None, periodo=None,
                resumo={...}, itens=[...],
                fonte="export",
                capturado_em=dado["capturado_em"],
                faltando=[...], lacunas={...})
```

**`fonte="export"` e `capturado_em` não são opcionais aqui.** Dado de planilha tem duas
idades: quando você processou, e **quando o arquivo foi baixado**. Sem isso o painel diz
"atualizado agora" sobre uma exportação da semana passada — e alguém decide com número velho
achando que é de hoje. O painel mostra as duas, e marca o bloco como vindo de planilha.

## O que nunca fazer com a planilha dele

- **Não corrija o arquivo dele.** Se tem linha estranha, diga qual e deixe ele decidir.
- **Não complete o que falta.** Custo ausente é lacuna declarada, nunca zero — zero inverte o
  sinal da margem e transforma prejuízo em lucro na tela.
- **Não some coluna que você não entendeu.** Pergunte.
- **Não grave a planilha inteira no painel.** Grave o resultado do cruzamento. O arquivo é
  dele e já está no computador dele.

## Quando o arquivo não abre

`.xls` antigo não abre — peça para salvar como `.xlsx` ou `.csv` no Excel ou no Google
Sheets, que leva dez segundos. Arquivo protegido por senha também não: peça uma cópia sem
senha. Em ambos o script já explica o que fazer, em português.
