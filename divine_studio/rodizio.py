"""Rodízio de combinações de fontes e de SFX entre vídeos e versões (config/historico.yaml)."""
from __future__ import annotations

import datetime as _dt

from .config import load, save
from .fonts import todas_combinacoes

CAB = ("# Rodízio de fontes e SFX entre vídeos (o Divine Studio atualiza sozinho a cada render).\n"
       "# Mais recente por último.\n")


def escolher_fontes(n: int, fixas: list | None = None, evitar_ultimas: int = 6) -> list:
    """n combinações diferentes entre si, evitando as usadas por último; respeita as já definidas."""
    hist = load("historico").get("fontes", [])
    recentes = set(hist[-evitar_ultimas:])
    ordem = todas_combinacoes()
    # começa logo depois da última usada, seguindo o ciclo A..N
    ini = (ordem.index(hist[-1]) + 1) % len(ordem) if hist and hist[-1] in ordem else 0
    ciclo = ordem[ini:] + ordem[:ini]
    escolhidas = []
    for k in range(n):
        if fixas and k < len(fixas) and fixas[k]:
            escolhidas.append(fixas[k])
            continue
        candidatas = [c for c in ciclo if c not in recentes and c not in escolhidas] or \
                     [c for c in ciclo if c not in escolhidas]
        escolhidas.append(candidatas[0])
    return escolhidas


def escolher_sfx(tipo: str, n: int, fixos: list | None = None) -> list:
    """Lista de n grupos de SFX (cada grupo = lista de nomes) evitando variações recentes."""
    cfg = load("sfx")[tipo]
    hist = load("historico").get(f"sfx_{tipo}", [])
    recentes = set(hist[-6:])
    escolhidos = []
    usados = set()
    for k in range(n):
        if fixos and k < len(fixos) and fixos[k]:
            g = fixos[k] if isinstance(fixos[k], list) else [fixos[k]]
            escolhidos.append(g)
            usados.update(g)
            continue
        cand = [g for g in cfg if not (set(g) & recentes) and not (set(g) & usados)] or \
               [g for g in cfg if not (set(g) & usados)] or cfg
        escolhidos.append(cand[0])
        usados.update(cand[0])
    return escolhidos


def registrar(projeto_nome: str, versoes: list) -> None:
    """versoes: [{'nome','fontes','sfx_abertura','sfx_fechamento','hook_id'}]"""
    h = dict(load("historico"))
    h["fontes"] = (h.get("fontes", []) + [v["fontes"] for v in versoes])[-40:]
    h["sfx_abertura"] = (h.get("sfx_abertura", []) + [s for v in versoes for s in v["sfx_abertura"]])[-30:]
    h["sfx_fechamento"] = (h.get("sfx_fechamento", []) + [s for v in versoes for s in v["sfx_fechamento"]])[-20:]
    vids = h.get("videos", []) or []
    vids.append({"data": _dt.date.today().isoformat(), "projeto": projeto_nome,
                 "versoes": {v["nome"]: {"fontes": v["fontes"], "hook": v.get("hook_id"),
                                         "sfx": v["sfx_abertura"] + v["sfx_fechamento"]} for v in versoes}})
    h["videos"] = vids[-60:]
    save("historico", h, CAB)
