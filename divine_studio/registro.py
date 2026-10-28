"""Registro de cada vídeo aprovado: índice de vídeos editados, histórico do banco de hooks e mapa do repositório."""
from __future__ import annotations

import datetime as _dt
import re

from .config import ROOT

INDICE = ROOT / "docs" / "INDICE_VIDEOS_EDITADOS.md"
BANCO = ROOT / "docs" / "BANCO_HOOKS.md"
MAPA = ROOT / "docs" / "MAPA_DO_REPOSITORIO.md"

CAB_INDICE = """# Índice de vídeos editados

Cada vídeo finalizado pelo Divine Studio entra aqui sozinho: data, tema, versões, hooks, fontes, SFX, nota viral,
compliance e onde está a legenda. Mais recente por último.
"""


def _data_br(iso: str) -> str:
    try:
        return _dt.date.fromisoformat(iso).strftime("%d/%m/%Y")
    except ValueError:
        return iso


def indice(projeto: dict, resultado: list, checklist: str) -> None:
    pasta = projeto["_pasta"]
    rel = pasta.relative_to(ROOT) if pasta.is_relative_to(ROOT) else pasta
    linhas = ["", f"## {_data_br(str(projeto.get('data', '')))} · {projeto.get('titulo')}", "",
              f"Template {projeto.get('template', 'divine')} · formato {projeto.get('formato', 'reels')} · "
              f"pasta `{rel}`", "",
              "| Versão | Hook | Banco | Fontes | SFX | Nota viral | Arquivo |", "|---|---|---|---|---|---|---|"]
    for r in resultado:
        nota = r.get("nota") or {}
        media = round(sum(nota.get("notas", {}).values()) / max(1, len(nota.get("notas", {}))), 1) if nota else ""
        sfx = " + ".join(r["sfx_abertura"] + r.get("sfx_transicao", []) + r["sfx_fechamento"])
        linhas.append(f"| {r['nome']} | {r['hook'].replace('|', '/')} | {r.get('hook_id') or ''} | {r['fontes']} | "
                      f"{sfx} | {media} | `saida/{r['arquivo']}` |")
    linhas += ["", f"Legenda: `{rel}/saida/legenda.txt` · {checklist}", ""]
    if not INDICE.exists():
        INDICE.write_text(CAB_INDICE, encoding="utf-8")
    with open(INDICE, "a", encoding="utf-8") as f:
        f.write("\n".join(linhas))


def historico_banco(projeto: dict, resultado: list, proximas_fontes: list) -> None:
    """Acrescenta a linha do vídeo no 'Histórico recente de fontes e SFX' e atualiza a sugestão do próximo."""
    if not BANCO.exists():
        return
    t = BANCO.read_text(encoding="utf-8")
    dia = _dt.date.today().strftime("%d/%m")
    fontes = ", ".join(r["fontes"] for r in resultado)
    sfx = ", ".join(s for r in resultado for s in r["sfx_abertura"])
    linha = f"- {dia} ({projeto.get('titulo')}): fontes {fontes}; SFX de abertura {sfx}."
    alvo = "- **Próximo vídeo: começar por"
    if alvo in t:
        i = t.index(alvo)
        t = t[:i] + linha + "\n" + t[i:]
        t = re.sub(r"- \*\*Próximo vídeo: começar por [^*]+\*\*",
                   f"- **Próximo vídeo: começar por {', '.join(proximas_fontes[:-1])} ou {proximas_fontes[-1]}.**", t,
                   count=1)
    BANCO.write_text(t, encoding="utf-8")


def mapa(projeto: dict, resultado: list) -> None:
    """Uma linha nova na tabela de projetos do mapa (seção 1), se o projeto ainda não estiver lá."""
    if not MAPA.exists():
        return
    t = MAPA.read_text(encoding="utf-8")
    pasta = projeto["_pasta"]
    rel = str(pasta.relative_to(ROOT)) if pasta.is_relative_to(ROOT) else str(pasta)
    if f"`{rel}/`" in t:
        return
    hooks = ", ".join(r.get("hook_id") or r["hook"][:30] for r in resultado)
    arqs = ", ".join(f"`saida/{r['arquivo']}`" for r in resultado)
    linha = (f"| `{rel}/` | {_data_br(str(projeto.get('data', '')))} | {projeto.get('template', 'divine')} "
             f"(Divine Studio) | {len(resultado)} versões {projeto.get('formato', 'reels')} | {hooks} | {arqs} |")
    i = t.find("\n## 2.")
    if i < 0:
        return
    bloco = t[:i].rstrip("\n")
    t = bloco + "\n" + linha + "\n" + t[i:]
    MAPA.write_text(t, encoding="utf-8")


def registrar(projeto: dict, resultado: list, checklist: str, proximas_fontes: list) -> None:
    indice(projeto, resultado, checklist)
    historico_banco(projeto, resultado, proximas_fontes)
    mapa(projeto, resultado)
