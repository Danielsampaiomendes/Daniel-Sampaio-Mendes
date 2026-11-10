"""Pontos de atenção da linha do tempo: o "!" que mostra onde a edição pode quebrar o engajamento.

Funciona como o corretor de um editor de texto: cada regra (config/alertas.yaml) olha a fala transcrita, a curva de
atenção da última prévia, os efeitos e a leitura do Higgsfield, e devolve pontos com o segundo exato, o nível e o que
fazer. Nada muda o vídeo sozinho: cada ponto traz ações de um toque (pôr um efeito, cortar a frase, dublar o trecho,
regravar) e pode ser ignorado (fica guardado em `alertas_ignorados` no projeto.yaml, não volta a aparecer).

Níveis (config/alertas.yaml > niveis):
  bloqueia  compliance CFM/Anvisa na fala: precisa sair ou ser regravado antes de postar
  confirmar compliance na fala que pode ser informação correta: trava até você conferir, tirar ou dublar
  refazer   pode quebrar o engajamento (atenção cai, abertura lenta, fim sem pedido)
  dublar    a fala está difícil de entender ou recomeçada: regrave só aquele trecho por cima
  conferir  vale uma olhada (fala corrida demais, efeitos demais)

Regra nova = função `_r_<nome>(ctx, cfg)` aqui + entrada em config/alertas.yaml. Uma regra que der erro é pulada
(as outras continuam) e o motivo aparece em `avisos`, para o painel nunca travar por causa de um ponto de atenção.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml

from .config import load

ORDEM = {"bloqueia": 0, "confirmar": 1, "refazer": 2, "dublar": 3, "conferir": 4}
TRAVAM = ("bloqueia", "confirmar")         # compliance: sempre na tela, nunca "Ignorar"


def _cfg() -> dict:
    try:
        return load("alertas")
    except OSError:
        return {}


def _ler_json(arq: Path, padrao):
    try:
        return json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def _id(regra: str, chave) -> str:
    """Id estável: frase (texto) ou segundo. Ignorar um ponto vale até a fala ou o momento mudarem."""
    if isinstance(chave, str):
        return f"{regra}:{hashlib.sha1(chave.strip().lower().encode()).hexdigest()[:8]}"
    return f"{regra}:{round(float(chave))}"


def _ponto(regra: str, cfg: dict, chave, t0: float, t1: float, titulo: str, texto: str, acoes: list,
           fonte: str = "app") -> dict:
    return {"id": _id(regra, chave), "regra": regra, "nivel": cfg.get("nivel", "conferir"),
            "t0": round(max(0.0, float(t0)), 2), "t1": round(max(float(t0), float(t1)), 2),
            "titulo": titulo, "texto": texto, "acoes": acoes, "fonte": fonte}


def _dublar(fr: dict, texto: str | None = None) -> dict:
    """Ação 'dublar': abre o gravador no início da frase, com a copy pronta e só aquele trecho no mudo."""
    return {"tipo": "dublar", "rotulo": "🎙 Dublar este trecho", "inicio": round(fr["inicio"], 2),
            "fim": round(fr["fim"], 2), "copy": texto or fr["texto"]}


def _cortar(fr: dict) -> dict:
    return {"tipo": "cortar_frase", "rotulo": "✂ Tirar esta frase", "frase": fr["texto"]}


# ---------------------------------------------------------------- regras

def _r_compliance_fala(ctx, cfg):
    """Mesma regra que trava o ✓ Aprovar, a final e o "postar sozinho" (compliance.achados_na_fala).
    Erro (percentual, "você vai perder 5 kg"): vermelho, não se ignora nem se confirma.
    Confira (prazo ou quantidade que pode ser informação correta): laranja, trava até você conferir, tirar ou dublar."""
    from .compliance import achados_na_fala
    marcadas = {" ".join(str(x).lower().split()) for x in ctx["projeto"].get("remover_trechos") or []}
    cfg_conf = ctx.get("regras", {}).get("compliance_confira") or {"nivel": "confirmar"}
    out = []
    for x in achados_na_fala(ctx["fala"], ctx["projeto"]):
        if x["conferido"]:
            continue
        fr, erro = x["frase"], x["achado"]
        partes = fr.get("partes") or [fr["texto"]]
        cortar = {"tipo": "cortar_frase", "rotulo": "✂ Tirar esta frase" if len(partes) == 1 else "✂ Tirar as duas frases",
                  "frase": partes[0], "frases": partes}
        if all(" ".join(p.lower().split()) in marcadas for p in partes):
            # marcada para sair e ainda está na prévia: ou falta gerar a prévia, ou o corte não achou a frase
            texto = (f"\"{fr['texto'][:90]}\" está marcada para sair, mas continua na última prévia. Gere as prévias de "
                     "novo; se ela continuar, a frase atravessa dois clipes: use ✂ Dividir na linha do tempo ou duble "
                     "sem ela.")
        elif x["nivel"] == "erro":
            texto = f"\"{fr['texto'][:90]}\": {erro.motivo} Corte a frase ou regrave sem ela."
        else:
            texto = (f"\"{fr['texto'][:90]}\" pode soar como promessa ({erro.motivo.split('.')[0]}). Se for informação "
                     "(recuperação, retorno, como é a consulta), toque em ✓ Conferi. Se for promessa de resultado, tire "
                     "a frase ou duble sem ela. Até lá o ✓ Aprovar e o postar sozinho ficam travados.")
        acoes = [cortar, _dublar(fr, "")]
        if x["nivel"] == "confirmar":
            acoes.append({"tipo": "conferir_fala", "rotulo": "✓ Conferi: é informação, não promessa",
                          "id_frase": x["id"], "frase": fr["texto"], "motivo": erro.motivo})
        p = _ponto("compliance_fala", cfg if x["nivel"] == "erro" else cfg_conf, fr["texto"], fr["inicio"], fr["fim"],
                   "A fala tem algo que o CFM/Anvisa não permite" if x["nivel"] == "erro" else
                   "Confira esta frase: pode ser promessa", texto, acoes)
        out.append(p)
    return out


def _r_fala_sem_revisor(ctx, cfg):
    """O vídeo tem fala, mas não há fala transcrita: o revisor de compliance não leu o que se ouve. Vermelho, não se
    ignora: o ✓ Aprovar, a final e o postar ficam travados até a transcrição existir (compliance.video_falado)."""
    from .compliance import video_falado
    if ctx["fala"] or not video_falado(ctx["projeto"]):
        return []
    return [_ponto("fala_sem_revisor", cfg, "fala_sem_revisor", 0, 0.5, "A fala deste vídeo ainda não foi lida",
                   "O vídeo tem fala, mas ela não foi transcrita (a transcrição não está instalada ou falhou). Sem o texto, "
                   "o revisor de compliance não confere promessa, prazo nem porcentagem no que é dito, então o ✓ Aprovar, "
                   "a final e o postar ficam travados. Instale a transcrição e gere as prévias de novo.",
                   [{"tipo": "instalar_fala", "rotulo": "🎤 Instalar a transcrição"}])]


def _r_queda_atencao(ctx, cfg):
    out = []
    for i, z in enumerate((ctx["atencao"] or {}).get("zonas") or []):
        if z["fim"] - z["ini"] < float(cfg.get("min_s", 2.0)):
            continue
        acoes = [{"tipo": "efeito", "rotulo": "✦ " + z["proposta"][:48], "efeito": z["acao"]}]
        fr = _frase_em(ctx, z["ini"])
        if fr:
            acoes.append(_cortar(fr))
        # id pela frase (não pelo segundo): depois de um corte, o "Ignorar" continua valendo para o mesmo trecho
        out.append(_ponto("queda_atencao", cfg, fr["texto"] if fr else z["ini"], z["ini"], z["fim"],
                          f"A atenção pode cair aqui ({z['causa']})",
                          f"Entre {z['ini']:.0f} e {z['fim']:.0f} s pouca coisa muda. Proposta: {z['proposta']}.", acoes))
    return out


def _r_abertura(ctx, cfg_lenta, cfg_apres):
    from .sugestoes import ABERTURA_FRACA
    fr = ctx["frases"]
    if not fr:
        return []
    p = fr[0]
    out = []
    if cfg_apres.get("ligada", True) and ABERTURA_FRACA.search(p["texto"]):
        forte = ctx.get("frase_forte")
        texto = "Nos primeiros 3 segundos a pessoa decide se fica. " + \
                (f"Abra direto com: \"{forte}\" e se apresente depois." if forte else "Abra com a frase mais forte.")
        out.append(_ponto("apresentacao_primeiro", cfg_apres, p["texto"], 0, min(p["fim"], 3.0),
                          "O vídeo começa pela apresentação, não pelo assunto", texto,
                          [{"tipo": "regravar", "rotulo": "🎬 Regravar a abertura", "copy": forte or ""},
                           _cortar(p)]))
    elif cfg_lenta.get("ligada", True) and p["fim"] - p["inicio"] > float(cfg_lenta.get("max_s", 3.0)) + 0.5:
        out.append(_ponto("abertura_lenta", cfg_lenta, p["texto"], 0, p["fim"],
                          f"A primeira frase leva {p['fim'] - p['inicio']:.0f} s",
                          f"Diga em até {cfg_lenta.get('max_s', 3)} s, sem pausa no meio. Dublar não encurta o vídeo "
                          "(a imagem continua com o mesmo tempo): regrave a abertura mais curta.",
                          [{"tipo": "regravar", "rotulo": "🎬 Regravar a abertura", "copy": p["texto"]}]))
    return out


def _r_fala_incerta(ctx, cfg):
    out, pal = [], ctx["fala"]
    lim, minimo = float(cfg.get("conf_min", 0.55)), int(cfg.get("min_palavras", 2))
    for fr in ctx["frases"]:
        ws = pal[fr["i0"]:fr["i1"] + 1]
        ruins = [w for w in ws if "conf" in w and float(w["conf"]) < lim]
        if len(ruins) >= minimo:
            palavras = ", ".join(f"\"{w['texto']}\"" for w in ruins[:4])
            out.append(_ponto("fala_incerta", cfg, fr["texto"], fr["inicio"], fr["fim"],
                              "Possivelmente dublar: trecho difícil de entender",
                              f"O app não teve certeza de {palavras}. Se ele não entendeu, quem assiste sem fone também "
                              "pode não entender (e a legenda pode sair errada). Confira a legenda ou dublar o trecho.",
                              [_dublar(fr), {"tipo": "corrigir", "rotulo": "Aa Corrigir a legenda", "inicio": fr["inicio"]}]))
    return out


def _r_voz_baixa(ctx, cfg):
    vdb = (ctx["atencao"] or {}).get("voz_db") or []
    passo = float((ctx["atencao"] or {}).get("passo", 0.5))
    if not vdb or not ctx["frases"]:
        return []
    niveis = []
    for fr in ctx["frases"]:
        a, b = int(fr["inicio"] / passo), max(int(fr["inicio"] / passo) + 1, int(fr["fim"] / passo))
        trecho = [x for x in vdb[a:b] if x is not None]
        niveis.append(sorted(trecho)[len(trecho) // 2] if trecho else None)
    validos = sorted(x for x in niveis if x is not None)
    if len(validos) < 3:
        return []
    mediana = validos[len(validos) // 2]
    out = []
    for fr, n in zip(ctx["frases"], niveis):
        if n is not None and n < mediana - float(cfg.get("abaixo_da_mediana_db", 8)):
            out.append(_ponto("voz_baixa", cfg, fr["texto"], fr["inicio"], fr["fim"],
                              "Possivelmente dublar: a voz fica baixa aqui",
                              f"Esta frase está {mediana - n:.0f} dB abaixo do resto da fala (longe do microfone ou de "
                              "costas). Dublar o trecho deixa o som igual ao resto.", [_dublar(fr)]))
    return out


def _norm(t: str) -> str:
    return re.sub(r"[^\wà-ú]", "", str(t).lower())


def _r_recomeco(ctx, cfg):
    n, out, fr = int(cfg.get("palavras_iguais", 3)), [], ctx["frases"]
    for a, b in zip(fr, fr[1:]):
        wa, wb = [_norm(x) for x in a["texto"].split()][:n], [_norm(x) for x in b["texto"].split()][:n]
        if len(wa) == n and wa == wb:
            out.append(_ponto("recomeco", cfg, a["texto"], a["inicio"], b["fim"],
                              "Possivelmente dublar: a frase foi recomeçada",
                              f"\"{a['texto'][:60]}\" e logo depois \"{b['texto'][:60]}\". Fica só a melhor: tire a "
                              "primeira ou duble as duas numa frase só.", [_cortar(a), _dublar(b)]))
    return out


def _r_fala_rapida(ctx, cfg):
    out, pal = [], ctx["fala"]
    for fr in ctx["frases"]:
        dur = fr["fim"] - fr["inicio"]
        nw = fr["i1"] - fr["i0"] + 1
        if dur >= float(cfg.get("min_s", 2.5)) and nw / dur > float(cfg.get("max_palavras_s", 4.3)):
            out.append(_ponto("fala_rapida", cfg, fr["texto"], fr["inicio"], fr["fim"],
                              "Fala muito corrida",
                              f"{nw / dur:.1f} palavras por segundo: a legenda passa rápido demais para ler. "
                              "Deixe só uma ideia neste trecho (tire a frase) ou regrave mais devagar. Dublar mais "
                              "devagar não cabe no mesmo tempo da imagem.",
                              [_cortar(fr), {"tipo": "regravar", "rotulo": "🎬 Regravar mais devagar", "copy": fr["texto"]}]))
    return out


def _r_efeitos_demais(ctx, cfg):
    tempos = sorted(float(e.get("inicio", 0)) for e in ctx["efeitos"])
    janela, maximo = 10.0, int(cfg.get("max_por_10s", 4))
    for i, t in enumerate(tempos):
        dentro = [x for x in tempos[i:] if x < t + janela]
        if len(dentro) > maximo:
            return [_ponto("efeitos_demais", cfg, t, t, t + janela, f"{len(dentro)} efeitos em 10 s",
                           "Mais efeitos do que a fala pede: fica com cara de efeito aleatório. Tire alguns ou toque em "
                           "➖ Menos efeitos na conversa da versão (vale para os próximos vídeos).",
                           [{"tipo": "abrir", "rotulo": "Ver os efeitos", "inicio": t}])]
    return []


def _r_sem_pedido_final(ctx, cfg):
    from .sugestoes import PEDIDO
    fr = ctx["frases"]
    if len(fr) < 2 or PEDIDO.search(" ".join(f["texto"] for f in fr[-2:])):
        return []
    if PEDIDO.search(str((ctx["projeto"].get("fechamento") or {}).get("cta") or "")) and not cfg.get("exigir_na_fala"):
        return []                       # o cartão final já pede (ex.: "Agende sua avaliação")
    ult = fr[-1]
    return [_ponto("sem_pedido_final", cfg, ult["texto"], ult["inicio"], ult["fim"], "A fala termina sem pedir nada",
                   "Grave uma frase final curta, por exemplo: \"Salva para lembrar\" ou \"Agende sua avaliação\".",
                   # sem "fim": a gravação entra logo depois da última palavra e pode seguir por cima do cartão
                   # final (cli._com_dublagem estende a voz até o fim do vídeo); a voz original não fica muda
                   [{"tipo": "dublar", "rotulo": "🎙 Gravar o pedido final", "inicio": round(ult["fim"] + 0.15, 2),
                     "fim": None, "copy": "Se isso faz sentido para você, agende sua avaliação."}])]


def _r_higgsfield_queda(ctx, cfg):
    """Quedas apontadas pelo Virality Predictor (quando a leitura veio em JSON com 'quedas'), só da prévia atual."""
    out = []
    velha = (ctx.get("higgsfield_info") or {}).get("velha")
    if velha and not ctx["higgsfield"]:
        return [_ponto("higgsfield_queda", {"nivel": "conferir"}, f"velha:{velha.get('id')}", 0, 0.5,
                       "A leitura do Higgsfield é de uma prévia antiga",
                       "Depois dela o vídeo mudou (frase tirada, novo render), então os segundos não batem mais e as "
                       "quedas dela não aparecem aqui. Se quiser a leitura desta prévia, peça de novo em "
                       "💡 Para a próxima (o custo em créditos aparece antes).",
                       [{"tipo": "abrir", "rotulo": "Ok", "inicio": 0}], fonte="Higgsfield")]
    for q in ctx["higgsfield"]:
        try:
            t = float(q.get("t", q.get("inicio")))
        except (TypeError, ValueError):
            continue
        out.append(_ponto("higgsfield_queda", cfg, t, t, t + 1.5, "Higgsfield: a atenção cai aqui",
                          str(q.get("motivo") or "O Virality Predictor apontou uma queda neste segundo.")[:300],
                          [{"tipo": "abrir", "rotulo": "Ir para o trecho", "inicio": t}], fonte="Higgsfield"))
    return out


def _r_ancora_perdida(ctx, cfg):
    """Dublagem ou efeito cuja frase saiu do vídeo depois de um corte (cli._reposicionar_ancoras): ficou de fora
    desta edição, nada foi apagado. Você decide: gravar de novo no lugar novo ou deixar sem."""
    out = []
    for x in ctx.get("ancoras_perdidas") or []:
        t = float(x.get("inicio") or 0)
        nome = "A dublagem" if x.get("tipo") == "dublagem" else f"O efeito {x.get('efeito') or ''}".strip()
        out.append(_ponto("ancora_perdida", cfg, f"{x.get('tipo')}:{x.get('palavras')}", t, t + 1.0,
                          f"{nome} ficou de fora", f"Ela estava presa à fala \"{x.get('palavras')}\", que saiu do vídeo "
                          "no último corte. Nada foi apagado: grave de novo no trecho certo ou ignore.",
                          [{"tipo": "abrir", "rotulo": "Ir para o trecho", "inicio": t}]))
    return out


# ---------------------------------------------------------------- contexto e execução

def _frase_em(ctx, t: float):
    return next((f for f in ctx["frases"] if f["inicio"] - 0.2 <= t <= f["fim"] + 0.2), None)


def _higgsfield(nome: str, pasta: Path | None = None, versao: str = "V1") -> dict:
    """Quedas do Virality Predictor que valem para a prévia ATUAL desta versão.

    Uma leitura só vale para o arquivo que foi analisado: mesma versão e mesmo render (o arquivo não mudou e não há
    prévia mais nova da versão). Se você tirou uma frase e gerou de novo, os segundos mudaram: a leitura antiga vira
    um aviso cinza ("peça de novo"), nunca um "!" no segundo errado."""
    out = {"quedas": [], "velha": None}
    try:
        from . import higgsfield as hf
        itens = [x for x in hf.listar(projeto=nome) if x.get("alvo") == "virality_predictor"
                 and x.get("status") == "pronto" and isinstance(x.get("analise"), dict)]
    except Exception:
        return out
    for x in itens:                                   # listar() já vem do mais novo para o mais velho
        ent = x.get("entrada") or {}
        arq = str(ent.get("arquivo") or "")
        m = re.search(r"_(V\d+|TV|IA)_", Path(arq).name + "_")
        if not m or m.group(1) != versao:
            continue
        valida = False
        if pasta is not None:
            f = Path(pasta) / arq
            mais_novas = [g for g in (Path(pasta) / "saida").glob(f"*_{versao}_*.mp4")
                          if f.exists() and g.stat().st_mtime > f.stat().st_mtime + 1] if (Path(pasta) / "saida").exists() else []
            mesmo = f.exists() and (ent.get("mtime") is None or abs(f.stat().st_mtime - float(ent["mtime"])) < 2)
            valida = mesmo and not mais_novas
        if valida:
            out["quedas"] = [q for q in x["analise"].get("quedas") or [] if isinstance(q, dict)]
            return out
        out["velha"] = out["velha"] or x
    return out


def contexto(pasta: Path, versao: str = "V1") -> dict:
    from .roteirista import frases, ganchos_da_fala
    pasta = Path(pasta)
    projeto = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    fala = _ler_json(pasta / "trabalho" / "fala_base.json", [])   # sem correções: "tirar a frase" usa o texto bruto
    linha = _ler_json(pasta / "trabalho" / f"linha_{versao}.json", {})
    forte = ""
    try:
        g = ganchos_da_fala(fala, 1)
        forte = re.sub(r"[*/]", "", g[0][0]["titulo"]).strip() if g else ""
    except Exception:
        pass
    return {"projeto": projeto, "fala": fala, "frases": frases(fala) if fala else [], "frase_forte": forte,
            "atencao": _ler_json(pasta / "trabalho" / f"atencao_{versao}.json", {}),
            "efeitos": list(projeto.get("efeitos") or []) + list(linha.get("efeitos") or []),
            "higgsfield_info": _higgsfield(pasta.name, pasta, versao),
            "ancoras_perdidas": _ler_json(pasta / "trabalho" / "ancoras_perdidas.json", [])}


def gerar(pasta: Path, versao: str = "V1", nome: str = "") -> dict:
    """Pontos de atenção de uma versão, do mais grave para o mais leve, sem os que você ignorou."""
    cfg = _cfg()
    regras = cfg.get("regras") or {}
    ctx = contexto(pasta, versao)
    ctx["regras"] = regras
    if nome and nome != Path(pasta).name:
        ctx["higgsfield_info"] = _higgsfield(nome, pasta, versao)
    ctx["higgsfield"] = ctx["higgsfield_info"]["quedas"]
    ligada = lambda r: (regras.get(r) or {}).get("ligada", True)
    execucao = [
        ("compliance_fala", lambda: _r_compliance_fala(ctx, regras.get("compliance_fala") or {})),
        ("fala_sem_revisor", lambda: _r_fala_sem_revisor(ctx, regras.get("fala_sem_revisor") or {"nivel": "bloqueia"})),
        ("queda_atencao", lambda: _r_queda_atencao(ctx, regras.get("queda_atencao") or {})),
        ("abertura", lambda: _r_abertura(ctx, regras.get("abertura_lenta") or {}, regras.get("apresentacao_primeiro") or {})),
        ("fala_incerta", lambda: _r_fala_incerta(ctx, regras.get("fala_incerta") or {})),
        ("voz_baixa", lambda: _r_voz_baixa(ctx, regras.get("voz_baixa") or {})),
        ("recomeco", lambda: _r_recomeco(ctx, regras.get("recomeco") or {})),
        ("fala_rapida", lambda: _r_fala_rapida(ctx, regras.get("fala_rapida") or {})),
        ("efeitos_demais", lambda: _r_efeitos_demais(ctx, regras.get("efeitos_demais") or {})),
        ("sem_pedido_final", lambda: _r_sem_pedido_final(ctx, regras.get("sem_pedido_final") or {})),
        ("higgsfield_queda", lambda: _r_higgsfield_queda(ctx, regras.get("higgsfield_queda") or {})),
        ("ancora_perdida", lambda: _r_ancora_perdida(ctx, regras.get("ancora_perdida") or {})),
    ]
    pontos, avisos = [], []
    for nome_regra, f in execucao:
        if nome_regra != "abertura" and not ligada(nome_regra):
            continue
        try:
            pontos += f()
        except Exception as e:                       # uma regra com defeito não derruba as outras nem o painel
            avisos.append(f"regra {nome_regra} pulada: {e}")
    ignorados = set(ctx["projeto"].get("alertas_ignorados") or [])
    vistos, out = set(), []
    for p in sorted(pontos, key=lambda p: (ORDEM.get(p["nivel"], 9), p["t0"])):
        if p["id"] in ignorados or p["id"] in vistos:
            continue
        vistos.add(p["id"])
        out.append(p)
    maximo = int(cfg.get("max_na_tela", 6))
    bloqueia = [p for p in out if p["nivel"] in TRAVAM]
    mostrar = bloqueia + [p for p in out if p["nivel"] not in TRAVAM][:max(0, maximo - len(bloqueia))]
    return {"versao": versao, "pontos": sorted(mostrar, key=lambda p: p["t0"]), "total": len(out),
            "zonas": (ctx["atencao"] or {}).get("zonas") or [],
            "ignorados": len(ignorados), "niveis": cfg.get("niveis") or {}, "avisos": avisos,
            "tem_fala": bool(ctx["fala"]), "tem_atencao": bool(ctx["atencao"])}
