# Plano executável — LST-17867 / 1.8.4

Spec: `docs/superpowers/specs/2026-11-07-prometheus-plugin-isolado-design.md`.
Base: `c28e5545cc1fff34ee35eaa8649d2d0b0c60a20c`.

1. Preservar `acoes/`, `scripts/`, teste de Ações e documentos de uso em ZIP de
   fontes fora do repo. Conferir arquivo antes de remover arquivos rastreados.
2. Criar `tests/test_plugin_package.py` e executar só seu inventário: deve falhar
   com os dois manifestos reais da base.
3. Retirar `acoes/` e seu teste; transferir garantias de leitura para o novo teste;
   ajustar README, changelog e versões. Não editar scripts nem skills de leitura.
4. Rodar suíte completa no ambiente virtual já auditado, `claude plugin validate`,
   diff check e comparação byte a byte dos diretórios preservados.
5. Revisar spec e código em separado; registrar contagens, limites e recibo.
6. Atualizar referências, abrir PR e publicar pelo Guard com commit travado.
7. Conferir manifestos e pacote público; repetir sincronização e instalação na
   conta de teste do Chrome. Registrar sucesso ou próximo erro com código exato.
8. Reconciliar LST-17867, Vault, LCM e roadmap; remover só a própria worktree
   integrada. Preservar a worktree do Claude/PR #17.

## Verificação do candidato

- RED: teste estrutural encontrou `.claude-plugin/plugin.json` e
  `acoes/.claude-plugin/plugin.json` na base: 1 falhou, 5 passaram.
- 123 casos pertenciam ao arquivo de testes de Ações. Após sua retirada, cinco
  garantias de leitura/catálogo foram preservadas; inventário, paridade dos
  manifestos e ambas as plataformas passaram a compor oito casos do novo arquivo.
- Suíte final: **332 passaram em 12,14 s**. Antes do reforço da revisão, 330
  passaram em 12,47 s. Não foram removidos testes de leitura ou atualização.
- `scripts/`, `skills/`, catálogo, testes base/trava/YAML e requisitos de teste
  idênticos à base. `git diff --check` limpo. `claude plugin validate .` passou,
  mantendo somente o aviso preexistente de ícone. Ambos os manifestos em 1.8.4.
- Fontes Ações preservadas fora do pacote, incluindo teste e dependências locais:
  ZIP 126573 bytes, SHA-256
  `adeb51d889221499c4cb4e587f5453b2d63c95ffe35a0d2c9bdc0d4fcba0b808`.

## Revisão e segurança

Revisão independente do Claude, limitada a Read/Glob/Grep, aprovou sem impedimento
de merge. Não executou testes. Observações menores tratadas: comparação de versões
automatizada; detecção de imports de escrita por AST em todos os scripts; verificação
de manifesto aninhado também para Codex. O inventário continua deliberadamente
validando a pasta real (inclui arquivos locais); seu limite está no README e é
complementado pela verificação do arquivo Git e do pacote remoto após publicação.

Checklist Cypher aplicada ao delta. Retirada de superfície de escrita, sem alteração
de autorização, conta/org, credencial, servidor, banco, RPC, storage, infraestrutura
ou persistência operacional. Scripts de leitura idênticos à versão anterior;
recusas de escrita e testes do verificador permanecem aprovados. Não há endpoint
próprio novo para a matriz visitante/sem aprovação/aprovado/outra org/revogado.
Nenhuma conta real de marketplace foi conectada ou usada. Dependências de teste
não mudaram desde a auditoria OSV limpa registrada na publicação 1.8.3; não há
dependências novas para os participantes.

GitHub público/main é o canal de distribuição. O Guard não tem configuração de
provedor Vercel ou contrato opt-in `githubPolicy` neste repositório; não afirmar
proteção remota/CI obrigatório. Publicação deve usar PR e wrapper, sem bypass,
com SHA confirmado. O recibo final e a prova no claude.ai serão registrados no
Vault após o merge; teste local não substitui essa prova.

## desvios[]

- Teste estrutural abrange também `.codex-plugin` para evitar a mesma regressão
  no outro manifesto distribuído. Sem alteração do comportamento de produto.
- Imports proibidos passaram de busca textual parcial a AST em todos os scripts,
  preservando e reforçando a garantia existente sem alterar esses scripts.
