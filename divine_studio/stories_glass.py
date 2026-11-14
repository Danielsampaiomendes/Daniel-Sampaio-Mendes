"""Stories e capas no Liquid Glass Divine (portfólio de identidade visual de novembro de 2026).

Regras em config/identidade.yaml (seção liquid_glass) e docs/IDENTIDADE_VISUAL.md:
  - fundo do banco de joalheria 3D (assets/fundos): ouro líquido, vidro e diamantes só nos cantos, centro escuro livre;
    nunca o mesmo fundo duas vezes seguidas, com pequenas variações a cada peça
  - cartão de vidro líquido no centro: vidro que refrata o fundo (ampliado e desfocado), tinta escura quente, luz no
    topo, aro luminoso duplo (brilho em gradiente angular e filete dourado interno) e brilhos especulares nos cantos
  - cabeçalho tipo tweet: avatar redondo com aro dourado, nome e @ pequenos
  - três vozes: frase (Poppins Light, leve), palavra-chave (Poppins Bold em CAIXA ALTA, dourado em degradê com brilho,
    1 ou 2 palavras) e fecho (Lora itálico, dourado claro)
  - versão escura (preto e ouro champanhe) e clara (marfim, grafite, ouro escuro e bronze, sem brilho), em teste A/B
  - pouco texto, toda linha começando com maiúscula, sem travessão, nada nas zonas mortas do Stories
  - figurinhas (enquete, caixinha, controle deslizante) não são desenhadas: entram nativas pelo app

stories.yaml:
  fotos: pasta das fotos (avatar)        # opcional
  avatar: rosto.jpg                      # foto do Dr. Daniel para o avatar (sem ela, o trevo Divine)
  versoes: [escura, clara]               # gera as duas para o teste A/B
  stories:
    - id: E1
      frase: "Conta quantos destes você já fez"
      chave: "Quem nunca?"               # sai em caixa alta
      blocos: [{tipo: lista, itens: [...]}]   # lista | opcoes | linhas | escala | texto
      fecho: "De 0 a 5, me conta no direct."
      chamada: "Sem julgamento"           # opcional, linha pequena
      fundo: ondas                        # opcional; sem ele, o app escolhe sem repetir o anterior
Uso: python3 -m divine_studio stories-glass <stories.yaml> [--saida pasta]
"""
from __future__ import annotations

import dataclasses
import math
import random
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from . import brand
from .config import ROOT, hexrgb, load
from .text import Estilo, render

W, H = 1080, 1920
FUNDOS = ROOT / "assets" / "fundos"


def cfg() -> dict:
    return load("identidade").get("liquid_glass") or {}


def cores(versao: str) -> dict:
    p = cfg()["paleta"]
    if versao == "clara":
        c = p["clara"]
        return {"frase": hexrgb(c["grafite_quente"]), "chave": [hexrgb(x) for x in c["ouro_escuro"]],
                "fecho": hexrgb(c["bronze"]), "corpo": hexrgb(c["grafite_quente"]), "apagado": hexrgb("#7A6E60"),
                "aro": hexrgb(c["ouro_escuro"][0]), "filete": hexrgb(c["bronze"]), "tinta": hexrgb(c["marfim"]),
                "nome": hexrgb(c["grafite_quente"]), "brilho": False, "placa": (38, 31, 24)}
    c = p["escura"]
    return {"frase": hexrgb(c["off_white"]), "chave": [hexrgb(c["champanhe_claro"]), hexrgb(c["ouro_antigo"])],
            "fecho": hexrgb(c["champanhe_claro"]), "corpo": hexrgb(c["off_white"]), "apagado": hexrgb("#9A958A"),
            "aro": hexrgb(c["champanhe_claro"]), "filete": hexrgb(c["ouro_antigo"]), "tinta": hexrgb(c["preto_quente"]),
            "nome": hexrgb(c["off_white"]), "brilho": True, "placa": (255, 255, 255)}


def _voz(nome: str, cor: tuple, escala: float = 1.0) -> Estilo:
    f = cfg()["vozes"][nome]
    return Estilo(arquivo=f["arquivo"], tamanho=float(f["tamanho"]) * escala, cor=cor, peso=f.get("peso"))


