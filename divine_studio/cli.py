"""Linha de comando do Divine Studio.

  python3 -m divine_studio novo "co2 no corpo"
  python3 -m divine_studio info bruto/IMG_1234.MOV
  python3 -m divine_studio revisar projetos/2026-10-28_co2-no-corpo
  python3 -m divine_studio editar projetos/2026-10-28_co2-no-corpo [--versoes V1,V3] [--teste]
  python3 -m divine_studio transcrever projetos/2026-10-28_co2-no-corpo [--motor faster_whisper]
  python3 -m divine_studio auto projetos/2026-10-28_co2-no-corpo --previa   (edição automática)
  python3 -m divine_studio cortar projetos/2026-10-28_co2-no-corpo
  python3 -m divine_studio hooks sortear --tema "laser co2"
  python3 -m divine_studio hooks novo "Frase / com *destaque.*" --tipo curiosidade
  python3 -m divine_studio voz bruto/IMG_1234.MOV
  python3 -m divine_studio regra "texto da regra"
  python3 -m divine_studio painel
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


def _digital_base(p, tamanho=None) -> str:
    """Tudo o que muda a base: se nada disso mudou, a base é reaproveitada.
    Inclui tamanho e data de cada bruto (vídeo reenviado com o mesmo nome refaz a base) e as configs usadas."""
    from .ingest import resolver
    arquivos = {}
    for c in p.get("clipes") or []:
        try:
            st = resolver(p, c["arquivo"]).stat()
            arquivos[c["arquivo"]] = [st.st_size, int(st.st_mtime)]
        except (SystemExit, OSError, KeyError):
            arquivos[c.get("arquivo", "?")] = None
    cfg = {"exportacao": load("exportacao"), "animacao": load("preferencias").get("animacao")}
    return json.dumps({**{k: p.get(k) for k in ("clipes", "dissolve", "zoom_respiro", "formato", "template", "qualidade", "cor")},
                       "tamanho": tamanho, "arquivos": arquivos, "cfg": cfg}, sort_keys=True, default=str)


def _base(p, arq: Path, w: int, h: int, refazer: bool = False) -> dict:
    """Monta (ou reaproveita) uma base de vídeo do tamanho pedido."""
    from .ingest import construir_base
    meta_arq = arq.with_suffix(".json")
    dig = _digital_base(p, [w, h])
    if not refazer and arq.exists() and meta_arq.exists():
        try:
            meta = json.loads(meta_arq.read_text(encoding="utf-8"))
            if meta.get("_digital") == dig:
                return meta
        except Exception:
            pass
    print(f"• Montando {arq.stem} (cortes, HDR, recorte, dissolve)…")
    meta = construir_base(p, w, h, arq)
    meta["_digital"] = dig
    meta_arq.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


def _transcritor(pasta: Path, motor: str | None = None, refazer: bool = False, ocr: dict | None = None):
    """Fala de cada bruto: transcrição (padrão) ou OCR da legenda queimada (texto_da_fala: ocr)."""
    from .transcricao import transcrever
    cache = {}

    def fn(arq: Path) -> list:
        k = str(arq)
        if k not in cache:
            if ocr is not None:
                from .ocr import ler_legenda_queimada
                cache[k] = ler_legenda_queimada(arq, pasta / "trabalho" / "transcricoes",
                                                tuple(ocr.get("faixa", (0.70, 0.88))), float(ocr.get("passo", 0.4)))
            else:
                cache[k] = transcrever(arq, pasta / "trabalho" / "transcricoes", motor, refazer)
        return cache[k]
    return fn


def _ocr_cfg(p):
    t = p.get("texto_da_fala")
    if t == "ocr":
        return {}
    return t if isinstance(t, dict) and t.get("modo") == "ocr" else None


def _precisa_fala(p) -> bool:
    from .legendas import ativas
    return bool(p.get("corte_limpo") or any(c.get("corte_limpo") for c in p.get("clipes") or [])
                or ativas(p) or any(m.get("na_fala") for m in p.get("mensagens") or []))


def _versao_ia(p, a) -> None:
    """Acrescenta a versão IA (guardada em trabalho/versao_ia.json para a final sair igual à prévia)."""
    from . import aprendizado
    from .hooks import batidas_do_hook
    if getattr(a, "sem_ia", False) or p.get("versao_ia") is False:
        return
    arq = p["_pasta"] / "trabalho" / "versao_ia.json"
    arq.parent.mkdir(exist_ok=True)
    if arq.exists():
        v = json.loads(arq.read_text(encoding="utf-8"))
    else:
        rod = p["_pasta"] / "trabalho" / "rodizio_escolhido.json"
        usadas = [x.get("fontes") for x in (json.loads(rod.read_text(encoding="utf-8")).values() if rod.exists() else [])]
        usadas += [v.get("fontes") for v in p.get("versoes") or []]
        v = aprendizado.versao_ia(p, p.get("versoes") or [], [u for u in usadas if u])
        if not v:
            return
        arq.write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")
    v = dict(v)
    if v.get("hook_id") and not v.get("hook"):
        try:
            v["hook"] = batidas_do_hook(v["hook_id"])
        except SystemExit:
            return
    if not any(x.get("nome") == "IA" for x in p.get("versoes") or []):
        p["versoes"] = list(p.get("versoes") or []) + [v]
        print(f"  IA: {'; '.join(v.get('porque', []))}")


def _entregar(p, arq: Path, nome_versao: str) -> None:
    """Final aprovada: cópia em entregas/AAAA-MM/<tipo>/ e status 'aprovado' na programação."""
    from . import aprendizado
    if not load("preferencias").get("aprendizado", {}).get("entregas", True):
        return
    tipo = {"reels": "Instagram Reels", "stories": "Instagram Stories", "feed45": "Instagram Feed",
            "feed11": "Instagram Feed", "tv": "TV da clinica"}.get(p.get("formato", "reels"), "Outros")
    if p.get("uso_interno"):
        tipo = "Uso interno (nao postar)"
    destino = ROOT / "entregas" / str(p.get("data", hoje()))[:7] / tipo
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copy2(arq, destino / arq.name)
    atual = next((x for x in p.get("publicacoes") or [] if x.get("versao") == nome_versao), {})
    status = atual.get("status") if atual.get("status") in ("agendado", "postado") else "aprovado"
    aprendizado.marcar(p["_pasta"], nome_versao, arquivo=f"saida/{arq.name}", status=status,
                       rede="tv" if p.get("formato") == "tv" else "instagram",
                       entrega=str((destino / arq.name).relative_to(ROOT)))


def _resolver_hooks(p) -> None:
    """hook vazio + hook_id = frase do banco; hook: auto = sorteio (positivo, curiosidade, negativo), guardado."""
    from .hooks import batidas_do_hook, sortear
    versoes = p.get("versoes") or []
    arq = p["_pasta"] / "trabalho" / "hooks_sorteados.json"
    guardados = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}
    from .hooks import por_id
    for nome_v, hid in list(guardados.items()):
        h = por_id(hid)
        if not h or h["uso_interno"] or h["reprovado"] or not h["batidas"]:
            del guardados[nome_v]          # deixou de valer: sorteia outro
    pedem = [v for v in versoes if v.get("hook") == "auto" and not v.get("hook_id")]
    faltam = [v for v in pedem if v.get("nome") not in guardados]
    if faltam:
        ja = {v.get("hook_id") for v in versoes if v.get("hook_id")} | set(guardados.values())
        novos = sortear(len(faltam), tema=p.get("titulo"), semente=sum(map(ord, p["_pasta"].name)), excluir=ja)
        for v, h in zip(faltam, novos):
            guardados[v.get("nome")] = h["id"]
        arq.parent.mkdir(exist_ok=True)
        arq.write_text(json.dumps(guardados, indent=1, ensure_ascii=False), encoding="utf-8")
    for v in versoes:
        if v in pedem and v.get("nome") in guardados:
            v["hook_id"] = guardados[v["nome"]]
            v["hook"] = None
        if not v.get("hook") and v.get("hook_id"):
            v["hook"] = batidas_do_hook(v["hook_id"])
            print(f"  {v.get('nome')}: hook {v['hook_id']} do banco: {' → '.join(b['titulo'] for b in v['hook'])}")


def cmd_editar(a):
    from . import efeitos3d
    try:                                   # kit de sons virais (cria os que faltam, rápido)
        from .config import ROOT as _R, load as _L
        from .sfx_viral import garantir
        garantir(_R / _L("sfx")["pasta"])
    except Exception as e:
        print(f"  aviso: kit de sons virais não criado ({e})")
    efeitos3d.RAPIDO["ligado"] = bool(getattr(a, "rapido", False))
    from .audio import ler_audio, mixar, salvar_wav
    from .compliance import linha_checklist, revisar
    from .exportar import exportar, quadros
    from .compliance import nota_viral
    from .render import renderizar
    from .rodizio import escolher_fontes, escolher_sfx, registrar
    from .templates import TEMPLATES

    t_ini = time.time()
    p = ler_projeto(Path(a.projeto))
    pasta = p["_pasta"]
    if p.get("template", "divine") not in TEMPLATES:
        raise SystemExit(f"Template '{p.get('template')}' não existe. Opções: {', '.join(TEMPLATES)}")
    tmpl = TEMPLATES[p.get("template", "divine")]
    if hasattr(tmpl, "preparar"):
        tmpl.preparar(p)
    if p.get("anuncio"):                               # anúncio: texto no topo, cartão final com o botão, copy A/B
        from . import anuncios
        anuncios.preparar(p)
        arq_copy = anuncios.salvar_copy(pasta, p)
        print(f"• Anúncio: copy com 3 variações em {arq_copy.relative_to(pasta)}")
    W, H = _formato(p)
    fps = load("exportacao")["fps"]
    trabalho, saida = pasta / "trabalho", pasta / "saida"
    trabalho.mkdir(exist_ok=True)
    saida.mkdir(exist_ok=True)

    print(f"Divine Studio {__version__} · {p.get('titulo')} · template {p.get('template', 'divine')} · "
          f"{p.get('formato', 'reels')} {W}x{H}")
    _resolver_hooks(p)
    _versao_ia(p, a)
    transcrever_fn = _transcritor(pasta, ocr=_ocr_cfg(p)) if _precisa_fala(p) else None
    md_cortes = ""
    if transcrever_fn and (p.get("corte_limpo") or any(c.get("corte_limpo") for c in p.get("clipes") or [])):
        from .corte import expandir_clipes
        print("• Corte limpo (muletas, takes repetidos, pausas longas)…")
        p["clipes"], md_cortes = expandir_clipes(p, transcrever_fn)
        (trabalho / "cortes.md").write_text(f"# Corte limpo · {p.get('titulo')}\n\n{md_cortes}\n", encoding="utf-8")
    from .legenda_post import garantir
    if garantir(p):
        print("• Legenda do post gerada (não havia no projeto.yaml); revise em saida/legenda.txt")
    ach = revisar(p)
    erros = [x for x in ach if x.nivel == "erro"]
    for x in ach:
        print("  " + x.linha())
    if erros and not a.forcar:
        raise SystemExit("Revisor bloqueou a exportação. Corrija os erros acima (ou use --forcar para um teste interno).")

    base = trabalho / "base.mov"
    bw, bh = tmpl.tamanho_base(p, W, H) if hasattr(tmpl, "tamanho_base") else (W, H)
    meta = _base(p, base, bw, bh, a.refazer_base)
    extras_video = []
    for ex in (tmpl.extras(p, W, H) if hasattr(tmpl, "extras") else []):
        arq_ex = trabalho / f"{ex['nome']}.mov"
        _base({**p, "clipes": ex["clipes"]}, arq_ex, ex["largura"], ex["altura"], a.refazer_base)
        extras_video.append((arq_ex, ex["largura"], ex["altura"]))
    dur = float(meta["duracao"])
    print(f"  base: {dur:.1f}s · alta qualidade: {'sim' if meta['alta_qualidade'] else 'não'}")
    p["_base_meta"] = meta
    if transcrever_fn:
        from .legendas import palavras_na_base
        try:
            original = (p.get("audio") or {}).get("original", True)
            trans = {c["caminho"]: transcrever_fn(Path(c["caminho"])) for c in meta["clipes"]
                     if original and c.get("caminho") and not _clipe_mudo(p, c)}
            p["_fala"] = palavras_na_base(meta["clipes"], trans)
            # dublagem gravada no painel: a fala dela também vira legenda, no tempo em que entra
            for d in (p.get("audio") or {}).get("dublagem") or []:
                from .ingest import resolver
                off = float(d.get("inicio", 0))
                p["_fala"] += [{**w, "inicio": round(w["inicio"] + off, 3), "fim": round(w["fim"] + off, 3)}
                               for w in transcrever_fn(resolver(p, d["arquivo"]))]
            p["_fala"].sort(key=lambda w: w["inicio"])
            (trabalho / "fala_base.json").write_text(json.dumps(p["_fala"], ensure_ascii=False), encoding="utf-8")
        except SystemExit as e:
            # legenda da fala e mensagens na fala são opcionais: segue sem elas (o corte limpo já teria parado antes)
            print(f"  aviso: sem a fala transcrita, a legenda da fala e o na_fala ficam de fora.\n  {e}")

    versoes = p.get("versoes") or []
    if a.versoes:
        quero = {v.strip() for v in a.versoes.split(",")}
        idx = [i for i, v in enumerate(versoes) if v.get("nome") in quero]
    else:
        idx = list(range(len(versoes)))
    if not idx:
        raise SystemExit("Nenhuma versão para renderizar (lista 'versoes' no projeto.yaml).")

    # rodízio decidido uma vez por projeto e guardado: a final sai igual à prévia que foi aprovada
    arq_rod = trabalho / "rodizio_escolhido.json"
    guardado = json.loads(arq_rod.read_text(encoding="utf-8")) if arq_rod.exists() else {}
    def _g(campo):
        return [v.get(campo) or (guardado.get(v.get("nome", f"V{k + 1}")) or {}).get(campo)
                for k, v in enumerate(versoes)]
    fontes = escolher_fontes(len(versoes), _g("fontes"))
    sfx_a = escolher_sfx("abertura", len(versoes), _g("sfx_abertura"))
    sfx_f = escolher_sfx("fechamento", len(versoes), _g("sfx_fechamento"))
    sfx_t = escolher_sfx("transicao", len(versoes), _g("sfx_transicao"),
                         ocupados=[a_ + f_ for a_, f_ in zip(sfx_a, sfx_f)])
    if p.get("sfx_automaticos") is False:          # só os sons colocados à mão na linha do tempo
        sfx_a = sfx_f = sfx_t = [[] for _ in versoes]
    arq_rod.write_text(json.dumps({v.get("nome", f"V{k + 1}"): {
        "fontes": fontes[k], "sfx_abertura": sfx_a[k], "sfx_fechamento": sfx_f[k], "sfx_transicao": sfx_t[k]}
        for k, v in enumerate(versoes)}, indent=1, ensure_ascii=False), encoding="utf-8")

    aud = p.get("audio") or {}
    voz = ler_audio(base, dur) if aud.get("original", True) else None
    voz = _com_dublagem(p, voz, dur)
    modo_voz = "sem voz"
    so_storyboard = bool(getattr(a, "storyboard", False))
    if voz is not None and not so_storyboard:
        voz, modo_voz = _voz_limpa(p, voz, base, trabalho)
    pendente = str(p.get("autorizacao_imagem", "pendente")).lower() not in ("sim", "nao_aparece", "proprio")
    resultado = []
    plano = None
    # prévias: cada versão num processo (usa os núcleos do Mac; 4 versões saem quase no tempo de 2)
    import os as _os
    filho = _os.environ.get("DIVINE_FILHO") == "1"
    n_par = min(len(idx), max(1, (_os.cpu_count() or 2) // 2))
    if a.rapido and not so_storyboard and not filho and n_par > 1:
        resultado = _render_paralelo(pasta, [versoes[i].get("nome", f"V{i + 1}") for i in idx], n_par, trabalho)
        idx = []
    for i in idx:
        v = versoes[i]
        nome = v.get("nome", f"V{i + 1}")
        print(f"• {nome}: fontes {fontes[i]} · SFX {'+'.join(sfx_a[i])} / {'+'.join(sfx_t[i])} / {'+'.join(sfx_f[i])}")
        from . import estilos
        pv, v = estilos.aplicar(p, v, dur)                      # estilo de edição (config/estilos.yaml)
        if isinstance(v.get("hook"), list) and pv.get("mensagens"):   # a frase que virou hook não se repete no meio
            from .roteirista import _sem_marca
            ganchos_v = {_sem_marca(b.get("titulo", "")) for b in v["hook"]}
            pv = {**pv, "mensagens": [m for m in pv["mensagens"] if _sem_marca(m.get("titulo", "")) not in ganchos_v]}
        if pv.get("_estilo"):
            print(f"  estilo de edição: {pv['_estilo']}")
        plano = tmpl.montar(pv, v, fontes[i], dur, W, H, sfx_a[i], sfx_f[i], sfx_t[i])
        usou_t = [n for n in sfx_t[i] if any(e[1] == n for e in plano.eventos_sfx)]
        ach_v = revisar(p, plano.textos_tela)
        if any(x.nivel == "erro" for x in ach_v) and not a.forcar:
            for x in ach_v:
                print("  " + x.linha())
            raise SystemExit(f"Revisor bloqueou {nome}.")
        _gravar_linha(trabalho, nome, p, plano)
        if so_storyboard:                                      # só os quadros da edição, sem render
            from . import storyboard
            sb = storyboard.gerar(pasta, nome, plano, pv, base, W, H, dur, (bw, bh), extras_video, versao_idx=i,
                                  estilo=pv.get("_estilo", ""))
            print(f"  ✓ storyboard {nome}: {sb['cenas_total']} cenas · {sb['momentos_total']} momentos · "
                  f"{sb['segundos']:.0f}s (nada renderizado)")
            resultado.append({"nome": nome, "storyboard": f"trabalho/storyboard_{nome}.json"})
            continue
        try:                                                   # suas opiniões: sons mais altos ou mais baixos
            from .feedback import ajustes as _aj
            off = float(_aj().get("ganho_sons_db", 0.0))
            if off:
                plano.eventos_sfx = [(t_, n_, g_ + off) for t_, n_, g_ in plano.eventos_sfx]
        except Exception:
            pass
        voz_v = voz
        if voz is not None and aud.get("volume_original_db"):
            voz_v = voz * float(10 ** (float(aud["volume_original_db"]) / 20))
        mix = mixar(plano.duracao_total, voz_v, plano.eventos_sfx, aud.get("trilha", True), semente=7 + i,
                    musica=_musica(p), volume_trilha_db=aud.get("volume_trilha_db"))
        wav = trabalho / f"{nome}_mix.wav"
        salvar_wav(mix, wav)
        master = trabalho / f"{nome}_master.mov"
        seg = renderizar(base, plano, W, H, fps, wav, master, dur, (bw, bh), extras_video)
        hook_txt = " ".join(b.get("titulo", "") for b in (v.get("hook") or [])) if isinstance(v.get("hook"), list) \
            else (v.get("hook") or {}).get("titulo", "")
        hook_slug = slug(hook_txt.replace("*", ""), 28) if hook_txt.strip() else ""
        cat = p.get("categoria") if p.get("categoria") != p.get("formato") else None
        tema = f"{cat}_{slug(p.get('tema', ''), 24)}" if cat else slug(p.get("tema") or p.get("titulo", "video"), 30)
        arq = f"{p.get('data', hoje())}_{p.get('formato', 'reels')}_{tema}_{nome}_" \
              f"{hook_slug}{'_autorizacao-pendente' if pendente else ''}" \
              f"{'_USO-INTERNO-NAO-POSTAR' if p.get('uso_interno') else ''}.mp4"
        arq = arq.replace("__", "_").replace("_.mp4", ".mp4")
        if a.rapido:
            arq = arq.replace(".mp4", "_PREVIA.mp4")
        ex = exportar(master, saida / arq, alta_qualidade=meta["alta_qualidade"], rapido=a.rapido,
                      limite_mb=p.get("limite_mb"), tv=p.get("formato") == "tv")
        nota = nota_viral(p, plano, ach_v, voz is not None)
        n_ef = len([e for e in (p.get("efeitos") or []) + (getattr(plano, "efeitos_auto", None) or [])])
        try:                                               # onde a atenção pode cair (e como resolver)
            from . import atencao
            atencao.salvar(trabalho, nome, atencao.analisar(plano, p, voz, base))
        except Exception as e:
            print(f"  aviso: análise de atenção indisponível ({e})")
        (trabalho / f"nota_{nome}.json").write_text(json.dumps({
            **nota, "media": round(sum(nota["notas"].values()) / max(1, len(nota["notas"])), 1),
            "duracao": round(plano.duracao_total, 1), "efeitos": n_ef, "sons": len(plano.eventos_sfx),
            "arquivo": f"saida/{arq}"}, ensure_ascii=False), encoding="utf-8")
        if not a.rapido and not a.teste and not p.get("uso_interno_sem_entrega"):
            _entregar(p, saida / arq, nome)
        folha = quadros(saida / arq, trabalho / f"{nome}_quadros.jpg")
        print(f"  ✓ {arq} · {ex['mb']} MB · render {seg:.0f}s")
        resultado.append({"nome": nome, "arquivo": arq, "mb": ex["mb"], "fontes": fontes[i], "hook_id": v.get("hook_id"),
                          "hook": hook_txt, "sfx_abertura": sfx_a[i], "sfx_fechamento": sfx_f[i],
                          "sfx_transicao": usou_t, "nota": nota,
                          "duracao": round(plano.duracao_total, 1), "quadros": str(folha.relative_to(pasta))})

    if so_storyboard:
        print(f"Storyboard pronto em {time.time() - t_ini:.0f}s. Responda 'aprovado' ou 'código: o que mudar'.")
        return
    if filho:                                   # processo de uma versão: o principal junta tudo e faz o relatório
        for r in resultado:
            (trabalho / f"resultado_{r['nome']}.json").write_text(json.dumps(r, ensure_ascii=False, default=str),
                                                                    encoding="utf-8")
        return
    if p.get("legenda"):
        (saida / "legenda.txt").write_text(p["legenda"].strip() + "\n", encoding="utf-8")
    extras = [f"Voz: limpeza {modo_voz}"]
    if md_cortes:
        extras.append("Corte limpo: ver `trabalho/cortes.md`")
    if p.get("_fala"):
        extras.append(f"Fala transcrita: {len(p['_fala'])} palavras"
                      + (" · legenda sincronizada na tela" if plano is None or any(c.nome.startswith("legenda") for c in plano.camadas)
                         else ""))
    _relatorio(p, resultado, linha_checklist(p, ach), ach, time.time() - t_ini, extras)
    if not a.teste and not a.rapido:
        from . import registro
        with registro.trava():
            load.cache_clear()
            registrar(p.get("titulo", pasta.name), resultado)
            registro.registrar(p, resultado, linha_checklist(p, ach), escolher_fontes(3))
        print("• Registrado em docs/INDICE_VIDEOS_EDITADOS.md, no histórico do banco de hooks e no mapa")
    print(f"Pronto em {time.time() - t_ini:.0f}s. Relatório: {(pasta / 'relatorio.md').relative_to(ROOT)}")


def _render_paralelo(pasta: Path, nomes: list, n_par: int, trabalho: Path) -> list:
    """Renderiza as prévias em paralelo (um processo por versão) e devolve o resultado de cada uma, na ordem."""
    import os
    import subprocess
    import threading
    print(f"• Renderizando {len(nomes)} versões em paralelo ({n_par} de cada vez)…", flush=True)
    for n in nomes:
        (trabalho / f"resultado_{n}.json").unlink(missing_ok=True)
    # cada processo com a sua fatia de núcleos: sem isso as threads de cálculo (numpy) se atropelam e tudo fica lento
    fatia = str(max(1, (os.cpu_count() or 2) // n_par))
    env = {**os.environ, "DIVINE_FILHO": "1", "PYTHONUNBUFFERED": "1", "OMP_NUM_THREADS": fatia,
           "OPENBLAS_NUM_THREADS": fatia, "MKL_NUM_THREADS": fatia, "VECLIB_MAXIMUM_THREADS": fatia,
           "NUMEXPR_NUM_THREADS": fatia, "DIVINE_FFMPEG_THREADS": fatia}
    fila, trava, falhas = list(nomes), threading.Lock(), []

    def trabalhar():
        while True:
            with trava:
                if not fila:
                    return
                n = fila.pop(0)
            proc = subprocess.Popen([sys.executable, "-u", "-m", "divine_studio", "editar", str(pasta), "--rapido",
                                     "--versoes", n], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
            for linha in proc.stdout:
                ln = linha.rstrip()
                if ln.startswith(("  ✓", "• " + n, "  aviso", "  [", "  estilo", "  ritmo")) or "Erro" in ln or "erro" in ln:
                    print(f"  [{n}] {ln.strip()}", flush=True)
            if proc.wait() != 0:
                falhas.append(n)

    ts = [threading.Thread(target=trabalhar) for _ in range(n_par)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    if falhas:
        raise SystemExit(f"A prévia de {', '.join(falhas)} parou com erro (veja o log acima).")
    out = []
    for n in nomes:
        arq = trabalho / f"resultado_{n}.json"
        if arq.exists():
            out.append(json.loads(arq.read_text(encoding="utf-8")))
    return out


def cmd_higgsfield(a):
    from . import higgsfield as hf
    if a.acao == "fila":
        for x in hf.listar():
            print(f"  {x['id']}  {x['status']:<9} {x['nome']:<22} {x['projeto']}  {x['entrada'].get('arquivo', '')}")
    elif a.acao == "instrucao":
        print(hf.instrucao_claude())
    elif a.acao == "analise":                 # Virality Predictor: a leitura (texto) vira sugestão no projeto
        if not (a.id and a.valor):
            raise SystemExit('Use: higgsfield analise <id> "<o que o Virality Predictor disse>"')
        r = hf.atualizar(a.id, status="pronto", analise=a.valor, **({"creditos": a.creditos} if a.creditos else {}))
        print(f"✓ análise guardada em {r['projeto']} (aparece em Sugestões para a próxima)")
    elif a.acao == "pronto":
        if not (a.id and a.valor):
            raise SystemExit("Use: higgsfield pronto <id> <arquivo ou link>")
        r = hf.receber(a.id, a.valor, a.job, a.creditos)
        print(f"✓ resultado em {r['projeto']}/{r['resultado']['arquivo']}")
    else:
        if not (a.id and a.valor):
            raise SystemExit("Use: higgsfield status <id> <pendente|gerando|erro|cancelado>")
        r = hf.atualizar(a.id, status=a.valor, **({"nota": a.nota} if a.nota else {}))
        print(f"✓ {r['id']} agora está {r['status']}")


def cmd_lab(a):
    from . import lab
    print("Placar dos formatos:")
    for x in lab.placar(a.conta):
        print(f"  {x['nome']:<38} {x['status']:<22} testes {x['testes']}  vitórias {x['vitorias']}  radar {x['radar']}")
    print("\nTestes da semana:")
    for x in lab.plano_semana(a.conta):
        print(f"  {x['dia']:<8} {x['nome']:<38} {x['motivo']}\n           gancho: {x['gancho']}")


def cmd_radar(a):
    from . import radar
    if a.acao == "missao":
        print(radar.missao(a.rede))
    elif a.acao == "buscar":
        print(radar.buscar_instagram())
    elif a.acao == "colar":
        texto = Path(a.arquivo).read_text(encoding="utf-8") if a.arquivo else sys.stdin.read()
        print(radar.importar_texto(texto))
    else:
        for i in radar.em_alta():
            print(f"  {i.get('outlier') or '-':>5}x  {i.get('rede'):<9} @{i.get('conta', ''):<20} "
                  f"{i.get('formato_viral') or '?':<18} {i.get('link', '')}")


def cmd_storyboard(a):
    from . import storyboard
    pasta = ler_projeto(Path(a.projeto))["_pasta"]
    if a.responder:
        r = storyboard.responder(pasta, a.responder, a.versao)
        if r["aprovado"]:
            print("✓ Storyboard aprovado. Finalizando a edição...")
            a.storyboard, a.rapido, a.teste = False, False, False
            return cmd_editar(a)
        for x in r["aplicados"]:
            print(f"  ✓ {x}")
        for x in r["avisos"]:
            print(f"  ! {x}")
        for x in r["nao_entendi"]:
            print(f"  ? não entendi: {x.get('codigo') or ''} {x['pedido']} "
                  "(ex.: 4B: troca o título por \"...\" · 7: tira · 2A: entra mais cedo · 3: mais longo 1s)")
        if not r["aplicados"]:
            return
        print("• Refazendo o storyboard com as mudanças...")
    cmd_editar(a)


def _gravar_linha(trabalho, nome, p, plano):
    """O que entrou sozinho nesta versão (efeitos do ritmo e sons automáticos), para a linha do tempo mostrar e editar."""
    manuais = {(s.get("nome"), round(float(s.get("inicio", 0)), 2)) for s in p.get("sons") or []}
    auto_ef = getattr(plano, "efeitos_auto", []) or []
    sons_ef = {(e.get("som"), round(float(e["inicio"]), 2)) for e in (p.get("efeitos") or []) + auto_ef if e.get("som")}
    inicios_ef = {round(float(e.get("inicio", 0)), 2) for e in (p.get("efeitos") or []) + auto_ef}
    sfx = [{"nome": n, "inicio": round(float(t), 2), "ganho_db": round(float(g), 1)} for t, n, g in plano.eventos_sfx
           if (n, round(float(t), 2)) not in manuais and (n, round(float(t), 2)) not in sons_ef
           and round(float(t), 2) not in inicios_ef]          # som que nasce junto com um efeito fica no efeito
    efs = [{k: v for k, v in e.items() if not k.startswith("_")} for e in auto_ef]
    (trabalho / f"linha_{nome}.json").write_text(json.dumps({"versao": nome, "efeitos": efs, "sons": sfx},
                                                            ensure_ascii=False, indent=1), encoding="utf-8")


def _musica(p):
    """Música de fora só com licença comercial declarada (o revisor bloqueia sem ela)."""
    m = (p.get("audio") or {}).get("musica")
    if not m:
        return None
    from .audio import ler_audio
    from .ingest import resolver
    return ler_audio(resolver(p, m))


def _clipe_mudo(p, meta_clipe) -> bool:
    return any(c.get("mudo") for c in p.get("clipes") or [] if c.get("arquivo") == meta_clipe.get("arquivo"))


def _com_dublagem(p, voz, dur: float):
    """Soma as gravações de voz do painel (audio.dublagem: [{arquivo, inicio, ganho_db}]) à voz da base."""
    import numpy as np
    from .audio import SR, db, ler_audio
    from .ingest import resolver
    dubs = (p.get("audio") or {}).get("dublagem") or []
    if not dubs:
        return voz
    n = int(dur * SR)
    out = voz.copy() if voz is not None else np.zeros((n, 2), np.float32)
    for d in dubs:
        a = ler_audio(resolver(p, d["arquivo"]))
        i = int(float(d.get("inicio", 0)) * SR)
        if i >= n:
            continue
        a = a[: n - i] * db(float(d.get("ganho_db", 0)))
        out[i:i + len(a)] += a
    return out


def _voz_limpa(p, voz, base: Path, trabalho: Path):
    """Limpa a voz da base uma vez e guarda (refaz só se a base ou o modo mudarem)."""
    from .audio import ler_audio, salvar_wav
    from .voz import limpar
    modo = (p.get("audio") or {}).get("limpeza") or load("preferencias").get("voz", {}).get("modo", "auto")
    arq, meta = trabalho / "voz_limpa.wav", trabalho / "voz_limpa.json"
    from .ingest import resolver
    dubs = [[d.get("arquivo"), d.get("inicio"), d.get("ganho_db"), resolver(p, d["arquivo"]).stat().st_mtime]
            for d in (p.get("audio") or {}).get("dublagem") or []]
    chave = {"base": base.stat().st_mtime, "modo": modo, "dublagem": dubs,
             "original": (p.get("audio") or {}).get("original", True)}
    if arq.exists() and meta.exists():
        m = json.loads(meta.read_text(encoding="utf-8"))
        if m.get("chave") == chave:
            return ler_audio(arq, len(voz) / 48000), m["modo_usado"]
    limpo, usado, medida = limpar(voz, modo)
    print(f"• Voz: ruído {medida['ruido_db']} dB, fala {medida['fala_db']} dB → limpeza {usado}")
    salvar_wav(limpo, arq)
    meta.write_text(json.dumps({"chave": chave, "modo_usado": usado, "medida": medida}), encoding="utf-8")
    return limpo, usado


def _relatorio(p, res, checklist, achados, segundos, extras=None):
    linhas = [f"# {p.get('titulo')} · relatório do Divine Studio", "",
              f"Gerado em {_dt.datetime.now():%d/%m/%Y %H:%M} · formato {p.get('formato', 'reels')} · "
              f"template {p.get('template', 'divine')} · {segundos:.0f}s de processamento", "",
              "| Versão | Hook | Banco | Fontes | SFX | Duração | Tamanho | Arquivo |",
              "|---|---|---|---|---|---|---|---|"]
    for r in res:
        linhas.append(f"| {r['nome']} | {r['hook']} | {r['hook_id'] or ''} | {r['fontes']} | "
                      f"{' + '.join(r['sfx_abertura'] + r.get('sfx_transicao', []) + r['sfx_fechamento'])} | {r['duracao']}s | {r['mb']} MB | "
                      f"`saida/{r['arquivo']}` |")
    linhas += [""] + [f"- {x}" for x in extras or []]
    for v in p.get("versoes") or []:
        if v.get("nome") == "IA" and v.get("porque"):
            linhas.append(f"- **Versão IA (a que o app acredita ser a melhor):** {'; '.join(v['porque'])}")
    for r in res:
        n = r.get("nota")
        if n:
            linhas.append(f"- **Nota viral {r['nome']}:** " + " · ".join(f"{k} {v}" for k, v in n["notas"].items())
                          + (f" (dicas: {'; '.join(n['dicas'])})" if n["dicas"] else ""))
    linhas += ["", f"**Compliance:** {checklist}"]
    if achados:
        linhas += [""] + [f"- {x.linha()}" for x in achados]
    (p["_pasta"] / "relatorio.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def cmd_transcrever(a):
    from .ingest import resolver
    p = ler_projeto(Path(a.projeto))
    fn = _transcritor(p["_pasta"], a.motor, a.refazer)
    linhas = [f"# Transcrição · {p.get('titulo')}", ""]
    vistos = set()
    for c in p.get("clipes") or []:
        if c.get("mudo") or c["arquivo"] in vistos:
            continue
        vistos.add(c["arquivo"])
        pal = fn(resolver(p, c["arquivo"]))
        txt = " ".join(w["texto"] for w in pal)
        linhas += [f"## {c['arquivo']}", "", txt or "(sem fala)", ""]
        print(f"{c['arquivo']}: {len(pal)} palavras")
    out = p["_pasta"] / "trabalho" / "transcricao.md"
    out.write_text("\n".join(linhas), encoding="utf-8")
    print(f"Texto corrido em {out.relative_to(ROOT)} (para corrigir uma palavra: trabalho/transcricoes/*.editado.json)")


def cmd_cortar(a):
    from .corte import expandir_clipes
    p = ler_projeto(Path(a.projeto))
    if not any(c.get("corte_limpo") for c in p.get("clipes") or []):
        p["corte_limpo"] = True    # simula para revisar, mesmo antes de ligar no projeto
    _, md = expandir_clipes(p, _transcritor(p["_pasta"]))
    out = p["_pasta"] / "trabalho" / "cortes.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(f"# Corte limpo · {p.get('titulo')}\n\n{md}\n", encoding="utf-8")
    print(md)
    print(f"\nRevisão em {out.relative_to(ROOT)}. Para usar: corte_limpo: true no projeto.yaml; "
          "trecho ruim que ficou: remover_trechos: [\"frase exata\"].")


def cmd_hooks(a):
    from . import hooks
    if a.acao == "sortear":
        tema = a.tema
        if a.projeto:
            tema = tema or ler_projeto(Path(a.projeto)).get("titulo")
        for h in hooks.sortear(a.n, tema=tema):
            print(f"{h['id']:8} {h['tipo']:12} {' → '.join(h['batidas'])}")
    elif a.acao == "ver":
        for hid in a.texto:
            h = hooks.por_id(hid)
            print(f"{hid}: " + (f"{h['tipo']} · {h['descricao']}" if h else "não encontrado"))
    elif a.acao == "novo":
        if not a.texto:
            raise SystemExit('Uso: hooks novo "Frase do hook / com *destaque.*" --tipo curiosidade')
        hid = hooks.adicionar(" ".join(a.texto), a.tipo, a.fontes or "", a.sfx or "")
        print(f"{hid} acrescentado em docs/BANCO_HOOKS.md (bloco E)")
    else:
        from collections import Counter
        b = hooks.ler_banco()
        prontos = [h for h in b if h["batidas"] and not h["uso_interno"] and not h["reprovado"]]
        print(f"{len(b)} hooks no banco, {len(prontos)} com frase pronta: "
              + ", ".join(f"{k} {v}" for k, v in Counter(h["tipo"] for h in prontos).items()))


def cmd_voz(a):
    from .audio import ler_audio
    from .voz import escolher_modo, medir_ruido
    m = medir_ruido(ler_audio(Path(a.arquivo)))
    print(f"ruído de fundo {m['ruido_db']} dB · fala {m['fala_db']} dB · distância {m['snr_db']} dB → "
          f"limpeza sugerida: {escolher_modo(m)}")


def cmd_pacote(a):
    from .pacote import montar_pacote
    p = ler_projeto(Path(a.projeto))
    cats = [c.strip() for c in a.categorias.split(",")] if a.categorias else None
    fn = _transcritor(p["_pasta"]) if a.com_fala else None
    if fn is None:
        try:
            from .transcricao import motor_disponivel
            if motor_disponivel() or any((p["_pasta"] / "trabalho" / "transcricoes").glob("*.json")):
                fn = _transcritor(p["_pasta"])
        except Exception:
            fn = None
    criadas = montar_pacote(p, cats, fn)
    for pasta, nome in criadas:
        print(f"  {nome:28} {pasta.relative_to(ROOT)}")
    print(f"{len(criadas)} peças criadas. Revise os projeto.yaml e rode editar em cada uma (ou use --renderizar).")
    if a.renderizar:
        for pasta, nome in criadas:
            print(f"\n=== {nome}")
            cmd_editar(argparse.Namespace(projeto=str(pasta), versoes=None, refazer_base=False, forcar=False,
                                          teste=a.teste, rapido=a.rapido))


def cmd_cortes(a):
    from .cortes_longos import montar
    p = ler_projeto(Path(a.projeto))
    fn = None
    try:
        from .transcricao import motor_disponivel
        if motor_disponivel() or any((p["_pasta"] / "trabalho" / "transcricoes").glob("*.json")):
            fn = _transcritor(p["_pasta"])
    except Exception:
        fn = None
    if fn is None:
        print("  sem transcrição: os cortes seguem as pausas do áudio (com faster-whisper eles seguem as frases)")
    criadas = montar(p, fn)
    for pasta, nome, c in criadas:
        print(f"  {nome:22} {c['de']}–{c['ate']} ({c['duracao_s']:.0f}s, nota {c['nota']})  {pasta.relative_to(ROOT)}")
    print(f"{len(criadas)} cortes criados. Abra cada um no painel e gere as prévias.")


def cmd_legenda(a):
    from .compliance import revisar
    from .legenda_post import gerar
    p = ler_projeto(Path(a.projeto))
    p["legenda"] = gerar(p)
    for x in revisar(p, []):
        print("  " + x.linha())
    out = p["_pasta"] / "saida" / "legenda.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text(p["legenda"], encoding="utf-8")
    print(p["legenda"])
    print(f"Salva em {out.relative_to(ROOT)}")


def cmd_carrossel(a):
    from . import carrossel
    if a.acao == "novo":
        pasta = carrossel.novo(" ".join(a.alvo), a.formula, a.objetivo, a.estilo)
        print(f"Carrossel criado: {pasta.relative_to(ROOT)} (edite no painel ou no projeto.yaml)")
        return
    p = ler_projeto(Path(a.alvo[0]))
    if p.get("tipo") != "carrossel":
        raise SystemExit("Este projeto não é um carrossel.")
    r = carrossel.exportar(p["_pasta"], p)
    print(f"{len(r['cards'])} cards exportados · {Path(r['zip']).relative_to(ROOT)}\n{r['checklist']}")


def cmd_post(a):
    from . import post
    if a.acao == "novo":
        pasta = post.novo(" ".join(a.alvo), estilo=a.estilo)
        print(f"Post criado: {pasta.relative_to(ROOT)} (edite no painel ou no projeto.yaml)")
        return
    p = ler_projeto(Path(a.alvo[0]))
    if p.get("tipo") != "post":
        raise SystemExit("Este projeto não é um post estático.")
    r = post.exportar(p["_pasta"], p)
    print(f"{len(r['arquivos'])} imagem(ns) exportada(s)\n{r['checklist']}")


def cmd_antes_depois(a):
    from . import antes_depois
    if a.acao == "novo":
        pasta = antes_depois.novo(" ".join(a.alvo), a.subtitulo or "")
        print(f"Antes e depois criado: {pasta.relative_to(ROOT)} (uso interno). Envie as fotos em bruto/ e liste os pares.")
        return
    p = ler_projeto(Path(a.alvo[0]))
    if p.get("tipo") != "antes_depois":
        raise SystemExit("Este projeto não é um antes e depois.")
    r = antes_depois.exportar(p["_pasta"], p)
    print(f"{len(r['arquivos'])} arquivo(s) de uso interno em entregas/ ({antes_depois.ENTREGA})")


def cmd_importar(a):
    from .importar import importar
    r = importar(a.origem, a.copiar, a.simular)
    print(f"Origem: {r['origem']} ({r['modo']})")
    for x in r["projetos"]:
        print(f"  {x['titulo']}: {x['editados']} editado(s), {x['brutos']} bruto(s), {x['prontos']} pronto(s) para postar"
              + (" · uso interno" if x["uso_interno"] else "") + f"  ->  projetos/{x['projeto']}")
    print(f"{len(r['projetos'])} projeto(s)." + (" Nada foi gravado (simulação)." if a.simular else ""))


def cmd_formatos(a):
    from . import formatos
    p = ler_projeto(Path(a.projeto))
    lista = [f.strip() for f in a.formatos.split(",")] if a.formatos else formatos.formatos_do_projeto(p)
    (p["_pasta"] / "trabalho").mkdir(exist_ok=True)
    _resolver_hooks(dict(p, versoes=[dict(v) for v in p.get("versoes") or []]))   # sorteia e guarda os hooks do principal
    criadas = formatos.gerar(p, lista)
    if not criadas:
        raise SystemExit("Nenhum formato novo para gerar (o principal já está nesse formato?).")
    for pasta, nome in criadas:
        print(f"\n=== {nome}  ({pasta.relative_to(ROOT)})")
        cmd_editar(argparse.Namespace(projeto=str(pasta), versoes=None, refazer_base=False, forcar=False,
                                      teste=a.teste, rapido=not a.final))


def cmd_auto(a):
    from . import auto
    from .transcricao import motor_disponivel
    p = ler_projeto(Path(a.projeto))
    tem_cache = any((p["_pasta"] / "trabalho" / "transcricoes").glob("*.json")) \
        if (p["_pasta"] / "trabalho" / "transcricoes").exists() else False
    fn = _transcritor(p["_pasta"]) if (motor_disponivel() or tem_cache) else None
    semente = sum(map(ord, p["_pasta"].name))
    novo = auto.montar(p, a.template, fn, semente)
    # roteirista: as 3 versões escritas EM CIMA da fala (como o Claude faz no chat), não pelo título
    falados = [c for c in novo.get("clipes") or [] if not c.get("mudo")]
    if fn and falados:
        try:
            from . import roteirista
            palavras = []
            for c in falados:
                palavras += fn(p["_pasta"] / c["arquivo"])
            if palavras:
                plano = roteirista.planejar(novo, palavras)
                novo = roteirista.aplicar(novo, plano)
                print(f"• Roteiro pela fala ({'Claude' if plano.get('fonte') == 'ia' else 'regras do app'}): "
                      f"{len(novo.get('mensagens') or [])} mensagem(ns), {len(novo.get('efeitos') or [])} efeito(s) no ponto da fala")
        except SystemExit as e:
            print(f"  aviso: roteiro pela fala indisponível ({e})")
    elif not fn:
        print("  aviso: SEM TRANSCRIÇÃO. O app não entende a fala e usa textos genéricos do tema. "
              "Instale com: pip3 install faster-whisper (o Divine Studio.command instala sozinho ao atualizar).")
    try:                                   # cada versão testa um formato viral diferente (Laboratório)
        from . import lab
        from .instagram import conta_do_projeto
        lab.aplicar_em_versoes(novo, conta_do_projeto(novo))
        print("• Formatos em teste: " + ", ".join(f"{v['nome']} {lab.nome(v.get('formato_viral'))}"
                                                   for v in novo.get("versoes") or []))
    except Exception as e:
        print(f"  aviso: laboratório de formatos indisponível ({e})")
    chave, _ = auto.tema(novo.get("titulo", ""))
    (p["_pasta"] / "trabalho" / "versao_ia.json").unlink(missing_ok=True)   # edição nova: a aposta IA é refeita
    arq = auto.salvar(p, novo)
    print(f"• Tema reconhecido: {chave} · template {novo['template']} · {len(novo['clipes'])} clipe(s) · "
          f"{len(novo['mensagens'])} mensagem(ns) · {len(novo['versoes'])} versão(ões)")
    print(f"Projeto montado em {arq.relative_to(ROOT)}")
    if a.previa:
        print()
        cmd_editar(argparse.Namespace(projeto=a.projeto, versoes=None, refazer_base=False, forcar=False,
                                      teste=False, rapido=True))


def cmd_efeitos(a):
    from . import efeitos
    if a.prancha:
        efeitos.prancha(a.prancha, a.fontes)
        print(f"Prancha em {a.prancha}")
        return
    tab = load("efeitos")["codigos"]
    for cod, e in tab.items():
        print(f"{cod}  {'✓ ' + e['tipo'] if e.get('tipo') else '· sem módulo':18} {e['nome']}"
              + (f"  ({e['obs']})" if e.get("obs") else ""))
    print("Tipos: " + ", ".join(sorted(efeitos.TIPOS) + sorted(efeitos.QUADRO)))


def cmd_painel(a):
    from .painel import rodar
    rodar(a.porta, not a.sem_navegador, a.celular)


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
    from .transcricao import motor_disponivel
    m = motor_disponivel()
    print(f"{'✓' if m else '•'} transcrição: " + (m or "nenhum motor (pip3 install faster-whisper ou ASSEMBLYAI_API_KEY); "
                                                 "só precisa para corte limpo e legenda da fala"))
    from .biblioteca import logo
    simb = logo("divine-simbolo") or ROOT / load("marca")["logo"]["simbolo_png"]
    print(f"{'✓' if simb.exists() else '•'} logo: {'oficial (' + simb.name + ')' if simb.exists() else 'usando o SVG vetorial'}")
    try:
        from .painel import diagnostico
        print("Extras:")
        for d in diagnostico():
            print(f"  {'✓' if d['ok'] else '•'} {d['item']}" + ("" if d["ok"] else f"  ({d['dica']})"))
    except Exception as e:                 # diagnóstico extra nunca bloqueia
        print(f"  (diagnóstico extra indisponível: {e})")
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
    s.add_argument("--sem-ia", action="store_true", help="não gera a versão IA")
    s.set_defaults(f=cmd_editar)
    s = sub.add_parser("storyboard", help="a edição em quadros reais, antes de renderizar (aprove ou peça mudanças)")
    s.add_argument("projeto")
    s.add_argument("--versoes", help="ex.: V1 (padrão: todas)")
    s.add_argument("--responder", help='"aprovado" ou "4B: troca o título por ...; 7: tira"')
    s.add_argument("--versao", default="V1", help="versão a que a resposta se refere")
    s.add_argument("--refazer-base", action="store_true")
    s.add_argument("--forcar", action="store_true")
    s.add_argument("--sem-ia", action="store_true")
    s.set_defaults(f=cmd_storyboard, rapido=False, teste=True, storyboard=True)
    s = sub.add_parser("entrada", help="analisa os vídeos novos da caixa de entrada (pasta ou Google Drive)")
    s.add_argument("--conta", help="perfil (dvmedicalspa ou drdanielmendess)")
    s.set_defaults(f=lambda a: __import__("divine_studio.entrada", fromlist=["varrer"]).varrer(a.conta))
    s = sub.add_parser("lab", help="laboratório de formatos: placar e plano de testes da semana")
    s.add_argument("--conta")
    s.set_defaults(f=cmd_lab)
    s = sub.add_parser("radar", help="radar viral: buscar (API oficial), missão do Claude no Chrome ou colar resultado")
    s.add_argument("acao", choices=["buscar", "missao", "colar", "listar"])
    s.add_argument("--rede", default="instagram")
    s.add_argument("--arquivo", help="arquivo com o resultado colado (para 'colar')")
    s.set_defaults(f=cmd_radar)
    s = sub.add_parser("higgsfield", help="fila de pedidos do Higgsfield (o Claude executa com o conector)")
    s.add_argument("acao", choices=["fila", "instrucao", "pronto", "status", "analise"])
    s.add_argument("id", nargs="?")
    s.add_argument("valor", nargs="?", help="pronto: arquivo ou link do resultado · status: pendente|gerando|erro|cancelado")
    s.add_argument("--job", default="")
    s.add_argument("--creditos", type=float)
    s.add_argument("--nota", default="")
    s.set_defaults(f=cmd_higgsfield)
    s = sub.add_parser("transcrever", help="transcreve a fala dos clipes (tempo por palavra)")
    s.add_argument("projeto")
    s.add_argument("--motor", choices=["auto", "assemblyai", "faster_whisper", "whisper"])
    s.add_argument("--refazer", action="store_true")
    s.set_defaults(f=cmd_transcrever)
    s = sub.add_parser("cortar", help="prévia do corte limpo em trabalho/cortes.md")
    s.add_argument("projeto")
    s.set_defaults(f=cmd_cortar)
    s = sub.add_parser("hooks", help="banco de hooks: resumo | sortear | ver ID | novo \"frase\"")
    s.add_argument("acao", nargs="?", default="resumo", choices=["resumo", "sortear", "ver", "novo"])
    s.add_argument("texto", nargs="*")
    s.add_argument("--n", type=int, default=3)
    s.add_argument("--tema")
    s.add_argument("--projeto")
    s.add_argument("--tipo", choices=["positivo", "curiosidade", "negativo"])
    s.add_argument("--fontes")
    s.add_argument("--sfx")
    s.set_defaults(f=cmd_hooks)
    s = sub.add_parser("voz", help="mede o ruído de um arquivo e sugere o modo de limpeza")
    s.add_argument("arquivo")
    s.set_defaults(f=cmd_voz)
    s = sub.add_parser("pacote", help="cria as peças por categoria (longo, médio, curto, viral, POV, cortes, TV...)")
    s.add_argument("projeto")
    s.add_argument("--categorias", help="ex.: reels-curto,tv,stories (lista em config/pacote.yaml)")
    s.add_argument("--com-fala", action="store_true", help="transcreve para cortar por frases")
    s.add_argument("--renderizar", action="store_true")
    s.add_argument("--rapido", action="store_true")
    s.add_argument("--teste", action="store_true")
    s.set_defaults(f=cmd_pacote)
    s = sub.add_parser("legenda", help="gera a legenda do post em saida/legenda.txt")
    s.add_argument("projeto")
    s.set_defaults(f=cmd_legenda)
    s = sub.add_parser("carrossel", help='carrossel: novo "tema" [--formula] | exportar <pasta>')
    s.add_argument("acao", choices=["novo", "exportar"])
    s.add_argument("alvo", nargs="+")
    s.add_argument("--formula", default="lista", choices=["lista", "mito_verdade", "metodo", "pergunta", "expectativa", "livre"])
    s.add_argument("--objetivo", choices=["salvar", "enviar", "comentar", "seguir"])
    s.add_argument("--estilo", default="divine", choices=["divine", "claro", "daniel", "george", "pessoal"])
    s.set_defaults(f=cmd_carrossel)
    s = sub.add_parser("cortes", help="vídeo longo vira cortes curtos, médios, longos, melhores momentos e Stories")
    s.add_argument("projeto")
    s.set_defaults(f=cmd_cortes)
    s = sub.add_parser("importar", help="traz os vídeos brutos e editados da pasta Divine Medical Spa Marketing")
    s.add_argument("origem", nargs="?")
    s.add_argument("--copiar", action="store_true", help="copia os arquivos (padrão: atalhos, sem ocupar espaço)")
    s.add_argument("--simular", action="store_true", help="só mostra o que seria importado")
    s.set_defaults(f=cmd_importar)
    s = sub.add_parser("post", help='post estático (Feed, Stories e TV): novo "tema" | exportar <pasta>')
    s.add_argument("acao", choices=["novo", "exportar"])
    s.add_argument("alvo", nargs="+")
    s.add_argument("--estilo", default="divine", choices=["divine", "claro", "daniel", "george", "pessoal"])
    s.set_defaults(f=cmd_post)
    s = sub.add_parser("antesdepois", help='antes e depois de USO INTERNO (TV, Stories, Feed): novo "título" | exportar <pasta>')
    s.add_argument("acao", choices=["novo", "exportar"])
    s.add_argument("alvo", nargs="+")
    s.add_argument("--subtitulo")
    s.set_defaults(f=cmd_antes_depois)
    s = sub.add_parser("formatos", help="a mesma edição em Stories, Feed e TV (padrão: formatos do projeto ou stories,tv)")
    s.add_argument("projeto")
    s.add_argument("--formatos", help="ex.: stories,feed45,tv")
    s.add_argument("--final", action="store_true", help="exporta a final (sem isso, prévias)")
    s.add_argument("--teste", action="store_true")
    s.set_defaults(f=cmd_formatos)
    s = sub.add_parser("auto", help="edição automática: monta o projeto.yaml a partir dos brutos (e gera as prévias)")
    s.add_argument("projeto")
    s.add_argument("--template", choices=["divine", "daniel", "george", "tv", "react", "pessoal"])
    s.add_argument("--previa", action="store_true", help="já gera as 3 prévias depois de montar")
    s.set_defaults(f=cmd_auto)
    s = sub.add_parser("efeitos", help="lista os efeitos EC/EV; --prancha arquivo.jpg mostra todos")
    s.add_argument("--prancha")
    s.add_argument("--fontes", default="B")
    s.set_defaults(f=cmd_efeitos)
    s = sub.add_parser("painel", help="abre a interface no navegador (http://127.0.0.1:8765)")
    s.add_argument("--porta", type=int, default=8765)
    s.add_argument("--sem-navegador", action="store_true")
    s.add_argument("--celular", action="store_true", help="aceita o iPhone na mesma rede Wi-Fi, com código de acesso")
    s.set_defaults(f=cmd_painel)
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
