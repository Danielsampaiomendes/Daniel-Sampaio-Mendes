"""Efeitos 3D e espaciais, câmera elegante e recursos com cara de "difícil de filmar" (versão suave Divine).

Todos são efeitos no quadro: f(quadro, t) -> quadro. Movimento lento com easing, nada piscando, nada tremendo.
Pensados para prender a atenção: algo muda no espaço a cada poucos segundos, sem cansar.

  camera_elegante   leve mudança de perspectiva + zoom que deriva devagar (como câmera num slider)
  cartao_3d         o vídeo vira um cartão que inclina no espaço (ou gira, como transição) sobre o fundo Divine
  parallax          2.5D: o fundo anda e desfoca de leve, a pessoa fica nítida e parada (precisa do recorte)
  dolly_zoom        "efeito vertigem": o fundo aproxima e a pessoa fica do mesmo tamanho (precisa do recorte)
  chicote           transição em chicote (whip pan) com borrão de movimento, para esconder o corte
  congelar          congela o quadro e aproxima devagar, com moldura dourada fina (pausa dramática)
  foco_lente        desfoque de lente em volta de um ponto (modo retrato; com recorte, o fundo todo)
  luz_dourada       feixe de luz dourada que atravessa a cena (light leak suave)

No projeto.yaml, `camera_elegante: true` aplica a câmera elegante no vídeo inteiro, mudando a direção a cada trecho.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .anim import clamp, ease_in_out
from .config import cor


# prévia rápida: a câmera elegante usa recorte simples (sem a inclinação de perspectiva); ligado pelo editar --rapido
RAPIDO = {"ligado": False}


# ---------------------------------------------------------------- geometria

def coeficientes(saida: list, entrada: list) -> tuple:
    """Coeficientes do Image.PERSPECTIVE que levam cada ponto de 'saida' (no quadro final) a 'entrada' (na fonte)."""
    A, b = [], []
    for (x, y), (u, v) in zip(saida, entrada):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b += [u, v]
    return tuple(np.linalg.solve(np.array(A, float), np.array(b, float)))


def projetar(w: float, h: float, cx: float, cy: float, guinada: float, arfagem: float = 0.0,
             foco: float = 2.4) -> list:
    """Cantos de um retângulo w x h girado no espaço (graus), projetado com câmera de foco relativo 'foco' * w."""
    f = foco * max(w, h)
    gy, gx = math.radians(guinada), math.radians(arfagem)
    pts = []
    for X, Y in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        x1, z1 = X * math.cos(gy), X * math.sin(gy)                  # guinada (eixo vertical)
        y2, z2 = Y * math.cos(gx) - z1 * math.sin(gx), Y * math.sin(gx) + z1 * math.cos(gx)   # arfagem
        k = f / (f + z2)
        pts.append((cx + x1 * k, cy + y2 * k))
    return pts


def _envelope(t, t0, dur, entrada=0.8, saida=0.8):
    if t < t0 or t > t0 + dur:
        return 0.0
    return ease_in_out(clamp((t - t0) / entrada)) * ease_in_out(clamp((t0 + dur - t) / saida))


def _janela(q: np.ndarray, cx: float, cy: float, s: float, keystone: float, inclina: float = 0.0) -> np.ndarray:
    """Recorta da fonte um quadrilátero (zoom s, perspectiva 'keystone' lateral e 'inclina' vertical) e enche o quadro."""
    h, w = q.shape[:2]
    hw, hh = w / 2 / s, h / 2 / s
    k, v = keystone, inclina
    fonte = [(cx - hw * (1 - v), cy - hh * (1 - k)), (cx + hw * (1 - v), cy - hh * (1 + k)),
             (cx + hw * (1 + v), cy + hh * (1 + k)), (cx - hw * (1 + v), cy + hh * (1 - k))]
    # nunca mostra borda: o quadrilátero fica dentro da fonte
    fx = [clamp(x, 0, w - 1) for x, _ in fonte]
    fy = [clamp(y, 0, h - 1) for _, y in fonte]
    if RAPIDO["ligado"] or (abs(k) < 1e-4 and abs(v) < 1e-4):
        # prévia (ou sem perspectiva): recorte + redimensiono, ~4x mais rápido; a final usa a perspectiva completa
        box = (min(fx), min(fy), max(fx), max(fy))
        return np.asarray(Image.fromarray(q).resize((w, h), Image.BILINEAR, box=box))
    c = coeficientes([(0, 0), (w, 0), (w, h), (0, h)], list(zip(fx, fy)))
    return np.asarray(Image.fromarray(q).transform((w, h), Image.PERSPECTIVE, c, Image.BILINEAR))


# ---------------------------------------------------------------- câmera elegante

def _movimento(direcao: str, p: float, intensidade: float) -> tuple:
    """(zoom, deriva_x, deriva_y, keystone, inclina) de um movimento elegante em p (0 a 1)."""
    e = ease_in_out(p)
    i = intensidade
    s = 1.06 + 0.05 * i * e                                   # zoom que entra devagar (sempre >= 1.06: sem borda)
    flutua = math.sin(p * math.pi) * 0.004 * i                 # sobe e desce quase imperceptível
    if direcao == "esquerda":
        return s, -0.018 * i * (e - 0.5), flutua, -0.022 * i * (e - 0.3), 0.0
    if direcao == "frente":
        return s + 0.02 * i * e, 0.0, flutua, 0.0, 0.012 * i * e
    if direcao == "cima":
        return s, 0.0, -0.016 * i * (e - 0.5), 0.0, -0.016 * i * (e - 0.3)
    return s, 0.018 * i * (e - 0.5), flutua, 0.022 * i * (e - 0.3), 0.0       # direita (padrão)


def camera_elegante(ef, combo, W, H, fps):
    """Perspectiva e zoom mudando devagar, como câmera num slider: dá profundidade sem chamar atenção para si."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 5.0))
    direcao = ef.get("direcao", "direita")
    intensidade = clamp(float(ef.get("intensidade", 1.0)), 0.2, 2.0)
    px, py = ef.get("ponto", [0.5, 0.45])

    def f(q, t):
        if t < t0 or t > t0 + dur:
            return q
        a = _envelope(t, t0, dur, 0.5, 0.5)
        s, dx, dy, k, v = _movimento(direcao, (t - t0) / dur, intensidade)
        s = 1 + (s - 1) * a
        h, w = q.shape[:2]
        cx = w * (0.5 + (px - 0.5) * 0.3 * a + dx * a)
        cy = h * (0.5 + (py - 0.5) * 0.3 * a + dy * a)
        return _janela(q, cx, cy, s, k * a, v * a)
    return f


