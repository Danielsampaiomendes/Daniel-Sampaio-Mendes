"""Kit de sons virais do Divine Studio: sintetizados aqui (originais, livres de direitos), no estilo dos sons que mais
aparecem em edits de Reels e TikTok, mas mixados baixos e elegantes.

  boom_grave      impacto grave tipo "boom" de meme, para o gancho e a revelação
  drop_sub        queda grave (808) depois de um riser, entrada da batida
  whoosh_rapido   passada rápida, para chicote e troca de cena
  glitch_digital  falha digital curta, para glitch/RGB
  flash_brilho    estalo brilhante de flash, para flash branco/dourado
  scratch_disco   arranhão de disco, para "pausa" e virada cômica
  coracao         batida de coração, para suspense
  zap_suave       raio descendente curto, para giro e zoom
  estalo_dedos    estalo de dedos, para corte seco e troca de look
  subida_tensao   riser curto de tensão (1,2 s), antes do drop

Gerados uma vez em Biblioteca_SFX/1_kit_original_divine (o app cria sozinho se faltar).
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 48000
SONS = ["boom_grave", "drop_sub", "whoosh_rapido", "glitch_digital", "flash_brilho", "scratch_disco", "coracao",
        "zap_suave", "estalo_dedos", "subida_tensao"]


def _t(d):
    return np.arange(int(d * SR)) / SR


def _filtro(x, lo=None, hi=None):
    """Passa-faixa por FFT (rápido, sem scipy)."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    m = np.ones_like(f)
    if lo:
        m *= 1 / (1 + (lo / np.maximum(f, 1)) ** 4)
    if hi:
        m *= 1 / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * m, len(x))


def _env(n, ataque=0.003, queda=6.0):
    a = max(1, int(ataque * SR))
    e = np.ones(n)
    e[:a] = np.linspace(0, 1, a)
    e[a:] = np.exp(-queda * np.linspace(0, 1, n - a))
    return e


def _reverb(x, mix=0.18, tam=1.0, rng=None):
    rng = rng or np.random.default_rng(3)
    n = int(SR * 1.2 * tam)
    ir = rng.standard_normal(n) * np.exp(-np.linspace(0, 8, n))
    ir = _filtro(ir, hi=6000)
    ir /= np.sqrt((ir ** 2).sum()) + 1e-9
    w = np.fft.irfft(np.fft.rfft(x, len(x) + n) * np.fft.rfft(ir, len(x) + n), len(x) + n)
    return np.concatenate([x, np.zeros(n)]) * (1 - mix) + w * mix * 0.6


def _sweep(f0, f1, d, curva=2.0):
    tt = _t(d)
    p = (tt / d) ** curva
    f = f0 + (f1 - f0) * p
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def gerar(nome: str, var: int = 0) -> np.ndarray:
    rng = np.random.default_rng(11 + var * 7 + SONS.index(nome))
    k = 1 + 0.08 * var
    if nome == "boom_grave":
        d = 1.3
        corpo = _sweep(140 * k, 38, d, 0.5) * _env(int(d * SR), 0.002, 4.5)
        clique = _filtro(rng.standard_normal(int(0.03 * SR)), lo=800) * np.linspace(1, 0, int(0.03 * SR)) * 0.6
        x = np.tanh(corpo * 2.2) * 0.9
        x[: len(clique)] += clique
        return _reverb(x, 0.12, 1.4, rng)
    if nome == "drop_sub":
        d = 1.8
        return np.tanh(_sweep(70 * k, 32, d, 0.7) * 1.6) * _env(int(d * SR), 0.004, 3.0)
    if nome == "whoosh_rapido":
        d = 0.32 * k
        n = rng.standard_normal(int(d * SR))
        p = np.linspace(0, 1, len(n))
        forma = np.sin(np.pi * p) ** 1.5
        return _reverb(_filtro(n, lo=600, hi=5000 + 2000 * var) * forma, 0.1, 0.6, rng)
    if nome == "glitch_digital":
        d = 0.38
        tt = _t(d)
        x = np.zeros_like(tt)
        for _ in range(9):
            a = rng.integers(0, len(tt) - 1500)
            n = rng.integers(400, 1500)
            f = rng.choice([220, 440, 880, 1760]) * k
            x[a:a + n] += np.sign(np.sin(2 * np.pi * f * tt[:n])) * rng.uniform(0.3, 0.8)
        return np.round(x * 6) / 6 * _env(len(tt), 0.001, 2.0)
    if nome == "flash_brilho":
        d = 0.7
        tt = _t(d)
        ruido = _filtro(rng.standard_normal(len(tt)), lo=5000) * _env(len(tt), 0.001, 14)
        sino = sum(a * np.sin(2 * np.pi * f * k * tt) * np.exp(-7 * tt) for f, a in ((2637, .5), (3951, .35), (5274, .2)))
        return _reverb(ruido * 0.8 + sino * 0.5, 0.25, 1.0, rng)
    if nome == "scratch_disco":
        d = 0.42
        tt = _t(d)
        vel = np.sin(2 * np.pi * (5 + var) * tt) * 0.9 + 0.1
        fase = np.cumsum(180 + 900 * np.abs(vel)) / SR
        x = np.sin(2 * np.pi * fase) * 0.4 + _filtro(rng.standard_normal(len(tt)), lo=300, hi=3000) * np.abs(vel) * 0.8
        return x * _env(len(tt), 0.005, 2.5)
    if nome == "coracao":
        d = 0.9
        tt = _t(d)
        x = np.zeros_like(tt)
        for ini, amp in ((0.0, 1.0), (0.22, 0.75)):
            a = int(ini * SR)
            b = _t(0.16)
            x[a:a + len(b)] += np.sin(2 * np.pi * 55 * k * b) * np.exp(-28 * b) * amp
        return np.tanh(x * 2)
    if nome == "zap_suave":
        d = 0.3
        return _reverb(_sweep(2400 * k, 300, d, 0.6) * _env(int(d * SR), 0.001, 5) * 0.7, 0.15, 0.6, rng)
    if nome == "estalo_dedos":
        d = 0.18
        n = rng.standard_normal(int(d * SR))
        return _reverb(_filtro(n, lo=1500 * k, hi=4500) * _env(len(n), 0.0005, 30), 0.2, 0.5, rng)
    if nome == "subida_tensao":
        d = 1.2 * k
        tt = _t(d)
        tom = _sweep(180, 1200, d, 2.2) * 0.4
        ruido = _filtro(rng.standard_normal(len(tt)), lo=1000, hi=9000) * (tt / d) ** 2 * 0.6
        corte = np.ones_like(tt)
        corte[-int(0.03 * SR):] = np.linspace(1, 0, int(0.03 * SR))
        return (tom + ruido) * (tt / d) ** 1.5 * corte
    raise ValueError(nome)


def _salvar(x: np.ndarray, arq: Path) -> None:
    x = x / (np.abs(x).max() + 1e-9) * 10 ** (-1 / 20)
    est = np.stack([x, np.roll(x, int(0.006 * SR)) * 0.96], 1)
    q = (np.clip(est, -1, 1) * 32767).astype("<i2")
    with wave.open(str(arq), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(q.tobytes())


def garantir(pasta: Path) -> list:
    """Cria os sons virais que faltam (duas variações de cada: _a e _b). Rápido quando já existem."""
    pasta.mkdir(parents=True, exist_ok=True)
    novos = []
    for nome in SONS:
        for var, letra in enumerate("ab"):
            arq = pasta / f"{nome}_{letra}.wav"
            if not arq.exists():
                _salvar(gerar(nome, var), arq)
                novos.append(arq.name)
    return novos
