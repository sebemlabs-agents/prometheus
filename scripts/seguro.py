#!/usr/bin/env python3
"""Primitivas de seguranca que todos os canais compartilham.

Tres problemas que nenhum canal resolve sozinho, levantados na revisao
cross-vendor de 22/10/2026:

1. Gravar segredo em dois tempos. `write_text` seguido de `chmod` deixa o
   arquivo legivel por outros usuarios durante um instante. Em maquina de uso
   compartilhado — recepcao, balcao, computador de familia — esse instante
   basta. `gravar_protegido` cria o arquivo ja restrito e so entao o coloca
   no lugar, de uma vez.

2. urllib reenvia cabecalho em redirecionamento. Se o servidor responder 302
   para outro endereco, o `Authorization: Bearer ...` vai junto, para um host
   que a gente nao escolheu. `abrir` recusa redirecionamento em qualquer
   chamada que leve credencial.

3. O retorno do navegador chega colado a mao. Conferir que ele veio do mesmo
   endereco que foi cadastrado evita trocar por token um `?code=` que a pessoa
   copiou de outro lugar — e, no uso normal, pega o erro mais comum: colar a
   URL errada.

4. Refresh token de uso unico + duas execucoes na mesma pasta = conexao morta
   horas depois, parecendo falha de rede. `trava` da exclusao ENTRE PROCESSOS
   para o trecho ler->renovar->gravar. Sem ela, comparar o refresh antes de
   gravar nao e condicional de verdade: sobra corrida entre comparar e escrever.

Compatibilidade: Python 3.8+, sem dependencia externa.
"""
import contextlib
import errno
import os
import tempfile
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

try:                      # POSIX (Mac, Linux)
    import fcntl
    _msvcrt = None
except ImportError:       # Windows
    fcntl = None
    import msvcrt as _msvcrt


class RedirecionamentoRecusado(RuntimeError):
    """O servidor pediu para reenviar a credencial a outro endereco."""


class RetornoDeOutroEndereco(ValueError):
    """O endereco colado nao e o mesmo que foi cadastrado no canal."""


