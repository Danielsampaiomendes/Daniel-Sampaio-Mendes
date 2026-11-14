"""Identidade visual e checklist do algoritmo em toda peça (config/identidade.yaml).

Vem das skills divine-algoritmo, divine-plano-crescimento e divine-postar-metricool:
  - checklist(pasta, versao): os itens que o Renato roda antes de agendar (abertura de identificação, quem fala,
    ganchos em camadas, "Já me segue" nos 5 s, pergunta no fim, duração, legenda no peito, palavra dourada,
    texto sem travessão e com maiúscula, legenda do post completa, compliance). Cada item diz o que ajustar.
  - capa(pasta, versao, t): capa do vídeo com o título do hook e a logo no topo, fora das zonas mortas.
  - conflito_feed(...): no máximo 1 post de feed por dia por perfil, contando collabs.
  - assinatura(conta) e pergunta_final(semente): usados pela legenda do post.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import yaml

from .config import load


def cfg() -> dict:
    try:
        return load("identidade")
    except FileNotFoundError:
        return {}


def _ler(arq: Path, padrao):
    try:
        return json.loads(Path(arq).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def _projeto(pasta: Path) -> dict:
    try:
        return yaml.safe_load((Path(pasta) / "projeto.yaml").read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}


def _fala(pasta: Path) -> list:
    from .sugestoes import _fala
    return _fala(Path(pasta)) or []


def _limpo(t) -> str:
    return re.sub(r"[*~/]", " ", str(t or "")).replace("  ", " ").strip()


def _hook(projeto: dict, versao: str, pasta: Path | None = None) -> list:
    """Batidas do hook da versão: as escritas no projeto, senão as do banco (hook_id ou o sorteado no hook: auto)."""
    vs = projeto.get("versoes") or []
    m = re.match(r"V(\d+)$", versao or "")
    v = vs[int(m.group(1)) - 1] if m and int(m.group(1)) - 1 < len(vs) else (vs[0] if vs else {})
    h = v.get("hook") or []
    if isinstance(h, dict):
        h = [h]
    batidas = [b for b in h if isinstance(b, dict) and b.get("titulo")] if isinstance(h, list) else []
    if batidas:
        return batidas
    hid = v.get("hook_id")
    if not hid and pasta is not None:
        hid = _ler(Path(pasta) / "trabalho" / "hooks_sorteados.json", {}).get(v.get("nome") or versao)
    if hid:
        try:
            from .hooks import batidas_do_hook
            return batidas_do_hook(str(hid))
        except (SystemExit, Exception):
            return []
    return []


def _texto_da_fala(fala: list, de: float, ate: float) -> str:
    return " ".join(str(w.get("texto", "")) for w in fala if de <= float(w.get("inicio", 0)) < ate).lower()


def assinatura(conta: str | None) -> str:
    a = (cfg().get("legenda_post") or {}).get("assinatura") or {}
    return a.get((conta or "").lstrip("@")) or a.get("dvmedicalspa") or ""


def pergunta_final(semente: int = 0) -> str:
    ps = (cfg().get("legenda_post") or {}).get("perguntas_finais") or []
    return ps[semente % len(ps)] if ps else ""


def problemas_de_texto(texto: str) -> list:
    """Travessão, linha começando com minúscula e isca de palavra ("comenta EU QUERO")."""
    c = cfg().get("texto") or {}
    out = []
    t = str(texto or "")
    sem_endereco = t.replace(str(load("marca")["clinica"]["endereco"]), "")   # o endereço oficial leva hífen
    if c.get("sem_travessao", True) and re.search(r"[—–]|\s-\s", sem_endereco):
        out.append("tem travessão (use vírgula, ponto ou dois-pontos)")
    if c.get("maiuscula_no_inicio", True):
        for ln in t.splitlines():
            s = re.sub(r"^[^\wÀ-ÿ]+", "", _limpo(ln))
            if s and s[0].isalpha() and s[0].islower():
                out.append(f"linha começa com minúscula: \"{s[:30]}\"")
                break
    for padrao in c.get("proibido") or []:
        if re.search(padrao, t, re.I):
            out.append("pede para comentar ou digitar uma palavra (isca): troque por pergunta de opinião")
            break
    return out


def _item(chave, titulo, ok, detalhe, grupo="algoritmo"):
    return {"id": chave, "titulo": titulo, "ok": ok, "detalhe": detalhe, "grupo": grupo}


def checklist(pasta: Path, versao: str = "V1") -> dict:
    """Checklist do algoritmo e da identidade visual (ok=True, False ou None quando não dá para saber)."""
    pasta = Path(pasta)
    p, c = _projeto(pasta), cfg()
    r = c.get("reels") or {}
    fala = _fala(pasta)
    linha = _ler(pasta / "trabalho" / f"linha_{versao}.json", {})
    hook = _hook(p, versao, pasta)
    hook_txt = " ".join(_limpo(b["titulo"]) for b in hook)
    itens = []
    tem_fala = len(fala) >= 6
    ini3 = _texto_da_fala(fala, 0, 3.5)
    ini8 = _texto_da_fala(fala, 0, 8)

    # 1. abertura de identificação (a pessoa se reconhece)
    ident = re.compile(r"\b(você|voce|vocês|se você|quem|sua|seu|eu também|médico também|igual a você)\b", re.I)
    ok1 = bool(ident.search(ini3) or ident.search(hook_txt)) if (tem_fala or hook_txt) else None
    itens.append(_item("identificacao", "Abertura de identificação nos 3 primeiros segundos", ok1,
                       "A pessoa se reconhece logo de cara." if ok1 else
                       "Abra com uma situação que a pessoa vive (\"Se você...\", \"Quem nunca...\", persona swap)."))
    # 2. quem fala e por que confiar (médico E quem resolve o problema)
    cred = re.compile(r"\b(médic[oa]|doutor|dr\.?|cirurgi[ãa]o|nutrologia|dermatolog|enfermeir[oa]|cl[íi]nica)\b", re.I)
    nome_na_tela = p.get("template") in ("daniel", "george")
    ok2 = bool(cred.search(ini8) or cred.search(hook_txt) or nome_na_tela) if (tem_fala or hook_txt) else None
    itens.append(_item("credencial", "Quem fala aparece como médico e como quem resolve o problema", ok2,
                       "Credencial dita ou nome na tela." if ok2 else
                       "Diga nos primeiros segundos: \"Como médico que trata..., esse é o erro que eu mais vejo.\" "
                       "(\"nutrólogo\" só com RQE na área)."))
    # 3. ganchos em camadas
    camadas = []
    if tem_fala and any(float(w.get("inicio", 9)) < 1.5 for w in fala):
        camadas.append("falado")
    if hook_txt and (not ini3 or _limpo(hook_txt).lower()[:25] not in ini3):
        camadas.append("escrito diferente da fala")
    efs = list(p.get("efeitos") or []) + list(linha.get("efeitos") or [])
    if any(float(e.get("inicio", 9) or 0) < 2 for e in efs if isinstance(e, dict)):
        camadas.append("visual")
    sons = list(p.get("sons") or []) + list(linha.get("sons") or [])
    if any(float(s.get("inicio", 9) or 0) < 1.5 for s in sons if isinstance(s, dict)) or p.get("sfx_automaticos", True) is not False:
        camadas.append("sonoro")
    minimo = int(r.get("ganchos_minimos", 3))
    itens.append(_item("ganchos", f"Gancho em pelo menos {minimo} camadas", len(camadas) >= minimo,
                       ("Camadas: " + ", ".join(camadas) + ".") if camadas else "Nenhuma camada de gancho detectada."
                       + ("" if len(camadas) >= minimo else " Retenção que despenca nos 10 s = só um tipo de gancho.")))
    # 4. "Já me segue" nos primeiros segundos
    ate = float(r.get("ja_me_segue_ate_s", 5))
    seg = re.compile(r"\b(me segue|segue|siga|seguir)\b", re.I)
    cta = p.get("cta_antecipado")
    cta_txt = cta if isinstance(cta, str) else (cta or {}).get("texto", "") if isinstance(cta, dict) else ""
    ok4 = bool(seg.search(_texto_da_fala(fala, 0, ate)) or seg.search(str(cta_txt)))
    itens.append(_item("ja_me_segue", f"\"Já me segue\" nos primeiros {ate:.0f} s", ok4,
                       "Chamada para seguir logo no começo." if ok4 else
                       "Fale ou escreva \"Já me segue\" nos primeiros segundos (CTA antecipado)."))
    # 5. pergunta no fim
    fim = max([float(w.get("fim", w.get("inicio", 0))) for w in fala] or [0])
    fala_fim = _texto_da_fala(fala, max(0, fim - 7), fim + 1)
    fech = str((p.get("fechamento") or {}).get("frase") or "")
    pergunta = re.compile(r"\?|\b(me conta|você já|e você|qual (é|desses|dessas)|o que você)\b", re.I)
    ok5 = bool(pergunta.search(fala_fim) or "?" in fech) if (tem_fala or fech) else None
    itens.append(_item("pergunta_fim", "Pergunta de opinião no fim", ok5,
                       "Fecha abrindo conversa." if ok5 else
                       "Termine com uma pergunta sobre a experiência da pessoa (nunca \"comenta PALAVRA\")."))
    # 6. duração
    at = _ler(pasta / "trabalho" / f"atencao_{versao}.json", {})
    dur = (len(at.get("curva") or []) * float(at.get("passo", 0.5))) if at.get("curva") else (fim if tem_fala else 0)
    lo, hi = (r.get("duracao_ideal_s") or [13, 35])[:2]
    itens.append(_item("duracao", f"Duração entre {lo} e {hi} s", (lo <= dur <= hi) if dur else None,
                       f"{dur:.0f} s." if dur else "Gere a prévia para medir a duração.", "algoritmo"))

    # identidade visual
    leg = p.get("legendas")
    pos = None
    if leg:
        from .legendas import _cfg as leg_cfg
        try:
            pos = float(leg_cfg(p).get("posicao", 0.66))
        except Exception:
            pos = None
    faixa = r.get("legenda_altura") or {"min": 0.56, "max": 0.78}
    itens.append(_item("legenda_peito", "Legenda na altura do peito (nunca no rosto nem na faixa de baixo)",
                       (faixa["min"] <= pos <= faixa["max"]) if pos is not None else None,
                       f"Posição {pos:.2f} da altura." if pos is not None else "Legenda da fala desligada.", "identidade"))
    blocos_txt = [b["titulo"] for b in hook] + [m.get("titulo", "") for m in p.get("mensagens") or [] if isinstance(m, dict)]
    sem_dourado = [_limpo(t)[:28] for t in blocos_txt if t and "*" not in t]
    itens.append(_item("palavra_dourada", "1 palavra-chave dourada por frase (*palavra*)", not sem_dourado if blocos_txt else None,
                       "Todas as frases têm destaque." if not sem_dourado else "Sem destaque: " + "; ".join(sem_dourado[:3]),
                       "identidade"))
    probs = []
    for t in blocos_txt + [cta_txt, fech]:
        probs += problemas_de_texto(t)
    itens.append(_item("texto", "Texto na tela: maiúscula, sem travessão, sem isca", not probs,
                       "Tudo certo." if not probs else "; ".join(sorted(set(probs))[:3]), "identidade"))
    capa_arq = pasta / "saida" / f"capa_{versao}.jpg"
    itens.append(_item("capa", "Capa com título do hook e logo no topo", capa_arq.exists(),
                       "Capa pronta." if capa_arq.exists() else "No Estúdio, pare num quadro bonito (boca fechada, "
                       "sorrindo) e toque em 📸 Capa neste quadro.", "identidade"))

    # legenda do post
    legenda = ""
    if (pasta / "saida" / "legenda.txt").exists():
        legenda = (pasta / "saida" / "legenda.txt").read_text(encoding="utf-8")
    legenda = legenda or str(p.get("legenda") or "")
    itens.append(_item("legenda_post", "Legenda do post no padrão", *_legenda_ok(legenda, p), grupo="legenda"))

    # compliance (prevalece sobre tudo)
    try:
        from .compliance import revisar
        erros = [a for a in revisar({**p, "_pasta": pasta}) if a.nivel == "erro"]
        itens.append(_item("compliance", "Compliance CFM e Anvisa", not erros,
                           "Sem promessa, prazo, percentual, medicamento ou antes e depois." if not erros
                           else "; ".join(a.trecho for a in erros[:3]), "compliance"))
    except Exception:
        pass
    ok = sum(1 for i in itens if i["ok"] is True)
    conta = sum(1 for i in itens if i["ok"] is not None)
    return {"versao": versao, "itens": itens, "ok": ok, "total": conta}


def _legenda_ok(legenda: str, projeto: dict) -> tuple:
    if not legenda.strip():
        return None, "A legenda sai na primeira prévia (ou toque em Gerar)."
    c = (cfg().get("legenda_post") or {})
    faltas = []
    primeira = legenda.strip().splitlines()[0]
    if len(primeira) > int(c.get("primeira_linha_max", 125)):
        faltas.append(f"1ª linha com {len(primeira)} caracteres (máx. {c.get('primeira_linha_max', 125)} antes do \"mais\")")
    corpo = legenda.split("#")[0]
    if "?" not in corpo:
        faltas.append("falta a pergunta de opinião no fim")
    n = len(re.findall(r"(?<!\w)#\w+", legenda))
    if projeto.get("marca") != "pessoal":
        if not 8 <= n <= 12:
            faltas.append(f"{n} hashtags (use 8 a 12)")
        if "📍" not in legenda:
            faltas.append("falta o 📍 endereço")
        if "variam de pessoa para pessoa" not in legenda:
            faltas.append("falta \"Resultados variam de pessoa para pessoa.\"")
        if "CRM" not in legenda:
            faltas.append("falta a assinatura com CRM")
    faltas += problemas_de_texto(corpo)
    return (not faltas), ("Gancho, pergunta, endereço, aviso, assinatura e hashtags." if not faltas else "; ".join(faltas))


# ---------------------------------------------------------------- capa

def capa(pasta: Path, versao: str, t: float | None = None, arquivo: str | None = None) -> Path:
    """Capa 1080x1920: quadro do vídeo em `t`, degradê escuro no topo, logo e título do hook dentro da área segura."""
    from PIL import Image, ImageDraw

    from . import brand
    from .fonts import combinacao
    from .text import Estilo, render
    from .config import cor, hexrgb

    pasta = Path(pasta)
    c = cfg().get("capa") or {}
    W, H = int(c.get("largura", 1080)), int(c.get("altura", 1920))
    t = float(c.get("momento_s", 1.0) if t is None else t)
    if not arquivo:
        cands = sorted((pasta / "saida").glob(f"*_{versao}_*.mp4"), key=lambda f: ("_PREVIA" in f.name, -f.stat().st_mtime))
        if not cands:
            raise ValueError(f"não achei o vídeo da {versao}: gere a prévia ou a final antes")
        fonte = cands[0]
    else:
        fonte = pasta / arquivo
        if not fonte.resolve().is_relative_to(pasta.resolve()) or not fonte.exists():
            raise ValueError("arquivo do vídeo inválido")
    base = pasta / "trabalho" / "base.mov"            # o quadro limpo, sem hook e legenda já gravados
    if not arquivo and base.exists():
        dur = _ler(pasta / "trabalho" / "base.json", {}).get("duracao")
        if not dur or t < float(dur):
            fonte = base
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.2f}", "-i", str(fonte), "-frames:v", "1",
                        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}",
                        "-f", "image2", "-c:v", "png", "-"], capture_output=True)
    if not r.stdout:
        raise ValueError("não consegui tirar o quadro do vídeo")
    import io
    img = Image.open(io.BytesIO(r.stdout)).convert("RGBA")
    seg = load("marca")["area_segura"]
    # degradê escuro só atrás do título (legibilidade sem caixa)
    alfa = float(c.get("escurecer_topo", 0.55))
    grad = Image.linear_gradient("L").rotate(180).resize((W, int(H * 0.42)))
    grad = grad.point(lambda v: int(v * alfa))
    sombra = Image.new("RGBA", (W, grad.height), hexrgb(load("marca")["cores"]["fundo"]) + (0,))
    sombra.putalpha(grad)
    img.alpha_composite(sombra, (0, 0))
    y = int(seg["topo"])
    logo = brand.horizontal(int(c.get("logo_altura", 54)))
    img.alpha_composite(logo, ((W - logo.width) // 2, y))
    y += logo.height + 26
    p = _projeto(pasta)
    hook = _hook(p, versao, pasta)
    titulo = " / ".join(b["titulo"] for b in hook) or str(p.get("titulo") or "")
    vs = p.get("versoes") or []
    m = re.match(r"V(\d+)$", versao or "")
    codigo = ((vs[int(m.group(1)) - 1] if m and int(m.group(1)) - 1 < len(vs) else {}) or {}).get("fontes") or "B"
    try:
        combo = combinacao(str(codigo))
    except Exception:
        combo = combinacao("B")
    tam = float(c.get("titulo_tamanho", 74))
    tit = Estilo.de_config(combo["titulo"], tam, cor("off_white"))
    dest = Estilo.de_config(combo["destaque"], tam, cor("dourado"))
    larg = W - int(seg["esquerda"]) - int(seg["direita"]) - 40
    bloco = render(titulo, tit, dest, largura_max=larg)
    limite = H - int(seg["base"]) - y
    if bloco.height > limite:
        bloco.thumbnail((larg, limite))
    img.alpha_composite(bloco, ((W - bloco.width) // 2, y))
    ImageDraw.Draw(img)
    destino = pasta / "saida" / f"capa_{versao}.jpg"
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(destino, "JPEG", quality=92)
    return destino


# ---------------------------------------------------------------- calendário

def _perfis_ocupados(conta: str | None) -> set:
    conta = (conta or "").lstrip("@")
    col = ((cfg().get("calendario") or {}).get("collabs") or {}).get(conta) or []
    return {conta, *[x.lstrip("@") for x in col]} - {""}


def conflito_feed(projeto: str, versao: str, data: str, pecas: list | None = None) -> list:
    """Outras peças de feed no mesmo dia num perfil que esta peça ocupa (contando collabs). Vazia = dia livre."""
    from . import aprendizado
    cal = cfg().get("calendario") or {}
    formatos = set(cal.get("formatos_feed") or [])
    pecas = aprendizado.todas_publicacoes() if pecas is None else pecas
    esta = next((x for x in pecas if x.get("projeto") == projeto and x.get("versao") == versao), None)
    conta = (esta or {}).get("conta")
    if esta is None:
        from .instagram import conta_do_projeto
        conta = conta_do_projeto(_projeto(Path(aprendizado.PROJETOS) / projeto))
    minha = _perfis_ocupados(conta)
    out = []
    for x in pecas:
        if (x.get("projeto"), x.get("versao")) == (projeto, versao):
            continue
        dia = x.get("data_agendada") if x.get("status") == "agendado" else (x.get("data_postagem") if x.get("status") == "postado" else None)
        if not dia or str(dia)[:10] != str(data)[:10]:
            continue
        if x.get("rede") in ("tv", "consulta") or x.get("na_tv") or x.get("versao") == "stories":
            continue
        if formatos and x.get("formato") not in formatos and x.get("tipo") not in formatos and x.get("versao") not in formatos:
            continue
        comum = minha & _perfis_ocupados(x.get("conta"))
        if comum:
            out.append(f"{x.get('titulo', x.get('projeto'))} ({x.get('versao')}) já ocupa o feed de @{sorted(comum)[0]} em {str(data)[:10]}")
    return out
