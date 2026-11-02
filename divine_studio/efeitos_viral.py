"""Efeitos e transições que mais aparecem em edits virais (CapCut, Edits, TikTok), feitos aqui no padrão Divine:
rápidos, mas limpos e com acabamento de luxo (nada de neon nem tremedeira longa).

  zoom_batida   "zoom punch": entra 12% em 0,08 s no tempo da batida e volta suave
  flash         flash branco ou dourado de 0,3 s (troca de cena, revelação)
  glitch_rgb    separação de cores + fatias deslocadas por 0,4 s (falha digital elegante)
  giro          giro de 360° com desfoque (transição "spin")
  tremor        tremor de impacto curto que some (camera shake)
  zoom_blur     desfoque radial de zoom (transição "zoom blur")
  pulso         pulsos de brilho e zoom no ritmo da música (bpm)
  revelar_foco  sai do desfoque para o nítido (blur in)
  cor_volta     preto e branco que volta a ter cor (color pop)

Cada um sugere um som do kit viral (divine_studio/sfx_viral.py).
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageFilter

from .anim import clamp, ease_in_out, ease_out
from .config import cor


def _dentro(t, t0, dur):
    return t0 <= t <= t0 + dur


def _zoom(q: np.ndarray, s: float, cx: float = 0.5, cy: float = 0.5) -> np.ndarray:
    if s <= 1.001:
        return q
    h, w = q.shape[:2]
    cw, ch = w / s, h / s
    x0 = clamp(cx * w - cw / 2, 0, w - cw)
    y0 = clamp(cy * h - ch / 2, 0, h - ch)
    return np.asarray(Image.fromarray(q).resize((w, h), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch)))


def zoom_batida(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 0.6))
    forca = float(ef.get("zoom", 1.12))
    px, py = ef.get("ponto", [0.5, 0.45])

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = t - t0
        p = ease_out(clamp(u / 0.08)) if u < 0.08 else 1 - ease_in_out(clamp((u - 0.08) / (dur - 0.08)))
        return _zoom(q, 1 + (forca - 1) * p, px, py)
    return f


def flash(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 0.3))
    alvo = np.array(cor("dourado_destaque") if ef.get("cor") == "dourado" else (255, 255, 255), np.float32)

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = (t - t0) / dur
        a = (1 - u) ** 2 * float(ef.get("forca", 0.85))
        return (q.astype(np.float32) * (1 - a) + alvo * a).astype(np.uint8)
    return f


def glitch_rgb(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 0.4))

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = (t - t0) / dur
        forca = math.sin(math.pi * u)
        h, w = q.shape[:2]
        d = max(1, int(w * 0.012 * forca))
        out = q.copy()
        out[..., 0] = np.roll(q[..., 0], d, axis=1)            # vermelho para a direita
        out[..., 2] = np.roll(q[..., 2], -d, axis=1)           # azul para a esquerda
        quadro = int(t * fps)
        r = np.random.default_rng(quadro + int(t0 * 1000))
        for _ in range(int(3 * forca) + 1):                    # fatias deslocadas
            y = int(r.integers(0, h - 10))
            alt = int(r.integers(4, max(6, h // 30)))
            out[y:y + alt] = np.roll(out[y:y + alt], int(r.integers(-w // 25, w // 25) * forca), axis=1)
        return out
    return f


def giro(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 0.5))
    sentido = -1 if ef.get("direcao") == "esquerda" else 1

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = ease_in_out((t - t0) / dur)
        ang = sentido * 360 * u
        im = Image.fromarray(q)
        h, w = q.shape[:2]
        th = math.radians(ang % 180)
        c_, s_ = abs(math.cos(th)), abs(math.sin(th))
        s = max(c_ + (h / w) * s_, c_ + (w / h) * s_) * 1.02     # escala exata para nunca mostrar borda
        rot = im.rotate(ang, resample=Image.BILINEAR, expand=False)
        rot = Image.fromarray(_zoom(np.asarray(rot), s))
        borr = 6 * math.sin(math.pi * u)
        if borr > 0.5:
            rot = rot.resize((w // 3, h // 3), Image.BILINEAR).filter(ImageFilter.GaussianBlur(borr / 3)).resize((w, h), Image.BILINEAR)
        return np.asarray(rot)
    return f


def tremor(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 0.45))
    amp = float(ef.get("forca", 1.0))

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = (t - t0) / dur
        h, w = q.shape[:2]
        a = (1 - u) ** 2 * amp * w * 0.012
        dx = int(a * math.sin(t * 95))
        dy = int(a * math.cos(t * 71))
        z = _zoom(q, 1 + 0.03 * amp)
        return np.roll(np.roll(z, dx, axis=1), dy, axis=0)
    return f


def zoom_blur(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 0.4))

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        forca = math.sin(math.pi * (t - t0) / dur)
        if forca < 0.05:
            return q
        acc = q.astype(np.float32)
        passos = 5
        for k in range(1, passos):
            acc += _zoom(q, 1 + 0.035 * k * forca).astype(np.float32)
        return (acc / passos).astype(np.uint8)
    return f


def pulso(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 4.0))
    bpm = float(ef.get("bpm", 100))
    periodo = 60 / max(40, bpm)

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        fase = ((t - t0) % periodo) / periodo
        p = math.exp(-fase * 9)                                 # bate e solta, em cada tempo
        z = _zoom(q, 1 + 0.03 * p)
        return np.clip(z.astype(np.float32) * (1 + 0.10 * p), 0, 255).astype(np.uint8)
    return f


def revelar_foco(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 0.8))

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        r = (1 - ease_out((t - t0) / dur)) * 14
        if r < 0.4:
            return q
        h, w = q.shape[:2]
        return np.asarray(Image.fromarray(q).resize((w // 2, h // 2), Image.BILINEAR)
                          .filter(ImageFilter.GaussianBlur(r / 2)).resize((w, h), Image.BILINEAR))
    return f


def cor_volta(ef, combo, W, H, fps):
    t0, dur = ef["inicio"], float(ef.get("duracao", 1.6))

    def f(q, t):
        if not _dentro(t, t0, dur):
            return q
        u = (t - t0) / dur
        cinza_ate = 0.55                                        # preto e branco e, de repente, a cor volta suave
        a = 1.0 if u < cinza_ate else 1 - ease_in_out((u - cinza_ate) / (1 - cinza_ate))
        qf = q.astype(np.float32)
        cinza = (qf @ np.array([0.299, 0.587, 0.114], np.float32))[..., None]
        return (qf * (1 - a) + cinza * a).astype(np.uint8)
    return f


EFEITOS = {"zoom_batida": zoom_batida, "flash": flash, "glitch_rgb": glitch_rgb, "giro": giro, "tremor": tremor,
           "zoom_blur": zoom_blur, "pulso": pulso, "revelar_foco": revelar_foco, "cor_volta": cor_volta}

NOMES = {"zoom_batida": "Zoom na batida (punch)", "flash": "Flash (branco ou dourado)", "glitch_rgb": "Glitch RGB",
         "giro": "Giro 360° (spin)", "tremor": "Tremor de impacto (shake)", "zoom_blur": "Zoom blur",
         "pulso": "Pulso no ritmo (bpm)", "revelar_foco": "Revelar do desfoque", "cor_volta": "P&B que volta a cor"}

CAMPOS = {
    "zoom_batida": [("ponto", "ponto", "Onde (clique no vídeo)"), ("zoom", "numero", "Força (1.05 a 1.25)")],
    "flash": [("cor", "escolha:branco|dourado", "Cor do flash")],
    "glitch_rgb": [],
    "giro": [("direcao", "escolha:direita|esquerda", "Sentido")],
    "tremor": [("forca", "numero", "Força (0.5 a 1.5)")],
    "zoom_blur": [],
    "pulso": [("bpm", "numero", "Batidas por minuto da música")],
    "revelar_foco": [],
    "cor_volta": [],
}

DURACAO = {"zoom_batida": 0.6, "flash": 0.3, "glitch_rgb": 0.4, "giro": 0.5, "tremor": 0.45, "zoom_blur": 0.4,
           "pulso": 4.0, "revelar_foco": 0.8, "cor_volta": 1.6}

EXEMPLOS = {"zoom_batida": {"zoom": 1.15}, "flash": {"cor": "dourado"}, "glitch_rgb": {}, "giro": {}, "tremor": {},
            "zoom_blur": {}, "pulso": {"bpm": 100}, "revelar_foco": {}, "cor_volta": {}}

MOMENTO_AMOSTRA = {"zoom_batida": 0.1, "flash": 0.06, "glitch_rgb": 0.2, "giro": 0.2, "tremor": 0.05, "zoom_blur": 0.2,
                   "pulso": 0.02, "revelar_foco": 0.2, "cor_volta": 0.4}

# som sugerido de cada um (família do kit viral ou do kit Divine)
SONS = {"zoom_batida": "boom_grave", "flash": "flash_brilho", "glitch_rgb": "glitch_digital", "giro": "zap_suave",
        "tremor": "boom_grave", "zoom_blur": "whoosh_rapido", "pulso": "coracao", "revelar_foco": "subida_tensao",
        "cor_volta": "estalo_dedos"}
