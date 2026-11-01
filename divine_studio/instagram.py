"""Instagram: puxa as métricas dos posts para o aprendizado (Instagram Graph API, conta profissional).

Ligar (uma vez): crie um app no developers.facebook.com, conecte a conta @dvmedicalspa (profissional, ligada a
uma página do Facebook) e gere um token de longa duração com instagram_basic e instagram_manage_insights. Depois:
  export INSTAGRAM_TOKEN=...       export INSTAGRAM_USER_ID=...   (id da conta profissional)
Sem isso, as métricas podem ser digitadas na tela Programação.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request


API = "https://graph.facebook.com/v21.0"
METRICAS = {"views": "views", "reach": "alcance", "likes": "curtidas", "comments": "comentarios",
            "shares": "compartilhamentos", "saved": "salvamentos"}


def configurado() -> bool:
    return bool(os.environ.get("INSTAGRAM_TOKEN") and os.environ.get("INSTAGRAM_USER_ID"))


def _get(caminho: str, **params) -> dict:
    params["access_token"] = os.environ["INSTAGRAM_TOKEN"]
    url = f"{API}/{caminho}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def _codigo(link: str) -> str | None:
    m = re.search(r"instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)", link or "")
    return m.group(1) if m else None


def posts_recentes(limite: int = 50) -> list:
    d = _get(f"{os.environ['INSTAGRAM_USER_ID']}/media", fields="id,permalink,timestamp,media_type,caption",
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
        raise SystemExit("Instagram não conectado: defina INSTAGRAM_TOKEN e INSTAGRAM_USER_ID (ver divine_studio/instagram.py).")
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

