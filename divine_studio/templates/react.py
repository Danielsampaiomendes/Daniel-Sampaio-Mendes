"""Template React / tela dividida: referência em cima, quem fala embaixo. docs/CONHECIMENTO_DIVINE.md 5.5 e 5.6.

projeto.yaml:
  template: react
  clipes: [...]                 # quem fala (vai para a metade de baixo)
  clipes_referencia: [...]      # vídeo ou fotos de referência (metade de cima, sem som)
  credito: "@perfil"            # crédito fixo na janela da referência (obrigatório com conteúdo de terceiros)

A legenda da fala fica logo acima da cabeça de quem fala, nunca sobre a janela da referência.
Com pessoa pública: nunca afirmar procedimentos que ela fez, dar crédito e cortar vinheta de outra clínica.
"""
from __future__ import annotations

import numpy as np

from ..compositor import Camada
from ..config import cor, load
from ..fonts import marca
from ..text import pill
from . import divine


def _div(H: int) -> int:
    return int(H * float(load("templates")["react"]["divisoria"])) // 2 * 2


def preparar(projeto: dict) -> None:
    cfg = load("templates")["react"]
    if not projeto.get("clipes_referencia"):
        raise SystemExit("Template react precisa de 'clipes_referencia' (o vídeo ou as fotos de referência).")
    if not projeto.get("credito"):
        print("  aviso: sem 'credito' no projeto; conteúdo de terceiros precisa de crédito fixo")
    leg = projeto.get("legendas")
    if leg:
        base = leg if isinstance(leg, dict) else {}
        projeto["legendas"] = {"posicao": cfg["legenda_posicao"], **base}
    for c in projeto["clipes_referencia"]:
        c.setdefault("mudo", True)


def tamanho_base(projeto: dict, W: int, H: int) -> tuple:
    return W, H - _div(H)


def extras(projeto: dict, W: int, H: int) -> list:
    return [{"nome": "base_ref", "clipes": projeto["clipes_referencia"], "largura": W, "altura": _div(H)}]


def montar(projeto, versao, combo, duracao_base, W, H, sfx_abertura, sfx_fechamento, sfx_transicao=None):
    escala = W / 1080.0
    div = _div(H)
    plano = divine.montar(projeto, versao, combo, duracao_base, W, H, sfx_abertura, sfx_fechamento, sfx_transicao,
                          divine.Opcoes(gradientes=True))
    linha = np.array(cor("dourado_escuro"), np.uint8)

    def moldura(q, extras, t):
        ref = extras[0] if extras else np.zeros((div, W, 3), np.uint8)
        quadro = np.concatenate([ref[:div], q], axis=0)
        quadro[div - 1:div + 2] = linha
        return quadro

    plano.moldura = moldura
    if projeto.get("credito"):
        prefixo = load("templates")["react"]["credito_prefixo"]
        txt = f"{prefixo} {projeto['credito']}"
        cp = pill(txt, marca("rotulo"), 18 * escala, cor("off_white"), cor("fundo"), cor("dourado_escuro"),
                  tracking=0.12, alpha_fundo=170)
        plano.camadas.append(Camada(cp, W - cp.width - int(150 * escala), div - cp.height - int(16 * escala), 0,
                                    plano.inicio_fechamento, entrada=0.6, saida=0.5, deslize=0, nome="credito"))
        plano.textos_tela.append(txt)
    return plano
