"""Camadas animadas compostas quadro a quadro sobre o vídeo (numpy, só na área de cada camada)."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

from .anim import envelope


class Camada:
    """Imagem RGBA que entra com fade + deslize lento e sai com fade."""

    def __init__(self, img: Image.Image, x: int, y: int, t0: float, t1: float,
                 entrada: float = 0.9, saida: float = 0.6, deslize: float = 34.0, nome: str = "", texto: str = ""):
        a = np.asarray(img.convert("RGBA"), dtype=np.float32) / 255.0
        self.alpha = a[..., 3:4]
        self.rgb_p = a[..., :3] * self.alpha * 255.0
        self.h, self.w = self.alpha.shape[:2]
        self.x, self.y = int(x), int(y)
        self.t0, self.t1 = t0, t1
        self.entrada, self.saida, self.deslize = entrada, saida, deslize
        self.nome = nome
        self.texto = texto      # texto mostrado (para o tempo de leitura na nota viral)

    def pintar(self, frame: np.ndarray, t: float) -> None:
        op, pin = envelope(t, self.t0, self.t1, self.entrada, self.saida)
        if op <= 0.003:
            return
        dy = int(round(self.deslize * (1 - pin)))
        H, W = frame.shape[:2]
        x0, y0 = self.x, self.y + dy
        x1, y1 = x0 + self.w, y0 + self.h
        cx0, cy0, cx1, cy1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
        if cx0 >= cx1 or cy0 >= cy1:
            return
        sx, sy = cx0 - x0, cy0 - y0
        a = self.alpha[sy:sy + cy1 - cy0, sx:sx + cx1 - cx0] * op
        c = self.rgb_p[sy:sy + cy1 - cy0, sx:sx + cx1 - cx0] * op
        reg = frame[cy0:cy1, cx0:cx1].astype(np.float32)
        frame[cy0:cy1, cx0:cx1] = (reg * (1 - a) + c).astype(np.uint8)


def gradiente_vertical(W: int, H: int, y0: int, y1: int, opacidade: float, de_cima: bool = True) -> Image.Image:
    """Escurecimento suave para leitura (topo ou base)."""
    h = max(1, y1 - y0)
    rampa = np.linspace(1, 0, h) if de_cima else np.linspace(0, 1, h)
    rampa = (rampa ** 1.6 * opacidade * 255).astype(np.uint8)
    a = np.repeat(rampa[:, None], W, axis=1)
    img = Image.new("RGBA", (W, h), (0, 0, 0, 0))
    img.putalpha(Image.fromarray(a, "L"))
    return img


def desfocado_escuro(frame: np.ndarray, escurecer: float = 0.45, raio: int = 6) -> np.ndarray:
    """Fundo do fechamento: quadro desfocado e escurecido (reduz, desfoca e amplia: rápido)."""
    H, W = frame.shape[:2]
    im = Image.fromarray(frame).resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(raio))
    im = im.resize((W, H), Image.BICUBIC)
    return (np.asarray(im, dtype=np.float32) * escurecer).astype(np.uint8)
