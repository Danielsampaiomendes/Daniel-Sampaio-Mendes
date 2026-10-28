"""Recorte da pessoa (máscara 0..1) para texto atrás da cabeça e capa de revista.

Usa MediaPipe (pip3 install mediapipe) ou rembg (pip3 install rembg), o que estiver instalado.
Sem nenhum dos dois, devolve None e o efeito sai com o texto na frente (com aviso).
"""
from __future__ import annotations

import numpy as np

_motor = None
_avisou = False


def _carregar():
    global _motor
    if _motor is not None:
        return _motor
    try:
        import mediapipe as mp
        seg = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=1)
        _motor = ("mediapipe", seg)
    except Exception:
        try:
            from rembg import new_session, remove
            _motor = ("rembg", (new_session("u2net_human_seg"), remove))
        except Exception:
            _motor = ("nenhum", None)
    return _motor


def disponivel() -> bool:
    return _carregar()[0] != "nenhum"


def mascara(quadro: np.ndarray) -> np.ndarray | None:
    """quadro RGB uint8 (H, W, 3) -> máscara float32 (H, W, 1) com 1 na pessoa."""
    global _avisou
    nome, m = _carregar()
    if nome == "mediapipe":
        r = m.process(quadro)
        if r.segmentation_mask is None:
            return None
        return np.clip((r.segmentation_mask.astype(np.float32) - 0.25) / 0.5, 0, 1)[..., None]
    if nome == "rembg":
        sessao, remove = m
        from PIL import Image
        rgba = np.asarray(remove(Image.fromarray(quadro), session=sessao, only_mask=True), np.float32) / 255
        return rgba[..., None] if rgba.ndim == 2 else rgba[..., :1]
    if not _avisou:
        print("  aviso: recorte da pessoa indisponível (pip3 install mediapipe); texto atrás da pessoa sai na frente")
        _avisou = True
    return None
