"""Ingestão: lê os brutos, corta, converte HDR para SDR, recorta no formato e monta a base do vídeo.

Cada clipe do projeto.yaml:
  arquivo: bruto/IMG_1234.MOV   (relativo à pasta do projeto ou à raiz do repositório)
  inicio: 2.0                    (s, opcional)
  fim: 8.5                       (s, opcional)
  velocidade: 0.72               (opcional; < 1 = câmera lenta com mescla de quadros)
  foco: [0.5, 0.35]              (âncora do recorte x, y de 0 a 1; padrão centro)
  zoom: 1.0                      (aproximação extra; 1 = só preencher o quadro)
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .config import ROOT, load

HDR_TRANSFERS = {"arib-std-b67", "smpte2084"}


def rodar(cmd: list, silencioso: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("Erro no FFmpeg:\n" + " ".join(map(str, cmd))[:600] + "\n" + r.stderr[-2500:])
    return r


def probe(arquivo: Path) -> dict:
    r = rodar(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(arquivo)])
    d = json.loads(r.stdout)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    if v is None:
        raise SystemExit(f"{arquivo} não tem trilha de vídeo")
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    rot = int(v.get("tags", {}).get("rotate", rot))
    if abs(rot) % 180 == 90:
        w, h = h, w
    num, den = (v.get("avg_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    dur = float(v.get("duration") or d["format"].get("duration") or 0)
    return {
        "arquivo": str(arquivo),
        "largura": w,
        "altura": h,
        "fps": round(fps, 3),
        "duracao": round(dur, 3),
        "hdr": v.get("color_transfer") in HDR_TRANSFERS,
        "transferencia": v.get("color_transfer"),
        "audio": a is not None,
        "codec": v.get("codec_name"),
    }


def resolver(projeto: dict, caminho: str) -> Path:
    for base in (projeto["_pasta"], ROOT):
        p = (base / caminho).expanduser()
        if p.exists():
            return p
    raise SystemExit(f"Arquivo do clipe não encontrado: {caminho}")


def _atempo(vel: float) -> str:
    partes, v = [], vel
    while v < 0.5:
        partes.append("atempo=0.5")
        v /= 0.5
    while v > 2.0:
        partes.append("atempo=2.0")
        v /= 2.0
    partes.append(f"atempo={v:.4f}")
    return ",".join(partes)


def construir_base(projeto: dict, W: int, H: int, saida: Path, forcar_hq: bool | None = None) -> dict:
    """Gera trabalho/base.mp4 (vídeo + áudio original) e devolve metadados."""
    exp = load("exportacao")
    pref = load("preferencias")
    fps = exp["fps"]
    hqcfg = exp["alta_qualidade"]
    dissolve = float(projeto.get("dissolve", pref["animacao"]["dissolve_entre_clipes_s"]))
    clipes = projeto.get("clipes") or []
    if not clipes:
        raise SystemExit("O projeto não tem clipes (lista 'clipes' no projeto.yaml).")

    entradas, filtros, info_clipes = [], [], []
    hq_geral = False
    for i, c in enumerate(clipes):
        arq = resolver(projeto, c["arquivo"])
        p = probe(arq)
        ini = float(c.get("inicio", 0))
        fim = float(c.get("fim", p["duracao"]))
        vel = float(c.get("velocidade", 1.0))
        dur_out = (fim - ini) / vel
        fx, fy = (c.get("foco") or [0.5, 0.5])
        z = float(c.get("zoom", 1.0))
        hq = forcar_hq if forcar_hq is not None else (min(p["largura"], p["altura"]) < hqcfg["altura_minima"] or c.get("alta_qualidade", False))
        hq_geral = hq_geral or hq
        entradas += ["-ss", f"{ini:.3f}", "-t", f"{fim - ini:.3f}", "-i", str(arq)]

        v = []
        if p["hdr"]:
            v.append("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
                     "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
        if hq:
            v.append(hqcfg["denoise"])
        v.append(f"setpts=(PTS-STARTPTS)/{vel}")
        if vel < 1.0:
            v.append(f"framerate=fps={fps}")
        v.append(f"scale={int(W * z)}:{int(H * z)}:force_original_aspect_ratio=increase:flags=lanczos")
        v.append(f"crop={W}:{H}:(iw-{W})*{fx}:(ih-{H})*{fy}")
        if hq:
            v.append(hqcfg["nitidez"])
        v.append(f"fps={fps},format=yuv420p,setsar=1")
        filtros.append(f"[{i}:v]{','.join(v)}[v{i}]")

        if p["audio"] and not c.get("mudo", False):
            filtros.append(f"[{i}:a]asetpts=PTS-STARTPTS,{_atempo(vel)},aresample=48000,"
                           f"aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]")
        else:
            filtros.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{dur_out:.3f}[a{i}]")
        info_clipes.append({"arquivo": c["arquivo"], "duracao": round(dur_out, 3), "hdr": p["hdr"], "hq": hq,
                            "resolucao": f"{p['largura']}x{p['altura']}"})

    n = len(clipes)
    if n == 1:
        filtros.append("[v0]null[vc];[a0]anull[ac]")
        total = info_clipes[0]["duracao"]
    elif dissolve > 0:
        L = info_clipes[0]["duracao"]
        pv, pa = "v0", "a0"
        for k in range(1, n):
            off = L - dissolve
            filtros.append(f"[{pv}][v{k}]xfade=transition=fade:duration={dissolve}:offset={off:.3f}[vx{k}]")
            filtros.append(f"[{pa}][a{k}]acrossfade=d={dissolve}[ax{k}]")
            pv, pa = f"vx{k}", f"ax{k}"
            L = L + info_clipes[k]["duracao"] - dissolve
        filtros.append(f"[{pv}]null[vc];[{pa}]anull[ac]")
        total = L
    else:
        filtros.append("".join(f"[v{k}][a{k}]" for k in range(n)) + f"concat=n={n}:v=1:a=1[vc][ac]")
        total = sum(c["duracao"] for c in info_clipes)

    zr = pref["animacao"]["zoom_respiro"]
    amp = float(projeto.get("zoom_respiro", zr["amplitude"]))
    ciclo = float(zr["ciclo_s"])
    pos = []
    if amp > 0:
        pos.append(f"scale=w='trunc({W}*(1+{amp}*(1-cos(2*PI*t/{ciclo}))/2)/2)*2':h=-2:eval=frame:flags=bicubic")
        pos.append(f"crop={W}:{H}")
    if not hq_geral:
        pos.append("eq=contrast=1.03:saturation=1.04,colorbalance=rs=0.02:bs=-0.02")
    else:
        pos.append("eq=contrast=1.02:saturation=1.02")
    pos.append("vignette=angle=PI/5")
    pos.append("format=yuv420p")
    filtros.append(f"[vc]{','.join(pos)}[vout]")

    saida.parent.mkdir(parents=True, exist_ok=True)
    crf = str(hqcfg["crf_intermediario"] if hq_geral else 14)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *entradas,
           "-filter_complex", ";".join(filtros), "-map", "[vout]", "-map", "[ac]",
           "-c:v", "libx264", "-preset", "medium", "-crf", crf, "-pix_fmt", "yuv420p",
           "-c:a", "pcm_s16le", "-ar", "48000", str(saida)]
    rodar(cmd)
    meta = {"duracao": round(total, 3), "largura": W, "altura": H, "fps": fps, "alta_qualidade": hq_geral,
            "clipes": info_clipes}
    saida.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta
