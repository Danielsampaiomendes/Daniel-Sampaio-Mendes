"""Storyboard: a edição real em quadros, antes de renderizar.

Cada quadro é exatamente o que vai sair naquele instante (mesma composição do render, render.quadros_em).
Cenas numeradas (1, 2, 3...) e, dentro delas, momentos com letra (4A, 4B): texto que entra, efeito, corte,
fechamento. Você responde "aprovado" (vai para a final) ou "4B: troca o título por ...", "7: tira",
"2A: entra mais cedo". Os pedidos mudam o projeto.yaml (com cópia em trabalho/) e o storyboard é refeito.

python3 -m divine_studio storyboard <pasta> [--versoes V1] [--responder "4B: ..."]
Regras e palavras em config/storyboard.yaml.
"""
from __future__ import annotations

import copy
import json
import re
import time
from pathlib import Path

import yaml
from PIL import Image

from .config import load

LETRAS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _cfg() -> dict:
    return load("storyboard")


# ------------------------------------------------------------------ momentos e cenas
def momentos(plano, projeto: dict, versao_idx: int = 0) -> list:
    """O que acontece no vídeo e de onde veio no projeto.yaml (para poder mudar)."""
    out = []
    fim_total = float(plano.inicio_fechamento)
    for c in plano.camadas:
        m = re.match(r"^(hook|msg)(\d+)_titulo$", c.nome)
        if m:
            k = int(m.group(2))
            origem = {"campo": "hook", "versao": versao_idx, "k": k} if m.group(1) == "hook" \
                else {"campo": "mensagens", "k": k}
            out.append({"t": c.t0, "fim": c.t1, "tipo": "hook" if m.group(1) == "hook" else "mensagem",
                        "texto": (c.texto or "").strip(), "origem": origem})
        elif c.nome == "cta_antecipado":
            out.append({"t": c.t0, "fim": c.t1, "tipo": "chamada", "texto": c.texto, "origem": {"campo": "cta_antecipado"}})
    ordem = getattr(plano, "efeitos_ordem", None)
    if ordem is not None:                                       # tempos reais, depois do espaçamento do render
        for e in ordem:
            o = e.get("_origem")
            if isinstance(o, (list, tuple)):
                origem = {"campo": o[0], "k": o[1], **({"versao": versao_idx} if o[0] == "versao_efeitos" else {})}
                out.append(_mom_efeito(e, origem))
            else:
                out.append(_mom_efeito(e, {"campo": "auto", "tipo": e.get("tipo"),
                                           "inicio": round(float(e.get("inicio", 0)), 2), "dados": _limpar(e)}, auto=True))
    else:
        for j, e in enumerate(projeto.get("efeitos") or []):
            out.append(_mom_efeito(e, {"campo": "efeitos", "k": j}))
        for e in getattr(plano, "efeitos_auto", None) or []:
            out.append(_mom_efeito(e, {"campo": "auto", "tipo": e.get("tipo"),
                                       "inicio": round(float(e.get("inicio", 0)), 2), "dados": _limpar(e)}, auto=True))
    for k, c in enumerate((projeto.get("_base_meta") or {}).get("clipes") or []):
        ini = float(c.get("inicio_base", 0))
        if k and ini < fim_total - 0.5:
            out.append({"t": ini, "fim": ini + 1.0, "tipo": "corte", "texto": f"corte para o take {k + 1}",
                        "origem": {"campo": "clipes", "k": k}})
    out.append({"t": fim_total, "fim": float(plano.duracao_total), "tipo": "fechamento",
                "texto": _texto_fechamento(projeto), "origem": {"campo": "fechamento"}})
    out = [m for m in out if m["t"] <= float(plano.duracao_total)]
    out.sort(key=lambda m: (round(m["t"], 2), m["tipo"] != "corte"))
    for m in out:
        m["t"] = round(float(m["t"]), 2)
        m["fim"] = round(float(m["fim"]), 2)
        m["t_quadro"] = _instante(m, float(plano.duracao_total))
    return out


