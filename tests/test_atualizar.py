"""Atualizador do app: pasta copiada à mão (sem .git) e pasta já clonada, sem perder nada do usuário."""
import subprocess
from pathlib import Path

from divine_studio import atualizar as at


def _repo_origem(tmp: Path) -> Path:
    o = tmp / "origem"
    o.mkdir()
    g = lambda *a: subprocess.run(["git", "-C", str(o), *a], check=True, capture_output=True)
    g("init", "-q", "-b", at.RAMO)
    g("config", "user.email", "t@t"), g("config", "user.name", "t")
    (o / "app.py").write_text("versao = 1\n")
    (o / "requirements.txt").write_text("")
    g("add", "."), g("commit", "-qm", "v1")
    return o


def _commit(o: Path, texto: str):
    (o / "app.py").write_text(texto)
    subprocess.run(["git", "-C", str(o), "commit", "-qam", "nova"], check=True, capture_output=True)


def test_pasta_sem_git_vira_clone_e_guarda_arquivos(tmp_path, monkeypatch):
    o = _repo_origem(tmp_path)
    monkeypatch.setattr(at, "REPO", str(o))
    mac = tmp_path / "mac"
    mac.mkdir()
    (mac / "app.py").write_text("versao = 0  # editado à mão\n")
    (mac / "video.mp4").write_bytes(b"midia")
    r = at.atualizar(mac)
    assert r["ok"], r
    assert (mac / "app.py").read_text() == "versao = 1\n"
    assert (mac / "video.mp4").read_bytes() == b"midia"                 # mídia intocada
    guardado = list((mac / "_arquivo").rglob("app.py"))
    assert guardado and "editado" in guardado[0].read_text()            # nada se perde

    _commit(o, "versao = 2\n")
    r = at.atualizar(mac)
    assert r["ok"] and r["mudou"] and (mac / "app.py").read_text() == "versao = 2\n"
    r = at.atualizar(mac)
    assert r["ok"] and not r["mudou"]


def test_commits_locais_nao_sao_atropelados(tmp_path, monkeypatch):
    o = _repo_origem(tmp_path)
    monkeypatch.setattr(at, "REPO", str(o))
    mac = tmp_path / "mac"
    subprocess.run(["git", "clone", "-q", "-b", at.RAMO, str(o), str(mac)], check=True)
    for k, v in (("user.email", "t@t"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(mac), "config", k, v], check=True)
    _commit(mac, "versao = local\n")
    _commit(o, "versao = 2\n")
    r = at.atualizar(mac)
    assert not r["ok"] and (mac / "app.py").read_text() == "versao = local\n"
