"""Stories no "liquid glass" Divine (config/identidade.yaml, seção liquid_glass).

Foto real em cima, cartão de vidro escuro translúcido embaixo do rosto, borda dourada fina, esferas de vidro e brilhos
dourados. Texto em caixa alta e baixa: título em Poppins Light com 1 palavra *dourada*, apoio em Lora itálico dourado.
Tudo fora das zonas mortas do Stories (250 px em cima e 340 px embaixo). Figurinhas (enquete, caixinha, controle
deslizante) não são desenhadas: entram nativas pelo app do Instagram.

Um arquivo stories.yaml descreve as peças:
  fotos: pasta das fotos (relativa ao arquivo)
  stories:
    - id: E1
      foto: sorriso_mao_queixo.jpg
      selo: "Mito ou verdade?"          # opcional (pílula dourada)
      titulo: "Quem *nunca*?"
      apoio: "Conta quantos você já fez"
      blocos:                            # lista | opcoes | linhas | escala | texto | grande
        - {tipo: lista, itens: ["...", "..."]}
      chamada: "De 0 a 5, quantos você fez?"
      chamada_apoio: "Me conta no direct, sem julgamento"
Uso: python3 -m divine_studio stories-glass <stories.yaml> [--saida pasta]
"""
from __future__ import annotations

import dataclasses
import random
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from . import brand
from .config import hexrgb, load
from .text import Estilo, render

W, H = 1080, 1920
OFF, OURO, TEXTO, CINZA = hexrgb("#F5F4F1"), hexrgb("#CCBD91"), hexrgb("#CDCDCB"), hexrgb("#96948C")


def cfg() -> dict:
    return load("identidade").get("liquid_glass") or {}


def _estilo(nome: str, escala: float, cor: tuple) -> Estilo:
    f = cfg()["fontes"][nome]
    return Estilo(arquivo=f["arquivo"], tamanho=float(f["tamanho"]) * escala, cor=cor, peso=f.get("peso"))


def _txt(texto: str, normal: Estilo, largura: int, destaque: Estilo | None = None, alinhar: str = "center",
         entrelinha: float = 1.18) -> Image.Image:
    return render(str(texto), normal, destaque or dataclasses.replace(normal, cor=OURO), largura_max=largura,
                  alinhamento=alinhar, sombra=False, entrelinha=entrelinha)


def _arredondado(tam: tuple, raio: int) -> Image.Image:
    m = Image.new("L", tam, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, tam[0] - 1, tam[1] - 1), raio, fill=255)
    return m


def _mini_vidro(tam: tuple, raio: int = 26, borda: float = 0.35, fundo: float = 0.07) -> Image.Image:
    """Placa de vidro clara dentro do cartão (opções, linhas)."""
    w, h = tam
    im = Image.new("RGBA", tam, (255, 255, 255, int(255 * fundo)))
    grad = Image.linear_gradient("L").resize((w, h)).point(lambda v: int((255 - v) * 0.10))
    im.alpha_composite(Image.merge("RGBA", (*[Image.new("L", tam, 255)] * 3, grad)))
    im.putalpha(Image.composite(im.getchannel("A"), Image.new("L", tam, 0), _arredondado(tam, raio)))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), raio, outline=OURO + (int(255 * borda),), width=2)
    return im


def _coluna(partes: list, gap: int) -> tuple:
    alt = sum(p.height for p in partes) + gap * max(0, len(partes) - 1)
    return alt


# ---------------------------------------------------------------- blocos do conteúdo

