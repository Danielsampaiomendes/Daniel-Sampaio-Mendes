"""Template TV 16:9 da clínica (padrão oficial, ref. "CO2 em manchas senis"). docs/CONHECIMENTO_DIVINE.md 5.2.

1920x1080, ~23 s em loop, 1 versão (TV não precisa de hook):
  centro    janela 4:5 com cantos arredondados, borda dourada fina, cantoneiras de visor e vinheta interna
  fundo     o mesmo vídeo muito desfocado e escurecido
  topo      DIVINE / MEDICAL SPA centralizado
  esquerda  mensagens em sequência (~4 s), título Italiana branco com palavra-chave dourada + Lora itálico dourado
  direita   fixo: TRATAMENTO, procedimento, indicação, "Ficou interessada?", pill e apoio (nunca "agende" nem endereço)
  final     ~6 s: logo empilhado grande, frase de marca, pill "FALE COM O NOSSO ATENDIMENTO", escurece para o loop
  rodapé    "Conteúdo informativo · Resultados variam · RT" o tempo todo

projeto.yaml:
  template: tv
  tv: {tratamento: "Laser de CO2", indicacao: "Manchas senis nas mãos"}
  mensagens: [{titulo: "...", apoio: "..."}]
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .. import brand
from ..compositor import Camada
from ..config import cor, load
from ..fonts import combinacao, marca
from ..text import Estilo, pill, render
from .divine import Plano


def _cfg() -> dict:
    return load("templates")["tv"]


def preparar(projeto: dict) -> None:
    cfg = _cfg()
    projeto["formato"] = "tv"
    projeto.setdefault("dissolve", cfg["dissolve"])
    for c in projeto.get("clipes") or []:
        c.setdefault("velocidade", cfg["velocidade"])
    projeto.setdefault("audio", {"original": False, "trilha": True})
    if not projeto.get("versoes"):
        projeto["versoes"] = [{"nome": "TV"}]
    projeto["versoes"] = projeto["versoes"][:1]
    projeto["versoes"][0]["fontes"] = "TV"
    projeto.setdefault("limite_mb", cfg["limite_mb"])


def tamanho_base(projeto: dict, W: int, H: int) -> tuple:
    w, h = _cfg()["janela"]
    return int(w), int(h)


def _mascara_janela(w: int, h: int, raio: int) -> np.ndarray:
    m = Image.new("L", (w * 2, h * 2), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * 2 - 1, h * 2 - 1), radius=raio * 2, fill=255)
    m = np.asarray(m.resize((w, h), Image.LANCZOS), np.float32) / 255
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    vinheta = 1 - 0.28 * np.clip((d - 0.55) / 0.85, 0, 1) ** 1.5
    return (m * vinheta)[..., None], m[..., None]


def _moldura_estatica(W: int, H: int, x0: int, y0: int, w: int, h: int, raio: int) -> Image.Image:
    """Borda dourada fina + cantoneiras de visor fora da janela."""
    S = 2
    img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ouro = cor("dourado_escuro") + (255,)
    d.rounded_rectangle((x0 * S, y0 * S, (x0 + w) * S - 1, (y0 + h) * S - 1), radius=raio * S, outline=ouro, width=2 * S)
    m, L, lw = 14, 46, 3
    for cx, cy, sx, sy in ((x0 - m, y0 - m, 1, 1), (x0 + w + m, y0 - m, -1, 1),
                           (x0 - m, y0 + h + m, 1, -1), (x0 + w + m, y0 + h + m, -1, -1)):
        d.line([(cx * S, cy * S), ((cx + sx * L) * S, cy * S)], fill=cor("dourado") + (255,), width=lw * S)
        d.line([(cx * S, cy * S), (cx * S, (cy + sy * L) * S)], fill=cor("dourado") + (255,), width=lw * S)
    return img.resize((W, H), Image.LANCZOS)


def montar(projeto, versao, combo_codigo, duracao_base, W, H, sfx_abertura, sfx_fechamento, sfx_transicao=None):
    cfg = _cfg()
    tvp = projeto.get("tv") or {}
    combo = combinacao("TV")
    jw, jh = (int(v) for v in cfg["janela"])
    x0, y0 = (W - jw) // 2, int(cfg["janela_y"])
    raio = int(cfg["raio"])
    margem = int(cfg["margem_lateral"])
    painel_w = x0 - margem - 60
    plano = Plano(barra_progresso=False)
    inicio_fech = max(1.0, duracao_base - 0.4)
    total = inicio_fech + float(cfg["fechamento_s"])
    plano.inicio_fechamento, plano.duracao_total = inicio_fech, total
    d0, d1 = cfg["duracao_alvo"]
    if not d0 <= total <= d1:
        print(f"  aviso: TV com {total:.1f}s (alvo ~23 s, entre {d0} e {d1} s); ajuste os clipes ou a velocidade")

    # composição: fundo desfocado + janela 4:5
    m_jan, m_borda = _mascara_janela(jw, jh, raio)
    esc = float(cfg["fundo_escurecer"])

    def moldura(q: np.ndarray, extras, t: float) -> np.ndarray:
        h = q.shape[0]
        faixa = q[int(h * 0.2):int(h * 0.2) + int(q.shape[1] * 9 / 16)]
        peq = Image.fromarray(faixa).resize((W // 8, H // 8), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3))
        fundo = np.asarray(peq.resize((W, H), Image.BICUBIC), np.float32) * esc
        reg = fundo[y0:y0 + jh, x0:x0 + jw]
        fundo[y0:y0 + jh, x0:x0 + jw] = reg * (1 - m_borda) + q.astype(np.float32) * m_jan
        return fundo.astype(np.uint8)

    plano.moldura = moldura
    plano.camadas.append(Camada(_moldura_estatica(W, H, x0, y0, jw, jh, raio), 0, 0, 0, inicio_fech + 0.2,
                                entrada=0.01, saida=0.6, deslize=0, nome="moldura"))

    # topo: letreiro centralizado
    let = brand.letreiro(44)
    plano.camadas.append(Camada(let, (W - let.width) // 2, 40, 0, inicio_fech + 0.2, entrada=0.8, saida=0.6,
                                deslize=0, nome="letreiro"))

    # rodapé fixo (fica também na tela final)
    rod = Estilo(arquivo=marca("rodape"), tamanho=17, cor=cor("rodape"))
    ir = render(cfg["rodape"], rod, rod, largura_max=W - 2 * margem, sombra=False)
    plano.camadas.append(Camada(ir, (W - ir.width) // 2, H - 46, 0, total + 1, entrada=0.8, saida=0.01, deslize=0,
                                nome="rodape"))
    plano.textos_tela.append(cfg["rodape"])

    # painel direito fixo
    xd = x0 + jw + 60
    centro_d = xd + painel_w // 2
    y = 330
    rot = pill(cfg["rotulo"], marca("rotulo"), 18, cor("dourado"), None, cor("dourado_escuro"), tracking=0.32)
    itens = [(rot, 0)]
    trat = tvp.get("tratamento") or projeto.get("titulo", "")
    it = render(trat, Estilo.de_config(combo["titulo"], 58, cor("off_white")),
                Estilo.de_config(combo["destaque"], 58, cor("dourado")), largura_max=painel_w)
    itens.append((it, 14))
    if tvp.get("indicacao"):
        ii = render(tvp["indicacao"], Estilo.de_config(combo["apoio"], 40, cor("dourado")), largura_max=painel_w)
        itens.append((ii, 2))
    ip = render(cfg["pergunta"], Estilo(marca("rodape"), 26, cor("texto")), largura_max=painel_w)
    itens.append((ip, 60))
    pp = pill(tvp.get("pill", cfg["pill"]), marca("pill"), 20, cor("fundo"), cor("dourado"), tracking=0.16)
    itens.append((pp, 14))
    ia = render(cfg["apoio_pill"], Estilo(marca("rodape"), 20, cor("rodape")), largura_max=painel_w, sombra=False)
    itens.append((ia, 10))
    for k, (img, gap) in enumerate(itens):
        y += gap
        plano.camadas.append(Camada(img, centro_d - img.width // 2, y, 0.6 + 0.15 * k, inicio_fech, entrada=1.0,
                                    saida=0.6, deslize=14, nome=f"painel_dir{k}"))
        y += img.height
    plano.textos_tela += [trat, tvp.get("indicacao") or "", cfg["pergunta"], tvp.get("pill", cfg["pill"]),
                          cfg["apoio_pill"]]

    # painel esquerdo: mensagens em sequência
    centro_e = margem + painel_w // 2
    t = 0.8
    passo = float(cfg["mensagem_s"])
    for k, m in enumerate(projeto.get("mensagens") or []):
        if t + 2.0 > inicio_fech:
            break
        fim = min(t + passo - 0.3, inicio_fech)
        tit = render(m.get("titulo", ""), Estilo.de_config(combo["titulo"], 64, cor("off_white")),
                     Estilo.de_config(combo["destaque"], 64, cor("dourado")), largura_max=painel_w)
        bloco_h = tit.height
        apo = None
        if m.get("apoio"):
            apo = render(m["apoio"], Estilo.de_config(combo["apoio"], 44, cor("dourado")), largura_max=painel_w)
            bloco_h += apo.height
        yb = int(H * 0.47 - bloco_h / 2)
        plano.camadas.append(Camada(tit, centro_e - tit.width // 2, yb, t, fim, entrada=0.9, saida=0.7, deslize=26,
                                    nome=f"msg{k}_titulo", texto=f"{m.get('titulo', '')} {m.get('apoio') or ''}"))
        if apo:
            plano.camadas.append(Camada(apo, centro_e - apo.width // 2, yb + tit.height - 6, t + 0.35, fim,
                                        entrada=0.9, saida=0.7, deslize=18, nome=f"msg{k}_apoio"))
        plano.textos_tela += [m.get("titulo", ""), m.get("apoio") or ""]
        t += passo
    plano.hook_fim = 0.0

    # tela final
    f0 = inicio_fech + 0.4
    emp = brand.empilhado(230)
    yf = 210
    plano.camadas_fechamento.append(Camada(emp, (W - emp.width) // 2, yf, f0, total + 1, entrada=1.1, saida=0.01,
                                           deslize=18, nome="logo_empilhado"))
    yf += emp.height + 48
    frase = tvp.get("frase_final", cfg["frase_final"])
    fi = render(frase, Estilo.de_config(combo["titulo"], 60, cor("off_white")),
                Estilo.de_config(combo["destaque"], 60, cor("dourado")), largura_max=1100)
    plano.camadas_fechamento.append(Camada(fi, (W - fi.width) // 2, yf, f0 + 0.4, total + 1, entrada=1.0, saida=0.01,
                                           deslize=16, nome="frase_final"))
    yf += fi.height + 26
    pf = pill(cfg["pill_final"], marca("pill"), 24, cor("fundo"), cor("dourado"), tracking=0.16)
    plano.camadas_fechamento.append(Camada(pf, (W - pf.width) // 2, yf, f0 + 0.8, total + 1, entrada=0.9, saida=0.01,
                                           deslize=12, nome="pill_final"))
    plano.textos_tela += [frase, cfg["pill_final"]]

    # áudio: swell discreto na entrada e chime suave no fim
    g = float(load("sfx").get("ganho_db", -24)) - 6
    plano.eventos_sfx.append((0.2, "swell_reverso_b", g))
    for nome in sfx_fechamento:
        plano.eventos_sfx.append((f0 + 0.3, nome, g + 2))
    return plano
