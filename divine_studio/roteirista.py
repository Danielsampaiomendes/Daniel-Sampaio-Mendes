"""Roteirista: a edição automática ENTENDE o vídeo pela fala (como o Claude faz no chat).

Com a transcrição do que foi falado, o app escreve as 3 versões em cima do próprio conteúdo:
  - ganchos tirados da fala (a frase mais forte vira o hook, sem inventar promessa)
  - mensagens na tela sincronizadas com o momento em que a frase é dita (na_fala)
  - selo, chamada, fechamento e legenda do post sobre o assunto do vídeo
  - efeitos só onde fazem sentido (frase de impacto, número, nome da tecnologia), também presos à fala
Com a IA ligada (ANTHROPIC_API_KEY), quem escreve é o Claude. Sem ela, o app usa regras sobre a própria fala.
Tudo passa pelo revisor de compliance (CFM 2.336/2023, Anvisa RDC 96/2008).
"""
from __future__ import annotations

import json
import re

from .config import load


def texto_da_fala(palavras: list) -> str:
    return " ".join(str(w.get("texto", "")).strip() for w in palavras).strip()


def frases(palavras: list) -> list:
    """Frases da fala (pela pontuação e pelas pausas), com o início em segundos no bruto."""
    out, atual, ini, i0 = [], [], None, 0
    for i, w in enumerate(palavras):
        t = str(w.get("texto", "")).strip()
        if not t:
            continue
        if ini is None:
            ini, i0 = float(w.get("inicio", 0)), i
        atual.append(t)
        prox = palavras[i + 1] if i + 1 < len(palavras) else None
        pausa = prox is not None and float(prox.get("inicio", 0)) - float(w.get("fim", 0)) > 0.6
        if re.search(r"[.!?…]$", t) or pausa or prox is None:
            # fim e índices das palavras (i0 a i1) servem aos pontos de atenção da linha do tempo (alertas.py)
            out.append({"texto": " ".join(atual), "inicio": ini, "fim": float(w.get("fim", ini)), "i0": i0, "i1": i})
            atual, ini = [], None
    return out


def _ok(frase: str) -> bool:
    from .compliance import revisar
    return not [a for a in revisar({"legenda": "", "conteudo_medico": False}, [frase]) if a.nivel == "erro"]


def _limpar(f: str) -> str:
    f = re.sub(r"^\s*(então|entao|né|tipo|e aí|eai|bom|olha)[, ]+", "", f.strip(), flags=re.I)
    return f[:1].upper() + f[1:] if f else f


def _destacar(f: str) -> str:
    from .auto import _destacar as d
    return d(f)


def ganchos_da_fala(palavras: list, n: int = 3) -> list:
    """As frases que mais prendem (pergunta, 'você', número, contraste, alerta) viram os hooks."""
    cand = []
    for k, fr in enumerate(frases(palavras)):
        f = _limpar(fr["texto"])
        nw = len(f.split())
        if not 4 <= nw <= 13 or not _ok(f):
            continue
        nf = f.lower()
        p = 2.0 - abs(nw - 8) * 0.15
        p += 2.0 * f.rstrip().endswith("?")
        p += 1.5 * bool(re.search(r"\bvocê|\bvoce|\bseu\b|\bsua\b", nf))
        p += 1.0 * bool(re.search(r"\d", nf))
        p += 1.2 * bool(re.search(r"\b(nunca|pare|erro|errado|segredo|ninguém|ninguem|verdade|mito|cuidado|não é)\b", nf))
        p += 1.0 * (k == 0)                                       # quem abre o vídeo já costuma ser o gancho
        if re.search(r"\b(agende|agenda|marque|segue|siga|link|direct|whatsapp|salva|salve|comenta)\b", nf):
            continue                                              # frase de pedido (CTA) fica para o final, nunca é hook
        from .sugestoes import ABERTURA_FRACA
        if ABERTURA_FRACA.search(f) or re.search(r"\b(eu sou|meu nome|hoje eu vou|vou te explicar)\b", nf):
            continue                                              # apresentação ("eu sou o Dr. ...") não prende ninguém
        cand.append((p, k, f))
    escolhidos = [f for _, _, f in sorted(cand, reverse=True)[:n]]
    return [[{"titulo": _destacar(f)}] for f in escolhidos]


def _assunto(palavras: list, titulo: str) -> str:
    from .auto import tema
    chave, rot = tema(titulo + " " + texto_da_fala(palavras)[:400])
    return chave


def _sem_marca(t: str) -> str:
    return re.sub(r"[^a-z0-9à-ú ]", "", re.sub(r"[*/]", " ", str(t)).lower()).split().__str__()


def planejar_regras(projeto: dict, palavras: list) -> dict:
    """Sem IA: hooks, mensagens e efeitos tirados da própria fala."""
    from .auto import mensagens_da_fala
    chave = _assunto(palavras, projeto.get("titulo", ""))
    msgs = mensagens_da_fala(palavras, chave, 3)
    na_tela = {_sem_marca(m["titulo"]) for m in msgs}
    # o hook não repete uma mensagem que já vai aparecer no meio; se faltar frase boa, a versão fica com o hook do banco
    ganchos = [g for g in ganchos_da_fala(palavras, 8) if _sem_marca(g[0]["titulo"]) not in na_tela][:3]
    # poucas frases fortes: a versão usa uma mensagem da fala como hook (e a edição tira essa mensagem do meio dela),
    # melhor do que um hook genérico do banco que não tem nada a ver com o vídeo
    for m in msgs:
        if len(ganchos) >= 3:
            break
        ganchos.append([{"titulo": m["titulo"]}])
    efeitos = []
    for fr in frases(palavras):                                    # números e nomes de tecnologia ganham destaque
        f = fr["texto"]
        if re.search(r"\b\d+[\d.,]*\s*(%|por cento|sessões|sessoes|minutos|dias|semanas|anos)?", f) and len(efeitos) < 2:
            efeitos.append({"tipo": "zoom_batida", "na_fala": " ".join(f.split()[:4]), "motivo": "número na fala"})
    return {"fonte": "regras", "tema": chave, "ganchos": ganchos, "mensagens": msgs, "efeitos": efeitos}


