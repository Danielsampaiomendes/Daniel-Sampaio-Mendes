"""Corte limpo: tira enrolação, muletas ("hum", "ééé"), takes repetidos e pausas longas, a partir da transcrição.

Liga no projeto.yaml com `corte_limpo: true` (vale para todos os clipes com fala) ou por clipe.
Trechos que o automático não pega: `remover_trechos: ["frase exata que saiu ruim"]`.
O resultado de cada clipe fica em trabalho/cortes.md para revisar antes de exportar.
"""
from __future__ import annotations

import re
import unicodedata

from .config import load


def _cfg() -> dict:
    return load("preferencias").get("corte", {})


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", t)


def _e_muleta(texto: str, muletas: set) -> bool:
    bruto = texto.lower().strip(" .,!?…:;\"'")
    return bruto in muletas or normalizar(texto) in {normalizar(m) for m in muletas if normalizar(m)}


def marcar_remocoes(palavras: list, remover_trechos: list | None = None, so_pedidas: bool = False) -> dict:
    """{índice: motivo} das palavras que saem. `so_pedidas`: só as frases de remover_trechos (corte_limpo: so_frases)."""
    cfg = _cfg()
    muletas = set(cfg.get("muletas", [])) if not so_pedidas else set()
    fora: dict = {}
    norm = [normalizar(p["texto"]) for p in palavras]

    for i, p in enumerate(palavras):
        if _e_muleta(p["texto"], muletas):
            fora[i] = "muleta"

    # take repetido: a pessoa recomeça a frase; sai a tentativa anterior
    k_min = int(cfg.get("retake_min_palavras", 3))
    janela = int(cfg.get("retake_janela_palavras", 25))
    i = 0 if not so_pedidas else len(palavras)
    while i < len(palavras):
        achou = False
        for j in range(i + 1, min(len(palavras) - k_min + 1, i + janela + 1)):
            if norm[i:i + k_min] == norm[j:j + k_min] and all(norm[i:i + k_min]):
                for x in range(i, j):
                    fora.setdefault(x, "take repetido")
                i = j
                achou = True
                break
        if not achou:
            i += 1

    # frases pedidas: procuradas no texto bruto e também no texto que SOBRA depois de tirar muletas e takes, que é
    # o texto que aparece na legenda e nos pontos "!" (ex.: "O laser né elimina..." some com "O laser elimina...")
    vivos = [i for i in range(len(norm)) if i not in fora and norm[i]]
    seq = [norm[i] for i in vivos]
    for frase in remover_trechos or []:
        alvo = [normalizar(w) for w in frase.split() if normalizar(w)]
        n = len(alvo)
        if not n:
            continue
        for i in range(len(norm) - n + 1):
            if norm[i:i + n] == alvo:
                for x in range(i, i + n):
                    fora[x] = "removido no projeto"
        for k in range(len(seq) - n + 1):
            if seq[k:k + n] == alvo:
                for x in range(vivos[k], vivos[k + n - 1] + 1):
                    fora[x] = "removido no projeto"
    return fora


def segmentos(palavras: list, fora: dict, inicio: float, fim: float) -> list:
    """Trechos [(a, b)] mantidos, com pausas longas encurtadas para a pausa natural."""
    cfg = _cfg()
    limite = float(cfg.get("cortar_pausas_acima_s", 0.9))
    natural = float(cfg.get("pausa_natural_s", 0.5))
    antes, depois = float(cfg.get("margem_antes_s", 0.12)), float(cfg.get("margem_depois_s", 0.3))
    minimo = float(cfg.get("trecho_minimo_s", 0.5))

    mantidas = [p for i, p in enumerate(palavras) if i not in fora and inicio <= p["inicio"] < fim]
    if not mantidas:
        return []
    segs = []
    a = max(inicio, mantidas[0]["inicio"] - antes)
    ultimo = mantidas[0]
    for p, q in zip(mantidas, mantidas[1:]):
        # removida no meio (muleta, take) também vira corte, mesmo sem pausa longa
        removida_no_meio = any(i in fora for i, w in enumerate(palavras) if p["fim"] <= w["inicio"] < q["inicio"])
        gap = q["inicio"] - p["fim"]
        if gap > limite or removida_no_meio:
            folga = min(natural / 2, gap / 2) if not removida_no_meio else min(0.08, gap / 2)
            segs.append((a, min(fim, p["fim"] + max(folga, 0.04))))
            a = max(inicio, q["inicio"] - max(folga, 0.04))
        ultimo = q
    segs.append((a, min(fim, ultimo["fim"] + depois)))

    # junta trechos curtos demais com o vizinho (corte em cima de corte fica nervoso)
    junt = []
    for s in segs:
        if junt and (s[1] - s[0] < minimo or junt[-1][1] - junt[-1][0] < minimo) and s[0] - junt[-1][1] < 1.2:
            junt[-1] = (junt[-1][0], s[1])
        else:
            junt.append(s)
    return [(round(x, 3), round(y, 3)) for x, y in junt if y - x > 0.05]


