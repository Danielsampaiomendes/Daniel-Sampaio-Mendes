"""Laboratório de formatos virais: cada peça postada é um teste; o app mede, compara e decide o próximo.

- Cada versão leva um `formato_viral` (config/formatos_virais.yaml). Ao postar, ele vai para as características.
- Placar por formato e por perfil: testes, vitórias (bateu a mediana do próprio perfil), alcance, envios,
  salvamentos, retenção (tempo médio / duração) e seguidores quando o Instagram ou o TikTok informa.
- Próximos testes por amostragem de Thompson: aproveita o que vence e sempre explora formato pouco testado.
  O Radar (o que está viralizando lá fora agora) entra como evidência extra.
"""
from __future__ import annotations

import datetime as _dt
import random
import statistics

from .config import load


def _cfg() -> dict:
    return load("formatos_virais")


def formatos() -> dict:
    return _cfg().get("formatos") or {}


def nome(chave: str) -> str:
    return (formatos().get(chave) or {}).get("nome", chave or "sem formato")


def classificar(texto: str) -> str | None:
    """Formato mais provável de um texto (legenda, gancho, fala), pelas palavras-sinal. None se nada bate."""
    t = f" {str(texto or '').lower()} "
    melhor, pontos = None, 0
    for chave, f in formatos().items():
        p = sum(1 for s in f.get("sinais") or [] if s.lower() in t)
        if p > pontos:
            melhor, pontos = chave, p
    return melhor


# ---------------------------------------------------------------- medir
def indicadores(pub: dict) -> dict:
    """Taxas de uma publicação (por alcance) e retenção."""
    m = pub.get("metricas") or {}
    alc = m.get("alcance") or m.get("views") or m.get("visualizacoes") or 0
    dur = (pub.get("caracteristicas") or {}).get("duracao")
    out = {"alcance": alc}
    if alc:
        for k, nome_ in (("compartilhamentos", "envios"), ("salvamentos", "salvos"), ("curtidas", "curtidas"),
                         ("comentarios", "comentarios"), ("seguidores", "seguidores")):
            if m.get(k) is not None:
                out[nome_] = round(100 * float(m[k]) / alc, 2)
    if m.get("tempo_medio_ms") and dur:
        out["retencao"] = round(min(1.0, float(m["tempo_medio_ms"]) / 1000 / float(dur)), 2)
    return out


def _postadas(conta: str | None = None) -> list:
    from .aprendizado import todas_publicacoes
    lim = (_dt.date.today() - _dt.timedelta(days=int(_cfg().get("lab", {}).get("janela_dias", 120)))).isoformat()
    out = []
    for p in todas_publicacoes():
        if p.get("status") != "postado" or not p.get("metricas"):
            continue
        if conta and p.get("conta") != conta:
            continue
        if str(p.get("data_postagem") or "9999") < lim:
            continue
        p["formato_viral"] = p.get("formato_viral") or (p.get("caracteristicas") or {}).get("formato_viral")
        out.append(p)
    return out


def _nota(pub: dict, med_alc: float | None) -> float:
    from .aprendizado import pontuar
    s = pontuar(pub, med_alc)
    ind = indicadores(pub)
    s += min(2.0, ind.get("seguidores", 0) * 2)          # prioridade atual: seguidores
    s += max(-1.0, min(1.0, (ind.get("retencao", 0.5) - 0.5) * 3))
    return s


def placar(conta: str | None = None) -> list:
    """Uma linha por formato do catálogo, com testes, vitórias e médias."""
    pubs = _postadas(conta)
    alcs = [indicadores(p)["alcance"] for p in pubs if indicadores(p)["alcance"]]
    med_alc = statistics.median(alcs) if alcs else None
    notas = [_nota(p, med_alc) for p in pubs]
    corte = statistics.median(notas) if notas else 0
    cfg = _cfg().get("lab", {})
    radar = _evidencia_radar()
    linhas = []
    for chave, f in formatos().items():
        dele = [(p, n) for p, n in zip(pubs, notas) if p.get("formato_viral") == chave]
        venceu = sum(1 for _, n in dele if n > corte)
        n = len(dele)
        inds = [indicadores(p) for p, _ in dele]

        def media(k):
            v = [i[k] for i in inds if k in i]
            return round(statistics.mean(v), 2) if v else None
        taxa = venceu / n if n else None
        if n == 0:
            status = "não testado"
        elif n >= int(cfg.get("minimo_para_campeao", 3)) and taxa >= 0.6:
            status = "campeão"
        elif n >= 4 and taxa < float(cfg.get("descartar_abaixo", 0.2)):
            status = "descartar por enquanto"
        elif taxa >= 0.5:
            status = "promissor"
        else:
            status = "em teste"
        linhas.append({"formato": chave, "nome": f.get("nome", chave), "ata": f.get("ata"), "testes": n,
                       "vitorias": venceu, "taxa": round(taxa, 2) if taxa is not None else None, "status": status,
                       "alcance_medio": media("alcance"), "envios": media("envios"), "salvos": media("salvos"),
                       "retencao": media("retencao"), "seguidores": media("seguidores"),
                       "radar": radar.get(chave, 0)})
    ordem = {"campeão": 0, "promissor": 1, "em teste": 2, "não testado": 3, "descartar por enquanto": 4}
    return sorted(linhas, key=lambda x: (ordem[x["status"]], -(x["taxa"] or 0), -x["radar"]))


