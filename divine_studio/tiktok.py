"""TikTok: conectar a conta, puxar métricas dos vídeos e enviar vídeos (rascunho ou publicação direta).

Precisa de um app em developers.tiktok.com (Login Kit + Content Posting API) com a URL de retorno de
config/redes.yaml cadastrada. Chave/segredo do app: TIKTOK_CLIENT_KEY e TIKTOK_CLIENT_SECRET (ou salvos pelo painel).
Tokens ficam só no Mac, em ~/.divine_studio/tiktok.json (chmod 600).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .config import load

ARQUIVO = Path("~/.divine_studio/tiktok.json").expanduser()
CAMPOS_VIDEO = "id,title,share_url,view_count,like_count,comment_count,share_count,duration,create_time"


def _cfg() -> dict:
    return load("redes").get("tiktok") or {}


def _ler() -> dict:
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _gravar(d: dict) -> None:
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(json.dumps(d), encoding="utf-8")
    os.chmod(ARQUIVO, 0o600)


def _app() -> tuple:
    d = _ler()
    return (os.environ.get("TIKTOK_CLIENT_KEY") or d.get("client_key"),
            os.environ.get("TIKTOK_CLIENT_SECRET") or d.get("client_secret"))


def salvar_app(client_key: str, client_secret: str) -> None:
    d = _ler()
    d.update({"client_key": client_key.strip(), "client_secret": client_secret.strip()})
    _gravar(d)


def configurado() -> bool:
    return bool(_ler().get("access_token"))


def estado() -> dict:
    d = _ler()
    ck, cs = _app()
    return {"app": bool(ck and cs), "conectado": bool(d.get("access_token")), "usuario": d.get("usuario", ""),
            "modo": _cfg().get("modo", "rascunho"), "retorno": _cfg().get("retorno")}


# ---------------------------------------------------------------- login (OAuth com PKCE)
def link_autorizacao() -> str:
    ck, cs = _app()
    if not (ck and cs):
        raise SystemExit("Falta a chave do app do TikTok (developers.tiktok.com): salve no painel ou use TIKTOK_CLIENT_KEY.")
    verificador = secrets.token_urlsafe(48)
    desafio = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).decode().rstrip("=")
    estado_ = secrets.token_urlsafe(16)
    d = _ler()
    d.update({"pkce": verificador, "estado": estado_})
    _gravar(d)
    q = {"client_key": ck, "scope": ",".join(_cfg().get("escopos") or []), "response_type": "code",
         "redirect_uri": _cfg().get("retorno"), "state": estado_, "code_challenge": desafio,
         "code_challenge_method": "S256"}
    return f"{_cfg().get('autorizar')}?{urllib.parse.urlencode(q)}"


def _post_form(url: str, campos: dict) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(campos).encode(), method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def retorno(code: str, estado_: str) -> dict:
    """URL de retorno do login: troca o código pelo token e guarda."""
    d = _ler()
    if not estado_ or estado_ != d.get("estado"):
        raise SystemExit("Retorno do TikTok inválido (estado não confere). Tente conectar de novo.")
    ck, cs = _app()
    t = _post_form(_cfg()["token"], {"client_key": ck, "client_secret": cs, "code": code,
                                      "grant_type": "authorization_code", "redirect_uri": _cfg().get("retorno"),
                                      "code_verifier": d.get("pkce", "")})
    if not t.get("access_token"):
        raise SystemExit(f"O TikTok não liberou o acesso: {t.get('error_description') or t.get('error') or t}")
    _guardar_token(d, t)
    try:
        u = _api("GET", "user/info/", campos="open_id,display_name,username,follower_count")
        d = _ler()
        info = (u.get("data") or {}).get("user") or {}
        d["usuario"] = info.get("username") or info.get("display_name") or ""
        _gravar(d)
    except Exception:
        pass
    return estado()


def _guardar_token(d: dict, t: dict) -> None:
    d.update({"access_token": t["access_token"], "refresh_token": t.get("refresh_token", d.get("refresh_token")),
              "expira": time.time() + int(t.get("expires_in", 86400)) - 120, "open_id": t.get("open_id", d.get("open_id"))})
    d.pop("pkce", None)
    d.pop("estado", None)
    _gravar(d)


def _token() -> str:
    d = _ler()
    if not d.get("access_token"):
        raise SystemExit("TikTok não conectado: Programação > Conectar TikTok.")
    if time.time() > float(d.get("expira", 0)) and d.get("refresh_token"):
        ck, cs = _app()
        t = _post_form(_cfg()["token"], {"client_key": ck, "client_secret": cs, "grant_type": "refresh_token",
                                          "refresh_token": d["refresh_token"]})
        if t.get("access_token"):
            _guardar_token(d, t)
            d = _ler()
    return d["access_token"]


def desconectar() -> None:
    d = _ler()
    for k in ("access_token", "refresh_token", "expira", "open_id", "usuario"):
        d.pop(k, None)
    _gravar(d)


def _api(metodo: str, caminho: str, corpo: dict | None = None, campos: str | None = None) -> dict:
    url = f"{_cfg()['api']}/{caminho}" + (f"?fields={campos}" if campos else "")
    req = urllib.request.Request(url, data=json.dumps(corpo).encode() if corpo is not None else None, method=metodo,
                                 headers={"Authorization": f"Bearer {_token()}",
                                          "Content-Type": "application/json; charset=UTF-8"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            erro = json.loads(e.read()).get("error") or {}
        except ValueError:
            erro = {}
        raise SystemExit(f"TikTok recusou ({e.code}): {erro.get('message') or erro.get('code') or 'sem detalhe'}")
    erro = d.get("error") or {}
    if erro.get("code") not in (None, "ok"):
        raise SystemExit(f"TikTok: {erro.get('message') or erro.get('code')}")
    return d


# ---------------------------------------------------------------- métricas
def videos(limite: int = 40) -> list:
    out, cursor = [], None
    while len(out) < limite:
        corpo = {"max_count": 20, **({"cursor": cursor} if cursor else {})}
        d = (_api("POST", "video/list/", corpo, CAMPOS_VIDEO).get("data") or {})
        out += d.get("videos") or []
        if not d.get("has_more"):
            break
        cursor = d.get("cursor")
    return out[:limite]


def seguidores() -> int | None:
    u = (_api("GET", "user/info/", campos="follower_count").get("data") or {}).get("user") or {}
    return u.get("follower_count")


def _id_link(link: str) -> str | None:
    import re
    m = re.search(r"/video/(\d+)", link or "")
    return m.group(1) if m else None


def sincronizar() -> dict:
    """Liga as peças com link do TikTok aos vídeos da conta e grava as métricas (alimenta o Laboratório)."""
    from . import aprendizado
    vs = {str(v["id"]): v for v in videos()}
    atualizadas = 0
    for pub in aprendizado.todas_publicacoes():
        vid = pub.get("tiktok_id") or _id_link(pub.get("link_tiktok", ""))
        v = vs.get(str(vid)) if vid else None
        if not v:
            continue
        m = {"views": v.get("view_count"), "curtidas": v.get("like_count"), "comentarios": v.get("comment_count"),
             "compartilhamentos": v.get("share_count")}
        aprendizado.marcar(aprendizado.PROJETOS / pub["projeto"], pub["versao"],
                           metricas_tiktok={k: x for k, x in m.items() if x is not None})
        atualizadas += 1
    return {"videos": len(vs), "atualizadas": atualizadas}


# ---------------------------------------------------------------- envio
def enviar(arquivo: Path, legenda: str = "", modo: str | None = None) -> dict:
    """Envia o vídeo: 'rascunho' (chega no app TikTok para você publicar) ou 'direto'. Devolve {publish_id, modo}."""
    modo = modo or _cfg().get("modo", "rascunho")
    tam = arquivo.stat().st_size
    origem = {"source": "FILE_UPLOAD", "video_size": tam, "chunk_size": tam, "total_chunk_count": 1}
    if tam > 64 * 1024 * 1024:
        pedaco = 32 * 1024 * 1024
        n = tam // pedaco
        origem.update({"chunk_size": pedaco, "total_chunk_count": n})
    if modo == "direto":
        info = (_api("POST", "post/publish/creator_info/query/", {}).get("data") or {})
        opcoes = info.get("privacy_level_options") or []
        priv = _cfg().get("privacidade_direto", "SELF_ONLY")
        if opcoes and priv not in opcoes:
            priv = "SELF_ONLY" if "SELF_ONLY" in opcoes else opcoes[0]
        d = _api("POST", "post/publish/video/init/", {"post_info": {"title": legenda[:2000], "privacy_level": priv,
                                                                    "disable_comment": False, "disable_duet": False,
                                                                    "disable_stitch": False}, "source_info": origem})
    else:
        d = _api("POST", "post/publish/inbox/video/init/", {"source_info": origem})
    dados = d.get("data") or {}
    _subir(arquivo, dados["upload_url"], origem["chunk_size"], origem["total_chunk_count"])
    return {"publish_id": dados.get("publish_id"), "modo": modo}


def _subir(arquivo: Path, url: str, pedaco: int, n: int) -> None:
    tam = arquivo.stat().st_size
    with open(arquivo, "rb") as f:
        for i in range(n):
            ini = i * pedaco
            fim = tam - 1 if i == n - 1 else ini + pedaco - 1
            f.seek(ini)
            dados = f.read(fim - ini + 1)
            req = urllib.request.Request(url, data=dados, method="PUT", headers={
                "Content-Type": "video/mp4", "Content-Length": str(len(dados)),
                "Content-Range": f"bytes {ini}-{fim}/{tam}"})
            with urllib.request.urlopen(req, timeout=600):
                pass


def status(publish_id: str) -> dict:
    return _api("POST", "post/publish/status/fetch/", {"publish_id": publish_id}).get("data") or {}
