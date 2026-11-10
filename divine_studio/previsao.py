"""Antever o público: de 100 pessoas, quantas ficam até cada segundo, onde saem e quem segura.

É o mesmo cálculo das tábuas de sobrevivência (seguro de vida, estudos clínicos): a cada meio segundo cada pessoa tem
uma chance de sair (o "risco"). O risco sobe quando a atenção prevista cai (atencao.py: nada novo na tela, imagem
parada, silêncio) e nos 3 primeiros segundos, quando o público decide se fica. Três tipos de pessoa
(config/previsao.yaml > personas) têm paciências diferentes; o resultado é a mistura deles.

Sem sorteio: o mesmo vídeo dá sempre a mesma previsão (dá para testar e comparar versões).

Calibração (o que é e o que não é): o Instagram entrega, por Reels, só o TEMPO MÉDIO assistido
(ig_reels_avg_watch_time), não a curva segundo a segundo. Então só o ritmo de saída é calibrado: para cada peça postada,
o app procura o multiplicador do risco que faz o modelo, com a MESMA entrada daquele vídeo (guardada em
previsao_postada_<versão>.json > entrada, congelado no momento em que a peça é postada), dar exatamente o tempo médio
real. A mediana desses multiplicadores, por perfil,
vale para as próximas previsões. Como cada peça é reproduzida de novo do zero com a entrada bruta, a calibração não se
calibra em cima dela mesma e converge: se as suas peças ficam em 0,6 da previsão, a próxima já sai perto de 0,6.
"Passam dos 3 s", "chegam à metade" e a divisão por tipo de público continuam estimativas do modelo (nenhuma métrica
da Meta confere esses números): por isso aparecem arredondados ("cerca de") e com esse aviso.
"""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

from .config import load


def _cfg() -> dict:
    try:
        return load("previsao")
    except OSError:
        return {}


def _curva_sobrevivencia(atencao: list, passo: float, paciencia: float, m: dict, inicio_fraco: bool,
                         escala: float) -> list:
    base = float(m.get("risco_base_por_s", 0.07))
    sens = float(m.get("sensibilidade", 2.4))
    dec = float(m.get("decisao_3s", 0.22)) * (1 + float(m.get("inicio_fraco_extra", 0.5)) * inicio_fraco)
    s, out = 1.0, [1.0]
    for k, a in enumerate(atencao):
        t = k * passo
        taxa = base * math.exp(sens * (0.5 - float(a)))
        if t < 3.0:
            taxa += dec * (1.0 - float(a))
        taxa = taxa / max(0.1, paciencia) * escala
        s *= math.exp(-taxa * passo)
        out.append(s)
    return out


def _mix(curva: list, passo: float, fraco: bool, escala: float, cfg: dict) -> tuple:
    m = cfg.get("modelo") or {}
    personas = cfg.get("personas") or [{"id": "todos", "nome": "Público", "peso": 1.0, "paciencia": 1.0}]
    peso_total = sum(float(p.get("peso", 1)) for p in personas) or 1.0
    curvas = [(p, _curva_sobrevivencia(curva, passo, float(p.get("paciencia", 1)), m, fraco, escala)) for p in personas]
    mix = [sum(float(p.get("peso", 1)) * c[k] for p, c in curvas) / peso_total for k in range(len(curva) + 1)]
    return curvas, mix


def _tempo_medio(mix: list, passo: float, dur: float) -> float:
    """Área sob a curva; quem chega ao fim do corpo vê o fechamento inteiro."""
    corpo = (len(mix) - 1) * passo
    return sum((mix[k] + mix[k + 1]) / 2 * passo for k in range(len(mix) - 1)) + mix[-1] * max(0.0, dur - corpo)


def tempo_medio_esperado(entrada: dict, cfg: dict | None = None) -> float:
    """O tempo médio que o modelo puro (sem calibração) dá para este vídeo: o "esperado" do aprendizado."""
    cfg = cfg if cfg is not None else _cfg()
    curva, passo = list(entrada.get("curva") or []), float(entrada.get("passo", 0.5))
    dur = float(entrada.get("duracao_s") or len(curva) * passo)
    return _tempo_medio(_mix(curva, passo, bool(entrada.get("inicio_fraco")), 1.0, cfg)[1], passo, dur) if curva else 0.0


def em_loop(real_s: float, dur: float, cfg: dict | None = None) -> bool:
    """Tempo médio acima de `max_fracao_duracao` da duração: o Instagram contou repetições, não é retenção."""
    cfg = cfg if cfg is not None else _cfg()
    return dur > 0 and real_s >= float((cfg.get("calibracao") or {}).get("max_fracao_duracao", 0.85)) * dur


