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
            "shares": "compartilhamentos", "saved": "salvamentos", "ig_reels_avg_watch_time": "tempo_medio_ms"}


ARQUIVO = Path("~/.divine_studio/instagram.json").expanduser()


def perfis() -> dict:
    """Perfis da clínica (config/contas.yaml): {usuario: {nome, templates, padrao}}."""
    from .config import load
    try:
        return load("contas").get("contas") or {}
    except Exception:
        return {"dvmedicalspa": {"nome": "Divine Medical Spa", "padrao": True}}


def conta_do_projeto(projeto: dict) -> str | None:
    """Perfil em que a peça é postada: o do projeto, senão o do template (Daniel -> @drdanielmendess)."""
    if projeto.get("conta"):
        return str(projeto["conta"]).lstrip("@")
    if projeto.get("template") == "pessoal" or projeto.get("estilo") == "pessoal":
        return None
    tmpl = projeto.get("template") or projeto.get("estilo") or "divine"
    for usuario, cfg in perfis().items():
        if tmpl in (cfg.get("templates") or []):
            return usuario
    return next((u for u, c in perfis().items() if c.get("padrao")), "dvmedicalspa")


def _todas() -> dict:
    """{usuario: {token, user_id, usuario}} de todas as contas conectadas (aceita o formato antigo, de uma conta)."""
    if os.environ.get("INSTAGRAM_TOKEN") and os.environ.get("INSTAGRAM_USER_ID"):
        u = os.environ.get("INSTAGRAM_USUARIO", "dvmedicalspa")
        return {u: {"token": os.environ["INSTAGRAM_TOKEN"], "user_id": os.environ["INSTAGRAM_USER_ID"], "usuario": u}}
    try:
        d = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if "contas" in d:
        return d["contas"]
    if d.get("token"):                                   # formato antigo
        return {d.get("usuario") or "dvmedicalspa": d}
    return {}


def _gravar(contas: dict) -> None:
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(json.dumps({"contas": contas}), encoding="utf-8")
    os.chmod(ARQUIVO, 0o600)


def _credenciais(usuario: str | None = None) -> dict:
    todas = _todas()
    if usuario and usuario in todas:
        return todas[usuario]
    return next(iter(todas.values()), {})


def configurado(usuario: str | None = None) -> bool:
    c = _credenciais(usuario) if usuario is None or usuario in _todas() else {}
    return bool(c.get("token") and c.get("user_id"))


def contas_conectadas() -> list:
    """Para a tela: todos os perfis da clínica, conectados ou não (sem tokens)."""
    todas = _todas()
    out = [{"usuario": u, "nome": c.get("nome", u), "conectado": u in todas} for u, c in perfis().items()]
    out += [{"usuario": u, "nome": u, "conectado": True} for u in todas if u not in perfis()]
    return out


def conta() -> dict:
    """Resumo para a tela (compatível com a versão de uma conta)."""
    cs = contas_conectadas()
    lig = [c for c in cs if c["conectado"]]
    return {"conectado": bool(lig), "usuario": lig[0]["usuario"] if lig else "", "contas": cs,
            "user_id": _credenciais().get("user_id", "")}


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
    """Testa o token e guarda TODAS as contas profissionais que ele alcança (ex.: @dvmedicalspa e @drdanielmendess,
    se as duas páginas estiverem no mesmo Facebook). Um token de outra pessoa soma às contas já conectadas."""
    import urllib.error
    token = (token or "").strip()
    if len(token) < 20:
        raise SystemExit("Cole o token inteiro (é um texto longo que começa com EAA... ou IG...).")
    try:
        paginas = [] if token.startswith("IG") else \
            _get("me/accounts", token, fields="name,instagram_business_account{id,username}").get("data", [])
        achadas = [p["instagram_business_account"] for p in paginas if p.get("instagram_business_account")]
        if not achadas:                                  # token do "Login do Instagram" (sem página do Facebook)
            eu = _get("me", token, fields="user_id,username")
            achadas = [{"id": eu.get("user_id") or eu.get("id"), "username": eu.get("username")}] if eu.get("username") else []
    except urllib.error.HTTPError as e:
        raise SystemExit(f"O Instagram recusou o token ({e.code}). Gere um novo com as permissões de insights.")
    except urllib.error.URLError:
        raise SystemExit("Sem conexão com o Instagram.")
    if not achadas:
        raise SystemExit("O token funciona, mas não achei conta profissional do Instagram ligada a ele.")
    todas = _todas()
    for c in achadas:
        u = (c.get("username") or c["id"]).lstrip("@")
        todas[u] = {"token": token, "user_id": c["id"], "usuario": u}
    _gravar(todas)
    r = conta()
    r["novas"] = [(c.get("username") or c["id"]) for c in achadas]
    return r


def desconectar(usuario: str | None = None) -> None:
    if not usuario:
        ARQUIVO.unlink(missing_ok=True)
        return
    todas = _todas()
    todas.pop(usuario, None)
    _gravar(todas) if todas else ARQUIVO.unlink(missing_ok=True)


def posts_recentes(limite: int = 50, usuario: str | None = None) -> list:
    c = _credenciais(usuario)
    d = _get(f"{c['user_id']}/media", c["token"], fields="id,permalink,timestamp,media_type,caption", limit=limite)
    return d.get("data", [])


def metricas(media_id: str, usuario: str | None = None) -> dict:
    out = {}
    token = _credenciais(usuario).get("token")
    for nome, campo in METRICAS.items():
        try:
            d = _get(f"{media_id}/insights", token, metric=nome)
            out[campo] = d["data"][0]["values"][0]["value"]
        except Exception:
            continue            # nem toda métrica existe para todo tipo de post
    return out


def sincronizar() -> dict:
    """Liga cada publicação postada (pelo link) ao post de qualquer conta conectada e grava as métricas."""
    from . import aprendizado
    if not configurado():
        raise SystemExit("Instagram não conectado: Programação > Conectar Instagram.")
    import urllib.error
    posts, por_conta, erros = {}, {}, []
    for usuario in _todas():
        try:
            lista = posts_recentes(usuario=usuario)
        except urllib.error.HTTPError as e:
            erros.append(f"@{usuario}: o Instagram recusou ({e.code}); gere um token novo")
            continue
        except urllib.error.URLError:
            raise SystemExit("Sem conexão com o Instagram.")
        por_conta[usuario] = len(lista)
        for p in lista:
            posts[_codigo(p.get("permalink")) or ""] = (usuario, p)
    atualizadas = 0
    for pub in aprendizado.todas_publicacoes():
        if pub.get("status") != "postado" or not pub.get("link"):
            continue
        achado = posts.get(_codigo(pub["link"]) or "-")
        if not achado:
            continue
        usuario, post = achado
        m = metricas(post["id"], usuario)
        if m:
            aprendizado.marcar(aprendizado.PROJETOS / pub["projeto"], pub["versao"], metricas=m, conta=usuario)
            atualizadas += 1
    return {"posts_no_instagram": sum(por_conta.values()), "por_conta": por_conta, "atualizadas": atualizadas,
            "erros": erros}
