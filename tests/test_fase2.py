"""Testes da fase 2: corte limpo, legenda sincronizada, hooks, rodízio de SFX, voz e linha do tempo da base."""
import shutil
import subprocess

import numpy as np
import pytest

from divine_studio import corte, hooks, legendas, rodizio, voz
from divine_studio.config import load


def _pal(frase, inicio=0.0, passo=0.3, dur=0.25):
    return [{"texto": w, "inicio": round(inicio + k * passo, 3), "fim": round(inicio + k * passo + dur, 3)}
            for k, w in enumerate(frase.split())]


# corte limpo

def test_muleta_e_take_repetido_saem():
    pal = _pal("O laser de CO2 ele O laser de CO2 trabalha hum por dentro")
    fora = corte.marcar_remocoes(pal)
    textos_fora = [pal[i]["texto"] for i in sorted(fora)]
    assert textos_fora == ["O", "laser", "de", "CO2", "ele", "hum"]
    assert fora[10] == "muleta" and fora[0] == "take repetido"


def test_e_verbo_nao_e_muleta():
    pal = _pal("O CO2 é invisível")
    assert not corte.marcar_remocoes(pal)


def test_remover_trecho_do_projeto():
    pal = _pal("A pele responde bem rápido no seu tempo")
    fora = corte.marcar_remocoes(pal, ["bem rápido"])
    assert {pal[i]["texto"] for i in fora} == {"bem", "rápido"}


def test_pausa_longa_vira_pausa_natural():
    pal = _pal("Primeira frase.") + _pal("Segunda frase.", inicio=4.0)
    segs = corte.segmentos(pal, {}, 0, 10)
    assert len(segs) == 2
    pausa = (segs[0][1] - pal[1]["fim"]) + (pal[2]["inicio"] - segs[1][0])   # respiro que sobra dos dois lados
    assert pausa == pytest.approx(load("preferencias")["corte"]["pausa_natural_s"], abs=0.01)


def test_pausa_curta_nao_corta():
    assert len(corte.segmentos(_pal("uma frase sem pausa longa", passo=0.5), {}, 0, 10)) == 1


# legenda sincronizada

def test_blocos_curtos_sem_conectivo_pendurado():
    b = legendas.blocos(_pal("O laser de CO2 trabalha por dentro da pele. Ele estimula o colágeno."))
    txt = [" ".join(w["texto"] for w in g) for g in b]
    assert all(len(g) <= 4 for g in b)
    assert not any(t.split()[-1] in legendas.CONECTIVOS for t in txt)
    assert txt[2] == "da pele."


def test_palavras_vao_para_o_tempo_da_base():
    meta = [{"caminho": "a.mov", "inicio": 2.0, "velocidade": 1.0, "duracao": 3.0, "inicio_base": 0.0},
            {"caminho": "a.mov", "inicio": 8.0, "velocidade": 0.5, "duracao": 4.0, "inicio_base": 3.0}]
    pal = {"a.mov": _pal("x y", inicio=2.5) + _pal("cortada", inicio=6.0) + _pal("z", inicio=9.0)}
    base = legendas.palavras_na_base(meta, pal)
    assert [w["texto"] for w in base] == ["x", "y", "z"]
    assert base[0]["inicio"] == pytest.approx(0.5)
    assert base[2]["inicio"] == pytest.approx(3.0 + (9.0 - 8.0) / 0.5)


def test_correcoes_e_achar_fala():
    pal = legendas.aplicar_correcoes(_pal("a divaine medical spa fica na paulista"), {"divaine": "Divine"})
    assert pal[1]["texto"] == "Divine"
    assert legendas.achar_fala(pal, "fica na Paulista") == pal[4]["inicio"]
    assert legendas.achar_fala(pal, "não existe") is None


# hooks

