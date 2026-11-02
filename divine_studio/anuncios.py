"""Vídeos de anúncio feitos para conversão (Meta Ads): estrutura gancho, problema, solução, prova e chamada no vídeo,
cartão final com o botão ("Saiba mais", "Enviar mensagem"), e a copy do anúncio em 3 variações para teste A/B.

projeto.yaml de um anúncio:
  anuncio: {objetivo: agendamento | mensagens | cadastro, servico: "Endolaser", dor: "...", beneficio: "..."}
Regras em config/anuncios.yaml. Tudo passa pelo revisor (CFM/Anvisa) antes de sair.
"""
from __future__ import annotations

import re
from pathlib import Path

from .config import load


def _cfg() -> dict:
    return load("anuncios")


def _tema(titulo: str) -> dict:
    from .auto import tema
    chave, _ = tema(titulo or "")
    temas = _cfg().get("temas") or {}
    return temas.get(chave) or temas.get("padrao") or {}


def dados_anuncio(projeto: dict) -> dict:
    a = dict(projeto.get("anuncio") or {})
    t = _tema(projeto.get("titulo", ""))
    a.setdefault("objetivo", "agendamento")
    a.setdefault("servico", projeto.get("selo") or projeto.get("titulo") or "o tratamento")
    a.setdefault("dor", t.get("dor", "você quer se cuidar com segurança"))
    a.setdefault("beneficio", t.get("beneficio", "um cuidado individualizado"))
    obj = (_cfg().get("objetivos") or {}).get(a["objetivo"]) or {}
    a.setdefault("botao", obj.get("botao", "Saiba mais"))
    a.setdefault("chamada", obj.get("chamada", "Toque em *Saiba mais* e agende sua avaliação"))
    return a


def roteiro(projeto: dict) -> dict:
    """Textos do vídeo (gancho nas versões, mensagens problema/solução/prova, CTA) a partir do serviço e da dor."""
    a = dados_anuncio(projeto)
    serv = a["servico"]
    ganchos = [g.format(dor=a["dor"], servico=serv) for g in _cfg()["copy"]["ganchos"]]
    return {
        "versoes": [{"nome": f"V{k + 1}", "hook": _batidas(g)} for k, g in enumerate(ganchos[:3])],
        "mensagens": [
            {"titulo": f"Já tentou de tudo / e *nada resolveu?*"},
            {"titulo": f"*{serv}* {a['beneficio']}", "apoio": "com avaliação e acompanhamento médico"},
            {"titulo": "Protocolo *individual*", "apoio": "Dr. Daniel Sampaio Mendes · CRM/SP 186.470"},
        ],
        "cta_antecipado": a["chamada"],
        "fechamento": {"frase": f"Seu próximo passo: / *{a['botao'].lower()}*", "cta": f"{a['botao']} ›"},
    }


def _batidas(frase: str) -> list:
    """Gancho longo vira duas batidas (quebra na vírgula ou no 'que'), cada uma lida em menos de 2 s."""
    if "," in frase:
        a, b = frase.split(",", 1)
        return [{"titulo": a.strip() + ","}, {"titulo": _destaque(b.strip())}]
    m = re.match(r"^(.{6,}?\bque)\s+(.+)$", frase)
    if m and len(frase.split()) > 7:
        return [{"titulo": m.group(1)}, {"titulo": _destaque(m.group(2))}]
    return [{"titulo": _destaque(frase)}]


def _curto(t: str, n: int = 40) -> str:
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0]


def _destaque(frase: str) -> str:
    """Põe a última palavra forte em dourado: 'Você sente que ...?' -> '... *incomoda?*'."""
    palavras = frase.split()
    if len(palavras) < 3:
        return frase
    return " ".join(palavras[:-1]) + f" *{palavras[-1]}*"


def copy(projeto: dict) -> list:
    """3 variações de copy do anúncio: texto principal, título, descrição e botão."""
    a = dados_anuncio(projeto)
    c = _cfg()["copy"]
    m = load("marca")
    serv = a["servico"]
    out = []
    for k in range(3):
        gancho = c["ganchos"][k % len(c["ganchos"])].format(dor=a["dor"], servico=serv)
        prova = c["provas"][k % len(c["provas"])]
        texto = (f"{gancho}\n\n{serv} {a['beneficio']}, sempre com avaliação individual e acompanhamento médico.\n\n"
                 f"{prova}\n\n👉 {re.sub(r'[*]', '', a['chamada'])}.\n\n"
                 f"📍 {m['clinica']['endereco']}\n{m['aviso_resultados']}\n{m['responsavel_tecnico']['curto']}")
        out.append({"variacao": "ABC"[k], "texto_principal": texto,
                    "titulo": _curto(c["titulos"][k % len(c["titulos"])].format(servico=serv)),
                    "descricao": c["descricao"], "botao": a["botao"]})
    return out


def revisar_copy(projeto: dict, variacoes: list) -> list:
    from .compliance import revisar
    textos = [v["texto_principal"] for v in variacoes] + [v["titulo"] for v in variacoes]
    return [x.linha() for x in revisar({**projeto, "legenda": variacoes[0]["texto_principal"]}, textos) if x.nivel == "erro"]


def salvar_copy(pasta: Path, projeto: dict) -> Path:
    vs = copy(projeto)
    linhas = ["# Copy do anúncio (3 variações para teste A/B no Meta Ads)", ""]
    for v in vs:
        linhas += [f"## Variação {v['variacao']}", "", "**Texto principal:**", "", v["texto_principal"], "",
                   f"**Título:** {v['titulo']}", f"**Descrição:** {v['descricao']}", f"**Botão:** {v['botao']}", ""]
    erros = revisar_copy(projeto, vs)
    if erros:
        linhas += ["## Revisor", ""] + [f"- {e}" for e in erros]
    arq = pasta / "saida" / "copy_anuncio.md"
    arq.parent.mkdir(exist_ok=True)
    arq.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return arq


def preparar(projeto: dict) -> None:
    """Antes de editar: texto sempre no topo (o botão do anúncio cobre a parte de baixo) e cartão final com o botão."""
    if not projeto.get("anuncio"):
        return
    projeto["posicao_texto"] = "topo"
    a = dados_anuncio(projeto)
    fech = dict(projeto.get("fechamento") or {})
    fech.setdefault("cta", f"{a['botao']} ›")
    projeto["fechamento"] = fech
    projeto.setdefault("cta_antecipado", a["chamada"])
