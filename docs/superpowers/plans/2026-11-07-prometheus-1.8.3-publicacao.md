# Publicação 1.8.3 — LST-17867

Autorização: Marvin pediu publicar a correção revisada. Base canônica consultada:
`origin/main`, `d603599306682223f4a3ebfd2ef2975f6086203b`, versão 1.8.2.

## Plano de execução

1. Conferir a principal e preservar LST-17866/PR #18. Concluído: base não avançou.
2. Incrementar os dois manifestos para 1.8.3, registrar o changelog e os limites.
3. Executar suíte, validar catálogo, preservar conteúdo e auditar dependências.
4. Commit e PR exclusivo desta frente; integração pelo Cypher Guard, sem bypass.
5. Conferir SHA remoto e pacote baixado do commit integrado; testar nove cabeçalhos.
6. Registrar recibo final no Vault/LCM e manter a prova na conta afetada pendente.

## Provas anteriores à integração

- 447 testes passaram em 12,91 s no ambiente anterior.
- Após atualizar somente as dependências de desenvolvimento: 447 passaram em
  13,22 s, Python 3.11, ambiente virtual isolado.
- Ambiente resolvido: pytest 9.2.0, PyYAML 6.0.3, Pygments 2.21.0, pluggy 1.7.0,
  packaging 26.3 e iniconfig 2.3.1. Consulta OSV dessas versões: nenhum aviso.
- `claude plugin validate .` passou, com aviso preexistente de ícone ausente.
- Dois manifestos 1.8.3; nenhum outro campo do manifesto mudou. Marketplace
  preservado, um plugin, sem version duplicada.
- Conteúdo decodificado e todos os bytes fora da descrição das três skills
  preservados. `scripts/` e `acoes/` idênticos à base. `git diff --check` limpo.

## Recibo de segurança do candidato

Checklist aplicada: `/Users/marvin/Projetos/cypher/cypher-checklist.md`.
Superfície: representação YAML e ferramentas de teste, sem novas dependências no
runtime. `yaml.safe_load` é usado pelo teste. Nenhuma conexão real ou credencial
foi usada na publicação ou nos testes.

Contrato de distribuição pública existente preservado: pacote MIT no repositório
público `sebemlabs-agents/prometheus`; catálogo oferece somente o plugin de leitura.
O delta não cria API, login, organização, banco, storage, grants, RPC, cache,
persistência ou escrita operacional. A matriz visitante/sem aprovação/aprovado/
outra organização/revogado não tem novos endpoints a exercitar neste delta.
Evidência preservada da base: scripts byte a byte iguais; os testes existentes
de recusa de escrita, conta incompatível, escopos e sigilo continuam na suíte
executada. Não equivale a novo pentest das APIs de terceiros.

Auditoria inicial identificou CVE-2025-71176 no pytest 8.4.2 e CVE-2026-4539 no
Pygments 2.19.2, restritos ao desenvolvimento. Corrigido o piso das dependências
antes do release, sem alterar o Python necessário para os scripts do participante.
Fontes: [pytest 9.0.3](https://github.com/pytest-dev/pytest/releases/tag/9.0.3),
[Pygments 2.20.0](https://github.com/pygments/pygments/releases/tag/2.20.0).

O Guard reporta `repo-policy: not_configured`: este repositório não declarou
`githubPolicy.required` nem possui ruleset. O verificador instalado trata esse
estado como ausência de contrato opt-in, não como ruleset obrigatório divergente.
Nenhuma proteção existente foi removida ou desativada. A publicação continua
por PR e wrapper protegido; não afirmar CI obrigatório ou proteção remota ativa.
Não há site Vercel/GitHub Pages ou backend implantado por esta frente: a distribuição
é a principal do repositório. SHA, URL e recibo efetivos serão confirmados após merge.

## Limites e rollback

Prova remota da instalação na conta afetada ainda pendente. Testes locais e pacote
válido não demonstram que a falha de sincronização da tela tenha sido resolvida.
Rollback, se necessário: novo PR que reverta apenas esta frente e nova versão
para a distribuição, preservando LST-17866. Não reescrever histórico ou publicar
o PR #17 junto. O ZIP 1.8.1 anterior permanece antigo; não reutilizá-lo como prova.
