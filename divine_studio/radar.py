"""Radar viral: o que está viralizando agora no nicho (Instagram e TikTok), para aprender e testar.

Fontes (config/radar.yaml):
  - API oficial do Instagram: perfis de referência (business discovery) e hashtags (top media).
  - Pesquisa com o Claude no Chrome: `missao()` gera o texto; o resultado colado entra por `importar_texto()`.
  - Colar à mão: links e números em qualquer formato.
Cada item ganha o formato viral (Laboratório) e "quantas vezes acima do normal" (outlier). Daí sai a copy e o
roteiro de gravação adaptados para a Divine (`roteiro()`), sempre pelo revisor de compliance.
Os dados ficam em projetos/.radar.json (fora do GitHub).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import statistics

from .config import ROOT, load

ARQUIVO = ROOT / "projetos" / ".radar.json"


def _cfg() -> dict:
    return load("radar")


def ler() -> list:
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _gravar(itens: list) -> None:
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(json.dumps(itens, ensure_ascii=False, indent=1), encoding="utf-8")


def _id(link: str, conta: str = "", gancho: str = "") -> str:
    base = re.sub(r"[?#].*$", "", (link or "").strip().rstrip("/")) or f"{conta}|{gancho}"
    return hashlib.sha1(base.encode()).hexdigest()[:12]


def _num(v) -> float | None:
    """'1,2 mi', '35,4 mil', '12k', '1.234', 5000 -> número."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    t = str(v).strip().lower().replace(" ", "")
    mult = 1
    for suf, m in (("mi", 1e6), ("m", 1e6), ("mil", 1e3), ("k", 1e3), ("bi", 1e9)):
        if t.endswith(suf):
            mult, t = m, t[: -len(suf)]
            break
    if mult > 1:
        t = t.replace(",", ".")
    else:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(re.sub(r"[^\d.]", "", t)) * mult
    except ValueError:
        return None


def _formato(item: dict) -> str | None:
    from .lab import classificar, formatos
    livre = str(item.get("formato") or "").lower()
    if livre:
        for chave, f in formatos().items():
            nome = f.get("nome", "").lower()
            if livre.replace(" ", "_") == chave or (nome and (livre in nome or nome.split(" (")[0] in livre)):
                return chave
    return classificar(" ".join(str(item.get(k) or "") for k in ("formato", "gancho", "texto_tela", "legenda", "por_que")))


def _engajamento(it: dict) -> float:
    return float(it.get("views") or 0) or (float(it.get("curtidas") or 0) + 3 * float(it.get("comentarios") or 0)
                                           + 4 * float(it.get("compartilhamentos") or 0))


def _outliers(itens: list) -> None:
    """Quantas vezes acima do normal do mesmo perfil (ou do lote, se o perfil tem um vídeo só)."""
    por_conta = {}
    for it in itens:
        por_conta.setdefault(it.get("conta") or "?", []).append(_engajamento(it))
    geral = [e for v in por_conta.values() for e in v if e]
    med_geral = statistics.median(geral) if len(geral) >= 3 else 0      # com 1 ou 2 vídeos não dá para comparar
    for it in itens:
        if it.get("outlier") is not None:
            continue
        lista = [e for e in por_conta.get(it.get("conta") or "?", []) if e]
        med = statistics.median(lista) if len(lista) >= 3 else med_geral
        it["outlier"] = round(_engajamento(it) / med, 1) if med else None


