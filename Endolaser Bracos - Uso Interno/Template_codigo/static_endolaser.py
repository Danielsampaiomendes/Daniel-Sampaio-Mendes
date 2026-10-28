from common import *

PW, PH = 384, 396  # box for every photo (same size and proportion)

# (file, box) for antes/depois of each case, cut on the original seam
CASES = [
    ('b1.jpg', (0, 0, 384, 405), (385, 0, 742, 405)),
    ('b2.jpg', (0, 0, 377, 361), (380, 0, 768, 361)),
]


def fit(im, w, h):
    # cover fit with the smallest possible trim, centered
    s = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    l, t = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((l, t, l + w, t + h))


def frame(p):
    out = Image.new('RGBA', (PW + 8, PH + 8), (0, 0, 0, 0))
    ImageDraw.Draw(out).rectangle((0, 0, PW + 7, PH + 7), outline=GOLD + (230,), width=1)
    out.alpha_composite(p.convert('RGBA'), (4, 4))
    return out


img = Image.new('RGBA', (W, H), BG + (255,))
glow = Image.new('L', (W, H), 0)
ImageDraw.Draw(glow).ellipse((560, -260, 1360, 420), fill=40)
glow = glow.filter(ImageFilter.GaussianBlur(160))
img.paste(Image.new('RGBA', (W, H), GOLD2 + (255,)), (0, 0), glow)

d = ImageDraw.Draw(img)
lg = horizontal_logo(70)
img.alpha_composite(lg, ((W - lg.width) // 2, 62))
draw_text(d, (W / 2, 156), 'Endolaser', italiana(96), OFF)
draw_text(d, (W / 2, 262), 'tecnologia para flacidez e gordura localizada nos braços', lora(30), GOLD)

gap_in, gap_out = 12, 70
pair_w = 2 * (PW + 8) + gap_in
x = (W - (2 * pair_w + gap_out)) // 2
y = 392
lab = jost(19, 400)
for f, bb, ab in CASES:
    src = Image.open(f).convert('RGB')
    for i, (box, t) in enumerate([(bb, 'ANTES'), (ab, 'DEPOIS')]):
        px = x + i * (PW + 8 + gap_in)
        draw_text(d, (px + (PW + 8) / 2, y - 36), t, lab, GOLD if i else TXT, spacing=6)
        img.alpha_composite(frame(fit(src.crop(box), PW, PH)), (px, y))
    x += pair_w + gap_out
# fine gold divider between the two cases
cx = (W - gap_out) // 2 + gap_out // 2
d.line((W // 2, y + 40, W // 2, y + PH - 32), fill=GOLD2, width=1)

draw_text(d, (W / 2, 846), 'Cada braço responde no seu tempo.', lora(30), OFF)
draw_text(d, (W / 2, 900), 'Agende sua avaliação', lora(34, 500), GOLD)
draw_text(d, (W / 2, 966), DISC, poppins(19), TXT)
draw_text(d, (W / 2, 1000), RT, poppins(17), (150, 148, 140))
border(img)
img.convert('RGB').save('TV_Endolaser_Bracos_Estatico.png')
