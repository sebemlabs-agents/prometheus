# Testes do pacote

Na raiz do repositório, com Python 3.10 ou posterior e um ambiente virtual ativado:

```bash
python3 -m pip install -r tests/requirements.txt
python3 -m pytest tests -q
```

PyYAML é usado somente para validar os cabeçalhos reais em `skills/*/SKILL.md`.
Não é uma dependência dos scripts executados pelo participante. A ausência de
PyYAML deve falhar na coleta dos testes; a validação não é opcional.

O Python 3.10 é requisito apenas do ambiente de testes, por causa do pytest 9.
Os mínimos de pytest e Pygments incluem as correções de CVE-2025-71176 e
CVE-2026-4539, respectivamente. Os scripts do participante não mudaram.

O teste de cabeçalhos complementa `claude plugin validate .`, que aprovava o
catálogo mesmo com três descrições YAML inválidas. Passar nesses testes não
comprova a sincronização do marketplace na interface remota do Claude.

O teste de estrutura em `test_plugin_package.py` examina os arquivos presentes
na pasta do plugin, incluindo arquivos locais não versionados. Rode em checkout
limpo ou no pacote extraído; antes de publicar, confira também o arquivo gerado
do commit Git e, depois, o pacote obtido da principal remota.
