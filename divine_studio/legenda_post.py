"""Legenda do post: gancho na 1ª linha, CTA antecipado, corpo em parágrafos corridos, CTA final com endereço,
aviso de resultados, RT e 8 a 12 hashtags. Regras em config/legenda.yaml; passa pelo revisor antes de salvar."""
from __future__ import annotations

import re

from .config import load
from .text import limpar


def _frase(t: str) -> str:
    t = limpar(t or "").strip()
    t = re.sub(r"\s+[—–-]\s+", ", ", t)          # sem travessão
    if t and t[-1] not in ".!?:…":
        t += "."
    return t[:1].upper() + t[1:] if t else t


def hashtags(projeto: dict) -> list:
    cfg = load("legenda")
    texto = " ".join([projeto.get("titulo", ""), str(projeto.get("selo", "")),
                      " ".join(m.get("titulo", "") for m in projeto.get("mensagens") or []),
                      str((projeto.get("tv") or {}).get("tratamento", ""))]).lower()
    texto = limpar(texto)
    tags = []
    for chave, lista in cfg["hashtags_tema"].items():
        if chave in texto:
            tags += [t for t in lista if t not in tags]
    for t in cfg["hashtags_base"]:
        if t not in tags:
            tags.append(t)
    extras = ["#autoestima", "#bemestar", "#cuidadoconsigo", "#saudeebeleza"]
    for t in extras:
        if len(tags) >= cfg["min_hashtags"]:
            break
        if t not in tags:
            tags.append(t)
    return tags[: cfg["max_hashtags"]]


def gerar(projeto: dict, semente: int = 0) -> str:
    cfg = load("legenda")
    marca = load("marca")
    pessoal = projeto.get("marca") == "pessoal"
    v0 = (projeto.get("versoes") or [{}])[0]
    hook = v0.get("hook") or []
    if isinstance(hook, dict):
        hook = [hook]
    gancho = " ".join(_frase(b.get("titulo", "")) for b in hook if b.get("titulo"))
    tv = projeto.get("tv") or {}
    if not gancho and tv.get("tratamento"):
        gancho = _frase(f"{tv['tratamento']}" + (f": {tv['indicacao'].lower()}" if tv.get("indicacao") else ""))
    if not gancho:
        gancho = _frase(projeto.get("titulo", ""))
    emoji = cfg["emojis"][semente % len(cfg["emojis"])]
    partes = [f"{gancho} {emoji}".strip()]

    if not pessoal:
        partes.append(cfg["cta_antecipado"][semente % len(cfg["cta_antecipado"])])

    corpo = []
    for m in projeto.get("mensagens") or []:
        f = _frase(" ".join(x for x in (m.get("titulo"), m.get("apoio")) if x))
        if f:
            corpo.append(f)
    if not corpo and projeto.get("_fala"):
        fala = " ".join(w["texto"] for w in projeto["_fala"])
        corpo = [_frase(s) for s in re.split(r"(?<=[.!?])\s+", fala) if len(s.split()) > 3][:3]
    frase_final = (projeto.get("fechamento") or {}).get("frase")
    if frase_final:
        corpo.append(_frase(frase_final))
    if corpo:
        partes.append(" ".join(corpo))

    if not pessoal:
        tv = projeto.get("template") == "tv"
        partes.append((cfg["cta_final_tv"] if tv else cfg["cta_final"]).format(whatsapp=marca["clinica"]["whatsapp"])
                      + f"\n📍 {marca['clinica']['endereco']}")
        rodape = [marca["aviso_resultados"]]
        if projeto.get("conteudo_medico", True):
            rodape.append(marca["responsavel_tecnico"]["curto"])
        partes.append("\n".join(rodape))
        partes.append(" ".join(hashtags(projeto)))
    return "\n\n".join(partes).strip() + "\n"


def garantir(projeto: dict) -> bool:
    """Gera a legenda quando o projeto não tem. Devolve True se gerou."""
    if projeto.get("legenda"):
        return False
    projeto["legenda"] = gerar(projeto, semente=sum(map(ord, str(projeto.get("titulo", "")))))
    return True
