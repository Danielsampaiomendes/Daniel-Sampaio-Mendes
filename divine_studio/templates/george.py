"""Template George: base Divine + azul-marinho (#0E194A) com borda dourada fina. docs/CONHECIMENTO_DIVINE.md 5.4.

- selo navy com o tema a partir de ~3,3 s; cartão de nome (~3,5 a 9 s e no fim) com "Enf." e COREN
- placa navy 100% opaca no terço inferior (y≈1500) cobrindo a legenda queimada que ele grava; a legenda nova
  (transcrição ou OCR da queimada) vai em cima da placa
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from ..compositor import Camada
from ..config import cor, load
from . import divine
from ._pessoa import cartao


def preparar(projeto: dict) -> None:
    cfg = load("templates")["george"]
    projeto.setdefault("selo_inicio", cfg["selo_inicio"])
    leg = projeto.get("legendas")
    pl = {**cfg["placa_legenda"], **(projeto.get("placa_legenda") or {})}
    if leg:
        base = leg if isinstance(leg, dict) else {}
        projeto["legendas"] = {"posicao": pl["y"] / 1920, "max_caracteres": 26, **base}


def montar(projeto, versao, combo, duracao_base, W, H, sfx_abertura, sfx_fechamento, sfx_transicao=None):
    cfg = load("templates")["george"]
    escala = W / 1080.0
    plano = divine.montar(projeto, versao, combo, duracao_base, W, H, sfx_abertura, sfx_fechamento, sfx_transicao,
                          divine.Opcoes(cor_placa=cfg["cor_placa"]))
    # CTA antecipado sobe para não bater na placa da legenda
    for c in plano.camadas:
        if c.nome == "cta_antecipado":
            c.y = int(cfg["y_cta"] * escala)
    pl = {**cfg["placa_legenda"], **(projeto.get("placa_legenda") or {})}
    if projeto.get("cobrir_legenda_queimada", True):
        w, h = int(pl["largura"] * escala), int(pl["altura"] * escala)
        img = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle((2, 2, w * 2 - 3, h * 2 - 3), radius=int(36 * escala),
                                              fill=cor("navy") + (int(pl["opacidade"]),),
                                              outline=cor("dourado_escuro") + (230,), width=3)
        img = img.resize((w, h), Image.LANCZOS)
        y = int(pl["y"] * escala - h / 2)
        # entra já no 1º quadro (sem fade) para a legenda antiga nunca aparecer; vem antes da legenda nova
        plano.camadas.insert(0, Camada(img, (W - w) // 2, y, 0, plano.inicio_fechamento + 0.3, entrada=0,
                                       saida=0.4, deslize=0, nome="placa_legenda"))
        # a placa fica por baixo das camadas de texto, mas por cima dos gradientes
        plano.camadas.sort(key=lambda c: 0 if c.nome.startswith("grad") else 1)
    cartao(plano, cfg, W, 250 if projeto.get("selo") else 190, cfg["cor_placa"])
    return plano
