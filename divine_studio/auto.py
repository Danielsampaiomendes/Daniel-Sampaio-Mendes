"""Edição automática: dos brutos soltos em bruto/ para um projeto.yaml completo, pronto para gerar as prévias.

  python3 -m divine_studio auto projetos/2026-11-01_co2-no-corpo [--template george] [--previa]

Monta sozinho, seguindo as regras aprovadas:
  clipes      todos os vídeos de bruto/ na ordem dos nomes (ordem de gravação do iPhone); quem tem fala ganha
              corte limpo e legenda da fala; b-roll sem fala entra mudo e em câmera lenta suave
  duração     sem fala, pega o miolo dos clipes até ~30 s (alvo 25 a 40 s do Código Viral)
  hooks       3 do banco, um positivo, um de curiosidade e um negativo, ligados ao tema (hook: auto)
  textos      selo, mensagens, fechamento e CTA do tema em config/roteiros.yaml; com fala transcrita, as
              frases mais fortes da própria fala viram as mensagens, sincronizadas (na_fala)
  revisão     toda frase passa pelo revisor de compliance antes de entrar
O projeto.yaml anterior fica guardado em trabalho/projeto.yaml.anterior; o que você já preencheu à mão
(autorização de imagem, template, legenda, versões com hook escolhido) é mantido.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import yaml

from .config import load

VIDEO = {".mov", ".mp4", ".m4v", ".mkv", ".webm"}


def _norm(t: str) -> str:
    return unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()


def tema(titulo: str) -> tuple:
    """(chave, roteiro) do tema reconhecido no título, ou ('padrao', roteiro padrão)."""
    cfg = load("roteiros")
    t = _norm(titulo)
    melhor, tam = None, 0
    for chave, r in cfg["temas"].items():
        for nome in r.get("nomes", [chave]):
            n = _norm(nome)
            if re.search(rf"\b{re.escape(n)}", t) and len(n) > tam:
                melhor, tam = chave, len(n)
    return (melhor, cfg["temas"][melhor]) if melhor else ("padrao", cfg["padrao"])


def tem_fala(arquivo: Path) -> bool:
    """Áudio com voz: nível de fala alto e bem acima do ruído de fundo."""
    from .audio import ler_audio
    from .ingest import probe
    from .voz import medir_ruido
    p = probe(arquivo)
    if not p["audio"]:
        return False
    m = medir_ruido(ler_audio(arquivo, min(p["duracao"], 60)))
    return m["fala_db"] > -32 and m["snr_db"] > 14


def _ok(frase: str) -> bool:
    from .compliance import revisar
    return not [a for a in revisar({"legenda": "", "conteudo_medico": False}, [frase]) if a.nivel == "erro"]


def _destacar(frase: str) -> str:
    """Frase da fala -> título de tela: sem ponto final, quebra no meio e as últimas palavras em dourado."""
    ws = re.sub(r"[.,;:…!]+$", "", frase.strip()).split()
    if not ws:
        return frase
    n_dest = 2 if len(ws) >= 5 else 1
    corpo, dest = ws[:-n_dest], ws[-n_dest:]
    if len(ws) >= 6:
        from .corte import normalizar
        from .legendas import CONECTIVOS
        meio = len(corpo) // 2 + (1 if len(corpo) % 2 else 0)
        while meio > 1 and normalizar(corpo[meio - 1]) in CONECTIVOS:
            meio -= 1         # a linha de cima não termina em "o", "de", "que"
        corpo = corpo[:meio] + ["/"] + corpo[meio:]
    titulo = " ".join(corpo + [f"*{' '.join(dest)}*"])
    return titulo[0].upper() + titulo[1:]


def mensagens_da_fala(palavras: list, chave: str, maximo: int = 3) -> list:
    """As frases mais fortes da fala (curtas, com o tema ou palavras de benefício) viram mensagens na tela."""
    from .corte import marcar_remocoes
    roteiro_nomes = [_norm(n) for n in (load("roteiros")["temas"].get(chave, {}).get("nomes") or [])]
    fora = marcar_remocoes(palavras)          # sem "hum", sem a tentativa repetida
    texto = " ".join(w["texto"] for i, w in enumerate(palavras) if i not in fora)
    frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+", texto) if f.strip()]
    candidatas = []
    for k, f in enumerate(frases):
        n = len(f.split())
        nf = _norm(f)
        if not 3 <= n <= 11 or not _ok(f):
            continue
        if re.search(r"\b(agende|agenda|segue|seguir|manda|link|direct|whatsapp|comenta)\b", nf):
            continue          # CTA falado já está no fechamento
        pontos = 3 - abs(n - 6) * 0.3
        pontos += 2 * any(nm in nf for nm in roteiro_nomes)
        pontos += sum(1 for w in ("pele", "colageno", "cuidado", "tempo", "saude", "corpo", "estimul", "firmeza",
                                  "tratamento", "avaliacao", "resultado", "musculo") if w in nf)
        pontos -= 2 * bool(re.search(r"\b(eu|meu|minha|ne|tipo|entao)\b", nf))
        candidatas.append((pontos, k, f))
    escolhidas = sorted(sorted(candidatas, reverse=True)[:maximo], key=lambda c: c[1])
    out = []
    for _, _, f in escolhidas:
        na_fala = " ".join(f.split()[:4])
        out.append({"titulo": _destacar(f), "na_fala": re.sub(r"[.,;:!?…]", "", na_fala)})
    return out


def _modelo() -> dict:
    return yaml.safe_load((Path(__file__).parent / "modelo_projeto.yaml").read_text(encoding="utf-8")) or {}


def _do_modelo(campo: str, valor) -> bool:
    """O valor ainda é o exemplo do modelo_projeto.yaml (não foi preenchido por você)."""
    m = _modelo().get(campo)
    if campo == "versoes":
        return any(valor == {k: v for k, v in mv.items() if k != "nome"} for mv in m or [])
    return valor == m


def montar(projeto: dict, template: str | None = None, transcrever_fn=None, semente: int = 0) -> dict:
    """Devolve o projeto completo (dict) a partir dos brutos e do que já estava preenchido."""
    from .pacote import recortar_miolo
    cfg = load("roteiros")
    pasta = projeto["_pasta"]
    brutos = sorted(f for f in (pasta / "bruto").glob("*") if f.suffix.lower() in VIDEO and not f.name.startswith("."))
    if not brutos:
        raise SystemExit("Nenhum vídeo em bruto/. Solte os vídeos no painel (ou copie para a pasta bruto/).")
    titulo = projeto.get("titulo") or pasta.name
    chave, rot = tema(titulo)
    p = {k: v for k, v in projeto.items() if not k.startswith("_")}
    if template:
        p["template"] = template
    p.setdefault("template", "divine")
    if p["template"] == "tv":
        p["formato"] = "tv"
    elif p.get("formato", "reels") == "tv":
        p["formato"] = "reels"

    # ajustes feitos à mão num clipe (início, fim, foco, velocidade) continuam valendo
    antes = {c.get("arquivo"): c for c in projeto.get("clipes") or [] if isinstance(c, dict)}
    clipes, com_fala = [], []
    for b in brutos:
        c = dict(antes.get(f"bruto/{b.name}") or {"arquivo": f"bruto/{b.name}", "foco": [0.5, 0.4]})
        if tem_fala(b):
            com_fala.append(c)
        else:
            c.setdefault("mudo", True)
            c.setdefault("velocidade", float(cfg.get("velocidade_broll", 0.85)))
        clipes.append(c)
    print(f"• {len(brutos)} vídeo(s): {len(com_fala)} com fala, {len(brutos) - len(com_fala)} sem fala (b-roll)")
    if not com_fala:
        clipes = recortar_miolo({**p, "_pasta": pasta}, clipes, float(cfg.get("alvo_sem_fala_s", 30)))
    p["clipes"] = clipes

    pode_transcrever = transcrever_fn is not None
    if com_fala and pode_transcrever and p["template"] != "tv":
        p["corte_limpo"] = True
        p["legendas"] = True
        p["audio"] = {**(p.get("audio") or {}), "original": True, "trilha": True}
    elif com_fala:
        p["corte_limpo"] = False
        p["legendas"] = False
        if p["template"] != "tv":
            print("  aviso: sem transcrição (pip3 install faster-whisper), o vídeo falado sai sem corte limpo "
                  "e sem legenda da fala")
    else:
        p["audio"] = {**(p.get("audio") or {}), "original": False, "trilha": True}
        p["legendas"] = False
        p["corte_limpo"] = False

    # textos do tema
    p["selo"] = rot.get("selo", "")
    lista_cta = cfg["cta_antecipado"]
    obj = (load("legenda").get("objetivos") or {}).get(p.get("objetivo") or "")
    p["cta_antecipado"] = obj["cta_tela"] if obj else lista_cta[semente % len(lista_cta)]
    msgs = []
    if com_fala and pode_transcrever:
        palavras = []
        for c in com_fala:
            try:
                palavras += transcrever_fn(pasta / c["arquivo"])
            except SystemExit as e:
                print(f"  aviso: {e}")
                break
        msgs = mensagens_da_fala(palavras, chave, int(cfg.get("max_mensagens_da_fala", 3)))
        if msgs:
            print(f"• {len(msgs)} mensagem(ns) tirada(s) da própria fala")
    if not msgs:
        msgs = [dict(m) for m in rot.get("mensagens", []) if _ok(m["titulo"])]
    p["mensagens"] = msgs
    p["fechamento"] = {"frase": rot.get("fechamento", ""), "cta": rot.get("cta", "Agende sua avaliação")}
    if p["template"] == "tv":
        nome_trat = rot.get("selo") or titulo
        p["tv"] = {**(p.get("tv") or {}), "tratamento": (p.get("tv") or {}).get("tratamento", nome_trat.title())}
        # TV: painel esquerdo com as mensagens do tema (sem fala) + uma da marca para fechar o ciclo
        p["mensagens"] = [dict(m) for m in rot.get("mensagens", [])] + [dict(cfg["padrao"]["mensagens"][0])]

    # versões: mantém as que já têm hook escolhido; o resto sorteia do banco
    def escolhida(v):
        resto = {k: x for k, x in v.items() if k != "nome"}
        return (v.get("hook_id") or (v.get("hook") and v.get("hook") != "auto")) and not _do_modelo("versoes", resto)
    versoes = [v for v in p.get("versoes") or [] if escolhida(v)]
    n = 1 if p["template"] == "tv" else int(load("preferencias").get("versoes_por_video", 3))
    while len(versoes) < n:
        versoes.append({"nome": f"V{len(versoes) + 1}", "hook": "auto"})
    for k, v in enumerate(versoes[:n]):
        v["nome"] = "TV" if p["template"] == "tv" else f"V{k + 1}"
    p["versoes"] = versoes[:n]
    if p.get("legenda") and _do_modelo("legenda", p["legenda"]):
        p.pop("legenda")          # a do modelo: a legenda certa sai sozinha no editar
    if not p.get("remover_trechos"):
        p.pop("remover_trechos", None)
    return p


def salvar(projeto: dict, novo: dict) -> Path:
    pasta = projeto["_pasta"]
    arq = pasta / "projeto.yaml"
    (pasta / "trabalho").mkdir(exist_ok=True)
    if arq.exists():
        (pasta / "trabalho" / "projeto.yaml.anterior").write_text(arq.read_text(encoding="utf-8"), encoding="utf-8")
    cab = ("# Montado pela edição automática do Divine Studio. Ajuste à vontade e gere as prévias de novo.\n"
           "# *palavra* = dourado · \" / \" = quebra de linha · hook: auto sorteia do banco (fica guardado).\n")
    arq.write_text(cab + yaml.safe_dump(novo, allow_unicode=True, sort_keys=False, width=1000,
                                        default_flow_style=None), encoding="utf-8")
    return arq
