"""Kit original de SFX Divine (sintetizado, livre de direitos). Gera WAV 24 bit 48 kHz."""
import numpy as np, os, sys, wave
try:
    import soundfile as sf
except ImportError:  # sem soundfile: grava WAV 24 bit com o módulo wave da biblioteca padrão
    sf = None
SR = 48000
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(7)

def t(d): return np.arange(int(d * SR)) / SR
def env_ad(n, a, d_curve=4.0):
    a = max(1, int(a * SR)); e = np.ones(n)
    e[:a] = np.linspace(0, 1, a) ** 2
    e[a:] = np.exp(-d_curve * np.linspace(0, 1, n - a))
    return e
def onepole_lp(x, fc):
    # fc pode ser array (varredura)
    fc = np.broadcast_to(fc, x.shape)
    a = np.exp(-2 * np.pi * fc / SR); y = np.zeros_like(x); s = 0.0
    for i in range(len(x)):
        s = (1 - a[i]) * x[i] + a[i] * s; y[i] = s
    return y
def bp(x, lo, hi):
    return onepole_lp(x, hi) - onepole_lp(onepole_lp(x, lo), lo)
def reverb(x, mix=0.25, size=1.0):
    n = int(SR * 1.6 * size); ir = rng.standard_normal(n) * np.exp(-np.linspace(0, 7, n))
    ir = onepole_lp(ir, 6000.0); ir /= np.sqrt((ir ** 2).sum())
    w = np.concatenate([np.convolve(x, ir), [0.0]])[: len(x) + n]
    d = np.concatenate([x, np.zeros(n)])
    return (1 - mix) * d + mix * w * 0.6
