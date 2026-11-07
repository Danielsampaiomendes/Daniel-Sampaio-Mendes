"""Mais efeitos (referência "24 efeitos de vídeo", 06/11/2026, e os que estão em alta nos apps de edição),
no padrão Divine. Todos entram na linha do tempo com um clique (mesmo formato dos demais efeitos de quadro).

Da referência: ascii, capa_revista, grade_cards, desinstalando, deletar_app, retro, barra_prompt, notas_dinheiro,
conta_gotas, palavras_caindo, pausado, grafico_linha, projetor, pixel, pasteis, negativo, linha_tempo_edicao,
capas_reels, mural_titulos, conquista, estudio_edicao, pilula_link, card_titulo.
Em alta nos apps: holofote, lupa, rastro, triptico, vhs, dupla_exposicao, brilhos, desfoque_fundo.
Sem logos de outras marcas (apps aparecem só com letras e cores da Divine).
"""
from __future__ import annotations

import datetime as _dt
import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .anim import clamp, ease_in_out, ease_out
from .efeitos_truques import (DOURADO, FUNDO, OFF, _cartao, _colar, _dentro, _env, _f, _limpo, _mascara, _miniatura,
                              _pop, _sombra, _texto)

ROSA, LILAS, MENTA, CREME = (236, 190, 200), (200, 186, 232), (186, 226, 210), (247, 236, 214)


def _mistura(q, r, a):
    return (q.astype(np.float32) * (1 - a) + r.astype(np.float32) * a).astype(np.uint8)


def _painel(larg, alt, e, borda=DOURADO, fundo=(24, 22, 20, 236), raio=18):
    c = Image.new("RGBA", (int(larg), int(alt)), (0, 0, 0, 0))
    ImageDraw.Draw(c).rounded_rectangle((0, 0, c.width - 1, c.height - 1), int(raio * e), fill=fundo,
                                        outline=borda + (255,) if borda else None, width=max(1, int(2 * e)))
    return c


# ------------------------------------------------------------------ filtros de imagem
def ascii_(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.0))
    cols = int(ef.get("colunas", 72))
    chars = np.array(list(" .:-=+*#%@"))
    cel = W / cols
    fnt = _f("CourierPrime-Regular.ttf", cel * 1.25)
    tinta = DOURADO if ef.get("cor") != "verde" else (120, 220, 140)

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        linhas = int(H / (cel * 1.6))
        peq = np.asarray(Image.fromarray(q).convert("L").resize((cols, linhas)), np.float32) / 255
        idx = np.clip((peq * (len(chars) - 1)).round().astype(int), 0, len(chars) - 1)
        tela = Image.new("RGB", (W, H), FUNDO)
        d = ImageDraw.Draw(tela)
        for y in range(linhas):
            d.text((0, y * cel * 1.6), "".join(chars[idx[y]]), font=fnt, fill=tinta)
        return _mistura(q, np.asarray(tela), _env(t, t0, dur, 0.15, 0.25))
    return f


def retro(ef, combo, W, H, fps):
    """Duotone com retícula (meio-tom): preto e dourado, ou rosa e vinho."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    escuro, claro = ((40, 18, 48), ROSA) if ef.get("cor") == "rosa" else ((18, 17, 15), DOURADO)
    passo = max(4, int(W / 150))
    yy, xx = np.mgrid[0:H, 0:W]
    grade = ((np.sin(xx * math.pi / passo) * np.sin(yy * math.pi / passo)) + 1) / 2

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        lum = q.astype(np.float32).mean(axis=2) / 255
        ponto = (lum > grade * 0.9 + 0.05).astype(np.float32)[..., None]
        r = np.array(escuro, np.float32) * (1 - ponto) + np.array(claro, np.float32) * ponto
        return _mistura(q, r, _env(t, t0, dur, 0.2, 0.3))
    return f


def notas_dinheiro(ef, combo, W, H, fps):
    """Gravura de cédula: linhas finas moduladas pela luz, tom verde acinzentado, moldura e valor nos cantos."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    e = W / 1080
    valor = str(ef.get("valor", "25"))
    yy = np.mgrid[0:H, 0:W][0]
    linhas = (np.sin(yy * math.pi / max(3, int(4 * e))) + 1) / 2
    moldura = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(moldura)
    tinta = (60, 74, 58, 255)
    for k in range(3):
        m = int((30 + k * 10) * e)
        d.rounded_rectangle((m, m, W - m, H - m), int(30 * e), outline=tinta, width=max(1, int((3 - k) * e)))
    fnt = _f("Cinzel[wght].ttf", 110 * e)
    for x, y in ((60, 60), (W - 220 * e, 60), (60, H - 200 * e), (W - 220 * e, H - 200 * e)):
        d.text((x * (e if x == 60 else 1), y * (e if y == 60 else 1)), valor, font=fnt, fill=tinta)

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        lum = q.astype(np.float32).mean(axis=2) / 255
        traco = (linhas > lum * 0.95).astype(np.float32)[..., None]
        papel = np.array((226, 228, 210), np.float32)
        r = papel * (1 - traco * 0.85) + np.array((50, 64, 52), np.float32) * traco * 0.85
        im = Image.fromarray(r.astype(np.uint8)).convert("RGBA")
        im.alpha_composite(moldura)
        return _mistura(q, np.asarray(im.convert("RGB")), _env(t, t0, dur, 0.2, 0.3))
    return f


