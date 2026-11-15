"""Base segura (15/11/2026): gravação atômica e histórico do projeto.yaml, painel que sempre responde, botão Parar,
tema pela fala e regra nova sem apagar os comentários do config."""
import json
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest
import yaml

from divine_studio import auto, cli, config, guardar, painel


def _pal(frases):
    out = []
    for texto, ini in frases:
        t = ini
        for w in texto.split():
            out.append({"texto": w, "inicio": t, "fim": t + 0.3})
            t += 0.35
    return out


FALA_ENDO = _pal([("Você sabia que a gordura nos braços não sai só com treino?", 0.0),
                  ("O Endolaser age por dentro da pele com fibra fina.", 5.0),
                  ("São 2 sessões em média, com avaliação antes.", 10.0),
                  ("Agende sua avaliação pelo link.", 15.0)])


@pytest.fixture
def projeto(tmp_path, monkeypatch):
    proj = tmp_path / "projetos"
    p = proj / "2026-11-15_x"
    (p / "bruto").mkdir(parents=True)
    (p / "projeto.yaml").write_text("titulo: X\nselo: A\nversoes: [{nome: V1}]\n", encoding="utf-8")
    monkeypatch.setattr(painel, "PROJETOS", proj)
    return p


@pytest.fixture
def servidor(projeto):
    srv = painel.ThreadingHTTPServer(("127.0.0.1", 0), painel.Painel)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _pedir(url, corpo=None, headers=None):
    req = urllib.request.Request(url, data=None if corpo is None else json.dumps(corpo).encode(),
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


# ---------------------------------------------------------------- gravação segura e histórico

def test_gravacao_atomica_guarda_anterior_e_historico(projeto, monkeypatch):
    monkeypatch.setattr(guardar, "_intervalo_s", lambda: 600.0)
    guardar.gravar_projeto(projeto, "titulo: Y\n")
    assert (projeto / "projeto.yaml").read_text(encoding="utf-8") == "titulo: Y\n"
    assert "titulo: X" in (projeto / "trabalho" / "projeto.yaml.anterior").read_text(encoding="utf-8")
    assert len(guardar.historico(projeto)) == 1                      # o primeiro salvamento guarda o original
    guardar.gravar_projeto(projeto, "titulo: Z\n")
    assert len(guardar.historico(projeto)) == 1                      # dentro do intervalo: sem retrato novo
    assert "titulo: Y" in (projeto / "trabalho" / "projeto.yaml.anterior").read_text(encoding="utf-8")
    assert not [f for f in projeto.rglob("*.gravando")]              # nenhum temporário esquecido


def test_historico_passado_o_intervalo_e_restaurar(projeto, monkeypatch):
    monkeypatch.setattr(guardar, "_intervalo_s", lambda: 0.0)
    guardar.gravar_projeto(projeto, "titulo: Y\n")
    guardar.gravar_projeto(projeto, "titulo: Z\n")
    h = guardar.historico(projeto)
    assert len(h) == 2                                               # o original (X) e o Y
    textos = {(projeto / "trabalho" / "historico" / x["arquivo"]).read_text(encoding="utf-8") for x in h}
    assert any("titulo: X" in t for t in textos) and "titulo: Y\n" in textos
    alvo = next(x["arquivo"] for x in h if "titulo: X" in
                (projeto / "trabalho" / "historico" / x["arquivo"]).read_text(encoding="utf-8"))
    guardar.restaurar(projeto, alvo)
    assert "titulo: X" in (projeto / "projeto.yaml").read_text(encoding="utf-8")
    # o que estava antes de restaurar (Z) também ficou guardado: nada se perde
    assert any((projeto / "trabalho" / "historico" / x["arquivo"]).read_text(encoding="utf-8") == "titulo: Z\n"
               for x in guardar.historico(projeto))
    with pytest.raises(ValueError):
        guardar.restaurar(projeto, "../../projeto.yaml")


def test_restaurar_pela_linha_de_comando(projeto, monkeypatch, capsys):
    monkeypatch.setattr(guardar, "_intervalo_s", lambda: 0.0)
    guardar.gravar_projeto(projeto, "titulo: Y\n")
    cli.main(["restaurar", str(projeto), "--listar"])
    assert "projeto_" in capsys.readouterr().out
    cli.main(["restaurar", str(projeto)])
    assert "titulo: X" in (projeto / "projeto.yaml").read_text(encoding="utf-8")


def test_leitor_nunca_ve_o_projeto_pela_metade(projeto):
    """Enquanto um fio grava sem parar, quem lê sempre encontra um YAML inteiro (antes: arquivo vazio por um instante)."""
    grande = "titulo: X\nmensagens:\n" + "".join(f"  - {{titulo: 'frase {i}'}}\n" for i in range(400))
    parar = threading.Event()
    vistos = []

    def ler():
        while not parar.is_set():
            vistos.append(len(yaml.safe_load((projeto / "projeto.yaml").read_text(encoding="utf-8")) or {}))

    t = threading.Thread(target=ler)
    t.start()
    for i in range(150):
        guardar.gravar_projeto(projeto, grande + f"selo: S{i}\n")
    parar.set()
    t.join()
    assert vistos and min(vistos) >= 2                               # nunca {} (arquivo truncado)


def test_dois_salvamentos_juntos_nao_se_apagam(projeto, monkeypatch):
    """Mac e iPhone salvando campos diferentes ao mesmo tempo: os dois ficam (antes, o último apagava o outro)."""
    original = painel.salvar_yaml

    def lento(nome, texto):
        time.sleep(0.15)                                             # alarga a janela entre ler e gravar
        original(nome, texto)

    monkeypatch.setattr(painel, "salvar_yaml", lento)
    fios = [threading.Thread(target=painel.salvar_dados, args=("2026-11-15_x", novos))
            for novos in ({"selo": "NOVO"}, {"cta_antecipado": "Salva para lembrar depois."}, {"titulo": "Outro"})]
    for f in fios:
        f.start()
    for f in fios:
        f.join()
    d = yaml.safe_load((projeto / "projeto.yaml").read_text(encoding="utf-8"))
    assert d["selo"] == "NOVO" and d["cta_antecipado"].startswith("Salva") and d["titulo"] == "Outro"


def test_trava_pode_ser_pedida_de_novo_pelo_mesmo_fio(projeto):
    with guardar.trava(projeto):
        with guardar.trava(projeto):
            guardar.gravar_projeto(projeto, "titulo: Dentro\n")
    assert "Dentro" in (projeto / "projeto.yaml").read_text(encoding="utf-8")


# ---------------------------------------------------------------- painel sempre responde

def test_erro_inesperado_vira_resposta_clara_e_fica_registrado(servidor, projeto, monkeypatch):
    def quebra():
        raise RuntimeError("defeito de teste")
    monkeypatch.setattr(painel, "listar", quebra)
    codigo, corpo = _pedir(servidor + "/api/projetos")
    assert codigo == 500
    assert "tropeçou" in json.loads(corpo)["erro"]
    log = (projeto.parent / ".erros_painel.log").read_text(encoding="utf-8")
    assert "defeito de teste" in log and "GET /api/projetos" in log
    recentes = painel.erros_recentes()
    assert recentes and recentes[0]["onde"] == "GET /api/projetos" and "defeito de teste" in recentes[0]["erro"]
    codigo, corpo = _pedir(servidor + "/api/erros")
    assert codigo == 200 and json.loads(corpo)[0]["onde"] == "GET /api/projetos"


def test_projeto_yaml_quebrado_nao_derruba_a_conexao(servidor, projeto):
    (projeto / "projeto.yaml").write_text("titulo: [quebrado\n", encoding="utf-8")
    codigo, corpo = _pedir(servidor + "/api/dados?p=2026-11-15_x")
    assert codigo == 500 and "projeto.yaml" in json.loads(corpo)["erro"]
    codigo, corpo = _pedir(servidor + "/api/dados", {"p": "2026-11-15_x", "dados": {"selo": "B"}})
    assert codigo == 400 and "YAML" in json.loads(corpo)["erro"]     # o POST já respondia; continua igual


def test_trecho_depois_do_fim_do_arquivo_responde_416(servidor, projeto):
    (projeto / "bruto" / "a.txt").write_text("abc", encoding="utf-8")
    url = servidor + "/arquivo?p=2026-11-15_x&f=bruto/a.txt"
    assert _pedir(url, headers={"Range": "bytes=10-"})[0] == 416
    assert _pedir(url, headers={"Range": "bytes=abc-"})[0] == 416
    assert _pedir(url, headers={"Range": "bytes=1-"}) == (206, b"bc")


def test_diagnostico_mostra_config_quebrado_e_erros(projeto, tmp_path, monkeypatch):
    cfg = tmp_path / "config"
    shutil.copytree(config.CONFIG, cfg)
    (cfg / "viral.yaml").write_text("ritmo: [aberto\n", encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG", cfg)
    assert painel._config_com_erro() == ["viral.yaml (linha 2)"]
    config.load.cache_clear()
    try:
        with pytest.raises(config.ErroDeConfig) as e:
            config.load("viral")
        assert "config/viral.yaml" in str(e.value) and "linha" in str(e.value)
        assert isinstance(e.value, yaml.YAMLError) and isinstance(e.value, ValueError)
    finally:
        config.load.cache_clear()


# ---------------------------------------------------------------- tarefas: parar e não reiniciar no meio

def _tarefa_falsa(projeto, monkeypatch):
    """Uma tarefa que abre um filho (como o render abre o FFmpeg) e ficaria 60 s rodando."""
    monkeypatch.setattr(painel, "JOBS", {})
    log = projeto / "trabalho" / "painel_previa_teste.log"
    log.parent.mkdir(exist_ok=True)
    fh = open(log, "w", encoding="utf-8")
    # o filho ignora o pedido educado de sair, como o FFmpeg da base fez no teste real: precisa sair mesmo assim
    filho = ("import os, signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
             "print('comecei filho', os.getpid(), flush=True); time.sleep(60)")
    codigo = f"import subprocess, sys, time; subprocess.Popen([sys.executable, '-u', '-c', {filho!r}]); time.sleep(60)"
    proc = subprocess.Popen([sys.executable, "-u", "-c", codigo], stdout=fh, stderr=subprocess.STDOUT,
                            start_new_session=True)
    painel.JOBS["teste"] = {"id": "teste", "projeto": "2026-11-15_x", "acao": "previa", "estado": "rodando",
                            "log": str(log), "inicio": time.time(), "proc": proc, "fh": fh, "versoes": []}
    for _ in range(200):
        if "comecei filho" in log.read_text(encoding="utf-8"):
            break
        time.sleep(0.05)
    return proc


def test_parar_encerra_a_tarefa_e_os_filhos(servidor, projeto, monkeypatch):
    proc = _tarefa_falsa(projeto, monkeypatch)
    assert painel._job_do_projeto("2026-11-15_x") == "teste"
    codigo, corpo = _pedir(servidor + "/api/atualizar", {})
    assert codigo == 409 and "Parar" in json.loads(corpo)["erro"]    # não atualiza nem reinicia com tarefa no meio
    assert _pedir(servidor + "/api/reiniciar", {})[0] == 409
    codigo, corpo = _pedir(servidor + "/api/job/parar", {"id": "teste"})
    e = json.loads(corpo)
    assert codigo == 200 and e["estado"] == "parado" and "parada por você" in e["log"] and "comecei" in e["log"]
    assert proc.poll() is not None
    filho = int(e["log"].split("comecei filho ")[1].split()[0])
    for _ in range(40):                                              # o filho (o "FFmpeg") saiu junto
        vivo = subprocess.run(["ps", "-o", "stat=", "-p", str(filho)], capture_output=True, text=True).stdout.strip()
        if not vivo or vivo.startswith("Z"):
            break
        time.sleep(0.1)
    assert not vivo or vivo.startswith("Z")
    assert painel._job_do_projeto("2026-11-15_x") is None            # o projeto fica livre para a próxima tarefa
    assert json.loads(_pedir(servidor + "/api/job?id=teste")[1])["estado"] == "parado"
    assert json.loads(_pedir(servidor + "/api/job/parar", {"id": "teste"})[1])["estado"] == "parado"   # 2 toques
    assert not (projeto / "trabalho" / "aprovacao.json").exists()


def test_tarefa_que_termina_sozinha_continua_ok(projeto, monkeypatch):
    monkeypatch.setattr(painel, "JOBS", {})
    log = projeto / "trabalho" / "t.log"
    log.parent.mkdir(exist_ok=True)
    fh = open(log, "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-c", "print('fim')"], stdout=fh, stderr=subprocess.STDOUT)
    painel.JOBS["j"] = {"id": "j", "projeto": "2026-11-15_x", "acao": "final", "estado": "rodando", "log": str(log),
                        "inicio": time.time(), "proc": proc, "fh": fh, "versoes": ["V1"]}
    proc.wait()
    assert painel.estado("j")["estado"] == "ok" and painel.tarefas_rodando() == []
    assert json.loads((projeto / "trabalho" / "aprovacao.json").read_text(encoding="utf-8"))["versoes"] == ["V1"]


def test_tela_tem_o_botao_parar():
    web = painel.WEB
    assert 'id="t-parar"' in (web / "index.html").read_text(encoding="utf-8")
    js = (web / "app.js").read_text(encoding="utf-8")
    assert "/api/job/parar" in js and "parada por você" in js and "Sem conexão com o Divine Studio" in js


# ---------------------------------------------------------------- tema pela fala

def _txt(frases):
    return " ".join(frases)


def test_tema_da_fala_so_quando_domina():
    assert auto.tema_da_fala("O Endolaser age por dentro. Endolaser é feito com fibra fina.") == "endolaser"
    # "colágeno" aparece em qualquer vídeo: não transforma um vídeo de HIPRO em microagulhamento
    assert auto.tema_da_fala("O Hipro estimula o colágeno. O colágeno responde no tempo dele.") == "hipro"
    assert auto.tema_da_fala("Hoje eu vou falar de colágeno e de peso.") == "padrao"
    # dois tratamentos disputando a fala: melhor sem selo do que com o selo errado
    assert auto.tema_da_fala("Tem gente que faz Endolaser e tem gente que faz laser de CO2.") == "padrao"
    assert auto.tema_da_fala("Endolaser, Endolaser e Endolaser. Depois falo do laser de CO2.") == "endolaser"
    assert auto.tema_da_fala("") == "padrao"


def test_titulo_manda_e_tema_guardado_vale_depois():
    assert auto.tema_do_projeto({"titulo": "Laser de CO2 no corpo"}, FALA_ENDO) == "co2"
    assert auto.tema_do_projeto({"titulo": "IMG 4032"}, FALA_ENDO) == "endolaser"
    assert auto.tema_do_projeto({"titulo": "IMG 4032"}) == "padrao"
    assert auto.tema_do_projeto({"titulo": "IMG 4032", "tema": "endolaser"}) == "endolaser"
    assert auto.tema_do_projeto({"titulo": "IMG 4032", "tema": "inventado"}) == "padrao"
    assert "endolaser" in auto.texto_do_tema({"titulo": "IMG 4032", "tema": "endolaser"})
    assert auto.texto_do_tema({"titulo": "IMG 4032"}) == "IMG 4032"


def test_aplicar_tema_so_troca_o_que_era_generico():
    pad = config.load("roteiros")["padrao"]
    base = {"titulo": "IMG 4032", "selo": "", "mensagens": [dict(m) for m in pad["mensagens"]],
            "fechamento": {"frase": pad["fechamento"], "cta": pad["cta"]}}
    p = auto.aplicar_tema(base, "endolaser")
    assert p["tema"] == "endolaser" and p["selo"] == "ENDOLASER"
    assert p["fechamento"]["frase"] == "Contorno com *cuidado.*"
    assert p["mensagens"] != base["mensagens"] and base["selo"] == ""          # não mexe no dicionário de quem chamou
    escrito = {**base, "selo": "MEU SELO", "mensagens": [{"titulo": "Da *fala.*", "na_fala": "da fala"}],
               "fechamento": {"frase": "Escrito *à mão.*", "cta": "Agende"}}
    q = auto.aplicar_tema(escrito, "endolaser")
    assert q["selo"] == "MEU SELO" and q["mensagens"] == escrito["mensagens"]
    assert q["fechamento"]["frase"] == "Escrito *à mão.*"
    assert "tema" not in auto.aplicar_tema({**base, "tema": "co2"}, "padrao")


def test_edicao_automatica_de_video_sem_nome_fica_no_assunto_da_fala(tmp_path, monkeypatch):
    """Ponta a ponta: bruto chamado IMG_4032, fala sobre Endolaser. Antes: selo vazio e fechamento genérico."""
    p = tmp_path / "projetos" / "2026-11-15_img-4032"
    (p / "bruto").mkdir(parents=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=s=64x64:d=18", "-f", "lavfi",
                    "-i", "anoisesrc=d=18:a=0.3", "-shortest", str(p / "bruto" / "IMG_4032.mp4")], check=True)
    (p / "projeto.yaml").write_text("titulo: IMG 4032\n", encoding="utf-8")
    fala = tmp_path / "fala.json"
    fala.write_text(json.dumps(FALA_ENDO), encoding="utf-8")
    monkeypatch.setenv("DIVINE_TRANSCRICAO_TESTE", str(fala))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    (p / "trabalho" / "transcricoes").mkdir(parents=True)
    (p / "trabalho" / "transcricoes" / "marcador.json").write_text("{}", encoding="utf-8")   # liga o transcritor
    cli.main(["auto", str(p)])
    d = yaml.safe_load((p / "projeto.yaml").read_text(encoding="utf-8"))
    assert d["tema"] == "endolaser" and d["selo"] == "ENDOLASER"
    assert d["fechamento"]["frase"] == "Contorno com *cuidado.*"
    assert len(d["versoes"]) == 3 and d["mensagens"]
    assert "titulo: IMG 4032" in (p / "trabalho" / "projeto.yaml.anterior").read_text(encoding="utf-8")
    assert guardar.historico(p)


