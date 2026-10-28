"""Pacote por categorias: de um projeto com vários brutos do mesmo procedimento, cria um projeto por peça
(Reels longo, médio, curto, ultracurto, viral, POV, cortes, bastidores, TV e Stories), com nomes claros.

  python3 -m divine_studio pacote projetos/2026-10-28_co2 [--categorias reels-curto,tv] [--renderizar]

Cada peça vira projetos/<projeto>-pacote/NN_<categoria>/projeto.yaml (os brutos continuam no projeto original).
A duração alvo usa a fala (frases inteiras) quando há transcrição; sem ela, pega o miolo de cada clipe.
"""
from __future__ import annotations

import copy
import re

import yaml

from .config import load


def _dur_clipe(projeto: dict, c: dict) -> float:
    from .ingest import probe, resolver
    ini = float(c.get("inicio", 0))
    fim = float(c["fim"]) if "fim" in c else probe(resolver(projeto, c["arquivo"]))["duracao"]
    return max(0.0, (fim - ini) / float(c.get("velocidade", 1.0)))


def recortar_miolo(projeto: dict, clipes: list, alvo: float) -> list:
    """Sem fala: pega o miolo de cada clipe, na proporção da duração alvo (mínimo 1,5 s por clipe)."""
    durs = [_dur_clipe(projeto, c) for c in clipes]
    total = sum(durs) or 1
    if total <= alvo:
        return copy.deepcopy(clipes)
    out = []
    for c, d in zip(clipes, durs):
        quero = max(1.5, d * alvo / total)
        if quero >= d:
            out.append(dict(c))
            continue
        ini = float(c.get("inicio", 0))
        vel = float(c.get("velocidade", 1.0))
        meio = ini + d * vel / 2
        n = dict(c)
        n["inicio"] = round(meio - quero * vel / 2, 2)
        n["fim"] = round(meio + quero * vel / 2, 2)
        out.append(n)
    return out


def trechos_de_fala(projeto: dict, transcrever_fn) -> list:
    """[(clipe, inicio, fim, texto)] por frase, a partir do corte limpo de cada clipe com fala."""
    from .corte import marcar_remocoes, segmentos
    from .ingest import resolver
    out = []
    for c in projeto.get("clipes") or []:
        if c.get("mudo"):
            continue
        arq = resolver(projeto, c["arquivo"])
        pal = transcrever_fn(arq)
        if not pal:
            continue
        fora = marcar_remocoes(pal, projeto.get("remover_trechos"))
        ini = float(c.get("inicio", 0))
        fim = float(c.get("fim", pal[-1]["fim"] + 0.5))
        # frases: quebra na pontuação final
        frase, frases = [], []
        for i, w in enumerate(pal):
            if i in fora or not ini <= w["inicio"] < fim:
                continue
            frase.append(w)
            if re.search(r"[.!?]$", w["texto"]):
                frases.append(frase)
                frase = []
        if frase:
            frases.append(frase)
        for f in frases:
            segs = segmentos(f, {}, ini, fim)
            if segs:
                out.append((c, segs[0][0], segs[-1][1], " ".join(w["texto"] for w in f)))
    return out


def escolher_trechos(trechos: list, alvo: float) -> list:
    """Frases em ordem até a duração alvo (sempre ao menos uma)."""
    sel, tot = [], 0.0
    for t in trechos:
        d = t[2] - t[1]
        if sel and tot + d > alvo * 1.1:
            break
        sel.append(t)
        tot += d
    return sel


def _clipes_de_trechos(sel: list) -> list:
    """Frases seguidas do mesmo take entram com corte seco; take diferente, com dissolve."""
    out = []
    for k, (c, a, b, _) in enumerate(sel):
        n = {kk: v for kk, v in c.items() if kk not in ("inicio", "fim", "corte_limpo")}
        n.update({"inicio": round(a, 2), "fim": round(b, 2)})
        if k and sel[k - 1][0].get("arquivo") == c.get("arquivo"):
            n["corte_seco"] = True
        out.append(n)
    return out


