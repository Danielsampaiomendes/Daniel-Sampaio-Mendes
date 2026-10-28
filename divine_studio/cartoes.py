"""Cartão de nome (foto oficial em anel dourado, nome, selo verificado, @) e selo verificado dourado."""
from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw, ImageOps

from .config import ROOT, cor, hexrgb, load
from .fonts import fonte
from .text import SS, Estilo, render


def pessoa(chave: str) -> dict:
    p = load("pessoas").get(chave)
    if not p:
        raise SystemExit(f"Pessoa '{chave}' não está em config/pessoas.yaml")
    return p


@lru_cache(maxsize=16)
def foto_redonda(chave: str, diametro: int) -> Image.Image:
    """Foto oficial recortada em círculo com anel dourado (iniciais quando a foto não existe)."""
    p = pessoa(chave)
    d = diametro * SS
    anel = max(2, int(d * 0.05))
    arq = ROOT / p.get("foto", "")
    if p.get("foto") and arq.exists():
        foto = ImageOps.fit(Image.open(arq).convert("RGB"), (d - 2 * anel, d - 2 * anel), Image.LANCZOS)
    else:
        print(f"  aviso: foto oficial de {p['nome']} não encontrada ({p.get('foto')}); usando as iniciais")
        foto = Image.new("RGB", (d - 2 * anel, d - 2 * anel), hexrgb(p.get("cor", "#12110F")))
        ini = "".join(w[0] for w in p["nome"].replace("Dr. ", "").replace("Dra. ", "").replace("Enf. ", "").split()[:2])
        f = fonte("CormorantGaramond[wght].ttf", int(foto.height * 0.42), 500)
        ImageDraw.Draw(foto).text((foto.width / 2, foto.height / 2), ini, font=f, fill=cor("dourado"), anchor="mm")
    mask = Image.new("L", foto.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, foto.width - 1, foto.height - 1), fill=255)
    img = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((0, 0, d - 1, d - 1), fill=cor("dourado") + (255,))
    img.paste(foto, (anel, anel), mask)
    return img.resize((diametro, diametro), Image.LANCZOS)


@lru_cache(maxsize=8)
def selo_verificado(tamanho: int) -> Image.Image:
    """Selo de verificado dourado (roseta de 12 pontas com visto)."""
    import math
    d = tamanho * SS * 2
    img = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    pts = []
    for k in range(24):
        r = d / 2 * (1.0 if k % 2 == 0 else 0.84)
        a = math.pi * k / 12
        pts.append((d / 2 + r * math.cos(a), d / 2 + r * math.sin(a)))
    dr.polygon(pts, fill=cor("dourado") + (255,))
    w = max(2, d // 11)
    dr.line([(d * 0.30, d * 0.52), (d * 0.44, d * 0.66), (d * 0.71, d * 0.36)], fill=cor("fundo") + (255,), width=w,
            joint="curve")
    return img.resize((tamanho, tamanho), Image.LANCZOS)


def cartao_nome(chave: str, escala: float = 1.0, cor_placa: str | None = None, mostrar_registro: bool = True):
    """Placa com foto, nome (+ selo), @ e subtítulo. Devolve RGBA."""
    p = pessoa(chave)
    fundo = hexrgb(cor_placa) if cor_placa and cor_placa.startswith("#") else hexrgb(p.get("cor", "#12110F"))
    diam = int(104 * escala)
    foto = foto_redonda(chave, diam)
    nome = render(p["nome"], Estilo("Poppins-Medium.ttf", 34 * escala, cor("off_white")), largura_max=900 * escala,
                  sombra=False, alinhamento="left")
    linha2 = render(p["instagram"], Estilo("Poppins-Light.ttf", 24 * escala, cor("dourado")), largura_max=900 * escala,
                    sombra=False, alinhamento="left")
    sub_txt = p.get("subtitulo", "") + (f" · {p['registro']}" if mostrar_registro and p.get("registro") else "")
    sub = render(sub_txt, Estilo("Poppins-Light.ttf", 19 * escala, cor("texto")), largura_max=540 * escala,
                 sombra=False, alinhamento="left", entrelinha=1.25) if sub_txt else None
    selo = selo_verificado(int(30 * escala)) if p.get("verificado") else None
    gap = int(22 * escala)
    larg_txt = max(nome.width + (selo.width + int(8 * escala) if selo else 0), linha2.width, sub.width if sub else 0)
    pad = int(18 * escala)
    W = pad + diam + gap + larg_txt + pad * 2
    alt_txt = nome.height + linha2.height + (sub.height if sub else 0) - int(12 * escala)
    H = max(diam, alt_txt) + 2 * pad
    img = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((2, 2, W * 2 - 3, H * 2 - 3), radius=H, fill=fundo + (225,),
                                          outline=cor("dourado_escuro") + (220,), width=3)
    img = img.resize((W, H), Image.LANCZOS)
    img.alpha_composite(foto, (pad, (H - diam) // 2))
    x = pad + diam + gap
    y = (H - alt_txt) // 2 - int(4 * escala)
    img.alpha_composite(nome, (x, y))
    if selo:
        img.alpha_composite(selo, (x + nome.width + int(6 * escala), y + (nome.height - selo.height) // 2))
    y += nome.height - int(8 * escala)
    img.alpha_composite(linha2, (x, y))
    if sub:
        img.alpha_composite(sub, (x, y + linha2.height - int(6 * escala)))
    return img
