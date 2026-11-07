"""Contrato do pacote distribuído pelo marketplace, incluindo o importador web."""
import ast
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import meli  # noqa: E402


@pytest.mark.parametrize("directory", [".claude-plugin", ".codex-plugin"])
def test_cada_plugin_do_catalogo_tem_apenas_um_manifesto_na_raiz(directory):
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    assert marketplace["plugins"]
    for plugin in marketplace["plugins"]:
        root = (ROOT / plugin["source"]).resolve()
        assert root.is_relative_to(ROOT)
        manifests = sorted(
            path.relative_to(root).as_posix()
            for path in root.rglob("plugin.json")
            if path.parent.name == directory
        )
        assert manifests == [f"{directory}/plugin.json"], (
            f"{plugin['name']}: marketplace_sync_multiple_manifests: {manifests}"
        )


def test_a_trava_de_leitura_nao_foi_tocada():
    with pytest.raises(PermissionError):
        meli.request("POST", "/seller-promotions/items/MLB1")


def test_nenhum_leitor_importa_o_modulo_de_escrita():
    writing_modules = {"escrever", "promover", "responder"}
    for path in (ROOT / "scripts").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""] + [alias.name for alias in node.names]
            else:
                continue
            assert not any(
                writing_modules.intersection(module.split(".")) for module in modules
            ), path.name


def test_manifestos_de_leitura_concordam_em_nome_e_versao():
    claude = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    codex = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
    assert claude["name"] == codex["name"] == "prometheus"
    assert claude["version"] == codex["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", claude["version"])


def test_o_marketplace_oferece_apenas_o_pacote_de_leitura():
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    assert [(p["name"], p["source"]) for p in marketplace["plugins"]] == [
        ("prometheus", "./")
    ]


def test_o_marketplace_nao_carrega_versao():
    source = (ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")
    assert '"version"' not in source


def test_os_scripts_de_escrita_nao_moram_no_pacote_de_leitura():
    for name in ("escrever.py", "promover.py", "responder.py"):
        assert not (ROOT / "scripts" / name).exists()