def camera_continua(duracao: float, cortes: list | None = None, intensidade: float = 0.8):
    """Câmera elegante no vídeo inteiro: um movimento por trecho (muda a direção a cada corte ou a cada ~4 s)."""
    marcos = sorted({0.0, *[c for c in (cortes or []) if 0.5 < c < duracao - 0.5]})
    if len(marcos) < 2:
        marcos = [x * 4.0 for x in range(int(duracao // 4) + 1)]
    marcos.append(duracao)
    trechos = [(a, b) for a, b in zip(marcos, marcos[1:]) if b - a > 0.3]
    direcoes = ["direita", "frente", "esquerda", "cima"]

    def f(q, t):
        for k, (a, b) in enumerate(trechos):
            if a <= t < b:
                s, dx, dy, ks, v = _movimento(direcoes[k % 4], (t - a) / (b - a), intensidade)
                h, w = q.shape[:2]
                return _janela(q, w * (0.5 + dx), h * (0.5 + dy), s, ks, v)
        return q
    return f


# ---------------------------------------------------------------- cartão 3D

def _fundo_divine(q: np.ndarray, p: float) -> np.ndarray:
    h, w = q.shape[:2]
    borr = Image.fromarray(q).resize((w // 8, h // 8), Image.BILINEAR).filter(ImageFilter.GaussianBlur(4))
    borr = np.asarray(borr.resize((w, h), Image.BICUBIC), np.float32) * 0.35
    fundo = np.array(cor("fundo"), np.float32)
    return q.astype(np.float32) * (1 - p) + (borr * 0.6 + fundo * 0.4) * p


def cartao_3d(ef, combo, W, H, fps):
    """O vídeo encolhe num cartão de bordas douradas que inclina no espaço e volta (modo girar: dá a volta)."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    angulo = float(ef.get("angulo", 22))
    escala = float(ef.get("escala", 0.74))
    girar = ef.get("modo") == "girar"

    def f(q, t):
        if t < t0 or t > t0 + dur:
            return q
        p = _envelope(t, t0, dur, 0.7, 0.7)
        h, w = q.shape[:2]
        u = clamp((t - t0) / dur)
        if girar:
            g = 360 * ease_in_out(u)
            gui, arf = (g if g <= 90 or g >= 270 else g - 180), 6 * math.sin(u * math.pi)
        else:
            gui = angulo * math.sin(u * math.pi * 2 - 0.4) * p
            arf = angulo * 0.25 * math.sin(u * math.pi) * p
        s = 1 - (1 - escala) * p
        quad = projetar(w * s, h * s, w / 2, h / 2, gui, arf)
        fonte = Image.fromarray(q).convert("RGBA")
        c = coeficientes(quad, [(0, 0), (w, 0), (w, h), (0, h)])
        card = fonte.transform((w, h), Image.PERSPECTIVE, c, Image.BILINEAR, fillcolor=(0, 0, 0, 0))
        base = Image.fromarray(_fundo_divine(q, p).astype(np.uint8)).convert("RGBA")
        sombra = Image.new("L", (w, h), 0)
        ImageDraw.Draw(sombra).polygon([(x + w * 0.015, y + h * 0.02) for x, y in quad], fill=int(150 * p))
        sombra = sombra.filter(ImageFilter.GaussianBlur(w * 0.025))
        base.paste(Image.new("RGBA", (w, h), (0, 0, 0, 255)), (0, 0), sombra)
        base.alpha_composite(card)
        if p > 0.05:
            ImageDraw.Draw(base).polygon(quad, outline=cor("dourado") + (int(220 * p),), width=max(2, w // 400))
        return np.asarray(base.convert("RGB"))
    return f


# ---------------------------------------------------------------- recorte da pessoa (parallax, vertigem, lente)

def _mascara(q):
    from . import recorte
    return recorte.mascara(q)


def parallax(ef, combo, W, H, fps):
    """2.5D: o fundo desliza e desfoca de leve enquanto a pessoa fica nítida. Sem recorte: câmera elegante."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 4.0))
    lado = -1 if ef.get("direcao") == "esquerda" else 1
    reserva = camera_elegante({**ef, "duracao": dur, "intensidade": 1.2}, combo, W, H, fps)

    def f(q, t):
        if t < t0 or t > t0 + dur:
            return q
        m = _mascara(q)
        if m is None:
            return reserva(q, t)
        p = _envelope(t, t0, dur, 0.8, 0.8)
        u = ease_in_out(clamp((t - t0) / dur))
        h, w = q.shape[:2]
        fundo = _janela(q, w * (0.5 + lado * 0.025 * (u - 0.5) * 2 * p), h / 2, 1 + 0.07 * p, 0.0)
        fundo = np.asarray(Image.fromarray(fundo).filter(ImageFilter.GaussianBlur(2.5 * p)), np.float32)
        pessoa = _janela(q, w * (0.5 - lado * 0.006 * (u - 0.5) * 2 * p), h / 2, 1 + 0.03 * p, 0.0)
        mm = _mascara(pessoa)
        mm = m if mm is None else mm
        return (fundo * (1 - mm) + pessoa.astype(np.float32) * mm).astype(np.uint8)
    return f


def dolly_zoom(ef, combo, W, H, fps):
    """Efeito vertigem: o fundo aproxima, a pessoa fica do mesmo tamanho. Sem recorte: aproximação lenta no ponto."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    forca = clamp(float(ef.get("forca", 1.0)), 0.3, 2.0)

    def f(q, t):
        if t < t0 or t > t0 + dur:
            return q
        u = ease_in_out(clamp((t - t0) / dur))
        a = _envelope(t, t0, dur, 0.15, 0.5)
        h, w = q.shape[:2]
        fundo = _janela(q, w / 2, h * 0.48, 1 + 0.22 * forca * u * a, 0.0).astype(np.float32)
        m = _mascara(q)
        if m is None:
            return fundo.astype(np.uint8)
        return (fundo * (1 - m) + q.astype(np.float32) * m).astype(np.uint8)
    return f


def foco_lente(ef, combo, W, H, fps):
    """Desfoque de lente: nítido no ponto (ou na pessoa, com recorte), fundo desfocado como lente clara."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    px, py = ef.get("ponto", [0.5, 0.42])
    raio = float(ef.get("raio", 0.38))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - px * W) / (W * raio)) ** 2 + ((yy - py * H) / (H * raio * 0.75)) ** 2)
    elipse = np.clip((d - 0.7) / 0.6, 0, 1)[..., None]

    def f(q, t):
        if t < t0 or t > t0 + dur:
            return q
        p = _envelope(t, t0, dur, 0.9, 0.7)
        h, w = q.shape[:2]
        borr = np.asarray(Image.fromarray(q).resize((w // 3, h // 3), Image.BILINEAR)
                          .filter(ImageFilter.GaussianBlur(5)).resize((w, h), Image.BICUBIC), np.float32)
        m = _mascara(q)
        a = (1 - m) if m is not None else (elipse if elipse.shape[:2] == (h, w) else 1.0)
        a = a * p
        return (q.astype(np.float32) * (1 - a) + borr * a).astype(np.uint8)
    return f


# ---------------------------------------------------------------- movimento de câmera "difícil"

def chicote(ef, combo, W, H, fps):
    """Whip pan: a imagem corre para o lado com borrão de movimento e volta; no meio, o corte some."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 0.45))
    lado = -1 if ef.get("direcao") == "esquerda" else 1

    def f(q, t):
        if t < t0 or t > t0 + dur:
            return q
        u = (t - t0) / dur
        forca = math.sin(u * math.pi)                          # 0 -> 1 -> 0
        h, w = q.shape[:2]
        desloc = int(lado * w * 0.35 * (ease_in_out(u) - 0.5) * 2 * forca)
        out = np.roll(q, desloc, axis=1).astype(np.float32)
        n = max(1, int(w * 0.09 * forca))                      # borrão de movimento horizontal
        if n > 1:
            pequeno = Image.fromarray(out.astype(np.uint8)).resize((max(1, w // n), h), Image.BILINEAR)
            out = np.asarray(pequeno.resize((w, h), Image.BILINEAR), np.float32)
        return np.clip(out * (1 + 0.08 * forca), 0, 255).astype(np.uint8)
    return f


def congelar(ef, combo, W, H, fps):
    """Congela o quadro e aproxima devagar, com moldura dourada fina e leve dessaturação: pausa para o texto."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 1.8))
    zoom = float(ef.get("zoom", 1.12))
    px, py = ef.get("ponto", [0.5, 0.45])
    guardado = {}

    def f(q, t):
        if t < t0 or t > t0 + dur:
            guardado.clear() if t > t0 + dur else None
            return q
        if "q" not in guardado:
            guardado["q"] = q.copy()
        u = ease_in_out(clamp((t - t0) / dur))
        a = _envelope(t, t0, dur, 0.12, 0.25)
        h, w = q.shape[:2]
        z = _janela(guardado["q"], w * (0.5 + (px - 0.5) * 0.4 * u), h * (0.5 + (py - 0.5) * 0.4 * u),
                    1 + (zoom - 1) * u, 0.0).astype(np.float32)
        cinza = z.mean(axis=2, keepdims=True)
        z = z * (1 - 0.35 * a) + cinza * 0.35 * a
        img = Image.fromarray(np.clip(z, 0, 255).astype(np.uint8))
        m = int(w * 0.035)
        ImageDraw.Draw(img, "RGBA").rectangle((m, m, w - m, h - m), outline=cor("dourado") + (int(200 * a),),
                                              width=max(2, w // 360))
        return np.asarray(img)
    return f


def luz_dourada(ef, combo, W, H, fps):
    """Feixe de luz dourada (light leak) que atravessa a cena na diagonal, somando luz de forma suave."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 1.6))
    forca = clamp(float(ef.get("forca", 1.0)), 0.3, 1.6)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    diag = (xx / W * 0.8 + yy / H * 0.5) / 1.3
    dourado = np.array(cor("dourado_destaque"), np.float32)

    def f(q, t):
        if t < t0 or t > t0 + dur:
            return q
        u = clamp((t - t0) / dur)
        centro = -0.3 + 1.6 * ease_in_out(u)
        feixe = np.exp(-((diag - centro) / 0.16) ** 2)[..., None] * math.sin(u * math.pi) * 0.42 * forca
        if feixe.shape[:2] != q.shape[:2]:
            return q
        out = q.astype(np.float32)
        out = out + (255 - out) * feixe * (dourado / 255)          # tela (screen): clareia sem estourar
        return np.clip(out, 0, 255).astype(np.uint8)
    return f


EFEITOS = {"camera_elegante": camera_elegante, "cartao_3d": cartao_3d, "parallax": parallax,
           "dolly_zoom": dolly_zoom, "chicote": chicote, "congelar": congelar, "foco_lente": foco_lente,
           "luz_dourada": luz_dourada}

NOMES = {"camera_elegante": "Câmera elegante (perspectiva + zoom)", "cartao_3d": "Cartão 3D (inclina ou gira)",
         "parallax": "Parallax 2.5D (fundo anda, pessoa fica)", "dolly_zoom": "Efeito vertigem (dolly zoom)",
         "chicote": "Transição chicote (whip pan)", "congelar": "Congelar e aproximar",
         "foco_lente": "Desfoque de lente (modo retrato)", "luz_dourada": "Luz dourada (light leak)"}

CAMPOS = {
    "camera_elegante": [("direcao", "escolha:direita|esquerda|frente|cima", "Direção"),
                        ("intensidade", "numero", "Intensidade (0.5 a 1.5)")],
    "cartao_3d": [("modo", "escolha:inclinar|girar", "Movimento"), ("angulo", "numero", "Ângulo (10 a 30)")],
    "parallax": [("direcao", "escolha:direita|esquerda", "Direção")],
    "dolly_zoom": [("forca", "numero", "Força (0.5 a 1.5)")],
    "chicote": [("direcao", "escolha:direita|esquerda", "Direção")],
    "congelar": [("ponto", "ponto", "Para onde aproxima (clique no vídeo)"), ("zoom", "numero", "Zoom (1.05 a 1.25)")],
    "foco_lente": [("ponto", "ponto", "O que fica nítido (clique no vídeo)")],
    "luz_dourada": [("forca", "numero", "Força (0.5 a 1.5)")],
}

DURACAO = {"camera_elegante": 5.0, "cartao_3d": 3.0, "parallax": 4.0, "dolly_zoom": 2.5, "chicote": 0.45,
           "congelar": 1.8, "foco_lente": 3.0, "luz_dourada": 1.6}

EXEMPLOS = {"camera_elegante": {"direcao": "direita"}, "cartao_3d": {"modo": "inclinar"},
            "parallax": {}, "dolly_zoom": {}, "chicote": {}, "congelar": {"zoom": 1.15},
            "foco_lente": {"ponto": [0.5, 0.42]}, "luz_dourada": {}}

# instante mais vistoso de cada um (miniatura no painel), em segundos depois do início
MOMENTO_AMOSTRA = {"camera_elegante": 4.0, "cartao_3d": 0.9, "parallax": 3.0, "dolly_zoom": 2.0, "chicote": 0.22,
                   "congelar": 1.2, "foco_lente": 1.5, "luz_dourada": 0.8}
