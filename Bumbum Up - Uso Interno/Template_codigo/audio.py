import numpy as np, wave, sys

SR = 48000


def readwav(p):
    w = wave.open(p)
    n, ch, sw, sr = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
    raw = w.readframes(n)
    dt = {2: np.int16, 4: np.int32}[sw]
    a = np.frombuffer(raw, dt).astype(np.float32) / np.iinfo(dt).max
    a = a.reshape(-1, ch).mean(1)
    if sr != SR:
        x = np.linspace(0, len(a) - 1, int(len(a) * SR / sr))
        a = np.interp(x, np.arange(len(a)), a)
    return a


def pad(total, seed):
    t = np.arange(int(total * SR)) / SR
    out = np.zeros_like(t)
    # slow lounge chord progression (Fmaj9 / Dm9 / Bbmaj7 / C6), 6.4 s each
    chords = [[174.6, 220.0, 261.6, 329.6, 392.0], [146.8, 174.6, 220.0, 261.6, 329.6],
              [116.5, 146.8, 174.6, 220.0, 293.7], [130.8, 164.8, 196.0, 220.0, 329.6]]
    seg = 6.4
    rng = np.random.default_rng(seed)
    for i in range(int(total / seg) + 1):
        c = chords[i % 4]
        s0 = i * seg
        idx = (t >= s0 - 0.8) & (t < s0 + seg + 1.2)
        tt = t[idx] - s0
        env = np.clip((tt + 0.8) / 1.6, 0, 1) * np.clip((seg + 1.2 - tt) / 1.6, 0, 1)
        sig = 0
        for f in c:
            ph = rng.uniform(0, 6.28)
            sig = sig + np.sin(2 * np.pi * f * tt + ph) * 0.6 + np.sin(2 * np.pi * f * 2.003 * tt + ph) * 0.12
        out[idx] += sig * env / len(c)
    # gentle tremolo + soft pluck notes
    out *= 0.85 + 0.15 * np.sin(2 * np.pi * 0.25 * t)
    notes = [523.3, 587.3, 659.3, 784.0, 880.0]
    for k, s in enumerate(np.arange(1.0, total - 2, 1.6)):
        f = notes[(k * 3) % 5]
        idx = (t >= s) & (t < s + 1.5)
        tt = t[idx] - s
        out[idx] += 0.10 * np.sin(2 * np.pi * f * tt) * np.exp(-tt * 3.0)
    # fade in/out
    out *= np.clip(t / 1.5, 0, 1) * np.clip((total - t) / 2.0, 0, 1)
    return out


def place(buf, clip, at, gain_db):
    i = int(at * SR)
    c = clip * (10 ** (gain_db / 20))
    e = min(len(buf), i + len(c))
    buf[i:e] += c[:e - i]


if __name__ == '__main__':
    hook = 4.6
    total = float(sys.argv[1])
    out_path = sys.argv[2]
    S = 'assets/Biblioteca_SFX/1_kit_original_divine/'
    wh = readwav(S + 'whoosh_suave_a.wav')
    br = readwav(S + 'brilho_dourado_b.wav')
    cr = readwav(S + 'cristal_a.wav')
    sw = readwav(S + 'swell_reverso_a.wav')
    buf = pad(total, 7)
    buf = buf / (np.abs(buf).max() + 1e-9) * 0.22
    sfx = np.zeros_like(buf)
    place(sfx, br, hook + 0.3, -24)                      # title
    t0 = hook + 4.2
    for k in range(3):
        place(sfx, wh, t0 + k * 6.6 + 1.85, -27)          # "depois" entering
    place(sfx, cr, t0 + 3 * 6.6 + 0.4, -27)               # grid
    place(sfx, sw, t0 + 3 * 6.6 + 6.4 - 1.6, -30)         # swell into close
    place(sfx, br, t0 + 3 * 6.6 + 6.4 + 0.2, -25)         # logo
    mix = buf + sfx
    mix = np.clip(mix, -0.98, 0.98)
    st = np.stack([mix, mix], 1)
    w = wave.open(out_path, 'wb')
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st * 32767).astype(np.int16).tobytes())
    w.close()