def _limpar(e: dict) -> dict:
    return {k: v for k, v in e.items() if not str(k).startswith("_")}


def _mom_efeito(e: dict, origem: dict, auto: bool = False) -> dict:
    from .efeitos import DURACAO_PADRAO, resolver_tipo
    tipo = resolver_tipo(dict(e))
    ini = float(e.get("inicio", 0))
    dur = float(e.get("duracao", DURACAO_PADRAO.get(tipo, 2.0)))
    texto = e.get("texto") or e.get("titulo") or ""
    return {"t": ini, "fim": ini + dur, "tipo": "efeito", "efeito": tipo, "auto": auto,
            "texto": f"{_nome_efeito(tipo)}{': ' + str(texto) if texto else ''}", "origem": origem}


def _nome_efeito(tipo: str) -> str:
    from .efeitos import NOMES
    return NOMES.get(tipo, tipo.replace("_", " "))


def _texto_fechamento(p: dict) -> str:
    f = p.get("fechamento") or {}
    return str(f.get("frase") or f.get("cta") or "fechamento com a marca").replace(" / ", " ")


def _instante(m: dict, total: float) -> float:
    """O quadro mostra o momento já inteiro na tela (depois da entrada), nunca o escurecer do fim."""
    if m["tipo"] == "efeito":
        t = m["t"] + (m["fim"] - m["t"]) * 0.5
    elif m["tipo"] == "corte":
        t = m["t"] + 0.3
    elif m["tipo"] == "fechamento":
        t = m["t"] + 1.6
    else:
        t = m["t"] + 0.75
    t = min(t, m["fim"] - 0.1) if m["fim"] > m["t"] + 0.2 else t
    return round(max(0.0, min(t, total - 0.8)), 2)


def cenas(moms: list, plano, projeto: dict) -> list:
    """Cenas pelos cortes entre takes e pelos blocos (hook, mensagens, fechamento). Códigos 1, 2, 4A, 4B..."""
    cfg = _cfg()["cenas"]
    total = float(plano.duracao_total)
    fech = float(plano.inicio_fechamento)
    marcos = {0.0, fech}
    marcos |= {m["t"] for m in moms if m["tipo"] in ("corte", "mensagem", "chamada", "hook")}
    marcos |= {float(getattr(plano, "hook_fim", 0) or 0)}
    lim = sorted(t for t in marcos if 0 <= t < total)
    juntos = []
    for t in lim:                                     # cenas curtas demais se juntam (menos a do fechamento)
        if juntos and t - juntos[-1] < float(cfg["juntar_menor_que_s"]) and t != fech:
            continue
        juntos.append(t)
    lim = juntos + [total]
    fala = projeto.get("_fala") or []
    out = []
    for i in range(len(lim) - 1):
        a, b = lim[i], lim[i + 1]
        dentro = [dict(m) for m in moms if a <= m["t"] < b]
        if not dentro or (b - a > float(cfg["quebrar_maior_que_s"]) and len(dentro) < 2):
            meio = round(a + min(b - a, 6.0) * (0.5 if dentro else 0.35), 2)
            dentro.append({"t": round(a, 2), "fim": round(b, 2), "tipo": "cena", "texto": "", "origem": {"campo": "cena"},
                           "t_quadro": round(min(meio, total - 0.8), 2)})
            dentro.sort(key=lambda m: m["t_quadro"])
        n = len(out) + 1
        for j, m in enumerate(dentro):
            m["codigo"] = f"{n}{LETRAS[j]}" if len(dentro) > 1 else str(n)
        out.append({"numero": n, "inicio": round(a, 2), "fim": round(b, 2),
                    "fala": " ".join(w["palavra"] for w in fala if a <= float(w["inicio"]) < b).strip(),
                    "momentos": dentro})
    return out


