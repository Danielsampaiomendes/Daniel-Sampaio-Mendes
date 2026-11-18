"""Ingestão: lê os brutos, corta, converte HDR para SDR, recorta no formato e monta a base do vídeo.

Cada clipe do projeto.yaml:
  arquivo: bruto/IMG_1234.MOV   (relativo à pasta do projeto ou à raiz do repositório)
  inicio: 2.0                    (s, opcional)
  fim: 8.5                       (s, opcional)
  velocidade: 0.72               (opcional; < 1 = câmera lenta com mescla de quadros)
  foco: [0.5, 0.35]              (âncora do recorte x, y de 0 a 1; padrão centro)
  zoom: 1.0                      (aproximação extra; 1 = só preencher o quadro)
  corte_seco: true               (entra com corte seco, sem dissolve: frases seguidas do mesmo take)
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .config import ROOT, load


HDR_COM_ZSCALE = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
                  "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
# FFmpeg sem o zscale (libzimg), comum no Mac: converte a matriz de cor pelo próprio FFmpeg e compensa o HLG do
# iPhone com um pouco de contraste e saturação. Ajustável em config/exportacao.yaml (hdr_sem_zscale).
HDR_SEM_ZSCALE = ("scale=in_color_matrix=bt2020:out_color_matrix=bt709:in_range=tv:out_range=tv,format=yuv420p,"
                  "eq=contrast=1.06:saturation=1.12,"
                  "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709")
_FILTROS: dict = {}          # respostas guardadas (e o que os testes forçam)
_LISTA: list = []            # [conjunto dos filtros deste FFmpeg], lido uma vez
_AVISADOS: set = set()

# Filtros de ACABAMENTO: se o FFmpeg desta máquina não tiver um deles, a edição segue sem ele (com aviso) em vez de
# parar com "No such filter". Os essenciais (scale, crop, concat, xfade, loudnorm...) existem em todo FFmpeg.
ACABAMENTO_VIDEO = {"eq", "vignette", "noise", "hqdn3d", "nlmeans", "unsharp", "colorbalance", "curves", "hue",
                    "deshake", "minterpolate", "vidstabtransform", "cas", "deflicker", "gblur", "lut3d"}
ACABAMENTO_AUDIO = {"deesser", "afftdn", "arnndn", "acompressor", "alimiter", "equalizer", "highpass", "lowpass",
                    "anlmdn", "speechnorm", "dynaudnorm", "agate"}


def _filtros_do_ffmpeg() -> set:
    if not _LISTA:
        try:
            saida = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, timeout=30).stdout
        except (OSError, subprocess.SubprocessError):
            saida = ""
        _LISTA.append({ln.split()[1] for ln in saida.splitlines() if len(ln.split()) >= 3 and "->" in ln})
    return _LISTA[0]


def tem_filtro(nome: str) -> bool:
    """O FFmpeg desta máquina tem o filtro? (a resposta fica guardada: a lista não muda com o app aberto)
    Se não der para ler a lista, responde que tem: é melhor tentar do que tirar um filtro que existe."""
    if nome not in _FILTROS:
        lista = _filtros_do_ffmpeg()
        _FILTROS[nome] = (nome in lista) if lista else True
    return _FILTROS[nome]


def ffmpeg_completo() -> dict:
    """O que este FFmpeg tem do que o app usa: {"faltam": [...], "essenciais": [...]} (para a Saúde do app).
    Sem o codificador de vídeo (libx264) nada exporta; sem os filtros de acabamento a edição sai, mas mais simples."""
    try:
        cods = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return {"faltam": [], "essenciais": []}
    essenciais = [c for c in ("libx264", "aac") if cods and f" {c} " not in cods]
    lista = _filtros_do_ffmpeg()
    faltam = sorted(f for f in ({"zscale"} | ACABAMENTO_VIDEO | ACABAMENTO_AUDIO) - {"vidstabtransform", "arnndn", "lut3d"}
                    if lista and f not in lista)
    return {"faltam": faltam, "essenciais": essenciais}


def _partes(grafo: str) -> list:
    """Quebra o grafo de filtros em (texto, separador) nas vírgulas e ponto e vírgulas de verdade (fora de aspas
    e sem barra de escape)."""
    out, atual, aspas, k = [], "", False, 0
    while k < len(grafo):
        ch = grafo[k]
        if ch == "\\" and k + 1 < len(grafo):
            atual += grafo[k:k + 2]
            k += 2
            continue
        if ch == "'":
            aspas = not aspas
        if ch in ",;" and not aspas:
            out.append((atual, ch))
            atual = ""
        else:
            atual += ch
        k += 1
    out.append((atual, ""))
    return out


def filtros_seguros(grafo: str) -> str:
    """O mesmo grafo, com os filtros de acabamento que este FFmpeg não tem trocados por null/anull."""
    import re
    partes, mudou = [], False
    for texto, sep in _partes(str(grafo)):
        m = re.match(r"^(\s*(?:\[[^\]]*\]\s*)*)([A-Za-z0-9_]+)(.*?)((?:\s*\[[^\]]*\])*\s*)$", texto, re.S)
        if m:
            nome = m.group(2)
            audio = nome in ACABAMENTO_AUDIO
            if (audio or nome in ACABAMENTO_VIDEO) and not tem_filtro(nome):
                if nome not in _AVISADOS:
                    _AVISADOS.add(nome)
                    print(f"  aviso: este FFmpeg não tem o filtro {nome}; a edição segue sem esse acabamento "
                          "(para ter todos: brew install ffmpeg)", flush=True)
                texto, mudou = m.group(1) + ("anull" if audio else "null") + m.group(4), True
        partes.append(texto + sep)
    return "".join(partes) if mudou else str(grafo)


_OPCOES_DE_FILTRO = ("-vf", "-af", "-filter_complex", "-filter:v", "-filter:a", "-lavfi")


def cmd_seguro(cmd: list) -> list:
    """Comando do FFmpeg com os grafos de filtro passados por filtros_seguros."""
    if not cmd or not str(cmd[0]).endswith("ffmpeg"):
        return cmd
    out = list(cmd)
    for k in range(len(out) - 1):
        if out[k] in _OPCOES_DE_FILTRO:
            out[k + 1] = filtros_seguros(out[k + 1])
    return out


def filtro_hdr() -> str:
    """Conversão do vídeo HDR do iPhone para cor normal: a melhor (zscale + tonemap) quando o FFmpeg tem o zscale;
    sem ele, a conversão que todo FFmpeg faz, em vez de parar com "No such filter: 'zscale'"."""
    if tem_filtro("zscale"):
        return HDR_COM_ZSCALE
    print("  aviso: este FFmpeg não tem o filtro zscale; usando a conversão HDR simples (a cor pode ficar um pouco "
          "menos fiel). Para a conversão completa: brew install ffmpeg", flush=True)
    return str(load("exportacao").get("hdr_sem_zscale") or HDR_SEM_ZSCALE)

HDR_TRANSFERS = {"arib-std-b67", "smpte2084"}


def com_threads(cmd: list) -> list:
    """FFmpeg com o limite de threads da prévia em paralelo (DIVINE_FFMPEG_THREADS); sem limite, igual."""
    import os
    cmd = cmd_seguro(cmd)                      # filtro de acabamento que falta neste FFmpeg não derruba a edição
    n = os.environ.get("DIVINE_FFMPEG_THREADS")
    if n and cmd and str(cmd[0]).endswith("ffmpeg") and "-threads" not in cmd and len(cmd) > 2:
        return [*cmd[:-1], "-threads", n, cmd[-1]]
    return cmd


def rodar(cmd: list, silencioso: bool = True) -> subprocess.CompletedProcess:
    cmd = com_threads(cmd)
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


VELOCITY = [(0.40, 1.8), (0.25, 0.4), (0.35, 1.8)]     # rápido, câmera lenta, rápido (fração do trecho, velocidade)


def _expandir_velocity(projeto: dict, clipes: list) -> list:
    """Clipe com 'velocity: true' vira 3 trechos colados (rápido, câmera lenta, rápido), o efeito velocity edit."""
    out = []
    for c in clipes:
        if not c.get("velocity"):
            out.append(c)
            continue
        arq = resolver(projeto, c["arquivo"])
        ini = float(c.get("inicio", 0))
        fim = float(c.get("fim") or probe(arq)["duracao"])
        t = ini
        for k, (frac, vel) in enumerate(VELOCITY):
            pedaco = {**{x: v for x, v in c.items() if x != "velocity"}, "inicio": round(t, 3),
                      "fim": round(t + (fim - ini) * frac, 3), "velocidade": vel}
            if k:
                pedaco["transicao"] = "corte"
                pedaco["_corte_seco"] = True
            out.append(pedaco)
            t += (fim - ini) * frac
    return out


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

    clipes = _expandir_velocity(projeto, clipes)
    entradas, filtros, info_clipes = [], [], []
    hq_geral = False
    for i, c in enumerate(clipes):
        arq = resolver(projeto, c["arquivo"])
        p = probe(arq)
        ini = float(c.get("inicio", 0))
        fim = float(c.get("fim", p["duracao"]))
        if p["duracao"]:
            fim = min(fim, p["duracao"])          # fim além do arquivo congelava a imagem e desalinhava o áudio
        if ini >= fim - 0.05:
            raise SystemExit(f"Clipe {c['arquivo']}: início ({ini:.2f}s) depois do fim do vídeo ({fim:.2f}s). "
                             "Ajuste inicio/fim no projeto.")
        vel = float(c.get("velocidade", 1.0))
        from .qualidade import opcoes, preparar
        ops = opcoes(projeto, c)
        if ops and projeto.get("_pasta"):
            # bruto melhorado (estabilizado, sem ruído, upscale) só no trecho usado; cache em trabalho/qualidade
            arq = preparar(arq, ini, fim, ops, (W, H), Path(projeto["_pasta"]) / "trabalho" / "qualidade")
            fim, ini = fim - ini, 0.0
            p = probe(arq)
            fim = min(fim, p["duracao"] or fim)
        dur_out = (fim - ini) / vel
        fx, fy = (c.get("foco") or [0.5, 0.5])
        z = float(c.get("zoom", 1.0))
        hq = forcar_hq if forcar_hq is not None else (min(p["largura"], p["altura"]) < hqcfg["altura_minima"] or c.get("alta_qualidade", False))
        hq_geral = hq_geral or hq
        entradas += ["-ss", f"{ini:.3f}", "-t", f"{fim - ini:.3f}", "-i", str(arq)]
        trans_cfg = (load("edicao").get("transicoes") or {}).get(c.get("transicao") or "dissolver", {})
        if dissolve <= 0 or (c.get("transicao") and trans_cfg.get("xfade") is None):
            c = {**c, "_corte_seco": True}

        v = []
        if p["hdr"]:
            v.append(filtro_hdr())
        if hq:
            v.append(hqcfg["denoise"])
        if c.get("reverso"):
            v.append("reverse")                      # de trás para frente (clipes curtos)
        v.append(f"setpts=(PTS-STARTPTS)/{vel}")
        if vel < 1.0:
            from .qualidade import filtro_camera_lenta
            v.append(filtro_camera_lenta(fps) if ops.get("camera_lenta_suave") else f"framerate=fps={fps}")
        v.append(f"scale={int(W * z)}:{int(H * z)}:force_original_aspect_ratio=increase:flags=lanczos")
        v.append(f"crop={W}:{H}:(iw-{W})*{fx}:(ih-{H})*{fy}")
        if hq:
            v.append(hqcfg["nitidez"])
        v.append(f"fps={fps},format=yuv420p,setsar=1,settb=AVTB")
        filtros.append(f"[{i}:v]{','.join(v)}[v{i}]")

        if p["audio"] and not c.get("mudo", False):
            # micro fade nas pontas: corte seco no meio da fala sem estalo
            extra_a = ("areverse," if c.get("reverso") else "") + \
                (f"volume={float(c['volume']):.3f}," if c.get("volume") not in (None, "", 1, 1.0) else "")
            filtros.append(f"[{i}:a:0]{extra_a}asetpts=PTS-STARTPTS,{_atempo(vel)},aresample=48000,"
                           f"aformat=sample_fmts=fltp:channel_layouts=stereo,afade=t=in:d=0.012,"
                           f"afade=t=out:st={max(0.0, dur_out - 0.012):.3f}:d=0.012[a{i}]")
        else:
            filtros.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{dur_out:.3f}[a{i}]")
        info_clipes.append({"arquivo": c["arquivo"], "caminho": str(arq), "inicio": ini, "velocidade": vel,
                            "duracao": round(dur_out, 3), "hdr": p["hdr"], "hq": hq,
                            "resolucao": f"{p['largura']}x{p['altura']}",
                            "transicao": 0.0 if (i == 0 or c.get("_corte_seco") or c.get("corte_seco")) else dissolve,
                            "tipo_transicao": trans_cfg.get("xfade") or "fade"})

    # dissolve entre clipes diferentes; corte seco entre trechos do mesmo take (corte limpo)
    pv, pa = "v0", "a0"
    L = info_clipes[0]["duracao"]
    info_clipes[0]["inicio_base"] = 0.0
    for k in range(1, len(clipes)):
        d = info_clipes[k]["transicao"]
        if d > 0:
            filtros.append(f"[{pv}][v{k}]xfade=transition={info_clipes[k]['tipo_transicao']}:duration={d}:offset={L - d:.3f}[vx{k}]")
            filtros.append(f"[{pa}][a{k}]acrossfade=d={d}[ax{k}]")
        else:
            filtros.append(f"[{pv}][v{k}]concat=n=2:v=1:a=0,settb=AVTB[vx{k}]")
            filtros.append(f"[{pa}][a{k}]concat=n=2:v=0:a=1[ax{k}]")
        info_clipes[k]["inicio_base"] = round(L - d, 3)
        pv, pa = f"vx{k}", f"ax{k}"
        L = L + info_clipes[k]["duracao"] - d
    filtros.append(f"[{pv}]null[vc];[{pa}]anull[ac]")
    total = L

    zr = pref["animacao"]["zoom_respiro"]
    amp = float(projeto.get("zoom_respiro", zr["amplitude"]))
    ciclo = float(zr["ciclo_s"])
    pos = []
    if amp > 0:
        pos.append(f"scale=w='trunc({W}*(1+{amp}*(1-cos(2*PI*t/{ciclo}))/2)/2)*2':h=-2:eval=frame:flags=bicubic")
        pos.append(f"crop={W}:{H}")
    acab = pref.get("acabamento") or {}
    original = bool(projeto.get("cor_original", acab.get("cor_original", False)))
    if original:
        pass                                  # cor original da gravação: sem correção automática
    elif not hq_geral:
        pos.append("eq=contrast=1.03:saturation=1.04,colorbalance=rs=0.02:bs=-0.02")
    else:
        pos.append("eq=contrast=1.02:saturation=1.02")
    cor = projeto.get("cor") or {}
    filtro = ((load("edicao").get("filtros") or {}).get(cor.get("filtro") or "natural") or {}).get("ffmpeg")
    if filtro:
        pos.append(filtro)
    ajustes = {k: float(cor.get(k) or 0) for k in ("brilho", "contraste", "saturacao", "temperatura")}
    if any(ajustes.values()):
        pos.append(f"eq=brightness={ajustes['brilho'] * 0.12:.3f}:contrast={1 + ajustes['contraste'] * 0.3:.3f}"
                   f":saturation={1 + ajustes['saturacao'] * 0.5:.3f}")
        if ajustes["temperatura"]:
            t = ajustes["temperatura"] * 0.08
            pos.append(f"colorbalance=rs={t:.3f}:bs={-t:.3f}:rm={t / 2:.3f}:bm={-t / 2:.3f}")
    if not original:
        pos.append("vignette=angle=PI/5")
    grao = 0 if original else int(acab.get("grao", 0))
    if grao > 0:
        pos.append(f"noise=alls={grao}:allf=u")       # grão fixo: acabamento sem inflar o arquivo
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
