"""Truques de edição dos vídeos de referência (02/11/2026), no padrão Divine (preto, dourado, off-white).

Dos "16 efeitos de vídeo que o Claude cria":
  manchetes        parede de manchetes: recortes de jornal que pipocam em volta da pessoa
  zoom_atravessa   zoom que atravessa a imagem e sai na cena seguinte (transição)
  vertigem         efeito vertigo (dolly zoom), mesmo do 3D
  tela_verde       a pessoa recortada sobre outra imagem (tela verde sem tela verde)
  celular          mockup de celular flutuando com o vídeo ou uma imagem na tela
  visor            zoom digital com visor de câmera (REC, régua e 1.29x)
  recorte_papel    pessoa recortada com borda branca sobre papel, letras de recorte de revista
  interface        mundo de interface: pedido digitado, barra "editando", linha do tempo
  orbita           cartões orbitando em volta da pessoa (passam por trás dela)
  quebra_moldura   o vídeo vira um post e a pessoa sai para fora da moldura
  rabisco          contorno desenhado à mão, tremido, em volta da pessoa
  adesivo          texto adesivo inclinado que cola na tela
  antes_depois     cortina antes/depois DA EDIÇÃO (bruto x editado). Nunca resultado de paciente.
  profundidade     palavra grande atrás da pessoa (mesmo do texto_atras)
  recuo_revela     a imagem recua e revela a mesa de edição (linha do tempo, checklist)
  balao            balão de comentário do Instagram que estoura na tela
Do "Claude editor profissional" e dos finais: mural (parede de vídeos), saiba_mais (Toque em Saiba mais + seta),
ticket (instrução em papel térmico), seta_mao (seta escrita à mão "clica aqui"), cartela_tempo
(fundo escuro, timecode e "Poucos minutos depois").

Sem MediaPipe/rembg (recorte da pessoa), os efeitos que precisam da silhueta usam uma elipse no centro.
"""
from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .anim import clamp, ease_in_out, ease_out
from .config import cor, load
from .fonts import fonte

DOURADO = cor("dourado")
OFF = cor("off_white")
FUNDO = cor("fundo")


# ------------------------------------------------------------------ ajudantes
def _dentro(t, t0, dur):
    return t0 <= t <= t0 + dur


def _env(t, t0, dur, ent=0.25, sai=0.25):
    return ease_out(clamp((t - t0) / ent)) * ease_in_out(clamp((t0 + dur - t) / sai))


def _pop(u: float) -> float:
    """Escala com um quique curto (0 -> 1.08 -> 1)."""
    if u <= 0:
        return 0.0
    if u < 0.6:
        return 1.08 * ease_out(u / 0.6)
    return 1.08 - 0.08 * ease_in_out(clamp((u - 0.6) / 0.4))


def _f(arq: str, tam: float):
    try:
        return fonte(arq, max(8, int(tam)))
    except SystemExit:
        return fonte(load("fontes")["marca"]["pill"], max(8, int(tam)))


def _colar(out: np.ndarray, img: Image.Image, x: float, y: float, alpha: float = 1.0, escala: float = 1.0,
           angulo: float = 0.0) -> None:
    """Cola uma imagem RGBA no quadro (float32), centrada em (x, y), com escala e rotação."""
    if alpha <= 0.01 or escala <= 0.01:
        return
    im = img
    if abs(escala - 1) > 0.01:
        im = im.resize((max(1, int(im.width * escala)), max(1, int(im.height * escala))), Image.BILINEAR)
    if abs(angulo) > 0.1:
        im = im.rotate(angulo, resample=Image.BICUBIC, expand=True)
    H, W = out.shape[:2]
    x0, y0 = int(x - im.width / 2), int(y - im.height / 2)
    xs, ys, xe, ye = max(0, x0), max(0, y0), min(W, x0 + im.width), min(H, y0 + im.height)
    if xe <= xs or ye <= ys:
        return
    a = np.asarray(im, np.float32)[ys - y0:ye - y0, xs - x0:xe - x0]
    al = a[..., 3:4] / 255 * alpha
    out[ys:ye, xs:xe] = out[ys:ye, xs:xe] * (1 - al) + a[..., :3] * al


