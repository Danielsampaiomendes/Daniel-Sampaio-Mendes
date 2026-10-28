"""Linha de comando do Divine Studio.

  python3 -m divine_studio novo "co2 no corpo"
  python3 -m divine_studio info bruto/IMG_1234.MOV
  python3 -m divine_studio revisar projetos/2026-10-28_co2-no-corpo
  python3 -m divine_studio editar projetos/2026-10-28_co2-no-corpo [--versoes V1,V3] [--teste]
  python3 -m divine_studio regra "texto da regra"
  python3 -m divine_studio quadros saida/arquivo.mp4
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import shutil
import sys
import time
from pathlib import Path

from . import __version__
from .config import CONFIG, ROOT, hoje, ler_projeto, load, save, slug


def cmd_novo(a):
    nome = slug(a.nome)
    pasta = ROOT / "projetos" / f"{hoje()}_{nome}"
    if pasta.exists():
        raise SystemExit(f"Já existe: {pasta}")
    for sub in ("bruto", "trabalho", "saida"):
        (pasta / sub).mkdir(parents=True)
    modelo = (Path(__file__).parent / "modelo_projeto.yaml").read_text(encoding="utf-8")
    modelo = modelo.replace("{data}", hoje()).replace('"Tema do vídeo"', f'"{a.nome}"')
    (pasta / "projeto.yaml").write_text(modelo, encoding="utf-8")
    print(f"Projeto criado: {pasta.relative_to(ROOT)}\nColoque os brutos em bruto/ e preencha projeto.yaml.")


def cmd_info(a):
    from .ingest import probe
    p = probe(Path(a.video))
    hq = min(p["largura"], p["altura"]) < load("exportacao")["alta_qualidade"]["altura_minima"]
    print(json.dumps(p, indent=2, ensure_ascii=False))
    print(f"HDR: {'sim (vai converter para SDR)' if p['hdr'] else 'não'} · "
          f"modo alta qualidade: {'liga automaticamente' if hq else 'não precisa'}")


def cmd_revisar(a):
    from .compliance import linha_checklist, revisar
    p = ler_projeto(Path(a.projeto))
    ach = revisar(p)
    for x in ach:
        print(x.linha())
    print(("Sem problemas. " if not ach else "") + linha_checklist(p, ach))
    return ach


def _formato(p):
    f = load("exportacao")["formatos"][p.get("formato", "reels")]
    return int(f["largura"]), int(f["altura"])


def _digital_base(p) -> str:
    """Tudo o que muda a base: se nada disso mudou, a base é reaproveitada."""
    return json.dumps({k: p.get(k) for k in ("clipes", "dissolve", "zoom_respiro", "formato")},
                      sort_keys=True, default=str)


def _base_atualizada(p, base: Path) -> bool:
    meta = base.with_suffix(".json")
    if not base.exists() or not meta.exists():
        return False
    try:
        return json.loads(meta.read_text(encoding="utf-8")).get("_digital") == _digital_base(p)
    except Exception:
        return False


def cmd_editar(a):
    from .audio import ler_audio, mixar, salvar_wav
    from .compliance import linha_checklist, revisar
    from .exportar import exportar, quadros
    from .ingest import construir_base
    from .render import renderizar
    from .rodizio import escolher_fontes, escolher_sfx, registrar
    from .templates import TEMPLATES

    t_ini = time.time()
    p = ler_projeto(Path(a.projeto))
    pasta = p["_pasta"]
    W, H = _formato(p)
    fps = load("exportacao")["fps"]
    trabalho, saida = pasta / "trabalho", pasta / "saida"
    trabalho.mkdir(exist_ok=True)
    saida.mkdir(exist_ok=True)

    print(f"Divine Studio {__version__} · {p.get('titulo')} · {p.get('formato', 'reels')} {W}x{H}")
    ach = revisar(p)
    erros = [x for x in ach if x.nivel == "erro"]
    for x in ach:
        print("  " + x.linha())
    if erros and not a.forcar:
        raise SystemExit("Revisor bloqueou a exportação. Corrija os erros acima (ou use --forcar para um teste interno).")

    base = trabalho / "base.mov"
    if a.refazer_base or not _base_atualizada(p, base):
        print("• Montando a base (cortes, HDR, recorte, dissolve)…")
        meta = construir_base(p, W, H, base)
        meta["_digital"] = _digital_base(p)
        base.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    meta = json.loads(base.with_suffix(".json").read_text(encoding="utf-8"))
    dur = float(meta["duracao"])
    print(f"  base: {dur:.1f}s · alta qualidade: {'sim' if meta['alta_qualidade'] else 'não'}")

    versoes = p.get("versoes") or []
    if a.versoes:
        quero = {v.strip() for v in a.versoes.split(",")}
        idx = [i for i, v in enumerate(versoes) if v.get("nome") in quero]
    else:
        idx = list(range(len(versoes)))
    if not idx:
        raise SystemExit("Nenhuma versão para renderizar (lista 'versoes' no projeto.yaml).")

    fontes = escolher_fontes(len(versoes), [v.get("fontes") for v in versoes])
    sfx_a = escolher_sfx("abertura", len(versoes), [v.get("sfx_abertura") for v in versoes])
    sfx_f = escolher_sfx("fechamento", len(versoes), [v.get("sfx_fechamento") for v in versoes])

    tmpl = TEMPLATES[p.get("template", "divine")]
    aud = p.get("audio") or {}
    voz = ler_audio(base, dur) if aud.get("original", True) else None
    pendente = str(p.get("autorizacao_imagem", "pendente")).lower() not in ("sim", "nao_aparece", "proprio")
    resultado = []
    for i in idx:
        v = versoes[i]
        nome = v.get("nome", f"V{i + 1}")
        print(f"• {nome}: fontes {fontes[i]} · SFX {'+'.join(sfx_a[i])} / {'+'.join(sfx_f[i])}")
        plano = tmpl.montar(p, v, fontes[i], dur, W, H, sfx_a[i], sfx_f[i])
        ach_v = revisar(p, plano.textos_tela)
        if any(x.nivel == "erro" for x in ach_v) and not a.forcar:
            for x in ach_v:
                print("  " + x.linha())
            raise SystemExit(f"Revisor bloqueou {nome}.")
        mix = mixar(plano.duracao_total, voz, plano.eventos_sfx, aud.get("trilha", True), semente=7 + i)
        wav = trabalho / f"{nome}_mix.wav"
        salvar_wav(mix, wav)
        master = trabalho / f"{nome}_master.mov"
        seg = renderizar(base, plano, W, H, fps, wav, master, dur)
        hook_txt = " ".join(b.get("titulo", "") for b in (v.get("hook") or [])) if isinstance(v.get("hook"), list) \
            else (v.get("hook") or {}).get("titulo", "")
        arq = f"{p.get('data', hoje())}_{p.get('formato', 'reels')}_{slug(p.get('titulo', 'video'), 30)}_{nome}_" \
              f"{slug(hook_txt.replace('*', ''), 28)}{'_autorizacao-pendente' if pendente else ''}.mp4"
        if a.rapido:
            arq = arq.replace(".mp4", "_PREVIA.mp4")
        ex = exportar(master, saida / arq, alta_qualidade=meta["alta_qualidade"], rapido=a.rapido)
        folha = quadros(saida / arq, trabalho / f"{nome}_quadros.jpg")
        print(f"  ✓ {arq} · {ex['mb']} MB · render {seg:.0f}s")
        resultado.append({"nome": nome, "arquivo": arq, "mb": ex["mb"], "fontes": fontes[i], "hook_id": v.get("hook_id"),
                          "hook": hook_txt, "sfx_abertura": sfx_a[i], "sfx_fechamento": sfx_f[i],
                          "duracao": round(plano.duracao_total, 1), "quadros": str(folha.relative_to(pasta))})

    if p.get("legenda"):
        (saida / "legenda.txt").write_text(p["legenda"].strip() + "\n", encoding="utf-8")
    _relatorio(p, resultado, linha_checklist(p, ach), ach, time.time() - t_ini)
    if not a.teste and not a.rapido:
        registrar(p.get("titulo", pasta.name), resultado)
    print(f"Pronto em {time.time() - t_ini:.0f}s. Relatório: {(pasta / 'relatorio.md').relative_to(ROOT)}")


def _relatorio(p, res, checklist, achados, segundos):
    linhas = [f"# {p.get('titulo')} · relatório do Divine Studio", "",
              f"Gerado em {_dt.datetime.now():%d/%m/%Y %H:%M} · formato {p.get('formato', 'reels')} · "
              f"template {p.get('template', 'divine')} · {segundos:.0f}s de processamento", "",
              "| Versão | Hook | Banco | Fontes | SFX | Duração | Tamanho | Arquivo |",
              "|---|---|---|---|---|---|---|---|"]
    for r in res:
        linhas.append(f"| {r['nome']} | {r['hook']} | {r['hook_id'] or ''} | {r['fontes']} | "
                      f"{' + '.join(r['sfx_abertura'] + r['sfx_fechamento'])} | {r['duracao']}s | {r['mb']} MB | "
                      f"`saida/{r['arquivo']}` |")
    linhas += ["", f"**Compliance:** {checklist}"]
    if achados:
        linhas += [""] + [f"- {x.linha()}" for x in achados]
    (p["_pasta"] / "relatorio.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def cmd_regra(a):
    pref = dict(load("preferencias"))
    regras = list(pref.get("regras_aprendidas") or [])
    regras.append({"data": hoje(), "regra": a.texto})
    pref["regras_aprendidas"] = regras
    cab = "# Regras de edição do Renato (docs/CONHECIMENTO_DIVINE.md, seção 7). Valores usados pelo template.\n"
    save("preferencias", pref, cab)
    doc = ROOT / "docs" / "CONHECIMENTO_DIVINE.md"
    if doc.exists():
        with open(doc, "a", encoding="utf-8") as f:
            f.write(f"- {_dt.date.today():%d/%m/%Y}: {a.texto}\n")
    print("Regra registrada em config/preferencias.yaml e docs/CONHECIMENTO_DIVINE.md (seção 12).")


def cmd_quadros(a):
    from .exportar import quadros
    v = Path(a.video)
    out = quadros(v, v.with_name(v.stem + "_quadros.jpg"), n=a.n)
    print(out)


def cmd_verificar(a):
    """Confere dependências, fontes e SFX."""
    ok = True
    for prog in ("ffmpeg", "ffprobe"):
        if not shutil.which(prog):
            print(f"✗ {prog} não encontrado (Mac: brew install ffmpeg)")
            ok = False
    for mod in ("PIL", "numpy", "yaml"):
        try:
            __import__(mod)
        except ImportError:
            print(f"✗ módulo {mod} faltando (pip3 install -r requirements.txt)")
            ok = False
    from .fonts import pasta_fontes
    faltam = set()
    for c in load("fontes")["combinacoes"].values():
        for papel in ("titulo", "apoio", "destaque"):
            if not (pasta_fontes() / c[papel]["arquivo"]).exists():
                faltam.add(c[papel]["arquivo"])
    for f in list(load("fontes")["marca"].values()) + ["CormorantGaramond[wght].ttf", "Jost[wght].ttf"]:
        if not (pasta_fontes() / f).exists():
            faltam.add(f)
    if faltam:
        print("✗ fontes faltando: " + ", ".join(sorted(faltam)) + "\n  rode: bash Biblioteca_Fontes/baixar_fontes.sh")
        ok = False
    sfx = ROOT / load("sfx")["pasta"]
    if not sfx.exists() or not any(sfx.glob("*.wav")):
        print("✗ kit de SFX ausente: python3 Biblioteca_SFX/gerar_kit_sfx.py Biblioteca_SFX/1_kit_original_divine")
        ok = False
    simb = ROOT / load("marca")["logo"]["simbolo_png"]
    print(f"{'✓' if simb.exists() else '•'} logo: {'PNG oficial' if simb.exists() else 'usando o SVG vetorial'}")
    print("✓ tudo pronto" if ok else "Ajuste os itens acima.")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="divine", description="Divine Studio: edição de vídeo da Divine Medical Spa")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("novo", help="cria projetos/AAAA-MM-DD_nome com projeto.yaml modelo")
    s.add_argument("nome")
    s.set_defaults(f=cmd_novo)
    s = sub.add_parser("info", help="mostra resolução, HDR, duração e se precisa do modo alta qualidade")
    s.add_argument("video")
    s.set_defaults(f=cmd_info)
    s = sub.add_parser("revisar", help="revisor de compliance do projeto")
    s.add_argument("projeto")
    s.set_defaults(f=cmd_revisar)
    s = sub.add_parser("editar", help="monta a base, renderiza as versões e exporta")
    s.add_argument("projeto")
    s.add_argument("--versoes", help="ex.: V1,V3")
    s.add_argument("--refazer-base", action="store_true")
    s.add_argument("--forcar", action="store_true", help="ignora bloqueios do revisor (só para teste interno)")
    s.add_argument("--teste", action="store_true", help="não registra no histórico de rodízio")
    s.add_argument("--rapido", action="store_true", help="prévia rápida (exportação veryfast, nome com _PREVIA)")
    s.set_defaults(f=cmd_editar)
    s = sub.add_parser("regra", help="registra uma regra aprendida")
    s.add_argument("texto")
    s.set_defaults(f=cmd_regra)
    s = sub.add_parser("quadros", help="folha de contato de um vídeo")
    s.add_argument("video")
    s.add_argument("--n", type=int, default=6)
    s.set_defaults(f=cmd_quadros)
    s = sub.add_parser("verificar", help="confere dependências, fontes e SFX")
    s.set_defaults(f=cmd_verificar)
    a = ap.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main(sys.argv[1:])
