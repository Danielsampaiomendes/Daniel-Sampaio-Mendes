"""Padrão viral luxo, Vídeo Épico, menu de edições, galeria, copy da dublagem e importador."""
import shutil
import subprocess

import numpy as np
import pytest
import yaml

from divine_studio import aprendizado, carrossel, copy_voz, importar, painel, ritmo


def test_ritmo_viral_e_epico_nao_batem_nos_seus_efeitos():
    manual = {"tipo": "contador", "inicio": 6.0}
    for m in ("viral", "epico"):
        auto = ritmo.planejar({"ritmo": m, "efeitos": [manual]}, {"nome": "V1"}, 20.0, [8.0, 14.0])
        assert auto and all(e["_auto"] for e in auto)
        for e in auto:
            assert e["inicio"] + e["duracao"] <= 6.0 or e["inicio"] >= 6.0 + 3.2, (m, e)
            assert e["inicio"] + e["duracao"] <= 20.0
    v = ritmo.planejar({"ritmo": "viral"}, {"nome": "V1"}, 20.0)
    e = ritmo.planejar({"ritmo": "epico"}, {"nome": "V1"}, 20.0)
    assert len(e) > len(v)                                                      # épico é mais intenso
    assert e[0]["tipo"] == "cartao_3d" and e[0]["modo"] == "girar"              # abertura épica
    assert any(x.get("som") for x in e)


def test_ritmo_muda_por_versao_e_respeita_calmo_e_tv():
    a = [x["tipo"] for x in ritmo.planejar({"ritmo": "epico"}, {"nome": "V1"}, 24.0)]
    b = [x["tipo"] for x in ritmo.planejar({"ritmo": "epico"}, {"nome": "V2"}, 24.0)]
    assert a != b
    assert ritmo.planejar({"ritmo": "calmo"}, {"nome": "V1"}, 24.0) == []
    assert ritmo.planejar({"template": "tv"}, {"nome": "V1"}, 24.0) == []
    assert ritmo.modo({"epico": True}) == "epico" and ritmo.modo({}) == "viral"


def test_grade_epica_mantem_formato():
    q = (np.random.rand(40, 30, 3) * 255).astype(np.uint8)
    r = ritmo.grade_epica(1.0)(q, 0)
    assert r.shape == q.shape and r.dtype == np.uint8 and not np.array_equal(r, q)


@pytest.fixture
def projetos(tmp_path, monkeypatch):
    p = tmp_path / "projetos"
    p.mkdir()
    for m in (painel, aprendizado):
        monkeypatch.setattr(m, "PROJETOS", p)
    monkeypatch.setattr(importar, "ROOT", tmp_path)
    monkeypatch.setattr(importar, "INDICE", p / ".importacao.json")
    monkeypatch.setattr(carrossel, "ROOT", tmp_path)
    return p


def _projeto(projetos, nome, extra=None):
    pasta = projetos / nome
    for s in ("bruto", "saida", "trabalho"):
        (pasta / s).mkdir(parents=True)
    carrossel.salvar(pasta, {"titulo": "Laser de CO2", "formato": "reels", **(extra or {})})
    return pasta


def test_categoria_do_menu():
    assert painel.categoria({"tipo": "carrossel"}) == "carrossel"
    assert painel.categoria({"formato": "stories"}) == "stories"
    assert painel.categoria({"template": "tv"}) == "tv"
    assert painel.categoria({}) == "video"


def test_galeria_so_mostra_validadas(projetos):
    pasta = _projeto(projetos, "p1")
    for n in ("a_V1_.mp4", "b_V2_.mp4", "c_V3_.mp4"):
        (pasta / "saida" / n).write_bytes(b"x")
    aprendizado.marcar(pasta, "V1", arquivo="saida/a_V1_.mp4", validado=True)
    aprendizado.marcar(pasta, "V2", arquivo="saida/b_V2_.mp4", status="rascunho")
    aprendizado.marcar(pasta, "V3", arquivo="saida/c_V3_.mp4", status="postado")
    assert sorted(i["versao"] for i in painel.galeria()) == ["V1", "V3"]