# ---------------------------------------------------------------- regra nova sem apagar os comentários

def test_regra_nova_nao_apaga_os_comentarios_do_config(tmp_path, monkeypatch):
    cfg = tmp_path / "config"
    shutil.copytree(config.CONFIG, cfg)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "CONHECIMENTO_DIVINE.md").write_text("# Conhecimento\n", encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG", cfg)
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    config.load.cache_clear()
    try:
        antes = (cfg / "preferencias.yaml").read_text(encoding="utf-8")
        dados_antes = yaml.safe_load(antes)
        cli.main(["regra", 'Legenda sempre na altura do peito: "nunca" no rosto'])
        cli.main(["regra", "Sem efeito de tremor em vídeo de consulta"])
        depois = (cfg / "preferencias.yaml").read_text(encoding="utf-8")
        assert depois.count("#") >= antes.count("#") > 20                     # antes: todos os comentários sumiam
        d = yaml.safe_load(depois)
        assert [r["regra"] for r in d["regras_aprendidas"]] == [
            'Legenda sempre na altura do peito: "nunca" no rosto', "Sem efeito de tremor em vídeo de consulta"]
        assert {k: v for k, v in d.items() if k != "regras_aprendidas"} == \
               {k: v for k, v in dados_antes.items() if k != "regras_aprendidas"}
        assert config.load("preferencias")["regras_aprendidas"][1]["regra"].startswith("Sem efeito")
        assert "Sem efeito de tremor" in (tmp_path / "docs" / "CONHECIMENTO_DIVINE.md").read_text(encoding="utf-8")
    finally:
        config.load.cache_clear()


def test_anexar_item_recusa_formato_inesperado(tmp_path, monkeypatch):
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "x.yaml").write_text("a: 1\nlista: {nao: lista}\n", encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG", cfg)
    assert config.anexar_item("x", "lista", {"k": 1}) is False
    assert config.anexar_item("x", "nao_existe", {"k": 1}) is False
    assert (cfg / "x.yaml").read_text(encoding="utf-8") == "a: 1\nlista: {nao: lista}\n"
    (cfg / "y.yaml").write_text("# topo\nlista:\n  - {k: 1}   # primeiro\n\n# fim\noutra: 2\n", encoding="utf-8")
    assert config.anexar_item("y", "lista", {"k": 2}) is True
    t = (cfg / "y.yaml").read_text(encoding="utf-8")
    assert yaml.safe_load(t) == {"lista": [{"k": 1}, {"k": 2}], "outra": 2} and "# primeiro" in t and "# fim" in t
    config.load.cache_clear()
