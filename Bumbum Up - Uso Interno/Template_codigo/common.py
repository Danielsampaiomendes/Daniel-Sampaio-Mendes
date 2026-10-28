from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import numpy as np

W, H = 1920, 1080
BG = (18, 17, 15)
GOLD = (204, 189, 145)
GOLD2 = (184, 161, 105)
OFF = (245, 244, 241)
TXT = (205, 205, 203)
F = 'assets/Biblioteca_Fontes/ttf/'


def font(name, size, wght=None):
    f = ImageFont.truetype(F + name, size)
    if wght is not None:
        try:
            f.set_variation_by_axes([wght])
        except Exception:
            pass
    return f


def italiana(s): return font('Italiana-Regular.ttf', s)
def lora(s, w=400): return font('Lora-Italic[wght].ttf', s, w)
def jost(s, w=300): return font('Jost[wght].ttf', s, w)
def poppins(s): return font('Poppins-Light.ttf', s)
def poppinsm(s): return font('Poppins-Medium.ttf', s)
def tenor(s): return font('TenorSans-Regular.ttf', s)


CROPS = {
    'p1': [(16, 16, 630, 784), (649, 453, 1263, 1221)],
    'p2': [(16, 16, 630, 784), (649, 453, 1263, 1221)],
    'p3': [(16, 16, 630, 784), (649, 453, 1263, 1221)],
}
ANGLES = {'p1': 'PERFIL', 'p2': 'TRÊS QUARTOS', 'p3': 'POSTERIOR'}


def photos():
    out = {}
    for k, boxes in CROPS.items():
        im = Image.open('p3c.jpg' if k == 'p3' else k + '.jpg').convert('RGB')
        out[k] = [im.crop(b) for b in boxes]
    return out


def logo_parts():
    """Symbol (RGBA gold) and lettering (RGBA gold) cut from the official logo files."""
    sym = Image.open('assets/divine-simbolo-1024.png').convert('RGBA')
    sym = sym.crop(sym.getbbox())
    v = Image.open('assets/Logo_com_nome_vertical2.png').convert('RGB').crop((0, 0, 990, 990))
    a = np.array(v).astype(np.float32)
    lum = a.max(axis=2)
    alpha = np.clip((lum - 25) / (150 - 25), 0, 1)
    rgba = np.zeros((v.size[1], v.size[0], 4), np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = GOLD
    rgba[..., 3] = (alpha * 255).astype(np.uint8)
    full = Image.fromarray(rgba)
    # find the gap between symbol and lettering
    split = 630
    letter = full.crop((0, split, v.size[0], v.size[1]))
    letter = letter.crop(letter.getbbox())
    stacked = full.crop(full.getbbox())
    return sym, letter, stacked


def recolor(img, col):
    r = Image.new('RGBA', img.size, col + (0,))
    r.putalpha(img.getchannel('A'))
    return r


def horizontal_logo(height):
    sym, letter, _ = logo_parts()
    sym = recolor(sym, GOLD)
    s = sym.resize((int(sym.width * height / sym.height), height), Image.LANCZOS)
    lh = int(height * 0.62)
    l = letter.resize((int(letter.width * lh / letter.height), lh), Image.LANCZOS)
    gap = int(height * 0.35)
    out = Image.new('RGBA', (s.width + gap + l.width, height), (0, 0, 0, 0))
    out.alpha_composite(s, (0, 0))
    out.alpha_composite(l, (s.width + gap, (height - lh) // 2))
    return out


def stacked_logo(height):
    _, _, st = logo_parts()
    return st.resize((int(st.width * height / st.height), height), Image.LANCZOS)


def text_w(d, t, f, spacing=0):
    if spacing:
        return sum(d.textlength(c, font=f) for c in t) + spacing * (len(t) - 1)
    return d.textlength(t, font=f)


def draw_text(d, xy, t, f, fill, spacing=0, anchor='center'):
    """anchor center: xy is center-top"""
    x, y = xy
    w = text_w(d, t, f, spacing)
    if anchor == 'center':
        x = x - w / 2
    if spacing:
        for c in t:
            d.text((x, y), c, font=f, fill=fill)
            x += d.textlength(c, font=f) + spacing
    else:
        d.text((x, y), t, font=f, fill=fill)
    return w


def border(img, inset=28, col=GOLD2, a=160):
    lay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rectangle((inset, inset, img.width - inset - 1, img.height - inset - 1), outline=col + (a,), width=2)
    img.alpha_composite(lay)


def framed(photo, w, h):
    p = photo.copy()
    # cover fit
    s = max(w / p.width, h / p.height)
    p = p.resize((round(p.width * s), round(p.height * s)), Image.LANCZOS)
    l = (p.width - w) // 2
    t = (p.height - h) // 2
    p = p.crop((l, t, l + w, t + h)).convert('RGBA')
    out = Image.new('RGBA', (w + 8, h + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    d.rectangle((0, 0, w + 7, h + 7), outline=GOLD + (230,), width=1)
    out.alpha_composite(p, (4, 4))
    return out


RT = 'Responsável técnico: Dr. Daniel Mendes  ·  CRM/SP 186.470  ·  RQE 105302  ·  RQE 130995'
DISC = 'Resultados variam de pessoa para pessoa.  Imagens de paciente, com autorização.  Uso exclusivo em consulta.'