def planejar_ia(projeto: dict, palavras: list) -> dict | None:
    """Com a IA: o Claude lê a transcrição e escreve a edição (3 versões) em JSON."""
    from . import assistente
    ok, _ = assistente.disponivel()
    if not ok or not palavras:
        return None
    from .efeitos import NOMES
    from .lab import formatos
    fala = "\n".join(f"[{fr['inicio']:.1f}s] {fr['texto']}" for fr in frases(palavras))[:9000]
    pedido = (
        "Você é o editor da Divine Medical Spa. Abaixo está a TRANSCRIÇÃO do vídeo bruto (com o segundo de cada frase).\n"
        "Escreva a edição automática em 3 versões que tenham TUDO A VER com o que é falado (nada genérico). "
        "Ganchos: use ou lapide frases da própria fala (sem inventar promessa). Mensagens na tela: frases-chave da fala, "
        "curtas, com *destaque* na palavra forte e ' / ' para quebrar linha, e o campo na_fala com as 3 a 5 primeiras "
        "palavras EXATAS da fala onde a mensagem entra. Efeitos: no máximo 1 a cada 4 segundos, só onde reforçam o que é "
        "dito, também presos à fala (na_fala). Português do Brasil, sem travessões, CFM e Anvisa (sem antes e depois, sem "
        "promessa de resultado, sem porcentagem de resultado).\n"
        f"Título do projeto: {projeto.get('titulo')}\n"
        f"Formatos virais possíveis: {', '.join(formatos())}\n"
        f"Efeitos possíveis (tipo): {', '.join(sorted(NOMES))}\n\n"
        f"TRANSCRIÇÃO:\n{fala}\n\n"
        "Responda SÓ com JSON: {\"tema\": \"...\", \"resumo\": \"uma frase\", \"selo\": \"TEMA · ÂNGULO\", "
        "\"versoes\": [{\"formato_viral\": \"...\", \"hook\": [{\"titulo\": \"...\"}]} x3], "
        "\"mensagens\": [{\"titulo\": \"...\", \"apoio\": \"opcional\", \"na_fala\": \"...\"}], "
        "\"efeitos\": [{\"tipo\": \"...\", \"na_fala\": \"...\", \"motivo\": \"...\"}], "
        "\"cta_antecipado\": \"...\", \"fechamento\": {\"frase\": \"...\", \"cta\": \"Agende sua avaliação\"}, "
        "\"legenda\": \"legenda do post em parágrafos curtos, com o assunto do vídeo\"}")
    try:
        texto, _, _ = assistente.perguntar([], pedido)
    except SystemExit:
        return None
    m = re.search(r"\{[\s\S]*\}", texto)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    d["fonte"] = "ia"
    return d


def aplicar(projeto: dict, plano: dict) -> dict:
    """Leva o plano para o projeto (só o que passa no revisor e só efeitos que existem)."""
    from .efeitos import QUADRO, TIPOS, resolver_tipo
    p = dict(projeto)
    vs = list(p.get("versoes") or [])
    ganchos = [v.get("hook") for v in plano.get("versoes") or [] if v.get("hook")] or plano.get("ganchos") or []
    formatos_ia = [v.get("formato_viral") for v in plano.get("versoes") or []]
    for i, v in enumerate(vs):
        if i < len(ganchos):
            h = [b for b in ganchos[i] if _ok(str(b.get("titulo", "")))]
            if h:
                v["hook"] = h
                v.pop("hook_id", None)
        if i < len(formatos_ia) and formatos_ia[i]:
            v["formato_viral"] = formatos_ia[i]
    p["versoes"] = vs
    msgs = [m for m in plano.get("mensagens") or [] if m.get("titulo") and _ok(m["titulo"])]
    if msgs:
        p["mensagens"] = msgs
    efs = []
    for e in plano.get("efeitos") or []:
        try:
            tipo = resolver_tipo({"tipo": e.get("tipo")})
        except SystemExit:
            continue
        if (tipo in TIPOS or tipo in QUADRO) and e.get("na_fala"):
            efs.append({k: v for k, v in {**e, "tipo": tipo}.items() if k in ("tipo", "na_fala", "texto", "duracao")})
    if efs:
        p["efeitos"] = efs[:6]
    for k in ("selo", "cta_antecipado"):
        if plano.get(k) and _ok(str(plano[k])):
            p[k] = plano[k]
    if isinstance(plano.get("fechamento"), dict) and _ok(str(plano["fechamento"].get("frase", ""))):
        p["fechamento"] = {**(p.get("fechamento") or {}), **plano["fechamento"]}
    if plano.get("legenda"):
        p["legenda"] = str(plano["legenda"]).strip() + ("\n\nResultados variam de pessoa para pessoa.\n"
                                                        "Resp. técnico: Dr. Daniel Sampaio Mendes · CRM/SP 186.470")
    p["roteiro_automatico"] = {"fonte": plano.get("fonte"), "tema": plano.get("tema"), "resumo": plano.get("resumo", "")}
    return p


def planejar(projeto: dict, palavras: list) -> dict:
    return planejar_ia(projeto, palavras) or planejar_regras(projeto, palavras)