def adicionar(novos: list, fonte: str) -> dict:
    """Junta itens ao Radar (sem duplicar pelo link) e classifica o formato."""
    itens = ler()
    por_id = {i["id"]: i for i in itens}
    limpos = []
    for n in novos:
        it = {k: v for k, v in n.items() if v not in (None, "")}
        for k in ("views", "curtidas", "comentarios", "compartilhamentos", "duracao_s"):
            if k in it:
                it[k] = _num(it[k])
        it["conta"] = str(it.get("conta") or "").lstrip("@")
        limpos.append(it)
    _outliers(limpos)
    entrou = 0
    hoje = _dt.date.today().isoformat()
    for it in limpos:
        it["id"] = _id(it.get("link", ""), it.get("conta", ""), it.get("gancho", ""))
        it["fonte"] = fonte
        it["rede"] = it.get("rede") or ("tiktok" if "tiktok.com" in str(it.get("link", "")) else "instagram")
        it["formato_viral"] = _formato(it)
        it.setdefault("adicionado_em", hoje)
        if it["id"] in por_id:
            por_id[it["id"]].update({k: v for k, v in it.items() if k != "adicionado_em"})
        else:
            itens.append(it)
            por_id[it["id"]] = it
            entrou += 1
    _gravar(itens)
    return {"novos": entrou, "total": len(itens)}


def importar_texto(texto: str, fonte: str = "chrome") -> dict:
    """Resultado colado: o JSON da missão do Claude no Chrome, ou linhas soltas com link e números."""
    m = re.search(r"\[[\s\S]*\]", texto or "")
    if m:
        try:
            dados = json.loads(m.group(0))
            if isinstance(dados, list) and dados and isinstance(dados[0], dict):
                return adicionar(dados, fonte)
        except ValueError:
            pass
    novos = []
    for linha in (texto or "").splitlines():
        link = re.search(r"https?://(?:www\.)?(?:instagram\.com|tiktok\.com)/\S+", linha)
        if not link:
            continue
        it = {"link": link.group(0).rstrip(").,")}
        conta = re.search(r"@([\w.]+)", linha) or re.search(r"(?:instagram|tiktok)\.com/@?([\w.]+)/", it["link"])
        if conta and conta.group(1) not in ("reel", "p", "reels", "video"):
            it["conta"] = conta.group(1)
        for chave, pal in (("views", r"(?:views?|visualiza\w*|plays?|reprodu\w*)"), ("curtidas", r"(?:curtidas?|likes?)"),
                           ("comentarios", r"(?:coment\w*|comments?)"), ("compartilhamentos", r"(?:compartilh\w*|shares?|envios?)")):
            achou = re.search(r"([\d.,]+\s?(?:mil|mi|k|m)?)\s*" + pal, linha, re.I) or \
                re.search(pal + r"\W{0,3}([\d.,]+\s?(?:mil|mi|k|m)?)", linha, re.I)
            if achou:
                it[chave] = achou.group(1)
        resto = re.sub(r"https?://\S+", "", linha).strip(" -:|")
        if resto:
            it["gancho"] = resto[:160]
        novos.append(it)
    if not novos:
        raise ValueError("não achei links do Instagram ou do TikTok no texto colado")
    return adicionar(novos, fonte)


def missao(rede: str = "instagram") -> str:
    """Texto para colar no Claude no Chrome (ele navega no seu navegador enquanto você acompanha)."""
    c = _cfg()
    modelo = (c.get("missao") or {}).get(rede) or (c.get("missao") or {}).get("instagram", "")
    perfis = ", ".join("@" + p for p in c.get("perfis_referencia") or []) or "(nenhum cadastrado)"
    hashtags = ", ".join("#" + h for h in c.get("hashtags") or [])
    return modelo.format(nicho=c.get("nicho", "estética"), hashtags=hashtags, perfis=perfis).strip()


