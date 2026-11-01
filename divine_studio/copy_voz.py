"""Copy para gravar a voz (dublagem ou narração): já vem sugerida, você edita, lê no teleprompter e grava.

Ordem da sugestão: a copy que você já salvou > o arquivo *COPY.md do projeto > montada do próprio projeto
(gancho da V1, mensagens, fechamento e chamada) > roteiro do tema (config/roteiros.yaml).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from .compliance import revisar


def _limpa(t: str) -> str:
    t = re.sub(r"[*~]", "", str(t or ""))
    t = re.sub(r"\s*/\s*", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _frase(t: str) -> str:
    t = _limpa(t)
    if t:
        t = t[0].upper() + t[1:]
    return t if not t or t[-1] in ".!?…:" else t + "."


def sugerida(pasta: Path, projeto: dict) -> tuple:
    """(copy, de_onde_veio)."""
    copias = sorted(pasta.glob("*COPY*.md")) + sorted((pasta / "trabalho").glob("*COPY*.md"))
    if copias:
        texto = copias[0].read_text(encoding="utf-8")
        texto = "\n".join(ln for ln in texto.splitlines() if not ln.startswith("#")).strip()
        if texto:
            return texto, copias[0].name
    from .auto import tema
    from .hooks import batidas_do_hook
    partes = []
    v1 = dict(next(iter(projeto.get("versoes") or []), {}))
    sorteados = pasta / "trabalho" / "hooks_sorteados.json"
    if not v1.get("hook_id") and sorteados.exists():           # hook: auto -> o que foi sorteado para a V1
        import json
        v1["hook_id"] = json.loads(sorteados.read_text(encoding="utf-8")).get(v1.get("nome", "V1"))
    if v1.get("hook_id"):
        try:
            partes.append(" ".join(_frase(b["titulo"]) for b in batidas_do_hook(v1["hook_id"])))
        except Exception:
            pass
    elif isinstance(v1.get("hook"), list):
        partes.append(" ".join(_frase(b.get("titulo", "")) for b in v1["hook"]))
    _, rot = tema(projeto.get("titulo", ""))
    msgs = projeto.get("mensagens") or rot.get("mensagens") or []
    for m in msgs:
        linha = _frase(m.get("titulo", "") if isinstance(m, dict) else m)
        if isinstance(m, dict) and m.get("apoio"):
            linha += " " + _frase(m["apoio"])
        partes.append(linha)
    fech = projeto.get("fechamento") or {}
    frase = fech.get("frase") if isinstance(fech, dict) else fech
    partes.append(_frase(frase or rot.get("fechamento", "")))
    cta = projeto.get("cta_antecipado") or rot.get("cta") or "Agende sua avaliação"
    partes.append(_frase(cta))
    texto = "\n\n".join(p for p in partes if p)
    return texto, "montada do projeto" if projeto.get("mensagens") else "roteiro do tema"


def ler(pasta: Path) -> dict:
    p = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    salva = p.get("copy_dublagem")
    sug, fonte = sugerida(pasta, p)
    texto = salva or sug
    alertas = [a.linha() for a in revisar({**p, "_pasta": pasta}, [texto]) if a.nivel == "erro"]
    palavras = len(texto.split())
    return {"copy": texto, "sugerida": sug, "fonte": "sua copy salva" if salva else fonte,
            "segundos": round(palavras / 2.6, 1), "alertas": alertas}


def melhorar_com_ia(pasta: Path, texto: str) -> str:
    """Reescreve a copy para ser falada (curta, ritmo de Reels, voz Divine, compliance), sem bloco de sugestão."""
    from . import assistente
    pedido = ("Reescreva esta copy para eu GRAVAR a voz deste vídeo (dublagem/narração). Regras: frases curtas para falar "
              "em voz alta, gancho forte nos 3 primeiros segundos, loop aberto, um único pedido no fim, tom elegante "
              "e próximo (mercado de luxo), sem promessa de resultado (CFM 2.336/2023) e sem marca de medicamento. "
              "Devolva SÓ o texto para ler, em parágrafos curtos, sem título, sem comentários e sem bloco de sugestão."
              f"\n\nCopy atual:\n{texto}")
    resposta, _, _ = assistente.perguntar([], pedido, assistente.contexto_projeto(pasta))
    return resposta.strip()
