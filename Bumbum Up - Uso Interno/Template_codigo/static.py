from common import *


def grid_layer(ph, pw=274, phh=343):
    """returns RGBA full-frame layer with the 3 pairs; photos start y=330"""
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    gap_in, gap_out = 12, 40
    pair_w = 2 * (pw + 8) + gap_in
    total = 3 * pair_w + 2 * gap_out
    x = (W - total) // 2
    y = 410
    lab = jost(19, 400)
    ang = tenor(22)
    for k in ['p1', 'p2', 'p3']:
        b, a = ph[k]
        for i, (img, t) in enumerate([(b, 'ANTES'), (a, 'DEPOIS')]):
            px = x + i * (pw + 8 + gap_in)
            draw_text(d, (px + (pw + 8) / 2, y - 34), t, lab, GOLD if i else TXT, spacing=6)
            lay.alpha_composite(framed(img, pw, phh), (px, y))
        cx = x + pair_w / 2
        yy = y + phh + 30
        d.line((cx - 60, yy, cx + 60, yy), fill=GOLD2 + (200,), width=1)
        draw_text(d, (cx, yy + 14), ANGLES[k], ang, OFF, spacing=5)
        x += pair_w + gap_out
    return lay


def header_layer():
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    lg = horizontal_logo(70)
    lay.alpha_composite(lg, ((W - lg.width) // 2, 62))
    d = ImageDraw.Draw(lay)
    draw_text(d, (W / 2, 156), 'Bumbum Up', italiana(96), OFF)
    draw_text(d, (W / 2, 262), 'bioestimulação glútea para mais firmeza e sustentação', lora(30), GOLD)
    return lay


def footer_layer():
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    draw_text(d, (W / 2, 912), 'Agende sua avaliação', lora(34, 500), GOLD)
    draw_text(d, (W / 2, 972), DISC, poppins(19), TXT)
    draw_text(d, (W / 2, 1004), RT, poppins(17), (150, 148, 140))
    return lay


if __name__ == '__main__':
    ph = photos()
    img = Image.new('RGBA', (W, H), BG + (255,))
    # soft warm vignette glow behind title
    glow = Image.new('L', (W, H), 0)
    ImageDraw.Draw(glow).ellipse((560, -260, 1360, 420), fill=40)
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    img.paste(Image.new('RGBA', (W, H), GOLD2 + (255,)), (0, 0), glow)
    img.alpha_composite(header_layer())
    img.alpha_composite(grid_layer(ph))
    img.alpha_composite(footer_layer())
    border(img)
    img.convert('RGB').save('TV_BumbumUp_Estatico.png')
    img.convert('RGB').resize((960, 540)).save('/tmp/claude-0/prev.png')
