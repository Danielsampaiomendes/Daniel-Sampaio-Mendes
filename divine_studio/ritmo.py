"""Ritmo automático da edição: o padrão viral com cara de luxo e o "Vídeo Épico".

A cada 2 a 3 s (viral) ou 1,3 a 1,9 s (épico) algo muda no espaço: câmera, foco, luz, cartão 3D, vertigem.
Os efeitos automáticos só entram onde não há efeito seu na linha do tempo, têm som discreto e mudam a cada versão.
Regras e listas em config/viral.yaml. No projeto.yaml: ritmo: viral | epico | calmo.
"""
from __future__ import annotations

import random

import numpy as np

from .config import ROOT, load

SEM_RITMO = {"tv"}


def _cfg() -> dict:
    return load("viral")


def modo(projeto: dict, versao: dict | None = None) -> str:
    versao = versao or {}
    if versao.get("epico") or projeto.get("epico"):
        return "epico"
    m = versao.get("ritmo") or projeto.get("ritmo") or _cfg().get("padrao", "viral")
    if projeto.get("template") in SEM_RITMO or projeto.get("tipo") in ("antes_depois",) or m in ("calmo", None, False):
        return "calmo"
    return m if m in _cfg()["modos"] else "viral"


def _som(familia: str, semente: int) -> str | None:
    pasta = ROOT / load("sfx")["pasta"]
    opcoes = sorted(f.stem for f in pasta.glob(f"{familia}*.wav")) if pasta.exists() else []
    return opcoes[semente % len(opcoes)] if opcoes else None


def _som_viral(tipo: str) -> str | None:
    from .efeitos_viral import SONS
    return SONS.get(tipo)


def _livre(t: float, dur: float, ocupados: list, folga: float, espaco: float = 0.0) -> bool:
    return all((t + dur + folga <= a or t >= b + folga) and abs(t - a) >= espaco for a, b in ocupados)


