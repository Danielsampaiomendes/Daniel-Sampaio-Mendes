"""Estilos de edição (config/estilos.yaml): legenda, ritmo, lista de efeitos e peças de uma vez.

Aplicado a cada versão antes de montar o plano. O que o projeto já define vale mais que o estilo.
As peças do estilo entram como efeitos marcados com _estilo (aparecem no storyboard e na linha do tempo e,
se você mudar ou tirar no storyboard, viram efeitos seus).
"""
from __future__ import annotations

import copy

from .config import load


def _cfg() -> dict:
    return load("estilos")


def lista() -> list:
    return [{"chave": k, "nome": v.get("nome", k), "descricao": v.get("descricao", "")}
            for k, v in (_cfg().get("estilos") or {}).items()]


def nome_do(projeto: dict, versao: dict | None = None) -> str:
    return (versao or {}).get("estilo_edicao") or projeto.get("estilo_edicao") or _cfg().get("padrao", "divine")


def _texto(valor, projeto: dict):
    if isinstance(valor, list):
        return [_texto(v, projeto) for v in valor]
    if not isinstance(valor, str):
        return valor
    selo = str(projeto.get("selo") or projeto.get("titulo") or "Divine").split("·")[0].strip()
    serv = ((projeto.get("anuncio") or {}).get("servico")) or selo
    return valor.replace("{titulo}", str(projeto.get("titulo", "Divine"))).replace("{selo}", selo) \
        .replace("{servico}", str(serv))


def _quando(q, dur: float, fim: float) -> float:
    if q == "abertura":
        return 0.3
    if q == "fim":
        return max(0.0, fim - 3.2)
    return round(max(0.0, min(float(q), 0.95)) * fim, 2)


def aplicar(projeto: dict, versao: dict, duracao: float) -> tuple:
    """(projeto, versão) com o estilo aplicado, sem mexer nos originais."""
    nome = nome_do(projeto, versao)
    est = (_cfg().get("estilos") or {}).get(nome)
    if not est or nome == "divine":
        return projeto, versao
    p = dict(projeto)
    p["_estilo"] = nome
    if est.get("legendas") and p.get("legendas"):
        leg = dict(est["legendas"])
        if isinstance(p["legendas"], dict):
            leg.update(p["legendas"])                              # o seu ajuste vence
        p["legendas"] = leg
    if est.get("ritmo") and not p.get("ritmo"):
        p["ritmo"] = est["ritmo"]
    if est.get("meio"):
        p["_estilo_meio"] = list(est["meio"])
    fim = max(1.0, duracao - 1.0)
    evitar = [(e.get("tipo"), float(e.get("inicio", 0))) for e in p.get("efeitos_evitar") or []]
    manuais = [(e.get("tipo"), float(e.get("inicio", 0))) for e in p.get("efeitos") or []]
    novos = []
    for el in est.get("elementos") or []:
        ef = {k: _texto(v, p) for k, v in copy.deepcopy(el).items() if k != "quando"}
        ef["inicio"] = _quando(el.get("quando", 0.5), duracao, fim)
        if ef["inicio"] >= fim - 0.5:
            continue
        if any(t == ef["tipo"] and abs(i - ef["inicio"]) < 0.6 for t, i in evitar + manuais):
            continue
        ef["_estilo"] = nome
        novos.append(ef)
    if novos:
        p["efeitos"] = list(p.get("efeitos") or []) + novos
    return p, versao