def escala_que_reproduz(entrada: dict, real_s: float, cfg: dict | None = None) -> float | None:
    """O multiplicador do risco que faz o modelo dar o tempo médio real deste vídeo (bisseção: o tempo médio sempre
    cai quando o risco sobe). Busca em `calibracao.busca` (0,02 a 5).
    Dois casos diferentes, que não se misturam:
      - None: o tempo médio passa de `max_fracao_duracao` (85%) da duração. Só um Reels que roda em LOOP chega lá (o
        Instagram conta as repetições) e um modelo de "ver uma vez" não reproduz isso: fica fora da calibração;
      - o limite de baixo da busca: a peça segurou MAIS do que o modelo consegue dar mesmo com o risco mínimo (um
        vídeo de 60 s com 37 s de média). É a sua melhor peça, não um loop: entra na conta e puxa a previsão para
        cima (antes ela era tratada como loop e a calibração só aprendia com as peças mais fracas)."""
    cfg = cfg if cfg is not None else _cfg()
    curva, passo = list(entrada.get("curva") or []), float(entrada.get("passo", 0.5))
    fraco, dur = bool(entrada.get("inicio_fraco")), float(entrada.get("duracao_s") or len(curva) * passo)
    tm = lambda e: _tempo_medio(_mix(curva, passo, fraco, e, cfg)[1], passo, dur)
    c = cfg.get("calibracao") or {}
    lo, hi = (float(x) for x in (c.get("busca") or [0.02, 5.0])[:2])
    if dur <= 0 or em_loop(real_s, dur, cfg):
        return None
    if real_s >= tm(lo):
        return lo
    if real_s <= tm(hi):
        return hi
    for _ in range(40):
        meio = math.sqrt(lo * hi)
        if tm(meio) > real_s:
            lo = meio
        else:
            hi = meio
    return math.sqrt(lo * hi)


def fator_calibracao(conta: str | None = None) -> dict:
    """Multiplicador do risco tirado das peças postadas com tempo médio real (mediana, por perfil quando dá)."""
    from . import aprendizado
    cfg = _cfg()
    c = cfg.get("calibracao") or {}
    minimo = int(c.get("min_pecas", 3))
    lo, hi = (c.get("limites") or [0.4, 2.5])[:2]
    escalas, do_perfil, pulados, loops, acima = [], [], [], [], []
    piso = float((c.get("busca") or [0.02])[0])
    for pub in aprendizado.todas_publicacoes():
        mt = pub.get("metricas") or {}
        ms = mt.get("tempo_medio_ms") or (float(mt["tempo_medio_s"]) * 1000 if mt.get("tempo_medio_s") else None)
        if pub.get("status") != "postado" or not ms:
            continue
        prev = _previsao_do_postado(aprendizado.PROJETOS / pub["projeto"], pub)
        if not prev:
            pulados.append(f"{pub['projeto']} {pub['versao']}")   # nunca calibra com uma prévia que não foi ao ar
            continue
        if not (prev.get("entrada") or {}).get("curva"):
            continue                                  # previsão antiga, sem a entrada guardada: não dá para refazer
        e = escala_que_reproduz(prev["entrada"], float(ms) / 1000, cfg)
        if e is None:                                 # loop: o tempo médio conta repetições, o modelo não reproduz
            loops.append(f"{pub['projeto']} {pub['versao']}")
            continue
        if e <= piso:                                 # segurou mais do que o modelo dá: entra, e a tela diz
            acima.append(f"{pub['projeto']} {pub['versao']}")
        escalas.append(e)
        if conta and pub.get("conta") == conta:
            do_perfil.append(e)
    usar = do_perfil if len(do_perfil) >= minimo else escalas
    if len(usar) < minimo:
        return {"escala": 1.0, "pecas": len(usar), "calibrado": False, "pulados": pulados, "loops": loops,
                "acima_do_modelo": acima}
    return {"escala": round(min(hi, max(lo, statistics.median(usar))), 3), "pecas": len(usar), "calibrado": True,
            "pulados": pulados, "loops": loops, "acima_do_modelo": acima}