class _SemRedirecionamento(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RedirecionamentoRecusado(
            "O servidor respondeu com um redirecionamento (HTTP %s), e seguir "
            "esse redirecionamento reenviaria a sua credencial para outro "
            "endereco. Recusei antes de reenviar. Se isso insistir, o problema "
            "esta do lado do canal — nao e erro seu." % code
        )


_ABRIDOR = urllib.request.build_opener(_SemRedirecionamento)


def abrir(req, timeout=30):
    """urlopen que NAO segue redirecionamento.

    Use em toda chamada que leve credencial — token, assinatura ou segredo
    de cliente. Erros HTTP continuam chegando como urllib.error.HTTPError,
    igual ao urlopen, para o tratamento de cada canal seguir funcionando."""
    return _ABRIDOR.open(req, timeout=timeout)


def fechado(arquivo):
    """Diz se o arquivo esta de fato fora do alcance de grupo e de outros.

    Mede o resultado em vez de confiar no chmod: e a unica forma de o relato
    ser verdadeiro nos dois sistemas."""
    try:
        return os.stat(arquivo).st_mode & 0o077 == 0
    except OSError:
        return False


def gravar_protegido(destino, conteudo):
    """Grava arquivo de segredo ja restrito ao dono, sem janela de exposicao.

    Escreve num temporario na MESMA pasta — para a substituicao ser atomica —
    com a permissao fechada desde a abertura, e so depois substitui o destino.
    Se a maquina cair no meio, o destino continua com o conteudo anterior
    inteiro; nunca truncado.

    Devolve {"protegido": bool, "motivo": str|None}. Nao recusa gravar quando
    nao consegue confirmar a restricao: no Windows a permissao e controlada por
    outro mecanismo, que este pacote ainda nao le, e recusar deixaria todo
    usuario de Windows sem conexao. Quem chama avisa a pessoa."""
    destino = Path(destino)
    dados = conteudo.encode("utf-8") if isinstance(conteudo, str) else conteudo
    fd, tmp = tempfile.mkstemp(dir=str(destino.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(dados)
            # Substituicao atomica garante que o destino nunca fica truncado,
            # mas NAO garante que o conteudo novo chegou ao disco. Sem isto, uma
            # queda de energia logo depois de renovar pode deixar o refresh
            # antigo no disco — e ele ja foi consumido.
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(destino))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    if fechado(destino):
        return {"protegido": True, "motivo": None}
    try:
        os.chmod(destino, 0o600)
    except OSError:
        return {"protegido": False, "motivo": "sem_permissao_para_mudar"}
    if fechado(destino):
        return {"protegido": True, "motivo": None}
    return {"protegido": False, "motivo": "nao_verificado_neste_sistema"}


class EnderecoIlegivel(ValueError):
    """Nao deu para entender o endereco colado."""


def _partes(endereco):
    """Quebra o endereco em partes comparaveis.

    Cuidado nao obvio: em `https://host:porta-invalida/`, o `.port` do urllib
    levanta ValueError com o TEXTO colado dentro da mensagem. Como quem chama
    imprime a excecao, essa mensagem levaria o endereco — e o `?code=` dele —
    para a tela e para a gravacao de video. Entao o erro e trocado por um
    nosso, sem interpolar nada."""
    try:
        p = urllib.parse.urlparse(endereco)
        porta = p.port
    except ValueError:
        raise EnderecoIlegivel(
            "Nao consegui entender esse endereco. Cole a barra do navegador "
            "inteira, sem editar nada, e salve o arquivo."
        )
    host = (p.hostname or "").lower().rstrip(".")
    esquema = p.scheme.lower()
    porta = porta or (443 if esquema == "https" else 80 if esquema == "http" else None)
    caminho = (p.path or "/").rstrip("/") or "/"
    return esquema, host, porta, caminho


def resumo(endereco):
    """So esquema, host e caminho — nunca a query, que carrega o code."""
    e, h, _, c = _partes(endereco)
    return "%s://%s%s" % (e, h, c) if h else "(endereco nao reconhecido)"


def conferir_origem(endereco, cadastrado):
    """Recusa retorno que nao veio do dominio cadastrado no canal.

    Compara esquema, host e porta. NAO compara o caminho, e isso foi aprendido
    num ensaio em 22/10/2026: o endereco cadastrado era a raiz de um aplicativo
    real, e o aplicativo redirecionou a visita sem sessao para /login. O
    dominio estava certo; so o caminho mudou no meio. Exigir o caminho fazia o
    pacote recusar um retorno legitimo.

    O dominio e onde mora a protecao: quem controla outro caminho no dominio da
    pessoa ja esta dentro. Nunca ecoa a query, que carrega o code."""
    e1, h1, p1, _ = _partes(endereco)
    e2, h2, p2, _ = _partes(cadastrado)
    if (e1, h1, p1) != (e2, h2, p2):
        raise RetornoDeOutroEndereco(
            "Esse endereco nao veio de onde deveria. O canal foi cadastrado "
            "para devolver em %s, e o que voce colou e de %s.\n"
            "Cole a barra do navegador da pagina que abriu DEPOIS de autorizar "
            "- nao o endereco de outra aba." % (resumo(cadastrado), resumo(endereco))
        )
    return True


# --------------------------------------------------------------------- trava
#
# Exclusao entre processos para renovar credencial [LST-17861].
#
# Tres decisoes que parecem detalhe e nao sao:
#
# 1. A trava fica em arquivo PROPRIO, nunca no arquivo de segredo. O segredo e
#    substituido por `os.replace` na gravacao atomica: travar o proprio arquivo
#    perderia a trava junto com o inode, no meio do trecho protegido.
# 2. O arquivo de trava NAO e apagado ao liberar. Apagar abre janela: outro
#    processo cria um inode novo e entra junto.
# 3. A trava NAO tem vencimento. Vencer enquanto o primeiro ainda espera a
#    resposta do provedor e o mesmo que nao ter trava.


class TravaOcupada(RuntimeError):
    """Outra execucao esta renovando a credencial nesta pasta."""


# "ocupado" e "este sistema nao sabe travar" chegam os dois como OSError, e
# confundir os dois tem consequencia grave nas duas direcoes: tratar
# nao-suportado como ocupado faz a renovacao esperar e FALHAR em pasta de rede
# ou monte exotico, onde hoje funciona; tratar ocupado como nao-suportado faz a
# trava deixar de travar.
_NAO_SUPORTADO = {
    getattr(errno, nome) for nome in
    ("ENOTSUP", "EOPNOTSUPP", "EINVAL", "ENOLCK", "ENOSYS", "EPERM", "EBADF")
    if hasattr(errno, nome)
}

_avisou_sem_trava = set()


def _avisar_sem_trava(alvo, motivo):
    """Avisa uma vez por processo, no stderr (stdout e saida de dado)."""
    if alvo in _avisou_sem_trava:
        return
    _avisou_sem_trava.add(alvo)
    print(
        "aviso: nao deu para usar a trava de renovacao nesta pasta (%s). Sigo sem "
        "ela — e o mesmo comportamento de antes da trava existir. Nao rode duas "
        "coisas ao mesmo tempo nesta pasta." % motivo,
        file=sys.stderr,
    )


_abertas = {}
_guarda = threading.Lock()


def caminho_da_trava(credencial):
    """Arquivo de trava correspondente a um arquivo de credencial."""
    p = Path(credencial)
    return p.parent / ("." + p.name + ".trava")


def trava_em_uso(credencial):
    """Diz se ESTE processo esta dentro da trava. Para testes e diagnostico."""
    with _guarda:
        return str(caminho_da_trava(credencial).resolve()) in _abertas


def _tentar_travar(fd):
    if fcntl is not None:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    else:
        # Posicao e tamanho constantes: no Windows a regiao travada tem de ser
        # sempre a mesma, senao dois processos travam regioes diferentes do
        # mesmo arquivo e nenhum espera pelo outro.
        os.lseek(fd, 0, os.SEEK_SET)
        _msvcrt.locking(fd, _msvcrt.LK_NBLCK, 1)


def _destravar(fd):
    if fcntl is not None:
        fcntl.flock(fd, fcntl.LOCK_UN)
    else:
        os.lseek(fd, 0, os.SEEK_SET)
        _msvcrt.locking(fd, _msvcrt.LK_UNLCK, 1)


@contextlib.contextmanager
def _trava_real(credencial, timeout=30):
    alvo = caminho_da_trava(credencial)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    chave = str(alvo.resolve())

    with _guarda:
        estado = _abertas.get(chave)
        if estado is not None:
            # Reentrante: `renovar()` e o caminho forcado passam pela mesma
            # trava. Sem isto o processo travaria a si mesmo.
            estado[0] += 1
            reentrou = True
        else:
            reentrou = False
    if reentrou:
        try:
            yield
        finally:
            with _guarda:
                estado = _abertas.get(chave)
                if estado is not None:
                    estado[0] -= 1
        return

    try:
        fd = os.open(str(alvo), os.O_CREAT | os.O_RDWR, 0o600)
    except OSError as e:
        # Nem o arquivo de trava da para criar. Quem explica o problema de
        # verdade e o `pode_gravar` de quem chamou, com mensagem util — nao um
        # erro cru de abertura de arquivo. Segue sem trava.
        _avisar_sem_trava(chave, "nao deu para criar %s" % alvo.name)
        yield
        return
    limite = time.time() + max(0, timeout)
    try:
        while True:
            try:
                _tentar_travar(fd)
                break
            except OSError as e:
                if e.errno in _NAO_SUPORTADO:
                    # Este sistema de arquivos nao faz trava. Esperar e depois
                    # falhar quebraria quem hoje funciona.
                    _avisar_sem_trava(chave, "o sistema de arquivos nao suporta")
                    yield
                    return
                if time.time() >= limite:
                    raise TravaOcupada(
                        "Outra execucao esta renovando a credencial nesta pasta. "
                        "Espere ela terminar e rode de novo — nao rode duas ao "
                        "mesmo tempo na mesma pasta."
                    )
                time.sleep(0.1)
        with _guarda:
            _abertas[chave] = [1, fd]
        try:
            yield
        finally:
            with _guarda:
                estado = _abertas.get(chave)
                if estado is not None:
                    estado[0] -= 1
                    if estado[0] <= 0:
                        _abertas.pop(chave, None)
            _destravar(fd)
    finally:
        os.close(fd)


def trava(credencial, timeout=30):
    """Exclusao entre processos para o trecho ler->renovar->gravar.

    Quem espera e entra depois deve RELER a credencial: normalmente o par ja
    foi renovado por quem estava dentro, e mandar o refresh lido antes seria
    mandar um token de uso unico ja consumido.

    O arquivo de trava e separado, permanente e sem vencimento — ver o bloco de
    comentarios acima para o porque de cada uma dessas tres coisas."""
    return _trava_real(credencial, timeout)


def pode_gravar(destino):
    """Diz se a pasta aceita a gravacao atomica, SEM tocar no arquivo atual.

    Serve para nao consumir um refresh de uso unico e descobrir depois que o par
    novo nao tem onde ser guardado. Nao garante a gravacao futura — reduz a
    falha previsivel (pasta sem permissao, caminho que nao existe, disco cheio
    no momento da conferencia)."""
    destino = Path(destino)
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(destino.parent), prefix=".teste-")
    except OSError:
        return False
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(b"x")
            f.flush()
            os.fsync(f.fileno())
        return True
    except OSError:
        return False
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def gravar_insistindo(destino, conteudo, tentativas=3, espera=0.2):
    """`gravar_protegido` com algumas tentativas.

    Recebido um par valido do provedor, insistir na GRAVACAO e correto: o par ja
    existe e perde-lo mata a conexao. Repetir a CHAMADA ao provedor, nunca — o
    refresh e de uso unico."""
    ultima = None
    for n in range(max(1, tentativas)):
        try:
            return gravar_protegido(destino, conteudo)
        except OSError as e:
            ultima = e
            if n + 1 < tentativas:
                time.sleep(espera)
    raise ultima
