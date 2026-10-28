"""Texto rico com palavra-chave em destaque.

Marcação usada em todo o projeto (igual ao banco de hooks):
  *palavra*  -> destaque (dourado, fonte de destaque da combinação)
  " / "      -> quebra de linha manual
Renderiza com supersampling 2x para bordas limpas.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

from PIL import Image, ImageDraw, ImageFilter

from .config import cor
from .fonts import fonte

SS = 2


@dataclass
class Estilo:
    arquivo: str
    tamanho: float
    cor: tuple = (245, 244, 241)
    peso: int | None = None
    caixa_alta: bool = False
    tracking: float = 0.0      # fração do tamanho, entre letras
    condensar: float = 1.0     # largura relativa (Abril Fatface condensada)

    @classmethod
    def de_config(cls, cfg: dict, tamanho_base: float, cor_rgb: tuple) -> "Estilo":
        return cls(
            arquivo=cfg["arquivo"],
            tamanho=tamanho_base * float(cfg.get("escala", 1.0)),
            cor=cor_rgb,
            peso=cfg.get("peso"),
            caixa_alta=bool(cfg.get("caixa_alta", False)),
            tracking=float(cfg.get("tracking", 0.0)),
            condensar=float(cfg.get("condensar", 1.0)),
        )

    def font(self, ss: int = SS):
        return fonte(self.arquivo, round(self.tamanho * ss), self.peso)


def contar_palavras(texto: str) -> int:
    return len(re.findall(r"\w+", texto.replace("*", "")))


def limpar(texto: str) -> str:
    return re.sub(r"\s*/\s*", " ", texto.replace("*", "")).strip()


def parse(texto: str) -> list:
    """Linhas (por ' / ' ou \\n) -> lista de palavras (texto, destaque)."""
    linhas = []
    destaque = False
    for bruta in re.split(r"\s+/\s+|\n", texto.strip()):
        palavras = []
        atual = ""
        for ch in bruta:
            if ch == "*":
                if atual:
                    palavras.append((atual, destaque))
                    atual = ""
                destaque = not destaque
            elif ch == " ":
                if atual:
                    palavras.append((atual, destaque))
                    atual = ""
                palavras.append((" ", destaque))
            else:
                atual += ch
        if atual:
            palavras.append((atual, destaque))
        linhas.append(palavras)
    return linhas


def _texto(s: str, e: Estilo) -> str:
    return s.upper() if e.caixa_alta else s


def _largura(s: str, e: Estilo, ss: int = SS) -> float:
    s = _texto(s, e)
    f = e.font(ss)
    if e.tracking:
        # mesmo avanço usado no desenho: espaçamento depois de cada letra
        return sum(f.getlength(c) for c in s) + e.tracking * e.tamanho * ss * len(s)
    return f.getlength(s)


def _quebrar(linhas: list, normal: Estilo, dest: Estilo, largura_max: float) -> list:
    """Quebra automática por largura, preservando quebras manuais."""
    saida = []
    for palavras in linhas:
        atual, larg = [], 0.0
        for p, d in palavras:
            e = dest if d else normal
            w = _largura(p, e)
            if p != " " and atual and larg + w > largura_max * SS:
                while atual and atual[-1][0] == " ":
                    atual.pop()
                saida.append(atual)
                atual, larg = [], 0.0
            if p == " " and not atual:
                continue
            atual.append((p, d))
            larg += w
        while atual and atual[-1][0] == " ":
            atual.pop()
        saida.append(atual)
    return saida


def render(
    texto: str,
    normal: Estilo,
    destaque: Estilo | None = None,
    largura_max: float = 900,
    alinhamento: str = "center",
    entrelinha: float = 1.12,
    sombra: bool = True,
) -> Image.Image:
    """Bloco de texto RGBA (escala 1x)."""
    destaque = destaque or replace(normal, cor=cor("dourado"))
    cond = normal.condensar
    linhas = _quebrar(parse(texto), normal, destaque, largura_max / cond)

    fn, fd = normal.font(), destaque.font()
    asc = max(fn.getmetrics()[0], fd.getmetrics()[0])
    desc = max(fn.getmetrics()[1], fd.getmetrics()[1])
    altura_linha = max(normal.tamanho, destaque.tamanho) * SS * entrelinha
    larguras = [sum(_largura(p, destaque if d else normal) for p, d in ln) for ln in linhas]
    pad = int(max(normal.tamanho, destaque.tamanho) * SS * 0.45)
    W = int(max(larguras + [1])) + 2 * pad
    H = int(asc + desc + altura_linha * (len(linhas) - 1)) + 2 * pad

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    y = pad + asc
    for ln, lw in zip(linhas, larguras):
        if alinhamento == "center":
            x = (W - lw) / 2
        elif alinhamento == "right":
            x = W - pad - lw
        else:
            x = pad
        for p, d in ln:
            e = destaque if d else normal
            s = _texto(p, e)
            f = e.font()
            if e.tracking:
                for c in s:
                    dr.text((x, y), c, font=f, fill=e.cor + (255,), anchor="ls")
                    x += f.getlength(c) + e.tracking * e.tamanho * SS
            else:
                dr.text((x, y), s, font=f, fill=e.cor + (255,), anchor="ls")
                x += f.getlength(s)
        y += altura_linha

    if cond != 1.0:
        img = img.resize((max(1, int(W * cond)), H), Image.LANCZOS)
    img = img.crop(img.getbbox() and _expandir(img.getbbox(), img.size, pad // 2))
    if sombra:
        img = com_sombra(img, raio=max(2, int(normal.tamanho * SS * 0.07)))
    return img.resize((max(1, img.width // SS), max(1, img.height // SS)), Image.LANCZOS)


def _expandir(bbox, size, m):
    return (max(0, bbox[0] - m), max(0, bbox[1] - m), min(size[0], bbox[2] + m), min(size[1], bbox[3] + m))


def com_sombra(img: Image.Image, raio: int, opacidade: float = 0.55, dy: int = 3) -> Image.Image:
    m = raio * 3
    base = Image.new("RGBA", (img.width + 2 * m, img.height + 2 * m), (0, 0, 0, 0))
    a = img.getchannel("A").point(lambda v: int(v * opacidade))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 255))
    sh.putalpha(a)
    base.alpha_composite(sh, (m, m + dy * SS))
    base = base.filter(ImageFilter.GaussianBlur(raio))
    base.alpha_composite(img, (m, m))
    return base


def pill(texto: str, arquivo: str, tamanho: float, cor_texto: tuple, cor_fundo: tuple | None,
         cor_borda: tuple | None = None, tracking: float = 0.14, pad_x: float = 1.3,
         pad_y: float = 0.7, alpha_fundo: int = 255) -> Image.Image:
    """Pílula (CTA, selo) com texto em caixa alta espaçada."""
    e = Estilo(arquivo=arquivo, tamanho=tamanho, cor=cor_texto, caixa_alta=True, tracking=tracking)
    f = e.font()
    w = _largura(texto, e)
    asc, desc = f.getmetrics()
    px, py = tamanho * SS * pad_x, tamanho * SS * pad_y
    W, H = int(w + 2 * px), int(asc * 0.78 + 2 * py)
    img = Image.new("RGBA", (W + 4, H + 4), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    r = H // 2
    if cor_fundo is not None:
        dr.rounded_rectangle((2, 2, W + 1, H + 1), radius=r, fill=cor_fundo + (alpha_fundo,))
    if cor_borda is not None:
        dr.rounded_rectangle((2, 2, W + 1, H + 1), radius=r, outline=cor_borda + (230,), width=SS * 2)
    x, y = px + 2, 2 + H / 2 + asc * 0.39
    s = texto.upper()
    for c in s:
        dr.text((x, y), c, font=f, fill=cor_texto + (255,), anchor="ls")
        x += f.getlength(c) + tracking * tamanho * SS
    return img.resize((max(1, img.width // SS), max(1, img.height // SS)), Image.LANCZOS)