def _txt(texto: str, est: Estilo, larg: int, alinhar: str = "left", entrelinha: float = 1.2) -> Image.Image:
    # folga de 6%: a quebra de linha mede no tamanho base e algumas letras passavam da borda
    return render(str(texto), est, dataclasses.replace(est), largura_max=larg * 0.94, alinhamento=alinhar,
                  sombra=False, entrelinha=entrelinha)


def _redondo(tam: tuple, raio: int) -> Image.Image:
    m = Image.new("L", tam, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, tam[0] - 1, tam[1] - 1), raio, fill=255)
    return m


def _empilha(partes: list, gap: int, larg: int, alinhar: str = "left") -> Image.Image:
    partes = [p for p in partes if p is not None]
    h = sum(p.height for p in partes) + gap * max(0, len(partes) - 1)
    out = Image.new("RGBA", (larg, max(1, h)), (0, 0, 0, 0))
    y = 0
    for p in partes:
        out.alpha_composite(p, (0 if alinhar == "left" else (larg - p.width) // 2, y))
        y += p.height + gap
    return out


# ---------------------------------------------------------------- as três vozes e os blocos

def palavra_chave(texto: str, c: dict, larg: int, escala: float = 1.0) -> Image.Image:
    """CAIXA ALTA em Poppins Bold, dourado em degradê vertical; na versão escura, com brilho (bloom)."""
    est = _voz("chave", (255, 255, 255), escala)
    while True:
        mascara = _txt(str(texto).upper(), est, larg, entrelinha=1.02)
        if mascara.width <= larg or est.tamanho < 40:
            break
        est = dataclasses.replace(est, tamanho=est.tamanho * 0.92)
    pad = 40 if c["brilho"] else 6
    a = mascara.getchannel("A")
    w, h = a.size
    topo, base = np.array(c["chave"][0], float), np.array(c["chave"][1], float)
    t = np.linspace(0, 1, h)[:, None, None]
    grad = (topo * (1 - t) + base * t).repeat(w, axis=1).astype(np.uint8)
    cor = Image.fromarray(grad, "RGB").convert("RGBA")
    cor.putalpha(a)
    out = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    if c["brilho"]:
        glow = Image.new("RGBA", out.size, c["chave"][0] + (0,))
        m = Image.new("L", out.size, 0)
        m.paste(a, (pad, pad))
        glow.putalpha(m.filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * 0.55)))
        out.alpha_composite(glow)
    out.alpha_composite(cor, (pad, pad))
    # alinha com o resto do texto: a sobra do brilho à esquerda sai (o brilho continua em cima, embaixo e à direita)
    return out.crop((max(0, pad - 4), int(pad * 0.45), out.width, out.height - int(pad * 0.45)))


def _placa(tam: tuple, c: dict, raio: int = 24) -> Image.Image:
    """Placa de vidro dentro do cartão (opções, linhas)."""
    im = Image.new("RGBA", tam, c["placa"] + (22 if c["brilho"] else 16,))
    im.putalpha(ImageChops.multiply(im.getchannel("A"), _redondo(tam, raio)))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, tam[0] - 1, tam[1] - 1), raio, outline=c["filete"] + (130,), width=2)
    return im


