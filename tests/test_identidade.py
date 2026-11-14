"""Identidade visual e checklist do algoritmo (config/identidade.yaml, skills divine-algoritmo e afins)."""
import json

import yaml

from divine_studio import identidade, legenda_post


def _projeto(tmp_path, dados, fala=None):
    (tmp_path / "trabalho").mkdir(parents=True, exist_ok=True)
    (tmp_path / "projeto.yaml").write_text(yaml.safe_dump(dados, allow_unicode=True), encoding="utf-8")
    if fala is not None:
        (tmp_path / "trabalho" / "fala_base.json").write_text(json.dumps(fala), encoding="utf-8")
    return tmp_path


def _palavras(texto, t0=0.0, passo=0.4):
    return [{"texto": w, "inicio": t0 + k * passo, "fim": t0 + k * passo + 0.35} for k, w in enumerate(texto.split())]


def test_texto_sem_travessao_maiuscula_e_sem_isca():
    assert identidade.problemas_de_texto("Pele *renovada* / e mais firme") == []      # a quebra " / " continua a frase
    assert any("travessão" in x for x in identidade.problemas_de_texto("Pele boa — sempre"))
    assert any("minúscula" in x for x in identidade.problemas_de_texto("pele boa"))
    assert any("isca" in x for x in identidade.problemas_de_texto("Comenta EU QUERO que eu te mando"))
    assert identidade.problemas_de_texto("📍 Av. Paulista 1636 - Ao lado do MASP") == []   # endereço oficial


def test_checklist_reconhece_abertura_credencial_segue_e_pergunta(tmp_path):
    fala = (_palavras("Se você acorda cansada, já me segue. Como médico eu vejo isso sempre.")
            + _palavras("E você, já passou por isso?", 14))
    pasta = _projeto(tmp_path, {"titulo": "Cansaço", "template": "divine",
                                "versoes": [{"nome": "V1", "hook": [{"titulo": "O cansaço que *ninguém* explica"}]}],
                                "mensagens": [{"titulo": "Sono *conta*"}], "legendas": {"posicao": 0.66}}, fala)
    c = identidade.checklist(pasta, "V1")
    por_id = {i["id"]: i for i in c["itens"]}
    for chave in ("identificacao", "credencial", "ja_me_segue", "pergunta_fim", "legenda_peito", "palavra_dourada", "texto"):
        assert por_id[chave]["ok"] is True, (chave, por_id[chave])
    assert por_id["capa"]["ok"] is False                     # ainda sem capa: o item diz como fazer


def test_checklist_aponta_o_que_falta(tmp_path):
    pasta = _projeto(tmp_path, {"titulo": "Teste", "versoes": [{"nome": "V1", "hook": [{"titulo": "texto sem destaque"}]}],
                                "legendas": {"posicao": 0.3}}, _palavras("Hoje vou falar de um assunto importante para todos"))
    por_id = {i["id"]: i for i in identidade.checklist(pasta, "V1")["itens"]}
    assert por_id["legenda_peito"]["ok"] is False             # legenda no rosto
    assert por_id["palavra_dourada"]["ok"] is False
    assert por_id["texto"]["ok"] is False                     # começa com minúscula
    assert por_id["ja_me_segue"]["ok"] is False


def test_hook_auto_usa_o_sorteado_e_o_revisor_nao_quebra(tmp_path):
    from divine_studio.compliance import revisar
    from divine_studio.hooks import ler_banco
    hid = next(h["id"] for h in ler_banco() if h.get("batidas") and not h.get("uso_interno") and not h.get("reprovado"))
    pasta = _projeto(tmp_path, {"titulo": "Auto", "versoes": [{"nome": "V1", "hook": "auto"}]})
    (pasta / "trabalho" / "hooks_sorteados.json").write_text(json.dumps({"V1": hid}), encoding="utf-8")
    assert identidade._hook(yaml.safe_load((pasta / "projeto.yaml").read_text()), "V1", pasta)
    revisar({"titulo": "Auto", "versoes": [{"nome": "V1", "hook": "auto"}]})           # não pode dar erro


def test_legenda_do_post_tem_assinatura_do_perfil_e_pergunta():
    d = legenda_post.gerar({"titulo": "Cabelo", "template": "daniel", "conta": "drdanielmendess",
                            "versoes": [{"hook": [{"titulo": "Queda de cabelo tem *causa*"}]}],
                            "mensagens": [{"titulo": "Exame antes de tudo"}]})
    assert "RQE 105302" in d and "?" in d.split("#")[0]
    ok, detalhe = identidade._legenda_ok(d, {"marca": "divine"})
    assert ok, detalhe
    divine = legenda_post.gerar({"titulo": "Spa", "conta": "dvmedicalspa", "mensagens": [{"titulo": "Pausa boa"}]})
    assert "RT: Dr. Daniel Sampaio Mendes, CRM/SP 186.470" in divine


def test_um_post_de_feed_por_dia_contando_collab():
    pecas = [
        {"projeto": "a", "versao": "V1", "titulo": "Post do Daniel", "conta": "drdanielmendess", "formato": "reels",
         "status": "agendado", "data_agendada": "2026-11-20"},
        {"projeto": "b", "versao": "V1", "titulo": "Post da Divine", "conta": "dvmedicalspa", "formato": "reels"},
        {"projeto": "c", "versao": "V1", "titulo": "Outro dia", "conta": "dvmedicalspa", "formato": "reels",
         "status": "agendado", "data_agendada": "2026-11-21"},
    ]
    choque = identidade.conflito_feed("b", "V1", "2026-11-20", pecas)
    assert choque and "dvmedicalspa" in choque[0]            # a collab do Daniel ocupa o feed da Divine
    assert identidade.conflito_feed("b", "V1", "2026-11-22", pecas) == []
    stories = pecas + [{"projeto": "d", "versao": "stories", "conta": "dvmedicalspa", "formato": "post",
                        "status": "agendado", "data_agendada": "2026-11-22"}]
    assert identidade.conflito_feed("b", "V1", "2026-11-22", stories) == []   # Stories não contam no feed


def test_stories_respeita_zonas_mortas():
    import numpy as np
    from divine_studio import carrossel
    p = {"titulo": "T", "formato": "stories", "estilo": "escuro",
         "cards": [{"layout": "capa", "titulo": "Quem nunca *adiou* o cuidado?"}, {"layout": "texto", "titulo": "Dois"}]}
    im = np.asarray(carrossel.desenhar(p, 0).convert("L")).astype(int)
    fundo = np.median(im[5:40, 5:40])
    assert np.abs(im[:240, :] - fundo).max() < 40            # nada nos 250 px de cima
    assert np.abs(im[-330:, :] - fundo).max() < 40           # nada nos 340 px de baixo
