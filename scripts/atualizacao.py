#!/usr/bin/env python3
"""Le e liga a atualizacao automatica do catalogo prometheus.

Sem isto, uma correcao publicada nunca chega na maquina da pessoa: catalogo
que nao e da Anthropic vem com atualizacao automatica DESLIGADA por padrao.

Ha DOIS caminhos de instalacao, e eles guardam o registro em lugares
diferentes:

  * pelo terminal: ~/.claude/settings.json + ~/.claude/plugins/known_marketplaces.json.
    Este o script consegue ligar sozinho.
  * pelo aplicativo do Claude (vitrine da conta ou envio de .zip):
    ~/.claude/plugins/synced/<conta>/, com .marketplaces.json e o pacote em
    pasta de UUID -- o nome de verdade so aparece no plugin.json de dentro.
    Nao existe arquivo local de autoUpdate: quem liga e o botao
    "Sincronizar automaticamente" da tela de Plugins.

Dizer "nao instalado" para quem instalou pelo aplicativo era o defeito
LST-17866: o pacote esta la, so nao no lugar que o script olhava.

Uso:
    python3 atualizacao.py            diz se esta ligada
    python3 atualizacao.py --ligar    liga (faz copia dos arquivos antes)

Nao toca em nenhuma outra configuracao, e so mexe na entrada do prometheus.

Compatibilidade: Python 3.8+.
"""
import json
import os
import shutil
import sys
from pathlib import Path

CATALOGO = "prometheus"


class SemClaude(RuntimeError):
    """A pasta de configuracao do Claude nao foi encontrada."""


class GerenciadoPeloApp(RuntimeError):
    """O catalogo veio pela conta: quem liga e a tela, nao este script."""


RECADO_DO_APP = (
    "Este pacote veio pelo aplicativo do Claude, pela sua conta.\n"
    "Nao da para ligar por aqui: quem manda e a tela.\n"
    "  Configuracoes > Plugins > prometheus > \"Sincronizar automaticamente\""
)


def pasta_config():
    bruto = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(bruto).expanduser() if bruto else Path.home() / ".claude"
    if not base.is_dir():
        raise SemClaude(
            "Nao achei a pasta de configuracao do Claude em %s.\n"
            "Se voce usa o Codex, nao e erro: atualizacao automatica e so do "
            "Claude. No Codex a atualizacao e manual, com\n"
            "  codex plugin marketplace upgrade\n"
            "Se voce usa o Claude, o Claude Code ja foi aberto nesta maquina?"
            % base
        )
    return base


def _pasta_plugins(base):
    bruto = os.environ.get("CLAUDE_CODE_PLUGIN_CACHE_DIR")
    return Path(bruto).expanduser() if bruto else base / "plugins"


def _ler(caminho):
    if not caminho.exists():
        return None
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def _buckets_do_app(base):
    """Pastas de conta dentro de plugins/synced (uma por conta logada)."""
    raiz = _pasta_plugins(base) / "synced"
    try:
        return sorted(p for p in raiz.iterdir() if p.is_dir())
    except OSError:
        return []


def _vitrine_do_app_cita(bucket):
    dado = _ler(bucket / ".marketplaces.json")
    linhas = dado.get("rows") if isinstance(dado, dict) else None
    if not isinstance(linhas, list):
        return False
    return any(isinstance(linha, dict) and linha.get("name") == CATALOGO
               for linha in linhas)


def _pacote_do_app(bucket):
    """Pacote prometheus numa pasta de UUID. Devolve a versao, ou None.

    Envio por .zip entra na vitrine "My Uploads" e a pasta tem nome de UUID:
    o unico lugar onde o nome aparece e o plugin.json de dentro.
    """
    try:
        pastas = sorted(p for p in bucket.iterdir() if p.is_dir())
    except OSError:
        return None
    for pasta in pastas:
        manifesto = _ler(pasta / ".claude-plugin" / "plugin.json")
        if isinstance(manifesto, dict) and manifesto.get("name") == CATALOGO:
            versao = manifesto.get("version")
            return versao if isinstance(versao, str) else ""
    return None


def instalado_pelo_app(base=None):
    """O aplicativo conhece este catalogo nesta maquina?"""
    base = base or pasta_config()
    for bucket in _buckets_do_app(base):
        if _vitrine_do_app_cita(bucket) or _pacote_do_app(bucket) is not None:
            return True
    return False


