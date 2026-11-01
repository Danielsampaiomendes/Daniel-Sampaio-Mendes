"""A mesma edição em outros tamanhos: Stories 9:16, Feed 4:5 e 1:1 e TV 16:9 (no template da TV).

  python3 -m divine_studio formatos projetos/2026-11-01_co2 [--formatos stories,tv] [--final]

Cada formato vira uma peça em projetos/<projeto>-formatos/<formato>/ com o mesmo conteúdo do projeto principal
(clipes, textos, efeitos, hooks já sorteados e fontes). Ajustes por formato:
  stories   mesmas versões
  feed45/11 mesmas versões
  tv        template TV (janela 4:5, painéis, 1 versão, sem legenda da fala, sem voz, ~23 s em loop)
"""
from __future__ import annotations

import copy
import shutil

import yaml

from .pacote import _rel

NOMES = {"reels": "Reels 9:16", "stories": "Stories 9:16", "feed45": "Feed 4:5", "feed11": "Feed 1:1", "tv": "TV 16:9"}


def derivar(projeto: dict, formato: str) -> dict:
    base = {k: v for k, v in projeto.items() if not k.startswith("_")}
    p = copy.deepcopy(base)
    p["titulo"] = f"{base.get('titulo', 'Vídeo')} · {NOMES.get(formato, formato)}"
    p["tema"] = base.get("tema") or base.get("titulo", "video")
    p["categoria"] = formato
    p["formato"] = formato
    p["formato_de"] = projeto["_pasta"].name
    origem = projeto["_pasta"]
    for chave in ("clipes", "clipes_referencia"):
        for c in p.get(chave) or []:
            c["arquivo"] = _rel(origem, c["arquivo"])
    if formato == "tv":
        p["template"] = "tv"
        p["versoes"] = [{"nome": "TV"}]
        p["audio"] = {"original": False, "trilha": True}
        p["legendas"] = False
        p["corte_limpo"] = False
        p.pop("efeitos", None)                 # a TV tem o próprio layout
        tv = dict(p.get("tv") or {})
        tv.setdefault("tratamento", (base.get("selo") or base.get("titulo", "")).title())
        p["tv"] = tv
        # textos com mais de uma frase ficam no painel esquerdo
        p["mensagens"] = [{k: v for k, v in m.items() if k in ("titulo", "apoio")} for m in p.get("mensagens") or []]
    elif p.get("template") == "tv":
        p["template"] = "divine"
    return p


def gerar(projeto: dict, formatos: list) -> list:
    """Cria (ou atualiza) as peças de cada formato. Devolve [(pasta, nome)]."""
    origem = projeto["_pasta"]
    destino = origem.parent / f"{origem.name}-formatos"
    destino.mkdir(exist_ok=True)
    criadas = []
    for f in formatos:
        if f not in NOMES or f == projeto.get("formato", "reels"):
            continue
        pasta = destino / f
        for sub in ("bruto", "trabalho", "saida"):
            (pasta / sub).mkdir(parents=True, exist_ok=True)
        p = derivar(projeto, f)
        cab = f"# {NOMES[f]} · gerado a partir de {origem.name} (botão Formatos). Edite o principal e gere de novo.\n"
        (pasta / "projeto.yaml").write_text(cab + yaml.safe_dump(p, allow_unicode=True, sort_keys=False, width=1000,
                                                                 default_flow_style=None), encoding="utf-8")
        # mesmos hooks sorteados do principal (as versões combinam entre os formatos)
        hs = origem / "trabalho" / "hooks_sorteados.json"
        if hs.exists() and f != "tv":
            shutil.copy(hs, pasta / "trabalho" / "hooks_sorteados.json")
        criadas.append((pasta, NOMES[f]))
    return criadas


def formatos_do_projeto(projeto: dict) -> list:
    f = projeto.get("formatos") or ["stories", "tv"]
    return [x for x in f if x in NOMES]

