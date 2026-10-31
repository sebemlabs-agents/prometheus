#!/usr/bin/env python3
"""Monta painel.html a partir dos arquivos de contrato presentes na pasta.

A skill coleta e grava; o painel le e formata. Este arquivo nunca chama a API.

Regras que o painel precisa cumprir (ver CONTRATO.md):
  - skill ausente nao e erro: o bloco simplesmente nao aparece;
  - fonte 'demo' aparece de forma visivel e permanente, nao em rodape;
  - toda lacuna e impressa com a explicacao em portugues;
  - a idade do dado aparece, porque dado de ontem lido como de hoje e decisao errada.

CLI:
    python3 painel.py            # le prometheus-*.json da pasta e grava painel.html

Compatibilidade: Python 3.8+.
"""
import html
import sys
import time
from pathlib import Path

import contrato

BASE = Path(__file__).resolve().parent

TITULOS = {
    "prometheus-pedidos": "Vendas e faturamento",
    "prometheus-promocoes": "Promoções terminando",
    "prometheus-devolucoes": "Reclamações e devoluções",
    "prometheus-anuncios": "Anúncios e estoque",
    "prometheus-visitas": "Conversão",
    "prometheus-recebiveis": "Dinheiro a receber",
    "prometheus-saude": "Saúde da conta",
    "prometheus-ads": "Anúncios pagos",
    "prometheus-avaliacoes": "Avaliações",
    "prometheus-concorrencia": "Concorrência",
}


def _e(txt):
    return html.escape(str(txt), quote=True)


