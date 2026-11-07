"""O catálogo válido não garante que o importador consiga ler cada skill."""
from pathlib import Path

import pytest
import yaml


RAIZ = Path(__file__).resolve().parent.parent
SKILLS = sorted((RAIZ / "skills").glob("*/SKILL.md"))
assert SKILLS, "Nenhum SKILL.md encontrado no pacote de leitura"


@pytest.mark.parametrize("skill", SKILLS, ids=lambda path: path.parent.name)
def test_cabecalho_da_skill_pode_ser_lido_como_yaml(skill):
    """Rejeita metadados ilegíveis, inclusive ': ' em descrição sem aspas."""
    linhas = skill.read_text(encoding="utf-8").splitlines()
    assert linhas and linhas[0] == "---", "Cabeçalho YAML ausente"
    assert "---" in linhas[1:], "Cabeçalho YAML sem delimitador de fechamento"
    fim = linhas.index("---", 1)
    metadados = yaml.safe_load("\n".join(linhas[1:fim]))

    assert isinstance(metadados, dict), "Cabeçalho precisa ser um mapa YAML"
    assert metadados.get("name") == skill.parent.name
    descricao = metadados.get("description")
    assert isinstance(descricao, str) and descricao.strip(), (
        "description precisa ser uma string não vazia"
    )
