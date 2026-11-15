"""Gravação segura do projeto.yaml e dos arquivos de estado: o lugar único por onde o app grava.

Por que existe (15/11/2026): o painel atende o Mac e o iPhone ao mesmo tempo (um fio por pedido) e as tarefas rodam
em outro processo. Gravar direto com write_text tinha três defeitos:
  1. o arquivo ficava vazio por um instante durante a gravação: quem lesse nesse instante via um projeto em branco e,
     se salvasse em seguida, gravava o projeto em branco por cima;
  2. dois salvamentos ao mesmo tempo (ler, mudar um campo, gravar) apagavam a mudança um do outro;
  3. trabalho/projeto.yaml.anterior só guardava o último salvamento: com o salvamento automático, o projeto de dez
     minutos atrás já não existia mais.

O que este módulo garante:
  gravar_texto     troca atômica (arquivo temporário na mesma pasta + os.replace): ou o arquivo antigo, ou o novo
  trava            uma gravação por vez no mesmo projeto (dentro do painel e entre o painel e as tarefas)
  gravar_projeto   projeto.yaml com a cópia anterior e um retrato em trabalho/historico/ (nada é apagado)
  historico, restaurar   a lista dos retratos e a volta para um deles (python3 -m divine_studio restaurar <pasta>)

O intervalo entre retratos fica em config/preferencias.yaml > historico_projeto.
"""
from __future__ import annotations

import contextlib
import os
import threading
import time
from pathlib import Path

try:                                   # Mac e Linux; sem fcntl a trava vale só dentro do painel
    import fcntl
except ImportError:                    # pragma: no cover
    fcntl = None

_TRAVAS: dict = {}
_GUARDA = threading.Lock()
_LOCAL = threading.local()


def gravar_texto(arq: Path, texto: str) -> None:
    """Grava por troca atômica: quem lê nunca encontra o arquivo pela metade."""
    arq = Path(arq)
    arq.parent.mkdir(parents=True, exist_ok=True)
    tmp = arq.with_name(f".{arq.name}.{os.getpid()}.{threading.get_ident()}.gravando")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(texto)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, arq)
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


@contextlib.contextmanager
def trava(pasta: Path):
    """Uma gravação por vez no projeto. Pode ser pedida de novo por quem já a tem (salvar_dados chama salvar_yaml)."""
    pasta = Path(pasta)
    chave = str(pasta.resolve())
    with _GUARDA:
        lock = _TRAVAS.setdefault(chave, threading.RLock())
    with lock:
        fundo = getattr(_LOCAL, "fundo", None)
        if fundo is None:
            fundo = _LOCAL.fundo = {}
        fh = None
        if not fundo.get(chave) and fcntl is not None:
            try:                       # entre processos: o painel e a tarefa (edição automática, prévia) do projeto
                (pasta / "trabalho").mkdir(exist_ok=True)
                fh = open(pasta / "trabalho" / ".projeto.lock", "w")
                fcntl.flock(fh, fcntl.LOCK_EX)
            except OSError:
                fh = None
        fundo[chave] = fundo.get(chave, 0) + 1
        try:
            yield
        finally:
            fundo[chave] -= 1
            if fh is not None:
                with contextlib.suppress(OSError):
                    fcntl.flock(fh, fcntl.LOCK_UN)
                fh.close()


def _intervalo_s() -> float:
    try:
        from .config import load
        return 60.0 * float((load("preferencias").get("historico_projeto") or {}).get("intervalo_min", 10))
    except Exception:
        return 600.0


def historico(pasta: Path) -> list:
    """Retratos guardados do projeto.yaml, do mais novo para o mais antigo."""
    out = []
    for f in sorted((Path(pasta) / "trabalho" / "historico").glob("projeto_*.yaml"), reverse=True):
        out.append({"arquivo": f.name, "quando": time.strftime("%d/%m/%Y %H:%M", time.localtime(f.stat().st_mtime)),
                    "bytes": f.stat().st_size})
    return out


def _retrato(pasta: Path, texto: str, forcar: bool = False) -> None:
    dest = pasta / "trabalho" / "historico"
    ultimos = sorted(dest.glob("projeto_*.yaml")) if dest.exists() else []
    if ultimos and not forcar and time.time() - ultimos[-1].stat().st_mtime < _intervalo_s():
        return
    if ultimos and ultimos[-1].read_text(encoding="utf-8") == texto:
        return                                         # nada mudou desde o último retrato
    nome = f"projeto_{time.strftime('%Y%m%d-%H%M%S')}.yaml"
    k = 1
    while (dest / nome).exists():                      # dois retratos no mesmo segundo: nenhum some
        k += 1
        nome = f"projeto_{time.strftime('%Y%m%d-%H%M%S')}-{k}.yaml"
    gravar_texto(dest / nome, texto)


def gravar_projeto(pasta: Path, texto: str, anterior: bool = True) -> Path:
    """Grava o projeto.yaml inteiro; o que estava antes fica em trabalho/ (anterior e histórico)."""
    pasta = Path(pasta)
    arq = pasta / "projeto.yaml"
    if not texto.endswith("\n"):
        texto += "\n"
    with trava(pasta):
        if arq.exists():
            velho = arq.read_text(encoding="utf-8")
            if velho == texto:
                return arq
            if velho.strip():
                _retrato(pasta, velho)
                if anterior:
                    gravar_texto(pasta / "trabalho" / "projeto.yaml.anterior", velho)
        gravar_texto(arq, texto)
    return arq


def restaurar(pasta: Path, arquivo: str | None = None) -> str:
    """Volta o projeto.yaml para um retrato (sem nome: o mais novo). O atual vira um retrato antes, nada se perde."""
    import yaml
    pasta = Path(pasta)
    lista = historico(pasta)
    if not lista:
        raise ValueError("este projeto ainda não tem histórico guardado")
    nome = Path(arquivo).name if arquivo else lista[0]["arquivo"]
    origem = pasta / "trabalho" / "historico" / nome
    if not origem.is_file() or nome not in {x["arquivo"] for x in lista}:
        raise ValueError("retrato não encontrado no histórico")
    texto = origem.read_text(encoding="utf-8")
    yaml.safe_load(texto)                              # retrato ilegível não substitui o projeto
    with trava(pasta):
        arq = pasta / "projeto.yaml"
        if arq.exists() and arq.read_text(encoding="utf-8").strip():
            _retrato(pasta, arq.read_text(encoding="utf-8"), forcar=True)
        gravar_texto(arq, texto)
    return nome
