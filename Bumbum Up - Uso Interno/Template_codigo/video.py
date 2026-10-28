import subprocess, sys
from common import *
from static import grid_layer, header_layer, footer_layer

FPS = 30


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def ramp(t, a, b):
    return ease((t - a) / (b - a)) if b > a else float(t >= a)


def with_alpha(img, a):
    if a >= 0.999:
        return img
    im = img.copy()
    al = im.getchannel('A').point(lambda v: int(v * a))
    im.putalpha(al)
    return im


def base_bg():
    img = Image.new('RGBA', (W, H), BG + (255,))
    glow = Image.new('L', (W, H), 0)
    ImageDraw.Draw(glow).ellipse((560, -260, 1360, 420), fill=40)
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    img.paste(Image.new('RGBA', (W, H), GOLD2 + (255,)), (0, 0), glow)
    border(img)
    return img


BGIMG = base_bg()


def text_layer(runs_lines, y0, line_gap=14):
    """runs_lines: list of lines, each line list of (text, font, color, spacing)"""
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    y = y0
    for runs in runs_lines:
        widths = [text_w(d, t, f, sp) for t, f, c, sp in runs]
        x = (W - sum(widths)) / 2
        hmax = max(f.getbbox('ÀgyÊ')[3] for t, f, c, sp in runs)
        for (t, f, c, sp), w in zip(runs, widths):
            draw_text(d, (x, y + (hmax - f.getbbox('ÀgyÊ')[3])), t, f, c, spacing=sp, anchor='left')
            x += w
        y += hmax + line_gap
    return lay


class Writer:
    def __init__(self, path):
        self.p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                                   '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium',
                                   '-crf', '16', '-pix_fmt', 'yuv420p', path], stdin=subprocess.PIPE)

    def put(self, img):
        self.p.stdin.write(img.convert('RGB').tobytes())

    def close(self):
        self.p.stdin.close(); self.p.wait()


# ---------------- hooks ----------------
def hook_layers(v):
    if v == 1:
        a = text_layer([[('Nem tudo se resolve', italiana(92), OFF, 0)],
                        [('no agachamento.', italiana(92), OFF, 0)]], 360)
        b = text_layer([[('Às vezes falta ', lora(58), TXT, 0), ('sustentação.', lora(58, 600), GOLD, 0)]], 640)
    elif v == 2:
        a = text_layer([[('É ASSIM QUE FUNCIONA', tenor(64), OFF, 6)]], 380)
        b = text_layer([[('o ', tenor(64), OFF, 0), ('sutiã', lora(82, 500), GOLD, 0), (' do bumbum:', tenor(64), OFF, 0)]], 500)
    else:
        a = text_layer([[('Cada corpo responde', italiana(92), OFF, 0)],
                        [('no seu tempo.', italiana(92), GOLD, 0)]], 350)
        b = text_layer([[('ESTE FOI O DELA.', jost(40, 300), TXT, 10)]], 660)
    return a, b


def render_hook(v, path, dur=4.6):
    a, b = hook_layers(v)
    w = Writer(path)
    n = int(dur * FPS)
    for i in range(n):
        t = i / FPS
        f = BGIMG.copy()
        out = 1 - ramp(t, dur - 0.55, dur)
        f.alpha_composite(with_alpha(a, ramp(t, 0.3, 1.3) * out))
        f.alpha_composite(with_alpha(b, ramp(t, 1.7, 2.7) * out))
        w.put(f)
    w.close()


