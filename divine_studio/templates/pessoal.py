"""Template pessoal do Renato: sem nenhum logo ou marca Divine. docs/CONHECIMENTO_DIVINE.md 5.7.

Linha de cima em caixa alta encorpada (Bodoni Moda) + linha de baixo em cursiva fina (Great Vibes) e um
traço fino ligado ao tema (linha, arco ou moldura, um por versão). Sem fechamento de marca, sem RT.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from ..compositor import Camada
from ..config import cor, load
from . import divine

SS = 3


def preparar(projeto: dict) -> None:
    cfg = load("templates")["pessoal"]
    projeto.setdefault("conteudo_medico", False)
    projeto["marca"] = "pessoal"
    for v in projeto.get("versoes") or []:
        v["fontes"] = cfg["fontes"]     # par fixo; as versões variam pelo hook, pelo ornamento e pelos SFX


def ornamento(tipo: str, largura: int, altura: int, cor_rgb: tuple) -> Image.Image:
    w, h = largura * SS, altura * SS
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lw = max(2, int(1.6 * SS))
    c = cor_rgb + (230,)
    if tipo == "linha":
        y = h // 2
        d.line([(w * 0.18, y), (w * 0.44, y)], fill=c, width=lw)
        d.line([(w * 0.56, y), (w * 0.82, y)], fill=c, width=lw)
        r = 5 * SS
        d.polygon([(w / 2, y - r), (w / 2 + r, y), (w / 2, y + r), (w / 2 - r, y)], outline=c, width=lw)
    elif tipo == "arco":
        pts = [(w * (0.15 + 0.7 * k / 60), h * 0.65 - math.sin(math.pi * k / 60) * h * 0.4) for k in range(61)]
        d.line(pts, fill=c, width=lw, joint="curve")
    else:  # moldura
        m = lw * 2
        d.rectangle((m, m, w - m, h - m), outline=c, width=lw)
    return img.resize((largura, altura), Image.LANCZOS)


def montar(projeto, versao, combo, duracao_base, W, H, sfx_abertura, sfx_fechamento, sfx_transicao=None):
    cfg = load("templates")["pessoal"]
    plano = divine.montar(projeto, versao, combo, duracao_base, W, H, sfx_abertura, sfx_fechamento, sfx_transicao,
                          divine.Opcoes(header=False, fechamento_marca=False))
    plano.barra_progresso = False
    escala = W / 1080.0
    nomes = [v.get("nome") for v in projeto.get("versoes") or []]
    k = nomes.index(versao.get("nome")) if versao.get("nome") in nomes else 0
    tipo = versao.get("ornamento") or cfg["ornamentos"][k % len(cfg["ornamentos"])]
    hooks = [c for c in plano.camadas if c.nome.startswith("hook")]
    if hooks:
        x0 = min(c.x for c in hooks)
        x1 = max(c.x + c.w for c in hooks)
        y0 = min(c.y for c in hooks)
        y1 = max(c.y + c.h for c in hooks)
        t1 = max(c.t1 for c in hooks)
        if tipo == "moldura":
            m = int(28 * escala)
            orn = ornamento(tipo, x1 - x0 + 2 * m, y1 - y0 + 2 * m, cor(cfg["cor_traco"]))
            pos = (x0 - m, y0 - m)
        else:
            orn = ornamento(tipo, int(520 * escala), int(70 * escala), cor(cfg["cor_traco"]))
            pos = ((W - orn.width) // 2, y1 + int(4 * escala))
        plano.camadas.append(Camada(orn, pos[0], pos[1], 0.3, t1, entrada=1.2, saida=0.6, deslize=0,
                                    nome=f"ornamento_{tipo}"))
    return plano
