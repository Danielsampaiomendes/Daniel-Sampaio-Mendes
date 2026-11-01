"""Post estático (imagem única) no padrão Divine, em vários tamanhos de uma vez: Feed 4:5, Stories 9:16 e TV 16:9.

Usa os mesmos layouts e estilos do carrossel (capa, texto, lista, mito x verdade, citação, final), num card só.
A foto de fundo vem do projeto (bruto/) ou da Biblioteca, pela tecnologia do tema.

  python3 -m divine_studio post novo "Endolaser nos braços"
  python3 -m divine_studio post exportar projetos/2026-11-01_post-endolaser-nos-bracos
"""
from __future__ import annotations

import shutil
from pathlib import Path

from .config import ROOT, hoje, load, slug


def _cfg() -> dict:
    return load("biblioteca").get("post", {})


def novo(titulo: str, layout: str | None = None, estilo: str = "divine") -> Path:
    from .carrossel import rascunho, salvar
    pasta = ROOT / "projetos" / f"{hoje()}_post-{slug(titulo)}"
    if pasta.exists():
        raise SystemExit(f"Já existe: {pasta.relative_to(ROOT)}")
    for sub in ("bruto", "trabalho", "saida"):
        (pasta / sub).mkdir(parents=True)
    layout = layout or _cfg().get("layout_padrao", "capa")
    cards = rascunho(titulo, "livre", "salvar", semente=sum(map(ord, titulo)))     # capa com gancho do banco
    card = next((c for c in cards if c.get("layout") == layout), cards[0] if cards else {"layout": "capa", "titulo": titulo})
    if card.get("layout") == "capa" and not card.get("apoio"):
        card["apoio"] = load("carrossel")["pedidos"].get("salvar", "")
    p = {"tipo": "post", "titulo": titulo, "data": hoje(), "estilo": estilo, "formato": "feed45",
         "formatos": list(_cfg().get("formatos") or ["feed45", "stories", "tv"]), "objetivo": "salvar",
         "conteudo_medico": estilo != "pessoal", "autorizacao_imagem": "nao_aparece", "tags": ["post"],
         "cards": [card]}
    salvar(pasta, p)
    return pasta


NOMES = {"feed45": "Feed 4x5", "feed11": "Feed 1x1", "stories": "Stories", "tv": "TV"}


def exportar(pasta: Path, p: dict) -> dict:
    """Um PNG por tamanho, a legenda e a entrega em entregas/AAAA-MM/Posts. Passa pelo revisor antes."""
    from . import aprendizado
    from .carrossel import desenhar, legenda, textos
    from .compliance import linha_checklist, revisar
    p = dict(p)
    if not p.get("cards"):
        raise SystemExit("O post está sem conteúdo.")
    p["cards"] = p["cards"][:1]
    p.setdefault("legenda", legenda(p))
    ach = revisar({**p, "_pasta": pasta}, textos(p))
    for a in ach:
        print("  " + a.linha())
    if any(a.nivel == "erro" for a in ach):
        raise SystemExit("Revisor bloqueou o post. Corrija os textos acima.")
    saida = pasta / "saida"
    saida.mkdir(exist_ok=True)
    base = f"{p.get('data', hoje())}_post_{slug(p.get('titulo', 'post'), 30)}"
    ent = ROOT / "entregas" / str(p.get("data", hoje()))[:7] / "Posts"
    ent.mkdir(parents=True, exist_ok=True)
    arquivos = []
    for fmt in p.get("formatos") or ["feed45"]:
        if fmt not in load("exportacao")["formatos"]:
            continue
        arq = saida / f"{base}_{fmt}.png"
        desenhar({**p, "formato": fmt}, 0, pasta).save(arq, optimize=True)
        shutil.copy2(arq, ent / arq.name)
        arquivos.append(arq)
        print(f"  {NOMES.get(fmt, fmt)}: {arq.relative_to(pasta)}")
        try:
            atual = next((x for x in aprendizado.ler(pasta).get("publicacoes") or [] if x.get("versao") == fmt), {})
            aprendizado.marcar(pasta, fmt, arquivo=f"saida/{arq.name}", rede="tv" if fmt == "tv" else "instagram",
                               status=atual.get("status") if atual.get("status") in ("agendado", "postado") else "aprovado",
                               entrega=str((ent / arq.name).relative_to(ROOT)))
        except Exception as e:
            print(f"  aviso: não registrei na programação ({e})")
    (saida / "legenda.txt").write_text(p["legenda"], encoding="utf-8")
    checklist = linha_checklist(p, ach)
    (pasta / "relatorio.md").write_text(
        f"# {p.get('titulo')} · post\n\nTamanhos: {', '.join(NOMES.get(f, f) for f in p.get('formatos') or [])} · "
        f"estilo {p.get('estilo', 'divine')}\n\n**Compliance:** {checklist}\n\n"
        + "\n".join(f"- {a.linha()}" for a in ach) + "\n", encoding="utf-8")
    return {"arquivos": [str(a) for a in arquivos], "checklist": checklist}