def _previsao_do_postado(pasta: Path, pub: dict) -> dict:
    """A previsão do vídeo que FOI ao ar: a congelada ao postar (aprendizado._guardar_previsao_postada) ou, em peça
    antiga sem ela, a da final (as prévias nunca escrevem esse arquivo). Nunca previsao_<versão>.json, que toda prévia
    nova da versão sobrescreve."""
    nomes = [pub["previsao_postada"]] if pub.get("previsao_postada") else []
    nomes.append(f"trabalho/previsao_{pub['versao']}_final.json")
    for rel in nomes:
        try:
            return json.loads((Path(pasta) / rel).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return {}


def prever(atencao: dict, duracao_total: float | None = None, conta: str | None = None,
           calibracao: dict | None = None) -> dict:
    """Previsão a partir da curva de atenção (atencao.analisar). duracao_total inclui o fechamento."""
    curva = list((atencao or {}).get("curva") or [])
    passo = float((atencao or {}).get("passo", 0.5))
    if not curva:
        return {"tem": False}
    cfg = _cfg()
    cal = calibracao if calibracao is not None else fator_calibracao(conta)
    fraco = bool(atencao.get("inicio_fraco"))
    dur_corpo = len(curva) * passo
    dur = max(dur_corpo, float(duracao_total or dur_corpo))
    escala = float(cal.get("escala", 1.0))
    _, mix_bruto = _mix(curva, passo, fraco, 1.0, cfg)
    bruto = _tempo_medio(mix_bruto, passo, dur)
    curvas, mix = _mix(curva, passo, fraco, escala, cfg)
    em = lambda s: mix[min(len(mix) - 1, int(round(s / passo)))]
    quedas = []
    for k in range(len(mix) - 1):
        j = min(len(mix) - 1, k + int(1.5 / passo))
        quedas.append((mix[k] - mix[j], k * passo))
    saidas, usados = [], []
    for d, t in sorted(quedas, reverse=True):
        if d <= 0.01 or any(abs(t - u) < 2.0 for u in usados):
            continue
        usados.append(t)
        zona = next((z for z in atencao.get("zonas") or [] if z["ini"] - 0.5 <= t <= z["fim"]), None)
        motivo = "decisão dos 3 primeiros segundos" if t < 3 else (zona["causa"] if zona else "atenção mais baixa")
        saidas.append({"t": round(t, 1), "saem": round(d * 100), "motivo": motivo})
        if len(saidas) == 3:
            break
    return {
        "tem": True, "passo": passo, "curva": [round(x * 100, 1) for x in mix],
        # estimativas do modelo: arredondadas de 5 em 5 para não parecer medida exata
        "de_100": {"passam_3s": _cinco(em(3.0)), "metade": _cinco(em(dur_corpo / 2)), "fim": _cinco(mix[-1])},
        "tempo_medio_s": round(_tempo_medio(mix, passo, dur), 1), "tempo_medio_s_bruto": round(bruto, 2),
        "duracao_s": round(dur, 1), "saidas": sorted(saidas, key=lambda s: s["t"]),
        "personas": [{"nome": p["nome"], "fim": _cinco(c[-1])} for p, c in curvas],
        "calibrado": bool(cal.get("calibrado")), "escala": escala, "pecas_calibracao": cal.get("pecas", 0),
        "pecas_em_loop": len(cal.get("loops") or []), "pecas_acima_do_modelo": len(cal.get("acima_do_modelo") or []),
        "calibrado_so": "tempo médio",            # o resto (3 s, metade, por público) é estimativa do modelo
        # a entrada bruta deste vídeo: a calibração refaz a conta com ela quando a peça tiver o tempo médio real
        "entrada": {"curva": [round(float(x), 3) for x in curva], "passo": passo, "inicio_fraco": fraco,
                    "duracao_s": round(dur, 2)},
    }


def _cinco(x: float) -> int:
    return int(5 * round(x * 100 / 5))


def frase(prev: dict) -> str:
    """Resumo de uma linha para a tela e para o relatório."""
    if not prev.get("tem"):
        return ""
    d = prev["de_100"]
    txt = (f"De 100 pessoas, cerca de {d['passam_3s']} passam dos 3 s, {d['metade']} chegam à metade e {d['fim']} veem "
           f"até o fim (em média {prev['tempo_medio_s']:.0f} s de {prev['duracao_s']:.0f} s).")
    if prev.get("calibrado"):
        loop, acima = prev.get("pecas_em_loop") or 0, prev.get("pecas_acima_do_modelo") or 0
        notas = ([f"{acima} peça(s) seguraram mais do que o modelo prevê e puxam a estimativa para cima"] if acima else []) \
            + ([f"{loop} peça(s) com tempo médio acima de 85% da duração (rodaram em loop) ficaram de fora"] if loop else [])
        fora = f" ({'; '.join(notas)})" if notas else ""
        return txt + (f" O tempo médio está ajustado pelo tempo real de {prev.get('pecas_calibracao', 0)} peças suas"
                      f"{fora}; o resto é estimativa, serve para comparar as versões.")
    return txt + " Estimativa do modelo, ainda sem o seu Instagram: serve para comparar as versões, não como número exato."


def salvar(trabalho: Path, versao: str, dados: dict, final: bool = False) -> None:
    """previsao_<versão>.json (a última prévia ou final, para a tela) e, na final, previsao_<versão>_final.json
    (o que vai ao ar; congelado de novo ao postar)."""
    texto = json.dumps(dados, ensure_ascii=False)
    (Path(trabalho) / f"previsao_{versao}.json").write_text(texto, encoding="utf-8")
    if final:
        (Path(trabalho) / f"previsao_{versao}_final.json").write_text(texto, encoding="utf-8")


def ler(pasta: Path, versao: str) -> dict:
    try:
        return json.loads((Path(pasta) / "trabalho" / f"previsao_{versao}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
