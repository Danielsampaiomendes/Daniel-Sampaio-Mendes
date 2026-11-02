"""Crescimento: seguidores, projeção, metas da semana e plano do dia, por perfil (@dvmedicalspa e @drdanielmendess).

Seguidores vêm do Instagram (quando conectado) ou de você (um número por dia na tela Crescimento).
Guardado em projetos/.crescimento.json (fica só no Mac).
"""
from __future__ import annotations

import datetime as _dt
import json

from .config import ROOT, load

ARQ = ROOT / "projetos" / ".crescimento.json"


def _ler() -> dict:
    try:
        return json.loads(ARQ.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"seguidores": {}, "stories": {}}


def _gravar(d: dict) -> None:
    ARQ.parent.mkdir(parents=True, exist_ok=True)
    ARQ.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def registrar_seguidores(conta: str, n: int, data: str | None = None) -> None:
    d = _ler()
    d.setdefault("seguidores", {}).setdefault(conta, {})[data or _dt.date.today().isoformat()] = int(n)
    _gravar(d)


def marcar_stories(conta: str, data: str | None = None, feito: bool = True) -> None:
    d = _ler()
    dias = set(d.setdefault("stories", {}).get(conta, []))
    dia = data or _dt.date.today().isoformat()
    (dias.add if feito else dias.discard)(dia)
    d["stories"][conta] = sorted(dias)
    _gravar(d)


def puxar_seguidores() -> dict:
    """Lê o número de seguidores de cada perfil conectado no Instagram e registra o de hoje."""
    from . import instagram
    out = {}
    for c in instagram.contas_conectadas():
        if not c["conectado"]:
            continue
        cred = instagram._credenciais(c["usuario"])
        try:
            r = instagram._get(cred["user_id"], cred["token"], fields="followers_count")
            registrar_seguidores(c["usuario"], int(r["followers_count"]))
            out[c["usuario"]] = int(r["followers_count"])
        except Exception as e:
            out[c["usuario"]] = f"erro: {e}"
    return out


def projecao(conta: str) -> dict:
    """Ritmo de ganho (regressão linear nos últimos 60 dias) e projeção para 30 e 90 dias."""
    serie = sorted((_ler().get("seguidores") or {}).get(conta, {}).items())
    if not serie:
        return {"tem": False}
    hoje = _dt.date.today()
    pts = [((_dt.date.fromisoformat(d) - hoje).days, n) for d, n in serie if (hoje - _dt.date.fromisoformat(d)).days <= 60]
    atual = serie[-1][1]
    if len(pts) < 2:
        por_dia = 0.0
    else:
        xm = sum(x for x, _ in pts) / len(pts)
        ym = sum(y for _, y in pts) / len(pts)
        den = sum((x - xm) ** 2 for x, _ in pts) or 1
        por_dia = sum((x - xm) * (y - ym) for x, y in pts) / den
    meta = float((load("algoritmo").get("meta_seguidores_mes") or {}).get(conta, 0))
    mes = por_dia * 30
    return {"tem": True, "atual": atual, "por_dia": round(por_dia, 1), "por_mes": round(mes),
            "em_30": round(atual + por_dia * 30), "em_90": round(atual + por_dia * 90), "meta_mes": int(meta),
            "no_ritmo": (mes >= meta) if meta else None, "serie": serie[-60:],
            "falta_por_dia": round(max(0.0, meta / 30 - por_dia), 1) if meta else 0}


def _semana(pubs: list, conta: str) -> list:
    hoje = _dt.date.today()
    ini = hoje - _dt.timedelta(days=6)
    def data(p):
        try:
            return _dt.date.fromisoformat(p.get("data_postagem") or "")
        except ValueError:
            return None
    return [p for p in pubs if p.get("conta") == conta and p.get("status") == "postado" and data(p) and ini <= data(p) <= hoje]


