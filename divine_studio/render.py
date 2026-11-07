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
    """Decodifica um vídeo quadro a quadro (segura o último quadro quando acaba). fps: reamostra (storyboard)."""

    def __init__(self, arquivo: Path, w: int, h: int, fps: float | None = None):
        self.w, self.h = w, h
        filtro = ["-vf", f"fps={fps}"] if fps else []
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(arquivo), *filtro, "-f", "rawvideo",
                                   "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
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


def _efeitos(plano, quadro, t):
    """Efeitos de quadro na ordem; um efeito com problema sai do plano e o vídeo segue."""
    for k, ef in enumerate(plano.efeitos_quadro):
        if ef is None:
            continue
        try:
            r = ef(quadro, t)
            if r is None or r.shape != quadro.shape:
                raise ValueError(f"quadro de tamanho {None if r is None else r.shape}")
            quadro = r
        except Exception as e:                  # um efeito com problema não derruba a prévia inteira
            nome = getattr(ef, "__qualname__", "efeito").split(".")[0]
            print(f"  aviso: efeito {nome} falhou em {t:.1f}s ({type(e).__name__}: {e}); seguindo sem ele", flush=True)
            plano.efeitos_quadro[k] = None
    return quadro if quadro.flags.writeable else quadro.copy()


def _compor(quadro, ext, plano, t, W, fps, fundo_de):
    """Do quadro com efeitos ao quadro final: moldura, fundo do fechamento, camadas, barra e escurecer do fim.
    fundo_de(quadro) devolve o fundo desfocado do fechamento. É a mesma conta no render e no storyboard."""
    pref = load("preferencias")
    total = plano.duracao_total
    ini_f = plano.inicio_fechamento
    if plano.moldura is not None:
        quadro = plano.moldura(quadro, ext, t)
    if t >= ini_f:
        a = ease_in_out(clamp((t - ini_f) / 0.6))
        quadro = (quadro.astype(np.float32) * (1 - a) + fundo_de(quadro).astype(np.float32) * a).astype(np.uint8)
    for c in plano.camadas:
        c.pintar(quadro, t)
    if t >= ini_f:
        for c in plano.camadas_fechamento:
            c.pintar(quadro, t)
    if plano.barra_progresso:
        larg = int(W * min(1.0, (t + 1 / fps) / total))
        quadro[0:int(pref["progresso"]["altura_px"]), 0:larg] = np.array(cor(pref["progresso"]["cor"]), dtype=np.uint8)
    escurecer = float(pref["fechamento"]["escurecer_final_s"])
    if t > total - escurecer:
        k = 1 - ease_in_out(clamp((t - (total - escurecer)) / escurecer))
        quadro = (quadro.astype(np.float32) * k).astype(np.uint8)
    return quadro


def renderizar(base: Path, plano, W: int, H: int, fps: int, mix_wav: Path, saida: Path,
               duracao_base: float, base_tamanho: tuple | None = None, extras: list | None = None) -> float:
    """extras: [(arquivo, w, h)] decodificados junto (React); a moldura do plano compõe o quadro final."""
    total = plano.duracao_total
    n = int(round(total * fps))
    nbase = int(duracao_base * fps)
    bw, bh = base_tamanho or (W, H)
    dec = _Leitor(base, bw, bh)
    outros = [_Leitor(a, w, h) for a, w, h in (extras or [])]
    from .ingest import com_threads
    enc = subprocess.Popen(com_threads(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(fps), "-i", "-", "-i", str(mix_wav), "-map", "0:v", "-map", "1:a",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-pix_fmt", "yuv420p",
                            "-c:a", "pcm_s16le", "-shortest", str(saida)]), stdin=subprocess.PIPE)
    fech = {"fundo": None}
    t_ini = time.time()
    for i in range(n):
        t = i / fps
        quadro = _ler(dec, bw, bh) if i < nbase else None
        if quadro is None:
            quadro = dec.ultimo.copy() if dec.ultimo is not None else np.zeros((bh, bw, 3), np.uint8)
        ext = [_ler(o, o.w, o.h, segurar=True) for o in outros]
        quadro = _efeitos(plano, quadro, t)

        def fundo_de(q, i=i):                    # depois da base, o fundo fica parado no último quadro
            if i < nbase or fech["fundo"] is None:
                f = desfocado_escuro(q)
                if i >= nbase - 1:
                    fech["fundo"] = f
                return f
            return fech["fundo"]
        quadro = _compor(quadro, ext, plano, t, W, fps, fundo_de)
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


def _ler(leitor, w, h, segurar=False):
    q = leitor.ler()
    if q is None and segurar:
        return leitor.ultimo if leitor.ultimo is not None else np.zeros((h, w, 3), np.uint8)
    return q


def quadros_em(base: Path, plano, tempos: list, W: int, H: int, duracao_base: float,
               base_tamanho: tuple | None = None, extras: list | None = None, amostra: float = 10.0,
               fps: int | None = None) -> dict:
    """A edição final em alguns instantes, sem renderizar o vídeo (storyboard).

    Lê a base no fps do vídeo e passa pelos efeitos de quadro na ordem, a `amostra` quadros por segundo (efeitos
    que guardam estado, como o congelar, veem a mesma sequência do render); compõe as camadas só nos quadros
    pedidos, com a mesma função do render. Devolve {t pedido: quadro RGB}."""
    fps = int(fps or load("exportacao")["fps"])
    alvos = {}
    for t in tempos:
        alvos.setdefault(int(round(float(t) * fps)), []).append(round(float(t), 3))
    if not alvos:
        return {}
    ultimo = max(alvos)
    passo = max(1, int(round(fps / float(amostra))))
    bw, bh = base_tamanho or (W, H)
    dec = _Leitor(base, bw, bh)
    outros = [_Leitor(a, w, h) for a, w, h in (extras or [])]
    nbase = int(duracao_base * fps)
    out = {}
    fundo = {"fim": None}
    try:
        for i in range(ultimo + 1):
            t = i / fps
            quadro = _ler(dec, bw, bh) if i < nbase else None
            if quadro is None:
                quadro = dec.ultimo.copy() if dec.ultimo is not None else np.zeros((bh, bw, 3), np.uint8)
            ext = [_ler(o, o.w, o.h, segurar=True) for o in outros]
            if i not in alvos:
                if i % passo == 0:                         # mantém os efeitos com estado na mesma sequência
                    _efeitos(plano, quadro, t)
                continue
            q = _efeitos(plano, quadro, t)

            def fundo_de(x, i=i):
                if i < nbase or fundo["fim"] is None:
                    f = desfocado_escuro(x)
                    if i >= nbase - 1:
                        fundo["fim"] = f
                    return f
                return fundo["fim"]
            final = _compor(q, [e.copy() for e in ext], plano, t, W, fps, fundo_de)
            for tk in alvos[i]:
                out[tk] = final
    finally:
        for d in [dec] + outros:
            d.fechar()
    return out