def bloco(b: dict, c: dict, larg: int, e: float) -> Image.Image:
    tipo = b.get("tipo", "texto")
    corpo = _voz("corpo", c["corpo"], e)
    if tipo == "lista":
        linhas = []
        for it in b.get("itens") or []:
            t = _txt(it, corpo, larg - 40)
            ln = Image.new("RGBA", (larg, t.height), (0, 0, 0, 0))
            cy = int(corpo.tamanho * 0.66)
            ImageDraw.Draw(ln).ellipse((4, cy - 5, 14, cy + 5), fill=c["filete"] + (255,))
            ln.alpha_composite(t, (36, 0))
            linhas.append(ln)
        return _empilha(linhas, int(16 * e), larg)
    if tipo == "opcoes":
        ops = b.get("itens") or []
        n, gap = max(1, len(ops)), int(20 * e)
        w = (larg - gap * (n - 1)) // n
        txts = [_txt(o, _voz("opcao", c["corpo"], e), w - 28, alinhar="center") for o in ops]
        h = max(t.height for t in txts) + int(56 * e)
        out = Image.new("RGBA", (larg, h), (0, 0, 0, 0))
        for k, t in enumerate(txts):
            x = k * (w + gap)
            out.alpha_composite(_placa((w, h), c), (x, 0))
            out.alpha_composite(t, (x + (w - t.width) // 2, (h - t.height) // 2))
        return out
    if tipo == "linhas":
        rows = []
        for it in b.get("itens") or []:
            t = _txt(it, corpo, larg - 64)
            h = t.height + int(34 * e)
            row = _placa((larg, h), c, raio=h // 2)
            row.alpha_composite(t, (32, (h - t.height) // 2))
            rows.append(row)
        return _empilha(rows, int(12 * e), larg)
    if tipo == "escala":
        de, ate = int(b.get("de", 0)), int(b.get("ate", 10))
        h = int(118 * e)
        out = Image.new("RGBA", (larg, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(out)
        y, x0, x1 = int(20 * e), 16, larg - 16
        for x in range(x0, x1):
            a = int(80 + 170 * (x - x0) / (x1 - x0))
            d.line((x, y - 2, x, y + 2), fill=c["aro"] + (a,))
        num = _voz("rodape", c["apagado"], e * 1.25)
        for k in range(de, ate + 1):
            x = x0 + (x1 - x0) * (k - de) / max(1, ate - de)
            d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=c["aro"] + (255,))
            t = _txt(str(k), num, 60, alinhar="center")
            out.alpha_composite(t, (int(x - t.width / 2), y + 14))
        rot = _voz("fecho", c["fecho"], e * 0.62)
        if b.get("rotulo_de"):
            t = _txt(b["rotulo_de"], rot, larg // 2)
            out.alpha_composite(t, (x0 - 4, h - t.height))
        if b.get("rotulo_ate"):
            t = _txt(b["rotulo_ate"], rot, larg // 2, alinhar="right")
            out.alpha_composite(t, (x1 + 4 - t.width, h - t.height))
        return out
    est = _voz("opcao", c["corpo"], e * 0.95) if b.get("forte") else dataclasses.replace(corpo, cor=c["corpo"])
    return _txt(b.get("texto", ""), est, larg, entrelinha=1.3)


def cabecalho(c: dict, avatar: Path | None, larg: int, e: float) -> Image.Image:
    cab = cfg()["cabecalho"]
    d = int(cab.get("avatar", 92) * e)
    out = Image.new("RGBA", (larg, d + 4), (0, 0, 0, 0))
    redondo = Image.new("L", (d, d), 0)
    ImageDraw.Draw(redondo).ellipse((0, 0, d - 1, d - 1), fill=255)
    if avatar and Path(avatar).exists():
        foto = ImageOps.fit(ImageOps.exif_transpose(Image.open(avatar)).convert("RGB"), (d, d), Image.LANCZOS,
                            centering=(0.5, 0.32)).convert("RGBA")
    else:                                                # trevo Divine no lugar da foto
        foto = Image.new("RGBA", (d, d), c["tinta"] + (255,))
        s = brand.simbolo(int(d * 0.52))
        foto.alpha_composite(s, ((d - s.width) // 2, (d - s.height) // 2))
    foto.putalpha(redondo)
    out.alpha_composite(foto, (2, 2))
    ImageDraw.Draw(out).ellipse((1, 1, d + 2, d + 2), outline=c["aro"] + (255,), width=3)
    nome = _txt(cab.get("nome", ""), _voz("nome", c["nome"], e), larg - d - 30)
    arroba = _txt(cab.get("arroba", ""), _voz("arroba", c["apagado"], e), larg - d - 30)
    y = (d + 4 - nome.height - arroba.height - 2) // 2
    out.alpha_composite(nome, (d + 26, y))
    out.alpha_composite(arroba, (d + 26, y + nome.height + 2))
    return out


def conteudo(s: dict, c: dict, avatar: Path | None, larg: int, e: float) -> Image.Image:
    partes = [cabecalho(c, avatar, larg, e)]
    meio = []
    if s.get("frase"):
        meio.append(_txt(s["frase"], _voz("frase", c["frase"], e), larg, entrelinha=1.22))
    if s.get("chave"):
        meio.append(palavra_chave(s["chave"], c, larg, e))
    blocos = [bloco(b, c, larg, e) for b in s.get("blocos") or []]
    fim = []
    if s.get("fecho"):
        fim.append(_txt(s["fecho"], _voz("fecho", c["fecho"], e), larg, entrelinha=1.25))
    if s.get("chamada"):
        fim.append(_txt(s["chamada"], _voz("corpo", c["apagado"], e * 0.82), larg))
    fim.append(_txt(str(cfg().get("rodape", "")), _voz("rodape", c["apagado"], e), larg, entrelinha=1.35))
    return _empilha([partes[0], _empilha(meio, int(8 * e), larg),
                     _empilha(blocos, int(22 * e), larg) if blocos else None,
                     _empilha(fim, int(14 * e), larg)], int(34 * e), larg)


# ---------------------------------------------------------------- fundo e vidro

def fundo(nome: str, rnd: random.Random) -> Image.Image:
    arq = FUNDOS / f"{nome}.jpg"
    if not arq.exists():
        base = Image.new("RGB", (W, H), hexrgb(cfg()["paleta"]["escura"]["preto_quente"]))
    else:
        base = Image.open(arq).convert("RGB")
        z = 1.0 + rnd.random() * 0.06                   # pequenas variações a cada peça
        base = base.resize((int(W * z), int(H * z)), Image.LANCZOS)
        dx, dy = rnd.randint(0, base.width - W), rnd.randint(0, base.height - H)
        base = base.crop((dx, dy, dx + W, dy + H))
        if rnd.random() < 0.5:
            base = ImageOps.mirror(base)
    return base.convert("RGBA")


def _aro_angular(tam: tuple, raio: int, cor: tuple, largura: int = 3) -> Image.Image:
    """Aro com brilho em gradiente angular: forte no alto à esquerda e embaixo à direita, suave no resto."""
    w, h = tam
    m = Image.new("L", tam, 0)
    ImageDraw.Draw(m).rounded_rectangle((1, 1, w - 2, h - 2), raio, outline=255, width=largura)
    yy, xx = np.mgrid[0:h, 0:w]
    ang = np.arctan2(yy - h / 2, xx - w / 2)
    forca = 0.30 + 0.70 * np.maximum(np.cos(ang - math.radians(-140)), np.cos(ang - math.radians(40))).clip(0) ** 3
    a = (np.asarray(m, float) * forca).astype(np.uint8)
    out = Image.new("RGBA", tam, cor + (0,))
    out.putalpha(Image.fromarray(a, "L"))
    return out


def vidro(bg: Image.Image, caixa: tuple, c: dict, versao: str) -> Image.Image:
    k = cfg()["cartao"]
    x0, y0, x1, y1 = caixa
    w, h = x1 - x0, y1 - y0
    amp = float(k.get("ampliar_fundo", 1.18))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    fw, fh = w / amp, h / amp                           # refrata: o fundo aparece ampliado atrás do vidro
    reg = bg.crop((int(cx - fw / 2), int(cy - fh / 2), int(cx + fw / 2), int(cy + fh / 2))).convert("RGB")
    reg = reg.resize((w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(float(k.get("desfoque", 34))))
    tinta = float(k.get("tinta_clara" if versao == "clara" else "tinta_escura", 0.74))
    reg = Image.blend(reg, Image.new("RGB", (w, h), c["tinta"]), tinta).convert("RGBA")
    luz = Image.linear_gradient("L").resize((w, int(h * 0.4))).point(
        lambda v: int((255 - v) * float(k.get("luz_topo", 0.12))))
    camada = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    a = Image.new("L", (w, h), 0)
    a.paste(luz, (0, 0))
    camada.putalpha(a)
    reg.alpha_composite(camada)
    raio = int(k.get("raio", 54))
    reg.putalpha(_redondo((w, h), raio))
    # aro luminoso duplo: brilho angular por fora, filete dourado por dentro
    reg.alpha_composite(_aro_angular((w, h), raio, c["aro"], 3))
    ImageDraw.Draw(reg).rounded_rectangle((10, 10, w - 11, h - 11), max(8, raio - 10), outline=c["filete"] + (120,), width=1)
    return reg


def _especular(img: Image.Image, x: int, y: int, r: int, forte: bool) -> None:
    s = Image.new("RGBA", (r * 6, r * 6), (255, 255, 255, 0))
    m = Image.new("L", s.size, 0)
    ImageDraw.Draw(m).ellipse((r * 2, r * 2, r * 4, r * 4), fill=255 if forte else 150)
    s.putalpha(m.filter(ImageFilter.GaussianBlur(r * 0.9)))
    img.alpha_composite(s, (x - r * 3, y - r * 3))


def desenhar(s: dict, versao: str = "escura", nome_fundo: str | None = None, avatar: Path | None = None,
             rnd: random.Random | None = None) -> Image.Image:
    k = cfg()["cartao"]
    c = cores(versao)
    rnd = rnd or random.Random(f"{s.get('id', '')}{versao}")
    m, pad = int(k.get("margem", 84)), 58
    larg_cartao = W - 2 * m
    larg = larg_cartao - 2 * pad
    e = float(s.get("escala", 1.0))
    topo_min, base_max = int(k.get("topo_minimo", 300)), int(k.get("base_maxima", 1560))
    while True:                                          # pouco texto: se não couber, a letra diminui um pouco
        miolo = conteudo(s, c, avatar, larg, e)
        alt = miolo.height + 2 * pad
        if alt <= base_max - topo_min or e < 0.6:
            break
        e *= 0.94
    topo = int(min(max(int(k.get("centro_y", 915)) - alt // 2, topo_min), base_max - alt))
    nome_fundo = nome_fundo or (cfg()["fundos"]["clara" if versao == "clara" else "escura"][0])
    bg = fundo(nome_fundo, rnd)
    sombra = Image.new("RGBA", (larg_cartao + 160, alt + 160), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle((80, 100, larg_cartao + 80, alt + 100), 54,
                                             fill=(0, 0, 0, 150) if versao == "escura" else (70, 50, 20, 60))
    bg.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(34)), (m - 80, topo - 80))
    bg.alpha_composite(vidro(bg, (m, topo, W - m, topo + alt), c, versao), (m, topo))
    _especular(bg, m + 34, topo + 10, 9, True)          # brilhos especulares nos cantos do aro
    _especular(bg, W - m - 30, topo + alt - 10, 8, versao == "escura")
    bg.alpha_composite(miolo, (m + pad, topo + pad))
    if s.get("logo_topo", cfg().get("logo_topo", False)):   # logo no topo (desligado: o cartão já assina)
        logo = brand.horizontal(46)
        bg.alpha_composite(logo, ((W - logo.width) // 2, 262))
    return bg.convert("RGB")


def gerar(arquivo: Path, saida: Path | None = None) -> list:
    arquivo = Path(arquivo)
    d = yaml.safe_load(arquivo.read_text(encoding="utf-8")) or {}
    pasta_fotos = (arquivo.parent / d.get("fotos", "fotos")).resolve()
    avatar = pasta_fotos / d["avatar"] if d.get("avatar") else None
    saida = Path(saida or arquivo.parent / "saida")
    saida.mkdir(parents=True, exist_ok=True)
    versoes = d.get("versoes") or ["escura"]
    from .identidade import problemas_de_texto
    feitos, ultimo = [], {}
    for i, s in enumerate(d.get("stories") or []):
        textos = [s.get("frase"), s.get("chave"), s.get("fecho"), s.get("chamada")]
        for b in s.get("blocos") or []:
            textos += list(b.get("itens") or []) + [b.get("texto")]
        for t in filter(None, textos):
            for p in problemas_de_texto(str(t)):
                print(f"  aviso {s.get('id')}: {p}")
        for versao in versoes:
            banco = list(cfg()["fundos"]["clara" if versao == "clara" else "escura"])
            nome = s.get("fundo") if versao == "escura" and s.get("fundo") else None
            if not nome:                                  # nunca o mesmo fundo duas vezes seguidas
                nome = banco[i % len(banco)]
                if nome == ultimo.get(versao) and len(banco) > 1:
                    nome = banco[(i + 1) % len(banco)]
            ultimo[versao] = nome
            img = desenhar(s, versao, nome, avatar)
            destino = saida / f"{s.get('id', 'story')}_{versao}.png"
            img.save(destino, optimize=True)
            feitos.append(destino)
            print(f"  {s.get('id')} ({versao}, fundo {nome}): {destino}")
    return feitos