def missao_completa(rede: str = "instagram", tema: str = "", url_studio: str = "http://127.0.0.1:8765",
                    higgsfield: bool = False) -> str:
    """Missão para o Claude no Chrome: pesquisa na rede E registra no Divine Studio (aba ao lado)."""
    c = _cfg()
    perfis = ", ".join("@" + p for p in c.get("perfis_referencia") or []) or "(nenhum cadastrado: use os que aparecerem)"
    hf = ""
    if higgsfield:
        from . import higgsfield as _hf
        o = _hf.orcamento()
        hf = (f"6. Higgsfield (só se eu pedir): abra higgsfield.ai numa aba nova, na minha conta. Sugira 1 ou 2 efeitos que "
              f"aumentariam a viralização do nosso vídeo (ex.: Eyes in, Orbit 360, Bullet time), me diga o custo em créditos "
              f"e ESPERE o meu ok. Teto: {o['por_video']:.0f} créditos por vídeo e {o['resta_semana']:.0f} restantes na semana. "
              "Baixe o resultado e solte em Vídeos brutos do projeto no Divine Studio.")
    return c.get("missao_completa", "").format(
        rede="TikTok" if rede == "tiktok" else "Instagram", nicho=c.get("nicho", "estética"),
        tema=f", com foco em \"{tema}\"" if tema else "", hashtags=", ".join("#" + h for h in c.get("hashtags") or []),
        perfis=perfis, url_studio=url_studio, higgsfield=hf).strip()


# ---------------------------------------------------------------- API oficial do Instagram
def buscar_instagram(usuario: str | None = None) -> dict:
    """Perfis de referência (business discovery) e hashtags (top media) pela API oficial."""
    import urllib.error

    from . import instagram
    if not instagram.configurado(usuario):
        raise SystemExit("Conecte o Instagram (Programação > Conectar Instagram) para o Radar buscar sozinho.")
    cred = instagram._credenciais(usuario)
    c = _cfg()
    campos = "caption,like_count,comments_count,media_type,media_product_type,permalink,timestamp"
    novos, erros = [], []
    for perfil in c.get("perfis_referencia") or []:
        try:
            d = instagram._get(cred["user_id"], cred["token"],
                               fields=f"business_discovery.username({perfil}){{followers_count,media.limit({int(c.get('max_por_busca', 30))}){{{campos}}}}}")
            bd = d.get("business_discovery") or {}
            for m in (bd.get("media") or {}).get("data") or []:
                novos.append(_de_api(m, perfil, "perfil"))
        except urllib.error.HTTPError as e:
            erros.append(f"@{perfil}: {e.code} (só contas profissionais aparecem)")
    for tag in c.get("hashtags") or []:
        try:
            hid = (instagram._get("ig_hashtag_search", cred["token"], user_id=cred["user_id"], q=tag).get("data") or [{}])[0].get("id")
            if not hid:
                continue
            d = instagram._get(f"{hid}/top_media", cred["token"], user_id=cred["user_id"], fields=campos,
                               limit=int(c.get("max_por_busca", 30)))
            lote = [_de_api(m, "", f"#{tag}") for m in d.get("data") or []]
            _outliers_lote(lote)
            novos += lote
        except urllib.error.HTTPError as e:
            erros.append(f"#{tag}: {e.code} (a busca por hashtag precisa do login pelo Facebook)")
        except urllib.error.URLError:
            raise SystemExit("Sem conexão com o Instagram.")
    corte = float(c.get("viral_a_partir_de", 2.0))
    _outliers([n for n in novos if n.get("outlier") is None])
    virais = [n for n in novos if (n.get("outlier") or 0) >= corte]
    r = adicionar(virais, "instagram_api") if virais else {"novos": 0, "total": len(ler())}
    return {**r, "analisados": len(novos), "virais": len(virais), "erros": erros}


def _de_api(m: dict, conta: str, origem: str) -> dict:
    return {"link": m.get("permalink"), "conta": conta, "curtidas": m.get("like_count"),
            "comentarios": m.get("comments_count"), "legenda": (m.get("caption") or "")[:500],
            "gancho": (m.get("caption") or "").split("\n")[0][:160], "tipo_midia": m.get("media_product_type") or m.get("media_type"),
            "data": (m.get("timestamp") or "")[:10], "origem": origem}


def _outliers_lote(lote: list) -> None:
    eng = [_engajamento(x) for x in lote if _engajamento(x)]
    med = statistics.median(eng) if eng else 0
    for x in lote:
        x["outlier"] = round(_engajamento(x) / med, 1) if med else None


