"""Automações no estilo do Zapier: gatilho -> ações, conferidas pelo painel a cada minuto (config/automacoes.yaml).

Estado (o que já foi disparado) e histórico ficam em projetos/.automacoes.json (fora do GitHub).
Tudo o que publica passa por publicar.pode_publicar (você liga "postar sozinho" + revisor de compliance).
"""
from __future__ import annotations

import datetime as _dt
import json
import threading
import urllib.request

from .config import ROOT, load

ESTADO = ROOT / "projetos" / ".automacoes.json"
_TRAVA = threading.Lock()
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def _cfg() -> dict:
    return load("automacoes")


def _estado() -> dict:
    try:
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"feitos": {}, "historico": []}


def _gravar(e: dict) -> None:
    e["historico"] = e.get("historico", [])[-200:]
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")


def historico(n: int = 40) -> list:
    return list(reversed(_estado().get("historico", [])[-n:]))


def regras() -> list:
    troca = _estado().get("ligado", {})
    return [{"indice": i, **r, "ligado": troca.get(str(i), r.get("ligado", True))}
            for i, r in enumerate(_cfg().get("regras") or [])]


def ligar(indice: int, ligado: bool) -> None:
    """Liga/desliga uma regra pelo painel (a escolha fica no Mac; o padrão continua em config/automacoes.yaml)."""
    e = _estado()
    e.setdefault("ligado", {})[str(int(indice))] = bool(ligado)
    _gravar(e)


def _registrar(e: dict, regra: str, acao: str, alvo: str, ok: bool, detalhe: str = "") -> None:
    e.setdefault("historico", []).append({"em": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "regra": regra,
                                          "acao": acao, "alvo": alvo, "ok": ok, "detalhe": str(detalhe)[:300]})


# ---------------------------------------------------------------- gatilhos
def _eventos(agora: _dt.datetime, e: dict) -> dict:
    """{gatilho: [alvos]} do que aconteceu desde a última volta."""
    from . import aprendizado, entrada
    ev = {k: [] for k in ("video_novo", "projeto_novo", "hora_de_postar", "postado", "depois_24h", "depois_7d",
                          "toda_semana")}
    try:
        ev["video_novo"] = [str(a) for a in entrada.pendentes()]
    except Exception:
        pass
    for nome in e.pop("_projetos_novos", []):
        ev["projeto_novo"].append(nome)
    for pub in aprendizado.todas_publicacoes():
        alvo = f"{pub['projeto']}::{pub['versao']}"
        if pub.get("status") == "agendado" and pub.get("auto_postar") and pub.get("data_agendada"):
            hora = str(pub.get("hora_agendada") or (load("redes").get("instagram") or {}).get("hora_padrao", "19:00"))
            try:
                data = str(pub["data_agendada"])
                quando = _dt.datetime.fromisoformat(data if "T" in data or " " in data else f"{data}T{hora}")
            except ValueError:
                quando = None
            if quando and quando <= agora:
                ev["hora_de_postar"].append(alvo)
        if pub.get("status") == "postado":
            ev["postado"].append(alvo)
            data = pub.get("postado_em") or pub.get("data_postagem")
            try:
                dt = _dt.datetime.fromisoformat(str(data)) if data else None
            except ValueError:
                dt = None
            if dt and agora - dt >= _dt.timedelta(hours=24):
                ev["depois_24h"].append(alvo)
            if dt and agora - dt >= _dt.timedelta(days=7):
                ev["depois_7d"].append(alvo)
    s = _cfg().get("toda_semana") or {}
    if DIAS[agora.weekday()] == s.get("dia", "segunda") and agora.hour >= int(s.get("hora", 7)):
        ev["toda_semana"].append(agora.strftime("%G-W%V"))
    return ev


# ---------------------------------------------------------------- ações
def _fazer(acao: str, alvo: str, regra: dict, e: dict, iniciar=None) -> str:
    if acao == "analisar_entrada":
        from . import entrada
        from pathlib import Path
        nome = entrada.processar(Path(alvo))
        e.setdefault("_projetos_novos", []).append(nome)
        return f"projeto {nome}"
    if acao == "previas":                  # o vídeo que chegou pelo celular já sai com as versões prontas para aprovar
        if iniciar is None:
            return "sem painel aberto: gere as prévias no projeto"
        return f"prévias em andamento ({iniciar(alvo, 'previa')})"
    if acao == "storyboard":
        if iniciar is None:
            return "sem painel aberto: rode o storyboard no projeto"
        return f"storyboard em andamento ({iniciar(alvo, 'storyboard')})"
    if acao == "publicar":
        from . import publicar
        projeto, versao = alvo.split("::", 1)
        r = publicar.publicar(projeto, versao)
        return "; ".join(f"{k}: {v}" for k, v in r.items())
    if acao == "puxar_metricas":
        return _puxar_metricas(e)
    if acao == "buscar_radar":
        from . import radar
        return str(radar.buscar_instagram())
    if acao == "webhook":
        url = regra.get("url")
        if not url:
            return "sem URL na regra"
        corpo = json.dumps({"evento": regra.get("quando"), "alvo": alvo, **_dados_alvo(alvo)}, ensure_ascii=False).encode()
        req = urllib.request.Request(url, data=corpo, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=20) as r:
            return f"webhook {r.status}"
    raise ValueError(f"ação desconhecida: {acao}")


