"""Campo "Ideia e pedidos": a ideia guia a edição, os pedidos por tempo mudam o projeto e viram padrão."""
import json

import yaml

from divine_studio import auto, estilos, pedidos, ritmo


def test_pedidos_por_tempo_e_gerais():
    proj = {"efeitos": [{"tipo": "contador", "inicio": 9.0}], "mensagens": [{"titulo": "Pele *boa*", "inicio": 12.0}],
            "legendas": True}
    texto = ('Aos 10 segundos tira o efeito. Em 0:12 troca o texto por "Pele firme"; coloca um zoom aos 8 segundos\n'
             "Aos 6 segundos troca o efeito por luz dourada\nLegenda mais para baixo\nmenos efeitos\nfaz um café")
    r = pedidos.aplicar(proj, texto, 20, [{"tipo": "foco_lente", "inicio": 5.8}])
    p = r["projeto"]
    assert r["nao_entendi"] == ["faz um café"] and len(r["aplicados"]) == 6
    assert {"tipo": "zoom_batida", "inicio": 8.0} in p["efeitos"] and {"tipo": "luz_dourada", "inicio": 5.8} in p["efeitos"]
    assert not any(e["tipo"] == "contador" for e in p["efeitos"])
    assert p["efeitos_evitar"] == [{"tipo": "foco_lente", "inicio": 5.8}]      # o automático trocado não volta
    assert p["mensagens"][0]["titulo"] == "Pele firme"
    assert p["legendas"]["posicao"] == 0.7 and p["ritmo"] == "calmo"
    assert proj["efeitos"] == [{"tipo": "contador", "inicio": 9.0}]            # o original não é alterado


def test_pedido_alcanca_o_mais_perto_do_tempo_dito():
    proj = {"efeitos": [{"tipo": "zoom_batida", "inicio": 8.0}]}
    r = pedidos.aplicar(proj, "aos 5,5 s tira o efeito", 20, [{"tipo": "foco_lente", "inicio": 5.8}])
    assert r["projeto"]["efeitos"] == [{"tipo": "zoom_batida", "inicio": 8.0}]
    assert r["projeto"]["efeitos_evitar"] == [{"tipo": "foco_lente", "inicio": 5.8}]


def test_o_que_ele_pede_vira_padrao_dos_proximos(tmp_path, monkeypatch):
    from divine_studio import aprendizado
    monkeypatch.setattr(aprendizado, "PROJETOS", tmp_path)
    pasta = tmp_path / "2026-11-18_x"
    (pasta / "trabalho").mkdir(parents=True)
    (pasta / "projeto.yaml").write_text(yaml.safe_dump({"titulo": "X", "legendas": True}), encoding="utf-8")
    (pasta / "trabalho" / "linha_V1.json").write_text(json.dumps({"efeitos": [{"tipo": "congelar", "inicio": 4.0}]}))
    r = pedidos.aplicar_no_projeto(pasta, "Legenda maior\naos 4 segundos tira o efeito")
    assert r["dados"]["legendas"]["tamanho"] == 64 and r["dados"]["efeitos_evitar"]
    assert any("padrão" in a for a in r["aprendi"])
    pedidos.aplicar_no_projeto(pasta, "aos 4 segundos tira o efeito")          # segunda vez: vira regra
    assert pedidos.efeitos_que_o_renato_tira() == {"congelar"}
    novo = {"titulo": "Outro", "legendas": True}
    assert pedidos.aplicar_padroes(novo) and novo["legendas"]["tamanho"] == 64
    sem = {"titulo": "Sem legenda", "legendas": False}
    pedidos.aplicar_padroes(sem)
    assert sem["legendas"] is False                                            # não religa o que o projeto desligou


def test_ideia_reconhece_o_tema_e_vira_texto_sem_fala():
    assert auto.tema_do_projeto({"titulo": "Vídeo 18/11", "ideia": "quero falar do laser de co2 e da recuperação"}) == "co2"
    plano = pedidos.plano_da_ideia({"ideia": "A pele avisa antes do espelho. Colágeno cai depois dos 25. Dá para cuidar a tempo."})
    assert plano["fonte"] == "ideia" and plano["ganchos"] and len(plano["mensagens"]) == 2
    assert pedidos.plano_da_ideia({"ideia": ""}) is None


def test_estilo_glass_e_um_zoom_por_video():
    assert estilos.nome_do({}) == "glass"
    assert len(estilos.fontes_do({})) == 3                                     # Vogue, Coroa e Revista, uma por versão
    efs = [{"tipo": "zoom_batida", "inicio": 3.0}, {"tipo": "luz_dourada", "inicio": 7.0}, {"tipo": "zoom_digital", "inicio": 12.0}]
    out = ritmo._um_zoom(efs, {"max_zoom_por_video": 1, "troca_do_zoom": "foco_lente"})
    assert [e["tipo"] for e in out] == ["zoom_batida", "luz_dourada", "foco_lente"]
    assert ritmo._um_zoom(efs, {"max_zoom_por_video": 0}) == efs


def test_pedido_do_canva_segue_o_liquid_glass(tmp_path):
    (tmp_path / "projeto.yaml").write_text(yaml.safe_dump({"titulo": "Colágeno", "ideia": "a pele avisa"}), encoding="utf-8")
    t = pedidos.pedido_canva(tmp_path, "uma gota de ouro", 8)
    assert "ouro líquido" in t and "a pele avisa" in t and "aos 8 segundos" in t and "Feito com IA" in t
