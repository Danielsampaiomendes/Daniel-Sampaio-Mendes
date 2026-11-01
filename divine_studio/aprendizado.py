"""Aprendizado com as suas edições: gostei, postei e métricas do Instagram viram preferências.

Cada sinal (gostei, postei, métricas) fica no projeto.yaml da peça, em `publicacoes`, junto com as
características da versão (fontes, hook e tipo de hook, sons, efeitos, template, duração). A partir disso:
  - o rodízio de fontes e o sorteio de hooks passam a preferir o que funciona com você
  - toda edição ganha uma versão "IA": a combinação que o app acredita ser a melhor, com o porquê no relatório
"""
from __future__ import annotations

import datetime as _dt
import math
import statistics
from collections import defaultdict
from pathlib import Path

import yaml

from .config import ROOT, load

PROJETOS = ROOT / "projetos"
STATUS = ("rascunho", "aprovado", "agendado", "postado")


def _cfg() -> dict:
    return load("preferencias").get("aprendizado", {})


def caracteristicas(projeto: dict, versao: str, resultado: dict | None = None) -> dict:
    """O que descreve uma versão (para aprender o que funciona)."""
    import json
    pasta = projeto["_pasta"]
    rod = {}
    arq = pasta / "trabalho" / "rodizio_escolhido.json"
    if arq.exists():
        rod = json.loads(arq.read_text(encoding="utf-8")).get(versao, {})
    hs = {}
    arq = pasta / "trabalho" / "hooks_sorteados.json"
    if arq.exists():
        hs = json.loads(arq.read_text(encoding="utf-8"))
    v = next((x for x in projeto.get("versoes") or [] if x.get("nome") == versao), {})
    hook_id = v.get("hook_id") or hs.get(versao)
    tipo_hook = None
    if hook_id:
        from .hooks import por_id
        h = por_id(hook_id)
        tipo_hook = h["tipo"] if h else None
    efeitos = sorted({e.get("tipo") for e in (projeto.get("efeitos") or []) + (v.get("efeitos") or []) if e.get("tipo")})
    base = pasta / "trabalho" / "base.json"
    dur = json.loads(base.read_text(encoding="utf-8")).get("duracao") if base.exists() else None
    return {k: x for k, x in {
        "template": projeto.get("template", "divine"), "formato": projeto.get("formato", "reels"),
        "tipo": projeto.get("tipo", "video"), "fontes": v.get("fontes") or rod.get("fontes") or projeto.get("fontes"),
        "hook_id": hook_id, "hook_tipo": tipo_hook,
        "sfx_abertura": (rod.get("sfx_abertura") or [None])[0], "efeitos": efeitos,
        "duracao": round(dur) if dur else None, "objetivo": projeto.get("objetivo"),
        "formula": projeto.get("formula"), "estilo": projeto.get("estilo"),
        "legendas": bool(projeto.get("legendas")), "tema": projeto.get("tema") or projeto.get("titulo"),
    }.items() if x not in (None, [], "")}


# ---------------------------------------------------------------- publicações (status, programação, métricas)

def ler(pasta: Path) -> dict:
    return yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}


def _gravar(pasta: Path, d: dict) -> None:
    texto = yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=1000, default_flow_style=None)
    (pasta / "projeto.yaml").write_text("# Divine Studio\n" + texto, encoding="utf-8")


def marcar(pasta: Path, versao: str, arquivo: str | None = None, **campos) -> dict:
    """Atualiza a publicação de uma versão: status, gostei, data_agendada, data_postagem, rede, link, metricas."""
    d = ler(pasta)
    pubs = d.setdefault("publicacoes", [])
    pub = next((x for x in pubs if x.get("versao") == versao), None)
    if pub is None:
        pub = {"versao": versao, "status": "rascunho"}
        pubs.append(pub)
    if arquivo:
        pub["arquivo"] = arquivo
    for k, v in campos.items():
        if v is None:
            pub.pop(k, None)
        elif k == "metricas":
            pub["metricas"] = {**(pub.get("metricas") or {}), **v}
        else:
            pub[k] = v
    if campos.get("status") == "postado" and not pub.get("data_postagem"):
        pub["data_postagem"] = _dt.date.today().isoformat()
    if campos.get("gostei") or campos.get("status") in ("postado", "aprovado"):
        pub["caracteristicas"] = caracteristicas({**d, "_pasta": pasta}, versao)
    _gravar(pasta, d)
    return pub


def todas_publicacoes() -> list:
    """Todas as peças de todos os projetos, para a tela de Programação."""
    out = []
    for y in sorted(PROJETOS.glob("**/projeto.yaml")):
        pasta = y.parent
        if "trabalho" in pasta.parts:
            continue
        try:
            d = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        nome = str(pasta.relative_to(PROJETOS))
        for pub in d.get("publicacoes") or []:
            out.append({"projeto": nome, "titulo": d.get("titulo", nome), "tipo": d.get("tipo", "video"),
                        "formato": d.get("formato", "reels"), "template": d.get("template", "divine"),
                        "tags": d.get("tags") or [], **pub})
    return out


# ---------------------------------------------------------------- aprendizado