def requisitos(conta: str) -> list:
    """Metas da semana (config/algoritmo.yaml): o que foi cumprido e o que falta."""
    from . import aprendizado
    m = load("algoritmo").get("metas_semana") or {}
    pubs = aprendizado.todas_publicacoes()
    semana = _semana(pubs, conta)
    reels = [p for p in semana if p.get("tipo", "video") == "video" and p.get("formato") in ("reels", None)]
    carros = [p for p in semana if p.get("tipo") == "carrossel"]
    hoje = _dt.date.today()
    datas = sorted({p["data_postagem"] for p in pubs if p.get("conta") == conta and p.get("status") == "postado"
                    and p.get("data_postagem")})
    dias_sem = (hoje - _dt.date.fromisoformat(datas[-1])).days if datas else None
    stories = [d for d in (_ler().get("stories") or {}).get(conta, []) if (hoje - _dt.date.fromisoformat(d)).days < 7]
    out = [
        {"item": f"Reels na semana: {len(reels)} de {m.get('reels', 4)}", "ok": len(reels) >= m.get("reels", 4)},
        {"item": f"Carrossel na semana: {len(carros)} de {m.get('carrosseis', 1)}", "ok": len(carros) >= m.get("carrosseis", 1)},
        {"item": f"Dias com Stories: {len(stories)} de {m.get('stories_dias', 5)}", "ok": len(stories) >= m.get("stories_dias", 5),
         "stories": True},
        {"item": ("Sem post há " + (f"{dias_sem} dia(s)" if dias_sem is not None else "muito tempo")) if (dias_sem is None or dias_sem > 0)
         else "Postou hoje", "ok": dias_sem is not None and dias_sem <= m.get("dias_sem_postar_max", 3)},
    ]
    refs = load("algoritmo").get("referencias_engajamento") or {}
    com = [p for p in semana if (p.get("metricas") or {}).get("alcance")]
    if com:
        for chave, campo in (("envios", "compartilhamentos"), ("salvamentos", "salvamentos")):
            taxa = sum((p["metricas"].get(campo) or 0) / p["metricas"]["alcance"] for p in com) / len(com)
            bom = (refs.get(chave) or [0.01])[0]
            out.append({"item": f"{chave.capitalize()} por alcance: {taxa * 100:.1f}% (bom: {bom * 100:.0f}%+)", "ok": taxa >= bom})
    return out


def plano_do_dia(conta: str) -> list:
    """O que fazer hoje para crescer, em ordem."""
    from . import aprendizado
    hoje = _dt.date.today().isoformat()
    pubs = [p for p in aprendizado.todas_publicacoes() if p.get("conta") == conta]
    out = []
    agendados = [p for p in pubs if p.get("status") == "agendado" and p.get("data_agendada") == hoje]
    for p in agendados:
        out.append({"acao": f"Postar hoje: {p['titulo']} ({p['versao']})", "projeto": p["projeto"]})
    if not agendados:
        prontos = [p for p in pubs if p.get("status") == "aprovado"]
        if prontos:
            p = prontos[0]
            out.append({"acao": f"Postar um pronto: {p['titulo']} ({p['versao']}), já aprovado", "projeto": p["projeto"]})
        else:
            out.append({"acao": "Nada pronto para postar: crie um Reels hoje (Nova edição) ou peça ideias à IA", "ir": "nova"})
    stories = (_ler().get("stories") or {}).get(conta, [])
    if hoje not in stories:
        out.append({"acao": "Fazer Stories hoje (bastidor, enquete ou caixinha) e marcar aqui", "stories": True})
    postados_sem_metrica = [p for p in pubs if p.get("status") == "postado" and not p.get("metricas")]
    if postados_sem_metrica:
        out.append({"acao": f"Puxar ou anotar as métricas de {len(postados_sem_metrica)} post(s)", "ir": "programacao"})
    proj = projecao(conta)
    if proj.get("tem") and proj.get("no_ritmo") is False:
        out.append({"acao": f"Para bater a meta, faltam ~{proj['falta_por_dia']} seguidor(es) por dia: priorize Reels com envio "
                            "(verdade que dá vontade de mandar) e chamada para seguir no fim"})
    if not proj.get("tem"):
        out.append({"acao": "Anote quantos seguidores o perfil tem hoje (ou conecte o Instagram) para eu projetar o crescimento"})
    return out


def resumo() -> dict:
    from .instagram import perfis
    alg = load("algoritmo")
    return {"perfis": [{"conta": u, "nome": c.get("nome", u), "projecao": projecao(u), "requisitos": requisitos(u),
                        "plano": plano_do_dia(u)} for u, c in perfis().items()],
            "algoritmo": {"sinais": alg.get("sinais") or [], "atualizado_em": alg.get("atualizado_em"),
                          "fontes": alg.get("fontes") or []}}
