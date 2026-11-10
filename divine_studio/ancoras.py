"""Âncoras: dublagens e efeitos presos às PALAVRAS da fala, não ao segundo da base.

É o mesmo problema da legenda de cinema e do marcador de texto num editor: quando um trecho anterior some (✂ Tirar
esta frase, corte limpo, transcrição refeita), o segundo 20,0 da base passa a ser outra palavra. Um item preso ao
segundo cai no lugar errado; um item preso às palavras acompanha a fala.

Cada dublagem e cada efeito do projeto.yaml ganha `ancora` ao ser gravado (painel.salvar_dados e /api/dublagem):
  t        o segundo em que foi ancorado (se você arrastar o item, `inicio` muda e a âncora é refeita)
  palavras as palavras da fala naquele trecho (normalizadas), `antes` as duas anteriores (para desempatar)
  desloc   quanto o item começa depois da 1ª palavra; `cauda` quanto a dublagem termina depois da última
A cada prévia ou final, `reposicionar` procura essas palavras na fala nova e acerta `inicio` e `fim`. Se a frase saiu
do vídeo, o item fica de fora DESTA edição (nada é apagado do projeto.yaml) e vira um "!" para você decidir.
"""
from __future__ import annotations

from .corte import normalizar

N_PONTO = 3          # palavras guardadas para um efeito (um instante)
TOL_MOVIDO = 0.05    # o item foi arrastado se `inicio` mudou mais que isso desde a âncora


def _tokens(fala: list) -> list:
    return [(normalizar(str(w.get("texto", ""))), w) for w in fala or [] if not w.get("dub")]


def ancorar(fala: list, inicio: float, fim: float | None = None) -> dict | None:
    """Âncora de um item que começa em `inicio` (e termina em `fim`, numa dublagem de trecho)."""
    tk = [(n, w) for n, w in _tokens(fala) if n]
    if not tk:
        return None
    inicio = float(inicio)
    if fim is not None:
        idx = [k for k, (_, w) in enumerate(tk) if inicio - 0.05 <= float(w["inicio"]) < float(fim)]
    else:
        k0 = next((k for k, (_, w) in enumerate(tk) if float(w["fim"]) > inicio), max(0, len(tk) - N_PONTO))
        idx = list(range(k0, min(len(tk), k0 + N_PONTO)))
    if not idx:
        return None
    pri, ult = tk[idx[0]][1], tk[idx[-1]][1]
    out = {"t": round(inicio, 3), "palavras": [tk[k][0] for k in idx],
           "antes": [tk[k][0] for k in range(max(0, idx[0] - 2), idx[0])],
           "desloc": round(inicio - float(pri["inicio"]), 3)}
    if fim is not None:
        out["cauda"] = round(float(fim) - float(ult["fim"]), 3)
    return out


def ancorar_itens(itens: list, fala: list, com_fim: bool = False) -> list:
    """Põe (ou refaz, se o item foi arrastado) a âncora de cada item. Sem fala transcrita, deixa como está."""
    if not fala:
        return itens
    out = []
    for it in itens or []:
        if not isinstance(it, dict) or it.get("inicio") is None:
            out.append(it)
            continue
        a = it.get("ancora")
        if not a or abs(float(it["inicio"]) - float(a.get("t", -99))) > TOL_MOVIDO:
            nova = ancorar(fala, float(it["inicio"]), it.get("fim") if com_fim else None)
            it = {**it, "ancora": nova} if nova else {k: v for k, v in it.items() if k != "ancora"}
        out.append(it)
    return out


def _achar(seq: list, alvo: list) -> list:
    n = len(alvo)
    return [k for k in range(len(seq) - n + 1) if n and seq[k:k + n] == alvo]


def localizar(fala_nova: list, a: dict) -> tuple | None:
    """(início, fim_da_última_palavra) das palavras da âncora na fala nova, ou None se a frase saiu do vídeo.
    Tenta a sequência exata; depois sem as palavras curtas (muleta que o corte limpo tirou do meio: "hum", "né")."""
    tk = [(n, w) for n, w in _tokens(fala_nova) if n]
    for filtro in (lambda n: True, lambda n: len(n) >= 3):
        sub = [(n, w) for n, w in tk if filtro(n)]
        seq = [n for n, _ in sub]
        alvo = [n for n in a.get("palavras") or [] if filtro(n)]
        achados = _achar(seq, alvo)
        if not achados:
            continue
        antes = [n for n in a.get("antes") or [] if filtro(n)]
        com_contexto = [k for k in achados if antes and seq[max(0, k - len(antes)):k] == antes]
        cand = com_contexto or achados
        t_old = float(a.get("t", 0))
        k = min(cand, key=lambda k: abs(float(sub[k][1]["inicio"]) - t_old))
        return float(sub[k][1]["inicio"]), float(sub[k + len(alvo) - 1][1]["fim"])
    return None


def reposicionar(itens: list, fala_nova: list, com_fim: bool = False) -> tuple:
    """(itens no lugar certo da fala nova, itens cuja frase saiu do vídeo). Item sem âncora fica onde está."""
    ok, perdidos = [], []
    for it in itens or []:
        a = it.get("ancora") if isinstance(it, dict) else None
        if not a:
            ok.append(it)
            continue
        achou = localizar(fala_nova, a)
        if achou is None:
            perdidos.append(it)
            continue
        ini = round(max(0.0, achou[0] + float(a.get("desloc", 0))), 3)
        novo = {**it, "inicio": ini, "ancora": {**a, "t": ini}}
        if com_fim and it.get("fim") is not None:
            novo["fim"] = round(max(ini + 0.1, achou[1] + float(a.get("cauda", 0))), 3)
        ok.append(novo)
    return ok, perdidos


def chave(it: dict) -> str:
    """Identifica o mesmo item no projeto.yaml depois de reposicionado (as palavras da âncora não mudam)."""
    a = it.get("ancora") or {}
    return f"{it.get('arquivo') or it.get('tipo')}|{' '.join(a.get('palavras') or [])}|{' '.join(a.get('antes') or [])}"
