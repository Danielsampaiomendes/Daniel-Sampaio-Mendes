"""Legenda da fala na tela, sincronizada palavra a palavra.

Fonte fixa da marca (não entra no rodízio), blocos curtos de até 4 palavras, entrada e saída em fade com
deslize curto, palavra falada em dourado. Some no fechamento e fica fora da área de UI do Instagram.
Liga no projeto.yaml com `legendas: true` (ou um dicionário com ajustes, ver config/preferencias.yaml).
"""
from __future__ import annotations

import re

from .compositor import Camada
from .config import cor, load
from .corte import normalizar
from .fonts import marca
from .text import Estilo, render

PONTUACAO_FIM = re.compile(r"[.!?…:;]$")
CONECTIVOS = {"a", "o", "as", "os", "e", "de", "da", "do", "das", "dos", "em", "na", "no", "nas", "nos", "um",
              "uma", "que", "por", "para", "pra", "com", "se", "ao", "sua", "seu", "meu", "minha"}


def _cfg(projeto: dict) -> dict:
    c = dict(load("preferencias").get("legendas", {}))
    p = projeto.get("legendas")
    if isinstance(p, dict):
        c.update(p)
    return c


def ativas(projeto: dict) -> bool:
    p = projeto.get("legendas", False)
    return bool(p) and (not isinstance(p, dict) or p.get("ativo", True))


def palavras_na_base(clipes_meta: list, transcricoes: dict) -> list:
    """Leva as palavras do tempo de cada bruto para o tempo da base (cortes, velocidade e dissolves)."""
    out = []
    for c in clipes_meta:
        pal = transcricoes.get(c.get("caminho"))
        if not pal:
            continue
        ini, vel, dur = float(c["inicio"]), float(c.get("velocidade", 1.0)), float(c["duracao"])
        fim_src = ini + dur * vel
        for w in pal:
            if ini <= w["inicio"] < fim_src:
                a = c["inicio_base"] + (w["inicio"] - ini) / vel
                b = c["inicio_base"] + (min(w["fim"], fim_src) - ini) / vel
                out.append({"texto": w["texto"], "inicio": round(a, 3), "fim": round(max(b, a + 0.06), 3)})
    out.sort(key=lambda w: w["inicio"])
    return out


def aplicar_correcoes(palavras: list, correcoes: dict | None) -> list:
    """correcoes: {"trecho errado": "trecho certo"}, por sequência de palavras (ex.: nome da clínica)."""
    if not correcoes:
        return palavras
    pal = [dict(w) for w in palavras]
    for errado, certo in correcoes.items():
        alvo = [normalizar(x) for x in str(errado).split() if normalizar(x)]
        novo = str(certo).split()
        n = len(alvo)
        i = 0
        while i <= len(pal) - n and n:
            if [normalizar(w["texto"]) for w in pal[i:i + n]] == alvo:
                a, b = pal[i]["inicio"], pal[i + n - 1]["fim"]
                passo = (b - a) / max(1, len(novo))
                pal[i:i + n] = [{"texto": t, "inicio": round(a + k * passo, 3), "fim": round(a + (k + 1) * passo, 3)}
                                for k, t in enumerate(novo)]
                i += len(novo)
            else:
                i += 1
    return [w for w in pal if w["texto"]]


def blocos(palavras: list, max_palavras: int = 4, max_caracteres: int = 24, pausa_quebra: float = 0.35) -> list:
    """Agrupa em blocos curtos: quebra na pontuação, na pausa e no limite de tamanho."""
    out, atual = [], []
    for k, w in enumerate(palavras):
        atual.append(w)
        prox = palavras[k + 1] if k + 1 < len(palavras) else None
        chars = sum(len(x["texto"]) + 1 for x in atual)
        natural = prox is None or PONTUACAO_FIM.search(w["texto"]) or prox["inicio"] - w["fim"] > pausa_quebra
        if natural or len(atual) >= max_palavras or chars + len(prox["texto"]) > max_caracteres:
            # quebra por tamanho não deixa "da", "de", "que" pendurado no fim do bloco
            sobra = []
            if not natural and len(atual) > 1 and normalizar(atual[-1]["texto"]) in CONECTIVOS:
                sobra = [atual.pop()]
            out.append(atual)
            atual = sobra
    if atual:
        out.append(atual)
    return out