def idade(gerado_em):
    """Texto curto com a idade do dado. Nunca esconde dado velho."""
    try:
        marca = time.strptime(gerado_em[:19], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        return "data de geração desconhecida"
    segundos = time.time() - time.mktime(marca)
    if segundos < 0:
        return "agora"
    minutos = int(segundos // 60)
    if minutos < 2:
        return "agora"
    if minutos < 60:
        return "há %d min" % minutos
    horas = int(minutos // 60)
    if horas < 24:
        return "há %d h" % horas
    return "há %d dia(s)" % int(horas // 24)


MARCAS_DE_DINHEIRO = (
    "valor", "preco", "custo", "imposto", "margem", "receita", "total", "taxa",
    "liquido", "bruto", "frete", "repasse", "desconto", "ticket", "receber",
    "liberado", "pago", "saldo",
)

MARCAS_DE_PERCENTUAL = ("percentual", "minimo", "maximo", "aliquota", "taxa_percentual")


def _e_dinheiro(chave):
    c = str(chave or "").lower()
    return any(m in c for m in MARCAS_DE_DINHEIRO)


def _e_percentual(chave):
    c = str(chave or "").lower()
    return any(m in c for m in MARCAS_DE_PERCENTUAL) or c.endswith("_pct")


def _numero(v, casas=2):
    """123456.7 -> 123.456,70 — separador de milhar, virgula decimal."""
    inteiro, _, decimal = ("%.*f" % (casas, v)).partition(".")
    sinal = "-" if inteiro.startswith("-") else ""
    inteiro = inteiro.lstrip("-")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro)
    junto = ".".join(grupos)
    return "%s%s,%s" % (sinal, junto, decimal) if decimal else "%s%s" % (sinal, junto)


def _reais(v):
    """O sinal vem antes do simbolo: -R$ 50,00, nunca R$ -50,00."""
    texto = _numero(abs(v))
    return "-R$ %s" % texto if v < 0 else "R$ %s" % texto


def _valor(v, chave=None):
    if v is None:
        return '<span class="vazio">não veio</span>'
    if isinstance(v, bool):
        return "sim" if v else "não"
    if isinstance(v, float):
        if _e_percentual(chave):
            texto = _numero(v, 2).rstrip("0").rstrip(",")
            return _e("%s%%" % texto)
        if _e_dinheiro(chave):
            return _e(_reais(v))
        return _e(_numero(v))
    if isinstance(v, int) and _e_dinheiro(chave):
        return _e(_reais(float(v)))
    if isinstance(v, (list, tuple)):
        return _e(", ".join(str(x) for x in v))
    if isinstance(v, dict):
        return _e("; ".join("%s: %s" % (k, x) for k, x in v.items()))
    return _e(v)


def bloco_resumo(resumo):
    if not resumo:
        return ""
    celulas = "".join(
        '<div class="kpi"><span class="rotulo">%s</span><strong>%s</strong></div>'
        % (_e(str(k).replace("_", " ")), _valor(v, k))
        for k, v in resumo.items()
    )
    return '<div class="kpis">%s</div>' % celulas


def bloco_itens(itens):
    if not itens:
        return '<p class="nada">Nada nesta janela.</p>'
    colunas = []
    for item in itens:
        if isinstance(item, dict):
            for k in item:
                if k not in colunas:
                    colunas.append(k)
    if not colunas:
        return "<ul>%s</ul>" % "".join("<li>%s</li>" % _valor(i) for i in itens)
    cabecalho = "".join("<th>%s</th>" % _e(c.replace("_", " ")) for c in colunas)
    linhas = []
    for item in itens:
        celulas = "".join("<td>%s</td>" % _valor(item.get(c), c) for c in colunas)
        linhas.append("<tr>%s</tr>" % celulas)
    return ('<div class="tabela"><table><thead><tr>%s</tr></thead><tbody>%s</tbody>'
            "</table></div>" % (cabecalho, "".join(linhas)))


def bloco_lacunas(dado):
    faltando = dado.get("faltando") or []
    if not faltando:
        return ""
    lacunas = dado.get("lacunas") or {}
    linhas = "".join(
        "<li><b>%s</b> não veio da API: %s</li>"
        % (_e(str(f).replace("_", " ")), _e(lacunas.get(f, "")))
        for f in faltando
    )
    return '<div class="lacunas"><p>O que falta neste bloco</p><ul>%s</ul></div>' % linhas


def bloco_avisos(dado):
    avisos = dado.get("avisos") or []
    if not avisos:
        return ""
    return '<div class="avisos">%s</div>' % "".join(
        "<span>%s</span>" % _e(a) for a in avisos
    )


def bloco_skill(dado):
    skill = dado.get("skill", "?")
    titulo = TITULOS.get(skill, skill)
    demo = dado.get("fonte") == "demo"
    periodo = dado.get("periodo") or {}
    recorte = ""
    if periodo.get("de") and periodo.get("ate"):
        recorte = " · %s a %s" % (_e(periodo["de"]), _e(periodo["ate"]))
    selo = '<span class="demo">dados de demonstração</span>' if demo else ""
    if dado.get("fonte") == "export":
        selo = '<span class="export">de planilha</span>'
    # Dado de arquivo tem duas idades. Mostrar so a do processamento faria
    # planilha de semana passada parecer leitura de agora.
    captura = ""
    if dado.get("capturado_em"):
        captura = " · arquivo de %s" % _e(idade(dado["capturado_em"]))
    return """
<section class="bloco%s">
  <header>
    <h2>%s %s</h2>
    <p class="meta">%s%s · atualizado %s%s</p>
  </header>
  %s
  %s
  %s
  %s
</section>""" % (
        " em-demo" if demo else "",
        _e(titulo),
        selo,
        _e(skill),
        recorte,
        _e(idade(dado.get("gerado_em"))),
        captura,
        bloco_resumo(dado.get("resumo")),
        bloco_lacunas(dado),
        bloco_itens(dado.get("itens")),
        bloco_avisos(dado),
    )


ESTILO = """
/* Identidade cosmic: neutros predominantes, indigo e violeta pontuais,
   superficies suaves. O universo fica so na entrada, nunca sobre dados. */
:root{
  --papel:#f6f6f8;--carta:#fff;--tinta:#202024;--tinta2:#686872;--tinta3:#8b8b96;
  --linha:#e1e1e7;--campo:#f8f8fa;--suave:#ededf3;--brilho:#818cf830;--anel:#b8b9d0;
  --acento:#27272d;--sobre-acento:#fff;--indigo:#4b53a4;--indigo-forte:#3c4390;
  --indigo-suave:#eceefa;--violeta:#6d4fc4;--violeta-suave:#f2eefc;
  --sombra:0 24px 70px #1515250a,0 2px 5px #15152504;
  --r-carta:20px;--r-suave:14px;--r-controle:11px;
}
@media (prefers-color-scheme:dark){:root{
  --papel:#0d0d10;--carta:#17171c;--tinta:#f4f4f7;--tinta2:#a4a4b0;--tinta3:#7c7c8a;
  --linha:#32323b;--campo:#111115;--suave:#25252e;--brilho:#6366f138;--anel:#424254;
  --acento:#f0f0f5;--sobre-acento:#15151b;--indigo:#818cf8;--indigo-forte:#a5adfb;
  --indigo-suave:#1b1c2e;--violeta:#a78bfa;--violeta-suave:#231c38;
  --sombra:0 24px 80px #0004,0 1px 0 #ffffff07 inset;
  color-scheme:dark;
}}
*{box-sizing:border-box}
body{margin:0;background:var(--papel);color:var(--tinta);
font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
font-optical-sizing:auto;-webkit-font-smoothing:antialiased}
.pagina{max-width:1040px;margin:0 auto;padding:0 20px 96px}

/* entrada */
.cabeca{position:relative;isolation:isolate;overflow:hidden;
padding:56px 0 28px;border-bottom:1px solid var(--linha);margin-bottom:4px}
.cabeca::before{content:"";position:absolute;z-index:-1;top:-220px;right:-180px;
width:520px;height:520px;border-radius:50%;
background:radial-gradient(ellipse,var(--brilho),transparent 65%);pointer-events:none}
h1{font-size:clamp(1.9rem,4.4vw,2.8rem);font-weight:550;letter-spacing:-.045em;
line-height:1.05;margin:0}
.cabeca p{margin:10px 0 0;color:var(--tinta2);font-size:.95rem}
.so-leitura{display:inline-block;margin-top:18px;padding:6px 14px;border-radius:30px;
background:var(--indigo-suave);color:var(--indigo-forte);font-size:.78rem;font-weight:600}

/* blocos */
.bloco{background:var(--carta);border:1px solid var(--linha);border-radius:var(--r-carta);
padding:26px 28px;margin-top:18px;box-shadow:var(--sombra)}
.bloco.em-demo{border-color:transparent;background:var(--violeta-suave);box-shadow:none}
.bloco h2{font-size:1.2rem;font-weight:600;letter-spacing:-.025em;margin:0}
.demo{display:inline-block;font-size:.68rem;font-weight:650;letter-spacing:.05em;
text-transform:uppercase;background:var(--violeta);color:#fff;padding:3px 10px;
border-radius:30px;vertical-align:middle;margin-left:8px}
.export{display:inline-block;font-size:.68rem;font-weight:650;letter-spacing:.05em;
text-transform:uppercase;background:var(--indigo-suave);color:var(--indigo-forte);
padding:3px 10px;border-radius:30px;vertical-align:middle;margin-left:8px}
.meta{margin:5px 0 0;color:var(--tinta3);font-size:.82rem}

/* numeros */
.kpis{display:flex;flex-wrap:wrap;gap:10px;margin:20px 0 0}
.kpi{background:var(--campo);border:1px solid var(--linha);border-radius:var(--r-suave);
padding:14px 18px;min-width:140px}
.bloco.em-demo .kpi{background:var(--carta);border-color:transparent}
.kpi .rotulo{display:block;font-size:.76rem;color:var(--tinta2);margin-bottom:3px}
.kpi strong{font-size:1.5rem;font-weight:550;letter-spacing:-.035em;
font-variant-numeric:tabular-nums;line-height:1.1}

/* o que nao veio */
.lacunas{background:var(--violeta-suave);padding:16px 20px;margin:18px 0 0;
border-radius:var(--r-suave)}
.bloco.em-demo .lacunas{background:var(--carta)}
.lacunas p{margin:0 0 6px;font-size:.68rem;text-transform:uppercase;font-weight:650;
letter-spacing:.12em;color:var(--violeta)}
.lacunas ul{margin:0;padding-left:1.1em;font-size:.89rem;color:var(--tinta2)}

/* tabela */
.tabela{overflow-x:auto;border:1px solid var(--linha);border-radius:var(--r-suave);
margin-top:20px}
.bloco.em-demo .tabela{border-color:transparent;background:var(--carta)}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th,td{text-align:left;padding:13px 16px;border-top:1px solid var(--linha);
vertical-align:top}
thead th{border-top:0;font-size:.68rem;text-transform:uppercase;font-weight:650;
letter-spacing:.12em;color:var(--tinta3);padding-block:15px 9px}
tbody tr:hover{background:var(--campo)}
.bloco.em-demo tbody tr:hover{background:transparent}
.vazio{color:var(--tinta3);font-style:italic}
.nada{color:var(--tinta2);font-size:.9rem;margin:18px 0 0}

/* avisos */
.avisos{margin-top:18px;display:flex;flex-wrap:wrap;gap:6px}
.avisos span{font-size:.75rem;background:var(--suave);border-radius:30px;
padding:5px 12px;color:var(--tinta2)}
.bloco.em-demo .avisos span{background:var(--carta)}

.vazio-geral{background:var(--carta);border:1px dashed var(--anel);
border-radius:var(--r-carta);padding:40px 32px;margin-top:18px;color:var(--tinta2)}
.vazio-geral b{color:var(--tinta);font-size:1.05rem}
.vazio-geral p{margin:8px 0 0}

footer{margin-top:40px;padding-top:18px;border-top:1px solid var(--linha);
color:var(--tinta3);font-size:.82rem}
footer code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.8rem}
@media print{body{background:#fff}.cabeca::before{display:none}
.bloco,.kpi,.tabela{break-inside:avoid}}
"""


def render(dados):
    """HTML do painel a partir de uma lista de arquivos de contrato."""
    conta = {}
    for d in dados:
        if d.get("conta", {}).get("id"):
            conta = d["conta"]
            break

    if dados:
        corpo = "".join(bloco_skill(d) for d in dados)
    else:
        corpo = (
            '<div class="vazio-geral"><b>Nenhuma skill rodou ainda.</b>'
            "<p>Depois de conectar a conta, rode uma das skills do pacote. "
            "Cada uma grava um arquivo nesta pasta e aparece aqui como um bloco.</p></div>"
        )

    titulo = "Painel Elo"
    quem = ""
    if conta:
        quem = "%s · conta %s" % (
            _e(conta.get("apelido") or "sem apelido"),
            _e(conta.get("id")),
        )

    return """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s</title><style>%s</style></head>
<body><div class="pagina">
<div class="cabeca">
  <h1>%s</h1>
  <p>%s</p>
  <span class="so-leitura">somente leitura · nada é alterado na sua conta</span>
</div>
%s
<footer>Gerado por painel.py a partir dos arquivos desta pasta. Para atualizar,
rode a skill de novo e depois <code>python3 painel.py</code>.</footer>
</div></body></html>
""" % (_e(titulo), ESTILO, _e(titulo), quem, corpo)


def _main():
    pasta = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE
    dados = contrato.carregar_todos(pasta)
    alvo = pasta / "painel.html"
    alvo.write_text(render(dados), encoding="utf-8")
    if not dados:
        print("Nenhum arquivo de skill encontrado em %s." % pasta)
        print("Painel criado vazio em %s — rode uma skill e gere de novo." % alvo.name)
        print("Abrir: %s" % alvo.resolve().as_uri())
        return 0
    nomes = ", ".join(d.get("skill", "?") for d in dados)
    print("Painel gerado: %s" % alvo)
    print("Abrir: %s" % alvo.resolve().as_uri())
    print("Blocos: %s" % nomes)
    demo = [d.get("skill") for d in dados if d.get("fonte") == "demo"]
    if demo:
        print("Atencao: em dados de demonstracao: %s" % ", ".join(demo))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
