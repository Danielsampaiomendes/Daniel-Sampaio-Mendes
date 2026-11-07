"""Atualiza o Divine Studio a partir do GitHub e reinicia o painel.

Roda sozinho (só biblioteca padrão), então serve até numa pasta antiga:
  python3 divine_studio/atualizar.py                 # atualiza a pasta onde ele está e reabre o painel
  python3 divine_studio/atualizar.py <pasta> --sem-painel

Pasta que já é um clone git: baixa o ramo e avança (fast-forward). Pasta copiada à mão (sem .git): liga ao
GitHub e traz os arquivos do ramo. Antes de trocar qualquer arquivo seu que esteja diferente, guarda uma cópia
em _arquivo/atualizacao-<data>/ (nada é apagado). Vídeos, fontes e áudios ficam fora do git e não são tocados.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = "https://github.com/Danielsampaiomendes/Daniel-Sampaio-Mendes.git"
RAMO = "claude/ola-8lmaep"
PORTA = 8765


def _git(pasta: Path, *args, check=True) -> str:
    r = subprocess.run(["git", "-C", str(pasta), *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip() or f"git {' '.join(args)} falhou")
    return r.stdout.strip()


def _ancestral(pasta: Path, a: str, b: str) -> bool:
    return subprocess.run(["git", "-C", str(pasta), "merge-base", "--is-ancestor", a, b],
                          capture_output=True).returncode == 0


def _guardar(pasta: Path, arquivos: list, pasta_backup: Path) -> int:
    n = 0
    for rel in arquivos:
        a = pasta / rel
        if a.is_file():
            destino = pasta_backup / rel
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(a, destino)
            n += 1
    return n


def _diferentes(pasta: Path, ref: str) -> list:
    """Arquivos do ramo que existem na pasta com conteúdo diferente (seriam trocados)."""
    out = []
    for linha in _git(pasta, "ls-tree", "-r", ref).splitlines():
        meta, rel = linha.split("\t", 1)
        blob = meta.split()[2]
        a = pasta / rel
        if a.is_file() and _git(pasta, "hash-object", str(a), check=False) != blob:
            out.append(rel)
    return out


def atualizar(pasta: Path) -> dict:
    """Traz a versão nova. Devolve {ok, mudou, commit, msg, guardados}."""
    pasta = Path(pasta).resolve()
    if not shutil.which("git"):
        return {"ok": False, "mudou": False, "msg": "Falta o git. No Terminal: xcode-select --install"}
    backup = pasta / "_arquivo" / f"atualizacao-{time.strftime('%Y-%m-%d_%H%M%S')}"
    novo = not (pasta / ".git").exists()
    try:
        if novo:
            _git(pasta, "init", "-q")
        remotos = _git(pasta, "remote").split()
        if "origin" not in remotos:
            _git(pasta, "remote", "add", "origin", REPO)
        _git(pasta, "fetch", "-q", "origin", RAMO)
        alvo = f"origin/{RAMO}"
        _git(pasta, "update-ref", f"refs/remotes/{alvo}", "FETCH_HEAD")
        antes = "" if novo else _git(pasta, "rev-parse", "HEAD", check=False)
        no_ramo = antes and _git(pasta, "rev-parse", "--abbrev-ref", "HEAD", check=False) == RAMO
        if no_ramo and _ancestral(pasta, alvo, "HEAD"):
            return {"ok": True, "mudou": False, "commit": antes[:7], "msg": "Já está na versão mais nova."}
        if no_ramo and not _ancestral(pasta, "HEAD", alvo):
            return {"ok": False, "mudou": False, "commit": antes[:7],
                    "msg": "Há commits feitos no Mac que não estão no GitHub. Nada foi trocado; peça ajuda para juntar."}
        trocar = _diferentes(pasta, alvo)
        guardados = _guardar(pasta, trocar, backup) if trocar else 0
        _git(pasta, "checkout", "-q", "-f", "-B", RAMO, alvo)
        _git(pasta, "branch", "-q", "--set-upstream-to", alvo, RAMO, check=False)
        depois = _git(pasta, "rev-parse", "HEAD")
        msg = f"Atualizado para {depois[:7]}: {_git(pasta, 'log', '-1', '--format=%s')}"
        if guardados:
            msg += f" ({guardados} arquivo(s) seus guardados em {backup.relative_to(pasta)})"
        return {"ok": True, "mudou": antes != depois, "commit": depois[:7], "msg": msg, "guardados": guardados}
    except RuntimeError as e:
        dica = " (sem internet ou sem acesso ao GitHub: confira o login do git)" if "fetch" in str(e) or "Could not" in str(e) else ""
        return {"ok": False, "mudou": False, "msg": f"Não consegui atualizar: {e}{dica}"}


def python_do_app(pasta: Path) -> str:
    """O Python que roda o app: o próprio do Divine Studio (.venv, Python novo) quando existe; senão o do Mac."""
    for cand in (Path(pasta) / ".venv" / "bin" / "python", Path(pasta) / ".venv" / "Scripts" / "python.exe"):
        if cand.exists():
            return str(cand)
    return sys.executable


def _versao(py: str) -> tuple:
    try:
        r = subprocess.run([py, "-c", "import sys; print(sys.version_info[0], sys.version_info[1])"],
                           capture_output=True, text=True, timeout=30)
        return tuple(int(x) for x in r.stdout.split()[:2])
    except (OSError, ValueError, subprocess.SubprocessError):
        return (0, 0)


def _uv() -> list:
    """Comando do uv (instalador rápido), onde estiver: neste Python, no python3 do Mac ou no PATH."""
    for cmd in ([sys.executable, "-m", "uv"], [shutil.which("python3") or "python3", "-m", "uv"], [shutil.which("uv") or "uv"]):
        try:
            if subprocess.run([*cmd, "--version"], capture_output=True, timeout=30).returncode == 0:
                return cmd
        except (OSError, subprocess.SubprocessError):
            pass
    return []


def _tem_uv() -> bool:
    return bool(_uv())


def preparar_python(pasta: Path) -> str | None:
    """O Python do Xcode no Mac é antigo (3.9, pip 21) e não instala a biblioteca nova do Claude nem tudo o que o
    app usa. Cria uma vez o Python próprio do app (3.12, em .venv) com o uv. Se falhar, segue com o do Mac."""
    pasta = Path(pasta)
    if (pasta / ".venv").exists() or _versao(sys.executable) >= (3, 10):
        return None
    print("  Preparando o Python do Divine Studio (só na primeira vez, leva 1 ou 2 minutos)...", flush=True)
    if not _tem_uv():
        subprocess.run([sys.executable, "-m", "pip", "install", "--user", "-q", "uv"], capture_output=True)
    if not _tem_uv():
        return "Aviso: não consegui preparar o Python novo (seguindo com o do Mac; a IA pode ficar desligada)."
    r = subprocess.run([*_uv(), "venv", "--seed", "--python", "3.12", str(pasta / ".venv")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        shutil.rmtree(pasta / ".venv", ignore_errors=True)
        return "Aviso: não consegui preparar o Python novo (seguindo com o do Mac; a IA pode ficar desligada)."
    (pasta / ".divine_studio_req.sha").unlink(missing_ok=True)       # instala tudo no Python novo
    return "Python 3.12 do Divine Studio pronto."


def _instalar(py: str, pacotes: list) -> bool:
    """Instala no Python do app: uv quando existe (rápido), senão pip (sem --user dentro do .venv)."""
    uv = _uv()
    if uv:
        cmd = [*uv, "pip", "install", "--python", py, "-q", *pacotes]
    else:
        no_venv = ".venv" in py
        cmd = [py, "-m", "pip", "install", "-q", *([] if no_venv else ["--user"]), *pacotes]
    return subprocess.run(cmd).returncode == 0


def dependencias(pasta: Path) -> str | None:
    """Reinstala as bibliotecas quando o requirements.txt muda. Uma que falhe não derruba as outras."""
    req = Path(pasta) / "requirements.txt"
    if not req.exists():
        return None
    marca = Path(pasta) / ".divine_studio_req.sha"
    h = hashlib.sha256(req.read_bytes()).hexdigest()
    if marca.exists() and marca.read_text().strip() == h:
        return None
    py = python_do_app(pasta)
    pacotes = [ln.split("#")[0].strip() for ln in req.read_text(encoding="utf-8").splitlines()]
    pacotes = [x for x in pacotes if x and not x.startswith("-")]
    print("  Instalando as bibliotecas do app...", flush=True)
    if _instalar(py, pacotes):
        marca.write_text(h)
        return "Bibliotecas atualizadas."
    falhas = [x for x in pacotes if not _instalar(py, [x])]      # uma por vez: o que dá, entra
    if not falhas:
        marca.write_text(h)
        return "Bibliotecas atualizadas."
    nomes = ", ".join(f.split(">")[0].split("=")[0] for f in falhas)
    return f"Aviso: não instalou {nomes}. O resto foi instalado e o app abre normalmente."


def fontes(pasta: Path) -> str | None:
    """Baixa as fontes que faltam (a lista cresce com as atualizações)."""
    script = Path(pasta) / "Biblioteca_Fontes" / "baixar_fontes.sh"
    if not script.exists() or not shutil.which("bash"):
        return None
    antes = len(list((script.parent / "ttf").glob("*.ttf"))) if (script.parent / "ttf").exists() else 0
    subprocess.run(["bash", str(script)], capture_output=True, timeout=600)
    depois = len(list((script.parent / "ttf").glob("*.ttf")))
    return f"{depois - antes} fonte(s) nova(s) baixada(s)." if depois > antes else None


def fechar_painel(porta: int = PORTA) -> bool:
    """Fecha o painel antigo que estiver na porta (ele seguraria o código velho)."""
    if not shutil.which("lsof"):
        return False
    pids = subprocess.run(["lsof", "-ti", f"tcp:{porta}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout.split()
    for pid in pids:
        if pid.isdigit() and int(pid) != os.getpid():
            try:
                os.kill(int(pid), 15)
            except OSError:
                pass
    if pids:
        time.sleep(1.0)
    return bool(pids)


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    sem_painel = "--sem-painel" in args
    args = [a for a in args if not a.startswith("--")]
    pasta = Path(args[0]).expanduser() if args else Path(__file__).resolve().parent.parent
    print("Divine Studio: procurando atualização...")
    r = atualizar(pasta)
    print("  " + r["msg"])
    pp = preparar_python(pasta)
    if pp:
        print("  " + pp)
    d = dependencias(pasta)
    if d:
        print("  " + d)
    f = fontes(pasta)
    if f:
        print("  " + f)
    if sem_painel:
        return 0 if r["ok"] else 1
    if fechar_painel():
        print("  Painel antigo fechado.")
    print("  Abrindo o painel atualizado...")
    os.chdir(pasta)
    py = python_do_app(pasta)
    os.execvp(py, [py, "-m", "divine_studio", "painel", "--porta", str(PORTA)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