def _evidencia_radar() -> dict:
    """{formato: quantos itens do Radar (últimos 30 dias) viralizaram nele}."""
    try:
        from . import radar
        return radar.formatos_em_alta(dias=30)
    except Exception:
        return {}


# ---------------------------------------------------------------- decidir
def proximos(n: int = 3, conta: str | None = None, semente: int | None = None, evitar: set | None = None) -> list:
    """Os n formatos para testar agora (Thompson: Beta(1 + vitórias + radar, 1 + derrotas)), com o motivo."""
    cfg = _cfg().get("lab", {})
    rnd = random.Random(semente if semente is not None else _dt.date.today().isocalendar()[1])
    linhas = [x for x in placar(conta) if x["formato"] not in (evitar or set())]
    total_radar = sum(x["radar"] for x in linhas) or 1
    sorteio = []
    for x in linhas:
        f = formatos()[x["formato"]]
        extra = float(cfg.get("peso_radar", 2.0)) * x["radar"] / total_radar * len(linhas) / 4
        a = 1 + x["vitorias"] + extra
        b = 1 + (x["testes"] - x["vitorias"])
        if x["status"] == "descartar por enquanto":
            b += 3
        valor = rnd.betavariate(a, b) * float(f.get("peso", 1.0))
        sorteio.append((valor, x))
    sorteio.sort(key=lambda v: -v[0])
    escolhidos = [x for _, x in sorteio[:n]]
    explorar = int(cfg.get("explorar_minimo", 1))
    pouco = [x for _, x in sorteio if x["testes"] < 2 and x not in escolhidos]
    if n >= 2 and sum(1 for x in escolhidos if x["testes"] < 2) < explorar and pouco:
        escolhidos[-1] = pouco[0]
    return [{**x, "motivo": _motivo(x)} for x in escolhidos]


def _motivo(x: dict) -> str:
    if x["status"] == "campeão":
        return f"campeão: venceu {x['vitorias']} de {x['testes']} testes; replicar a estrutura"
    if x["testes"] == 0 and x["radar"]:
        return f"nunca testado e está em alta lá fora ({x['radar']} vídeos virais no Radar)"
    if x["testes"] == 0:
        return "nunca testado: teste de exploração"
    if x["testes"] < 2:
        return f"só {x['testes']} teste: precisa de mais um para saber"
    if x["status"] == "promissor":
        return f"promissor: {x['vitorias']} de {x['testes']} acima da sua média"
    return f"em teste: {x['vitorias']} de {x['testes']} acima da média"


def plano_semana(conta: str | None = None) -> list:
    """Os testes da semana: um formato por dia de postagem, com gancho modelo e o que medir."""
    n = int(_cfg().get("lab", {}).get("testes_por_semana", 5))
    hoje = _dt.date.today()
    seg = hoje - _dt.timedelta(days=hoje.weekday())
    dias = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
    escolha = proximos(n, conta, semente=seg.isocalendar()[1] * 31 + sum(map(ord, conta or "")))
    passo = 7 / max(1, n)
    out = []
    for i, x in enumerate(escolha):
        f = formatos()[x["formato"]]
        d = seg + _dt.timedelta(days=int(i * passo))
        out.append({"dia": dias[d.weekday()], "data": d.isoformat(), "formato": x["formato"], "nome": x["nome"],
                    "ata": f.get("ata"), "motivo": x["motivo"], "gancho": _gancho(f, i),
                    "edicao": f.get("edicao") or {}, "medir": _o_que_medir(f)})
    return out


DICAS = {"tema": "[tema]", "dor": "[a dor da paciente]", "acao": "[ação]", "obvio": "[o óbvio]",
         "objetivo": "[objetivo]", "pergunta": "[pergunta]", "mito": "[o mito]", "etapa": "[etapa]"}


def _gancho(f: dict, i: int) -> str:
    g = f.get("ganchos") or [""]
    try:
        return g[i % len(g)].format(**DICAS)
    except (KeyError, IndexError):
        return g[i % len(g)]


def _o_que_medir(f: dict) -> str:
    return {"seguir": "seguidores ganhos e envios", "salvar": "salvamentos", "enviar": "compartilhamentos",
            "comentar": "comentários", "agendar": "cliques no link e conversas"}.get(f.get("cta"), "alcance e retenção")


def versoes_para(projeto: dict, n: int = 3, conta: str | None = None) -> list:
    """Formato de cada versão de uma edição nova: o melhor agora + exploração (teste A/B/C de formato)."""
    return [x["formato"] for x in proximos(n, conta)]


def aplicar_em_versoes(projeto: dict, conta: str | None = None) -> dict:
    """Põe um formato diferente em cada versão (e o estilo de edição do formato), sem tirar o que já existe."""
    vs = projeto.get("versoes") or []
    escolha = versoes_para(projeto, len(vs), conta)
    for v, fmt in zip(vs, escolha):
        if v.get("formato_viral"):
            continue
        v["formato_viral"] = fmt
        est = (formatos()[fmt].get("edicao") or {}).get("estilo_edicao")
        if est and not v.get("estilo_edicao"):
            v["estilo_edicao"] = est
    return projeto
