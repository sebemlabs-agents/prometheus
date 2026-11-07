# Cabeçalhos YAML das skills — LST-17867

Status: **aprovada por Marvin nesta sessão** para implementação local.

## Objetivo e contexto comprovado

Eliminar YAML inválido nas descrições de `prometheus-conectar-meli`, `prometheus-conectar-olist` e `prometheus-conectar-shopee`. Na versão 1.8.1, `claude plugin validate` aprovava o catálogo, mas PyYAML 6.0.3 rejeitava essas três skills por `: ` em escalares sem aspas. A base atual é `origin/main` em `d603599306682223f4a3ebfd2ef2975f6086203b` (1.8.2), que já contém a correção independente do verificador de atualização, e ainda contém os três cabeçalhos inválidos.

## Contrato aprovado

- Corrigir somente a representação YAML das descrições das três skills.
- Preservar nomes, descrições decodificadas e corpo das instruções, caractere por caractere.
- Acrescentar teste de regressão que leia os cabeçalhos reais das nove skills do plugin de leitura e exija `name` e `description` como strings não vazias.
- O teste precisa falhar nos três originais antes da correção e passar depois.
- Declarar dependências do teste; nenhum pacote novo é necessário para o participante executar as skills.

## Limites

Não alterar o verificador de atualização (LST-17866), PR #17, vitrine, capacidades, conexões, permissões, credenciais ou dados. Não alterar a versão nem distribuir novo ZIP nesta entrega local. Merge e publicação não estão autorizados. A correção de formato não comprova que o erro da interface tem esta causa: falta prova no importador remoto ou na conta afetada.

## Aceite e testes

1. Teste estrito falha precisamente nos três cabeçalhos originais.
2. Nove skills passam após o ajuste; suíte existente passa.
3. Comparação com a base confirma igualdade dos nomes, descrição decodificada e corpo.
4. `claude plugin validate .` continua passando; aviso preexistente de ícone documentado.
5. Revisão separa conformidade com este contrato de qualidade/segurança.

## Rollout, rollback e dados

Entrega em branch/worktree Codex própria. Publicação posterior exige nova autorização, versão incrementada e gates aplicáveis. O aceite da distribuição exige adicionar o marketplace pela interface real, instalar e listar as nove skills. Rollback: reverter somente o commit desta correção. Nenhuma persistência operacional, política de retenção, cron, migração ou ampliação de acesso é criada.

## Desvios

Nenhuma mudança de produto. Base atualizada para incorporar LST-17866 já integrado. Declaração de PyYAML apenas nas dependências de desenvolvimento é detalhe técnico necessário para o teste reproduzível.
