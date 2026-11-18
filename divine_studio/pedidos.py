"""Ideia do vídeo e pedidos de edição escritos (ou ditados) em português, no mesmo campo do painel.

- A IDEIA (`ideia:` no projeto.yaml) é o roteirinho que o Renato escreve antes de gerar: o app usa para reconhecer o
  tema, escolher as frases que vão para a tela e, sem fala no vídeo, escrever as mensagens a partir dela.
- Os PEDIDOS são frases como "aos 10 segundos tira o efeito", "em 0:12 troca o texto por Pele firme",
  "coloca um zoom aos 8 s", "legenda mais para baixo", "menos efeitos". Cada frase vira uma mudança no projeto.yaml.
  As palavras que o app entende ficam em config/pedidos.yaml. O que ele não entende volta com exemplos (e, com a
  chave do Claude, pode ir para a IA do projeto).
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .config import load


def cfg() -> dict:
    return load("pedidos")


def _sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "")) if unicodedata.category(c) != "Mn").lower()


# ---------------------------------------------------------------- ideia

def frases_da_ideia(ideia: str, n: int = 3) -> list:
    """Frases curtas da ideia, prontas para a tela (quando o vídeo não tem fala para tirar o texto)."""
    from .auto import _destacar
    from .roteirista import _ok
    partes = [p.strip(" .;:") for p in re.split(r"[.\n;!?]+", str(ideia or "")) if p.strip()]
    out = []
    for p in partes:
        palavras = p.split()
        if not 2 <= len(palavras) <= 10 or not _ok(p):
            continue
        out.append({"titulo": _destacar(p[:1].upper() + p[1:])})
        if len(out) >= n:
            break
    return out


def plano_da_ideia(projeto: dict) -> dict | None:
    """Vídeo sem fala: hooks e mensagens saem da ideia escrita (em vez dos textos genéricos do tema)."""
    msgs = frases_da_ideia(projeto.get("ideia") or "", 4)
    if not msgs:
        return None
    return {"fonte": "ideia", "tema": None, "ganchos": [[msgs[0]]], "mensagens": msgs[1:], "efeitos": []}


# ---------------------------------------------------------------- pedidos

def _tempo(frase: str, duracao: float) -> float | None:
    s = _sem_acento(frase)
    m = re.search(r"\b(\d{1,2}):(\d{2})\b", s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = re.search(r"\b(?:aos?|em|no|nos|segundo)\s+(?:segundo\s+)?(\d+(?:[.,]\d+)?)\s*(?:s\b|seg\b|segundos?\b)?", s)
    if m and re.search(r"\b(aos?|segundos?|seg|s)\b", s[m.start():m.end() + 10]):
        return float(m.group(1).replace(",", "."))
    m = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(?:s|seg|segundos?)\b", s)
    if m and not re.search(r"\b(mais|menos)\s+" + re.escape(m.group(0)), s):
        return float(m.group(1).replace(",", "."))
    if re.search(r"\b(comeco|inicio|abertura)\b", s):
        return 0.5
    if re.search(r"\b(final|fim|encerramento)\b", s):
        return max(0.0, duracao - 3.0)
    return None


def _entre_aspas(frase: str) -> str | None:
    m = re.search(r"[\"“']([^\"”']{2,})[\"”']", frase)
    if m:
        return m.group(1).strip()
    m = re.search(r"\b(?:por|para|escreve|escreva|escrito)\b[: ]+(.{3,})$", frase, re.I)
    return m.group(1).strip(" .") if m else None


def _efeito_pedido(frase: str) -> str | None:
    """Tipo do efeito citado na frase: apelidos de config/pedidos.yaml, depois o nome no catálogo."""
    s = _sem_acento(frase)
    for apelido, tipo in (cfg().get("efeitos") or {}).items():
        if re.search(r"\b" + re.escape(_sem_acento(apelido)) + r"\b", s):
            return tipo
    try:
        from .efeitos import NOMES
        for tipo, nome in NOMES.items():
            if len(nome) > 4 and _sem_acento(nome.split("(")[0].strip()) in s:
                return tipo
    except Exception:
        pass
    return None


def _perto(lista: list, t: float, raio: float):
    """(índice, item) do item com `inicio` mais perto de t, dentro do raio."""
    melhor = None
    for i, x in enumerate(lista or []):
        if not isinstance(x, dict) or x.get("inicio") in (None, ""):
            continue
        d = abs(float(x["inicio"]) - t)
        if d <= raio and (melhor is None or d < melhor[0]):
            melhor = (d, i, x)
    return (melhor[1], melhor[2]) if melhor else (None, None)


def _acao(frase: str) -> str | None:
    s = _sem_acento(frase)
    for nome, palavras in (cfg().get("acoes") or {}).items():
        if any(re.search(r"\b" + re.escape(_sem_acento(p)) + r"\b", s) for p in palavras):
            return nome
    return None


def interpretar(texto: str) -> list:
    """Uma frase por pedido (ponto, ponto e vírgula, quebra de linha ou ' e depois ')."""
    partes = re.split(r"[;\n]+|\.\s+(?=[A-ZÀ-Ú0-9a])|\s+e depois\s+", str(texto or ""))
    return [p.strip(" .") for p in partes if len(p.strip(" .")) > 2]


def aplicar(projeto: dict, texto: str, duracao: float = 30.0, autos: list | None = None) -> dict:
    """Aplica os pedidos no dicionário do projeto. Devolve {projeto, aplicados, nao_entendi, mudou}.

    `autos`: efeitos automáticos da versão (trabalho/linha_<V>.json), para "tira o efeito aos 10 s" alcançar também
    o que o ritmo colocou sozinho (vai para efeitos_evitar e não volta).
    """
    p = dict(projeto)
    raio = float(cfg().get("raio_s", 2.5))
    aplicados, nao = [], []
    for frase in interpretar(texto):
        s = _sem_acento(frase)
        t = _tempo(frase, duracao)
        acao = _acao(frase)
        feito, aprende, tirado_tipo = None, None, None
        # ---- ajustes do vídeo inteiro (sem tempo)
        for g in cfg().get("gerais") or []:
            if re.search(g["padrao"], s):
                alvo = p
                chaves = g["campo"].split(".")
                for k in chaves[:-1]:
                    atual = alvo.get(k)
                    alvo[k] = dict(atual) if isinstance(atual, dict) else ({"ativo": True} if atual else {})
                    alvo = alvo[k]
                if "soma" in g:
                    base = float(alvo.get(chaves[-1], g.get("base", 0)) or g.get("base", 0))
                    alvo[chaves[-1]] = round(min(g.get("max", 1e9), max(g.get("min", -1e9), base + float(g["soma"]))), 3)
                else:
                    alvo[chaves[-1]] = g["valor"]
                feito = g["resposta"]
                aprende = {"campo": g["campo"], "valor": alvo[chaves[-1]]} if g.get("aprende", True) else None
                break
        if feito:
            aplicados.append({"pedido": frase, "feito": feito, **({"aprende": aprende} if aprende else {})})
            continue
        if t is None or acao is None:
            nao.append(frase)
            continue
        efeitos = list(p.get("efeitos") or [])
        msgs = list(p.get("mensagens") or [])
        sons = list(p.get("sons") or [])
        quer_texto = bool(re.search(r"\b(texto|frase|mensagem|titulo|escrit)", s))
        quer_som = bool(re.search(r"\b(som|sfx|barulho|efeito sonoro)\b", s))
        if acao == "tirar":
            i, meu = _perto(msgs if quer_texto else sons if quer_som else efeitos, t, raio)
            _, ef = _perto(autos or [], t, raio) if not quer_texto and not quer_som else (None, None)
            if ef and meu and abs(float(meu["inicio"]) - t) <= abs(float(ef["inicio"]) - t):
                ef = None                                     # o seu está mais perto do tempo dito
            if ef or (i is None and not quer_texto and not quer_som):
                i = None if ef else i
                if ef:
                    p["efeitos_evitar"] = list(p.get("efeitos_evitar") or []) + [{"tipo": ef["tipo"], "inicio": ef["inicio"]}]
                    feito = f"Tirei o efeito automático ({ef['tipo']}) de {float(ef['inicio']):.1f} s"
                    tirado_tipo = ef["tipo"]
                else:
                    i, _ = _perto(msgs, t, raio)
                    if i is not None:
                        quer_texto = True
            if not feito and i is not None:
                alvo = msgs if quer_texto else sons if quer_som else efeitos
                tirado = alvo.pop(i)
                feito = f"Tirei {'o texto' if quer_texto else 'o som' if quer_som else 'o efeito'} de {float(tirado['inicio']):.1f} s"
        elif acao == "trocar":
            novo_txt = _entre_aspas(frase)
            tipo = _efeito_pedido(frase.split(" por ", 1)[-1]) if " por " in frase.lower() else None
            if tipo and not quer_texto:
                i, ef = _perto(efeitos, t, raio)
                _, auto = _perto(autos or [], t, raio)
                if auto and ef and abs(float(ef["inicio"]) - t) <= abs(float(auto["inicio"]) - t):
                    auto = None                               # o seu está mais perto do tempo dito
                if ef is None or auto:
                    if auto:
                        p["efeitos_evitar"] = list(p.get("efeitos_evitar") or []) + [{"tipo": auto["tipo"], "inicio": auto["inicio"]}]
                    efeitos.append({"tipo": tipo, "inicio": round(float((auto or {}).get("inicio", t)), 2)})
                else:
                    efeitos[i] = {"tipo": tipo, "inicio": ef["inicio"]}
                feito = f"Troquei o efeito de {t:.1f} s por {tipo}"
            elif novo_txt:
                i, m = _perto(msgs, t, raio)
                if m is None:
                    msgs.append({"titulo": novo_txt, "inicio": round(t, 2)})
                    feito = f"Pus o texto \"{novo_txt}\" em {t:.1f} s"
                else:
                    msgs[i] = {**m, "titulo": novo_txt}
                    feito = f"Troquei o texto de {float(m['inicio']):.1f} s por \"{novo_txt}\""
        elif acao == "por":
            tipo = _efeito_pedido(frase)
            novo_txt = _entre_aspas(frase) if quer_texto else None
            if novo_txt:
                msgs.append({"titulo": novo_txt, "inicio": round(t, 2)})
                feito = f"Pus o texto \"{novo_txt}\" em {t:.1f} s"
            elif tipo == "insert_foto":                  # a imagem vem do acervo, pelas palavras do pedido
                from .acervo import buscar
                achadas = buscar(re.sub(r"\d+[.,:]?\d*\s*(s|seg|segundos?)?\b", " ", frase), n=1)
                if achadas:
                    efeitos.append({"tipo": tipo, "inicio": round(t, 2), "foto": achadas[0]["arquivo"]})
                    feito = f"Pus a imagem {Path(achadas[0]['arquivo']).name} em {t:.1f} s"
            elif tipo:
                efeitos.append({"tipo": tipo, "inicio": round(t, 2)})
                feito = f"Pus {tipo} em {t:.1f} s"
        elif acao in ("antes", "depois"):
            passo = float(cfg().get("passo_s", 0.5)) * (-1 if acao == "antes" else 1)
            alvo = msgs if quer_texto else sons if quer_som else efeitos
            i, x = _perto(alvo, t, raio)
            if x is not None:
                alvo[i] = {**x, "inicio": round(max(0.0, float(x["inicio"]) + passo), 2)}
                feito = f"Movi para {alvo[i]['inicio']:.1f} s"
        if feito:
            p["efeitos"], p["mensagens"], p["sons"] = efeitos, msgs, sons
            aplicados.append({"pedido": frase, "feito": feito,
                              **({"aprende": {"efeito_tirado": tirado_tipo}} if tirado_tipo else {})})
        else:
            nao.append(frase)
    for k in ("efeitos", "mensagens", "sons"):
        if k in p and not p[k] and k not in projeto:
            del p[k]
    return {"projeto": p, "aplicados": aplicados, "nao_entendi": nao, "mudou": bool(aplicados),
            "aprendidos": [a for a in aplicados if a.get("aprende")]}


# ---------------------------------------------------------------- o que o Renato pede vira padrão dos próximos

def _arq_padroes() -> Path:
    from .aprendizado import PROJETOS
    return Path(PROJETOS) / ".padroes_aprendidos.json"


def padroes() -> dict:
    """{"campos": {"legendas.posicao": 0.7, "ritmo": "calmo"}, "efeitos_tirados": {"congelar": 2}} (só no Mac)."""
    import json
    try:
        d = json.loads(_arq_padroes().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    return {"campos": dict(d.get("campos") or {}), "efeitos_tirados": dict(d.get("efeitos_tirados") or {})}


def aprender(itens: list) -> list:
    """Guarda cada pedido geral como padrão e conta os efeitos tirados. Devolve frases para a tela."""
    import json
    d, frases = padroes(), []
    for it in itens:
        if "campo" in it:
            d["campos"][it["campo"]] = it["valor"]
            frases.append("Guardei como padrão dos próximos vídeos.")
        elif it.get("efeito_tirado"):
            t = it["efeito_tirado"]
            d["efeitos_tirados"][t] = int(d["efeitos_tirados"].get(t, 0)) + 1
            if d["efeitos_tirados"][t] == int(cfg().get("tirar_vira_regra", 2)):
                frases.append(f"Você já tirou o efeito {t} mais de uma vez: ele sai do sorteio dos próximos vídeos.")
    try:
        from . import guardar
        _arq_padroes().parent.mkdir(parents=True, exist_ok=True)
        guardar.gravar_texto(_arq_padroes(), json.dumps(d, ensure_ascii=False, indent=1))
    except OSError:
        pass
    return sorted(set(frases))


def efeitos_que_o_renato_tira() -> set:
    n = int(cfg().get("tirar_vira_regra", 2))
    return {t for t, k in padroes()["efeitos_tirados"].items() if int(k) >= n}


def aplicar_padroes(projeto: dict) -> list:
    """Na edição automática de um vídeo novo: aplica o que ele já pediu antes (só no que o projeto não define)."""
    feitos = []
    for campo, valor in padroes()["campos"].items():
        chaves = campo.split(".")
        alvo = projeto
        for k in chaves[:-1]:
            atual = alvo.get(k)
            if atual is False:                       # recurso desligado neste projeto: não religa
                alvo = None
                break
            alvo[k] = dict(atual) if isinstance(atual, dict) else ({"ativo": True} if atual else {})
            alvo = alvo[k]
        if alvo is None or alvo.get(chaves[-1]) == valor:
            continue
        alvo[chaves[-1]] = valor
        feitos.append(f"{campo} = {valor}")
    return feitos


CAMPOS = ("efeitos", "mensagens", "sons", "efeitos_evitar", "legendas", "ritmo", "audio", "sfx_automaticos",
          "ritmo_fixo", "fontes_livres")


def aplicar_no_projeto(pasta: Path, texto: str, versao: str = "V1") -> dict:
    """Lê o projeto e aplica os pedidos. Devolve o resumo para a tela e `dados`: só os campos que mudaram
    (quem grava é o painel, pelo mesmo caminho seguro de todo salvamento)."""
    import json

    import yaml
    pasta = Path(pasta)
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    try:
        linha = json.loads((pasta / "trabalho" / f"linha_{versao}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        linha = {}
    try:
        dur = float(json.loads((pasta / "trabalho" / "base.json").read_text(encoding="utf-8")).get("duracao") or 30)
    except (OSError, ValueError):
        dur = 30.0
    r = aplicar(d, texto, dur, linha.get("efeitos") or [])
    dados = {k: r["projeto"].get(k) for k in CAMPOS if r["projeto"].get(k) != d.get(k)}
    novos = aprender([a["aprende"] for a in r["aprendidos"]]) if (r.get("aprendidos")) else []
    for a in r["aplicados"]:
        a.pop("aprende", None)
    return {"aplicados": r["aplicados"], "nao_entendi": r["nao_entendi"], "exemplos": cfg().get("exemplos") or [],
            "dados": dados, "aprendi": novos}


def pedido_canva(pasta: Path, texto: str = "", t: float | None = None) -> str:
    """Instrução pronta para colar no Claude (com o conector do Canva): gerar um fundo ou elemento gráfico no padrão
    Liquid Glass para este vídeo. O app não fala com o Canva sozinho; a imagem volta para o projeto pelo botão de
    enviar arquivo (pasta bruto/) e entra no vídeo como "Foto que entra na fala"."""
    import yaml
    pasta = Path(pasta)
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    c = (load("identidade").get("liquid_glass") or {}).get("canva") or {}
    onde = f" para entrar aos {float(t):.0f} segundos do vídeo" if t not in (None, "") else ""
    return (c.get("abertura", "Gere no Canva (IA) uma imagem para um vídeo da Divine Medical Spa.") + "\n\n"
            f"Vídeo: {d.get('titulo', pasta.name)}\n"
            + (f"Ideia do vídeo: {d['ideia']}\n" if d.get("ideia") else "")
            + (f"O que eu preciso{onde}: {texto.strip()}\n" if texto.strip() else
               f"O que eu preciso{onde}: um elemento gráfico ou fundo que combine com a ideia acima.\n")
            + "\nPadrão visual (Liquid Glass Divine):\n" + str(c.get("receita", "")).strip() + "\n\n"
            + str(c.get("entrega", "")).strip().replace("{pasta}", f"projetos/{pasta.name}/bruto"))
