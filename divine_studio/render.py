"""Render: decodifica a base, compõe as camadas quadro a quadro e grava o master."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import numpy as np

from .anim import clamp, ease_in_out
from .compositor import desfocado_escuro
from .config import cor, load


class _Leitor:
    """Decodifica um vídeo quadro a quadro (segura o último quadro quando acaba)."""

    def __init__(self, arquivo: Path, w: int, h: int):
        self.w, self.h = w, h
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(arquivo), "-f", "rawvideo", "-pix_fmt", "rgb24",
                                   "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.ultimo = None

    def ler(self):
        buf = self.p.stdout.read(self.w * self.h * 3) if self.p else b""
        if len(buf) == self.w * self.h * 3:
            self.ultimo = np.frombuffer(buf, np.uint8).reshape(self.h, self.w, 3).copy()
            return self.ultimo
        return None

    def fechar(self):
        if self.p:
            self.p.kill()
            self.p.stdout.close()
            self.p.wait()
            self.p = None


def renderizar(base: Path, plano, W: int, H: int, fps: int, mix_wav: Path, saida: Path,
               duracao_base: float, base_tamanho: tuple | None = None, extras: list | None = None) -> float:
    """extras: [(arquivo, w, h)] decodificados junto (React); a moldura do plano compõe o quadro final."""
    pref = load("preferencias")
    total = plano.duracao_total
    n = int(round(total * fps))
    nbase = int(duracao_base * fps)
    ini_f = plano.inicio_fechamento
    escurecer = float(pref["fechamento"]["escurecer_final_s"])
    barra_h = int(pref["progresso"]["altura_px"])
    barra_cor = np.array(cor(pref["progresso"]["cor"]), dtype=np.uint8)

    bw, bh = base_tamanho or (W, H)
    dec = _Leitor(base, bw, bh)
    outros = [_Leitor(a, w, h) for a, w, h in (extras or [])]
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(fps), "-i", "-", "-i", str(mix_wav), "-map", "0:v", "-map", "1:a",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-pix_fmt", "yuv420p",
                            "-c:a", "pcm_s16le", "-shortest", str(saida)], stdin=subprocess.PIPE)
    fundo_fech = None
    t_ini = time.time()
    for i in range(n):
        t = i / fps
        quadro = dec.ler() if i < nbase else None
        if quadro is None:
            quadro = dec.ultimo.copy() if dec.ultimo is not None else np.zeros((bh, bw, 3), np.uint8)
        ext = []
        for o in outros:
            q = o.ler()
            ext.append(q if q is not None else (o.ultimo if o.ultimo is not None else np.zeros((o.h, o.w, 3), np.uint8)))
        for ef in plano.efeitos_quadro:
            quadro = ef(quadro, t)
        if plano.moldura is not None:
            quadro = plano.moldura(quadro, ext, t)

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
        if plano.barra_progresso:
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
    for d in [dec] + outros:
        d.fechar()
    if enc.returncode != 0:
        raise SystemExit("Falha ao gravar o master do vídeo")
    return time.time() - t_ini
