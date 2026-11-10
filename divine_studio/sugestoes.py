"""Sugestões para a próxima versão ficar SUPERIOR à que você aprovou.

O app olha a sua fala (transcrição), a edição montada, o que você aprovou antes e, se houver, a análise de
viralidade do Higgsfield (Virality Predictor). Devolve poucas sugestões concretas, da mais forte para a mais fraca:
  - o que regravar ou trocar na fala (abertura lenta, apresentação antes do assunto, sem pedido no final)
  - o que cortar (vídeo longo demais, fala lenta)
  - o que já funcionou com você e ainda não está nesta edição
Com a IA ligada (chave da API), o Claude completa com as dele. Nada aqui muda o vídeo sozinho: você decide.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ABERTURA_FRACA = re.compile(r"^\s*(oi|olá|ola|e aí|eai|bom dia|boa tarde|boa noite|tudo bem|eu sou|meu nome|"
                            r"hoje eu vou|hoje vou|nesse vídeo|neste vídeo|nesse video|neste video|então|entao)\b", re.I)
PEDIDO = re.compile(r"\b(agende|agenda|marque|segue|siga|salva|salve|manda|mande|comenta|comente|link|direct|"
                    r"whatsapp|avaliação|avaliacao)\b", re.I)


def _fala(pasta: Path) -> list:
    arq = pasta / "trabalho" / "fala_base.json"
    if arq.exists():
        try:
            return json.loads(arq.read_text(encoding="utf-8"))
        except ValueError:
            return []
    pal = []
    for f in sorted((pasta / "trabalho" / "transcricoes").glob("*.json")) if (pasta / "trabalho" / "transcricoes").exists() else []:
        if ".editado." in f.name:
            continue
        try:
            pal += json.loads(f.read_text(encoding="utf-8")).get("palavras") or []
        except ValueError:
            pass
    return pal


def da_fala(palavras: list) -> list:
    """Sugestões tiradas só da fala."""
    from .roteirista import frases, ganchos_da_fala
    out = []
    if not palavras:
        return [{"tipo": "fala", "forca": 3, "titulo": "Ligue a transcrição",
                 "texto": "Sem a fala transcrita o app não sabe o que você disse e não consegue sugerir trocas. "
                          "Toque em ⟳ Atualizar (instala sozinho)."}]
    fr = frases(palavras)
    if not fr:
        return out
    primeira = fr[0]
    dur_primeira = (fr[1]["inicio"] if len(fr) > 1 else palavras[-1]["fim"]) - primeira["inicio"]
    melhores = ganchos_da_fala(palavras, 1)
    forte = re.sub(r"[*/]", "", melhores[0][0]["titulo"]).replace("  ", " ").strip() if melhores else ""
    if ABERTURA_FRACA.search(primeira["texto"]):
        out.append({"tipo": "regravar", "forca": 5, "titulo": "Comece pelo assunto, não pela apresentação",
                    "texto": f"O vídeo abre com \"{primeira['texto'][:70]}\". Nos primeiros 3 segundos a pessoa decide se fica. "
                             + (f"Abra direto com: \"{forte}\" e se apresente depois." if forte else "Abra com a frase mais forte.")})
    elif dur_primeira > 4.5:
        mesma = forte and forte.lower().rstrip("?.!") in primeira["texto"].lower()
        curta = re.sub(r"^(você sabia que|voce sabia que|sabia que|olha|então|entao|vou te contar)\s+", "",
                       primeira["texto"].strip(), flags=re.I)
        curta = curta[:1].upper() + curta[1:]
        if mesma:
            texto = (f"A abertura é boa, mas leva {dur_primeira:.0f} s. Diga em até 3 s, mais direto: \"{curta}\"."
                     if curta != primeira["texto"].strip() else
                     f"A abertura é boa, mas leva {dur_primeira:.0f} s. Diga mais rápido, sem pausa no meio, em até 3 s.")
        else:
            texto = f"A primeira frase leva {dur_primeira:.0f} s. Abra com a frase mais forte do vídeo: \"{forte}\"."
        out.append({"tipo": "regravar", "forca": 4, "titulo": "Abertura longa", "texto": texto})
    fim = " ".join(f["texto"] for f in fr[-2:])
    if not PEDIDO.search(fim):
        out.append({"tipo": "regravar", "forca": 4, "titulo": "Feche com um pedido só",
                    "texto": "A fala termina sem pedir nada. Grave uma frase final curta, por exemplo: "
                             "\"Se isso faz sentido para você, agende sua avaliação\" ou \"Salva para lembrar\"."})
    dur = float(palavras[-1]["fim"]) - float(palavras[0]["inicio"])
    ritmo = len(palavras) / max(1.0, dur)
    if dur > 75:
        out.append({"tipo": "cortar", "forca": 4, "titulo": f"Vídeo longo ({dur:.0f} s de fala)",
                    "texto": "Reels que mais ganham seguidores ficam entre 20 e 45 s. Dá para virar 2 vídeos ou "
                             "cortar a parte do meio que repete a ideia (use Cortes do vídeo longo)."})
    if ritmo < 1.8 and dur > 10:
        out.append({"tipo": "ritmo", "forca": 3, "titulo": "Fala devagar",
                    "texto": f"{ritmo:.1f} palavras por segundo. O corte limpo já tira as pausas; acelerar 1,1x "
                             "(Edição > clipe > velocidade) costuma segurar mais."})
    vicios = [w for w in palavras if re.fullmatch(r"(é+|hum+|ãh+|ah+|né|tipo)[.,…]*", str(w.get("texto", "")).lower())]
    if len(vicios) >= 5:
        out.append({"tipo": "fala", "forca": 2, "titulo": f"{len(vicios)} vícios de fala (é, né, tipo)",
                    "texto": "O corte limpo tira a maior parte. Na próxima gravação, uma pausa curta no lugar do \"é\" "
                             "deixa o corte mais natural."})
    return out


def do_aprendizado(projeto: dict) -> list:
    """O que já funcionou com você e não está nesta edição."""
    try:
        from .aprendizado import preferencias
        from .instagram import conta_do_projeto
        prefs = preferencias(conta_do_projeto(projeto))
    except Exception:
        return []
    out = []
    tipos = {v: n for v, (n_, c) in (prefs.get("hook_tipo") or {}).items() for n in [n_] if c >= 2}
    if tipos:
        melhor, nota = max(tipos.items(), key=lambda x: x[1])
        if nota > 0.5:
            out.append({"tipo": "aprendizado", "forca": 3, "titulo": f"Hook de {melhor} funciona com você",
                        "texto": f"As peças que você aprovou ou que foram melhor usam hook do tipo \"{melhor}\". "
                                 "A versão IA desta edição já testa isso; se não estiver nela, troque um hook na Edição."})
    durs = {v: n for v, (n, c) in (prefs.get("duracao") or {}).items() if c >= 2}
    if durs:
        d, nota = max(durs.items(), key=lambda x: x[1])
        if nota > 0.5:
            out.append({"tipo": "aprendizado", "forca": 2, "titulo": f"Suas melhores peças têm uns {d} s",
                        "texto": "Tente deixar esta perto disso."})
    return out


def do_higgsfield(nome: str) -> list:
    """Análise de viralidade do Higgsfield (quando você pediu e o Claude trouxe o resultado)."""
    try:
        from . import higgsfield as hf
        itens = [x for x in hf.listar(projeto=nome) if x.get("alvo") == "virality_predictor"]
    except Exception:
        return []
    out = []
    for x in itens[:1]:
        if x.get("status") == "pronto" and x.get("analise"):
            a = x["analise"]
            texto = a if isinstance(a, str) else "; ".join(f"{k}: {v}" for k, v in a.items() if k != "quedas")
            if isinstance(a, dict) and a.get("quedas"):
                texto += f" ({len(a['quedas'])} queda(s) marcadas com ! na linha do tempo)"
            out.append({"tipo": "higgsfield", "forca": 5, "titulo": "Leitura do Higgsfield (viralidade)", "texto": texto[:600]})
        elif x.get("status") in ("pendente", "gerando"):
            out.append({"tipo": "higgsfield", "forca": 1, "titulo": "Análise do Higgsfield na fila",
                        "texto": "Peça ao Claude para processar a fila do Higgsfield (botão \"Copiar pedido\")."})
    return out


def gerar(pasta: Path, nome: str = "") -> dict:
    """Sugestões do projeto, da mais forte para a mais fraca (no máximo 5)."""
    pasta = Path(pasta)
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    d["_pasta"] = pasta
    nome = nome or pasta.name
    itens = do_higgsfield(nome) + da_fala(_fala(pasta)) + do_aprendizado(d)
    vistos, out = set(), []
    for s in sorted(itens, key=lambda s: -s["forca"]):
        if s["titulo"] not in vistos:
            vistos.add(s["titulo"])
            out.append(s)
    return {"sugestoes": out[:5], "aprovadas": sum(1 for p in d.get("publicacoes") or []
                                                    if p.get("status") in ("aprovado", "agendado", "postado"))}


def com_ia(pasta: Path) -> list:
    """O Claude lê a transcrição e a edição e diz o que trocar para a próxima versão ser melhor (com a chave)."""
    from . import assistente
    from .roteirista import frases
    ok, motivo = assistente.disponivel()
    if not ok:
        raise SystemExit(motivo)
    pasta = Path(pasta)
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    fala = "\n".join(f"[{f['inicio']:.1f}s] {f['texto']}" for f in frases(_fala(pasta)))[:8000]
    edicao = {k: d.get(k) for k in ("titulo", "versoes", "mensagens", "cta_antecipado", "fechamento")}
    pedido = ("Você é o editor-chefe da Divine Medical Spa. Esta edição foi aprovada, mas quero que a PRÓXIMA versão seja "
              "superior. Leia a fala e a edição e me dê até 4 sugestões concretas que mais aumentam visualizações e "
              "seguidores: o que regravar ou trocar na fala (com a frase nova pronta), o que cortar, que hook usar. "
              "Português do Brasil, sem travessões, dentro do CFM e da Anvisa. Responda SÓ com JSON: "
              "[{\"titulo\": \"...\", \"texto\": \"...\", \"tipo\": \"regravar|cortar|hook|texto\"}]\n\n"
              f"FALA:\n{fala}\n\nEDIÇÃO:\n{json.dumps(edicao, ensure_ascii=False, default=str)[:4000]}")
    texto, _, _ = assistente.perguntar([], pedido)
    m = re.search(r"\[[\s\S]*\]", texto)
    try:
        lista = json.loads(m.group(0)) if m else []
    except ValueError:
        lista = []
    return [{"tipo": s.get("tipo", "ia"), "forca": 4, "titulo": str(s.get("titulo", ""))[:90],
             "texto": str(s.get("texto", ""))[:600], "fonte": "Claude"} for s in lista if isinstance(s, dict)][:4]


def pedir_higgsfield(nome: str, pasta: Path, arquivo: str) -> dict:
    """Põe a versão na fila do Virality Predictor (o Claude executa com o conector e traz a leitura)."""
    from . import higgsfield as hf
    return hf.criar(nome, "ferramenta", "virality_predictor", arquivo=arquivo)
