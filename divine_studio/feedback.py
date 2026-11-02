"""Conversa sobre cada edição: o que o app acha (nota, se vai viralizar, o que melhorar) e o que você acha.

Suas reações viram ajuste concreto nos próximos vídeos (config/preferencias.yaml > feedback):
  mais_efeitos / menos_efeitos  -> intervalo do ritmo automático menor / maior
  mais_sons / menos_sons        -> volume dos efeitos sonoros +3 dB / -3 dB
  mais_rapido / mais_calmo      -> cortes e efeitos mais / menos seguidos
  vai_viralizar / nao_viraliza  -> entra no aprendizado (como gostei / não gostei)
Observações escritas ficam no projeto e em docs/CONHECIMENTO_DIVINE.md (Regras aprendidas), como manda o CLAUDE.md.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

from .config import ROOT, load

REACOES = {
    "vai_viralizar": "🔥 Vai viralizar", "gostei": "♥ Gostei", "media": "😐 Edição média", "nao_gostei": "👎 Não gostei",
    "nao_viraliza": "🧊 Não vai viralizar", "mais_efeitos": "✨ Mais efeitos", "menos_efeitos": "➖ Menos efeitos",
    "mais_sons": "🔊 Mais sons", "menos_sons": "🔇 Menos sons", "mais_rapido": "⚡ Mais rápido", "mais_calmo": "🐢 Mais calmo",
    "texto_maior": "🔠 Texto maior", "menos_texto": "✂ Menos texto",
}
# palavras da observação escrita que viram reação
PALAVRAS = [(r"mais efeito|pouco efeito|sem graça|parad", "mais_efeitos"), (r"menos efeito|muito efeito|exager|polu", "menos_efeitos"),
            (r"mais som|sem som|som baixo|baixo demais|faltou som|pouco som|faltou efeito sonoro", "mais_sons"), (r"menos som|som alto|muito som|barulh|som demais", "menos_sons"),
            (r"lent|arrast|demor|cansativ", "mais_rapido"), (r"rápid|corrid|acelerad|frenétic", "mais_calmo"),
            (r"texto pequen|letra pequen|não dá pra ler", "texto_maior"), (r"muito texto|texto demais", "menos_texto"),
            (r"viraliz|bombar|incrível|perfeit|amei", "vai_viralizar"), (r"não viraliz|fraco|ruim|feio", "nao_viraliza"),
            (r"médi|ok|normal|razoável", "media")]


def _nota(pasta: Path, versao: str) -> dict:
    arq = pasta / "trabalho" / f"nota_{versao}.json"
    try:
        return json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def opiniao_app(pasta: Path, versao: str) -> dict:
    """O que o app pensa desta versão: nota de 0 a 10, veredito e sugestões concretas."""
    n = _nota(pasta, versao)
    if not n:
        return {"tem": False}
    media = float(n.get("media", 0))
    veredito = ("forte candidata a viralizar" if media >= 8 else "boa, com chance de ir bem" if media >= 6.5
                else "média: precisa de ajuste antes de postar")
    sugestoes = [d[0].upper() + d[1:] for d in n.get("dicas") or []][:4]
    dur = n.get("duracao") or 0
    if dur > 45:
        sugestoes.append(f"Tem {dur:.0f} s: teste também um corte de 20 a 30 s (mais gente assiste até o fim)")
    if n.get("efeitos", 0) == 0:
        sugestoes.append("Sem efeitos: um zoom na batida ou uma luz dourada no meio ajudam a segurar a atenção")
    pior = min((n.get("notas") or {}).items(), key=lambda kv: kv[1], default=None)
    if pior and pior[1] < 8:
        sugestoes.append(f"O ponto mais fraco é {pior[0]} ({pior[1]}/10): comece por ele")
    proximo = "Para o próximo: grave a primeira frase já olhando para a câmera e com o assunto na tela, sem apresentação."
    if pior and pior[0] == "áudio":
        proximo = "Para o próximo: grave mais perto do microfone (ou com lapela) e longe do ar-condicionado."
    elif pior and pior[0] == "leitura":
        proximo = "Para o próximo: frases curtas na tela (até 7 palavras) e uma ideia por vez."
    return {"tem": True, "nota": round(media, 1), "notas": n.get("notas") or {}, "veredito": veredito,
            "viraliza": media >= 7.5, "sugestoes": sugestoes[:5], "proximo": proximo}


def _cfg() -> dict:
    return (load("preferencias").get("feedback") or {})


def interpretar(texto: str) -> list:
    t = (texto or "").lower()
    achadas = []
    for padrao, reacao in PALAVRAS:
        if re.search(padrao, t) and reacao not in achadas:
            achadas.append(reacao)
    if "nao_viraliza" in achadas and "vai_viralizar" in achadas:
        achadas.remove("vai_viralizar")
    return achadas


def registrar(pasta: Path, versao: str, reacoes: list, texto: str = "", nota_usuario: int | None = None) -> dict:
    """Guarda a sua opinião na publicação da versão e devolve o que vai mudar nos próximos vídeos."""
    from . import aprendizado
    reacoes = [r for r in reacoes if r in REACOES]
    lidas = interpretar(texto)
    todas = list(dict.fromkeys(reacoes + lidas))
    app = opiniao_app(pasta, versao)
    campos = {"feedback": {"reacoes": todas, "texto": texto.strip() or None, "nota_usuario": nota_usuario,
                           "nota_app": app.get("nota"), "data": _dt.date.today().isoformat()}}
    if {"gostei", "vai_viralizar"} & set(todas):
        campos["gostei"] = True
    if {"nao_gostei", "nao_viraliza"} & set(todas):
        campos["nao_gostei"] = True
    aprendizado.marcar(pasta, versao, **campos)
    _CACHE["v"] = None
    if texto.strip():
        _registrar_regra(pasta, versao, texto.strip())
    concordam = None
    if app.get("tem") and ({"vai_viralizar", "nao_viraliza"} & set(todas)):
        concordam = ("vai_viralizar" in todas) == bool(app.get("viraliza"))
    return {"reacoes": todas, "lidas_do_texto": lidas, "concordam": concordam, "ajustes": ajustes(),
            "explicacao": explicar(ajustes())}


def _registrar_regra(pasta: Path, versao: str, texto: str) -> None:
    arq = ROOT / "docs" / "CONHECIMENTO_DIVINE.md"
    if not arq.exists():
        return
    linha = f"- {_dt.date.today():%d/%m/%Y}: (opinião do Renato sobre {pasta.name} {versao}) {texto.replace(chr(10), ' ')}\n"
    with open(arq, "a", encoding="utf-8") as f:
        f.write(linha)


_CACHE = {"t": 0.0, "v": None}


def ajustes() -> dict:
    """Soma as reações recentes (últimas 15 versões com opinião) em ajustes de edição (cache de 20 s)."""
    import time
    if _CACHE["v"] is not None and time.time() - _CACHE["t"] < 20:
        return _CACHE["v"]
    _CACHE["v"] = _calcular_ajustes()
    _CACHE["t"] = time.time()
    return _CACHE["v"]


def _calcular_ajustes() -> dict:
    from . import aprendizado
    pubs = [p for p in aprendizado.todas_publicacoes() if (p.get("feedback") or {}).get("reacoes")]
    pubs.sort(key=lambda p: (p.get("feedback") or {}).get("data") or "")
    recentes = pubs[-int(_cfg().get("janela", 15)):]
    conta = {}
    for p in recentes:
        for r in p["feedback"]["reacoes"]:
            conta[r] = conta.get(r, 0) + 1
    passo = float(_cfg().get("passo", 0.12))
    efeitos = conta.get("mais_efeitos", 0) - conta.get("menos_efeitos", 0)
    ritmo = conta.get("mais_rapido", 0) - conta.get("mais_calmo", 0)
    sons = conta.get("mais_sons", 0) - conta.get("menos_sons", 0)
    texto = conta.get("texto_maior", 0)
    return {
        "intervalo_efeitos": round(max(0.55, min(1.6, 1 - passo * (efeitos + 0.5 * ritmo))), 2),  # x no intervalo do ritmo
        "ganho_sons_db": round(max(-9.0, min(6.0, 2.0 * sons)), 1),
        "escala_texto": round(max(1.0, min(1.25, 1 + 0.05 * texto)), 2),
        "menos_texto": conta.get("menos_texto", 0) > conta.get("texto_maior", 0),
        "contagem": conta, "opinioes": len(recentes),
    }


def explicar(a: dict) -> list:
    out = []
    if a["intervalo_efeitos"] < 0.97:
        out.append(f"mais efeitos e movimento: um a cada {round(2.9 * a['intervalo_efeitos'], 1)} s em vez de 2,9 s")
    elif a["intervalo_efeitos"] > 1.03:
        out.append(f"menos efeitos: um a cada {round(2.9 * a['intervalo_efeitos'], 1)} s em vez de 2,9 s")
    if a["ganho_sons_db"] > 0.5:
        out.append(f"efeitos sonoros {a['ganho_sons_db']:+.0f} dB mais altos")
    elif a["ganho_sons_db"] < -0.5:
        out.append(f"efeitos sonoros {a['ganho_sons_db']:+.0f} dB mais baixos")
    if a["escala_texto"] > 1.0:
        out.append(f"textos {round((a['escala_texto'] - 1) * 100)}% maiores")
    return out or ["por enquanto, nada muda: suas opiniões estão equilibradas"]


def comentario_ia(pasta: Path, versao: str) -> str:
    """Comentário da IA (Claude) olhando os quadros da versão: o que melhorar nela e no próximo vídeo."""
    from . import assistente
    ok, motivo = assistente.disponivel()
    if not ok:
        raise SystemExit(motivo)
    n = _nota(pasta, versao)
    imagens = []
    if n.get("arquivo") and (pasta / n["arquivo"]).exists():
        imagens = assistente.quadros_do_video(pasta / n["arquivo"], n=6)
    pedido = (f"Olhe a versão {versao} deste vídeo (quadros anexos) e a nota do app ({json.dumps(n.get('notas', {}), ensure_ascii=False)}, "
              f"dicas: {'; '.join(n.get('dicas') or []) or 'nenhuma'}). Responda em 3 partes curtas: 1) vai viralizar? (sim, talvez, "
              "não, e por quê em uma frase); 2) três ajustes concretos para ESTA versão (efeitos, sons, ritmo, texto, corte); "
              "3) uma ideia para o PRÓXIMO vídeo. Seja direto, no padrão de luxo da Divine, sem bloco de sugestão.")
    texto, _, _ = assistente.perguntar([], pedido, assistente.contexto_projeto(pasta), imagens)
    from . import aprendizado
    aprendizado.marcar(pasta, versao, comentario_ia=texto.strip()[:3000])
    return texto.strip()