def segmentos_sem_frases(palavras: list, fora: dict, inicio: float, fim: float) -> list:
    """corte_limpo: so_frases (ligado por "✂ Tirar esta frase" num projeto sem corte limpo): o clipe fica inteiro,
    com pausas e muletas, e só os trechos das frases marcadas saem."""
    buracos, k = [], 0
    idx = sorted(i for i in fora if inicio <= palavras[i]["inicio"] < fim)
    while k < len(idx):
        j = k
        while j + 1 < len(idx) and idx[j + 1] == idx[j] + 1:
            j += 1
        a = float(palavras[idx[k]]["inicio"]) - 0.04
        b = float(palavras[idx[j]]["fim"]) + 0.04
        prox = idx[j] + 1
        if prox < len(palavras):
            b = min(b, float(palavras[prox]["inicio"]) - 0.02)
        buracos.append((max(inicio, a), min(fim, b)))
        k = j + 1
    segs, t = [], inicio
    for a, b in buracos:
        if a - t > 0.05:
            segs.append((round(t, 3), round(a, 3)))
        t = max(t, b)
    if fim - t > 0.05:
        segs.append((round(t, 3), round(fim, 3)))
    return segs


def expandir_clipes(projeto: dict, transcrever_fn) -> tuple:
    """Troca cada clipe com corte limpo por subclipes (corte seco entre eles). Devolve (clipes, relatorio_md)."""
    from .ingest import probe, resolver
    geral = bool(projeto.get("corte_limpo", False))
    remover = projeto.get("remover_trechos") or []
    novos, md = [], []
    for c in projeto.get("clipes") or []:
        if not c.get("corte_limpo", geral) or c.get("mudo"):
            novos.append(c)
            continue
        arq = resolver(projeto, c["arquivo"])
        info = probe(arq)
        if not info["audio"]:
            novos.append(c)            # b-roll sem trilha de áudio: nada para transcrever
            continue
        pal = transcrever_fn(arq)
        ini = float(c.get("inicio", 0))
        fim = min(float(c.get("fim", info["duracao"])), info["duracao"] or 1e9)
        so_frases = str(c.get("corte_limpo", projeto.get("corte_limpo"))) == "so_frases"
        fora = marcar_remocoes(pal, remover, so_pedidas=so_frases)
        segs = segmentos_sem_frases(pal, fora, ini, fim) if so_frases else segmentos(pal, fora, ini, fim)
        if not segs:
            novos.append(c)
            md.append(f"## {c['arquivo']}\n\nSem fala reconhecida: clipe mantido inteiro.\n")
            continue
        for k, (a, b) in enumerate(segs):
            sub = {kk: v for kk, v in c.items() if kk not in ("inicio", "fim", "corte_limpo")}
            sub.update({"inicio": a, "fim": b})
            if k:
                sub["_corte_seco"] = True
            novos.append(sub)
        antes_s = fim - ini
        depois_s = sum(b - a for a, b in segs)
        md.append(f"## {c['arquivo']}\n\n{antes_s:.1f}s → {depois_s:.1f}s ({len(segs)} trechos)\n")
        for a, b in segs:
            txt = " ".join(p["texto"] for i, p in enumerate(pal) if i not in fora and a <= p["inicio"] < b)
            md.append(f"- {a:6.2f} a {b:6.2f}: {txt}")
        saiu = {}
        for i, motivo in sorted(fora.items()):
            if ini <= pal[i]["inicio"] < fim:
                saiu.setdefault(motivo, []).append(pal[i]["texto"])
        for motivo, ws in saiu.items():
            md.append(f"- **saiu ({motivo}):** {' '.join(ws)}")
        md.append("")
    return novos, "\n".join(md)
