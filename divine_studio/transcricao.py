"""Transcrição com tempo por palavra (AssemblyAI, faster-whisper ou Whisper local).

Resultado: lista de palavras {"texto", "inicio", "fim", "conf"} em segundos, no tempo do arquivo bruto.
Fica em cache em trabalho/transcricoes/. Para corrigir uma palavra errada, copie o .json para
<mesmo nome>.editado.json, ajuste o texto e ele passa a valer no lugar do automático.

Motores (config/preferencias.yaml, transcricao.motor):
  auto            AssemblyAI se existir ASSEMBLYAI_API_KEY; senão faster-whisper; senão whisper
  assemblyai      precisa de ASSEMBLYAI_API_KEY no ambiente
  faster_whisper  pip3 install faster-whisper (roda no Mac, sem internet depois de baixar o modelo)
  whisper         pip3 install openai-whisper
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import urllib.request
from pathlib import Path

from .config import load
from .ingest import rodar


def _cfg() -> dict:
    return load("preferencias").get("transcricao", {})


def _chave_cache(arquivo: Path) -> str:
    st = arquivo.stat()
    h = hashlib.sha1(f"{arquivo.resolve()}|{st.st_size}|{int(st.st_mtime)}".encode()).hexdigest()[:10]
    return f"{arquivo.stem}_{h}"


def extrair_audio(arquivo: Path, saida: Path) -> Path:
    """Mono 16 kHz, só a primeira trilha de áudio (iPhone .mov às vezes traz trilhas extras)."""
    rodar(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(arquivo), "-map", "0:a:0", "-vn",
           "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(saida)])
    return saida


def _assemblyai(wav: Path, idioma: str) -> list:
    chave = os.environ.get("ASSEMBLYAI_API_KEY")
    if not chave:
        raise SystemExit("Defina ASSEMBLYAI_API_KEY para usar a AssemblyAI.")
    base = "https://api.assemblyai.com/v2"

    def req(url, dados=None, json_=None):
        cab = {"authorization": chave}
        if json_ is not None:
            dados = json.dumps(json_).encode()
            cab["content-type"] = "application/json"
        r = urllib.request.Request(url, data=dados, headers=cab, method="POST" if dados is not None else "GET")
        with urllib.request.urlopen(r, timeout=300) as resp:
            return json.loads(resp.read())

    url_audio = req(f"{base}/upload", dados=wav.read_bytes())["upload_url"]
    # disfluencies: devolve "é", "hum" etc. para o corte limpo poder tirar
    job = req(f"{base}/transcript", json_={"audio_url": url_audio, "language_code": idioma, "disfluencies": True,
                                           "punctuate": True, "format_text": True})
    while True:
        r = req(f"{base}/transcript/{job['id']}")
        if r["status"] == "completed":
            break
        if r["status"] == "error":
            raise SystemExit(f"AssemblyAI: {r.get('error')}")
        time.sleep(3)
    return [{"texto": w["text"], "inicio": w["start"] / 1000, "fim": w["end"] / 1000,
             "conf": round(w.get("confidence", 1.0), 3)} for w in r.get("words") or []]


def _faster_whisper(wav: Path, idioma: str, modelo: str) -> list:
    from faster_whisper import WhisperModel
    m = WhisperModel(modelo, device="auto", compute_type="int8")
    segs, _ = m.transcribe(str(wav), language=idioma, word_timestamps=True,
                           initial_prompt="Divine Medical Spa, Avenida Paulista, laser de CO2, endolaser.")
    out = []
    for s in segs:
        for w in s.words or []:
            out.append({"texto": w.word.strip(), "inicio": round(w.start, 3), "fim": round(w.end, 3),
                        "conf": round(w.probability, 3)})
    return out


def _whisper(wav: Path, idioma: str, modelo: str) -> list:
    import whisper
    m = whisper.load_model(modelo)
    r = m.transcribe(str(wav), language=idioma, word_timestamps=True)
    return [{"texto": w["word"].strip(), "inicio": round(w["start"], 3), "fim": round(w["end"], 3),
             "conf": round(w.get("probability", 1.0), 3)} for s in r["segments"] for w in s.get("words", [])]


def motor_disponivel(pedido: str = "auto") -> str:
    if pedido != "auto":
        return pedido
    if os.environ.get("ASSEMBLYAI_API_KEY"):
        return "assemblyai"
    for mod, nome in (("faster_whisper", "faster_whisper"), ("whisper", "whisper")):
        try:
            __import__(mod)
            return nome
        except ImportError:
            pass
    return ""


def transcrever(arquivo: Path, pasta_cache: Path, motor: str | None = None, refazer: bool = False) -> list:
    """Palavras do arquivo (com cache). Prefere a versão .editado.json quando existe."""
    cfg = _cfg()
    pasta_cache.mkdir(parents=True, exist_ok=True)
    chave = _chave_cache(Path(arquivo))
    editado = pasta_cache / f"{chave}.editado.json"
    cache = pasta_cache / f"{chave}.json"
    if editado.exists():
        return json.loads(editado.read_text(encoding="utf-8"))["palavras"]
    if cache.exists() and not refazer:
        return json.loads(cache.read_text(encoding="utf-8"))["palavras"]
    if not refazer:
        # o mesmo bruto já transcrito em outro projeto (ex.: peças do pacote): reaproveita, editado primeiro
        from .config import ROOT
        achados = sorted((ROOT / "projetos").glob(f"**/trabalho/transcricoes/{chave}*.json"),
                         key=lambda x: ".editado." not in x.name)
        if achados:
            return json.loads(achados[0].read_text(encoding="utf-8"))["palavras"]

    m = motor_disponivel(motor or cfg.get("motor", "auto"))
    if not m:
        raise SystemExit("Nenhum motor de transcrição disponível. Opções:\n"
                         "  export ASSEMBLYAI_API_KEY=...        (AssemblyAI, na nuvem)\n"
                         "  pip3 install faster-whisper          (local, recomendado no Mac)")
    idioma = cfg.get("idioma", "pt")
    with tempfile.TemporaryDirectory() as tmp:
        wav = extrair_audio(Path(arquivo), Path(tmp) / "audio.wav")
        print(f"  transcrevendo {Path(arquivo).name} com {m}…", flush=True)
        if m == "assemblyai":
            palavras = _assemblyai(wav, idioma)
        elif m == "faster_whisper":
            palavras = _faster_whisper(wav, idioma, cfg.get("modelo_whisper", "small"))
        elif m == "whisper":
            palavras = _whisper(wav, idioma, cfg.get("modelo_whisper", "small"))
        else:
            raise SystemExit(f"Motor de transcrição desconhecido: {m}")
    palavras = [p for p in palavras if p["texto"]]
    cache.write_text(json.dumps({"arquivo": str(arquivo), "motor": m, "palavras": palavras}, indent=1,
                                ensure_ascii=False), encoding="utf-8")
    return palavras


def texto_corrido(palavras: list) -> str:
    return " ".join(p["texto"] for p in palavras)


def importar_srt(arquivo: Path) -> list:
    """Legenda .srt (sem tempo por palavra) -> palavras com tempo distribuído pelo tamanho de cada palavra."""
    import re
    blocos = re.split(r"\n\s*\n", Path(arquivo).read_text(encoding="utf-8-sig").strip())
    out = []

    def seg(s):
        h, m, r = s.replace(",", ".").split(":")
        return int(h) * 3600 + int(m) * 60 + float(r)

    for b in blocos:
        linhas = b.strip().splitlines()
        tl = next((ln for ln in linhas if "-->" in ln), None)
        if not tl:
            continue
        a, z = (seg(x.strip()) for x in tl.split("-->"))
        txt = " ".join(ln for ln in linhas[linhas.index(tl) + 1:]).split()
        total = sum(len(w) + 1 for w in txt) or 1
        t = a
        for w in txt:
            d = (z - a) * (len(w) + 1) / total
            out.append({"texto": w, "inicio": round(t, 3), "fim": round(t + d * 0.92, 3), "conf": 1.0})
            t += d
    return out