def montar_pacote(projeto: dict, categorias: list | None = None, transcrever_fn=None) -> list:
    """Cria as pastas e os projeto.yaml de cada peça. Devolve [(pasta, nome)]."""
    from .hooks import sortear
    cfg = load("pacote")["categorias"]
    if categorias:
        desconhecidas = set(categorias) - {c["id"] for c in cfg}
        if desconhecidas:
            raise SystemExit(f"Categorias desconhecidas: {', '.join(desconhecidas)} (veja config/pacote.yaml)")
    origem = projeto["_pasta"]
    destino = origem.parent / f"{origem.name}-pacote"
    destino.mkdir(exist_ok=True)
    base = {k: v for k, v in projeto.items() if not k.startswith("_")}
    trechos = trechos_de_fala(projeto, transcrever_fn) if transcrever_fn else []
    criadas = []
    usados = {v.get("hook_id") for v in projeto.get("versoes") or [] if v.get("hook_id")}
    for n, cat in enumerate(cfg, start=1):
        if categorias and cat["id"] not in categorias:
            continue      # a numeração fica a mesma do pacote completo
        grupos = [None]
        if cat.get("por_trecho"):
            if not trechos:
                print(f"  · {cat['nome']}: sem transcrição, pulei (cortes precisam da fala)")
                continue
            grupos = _cortes(trechos, float(cat["alvo_s"]), int(cat.get("max_cortes", 3)))
        for g_i, grupo in enumerate(grupos, start=1):
            p = copy.deepcopy(base)
            sufixo = f"-{g_i}" if len(grupos) > 1 else ""
            nome = f"{cat['nome']}{f' {g_i}' if len(grupos) > 1 else ''}"
            p["titulo"] = f"{base.get('titulo', 'Vídeo')} · {nome}"
            p["tema"] = base.get("tema") or base.get("titulo", "video")
            p["categoria"] = f"{cat['id']}{sufixo}"
            p["formato"] = cat["formato"]
            if cat.get("template"):
                p["template"] = cat["template"]
            alvo = cat.get("alvo_s")
            if grupo is not None:
                p["clipes"] = _clipes_de_trechos(grupo)
                p.pop("corte_limpo", None)
            elif alvo:
                if trechos and not cat.get("sem_voz"):
                    p["clipes"] = _clipes_de_trechos(escolher_trechos(trechos, float(alvo)))
                    p.pop("corte_limpo", None)
                else:
                    clipes = copy.deepcopy(p.get("clipes") or [])
                    if cat.get("template") == "tv":
                        vel = load("templates")["tv"]["velocidade"]
                        clipes = [{**c, "velocidade": c.get("velocidade", vel)} for c in clipes]
                    p["clipes"] = recortar_miolo(p | {"_pasta": origem}, clipes, float(alvo))
            if cat.get("sem_voz"):
                p["audio"] = {**(p.get("audio") or {}), "original": False, "trilha": True}
                p["legendas"] = False
            if cat.get("sem_mensagens"):
                p["mensagens"] = []
            # caminhos dos brutos relativos à nova pasta
            for c in p.get("clipes") or []:
                c["arquivo"] = _rel(origem, c["arquivo"])
            for c in p.get("clipes_referencia") or []:
                c["arquivo"] = _rel(origem, c["arquivo"])
            nv = int(cat.get("versoes", 3))
            if cat.get("template") == "tv":
                p["versoes"] = [{"nome": "TV"}]
                p.setdefault("tv", {"tratamento": base.get("titulo", "")})
                p["audio"] = {"original": False, "trilha": True}    # TV da recepção: sem voz
                p["legendas"] = False
            elif cat.get("hook") == "banco" and base.get("versoes"):
                p["versoes"] = copy.deepcopy(base["versoes"][:nv])
            else:
                excl = set(usados)
                if cat.get("hook") == "pov":
                    from .hooks import ler_banco
                    excl |= {h["id"] for h in ler_banco() if "pov" not in h["descricao"].lower()}
                hs = sortear(nv, tema=base.get("titulo"), semente=n * 31 + g_i, excluir=excl)
                usados |= {h["id"] for h in hs}
                p["versoes"] = [{"nome": f"V{k + 1}", "hook_id": h["id"]} for k, h in enumerate(hs)]
            if cat["id"] != "reels-longo":
                p.pop("legenda", None)      # cada peça ganha a própria legenda (gerada no editar)
            pasta = destino / f"{n:02d}_{cat['id']}{sufixo}"
            pasta.mkdir(exist_ok=True)
            for sub in ("bruto", "trabalho", "saida"):
                (pasta / sub).mkdir(exist_ok=True)
            cab = (f"# {nome} · gerado por `divine pacote` a partir de {origem.name}. Revise e ajuste à vontade.\n")
            (pasta / "projeto.yaml").write_text(cab + yaml.safe_dump(p, allow_unicode=True, sort_keys=False, width=1000),
                                                encoding="utf-8")
            criadas.append((pasta, nome))
    return criadas


def _cortes(trechos: list, alvo: float, maximo: int) -> list:
    """Divide a fala em cortes de ~alvo segundos, cada um com frases inteiras."""
    grupos, atual, tot = [], [], 0.0
    for t in trechos:
        d = t[2] - t[1]
        if atual and tot + d > alvo * 1.15:
            grupos.append(atual)
            atual, tot = [], 0.0
        atual.append(t)
        tot += d
    if atual and (tot > alvo * 0.4 or not grupos):
        grupos.append(atual)
    return grupos[:maximo]


def _rel(origem, caminho: str) -> str:
    """Caminho do bruto visto da pasta da peça (dois níveis abaixo da pasta de projetos)."""
    from pathlib import Path
    p = Path(caminho)
    if p.is_absolute():
        return str(p)
    if (origem / p).exists() or not (origem.parent.parent / p).exists():
        return str(Path("..") / ".." / origem.name / p)
    return str(p)
