"""Cortes de vídeo longo: um bruto longo vira várias peças (curtas, médias, longas, melhores momentos e Stories).

  python3 -m divine_studio cortes projetos/2026-11-02_podcast-co2

Com transcrição (faster-whisper ou AssemblyAI): cada corte é feito de frases inteiras e seguidas, começando pela frase
mais forte (pergunta, número, "você", palavras de força). "Melhores momentos" junta as frases mais fortes de partes
diferentes, em ordem, para fazer sentido. Sem transcrição: os cortes seguem as pausas do áudio.
Cada peça vira projetos/<projeto>-cortes/NN_<tipo>-<n>/projeto.yaml, pronta para editar (3 versões, legenda da fala).
"""
from __future__ import annotations

import copy
import re
import subprocess

import yaml

from .config import load


def _cfg() -> dict:
    return load("cortes")


def pontuar(texto: str, dur: float) -> float:
    c = _cfg()["pontuacao"]
    t = (texto or "").lower()
    s = 1.0
    if "?" in t:
        s += c["pergunta"]
    if re.search(r"\d", t):
        s += c["numero"]
    s += c["palavras_forca"] * sum(1 for p in _cfg()["palavras_forca"] if re.search(rf"\b{re.escape(p)}\b", t))
    if re.match(r"^(você|voce|sabe|o que|por que|porque|como|qual)\b", t):
        s += c["abre_com_voce"]
    if dur < c["curta_demais_s"]:
        s -= 1.0
    return round(s, 2)


