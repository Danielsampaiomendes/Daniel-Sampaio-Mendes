"""Instagram: puxa as métricas dos posts para o aprendizado (Instagram Graph API, conta profissional).

Ligar (uma vez): no painel, Programação > "Conectar Instagram" e cole o token (o app descobre o id da conta sozinho).
O token fica só no Mac, em ~/.divine_studio/instagram.json (fora do repositório e do GitHub).
Também vale por variável de ambiente: INSTAGRAM_TOKEN e INSTAGRAM_USER_ID.
Sem isso, as métricas podem ser digitadas na tela Programação.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path


API = "https://graph.facebook.com/v21.0"
API_IG = "https://graph.instagram.com/v21.0"
METRICAS = {"views": "views", "reach": "alcance", "likes": "curtidas", "comments": "comentarios",
            "shares": "compartilhamentos", "saved": "salvamentos"}


ARQUIVO = Path("~/.divine_studio/instagram.json").expanduser()


def _credenciais() -> dict:
    if os.environ.get("INSTAGRAM_TOKEN") and os.environ.get("INSTAGRAM_USER_ID"):
        return {"token": os.environ["INSTAGRAM_TOKEN"], "user_id": os.environ["INSTAGRAM_USER_ID"]}
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def configurado() -> bool:
    c = _credenciais()
    return bool(c.get("token") and c.get("user_id"))


def conta() -> dict:
    """Conta conectada (sem o token), para a tela."""
    c = _credenciais()
    return {"conectado": configurado(), "usuario": c.get("usuario", ""), "user_id": c.get("user_id", "")}


def _get(caminho: str, token: str | None = None, **params) -> dict:
    params["access_token"] = token or _credenciais()["token"]
    base = API_IG if params["access_token"].startswith("IG") else API     # token do "Login do Instagram"
    url = f"{base}/{caminho}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def _codigo(link: str) -> str | None:
    m = re.search(r"instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)", link or "")
    return m.group(1) if m else None


def conectar(token: str) -> dict:
    """Testa o token, acha a conta profissional ligada à página do Facebook e guarda tudo só neste Mac."""
    import urllib.error
    token = (token or "").strip()
    if len(token) < 20:
        raise SystemExit("Cole o token inteiro (é um texto longo que começa com EAA...).")
    try:
        paginas = [] if token.startswith("IG") else \
            _get("me/accounts", token, fields="name,instagram_business_account{id,username}").get("data", [])
        contas = [p["instagram_business_account"] for p in paginas if p.get("instagram_business_account")]
        if not contas:                                   # token do "Instagram Login" (sem página do Facebook)
            eu = _get("me", token, fields="user_id,username")
            contas = [{"id": eu.get("user_id") or eu.get("id"), "username": eu.get("username")}] if eu.get("username") else []
    except urllib.error.HTTPError as e:
        raise SystemExit(f"O Instagram recusou o token ({e.code}). Gere um novo com as permissões de insights.")
    except urllib.error.URLError:
        raise SystemExit("Sem conexão com o Instagram.")
    if not contas:
        raise SystemExit("O token funciona, mas não achei conta profissional do Instagram ligada a ele.")
    alvo = next((c for c in contas if "dvmedicalspa" in (c.get("username") or "")), contas[0])
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(json.dumps({"token": token, "user_id": alvo["id"], "usuario": alvo.get("username", "")}),
                       encoding="utf-8")
    os.chmod(ARQUIVO, 0o600)
    return conta()


def desconectar() -> None:
    ARQUIVO.unlink(missing_ok=True)


def posts_recentes(limite: int = 50) -> list:
    d = _get(f"{_credenciais()['user_id']}/media", fields="id,permalink,timestamp,media_type,caption",
             limit=limite)
    return d.get("data", [])


def metricas(media_id: str) -> dict:
    out = {}
    for nome, campo in METRICAS.items():
        try:
            d = _get(f"{media_id}/insights", metric=nome)
            out[campo] = d["data"][0]["values"][0]["value"]
        except Exception:
            continue            # nem toda métrica existe para todo tipo de post
    return out


def sincronizar() -> dict:
    """Liga cada publicação marcada como postada (pelo link) ao post do Instagram e grava as métricas."""
    from . import aprendizado
    if not configurado():
        raise SystemExit("Instagram não conectado: Programação > Conectar Instagram.")
    import urllib.error
    try:
        posts = {(_codigo(p.get("permalink")) or ""): p for p in posts_recentes()}
    except urllib.error.HTTPError as e:
        raise SystemExit(f"O Instagram recusou o pedido ({e.code}). Confira o token e o id da conta.")
    except urllib.error.URLError:
        raise SystemExit("Sem conexão com o Instagram.")
    atualizadas = 0
    for pub in aprendizado.todas_publicacoes():
        if pub.get("status") != "postado" or not pub.get("link"):
            continue
        post = posts.get(_codigo(pub["link"]) or "-")
        if not post:
            continue
        m = metricas(post["id"])
        if m:
            aprendizado.marcar(aprendizado.PROJETOS / pub["projeto"], pub["versao"], metricas=m)
            atualizadas += 1
    return {"posts_no_instagram": len(posts), "atualizadas": atualizadas}

