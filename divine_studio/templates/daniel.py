"""Template Daniel (@drdanielmendess): base Divine suave + cartão com a foto oficial, nome, selo verificado e @.

Placas em verde-petróleo (#143A3F, cor dos posts dele), logo oficial Divine no topo. docs/CONHECIMENTO_DIVINE.md 5.3.
"""
from __future__ import annotations

from ..config import load
from . import divine
from ._pessoa import cartao


def montar(projeto, versao, combo, duracao_base, W, H, sfx_abertura, sfx_fechamento, sfx_transicao=None):
    cfg = load("templates")["daniel"]
    plano = divine.montar(projeto, versao, combo, duracao_base, W, H, sfx_abertura, sfx_fechamento, sfx_transicao,
                          divine.Opcoes(cor_placa=cfg["cor_placa"]))
    cartao(plano, cfg, W, 250 if projeto.get("selo") else 190, cfg["cor_placa"])
    return plano
