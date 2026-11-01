"""Testes do assistente de IA (com o cliente da API simulado) e das referências."""
import json
from types import SimpleNamespace

import pytest
import yaml

from divine_studio import assistente, referencias


class Bloco(SimpleNamespace):
    def to_dict(self):
        return dict(self.__dict__)


class ClienteFalso:
    def __init__(self, texto):
        self.texto, self.pedidos = texto, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.pedidos.append(kw)
        return SimpleNamespace(stop_reason="end_turn",
                               content=[Bloco(type="thinking", thinking="", signature="x"), Bloco(type="text", text=self.texto)])


@pytest.fixture
def ia(monkeypatch):
    def usar(texto):
        cli = ClienteFalso(texto)
        monkeypatch.setattr(assistente, "_cliente", lambda: cli)
        monkeypatch.setattr(assistente, "disponivel", lambda: (True, ""))
        return cli
    return usar


SUG = {"hooks": [{"nome": "V1", "hook": [{"titulo": "Essa luz / é só a *mira.*"}]}],
       "mensagens": [{"titulo": "Estímulo / ao *colágeno*"}], "objetivo": "enviar", "roteiro": "1. entrada"}


def test_pedido_usa_modelo_skills_cache_e_fallback(ia):
    cli = ia("Oi, Renato.")
    texto, sug, hist = assistente.perguntar([], "ideias?", "contexto X")
    kw = cli.pedidos[0]
    assert kw["model"] == "claude-opus-5-5" and kw["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in kw["betas"]
    assert kw["system"][1]["cache_control"] == {"type": "ephemeral"}
    assert "divine-raio-x-referencia" in kw["system"][1]["text"] and "Conhecimento Divine" in kw["system"][1]["text"]
    assert "contexto X" in kw["messages"][0]["content"][-1]["text"]
    assert texto == "Oi, Renato." and sug is None
    assert hist[-1]["role"] == "assistant" and hist[-1]["content"][0]["type"] == "thinking"   # volta inteiro


def test_sugestao_e_separada_do_texto():
    t = "Gostei.\n```divine-sugestao\n" + json.dumps(SUG) + "\n```"
    texto, sug = assistente.separar_sugestao(t)
    assert texto == "Gostei." and sug["objetivo"] == "enviar"
    assert assistente.separar_sugestao("```divine-sugestao\n{quebrado\n```")[1] is None


def test_conversa_do_projeto_e_aplicar(tmp_path, ia):
    pasta = tmp_path / "proj"
    (pasta / "trabalho").mkdir(parents=True)
    (pasta / "projeto.yaml").write_text(yaml.safe_dump({"titulo": "CO2", "versoes": [{"nome": "V1", "hook_id": "A-H18"}]}))
    ia("Proposta:\n```divine-sugestao\n" + json.dumps(SUG) + "\n```")
    r = assistente.conversar(pasta, "melhore o hook")
    assert r["sugestao"]["hooks"][0]["nome"] == "V1"
    tela = assistente.mensagens_para_tela(assistente.carregar_conversa(pasta))
    assert tela[0]["papel"] == "user" and "<contexto_atual>" not in tela[0]["texto"]
    assert tela[1]["sugestao"] and "divine-sugestao" not in tela[1]["texto"]
    mudou = assistente.aplicar_sugestao(pasta, r["sugestao"])
    d = yaml.safe_load((pasta / "projeto.yaml").read_text())
    assert {"hooks", "mensagens", "objetivo", "roteiro.md"} <= set(mudou)
    assert "hook_id" not in d["versoes"][0] and d["versoes"][0]["hook"][0]["titulo"].startswith("Essa luz")
    assert (pasta / "roteiro.md").exists()


def test_revisor_barra_sugestao_com_promessa(tmp_path):
    pasta = tmp_path / "p"
    pasta.mkdir()
    (pasta / "projeto.yaml").write_text("titulo: x\n")
    with pytest.raises(SystemExit, match="revisor"):
        assistente.aplicar_sugestao(pasta, {"mensagens": [{"titulo": "Resultado garantido"}]})


def test_referencia_analisar_e_incorporar(tmp_path, monkeypatch, ia):
    monkeypatch.setattr(referencias, "PASTA", tmp_path / "referencias")
    monkeypatch.setattr(referencias, "IDEIAS", tmp_path / "IDEIAS.md")
    adicionados = []
    monkeypatch.setattr("divine_studio.hooks.adicionar", lambda t, *a, **k: adicionados.append(t) or "H999")
    p = referencias.nova("Reels do perfil X", "https://www.instagram.com/reel/abc", "texto atrás da cabeça")
    sug = {**SUG, "efeitos_app": [{"nome": "Texto 3D", "como": "título dourado em relevo"}]}
    ia("## Linha do tempo\n...\n```divine-sugestao\n" + json.dumps(sug) + "\n```")
    r = referencias.analisar(p.name)
    assert "Linha do tempo" in (p / "analise.md").read_text() and r["sugestao"]
    inc = referencias.incorporar(p.name)
    assert inc == {"hooks": ["H999"], "ideias": 1} and "Texto 3D" in (tmp_path / "IDEIAS.md").read_text()
    assert yaml.safe_load((p / "meta.yaml").read_text())["status"] == "incorporada"


def test_sem_chave_explica_como_ligar(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(assistente.Path, "home", lambda: assistente.Path("/nao/existe"))
    ok, motivo = assistente.disponivel()
    assert not ok and "ANTHROPIC_API_KEY" in motivo
