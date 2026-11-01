"""Assistente de IA do Divine Studio (Claude): brainstorm, ajuste de hook e de ideia, crítica do vídeo,
raio-X de referências e análise de desempenho no Instagram.

Base de conhecimento (sempre no prompt, com cache): as skills Divine em skills/, docs/CONHECIMENTO_DIVINE.md,
docs/BANCO_HOOKS.md e config/roteiros.yaml. O estado do projeto vai em cada mensagem.

Chave: export ANTHROPIC_API_KEY=... (console.anthropic.com) ou `ant auth login`.
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from .config import ROOT, load

MARCA_SUGESTAO = "divine-sugestao"

INSTRUCOES = f"""Você é o diretor criativo e editor-chefe do Divine Studio, a ferramenta de edição de vídeo da Divine
Medical Spa (Av. Paulista 1636, São Paulo). Você conversa com o Renato, sócio administrador, em português do Brasil,
de forma direta, prática e calorosa, como um parceiro de criação que entende de Instagram, Código Viral e do padrão
Divine (suave, glamouroso, dourado).

Como trabalhar:
- Responda curto e útil. Quando for brainstorm, traga opções concretas (3 a 5) e diga qual você escolheria e por quê.
- Pense sempre em prender a atenção: gancho nos primeiros 3 s, troca visual a cada ~2 s, um objetivo por post
  (enviar, salvar, comentar, seguir), final que gera replay.
- Compliance prevalece sobre qualquer ideia (CFM 2.336/2023 e Anvisa RDC 96/2008): sem promessa, prazo, percentual,
  antes e depois para postar, nome de medicamento; nunca pedir para comentar uma palavra. Sem travessões.
- Use os hooks do banco quando servirem (cite o código, ex.: C-H70) e invente novos quando for melhor.
- Use o que o app aprendeu com o Renato (gostei, postei, métricas) quando vier no contexto.

