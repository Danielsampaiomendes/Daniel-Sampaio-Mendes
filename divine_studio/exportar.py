"""Exportação final: x264 (slow, tune film, aq-mode=3), loudnorm -16 LUFS e teto de tamanho em 2 passes."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from .config import load
from .ingest import probe, rodar


def _audio_args(exp: dict) -> list:
    a = exp["audio"]
    return ["-af", f"loudnorm=I={a['lufs_alvo']}:TP=-1.5:LRA=11", "-c:a", a["codec"], "-b:a", a["bitrate"],
            "-ar", str(a["taxa"])]


def exportar(master: Path, saida: Path, alta_qualidade: bool = False, limite_mb: float | None = None,
             rapido: bool = False) -> dict:
    """rapido=True: prévia (preset veryfast/fast), mesma aparência, arquivo um pouco maior."""
    exp = load("exportacao")
    v = dict(exp["video"])
    if rapido:
        v["preset"] = "veryfast"
    limite = float(limite_mb if limite_mb is not None else exp.get("limite_mb", 0) or 0)
    saida.parent.mkdir(parents=True, exist_ok=True)

    if alta_qualidade and exp["alta_qualidade"].get("final_hevc"):
        preset_hevc = "fast" if rapido else exp["alta_qualidade"].get("preset_hevc", "medium")
        codec = ["-c:v", "libx265", "-tag:v", "hvc1", "-preset", preset_hevc, "-x265-params", "log-level=error"]
        q = ["-crf", "20"]
    else:
        codec = ["-c:v", v["codec"], "-preset", v["preset"], "-tune", v["tune"], "-x264-params", v["x264_params"]]
        q = ["-crf", str(v["crf"])]
    comum = ["-pix_fmt", v["pix_fmt"], "-movflags", "+faststart"]
    rodar(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(master), *codec, *q, *comum,
           *_audio_args(exp), str(saida)])

    mb = saida.stat().st_size / 1e6
    dois_passes = False
    if limite and mb > limite:
        dur = probe(saida)["duracao"] or 1
        kbps = int((limite * 0.94 * 8000) / dur - 192)
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "passe")
            if "libx265" in codec:
                p1 = [*codec[:-2], "-x265-params", f"pass=1:stats={log}.log:log-level=error"]
                p2 = [*codec[:-2], "-x265-params", f"pass=2:stats={log}.log:log-level=error"]
            else:
                p1 = [*codec, "-pass", "1", "-passlogfile", log]
                p2 = [*codec, "-pass", "2", "-passlogfile", log]
            rodar(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(master), *p1, "-b:v", f"{kbps}k",
                   *comum, "-an", "-f", "mp4", os.devnull])
            rodar(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(master), *p2, "-b:v", f"{kbps}k",
                   *comum, *_audio_args(exp), str(saida)])
        mb = saida.stat().st_size / 1e6
        dois_passes = True
    return {"arquivo": str(saida), "mb": round(mb, 1), "dois_passes": dois_passes}


def quadros(video: Path, saida_jpg: Path, n: int = 6, largura: int = 240) -> Path:
    """Folha de contato com n quadros espaçados (para conferir rápido)."""
    d = probe(video)["duracao"] or 1
    tempos = [d * (k + 0.5) / n for k in range(n)]
    with tempfile.TemporaryDirectory() as tmp:
        arqs = []
        for k, t in enumerate(tempos):
            a = Path(tmp) / f"q{k}.png"
            subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                            "-vf", f"scale={largura}:-2", str(a)], check=True)
            arqs.append(a)
        from PIL import Image
        ims = [Image.open(a).convert("RGB") for a in arqs]
        W = sum(i.width for i in ims) + 6 * (len(ims) - 1)
        folha = Image.new("RGB", (W, max(i.height for i in ims)), (255, 255, 255))
        x = 0
        for im in ims:
            folha.paste(im, (x, 0))
            x += im.width + 6
        folha.save(saida_jpg, quality=80)
    return saida_jpg
