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
        "formato_viral": v.get("formato_viral") or projeto.get("formato_viral"),
        "estilo_edicao": v.get("estilo_edicao") or projeto.get("estilo_edicao"),
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
    ja_postado = pub.get("status") == "postado"
    for k, v in campos.items():
        if v is None:
            pub.pop(k, None)
        elif k == "metricas":
            pub["metricas"] = {**(pub.get("metricas") or {}), **v}
            if v.get("idade_h") is not None:          # histórico por idade do post (últimos 12 retratos)
                hist = list(pub.get("historico_metricas") or []) + [dict(v)]
                pub["historico_metricas"] = _podar_historico(hist)
        else:
            pub[k] = v
    if campos.get("status") == "postado" and not pub.get("data_postagem"):
        pub["data_postagem"] = _dt.date.today().isoformat()
    if campos.get("status") == "postado" and not ja_postado:
        _guardar_previsao_postada(Path(pasta), versao, pub)
    if campos.get("gostei") or campos.get("status") in ("postado", "aprovado"):
        pub["caracteristicas"] = caracteristicas({**d, "_pasta": pasta}, versao)
    _gravar(pasta, d)
    return pub


def _guardar_previsao_postada(pasta: Path, versao: str, pub: dict) -> None:
    """Congela a previsão da FINAL no momento em que a peça é postada (trabalho/previsao_postada_<versão>.json).

    A calibração (previsao.fator_calibracao) compara o tempo médio real do Instagram com a entrada DESTE arquivo.
    Sem isso, uma prévia nova da mesma versão (buscando a versão superior) trocaria a entrada, e o tempo real do que
    foi postado seria comparado com um vídeo que nunca foi ao ar."""
    import shutil
    trab = pasta / "trabalho"
    origem = trab / f"previsao_{versao}_final.json"
    if not origem.exists():
        pub["previsao_postada"] = None
        pub["previsao_postada_falta"] = "sem previsão da final (exporte a final pelo app para calibrar com esta peça)"
        return
    destino = trab / f"previsao_postada_{versao}.json"
    shutil.copy2(origem, destino)
    pub["previsao_postada"] = f"trabalho/{destino.name}"
    pub.pop("previsao_postada_falta", None)


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
        from .instagram import conta_do_projeto
        conta_proj = conta_do_projeto(d)
        for pub in d.get("publicacoes") or []:
            out.append({"projeto": nome, "titulo": d.get("titulo", nome), "tipo": d.get("tipo", "video"),
                        "conta": pub.get("conta") or conta_proj,
                        "formato": d.get("formato", "reels"), "template": d.get("template", "divine"),
                        "tags": d.get("tags") or [], **pub})
    return out


# ---------------------------------------------------------------- aprendizado

def retencao(pub: dict, modo: str = "bruta") -> float | None:
    """Quanto a peça segurou. Como num estudo clínico, o desfecho é "observado / esperado":

      modo "relativa": tempo médio real / tempo médio que o modelo dava para ESTE vídeo (a previsão congelada ao
                       postar). Assim um vídeo curto não ganha só por ser curto (10 s com 6 s de média é 60% da
                       duração, mas é o esperado), e um longo que segura bem não perde por ser longo;
      modo "bruta":    tempo médio / duração (peças antigas, sem a previsão congelada).
    None quando não há o número ou quando é loop (acima de 85% da duração, previsao.em_loop): o Instagram contou as
    repetições e isso não é retenção. É a mesma regra que tira o loop da calibração (antes, o loop ganhava a nota
    máxima aqui e virava favorito)."""
    from . import previsao
    m = pub.get("metricas") or {}
    ms = m.get("tempo_medio_ms") or (float(m["tempo_medio_s"]) * 1000 if m.get("tempo_medio_s") else None)
    dur = (pub.get("caracteristicas") or {}).get("duracao")
    if not ms or not dur:
        return None
    real = float(ms) / 1000
    if previsao.em_loop(real, float(dur)):
        return None
    if modo == "bruta":
        return real / float(dur)
    entrada = (previsao._previsao_do_postado(PROJETOS / pub["projeto"], pub).get("entrada") or {}) \
        if pub.get("projeto") else {}
    esperado = previsao.tempo_medio_esperado(entrada) if entrada.get("curva") else 0.0
    return real / esperado if esperado > 0 else None


def alcance_comparavel(pub: dict) -> float | None:
    """Alcance na mesma idade para todas as peças (um Reels de 2 dias não se compara com um de 30).

    Com retratos por idade (historico_metricas, da sincronização), usa o retrato mais perto de `alcance_idade_h`
    (7 dias) entre os que já passaram de `alcance_idade_min_h` (3 dias); peça mais nova que isso ainda não entra na
    comparação de alcance (o engajamento por alcance continua contando). Sem retratos (número digitado ou peça
    antiga): o alcance que há."""
    m = pub.get("metricas") or {}
    atual = m.get("alcance") or m.get("views") or m.get("visualizacoes")
    hist = [h for h in pub.get("historico_metricas") or []
            if h.get("idade_h") is not None and (h.get("alcance") or h.get("views"))]
    if not hist:
        return atual
    cfg = _cfg()
    alvo, minimo = float(cfg.get("alcance_idade_h", 168)), float(cfg.get("alcance_idade_min_h", 72))
    maduros = [h for h in hist if float(h["idade_h"]) >= minimo]
    if not maduros:
        return None
    h = min(maduros, key=lambda h: abs(float(h["idade_h"]) - alvo))
    return h.get("alcance") or h.get("views")