# ---------------- body ----------------
def render_body(path):
    ph = photos()
    w = Writer(path)
    small_logo = horizontal_logo(52)
    top = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    top.alpha_composite(small_logo, ((W - small_logo.width) // 2, 56))
    foot = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(foot)
    draw_text(ImageDraw.Draw(foot), (W / 2, 1002), 'Resultados variam de pessoa para pessoa.   ' + RT, poppins(16), (150, 148, 140))

    # 1) title card
    lg = horizontal_logo(84)
    title = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    title.alpha_composite(lg, ((W - lg.width) // 2, 300))
    t1 = text_layer([[('Bumbum Up', italiana(140), OFF, 0)]], 420)
    t2 = text_layer([[('bioestimulação glútea', lora(46), GOLD, 0)]], 600)
    t3 = text_layer([[('ESTÍMULO DE COLÁGENO  ·  FIRMEZA  ·  SUSTENTAÇÃO', jost(24, 300), TXT, 6)]], 690)
    dur = 4.2
    for i in range(int(dur * FPS)):
        t = i / FPS
        out = 1 - ramp(t, dur - 0.5, dur)
        f = BGIMG.copy()
        f.alpha_composite(with_alpha(title, ramp(t, 0.0, 0.9) * out))
        f.alpha_composite(with_alpha(t1, ramp(t, 0.3, 1.3) * out))
        f.alpha_composite(with_alpha(t2, ramp(t, 0.9, 1.9) * out))
        f.alpha_composite(with_alpha(t3, ramp(t, 1.4, 2.4) * out))
        f.alpha_composite(with_alpha(foot, ramp(t, 1.4, 2.4) * out))
        w.put(f)

    # 2) each angle
    pw, phh, gap = 560, 700, 44
    x0 = (W - (2 * pw + gap)) // 2
    y0 = 214
    for k in ['p1', 'p2', 'p3']:
        b, a = ph[k]
        ang = text_layer([[(ANGLES[k], tenor(30), OFF, 8)]], 150)
        labA = text_layer([[('ANTES', jost(22, 400), TXT, 7)]], 926)
        labD = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        draw_text(ImageDraw.Draw(labA), (x0 + pw / 2, 0), '', jost(10), TXT)
        la = Image.new('RGBA', (W, H), (0, 0, 0, 0)); draw_text(ImageDraw.Draw(la), (x0 + pw / 2 + 4, 928), 'ANTES', jost(22, 400), TXT, spacing=7)
        ld = Image.new('RGBA', (W, H), (0, 0, 0, 0)); draw_text(ImageDraw.Draw(ld), (x0 + pw + gap + pw / 2 + 4, 928), 'DEPOIS', jost(22, 500), GOLD, spacing=7)
        dur = 6.6
        boxes = [framed(b, pw, phh), framed(a, pw, phh)]
        for i in range(int(dur * FPS)):
            t = i / FPS
            out = 1 - ramp(t, dur - 0.5, dur)
            f = BGIMG.copy()
            f.alpha_composite(with_alpha(top, out))
            f.alpha_composite(with_alpha(foot, out))
            f.alpha_composite(with_alpha(ang, ramp(t, 0.1, 0.9) * out))
            for j, (img, start, lab) in enumerate([(b, 0.2, la), (a, 1.9, ld)]):
                al = ramp(t, start, start + 1.0) * out
                if al <= 0:
                    continue
                box = boxes[j]
                slide = int(18 * (1 - ramp(t, start, start + 1.0))) if j == 1 else 0
                px = x0 + j * (pw + gap) + slide
                lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
                lay.alpha_composite(box, (px, y0))
                f.alpha_composite(with_alpha(lay, al))
                f.alpha_composite(with_alpha(lab, al))
            w.put(f)

    # 3) grid (static layout)
    hdr, grd, ftr = header_layer(), grid_layer(ph), footer_layer()
    dur = 6.4
    for i in range(int(dur * FPS)):
        t = i / FPS
        out = 1 - ramp(t, dur - 0.5, dur)
        f = BGIMG.copy()
        f.alpha_composite(with_alpha(hdr, ramp(t, 0.0, 0.9) * out))
        f.alpha_composite(with_alpha(grd, ramp(t, 0.5, 1.6) * out))
        f.alpha_composite(with_alpha(ftr, ramp(t, 1.2, 2.2) * out))
        w.put(f)

    # 4) closing
    st = stacked_logo(300)
    cl = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    cl.alpha_composite(st, ((W - st.width) // 2, 170))
    c1 = text_layer([[('Agende sua avaliação', lora(52, 500), GOLD, 0)]], 540)
    c2 = text_layer([[('cada protocolo é individualizado em consulta', lora(30), TXT, 0)]], 625)
    c3 = text_layer([[('AV. PAULISTA 1636  ·  AO LADO DO MASP', jost(24, 300), OFF, 6)]], 720)
    c4 = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d4 = ImageDraw.Draw(c4)
    draw_text(d4, (W / 2, 960), 'Resultados variam de pessoa para pessoa.', poppins(19), TXT)
    draw_text(d4, (W / 2, 994), RT, poppins(17), (150, 148, 140))
    dur = 5.6
    for i in range(int(dur * FPS)):
        t = i / FPS
        f = BGIMG.copy()
        f.alpha_composite(with_alpha(cl, ramp(t, 0.0, 1.2)))
        f.alpha_composite(with_alpha(c1, ramp(t, 0.8, 1.8)))
        f.alpha_composite(with_alpha(c2, ramp(t, 1.3, 2.3)))
        f.alpha_composite(with_alpha(c3, ramp(t, 1.8, 2.8)))
        f.alpha_composite(with_alpha(c4, ramp(t, 1.8, 2.8)))
        w.put(f)
    w.close()


if __name__ == '__main__':
    what = sys.argv[1]
    if what == 'body':
        render_body('seg_body.mp4')
    else:
        render_hook(int(what), f'seg_hook{what}.mp4')