def pontuar(pub: dict, mediana_alcance: float | None = None) -> float:
    """Sinal de quanto a versão funcionou: gostei +1, postado +2, métricas até +4 (relativas ao seu normal)."""
    s = 0.0
    if pub.get("gostei"):
        s += 1
    if pub.get("status") == "postado":
        s += 2
    m = pub.get("metricas") or {}
    alcance = m.get("alcance") or m.get("views") or m.get("visualizacoes")
    if alcance:
        envio = (m.get("compartilhamentos", 0) * 3 + m.get("salvamentos", 0) * 2 + m.get("comentarios", 0)
                 + m.get("curtidas", 0) * 0.5) / max(1, alcance) * 100
        s += min(2.0, envio / 2)                               # engajamento por alcance
        if mediana_alcance:
            s += max(-1.0, min(2.0, math.log2(max(1, alcance) / mediana_alcance)))   # acima da sua média
    if pub.get("nao_gostei"):
        s -= 1.5
    return s


def preferencias() -> dict:
    """{campo: {valor: (média, n)}} para cada característica, com suavização (poucos dados pesam pouco)."""
    pubs = [p for p in todas_publicacoes() if p.get("caracteristicas")]
    alcances = [(p.get("metricas") or {}).get("alcance") or (p.get("metricas") or {}).get("views") for p in pubs]
    alcances = [a for a in alcances if a]
    med = statistics.median(alcances) if alcances else None
    soma, cont = defaultdict(lambda: defaultdict(float)), defaultdict(lambda: defaultdict(int))
    for p in pubs:
        s = pontuar(p, med)
        for campo, valor in p["caracteristicas"].items():
            for v in (valor if isinstance(valor, list) else [valor]):
                soma[campo][str(v)] += s
                cont[campo][str(v)] += 1
    k = float(_cfg().get("suavizacao", 2))
    return {c: {v: (round(soma[c][v] / (cont[c][v] + k), 3), cont[c][v]) for v in soma[c]} for c in soma}


def melhor(campo: str, opcoes: list, prefs: dict | None = None, evitar: set | None = None):
    """A opção com melhor histórico (empate: a primeira da lista, que já vem do rodízio)."""
    prefs = prefs if prefs is not None else preferencias()
    tab = prefs.get(campo, {})
    cand = [o for o in opcoes if not evitar or o not in evitar] or list(opcoes)
    return max(cand, key=lambda o: (tab.get(str(o), (0, 0))[0], -cand.index(o))) if cand else None


def resumo(prefs: dict | None = None) -> list:
    """Frases curtas do que o app aprendeu (para o painel e para a IA)."""
    prefs = prefs if prefs is not None else preferencias()
    nomes = {"fontes": "fontes", "hook_tipo": "tipo de hook", "template": "template", "sfx_abertura": "som de abertura",
             "efeitos": "efeito", "duracao": "duração (s)", "objetivo": "objetivo", "estilo": "estilo de carrossel",
             "formula": "fórmula de carrossel"}
    out = []
    for campo, nome in nomes.items():
        tab = {v: x for v, x in (prefs.get(campo) or {}).items() if x[1] >= 1}
        if not tab:
            continue
        top = max(tab.items(), key=lambda kv: kv[1][0])
        if top[1][0] > 0:
            out.append(f"Melhor {nome}: {top[0]} (nota {top[1][0]}, {top[1][1]} peça(s))")
    return out


def versao_ia(projeto: dict, versoes: list, fontes_escolhidas: list) -> dict | None:
    """A versão que o app acredita ser a melhor: hook, fontes e efeitos com melhor histórico (e o porquê)."""
    if not _cfg().get("versao_ia", True) or projeto.get("template") == "tv" or projeto.get("tipo") == "carrossel":
        return None
    prefs = preferencias()
    if not prefs and not _cfg().get("versao_ia_sem_historico", True):
        return None
    from .fonts import todas_combinacoes
    from .hooks import sortear
    porque = []
    fonte = melhor("fontes", todas_combinacoes(), prefs, evitar=set(fontes_escolhidas))
    if prefs.get("fontes", {}).get(str(fonte)):
        porque.append(f"fontes {fonte}, as que mais funcionaram com você")
    else:
        porque.append(f"fontes {fonte} (ainda sem histórico: ela entra para testar)")
    tipo_bom = melhor("hook_tipo", ["curiosidade", "negativo", "positivo"], prefs)
    usados = {v.get("hook_id") for v in versoes if v.get("hook_id")}
    cands = [h for h in sortear(9, tema=projeto.get("titulo"), semente=7, excluir=usados) if h["tipo"] == tipo_bom]
    hook = cands[0] if cands else None
    if hook:
        porque.append(f"hook de {tipo_bom} ({hook['id']})" + (", o tipo com melhor resposta" if prefs.get("hook_tipo") else ""))
    efeitos = []
    tab_ef = prefs.get("efeitos") or {}
    ja = {e.get("tipo") for e in projeto.get("efeitos") or []}
    bons = [e for e, (nota, n) in sorted(tab_ef.items(), key=lambda kv: -kv[1][0]) if nota > 0.5 and e not in ja]
    if bons:
        efeitos.append({"tipo": bons[0], "inicio": 4.0, **_exemplo(bons[0])})
        porque.append(f"efeito {bons[0]}, que esteve nas peças que você mais gostou")
    v = {"nome": "IA", "fontes": fonte, "porque": porque}
    if hook:
        v["hook_id"] = hook["id"]
    else:
        v["hook"] = "auto"
    if efeitos:
        v["efeitos"] = efeitos
    return v


def _exemplo(tipo: str) -> dict:
    from .efeitos import EXEMPLOS
    return dict(EXEMPLOS.get(tipo, {}))