# ---------------------------------------------------------------- para o Laboratório e para a tela
def em_alta(dias: int | None = None, formato: str | None = None, rede: str | None = None) -> list:
    dias = dias or int(_cfg().get("manter_dias", 60))
    lim = (_dt.date.today() - _dt.timedelta(days=dias)).isoformat()
    corte = float(_cfg().get("viral_a_partir_de", 2.0))
    out = [i for i in ler() if not i.get("descartado") and i.get("adicionado_em", "") >= lim
           and (i.get("outlier") or corte) >= corte
           and (not formato or i.get("formato_viral") == formato) and (not rede or i.get("rede") == rede)]
    return sorted(out, key=lambda i: -(i.get("outlier") or 0))


def formatos_em_alta(dias: int = 30) -> dict:
    cont = {}
    for i in em_alta(dias):
        if i.get("formato_viral"):
            cont[i["formato_viral"]] = cont.get(i["formato_viral"], 0) + 1
    return cont


def item(id_: str) -> dict:
    it = next((i for i in ler() if i["id"] == id_), None)
    if not it:
        raise ValueError("item do Radar não encontrado")
    return it


def marcar(id_: str, **campos) -> dict:
    itens = ler()
    for i in itens:
        if i["id"] == id_:
            i.update(campos)
            _gravar(itens)
            return i
    raise ValueError("item do Radar não encontrado")


# ---------------------------------------------------------------- da referência viral para a copy da Divine
def roteiro(id_: str, tema: str, usar_ia: bool = True) -> dict:
    """Roteiro de gravação + copy adaptados à Divine a partir de um vídeo que viralizou (mesmo formato, outra ideia).
    Com a IA ligada, o Claude escreve; sem ela, o app monta pelo catálogo de formatos. Sempre passa pelo revisor."""
    from .lab import formatos
    it = item(id_)
    fmt = it.get("formato_viral") or "lista_monta"
    f = formatos().get(fmt, {})
    r = None
    if usar_ia:
        try:
            r = _roteiro_ia(it, f, tema)
        except SystemExit:
            r = None
    r = r or _roteiro_modelo(it, f, tema)
    r.update({"formato_viral": fmt, "formato_nome": f.get("nome", fmt), "referencia": it.get("link"),
              "tema": tema, "erros_compliance": _revisar(r)})
    return r


def _roteiro_modelo(it: dict, f: dict, tema: str) -> dict:
    preencher = {"tema": tema, "dor": f"{tema} te incomoda", "acao": f"cuidar de {tema}", "obvio": "falta de cuidado",
                 "objetivo": "saúde", "pergunta": f"{tema} é para mim", "mito": "é tudo igual", "etapa": "a avaliação"}

    def fmt(t):
        try:
            return t.format(**preencher)
        except (KeyError, IndexError):
            return t
    ganchos = [fmt(g) for g in (f.get("ganchos") or [])][:3]
    if it.get("gancho"):
        ganchos.append(f"(adaptar da referência) {it['gancho']}")
    cta = {"seguir": "Segue a Divine para aprender mais.", "salvar": "Salva para lembrar e segue para mais.",
           "enviar": "Manda para quem precisa ver isso.", "comentar": "Me conta nos comentários a sua dúvida.",
           "agendar": "Agende sua avaliação pelo link da bio."}.get(f.get("cta"), "Segue a Divine para mais.")
    planos = [f"{i + 1}. {passo}" for i, passo in enumerate(f.get("estrutura") or [])]
    return {"ganchos": ganchos[:4], "sequencia": planos, "texto_tela": ganchos[0] if ganchos else tema, "cta": cta,
            "fala": " ".join(p.split(": ", 1)[-1] for p in (f.get("estrutura") or [])),
            "legenda": f"{ganchos[0] if ganchos else tema}\n\n{f.get('descricao', '')}\n\n{cta}",
            "por_que_funciona": it.get("por_que") or f.get("descricao", ""), "fonte": "modelo"}