def versao_instalada(base=None):
    """Versao que a pessoa tem de fato, ou None quando nao da para saber."""
    base = base or pasta_config()
    plugins = _pasta_plugins(base)

    registro = _ler(plugins / "installed_plugins.json")
    if isinstance(registro, dict):
        mapa = registro.get("plugins")
        if isinstance(mapa, dict):
            for chave, copias in mapa.items():
                if chave.split("@")[0] != CATALOGO or not isinstance(copias, list):
                    continue
                for copia in copias:
                    if isinstance(copia, dict) and isinstance(copia.get("version"), str):
                        return copia["version"]

    clone = _ler(plugins / "marketplaces" / CATALOGO / ".claude-plugin" / "plugin.json")
    if isinstance(clone, dict) and isinstance(clone.get("version"), str):
        return clone["version"]

    for bucket in _buckets_do_app(base):
        versao = _pacote_do_app(bucket)
        if versao:
            return versao
    return None


def _entrada_catalogo(dado):
    """known_marketplaces.json ja apareceu nas duas formas."""
    if not isinstance(dado, dict):
        return None
    mapa = dado.get("marketplaces") if isinstance(dado.get("marketplaces"), dict) else dado
    alvo = mapa.get(CATALOGO)
    return alvo if isinstance(alvo, dict) else None


def estado(base=None):
    """Devolve 'ligada', 'desligada', 'pelo app' ou 'nao instalado'.

    O terminal vem primeiro de proposito: quem tem os dois leva a resposta
    do caminho que este script consegue mudar.
    """
    base = base or pasta_config()

    cfg = _ler(base / "settings.json") or {}
    extra = cfg.get("extraKnownMarketplaces")
    if isinstance(extra, dict) and isinstance(extra.get(CATALOGO), dict):
        if CATALOGO in extra and "autoUpdate" in extra[CATALOGO]:
            return "ligada" if extra[CATALOGO]["autoUpdate"] else "desligada"

    conhecidos = _entrada_catalogo(_ler(_pasta_plugins(base) / "known_marketplaces.json"))
    if conhecidos is None and not (isinstance(extra, dict) and CATALOGO in extra):
        return "pelo app" if instalado_pelo_app(base) else "nao instalado"
    if conhecidos and "autoUpdate" in conhecidos:
        return "ligada" if conhecidos["autoUpdate"] else "desligada"
    return "desligada"


def ligar(base=None):
    """Liga nos dois lugares. Devolve a lista de arquivos alterados."""
    base = base or pasta_config()
    agora = estado(base)
    if agora == "pelo app":
        raise GerenciadoPeloApp(RECADO_DO_APP)
    if agora == "nao instalado":
        raise SemClaude(
            "O catalogo prometheus nao esta registrado nesta maquina. "
            "Instale o pacote primeiro."
        )

    alterados = []

    s = base / "settings.json"
    cfg = _ler(s)
    if isinstance(cfg, dict):
        extra = cfg.setdefault("extraKnownMarketplaces", {})
        if isinstance(extra, dict) and isinstance(extra.get(CATALOGO), dict):
            if extra[CATALOGO].get("autoUpdate") is not True:
                shutil.copy(str(s), str(s) + ".bak-elo")
                extra[CATALOGO]["autoUpdate"] = True
                s.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
                alterados.append(s.name)

    k = _pasta_plugins(base) / "known_marketplaces.json"
    dado = _ler(k)
    alvo = _entrada_catalogo(dado)
    if alvo is not None and alvo.get("autoUpdate") is not True:
        shutil.copy(str(k), str(k) + ".bak-elo")
        alvo["autoUpdate"] = True
        k.write_text(json.dumps(dado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        alterados.append(k.name)

    return alterados


def _main():
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    agora = estado()
    if agora == "nao instalado":
        print("O pacote prometheus nao esta instalado nesta maquina.")
        return 1

    versao = versao_instalada()
    tenho = ("Voce esta na versao %s." % versao) if versao else None

    if agora == "pelo app":
        print("Atualizacao automatica: quem controla e o aplicativo do Claude.")
        print(RECADO_DO_APP)
        if tenho:
            print(tenho)
        return 0

    if "--ligar" not in args:
        if agora == "ligada":
            print("Atualizacao automatica: LIGADA. As correcoes chegam sozinhas.")
        else:
            print("Atualizacao automatica: DESLIGADA.")
            print("Para ligar:  python3 atualizacao.py --ligar")
        if tenho:
            print(tenho)
        return 0

    if agora == "ligada":
        print("Ja estava ligada. Nada a fazer.")
        return 0

    mudou = ligar()
    print("Atualizacao automatica LIGADA.")
    if mudou:
        print("Alterado: %s (copia de seguranca .bak-elo ao lado)" % ", ".join(mudou))
    print("Vale a partir da proxima vez que o Claude for aberto.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(_main())
    except SemClaude as e:
        sys.exit("PARADO: %s" % e)
    except GerenciadoPeloApp as e:
        sys.exit("PARADO: %s" % e)
