# Cabeçalhos YAML — LST-17867 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans. Implementação direta; revisão final independente.

**Goal:** corrigir os três cabeçalhos inválidos e impedir regressão, sem alterar o texto das skills.
**Architecture:** serialização válida apenas das três descrições; teste pytest lê os arquivos reais com `yaml.safe_load`. PyYAML é dependência exclusiva de desenvolvimento, declarada em `tests/requirements.txt`.
**Tech Stack:** Python 3.8+, pytest, PyYAML 6.x.
**Spec:** `docs/superpowers/specs/2026-11-06-prometheus-skill-yaml-design.md`, aprovada por Marvin.

## Global Constraints

- LST-17867; branch `codex/lst-17867-skill-yaml`, a partir de `origin/main` atualizado.
- Preservar nomes, descrições decodificadas e corpos das skills.
- Não alterar `atualizacao.py`, a worktree do Claude ou PR #17.
- Nenhuma alteração de versão, ZIP distribuído, merge ou publicação nesta entrega local.

## Review Focus

- Descrição com dois-pontos e aspas precisa ser lida como string inteira.
- Acentos e corpo das instruções precisam permanecer idênticos à base.
- O teste cobre todas as skills do plugin de leitura e não passa se a descoberta ficar vazia.
- Dependência YAML não pode ser opcional nem introduzida no runtime do participante.
- Suíte local verde não comprova aceitação pelo importador remoto.

### Task 1: Corrigir e verificar os cabeçalhos

**Files:** modificar os três `skills/prometheus-conectar-{meli,olist,shopee}/SKILL.md`; criar `tests/test_skill_frontmatter.py`, `tests/requirements.txt` e `tests/README.md`.
**Interfaces:** entrada: arquivos reais em `skills/*/SKILL.md`; saída: metadados YAML com `name` e `description` como strings não vazias.

- [x] Preparar worktree própria e executar `python3 -m pytest tests -q` antes das edições. Expected: suíte de base passa, ou falhas preexistentes identificadas antes de atribuí-las à mudança.
- [x] Criar teste parametrizado que lê cabeçalhos delimitados por linhas `---`, usa `yaml.safe_load`, exige mapa, nome igual ao diretório e descrição string não vazia. Exigir inventário não vazio. Declarar pytest/PyYAML em dependências de teste, sem skip para importação ausente.
- [x] Rodar `python3 -m pytest tests/test_skill_frontmatter.py -q --tb=short`. Expected: falham precisamente as três skills de conexão; seis outras passam.
- [x] Serializar somente as três descrições como strings YAML válidas, preservando cada caractere decodificado e todo o restante do arquivo.
- [x] Rodar teste novo, suíte completa e `claude plugin validate .`. Expected: teste novo e suíte passam; aviso de ícone conhecido não bloqueante no CLI.
- [x] Comparar automaticamente os três textos com `git show` da base: nomes e corpo idênticos, descrição decodificada idêntica à descrição original. Expected: três preservados.
- [ ] Revisar conformidade e qualidade em contexto independente, corrigir achados materiais necessários, registrar provas e commit com LST-17867. Entregar localmente; confirmação remota permanece pendente de publicação autorizada.

## Desvios

Nenhum desvio de produto. A declaração da dependência de teste em `tests/requirements.txt` é detalhe técnico necessário para a verificação funcionar fora da máquina atual.

## Verificação executada

- Base 1.8.2: 438 testes passaram.
- RED: 3 falhas de YAML, 6 skills válidas.
- GREEN: 9/9 cabeçalhos válidos; suíte completa 447 passou em 13,25 s.
- Nomes, descrições decodificadas e corpos idênticos à base.
- Validador CLI passou; aviso preexistente ICON_MISSING.
- Revisão independente pendente; nenhuma publicação.
