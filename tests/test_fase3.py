"""Testes da fase 3: templates (sem renderizar vídeo), revisor ampliado, nota viral e OCR."""
import pytest

from divine_studio import compliance, ocr
from divine_studio.templates import TEMPLATES


def _proj(**kw):
    p = {"titulo": "Teste", "conteudo_medico": True, "autorizacao_imagem": "sim", "posicao_texto": "topo",
         "cta_antecipado": "Manda pra amiga.", "mensagens": [{"titulo": "Uma *ideia.*"}],
         "fechamento": {"frase": "Cada pele no *seu tempo.*"},
         "versoes": [{"nome": "V1", "hook": [{"titulo": "Essa luz / é só a *mira.*"}]}],
         "legenda": "Oi.\nResultados variam de pessoa para pessoa.\nCRM/SP 186.470"}
    p.update(kw)
    return p


def _montar(nome, p=None, W=1080, H=1920):
    p = p or _proj(template=nome)
    t = TEMPLATES[nome]
    if hasattr(t, "preparar"):
        t.preparar(p)
    return p, t.montar(p, p["versoes"][0], p["versoes"][0].get("fontes", "B"), 20.0, W, H,
                       ["brilho_dourado_a"], ["cristal_a"], ["whoosh_suave_a"])


def _nomes(plano):
    return {c.nome for c in plano.camadas} | {c.nome for c in plano.camadas_fechamento}


def test_divine_tem_header_hook_cta_e_fechamento():
    _, pl = _montar("divine")
    assert {"header", "hook0_titulo", "cta_antecipado", "msg0_titulo", "logo_empilhado", "pill_cta"} <= _nomes(pl)
    assert pl.barra_progresso and pl.moldura is None


def test_daniel_e_george_tem_cartao_de_nome():
    for nome in ("daniel", "george"):
        _, pl = _montar(nome)
        assert "cartao_nome" in _nomes(pl) and "cartao_nome_fim" in _nomes(pl)


def test_george_placa_opaca_cobre_legenda_queimada_desde_o_inicio():
    _, pl = _montar("george")
    placa = next(c for c in pl.camadas if c.nome == "placa_legenda")
    assert placa.t0 == 0 and placa.entrada == 0 and placa.alpha.max() > 0.99
    assert 1400 < placa.y + placa.h / 2 < 1600
    cta = next(c for c in pl.camadas if c.nome == "cta_antecipado")
    assert cta.y + cta.h < placa.y


def test_pessoal_sem_marca_e_com_ornamento():
    p, pl = _montar("pessoal")
    nomes = _nomes(pl)
    assert "header" not in nomes and "logo_empilhado" not in nomes
    assert any(n.startswith("ornamento_") for n in nomes)
    assert not pl.barra_progresso and p["marca"] == "pessoal"


def test_tv_uma_versao_janela_e_paineis():
    p = _proj(template="tv", tv={"tratamento": "Laser de CO2", "indicacao": "Manchas senis"},
              clipes=[{"arquivo": "x.mov"}],
              mensagens=[{"titulo": f"Mensagem {k}"} for k in range(6)])
    p, pl = _montar("tv", p, 1920, 1080)
    assert len(p["versoes"]) == 1 and p["clipes"][0]["velocidade"] == 0.72
    assert TEMPLATES["tv"].tamanho_base(p, 1920, 1080) == (688, 860)
    assert pl.moldura is not None and not pl.barra_progresso
    assert {"moldura", "letreiro", "rodape", "painel_dir0", "logo_empilhado", "pill_final"} <= _nomes(pl)
    assert pl.duracao_total - pl.inicio_fechamento == pytest.approx(6.0)
    # mensagens não passam do fechamento
    assert all(c.t1 <= pl.inicio_fechamento + 0.01 for c in pl.camadas if c.nome.startswith("msg"))
    assert not any("agende" in t.lower() for t in pl.textos_tela)