# ------------------------------------------------------------------ gerar
def gerar(pasta: Path, nome_versao: str, plano, projeto: dict, base: Path, W: int, H: int, duracao_base: float,
          base_tamanho: tuple | None = None, extras: list | None = None, versao_idx: int = 0, estilo: str = "") -> dict:
    """Grava trabalho/storyboard/<V>/<código>.jpg e trabalho/storyboard_<V>.json."""
    from .render import quadros_em
    t0 = time.time()
    cfg = _cfg()
    moms = momentos(plano, projeto, versao_idx)
    cs = cenas(moms, plano, projeto)
    todos = [m for c in cs for m in c["momentos"]]
    quadros = quadros_em(base, plano, [m["t_quadro"] for m in todos], W, H, duracao_base, base_tamanho, extras,
                         amostra=float(cfg.get("amostra_fps", 10)))
    destino = pasta / "trabalho" / "storyboard" / nome_versao
    destino.mkdir(parents=True, exist_ok=True)
    for f in destino.glob("*.jpg"):
        f.unlink()                                      # miniaturas são refeitas a cada storyboard (não são peças)
    larg = int(cfg.get("largura_quadro", 360))
    for m in todos:
        q = quadros.get(round(float(m["t_quadro"]), 3))
        if q is None:
            continue
        img = Image.fromarray(q)
        grande = destino / f"{m['codigo']}_grande.jpg"
        img.convert("RGB").save(grande, quality=86)
        img.thumbnail((larg, larg * 4))
        img.convert("RGB").save(destino / f"{m['codigo']}.jpg", quality=84)
        m["quadro"] = str((destino / f"{m['codigo']}.jpg").relative_to(pasta))
        m["quadro_grande"] = str(grande.relative_to(pasta))
    v = (projeto.get("versoes") or [{}])[versao_idx] if projeto.get("versoes") else {}
    hook = v.get("hook") or []
    dados = {"versao": nome_versao, "titulo": projeto.get("titulo", pasta.name),
             "estilo": estilo or projeto.get("estilo_edicao") or projeto.get("template", "divine"),
             "duracao": round(float(plano.duracao_total), 1), "cenas_total": len(cs), "momentos_total": len(todos),
             "gerado_em": time.strftime("%d/%m/%Y %H:%M"), "segundos": round(time.time() - t0, 1),
             "hook": hook if isinstance(hook, list) else [hook], "cenas": cs}
    (pasta / "trabalho" / "storyboard_aprovado.json").unlink(missing_ok=True)     # storyboard novo: aprovar de novo
    (pasta / "trabalho" / f"storyboard_{nome_versao}.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                                                                       encoding="utf-8")
    return dados


def ler(pasta: Path, versao: str = "V1") -> dict:
    try:
        return json.loads((pasta / "trabalho" / f"storyboard_{versao}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def versoes_com_storyboard(pasta: Path) -> list:
    nomes = [f.stem.split("_", 1)[1] for f in (pasta / "trabalho").glob("storyboard_*.json")] \
        if (pasta / "trabalho").exists() else []
    return sorted((n for n in nomes if n != "aprovado"), key=lambda n: (not n.startswith("V"), n))


# ------------------------------------------------------------------ responder
def eh_aprovacao(texto: str) -> bool:
    t = re.sub(r"[^\wà-ú ]", " ", (texto or "").lower()).strip()
    if re.search(r"\b(n[aã]o|ainda|nada)\b", t) or "?" in (texto or ""):
        return False
    return any(t == a or t.startswith(a + " ") or t.endswith(" " + a) for a in _cfg()["aprovar"])


def interpretar(texto: str) -> list:
    """'4B: troca o título por "X"; 7: tira' -> [{codigo, pedido, acao, valor}]."""
    itens = []
    partes = re.split(r"[;\n]+|,\s*(?=\d{1,2}[A-Za-z]?\s*[:\-–])", texto or "")
    for parte in partes:
        m = re.match(r"^\s*(\d{1,2}[A-Za-z]?)\s*[:\-–]\s*(.+)$", parte.strip())
        if not m:
            if parte.strip():
                itens.append({"codigo": None, "pedido": parte.strip(), "acao": None})
            continue
        codigo, pedido = m.group(1).upper(), m.group(2).strip()
        acao, valor = None, None
        for regra in _cfg()["pedidos"]:
            r = re.search(regra["padrao"], pedido, re.I)
            if r:
                acao = regra["acao"]
                valor = r.groupdict().get("valor")
                break
        itens.append({"codigo": codigo, "pedido": pedido, "acao": acao, "valor": (valor or "").strip() or None})
    return itens


def _numero(pedido: str, padrao: float) -> float:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(s|seg|segundo)", pedido)
    return float(m.group(1).replace(",", ".")) if m else padrao


def _achar(sb: dict, codigo: str) -> dict | None:
    for c in sb.get("cenas") or []:
        for m in c["momentos"]:
            if m["codigo"].upper() == codigo.upper():
                return m
        if str(c["numero"]) == codigo and c["momentos"]:
            return c["momentos"][0]
    return None


def responder(pasta: Path, texto: str, versao: str = "V1") -> dict:
    """Aplica a resposta ao storyboard. Devolve {aprovado, aplicados, nao_entendi, avisos}."""
    if eh_aprovacao(texto):
        (pasta / "trabalho").mkdir(exist_ok=True)
        (pasta / "trabalho" / "storyboard_aprovado.json").write_text(json.dumps(
            {"versao": versao, "em": time.strftime("%Y-%m-%d %H:%M")}), encoding="utf-8")
        return {"aprovado": True, "aplicados": [], "nao_entendi": [], "avisos": []}
    sb = ler(pasta, versao)
    if not sb:
        raise ValueError("gere o storyboard primeiro")
    arq = pasta / "projeto.yaml"
    d = yaml.safe_load(arq.read_text(encoding="utf-8")) or {}
    original = arq.read_text(encoding="utf-8")
    aplicados, nao, avisos = [], [], []
    passo = float(_cfg().get("passo_s", 0.5))
    for it in interpretar(texto):
        m = _achar(sb, it["codigo"]) if it["codigo"] else None
        if it["codigo"] and not m:
            nao.append({**it, "motivo": f"não existe o código {it['codigo']} neste storyboard"})
            continue
        if not m or not it["acao"]:
            nao.append({**it, "motivo": "não entendi o pedido"})
            continue
        tentativa = copy.deepcopy(d)                  # só vale se o pedido inteiro der certo
        try:
            feito = _aplicar(tentativa, sb, m, it, passo, versao, pasta)
        except ValueError as e:
            avisos.append(f"{it['codigo']}: {e}")
            continue
        if feito:
            d = tentativa
            aplicados.append(f"{it['codigo']}: {feito}")
        else:
            nao.append({**it, "motivo": f"esse pedido não vale para {_tipo_txt(m)}"})
    if aplicados:
        from .compliance import revisar
        erros = [a.linha() for a in revisar(d) if a.nivel == "erro"]
        if erros:
            return {"aprovado": False, "aplicados": [], "nao_entendi": nao,
                    "avisos": ["O revisor (CFM/Anvisa) barrou a mudança: " + "; ".join(erros)]}
        (pasta / "trabalho").mkdir(exist_ok=True)
        (pasta / "trabalho" / f"projeto.yaml.antes-do-storyboard-{time.strftime('%H%M%S')}").write_text(
            original, encoding="utf-8")
        arq.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=1000, default_flow_style=None),
                       encoding="utf-8")
        _aprender(pasta, versao, aplicados)
    return {"aprovado": False, "aplicados": aplicados, "nao_entendi": nao, "avisos": avisos}


def _tipo_txt(m: dict) -> str:
    return {"hook": "o hook", "mensagem": "a mensagem", "chamada": "a chamada", "efeito": "o efeito",
            "corte": "o corte", "fechamento": "o fechamento", "cena": "esta cena"}.get(m["tipo"], "este momento")


def _alvo(d: dict, sb: dict, origem: dict, versao: str, pasta: Path):
    """(lista, índice) do elemento no projeto.yaml, resolvendo hook do banco e efeito automático."""
    campo = origem.get("campo")
    if campo == "hook":
        vs = d.setdefault("versoes", [])
        v = next((x for x in vs if x.get("nome") == versao), None)
        if v is None:
            raise ValueError("versão não encontrada no projeto")
        if not isinstance(v.get("hook"), list):                 # hook do banco: vira texto próprio editável
            v["hook"] = [dict(b) for b in sb.get("hook") or []] or ([v["hook"]] if isinstance(v.get("hook"), dict) else [])
            v.pop("hook_id", None)
        return v["hook"], int(origem["k"])
    if campo == "mensagens":
        return d.setdefault("mensagens", []), int(origem["k"])
    if campo == "efeitos":
        return d.setdefault("efeitos", []), int(origem["k"])
    if campo == "versao_efeitos":
        v = next((x for x in d.get("versoes") or [] if x.get("nome") == versao), None)
        return (v or {}).setdefault("efeitos", []), int(origem["k"])
    if campo == "auto":                                         # automático: entra na linha do tempo para mudar
        ef = origem.get("dados")
        if not ef:
            linha = pasta / "trabalho" / f"linha_{versao}.json"
            auto = json.loads(linha.read_text(encoding="utf-8")).get("efeitos", []) if linha.exists() else []
            ef = next((e for e in auto if e.get("tipo") == origem["tipo"]
                       and abs(float(e.get("inicio", 0)) - float(origem["inicio"])) < 0.05), None)
        if ef is None:
            raise ValueError("efeito automático não encontrado; gere o storyboard de novo")
        evitar = d.setdefault("efeitos_evitar", [])            # o original automático não volta
        if not any(e.get("tipo") == ef["tipo"] and abs(float(e.get("inicio", 0)) - float(ef["inicio"])) < 0.05
                   for e in evitar):
            evitar.append({"tipo": ef["tipo"], "inicio": round(float(ef["inicio"]), 2)})
        lista = d.setdefault("efeitos", [])
        lista.append({k: v for k, v in ef.items() if not k.startswith("_")})
        return lista, len(lista) - 1
    return None, None


def _aplicar(d, sb, m, it, passo, versao, pasta) -> str | None:
    acao, pedido, valor = it["acao"], it["pedido"], it.get("valor")
    origem = m["origem"]
    if acao == "fonte":
        from .rodizio import todas_combinacoes
        v = next((x for x in d.get("versoes") or [] if x.get("nome") == versao), None)
        rod = pasta / "trabalho" / "rodizio_escolhido.json"
        atual = (v or {}).get("fontes") or (json.loads(rod.read_text(encoding="utf-8")).get(versao, {}).get("fontes")
                                            if rod.exists() else None)
        ordem = todas_combinacoes()
        nova = ordem[(ordem.index(atual) + 1) % len(ordem)] if atual in ordem else ordem[0]
        if v is not None:
            v["fontes"] = nova
        return f"fontes da {versao} trocadas para a combinação {nova}"
    if origem.get("campo") == "fechamento":
        if acao == "texto":
            d.setdefault("fechamento", {})["frase"] = valor
            return f"frase final: {valor}"
        return None
    if origem.get("campo") in ("cena", "clipes"):
        if acao == "tirar" and origem.get("campo") == "clipes":
            clipes = d.get("clipes") or []
            k = int(origem["k"])
            if k < len(clipes):
                d.setdefault("clipes_descartados", []).append(clipes.pop(k))   # não apaga: fica guardado
                return f"take {k + 1} fora da edição (guardado em clipes_descartados)"
        return None
    if origem.get("campo") == "cta_antecipado":
        if acao == "texto":
            d["cta_antecipado"] = valor
            return f"chamada: {valor}"
        if acao == "tirar":
            d.pop("cta_antecipado", None)
            return "chamada antecipada retirada"
        return None
    lista, k = _alvo(d, sb, origem, versao, pasta)
    if lista is None or k is None or k >= len(lista):
        return None
    el = lista[k]
    n = _numero(pedido, passo)
    eh_ef = origem.get("campo") in ("efeitos", "versao_efeitos", "auto")
    if acao == "texto":
        if eh_ef:
            from .efeitos import CAMPOS
            campos = {c[0] if isinstance(c, (list, tuple)) else c for c in CAMPOS.get(el.get("tipo"), [])}
            chave = "texto" if "texto" in campos else "titulo" if "titulo" in campos else None
            if not chave:
                raise ValueError(f"o efeito {_nome_efeito(el.get('tipo'))} não tem texto; para trocar o efeito diga "
                                 "'troca o efeito por flash'")
            el[chave] = valor
        else:
            el["titulo"] = valor
        return f"texto trocado para \"{valor}\""
    if acao == "tirar":
        lista.pop(k)
        if origem.get("campo") == "auto":
            return f"efeito automático {_nome_efeito(origem['tipo'])} em {origem['inicio']}s não entra mais"
        return "retirado"
    if acao in ("mais_cedo", "mais_tarde"):
        delta = -n if acao == "mais_cedo" else n
        if origem.get("campo") == "hook":
            if k == 0:
                raise ValueError("o hook já começa no 0 s; para ele durar menos, diga 'mais curto'")
            ant = lista[k - 1]
            ant["duracao"] = round(max(0.8, float(ant.get("duracao") or m["t"]) + delta), 2)
        else:
            el["inicio"] = round(max(0.0, float(el.get("inicio", m["t"])) + delta), 2)
            if "fim" in el:
                el["fim"] = round(float(el["fim"]) + delta, 2)
        return f"entra {abs(delta):.1f}s {'mais cedo' if delta < 0 else 'mais tarde'}"
    if acao in ("mais_longo", "mais_curto"):
        delta = n if acao == "mais_longo" else -n
        dur = float(el.get("duracao") or (m["fim"] - m["t"]))
        if "fim" in el:
            el["fim"] = round(max(float(el.get("inicio", m["t"])) + 0.8, float(el["fim"]) + delta), 2)
        else:
            el["duracao"] = round(max(0.8, dur + delta), 2)
        return f"{'mais longo' if delta > 0 else 'mais curto'} ({abs(delta):.1f}s)"
    if acao == "posicao":
        p = pedido.lower()
        pos = "topo" if re.search(r"cima|topo", p) else "base" if re.search(r"baixo", p) else "centro"
        el["posicao"] = pos
        return f"texto {'em cima' if pos == 'topo' else 'embaixo' if pos == 'base' else 'no meio'}"
    if acao == "sem_som" and eh_ef:
        el["som"] = None
        return "sem som"
    if acao == "efeito" and eh_ef and valor:
        from .efeitos import QUADRO, TIPOS
        tipo = _tipo_por_nome(valor)
        if tipo not in TIPOS and tipo not in QUADRO:
            raise ValueError(f"não conheço o efeito \"{valor}\"")
        el["tipo"] = tipo
        return f"efeito trocado por {_nome_efeito(tipo)}"
    return None


def _tipo_por_nome(valor: str) -> str:
    v = re.sub(r"\s+", "_", valor.strip().lower())
    from .efeitos import NOMES
    for tipo, nome in NOMES.items():
        curto = re.sub(r"\s+", "_", re.sub(r"\s*\(.*\)", "", nome).strip().lower())
        if v in (tipo, curto) or (len(v) > 3 and curto.startswith(v)):
            return tipo
    return v


def _aprender(pasta: Path, versao: str, aplicados: list) -> None:
    """Histórico dos pedidos no storyboard do projeto (o assistente e a conversa da edição leem daqui)."""
    arq = pasta / "trabalho" / "storyboard_historico.json"
    try:
        hist = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else []
    except ValueError:
        hist = []
    hist.append({"em": time.strftime("%Y-%m-%d %H:%M"), "versao": versao, "pedidos": aplicados})
    arq.write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")
