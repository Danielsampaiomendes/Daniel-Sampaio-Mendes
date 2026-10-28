"""Peças comuns aos templates com uma pessoa em destaque (Daniel, George): cartão de nome no início e no fim."""
from __future__ import annotations

from ..cartoes import cartao_nome
from ..compositor import Camada
from ..config import load


def cartao(plano, cfg: dict, W: int, y_px: float, cor_placa: str) -> None:
    escala = W / 1080.0
    marca = load("marca")["cores"]
    img = cartao_nome(cfg["pessoa"], escala, marca.get(cor_placa, cor_placa))
    x = (W - img.width) // 2
    y = int(y_px * escala)
    a, b = cfg.get("cartao", [3.5, 9.0])
    a = max(a, plano.hook_fim + 0.2)
    if b - a > 1.5:
        plano.camadas.append(Camada(img, x, y, a, min(b, plano.inicio_fechamento), entrada=0.9, saida=0.6,
                                    deslize=18, nome="cartao_nome"))
    fim_s = float(cfg.get("cartao_fim_s", 3.0))
    c0 = plano.inicio_fechamento - fim_s
    if c0 > b + 1.0:
        plano.camadas.append(Camada(img, x, y, c0, plano.inicio_fechamento, entrada=0.9, saida=0.5, deslize=18,
                                    nome="cartao_nome_fim"))
