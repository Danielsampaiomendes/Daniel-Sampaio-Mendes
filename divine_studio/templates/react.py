"""Template React / tela dividida: referência em cima, quem fala embaixo. docs/CONHECIMENTO_DIVINE.md 5.5 e 5.6.

projeto.yaml:
  template: react
  clipes: [...]                 # quem fala (vai para a metade de baixo)
  clipes_referencia: [...]      # vídeo ou fotos de referência (metade de cima, sem som)
  credito: "@perfil"            # crédito fixo na janela da referência (obrigatório com conteúdo de terceiros)

  layout: auto | dividida | cabecinha   # auto escolhe pelo formato do vídeo de referência
  divisoria: auto | 0.6                 # dividida: parte de cima (vídeo); auto escolhe o melhor enquadramento

Layouts:
  dividida  - o vídeo em cima e você embaixo. Referência vertical/quadrada: 60% vídeo, 40% você (corte que preenche).
              Referência deitada (16:9): o vídeo inteiro sem corte, sobre um fundo desfocado dele mesmo, em 50%.
  cabecinha - o vídeo em tela cheia e você numa janela redonda no canto (melhor para referência vertical, Reels).

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


def _proporcao_ref(projeto: dict) -> float:
    """Largura/altura do primeiro vídeo (ou foto) de referência."""
    if "_ar_ref" in projeto:
        return projeto["_ar_ref"]
    ar = 9 / 16
    try:
        from ..ingest import probe, resolver
        c = (projeto.get("clipes_referencia") or [])[0]
        arq = resolver(projeto, c["arquivo"])
        if arq.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".heic"):
            from PIL import Image
            with Image.open(arq) as im:
                ar = im.width / im.height
        else:
            pr = probe(arq)
            ar = pr["largura"] / max(1, pr["altura"])
    except Exception:
        pass
    projeto["_ar_ref"] = ar
    return ar


def layout(projeto: dict) -> str:
    lay = projeto.get("layout") or load("templates")["react"].get("layout", "auto")
    if lay == "auto":
        lay = "cabecinha" if _proporcao_ref(projeto) < 0.7 else "dividida"
    return lay


def _deitada(projeto: dict) -> bool:
    return _proporcao_ref(projeto) >= 1.2


def _div_frac(projeto: dict) -> float:
    d = projeto.get("divisoria", load("templates")["react"].get("divisoria", "auto"))
    if d not in (None, "auto"):
        return float(d)
    return 0.5 if _deitada(projeto) else 0.6       # deitada: vídeo inteiro em 50%; vertical/quadrada: 60/40


def _div(H: int, projeto: dict | None = None) -> int:
    return int(H * (_div_frac(projeto) if projeto is not None else 0.5)) // 2 * 2


def _lado_cabecinha(W: int) -> int:
    return int(W * float(load("templates")["react"].get("cabecinha_tamanho", 0.34))) // 2 * 2


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
    if layout(projeto) == "cabecinha":
        for c in projeto.get("clipes") or []:
            c.setdefault("foco", [0.5, 0.3])                # rosto costuma ficar no terço de cima
    if layout(projeto) == "cabecinha" and projeto.get("legendas"):
        projeto["legendas"] = {**projeto["legendas"], "posicao": 0.58}     # legenda no meio, longe da janela redonda


def tamanho_base(projeto: dict, W: int, H: int) -> tuple:
    if layout(projeto) == "cabecinha":
        lado = _lado_cabecinha(W)
        return lado, lado
    return W, H - _div(H, projeto)


def extras(projeto: dict, W: int, H: int) -> list:
    if layout(projeto) == "cabecinha":
        return [{"nome": "base_ref", "clipes": projeto["clipes_referencia"], "largura": W, "altura": H}]
    if _deitada(projeto):                          # vídeo deitado inteiro, sem corte (o fundo desfocado vem dele)
        alt = int(W / _proporcao_ref(projeto)) // 2 * 2
        return [{"nome": "base_ref", "clipes": projeto["clipes_referencia"], "largura": W, "altura": alt}]
    return [{"nome": "base_ref", "clipes": projeto["clipes_referencia"], "largura": W, "altura": _div(H, projeto)}]


def montar(projeto, versao, combo, duracao_base, W, H, sfx_abertura, sfx_fechamento, sfx_transicao=None):
    escala = W / 1080.0
    lay = layout(projeto)
    div = _div(H, projeto)
    plano = divine.montar(projeto, versao, combo, duracao_base, W, H, sfx_abertura, sfx_fechamento, sfx_transicao,
                          divine.Opcoes(gradientes=True))
    linha = np.array(cor("dourado_escuro"), np.uint8)

    if lay == "cabecinha":
        from PIL import Image, ImageDraw
        lado = _lado_cabecinha(W)
        mascara = Image.new("L", (lado * 2, lado * 2), 0)
        ImageDraw.Draw(mascara).ellipse((0, 0, lado * 2 - 1, lado * 2 - 1), fill=255)
        m = np.asarray(mascara.resize((lado, lado), Image.LANCZOS), np.float32)[..., None] / 255
        anel = Image.new("RGBA", (lado * 2 + 16, lado * 2 + 16), (0, 0, 0, 0))
        ImageDraw.Draw(anel).ellipse((2, 2, lado * 2 + 13, lado * 2 + 13), outline=cor("dourado") + (255,), width=10)
        anel = np.asarray(anel.resize((lado + 8, lado + 8), Image.LANCZOS), np.float32) / 255
        seg = load("marca")["area_segura"]
        x0 = W - lado - int(seg["direita"] * escala * 0.6)
        y0 = H - lado - int(seg["base"] * escala * 0.9)

        def moldura(q, extras, t):
            quadro = (extras[0] if extras else np.zeros((H, W, 3), np.uint8)).copy()
            reg = quadro[y0:y0 + lado, x0:x0 + lado].astype(np.float32)
            quadro[y0:y0 + lado, x0:x0 + lado] = (reg * (1 - m) + q[:lado, :lado].astype(np.float32) * m).astype(np.uint8)
            ay, ax = y0 - 4, x0 - 4
            sub = quadro[ay:ay + anel.shape[0], ax:ax + anel.shape[1]].astype(np.float32)
            a = anel[:sub.shape[0], :sub.shape[1], 3:4]
            quadro[ay:ay + sub.shape[0], ax:ax + sub.shape[1]] = (sub * (1 - a) + anel[:sub.shape[0], :sub.shape[1], :3] * 255 * a).astype(np.uint8)
            return quadro
    elif _deitada(projeto):
        from PIL import Image, ImageFilter

        def moldura(q, extras, t):
            ref = extras[0] if extras else np.zeros((div // 2, W, 3), np.uint8)
            fundo = Image.fromarray(ref).resize((W // 6, div // 6), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3))
            fundo = (np.asarray(fundo.resize((W, div), Image.BILINEAR), np.float32) * 0.45).astype(np.uint8)
            y = max(0, (div - ref.shape[0]) // 2)
            fundo[y:y + ref.shape[0]] = ref[:div - y]
            quadro = np.concatenate([fundo, q], axis=0)
            quadro[div - 1:div + 2] = linha
            return quadro
    else:
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
        y_cred = (int(230 * escala) if lay == "cabecinha" else div - cp.height - int(16 * escala))
        plano.camadas.append(Camada(cp, W - cp.width - int(150 * escala), y_cred, 0,
                                    plano.inicio_fechamento, entrada=0.6, saida=0.5, deslize=0, nome="credito"))
        plano.textos_tela.append(txt)
    return plano