Quando propuser mudanças concretas no projeto, termine a resposta com UM bloco assim (JSON válido, só os campos que
mudam):
```{MARCA_SUGESTAO}
{{"hooks": [{{"nome": "V1", "hook": [{{"titulo": "Frase / com *destaque.*"}}, {{"titulo": "Segunda batida"}}]}}],
 "mensagens": [{{"titulo": "Mensagem / com *destaque*", "apoio": "opcional"}}],
 "selo": "TEMA", "cta_antecipado": "Manda pra amiga que...", "fechamento": {{"frase": "..."}},
 "objetivo": "enviar", "legenda": "texto da legenda", "roteiro": "roteiro de gravação em tópicos",
 "ideia_projeto": {{"titulo": "Tema do vídeo", "template": "divine"}}}}
```
Nos textos de tela: *palavra* fica dourada e " / " quebra a linha. Não use o bloco quando for só conversa.
"""


def _cfg() -> dict:
    return load("preferencias").get("ia", {})


@lru_cache(maxsize=1)
def base_conhecimento() -> str:
    partes = []
    for skill in sorted((ROOT / "skills").glob("*/SKILL.md")):
        partes.append(f"<skill nome=\"{skill.parent.name}\">\n{skill.read_text(encoding='utf-8')}\n</skill>")
    for doc in ("docs/CONHECIMENTO_DIVINE.md", "docs/BANCO_HOOKS.md", "config/roteiros.yaml"):
        arq = ROOT / doc
        if arq.exists():
            partes.append(f"<documento nome=\"{doc}\">\n{arq.read_text(encoding='utf-8')}\n</documento>")
    return "\n\n".join(partes)


def disponivel() -> tuple:
    """(ok, motivo). Sem chave a IA fica desligada e o painel explica como ligar."""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False, "Instale o SDK: pip3 install anthropic"
    import os
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True, ""
    perfil = Path.home() / ".config" / "anthropic"
    if perfil.exists():
        return True, ""
    return False, ("Para ligar a IA: crie uma chave em console.anthropic.com e rode no Terminal "
                   "export ANTHROPIC_API_KEY=sua-chave (ou ant auth login) antes de abrir o Divine Studio.")


def _cliente():
    import anthropic
    return anthropic.Anthropic()


def perguntar(historico: list, mensagem: str, contexto: str = "", imagens: list | None = None) -> tuple:
    """Envia uma mensagem e devolve (resposta_texto, sugestao|None, historico_novo).

    historico: mensagens anteriores no formato da API (o conteúdo do assistente volta inteiro e sem edição).
    imagens: [(bytes, 'image/jpeg')] (quadros do vídeo, prints de referência)."""
    import anthropic
    ok, motivo = disponivel()
    if not ok:
        raise SystemExit(motivo)
    conteudo = []
    for dados, tipo in imagens or []:
        conteudo.append({"type": "image", "source": {"type": "base64", "media_type": tipo,
                                                     "data": base64.standard_b64encode(dados).decode()}})
    texto = (f"<contexto_atual>\n{contexto}\n</contexto_atual>\n\n" if contexto else "") + mensagem
    conteudo.append({"type": "text", "text": texto})
    msgs = list(historico) + [{"role": "user", "content": conteudo}]
    try:
        resp = _cliente().beta.messages.create(
            model=_cfg().get("modelo", "claude-opus-5-5"),
            max_tokens=16000,
            system=[{"type": "text", "text": INSTRUCOES},
                    {"type": "text", "text": base_conhecimento(), "cache_control": {"type": "ephemeral"}}],
            messages=msgs,
            output_config={"effort": _cfg().get("esforco", "medium")},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError:
        raise SystemExit("Chave da IA inválida. Confira o ANTHROPIC_API_KEY.")
    except anthropic.RateLimitError:
        raise SystemExit("A IA está ocupada (limite de uso). Tente de novo em um minuto.")
    except anthropic.APIConnectionError:
        raise SystemExit("Sem conexão com a IA. Confira a internet.")
    except anthropic.APIStatusError as e:
        raise SystemExit(f"A IA respondeu com erro ({e.status_code}): {e.message}")
    if resp.stop_reason == "refusal":
        return ("A IA não pôde responder a esse pedido. Reformule (ela segue as regras do CFM e da Anvisa).",
                None, msgs)
    resposta = "\n".join(b.text for b in resp.content if b.type == "text").strip()
    # o conteúdo do assistente volta exatamente como veio (thinking incluído), sempre anexando ao histórico
    msgs.append({"role": "assistant", "content": [b.to_dict() for b in resp.content]})
    texto_limpo, sugestao = separar_sugestao(resposta)
    return texto_limpo, sugestao, msgs


def separar_sugestao(texto: str) -> tuple:
    m = re.search(rf"```{MARCA_SUGESTAO}\s*(\{{.*?\}})\s*```", texto, re.S)
    if not m:
        return texto, None
    try:
        sug = json.loads(m.group(1))
    except json.JSONDecodeError:
        return texto, None
    return (texto[:m.start()] + texto[m.end():]).strip(), sug


def texto_visivel(msg: dict) -> str:
    """Texto que aparece no chat para uma mensagem do histórico."""
    c = msg.get("content")
    if isinstance(c, str):
        return c
    partes = [b.get("text", "") for b in c if b.get("type") == "text"]
    t = "\n".join(partes)
    t = re.sub(r"<contexto_atual>.*?</contexto_atual>\s*", "", t, flags=re.S)
    return separar_sugestao(t)[0]


# ---------------------------------------------------------------- contexto do projeto

def contexto_projeto(pasta: Path) -> str:
    """Resumo do projeto para a IA: tema, template, hooks, textos, fala, notas, relatório e aprendizado."""
    import yaml
    from . import aprendizado
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    linhas = [f"Projeto: {d.get('titulo')} · template {d.get('template', 'divine')} · formato {d.get('formato', 'reels')}"
              f" · objetivo {d.get('objetivo') or 'não definido'} · tags {', '.join(d.get('tags') or []) or '-'}"]
    if d.get("tipo") == "carrossel":
        linhas.append("Carrossel: " + json.dumps(d.get("cards") or [], ensure_ascii=False))
    for v in d.get("versoes") or []:
        h = v.get("hook")
        linhas.append(f"Versão {v.get('nome')}: hook_id {v.get('hook_id') or '-'} · hook {json.dumps(h, ensure_ascii=False)}"
                      f" · fontes {v.get('fontes') or 'rodízio'}")
    for k in ("selo", "cta_antecipado", "mensagens", "fechamento", "efeitos"):
        if d.get(k):
            linhas.append(f"{k}: {json.dumps(d[k], ensure_ascii=False)}")
    trans = sorted((pasta / "trabalho" / "transcricoes").glob("*.json")) if (pasta / "trabalho" / "transcricoes").exists() else []
    if trans:
        pal = json.loads(trans[0].read_text(encoding="utf-8")).get("palavras", [])
        linhas.append("Fala transcrita: " + " ".join(w["texto"] for w in pal)[:3000])
    rel = pasta / "relatorio.md"
    if rel.exists():
        linhas.append("Relatório da última edição:\n" + rel.read_text(encoding="utf-8")[:3000])
    if d.get("publicacoes"):
        linhas.append("Publicações e métricas: " + json.dumps(
            [{k: p.get(k) for k in ("versao", "status", "gostei", "metricas", "data_postagem")} for p in d["publicacoes"]],
            ensure_ascii=False))
    aprendi = aprendizado.resumo()
    if aprendi:
        linhas.append("O que o app aprendeu com o Renato: " + "; ".join(aprendi))
    return "\n".join(linhas)


def quadros_do_video(video: Path, n: int = 6, largura: int = 540) -> list:
    """n quadros JPEG espaçados de um vídeo (para a IA olhar o resultado ou uma referência)."""
    from .ingest import probe
    dur = probe(video)["duracao"] or 1
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for k in range(n):
            t = dur * (k + 0.5) / n
            arq = Path(tmp) / f"q{k}.jpg"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                            "-vf", f"scale={largura}:-2", "-q:v", "4", str(arq)], check=False)
            if arq.exists():
                out.append((arq.read_bytes(), "image/jpeg"))
    return out


# ---------------------------------------------------------------- conversas guardadas

def _arquivo_conversa(pasta: Path | None, conversa: str | None) -> Path:
    if pasta is not None:
        return pasta / "trabalho" / "conversa_ia.json"
    base = ROOT / "ideias" / "conversas"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{re.sub(r'[^a-z0-9-]', '', (conversa or 'geral').lower()) or 'geral'}.json"


def carregar_conversa(pasta: Path | None, conversa: str | None = None) -> dict:
    arq = _arquivo_conversa(pasta, conversa)
    if arq.exists():
        return json.loads(arq.read_text(encoding="utf-8"))
    return {"historico": [], "sugestoes": {}}


def salvar_conversa(pasta: Path | None, conversa: str | None, dados: dict) -> None:
    arq = _arquivo_conversa(pasta, conversa)
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")


def conversar(pasta: Path | None, mensagem: str, conversa: str | None = None, olhar_video: bool = False,
              imagens: list | None = None) -> dict:
    """Uma rodada de conversa, guardada (projeto: trabalho/conversa_ia.json; geral: ideias/conversas/)."""
    dados = carregar_conversa(pasta, conversa)
    contexto = contexto_projeto(pasta) if pasta is not None else ""
    if pasta is None:
        from . import aprendizado
        aprendi = aprendizado.resumo()
        contexto = ("Brainstorm livre (sem projeto aberto). " + ("Aprendizado: " + "; ".join(aprendi) if aprendi else "")).strip()
    imgs = list(imagens or [])
    if olhar_video and pasta is not None:
        videos = sorted((x for x in (pasta / "saida").glob("*.mp4") if not x.name.startswith(".")),
                        key=lambda f: f.stat().st_mtime, reverse=True)
        if videos:
            imgs += quadros_do_video(videos[0])
            mensagem += f"\n\n(Junto vão {len(imgs)} quadros da versão mais recente: {videos[0].name}.)"
    texto, sugestao, hist = perguntar(dados["historico"], mensagem, contexto, imgs)
    dados["historico"] = hist
    if sugestao:
        dados.setdefault("sugestoes", {})[str(len(hist) - 1)] = sugestao
    salvar_conversa(pasta, conversa, dados)
    return {"resposta": texto, "sugestao": sugestao}


def mensagens_para_tela(dados: dict) -> list:
    out = []
    for i, m in enumerate(dados.get("historico") or []):
        t = texto_visivel(m)
        if m["role"] == "user":
            t = re.sub(r"\n\n\(Junto vão .*?\)$", " 📷", t, flags=re.S)
        out.append({"papel": m["role"], "texto": t, "sugestao": (dados.get("sugestoes") or {}).get(str(i))})
    return out


def aplicar_sugestao(pasta: Path, sug: dict) -> list:
    """Leva a sugestão para o projeto (depois do revisor). Devolve os campos alterados."""
    import yaml
    from .compliance import revisar
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    textos = []
    for h in sug.get("hooks") or []:
        textos += [b.get("titulo", "") for b in h.get("hook") or []]
    textos += [m.get("titulo", "") for m in sug.get("mensagens") or []]
    textos += [sug.get(k, "") for k in ("selo", "cta_antecipado") if sug.get(k)]
    if (sug.get("fechamento") or {}).get("frase"):
        textos.append(sug["fechamento"]["frase"])
    erros = [a for a in revisar({**d, "legenda": sug.get("legenda", "")}, textos) if a.nivel == "erro"]
    if erros:
        raise SystemExit("O revisor barrou a sugestão: " + "; ".join(a.linha() for a in erros))
    mudou = []
    if sug.get("hooks"):
        versoes = {v.get("nome"): v for v in d.get("versoes") or []}
        for h in sug["hooks"]:
            v = versoes.setdefault(h.get("nome", "V1"), {"nome": h.get("nome", "V1")})
            v.pop("hook_id", None)
            v["hook"] = h.get("hook")
        d["versoes"] = list(versoes.values())
        mudou.append("hooks")
    for k in ("mensagens", "selo", "cta_antecipado", "objetivo", "legenda"):
        if k in sug:
            d[k] = sug[k]
            mudou.append(k)
    if sug.get("fechamento"):
        d["fechamento"] = {**(d.get("fechamento") or {}), **sug["fechamento"]}
        mudou.append("fechamento")
    if sug.get("roteiro"):
        (pasta / "roteiro.md").write_text(f"# Roteiro de gravação · {d.get('titulo')}\n\n{sug['roteiro']}\n",
                                          encoding="utf-8")
        mudou.append("roteiro.md")
    if mudou:
        (pasta / "trabalho").mkdir(exist_ok=True)
        (pasta / "trabalho" / "projeto.yaml.anterior").write_text((pasta / "projeto.yaml").read_text(encoding="utf-8"),
                                                                  encoding="utf-8")
        (pasta / "projeto.yaml").write_text("# Divine Studio (sugestão da IA aplicada)\n" + yaml.safe_dump(
            d, allow_unicode=True, sort_keys=False, width=1000, default_flow_style=None), encoding="utf-8")
    return mudou
