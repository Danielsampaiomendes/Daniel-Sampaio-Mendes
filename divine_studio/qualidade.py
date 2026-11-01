"""Qualidade máxima do bruto antes da edição: estabilizar, tirar ruído, aumentar a resolução (upscale) e nitidez.

No projeto.yaml (vale para todos os clipes) ou num clipe:
  qualidade: {estabilizar: true, denoise: forte, upscale: auto, nitidez: true, camera_lenta_suave: true}
  qualidade: maxima        # atalho: tudo ligado

- estabilizar: vid.stab em 2 passes (vidstabdetect + vidstabtransform), o melhor do FFmpeg; sem ele, deshake.
- upscale: 'auto' sobe para a resolução da peça quando o bruto é menor. Com o Real-ESRGAN instalado
  (realesrgan-ncnn-vulkan no PATH ou em config/exportacao.yaml > qualidade > realesrgan) usa IA quadro a quadro;
  sem ele, Lanczos + nitidez (já ótimo para celular).
- denoise: leve (hqdn3d) | forte (nlmeans, mais lento, ótimo para cena escura).
- camera_lenta_suave: em clipes com velocidade < 1, cria quadros intermediários (minterpolate), sem engasgar.

O resultado fica em cache em trabalho/qualidade/ (só refaz se o bruto ou as opções mudarem).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from .config import load

MAXIMA = {"estabilizar": True, "denoise": "leve", "upscale": "auto", "nitidez": True, "camera_lenta_suave": True}


def _cfg() -> dict:
    return load("exportacao").get("qualidade", {})


def opcoes(projeto: dict, clipe: dict) -> dict:
    """Junta as opções do projeto e do clipe ('maxima' liga tudo)."""
    out = {}
    for fonte in (projeto.get("qualidade"), clipe.get("qualidade")):
        if fonte in ("maxima", "máxima", True):
            out.update(MAXIMA)
        elif isinstance(fonte, dict):
            out.update(fonte)
    return {k: v for k, v in out.items() if v not in (None, False, "nao", "não")}


@lru_cache(maxsize=1)
def tem_vidstab() -> bool:
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, timeout=20)
        return "vidstabdetect" in r.stdout
    except (OSError, subprocess.SubprocessError):
        return False


def realesrgan() -> str | None:
    cand = _cfg().get("realesrgan") or "realesrgan-ncnn-vulkan"
    return shutil.which(str(Path(cand).expanduser())) or (str(Path(cand).expanduser()) if Path(cand).expanduser().is_file() else None)


def _rodar(cmd: list) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"Falha ao melhorar a qualidade do bruto:\n{r.stderr[-800:]}")


def preparar(arquivo: Path, ini: float, fim: float, ops: dict, alvo: tuple, cache: Path) -> Path:
    """Trecho [ini, fim] do bruto melhorado (estabilizado, sem ruído, em alta resolução). Devolve o arquivo novo."""
    st = arquivo.stat()
    chave = hashlib.sha1(json.dumps([str(arquivo), st.st_size, st.st_mtime, ini, fim, ops, alvo, _cfg()],
                                    sort_keys=True, default=str).encode()).hexdigest()[:16]
    cache.mkdir(parents=True, exist_ok=True)
    saida = cache / f"{arquivo.stem}_{chave}.mov"
    if saida.exists():
        return saida
    from .ingest import probe
    p = probe(arquivo)
    print(f"  qualidade: melhorando {arquivo.name} ({', '.join(f'{k}={v}' for k, v in ops.items())})", flush=True)
    tmp = Path(tempfile.mkdtemp(prefix="divine_q_"))
    try:
        filtros = []
        if ops.get("estabilizar"):
            trf = tmp / "movimento.trf"
            if tem_vidstab():
                _rodar(["ffmpeg", "-y", "-v", "error", "-ss", f"{ini:.3f}", "-t", f"{fim - ini:.3f}", "-i", str(arquivo),
                        "-vf", f"vidstabdetect=shakiness=6:accuracy=15:result={trf}", "-f", "null", "-"])
                filtros.append(f"vidstabtransform=input={trf}:smoothing={int(_cfg().get('suavizar', 20))}"
                               ":crop=keep:zoom=0:optzoom=1:interpol=bicubic")
            else:
                filtros.append("deshake=rx=24:ry=24")
        den = ops.get("denoise")
        if den == "forte":
            filtros.append("nlmeans=s=2.2:p=5:r=11")
        elif den:
            filtros.append("hqdn3d=2:2:6:6")
        lado = min(p["largura"], p["altura"])
        quer = min(alvo)
        sobe = ops.get("upscale") and lado < quer * 0.98
        esrgan = realesrgan() if sobe and ops.get("upscale") != "lanczos" else None
        if sobe and not esrgan:
            k = quer / lado
            filtros.append(f"scale=trunc(iw*{k:.4f}/2)*2:trunc(ih*{k:.4f}/2)*2:flags=lanczos")
        if ops.get("nitidez") or (sobe and not esrgan):
            filtros.append("unsharp=5:5:0.55:5:5:0.0")
        base = tmp / "base.mov"
        cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{ini:.3f}", "-t", f"{fim - ini:.3f}", "-i", str(arquivo)]
        if filtros:
            cmd += ["-vf", ",".join(filtros)]
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "12", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le",
                str(base)]
        _rodar(cmd)
        if esrgan:
            _upscale_ia(esrgan, base, saida, tmp, p)
        else:
            shutil.move(str(base), saida)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return saida


def _upscale_ia(binario: str, entrada: Path, saida: Path, tmp: Path, p: dict) -> None:
    """Real-ESRGAN quadro a quadro: extrai PNG, aumenta com IA e remonta com o áudio original."""
    from .ingest import probe
    q, up = tmp / "quadros", tmp / "up"
    q.mkdir()
    up.mkdir()
    fps = probe(entrada).get("fps") or 30
    _rodar(["ffmpeg", "-y", "-v", "error", "-i", str(entrada), str(q / "%06d.png")])
    modelo = _cfg().get("modelo_realesrgan", "realesr-animevideov3")
    escala = str(int(_cfg().get("escala_realesrgan", 2)))
    _rodar([binario, "-i", str(q), "-o", str(up), "-n", modelo, "-s", escala, "-f", "png"])
    _rodar(["ffmpeg", "-y", "-v", "error", "-framerate", str(fps), "-i", str(up / "%06d.png"), "-i", str(entrada),
            "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-preset", "medium", "-crf", "13", "-pix_fmt", "yuv420p",
            "-c:a", "copy", "-shortest", str(saida)])


def filtro_camera_lenta(fps: int) -> str:
    """Quadros intermediários por movimento (câmera lenta sem engasgo)."""
    return f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"


def diagnostico() -> dict:
    """O que está disponível nesta máquina (para o painel e o comando 'verificar')."""
    return {"vidstab": tem_vidstab(), "realesrgan": bool(realesrgan()),
            "dica": "" if realesrgan() else "Upscale com IA: baixe o realesrgan-ncnn-vulkan (GitHub xinntao/Real-ESRGAN) "
                                            "e coloque no PATH. Sem ele, o app usa Lanczos + nitidez."}