def _bloco(b: dict, larg: int, e: float) -> Image.Image:
    tipo = b.get("tipo", "texto")
    corpo, dest = _estilo("corpo", e, OFF), _estilo("destaque", e, OFF)
    if tipo == "lista":
        linhas = []
        for it in b.get("itens") or []:
            t = _txt(it, dataclasses.replace(corpo, tamanho=corpo.tamanho * 0.95), larg - 56, alinhar="left")
            ln = Image.new("RGBA", (larg, max(t.height, 30)), (0, 0, 0, 0))
            d = ImageDraw.Draw(ln)
            r = int(7 * e)
            cy = int(corpo.tamanho * 0.62)
            d.ellipse((14 - r, cy - r, 14 + r, cy + r), outline=OURO + (230,), width=2)
            ln.alpha_composite(t, (48, 0))
            linhas.append(ln)
        return _empilha(linhas, int(22 * e), larg, "left")
    if tipo == "opcoes":
        ops = b.get("itens") or []
        n = max(1, len(ops))
        gap = int(22 * e)
        w = (larg - gap * (n - 1)) // n
        txts = [_txt(o, dataclasses.replace(dest, tamanho=dest.tamanho * 1.08), w - 30) for o in ops]
        h = max(t.height for t in txts) + int(70 * e)
        out = Image.new("RGBA", (larg, h), (0, 0, 0, 0))
        for k, t in enumerate(txts):
            x = k * (w + gap)
            out.alpha_composite(_mini_vidro((w, h)), (x, 0))
            out.alpha_composite(t, (x + (w - t.width) // 2, (h - t.height) // 2))
        return out
    if tipo == "linhas":
        rows = []
        for it in b.get("itens") or []:
            t = _txt(it, corpo, larg - 70, alinhar="left")
            h = t.height + int(40 * e)
            row = _mini_vidro((larg, h), raio=int(h / 2.2))
            row.alpha_composite(t, (36, (h - t.height) // 2))
            rows.append(row)
        return _empilha(rows, int(16 * e), larg, "left")
    if tipo == "escala":
        de, ate = int(b.get("de", 0)), int(b.get("ate", 10))
        h = int(130 * e)
        out = Image.new("RGBA", (larg, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(out)
        y = int(30 * e)
        x0, x1 = 30, larg - 30
        for x in range(x0, x1):                      # trilho dourado em degradê
            a = int(90 + 150 * (x - x0) / (x1 - x0))
            d.line((x, y - 3, x, y + 3), fill=OURO + (a,))
        num = _estilo("rodape", e * 1.35, TEXTO)
        for k in range(de, ate + 1):
            x = x0 + (x1 - x0) * (k - de) / max(1, ate - de)
            d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=OURO + (255,))
            t = _txt(str(k), num, 60)
            out.alpha_composite(t, (int(x - t.width / 2), y + 16))
        rot = _estilo("apoio", e * 0.55, OURO)
        if b.get("rotulo_de"):
            t = _txt(b["rotulo_de"], rot, larg // 2, alinhar="left")
            out.alpha_composite(t, (x0 - 6, h - t.height))
        if b.get("rotulo_ate"):
            t = _txt(b["rotulo_ate"], rot, larg // 2, alinhar="right")
            out.alpha_composite(t, (x1 + 6 - t.width, h - t.height))
        return out
    if tipo == "grande":
        return _txt(b.get("texto", ""), _estilo("apoio", e * 2.6, OURO), larg)
    # texto: parágrafo (forte em Poppins Medium)
    est = dest if b.get("forte") else dataclasses.replace(corpo, cor=TEXTO)
    return _txt(b.get("texto", ""), est, larg, alinhar=b.get("alinhar", "center"), entrelinha=1.3)


def _empilha(partes: list, gap: int, larg: int, alinhar: str = "center") -> Image.Image:
    partes = [p for p in partes if p is not None]
    h = _coluna(partes, gap)
    out = Image.new("RGBA", (larg, max(1, h)), (0, 0, 0, 0))
    y = 0
    for p in partes:
        x = 0 if alinhar == "left" else (larg - p.width) // 2
        out.alpha_composite(p, (x, y))
        y += p.height + gap
    return out


def _divisor(larg: int) -> Image.Image:
    im = Image.new("RGBA", (larg, 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = larg // 2
    for x in range(c - 150, c + 151):
        a = int(170 * (1 - abs(x - c) / 150))
        d.point((x, 10), fill=OURO + (a,))
    d.polygon([(c, 4), (c + 6, 10), (c, 16), (c - 6, 10)], fill=OURO + (230,))
    return im


def _selo(texto: str, e: float) -> Image.Image:
    t = _txt(texto, _estilo("destaque", e * 0.72, OURO), 600)
    w, h = t.width + 44, t.height + 18
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=OURO + (34,), outline=OURO + (190,), width=2)
    im.alpha_composite(t, (22, 9))
    return im


def conteudo(s: dict, larg: int, e: float) -> Image.Image:
    partes = [brand.horizontal(int(40 * e))]
    if s.get("selo"):
        partes.append(_selo(s["selo"], e))
    tit = _estilo("titulo", e, OFF)
    partes.append(_txt(s.get("titulo", ""), tit, larg, destaque=dataclasses.replace(tit, cor=OURO)))
    if s.get("apoio"):
        partes.append(_txt(s["apoio"], _estilo("apoio", e, OURO), larg))
    blocos = [_bloco(b, larg, e) for b in s.get("blocos") or []]
    topo = _empilha(partes[:1], 0, larg)
    resto = _empilha(partes[1:], int(14 * e), larg)
    corpo = _empilha(blocos, int(26 * e), larg) if blocos else None
    fim = []
    if s.get("chamada") or s.get("chamada_apoio"):
        fim.append(_divisor(larg))
        if s.get("chamada"):
            fim.append(_txt(s["chamada"], _estilo("destaque", e * 0.98, OURO), larg))
        if s.get("chamada_apoio"):
            fim.append(_txt(s["chamada_apoio"], dataclasses.replace(_estilo("corpo", e * 0.9, TEXTO)), larg))
    fim.append(_txt(str(cfg().get("rodape", "")), _estilo("rodape", e, CINZA), larg, entrelinha=1.35))
    return _empilha([topo, resto, corpo, _empilha(fim, int(16 * e), larg)], int(34 * e), larg)


# ---------------------------------------------------------------- fundo, vidro, esferas e brilhos

def fundo(foto: Path | None, topo_cartao: int) -> Image.Image:
    base = Image.new("RGB", (W, H), hexrgb("#12110F"))
    if foto and Path(foto).exists():
        im = ImageOps.exif_transpose(Image.open(foto)).convert("RGB")
        alvo_h = max(topo_cartao + 220, int(H * 0.55))
        esc = max(W / im.width, alvo_h / im.height)
        im = im.resize((int(im.width * esc), int(im.height * esc)), Image.LANCZOS)
        x = (im.width - W) // 2
        im = im.crop((x, 0, x + W, min(im.height, H)))
        # o que falta embaixo: a última faixa da foto, esticada e bem desfocada (continua a roupa e a luz)
        if im.height < H:
            faixa = im.crop((0, im.height - 60, W, im.height)).resize((W, H - im.height + 200))
            faixa = faixa.filter(ImageFilter.GaussianBlur(60))
            base.paste(faixa, (0, im.height - 200))
            mascara = Image.linear_gradient("L").resize((W, 200)).point(lambda v: 255 - v)
            bloco = Image.new("L", (W, im.height), 255)
            bloco.paste(mascara, (0, im.height - 200))
            base.paste(im, (0, 0), bloco)
        else:
            base.paste(im, (0, 0))
    # escurece suavemente de baixo para cima (o vidro e o texto ganham contraste)
    grad = Image.linear_gradient("L").resize((W, H)).point(lambda v: int(min(255, max(0, (v - 70) * 1.35)) * 0.9))
    base = Image.composite(Image.new("RGB", (W, H), hexrgb("#12110F")), base, grad)
    return base.convert("RGBA")


def vidro(bg: Image.Image, caixa: tuple) -> Image.Image:
    c = cfg()["cartao"]
    x0, y0, x1, y1 = caixa
    w, h = x1 - x0, y1 - y0
    reg = bg.crop(caixa).convert("RGB").filter(ImageFilter.GaussianBlur(float(c.get("desfoque", 30))))
    reg = Image.blend(reg, Image.new("RGB", (w, h), hexrgb(c.get("cor", "#1B1916"))), float(c.get("escurecer", 0.62)))
    reg = reg.convert("RGBA")
    brilho = Image.linear_gradient("L").resize((w, int(h * 0.35))).point(
        lambda v: int((255 - v) * float(c.get("brilho_topo", 0.1))))
    reflexo = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    reflexo.putalpha(Image.new("L", (w, h), 0))
    reflexo.paste(Image.merge("RGBA", (*[Image.new("L", brilho.size, 255)] * 3, brilho)), (0, 0))
    reg.alpha_composite(reflexo)
    raio = int(c.get("raio", 46))
    reg.putalpha(_arredondado((w, h), raio))
    d = ImageDraw.Draw(reg)
    d.rounded_rectangle((0, 0, w - 1, h - 1), raio, outline=OURO + (int(255 * float(c.get("borda_opacidade", 0.55))),), width=2)
    d.arc((raio // 2, 3, w - raio // 2, raio), 200, 340, fill=(255, 255, 255, 60), width=2)
    return reg


def esfera(bg: Image.Image, cx: int, cy: int, r: int) -> None:
    caixa = (cx - r, cy - r, cx + r, cy + r)
    reg = bg.crop(caixa).convert("RGB").filter(ImageFilter.GaussianBlur(10))
    reg = Image.blend(reg, Image.new("RGB", reg.size, (235, 228, 210)), 0.35).convert("RGBA")
    lado = int(r * 1.3)
    luz = Image.radial_gradient("L").resize((lado, lado)).point(lambda v: int(max(0, 160 - v) * 1.1))
    redondo = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(redondo).ellipse((0, 0, lado - 1, lado - 1), fill=255)
    luz = Image.composite(luz, Image.new("L", (lado, lado), 0), redondo.filter(ImageFilter.GaussianBlur(lado / 8)))
    camada = Image.new("RGBA", reg.size, (255, 255, 255, 0))
    camada.putalpha(Image.new("L", reg.size, 0))
    camada.paste(Image.merge("RGBA", (*[Image.new("L", luz.size, 255)] * 3, luz)), (int(r * 0.15), int(r * 0.1)))
    reg.alpha_composite(camada)
    m = Image.new("L", reg.size, 0)
    ImageDraw.Draw(m).ellipse((0, 0, 2 * r - 1, 2 * r - 1), fill=230)
    reg.putalpha(m)
    sombra = Image.new("RGBA", (2 * r + 60, 2 * r + 60), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).ellipse((30, 44, 2 * r + 30, 2 * r + 44), fill=(0, 0, 0, 90))
    bg.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(14)), (cx - r - 30, cy - r - 30))
    bg.alpha_composite(reg, (cx - r, cy - r))
    ImageDraw.Draw(bg).ellipse(caixa, outline=OURO + (110,), width=2)


def brilho(img: Image.Image, x: int, y: int, t: int) -> None:
    camada = Image.new("RGBA", (t * 4, t * 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    c = t * 2
    d.polygon([(c, 0), (c + t // 4, c - t // 4), (c * 2, c), (c + t // 4, c + t // 4), (c, c * 2),
               (c - t // 4, c + t // 4), (0, c), (c - t // 4, c - t // 4)], fill=OURO + (235,))
    glow = camada.filter(ImageFilter.GaussianBlur(t / 2))
    img.alpha_composite(glow, (x - c, y - c))
    img.alpha_composite(camada, (x - c, y - c))


# ---------------------------------------------------------------- peça

def desenhar(s: dict, foto: Path | None = None) -> Image.Image:
    c = cfg()["cartao"]
    m, base, pad = int(c.get("margem", 56)), int(c.get("base", 1560)), 56
    larg_cartao = W - 2 * m
    larg = larg_cartao - 2 * pad
    e = float(s.get("escala", 1.0))
    while True:                                       # cabe sem cobrir o rosto: reduz a letra aos poucos
        bloco = conteudo(s, larg, e)
        alt = bloco.height + 2 * pad
        if base - alt >= int(c.get("topo_minimo", 760)) or e < 0.62:
            break
        e *= 0.94
    topo = base - alt
    bg = fundo(foto, topo)
    # sombra do cartão
    sombra = Image.new("RGBA", (larg_cartao + 120, alt + 120), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle((60, 80, larg_cartao + 60, alt + 80), 46, fill=(0, 0, 0, 120))
    bg.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(26)), (m - 60, topo - 60))
    rnd = random.Random(str(s.get("id", s.get("titulo", ""))))
    bg.alpha_composite(vidro(bg, (m, topo, W - m, base)), (m, topo))
    n_esf = int(cfg().get("esferas", 2))                # esferas de vidro sobre a borda do cartão, longe do texto
    if n_esf >= 1:
        esfera(bg, W - m - 26, topo - 34, 62)
    if n_esf >= 2:
        esfera(bg, m + 4, topo + int(alt * 0.62), 30)
    bg.alpha_composite(bloco, (m + pad, topo + pad))
    for _ in range(int(cfg().get("brilhos", 7))):     # brilhos na moldura do cartão e no ar, nunca sobre o texto
        lado = rnd.random()
        if lado < 0.5:
            x, y = rnd.randint(m - 20, W - m + 20), topo + rnd.choice([-1, 1]) * rnd.randint(14, 70)
        else:
            x, y = rnd.choice([rnd.randint(24, m + 14), rnd.randint(W - m - 14, W - 24)]), rnd.randint(topo, base)
        brilho(bg, x, y, rnd.randint(5, 11))
    return bg.convert("RGB")


def gerar(arquivo: Path, saida: Path | None = None) -> list:
    arquivo = Path(arquivo)
    d = yaml.safe_load(arquivo.read_text(encoding="utf-8")) or {}
    fotos = (arquivo.parent / d.get("fotos", "fotos")).resolve()
    saida = Path(saida or arquivo.parent / "saida")
    saida.mkdir(parents=True, exist_ok=True)
    from .identidade import problemas_de_texto
    feitos = []
    for s in d.get("stories") or []:
        textos = [s.get("titulo"), s.get("apoio"), s.get("chamada"), s.get("chamada_apoio"), s.get("selo")]
        for b in s.get("blocos") or []:
            textos += list(b.get("itens") or []) + [b.get("texto")]
        for t in filter(None, textos):
            for p in problemas_de_texto(str(t)):
                print(f"  aviso {s.get('id')}: {p}")
        foto = fotos / s["foto"] if s.get("foto") else None
        img = desenhar(s, foto)
        destino = saida / f"{s.get('id', 'story')}_liquid_glass.png"
        img.save(destino, optimize=True)
        feitos.append(destino)
        print(f"  {s.get('id')}: {destino}")
    return feitos