def _sombra(img: Image.Image, raio: int = 14, deslocar: int = 8, forca: int = 120) -> Image.Image:
    """Imagem com sombra suave embaixo (papel, cartão, adesivo)."""
    m = raio * 2 + deslocar
    base = Image.new("RGBA", (img.width + m * 2, img.height + m * 2), (0, 0, 0, 0))
    sombra = Image.new("RGBA", img.size, (0, 0, 0, forca))
    sombra.putalpha(img.getchannel("A").point(lambda v: v * forca // 255))
    base.paste(sombra, (m + deslocar // 2, m + deslocar), sombra)
    base = base.filter(ImageFilter.GaussianBlur(raio))
    base.alpha_composite(img, (m, m))
    return base


def _mascara(q: np.ndarray) -> np.ndarray:
    """Pessoa = 1 (H, W, 1). Sem recorte instalado: elipse no centro-alto (onde a pessoa costuma estar)."""
    try:
        from . import recorte
        m = recorte.mascara(q)
        if m is not None:
            return m.astype(np.float32)
    except Exception:
        pass
    H, W = q.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = ((xx - W * 0.5) / (W * 0.36)) ** 2 + ((yy - H * 0.52) / (H * 0.40)) ** 2
    return np.clip((1.08 - d) * 9, 0, 1)[..., None]


def _miniatura(q: np.ndarray, larg: int) -> Image.Image:
    im = Image.fromarray(q)
    return im.resize((larg, int(larg * im.height / im.width)), Image.BILINEAR)


def _cartao(conteudo: Image.Image, borda: int, cor_borda=(255, 255, 255), raio: int = 0) -> Image.Image:
    c = Image.new("RGBA", (conteudo.width + borda * 2, conteudo.height + borda * 2), cor_borda + (255,))
    c.paste(conteudo.convert("RGBA"), (borda, borda))
    if raio:
        m = Image.new("L", c.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, c.width - 1, c.height - 1), raio, fill=255)
        c.putalpha(m)
    return c


def _texto(txt: str, arq: str, tam: float, cor_txt, larg_max: int | None = None) -> Image.Image:
    fnt = _f(arq, tam)
    linhas = []
    for parte in str(txt).replace(" / ", "\n").split("\n"):
        palavras, atual = parte.split(), ""
        for p in palavras:
            teste = (atual + " " + p).strip()
            if larg_max and fnt.getlength(teste) > larg_max and atual:
                linhas.append(atual)
                atual = p
            else:
                atual = teste
        linhas.append(atual)
    alt = int(tam * 1.18)
    w = int(max(fnt.getlength(l) for l in linhas) + tam * 0.2)
    img = Image.new("RGBA", (max(1, w), alt * len(linhas) + int(tam * 0.3)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, l in enumerate(linhas):
        d.text((int(tam * 0.1), i * alt), l, font=fnt, fill=tuple(cor_txt) + (255,))
    return img


def _limpo(txt) -> str:
    return str(txt or "").replace("*", "")


# ------------------------------------------------------------------ 01 parede de manchetes
def _manchete(texto: str, k: int, escala: float) -> Image.Image:
    rnd = random.Random(k)
    larg = int((330 + rnd.randint(-30, 60)) * escala)
    topo = _texto("NOTÍCIAS DA DIVINE · HOJE", "CourierPrime-Regular.ttf", 15 * escala, (90, 86, 78))
    tit = _texto(_limpo(texto), "DMSerifDisplay-Regular.ttf", 40 * escala, (24, 22, 20), larg - int(30 * escala))
    alt = topo.height + tit.height + int(44 * escala)
    papel = Image.new("RGBA", (larg, alt), (246, 242, 232, 255))
    d = ImageDraw.Draw(papel)
    papel.alpha_composite(topo, (int(15 * escala), int(12 * escala)))
    d.line((int(15 * escala), topo.height + int(16 * escala), larg - int(15 * escala), topo.height + int(16 * escala)),
           fill=(60, 56, 50), width=max(1, int(2 * escala)))
    if k % 2 == 0:                                                     # marca-texto dourado em metade delas
        d.rectangle((int(12 * escala), topo.height + int(26 * escala) + tit.height // 2, larg - int(12 * escala),
                     topo.height + int(26 * escala) + tit.height - int(6 * escala)), fill=DOURADO + (255,))
    papel.alpha_composite(tit, (int(15 * escala), topo.height + int(24 * escala)))
    return _sombra(papel, int(10 * escala), int(6 * escala))


def manchetes(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    e = W / 1080
    textos = ef.get("textos") or [ef.get("texto") or "A Divine *agora* faz isso", "Tecnologia e cuidado médico",
                                  "Av. Paulista, ao lado do MASP"]
    lugares = [(0.78, 0.56), (0.22, 0.50), (0.24, 0.76), (0.77, 0.80), (0.5, 0.90)]   # fora da faixa dos títulos
    cartoes = [(_manchete(tx, k, e), lugares[k % len(lugares)], (-7, 5, -4, 6, -3)[k % 5]) for k, tx in enumerate(textos[:5])]

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        out = q.astype(np.float32)
        a = _env(t, t0, dur, 0.15, 0.3)
        for k, (img, (px, py), ang) in enumerate(cartoes):
            u = clamp((t - t0 - k * 0.28) / 0.35)
            _colar(out, img, px * W, py * H, a * clamp(u * 3), _pop(u), ang)
        return out.astype(np.uint8)
    return f


# ------------------------------------------------------------------ 02 zoom que atravessa
def zoom_atravessa(ef, combo, W, H, fps):
    from .efeitos_viral import _zoom
    t0, dur = ef["inicio"], float(ef.get("duracao", 0.6))
    px, py = ef.get("ponto", [0.5, 0.42])

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = (t - t0) / dur
        if u < 0.5:                                         # mergulha na imagem
            s = 1 + 3.2 * ease_in_out(u / 0.5) ** 1.6
            r = _zoom(q, s, px, py)
        else:                                               # sai de dentro da cena seguinte
            s = 1 + 1.6 * (1 - ease_out((u - 0.5) / 0.5))
            r = _zoom(q, s, 0.5, 0.5)
        borrao = math.sin(math.pi * u)
        if borrao > 0.15:
            r = np.asarray(Image.fromarray(r).filter(ImageFilter.GaussianBlur(borrao * 6 * W / 1080)))
        return r
    return f


# ------------------------------------------------------------------ 04 tela verde
def _fundo_imagem(ef, W, H) -> np.ndarray | None:
    from pathlib import Path

    from .config import ROOT
    arq = ef.get("imagem") or ef.get("fundo")
    if not arq:
        try:
            from .biblioteca import foto_do_tema
            arq = foto_do_tema(ef.get("tema", "clinica"))
        except Exception:
            arq = None
    if arq:
        p = Path(arq)
        p = p if p.is_absolute() else (Path(ef["_pasta"]) / p if ef.get("_pasta") and (Path(ef["_pasta"]) / p).exists()
                                       else ROOT / p)
        if p.exists():
            im = ImageOps.fit(Image.open(p).convert("RGB"), (W, H), Image.LANCZOS)
            return np.asarray(im, np.float32)
    return None


def tela_verde(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    fundo = _fundo_imagem(ef, W, H)
    if fundo is None:                                       # sem foto: luz dourada e preto (estúdio Divine)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        g = np.clip(1 - np.hypot((xx - W * 0.7) / W, (yy - H * 0.25) / H) * 1.6, 0, 1)[..., None]
        fundo = np.array(FUNDO, np.float32) * (1 - g) + np.array(DOURADO, np.float32) * g * 0.55

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.3, 0.3)
        m = _mascara(q)
        qf = q.astype(np.float32)
        troca = qf * m + fundo * (1 - m)
        return (qf * (1 - a) + troca * a).astype(np.uint8)
    return f


# ------------------------------------------------------------------ 05 mockup de celular
def _celular(tela: Image.Image, larg: int) -> Image.Image:
    alt = int(larg * 2.05)
    b = max(6, larg // 22)
    corpo = Image.new("RGBA", (larg, alt), (0, 0, 0, 0))
    d = ImageDraw.Draw(corpo)
    d.rounded_rectangle((0, 0, larg - 1, alt - 1), larg // 7, fill=(18, 17, 16, 255), outline=DOURADO + (255,),
                        width=max(2, larg // 120))
    tela = ImageOps.fit(tela.convert("RGB"), (larg - b * 2, alt - b * 2), Image.LANCZOS)
    m = Image.new("L", tela.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, tela.width - 1, tela.height - 1), larg // 9, fill=255)
    corpo.paste(tela, (b, b), m)
    d.rounded_rectangle((larg * 0.36, b + 6, larg * 0.64, b + 6 + larg // 14), larg // 28, fill=(0, 0, 0, 255))
    return _sombra(corpo, larg // 18, larg // 30, 150)


def celular(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    lado = ef.get("lado", "esquerda")
    larg = int(W * float(ef.get("tamanho", 0.30)))
    fundo = _fundo_imagem(ef, W, H) if (ef.get("imagem") or ef.get("fundo")) else None
    fixo = _celular(Image.fromarray(fundo.astype(np.uint8)), larg) if fundo is not None else None
    cache = {}

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = clamp((t - t0) / 0.5)
        a = _env(t, t0, dur, 0.3, 0.35)
        k = int((t - t0) * 6)                                # vídeo na tela: atualiza 6x por segundo
        img = fixo or cache.get(k) or cache.setdefault(k, _celular(Image.fromarray(q), larg))
        out = q.astype(np.float32)
        x = W * (0.24 if lado == "esquerda" else 0.76)
        y = H * 0.52 + math.sin((t - t0) * 2.2) * H * 0.008 + (1 - ease_out(u)) * H * 0.25
        _colar(out, img, x, y, a, 1.0, (8 if lado == "esquerda" else -8) * (1 - 0.5 * ease_out(u)))
        return out.astype(np.uint8)
    return f


# ------------------------------------------------------------------ 06 visor de câmera
def visor(ef, combo, W, H, fps):
    from .efeitos_viral import _zoom
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    zoom = float(ef.get("zoom", 1.29))
    px, py = ef.get("ponto", [0.5, 0.38])
    e = W / 1080
    fnt = _f("CourierPrime-Regular.ttf", 26 * e)
    fnt_g = _f("Poppins-Medium.ttf", 40 * e)

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = ease_in_out(clamp((t - t0) / (dur * 0.7)))
        s = 1 + (zoom - 1) * u
        r = Image.fromarray(_zoom(q, s, px, py)).convert("RGBA")
        cam = Image.new("RGBA", r.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(cam)
        a = int(255 * _env(t, t0, dur, 0.2, 0.25))
        br = (*OFF, a)
        cx, cy, lw = px * W, py * H, max(2, int(3 * e))
        L, A = W * 0.20, int(40 * e)
        for sx in (-1, 1):
            for sy in (-1, 1):
                x, y = cx + sx * L, cy + sy * L * 0.9
                d.line((x, y, x - sx * A, y), fill=br, width=lw)
                d.line((x, y, x, y - sy * A), fill=br, width=lw)
        yb = H * 0.80
        seg = t - t0 + 7.5
        d.ellipse((W * 0.08, yb - 9 * e, W * 0.08 + 18 * e, yb + 9 * e), fill=(214, 62, 52, a if int(t * 2) % 2 else a // 3))
        d.text((W * 0.08 + 28 * e, yb - 16 * e), f"REC  00:00:{int(seg):02d}:{int((seg % 1) * 30):02d}", font=fnt, fill=br)
        for k in range(21):                                   # régua do zoom
            x = W * 0.42 + k * W * 0.017
            d.line((x, yb - (12 if k % 5 == 0 else 6) * e, x, yb + (12 if k % 5 == 0 else 6) * e), fill=br, width=lw - 1)
        xm = W * 0.42 + (s - 1) / (zoom - 1 + 1e-6) * 20 * W * 0.017
        d.polygon([(xm, yb - 20 * e), (xm - 8 * e, yb - 32 * e), (xm + 8 * e, yb - 32 * e)], fill=(*DOURADO, a))
        d.text((W * 0.80, yb - 26 * e), f"{s:.2f}x", font=fnt_g, fill=br)
        r.alpha_composite(cam)
        return np.asarray(r.convert("RGB"))
    return f


# ------------------------------------------------------------------ 07 recorte de papel
def _letras_recorte(texto: str, escala: float) -> Image.Image:
    rnd = random.Random(texto)
    fontes_ = ["DMSerifDisplay-Regular.ttf", "BebasNeue-Regular.ttf", "AbrilFatface-Regular.ttf", "Gloock-Regular.ttf",
               "CourierPrime-Regular.ttf", "Cinzel[wght].ttf"]
    papeis = [(246, 242, 232), (20, 19, 17), DOURADO, (235, 230, 214), (60, 52, 40)]
    pecas = []
    for ch in _limpo(texto).upper():
        if ch == " ":
            pecas.append(None)
            continue
        tam = rnd.randint(70, 96) * escala
        bg = rnd.choice(papeis)
        fg = (20, 19, 17) if sum(bg) > 400 else OFF
        im = _texto(ch, rnd.choice(fontes_), tam, fg)
        p = Image.new("RGBA", (im.width + int(14 * escala), im.height + int(6 * escala)), bg + (255,))
        p.alpha_composite(im, (int(7 * escala), 0))
        pecas.append(p.rotate(rnd.uniform(-8, 8), expand=True, resample=Image.BICUBIC))
    larg = sum(p.width if p else int(30 * escala) for p in pecas)
    alt = max(p.height for p in pecas if p) if any(pecas) else 10
    linha = Image.new("RGBA", (max(1, larg), alt), (0, 0, 0, 0))
    x = 0
    for p in pecas:
        if p is None:
            x += int(30 * escala)
            continue
        linha.alpha_composite(p, (x, (alt - p.height) // 2))
        x += p.width - int(4 * escala)
    return _sombra(linha, int(6 * escala), int(4 * escala), 110)


def recorte_papel(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    e = W / 1080
    letras = _letras_recorte(ef.get("texto", "Divine"), e)
    rnd = np.random.default_rng(3)
    papel = np.ones((H, W, 3), np.float32) * np.array([238, 233, 220], np.float32)
    papel += rnd.normal(0, 4, (H, W, 1)).astype(np.float32)                 # textura de papel
    faixa = np.zeros((H, W, 1), np.float32)                                 # rasgo dourado atrás da pessoa
    yy, xx = np.mgrid[0:H, 0:W]
    borda = H * 0.30 + np.sin(xx / W * 22) * H * 0.012 + (xx / W) * H * 0.08
    faixa[(yy > borda) & (yy < borda + H * 0.22)] = 1
    papel = papel * (1 - faixa) + np.array(DOURADO, np.float32) * faixa

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.18, 0.25)
        m = _mascara(q)
        grosso = np.asarray(Image.fromarray((m[..., 0] * 255).astype(np.uint8)).filter(
            ImageFilter.MaxFilter(int(9 * e) * 2 + 1)), np.float32)[..., None] / 255
        qf = q.astype(np.float32)
        r = papel * (1 - grosso) + 255 * grosso                              # borda branca de tesoura
        r = r * (1 - m) + qf * m
        out = qf * (1 - a) + r * a
        u = clamp((t - t0 - 0.25) / 0.4)
        _colar(out, letras, W * 0.5, H * 0.62, a * clamp(u * 3), _pop(u), -3)
        return np.clip(out, 0, 255).astype(np.uint8)
    return f


# ------------------------------------------------------------------ 08 mundo de interface
def interface(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.5))
    e = W / 1080
    pedido = _limpo(ef.get("texto", "edita meu reel no padrão Divine"))
    fnt = _f("Poppins-Medium.ttf", 30 * e)
    fnt_p = _f("Poppins-Light.ttf", 24 * e)
    thumbs = {}

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = t - t0
        a = _env(t, t0, dur, 0.25, 0.3)
        out = q.astype(np.float32)
        # 1) pedido sendo digitado
        n = int(len(pedido) * clamp(u / 1.1))
        caixa = Image.new("RGBA", (int(W * 0.56), int(96 * e)), (24, 22, 20, 235))
        d = ImageDraw.Draw(caixa)
        d.rounded_rectangle((0, 0, caixa.width - 1, caixa.height - 1), int(22 * e), outline=DOURADO + (255,), width=2)
        d.text((24 * e, 30 * e), pedido[:n] + ("|" if int(u * 3) % 2 else ""), font=fnt, fill=OFF + (255,))
        _colar(out, _sombra(caixa, int(10 * e), 4), W * 0.33, H * 0.34, a * clamp(u * 4))
        # 2) barra editando 0 -> 100%
        if u > 0.9:
            p = clamp((u - 0.9) / 1.4)
            barra = Image.new("RGBA", (int(W * 0.40), int(70 * e)), (24, 22, 20, 235))
            d = ImageDraw.Draw(barra)
            d.text((18 * e, 8 * e), f"editando… {int(p * 100)}%", font=fnt_p, fill=OFF + (255,))
            d.rounded_rectangle((18 * e, 46 * e, barra.width - 18 * e, 56 * e), 5, fill=(70, 64, 54, 255))
            d.rounded_rectangle((18 * e, 46 * e, 18 * e + (barra.width - 36 * e) * p, 56 * e), 5, fill=DOURADO + (255,))
            _colar(out, _sombra(barra, int(8 * e), 4), W * 0.26, H * 0.42, a * clamp((u - 0.9) * 4))
        # 3) linha do tempo com miniaturas do próprio vídeo
        if u > 1.5:
            k = len(thumbs)
            if k < 6 and int((u - 1.5) * 8) >= k:
                thumbs[k] = _cartao(_miniatura(q, int(78 * e)), 3, DOURADO)
            tira = Image.new("RGBA", (int(W * 0.62), int(190 * e)), (18, 17, 16, 230))
            d = ImageDraw.Draw(tira)
            d.text((16 * e, 8 * e), "LINHA DO TEMPO", font=fnt_p, fill=DOURADO + (255,))
            for i in sorted(thumbs):
                tira.alpha_composite(thumbs[i], (int(16 * e + i * 102 * e), int(46 * e)))
            _colar(out, _sombra(tira, int(10 * e), 5), W * 0.36, H * 0.78, a * clamp((u - 1.5) * 4))
        return out.astype(np.uint8)
    return f


# ------------------------------------------------------------------ 09 órbita
def orbita(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    e = W / 1080
    textos = ef.get("textos") or ["Avaliação", "Tecnologia", "Cuidado", "Protocolo"]
    cartoes = []
    for k, tx in enumerate(textos[:6]):
        c = Image.new("RGBA", (int(230 * e), int(300 * e)), (24, 22, 20, 255))
        d = ImageDraw.Draw(c)
        d.rounded_rectangle((0, 0, c.width - 1, c.height - 1), int(18 * e), outline=DOURADO + (255,), width=3)
        tt = _texto(_limpo(tx), "DMSerifDisplay-Regular.ttf", 38 * e, OFF, c.width - int(30 * e))
        c.alpha_composite(tt, ((c.width - tt.width) // 2, c.height - tt.height - int(26 * e)))
        d.ellipse((c.width / 2 - 36 * e, 60 * e, c.width / 2 + 36 * e, 132 * e), outline=DOURADO + (255,), width=3)
        cartoes.append(_sombra(c, int(10 * e), 5))

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.35, 0.35)
        qf = q.astype(np.float32)
        m = _mascara(q)
        tras, frente = qf.copy(), qf.copy()
        for k, c in enumerate(cartoes):
            ang = (t - t0) * 1.6 + k * 2 * math.pi / len(cartoes)
            x = W * 0.5 + math.cos(ang) * W * 0.40
            y = H * 0.50 + math.sin(ang) * H * 0.06
            prof = math.sin(ang)                              # > 0 na frente da pessoa
            esc = 0.75 + 0.25 * (prof + 1) / 2
            _colar(frente if prof > 0 else tras, c, x, y, a * (0.55 + 0.45 * (prof + 1) / 2), esc, -math.cos(ang) * 12)
        out = tras * (1 - m) + qf * m                          # os de trás passam atrás da pessoa
        dif = np.abs(frente - qf).sum(axis=2, keepdims=True) > 1
        out = np.where(dif, frente, out)
        return out.astype(np.uint8)
    return f


# ------------------------------------------------------------------ 10 quebra de moldura
def quebra_moldura(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    e = W / 1080
    usuario = ef.get("usuario", "@dvmedicalspa")
    fnt = _f("Poppins-Medium.ttf", 26 * e)

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = ease_in_out(clamp((t - t0) / 0.6))
        a = _env(t, t0, dur, 0.2, 0.3)
        qf = q.astype(np.float32)
        fundo = np.asarray(Image.fromarray(q).filter(ImageFilter.GaussianBlur(24 * e)), np.float32) * 0.35
        s = 1 - 0.30 * u
        pw, ph = int(W * s), int(H * s * 0.80)
        x0, y0 = (W - pw) // 2, int(H * 0.28 - (H * 0.10) * u)
        post = Image.fromarray(q).resize((pw, int(H * s)), Image.BILINEAR).crop((0, int(H * s * 0.12), pw, int(H * s * 0.12) + ph))
        cartao = Image.new("RGBA", (pw + int(24 * e), ph + int(150 * e)), (250, 248, 244, 255))
        d = ImageDraw.Draw(cartao)
        cartao.paste(post, (int(12 * e), int(78 * e)))
        d.ellipse((14 * e, 16 * e, 62 * e, 64 * e), fill=DOURADO + (255,))
        d.text((76 * e, 26 * e), usuario, font=fnt, fill=(30, 28, 26, 255))
        yb = ph + int(96 * e)
        for i, simb in enumerate(("♡", "◯", "➤")):
            d.text((20 * e + i * 60 * e, yb), simb, font=_f("Poppins-Medium.ttf", 34 * e), fill=(30, 28, 26, 255))
        out = fundo.copy()
        _colar(out, _sombra(cartao, int(14 * e), 8), W / 2, y0 + cartao.height / 2, 1.0)
        # a pessoa sai para fora da moldura (por cima do topo do post)
        m = _mascara(q)
        mm = np.asarray(Image.fromarray((m[..., 0] * 255).astype(np.uint8)).resize((pw, int(H * s))), np.float32)[..., None] / 255
        pessoa = np.asarray(Image.fromarray(q).resize((pw, int(H * s))), np.float32)
        py0 = y0 + int(78 * e) - int(H * s * 0.12)
        corte = max(0, y0 + int(78 * e) - py0)                 # só a parte acima da moldura
        ys, ye = max(0, py0), min(H, py0 + corte)
        if ye > ys:
            sub = slice(ys - py0, ye - py0)
            xx = slice(x0 + int(12 * e) - int(12 * e), x0 + pw)
            reg = out[ys:ye, xx]
            mk = mm[sub, :reg.shape[1]] * u
            out[ys:ye, xx] = reg * (1 - mk) + pessoa[sub, :reg.shape[1]] * mk
        return (qf * (1 - a) + out * a).astype(np.uint8)
    return f


# ------------------------------------------------------------------ 11 rabisco tremido
def rabisco(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    e = W / 1080
    tinta = cor(ef.get("cor", "dourado")) if ef.get("cor") != "branco" else (255, 255, 255)

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = clamp((t - t0) / 0.5)
        a = _env(t, t0, dur, 0.1, 0.25)
        m = (_mascara(q)[..., 0] * 255).astype(np.uint8)
        ferv = int((t - t0) * 12)                              # "boil": o traço treme 12x por segundo
        rnd = random.Random(ferv)
        mi = Image.fromarray(m).resize((W // 4, H // 4))
        borda = mi.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.FIND_EDGES)
        pts = np.argwhere(np.asarray(borda) > 60)
        im = Image.fromarray(q).convert("RGBA")
        cam = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(cam)
        if len(pts):
            pts = pts[np.argsort(np.arctan2(pts[:, 0] - pts[:, 0].mean(), pts[:, 1] - pts[:, 1].mean()))]
            pts = pts[:: max(1, len(pts) // 90)]
            n = int(len(pts) * ease_out(u))
            linha = [(p[1] * 4 + rnd.uniform(-5, 5) * e, p[0] * 4 + rnd.uniform(-5, 5) * e) for p in pts[:n]]
            if len(linha) > 2:
                d.line(linha, fill=tinta + (int(255 * a),), width=max(3, int(7 * e)), joint="curve")
        for k in range(3):                                   # brilhinhos desenhados
            cx, cy = W * (0.18 + 0.64 * (k % 2)) + rnd.uniform(-4, 4), H * (0.30 + 0.14 * k) + rnd.uniform(-4, 4)
            r = 18 * e
            for ang in range(0, 360, 60):
                d.line((cx, cy, cx + math.cos(math.radians(ang)) * r, cy + math.sin(math.radians(ang)) * r),
                       fill=tinta + (int(220 * a * u),), width=max(2, int(4 * e)))
        im.alpha_composite(cam)
        return np.asarray(im.convert("RGB"))
    return f


# ------------------------------------------------------------------ 12 texto adesivo
def _adesivo(texto: str, e: float) -> Image.Image:
    tt = _texto(_limpo(texto), "Poppins-Medium.ttf", 52 * e, (20, 19, 17))
    pad = int(26 * e)
    c = Image.new("RGBA", (tt.width + pad * 2, tt.height + pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(c)
    d.rounded_rectangle((0, 0, c.width - 1, c.height - 1), int(16 * e), fill=(255, 255, 255, 255))
    d.rounded_rectangle((int(6 * e), int(6 * e), c.width - 1 - int(6 * e), c.height - 1 - int(6 * e)), int(12 * e),
                        fill=DOURADO + (255,))
    c.alpha_composite(tt, (pad, pad // 2 - int(4 * e)))
    return _sombra(c, int(10 * e), int(6 * e), 140)


def adesivo(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.2))
    e = W / 1080
    img = _adesivo(ef.get("texto", "agende sua avaliação"), e)
    px, py = ef.get("ponto", [0.5, 0.70])

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = clamp((t - t0) / 0.3)
        out = q.astype(np.float32)
        _colar(out, img, px * W, py * H, _env(t, t0, dur, 0.05, 0.2), _pop(u) * (1.6 - 0.6 * ease_out(u)), -6)
        return out.astype(np.uint8)
    return f


# ------------------------------------------------------------------ 13 antes e depois DA EDIÇÃO
def antes_depois(ef, combo, W, H, fps):
    """Mostra a mesma imagem sem tratamento (antes) e editada (depois). Uso: bastidores da edição. NUNCA para
    resultado de paciente (CFM 2.336/2023)."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    e = W / 1080
    fnt = _f("Poppins-Medium.ttf", 28 * e)

    def pilula(txt):
        im = _texto(txt, "Poppins-Medium.ttf", 28 * e, OFF)
        c = Image.new("RGBA", (im.width + int(40 * e), im.height + int(10 * e)), (18, 17, 16, 200))
        ImageDraw.Draw(c).ellipse((12 * e, c.height / 2 - 5 * e, 22 * e, c.height / 2 + 5 * e), fill=OFF + (255,))
        c.alpha_composite(im, (int(28 * e), int(4 * e)))
        return c
    p_antes, p_depois = pilula("antes"), pilula("depois")

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = ease_in_out(clamp((t - t0) / dur))
        qf = q.astype(np.float32)
        cinza = qf.mean(axis=2, keepdims=True)
        bruto = (qf * 0.75 + cinza * 0.25) * 0.88 + 18                       # sem cor e sem contraste: o bruto
        x = int(W * (0.85 - 0.75 * u))
        out = qf.copy()
        out[:, :x] = bruto[:, :x]
        a = _env(t, t0, dur, 0.15, 0.2)
        luz = np.exp(-((np.arange(W) - x) / (6 * e)) ** 2)[None, :, None] * 255 * a
        out = np.clip(out + luz, 0, 255)
        _colar(out, p_antes, W * 0.14, H * 0.70, a)
        _colar(out, p_depois, W * 0.86, H * 0.70, a)
        return out.astype(np.uint8)
    return f


# ------------------------------------------------------------------ 15 recuo que revela
def recuo_revela(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    e = W / 1080
    rnd = random.Random(5)
    mesa = Image.new("RGB", (W, H), FUNDO)
    d = ImageDraw.Draw(mesa)
    fnt = _f("Poppins-Light.ttf", 24 * e)
    y0 = int(H * 0.74)
    for faixa in range(3):                                    # trilhas da linha do tempo
        x = int(W * 0.04)
        while x < W * 0.96:
            w = rnd.randint(60, 180) * e
            d.rounded_rectangle((x, y0 + faixa * 46 * e, x + w, y0 + faixa * 46 * e + 34 * e), 6,
                                fill=[DOURADO, (122, 110, 86), (70, 64, 54)][faixa])
            x += w + 6 * e
    for i in range(int(W * 0.92 / (4 * e))):                   # forma de onda do áudio
        hh = abs(math.sin(i * 0.37) * math.cos(i * 0.11)) * 40 * e + 4 * e
        xx = W * 0.04 + i * 4 * e
        d.line((xx, y0 + 170 * e - hh, xx, y0 + 170 * e + hh), fill=(96, 150, 110), width=max(1, int(2 * e)))
    d.line((W * 0.55, y0 - 20 * e, W * 0.55, y0 + 220 * e), fill=DOURADO, width=max(2, int(3 * e)))
    lista = ["cortar pausas", "pôr efeitos", "legendas", "exportar"]
    d.rounded_rectangle((W * 0.04, H * 0.50, W * 0.36, H * 0.50 + 200 * e), 14, fill=(28, 26, 23))
    for i, it in enumerate(lista):
        d.ellipse((W * 0.06, H * 0.50 + (24 + i * 42) * e, W * 0.06 + 22 * e, H * 0.50 + (46 + i * 42) * e), fill=DOURADO)
        d.text((W * 0.06 + 34 * e, H * 0.50 + (20 + i * 42) * e), it, font=fnt, fill=OFF)
    mesa_np = np.asarray(mesa, np.float32)

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = ease_in_out(clamp((t - t0) / 0.8)) * ease_in_out(clamp((t0 + dur - t) / 0.6))
        s = 1 - 0.48 * u
        out = mesa_np.copy() if u > 0.01 else q.astype(np.float32)
        img = Image.fromarray(q).resize((max(1, int(W * s)), max(1, int(H * s))), Image.BILINEAR)
        moldura = _cartao(img, max(1, int(3 * e)), DOURADO, int(18 * e * u))
        _colar(out, moldura, W * (0.5 + 0.14 * u), H * (0.5 - 0.17 * u), 1.0)
        return out.astype(np.uint8)
    return f


# ------------------------------------------------------------------ 16 balão de comentário
def balao(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    e = W / 1080
    usuario = ef.get("usuario", "paciente")
    tt = _texto(_limpo(ef.get("texto", "Quero agendar minha avaliação!")), "Poppins-Medium.ttf", 30 * e, (24, 22, 20),
                int(W * 0.52))
    nome = _texto(usuario, "Poppins-Medium.ttf", 24 * e, (120, 114, 104))
    c = Image.new("RGBA", (max(tt.width, nome.width) + int(120 * e), tt.height + nome.height + int(40 * e)), (0, 0, 0, 0))
    d = ImageDraw.Draw(c)
    d.rounded_rectangle((0, 0, c.width - 1, c.height - 1), int(28 * e), fill=(255, 255, 255, 250))
    d.ellipse((16 * e, 18 * e, 76 * e, 78 * e), fill=DOURADO + (255,))
    c.alpha_composite(nome, (int(92 * e), int(14 * e)))
    c.alpha_composite(tt, (int(92 * e), int(16 * e) + nome.height))
    img = _sombra(c, int(12 * e), 6, 120)
    px, py = ef.get("ponto", [0.5, 0.30])

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = clamp((t - t0) / 0.35)
        out = q.astype(np.float32)
        _colar(out, img, px * W, py * H - (1 - ease_out(u)) * 40 * e, _env(t, t0, dur, 0.12, 0.3), _pop(u))
        return out.astype(np.uint8)
    return f


# ------------------------------------------------------------------ extras dos vídeos
def mural(ef, combo, W, H, fps):
    """Parede de vídeos (miniaturas do próprio vídeo) que se monta atrás da pessoa."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    col, lin = 6, 9
    tw, th = W // col, H // lin
    guardadas = []

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        if len(guardadas) < 8 and int((t - t0) * 12) >= len(guardadas):
            guardadas.append(np.asarray(Image.fromarray(q).resize((tw - 6, th - 6)), np.float32))
        a = _env(t, t0, dur, 0.4, 0.3)
        parede = np.zeros_like(q, dtype=np.float32) + np.array(FUNDO, np.float32)
        for i in range(lin):
            for j in range(col):
                k = (i * 7 + j * 3) % max(1, len(guardadas))
                if guardadas and ((i + j) % 5) / 5 <= clamp((t - t0) / 0.8):
                    parede[i * th + 3:i * th + 3 + th - 6, j * tw + 3:j * tw + 3 + tw - 6] = guardadas[k] * 0.55
        m = _mascara(q)
        qf = q.astype(np.float32)
        out = parede * (1 - m) + qf * m
        return (qf * (1 - a) + out * a).astype(np.uint8)
    return f


def saiba_mais(ef, combo, W, H, fps):
    """Final de anúncio: 'Toque em Saiba mais' com seta dourada que pula para o botão."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    e = W / 1080
    l1 = _texto(_limpo(ef.get("texto", "Toque em")), "Poppins-Medium.ttf", 70 * e, OFF)
    botao_txt = _texto(_limpo(ef.get("botao", "Saiba mais")), "Poppins-Medium.ttf", 84 * e, (20, 19, 17))
    botao = Image.new("RGBA", (botao_txt.width + int(50 * e), botao_txt.height + int(16 * e)), DOURADO + (255,))
    botao.alpha_composite(botao_txt, (int(25 * e), int(4 * e)))
    botao = _sombra(botao, int(8 * e), 6)

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.25, 0.2)
        out = q.astype(np.float32) * (1 - 0.55 * a)
        u = clamp((t - t0) / 0.4)
        _colar(out, l1, W / 2, H * 0.42, a)
        _colar(out, botao, W / 2, H * 0.50, a, _pop(u))
        im = Image.fromarray(out.astype(np.uint8)).convert("RGBA")
        d = ImageDraw.Draw(im)
        y = H * 0.62 + abs(math.sin((t - t0) * 6)) * 30 * e
        x = W / 2
        d.line((x, y, x, y + 110 * e), fill=DOURADO + (int(255 * a),), width=int(16 * e))
        d.polygon([(x - 42 * e, y + 96 * e), (x + 42 * e, y + 96 * e), (x, y + 150 * e)], fill=DOURADO + (int(255 * a),))
        return np.asarray(im.convert("RGB"))
    return f


def ticket(ef, combo, W, H, fps):
    """Tíquete de papel térmico (instrução, pedido, 'TUDO APROVADO. FINALIZA.') que desce do topo."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.8))
    e = W / 1080
    larg = int(W * 0.50)
    corpo = _texto(_limpo(ef.get("texto", "Tudo aprovado. / Finaliza.")).upper(), "CourierPrime-Regular.ttf", 46 * e,
                   (24, 22, 20), larg - int(40 * e))
    pe = _texto(f"TOTAL{' ' * 14}{ef.get('total', '1 FRASE')}", "CourierPrime-Regular.ttf", 20 * e, (60, 56, 50))
    cab = _texto(ef.get("titulo", "INSTRUÇÃO PARA O CLAUDE"), "CourierPrime-Regular.ttf", 20 * e, (60, 56, 50))
    alt = cab.height + corpo.height + pe.height + int(90 * e)
    papel = Image.new("RGBA", (larg, alt), (238, 234, 222, 255))
    d = ImageDraw.Draw(papel)
    papel.alpha_composite(cab, (int(20 * e), int(16 * e)))
    yc = cab.height + int(34 * e)
    for x in range(int(20 * e), larg - int(20 * e), int(14 * e)):
        d.line((x, yc - 8 * e, x + 7 * e, yc - 8 * e), fill=(90, 86, 78), width=1)
    papel.alpha_composite(corpo, (int(20 * e), yc))
    papel.alpha_composite(pe, (int(20 * e), yc + corpo.height + int(26 * e)))
    img = _sombra(papel, int(10 * e), 6)

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = ease_out(clamp((t - t0) / 0.7))
        out = q.astype(np.float32)
        _colar(out, img, W / 2, -img.height / 2 + (img.height + H * 0.55) * u, _env(t, t0, dur, 0.05, 0.3))
        return out.astype(np.uint8)
    return f


def seta_mao(ef, combo, W, H, fps):
    """Seta e texto escritos à mão ('clica aqui'), desenhados em traço, apontando para o botão ou a legenda."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    e = W / 1080
    tinta = cor(ef.get("cor", "dourado")) if ef.get("cor") != "vermelho" else (214, 52, 44)
    txt = _texto(_limpo(ef.get("texto", "clica aqui")).replace(" ", "\n"), "Caveat[wght].ttf", 84 * e, tinta)
    px, py = ef.get("ponto", [0.88, 0.80])

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = clamp((t - t0) / 0.8)
        a = _env(t, t0, dur, 0.05, 0.3)
        im = Image.fromarray(q).convert("RGBA")
        lx = int(txt.width * min(1, u * 1.6))
        if lx > 0:
            im.alpha_composite(txt.crop((0, 0, lx, txt.height)), (int(px * W - txt.width / 2), int(py * H - H * 0.30)))
        d = ImageDraw.Draw(im)
        x0, y0 = px * W, py * H - H * 0.30 + txt.height + 10 * e
        n = int(30 * clamp((u - 0.4) / 0.5))
        pts = [(x0 + math.sin(k * 0.5) * 6 * e, y0 + (py * H - y0) * k / 30) for k in range(n + 1)]
        if len(pts) > 1:
            d.line(pts, fill=tinta + (int(255 * a),), width=max(3, int(7 * e)), joint="curve")
        if n >= 30:
            d.line((x0 - 26 * e, py * H - 30 * e, x0, py * H, x0 + 26 * e, py * H - 30 * e), fill=tinta + (int(255 * a),),
                   width=max(3, int(7 * e)), joint="curve")
            d.ellipse((x0 - 34 * e, py * H + 6 * e, x0 + 34 * e, py * H + 74 * e), outline=tinta + (int(255 * a),),
                      width=max(2, int(4 * e)))
        return np.asarray(im.convert("RGB"))
    return f


def cartela_tempo(ef, combo, W, H, fps):
    """Cartela escura com timecode correndo e título em serifa ('Poucos minutos depois'), para pular no tempo."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 1.8))
    e = W / 1080
    tit = _texto(_limpo(ef.get("texto", "Poucos minutos depois")).upper().replace(" ", "\n"), "Cinzel[wght].ttf",
                 120 * e, OFF)
    fnt = _f("CourierPrime-Regular.ttf", 26 * e)

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.15, 0.25)
        out = q.astype(np.float32) * (1 - a) + np.array([30, 28, 24], np.float32) * a
        _colar(out, tit, W / 2, H * 0.47, a)
        im = Image.fromarray(out.astype(np.uint8))
        seg = 45 + (t - t0) * 7
        ImageDraw.Draw(im).text((W / 2 - 110 * e, H * 0.30), f"00:00:{int(seg):02d}:{int((seg % 1) * 30):02d}",
                                font=fnt, fill=DOURADO)
        return np.asarray(im)
    return f


# ------------------------------------------------------------------ registro
EFEITOS = {"manchetes": manchetes, "zoom_atravessa": zoom_atravessa, "tela_verde": tela_verde, "celular": celular,
           "visor": visor, "recorte_papel": recorte_papel, "interface": interface, "orbita": orbita,
           "quebra_moldura": quebra_moldura, "rabisco": rabisco, "adesivo": adesivo, "antes_depois": antes_depois,
           "recuo_revela": recuo_revela, "balao": balao, "mural": mural, "saiba_mais": saiba_mais, "ticket": ticket,
           "seta_mao": seta_mao, "cartela_tempo": cartela_tempo}

# apelidos com o nome do vídeo de referência
APELIDOS = {"vertigem": "dolly_zoom", "profundidade": "texto_atras", "zoom_que_atravessa": "zoom_atravessa",
            "parede_de_manchetes": "manchetes", "mockup_de_celular": "celular", "mundo_de_interface": "interface",
            "quebra_de_moldura": "quebra_moldura", "rabisco_tremido": "rabisco", "texto_adesivo": "adesivo",
            "recuo_que_revela": "recuo_revela", "balao_de_comentario": "balao", "zoom_visor": "visor"}

NOMES = {"manchetes": "Parede de manchetes", "zoom_atravessa": "Zoom que atravessa", "tela_verde": "Tela verde (pessoa sobre outra imagem)",
         "celular": "Mockup de celular", "visor": "Zoom com visor de câmera (REC)", "recorte_papel": "Recorte de papel",
         "interface": "Mundo de interface", "orbita": "Órbita de cartões", "quebra_moldura": "Quebra de moldura",
         "rabisco": "Rabisco tremido", "adesivo": "Texto adesivo", "antes_depois": "Antes e depois da edição",
         "recuo_revela": "Recuo que revela", "balao": "Balão de comentário", "mural": "Parede de vídeos",
         "saiba_mais": "Toque em Saiba mais", "ticket": "Tíquete de instrução", "seta_mao": "Seta à mão (clica aqui)",
         "cartela_tempo": "Cartela de tempo (minutos depois)"}

CAMPOS = {
    "manchetes": [("textos", "linhas", "Manchetes (uma por linha)")],
    "zoom_atravessa": [("ponto", "ponto", "Por onde atravessa")],
    "tela_verde": [("imagem", "texto", "Imagem de fundo (bruto/ ou assets/)"), ("tema", "texto", "Ou tema da Biblioteca")],
    "celular": [("imagem", "texto", "Imagem na tela (vazio = o próprio vídeo)"), ("lado", "escolha:esquerda|direita", "Lado")],
    "visor": [("ponto", "ponto", "Onde aproxima"), ("zoom", "numero", "Zoom final (1.29)")],
    "recorte_papel": [("texto", "texto", "Palavra em letras recortadas")],
    "interface": [("texto", "texto", "Pedido digitado")],
    "orbita": [("textos", "linhas", "Cartões (um por linha)")],
    "quebra_moldura": [("usuario", "texto", "@ do post")],
    "rabisco": [("cor", "escolha:dourado|branco", "Cor do traço")],
    "adesivo": [("texto", "texto", "Texto do adesivo"), ("ponto", "ponto", "Onde cola")],
    "antes_depois": [],
    "recuo_revela": [],
    "balao": [("usuario", "texto", "Quem comenta"), ("texto", "texto", "Comentário"), ("ponto", "ponto", "Onde aparece")],
    "mural": [],
    "saiba_mais": [("texto", "texto", "Frase de cima"), ("botao", "texto", "Botão")],
    "ticket": [("titulo", "texto", "Cabeçalho"), ("texto", "texto", "Instrução"), ("total", "texto", "Total")],
    "seta_mao": [("texto", "texto", "Texto à mão"), ("ponto", "ponto", "Para onde aponta"), ("cor", "escolha:dourado|vermelho", "Cor")],
    "cartela_tempo": [("texto", "texto", "Título")],
}

DURACAO = {"manchetes": 3.0, "zoom_atravessa": 0.6, "tela_verde": 3.0, "celular": 3.0, "visor": 2.5,
           "recorte_papel": 3.0, "interface": 3.5, "orbita": 3.0, "quebra_moldura": 3.0, "rabisco": 2.5, "adesivo": 2.2,
           "antes_depois": 2.5, "recuo_revela": 3.0, "balao": 2.5, "mural": 2.5, "saiba_mais": 2.5, "ticket": 2.8,
           "seta_mao": 2.5, "cartela_tempo": 1.8}

EXEMPLOS = {"manchetes": {"textos": ["A Divine *agora* faz isso", "Tecnologia e cuidado médico", "Na Av. Paulista"]},
            "zoom_atravessa": {}, "tela_verde": {}, "celular": {"lado": "esquerda"}, "visor": {"zoom": 1.29},
            "recorte_papel": {"texto": "Divine"}, "interface": {"texto": "edita meu reel no padrão Divine"},
            "orbita": {"textos": ["Avaliação", "Tecnologia", "Cuidado", "Protocolo"]}, "quebra_moldura": {},
            "rabisco": {}, "adesivo": {"texto": "agende sua avaliação"}, "antes_depois": {}, "recuo_revela": {},
            "balao": {"usuario": "paciente", "texto": "Quero agendar minha avaliação!"}, "mural": {},
            "saiba_mais": {}, "ticket": {"texto": "Tudo aprovado. / Finaliza."}, "seta_mao": {"texto": "clica aqui"},
            "cartela_tempo": {"texto": "Poucos minutos depois"}}

MOMENTO_AMOSTRA = {k: min(1.6, v * 0.6) for k, v in DURACAO.items()}

SONS = {"manchetes": "estalo_dedos", "zoom_atravessa": "whoosh_rapido", "tela_verde": "zap_suave", "celular": "whoosh_rapido",
        "visor": "subida_tensao", "recorte_papel": "estalo_dedos", "interface": "zap_suave", "orbita": "whoosh_rapido",
        "quebra_moldura": "boom_grave", "rabisco": "scratch_disco", "adesivo": "estalo_dedos", "antes_depois": "whoosh_rapido",
        "recuo_revela": "drop_sub", "balao": "flash_brilho", "mural": "subida_tensao", "saiba_mais": "coracao",
        "ticket": "zap_suave", "seta_mao": "scratch_disco", "cartela_tempo": "boom_grave"}


# ------------------------------------------------------------------ mais efeitos (efeitos_mais.py) no mesmo registro
from . import efeitos_mais as _mais  # noqa: E402

EFEITOS.update(_mais.EFEITOS)
APELIDOS.update(_mais.APELIDOS)
NOMES.update(_mais.NOMES)
CAMPOS.update(_mais.CAMPOS)
DURACAO.update(_mais.DURACAO)
EXEMPLOS.update(_mais.EXEMPLOS)
MOMENTO_AMOSTRA.update(_mais.MOMENTO_AMOSTRA)
SONS.update(_mais.SONS)