def pixel(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.0))
    bloco = int(ef.get("bloco", 28))
    e = W / 1080

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.4, 0.4)
        b = max(1, int(bloco * a * e))
        if b <= 1:
            return q
        im = Image.fromarray(q).resize((max(1, W // b), max(1, H // b)), Image.BILINEAR)
        im = im.quantize(colors=24, method=Image.Quantize.MEDIANCUT).convert("RGB")
        pal = im.resize((12, 1), Image.NEAREST)
        im = im.resize((W, H), Image.NEAREST).convert("RGBA")
        tira = pal.resize((int(W * 0.5), int(26 * e)), Image.NEAREST).convert("RGBA")
        moldura = _cartao(tira, max(2, int(6 * e)), (250, 248, 244))
        im.alpha_composite(moldura, ((W - moldura.width) // 2, int(H * 0.08)))
        return np.asarray(im.convert("RGB"))
    return f


def projetor(ef, combo, W, H, fps):
    """Projetor de cinema: a imagem vira tela, sépia com tremulação, feixe de luz e poeira."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    e = W / 1080
    rnd = np.random.default_rng(4)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    vinheta = np.clip(1.25 - np.hypot((xx - W / 2) / W, (yy - H * 0.42) / H) * 1.9, 0, 1)[..., None]
    feixe = np.clip(1 - np.abs(xx - W / 2) / (W * (0.08 + 0.45 * np.clip((H * 0.9 - yy) / H, 0, 1))), 0, 1)
    feixe = (feixe * np.clip((yy - H * 0.55) / (H * 0.35), 0, 1))[..., None] * 0.25

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.35, 0.35)
        s = 1 - 0.18 * a
        tela = Image.fromarray(q).resize((int(W * s), int(H * s * 0.8)))
        lum = np.asarray(tela.convert("L"), np.float32)[..., None] / 255
        sep = lum * np.array((255, 226, 180), np.float32) * (0.92 + 0.08 * math.sin(t * 47))
        fundo = np.zeros((H, W, 3), np.float32) + 8
        y0, x0 = int(H * 0.08), (W - tela.width) // 2
        fundo[y0:y0 + tela.height, x0:x0 + tela.width] = sep
        r = fundo * vinheta + feixe * 255
        for _ in range(8):                                    # poeira
            x, y = int(rnd.integers(0, W)), int(rnd.integers(y0, y0 + tela.height))
            r[max(0, y - 1):y + 2, max(0, x - 1):x + 2] = 230
        im = Image.fromarray(np.clip(r, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(im)
        cx, cy = W / 2, H * 0.86
        for dx in (-50, 50):
            d.ellipse((cx + dx * e - 42 * e, cy - 120 * e, cx + dx * e + 42 * e, cy - 36 * e), outline=(150, 140, 120), width=int(6 * e))
        d.rounded_rectangle((cx - 90 * e, cy - 30 * e, cx + 90 * e, cy + 40 * e), int(10 * e), fill=(40, 38, 34))
        return _mistura(q, np.asarray(im), a)
    return f


def pasteis(ef, combo, W, H, fps):
    """Cores pastéis: fundo vira degradê pastel, letras grandes 3D pastéis e cartão de seguir."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    e = W / 1080
    yy = np.linspace(0, 1, H)[:, None, None]
    deg = np.array(ROSA, np.float32) * (1 - yy) + np.array(LILAS, np.float32) * yy * 0.6 + np.array(MENTA, np.float32) * yy * 0.4
    deg = np.broadcast_to(deg, (H, W, 3))
    texto = _limpo(ef.get("texto", "Divine")).upper()
    fnt = _f("Unbounded[wght].ttf", min(190, 1400 / max(4, len(texto))) * e)
    letras = Image.new("RGBA", (W, int(260 * e)), (0, 0, 0, 0))
    d = ImageDraw.Draw(letras)
    x = (W - fnt.getlength(texto)) / 2
    cores = [ROSA, LILAS, MENTA, CREME, (250, 214, 165)]
    for i, ch in enumerate(texto):
        for k in range(8, 0, -1):
            d.text((x + k * e, 30 * e + k * e), ch, font=fnt, fill=(160, 140, 170, 255))
        d.text((x, 30 * e), ch, font=fnt, fill=cores[i % len(cores)] + (255,))
        x += fnt.getlength(ch)
    seguir = _painel(W * 0.62, 90 * e, e, None, (255, 255, 255, 240), 40)
    ImageDraw.Draw(seguir).ellipse((14 * e, 14 * e, 76 * e, 76 * e), fill=DOURADO)
    seguir.alpha_composite(_texto(ef.get("usuario", "@dvmedicalspa"), "Poppins-Medium.ttf", 30 * e, (30, 28, 26)), (int(92 * e), int(24 * e)))
    btn = _painel(150 * e, 54 * e, e, None, (80, 90, 230, 255), 27)
    btn.alpha_composite(_texto("Seguir", "Poppins-Medium.ttf", 26 * e, (255, 255, 255)), (int(32 * e), int(8 * e)))
    seguir.alpha_composite(btn, (seguir.width - btn.width - int(18 * e), int(18 * e)))

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.3, 0.3)
        m = _mascara(q)
        qf = q.astype(np.float32)
        r = qf * m + (deg * 0.75 + qf * 0.25) * (1 - m)
        out = qf * (1 - a) + r * a
        u = clamp((t - t0 - 0.2) / 0.5)
        _colar(out, letras, W / 2, H * 0.30, a, _pop(u))
        _colar(out, _sombra(seguir, int(8 * e), 4), W / 2, H * 0.12, a * clamp((t - t0) * 3))
        return np.clip(out, 0, 255).astype(np.uint8)
    return f


def estudio_edicao(ef, combo, W, H, fps):
    """Estúdio de edição: painel com controles deslizantes que mexem na imagem ao vivo."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    e = W / 1080
    nomes = ["Saturação", "Contraste", "Brilho", "Calor"]
    fnt = _f("Poppins-Light.ttf", 24 * e)

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = (t - t0) / dur
        vals = [0.5 + 0.35 * math.sin(u * math.pi * (1.2 + k * 0.4) + k) for k in range(4)]
        qf = q.astype(np.float32)
        cinza = qf.mean(axis=2, keepdims=True)
        qf = cinza + (qf - cinza) * (0.3 + 1.4 * vals[0])
        qf = (qf - 128) * (0.7 + 0.6 * vals[1]) + 128 + (vals[2] - 0.5) * 60
        qf[..., 0] += (vals[3] - 0.5) * 30
        qf[..., 2] -= (vals[3] - 0.5) * 30
        a = _env(t, t0, dur, 0.25, 0.3)
        out = q.astype(np.float32) * (1 - a) + np.clip(qf, 0, 255) * a
        p = _painel(W * 0.86, 300 * e, e)
        d = ImageDraw.Draw(p)
        d.text((24 * e, 16 * e), "Estúdio de edição", font=_f("Poppins-Medium.ttf", 30 * e), fill=OFF + (255,))
        for k, (n, v) in enumerate(zip(nomes, vals)):
            y = 80 * e + k * 52 * e
            d.text((24 * e, y), n, font=fnt, fill=(200, 196, 186, 255))
            x0, x1 = 240 * e, p.width - 40 * e
            d.line((x0, y + 16 * e, x1, y + 16 * e), fill=(90, 84, 74, 255), width=max(2, int(4 * e)))
            d.line((x0, y + 16 * e, x0 + (x1 - x0) * v, y + 16 * e), fill=DOURADO + (255,), width=max(2, int(4 * e)))
            cx = x0 + (x1 - x0) * v
            d.ellipse((cx - 12 * e, y + 4 * e, cx + 12 * e, y + 28 * e), fill=OFF + (255,))
        _colar(out, _sombra(p, int(10 * e), 5), W / 2, H * 0.17, a)
        return np.clip(out, 0, 255).astype(np.uint8)
    return f


# ------------------------------------------------------------------ interface e apps
def desinstalando(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    e = W / 1080
    txt = _limpo(ef.get("texto", "Desinstalando: hábitos que atrapalham"))

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        p = clamp((t - t0 - 0.3) / (dur - 0.7))
        c = _painel(W * 0.74, 110 * e, e, (90, 84, 74), (250, 248, 244, 245), 20)
        d = ImageDraw.Draw(c)
        d.text((26 * e, 18 * e), txt, font=_f("Poppins-Medium.ttf", 28 * e), fill=(30, 28, 26, 255))
        d.rounded_rectangle((26 * e, 70 * e, c.width - 26 * e, 84 * e), 7, fill=(225, 220, 210, 255))
        d.rounded_rectangle((26 * e, 70 * e, 26 * e + (c.width - 52 * e) * p, 84 * e), 7, fill=(64, 110, 220, 255))
        out = q.astype(np.float32)
        _colar(out, _sombra(c, int(10 * e), 5), W / 2, H * 0.16 - (1 - ease_out(clamp((t - t0) / 0.3))) * 120 * e,
               _env(t, t0, dur, 0.05, 0.25))
        return out.astype(np.uint8)
    return f


def deletar_app(ef, combo, W, H, fps):
    """Ícones tremendo como na hora de apagar app; o seu ícone (a pessoa) no centro, com o X."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    e = W / 1080
    apps = ef.get("apps") or ["Ed", "Cl", "Le", "Mú", "No", "Ex", "Ti", "Fo"]
    cores = [(92, 80, 200), (230, 140, 40), (70, 180, 90), (210, 60, 90), (240, 200, 40), (60, 140, 230),
             (160, 90, 220), (60, 190, 230)]
    lado = int(120 * e)
    icones = []
    for k, a in enumerate(apps[:8]):
        ic = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
        ImageDraw.Draw(ic).rounded_rectangle((0, 0, lado - 1, lado - 1), int(28 * e), fill=cores[k % len(cores)] + (255,))
        tt = _texto(a, "Poppins-Medium.ttf", 44 * e, (255, 255, 255))
        ic.alpha_composite(tt, ((lado - tt.width) // 2, (lado - tt.height) // 2))
        icones.append(_sombra(ic, int(6 * e), 3))
    lugares = [(0.2, 0.17), (0.4, 0.17), (0.6, 0.17), (0.8, 0.17), (0.2, 0.84), (0.4, 0.84), (0.6, 0.84), (0.8, 0.84)]

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.25, 0.3)
        fundo = np.asarray(Image.fromarray(q).filter(ImageFilter.GaussianBlur(20 * e)), np.float32) * 0.75
        out = q.astype(np.float32) * (1 - a) + fundo * a
        for k, ic in enumerate(icones):
            px, py = lugares[k]
            _colar(out, ic, px * W, py * H, a, 1.0, math.sin(t * 30 + k) * 3)
        rosto = ImageOps.fit(Image.fromarray(q), (int(260 * e), int(260 * e)), centering=(0.5, 0.35)).convert("RGBA")
        m = Image.new("L", rosto.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, rosto.width - 1, rosto.height - 1), int(56 * e), fill=255)
        rosto.putalpha(m)
        rx = _sombra(rosto, int(10 * e), 5)
        d = ImageDraw.Draw(rx)
        d.ellipse((4, 4, 60 * e, 60 * e), fill=(235, 235, 235, 255))
        d.line((18 * e, 18 * e, 46 * e, 46 * e), fill=(60, 60, 60, 255), width=max(2, int(5 * e)))
        d.line((46 * e, 18 * e, 18 * e, 46 * e), fill=(60, 60, 60, 255), width=max(2, int(5 * e)))
        _colar(out, rx, W / 2, H * 0.5, a, _pop(clamp((t - t0) / 0.4)), math.sin(t * 28) * 2.5)
        return np.clip(out, 0, 255).astype(np.uint8)
    return f


def barra_prompt(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.8))
    e = W / 1080
    txt = _limpo(ef.get("texto", "/edita meu reel no padrão Divine"))

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = t - t0
        n = int(len(txt) * clamp((u - 0.3) / 1.4))
        c = _painel(W * 0.86, 110 * e, e, (210, 205, 195), (250, 248, 244, 248), 26)
        d = ImageDraw.Draw(c)
        d.text((28 * e, 34 * e), (txt[:n] + ("|" if int(u * 3) % 2 else "")) or "|", font=_f("CourierPrime-Regular.ttf", 32 * e),
               fill=(160, 60, 40, 255) if txt.startswith("/") else (30, 28, 26, 255))
        cx = c.width - 60 * e
        d.ellipse((cx - 28 * e, 27 * e, cx + 28 * e, 83 * e), fill=(214, 110, 70, 255))
        d.polygon([(cx, 40 * e), (cx - 12 * e, 58 * e), (cx + 12 * e, 58 * e)], fill=(255, 255, 255, 255))
        out = q.astype(np.float32)
        _colar(out, _sombra(c, int(10 * e), 5), W / 2, H * 0.12, _env(t, t0, dur, 0.2, 0.25))
        return out.astype(np.uint8)
    return f


def pausado(ef, combo, W, H, fps):
    """Pausa: congela a imagem, escurece, botão de pausa, barra do vídeo e a palavra digitada no topo."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.0))
    e = W / 1080
    txt = _limpo(ef.get("texto", "PAUSA")).upper()
    guardado = {}

    def f(q, t):
        if not _dentro(t, t0, dur):
            guardado.clear()
            return q
        base = guardado.setdefault("q", q.copy())
        a = _env(t, t0, dur, 0.12, 0.2)
        out = base.astype(np.float32) * (1 - 0.35 * a)
        im = Image.fromarray(out.astype(np.uint8)).convert("RGBA")
        d = ImageDraw.Draw(im)
        r = 70 * e
        d.ellipse((W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r), fill=(0, 0, 0, int(140 * a)))
        for dx in (-22, 14):
            d.rounded_rectangle((W / 2 + dx * e, H / 2 - 30 * e, W / 2 + (dx + 10) * e, H / 2 + 30 * e), 4,
                                fill=(255, 255, 255, int(255 * a)))
        y = H * 0.94
        d.line((W * 0.06, y, W * 0.94, y), fill=(255, 255, 255, int(160 * a)), width=max(2, int(5 * e)))
        xp = W * (0.06 + 0.88 * 0.42)
        d.line((W * 0.06, y, xp, y), fill=(214, 52, 44, int(255 * a)), width=max(2, int(5 * e)))
        d.ellipse((xp - 10 * e, y - 10 * e, xp + 10 * e, y + 10 * e), fill=(214, 52, 44, int(255 * a)))
        n = int(len(txt) * clamp((t - t0) / 0.6))
        tt = _texto(txt[:n] or " ", "BebasNeue-Regular.ttf", 110 * e, (240, 220, 80))
        im.alpha_composite(tt, (int((W - tt.width) / 2), int(H * 0.12)))
        return np.asarray(im.convert("RGB"))
    return f


def grafico_linha(ef, combo, W, H, fps):
    """Gráfico em ascensão: linha subindo e o número contando."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    e = W / 1080
    de, ate = float(ef.get("de", 0)), float(ef.get("ate", 24))
    rot = _limpo(ef.get("rotulo", "efeitos neste vídeo"))
    rnd = random.Random(3)
    pontos = [0.0]
    for _ in range(11):
        pontos.append(min(1.0, pontos[-1] + rnd.uniform(0.02, 0.12)))
    pontos = [p / pontos[-1] for p in pontos]

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = ease_in_out(clamp((t - t0 - 0.2) / (dur * 0.7)))
        c = _painel(W * 0.86, 330 * e, e, (90, 84, 74), (28, 26, 23, 220), 22)
        d = ImageDraw.Draw(c)
        d.text((24 * e, 18 * e), rot, font=_f("Poppins-Light.ttf", 26 * e), fill=(200, 196, 186, 255))
        x0, x1, yb, yt = 30 * e, c.width * 0.7, c.height - 40 * e, 80 * e
        n = max(2, int(len(pontos) * u) + 1)
        pts = [(x0 + (x1 - x0) * k / (len(pontos) - 1), yb - (yb - yt) * (p ** 1.6)) for k, p in enumerate(pontos[:n])]
        d.line(pts, fill=(140, 120, 255, 255), width=max(2, int(6 * e)), joint="curve")
        d.ellipse((pts[-1][0] - 9 * e, pts[-1][1] - 9 * e, pts[-1][0] + 9 * e, pts[-1][1] + 9 * e), fill=OFF + (255,))
        num = _texto(str(int(round(de + (ate - de) * u))), "Poppins-Medium.ttf", 110 * e, OFF)
        c.alpha_composite(num, (int(c.width - num.width - 30 * e), int(60 * e)))
        out = q.astype(np.float32)
        _colar(out, _sombra(c, int(10 * e), 5), W / 2, H * 0.2, _env(t, t0, dur, 0.25, 0.3))
        return out.astype(np.uint8)
    return f


def linha_tempo_edicao(ef, combo, W, H, fps):
    """Painel da linha do tempo de edição no topo: miniatura, faixas coloridas e a agulha andando."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    e = W / 1080
    rnd = random.Random(8)
    faixas = []
    for k in range(3):
        x, lst = 0.0, []
        while x < 1:
            w = rnd.uniform(0.08, 0.22)
            lst.append((x, min(1, x + w - 0.01)))
            x += w
        faixas.append(lst)
    cores = [(150, 120, 230), DOURADO, (110, 190, 150)]

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = clamp((t - t0) / dur)
        c = _painel(W * 0.92, 340 * e, e, (90, 84, 74), (26, 22, 34, 236), 20)
        d = ImageDraw.Draw(c)
        mini = _miniatura(q, int(150 * e))
        c.alpha_composite(_cartao(mini, 2, DOURADO).crop((0, 0, int(154 * e), int(150 * e))), (int(20 * e), int(20 * e)))
        fnt = _f("CourierPrime-Regular.ttf", 24 * e)
        d.text((190 * e, 30 * e), "DIVINE STUDIO · EDIÇÃO", font=fnt, fill=OFF + (255,))
        d.text((190 * e, 70 * e), f"00:00:{int(u * 30):02d}:{int((u * 900) % 30):02d}", font=fnt, fill=DOURADO + (255,))
        x0, x1 = 20 * e, c.width - 20 * e
        for k, lst in enumerate(faixas):
            y = 190 * e + k * 44 * e
            for a, b in lst:
                d.rounded_rectangle((x0 + (x1 - x0) * a, y, x0 + (x1 - x0) * b, y + 34 * e), 6, fill=cores[k] + (255,))
        xa = x0 + (x1 - x0) * u
        d.line((xa, 180 * e, xa, c.height - 10 * e), fill=(255, 255, 255, 255), width=max(2, int(3 * e)))
        out = q.astype(np.float32)
        _colar(out, _sombra(c, int(10 * e), 5), W / 2, H * 0.15, _env(t, t0, dur, 0.25, 0.3))
        return out.astype(np.uint8)
    return f


def conquista(ef, combo, W, H, fps):
    """Conquista desbloqueada: aviso no topo, troféu dourado com raios e brilhos."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.8))
    e = W / 1080
    txt = _limpo(ef.get("texto", "Primeira avaliação agendada"))

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.2, 0.3)
        u = clamp((t - t0) / 0.5)
        im = Image.fromarray(q).convert("RGBA")
        luz = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(luz)
        cx, cy = W / 2, H * 0.33
        for k in range(16):                                   # raios girando
            ang = k * math.pi / 8 + t * 0.6
            d.polygon([(cx, cy), (cx + math.cos(ang - 0.08) * W, cy + math.sin(ang - 0.08) * W),
                       (cx + math.cos(ang + 0.08) * W, cy + math.sin(ang + 0.08) * W)], fill=DOURADO + (int(50 * a),))
        luz = luz.filter(ImageFilter.GaussianBlur(6 * e))
        im.alpha_composite(luz)
        d = ImageDraw.Draw(im)
        s = _pop(u) * e
        d.pieslice((cx - 90 * s, cy - 110 * s, cx + 90 * s, cy + 70 * s), 0, 180, fill=DOURADO + (int(255 * a),))
        d.rectangle((cx - 16 * s, cy + 60 * s, cx + 16 * s, cy + 110 * s), fill=DOURADO + (int(255 * a),))
        d.rounded_rectangle((cx - 70 * s, cy + 105 * s, cx + 70 * s, cy + 135 * s), 6, fill=(150, 120, 60, int(255 * a)))
        for k in range(10):                                   # brilhos
            ang, rr = k * 0.63 + t * 2, (160 + 40 * math.sin(t * 5 + k)) * e
            x, y = cx + math.cos(ang) * rr, cy + math.sin(ang) * rr
            d.text((x, y), "✦", font=_f("Poppins-Medium.ttf", 28 * e), fill=(255, 240, 200, int(230 * a)))
        aviso = _painel(W * 0.84, 110 * e, e, DOURADO, (20, 19, 17, 240), 24)
        ad = ImageDraw.Draw(aviso)
        ad.ellipse((22 * e, 22 * e, 88 * e, 88 * e), outline=DOURADO + (255,), width=max(2, int(4 * e)))
        ad.text((110 * e, 16 * e), "CONQUISTA DESBLOQUEADA", font=_f("Poppins-Light.ttf", 22 * e), fill=DOURADO + (255,))
        ad.text((110 * e, 50 * e), txt, font=_f("Poppins-Medium.ttf", 32 * e), fill=OFF + (255,))
        out = np.asarray(im.convert("RGB")).astype(np.float32)
        _colar(out, _sombra(aviso, int(10 * e), 5), W / 2, H * 0.1 - (1 - ease_out(u)) * 160 * e, a)
        return out.astype(np.uint8)
    return f


def pilula_link(ef, combo, W, H, fps):
    """'Link aqui embaixo': pílula dourada que pula com seta para o botão ou a legenda."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    e = W / 1080
    tt = _texto(_limpo(ef.get("texto", "link aqui embaixo")), "Poppins-Medium.ttf", 36 * e, (20, 19, 17))
    p = _painel(tt.width + 60 * e, tt.height + 24 * e, e, None, DOURADO + (255,), 40)
    p.alpha_composite(tt, (int(30 * e), int(10 * e)))
    p = _sombra(p, int(8 * e), 5)
    px, py = ef.get("ponto", [0.5, 0.80])

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.15, 0.25)
        pulo = abs(math.sin((t - t0) * 5)) * 18 * e
        out = q.astype(np.float32)
        _colar(out, p, px * W, py * H - pulo, a, _pop(clamp((t - t0) / 0.35)))
        im = Image.fromarray(out.astype(np.uint8))
        d = ImageDraw.Draw(im)
        y = py * H + p.height / 2 + 10 * e - pulo
        d.polygon([(px * W - 20 * e, y), (px * W + 20 * e, y), (px * W, y + 30 * e)], fill=DOURADO)
        return np.asarray(im)
    return f


def card_titulo(ef, combo, W, H, fps):
    """Cartão de título com borda em degradê dourado (lançamento, série, nome do método)."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.8))
    e = W / 1080
    cab = _limpo(ef.get("cabecalho", "DIVINE · MÉTODO"))
    tit = _texto(_limpo(ef.get("texto", "Protocolo Divine / passo a passo")), "DMSerifDisplay-Regular.ttf", 64 * e, OFF, int(W * 0.72))
    c = _painel(W * 0.84, tit.height + 120 * e, e, None, (22, 20, 18, 240), 26)
    borda = Image.new("RGBA", c.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(borda)
    for k in range(c.width):
        cor_k = tuple(int(a + (b - a) * k / c.width) for a, b in zip(DOURADO, (240, 220, 170)))
        bd.line((k, 0, k, c.height), fill=cor_k + (255,))
    m = Image.new("L", c.size, 0)
    md = ImageDraw.Draw(m)
    md.rounded_rectangle((0, 0, c.width - 1, c.height - 1), int(26 * e), fill=255)
    md.rounded_rectangle((4 * e, 4 * e, c.width - 1 - 4 * e, c.height - 1 - 4 * e), int(23 * e), fill=0)
    borda.putalpha(m)
    c.alpha_composite(borda)
    ImageDraw.Draw(c).text((32 * e, 26 * e), cab, font=_f("Poppins-Light.ttf", 22 * e), fill=DOURADO + (255,))
    c.alpha_composite(tit, (int(32 * e), int(68 * e)))
    c = _sombra(c, int(12 * e), 6)

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = clamp((t - t0) / 0.45)
        out = q.astype(np.float32)
        _colar(out, c, W / 2, H * 0.16 + (1 - ease_out(u)) * 40 * e, _env(t, t0, dur, 0.3, 0.3))
        return out.astype(np.uint8)
    return f


# ------------------------------------------------------------------ colagem e papel
def capa_revista(ef, combo, W, H, fps):
    """Capa de revista: moldura off-white, nome da revista em serifa, edição, chamadas e manchete."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    e = W / 1080
    nome = _limpo(ef.get("revista", "DIVINE"))
    manchete = _limpo(ef.get("texto", "Edição especial"))
    chamadas = ef.get("chamadas") or ["Tecnologia", "Cuidado médico", "Av. Paulista"]
    papel = Image.new("RGBA", (W, H), (244, 238, 226, 255))
    d = ImageDraw.Draw(papel)
    mt = _f("DMSerifDisplay-Regular.ttf", 190 * e)
    d.text(((W - mt.getlength(nome)) / 2, 40 * e), nome, font=mt, fill=(26, 24, 22, 255))
    d.text((60 * e, 270 * e), f"Nº {ef.get('numero', '01')} · {_dt.date.today():%m/%Y}", font=_f("CourierPrime-Regular.ttf", 24 * e),
           fill=(90, 86, 78, 255))
    for k, c in enumerate(chamadas[:4]):
        d.text((60 * e, H * 0.42 + k * 70 * e), _limpo(c), font=_f("PlayfairDisplay[wght].ttf", 34 * e), fill=(30, 28, 26, 255))
    mf = _texto(manchete, "PlayfairDisplay-Italic[wght].ttf", 70 * e, (150, 40, 40), int(W * 0.84))
    jx, jy, jw, jh = int(W * 0.30), int(330 * e), int(W * 0.62), int(H * 0.55)

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.3, 0.3)
        im = papel.copy()
        foto = ImageOps.fit(Image.fromarray(q), (jw, jh), centering=(0.5, 0.35))
        im.paste(foto, (jx, jy))
        im.alpha_composite(mf, ((W - mf.width) // 2, int(jy + jh + 40 * e)))
        return _mistura(q, np.asarray(im.convert("RGB")), a)
    return f


def grade_cards(ef, combo, W, H, fps):
    """O vídeo vira um cartão no topo e entram cartões de número e de capa embaixo."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    e = W / 1080
    num, rot = str(ef.get("numero", "24")), _limpo(ef.get("rotulo", "efeitos · 1 vídeo"))
    card_num = _painel(260 * e, 300 * e, e, None, (120, 30, 40, 255), 22)
    tn = _texto(num, "Poppins-Medium.ttf", 130 * e, OFF)
    card_num.alpha_composite(tn, ((card_num.width - tn.width) // 2, int(40 * e)))
    tr = _texto(rot, "Poppins-Light.ttf", 24 * e, OFF, int(220 * e))
    card_num.alpha_composite(tr, ((card_num.width - tr.width) // 2, int(210 * e)))
    card_num = _sombra(card_num, int(10 * e), 5)

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = ease_in_out(clamp((t - t0) / 0.5))
        a = _env(t, t0, dur, 0.2, 0.3)
        fundo = np.ones_like(q, dtype=np.float32) * np.array((240, 236, 228), np.float32)
        s = 1 - 0.42 * u
        cartao = _cartao(Image.fromarray(q).resize((int(W * s), int(H * s * 0.62))), int(4 * e), (255, 255, 255), int(26 * e * u))
        out = fundo.copy()
        _colar(out, _sombra(cartao, int(12 * e), 6), W * (0.5 + 0.12 * u), H * (0.31), 1.0)
        _colar(out, card_num, W * 0.28, H * 0.78, clamp((t - t0 - 0.4) * 3), _pop(clamp((t - t0 - 0.4) / 0.4)))
        capa = _cartao(_miniatura(q, int(220 * e)), int(5 * e), (20, 19, 17))
        _colar(out, _sombra(capa, int(10 * e), 5), W * 0.66, H * 0.78, clamp((t - t0 - 0.6) * 3), _pop(clamp((t - t0 - 0.6) / 0.4)), 4)
        return (q.astype(np.float32) * (1 - a) + out * a).astype(np.uint8)
    return f


def palavras_caindo(ef, combo, W, H, fps):
    """Palavras em adesivos caindo com gravidade e quicando até empilhar embaixo."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    e = W / 1080
    palavras = ef.get("palavras") or ["cuidado", "avaliação", "tecnologia", "protocolo", "pele", "saúde", "Divine", "tempo"]
    rnd = random.Random(11)
    cores = [((250, 248, 244), (20, 19, 17)), (DOURADO, (20, 19, 17)), ((20, 19, 17), OFF), ((236, 190, 200), (40, 30, 34))]
    pecas = []
    for k, p in enumerate(palavras[:10]):
        bg, fg = cores[k % len(cores)]
        tt = _texto(_limpo(p), "Poppins-Medium.ttf", 40 * e, fg)
        c = _painel(tt.width + 40 * e, tt.height + 20 * e, e, None, bg + (255,), 30)
        c.alpha_composite(tt, (int(20 * e), int(6 * e)))
        x = rnd.uniform(0.15, 0.85) * W
        chao = H * (0.9 - 0.06 * (k % 4))
        pecas.append((_sombra(c, int(6 * e), 4), x, chao, k * 0.18, rnd.uniform(-20, 20)))

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.05, 0.3)
        out = q.astype(np.float32)
        for img, x, chao, atraso, ang in pecas:
            u = t - t0 - atraso
            if u <= 0:
                continue
            y = -100 * e + 0.5 * 5200 * e * u * u
            if y > chao:                                     # quica uma vez e assenta
                tq = u - math.sqrt(2 * (chao + 100 * e) / (5200 * e))
                y = chao - max(0.0, 900 * e * tq - 0.5 * 5200 * e * tq * tq)
            _colar(out, img, x, y, a, 1.0, ang * clamp(u * 2))
        return out.astype(np.uint8)
    return f


def negativo(ef, combo, W, H, fps):
    """Folha de contato de negativo: o mesmo quadro repetido em tira de filme, um marcado de vermelho."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.8))
    e = W / 1080
    col, lin = 4, 6
    marca = int(ef.get("marca", 9))

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.25, 0.3)
        im = Image.new("RGB", (W, H), (196, 104, 40))
        d = ImageDraw.Draw(im)
        cw, ch = W / col, H / lin
        mini = Image.fromarray(q).resize((int(cw * 0.86), int(ch * 0.72)))
        laranja = ImageOps.colorize(mini.convert("L"), (40, 20, 10), (240, 190, 140))
        for i in range(lin):
            for j in range(col):
                x, y = j * cw + cw * 0.07, i * ch + ch * 0.14
                im.paste(mini if i * col + j == marca else laranja, (int(x), int(y)))
            for k in range(14):                              # furos da película
                d.rectangle((k * W / 14 + 8 * e, i * ch + 4 * e, k * W / 14 + 30 * e, i * ch + 16 * e), fill=(250, 240, 225))
        mx, my = (marca % col) * cw + cw / 2, (marca // col) * ch + ch / 2
        p = clamp((t - t0 - 0.4) / 0.6)
        d.arc((mx - cw * 0.55, my - ch * 0.5, mx + cw * 0.55, my + ch * 0.5), -90, -90 + 360 * p, fill=(214, 40, 40), width=max(3, int(8 * e)))
        return _mistura(q, np.asarray(im), a)
    return f


def capas_reels(ef, combo, W, H, fps):
    """Capas de Reels (quadros do próprio vídeo) espalhadas em volta da pessoa."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    e = W / 1080
    lugares = [(0.2, 0.25, -8), (0.78, 0.22, 7), (0.18, 0.62, 6), (0.82, 0.6, -6), (0.5, 0.12, 3)]
    capas = {}

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        k = len(capas)
        if k < len(lugares) and (t - t0) >= k * 0.22:
            capas[k] = _sombra(_cartao(_miniatura(q, int(200 * e)), int(6 * e), (250, 248, 244)), int(8 * e), 5)
        a = _env(t, t0, dur, 0.05, 0.3)
        out = q.astype(np.float32)
        for i, img in capas.items():
            x, y, ang = lugares[i]
            _colar(out, img, x * W, y * H, a, _pop(clamp((t - t0 - i * 0.22) / 0.35)), ang)
        return out.astype(np.uint8)
    return f


def mural_titulos(ef, combo, W, H, fps):
    """Mural de bilhetes coloridos com títulos que vão aparecendo em volta da pessoa."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.2))
    e = W / 1080
    textos = ef.get("textos") or ["Avaliação individual", "Tecnologia de ponta", "Cuidado médico", "Na Av. Paulista",
                                  "Protocolo para você", "Sem pressa"]
    cores = [(250, 236, 140), (236, 190, 200), (186, 210, 240), (250, 248, 244), DOURADO, (20, 19, 17)]
    lugares = [(0.22, 0.2), (0.75, 0.24), (0.2, 0.46), (0.8, 0.5), (0.25, 0.72), (0.76, 0.76)]
    notas = []
    rnd = random.Random(2)
    for k, tx in enumerate(textos[:6]):
        bg = cores[k % len(cores)]
        fg = OFF if sum(bg) < 200 else (30, 28, 26)
        tt = _texto(_limpo(tx), "Poppins-Medium.ttf", 30 * e, fg, int(250 * e))
        c = Image.new("RGBA", (tt.width + int(40 * e), tt.height + int(36 * e)), bg + (255,))
        c.alpha_composite(tt, (int(20 * e), int(18 * e)))
        notas.append((_sombra(c, int(6 * e), 4), rnd.uniform(-7, 7)))

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.05, 0.3)
        out = q.astype(np.float32)
        for k, (img, ang) in enumerate(notas):
            u = clamp((t - t0 - k * 0.25) / 0.3)
            if u > 0:
                x, y = lugares[k]
                _colar(out, img, x * W, y * H, a, _pop(u), ang)
        return out.astype(np.uint8)
    return f


def conta_gotas(ef, combo, W, H, fps):
    """Conta-gotas: o cursor pega a cor de um ponto e a cor se espalha pela imagem como uma onda."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    e = W / 1080
    px, py = ef.get("ponto", [0.5, 0.45])
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dist = np.hypot(xx - px * W, yy - py * H)
    guardado = {}

    def f(q, t):
        if not _dentro(t, t0, dur):
            guardado.clear()
            return q
        u = t - t0
        cor_ = guardado.setdefault("c", q[int(py * (H - 1)), int(px * (W - 1))].astype(np.float32))
        out = q.astype(np.float32)
        if u > 0.6:
            raio = (u - 0.6) * W * 1.4
            onda = np.clip((raio - dist) / (80 * e), 0, 1)[..., None] * 0.45 * _env(t, t0, dur, 0.6, 0.4)
            lum = out.mean(axis=2, keepdims=True) / 255
            out = out * (1 - onda) + (cor_ * (0.4 + 0.9 * lum)) * onda
        im = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(im)
        m = ease_out(clamp(u / 0.5))
        cx, cy = W * (0.85 - (0.85 - px) * m), H * (0.85 - (0.85 - py) * m)
        r = 46 * e
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255), width=max(3, int(7 * e)))
        d.ellipse((cx - r + 8 * e, cy - r + 8 * e, cx + r - 8 * e, cy + r - 8 * e), outline=tuple(int(v) for v in cor_), width=max(3, int(10 * e)))
        return np.asarray(im)
    return f


# ------------------------------------------------------------------ em alta nos apps de edição
def holofote(ef, combo, W, H, fps):
    """Holofote: escurece tudo e deixa um círculo de luz no ponto (ou na pessoa)."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    px, py = ef.get("ponto", [0.5, 0.4])
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.hypot((xx - px * W) / W, (yy - py * H) / W)

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.35, 0.35)
        luz = np.clip(1 - (d - 0.22) / 0.12, 0.18, 1)[..., None]
        return (q.astype(np.float32) * (1 - a + a * luz)).astype(np.uint8)
    return f


def lupa(ef, combo, W, H, fps):
    """Lupa: um círculo com aumento passando por um detalhe (rótulo, aparelho, textura)."""
    from .efeitos_viral import _zoom
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    e = W / 1080
    px, py = ef.get("ponto", [0.5, 0.5])
    r = int(170 * e)
    mascara = Image.new("L", (r * 2, r * 2), 0)
    ImageDraw.Draw(mascara).ellipse((0, 0, r * 2 - 1, r * 2 - 1), fill=255)

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.25, 0.3)
        cx = int(px * W + math.sin((t - t0) * 1.5) * 40 * e)
        cy = int(py * H)
        grande = Image.fromarray(_zoom(q, 2.2, cx / W, cy / H))
        rec = grande.crop((W // 2 - r, H // 2 - r, W // 2 + r, H // 2 + r))
        im = Image.fromarray(q)
        im.paste(rec, (cx - r, cy - r), mascara.point(lambda v: int(v * a)))
        dd = ImageDraw.Draw(im)
        dd.ellipse((cx - r, cy - r, cx + r, cy + r), outline=DOURADO, width=max(3, int(8 * e)))
        dd.line((cx + r * 0.7, cy + r * 0.7, cx + r * 1.3, cy + r * 1.3), fill=DOURADO, width=max(6, int(22 * e)))
        return np.asarray(im)
    return f


def rastro(ef, combo, W, H, fps):
    """Rastro (eco): os quadros anteriores ficam como fantasmas atrás do movimento."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 1.6))
    acum = {}

    def f(q, t):
        if not _dentro(t, t0, dur):
            acum.clear()
            return q
        qf = q.astype(np.float32)
        ant = acum.get("q")
        novo = qf if ant is None else np.maximum(qf, ant * 0.86)
        acum["q"] = novo
        return _mistura(q, novo, _env(t, t0, dur, 0.1, 0.3))
    return f


def triptico(ef, combo, W, H, fps):
    """Tríptico: a tela vira três faixas com o mesmo vídeo (meio colorido, laterais em preto e branco)."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.0))
    e = W / 1080

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.2, 0.25)
        faixa = Image.fromarray(q).resize((W, H // 3 + 1))
        cinza = ImageOps.grayscale(faixa).convert("RGB")
        im = Image.new("RGB", (W, H), FUNDO)
        im.paste(cinza, (0, 0))
        im.paste(faixa, (0, H // 3))
        im.paste(cinza, (0, 2 * H // 3))
        d = ImageDraw.Draw(im)
        for k in (1, 2):
            d.line((0, k * H // 3, W, k * H // 3), fill=DOURADO, width=max(2, int(4 * e)))
        return _mistura(q, np.asarray(im), a)
    return f


def vhs(ef, combo, W, H, fps):
    """VHS: linhas de varredura, cor deslocada, ruído e data no canto."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.0))
    e = W / 1080
    linhas = (np.arange(H) % max(2, int(4 * e)) < max(1, int(2 * e))).astype(np.float32)[:, None, None]
    fnt = _f("CourierPrime-Regular.ttf", 40 * e)
    rnd = np.random.default_rng(9)

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        qf = q.astype(np.float32)
        d = max(1, int(6 * e))
        r = qf.copy()
        r[:, d:, 0] = qf[:, :-d, 0]
        r[:, :-d, 2] = qf[:, d:, 2]
        r = r * (1 - 0.18 * linhas) + rnd.normal(0, 8, (H, W, 1)).astype(np.float32)
        im = Image.fromarray(np.clip(r, 0, 255).astype(np.uint8))
        dd = ImageDraw.Draw(im)
        dd.text((50 * e, 60 * e), "▶ PLAY", font=fnt, fill=(240, 240, 240))
        dd.text((50 * e, H - 120 * e), _dt.date.today().strftime("%d %b %Y").upper(), font=fnt, fill=(240, 240, 240))
        return _mistura(q, np.asarray(im), _env(t, t0, dur, 0.1, 0.25))
    return f


def dupla_exposicao(ef, combo, W, H, fps):
    """Dupla exposição: a pessoa ganha por dentro uma segunda imagem (clínica, tecnologia) em tom dourado."""
    from .efeitos_truques import _fundo_imagem
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    img = _fundo_imagem(ef, W, H)

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.35, 0.35)
        qf = q.astype(np.float32)
        seg = img if img is not None else np.asarray(Image.fromarray(q).resize((int(W * 1.6), int(H * 1.6))).crop(
            (int(W * 0.3), int(H * 0.2), int(W * 1.3), int(H * 1.2))), np.float32)
        tela = 255 - (255 - qf) * (255 - seg) / 255                      # mistura "tela"
        m = _mascara(q)
        r = qf * (1 - m) + (tela * 0.6 + np.array(DOURADO, np.float32) * 0.15 + qf * 0.25) * m
        return np.clip(qf * (1 - a) + r * a, 0, 255).astype(np.uint8)
    return f


def brilhos(ef, combo, W, H, fps):
    """Brilhos: estrelinhas douradas piscando em volta (momento de revelação ou de beleza)."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.0))
    e = W / 1080
    rnd = random.Random(21)
    pts = [(rnd.uniform(0.08, 0.92), rnd.uniform(0.15, 0.85), rnd.uniform(0, 6.28), rnd.uniform(14, 34)) for _ in range(18)]

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.2, 0.3)
        im = Image.fromarray(q).convert("RGBA")
        cam = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(cam)
        for x, y, fase, tam in pts:
            b = max(0.0, math.sin(t * 6 + fase))
            if b < 0.1:
                continue
            r = tam * e * b
            cx, cy = x * W, y * H
            d.polygon([(cx, cy - r), (cx + r * 0.25, cy - r * 0.25), (cx + r, cy), (cx + r * 0.25, cy + r * 0.25),
                       (cx, cy + r), (cx - r * 0.25, cy + r * 0.25), (cx - r, cy), (cx - r * 0.25, cy - r * 0.25)],
                      fill=(255, 236, 190, int(255 * a * b)))
        brilho = cam.filter(ImageFilter.GaussianBlur(3 * e))
        im.alpha_composite(brilho)
        im.alpha_composite(cam)
        return np.asarray(im.convert("RGB"))
    return f


def desfoque_fundo(ef, combo, W, H, fps):
    """Fundo desfocado (modo retrato): a pessoa nítida, o fundo some no desfoque."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    e = W / 1080

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.4, 0.4)
        fundo = np.asarray(Image.fromarray(q).filter(ImageFilter.GaussianBlur(18 * e * a)), np.float32)
        m = _mascara(q)
        return np.clip(q.astype(np.float32) * m + fundo * (1 - m), 0, 255).astype(np.uint8)
    return f


# ------------------------------------------------------------------ registro
EFEITOS = {"ascii": ascii_, "capa_revista": capa_revista, "grade_cards": grade_cards, "desinstalando": desinstalando,
           "deletar_app": deletar_app, "retro": retro, "barra_prompt": barra_prompt, "notas_dinheiro": notas_dinheiro,
           "conta_gotas": conta_gotas, "palavras_caindo": palavras_caindo, "pausado": pausado,
           "grafico_linha": grafico_linha, "projetor": projetor, "pixel": pixel, "pasteis": pasteis,
           "negativo": negativo, "linha_tempo_edicao": linha_tempo_edicao, "capas_reels": capas_reels,
           "mural_titulos": mural_titulos, "conquista": conquista, "estudio_edicao": estudio_edicao,
           "pilula_link": pilula_link, "card_titulo": card_titulo,
           "holofote": holofote, "lupa": lupa, "rastro": rastro, "triptico": triptico, "vhs": vhs,
           "dupla_exposicao": dupla_exposicao, "brilhos": brilhos, "desfoque_fundo": desfoque_fundo}

APELIDOS = {"efeito_ascii": "ascii", "estilo_retro": "retro", "efeito_pixel": "pixel", "cores_pasteis": "pasteis",
            "negativo_de_filme": "negativo", "projetor_de_cinema": "projetor", "grafico_em_ascensao": "grafico_linha",
            "conquista_desbloqueada": "conquista", "estudio_de_edicao": "estudio_edicao", "barra_de_prompt": "barra_prompt",
            "zoom_atravessando": "zoom_atravessa", "linha_do_tempo_de_edicao": "linha_tempo_edicao",
            "mural_de_titulos": "mural_titulos", "capas_de_reels": "capas_reels", "grade_de_cards": "grade_cards",
            "notas_de_dinheiro": "notas_dinheiro", "deletar": "deletar_app", "modo_retrato": "desfoque_fundo"}

NOMES = {"ascii": "Efeito ASCII", "capa_revista": "Capa de revista", "grade_cards": "Grade de cards",
         "desinstalando": "Desinstalando (barra de progresso)", "deletar_app": "Deletar app (ícones tremendo)",
         "retro": "Estilo retrô (meio-tom)", "barra_prompt": "Barra de prompt", "notas_dinheiro": "Gravura de cédula",
         "conta_gotas": "Conta-gotas (cor que se espalha)", "palavras_caindo": "Palavras caindo",
         "pausado": "Pausado", "grafico_linha": "Gráfico em ascensão", "projetor": "Projetor de cinema",
         "pixel": "Efeito pixel", "pasteis": "Cores pastéis", "negativo": "Negativo de filme",
         "linha_tempo_edicao": "Linha do tempo de edição", "capas_reels": "Capas de Reels",
         "mural_titulos": "Mural de títulos", "conquista": "Conquista desbloqueada",
         "estudio_edicao": "Estúdio de edição (controles)", "pilula_link": "Link aqui embaixo",
         "card_titulo": "Cartão de título", "holofote": "Holofote", "lupa": "Lupa", "rastro": "Rastro (eco)",
         "triptico": "Tríptico", "vhs": "VHS", "dupla_exposicao": "Dupla exposição", "brilhos": "Brilhos",
         "desfoque_fundo": "Fundo desfocado (modo retrato)"}

_PT = ("ponto", "ponto", "Onde (clique no vídeo)")
CAMPOS = {
    "ascii": [("cor", "escolha:dourado|verde", "Cor dos caracteres")],
    "capa_revista": [("revista", "texto", "Nome da revista"), ("texto", "texto", "Manchete"), ("chamadas", "linhas", "Chamadas")],
    "grade_cards": [("numero", "texto", "Número grande"), ("rotulo", "texto", "Rótulo")],
    "desinstalando": [("texto", "texto", "Texto da barra")],
    "deletar_app": [("apps", "linhas", "Letras dos ícones (uma por linha)")],
    "retro": [("cor", "escolha:dourado|rosa", "Cores")],
    "barra_prompt": [("texto", "texto", "Texto digitado")],
    "notas_dinheiro": [("valor", "texto", "Número nos cantos")],
    "conta_gotas": [_PT],
    "palavras_caindo": [("palavras", "linhas", "Palavras (uma por linha)")],
    "pausado": [("texto", "texto", "Palavra no topo")],
    "grafico_linha": [("de", "numero", "De"), ("ate", "numero", "Até"), ("rotulo", "texto", "Rótulo")],
    "projetor": [], "pixel": [("bloco", "numero", "Tamanho do pixel")],
    "pasteis": [("texto", "texto", "Palavra grande"), ("usuario", "texto", "@ do cartão")],
    "negativo": [("marca", "numero", "Qual quadro marcar (0 a 23)")],
    "linha_tempo_edicao": [], "capas_reels": [],
    "mural_titulos": [("textos", "linhas", "Bilhetes (um por linha)")],
    "conquista": [("texto", "texto", "Conquista")],
    "estudio_edicao": [],
    "pilula_link": [("texto", "texto", "Texto"), _PT],
    "card_titulo": [("cabecalho", "texto", "Linha de cima"), ("texto", "texto", "Título")],
    "holofote": [_PT], "lupa": [_PT], "rastro": [], "triptico": [], "vhs": [],
    "dupla_exposicao": [("imagem", "texto", "Imagem (vazio = foto do tema da Biblioteca)")],
    "brilhos": [], "desfoque_fundo": [],
}

DURACAO = {"ascii": 2.0, "capa_revista": 3.0, "grade_cards": 3.0, "desinstalando": 2.5, "deletar_app": 3.0,
           "retro": 2.5, "barra_prompt": 2.8, "notas_dinheiro": 2.5, "conta_gotas": 2.5, "palavras_caindo": 3.0,
           "pausado": 2.0, "grafico_linha": 3.0, "projetor": 3.0, "pixel": 2.0, "pasteis": 3.0, "negativo": 2.8,
           "linha_tempo_edicao": 3.0, "capas_reels": 3.0, "mural_titulos": 3.2, "conquista": 2.8,
           "estudio_edicao": 3.0, "pilula_link": 2.5, "card_titulo": 2.8, "holofote": 2.5, "lupa": 2.5,
           "rastro": 1.6, "triptico": 2.0, "vhs": 2.0, "dupla_exposicao": 2.5, "brilhos": 2.0, "desfoque_fundo": 3.0}

EXEMPLOS = {"capa_revista": {"texto": "Edição especial"}, "grade_cards": {"numero": "24", "rotulo": "efeitos · 1 vídeo"},
            "desinstalando": {"texto": "Desinstalando: hábitos que atrapalham"}, "barra_prompt": {"texto": "/edita meu reel"},
            "palavras_caindo": {"palavras": ["cuidado", "avaliação", "tecnologia", "pele", "Divine"]},
            "pausado": {"texto": "PAUSA"}, "grafico_linha": {"de": 0, "ate": 24, "rotulo": "efeitos neste vídeo"},
            "pasteis": {"texto": "Divine"}, "mural_titulos": {}, "conquista": {"texto": "Primeira avaliação agendada"},
            "pilula_link": {"texto": "link aqui embaixo"}, "card_titulo": {"texto": "Protocolo Divine / passo a passo"},
            "conta_gotas": {"ponto": [0.5, 0.45]}, "holofote": {"ponto": [0.5, 0.4]}, "lupa": {"ponto": [0.5, 0.5]}}

MOMENTO_AMOSTRA = {k: min(1.6, v * 0.6) for k, v in DURACAO.items()}

SONS = {"ascii": "glitch_digital", "capa_revista": "flash_brilho", "grade_cards": "whoosh_rapido",
        "desinstalando": "zap_suave", "deletar_app": "estalo_dedos", "retro": "scratch_disco", "barra_prompt": "zap_suave",
        "notas_dinheiro": "estalo_dedos", "conta_gotas": "zap_suave", "palavras_caindo": "estalo_dedos",
        "pausado": "estalo_dedos", "grafico_linha": "subida_tensao", "projetor": "scratch_disco", "pixel": "glitch_digital",
        "pasteis": "flash_brilho", "negativo": "scratch_disco", "linha_tempo_edicao": "zap_suave",
        "capas_reels": "whoosh_rapido", "mural_titulos": "estalo_dedos", "conquista": "flash_brilho",
        "estudio_edicao": "zap_suave", "pilula_link": "coracao", "card_titulo": "whoosh_rapido",
        "holofote": "drop_sub", "lupa": "zap_suave", "rastro": "whoosh_rapido", "triptico": "boom_grave",
        "vhs": "scratch_disco", "dupla_exposicao": "subida_tensao", "brilhos": "flash_brilho", "desfoque_fundo": "drop_sub"}


# ------------------------------------------------------------------ versões nativas de efeitos do Higgsfield
# (o que dá para fazer sobre o vídeo gravado, sem IA generativa: grátis, no Mac, sem internet)
def congelar_pessoa(ef, combo, W, H, fps):
    """'Stop world' / 'Act natural': a pessoa congela no lugar enquanto o fundo continua andando."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    guardado = {}

    def f(q, t):
        if not _dentro(t, t0, dur):
            guardado.clear()
            return q
        if "q" not in guardado:
            guardado["q"] = q.astype(np.float32)
            guardado["m"] = _mascara(q)
        a = _env(t, t0, dur, 0.05, 0.25)
        m = guardado["m"] * a
        r = guardado["q"] * m + q.astype(np.float32) * (1 - m)
        return np.clip(r, 0, 255).astype(np.uint8)
    return f


def mundo_congelado(ef, combo, W, H, fps):
    """'Frozen in motion' ao contrário: o fundo para no tempo e só a pessoa continua se mexendo."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    guardado = {}

    def f(q, t):
        if not _dentro(t, t0, dur):
            guardado.clear()
            return q
        fundo = guardado.setdefault("q", q.astype(np.float32))
        m = _mascara(q)
        a = _env(t, t0, dur, 0.05, 0.25)
        cinza = fundo.mean(axis=2, keepdims=True)
        fundo_t = fundo * (1 - 0.35 * a) + cinza * 0.35 * a                 # o mundo parado perde um pouco a cor
        r = q.astype(np.float32) * m + (fundo_t * a + q.astype(np.float32) * (1 - a)) * (1 - m)
        return np.clip(r, 0, 255).astype(np.uint8)
    return f


def clones(ef, combo, W, H, fps):
    """'Clones' / 'Studio slide': cópias recortadas da pessoa ao lado e atrás, entrando em sequência."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    n = int(ef.get("quantos", 4))
    lugares = [(-0.28, 0.9), (0.28, 0.9), (-0.16, 0.75), (0.16, 0.75), (-0.38, 0.7), (0.38, 0.7)][:n]

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.1, 0.3)
        m = _mascara(q)
        pessoa = np.concatenate([q, (m * 255).astype(np.uint8)], axis=2)
        img = Image.fromarray(pessoa, "RGBA")
        out = q.astype(np.float32)
        base = out.copy()
        for k, (dx, esc) in enumerate(sorted(lugares, key=lambda v: v[1])):
            u = clamp((t - t0 - k * 0.15) / 0.3)
            if u <= 0:
                continue
            c = img.resize((int(W * esc), int(H * esc)))
            cam = np.zeros_like(out)
            _colar(cam, c, W / 2 + dx * W, H * (1 - esc / 2) + (1 - esc) * H * 0.02, 1.0)
            mk = np.zeros((H, W, 1), np.float32)
            cm = Image.fromarray((np.asarray(c)[..., 3]).astype(np.uint8))
            tmp = np.zeros((H, W), np.float32)
            x0 = int(W / 2 + dx * W - c.width / 2)
            y0 = int(H * (1 - esc / 2) + (1 - esc) * H * 0.02 - c.height / 2)
            xs, ys, xe, ye = max(0, x0), max(0, y0), min(W, x0 + c.width), min(H, y0 + c.height)
            if xe > xs and ye > ys:
                tmp[ys:ye, xs:xe] = np.asarray(cm, np.float32)[ys - y0:ye - y0, xs - x0:xe - x0] / 255
            mk[..., 0] = tmp * a * ease_out(u) * 0.95
            base = base * (1 - mk) + cam * mk
        r = base * (1 - m) + out * m                                         # a original fica na frente
        return np.clip(r, 0, 255).astype(np.uint8)
    return f


def desenho(ef, combo, W, H, fps):
    """'Sketch' / 'Canvas': vira desenho a lápis sobre papel creme."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        g = Image.fromarray(q).convert("L")
        inv = ImageOps.invert(g).filter(ImageFilter.GaussianBlur(max(2, W // 160)))
        gf, bf = np.asarray(g, np.float32), np.asarray(inv, np.float32)
        lapis = np.clip(gf * 255 / np.maximum(1, 255 - bf), 0, 255)            # "color dodge": traço de lápis
        papel = np.array(CREME, np.float32)
        r = (lapis[..., None] / 255) * papel + (1 - lapis[..., None] / 255) * np.array((60, 52, 44), np.float32)
        return _mistura(q, r, _env(t, t0, dur, 0.3, 0.3))
    return f


def quadrinho(ef, combo, W, H, fps):
    """'Comic' / 'Flash comic': cores chapadas, contorno preto grosso e retícula."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.0))
    passo = max(4, W // 160)
    yy, xx = np.mgrid[0:H, 0:W]
    pontos = ((xx % passo - passo / 2) ** 2 + (yy % passo - passo / 2) ** 2 < (passo * 0.3) ** 2)[..., None]

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        im = Image.fromarray(q)
        chapado = np.asarray(ImageOps.posterize(im.filter(ImageFilter.MedianFilter(5)), 3), np.float32)
        bordas = np.asarray(im.convert("L").filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3)), np.float32)[..., None]
        r = chapado * (1 - np.clip(bordas / 60, 0, 1))
        sombra = (chapado.mean(axis=2, keepdims=True) < 90) & pontos
        r = np.where(sombra, r * 0.4, r)
        return _mistura(q, r, _env(t, t0, dur, 0.15, 0.25))
    return f


def luz_estourada(ef, combo, W, H, fps):
    """'Overexposed': luz estourada e brilho difuso (abertura etérea, sonho)."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.0))

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        a = _env(t, t0, dur, 0.3, 0.4)
        qf = q.astype(np.float32)
        brilho = np.clip(qf - 150, 0, 255)
        bloom = np.asarray(Image.fromarray(brilho.astype(np.uint8)).filter(ImageFilter.GaussianBlur(W // 30)), np.float32)
        r = np.clip(qf * (1 + 0.6 * a) + bloom * 1.6 * a + 25 * a, 0, 255)
        return r.astype(np.uint8)
    return f


def noir(ef, combo, W, H, fps):
    """'Noir': preto e branco de alto contraste, vinheta e sombra de persiana."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    vinheta = np.clip(1.3 - np.hypot((xx - W / 2) / W, (yy - H / 2) / H) * 1.6, 0.25, 1)
    persiana = 0.82 + 0.18 * (np.sin((yy + xx * 0.35) / (H / 40)) > 0)

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        g = q.astype(np.float32).mean(axis=2)
        g = np.clip((g - 128) * 1.45 + 128, 0, 255) * vinheta * persiana
        return _mistura(q, np.repeat(g[..., None], 3, axis=2), _env(t, t0, dur, 0.3, 0.3))
    return f


def marmore(ef, combo, W, H, fps):
    """'Marble': vira escultura em mármore (relevo claro com veios suaves)."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    rnd = np.random.default_rng(12)
    ruido = np.asarray(Image.fromarray((rnd.random((H // 8, W // 8)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    veios = (np.abs(np.sin((xx * 0.8 + yy * 0.5) / (W / 9) + ruido / 40)) ** 6)[..., None]

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        relevo = np.asarray(Image.fromarray(q).convert("L").filter(ImageFilter.EMBOSS), np.float32)[..., None]
        lum = q.astype(np.float32).mean(axis=2, keepdims=True)
        pedra = (lum * 0.55 + relevo * 0.45) * np.array((1.02, 1.0, 0.95), np.float32) + 40
        pedra = pedra * (1 - veios * 0.12)
        return _mistura(q, np.clip(pedra, 0, 255), _env(t, t0, dur, 0.4, 0.4))
    return f


EFEITOS.update({"congelar_pessoa": congelar_pessoa, "mundo_congelado": mundo_congelado, "clones": clones,
                "desenho": desenho, "quadrinho": quadrinho, "luz_estourada": luz_estourada, "noir": noir,
                "marmore": marmore})
APELIDOS.update({"stop_world": "congelar_pessoa", "act_natural": "congelar_pessoa", "frozen_in_motion": "mundo_congelado",
                 "studio_slide": "clones", "sketch": "desenho", "comic": "quadrinho", "overexposed": "luz_estourada",
                 "marble": "marmore"})
NOMES.update({"congelar_pessoa": "Pessoa congelada (Stop world)", "mundo_congelado": "Mundo congelado (Frozen in motion)",
              "clones": "Clones", "desenho": "Desenho a lápis (Sketch)", "quadrinho": "Quadrinho (Comic)",
              "luz_estourada": "Luz estourada (Overexposed)", "noir": "Noir", "marmore": "Mármore (Marble)"})
CAMPOS.update({"congelar_pessoa": [], "mundo_congelado": [], "clones": [("quantos", "numero", "Quantos clones (2 a 6)")],
               "desenho": [], "quadrinho": [], "luz_estourada": [], "noir": [], "marmore": []})
DURACAO.update({"congelar_pessoa": 2.5, "mundo_congelado": 2.5, "clones": 2.5, "desenho": 2.5, "quadrinho": 2.0,
                "luz_estourada": 2.0, "noir": 2.5, "marmore": 2.5})
EXEMPLOS.update({"clones": {"quantos": 4}})
MOMENTO_AMOSTRA.update({k: min(1.6, DURACAO[k] * 0.6) for k in ("congelar_pessoa", "mundo_congelado", "clones", "desenho",
                                                                 "quadrinho", "luz_estourada", "noir", "marmore")})
SONS.update({"congelar_pessoa": "drop_sub", "mundo_congelado": "subida_tensao", "clones": "whoosh_rapido",
             "desenho": "scratch_disco", "quadrinho": "estalo_dedos", "luz_estourada": "flash_brilho", "noir": "boom_grave",
             "marmore": "drop_sub"})
