"""Carrosséis do Instagram no padrão Divine: rascunho por fórmula, cards editáveis e exportação em PNG.

  python3 -m divine_studio carrossel novo "Laser de CO2 no corpo" --formula mito_verdade
  python3 -m divine_studio carrossel exportar projetos/2026-11-01_carrossel-laser-de-co2-no-corpo

projeto.yaml de um carrossel:
  tipo: carrossel
  estilo: divine | claro | daniel | george | pessoal      (config/carrossel.yaml)
  fontes: O3                                               (combinação; sem isso, rodízio)
  formula: lista | mito_verdade | metodo | pergunta | expectativa | livre
  objetivo: salvar | enviar | comentar | seguir
  cards:
    - {layout: capa, titulo: "...", apoio: "...", foto: bruto/foto.jpg}
    - {layout: texto, titulo: "...", texto: "..."}
    - {layout: lista, titulo: "...", itens: [a, b, c]}
    - {layout: mito_verdade, mito: "...", verdade: "..."}
    - {layout: citacao, texto: "...", pessoa: daniel}
    - {layout: cta, titulo: "...", pedido: "..."}
"""
from __future__ import annotations

import dataclasses
import io
import re
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .config import ROOT, hexrgb, hoje, load, slug
from .fonts import combinacao
from .text import Estilo, render

LAYOUTS = ["capa", "texto", "lista", "mito_verdade", "citacao", "cta"]
IMAGEM = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


def _cfg() -> dict:
    return load("carrossel")


def tamanho(p: dict) -> tuple:
    f = load("exportacao")["formatos"][p.get("formato") or _cfg().get("formato", "feed45")]
    return int(f["largura"]), int(f["altura"])


# ---------------------------------------------------------------- rascunho (como os geradores de carrossel com IA)

def rascunho(titulo: str, formula: str = "lista", objetivo: str | None = None, semente: int = 0) -> list:
    """Cards prontos para editar a partir do tema e da fórmula, com textos aprovados (config/roteiros e carrossel)."""
    from .auto import tema
    from .hooks import sortear
    cfg = _cfg()
    chave, rot = tema(titulo)
    objetivo = objetivo or cfg["formulas"].get(formula, {}).get("objetivo", "salvar")
    pedido = cfg["pedidos"].get(objetivo, cfg["pedidos"]["salvar"])
    assunto = (rot.get("selo") or titulo).strip()
    assunto_min = _sigla(assunto) if assunto.isupper() else assunto
    hs = sortear(1, tema=titulo, semente=semente)
    gancho = hs[0]["batidas"][0] if hs else titulo
    cards = []
    if formula == "mito_verdade":
        mitos = list(cfg["mitos"].get(chave) or [])
        mitos += [m for m in cfg["mitos"]["padrao"] if m not in mitos][: max(0, 3 - len(mitos))]   # mínimo de 5 cards
        mitos = mitos[:4]
        cards.append({"layout": "capa", "titulo": f"Mitos sobre / *{assunto_min}*",
                      "apoio": "o primeiro é o que mais aparece"})
        cards += [{"layout": "mito_verdade", **m} for m in mitos]
        cards.append({"layout": "cta", "titulo": "Agora você *sabe.*", "pedido": cfg["pedidos"]["enviar"]})
    elif formula == "metodo":
        m = cfg["metodo"]
        cards.append({"layout": "capa", "titulo": f"Como funciona o / *{m['nome']}*", "apoio": "um pilar por vez"})
        cards += [{"layout": "texto", "titulo": f"*{p['titulo']}*", "texto": p["texto"]} for p in m["pilares"]]
        cards.append({"layout": "lista", "titulo": f"O {m['nome']} / *inteiro:*",
                      "itens": [p["titulo"] for p in m["pilares"]]})
        cards.append({"layout": "cta", "titulo": "Tudo começa / na *avaliação.*", "pedido": pedido})
    elif formula == "pergunta":
        msgs = rot.get("mensagens") or []
        cards.append({"layout": "capa", "titulo": f"*{assunto_min}:* / a pergunta que mais recebemos",
                      "apoio": "pergunta frequente"})
        cards += [{"layout": "texto", "titulo": m["titulo"], "texto": m.get("apoio", "")} for m in msgs[:4]]
        cards.append({"layout": "cta", "titulo": "Ficou alguma *dúvida?*", "pedido": pedido})
    elif formula == "expectativa":
        cards.append({"layout": "capa", "titulo": f"*{assunto_min}:* / expectativa x realidade",
                      "apoio": "sobre a experiência, não sobre resultado"})
        pares = [("Vai doer muito.", "A maioria sente só um calorzinho, e a equipe ajusta o conforto."),
                 ("Vou sair do consultório outra pessoa.", "O corpo responde no tempo dele, com acompanhamento."),
                 ("É só marcar e fazer.", "Antes vem a avaliação, que define se é indicado para você.")]
        cards += [{"layout": "mito_verdade", "mito": a, "verdade": b, "rotulos": ["Expectativa", "Realidade"]}
                  for a, b in pares]
        cards.append({"layout": "cta", "titulo": "Expectativa *alinhada* / é cuidado.", "pedido": pedido})
    elif formula == "livre":
        cards.append({"layout": "capa", "titulo": gancho, "apoio": ""})
        cards += [{"layout": "texto", "titulo": m["titulo"], "texto": m.get("apoio", "")}
                  for m in (rot.get("mensagens") or [])[:3]]
        cards.append({"layout": "cta", "titulo": (rot.get("fechamento") or "Cada pele tem o *seu tempo.*"),
                      "pedido": pedido})
    else:   # lista (IG5)
        itens = [re.sub(r"\s*/\s*", " ", m["titulo"]) for m in (rot.get("mensagens") or [])][:5]
        n = len(itens)
        cards.append({"layout": "capa", "titulo": f"{n} coisas sobre / *{assunto_min}*",
                      "apoio": "a última quase ninguém sabe"})
        cards += [{"layout": "texto", "titulo": it, "texto": m.get("apoio", "")}
                  for it, m in zip(itens, rot.get("mensagens") or [])]
        cards.append({"layout": "lista", "titulo": "Para *salvar:*", "itens": [i.replace("*", "") for i in itens]})
        cards.append({"layout": "cta", "titulo": rot.get("fechamento", "Cada pele tem o *seu tempo.*"), "pedido": pedido})
    return cards[: _cfg().get("max_cards", 8)]


