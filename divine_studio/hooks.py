"""Banco de hooks (docs/BANCO_HOOKS.md): leitura, classificação, sorteio de 3 por vídeo e cadastro de novos.

Cada vídeo sai com 3 hooks de tipos diferentes (Código Viral): positivo, curiosidade e negativo.
O tipo vem de config/hooks.yaml (quando alguém já classificou) ou de pistas no próprio texto.
"""
from __future__ import annotations

import datetime as _dt
import random
import re

from .config import ROOT, load, save

BANCO = ROOT / "docs" / "BANCO_HOOKS.md"
TIPOS = ("positivo", "curiosidade", "negativo")

_LINHA = re.compile(r"^- (?:(?P<bloco>[ABC])-)?(?P<num>H\d+[a-z]?(?: \((?:a|b)\))?)\s+(?P<resto>.+)$")
_ASPAS = re.compile(r"\"([^\"]+)\"")


def ler_banco() -> list:
    """[{id, bloco, descricao, batidas, tipo, uso_interno, reprovado}] na ordem do arquivo."""
    if not BANCO.exists():
        return []
    texto = BANCO.read_text(encoding="utf-8")
    bloco_atual = None
    hooks = []
    tipos_cfg = load("hooks").get("tipos") or {}
    for linha in texto.splitlines():
        m = re.match(r"^## Bloco ([A-E])", linha)
        if m:
            bloco_atual = m.group(1)
            continue
        m = _LINHA.match(linha.strip())
        if not m or not bloco_atual:
            continue
        # uma linha pode trazer vários hooks ("H177 ... H178 ..."): separa em cada id depois de fim de frase
        pedacos = re.split(r"(?<=[.!?)”\"*])\s+(?=(?:[ABC]-)?H\d+\s)", m.group("resto"))
        itens = [(m.group("bloco"), m.group("num").split(" ")[0], pedacos[0])]
        for p in pedacos[1:]:
            mm = re.match(r"(?:(?P<bloco>[ABC])-)?(?P<num>H\d+)\s+(?P<resto>.+)$", p)
            if mm:
                itens.append((mm.group("bloco"), mm.group("num"), mm.group("resto")))
        # "uso interno" / "antes e depois" em qualquer parte da linha vale para todos os hooks dela
        linha_interna = bool(re.search(r"uso interno|antes e depois", m.group("resto"), re.I))
        for bl, num, resto in itens:
            bloco = bl or bloco_atual
            hid = num if bloco in ("D", "E") else f"{bloco}-{num}"
            # entradas do bloco E começam com a data: "(2026-10-28) ..."
            resto = re.sub(r"^\(\d{4}-\d{2}-\d{2}\)\s*", "", resto)
            faixa = bool(re.match(r"a (?:[ABC]-)?H\d+", resto))   # "C-H90 a C-H94 ...": grupo, sem frase única
            batidas = [b.strip().strip("“”").strip() for b in _ASPAS.findall(resto)]
            batidas = [b for b in batidas if re.search(r"\w", b)]
            hooks.append({
                "id": hid, "bloco": bloco, "descricao": resto, "batidas": [] if faixa else batidas,
                "tipo": tipos_cfg.get(hid) or classificar(resto),
                "uso_interno": linha_interna or bool(re.search(r"uso interno|antes e depois", resto, re.I)),
                "reprovado": "REPROVADO" in resto,
                "modelo": any("[" in b for b in batidas),   # tem lacuna tipo [procedimento]
            })
    return hooks


def classificar(texto: str) -> str:
    t = texto.lower()
    if "?" in t or re.search(r"\b(pov|spoiler|sabe|segredo|descobr|quem|adivinha|até o final|teste|quiz|"
                             r"quantos|pergunta|escondid)\b", t):
        return "curiosidade"
    if re.search(r"\b(não|nem|nunca|ninguém|erro|errad|esquec|parou|cansou|riscad[oa]|julgar|dói|problema|"
                 r"apagar|perdido|pare)\b", t):
        return "negativo"
    return "positivo"


def por_id(hid: str) -> dict | None:
    hid = hid.strip()
    for h in ler_banco():
        if h["id"].lower() == hid.lower():
            return h
    return None


def batidas_do_hook(hid: str) -> list:
    """Hook do banco em formato de projeto: [{titulo: ...}, ...] (segunda batida depois do →)."""
    h = por_id(hid)
    if not h:
        raise SystemExit(f"Hook {hid} não está em docs/BANCO_HOOKS.md")
    if not h["batidas"]:
        raise SystemExit(f"Hook {hid} é uma técnica visual sem frase pronta: escreva o texto em 'hook' no projeto.")
    return [{"titulo": b} for b in h["batidas"][:2]]


