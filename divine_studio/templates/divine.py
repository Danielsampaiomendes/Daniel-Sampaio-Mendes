"""Template Divine suave/glamour (padrão de Reels e Stories) e peças reaproveitadas pelos outros templates.

Estrutura (docs/CONHECIMENTO_DIVINE.md 5.1 + Código Viral):
  0 a 3 s   hook em 1 ou 2 batidas (texto já no 1º quadro, fade + deslize lento)
  logo após CTA antecipado curto (pílula no terço de baixo)
  meio      mensagens com tempo de leitura, sem numeração
  fim       fechamento curto: logo empilhado, frase, pill de CTA, endereço, aviso e RT; escurece para o loop
Fixos: barra de progresso dourada, header DIVINE horizontal, escurecimento suave atrás do texto.

Os templates Daniel, George e React chamam `montar(..., opcoes=Opcoes(...))` e acrescentam as próprias camadas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .. import brand, efeitos, legendas
from ..compositor import Camada, gradiente_vertical
from ..config import cor, load
from ..fonts import combinacao, marca
from ..rodizio import familias
from ..text import Estilo, contar_palavras, pill, render


@dataclass
class Plano:
    camadas: list = field(default_factory=list)       # Camada
    camadas_fechamento: list = field(default_factory=list)
    eventos_sfx: list = field(default_factory=list)   # (s, nome, ganho_db)
    textos_tela: list = field(default_factory=list)   # para o revisor
    inicio_fechamento: float = 0.0
    duracao_total: float = 0.0
    hook_fim: float = 0.0
    # composição do quadro (TV e React): a base tem outro tamanho e a moldura monta o quadro final
    moldura: Callable | None = None                   # moldura(quadro_base, extras, t) -> quadro W x H
    barra_progresso: bool = True
    efeitos_quadro: list = field(default_factory=list)  # efeitos que mexem no próprio vídeo (zoom digital)


@dataclass
class Opcoes:
    header: bool = True
    cor_placa: str = "fundo"              # fundo das placas (CTA, selo): navy no George, petróleo no Daniel
    fechamento_marca: bool = True         # logo, pill, endereço, aviso e RT
    posicao_hook: str | None = None       # topo | centro | base (padrão: posicao_texto do projeto)
    y_selo: float = 176                   # px em 1080 de largura
    gradientes: bool = True


def tempo_leitura(texto: str, minimo: float | None = None) -> float:
    p = load("preferencias")["texto"]
    m = p["tempo_minimo_s"] if minimo is None else minimo
    return max(m, contar_palavras(texto) / p["leitura_palavras_por_s"] + 0.7)


def zona(posicao: str, H: int) -> float:
    """Centro vertical do bloco de texto principal."""
    return {"topo": H * 0.30, "centro": H * 0.47, "base": H * 0.66}.get(posicao, H * 0.30)


def bloco(titulo: str, apoio: str | None, combo: dict, tam: float, largura_max: float,
          cor_titulo: str = "off_white", cor_apoio: str = "texto"):
    """Título (+ apoio) renderizados com a combinação de fontes; devolve (img_titulo, img_apoio|None)."""
    dourado = cor("dourado")
    et = Estilo.de_config(combo["titulo"], tam, cor(cor_titulo))
    ed = Estilo.de_config(combo["destaque"], tam, dourado)
    it = render(titulo, et, ed, largura_max=largura_max)
    ia = None
    if apoio:
        ea = Estilo.de_config(combo["apoio"], tam * 0.62, cor(cor_apoio))
        eda = Estilo.de_config(combo["apoio"], tam * 0.62, dourado)
        ia = render(apoio, ea, eda, largura_max=largura_max)
    return it, ia


def placa(img, escala: float, opacidade: int = 150, cor_fundo: str = "fundo"):
    """Placa arredondada com borda dourada fina atrás de um texto (CTA)."""
    from PIL import Image, ImageDraw
    px, py = int(30 * escala), int(14 * escala)
    W, H = img.width + 2 * px, img.height + 2 * py
    base = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    d.rounded_rectangle((2, 2, W * 2 - 3, H * 2 - 3), radius=H, fill=cor(cor_fundo) + (opacidade,),
                        outline=cor("dourado_escuro") + (200,), width=3)
    base = base.resize((W, H), Image.LANCZOS)
    base.alpha_composite(img, (px, py))
    return base


def montar(projeto: dict, versao: dict, combo_codigo: str, duracao_base: float, W: int, H: int,
           sfx_abertura: list, sfx_fechamento: list, sfx_transicao: list | None = None,
           opcoes: Opcoes | None = None) -> Plano:
    op = opcoes or Opcoes()
    pref = load("preferencias")
    marca_cfg = load("marca")
    sfx_cfg = load("sfx")
    an = pref["animacao"]
    ent, sai, desl = an["entrada_s"], an["saida_s"], an["deslize_px"]
    seg = marca_cfg["area_segura"]
    larg = min(pref["texto"]["largura_max_px"], W - seg["esquerda"] - seg["direita"] - 20)
    combo = combinacao(combo_codigo)
    escala = W / 1080.0
    plano = Plano()

    fech_cfg = projeto.get("fechamento") or {}
    dur_fech = float(fech_cfg.get("duracao", pref["fechamento"]["duracao_s"] if op.fechamento_marca else 1.2))
    inicio_fech = max(0.5, duracao_base - 0.5)
    total = inicio_fech + dur_fech
    plano.inicio_fechamento, plano.duracao_total = inicio_fech, total

    # Escurecimento suave para leitura (topo e base)
    if op.gradientes:
        plano.camadas.append(Camada(gradiente_vertical(W, int(H * 0.52), 0, int(H * 0.52), 0.62, True),
                                    0, 0, 0, inicio_fech + 0.3, entrada=0.01, saida=0.4, deslize=0, nome="grad_topo"))
        plano.camadas.append(Camada(gradiente_vertical(W, int(H * 0.30), 0, int(H * 0.30), 0.45, False),
                                    0, int(H * 0.70), 0, inicio_fech + 0.3, entrada=0.01, saida=0.4, deslize=0,
                                    nome="grad_base"))

    # Header horizontal (logo oficial)
    if op.header:
        hdr = brand.horizontal(int(64 * escala))
        plano.camadas.append(Camada(hdr, (W - hdr.width) // 2, int(86 * escala), 0, inicio_fech + 0.2,
                                    entrada=0.6, saida=0.5, deslize=0, nome="header"))

    posicao = projeto.get("posicao_texto", "topo")
    centro = zona(op.posicao_hook or posicao, H)

    # Hook: 1 ou 2 batidas
    t = 0.0
    batidas = versao.get("hook") or []
    if isinstance(batidas, dict):
        batidas = [batidas]
    for k, b in enumerate(batidas):
        tit, apo = b.get("titulo", ""), b.get("apoio")
        dur = float(b.get("duracao") or tempo_leitura(tit + " " + (apo or "")))
        it, ia = bloco(tit, apo, combo, 92 * escala, larg)
        altura = it.height + (ia.height - 10 if ia else 0)
        y = int(centro - altura / 2)
        fim = t + dur
        e0 = 0.55 if k == 0 else ent
        plano.camadas.append(Camada(it, (W - it.width) // 2, y, t, fim, entrada=e0, saida=sai, deslize=desl,
                                    nome=f"hook{k}_titulo", texto=f"{tit} {apo or ''}"))
        if ia:
            plano.camadas.append(Camada(ia, (W - ia.width) // 2, y + it.height - 10, t + 0.45, fim,
                                        entrada=ent, saida=sai, deslize=desl * 0.7, nome=f"hook{k}_apoio"))
        plano.textos_tela += [tit] + ([apo] if apo else [])
        t = fim + (0.05 if k < len(batidas) - 1 else 0.0)
    plano.hook_fim = t

    # SFX de abertura (baixo)
    g = float(sfx_cfg.get("ganho_db", -24))
    for nome in sfx_abertura:
        plano.eventos_sfx.append((0.05, nome, g - (2 if "impacto" in nome else 0)))

    # Selo fixo (opcional) depois do hook
    selo = projeto.get("selo")
    if selo:
        sp = pill(selo, marca("rotulo"), 20 * escala, cor("dourado"), cor(op.cor_placa), cor("dourado_escuro"),
                  tracking=0.26, alpha_fundo=150 if op.cor_placa == "fundo" else 235)
        plano.camadas.append(Camada(sp, (W - sp.width) // 2, int(op.y_selo * escala),
                                    float(projeto.get("selo_inicio", plano.hook_fim + 0.1)), inicio_fech,
                                    entrada=ent, saida=sai, deslize=0, nome="selo"))
        plano.textos_tela.append(selo)

    # CTA antecipado (curto, logo depois do hook)
    cta = projeto.get("cta_antecipado")
    y_cta = int((H - seg["base"]) - 150 * escala) if posicao != "base" else int(300 * escala)
    if cta:
        cta_txt = cta if isinstance(cta, str) else cta.get("texto", "")
        c_ini = plano.hook_fim + 0.15 if isinstance(cta, str) else float(cta.get("inicio", plano.hook_fim + 0.15))
        c_dur = tempo_leitura(cta_txt, 2.4) if isinstance(cta, str) else float(cta.get("duracao", tempo_leitura(cta_txt, 2.4)))
        ec = Estilo(arquivo=marca("pill"), tamanho=36 * escala, cor=cor("off_white"))
        ecd = Estilo(arquivo=marca("pill"), tamanho=36 * escala, cor=cor("dourado"))
        ic = placa(render(cta_txt, ec, ecd, largura_max=larg * 0.9, sombra=False), escala,
                   150 if op.cor_placa == "fundo" else 225, op.cor_placa)
        plano.camadas.append(Camada(ic, (W - ic.width) // 2, y_cta, c_ini, min(c_ini + c_dur, inicio_fech),
                                    entrada=ent, saida=sai, deslize=desl * 0.6, nome="cta_antecipado", texto=cta_txt))
        plano.textos_tela.append(cta_txt)
        t_msg = c_ini + 0.6
    else:
        t_msg = plano.hook_fim + 0.2

    # Mensagens do meio
    for k, m in enumerate(projeto.get("mensagens") or []):
        tit, apo = m.get("titulo", ""), m.get("apoio")
        ini = float(m.get("inicio", t_msg))
        if m.get("na_fala"):
            t_fala = legendas.achar_fala(projeto.get("_fala") or [], m["na_fala"])
            if t_fala is None:
                print(f"  aviso: não achei \"{m['na_fala']}\" na fala; mensagem entra em sequência")
            else:
                # nunca em cima do hook nem da mensagem anterior (mesma zona da tela)
                ini = max(t_fala, plano.hook_fim + 0.1, t_msg - 0.2 if k else 0.0)
        dur = float(m["fim"]) - ini if "fim" in m else tempo_leitura(tit + " " + (apo or ""))
        fim = min(ini + dur, inicio_fech)
        if fim - ini < 0.8:
            continue
        cm = zona(m.get("posicao", posicao), H)
        it, ia = bloco(tit, apo, combo, 76 * escala, larg)
        altura = it.height + (ia.height - 8 if ia else 0)
        y = int(cm - altura / 2)
        plano.camadas.append(Camada(it, (W - it.width) // 2, y, ini, fim, entrada=ent, saida=sai, deslize=desl,
                                    nome=f"msg{k}_titulo", texto=f"{tit} {apo or ''}"))
        if ia:
            plano.camadas.append(Camada(ia, (W - ia.width) // 2, y + it.height - 8, ini + 0.35, fim,
                                        entrada=ent, saida=sai, deslize=desl * 0.7, nome=f"msg{k}_apoio"))
        plano.textos_tela += [tit] + ([apo] if apo else [])
        t_msg = fim + 0.25

    # Legenda da fala sincronizada (fonte fixa da marca)
    if legendas.ativas(projeto) and projeto.get("_fala"):
        cam, txts = legendas.camadas(projeto, projeto["_fala"], W, H, inicio_fech)
        plano.camadas += cam
        plano.textos_tela += txts

    efeitos.aplicar(plano, projeto, versao, combo, W, H, int(load("exportacao")["fps"]))
    transicoes(plano, projeto, sfx_abertura, sfx_fechamento, sfx_transicao, inicio_fech)
    if op.fechamento_marca:
        fechamento(plano, projeto, combo, W, H, larg, sfx_fechamento)
    else:
        fechamento_simples(plano, projeto, combo, W, H, larg, sfx_fechamento)
    return plano


def transicoes(plano: Plano, projeto: dict, sfx_abertura, sfx_fechamento, sfx_transicao, inicio_fech: float):
    """Whoosh baixo só na troca entre clipes diferentes, se couber no limite de famílias por vídeo."""
    sfx_cfg = load("sfx")
    if not sfx_transicao or len(familias(sfx_abertura, sfx_fechamento, sfx_transicao)) > int(sfx_cfg.get("max_familias", 4)):
        return
    ultimo_t, n_tr = -99.0, 0
    for c in (projeto.get("_base_meta") or {}).get("clipes", [])[1:]:
        d = float(c.get("transicao", 0))
        t_tr = float(c.get("inicio_base", 0))
        if d <= 0 or t_tr < plano.hook_fim or t_tr > inicio_fech - 0.5:
            continue
        if t_tr - ultimo_t < float(sfx_cfg.get("transicao_intervalo_s", 4.0)) or n_tr >= int(sfx_cfg.get("transicao_max", 3)):
            continue
        for nome in sfx_transicao:
            plano.eventos_sfx.append((max(0.0, t_tr - 0.15), nome, float(sfx_cfg.get("transicao_ganho_db", -30))))
        ultimo_t, n_tr = t_tr, n_tr + 1


def fechamento(plano: Plano, projeto: dict, combo: dict, W: int, H: int, larg: float, sfx_fechamento: list):
    """Fechamento curto da marca: logo empilhado, frase, pill de CTA, endereço, aviso e RT."""
    marca_cfg = load("marca")
    seg = marca_cfg["area_segura"]
    desl = load("preferencias")["animacao"]["deslize_px"]
    fech_cfg = projeto.get("fechamento") or {}
    escala = W / 1080.0
    total = plano.duracao_total
    f0 = plano.inicio_fechamento + 0.35
    emp = brand.empilhado(int(150 * escala))
    y = int(H * 0.27)
    plano.camadas_fechamento.append(Camada(emp, (W - emp.width) // 2, y, f0, total + 1, entrada=0.9, saida=0.01,
                                           deslize=16, nome="logo_empilhado"))
    y += emp.height + int(56 * escala)
    frase = fech_cfg.get("frase")
    if frase:
        it, _ = bloco(frase, None, combo, 60 * escala, larg)
        plano.camadas_fechamento.append(Camada(it, (W - it.width) // 2, y, f0 + 0.3, total + 1, entrada=0.9,
                                               saida=0.01, deslize=desl * 0.6, nome="frase_final"))
        y += it.height + int(18 * escala)
        plano.textos_tela.append(frase)
    cta_final = fech_cfg.get("cta", "Agende sua avaliação")
    pf = pill(cta_final, marca("pill"), 26 * escala, cor("fundo"), cor("dourado"), tracking=0.16)
    plano.camadas_fechamento.append(Camada(pf, (W - pf.width) // 2, y, f0 + 0.6, total + 1, entrada=0.8,
                                           saida=0.01, deslize=12, nome="pill_cta"))
    plano.textos_tela.append(cta_final)
    y += pf.height + int(30 * escala)
    end = Estilo(arquivo="Jost[wght].ttf", tamanho=22 * escala, cor=cor("off_white"), peso=300, caixa_alta=True,
                 tracking=0.16)
    ie = render(marca_cfg["clinica"]["endereco"].replace(" - ", " · "), end, end, largura_max=W, sombra=False)
    plano.camadas_fechamento.append(Camada(ie, (W - ie.width) // 2, y, f0 + 0.8, total + 1, entrada=0.8,
                                           saida=0.01, deslize=0, nome="endereco"))
    y += ie.height + int(4 * escala)
    linhas = [marca_cfg["aviso_resultados"]]
    if projeto.get("conteudo_medico", True):
        linhas.append(marca_cfg["responsavel_tecnico"]["curto"])
    rod = Estilo(arquivo=marca("rodape"), tamanho=19 * escala, cor=cor("rodape"))
    for k, ln in enumerate(linhas):
        ir = render(ln, rod, rod, largura_max=W - 80, sombra=False)
        plano.camadas_fechamento.append(Camada(ir, (W - ir.width) // 2, y, f0 + 0.9, total + 1, entrada=0.8,
                                               saida=0.01, deslize=0, nome=f"rodape{k}"))
        y += ir.height - 4
    plano.textos_tela += linhas
    if y > H - seg["base"] + 40:
        print(f"  aviso: o fechamento passou da área segura (y={y})")
    g = float(load("sfx").get("ganho_db", -24))
    for nome in sfx_fechamento:
        plano.eventos_sfx.append((f0 + 0.2, nome, g))


def fechamento_simples(plano: Plano, projeto: dict, combo: dict, W: int, H: int, larg: float, sfx_fechamento: list):
    """Sem marca: só a frase final (se houver) sobre o fundo desfocado."""
    escala = W / 1080.0
    frase = (projeto.get("fechamento") or {}).get("frase")
    f0 = plano.inicio_fechamento + 0.25
    if frase:
        it, _ = bloco(frase, None, combo, 70 * escala, larg)
        plano.camadas_fechamento.append(Camada(it, (W - it.width) // 2, int(H * 0.42), f0, plano.duracao_total + 1,
                                               entrada=0.8, saida=0.01, deslize=20, nome="frase_final"))
        plano.textos_tela.append(frase)
    g = float(load("sfx").get("ganho_db", -24))
    for nome in sfx_fechamento:
        plano.eventos_sfx.append((f0, nome, g))