def novo(titulo: str, formula: str = "lista", objetivo: str | None = None, estilo: str = "divine") -> Path:
    pasta = ROOT / "projetos" / f"{hoje()}_carrossel-{slug(titulo)}"
    if pasta.exists():
        raise SystemExit(f"Já existe: {pasta.relative_to(ROOT)}")
    for sub in ("bruto", "trabalho", "saida"):
        (pasta / sub).mkdir(parents=True)
    cfg = _cfg()
    objetivo = objetivo or cfg["formulas"].get(formula, {}).get("objetivo", "salvar")
    p = {"tipo": "carrossel", "titulo": titulo, "data": hoje(), "estilo": estilo, "formato": cfg.get("formato", "feed45"),
         "formula": formula, "objetivo": objetivo, "conteudo_medico": estilo != "pessoal",
         "autorizacao_imagem": "nao_aparece", "tags": ["carrossel"],
         "cards": rascunho(titulo, formula, objetivo, semente=sum(map(ord, titulo)))}
    salvar(pasta, p)
    return pasta


def salvar(pasta: Path, p: dict) -> None:
    import yaml
    dados = {k: v for k, v in p.items() if not k.startswith("_")}
    (pasta / "projeto.yaml").write_text("# Carrossel do Divine Studio (edite no painel ou aqui).\n" + yaml.safe_dump(
        dados, allow_unicode=True, sort_keys=False, width=1000, default_flow_style=None), encoding="utf-8")


# ---------------------------------------------------------------- desenho dos cards

def _abrir_imagem(arq: Path) -> Image.Image:
    if arq.suffix.lower() in (".heic", ".heif"):
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            import shutil
            import subprocess
            import tempfile
            if not shutil.which("sips"):
                raise SystemExit("Foto HEIC: no Mac funciona sozinho; aqui, mande em JPG.")
            tmp = Path(tempfile.mkdtemp()) / "foto.jpg"
            subprocess.run(["sips", "-s", "format", "jpeg", str(arq), "--out", str(tmp)], check=True,
                           capture_output=True)
            arq = tmp
    return ImageOps.exif_transpose(Image.open(arq)).convert("RGB")


