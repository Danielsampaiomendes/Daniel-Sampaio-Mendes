"""Instala a transcrição (o app passa a entender a sua fala) e deixa o painel no Python certo.

O Python que vem com o Mac (Xcode, 3.9, pip 21) não instala as bibliotecas novas. Este instalador:
  1. arranja o uv (instalador rápido): pip do Mac, ou o instalador oficial do uv, ou o que já existir
  2. cria o Python próprio do app (3.12, em .venv); sem uv, tenta o Python do Homebrew
  3. instala as bibliotecas uma por uma (uma falha não derruba as outras) e confere a transcrição
  4. baixa já o modelo de fala (a primeira edição não fica parada baixando)
Depois o painel reinicia sozinho no Python novo. Roda pelo botão "Instalar a transcrição agora" ou:
  python3 -m divine_studio instalar-fala
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .config import ROOT, load

VENV = ROOT / ".venv"


def _py_venv() -> Path:
    return VENV / "bin" / "python"


def _passo(msg: str) -> None:
    print(f"• {msg}", flush=True)


def _ok_import(py: str, modulos: str) -> bool:
    try:
        return subprocess.run([py, "-c", f"import {modulos}"], capture_output=True, timeout=120).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def no_python_do_app() -> bool:
    """O painel já está rodando no Python próprio do app?"""
    try:
        return Path(sys.prefix).resolve() == VENV.resolve()
    except OSError:
        return False


def estado() -> dict:
    """O que o painel mostra quando o app ainda não entende a fala."""
    from .transcricao import modelo_escolhido, motor_disponivel, preciso_baixado
    venv_ok = _py_venv().exists() and _ok_import(str(_py_venv()), "faster_whisper")
    return {"transcricao": bool(motor_disponivel()), "python": sys.version.split()[0],
            "no_python_do_app": no_python_do_app(), "venv": _py_venv().exists(), "venv_com_fala": venv_ok,
            "precisa_reiniciar": venv_ok and not no_python_do_app(),
            "preciso": motor_disponivel() != "faster_whisper" or preciso_baixado(),
            "modelo": modelo_escolhido() if motor_disponivel() == "faster_whisper" else motor_disponivel()}


def _uv() -> list:
    from . import atualizar
    cmd = atualizar._uv()
    if cmd:
        return cmd
    for cand in (Path.home() / ".local" / "bin" / "uv", Path.home() / ".cargo" / "bin" / "uv", Path("/opt/homebrew/bin/uv"),
                 Path("/usr/local/bin/uv")):
        if cand.exists():
            return [str(cand)]
    return []


def arranjar_uv() -> list:
    cmd = _uv()
    if cmd:
        return cmd
    _passo("Instalando o uv (instalador rápido de Python)…")
    subprocess.run([sys.executable, "-m", "pip", "install", "--user", "-q", "uv"])
    cmd = _uv()
    if cmd:
        return cmd
    if shutil.which("curl"):
        _passo("Tentando o instalador oficial do uv…")
        subprocess.run("curl -LsSf https://astral.sh/uv/install.sh | sh", shell=True)
        cmd = _uv()
    return cmd


def criar_python() -> bool:
    if _py_venv().exists() and _ok_import(str(_py_venv()), "sys"):
        _passo(f"Python do app já existe ({_py_venv()}).")
        return True
    uv = arranjar_uv()
    if uv:
        _passo("Criando o Python 3.12 do app (baixa uma vez, 1 a 2 minutos)…")
        r = subprocess.run([*uv, "venv", "--seed", "--python", "3.12", str(VENV)])
        if r.returncode == 0 and _py_venv().exists():
            return True
        shutil.rmtree(VENV, ignore_errors=True)
    for py in ("/opt/homebrew/bin/python3.12", "/usr/local/bin/python3.12", shutil.which("python3.12") or "",
               "/opt/homebrew/bin/python3.11", "/usr/local/bin/python3.11", shutil.which("python3.11") or ""):
        if py and Path(py).exists():
            _passo(f"Criando o Python do app a partir de {py}…")
            if subprocess.run([py, "-m", "venv", str(VENV)]).returncode == 0:
                return True
    if shutil.which("brew"):
        _passo("Instalando o Python 3.12 pelo Homebrew (alguns minutos)…")
        if subprocess.run(["brew", "install", "python@3.12"]).returncode == 0:
            for py in ("/opt/homebrew/bin/python3.12", "/usr/local/bin/python3.12"):
                if Path(py).exists() and subprocess.run([py, "-m", "venv", str(VENV)]).returncode == 0:
                    return True
    return False


def instalar_bibliotecas(py: str) -> list:
    """Instala o requirements.txt no Python do app, uma por uma. Devolve as que falharam."""
    req = ROOT / "requirements.txt"
    pacotes = [ln.split("#")[0].strip() for ln in req.read_text(encoding="utf-8").splitlines()]
    pacotes = [x for x in pacotes if x and not x.startswith("-")]
    uv = _uv()
    falhas = []
    for pac in pacotes:
        nome = pac.split(">")[0].split("=")[0]
        _passo(f"Instalando {nome}…")
        cmd = [*uv, "pip", "install", "--python", py, "-q", pac] if uv else [py, "-m", "pip", "install", "-q", pac]
        if subprocess.run(cmd).returncode != 0:
            falhas.append(nome)
            print(f"  ✗ {nome} não instalou", flush=True)
    return falhas


def baixar_modelo(py: str, preciso: bool = False) -> bool:
    """Baixa o modelo rápido (instalação) ou o preciso (botão 🎯 Transcrição mais precisa, ~1,6 GB)."""
    t = load("preferencias").get("transcricao") or {}
    modelo = t.get("modelo_whisper", "auto")
    if modelo == "auto" or preciso:
        modelo = t.get("modelo_preciso", "large-v3-turbo") if preciso else t.get("modelo_reserva", "small")
    _passo(f"Baixando o modelo de fala '{modelo}' (uma vez; {'cerca de 1,6 GB, 5 a 20 minutos' if preciso else 'algumas centenas de MB'})…")
    r = subprocess.run([py, "-c", f"from faster_whisper import WhisperModel; WhisperModel('{modelo}', device='auto', "
                                  "compute_type='int8'); print('modelo pronto')"], capture_output=True, text=True)
    if r.returncode != 0:                    # sem o rastro técnico na tela: só a última linha do erro
        print("  " + ((r.stderr or r.stdout).strip().splitlines() or ["erro"])[-1][:200], flush=True)
    return r.returncode == 0


def main(preciso: bool = False) -> int:
    if preciso:                              # só o modelo preciso, no Python do app que já existe
        py = str(_py_venv()) if _py_venv().exists() else sys.executable
        if not baixar_modelo(py, preciso=True):
            print("\n✗ O modelo preciso não baixou (internet?). As edições continuam com o rápido.", flush=True)
            return 1
        try:                                 # baixou de novo: tenta o preciso outra vez, mesmo que antes tenha ficado lento
            from .transcricao import _estado_arq
            _estado_arq().write_text("{}", encoding="utf-8")
        except OSError:
            pass
        print("\n✓ Pronto: as próximas edições usam a transcrição mais precisa.", flush=True)
        return 0
    print(f"Python do painel agora: {sys.version.split()[0]} ({sys.executable})", flush=True)
    if not criar_python():
        print("\n✗ Não consegui criar o Python do app. Copie esta tela e mande para o Claude.\n"
              "  Alternativa sem instalar nada: transcrição na nuvem com uma chave da AssemblyAI (ASSEMBLYAI_API_KEY).")
        return 1
    py = str(_py_venv())
    falhas = instalar_bibliotecas(py)
    (ROOT / ".divine_studio_req.sha").unlink(missing_ok=True)
    if not _ok_import(py, "PIL, numpy, yaml"):
        print("\n✗ As bibliotecas básicas não entraram no Python do app. Mande esta tela para o Claude.")
        return 1
    if not _ok_import(py, "faster_whisper"):
        print("\n✗ A transcrição (faster-whisper) não instalou" + (f" (falharam: {', '.join(falhas)})" if falhas else "")
              + ". Mande esta tela para o Claude.")
        return 1
    if not baixar_modelo(py):
        print("  aviso: o modelo de fala baixa na primeira edição (sem internet agora?).")
    if not falhas:
        import hashlib
        (ROOT / ".divine_studio_req.sha").write_text(hashlib.sha256((ROOT / "requirements.txt").read_bytes()).hexdigest())
    print("\n✓ Pronto: o app entende a sua fala. O painel vai reiniciar no Python novo." +
          (f" (Ficaram de fora: {', '.join(falhas)}; o resto funciona.)" if falhas else ""), flush=True)
    return 0


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.exit(main())