def _puxar_metricas(e: dict) -> str:
    """Uma vez por hora no máximo (vários alvos no mesmo minuto puxam uma vez só)."""
    agora = _dt.datetime.now()
    ult = e.get("ultima_metrica")
    if ult and agora - _dt.datetime.fromisoformat(ult) < _dt.timedelta(hours=1):
        return "já puxadas há pouco"
    e["ultima_metrica"] = agora.isoformat(timespec="minutes")
    partes = []
    try:
        from . import instagram
        if instagram.configurado():
            partes.append(f"Instagram: {instagram.sincronizar().get('atualizadas', 0)} atualizadas")
    except SystemExit as x:
        partes.append(f"Instagram: {x}")
    try:
        from . import tiktok
        if tiktok.configurado():
            partes.append(f"TikTok: {tiktok.sincronizar().get('atualizadas', 0)} atualizadas")
    except SystemExit as x:
        partes.append(f"TikTok: {x}")
    return "; ".join(partes) or "nenhuma rede conectada"


def _dados_alvo(alvo: str) -> dict:
    if "::" not in alvo:
        return {}
    from . import aprendizado
    projeto, versao = alvo.split("::", 1)
    pub = next((p for p in aprendizado.todas_publicacoes() if p["projeto"] == projeto and p["versao"] == versao), {})
    return {k: pub.get(k) for k in ("titulo", "conta", "link", "link_tiktok", "data_postagem", "metricas") if pub.get(k)}


# ---------------------------------------------------------------- volta
def ciclo(agora: _dt.datetime | None = None, iniciar=None) -> list:
    """Confere os gatilhos e roda as ações das regras ligadas. Cada (regra, alvo) roda uma vez só."""
    agora = agora or _dt.datetime.now()
    if not _TRAVA.acquire(blocking=False):
        return []
    try:
        e = _estado()
        feitos = e.setdefault("feitos", {})
        rodou = []
        ev = _eventos(agora, e)
        troca = e.get("ligado", {})
        for i, r in enumerate(_cfg().get("regras") or []):
            if not troca.get(str(i), r.get("ligado", True)):
                continue
            for alvo in ev.get(r.get("quando"), []):
                chave = f"{i}|{r.get('quando')}|{alvo}"
                if chave in feitos:
                    continue
                if r.get("quando") == "postado" and alvo in e.get("ja_postados_antes", []):
                    feitos[chave] = agora.isoformat(timespec="minutes")
                    continue
                for acao in r.get("fazer") or []:
                    try:
                        det = _fazer(acao, alvo, r, e, iniciar)
                        _registrar(e, r.get("nome", ""), acao, alvo, True, det)
                    except (SystemExit, Exception) as x:      # uma ação com erro não para as outras
                        det = str(x)
                        _registrar(e, r.get("nome", ""), acao, alvo, False, det)
                    rodou.append((r.get("nome"), acao, alvo, det))
                feitos[chave] = agora.isoformat(timespec="minutes")
                # o que nasceu nesta volta dispara as regras de 'projeto_novo' na mesma volta
                if e.get("_projetos_novos"):
                    ev["projeto_novo"] += [n for n in e["_projetos_novos"] if n not in ev["projeto_novo"]]
        e.pop("_projetos_novos", None)
        _gravar(e)
        return rodou
    finally:
        _TRAVA.release()


def iniciar_vigia(iniciar=None) -> threading.Thread:
    """Laço em segundo plano do painel. Na primeira volta, o que já estava postado não dispara 'postado'."""
    from . import aprendizado
    e = _estado()
    if "ja_postados_antes" not in e:
        e["ja_postados_antes"] = [f"{p['projeto']}::{p['versao']}" for p in aprendizado.todas_publicacoes()
                                  if p.get("status") == "postado"]
        _gravar(e)

    def laco():
        import time
        while True:
            try:
                ciclo(iniciar=iniciar)
            except Exception as x:                        # o vigia nunca derruba o painel
                print(f"  aviso: automações ({x})", flush=True)
            time.sleep(int(_cfg().get("intervalo_s", 60)))
    t = threading.Thread(target=laco, name="automacoes", daemon=True)
    t.start()
    return t