def _estilos(p: dict, est: dict, tam: float):
    """Título (combo, caixa alta, degradê no fundo escuro), destaque e apoio (cursiva da combinação)."""
    from .rodizio import escolher_fontes
    codigo = p.get("fontes") or escolher_fontes(1)[0]
    combo = combinacao(codigo)
    texto, destaque, apoio = hexrgb(est["texto"]), hexrgb(est["destaque"]), hexrgb(est["apoio"])
    claro = sum(hexrgb(est["fundo"])) > 382
    t = Estilo.de_config(combo["titulo"], tam, texto)
    d = Estilo.de_config(combo["destaque"], tam, destaque)
    if claro:        # degradê dourado claro some no fundo creme: cor sólida
        t, d = dataclasses.replace(t, degrade=None), dataclasses.replace(d, degrade=None)
    a = Estilo.de_config(combo["apoio"], tam * 0.62, destaque)
    return t, d, a, codigo


def _caber(fn, largura: int, altura: int, tam: float, minimo: float = 0.45):
    """Renderiza diminuindo até caber na caixa."""
    k = 1.0
    while True:
        img = fn(tam * k)
        if (img.width <= largura and img.height <= altura) or k <= minimo:
            return img
        k -= 0.06


def _texto_corrido(texto: str, est: dict, tam: float, largura: int, alinhamento="center"):
    e = Estilo("Poppins-Light.ttf", tam, hexrgb(est["apoio"]))
    d = Estilo("Lora-Italic[wght].ttf", tam * 1.05, hexrgb(est["destaque"]), peso=500)
    return render(texto, e, d, largura_max=largura, alinhamento=alinhamento, entrelinha=1.35, sombra=False)


def _sigla(t: str) -> str:
    """Minúsculas sem estragar siglas: 'LASER DE CO2' -> 'laser de CO2'."""
    return " ".join(w if re.search(r"\d", w) or (w.isupper() and len(w) <= 3 and w not in ("DE", "DA", "DO", "E"))
                    else w.lower() for w in t.split())