def test_react_divide_a_tela_e_da_credito():
    p = _proj(template="react", clipes=[{"arquivo": "fala.mov"}], clipes_referencia=[{"arquivo": "ref.mov"}],
              credito="@perfil", legendas=True)
    p, pl = _montar("react", p)
    assert TEMPLATES["react"].tamanho_base(p, 1080, 1920) == (1080, 960)
    assert TEMPLATES["react"].extras(p, 1080, 1920)[0]["altura"] == 960
    assert "credito" in _nomes(pl) and p["legendas"]["posicao"] > 0.5
    import numpy as np
    q = pl.moldura(np.zeros((960, 1080, 3), np.uint8), [np.full((960, 1080, 3), 200, np.uint8)], 0)
    assert q.shape == (1920, 1080, 3) and q[100, 100, 0] == 200 and q[1500, 100, 0] == 0


def test_react_sem_referencia_para():
    with pytest.raises(SystemExit):
        TEMPLATES["react"].preparar(_proj(template="react"))


# revisor ampliado

def _regras(ach, nivel="erro"):
    return {a.regra for a in ach if a.nivel == nivel}


def test_george_e_enfermeiro():
    assert "dr_george" in _regras(compliance.revisar(_proj(), ["Com o Dr. George"]))
    assert not _regras(compliance.revisar(_proj(), ["Com o Enf. George"]))


def test_antes_e_depois_bloqueia_menos_no_uso_interno():
    assert "antes_depois" in _regras(compliance.revisar(_proj(), ["Antes e depois"]))
    ach = compliance.revisar(_proj(uso_interno=True, legenda=""), ["Antes e depois"])
    assert "antes_depois" not in _regras(ach) and "uso_interno" in _regras(ach, "aviso")


def test_pessoal_sem_divine_e_sem_rt():
    p = _proj(marca="pessoal", conteudo_medico=False, legenda="Bom dia.")
    assert not _regras(compliance.revisar(p, ["faz chuva ou faz sol"]))
    assert "marca_pessoal" in _regras(compliance.revisar(p, ["Hoje na Divine"]))


def test_musica_de_fora_precisa_de_licenca():
    p = _proj(audio={"musica": "trilha.mp3"})
    assert "musica" in _regras(compliance.revisar(p, []))
    assert "musica" not in _regras(compliance.revisar({**p, "musica_licenciada": True}, []))


def test_nota_viral_tem_os_seis_criterios():
    p, pl = _montar("divine")
    n = compliance.nota_viral(p, pl, [], True)
    assert set(n["notas"]) == {"hook", "retenção", "leitura", "áudio", "glamour", "compliance"}
    assert all(0 <= v <= 10 for v in n["notas"].values())
    assert n["notas"]["hook"] == 10


def test_nota_viral_aponta_gancho_longo_e_sem_cta():
    p = _proj(cta_antecipado=None, versoes=[{"nome": "V1", "hook": [
        {"titulo": "Uma frase de gancho comprida demais para caber em poucos segundos de leitura confortável"}]}])
    p, pl = _montar("divine", p)
    n = compliance.nota_viral(p, pl, [], True)
    assert n["notas"]["hook"] < 10 and n["notas"]["retenção"] < 10
    assert any("CTA" in d for d in n["dicas"])


# OCR (sem Tesseract: testa a montagem dos trechos)

def test_ocr_junta_leituras_parecidas():
    leit = [(0.0, ""), (0.4, "O laser de CO2"), (0.8, "O laser de C02"), (1.2, "O laser de CO2"), (1.6, ""),
            (2.0, "trabalha por dentro"), (2.4, "trabalha por dentro")]
    trs = ocr.trechos(leit)
    assert [t[2] for t in trs] == ["O laser de CO2", "trabalha por dentro"]
    assert trs[0][:2] == (0.4, 1.2)
    pal = ocr.palavras_dos_trechos(trs, 0.4)
    assert [w["texto"] for w in pal][:4] == ["O", "laser", "de", "CO2"]
    assert pal[-1]["fim"] <= 2.8
