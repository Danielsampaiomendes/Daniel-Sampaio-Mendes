"""Revisor de compliance: CFM 2.336/2023, Anvisa RDC 96/2008 e regras de texto do Renato."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .config import load
from .text import limpar


@dataclass
class Achado:
    nivel: str      # erro | aviso
    regra: str
    onde: str       # tela | legenda | projeto
    trecho: str
    motivo: str

    def linha(self) -> str:
        return f"[{self.nivel.upper()}] {self.regra} ({self.onde}): \"{self.trecho}\" → {self.motivo}"


def _casamentos(regras: list, texto: str, onde: str, projeto: dict, vocab: dict | None = None):
    """(regra, início, fim) de cada trecho que casa. Uma regra com `todos: [a, b, c]` casa quando as três partes
    aparecem na mesma frase, em qualquer ordem; o trecho vai da primeira à última (é nele que a exceção é procurada)."""
    for r in regras:
        if r.get("so_tela") and onde != "tela":
            continue
        if r["id"] == "numeracao_tela" and onde != "tela":
            continue
        if r["id"] in ("percentual", "percentual_falado") and projeto.get("permitir_percentual"):
            continue
        if r["id"] == "antes_depois" and projeto.get("uso_interno"):
            continue
        flags = re.MULTILINE if r.get("sensivel_maiusculas") else (re.IGNORECASE | re.MULTILINE)
        if r.get("todos"):
            achado = _todos_separados([list(re.finditer(_expandir(x, vocab), texto, flags)) for x in r["todos"]])
            if achado:
                yield r, achado[0], achado[1]
            continue
        for m in re.finditer(_expandir(r["padrao"], vocab), texto, flags):
            yield r, m.start(), m.end()


def _todos_separados(listas: list) -> tuple | None:
    """(início, fim) do trecho mais curto em que cada parte de `todos` casa com uma palavra DIFERENTE (sem se
    sobrepor). Sem isso, uma palavra que está em duas listas ("resultado" é verbo e alvo) contaria duas vezes, e
    "na primeira sessão a gente conversa sobre o resultado" viraria prazo + verbo + alvo."""
    from itertools import product
    if not all(listas):
        return None
    melhor = None
    for combo in product(*listas):
        faixas = sorted((m.start(), m.end()) for m in combo)
        if any(b[0] < a[1] for a, b in zip(faixas, faixas[1:])):
            continue
        ini, fim = faixas[0][0], max(f for _, f in faixas)
        if melhor is None or fim - ini < melhor[1] - melhor[0]:
            melhor = (ini, fim)
    return melhor


def _expandir(padrao: str, vocab: dict | None) -> str:
    """`<tempo>`, `<verbo_resultado>`... viram o trecho de config/compliance.yaml > fala.vocabulario: cada palavra da
    lista fica num lugar só, e todas as regras da fala usam a mesma lista (nunca duas listas que divergem)."""
    if not vocab:
        return padrao
    return re.sub(r"(?<!\?P)<(\w+)>", lambda m: f"(?:{vocab[m.group(1)]})" if m.group(1) in vocab else m.group(0),
                  padrao)


def _aplicar(regras: list, nivel: str, texto: str, onde: str, projeto: dict) -> list:
    achados = []
    for r, a, b in _casamentos(regras, texto, onde, projeto):
        ini = max(0, a - 25)
        achados.append(Achado(nivel, r["id"], onde, texto[ini:b + 25].replace("\n", " ").strip(), r["motivo"]))
    return achados


def revisar(projeto: dict, textos_tela: list | None = None) -> list:
    cfg = load("compliance")
    marca = load("marca")
    achados = []

    if textos_tela is None:
        textos_tela = textos_do_projeto(projeto)
    for t in textos_tela:
        if not t:
            continue
        for nivel in ("erros", "avisos"):
            achados += _aplicar(cfg.get(nivel, []), nivel[:-1] if nivel == "erros" else "aviso", limpar(t), "tela",
                                projeto)

    legenda = projeto.get("legenda") or ""
    if legenda:
        # o endereço oficial tem " - " por padrão da marca: não conta como travessão
        leg = legenda.replace(marca["clinica"]["endereco"], "")
        for nivel in ("erros", "avisos"):
            achados += _aplicar(cfg.get(nivel, []), "erro" if nivel == "erros" else "aviso", leg, "legenda",
                                projeto)

    ex = cfg.get("exigir", {})
    if legenda:
        primeira = legenda.strip().splitlines()[0] if legenda.strip() else ""
        dobra = int(ex.get("dobra_legenda", 125))
        if len(primeira) > dobra:
            achados.append(Achado("aviso", "dobra_125", "legenda", primeira[:60] + "…",
                                  f"1ª linha com {len(primeira)} caracteres: o gancho precisa caber antes do \"mais\" (~{dobra})."))
        emojis = len(re.findall(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", legenda))
        if emojis > int(ex.get("max_emojis_legenda", 3)):
            achados.append(Achado("aviso", "emojis", "legenda", f"{emojis} emojis",
                                  "0 a 3 emojis, com intenção (skill divine-instagram-pro)."))
    pessoal = projeto.get("marca") == "pessoal"
    if pessoal:
        # template pessoal do Renato: nenhuma marca Divine (nem texto, nem logo)
        for t in textos_tela + ([legenda] if legenda else []):
            if t and re.search(r"\bdivine\b", t, re.IGNORECASE):
                achados.append(Achado("erro", "marca_pessoal", "tela", limpar(t)[:60],
                                      "Template pessoal: sem nenhuma marca Divine."))
    aud = projeto.get("audio") or {}
    if ex.get("musica_licenciada") and aud.get("musica") and not projeto.get("musica_licenciada"):
        achados.append(Achado("erro", "musica", "projeto", str(aud["musica"]),
                              "Conta comercial: música de fora só liberada para uso comercial (musica_licenciada: true)."))
    if projeto.get("uso_interno"):
        achados.append(Achado("aviso", "uso_interno", "projeto", "uso_interno: true",
                              "Peça de uso interno: o arquivo sai marcado NAO-POSTAR."))
    if pessoal or projeto.get("uso_interno"):
        ex = {**ex, "aviso_resultados": False, "rt_em_conteudo_medico": False}
    if ex.get("aviso_resultados") and legenda and "resultados variam" not in legenda.lower():
        achados.append(Achado("erro", "aviso_resultados", "legenda", "(ausente)",
                              f"Incluir \"{marca['aviso_resultados']}\" na legenda."))
    if ex.get("rt_em_conteudo_medico") and projeto.get("conteudo_medico", True) and legenda \
            and "crm" not in legenda.lower():
        achados.append(Achado("erro", "rt", "legenda", "(ausente)",
                              f"Conteúdo médico: assinar com \"{marca['responsavel_tecnico']['curto']}\"."))
    if ex.get("autorizacao_imagem"):
        aut = str(projeto.get("autorizacao_imagem", "")).strip().lower()
        if aut not in ("sim", "nao_aparece", "não aparece", "proprio", "próprio"):
            achados.append(Achado("aviso", "autorizacao_imagem", "projeto", aut or "(não informado)",
                                  "Autorização de uso de imagem pendente: o arquivo sai marcado como pendente."))
    return achados


def video_falado(projeto: dict | None) -> bool:
    """O que se OUVE no vídeo tem fala? Decide se o revisor PRECISA ler a fala antes da final e do postar.

    Nunca pelos interruptores de legenda e corte limpo: o fluxo automático desliga os dois justamente quando não
    consegue transcrever, e a fala que ninguém leu passaria por todas as portas. Ordem:
      1. `tem_fala` gravado pelo fluxo automático (auto.montar mede a voz de cada bruto, com ou sem transcrição);
      2. projeto feito à mão (sem `tem_fala`): legenda da fala, corte limpo ou mensagem na fala ligados, ou algum
         clipe com som original que não está no mudo. Na dúvida, conta como falado (falha para o lado seguro)."""
    p = projeto or {}
    if p.get("tipo") in ("carrossel", "post", "antes_depois"):
        return False
    if p.get("tem_fala") is not None:
        return bool(p["tem_fala"])
    lg = p.get("legendas")
    if (lg.get("ativo", True) if isinstance(lg, dict) else bool(lg)) or p.get("corte_limpo") \
            or any(m.get("na_fala") for m in p.get("mensagens") or [] if isinstance(m, dict)):
        return True
    if (p.get("audio") or {}).get("original", True) is False:
        return bool((p.get("audio") or {}).get("dublagem"))
    return any(isinstance(c, dict) and not c.get("mudo") for c in p.get("clipes") or [])


def id_frase(texto: str) -> str:
    """Id estável de uma frase da fala (o mesmo texto dá o mesmo id em toda prévia)."""
    import hashlib
    return hashlib.sha1(" ".join(str(texto).lower().split()).encode()).hexdigest()[:10]


def _juntas(a: dict, b: dict) -> dict:
    """Duas frases seguidas como uma só: promessa cortada por uma pausa ("Em duas semanas," [pausa] "a gordura some")."""
    texto = a["texto"].rstrip(" .,;:!?…") + ", " + b["texto"]
    return {"texto": texto, "inicio": a["inicio"], "fim": b["fim"], "i0": a.get("i0"), "i1": b.get("i1"),
            "partes": [a["texto"], b["texto"]]}


def numeros_falados(texto: str, mapa: dict | None) -> str:
    """O transcritor escreve "duas semanas", a tela escreve "2 semanas": a fala é conferida com os números em
    algarismos (config/compliance.yaml > fala.numeros), para a MESMA promessa dar o MESMO nível dos dois jeitos."""
    if not mapa:
        return texto
    nomes = sorted(mapa, key=len, reverse=True)
    rx = re.compile(r"\b(" + "|".join(map(re.escape, nomes)) + r")\b", re.I)
    texto = rx.sub(lambda m: str(mapa.get(m.group(1).lower(), m.group(1))), texto)
    # número composto falado: "vinte e um dias" -> "20 e 1 dias" -> "21 dias" (e "quarenta e cinco" -> "45")
    return re.sub(r"\b([2-9]0) e ([1-9])\b", lambda m: str(int(m.group(1)) + int(m.group(2))), texto)


def _rebaixa(regra_id: str, texto: str, a: int, b: int, rebaixar: list) -> str | None:
    """Uma regra vermelha vira laranja ("confira") quando o contexto mostra que pode ser frase correta: negação logo
    antes ("nenhum tratamento tem resultado garantido") ou orientação ("antes e depois da sessão, beba água").
    Nunca some sozinha: alguém confere."""
    for rb in rebaixar or []:
        regras = rb.get("regra")
        if regra_id not in (regras if isinstance(regras, list) else [regras]):
            continue
        if rb.get("antes") and re.search(rb["antes"], texto[:a], re.I):
            return rb.get("por_que") or "contexto"
        if rb.get("depois") and re.search(rb["depois"], texto[b:], re.I):
            return rb.get("por_que") or "contexto"
        if rb.get("dentro") and re.search(rb["dentro"], texto[a:b], re.I):    # só no trecho que casou
            return rb.get("por_que") or "contexto"
    return None


def _achado_fala(texto: str, proj: dict, cfg: dict, exc) -> tuple:
    """(nível, Achado) do que a frase tem de mais grave, ou (None, None). `texto` já vem com números em algarismos."""
    fc = cfg.get("fala") or {}
    vocab = fc.get("vocabulario") or {}
    com_excecao = set(fc.get("excecao_vale_para") or [])
    janela = lambda a, b: texto[max(0, a - 25):b + 25].strip()
    vermelhas = list(cfg.get("erros") or []) + list(fc.get("erros") or [])
    rebaixado = None
    for r, a, b in _casamentos(vermelhas, texto, "fala", proj, vocab):
        if r["id"] in com_excecao and exc and exc.search(texto[a:b]):
            continue                              # "em 3 dias o roxinho some": efeito do pós, não resultado
        por_que = _rebaixa(r["id"], texto, a, b, fc.get("rebaixar"))
        if por_que is None:
            return "erro", Achado("erro", r["id"], "fala", janela(a, b), r["motivo"])
        rebaixado = rebaixado or Achado("confirmar", r["id"], "fala", janela(a, b),
                                        f"{r['motivo']} Parece {por_que}: confira.")
    if rebaixado:
        return "confirmar", rebaixado
    for r, a, b in _casamentos(fc.get("confirmar") or [], texto, "fala", proj, vocab):
        if exc and exc.search(texto[a:b]):
            continue
        return "confirmar", Achado("confirmar", r["id"], "fala", janela(a, b), r["motivo"])
    return None, None


def achados_na_fala(palavras: list, projeto: dict | None = None, ignorar: list | None = None) -> list:
    """Tudo o que o revisor acha no que se OUVE no vídeo, frase a frase (e cada frase junto com a seguinte).

    Devolve [{"frase", "achado", "nivel", "id", "conferido"}]:
      nivel "erro"       regra de `erros` (as dos textos da tela) ou de `fala.erros`: bloqueia sempre, não se confirma
      nivel "confirmar"  regra de `fala.confirmar`, ou vermelha com contexto de frase correta (`fala.rebaixar`): pode
                         ser promessa ou informação; bloqueia até você conferir (projeto.yaml > compliance_conferido),
                         tirar a frase ou dublar sem ela
    Antes de conferir, os números falados viram algarismos (`fala.numeros`): "em duas semanas" = "em 2 semanas".
    `ignorar`: frases já marcadas para sair (remover_trechos), que somem na próxima prévia."""
    from .roteirista import frases
    cfg = load("compliance")
    fc = cfg.get("fala") or {}
    proj = {"legenda": "", "conteudo_medico": False,
            **{k: v for k, v in (projeto or {}).items() if k in ("permitir_percentual", "uso_interno")}}
    fora = {" ".join(str(x).lower().split()) for x in ignorar or []}
    conferidos = {str(x.get("id") if isinstance(x, dict) else x) for x in (projeto or {}).get("compliance_conferido") or []}
    exc = re.compile(fc["excecoes"], re.I) if fc.get("excecoes") else None
    frs = frases(palavras or [])
    juntar = float(fc.get("juntar_pausa_ate_s", 1.5))
    candidatos = [(fr, [fr["texto"]]) for fr in frs]
    candidatos += [(_juntas(a, b), [a["texto"], b["texto"]]) for a, b in zip(frs, frs[1:])
                   if float(b["inicio"]) - float(a["fim"]) <= juntar]
    out, achadas = [], set()          # (regra, frase) já achada sozinha: a junção não repete o mesmo ponto
    for fr, partes in candidatos:
        if any(" ".join(x.lower().split()) in fora for x in partes):
            continue
        texto = numeros_falados(limpar(fr["texto"]), fc.get("numeros"))
        fechada = len(partes) > 1 and re.search(r"[.!?…]\s*$", partes[0].strip())
        if fechada and exc and exc.search(texto):
            continue                  # "O retorno é em 2 semanas." + "A celulite melhora...": duas frases inteiras
        nivel, achado = _achado_fala(texto, proj, cfg, exc)
        if achado is None:
            continue
        if len(partes) > 1 and any((achado.regra, p) in achadas for p in partes):
            continue
        if fechada and nivel == "erro":
            # a 1ª frase terminou com ponto: são duas frases inteiras, não uma promessa cortada por uma pausa
            # ("Em 2 semanas," [pausa] "a gordura some" continua vermelho). Pode ser coincidência: confira.
            nivel = "confirmar"
            achado = Achado("confirmar", achado.regra, "fala", achado.trecho,
                            f"{achado.motivo} São duas frases seguidas: confira se juntas prometem prazo.")
        achadas.update((achado.regra, p) for p in partes)
        fid = id_frase(fr["texto"])
        out.append({"frase": fr, "achado": achado, "nivel": nivel, "id": fid,
                    "conferido": nivel == "confirmar" and fid in conferidos})
    # a promessa cortada por uma pausa já é vermelha na junção: a laranja de uma das partes sozinha seria repetida
    vermelhas = {p for x in out if x["nivel"] == "erro" for p in (x["frase"].get("partes") or [])}
    return [x for x in out if not (x["nivel"] == "confirmar" and not x["frase"].get("partes")
                                   and x["frase"]["texto"] in vermelhas)]


def erros_na_fala(palavras: list, projeto: dict | None = None, ignorar: list | None = None) -> list:
    """O que TRAVA: [(frase, Achado)] com os erros e as frases "confira" ainda não conferidas.

    Um único ponto de verdade: a linha do tempo (o "!"), o ✓ Aprovar, a exportação da final e o "postar sozinho"
    (publicar.pode_publicar) chamam esta função. O que é uma regra de compliance fica em config/compliance.yaml."""
    return [(x["frase"], x["achado"]) for x in achados_na_fala(palavras, projeto, ignorar) if not x["conferido"]]


def textos_do_projeto(projeto: dict) -> list:
    t = []
    for v in projeto.get("versoes") or []:
        for b in (v.get("hook") or []) if isinstance(v.get("hook"), list) else [v.get("hook") or {}]:
            if isinstance(b, dict):            # hook: auto (ou id do banco) ainda sem frase não é texto de tela
                t += [b.get("titulo"), b.get("apoio")]
    for m in projeto.get("mensagens") or []:
        t += [m.get("titulo"), m.get("apoio")]
    cta = projeto.get("cta_antecipado")
    t.append(cta if isinstance(cta, str) else (cta or {}).get("texto"))
    t.append(projeto.get("selo"))
    f = projeto.get("fechamento") or {}
    t += [f.get("frase"), f.get("cta")]
    return [x for x in t if x]


def linha_checklist(projeto: dict, achados: list) -> str:
    cfm = not any(a.nivel == "erro" and a.regra in ("percentual", "prazo_garantido", "promessa", "comparacao")
                  for a in achados)
    anv = not any(a.nivel == "erro" and a.regra == "medicamento" for a in achados)
    aut = str(projeto.get("autorizacao_imagem", "pendente")).lower()
    aut = {"sim": "ok", "nao_aparece": "ninguém aparece", "proprio": "conteúdo próprio"}.get(aut, "pendente")
    return f"{'OK' if cfm else 'REVISAR'} CFM / {'OK' if anv else 'REVISAR'} Anvisa / autorização de imagem: {aut}"


def nota_viral(projeto: dict, plano, achados: list, tem_voz: bool) -> dict:
    """Nota de 0 a 10 por critério (hook, retenção, leitura, áudio, glamour, compliance) com dicas curtas."""
    from .text import contar_palavras
    cfg = load("compliance").get("nota_viral", {})
    pref = load("preferencias")
    tv = projeto.get("template") == "tv"
    dicas = []
    notas = {}

    # hook: texto no 1º quadro, curto, completo antes de 4 s
    hooks = [c for c in plano.camadas if c.nome.startswith("hook") and c.nome.endswith("titulo")]
    h = 10
    if not tv:
        if not hooks or min(c.t0 for c in hooks) > 0.3:
            h -= 4
            dicas.append("texto do gancho já no 1º quadro")
        if hooks and contar_palavras(min(hooks, key=lambda c: c.t0).texto) > cfg.get("hook_palavras_max", 10):
            h -= 2
            dicas.append("1ª batida do gancho mais curta")
        if hooks and min(c.t1 for c in hooks) > cfg.get("hook_ate_s", 4.0) + 1.5:
            h -= 2
            dicas.append("gancho completo antes de 4 s")
    notas["hook"] = max(0, h)

    # retenção: duração alvo, troca visual frequente, CTA antecipado, final curto
    r = 10
    d0, d1 = cfg.get("duracao_alvo", [25, 40])
    dur = plano.duracao_total
    if not tv and not d0 <= dur <= d1 and not projeto.get("relato"):
        r -= 2
        dicas.append(f"duração {dur:.0f}s (alvo {d0} a {d1}s)")
    marcos = sorted({round(c.t0, 1) for c in plano.camadas if c.t0 > 0.2 and not c.nome.startswith(("grad", "moldura"))}
                    | {round(float(c.get("inicio_base", 0)), 1) for c in (projeto.get("_base_meta") or {}).get("clipes", [])})
    marcos = [m for m in marcos if m < plano.inicio_fechamento]
    media = plano.inicio_fechamento / max(1, len(marcos))
    if media > cfg.get("troca_visual_s", 2.5):
        r -= min(4, int(media - cfg.get("troca_visual_s", 2.5)) + 1)
        dicas.append(f"mudança visual a cada {media:.1f}s (alvo ~2 s)")
    if not tv and not projeto.get("cta_antecipado"):
        r -= 2
        dicas.append("CTA antecipado curto depois do gancho")
    if not tv and dur - plano.inicio_fechamento > cfg.get("fechamento_max_s", 3.0) + 0.2:
        r -= 1
        dicas.append("fechamento mais curto (porta na cara)")
    notas["retenção"] = max(0, r)

    # leitura: cada texto fica o tempo mínimo de leitura
    lp = pref["texto"]["leitura_palavras_por_s"]
    curtos = sum(1 for c in plano.camadas if getattr(c, "texto", "") and c.t1 - c.t0 < contar_palavras(c.texto) / lp)
    notas["leitura"] = max(0, 10 - 2 * curtos)
    if curtos:
        dicas.append(f"{curtos} texto(s) com pouco tempo de leitura")

    # áudio: voz limpa ou trilha, poucos SFX
    a = 10
    fams = {e[1].rsplit("_", 1)[0] for e in plano.eventos_sfx}
    if len(fams) > load("sfx").get("max_familias", 4):
        a -= 3
        dicas.append("menos famílias de SFX")
    if not tem_voz and not (projeto.get("audio") or {}).get("trilha", True):
        a -= 4
        dicas.append("vídeo sem voz e sem trilha")
    notas["áudio"] = max(0, a)

    # glamour: entradas lentas, dissolve, nada piscando
    g = 10
    rapidos = [c for c in plano.camadas if c.entrada and c.entrada < cfg.get("entrada_min_s", 0.5)
               and not c.nome.startswith(("legenda", "grad", "placa", "moldura", "ef_"))]
    if rapidos:
        g -= 2
        dicas.append("textos entrando rápido demais")
    if float(projeto.get("dissolve", pref["animacao"]["dissolve_entre_clipes_s"])) <= 0 and \
            len((projeto.get("_base_meta") or {}).get("clipes", [])) > 1 and not projeto.get("corte_limpo"):
        g -= 2
        dicas.append("dissolve entre clipes")
    notas["glamour"] = max(0, g)

    erros = [x for x in achados if x.nivel == "erro"]
    avisos = [x for x in achados if x.nivel == "aviso" and x.regra not in ("autorizacao_imagem", "uso_interno")]
    notas["compliance"] = 0 if erros else max(6, 10 - len(avisos))
    return {"notas": notas, "dicas": dicas}