def trechos_por_pausas(projeto: dict) -> list:
    """Sem fala transcrita: divide cada clipe nas pausas do áudio (silencedetect)."""
    from .ingest import probe, resolver
    out = []
    for c in projeto.get("clipes") or []:
        arq = resolver(projeto, c["arquivo"])
        dur = probe(arq)["duracao"]
        ini, fim = float(c.get("inicio", 0)), float(c.get("fim") or dur)
        r = subprocess.run(["ffmpeg", "-hide_banner", "-ss", str(ini), "-t", str(fim - ini), "-i", str(arq),
                            "-af", "silencedetect=noise=-32dB:d=0.45", "-f", "null", "-"], capture_output=True, text=True)
        pausas = [ini + float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
        marcos = [ini] + [p for p in pausas if ini + 2 < p < fim - 2] + [fim]
        # pedaços de 4 a 12 s entre pausas
        a = marcos[0]
        for b in marcos[1:]:
            if b - a >= 4 or b == marcos[-1]:
                while b - a > 12:
                    out.append((c, a, a + 8, ""))
                    a += 8
                if b - a > 1:
                    out.append((c, a, b, ""))
                a = b
    return out


def _blocos(trechos: list, min_s: float, max_s: float) -> list:
    """Sequências de frases seguidas (mesmo arquivo, sem buraco grande) com duração entre min e max."""
    blocos = []
    for i in range(len(trechos)):
        tot, sel = 0.0, []
        for j in range(i, len(trechos)):
            c, a, b, txt = trechos[j]
            if sel:
                pc, pa, pb, _ = sel[-1]
                if pc.get("arquivo") != c.get("arquivo") or a - pb > 2.5:
                    break
            sel.append(trechos[j])
            tot += b - a
            if tot > max_s:
                sel.pop()
                tot -= b - a
                break
        if tot >= min_s and sel:
            notas = [pontuar(t[3], t[2] - t[1]) for t in sel]
            fecha = 0.5 if re.search(r"[.!?]\s*$", sel[-1][3] or ".") else 0.0
            nota = notas[0] * 2 + sum(notas[1:]) / max(1, len(notas) - 1) + fecha
            blocos.append({"trechos": sel, "nota": round(nota, 2), "ini": sel[0][1], "fim": sel[-1][2],
                           "arquivo": sel[0][0].get("arquivo"), "dur": round(tot, 1)})
    return sorted(blocos, key=lambda b: -b["nota"])


def _sobrepoe(b, escolhidos):
    return any(b["arquivo"] == e["arquivo"] and b["ini"] < e["fim"] and e["ini"] < b["fim"] for e in escolhidos)


def _sobreposicao(b, usados) -> float:
    """Fração do bloco que já está em outra peça (para espalhar os cortes pelo vídeo inteiro)."""
    tot = 0.0
    for arq, a, z in usados:
        if arq == b["arquivo"]:
            tot += max(0.0, min(z, b["fim"]) - max(a, b["ini"]))
    return tot / max(0.1, b["fim"] - b["ini"])


def planejar(trechos: list) -> list:
    """[(tipo, nome, [trechos], nota)] de todas as peças. Do maior para o menor, preferindo partes ainda não usadas."""
    cfg = _cfg()
    pecas, usados = [], []
    tam = cfg["tamanhos"]
    for tipo in sorted(tam, key=lambda k: -float(tam[k]["max_s"])):
        t = tam[tipo]
        escolhidos = []
        cands = _blocos(trechos, float(t["min_s"]), float(t["max_s"]))
        while len(escolhidos) < int(t["quantos"]):
            livres = [b for b in cands if not _sobrepoe(b, escolhidos)]
            if not livres:
                break
            b = max(livres, key=lambda x: x["nota"] - 2.5 * _sobreposicao(x, usados))
            escolhidos.append(b)
        usados += [(b["arquivo"], b["ini"], b["fim"]) for b in escolhidos]
        for k, b in enumerate(sorted(escolhidos, key=lambda x: (x["arquivo"], x["ini"])), start=1):
            pecas.append((tipo, f"{t['nome']} {k}", b["trechos"], b["nota"]))
    # melhores momentos: as frases mais fortes de partes diferentes, em ordem
    mm = cfg["melhores_momentos"]
    fortes = sorted(trechos, key=lambda t: -pontuar(t[3], t[2] - t[1]))
    sel, tot = [], 0.0
    for t in fortes:
        if any(t[0].get("arquivo") == s[0].get("arquivo") and abs(t[1] - s[1]) < float(mm["distancia_min_s"]) for s in sel):
            continue
        if tot + (t[2] - t[1]) > float(mm["alvo_s"]) * 1.1:
            continue
        sel.append(t)
        tot += t[2] - t[1]
    if len(sel) >= int(mm["min_frases"]):
        sel.sort(key=lambda t: (str(t[0].get("arquivo")), t[1]))
        pecas.append(("melhores", mm["nome"], sel, round(sum(pontuar(t[3], t[2] - t[1]) for t in sel) / len(sel), 2)))
    # stories: os melhores curtos de até 15 s
    st = cfg["stories"]
    esc = []
    cands = _blocos(trechos, 5, float(st["max_s"]))
    while len(esc) < int(st["quantos"]):
        livres = [b for b in cands if not _sobrepoe(b, esc)]
        if not livres:
            break
        esc.append(max(livres, key=lambda x: x["nota"] - 2.5 * _sobreposicao(x, usados)))
    for k, b in enumerate(esc, start=1):
        pecas.append(("stories", f"{st['nome']} {k}", b["trechos"], b["nota"]))
    return pecas


def _mmss(s: float) -> str:
    return f"{int(s // 60)}:{int(s % 60):02d}"


def montar(projeto: dict, transcrever_fn=None) -> list:
    """Cria as peças. Devolve [(pasta, nome, resumo)]."""
    from .hooks import sortear
    from .pacote import _clipes_de_trechos, _rel, trechos_de_fala
    origem = projeto["_pasta"]
    trechos = trechos_de_fala(projeto, transcrever_fn) if transcrever_fn else []
    com_fala = bool(trechos)
    if not trechos:
        trechos = trechos_por_pausas(projeto)
    if not trechos:
        raise SystemExit("Não achei trechos no vídeo (ele tem áudio?).")
    pecas = planejar(trechos)
    destino = origem.parent / f"{origem.name}-cortes"
    destino.mkdir(exist_ok=True)
    base = {k: v for k, v in projeto.items() if not k.startswith("_")}
    cfg = _cfg()
    usados, criadas = set(), []
    for n, (tipo, nome, sel, nota) in enumerate(pecas, start=1):
        p = copy.deepcopy(base)
        t_ini, t_fim = sel[0][1], sel[-1][2]
        dur = sum(t[2] - t[1] for t in sel)
        p["titulo"] = f"{base.get('titulo', 'Vídeo')} · {nome}"
        p["categoria"] = f"corte-{tipo}"
        p["formato"] = "stories" if tipo == "stories" else "reels"
        p["clipes"] = _clipes_de_trechos(sel)
        for c in p["clipes"]:
            c["arquivo"] = _rel(origem, c["arquivo"])
        p.pop("corte_limpo", None)
        p["legendas"] = com_fala
        p["mensagens"] = []
        p.pop("legenda", None)
        p.pop("publicacoes", None)
        p["corte"] = {"tipo": tipo, "de": _mmss(t_ini), "ate": _mmss(t_fim), "duracao_s": round(dur, 1), "nota": nota,
                      "texto": " ".join(t[3] for t in sel)[:400]}
        if tipo == "stories":
            nv = int(cfg["stories"]["versoes"])
        elif tipo == "melhores":
            nv = int(cfg["melhores_momentos"]["versoes"])
        else:
            nv = int(cfg["tamanhos"][tipo]["versoes"])
        hs = sortear(nv, tema=base.get("titulo"), semente=n * 17, excluir=usados)
        usados |= {h["id"] for h in hs}
        p["versoes"] = [{"nome": f"V{k + 1}", "hook_id": h["id"]} for k, h in enumerate(hs)]
        tags = list(dict.fromkeys(list(base.get("tags") or []) + ["corte", tipo]))
        p["tags"] = tags
        pasta = destino / f"{n:02d}_{tipo}-{slug_num(nome)}"
        for sub in ("bruto", "trabalho", "saida"):
            (pasta / sub).mkdir(parents=True, exist_ok=True)
        cab = f"# {nome} · corte de {origem.name} ({_mmss(t_ini)} a {_mmss(t_fim)}, {dur:.0f} s). Ajuste à vontade.\n"
        (pasta / "projeto.yaml").write_text(cab + yaml.safe_dump(p, allow_unicode=True, sort_keys=False, width=1000),
                                            encoding="utf-8")
        criadas.append((pasta, nome, p["corte"]))
    return criadas


def slug_num(nome: str) -> str:
    m = re.search(r"(\d+)$", nome)
    return m.group(1) if m else "1"
