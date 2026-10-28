"""Logomarca oficial: símbolo (trevo dourado) + letreiro DIVINE / MEDICAL SPA.

Regra: nunca escrever "Divine Medical Spa" como texto comum; sempre esta composição.
Horizontal no topo (símbolo à esquerda, letreiro à direita, como no site) e empilhada no fechamento.
"""
from __future__ import annotations

import re
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw

from .config import ROOT, hexrgb, load
from .fonts import fonte
from .text import SS


def _rasterizar_svg(caminho, altura_px: int, cor: tuple) -> Image.Image:
    """Rasteriza o SVG do trevo (caminhos M/Q/Z, regra evenodd) sem dependências externas."""
    svg = caminho.read_text(encoding="utf-8")
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', svg).group(1).split()]
    escala = altura_px / vb[3]
    W, H = int(vb[2] * escala) + 2, altura_px + 2
    mascara = Image.new("1", (W, H), 0)
    for d in re.findall(r'\sd="([^"]+)"', svg):
        tokens = re.findall(r"[MQLZ]|-?\d+(?:\.\d+)?", d)
        subpaths, atual, i, pos = [], [], 0, (0.0, 0.0)
        while i < len(tokens):
            t = tokens[i]
            if t == "M":
                if atual:
                    subpaths.append(atual)
                pos = (float(tokens[i + 1]), float(tokens[i + 2]))
                atual = [pos]
                i += 3
            elif t == "L":
                pos = (float(tokens[i + 1]), float(tokens[i + 2]))
                atual.append(pos)
                i += 3
            elif t == "Q":
                c = (float(tokens[i + 1]), float(tokens[i + 2]))
                p = (float(tokens[i + 3]), float(tokens[i + 4]))
                for k in range(1, 9):
                    u = k / 8
                    atual.append((
                        (1 - u) ** 2 * pos[0] + 2 * (1 - u) * u * c[0] + u * u * p[0],
                        (1 - u) ** 2 * pos[1] + 2 * (1 - u) * u * c[1] + u * u * p[1],
                    ))
                pos = p
                i += 5
            elif t == "Z":
                if atual:
                    subpaths.append(atual)
                atual = []
                i += 1
            else:
                i += 1
        if atual:
            subpaths.append(atual)
        for sp in subpaths:
            m = Image.new("1", (W, H), 0)
            ImageDraw.Draw(m).polygon([((x - vb[0]) * escala, (y - vb[1]) * escala) for x, y in sp], fill=1)
            mascara = ImageChops.logical_xor(mascara, m)
    img = Image.new("RGBA", (W, H), cor + (0,))
    img.putalpha(mascara.convert("L"))
    return img


@lru_cache(maxsize=8)
def simbolo(altura: int) -> Image.Image:
    cfg = load("marca")["logo"]
    png = ROOT / cfg["simbolo_png"]
    if png.exists():
        im = Image.open(png).convert("RGBA")
        im = im.crop(im.getbbox())
    else:
        dourado = hexrgb(load("marca")["cores"]["dourado_escuro"])
        im = _rasterizar_svg(ROOT / cfg["simbolo_svg"], altura * SS * 2, dourado)
        im = im.crop(im.getbbox())
    return im.resize((max(1, round(im.width * altura / im.height)), altura), Image.LANCZOS)


def _linha_espacada(texto: str, arquivo: str, peso: int, tamanho: float, tracking: float, cor: tuple) -> Image.Image:
    f = fonte(arquivo, round(tamanho * SS), peso)
    larg = sum(f.getlength(c) for c in texto) + tracking * tamanho * SS * (len(texto) - 1)
    asc, desc = f.getmetrics()
    img = Image.new("RGBA", (int(larg) + 4, asc + desc + 4), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    x = 2
    for c in texto:
        dr.text((x, 2 + asc), c, font=f, fill=cor + (255,), anchor="ls")
        x += f.getlength(c) + tracking * tamanho * SS
    img = img.crop(img.getbbox())
    return img.resize((max(1, img.width // SS), max(1, img.height // SS)), Image.LANCZOS)


def _letreiro(tamanho1: float, tamanho2: float, gap: float):
    l = load("marca")["logo"]["letreiro"]
    c = hexrgb(l["cor"])
    a = _linha_espacada(l["linha1"], l["fonte1"], l["peso1"], tamanho1, l["tracking1"], c)
    b = _linha_espacada(l["linha2"], l["fonte2"], l["peso2"], tamanho2, l["tracking2"], c)
    W = max(a.width, b.width)
    img = Image.new("RGBA", (W, a.height + int(gap) + b.height), (0, 0, 0, 0))
    img.alpha_composite(a, ((W - a.width) // 2, 0))
    img.alpha_composite(b, ((W - b.width) // 2, a.height + int(gap)))
    return img


@lru_cache(maxsize=8)
def horizontal(altura: int = 56) -> Image.Image:
    s = simbolo(altura)
    let = _letreiro(altura * 0.50, altura * 0.20, altura * 0.13)
    gap = int(altura * 0.32)
    img = Image.new("RGBA", (s.width + gap + let.width, max(altura, let.height)), (0, 0, 0, 0))
    img.alpha_composite(s, (0, (img.height - s.height) // 2))
    img.alpha_composite(let, (s.width + gap, (img.height - let.height) // 2))
    return img


@lru_cache(maxsize=8)
def empilhado(altura_simbolo: int = 190) -> Image.Image:
    s = simbolo(altura_simbolo)
    let = _letreiro(altura_simbolo * 0.36, altura_simbolo * 0.14, altura_simbolo * 0.09)
    gap = int(altura_simbolo * 0.16)
    W = max(s.width, let.width)
    img = Image.new("RGBA", (W, s.height + gap + let.height), (0, 0, 0, 0))
    img.alpha_composite(s, ((W - s.width) // 2, 0))
    img.alpha_composite(let, ((W - let.width) // 2, s.height + gap))
    return img
