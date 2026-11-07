# Verificação local — LST-17867

Base: `d603599306682223f4a3ebfd2ef2975f6086203b` (1.8.2, inclui LST-17866).
Código revisado: `a0bf5314468021b542db440810823973b706c504`.
Branch: `codex/lst-17867-skill-yaml`.

## Conformidade com a spec

Somente a linha de descrição das três skills de conexão mudou. Os valores YAML decodificados são iguais às descrições anteriores, inclusive acentos, aspas e dois-pontos; todos os bytes fora dessa linha são idênticos. Nomes e corpos preservados. O verificador de atualização, seus testes existentes, manifestos de versão e vitrine não mudaram.

## Provas executadas

| Prova | Resultado |
|---|---|
| Suíte na base, antes de editar | 438 passaram em 12,73 s |
| Teste novo antes da correção | 3 falhas YAML (Meli, Olist, Shopee), 6 passaram |
| Teste novo após a correção | 9 passaram |
| Suíte completa no candidato | 447 passaram em 13,25 s |
| Comparação dos textos com a base | 3/3 preservados |
| `claude plugin validate .` | Passou; aviso preexistente `ICON_MISSING` |
| `git diff --check` | Passou |

## Revisão de qualidade e segurança

Revisor independente, em contexto separado, leu o diff real e a spec; reproduziu por leitura dos blobs Git as três falhas originais e a leitura correta dos nove candidatos. Aprovou a entrega local sem achados acionáveis. O teste usa `yaml.safe_load`, exige metadados textuais, falha com inventário vazio e não ignora a ausência de PyYAML. PyYAML é dependência exclusiva dos testes, declarada em `tests/requirements.txt`.

## Limites e decisões de revisão

A aceitação pelo importador remoto e a causa do erro da interface não foram comprovadas. Permanecem pendentes de publicação autorizada e teste real. O conteúdo operacional preexistente das skills e o verificador ficaram fora do delta e foram preservados. A suíte não foi repetida após a revisão, pois não houve alteração de software; o revisor verificou os blobs do commit testado. Nenhum achado menor foi adiado.

## desvios[]

- Requisito: worktree própria. Mudança: fallback para Git após a ferramenta nativa não concluir nem criar checkout. Motivo: manter isolamento sem editar a principal; antes do fallback foi conferida a lista de worktrees.
- Requisito: base confiável atual. Mudança: partir de 1.8.2/d603599, pois LST-17866 foi integrado durante a preparação. Motivo: preservar a correção do Claude e testar a combinação.
- Requisito: teste reproduzível. Mudança: declarar pytest e PyYAML apenas em `tests/requirements.txt` e instruir sua instalação no README de testes. Motivo: não depender de biblioteca instalada apenas na máquina do autor.

## Entrega e próximo gate

Entrega somente local: sem push, PR, merge, incremento de versão ou publicação. A worktree deve ser preservada. Uma publicação posterior precisa atualizar a versão conforme a regra do repositório, incorporar a principal vigente e passar pelos gates aplicáveis. Após publicar, testar adicionar o marketplace pela interface afetada, instalar e listar as nove skills. O ZIP antigo não foi substituído.