def desenhar(p: dict, i: int, pasta: Path | None = None) -> Image.Image:
    from . import brand
    cfg = _cfg()
    W, H = tamanho(p)
    esc = W / 1080
    est = cfg["estilos"].get(p.get("estilo", "divine"), cfg["estilos"]["divine"])
    cards = p.get("cards") or []
    c = cards[i]
    lay = c.get("layout", "texto")
    fundo = hexrgb(est["fundo"])
    img = Image.new("RGB", (W, H), fundo)
    escuro = sum(fundo) <= 382

    # fundo: foto escurecida (quando tem) ou brilho radial suave
    if c.get("foto") and pasta:
        arq = (pasta / c["foto"]) if not Path(c["foto"]).is_absolute() else Path(c["foto"])
        if arq.exists():
            foto = ImageOps.fit(_abrir_imagem(arq), (W, H), Image.LANCZOS, centering=(0.5, 0.35))
            img = Image.blend(foto, Image.new("RGB", (W, H), fundo), 0.45 if lay != "capa" else 0.35)
            grad = Image.linear_gradient("L").resize((W, H)).point(lambda v: int(v * 0.85))
            img.paste(Image.new("RGB", (W, H), fundo), (0, 0), grad)
    else:
        brilho = Image.radial_gradient("L").resize((W * 2, H * 2)).crop((W // 2, 0, W // 2 + W, H))
        luz = tuple(min(255, int(x * 1.25 + 14)) for x in fundo) if escuro else tuple(min(255, x + 6) for x in fundo)
        img = Image.composite(img, Image.new("RGB", (W, H), luz), brilho)
    rgba = img.convert("RGBA")
    dr = ImageDraw.Draw(rgba)
    margem = int(90 * esc)
    larg = W - 2 * margem

    # marca no topo e progresso discreto (pontos, sem número)
    if est.get("marca", True):
        hdr = brand.horizontal(int(48 * esc))
        rgba.alpha_composite(hdr, ((W - hdr.width) // 2, int(56 * esc)))
    n = len(cards)
    r = int(5 * esc)
    x0 = W // 2 - (n - 1) * int(9 * esc)
    for k in range(n):
        cor_p = hexrgb(est["destaque"]) + ((255,) if k == i else (80,))
        cx = x0 + k * int(18 * esc)
        dr.ellipse((cx - r, H - int(60 * esc) - r, cx + r, H - int(60 * esc) + r), fill=cor_p)

    topo, base = int(170 * esc), H - int(120 * esc)
    area_h = base - topo

    def centro(bloco):
        rgba.alpha_composite(bloco, ((W - bloco.width) // 2, topo + (area_h - bloco.height) // 2))

    if lay == "capa":
        t, d, a, _ = _estilos(p, est, 120 * esc)
        tit = _caber(lambda s: render(c.get("titulo", ""), dataclasses.replace(t, tamanho=s),
                                      dataclasses.replace(d, tamanho=s * d.tamanho / t.tamanho), largura_max=larg,
                                      sombra=escuro),
                     larg, int(area_h * 0.7), t.tamanho)
        bloco = [tit]
        if c.get("apoio"):
            bloco.append(render(c["apoio"], a, a, largura_max=larg, sombra=escuro))
        centro(_empilhar(bloco, -int(18 * esc)))
        dica = render("deslize  ›", Estilo("Poppins-Light.ttf", 26 * esc, hexrgb(est["apoio"])), sombra=False)
        rgba.alpha_composite(dica, (W - margem - dica.width, H - int(90 * esc) - dica.height // 2))
    elif lay == "texto":
        t, d, _, _ = _estilos(p, est, 84 * esc)
        tit = _caber(lambda s: render(c.get("titulo", ""), dataclasses.replace(t, tamanho=s),
                                      dataclasses.replace(d, tamanho=s * d.tamanho / t.tamanho), largura_max=larg,
                                      sombra=escuro),
                     larg, int(area_h * 0.5), t.tamanho)
        bloco = [tit]
        if c.get("texto"):
            bloco.append(_caber(lambda s: _texto_corrido(c["texto"], est, s, larg), larg, int(area_h * 0.42), 40 * esc))
        centro(_empilhar(bloco, int(26 * esc)))
    elif lay == "lista":
        t, d, _, _ = _estilos(p, est, 76 * esc)
        tit = render(c.get("titulo", ""), t, d, largura_max=larg, sombra=escuro)
        linhas = []
        for item in c.get("itens") or []:
            it = _texto_corrido(item, est, 40 * esc, larg - int(70 * esc), "left")
            linha = Image.new("RGBA", (larg, max(it.height, int(50 * esc))), (0, 0, 0, 0))
            ld = ImageDraw.Draw(linha)
            cx, cy, rr = int(20 * esc), linha.height // 2, int(17 * esc)
            ld.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=hexrgb(est["destaque"]) + (255,), width=max(2, int(3 * esc)))
            ld.line([(cx - rr * 0.45, cy), (cx - rr * 0.1, cy + rr * 0.38), (cx + rr * 0.5, cy - rr * 0.35)],
                    fill=hexrgb(est["destaque"]) + (255,), width=max(2, int(4 * esc)))
            linha.alpha_composite(it, (int(60 * esc), (linha.height - it.height) // 2))
            linhas.append(linha)
        centro(_empilhar([tit] + linhas, int(22 * esc), alinhar="left" if linhas else "center"))
    elif lay == "mito_verdade":
        rot = c.get("rotulos") or ["Mito", "Verdade"]
        caixas = []
        for k, (rotulo, txt) in enumerate(zip(rot, (c.get("mito", ""), c.get("verdade", "")))):
            verdade = k == 1
            er = Estilo("Jura[wght].ttf", 30 * esc, hexrgb(est["destaque"]) if verdade else hexrgb(est["apoio"]),
                        caixa_alta=True, tracking=0.3, peso=600)
            ir = render(rotulo, er, er, sombra=False)
            it = _caber(lambda s: _texto_corrido(txt, {**est, "apoio": est["texto"] if verdade else est["apoio"]}, s,
                                                 larg - int(80 * esc)), larg - int(80 * esc), int(area_h * 0.3), 46 * esc)
            h = ir.height + it.height + int(70 * esc)
            cx = Image.new("RGBA", (larg * 2, h * 2), (0, 0, 0, 0))
            cor_borda = hexrgb(est["destaque"]) + (230 if verdade else 90,)
            fundo_caixa = (tuple(min(255, v + 18) for v in fundo) if escuro else tuple(max(0, v - 10) for v in fundo)) + (235,)
            ImageDraw.Draw(cx).rounded_rectangle((2, 2, larg * 2 - 3, h * 2 - 3), radius=int(40 * esc), fill=fundo_caixa,
                                                 outline=cor_borda, width=4 if verdade else 2)
            cx = cx.resize((larg, h), Image.LANCZOS)
            cx.alpha_composite(ir, ((larg - ir.width) // 2, int(26 * esc)))
            cx.alpha_composite(it, ((larg - it.width) // 2, ir.height + int(40 * esc)))
            if not verdade:
                ImageDraw.Draw(cx).line([(larg * 0.2, ir.height + int(40 * esc) + it.height / 2),
                                         (larg * 0.8, ir.height + int(40 * esc) + it.height / 2)],
                                        fill=hexrgb(est["destaque"]) + (150,), width=max(2, int(3 * esc)))
            caixas.append(cx)
        centro(_empilhar(caixas, int(30 * esc)))
    elif lay == "citacao":
        from .cartoes import foto_redonda, pessoa, selo_verificado
        quem = c.get("pessoa") or est.get("pessoa") or "daniel"
        pe = pessoa(quem)
        foto = foto_redonda(quem, int(120 * esc))
        en = Estilo("Poppins-Medium.ttf", 38 * esc, hexrgb(est["texto"]))
        ea = Estilo("Poppins-Light.ttf", 28 * esc, hexrgb(est["destaque"]))
        nome, arroba = render(pe["nome"], en, en, sombra=False), render(pe["instagram"], ea, ea, sombra=False)
        et = Estilo("CormorantGaramond[wght].ttf", 62 * esc, hexrgb(est["texto"]), peso=500)
        etd = Estilo("CormorantGaramond-Italic[wght].ttf", 64 * esc, hexrgb(est["destaque"]), peso=500)
        frase = _caber(lambda s: render(c.get("texto", ""), dataclasses.replace(et, tamanho=s),
                                        dataclasses.replace(etd, tamanho=s * 1.03), largura_max=larg, alinhamento="left",
                                        sombra=False), larg, int(area_h * 0.6), et.tamanho)
        cab = Image.new("RGBA", (larg, foto.height), (0, 0, 0, 0))
        cab.alpha_composite(foto, (0, 0))
        cab.alpha_composite(nome, (foto.width + int(24 * esc), int(10 * esc)))
        if pe.get("verificado"):
            cab.alpha_composite(selo_verificado(int(34 * esc)), (foto.width + int(30 * esc) + nome.width, int(16 * esc)))
        cab.alpha_composite(arroba, (foto.width + int(24 * esc), int(14 * esc) + nome.height))
        centro(_empilhar([cab, frase], int(40 * esc), alinhar="left"))
    else:   # cta
        t, d, _, _ = _estilos(p, est, 84 * esc)
        bloco = []
        if est.get("marca", True):
            bloco.append(brand.empilhado(int(150 * esc)))
        bloco.append(render(c.get("titulo", ""), t, d, largura_max=larg, sombra=escuro))
        if c.get("pedido"):
            ep = Estilo("Poppins-Medium.ttf", 34 * esc, hexrgb(est["destaque"]))
            bloco.append(render(c["pedido"], ep, ep, largura_max=larg, sombra=False))
        centro(_empilhar(bloco, int(34 * esc)))
        if est.get("marca", True):
            m = load("marca")
            linhas = [m["clinica"]["endereco"], m["aviso_resultados"]]
            if p.get("conteudo_medico", True):
                linhas.append(m["responsavel_tecnico"]["curto"])
            er = Estilo("Poppins-Light.ttf", 21 * esc, hexrgb(est["apoio"]))
            ir = render("\n".join(linhas), er, er, largura_max=larg, sombra=False, entrelinha=1.3)
            rgba.alpha_composite(ir, ((W - ir.width) // 2, H - int(100 * esc) - ir.height))
    return rgba.convert("RGB")


def _empilhar(imgs: list, gap: int, alinhar: str = "center") -> Image.Image:
    W = max(i.width for i in imgs)
    H = sum(i.height for i in imgs) + gap * (len(imgs) - 1)
    out = Image.new("RGBA", (W, max(1, H)), (0, 0, 0, 0))
    y = 0
    for im in imgs:
        out.alpha_composite(im, ((W - im.width) // 2 if alinhar == "center" else 0, y))
        y += im.height + gap
    return out


def textos(p: dict) -> list:
    out = []
    for c in p.get("cards") or []:
        for k in ("titulo", "apoio", "texto", "mito", "verdade", "pedido"):
            if c.get(k):
                out.append(c[k])
        out += list(c.get("itens") or [])
    return out


def legenda(p: dict) -> str:
    """Legenda curta do carrossel: gancho na dobra, uma linha de contexto, um CTA, aviso, RT e hashtags."""
    from .legenda_post import _frase, hashtags
    m = load("marca")
    cards = p.get("cards") or []
    capa = cards[0] if cards else {}
    gancho = _frase(capa.get("titulo", p.get("titulo", "")))
    contexto = _frase(capa.get("apoio", "")) if capa.get("apoio") else ""
    pedido = next((c.get("pedido") for c in reversed(cards) if c.get("pedido")), "")
    partes = [f"{gancho} ✨", contexto, pedido]
    if p.get("estilo") != "pessoal":
        partes.append(f"📍 {m['clinica']['endereco']}\nWhatsApp {m['clinica']['whatsapp']}")
        rod = [m["aviso_resultados"]] + ([m["responsavel_tecnico"]["curto"]] if p.get("conteudo_medico", True) else [])
        partes.append("\n".join(rod))
        partes.append(" ".join(hashtags({"titulo": p.get("titulo", ""),
                                         "mensagens": [{"titulo": t} for t in textos(p)]})))
    return "\n\n".join(x for x in partes if x).strip() + "\n"


def exportar(pasta: Path, p: dict) -> dict:
    """PNG de cada card (1080x1350), um .zip com todos e a legenda. Passa pelo revisor antes."""
    from .compliance import linha_checklist, revisar
    cfg = _cfg()
    n = len(p.get("cards") or [])
    if not cfg.get("min_cards", 5) <= n <= cfg.get("max_cards", 8):
        print(f"  aviso: {n} cards (o padrão é de {cfg.get('min_cards', 5)} a {cfg.get('max_cards', 8)})")
    p = dict(p)
    p.setdefault("legenda", legenda(p))
    ach = revisar({**p, "_pasta": pasta}, textos(p))
    erros = [a for a in ach if a.nivel == "erro"]
    for a in ach:
        print("  " + a.linha())
    if erros:
        raise SystemExit("Revisor bloqueou o carrossel. Corrija os textos acima.")
    saida = pasta / "saida"
    saida.mkdir(exist_ok=True)
    base = f"{p.get('data', hoje())}_carrossel_{slug(p.get('titulo', 'carrossel'), 30)}"
    arquivos = []
    for i in range(n):
        arq = saida / f"{base}_card{i + 1:02d}.png"
        desenhar(p, i, pasta).save(arq, optimize=True)
        arquivos.append(arq)
    zipf = saida / f"{base}.zip"
    with zipfile.ZipFile(zipf, "w") as z:
        for a in arquivos:
            z.write(a, a.name)
    (saida / "legenda.txt").write_text(p["legenda"], encoding="utf-8")
    checklist = linha_checklist(p, ach)
    (pasta / "relatorio.md").write_text(
        f"# {p.get('titulo')} · carrossel\n\n{n} cards · estilo {p.get('estilo', 'divine')} · fórmula "
        f"{p.get('formula', '')} · objetivo {p.get('objetivo', '')}\n\n**Compliance:** {checklist}\n\n"
        + "\n".join(f"- {a.linha()}" for a in ach) + "\n", encoding="utf-8")
    return {"cards": [str(a) for a in arquivos], "zip": str(zipf), "checklist": checklist}


def png(p: dict, i: int, pasta: Path, largura: int = 540) -> bytes:
    img = desenhar(p, i, pasta)
    img = img.resize((largura, int(img.height * largura / img.width)), Image.LANCZOS)
    b = io.BytesIO()
    img.save(b, "JPEG", quality=88)
    return b.getvalue()