def _podar_historico(hist: list, marcos=(24, 72, 168), ultimos: int = 6) -> list:
    """Guarda o retrato mais perto de cada idade-marco (24 h, 3 dias, 7 dias) e os últimos: sincronizando todo dia,
    os 12 mais recentes de uma peça de 30 dias já não teriam o retrato dos 7 dias."""
    com_idade = [h for h in hist if h.get("idade_h") is not None]
    guardar = {id(min(com_idade, key=lambda h: abs(float(h["idade_h"]) - mk))) for mk in marcos if com_idade}
    guardar |= {id(h) for h in hist[-ultimos:]}
    return [h for h in hist if id(h) in guardar]


def pontuar(pub: dict, mediana_alcance: float | None = None, mediana_retencao: float | None = None,
            modo_retencao: str = "bruta") -> float:
    """Sinal de quanto a versão funcionou: gostei +1, postado +2, métricas até +4 (relativas ao seu normal) e a
    retenção (o quanto assistem, comparado com a mediana das suas peças) de -1,5 a +2. Uma queda da linha de
    retenção logo na abertura ("linha cai em") tira ponto: é o hook que não segurou."""
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
        s += min(2.0, envio / 2)                               # engajamento por alcance (taxa: não depende da idade)
        comparavel = alcance_comparavel(pub)
        if mediana_alcance and comparavel:                     # alcance na mesma idade (7 dias) que as outras
            s += max(-1.0, min(2.0, math.log2(max(1, comparavel) / mediana_alcance)))   # acima da sua média
    cfg = _cfg()
    ret = retencao(pub, modo_retencao)
    if ret and mediana_retencao:
        s += max(-1.5, min(2.0, float(cfg.get("peso_retencao", 2.0)) * math.log2(max(0.05, ret) / mediana_retencao)))
    if m.get("queda_s") is not None and float(m["queda_s"]) <= float(cfg.get("queda_na_abertura_s", 3)):
        s -= float(cfg.get("penalidade_queda_abertura", 0.75))
    if pub.get("nao_gostei"):
        s -= 1.5
    return s


def preferencias(conta: str | None = None) -> dict:
    """{campo: {valor: (média, n)}} para cada característica, com suavização (poucos dados pesam pouco).
    Com 'conta', aprende só com o perfil (@dvmedicalspa e @drdanielmendess têm públicos diferentes); com pouca
    coisa do perfil (menos de 3 peças), usa tudo."""
    pubs = [p for p in todas_publicacoes() if p.get("caracteristicas")]
    if conta:
        do_perfil = [p for p in pubs if p.get("conta") == conta]
        if len(do_perfil) >= 3:
            pubs = do_perfil
    alcances = [a for a in (alcance_comparavel(p) for p in pubs) if a]
    med = statistics.median(alcances) if alcances else None
    # retenção "observado / esperado" quando 2 peças ou mais têm a previsão congelada; senão, a bruta. Nunca as duas
    # misturadas na mesma mediana (escalas diferentes)
    rel = [r for r in (retencao(p, "relativa") for p in pubs) if r]
    modo = "relativa" if len(rel) >= 2 else "bruta"
    rets = rel if modo == "relativa" else [r for r in (retencao(p) for p in pubs) if r]
    med_ret = statistics.median(rets) if len(rets) >= 2 else None     # com uma peça só, não há com o que comparar
    soma, cont = defaultdict(lambda: defaultdict(float)), defaultdict(lambda: defaultdict(int))
    for p in pubs:
        s = pontuar(p, med, med_ret, modo)
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
        pior = min(tab.items(), key=lambda kv: kv[1][0])
        if pior[1][0] < 0 and pior[0] != top[0]:
            out.append(f"Evitar {nome}: {pior[0]} (nota {pior[1][0]}, {pior[1][1]} peça(s))")
    return out


def versao_ia(projeto: dict, versoes: list, fontes_escolhidas: list) -> dict | None:
    """A versão que o app acredita ser a melhor: hook, fontes e efeitos com melhor histórico (e o porquê)."""
    if not _cfg().get("versao_ia", True) or projeto.get("template") == "tv" or projeto.get("tipo") == "carrossel":
        return None
    from .instagram import conta_do_projeto
    prefs = preferencias(conta_do_projeto(projeto))
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
    if projeto.get("roteiro_automatico"):
        # edição pela fala: a aposta usa a frase mais forte do próprio vídeo (V1) com o acabamento que mais funciona
        falado = next((v.get("hook") for v in versoes if isinstance(v.get("hook"), list) and v.get("hook")), None)
        if falado:
            porque.append("hook: a frase mais forte da sua própria fala")
            return {"nome": "IA", "fontes": fonte, "porque": porque, "hook": [dict(b) for b in falado]}
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
