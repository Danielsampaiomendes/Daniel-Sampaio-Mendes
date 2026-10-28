"""Áudio: trilha lounge original sintetizada (sem direitos), SFX baixos do kit Divine e ducking sob a fala."""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np

from .config import ROOT, load

SR = 48000


def ler_audio(arquivo: Path, duracao: float | None = None) -> np.ndarray:
    """Qualquer arquivo de áudio/vídeo -> float32 estéreo (n, 2) em 48 kHz."""
    cmd = ["ffmpeg", "-v", "error", "-i", str(arquivo), "-vn", "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or not r.stdout:
        n = int((duracao or 0) * SR)
        return np.zeros((n, 2), np.float32)
    a = np.frombuffer(r.stdout, np.float32).reshape(-1, 2).copy()
    if duracao is not None:
        n = int(duracao * SR)
        a = a[:n] if len(a) >= n else np.vstack([a, np.zeros((n - len(a), 2), np.float32)])
    return a


def salvar_wav(a: np.ndarray, arquivo: Path) -> None:
    a = np.clip(a, -0.98, 0.98)
    with wave.open(str(arquivo), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((a * 32767).astype(np.int16).tobytes())


def db(x: float) -> float:
    return 10 ** (x / 20)


def trilha_lounge(duracao: float, bpm: float = 84, semente: int = 7) -> np.ndarray:
    """Pad lounge suave (Fmaj9, Dm9, Bbmaj7, C6) + baixo macio + notas dedilhadas discretas."""
    t = np.arange(int(duracao * SR)) / SR
    out = np.zeros_like(t)
    acordes = [[174.6, 220.0, 261.6, 329.6, 392.0], [146.8, 174.6, 220.0, 261.6, 329.6],
               [116.5, 146.8, 174.6, 220.0, 293.7], [130.8, 164.8, 196.0, 220.0, 329.6]]
    baixos = [87.3, 73.4, 58.3, 65.4]
    compasso = 4 * 60.0 / bpm * 2  # 2 compassos por acorde
    rng = np.random.default_rng(semente)
    for i in range(int(duracao / compasso) + 2):
        c = acordes[i % 4]
        s0 = i * compasso
        idx = (t >= s0 - 0.8) & (t < s0 + compasso + 1.2)
        tt = t[idx] - s0
        env = np.clip((tt + 0.8) / 1.6, 0, 1) * np.clip((compasso + 1.2 - tt) / 1.6, 0, 1)
        sig = 0
        for f in c:
            ph = rng.uniform(0, 6.28)
            sig = sig + np.sin(2 * np.pi * f * tt + ph) * 0.6 + np.sin(2 * np.pi * f * 2.003 * tt + ph) * 0.12
        out[idx] += sig * env / len(c)
        b = baixos[i % 4]
        out[idx] += 0.35 * np.sin(2 * np.pi * b * tt) * env * np.exp(-((tt % (compasso / 2)) * 1.2))
    out *= 0.85 + 0.15 * np.sin(2 * np.pi * 0.25 * t)
    notas = [523.3, 587.3, 659.3, 784.0, 880.0]
    passo = 60.0 / bpm * 2
    for k, s in enumerate(np.arange(1.0, max(1.0, duracao - 2), passo)):
        f = notas[(k * 3) % 5]
        idx = (t >= s) & (t < s + 1.5)
        tt = t[idx] - s
        out[idx] += 0.08 * np.sin(2 * np.pi * f * tt) * np.exp(-tt * 3.0)
    out /= np.abs(out).max() + 1e-9
    return np.stack([out, out], 1).astype(np.float32)


def sfx(nome: str) -> np.ndarray:
    pasta = ROOT / load("sfx")["pasta"]
    arq = pasta / f"{nome}.wav"
    if not arq.exists():
        print(f"  aviso: SFX {nome} não encontrado em {pasta} (rode Biblioteca_SFX/gerar_kit_sfx.py)")
        return np.zeros((1, 2), np.float32)
    return ler_audio(arq)


def colocar(buf: np.ndarray, clip: np.ndarray, em: float, ganho_db: float) -> None:
    i = int(em * SR)
    if i >= len(buf):
        return
    c = clip * db(ganho_db)
    e = min(len(buf), i + len(c))
    buf[i:e] += c[: e - i]


def envelope_fala(voz: np.ndarray, janela_s: float = 0.25) -> np.ndarray:
    """0..1 indicando presença de fala (para o ducking)."""
    mono = np.abs(voz).mean(1)
    n = max(1, int(janela_s * SR))
    k = np.ones(n) / n
    rms = np.sqrt(np.convolve(mono ** 2, k, mode="same"))
    limiar = max(0.01, np.percentile(rms, 60) * 0.5)
    pres = np.clip((rms - limiar) / (limiar * 2), 0, 1)
    # suaviza ataque/soltura
    k2 = np.ones(int(0.4 * SR)) / int(0.4 * SR)
    return np.clip(np.convolve(pres, k2, mode="same") * 1.6, 0, 1)


def mixar(duracao: float, voz: np.ndarray | None, eventos: list, usar_trilha: bool = True,
          volume_trilha_db: float | None = None, semente: int = 7) -> np.ndarray:
    """voz: áudio original da base (ou None); eventos: [(segundos, nome_sfx, ganho_db)]."""
    pref = load("preferencias")["trilha"]
    n = int(duracao * SR)
    mix = np.zeros((n, 2), np.float32)
    tem_fala = False
    if voz is not None and len(voz):
        v = voz[:n] if len(voz) >= n else np.vstack([voz, np.zeros((n - len(voz), 2), np.float32)])
        pico = np.abs(v).max()
        tem_fala = pico > 0.02
        if tem_fala:
            mix += v
    if usar_trilha:
        tr = trilha_lounge(duracao, pref["bpm"], semente)
        vol = db(volume_trilha_db if volume_trilha_db is not None else pref["volume_db"])
        if tem_fala:
            env = envelope_fala(mix)
            g = vol * (1 - env) + db(pref["ducking_db"]) * env
            tr = tr * g[:, None]
        else:
            tr = tr * vol * 1.8
        t = np.arange(n) / SR
        fade_in = np.clip(t / pref["entrada_s"], 0, 1)
        fade_out = np.clip((duracao - t) / 0.8, 0, 1)
        mix += tr * (fade_in * fade_out)[:, None]
    for em, nome, g in eventos:
        colocar(mix, sfx(nome), em, g)
    return mix