def test_banco_lido_com_ids_e_batidas():
    h = hooks.por_id("A-H18")
    assert h and h["batidas"][0] == "Essa luz vermelha / é só a *mira.*"
    assert hooks.batidas_do_hook("A-H18")[1]["titulo"] == "O laser de verdade / é *invisível.*"
    assert hooks.por_id("H178")["batidas"] == ["Vou só fazer o procedimento."]   # vários hooks na mesma linha


def test_sorteio_tres_tipos_sem_uso_interno_nem_reprovado():
    s = hooks.sortear(3, semente=4)
    assert [h["tipo"] for h in s] == ["positivo", "curiosidade", "negativo"]
    assert len({h["id"] for h in s}) == 3
    assert not any(h["uso_interno"] or h["reprovado"] or h["modelo"] for h in s)


def test_hook_novo_entra_no_bloco_e(tmp_path, monkeypatch):
    copia = tmp_path / "BANCO_HOOKS.md"
    shutil.copy(hooks.BANCO, copia)
    monkeypatch.setattr(hooks, "BANCO", copia)
    n = hooks.proximo_numero()
    hid = hooks.adicionar("Frase nova / com *destaque.*")
    assert hid == f"H{n}"
    assert hooks.por_id(hid)["batidas"] == ["Frase nova / com *destaque.*"]
    assert f"Próximo número livre: H{n + 1}" in copia.read_text(encoding="utf-8")


# SFX

def test_sfx_por_versao_sem_repetir_e_no_limite_de_familias():
    a = rodizio.escolher_sfx("abertura", 3)
    f = rodizio.escolher_sfx("fechamento", 3)
    t = rodizio.escolher_sfx("transicao", 3, ocupados=[x + y for x, y in zip(a, f)])
    cfg = load("sfx")
    for k in range(3):
        sons = a[k] + f[k] + t[k]
        assert len(sons) == len(set(sons))
        assert len(rodizio.familias(a[k], f[k], t[k])) <= cfg["max_familias"]
        assert sum("impacto" in s for s in sons) <= cfg["max_impactos"]


def test_familia():
    assert rodizio.familia("whoosh_suave_b") == "whoosh_suave"
    assert rodizio.familia("camera_shutter_b_duplo") == "camera_shutter"


# voz

def test_modo_de_limpeza_pelo_ruido():
    rng = np.random.default_rng(0)
    t = np.arange(48000 * 4) / 48000
    fala = (np.sin(2 * np.pi * 200 * t) * (np.sin(2 * np.pi * 0.5 * t) > 0) * 0.3)[:, None].repeat(2, 1)
    limpo = fala + rng.standard_normal(fala.shape) * 0.0005
    sujo = fala + rng.standard_normal(fala.shape) * 0.05
    assert voz.escolher_modo(voz.medir_ruido(limpo.astype(np.float32))) == "minima"
    assert voz.escolher_modo(voz.medir_ruido(sujo.astype(np.float32))) in ("forte", "elevenlabs")


# linha do tempo da base (precisa do FFmpeg)

@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="sem FFmpeg")
def test_base_com_corte_seco_e_dissolve(tmp_path):
    from divine_studio.ingest import construir_base
    for nome, cor in (("a", "red"), ("b", "blue")):
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c={cor}:s=320x568:r=30:d=4",
                        "-f", "lavfi", "-i", "sine=f=300:d=4", "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                        str(tmp_path / f"{nome}.mp4")], check=True)
    proj = {"_pasta": tmp_path, "dissolve": 0.4, "zoom_respiro": 0, "clipes": [
        {"arquivo": "a.mp4", "inicio": 0, "fim": 1.5},
        {"arquivo": "a.mp4", "inicio": 2.5, "fim": 3.5, "_corte_seco": True},
        {"arquivo": "b.mp4", "inicio": 0, "fim": 2}]}
    meta = construir_base(proj, 320, 568, tmp_path / "base.mov")
    ini = [c["inicio_base"] for c in meta["clipes"]]
    assert ini == pytest.approx([0.0, 1.5, 2.1], abs=0.01)
    assert meta["duracao"] == pytest.approx(4.1, abs=0.05)