def test_copy_sugerida_vem_do_projeto_e_respeita_a_salva(projetos):
    pasta = _projeto(projetos, "p2", {"mensagens": [{"titulo": "Estímulo / ao *colágeno.*"}],
                                     "fechamento": {"frase": "Cada pele tem o *seu tempo.*"}})
    c = copy_voz.ler(pasta)
    assert "Estímulo ao colágeno." in c["copy"] and "*" not in c["copy"] and c["segundos"] > 0
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8"))
    d["copy_dublagem"] = "Minha copy."
    carrossel.salvar(pasta, d)
    c = copy_voz.ler(pasta)
    assert c["copy"] == "Minha copy." and c["fonte"] == "sua copy salva" and c["sugerida"] != "Minha copy."
    (pasta / "x_COPY.md").write_text("# título\nTexto do roteiro.", encoding="utf-8")
    assert copy_voz.sugerida(pasta, d)[0] == "Texto do roteiro."


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="sem ffmpeg")
def test_importar_cria_projetos_com_atalhos_sem_mexer_na_origem(projetos, tmp_path):
    origem = tmp_path / "Divine Medical Spa Marketing"
    pronto = origem / "Videos/HIPRO/Pronto para postar"
    pronto.mkdir(parents=True)
    (origem / "Videos/HIPRO/brutos").mkdir()
    (origem / "Videos/_Versoes anteriores").mkdir()
    for f in (pronto / "2026-10-19_reels_HIPRO_V1.mp4", origem / "Videos/HIPRO/TV_HIPRO_16x9.mp4",
              origem / "Videos/HIPRO/brutos/IMG_0001.MOV", origem / "Videos/_Versoes anteriores/velho.mp4"):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=64x112:r=5:d=0.6",
                        "-c:v", "libx264", str(f)], check=True)
    (origem / "Videos/HIPRO/Legendas_HIPRO.md").write_text("legenda", encoding="utf-8")
    antes = sorted(str(p) for p in origem.rglob("*"))
    r = importar.importar(origem)
    assert [x["titulo"] for x in r["projetos"]] == ["HIPRO"]
    pasta = projetos / r["projetos"][0]["projeto"]
    assert (pasta / "bruto/IMG_0001.MOV").is_symlink() and (pasta / "Legendas_HIPRO.md").exists()
    det = painel.detalhe(pasta.name)
    assert len(det["saidas"]) == 2 and all(s["versao"] for s in det["saidas"])
    assert [i["status"] for i in painel.galeria()] == ["aprovado"]              # o "Pronto para postar"
    assert painel._arquivo_do_projeto(pasta, det["saidas"][0]["arquivo"]).is_file()
    importar.importar(origem)                                                   # de novo: não duplica
    assert len(yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8"))["publicacoes"]) == 2
    assert sorted(str(p) for p in origem.rglob("*")) == antes                  # origem intacta


def test_duplicar_e_arquivar_sem_apagar(projetos, tmp_path, monkeypatch):
    monkeypatch.setattr(painel, "ROOT", tmp_path)
    pasta = _projeto(projetos, "2026-11-01_co2")
    (pasta / "bruto" / "a.mp4").write_bytes(b"video")
    aprendizado.marcar(pasta, "V1", status="postado")
    nome = painel.duplicar(pasta.name)
    nova = projetos / nome
    assert nome.endswith("-v2") and (nova / "bruto" / "a.mp4").read_bytes() == b"video"
    assert "publicacoes" not in yaml.safe_load((nova / "projeto.yaml").read_text(encoding="utf-8"))
    destino = painel.arquivar(nome)
    assert not nova.exists() and (tmp_path / destino / "projeto.yaml").exists()


def test_diagnostico_lista_os_itens():
    itens = {d["item"]: d for d in painel.diagnostico()}
    assert "FFmpeg" in itens and "IA (Claude)" in itens and all("ok" in d for d in itens.values())


def test_clipe_novo_nunca_quebra_o_yaml_e_tira_o_exemplo():
    modelo = (painel.Path(painel.__file__).parent / "modelo_projeto.yaml").read_text(encoding="utf-8")
    t = painel.adicionar_clipe(modelo, "bruto/a.mov")
    assert [c["arquivo"] for c in yaml.safe_load(t)["clipes"]] == ["bruto/a.mov"] and "# Projeto de vídeo" in t
    regravado = yaml.safe_dump(yaml.safe_load(modelo), allow_unicode=True, sort_keys=False, default_flow_style=None)
    t2 = painel.adicionar_clipe(painel.adicionar_clipe(regravado, "bruto/a.mov"), "bruto/b.mov")
    assert [c["arquivo"] for c in yaml.safe_load(t2)["clipes"]] == ["bruto/a.mov", "bruto/b.mov"]


def test_reparo_de_projeto_quebrado(tmp_path):
    pasta = tmp_path / "p"
    pasta.mkdir()
    (pasta / "projeto.yaml").write_text("titulo: x\nclipes:\n  - {arquivo: \"bruto/a.mov\"}\n- {arquivo: bruto/IMG_0001.MOV, inicio: 0}\n",
                                        encoding="utf-8")
    assert painel.reparar_projeto(pasta)
    assert [c["arquivo"] for c in yaml.safe_load((pasta / "projeto.yaml").read_text())["clipes"]] == ["bruto/a.mov"]
    assert (pasta / "trabalho" / "projeto.yaml.antes-do-reparo").exists()
    assert not painel.reparar_projeto(pasta)                                   # já está bom: não mexe


def test_conectar_instagram_guarda_fora_do_repositorio(tmp_path, monkeypatch):
    from divine_studio import instagram
    monkeypatch.delenv("INSTAGRAM_TOKEN", raising=False)
    monkeypatch.delenv("INSTAGRAM_USER_ID", raising=False)
    monkeypatch.setattr(instagram, "ARQUIVO", tmp_path / "instagram.json")
    chamadas = []

    def falso(caminho, token=None, **params):
        chamadas.append(caminho)
        return {"data": [{"name": "Divine", "instagram_business_account": {"id": "1784", "username": "dvmedicalspa"}}]}
    monkeypatch.setattr(instagram, "_get", falso)
    assert not instagram.configurado()
    r = instagram.conectar("EAA" + "x" * 40)
    assert r == {"conectado": True, "usuario": "dvmedicalspa", "user_id": "1784"} and chamadas == ["me/accounts"]
    assert oct((tmp_path / "instagram.json").stat().st_mode)[-3:] == "600"
    instagram.desconectar()
    assert not instagram.configurado()
    with pytest.raises(SystemExit):
        instagram.conectar("curto")
