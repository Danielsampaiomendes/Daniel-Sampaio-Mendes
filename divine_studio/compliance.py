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


def _aplicar(regras: list, nivel: str, texto: str, onde: str, projeto: dict) -> list:
    achados = []
    for r in regras:
        if r.get("so_tela") and onde != "tela":
            continue
        if r["id"] == "numeracao_tela" and onde != "tela":
            continue
        if r["id"] == "percentual" and projeto.get("permitir_percentual"):
            continue
        if r["id"] == "antes_depois" and projeto.get("uso_interno"):
            continue
        flags = re.MULTILINE if r.get("sensivel_maiusculas") else (re.IGNORECASE | re.MULTILINE)
        for m in re.finditer(r["padrao"], texto, flags):
            ini = max(0, m.start() - 25)
            achados.append(Achado(nivel, r["id"], onde, texto[ini:m.end() + 25].replace("\n", " ").strip(),
                                  r["motivo"]))
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


def textos_do_projeto(projeto: dict) -> list:
    t = []
    for v in projeto.get("versoes") or []:
        for b in (v.get("hook") or []) if isinstance(v.get("hook"), list) else [v.get("hook") or {}]:
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
               and not c.nome.startswith(("legenda", "grad", "placa", "moldura"))]
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
