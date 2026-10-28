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
