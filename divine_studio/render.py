"""Render: decodifica a base, compõe as camadas quadro a quadro e grava o master."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import numpy as np

from .anim import clamp, ease_in_out
from .compositor import desfocado_escuro
from .config import cor, load


def renderizar(base: Path, plano, W: int, H: int, fps: int, mix_wav: Path, saida: Path,
               duracao_base: float) -> float:
    pref = load("preferencias")
    total = plano.duracao_total
    n = int(round(total * fps))
    nbase = int(duracao_base * fps)
    ini_f = plano.inicio_fechamento
    escurecer = float(pref["fechamento"]["escurecer_final_s"])
    barra_h = int(pref["progresso"]["altura_px"])
    barra_cor = np.array(cor(pref["progresso"]["cor"]), dtype=np.uint8)

    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(base), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(fps), "-i", "-", "-i", str(mix_wav), "-map", "0:v", "-map", "1:a",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-pix_fmt", "yuv420p",
                            "-c:a", "pcm_s16le", "-shortest", str(saida)], stdin=subprocess.PIPE)
    tam = W * H * 3
    ultimo = None
    fundo_fech = None
    t_ini = time.time()
    for i in range(n):
        t = i / fps
        quadro = None
        if i < nbase:
            buf = dec.stdout.read(tam)
            if len(buf) == tam:
                quadro = np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy()
                ultimo = quadro
        if quadro is None:
            quadro = ultimo.copy() if ultimo is not None else np.zeros((H, W, 3), np.uint8)

        # transição para o fundo desfocado do fechamento
        if t >= ini_f:
            a = ease_in_out(clamp((t - ini_f) / 0.6))
            if i < nbase or fundo_fech is None:
                fundo = desfocado_escuro(quadro)
                if i >= nbase - 1:
                    fundo_fech = fundo
            else:
                fundo = fundo_fech
            quadro = (quadro.astype(np.float32) * (1 - a) + fundo.astype(np.float32) * a).astype(np.uint8)

        for c in plano.camadas:
            c.pintar(quadro, t)
        if t >= ini_f:
            for c in plano.camadas_fechamento:
                c.pintar(quadro, t)

        # barra de progresso dourada
        larg = int(W * min(1.0, (t + 1 / fps) / total))
        quadro[0:barra_h, 0:larg] = barra_cor

        # escurece no fim para o loop
        if t > total - escurecer:
            k = 1 - ease_in_out(clamp((t - (total - escurecer)) / escurecer))
            quadro = (quadro.astype(np.float32) * k).astype(np.uint8)

        enc.stdin.write(quadro.tobytes())
        if i and i % (fps * 5) == 0:
            print(f"    {t:5.1f}s / {total:.1f}s", flush=True)
    enc.stdin.close()
    enc.wait()
    dec.stdout.close()
    dec.wait()
    if enc.returncode != 0:
        raise SystemExit("Falha ao gravar o master do vídeo")
    return time.time() - t_ini
