"""Testes da fase 4: efeitos cinéticos, legenda do post, pacote por categorias e registro."""
import numpy as np
import pytest
import yaml

from divine_studio import compliance, efeitos, legenda_post, pacote, registro
from divine_studio.config import load
from divine_studio.fonts import combinacao


@pytest.mark.parametrize("tipo", sorted(efeitos.EXEMPLOS))
def test_cada_efeito_gera_camadas_ou_efeito_de_quadro(tipo):
    ef = {"tipo": tipo, "inicio": 1.0, **efeitos.EXEMPLOS[tipo]}
    combo = combinacao("B")
    q = np.zeros((480, 270, 3), np.uint8)
    if tipo in efeitos.TIPOS:
        cams = efeitos.TIPOS[tipo](ef, combo, 270, 480, 5)
        assert cams and all(c.t0 >= 1.0 for c in cams)
        for c in cams:
            c.pintar(q, (c.t0 + c.t1) / 2)
    else:
        f, cams = efeitos.QUADRO[tipo](ef, combo, 270, 480, 5)
        q = f(q, 2.0)
        for c in cams:
            c.pintar(q, 2.0)
    assert q.max() > 0                       # desenhou alguma coisa


@pytest.mark.parametrize("tipo", ["zoom_digital", "fundo_pip", "cortina", "filme", "texto_atras"])
def test_efeitos_de_quadro_mantem_tamanho(tipo):
    ef = {"tipo": tipo, "inicio": 0.0, "texto": "CAPA"}
    r = efeitos.QUADRO[tipo](ef, combinacao("B"), 270, 480, 5)
    f = r[0] if isinstance(r, tuple) else r
    q = (np.random.default_rng(0).random((480, 270, 3)) * 255).astype(np.uint8)
    out = f(q, 0.8)
    assert out.shape == q.shape and out.dtype == np.uint8
    assert f(q, 99.0) is q                    # fora do intervalo não mexe


def test_efeitos_espacados_no_minimo_intervalo():
    lst = efeitos.espacar([{"tipo": "circulo", "inicio": 2.0}, {"tipo": "contador", "inicio": 2.5},
                           {"tipo": "riscado", "inicio": 8.0}], 1.5)
    assert [e["inicio"] for e in lst] == [2.0, 3.5, 8.0]


def test_codigos_ec_ev_resolvem_para_modulos():
    tab = load("efeitos")["codigos"]
    assert len(tab) == 33
    for cod, e in tab.items():
        if e.get("tipo"):
            assert e["tipo"] in efeitos.TIPOS or e["tipo"] in efeitos.QUADRO, cod
    assert efeitos.resolver_tipo({"codigo": "EC06"}) == "riscado"
    with pytest.raises(SystemExit):
        efeitos.resolver_tipo({"codigo": "EC09"})        # tremor: fora do estilo suave


def test_efeito_no_plano_respeita_fechamento():
    from divine_studio.templates import divine
    p = {"titulo": "t", "versoes": [{"nome": "V1", "hook": [{"titulo": "Oi"}]}],
         "efeitos": [{"tipo": "contador", "inicio": 3, "de": 0, "ate": 12, "sufixo": " TESLA"},
                     {"tipo": "circulo", "inicio": 50}]}
    pl = divine.montar(p, p["versoes"][0], "B", 10.0, 540, 960, [], [], [])
    nomes = [c.nome for c in pl.camadas]
    assert "ef_contador" in nomes and "ef_circulo" not in nomes
    assert all(c.t1 <= pl.inicio_fechamento for c in pl.camadas if c.nome.startswith("ef_"))


# legenda do post

def _proj(**kw):
    p = {"titulo": "Laser de CO2 no corpo", "conteudo_medico": True,
         "versoes": [{"nome": "V1", "hook": [{"titulo": "Essa luz vermelha / é só a *mira.*"}]}],
         "mensagens": [{"titulo": "Energia que *estimula*", "apoio": "a renovação — da pele"}],
         "fechamento": {"frase": "Cada pele no *seu tempo.*"}}
    p.update(kw)
    return p


def test_legenda_segue_as_regras_e_passa_no_revisor():
    leg = legenda_post.gerar(_proj())
    linhas = leg.splitlines()
    assert linhas[0].startswith("Essa luz vermelha é só a mira.")
    assert "Resultados variam de pessoa para pessoa." in leg and "CRM/SP 186.470" in leg
    assert "Av. Paulista 1636 - Ao lado do MASP" in leg
    assert "—" not in leg and "*" not in leg
    tags = [w for w in leg.split() if w.startswith("#")]
    assert 8 <= len(tags) <= 12 and "#laserco2" in tags
    assert not [a for a in compliance.revisar({**_proj(), "legenda": leg}, []) if a.nivel == "erro"]