def _roteiro_ia(it: dict, f: dict, tema: str) -> dict | None:
    from . import assistente
    pedido = (
        "Adapte para a Divine Medical Spa um vídeo que VIRALIZOU, mantendo o FORMATO e a estrutura de retenção, "
        f"mas com o tema \"{tema}\". Referência: {json.dumps(it, ensure_ascii=False)}\n"
        f"Formato: {f.get('nome')} ({f.get('descricao')}). Estrutura: {f.get('estrutura')}.\n"
        "Responda SÓ com JSON: {\"ganchos\": [3 ganchos falados], \"texto_tela\": \"...\", \"sequencia\": [planos de "
        "gravação com o que filmar e falar], \"fala\": \"roteiro completo para o teleprompter\", \"cta\": \"...\", "
        "\"legenda\": \"...\", \"por_que_funciona\": \"...\"}. Português do Brasil, sem travessões, CFM e Anvisa "
        "(sem promessa de resultado, sem antes e depois de paciente).")
    texto, _, _ = assistente.perguntar([], pedido)
    m = re.search(r"\{[\s\S]*\}", texto)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    d["fonte"] = "ia"
    return d


def _revisar(r: dict) -> list:
    from .compliance import revisar
    textos = list(r.get("ganchos") or []) + [r.get("texto_tela", ""), r.get("cta", "")]
    return [a.linha() for a in revisar({"legenda": r.get("legenda", "") + "\nResultados variam de pessoa para pessoa.",
                                        "conteudo_medico": False}, textos) if a.nivel == "erro"]


def criar_projeto(id_: str, tema: str, usar_ia: bool = True) -> str:
    """Projeto novo já com o roteiro (roteiro.md), a copy do teleprompter, o formato e os 3 ganchos nas versões."""
    import yaml

    from .painel import PROJETOS, _pasta, novo
    r = roteiro(id_, tema, usar_ia)
    nome = novo(tema)
    pasta = _pasta(nome)
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    d["formato_viral"] = r["formato_viral"]
    d["copy_dublagem"] = r.get("fala", "")
    d["referencia_viral"] = r.get("referencia")
    ganchos = [g for g in r.get("ganchos") or [] if not g.startswith("(adaptar")] or [tema]
    d["versoes"] = [{"nome": f"V{k + 1}", "formato_viral": r["formato_viral"], "hook": [{"titulo": g}]}
                    for k, g in enumerate(ganchos[:3])]
    if r.get("legenda"):
        d["legenda"] = r["legenda"].strip() + "\n\nResultados variam de pessoa para pessoa.\n" \
            "Resp. técnico: Dr. Daniel Sampaio Mendes · CRM/SP 186.470"
    (pasta / "projeto.yaml").write_text("# Divine Studio (roteiro a partir do Radar viral)\n" + yaml.safe_dump(
        d, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
    md = [f"# Roteiro de gravação · {tema}", "", f"Formato: **{r['formato_nome']}** · referência: {r.get('referencia') or '-'}",
          "", "## Ganchos (escolha um por versão)", ""] + [f"- {g}" for g in r.get("ganchos") or []] + \
         ["", "## Sequência de gravação", ""] + [f"- {s}" for s in r.get("sequencia") or []] + \
         ["", "## Texto na tela", "", r.get("texto_tela", ""), "", "## Fala (teleprompter)", "", r.get("fala", ""),
          "", "## CTA", "", r.get("cta", ""), "", "## Por que funciona", "", r.get("por_que_funciona", "")]
    if r["erros_compliance"]:
        md += ["", "## Revisor (corrigir antes de gravar)", ""] + [f"- {e}" for e in r["erros_compliance"]]
    (pasta / "roteiro.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    marcar(id_, usado_em=nome)
    return str(pasta.relative_to(PROJETOS))