def stereo(x, width=0.3):
    d = int(0.011 * SR); r = np.concatenate([np.zeros(d), x])[: len(x)]
    return np.stack([x * (1 - width / 2) + r * width / 2, x * (1 - width / 2) + np.roll(r, d // 2) * width / 2], 1)
def save(name, x, rev=0.2, size=1.0, width=0.3):
    if rev: x = reverb(x, rev, size)
    x = stereo(x, width)
    nz = np.where(np.abs(x).max(1) > 2e-3 * np.abs(x).max())[0]; x = x[: nz[-1] + 1]
    f = int(0.02 * SR); x[-f:] *= np.linspace(1, 0, f)[:, None]
    x = x / np.abs(x).max() * 10 ** (-1 / 20)
    if sf is not None:
        sf.write(f"{OUT}/{name}.wav", x, SR, subtype="PCM_24")
    else:
        q = (np.clip(x, -1, 1) * 8388607).astype("<i4")
        raw = np.frombuffer(q.tobytes(), np.uint8).reshape(-1, 4)[:, :3].tobytes()
        with wave.open(f"{OUT}/{name}.wav", "wb") as w:
            w.setnchannels(2); w.setsampwidth(3); w.setframerate(SR); w.writeframes(raw)
    print(name, round(len(x) / SR, 2))

def bell(f0, d, ratios=(1, 2.76, 5.4, 8.93), amps=(1, .5, .25, .12), decay=5):
    tt = t(d); x = sum(a * np.sin(2 * np.pi * f0 * r * tt) * np.exp(-decay * r ** .5 * tt) for r, a in zip(ratios, amps))
    return x * env_ad(len(tt), 0.002, 0.5)

# WHOOSH (3 variações)
for k, (d, f1, f2, pk) in enumerate([(0.55, 300, 5000, .55), (0.8, 200, 3500, .6), (0.4, 600, 8000, .45)]):
    tt = t(d); n = rng.standard_normal(len(tt)); p = np.clip(tt / d, 0, 1)
    shape = np.where(p < pk, (p / pk) ** 2, np.exp(-6 * (p - pk) / (1 - pk)))
    fc = f1 + (f2 - f1) * np.sin(np.pi * np.clip(p / (pk * 2), 0, 1))
    save(f"whoosh_suave_{'abc'[k]}", bp(n, 150, fc) * shape, rev=0.15)

# BRILHO / MAGIC (3) — cascata de sininhos agudos
for k, (n_notes, base, d) in enumerate([(14, 1800, 1.4), (9, 2400, 1.1), (20, 1500, 1.8)]):
    x = np.zeros(int(d * SR) + SR)
    scale = [1, 9/8, 5/4, 3/2, 5/3, 2, 9/4, 5/2, 3]
    for i in range(n_notes):
        st = int((i / n_notes) ** 0.8 * d * 0.7 * SR)
        f = base * scale[rng.integers(len(scale))] * (1 + i / n_notes * .5)
        b = bell(f, 0.6, decay=7) * (0.4 + 0.6 * rng.random()) * (1 - 0.5 * i / n_notes)
        x[st:st + len(b)] += b
    air = bp(rng.standard_normal(len(x)), 4000, 12000) * np.exp(-np.linspace(0, 5, len(x))) * 0.15
    save(f"brilho_dourado_{'abc'[k]}", x + air, rev=0.35, size=1.3, width=0.6)

# CHIME / DING (3)
for k, (f0, d) in enumerate([(1318.5, 1.6), (1046.5, 1.8), (1568, 1.3)]):
    save(f"ding_suave_{'abc'[k]}", bell(f0, d, ratios=(1, 2, 3.01, 4.2), amps=(1, .3, .12, .05), decay=3), rev=0.3)

# NOTIFICAÇÃO 2 notas (2)
for k, (fa, fb) in enumerate([(1046.5, 1568), (1318.5, 1760)]):
    a = bell(fa, 0.5, ratios=(1, 2), amps=(1, .2), decay=6); b = bell(fb, 0.9, ratios=(1, 2), amps=(1, .2), decay=4)
    x = np.zeros(int(1.2 * SR)); x[:len(a)] += a; s = int(0.11 * SR); x[s:s + len(b)] += b
    save(f"notificacao_suave_{'ab'[k]}", x, rev=0.25)

# CLICK / TICK (3)
for k, f in enumerate([3200, 2200, 4500]):
    tt = t(0.06); x = np.sin(2 * np.pi * f * tt) * np.exp(-90 * tt) + rng.standard_normal(len(tt)) * np.exp(-300 * tt) * .3
    save(f"tick_suave_{'abc'[k]}", x, rev=0.1)

# POP (3) — bolha com pitch descendo
for k, (f1, f2, d) in enumerate([(900, 300, .09), (1300, 500, .07), (700, 220, .12)]):
    tt = t(d); f = f2 + (f1 - f2) * np.exp(-tt * 40); ph = 2 * np.pi * np.cumsum(f) / SR
    save(f"pop_suave_{'abc'[k]}", np.sin(ph) * env_ad(len(tt), 0.003, 5), rev=0.1)

# SHUTTER DE CÂMERA (2: simples e duplo)
def shutter():
    tt = t(0.09); n = bp(rng.standard_normal(len(tt)), 1500, 9000)
    c1 = n * np.exp(-120 * tt); x = np.zeros(int(0.16 * SR)); x[:len(c1)] += c1
    s = int(0.055 * SR); x[s:s + len(c1)] += 0.7 * c1 * np.exp(-30 * tt); return x
save("camera_shutter_a", shutter(), rev=0.08)
x = np.zeros(int(0.45 * SR)); s1 = shutter(); x[:len(s1)] += s1; x[int(.2 * SR):int(.2 * SR) + len(s1)] += .8 * shutter()
save("camera_shutter_b_duplo", x, rev=0.08)

# IMPACTO GRAVE SUAVE (3) — "boom" elegante, sem slam
for k, (f1, f2, d) in enumerate([(90, 42, 1.2), (70, 35, 1.6), (120, 55, 0.9)]):
    tt = t(d); f = f2 + (f1 - f2) * np.exp(-tt * 6); ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * env_ad(len(tt), 0.012, 3.5) + 0.25 * np.tanh(2 * np.sin(ph)) * np.exp(-8 * tt)
    x += bp(rng.standard_normal(len(tt)), 80, 900) * np.exp(-25 * tt) * .15
    save(f"impacto_grave_suave_{'abc'[k]}", x, rev=0.2, width=0.15)

# RISER (2) — sobe suave antes de uma revelação
for k, (d, f1, f2) in enumerate([(1.5, 300, 1200), (2.2, 200, 900)]):
    tt = t(d); p = tt / d; f = f1 * (f2 / f1) ** p; ph = 2 * np.pi * np.cumsum(f) / SR
    x = (np.sin(ph) + .5 * np.sin(2 * ph) + .3 * np.sin(1.005 * ph)) * p ** 2.2
    x += bp(rng.standard_normal(len(tt)), 500, 1000 + 7000 * p) * p ** 3 * .5
    x[-int(.03 * SR):] *= np.linspace(1, 0, int(.03 * SR))
    save(f"riser_suave_{'ab'[k]}", x, rev=0.3)

# SWELL REVERSO (2) — "inspira" antes do texto
for k, d in enumerate([1.0, 1.4]):
    tt = t(d); n = bp(rng.standard_normal(len(tt)), 2000, 10000) * np.exp(-4 * tt)
    pad = sum(np.sin(2 * np.pi * f * tt) for f in (523.25, 659.25, 783.99)) * np.exp(-3 * tt) * .2
    save(f"swell_reverso_{'ab'[k]}", reverb((n + pad), 0.3)[::-1], rev=0)

# CRISTAL / TAÇA (2)
for k, f0 in enumerate([2093, 1760]):
    save(f"cristal_{'ab'[k]}", bell(f0, 2.2, ratios=(1, 2.32, 4.25, 6.63), amps=(1, .35, .15, .07), decay=1.6), rev=0.35, width=0.5)
