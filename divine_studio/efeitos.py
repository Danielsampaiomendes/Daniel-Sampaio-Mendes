"""Efeitos cinéticos EC/EV na versão suave Divine (docs/CONHECIMENTO_DIVINE.md, seção 11).

Cada efeito vira camadas animadas (overlay RGBA com alfa) ou um efeito no próprio quadro (zoom, PiP, vidro,
texto atrás da pessoa). Easing cubic in-out, cores e fontes da marca, nada piscando.
Regra: no máximo um efeito a cada 1,5 a 2 s (efeitos muito próximos são empurrados, com aviso).

No projeto.yaml (vale para todas as versões) ou dentro de uma versão:
  efeitos:
    - {tipo: riscado, inicio: 1.0, texto: "“Vou deixar para depois.”", virada: "Vou começar *agora.*"}
    - {tipo: contador, inicio: 6, de: 1, ate: 90, prefixo: "DIA "}
    - {tipo: checklist, inicio: 9, titulo: "Quantos desses *você tem?*", itens: [a, b, c]}
    - {tipo: circulo, inicio: 12, ponto: [0.5, 0.55], texto: "*Spoiler:* é a mira"}
Códigos EC/EV aceitos no lugar de tipo (ex.: codigo: EC06); a tabela fica em config/efeitos.yaml.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .anim import clamp, ease_in_out, ease_out
from .compositor import Camada, CamadaAnimada
from .config import cor, load
from .fonts import marca
from .text import SS, Estilo, render


def _cfg() -> dict:
    return load("efeitos")


def _y(ef: dict, H: int, padrao: float = 0.47) -> float:
    pos = ef.get("posicao", padrao)
    if isinstance(pos, str):
        pos = {"topo": 0.30, "centro": 0.47, "base": 0.62}.get(pos, padrao)
    return H * float(pos)


def _estilos(combo: dict, tam: float):
    return (Estilo.de_config(combo["titulo"], tam, cor("off_white")),
            Estilo.de_config(combo["destaque"], tam, cor("dourado")))


def _card(w: int, h: int, fundo: str = "fundo", alfa: int = 215, raio: int = 34, borda: bool = True) -> Image.Image:
    img = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((2, 2, w * 2 - 3, h * 2 - 3), radius=raio * 2, fill=cor(fundo) + (alfa,),
                                          outline=(cor("dourado_escuro") + (220,)) if borda else None, width=3)
    return img.resize((w, h), Image.LANCZOS)


def _cola(base: Image.Image, img: Image.Image, x: float, y: float, opacidade: float = 1.0) -> None:
    if opacidade <= 0.003:
        return
    if opacidade < 1:
        img = img.copy()
        img.putalpha(img.getchannel("A").point(lambda v: int(v * opacidade)))
    base.alpha_composite(img, (int(x), int(y)))


# ---------------------------------------------------------------- texto animado

def _letras(texto: str, estilo: Estilo, destaque: Estilo):
    """Letras renderizadas uma a uma (imagem, avanço) respeitando *destaque*."""
    out, dest = [], False
    for ch in texto:
        if ch == "*":
            dest = not dest
            continue
        e = destaque if dest else estilo
        f = e.font()
        s = ch.upper() if e.caixa_alta else ch
        w = max(1, int(f.getlength(s)))
        asc, desc = f.getmetrics()
        img = Image.new("RGBA", (w + 4, asc + desc + 4), (0, 0, 0, 0))
        ImageDraw.Draw(img).text((2, 2 + asc), s, font=f, fill=e.cor + (255,), anchor="ls")
        img = img.resize((max(1, img.width // SS), max(1, img.height // SS)), Image.LANCZOS)
        out.append((img, f.getlength(s) / SS + e.tracking * e.tamanho))
    return out


def letra_a_letra(ef, combo, W, H, fps, queda=False):
    """EC16 (sobe letra a letra) e EC02 (queda livre suave): cada letra entra com atraso e assenta."""
    tam = float(ef.get("tamanho", 96)) * W / 1080
    e, d = _estilos(combo, tam)
    letras = _letras(ef["texto"], e, d)
    larg = int(sum(a for _, a in letras)) + 20
    alt = max(i.height for i, _ in letras) + int(tam * 0.9)
    dur = float(ef.get("duracao", 3.0))
    passo = min(0.06, 1.0 / max(1, len(letras)))
    sobe = tam * (0.9 if queda else 0.45) * (-1 if queda else 1)

    def ger(t):
        img = Image.new("RGBA", (larg, alt), (0, 0, 0, 0))
        x = 10
        for k, (li, av) in enumerate(letras):
            p = ease_out(clamp((t - k * passo) / 0.55))
            _cola(img, li, x, int(tam * 0.45) + (1 - p) * sobe, p)
            x += av
        return img
    y = int(_y(ef, H) - alt / 2)
    return [CamadaAnimada(ger, larg, alt, (W - larg) // 2, y, ef["inicio"], ef["inicio"] + dur, fps, 0.01, 0.6,
                          nome=f"ef_{ef['tipo']}", texto=ef["texto"])]


def camadas_cineticas(ef, combo, W, H, fps):
    """EC01 gancho cinético em camadas: palavras entram uma a uma com escala suave, em linhas."""
    tam = float(ef.get("tamanho", 92)) * W / 1080
    e, d = _estilos(combo, tam)
    # cada palavra sem a margem da sombra, para o espaçamento ficar o de uma frase normal
    palavras = []
    dest = False
    for p in ef["texto"].split():
        marcado = ("*" if dest else "") + p
        dest = dest ^ (p.count("*") % 2 == 1)
        im = render(marcado, e, d, sombra=False)
        palavras.append(im.crop(im.getbbox()))
    esp = int(tam * 0.26)
    linhas, atual, larg_max = [], [], W * 0.82
    for p in palavras:
        if atual and sum(i.width + esp for i in atual) + p.width > larg_max:
            linhas.append(atual)
            atual = []
        atual.append(p)
    linhas.append(atual)
    larg = int(max(sum(i.width + esp for i in ln) for ln in linhas)) + 20
    alt_l = int(tam * 1.15)
    alt = int(alt_l * len(linhas) + alt_l * 0.3)
    dur = float(ef.get("duracao", 3.0))

    def ger(t):
        img = Image.new("RGBA", (larg, alt), (0, 0, 0, 0))
        k = 0
        for li, ln in enumerate(linhas):
            x = (larg - sum(i.width + esp for i in ln) + esp) / 2
            for p in ln:
                pr = ease_out(clamp((t - k * 0.22) / 0.6))
                s = 0.86 + 0.14 * pr
                im = p.resize((max(1, int(p.width * s)), max(1, int(p.height * s))), Image.LANCZOS)
                _cola(img, im, x + (p.width - im.width) / 2, li * alt_l + alt_l - p.height + (p.height - im.height) / 2, pr)
                x += p.width + esp
                k += 1
        from .text import com_sombra
        return com_sombra(img, raio=max(2, int(tam * 0.07)), dy=1).resize((larg, alt), Image.LANCZOS)
    y = int(_y(ef, H, 0.30) - alt / 2)
    return [CamadaAnimada(ger, larg, alt, (W - larg) // 2, y, ef["inicio"], ef["inicio"] + dur, fps, 0.01, 0.6,
                          nome="ef_camadas", texto=ef["texto"])]


def riscado(ef, combo, W, H, fps):
    """EC06 / crença riscada: a frase aparece, um traço dourado risca da esquerda para a direita, a virada entra."""
    tam = float(ef.get("tamanho", 80)) * W / 1080
    e, d = _estilos(combo, tam)
    frase = render(ef["texto"], e, d)
    dur = float(ef.get("duracao", 3.6))
    t_risco = float(ef.get("riscar_em", 0.9))
    alt = frase.height + int(tam * 0.2)

    def ger(t):
        img = Image.new("RGBA", (frase.width, alt), (0, 0, 0, 0))
        apaga = 1 - 0.45 * ease_in_out(clamp((t - t_risco - 0.5) / 0.6))
        _cola(img, frase, 0, 0, apaga)
        p = ease_in_out(clamp((t - t_risco) / 0.6))
        if p > 0:
            dr = ImageDraw.Draw(img)
            y = frase.height * 0.52
            dr.line([(frase.width * 0.06, y), (frase.width * (0.06 + 0.88 * p), y - tam * 0.05)],
                    fill=cor("dourado") + (255,), width=max(3, int(tam * 0.06)))
        return img
    y = int(_y(ef, H, 0.30) - alt / 2)
    out = [CamadaAnimada(ger, frase.width, alt, (W - frase.width) // 2, y, ef["inicio"], ef["inicio"] + dur, fps,
                         0.7, 0.6, nome="ef_riscado", texto=ef["texto"])]
    if ef.get("virada"):
        iv = render(ef["virada"], e, d)
        out.append(Camada(iv, (W - iv.width) // 2, y + alt, ef["inicio"] + t_risco + 0.7, ef["inicio"] + dur,
                          entrada=0.8, saida=0.6, deslize=24, nome="ef_riscado_virada", texto=ef["virada"]))
    return out


def digitando(ef, combo, W, H, fps):
    """EC04/EC15 barra de mensagem digitando (nunca pedindo palavra): texto letra a letra com cursor."""
    escala = W / 1080
    txt = ef["texto"]
    e = Estilo(marca("pill"), 36 * escala, cor("off_white"))
    larg = int(min(W * 0.84, 900 * escala))
    alt = int(96 * escala)
    dur = float(ef.get("duracao", max(3.0, len(txt) * 0.06 + 1.6)))
    velocidade = float(ef.get("letras_por_s", 18))
    fundo = _card(larg, alt, "fundo", 205, alt // 2)
    rotulo = ef.get("rotulo", "Mensagem")

    def ger(t):
        img = fundo.copy()
        n = int(clamp(t - 0.3, 0, 99) * velocidade)
        parcial = txt[:n]
        cursor = "|" if (int(t * 2) % 2 == 0 or n < len(txt)) else " "
        it = render(parcial + cursor if parcial else (rotulo + "…" if n == 0 else cursor), e if parcial else
                    Estilo(marca("pill"), 36 * escala, cor("rodape")), largura_max=larg - 120 * escala, sombra=False,
                    alinhamento="left")
        img.alpha_composite(it, (int(40 * escala), (alt - it.height) // 2))
        dr = ImageDraw.Draw(img)
        r = alt * 0.32
        cx, cy = larg - alt * 0.55, alt / 2
        dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=cor("dourado") + (255,))
        dr.polygon([(cx - r * 0.35, cy - r * 0.45), (cx + r * 0.5, cy), (cx - r * 0.35, cy + r * 0.45)],
                   fill=cor("fundo") + (255,))
        return img
    y = int(_y(ef, H, 0.62) - alt / 2)
    return [CamadaAnimada(ger, larg, alt, (W - larg) // 2, y, ef["inicio"], ef["inicio"] + dur, fps, 0.6, 0.5,
                          nome="ef_digitando", texto=txt)]


# ---------------------------------------------------------------- cards e listas

def checklist(ef, combo, W, H, fps):
    """EV06/EV07 painel de checklist: título e itens entrando um a um, cada um ganhando o visto dourado."""
    escala = W / 1080
    e, d = _estilos(combo, 62 * escala)
    tit = render(ef.get("titulo", ""), e, d, largura_max=820 * escala) if ef.get("titulo") else None
    ei = Estilo(marca("pill"), 34 * escala, cor("off_white"))
    eid = Estilo(marca("pill"), 34 * escala, cor("dourado"))
    itens = [render(i, ei, eid, largura_max=700 * escala, sombra=False, alinhamento="left") for i in ef["itens"]]
    larg = int(880 * escala)
    gap = int(22 * escala)
    caixa = int(40 * escala)
    alt = (tit.height + gap if tit else 0) + sum(max(i.height, caixa) + gap for i in itens) + int(50 * escala)
    fundo = _card(larg, alt, "fundo", 200)
    passo = float(ef.get("intervalo", 0.9))
    dur = float(ef.get("duracao", 1.2 + passo * len(itens) + 1.6))

    def ger(t):
        img = fundo.copy()
        y = int(28 * escala)
        if tit:
            img.alpha_composite(tit, ((larg - tit.width) // 2, y))
            y += tit.height + gap
        for k, it in enumerate(itens):
            ti = 0.6 + k * passo
            p = ease_out(clamp((t - ti) / 0.5))
            h = max(it.height, caixa)
            x0 = int(50 * escala)
            dr = ImageDraw.Draw(img)
            if p > 0:
                a = int(255 * p)
                dr.rounded_rectangle((x0, y + (h - caixa) // 2, x0 + caixa, y + (h + caixa) // 2), radius=caixa // 4,
                                     outline=cor("dourado") + (a,), width=max(2, int(3 * escala)))
                _cola(img, it, x0 + caixa + 22 * escala, y + (h - it.height) // 2, p)
            v = ease_in_out(clamp((t - ti - 0.45) / 0.35))
            if v > 0:
                cx, cy = x0, y + (h - caixa) // 2
                pts = [(cx + caixa * 0.2, cy + caixa * 0.52), (cx + caixa * 0.42, cy + caixa * 0.74),
                       (cx + caixa * 0.82, cy + caixa * 0.26)]
                if v < 0.5:
                    seg = [pts[0], (pts[0][0] + (pts[1][0] - pts[0][0]) * v * 2, pts[0][1] + (pts[1][1] - pts[0][1]) * v * 2)]
                else:
                    q = (v - 0.5) * 2
                    seg = [pts[0], pts[1], (pts[1][0] + (pts[2][0] - pts[1][0]) * q, pts[1][1] + (pts[2][1] - pts[1][1]) * q)]
                dr.line(seg, fill=cor("dourado") + (255,), width=max(3, int(5 * escala)), joint="curve")
            y += h + gap
        return img
    y = int(_y(ef, H) - alt / 2)
    textos = " ".join([ef.get("titulo", "")] + list(ef["itens"]))
    return [CamadaAnimada(ger, larg, alt, (W - larg) // 2, y, ef["inicio"], ef["inicio"] + dur, fps, 0.7, 0.6,
                          nome="ef_checklist", texto=textos)]


def contador(ef, combo, W, H, fps):
    """Contador suave (DIA 1 → DIA 90, 0 → 12 TESLA): o número rola com easing e assenta."""
    escala = W / 1080
    de, ate = float(ef.get("de", 0)), float(ef.get("ate", 10))
    dec = int(ef.get("casas", 0))
    pre, suf = ef.get("prefixo", ""), ef.get("sufixo", "")
    tam = float(ef.get("tamanho", 150)) * escala
    e, d = _estilos(combo, tam)
    rot = ef.get("rotulo")
    ir = render(rot, Estilo(marca("rotulo"), 30 * escala, cor("dourado"), caixa_alta=True, tracking=0.3),
                sombra=True) if rot else None
    amostra = render(f"{pre}*{ate:.{dec}f}*{suf}", e, d)
    larg, alt = amostra.width + int(80 * escala), amostra.height + (ir.height if ir else 0) + int(20 * escala)
    dur = float(ef.get("duracao", 3.2))
    rolar = float(ef.get("rolar_s", 1.8))

    def ger(t):
        img = Image.new("RGBA", (larg, alt), (0, 0, 0, 0))
        v = de + (ate - de) * ease_in_out(clamp((t - 0.2) / rolar))
        im = render(f"{pre}*{v:.{dec}f}*{suf}", e, d)
        img.alpha_composite(im, ((larg - im.width) // 2, 0))
        if ir:
            img.alpha_composite(ir, ((larg - ir.width) // 2, im.height - int(10 * escala)))
        return img
    y = int(_y(ef, H) - alt / 2)
    return [CamadaAnimada(ger, larg, alt, (W - larg) // 2, y, ef["inicio"], ef["inicio"] + dur, fps, 0.6, 0.6,
                          nome="ef_contador", texto=f"{pre}{ate:.{dec}f}{suf} {rot or ''}")]


def linha_tempo(ef, combo, W, H, fps):
    """EC08 / C-H75: linha dourada se desenhando com marcos (OUT, NOV, DEZ) que acendem em sequência."""
    escala = W / 1080
    marcos = ef["marcos"]
    larg, alt = int(860 * escala), int(170 * escala)
    em = Estilo(marca("rotulo"), 30 * escala, cor("off_white"), caixa_alta=True, tracking=0.2)
    emd = Estilo(marca("rotulo"), 30 * escala, cor("dourado"), caixa_alta=True, tracking=0.2)
    rots = [render(m, em, emd, sombra=True) for m in marcos]
    dur = float(ef.get("duracao", 3.6))
    desenho = float(ef.get("desenhar_s", 2.0))

    def ger(t):
        img = Image.new("RGBA", (larg * 2, alt * 2), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        p = ease_in_out(clamp((t - 0.2) / desenho))
        y = alt * 0.45 * 2
        x0, x1 = 40 * escala * 2, (larg - 40 * escala) * 2
        dr.line([(x0, y), (x0 + (x1 - x0) * p, y)], fill=cor("dourado") + (255,), width=int(4 * escala * 2))
        img = img.resize((larg, alt), Image.LANCZOS)
        dr = ImageDraw.Draw(img)
        for k, r in enumerate(rots):
            pos = k / max(1, len(rots) - 1)
            if p + 1e-6 >= pos:
                q = ease_out(clamp((p - pos) * 6 + 0.01))
                cx = 40 * escala + (larg - 80 * escala) * pos
                rr = 9 * escala * q
                dr.ellipse((cx - rr, alt * 0.45 - rr, cx + rr, alt * 0.45 + rr), fill=cor("dourado") + (255,))
                _cola(img, r, cx - r.width / 2, alt * 0.45 + 20 * escala, q)
        return img
    y = int(_y(ef, H) - alt / 2)
    return [CamadaAnimada(ger, larg, alt, (W - larg) // 2, y, ef["inicio"], ef["inicio"] + dur, fps, 0.5, 0.6,
                          nome="ef_linha_tempo", texto=" ".join(marcos))]


def circulo(ef, combo, W, H, fps):
    """A-H19/H21, EV14: círculo (ou rabisco) dourado se desenhando sobre um detalhe + texto opcional (Spoiler)."""
    escala = W / 1080
    px, py = ef.get("ponto", [0.5, 0.5])
    r = float(ef.get("raio", 120)) * escala
    lado = int(r * 2 + 40 * escala)
    dur = float(ef.get("duracao", 3.0))
    desenho = float(ef.get("desenhar_s", 0.8))
    giro = float(ef.get("inicio_angulo", -100))

    def ger(t):
        img = Image.new("RGBA", (lado * 2, lado * 2), (0, 0, 0, 0))
        p = ease_in_out(clamp((t - 0.1) / desenho))
        if p > 0:
            ImageDraw.Draw(img).arc((40 * escala, 40 * escala, lado * 2 - 40 * escala, lado * 2 - 40 * escala),
                                    giro, giro + 362 * p, fill=cor("dourado") + (255,), width=int(7 * escala * 2))
            img = img.filter(ImageFilter.GaussianBlur(0.6))
        return img.resize((lado, lado), Image.LANCZOS)
    cx, cy = int(W * px), int(H * py)
    out = [CamadaAnimada(ger, lado, lado, cx - lado // 2, cy - lado // 2, ef["inicio"], ef["inicio"] + dur, fps,
                         0.01, 0.6, nome="ef_circulo")]
    if ef.get("texto"):
        e, d = _estilos(combo, 64 * escala)
        it = render(ef["texto"], e, d, largura_max=820 * escala)
        ty = cy + lado // 2 + int(10 * escala) if py < 0.55 else cy - lado // 2 - it.height
        out.append(Camada(it, (W - it.width) // 2, ty, ef["inicio"] + desenho, ef["inicio"] + dur, entrada=0.8,
                          saida=0.6, deslize=22, nome="ef_circulo_texto", texto=ef["texto"]))
    return out


def notificacao(ef, combo, W, H, fps):
    """H188 card de notificação: desce do topo devagar (app · agora / título / texto)."""
    escala = W / 1080
    larg, pad = int(860 * escala), int(30 * escala)
    ea = Estilo(marca("rotulo"), 22 * escala, cor("rodape"), caixa_alta=True, tracking=0.18)
    et = Estilo(marca("pill"), 32 * escala, cor("off_white"))
    etd = Estilo(marca("pill"), 32 * escala, cor("dourado"))
    ex = Estilo(marca("rodape"), 28 * escala, cor("texto"))
    cab = render(f"{ef.get('app', 'SEU CORPO')} · agora", ea, ea, sombra=False, alinhamento="left")
    tit = render(ef.get("titulo", ""), et, etd, largura_max=larg - 2 * pad, sombra=False, alinhamento="left")
    txt = render(ef.get("texto", ""), ex, ex, largura_max=larg - 2 * pad, sombra=False, alinhamento="left") \
        if ef.get("texto") else None
    alt = pad * 2 + cab.height + tit.height + (txt.height if txt else 0)
    card = _card(larg, alt, "fundo", 225, int(30 * escala))
    card.alpha_composite(cab, (pad, pad))
    card.alpha_composite(tit, (pad, pad + cab.height))
    if txt:
        card.alpha_composite(txt, (pad, pad + cab.height + tit.height - int(4 * escala)))
    y = int(float(ef.get("y", 250)) * escala)
    dur = float(ef.get("duracao", 3.4))
    return [Camada(card, (W - larg) // 2, y, ef["inicio"], ef["inicio"] + dur, entrada=0.8, saida=0.6,
                   deslize=-60 * escala, nome="ef_notificacao",
                   texto=f"{ef.get('titulo', '')} {ef.get('texto', '')}")]


def artigo(ef, combo, W, H, fps):
    """C-H77 card de artigo científico: card creme com a frase e o marca-texto dourado passando por cima."""
    escala = W / 1080
    larg, pad = int(840 * escala), int(44 * escala)
    ef_rot = Estilo(marca("rotulo"), 22 * escala, (120, 110, 90), caixa_alta=True, tracking=0.2)
    efr = Estilo("Lora-Italic[wght].ttf", 40 * escala, (40, 36, 30), peso=500)
    rot = render(ef.get("fonte", "Estudo científico"), ef_rot, ef_rot, sombra=False, alinhamento="left")
    fr = render(ef["texto"], efr, efr, largura_max=larg - 2 * pad, sombra=False, alinhamento="left")
    alt = pad * 2 + rot.height + fr.height + int(10 * escala)
    base = _card(larg, alt, "creme", 245, int(18 * escala))
    dur = float(ef.get("duracao", 3.6))

    def ger(t):
        img = base.copy()
        img.alpha_composite(rot, (pad, pad))
        p = ease_in_out(clamp((t - 0.7) / 1.0))
        if p > 0:
            hl = Image.new("RGBA", (int(fr.width * p), fr.height), cor("dourado") + (150,))
            img.alpha_composite(hl, (pad, pad + rot.height + int(8 * escala)))
        img.alpha_composite(fr, (pad, pad + rot.height + int(8 * escala)))
        return img
    y = int(_y(ef, H) - alt / 2)
    return [CamadaAnimada(ger, larg, alt, (W - larg) // 2, y, ef["inicio"], ef["inicio"] + dur, fps, 0.7, 0.6,
                          nome="ef_artigo", texto=ef["texto"])]


def tweet(ef, combo, W, H, fps):
    """C-H176 / post tweet do Dr. Daniel: card creme com foto, nome, selo e a frase, fixo no terço de baixo."""
    from .cartoes import foto_redonda, pessoa, selo_verificado
    escala = W / 1080
    p = pessoa(ef.get("pessoa", "daniel"))
    larg, pad = int(860 * escala), int(34 * escala)
    foto = foto_redonda(ef.get("pessoa", "daniel"), int(84 * escala))
    en = Estilo("Poppins-Medium.ttf", 30 * escala, (30, 30, 30))
    ea = Estilo("Poppins-Light.ttf", 24 * escala, (110, 110, 110))
    et = Estilo("CormorantGaramond[wght].ttf", 46 * escala, (25, 25, 25), peso=500)
    etd = Estilo("CormorantGaramond[wght].ttf", 46 * escala, cor("dourado_escuro"), peso=600)
    nome = render(p["nome"], en, en, sombra=False, alinhamento="left")
    arroba = render(p["instagram"], ea, ea, sombra=False, alinhamento="left")
    frase = render(ef["texto"], et, etd, largura_max=larg - 2 * pad, sombra=False, alinhamento="left")
    alt = pad * 2 + foto.height + int(16 * escala) + frase.height
    card = _card(larg, alt, "creme", 250, int(26 * escala))
    card.alpha_composite(foto, (pad, pad))
    card.alpha_composite(nome, (pad + foto.width + int(18 * escala), pad + int(6 * escala)))
    if p.get("verificado"):
        s = selo_verificado(int(26 * escala))
        card.alpha_composite(s, (pad + foto.width + int(24 * escala) + nome.width, pad + int(12 * escala)))
    card.alpha_composite(arroba, (pad + foto.width + int(18 * escala), pad + nome.height))
    card.alpha_composite(frase, (pad, pad + foto.height + int(16 * escala)))
    y = int(_y(ef, H, 0.62) - alt / 2)
    return [Camada(card, (W - larg) // 2, y, ef["inicio"], ef["inicio"] + float(ef.get("duracao", 4.0)),
                   entrada=0.9, saida=0.6, deslize=30, nome="ef_tweet", texto=ef["texto"])]


def pergunta(ef, combo, W, H, fps):
    """C-H152 / C-H106 card "Pergunta que mais recebemos": card que gira suavemente de leve inclinação para frente."""
    escala = W / 1080
    larg, pad = int(820 * escala), int(40 * escala)
    er = Estilo(marca("rotulo"), 24 * escala, cor("dourado"), caixa_alta=True, tracking=0.24)
    e, d = _estilos(combo, 58 * escala)
    rot = render(ef.get("rotulo", "Pergunta que mais recebemos"), er, er, sombra=False)
    q = render(ef["texto"], e, d, largura_max=larg - 2 * pad, sombra=False)
    alt = pad * 2 + rot.height + q.height
    card = _card(larg, alt, "fundo", 230)
    card.alpha_composite(rot, ((larg - rot.width) // 2, pad))
    card.alpha_composite(q, ((larg - q.width) // 2, pad + rot.height))
    dur = float(ef.get("duracao", 3.6))
    folga = int(alt * 0.25)

    def ger(t):
        p = ease_out(clamp(t / 1.0))
        ang = (1 - p) * 0.35            # inclinação inicial (rad) que assenta
        enc = math.cos(ang)
        h2 = max(2, int(alt * enc))
        topo = int(larg * 0.06 * math.sin(ang))
        im = card.transform(card.size, Image.QUAD, (topo, 0, 0, alt, larg, alt, larg - topo, 0), Image.BICUBIC)
        im = im.resize((larg, h2), Image.LANCZOS)
        out = Image.new("RGBA", (larg, alt + folga), (0, 0, 0, 0))
        out.alpha_composite(im, (0, (alt + folga - h2) // 2))
        return out
    y = int(_y(ef, H) - (alt + folga) / 2)
    return [CamadaAnimada(ger, larg, alt + folga, (W - larg) // 2, y, ef["inicio"], ef["inicio"] + dur, fps, 0.6, 0.6,
                          nome="ef_pergunta", texto=ef["texto"])]


def chat(ef, combo, W, H, fps):
    """EV03 interface de chat: balões entrando um a um (pergunta frequente à esquerda, resposta à direita)."""
    escala = W / 1080
    msgs = ef["mensagens"]                  # [{de: "paciente"|"clinica", texto: ...}]
    eb = Estilo(marca("rodape"), 30 * escala, cor("off_white"))
    ebd = Estilo(marca("rodape"), 30 * escala, cor("fundo"))
    bal = []
    for m in msgs:
        clin = m.get("de") == "clinica"
        it = render(m["texto"], ebd if clin else eb, ebd if clin else eb, largura_max=560 * escala, sombra=False,
                    alinhamento="left")
        w, h = it.width + int(44 * escala), it.height + int(26 * escala)
        b = _card(w, h, "dourado" if clin else "fundo", 240, int(24 * escala), borda=not clin)
        b.alpha_composite(it, (int(22 * escala), int(13 * escala)))
        bal.append((b, clin))
    larg = int(860 * escala)
    gap = int(16 * escala)
    alt = sum(b.height + gap for b, _ in bal)
    passo = float(ef.get("intervalo", 1.0))
    dur = float(ef.get("duracao", passo * len(bal) + 2.0))

    def ger(t):
        img = Image.new("RGBA", (larg, alt), (0, 0, 0, 0))
        y = 0
        for k, (b, clin) in enumerate(bal):
            p = ease_out(clamp((t - 0.3 - k * passo) / 0.5))
            x = larg - b.width if clin else 0
            _cola(img, b, x, y + (1 - p) * 20 * escala, p)
            y += b.height + gap
        return img
    y = int(_y(ef, H) - alt / 2)
    return [CamadaAnimada(ger, larg, alt, (W - larg) // 2, y, ef["inicio"], ef["inicio"] + dur, fps, 0.01, 0.6,
                          nome="ef_chat", texto=" ".join(m["texto"] for m in msgs))]


def grafico(ef, combo, W, H, fps):
    """EV10 gráfico em expansão (sem números): barras douradas crescendo com rótulos."""
    escala = W / 1080
    barras = ef["barras"]                   # [{rotulo, valor 0..1}]
    larg, alt = int(820 * escala), int(460 * escala)
    er = Estilo(marca("rotulo"), 24 * escala, cor("off_white"), caixa_alta=True, tracking=0.16)
    rots = [render(b["rotulo"], er, er, sombra=True) for b in barras]
    dur = float(ef.get("duracao", 3.6))

    def ger(t):
        img = Image.new("RGBA", (larg, alt), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        n = len(barras)
        bw = larg / (n * 1.6)
        base = alt - int(60 * escala)
        for k, b in enumerate(barras):
            p = ease_in_out(clamp((t - 0.3 - k * 0.25) / 1.2))
            x = (larg - n * bw * 1.6) / 2 + k * bw * 1.6 + bw * 0.3
            h = (base - 20 * escala) * float(b["valor"]) * p
            dr.rounded_rectangle((x, base - h, x + bw, base), radius=int(10 * escala),
                                 fill=cor("dourado" if k == n - 1 else "dourado_escuro") + (235,))
            _cola(img, rots[k], x + bw / 2 - rots[k].width / 2, base + 6 * escala, clamp(p * 2))
        return img
    y = int(_y(ef, H) - alt / 2)
    return [CamadaAnimada(ger, larg, alt, (W - larg) // 2, y, ef["inicio"], ef["inicio"] + dur, fps, 0.5, 0.6,
                          nome="ef_grafico", texto=" ".join(b["rotulo"] for b in barras))]


# ---------------------------------------------------------------- efeitos no quadro

def zoom_digital(ef, combo, W, H, fps):
    """EV05/EV09 zoom digital suave no ponto (entra, segura, volta), sem tranco."""
    z = float(ef.get("zoom", 1.15))
    px, py = ef.get("ponto", [0.5, 0.42])
    t0, dur = ef["inicio"], float(ef.get("duracao", 2.5))
    rampa = float(ef.get("rampa_s", 0.7))

    def f(q, t):
        if t < t0 or t > t0 + dur:
            return q
        p = ease_in_out(clamp((t - t0) / rampa)) * ease_in_out(clamp((t0 + dur - t) / rampa))
        s = 1 + (z - 1) * p
        if s <= 1.001:
            return q
        h, w = q.shape[:2]
        cw, ch = int(w / s), int(h / s)
        x = int(clamp(px * w - cw / 2, 0, w - cw))
        y = int(clamp(py * h - ch / 2, 0, h - ch))
        return np.array(Image.fromarray(q[y:y + ch, x:x + cw]).resize((w, h), Image.BICUBIC))
    return f


def fundo_pip(ef, combo, W, H, fps):
    """EV12/EC14 fundo #12110F com o vídeo em janela (PiP) de cantos arredondados e borda dourada."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    esc = float(ef.get("escala", 0.62))
    cy = float(ef.get("centro_y", 0.55))
    fundo = np.array(cor("fundo"), np.float32)

    def f(q, t):
        if t < t0 or t > t0 + dur:
            return q
        p = ease_in_out(clamp((t - t0) / 0.7)) * ease_in_out(clamp((t0 + dur - t) / 0.7))
        s = 1 - (1 - esc) * p
        h, w = q.shape[:2]
        pw, ph = int(w * s) // 2 * 2, int(h * s) // 2 * 2
        peq = Image.fromarray(q).resize((pw, ph), Image.BICUBIC)
        m = Image.new("L", (pw, ph), 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, pw - 1, ph - 1), radius=int(36 * p), fill=255)
        out = np.empty_like(q, dtype=np.float32)
        out[:] = q.astype(np.float32) * (1 - p) + fundo * p
        x = (w - pw) // 2
        y = int(clamp((h - ph) / 2 + (h * cy - h / 2) * p, 0, h - ph))
        mm = np.asarray(m, np.float32)[..., None] / 255
        reg = out[y:y + ph, x:x + pw]
        out[y:y + ph, x:x + pw] = reg * (1 - mm) + np.asarray(peq, np.float32) * mm
        if p > 0.05:
            borda = Image.new("RGBA", (pw + 6, ph + 6), (0, 0, 0, 0))
            ImageDraw.Draw(borda).rounded_rectangle((0, 0, pw + 5, ph + 5), radius=int(36 * p) + 3,
                                                    outline=cor("dourado_escuro") + (int(220 * p),), width=3)
            ba = np.asarray(borda, np.float32) / 255
            y0, x0 = max(0, y - 3), max(0, x - 3)
            sub = out[y0:y0 + ba.shape[0], x0:x0 + ba.shape[1]]
            a = ba[:sub.shape[0], :sub.shape[1], 3:4]
            out[y0:y0 + sub.shape[0], x0:x0 + sub.shape[1]] = sub * (1 - a) + ba[:sub.shape[0], :sub.shape[1], :3] * 255 * a
        return out.astype(np.uint8)
    return f