def test_legenda_pessoal_sem_marca():
    leg = legenda_post.gerar(_proj(marca="pessoal", conteudo_medico=False))
    assert "Divine" not in leg and "CRM" not in leg and "#" not in leg


def test_garantir_nao_sobrescreve():
    p = _proj(legenda="Minha legenda.")
    assert not legenda_post.garantir(p) and p["legenda"] == "Minha legenda."


# pacote

def test_pacote_cria_pecas_com_duracao_alvo(tmp_path):
    import subprocess
    origem = tmp_path / "projetos" / "2026-10-28_co2"
    (origem / "bruto").mkdir(parents=True)
    for k in range(2):
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=160x284:r=30:d=12",
                        "-c:v", "libx264", "-preset", "ultrafast", str(origem / "bruto" / f"c{k}.mp4")], check=True)
    p = {"_pasta": origem, "titulo": "CO2", "clipes": [{"arquivo": "bruto/c0.mp4"}, {"arquivo": "bruto/c1.mp4"}],
         "versoes": [{"nome": "V1", "hook_id": "A-H18"}], "legenda": "x"}
    criadas = pacote.montar_pacote(p, ["reels-curto", "tv", "cortes"])
    nomes = [c[0].name for c in criadas]
    assert nomes == ["03_reels-curto", "09_tv"]        # cortes precisam de fala: pulado
    curto = yaml.safe_load((origem.parent / "2026-10-28_co2-pacote" / "03_reels-curto" / "projeto.yaml").read_text())
    dur = sum(c["fim"] - c["inicio"] for c in curto["clipes"])
    assert dur == pytest.approx(20, abs=0.5)
    assert curto["clipes"][0]["arquivo"] == "../../2026-10-28_co2/bruto/c0.mp4"
    assert len(curto["versoes"]) == 3 and "legenda" not in curto
    tv = yaml.safe_load((origem.parent / "2026-10-28_co2-pacote" / "09_tv" / "projeto.yaml").read_text())
    assert tv["template"] == "tv" and tv["audio"]["original"] is False


def test_trechos_de_frase_com_corte_seco():
    sel = [({"arquivo": "a.mov"}, 0.0, 2.0, "x."), ({"arquivo": "a.mov"}, 3.0, 5.0, "y."),
           ({"arquivo": "b.mov"}, 0.0, 1.0, "z.")]
    cl = pacote._clipes_de_trechos(sel)
    assert [c.get("corte_seco", False) for c in cl] == [False, True, False]
    assert len(pacote._cortes(sel, 3.0, 3)) == 2


# registro

def test_registro_escreve_indice_historico_e_mapa(tmp_path, monkeypatch):
    import shutil
    from divine_studio.config import ROOT
    for nome in ("BANCO", "MAPA"):
        dst = tmp_path / f"{nome}.md"
        shutil.copy(getattr(registro, nome), dst)
        monkeypatch.setattr(registro, nome, dst)
    monkeypatch.setattr(registro, "INDICE", tmp_path / "INDICE.md")
    p = {"_pasta": ROOT / "projetos" / "2026-10-28_teste", "titulo": "Teste", "data": "2026-10-28"}
    res = [{"nome": "V1", "hook": "Oi", "hook_id": "A-H18", "fontes": "B", "sfx_abertura": ["brilho_dourado_a"],
            "sfx_fechamento": ["cristal_a"], "arquivo": "v1.mp4", "nota": {"notas": {"hook": 10, "leitura": 8}}}]
    registro.registrar(p, res, "OK CFM / OK Anvisa / autorização de imagem: ok", ["C", "H", "L"])
    ind = (tmp_path / "INDICE.md").read_text()
    assert "28/10/2026 · Teste" in ind and "| V1 | Oi | A-H18 | B |" in ind and "| 9.0 |" in ind
    banco = (tmp_path / "BANCO.md").read_text()
    assert "(Teste): fontes B" in banco and "começar por C, H ou L." in banco
    mapa = (tmp_path / "MAPA.md").read_text()
    assert "`projetos/2026-10-28_teste/`" in mapa.split("## 2.")[0]
    registro.mapa(p, res)                                 # não duplica
    assert (tmp_path / "MAPA.md").read_text().count("`projetos/2026-10-28_teste/`") == 1