def usados_recentes(n_videos: int = 12) -> set:
    vids = (load("historico").get("videos") or [])[-n_videos:]
    return {v.get("hook") for x in vids for v in (x.get("versoes") or {}).values() if v.get("hook")}


def sortear(n: int = 3, tema: str | None = None, semente: int | None = None, excluir: set | None = None) -> list:
    """n hooks com frase pronta, um de cada tipo (positivo, curiosidade, negativo), fora dos usados recentes."""
    rng = random.Random(semente)
    fora = usados_recentes() | (excluir or set())
    cand = [h for h in ler_banco() if h["batidas"] and not h["uso_interno"] and not h["reprovado"]
            and not h["modelo"] and h["id"] not in fora]
    afins, genericos = cand, cand
    if tema:
        afins, genericos = _por_tema(cand, tema)
    escolhidos = []
    for k in range(n):
        tipo = TIPOS[k % 3]
        for grupo in (afins, genericos):
            pool = [h for h in grupo if h["tipo"] == tipo and h not in escolhidos]
            if pool:
                escolhidos.append(rng.choice(pool))
                break
        else:
            pool = [h for h in afins + genericos if h not in escolhidos] or [h for h in cand if h not in escolhidos]
            if pool:
                escolhidos.append(rng.choice(pool))
    return escolhidos


_PARADAS = {"de", "da", "do", "das", "dos", "no", "na", "nos", "nas", "em", "com", "para", "pra", "por", "um", "uma",
            "teste", "sintetico", "video", "reels", "stories", "the"}


def _norm(t: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()


def _por_tema(cand: list, tema: str) -> tuple:
    """(afins, genéricos): afins citam o tema; genéricos não citam nenhum procedimento de config/roteiros.yaml."""
    t = _norm(tema)
    termos = {w for w in re.findall(r"[a-z0-9]{3,}", t) if w not in _PARADAS}
    try:
        temas = load("roteiros")["temas"]
    except Exception:
        temas = {}
    todos_nomes = set()
    for chave, r in temas.items():
        nomes = {_norm(n) for n in r.get("nomes", [chave])}
        todos_nomes |= nomes
        if any(re.search(rf"\b{re.escape(n)}", t) for n in nomes):
            termos |= nomes
    afins = [h for h in cand if any(re.search(rf"\b{re.escape(w)}", _norm(h["descricao"])) for w in termos)]
    todos_nomes |= {_norm(str(x)) for x in (load("hooks").get("especificos") or [])}
    genericos = [h for h in cand if h not in afins
                 and not any(re.search(rf"\b{re.escape(n)}", _norm(" ".join(h["batidas"]) + " " + h["descricao"]))
                             for n in todos_nomes if n not in termos)]
    return afins, genericos


def proximo_numero() -> int:
    t = BANCO.read_text(encoding="utf-8")
    m = re.search(r"Próximo número livre: H(\d+)", t)
    usados = [int(x) for x in re.findall(r"\bH(\d+)\b", t)]
    return max(int(m.group(1)) if m else 0, max(usados, default=0) + 1)


def adicionar(texto: str, tipo: str | None = None, fontes: str = "", sfx: str = "") -> str:
    """Acrescenta um hook novo no bloco E (fim do arquivo) e atualiza o próximo número livre."""
    n = proximo_numero()
    hid = f"H{n}"
    frase = texto if "\"" in texto else f"\"{texto}\""
    extras = "; ".join(x for x in (fontes and f"fontes {fontes}", sfx and f"SFX {sfx}") if x)
    linha = f"- {hid} ({_dt.date.today().isoformat()}) {frase}" + (f" ({extras})" if extras else "")
    t = BANCO.read_text(encoding="utf-8").rstrip("\n") + "\n" + linha + "\n"
    t = re.sub(r"Próximo número livre: H\d+", f"Próximo número livre: H{n + 1}", t)
    BANCO.write_text(t, encoding="utf-8")
    if tipo:
        cfg = dict(load("hooks"))
        tipos = dict(cfg.get("tipos") or {})
        tipos[hid] = tipo
        cfg["tipos"] = tipos
        save("hooks", cfg, "# Tipo de cada hook (positivo | curiosidade | negativo) quando a classificação automática erra.\n")
    return hid