def _limpo(t: str) -> str:
    return re.sub(r"[.,;:…]+$", "", t.strip()).replace("*", "")


def camadas(projeto: dict, palavras: list, W: int, H: int, ate: float) -> tuple:
    """(camadas, textos) da legenda até o tempo `ate` (início do fechamento)."""
    cfg = _cfg(projeto)
    escala = W / 1080.0
    seg = load("marca")["area_segura"]
    pal = aplicar_correcoes(palavras, projeto.get("correcoes"))
    grupos = blocos([w for w in pal if w["inicio"] < ate], int(cfg.get("max_palavras", 4)),
                    int(cfg.get("max_caracteres", 24)), float(cfg.get("pausa_quebra_s", 0.35)))
    normal = Estilo(arquivo=cfg.get("fonte") or marca("legenda"), tamanho=float(cfg.get("tamanho", 58)) * escala,
                    cor=cor(cfg.get("cor", "off_white")), caixa_alta=bool(cfg.get("caixa_alta", False)))
    dest = Estilo(arquivo=normal.arquivo, tamanho=normal.tamanho, cor=cor(cfg.get("cor_destaque", "dourado")),
                  caixa_alta=normal.caixa_alta)
    larg = min(W - seg["esquerda"] - seg["direita"] - 40, int(cfg.get("largura_max_px", 820) * escala))
    centro_y = H * float(cfg.get("posicao", 0.66))
    ent, sai, desl = float(cfg.get("entrada_s", 0.18)), float(cfg.get("saida_s", 0.15)), float(cfg.get("deslize_px", 10))
    palavra_a_palavra = bool(cfg.get("palavra_a_palavra", True))
    out, textos = [], []
    for g_i, g in enumerate(grupos):
        t0 = g[0]["inicio"]
        prox = grupos[g_i + 1][0]["inicio"] if g_i + 1 < len(grupos) else ate
        # fica um pouco depois da última palavra (leitura), sem invadir o próximo bloco nem o fechamento
        t1 = min(max(g[-1]["fim"] + float(cfg.get("segurar_s", 0.35)), t0 + float(cfg.get("minimo_s", 0.7))),
                 prox - 0.02, ate)
        if t1 - t0 < 0.15:
            continue
        palavras_txt = [_limpo(w["texto"]) for w in g]
        textos.append(" ".join(palavras_txt))
        estados = range(len(g)) if palavra_a_palavra else [None]
        for k in estados:
            txt = " ".join(f"*{p}*" if k == j and p else p for j, p in enumerate(palavras_txt))
            img = render(txt, normal, dest, largura_max=larg)
            a = t0 if k in (None, 0) else g[k]["inicio"]
            b = t1 if k is None or k == len(g) - 1 else g[k + 1]["inicio"] - 1e-3
            if b <= a:
                continue
            primeiro, ultimo = k in (None, 0), k is None or k == len(g) - 1
            out.append(Camada(img, (W - img.width) // 2, int(centro_y - img.height / 2), a, b,
                              entrada=ent if primeiro else 0, saida=sai if ultimo else 0,
                              deslize=desl if primeiro else 0, nome=f"legenda{g_i}_{k}"))
    return out, textos


def achar_fala(palavras: list, frase: str) -> float | None:
    """Início (na base) da primeira ocorrência de `frase` na fala, para sincronizar mensagens."""
    alvo = [normalizar(x) for x in frase.split() if normalizar(x)]
    norm = [normalizar(w["texto"]) for w in palavras]
    for i in range(len(norm) - len(alvo) + 1):
        if alvo and norm[i:i + len(alvo)] == alvo:
            return palavras[i]["inicio"]
    return None
