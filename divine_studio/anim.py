"""Curvas de animação suaves (padrão Divine: nada brusco)."""
from __future__ import annotations


def clamp(x: float, a: float = 0.0, b: float = 1.0) -> float:
    return a if x < a else b if x > b else x


def ease_in_out(t: float) -> float:
    """Cúbica in-out."""
    t = clamp(t)
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out(t: float) -> float:
    t = clamp(t)
    return 1 - (1 - t) ** 3


def envelope(t: float, t0: float, t1: float, entrada: float, saida: float):
    """Opacidade (0..1) e progresso de entrada (0..1) de um elemento visível entre t0 e t1."""
    if t < t0 or t > t1:
        return 0.0, 0.0
    pin = ease_out((t - t0) / entrada) if entrada > 0 else 1.0
    pout = ease_in_out((t1 - t) / saida) if saida > 0 else 1.0
    return min(pin, pout), pin