def cortina(ef, combo, W, H, fps):
    """EC10 cortina (nunca em paciente): painel escuro que se abre do meio para os lados revelando a cena."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 1.4))
    fundo = np.array(cor("fundo"), np.uint8)

    def f(q, t):
        if t < t0 - 0.01 or t > t0 + dur:
            return q
        p = ease_in_out(clamp((t - t0) / dur))
        h, w = q.shape[:2]
        aberto = int(w / 2 * p)
        out = q.copy()
        out[:, : max(0, w // 2 - aberto)] = fundo
        out[:, min(w, w // 2 + aberto):] = fundo
        return out
    return f


def filme(ef, combo, W, H, fps):
    """EC12 visual de filme: faixas pretas entram devagar e um grão bem leve."""
    t0, dur = ef["inicio"], float(ef.get("duracao", 4.0))
    rng = np.random.default_rng(3)

    def f(q, t):
        if t < t0 or t > t0 + dur:
            return q
        p = ease_in_out(clamp((t - t0) / 0.8)) * ease_in_out(clamp((t0 + dur - t) / 0.8))
        h = q.shape[0]
        faixa = int(h * 0.11 * p)
        out = q.astype(np.int16)
        out += (rng.standard_normal(q.shape[:2]) * 5 * p).astype(np.int16)[..., None]
        out = np.clip(out, 0, 255).astype(np.uint8)
        if faixa:
            out[:faixa] = 0
            out[-faixa:] = 0
        return out
    return f


def vidro(ef, combo, W, H, fps):
    """EV17 texto em vidro dourado: o vídeo desfoca atrás de um card translúcido com borda dourada."""
    escala = W / 1080
    e, d = _estilos(combo, float(ef.get("tamanho", 84)) * escala)
    it = render(ef["texto"], e, d, largura_max=760 * escala)
    larg, alt = it.width + int(90 * escala), it.height + int(70 * escala)
    x0, y0 = (W - larg) // 2, int(_y(ef, H) - alt / 2)
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.0))
    m = Image.new("L", (larg, alt), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, larg - 1, alt - 1), radius=int(30 * escala), fill=255)
    mm = np.asarray(m, np.float32)[..., None] / 255

    def f(q, t):
        if t < t0 or t > t0 + dur:
            return q
        p = ease_in_out(clamp((t - t0) / 0.6)) * ease_in_out(clamp((t0 + dur - t) / 0.6))
        reg = q[y0:y0 + alt, x0:x0 + larg]
        borr = np.asarray(Image.fromarray(reg).filter(ImageFilter.GaussianBlur(18 * escala)), np.float32)
        borr = borr * 0.82 + np.array(cor("dourado"), np.float32) * 0.06
        out = q.copy()
        a = mm[:reg.shape[0], :reg.shape[1]] * p
        out[y0:y0 + alt, x0:x0 + larg] = (reg * (1 - a) + borr * a).astype(np.uint8)
        return out
    vid = Image.new("RGBA", (larg, alt), (0, 0, 0, 0))
    ImageDraw.Draw(vid).rounded_rectangle((0, 0, larg - 1, alt - 1), radius=int(30 * escala),
                                          outline=cor("dourado") + (200,), width=2)
    vid.alpha_composite(it, ((larg - it.width) // 2, (alt - it.height) // 2))
    return f, [Camada(vid, x0, y0, t0, t0 + dur, entrada=0.6, saida=0.6, deslize=0, nome="ef_vidro",
                      texto=ef["texto"])]


def texto_atras(ef, combo, W, H, fps):
    """EV16 capa de revista / C-H151 / H203: título grande atrás da cabeça (pessoa recortada por cima)."""
    from . import recorte
    escala = W / 1080
    e, d = _estilos(combo, float(ef.get("tamanho", 200)) * escala)
    it = render(ef["texto"], e, d, largura_max=W * 0.94)
    x0, y0 = (W - it.width) // 2, int(_y(ef, H, 0.22) - it.height / 2)
    t0, dur = ef["inicio"], float(ef.get("duracao", 3.5))
    a_txt = np.asarray(it, np.float32) / 255

    def f(q, t):
        if t < t0 or t > t0 + dur:
            return q
        p = ease_in_out(clamp((t - t0) / 0.8)) * ease_in_out(clamp((t0 + dur - t) / 0.6))
        out = q.astype(np.float32)
        hh, ww = a_txt.shape[:2]
        ys, xs = max(0, y0), max(0, x0)
        ye, xe = min(H, y0 + hh), min(W, x0 + ww)
        sub = a_txt[ys - y0:ye - y0, xs - x0:xe - x0]
        a = sub[..., 3:4] * p
        out[ys:ye, xs:xe] = out[ys:ye, xs:xe] * (1 - a) + sub[..., :3] * 255 * a
        m = recorte.mascara(q)
        if m is not None:
            out = out * (1 - m) + q.astype(np.float32) * m      # a pessoa volta para a frente do texto
        return out.astype(np.uint8)
    return f, []


TIPOS = {
    "camadas": camadas_cineticas, "queda_letras": lambda *a: letra_a_letra(*a, queda=True),
    "letra_a_letra": letra_a_letra, "riscado": riscado, "digitando": digitando, "checklist": checklist,
    "contador": contador, "linha_tempo": linha_tempo, "circulo": circulo, "notificacao": notificacao,
    "artigo": artigo, "tweet": tweet, "pergunta": pergunta, "chat": chat, "grafico": grafico,
}
QUADRO = {"zoom_digital": zoom_digital, "fundo_pip": fundo_pip, "cortina": cortina, "filme": filme,
          "vidro": vidro, "texto_atras": texto_atras}


def resolver_tipo(ef: dict) -> str:
    if ef.get("tipo"):
        return ef["tipo"]
    cod = str(ef.get("codigo", "")).upper()
    tab = _cfg().get("codigos", {})
    if cod not in tab:
        raise SystemExit(f"Efeito {cod} não está em config/efeitos.yaml")
    tipo = tab[cod].get("tipo")
    if not tipo:
        raise SystemExit(f"Efeito {cod} ({tab[cod].get('nome')}) ainda não tem módulo: {tab[cod].get('obs', '')}")
    return tipo


def espacar(efeitos: list, intervalo: float) -> list:
    """Garante no máximo um efeito a cada `intervalo` s (empurra os seguintes, com aviso)."""
    out, ultimo = [], -99.0
    for ef in sorted(efeitos, key=lambda e: float(e.get("inicio", 0))):
        ef = dict(ef)
        ini = float(ef.get("inicio", 0))
        if ini - ultimo < intervalo:
            print(f"  aviso: efeito {ef.get('tipo') or ef.get('codigo')} em {ini:.1f}s muito perto do anterior; "
                  f"empurrado para {ultimo + intervalo:.1f}s")
            ini = ultimo + intervalo
        ef["inicio"] = ini
        out.append(ef)
        ultimo = ini
    return out


def aplicar(plano, projeto: dict, versao: dict, combo: dict, W: int, H: int, fps: int = 30) -> None:
    lista = list(projeto.get("efeitos") or []) + list(versao.get("efeitos") or [])
    if not lista:
        return
    for ef in lista:
        ef["tipo"] = resolver_tipo(ef)
    ordem = espacar(lista, float(_cfg().get("intervalo_minimo_s", 1.5)))
    for k, ef in enumerate(ordem):
        if ef["inicio"] >= plano.inicio_fechamento:
            print(f"  aviso: efeito {ef['tipo']} começa depois do fim do vídeo; ignorado")
            continue
        # quando o próximo efeito entra, este sai em fade (nunca dois efeitos empilhados)
        limite = min(plano.inicio_fechamento, ordem[k + 1]["inicio"] + 0.3 if k + 1 < len(ordem) else 1e9)
        tipo = ef["tipo"]
        if tipo in TIPOS:
            cam = TIPOS[tipo](ef, combo, W, H, fps)
            for c in cam:
                c.t1 = min(c.t1, limite)
            plano.camadas += cam
            plano.textos_tela += [c.texto for c in cam if c.texto]
        elif tipo in QUADRO:
            ef["duracao"] = min(float(ef.get("duracao", 3.0)), limite - ef["inicio"])
            r = QUADRO[tipo](ef, combo, W, H, fps)
            f, cams = r if isinstance(r, tuple) else (r, [])
            plano.efeitos_quadro.append(f)
            plano.camadas += cams
            plano.textos_tela += [c.texto for c in cams if c.texto]
            if tipo == "texto_atras":
                plano.textos_tela.append(ef["texto"])
        else:
            raise SystemExit(f"Tipo de efeito desconhecido: {tipo}. Opções: {', '.join(sorted(TIPOS) + sorted(QUADRO))}")
        if ef.get("som"):
            plano.eventos_sfx.append((ef["inicio"], ef["som"], float(load("sfx").get("ganho_db", -24))))


# Exemplos usados na prancha (python3 -m divine_studio efeitos --prancha) e nos testes
EXEMPLOS = {
    "camadas": {"texto": "Você deita. O músculo *treina.*"},
    "queda_letras": {"texto": "Pausa *obrigatória*"},
    "letra_a_letra": {"texto": "Spa *Divine*"},
    "riscado": {"texto": "“Vou deixar para depois.”", "virada": "Vou começar *agora.*"},
    "digitando": {"texto": "Quero agendar minha avaliação"},
    "checklist": {"titulo": "Quantos desses *você tem?*", "itens": ["Cansaço no fim do dia", "Queda de cabelo",
                                                                  "Unhas fracas"]},
    "contador": {"de": 1, "ate": 90, "prefixo": "DIA ", "rotulo": "acompanhamento"},
    "linha_tempo": {"marcos": ["OUT", "NOV", "DEZ"]},
    "circulo": {"ponto": [0.5, 0.42], "texto": "*Spoiler:* é só a mira"},
    "notificacao": {"app": "SEU CORPO", "titulo": "Freio de mão desativado.", "texto": "Você completou 35 anos."},
    "artigo": {"texto": "O microagulhamento estimulou a produção de colágeno", "fonte": "Estudo, 2008"},
    "tweet": {"texto": "Sem treino, nada *se mantém.*"},
    "pergunta": {"texto": "Laser de CO2 *dói?*"},
    "chat": {"mensagens": [{"de": "paciente", "texto": "Pode fazer CO2 no verão?"},
                           {"de": "clinica", "texto": "Pode, com cuidado e protetor."}]},
    "grafico": {"barras": [{"rotulo": "mês 1", "valor": 0.3}, {"rotulo": "mês 2", "valor": 0.55},
                           {"rotulo": "mês 3", "valor": 0.85}]},
    "vidro": {"texto": "Cuidado *sob medida*"},
}


def prancha(arquivo, combo_codigo: str = "B", W: int = 540, H: int = 960) -> None:
    """Folha com cada efeito de camada no meio da animação, sobre um fundo neutro."""
    from .fonts import combinacao
    combo = combinacao(combo_codigo)
    fundo = np.zeros((H, W, 3), np.uint8)
    yy = np.linspace(0, 1, H)[:, None, None]
    fundo[:] = (np.array([70, 60, 52]) * (1 - yy) + np.array([30, 28, 26]) * yy).astype(np.uint8)
    tiles = []
    for tipo, ex in EXEMPLOS.items():
        ef = {"tipo": tipo, "inicio": 0.0, **ex}
        q = fundo.copy()
        if tipo in TIPOS:
            cams = TIPOS[tipo](ef, combo, W, H, 10)
        else:
            f, cams = QUADRO[tipo](ef, combo, W, H, 10)
            q = f(q, 1.5)
        for c in cams:
            c.pintar(q, min(c.t1 - 0.7, 2.6))
        im = Image.fromarray(q)
        ImageDraw.Draw(im).text((12, 10), tipo, fill=(204, 189, 145))
        tiles.append(im.resize((W // 2, H // 2), Image.LANCZOS))
    cols = 4
    linhas = (len(tiles) + cols - 1) // cols
    folha = Image.new("RGB", (cols * (W // 2 + 6), linhas * (H // 2 + 6)), (255, 255, 255))
    for k, t in enumerate(tiles):
        folha.paste(t, ((k % cols) * (W // 2 + 6), (k // cols) * (H // 2 + 6)))
    folha.save(arquivo, quality=85)
