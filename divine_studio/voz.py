"""Limpeza de voz: highpass, redução de ruído e compressor suave. O loudnorm −16 LUFS fica na exportação.

Modos (projeto.yaml, audio.limpeza; padrão em config/preferencias.yaml, voz.modo):
  auto        mede o ruído de fundo e escolhe sozinho
  minima      só highpass (gravação limpa, lapela)
  leve        highpass + redução de ruído FFT + compressor suave
  forte       RNNoise (modelo .rnnn em config) ou, sem modelo, redução FFT mais forte
  elevenlabs  ElevenLabs Voice Isolator (precisa de ELEVENLABS_API_KEY); para ruído pesado (rua, ar-condicionado)
  nenhuma     áudio original intocado
"""
from __future__ import annotations

import os
import tempfile
import urllib.request
import uuid
from pathlib import Path

import numpy as np

from .config import ROOT, load
from .ingest import rodar

SR = 48000


def _cfg() -> dict:
    return load("preferencias").get("voz", {})


def medir_ruido(audio: np.ndarray) -> dict:
    """Piso de ruído e nível de fala (dBFS) em janelas de 50 ms; snr = distância entre os dois."""
    mono = audio.mean(1) if audio.ndim == 2 else audio
    n = int(0.05 * SR)
    if len(mono) < n * 4:
        return {"ruido_db": -90.0, "fala_db": -90.0, "snr_db": 0.0}
    janelas = mono[: len(mono) // n * n].reshape(-1, n)
    rms = np.sqrt((janelas ** 2).mean(1)) + 1e-9
    dbs = 20 * np.log10(rms)
    dbs = dbs[dbs > -100]          # silêncio digital (trecho mudo, b-roll) não é ruído de fundo
    if len(dbs) < 4:
        return {"ruido_db": -90.0, "fala_db": -90.0, "snr_db": 0.0}
    ruido, fala = float(np.percentile(dbs, 10)), float(np.percentile(dbs, 90))
    return {"ruido_db": round(ruido, 1), "fala_db": round(fala, 1), "snr_db": round(fala - ruido, 1)}


def escolher_modo(medida: dict) -> str:
    cfg = _cfg()
    if medida["fala_db"] < -60:
        return "nenhuma"                       # sem fala: não mexe
    if medida["snr_db"] < float(cfg.get("snr_ruido_pesado_db", 18)):
        return "elevenlabs" if os.environ.get("ELEVENLABS_API_KEY") else "forte"
    if medida["snr_db"] < float(cfg.get("snr_ruido_leve_db", 32)):
        return "leve"
    return "minima"


def _filtros(modo: str) -> str:
    cfg = _cfg()
    hp = f"highpass=f={cfg.get('highpass_hz', 80)}"
    comp = "acompressor=threshold=-21dB:ratio=2.2:attack=12:release=220:makeup=1.5"
    if modo == "minima":
        return hp
    if modo == "leve":
        return f"{hp},afftdn=nr=10:nf=-42:tn=1,{comp}"
    if modo == "forte":
        modelo = ROOT / cfg.get("modelo_rnnoise", "config/rnnoise/sh.rnnn")
        if modelo.exists():
            return f"{hp},arnndn=m='{modelo}':mix=0.85,{comp}"
        return f"{hp},afftdn=nr=18:nf=-36:tn=1,{comp}"
    raise ValueError(modo)


def _elevenlabs(entrada: Path, saida: Path) -> None:
    chave = os.environ.get("ELEVENLABS_API_KEY")
    if not chave:
        raise SystemExit("Defina ELEVENLABS_API_KEY para usar o Voice Isolator.")
    limite = uuid.uuid4().hex
    corpo = (f"--{limite}\r\nContent-Disposition: form-data; name=\"audio\"; filename=\"voz.wav\"\r\n"
             f"Content-Type: audio/wav\r\n\r\n").encode() + entrada.read_bytes() + f"\r\n--{limite}--\r\n".encode()
    req = urllib.request.Request("https://api.elevenlabs.io/v1/audio-isolation", data=corpo, method="POST",
                                 headers={"xi-api-key": chave,
                                          "content-type": f"multipart/form-data; boundary={limite}"})
    with urllib.request.urlopen(req, timeout=600) as r:
        isolado = r.read()
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(isolado)
    try:
        rodar(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", tmp.name, "-af",
               f"highpass=f={_cfg().get('highpass_hz', 80)}", "-ac", "2", "-ar", str(SR), str(saida)])
    finally:
        os.unlink(tmp.name)


def limpar(audio: np.ndarray, modo: str = "auto") -> tuple:
    """audio float32 (n, 2) 48 kHz -> (audio limpo, modo usado, medida)."""
    medida = medir_ruido(audio)
    if modo == "auto":
        modo = escolher_modo(medida)
    if modo == "nenhuma" or not len(audio):
        return audio, modo, medida
    with tempfile.TemporaryDirectory() as tmp:
        ent, sai = Path(tmp) / "ent.wav", Path(tmp) / "sai.wav"
        from .audio import ler_audio, salvar_wav
        salvar_wav(audio, ent)
        if modo == "elevenlabs":
            _elevenlabs(ent, sai)
        else:
            rodar(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(ent), "-af", _filtros(modo),
                   "-ac", "2", "-ar", str(SR), "-c:a", "pcm_s16le", str(sai)])
        limpo = ler_audio(sai, len(audio) / SR)
    return limpo, modo, medida