def planejar(projeto: dict, versao: dict, fim: float, cortes: list | None = None) -> list:
    """Lista de efeitos automáticos para esta versão (com '_auto': True), sem bater nos seus efeitos."""
    from .efeitos import DURACAO_PADRAO, resolver_tipo
    from .efeitos3d import EXEMPLOS
    m = modo(projeto, versao)
    if m == "calmo" or fim < 3 or projeto.get("ritmo_fixo"):     # ritmo_fixo: os automáticos já estão na linha do tempo
        return []
    cfg = _cfg()["modos"][m]
    sons = _cfg().get("sons") or {}
    semente = sum(map(ord, str(versao.get("nome", "V1")))) + (7 if m == "epico" else 0)
    rnd = random.Random(semente)
    manuais = list(projeto.get("efeitos") or []) + list(versao.get("efeitos") or [])
    ocupados = []
    for e in manuais:
        tipo = resolver_tipo(dict(e))
        ini = float(e.get("inicio", 0))
        ocupados.append((ini, ini + float(e.get("duracao", DURACAO_PADRAO.get(tipo, 3.0)))))
    folga = 0.3
    espaco = float(cfg.get("espacamento_minimo_s", 1.5)) + 0.05     # o mesmo mínimo do render: nada é empurrado
    out = []

    def por(ef: dict, t: float) -> bool:
        tipo = ef["tipo"]
        dur = float(ef.get("duracao", DURACAO_PADRAO.get(tipo, 2.0)))
        if t < 0 or t + dur > fim - 0.2 or not _livre(t, dur, ocupados, folga, espaco):
            return False
        novo = {**EXEMPLOS.get(tipo, {}), **ef, "inicio": round(t, 2), "duracao": dur, "_auto": True}
        if "som" in novo:
            novo["som"] = _som(novo["som"], semente + len(out))
        elif m == "epico" and (sons.get(tipo) or _som_viral(tipo)):
            novo["som"] = _som(sons.get(tipo) or _som_viral(tipo), semente + len(out))
        if not novo.get("som") or projeto.get("sfx_automaticos") is False:
            novo.pop("som", None)
        out.append(novo)
        ocupados.append((t, t + dur))
        return True

    for ef in cfg.get("abertura") or []:
        por(dict(ef), float(ef.get("inicio", 0)))
    # fim: pausa dramática antes do CTA/fechamento
    if cfg.get("antes_do_cta"):
        ef = dict(cfg["antes_do_cta"])
        por(ef, fim - float(ef.get("duracao", 1.5)) - 0.4)
    # cortes entre takes: transição em chicote (épico)
    trans = list(cfg.get("nos_cortes") or [])
    rnd.shuffle(trans)
    for k, c in enumerate(cortes or []):                      # uma transição por corte, alternando os tipos
        if trans:
            ef = dict(trans[k % len(trans)])
            por(ef, max(0.0, c - float(ef.get("duracao", 0.4)) / 2))
    # meio: uma interrupção de padrão a cada intervalo, alternando os efeitos sem repetir em seguida
    a, b = cfg.get("intervalo_s", [2.6, 3.4])
    lista = list(cfg.get("meio") or [])
    rnd.shuffle(lista)
    t, k = (2.2 if m == "viral" else 1.4), 0
    anterior = ((cfg.get("abertura") or [{}])[-1]).get("tipo")
    while t < fim - 2.0 and lista:
        colocou = False
        for j in range(len(lista)):                       # tenta os efeitos na vez; se não cabe, o próximo
            tipo = lista[(k + j) % len(lista)]
            if tipo == anterior or tipo == "camera_elegante" or \
                    any(e["tipo"] == tipo and abs(e["inicio"] - t) < 3.0 for e in out):   # sem repetir colado
                continue
            ef = {"tipo": tipo}
            if tipo == "cartao_3d":
                ef["modo"] = rnd.choice(["inclinar", "inclinar", "girar"]) if m == "epico" else "inclinar"
            if tipo in ("zoom_digital", "congelar"):
                ef["duracao"] = 1.6 if m == "epico" else 2.0
                ef["zoom"] = 1.18 if m == "epico" else 1.1
            if m == "epico":                               # épico: tudo mais curto e mais seguido
                ef["duracao"] = min(float(ef.get("duracao", DURACAO_PADRAO.get(tipo, 2.0))), 1.8)
            if por(ef, t):
                anterior, k, colocou = tipo, k + j + 1, True
                break
        t += rnd.uniform(a, b) if colocou else 0.5
    return sorted(out, key=lambda e: e["inicio"])


def intensidade_camera(projeto: dict, versao: dict | None = None) -> float:
    m = modo(projeto, versao)
    return 0.0 if m == "calmo" else float(_cfg()["modos"][m].get("camera", 0.8))


def espacamento(projeto: dict, versao: dict | None = None, padrao: float = 1.5) -> float:
    m = modo(projeto, versao)
    return padrao if m == "calmo" else float(_cfg()["modos"][m].get("espacamento_minimo_s", padrao))


def grade_epica(forca: float):
    """Contraste de cinema e luzes douradas (LUT por canal: rápido)."""
    x = np.arange(256, dtype=np.float32) / 255
    curva = x + forca * 0.18 * (x - 0.5) * (1 - np.abs(2 * x - 1))          # curva em S suave
    luz = np.clip((x - 0.6) / 0.4, 0, 1) * forca
    r = np.clip((curva + luz * 0.035) * 255, 0, 255).astype(np.uint8)
    g = np.clip((curva + luz * 0.015) * 255, 0, 255).astype(np.uint8)
    b = np.clip((curva - luz * 0.03 - forca * 0.01) * 255, 0, 255).astype(np.uint8)

    def f(q, t):
        out = np.empty_like(q)
        out[..., 0], out[..., 1], out[..., 2] = r[q[..., 0]], g[q[..., 1]], b[q[..., 2]]
        return out
    return f
