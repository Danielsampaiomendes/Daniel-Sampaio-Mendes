// Estúdio: a tela de edição profissional do projeto no computador (config/estudio.yaml).
// Mídia e efeitos à esquerda, fonte e agentes trabalhando, monitor (programa) no centro, scopes, atenção e previsão,
// inspetor à direita e a linha do tempo embaixo. Não duplica nada: move os blocos que já existem (linha do tempo,
// formulários, aprovar e postar) para dentro da grade e devolve tudo ao lugar quando você sai do Estúdio.
// No iPhone e em tela estreita continua o modo simples.

const es = { cfg: null, ligado: false, movidos: [], log: [], linhasJob: 0, ultimoJob: null, previsao: {}, audio: null,
  scopeT: 0, autoTimer: null, autoPendente: false, aba: "ajuste" };

function esPreferencia() {
  try { const v = localStorage.getItem("ds_estudio"); if (v !== null) return v === "1"; } catch (e) { /* segue */ }
  return !!(es.cfg && es.cfg.abrir_sozinho);
}
function esCabe() { return !NO_IPHONE && window.innerWidth >= ((es.cfg && es.cfg.largura_minima) || 1100); }
function esAutoPrevia() {
  try { const v = localStorage.getItem("ds_previa_auto"); if (v !== null) return v === "1"; } catch (e) { /* segue */ }
  return !!(es.cfg && es.cfg.previa_automatica.ligada_por_padrao);
}
const esHora = () => new Date().toTimeString().slice(0, 8);
const esAgente = (chave) => (es.cfg.agentes || []).find((a) => a.chave === chave) || { chave, nome: chave, cor: "#CCBD91" };
function esClassificar(linha) {
  const l = linha.toLowerCase();
  const a = (es.cfg.agentes || []).find((x) => (x.palavras || []).some((p) => l.includes(String(p).toLowerCase())));
  return a ? a.chave : "render";
}

// ---------------------------------------------------------------- montar e desmontar a grade

function esMontar() {
  if (es.ligado) return;
  es.ligado = true;
  document.body.classList.add("estudio");
  const grade = document.createElement("div");
  grade.id = "estudio"; grade.className = "es-grade";
  grade.innerHTML = `
    <div class="es-topo">
      <div class="es-agentes" id="es-agentes" title="Os agentes que montam a sua edição"></div>
      <span class="es-estado" id="es-estado"></span>
      <label class="es-auto" title="Mexeu na linha do tempo? Salva sozinho e gera a prévia da versão que está na tela"><input type="checkbox" id="es-auto"> ⚡ Prévia automática</label>
      <span class="es-salvar" id="es-salvar"></span>
      <button id="es-auto-edicao" class="dourado" title="Monta tudo pela fala e gera as 3 versões">✦ Edição automática</button>
      <button id="es-aprovar" title="Aprova a versão que está no monitor e exporta a final">✓ Aprovar esta</button>
      <button id="es-sair" class="es-sair" title="Volta para a tela simples, passo a passo">◧ Tela simples</button>
    </div>
    <section class="es-p es-midia">
      <header>Mídia</header>
      <div class="es-sub">Versões <small>toque para pôr no monitor</small></div><div id="es-versoes" class="es-versoes"></div>
      <div class="es-sub">Vídeos brutos</div><div id="es-brutos" class="es-brutos"></div>
      <div class="es-sub">Efeitos · SFX <small>entram na agulha</small></div><div id="es-rapidos" class="es-rapidos"></div>
    </section>
    <section class="es-p es-fonte">
      <header>Fonte <small id="es-fonte-nome"></small></header>
      <div class="es-fonte-v"><video id="es-fonte" playsinline muted controls preload="metadata"></video></div>
      <header>Atividade dos agentes <small id="es-log-n"></small></header>
      <ol id="es-log" class="es-log"></ol>
    </section>
    <section class="es-p es-programa">
      <header>Programa <b id="es-versao-nome"></b><span class="es-tc" id="es-tc">00:00:00:00</span></header>
      <div id="es-monitor" class="es-monitor"></div>
    </section>
    <section class="es-p es-analise">
      <header>Scopes <small>forma de onda · vetorscópio · nível</small></header>
      <div class="es-scopes"><canvas id="es-onda" width="220" height="110"></canvas><canvas id="es-vetor" width="110" height="110"></canvas>
        <div class="es-nivel" title="Nível do som (dBFS) enquanto toca"><i id="es-nivel-b"></i><small id="es-nivel-t">som</small></div></div>
      <header>Retenção prevista <small id="es-ret-v"></small></header>
      <canvas id="es-ret" width="300" height="90"></canvas>
      <p class="es-frase" id="es-frase"></p>
      <header>Pontos ! <small id="es-al-n"></small></header>
      <ul id="es-alertas" class="es-alertas"></ul>
    </section>
    <section class="es-p es-inspetor">
      <nav class="es-abas">
        <button data-es="ajuste">Ajuste</button><button data-es="cor">Cor e áudio</button>
        <button data-es="textos">Textos</button><button data-es="marca" title="Identidade visual e checklist do algoritmo">Marca <b id="es-marca-n"></b></button><button data-es="fluxo">Aprovar e postar</button>
      </nav>
      <div class="es-pane" data-pane="ajuste"><p class="dica es-dica" id="es-dica">Toque numa marca da linha do tempo, num ponto <b>!</b> ou num efeito rápido: o ajuste aparece aqui.</p></div>
      <div class="es-pane" data-pane="cor"></div>
      <div class="es-pane" data-pane="textos"></div>
      <div class="es-pane" data-pane="marca"><div id="es-marca"></div></div>
      <div class="es-pane" data-pane="fluxo"></div>
    </section>
    <section class="es-p es-linha"><div id="es-linha-topo" class="es-linha-topo"></div></section>`;
  const cab = $("#projeto .cabecalho");
  cab.after(grade);
  const mover = (no, destino, antes) => {
    if (!no) return;
    es.movidos.push({ no, pai: no.parentNode, prox: no.nextSibling });
    if (antes) destino.insertBefore(no, antes); else destino.appendChild(no);
  };
  const q = (s) => grade.querySelector(s);
  mover($(".barra-salvar"), q("#es-salvar"));
  mover($("#soltar"), q("#es-brutos")); mover($("#envio"), q("#es-brutos")); mover($("#brutos"), q("#es-brutos"));
  mover($(".cc-preview"), q("#es-monitor")); mover($(".cc-controles"), q("#es-monitor"));
  mover($("#tl-versao-box"), q("#es-linha-topo")); mover($("#tl-auto-info"), q("#es-linha-topo"));
  mover($(".cc-sfx"), q("#es-linha-topo"));
  mover($(".cc-trilhas"), q(".es-linha")); mover($(".cc-ferramentas"), q(".es-linha"));
  mover($("#tl-form"), q('[data-pane="ajuste"]'));
  mover($("#ed-filtro").closest(".cartao"), q('[data-pane="cor"]')); mover($("#ed-vol-orig").closest(".cartao"), q('[data-pane="cor"]'));
  mover($("#ed-versoes").closest(".cartao"), q('[data-pane="textos"]')); mover($("#ed-selo").closest(".cartao"), q('[data-pane="textos"]'));
  mover($("#p-passos"), q('[data-pane="fluxo"]')); mover($("#proximo-passo"), q('[data-pane="fluxo"]'));
  // cursores dos agentes em cima do vídeo (como no editor com agentes ao vivo)
  const tv = q(".tl-video");
  if (tv) { const c = document.createElement("div"); c.id = "es-cursores"; c.className = "es-cursores"; tv.appendChild(c); es.movidos.push({ no: c, pai: null }); }

  q("#es-sair").onclick = () => { try { localStorage.setItem("ds_estudio", "0"); } catch (e) { /* segue */ } esDesmontar(); aviso("Tela simples. Para voltar: ▣ Estúdio, no alto do projeto."); };
  q("#es-auto-edicao").onclick = () => rodar("auto");
  q("#es-aprovar").onclick = esAprovar;
  const auto = q("#es-auto");
  auto.checked = esAutoPrevia();
  auto.onchange = () => { try { localStorage.setItem("ds_previa_auto", auto.checked ? "1" : "0"); } catch (e) { /* segue */ }
    aviso(auto.checked ? "Prévia automática ligada: depois de cada ajuste o app salva e gera a prévia desta versão." : "Prévia automática desligada."); };
  $$("#estudio [data-es]").forEach((b) => b.onclick = () => esAba(b.dataset.es));
  esAba(es.aba);
  esRapidos();
  esLigarVideo();
  if (ed.proj) desenharTimeline();
  esAtualizar();
}

function esDesmontar() {
  if (!es.ligado) return;
  es.ligado = false;
  for (const m of es.movidos.reverse()) {
    if (!m.pai) { m.no.remove(); continue; }
    if (m.prox && m.prox.parentNode === m.pai) m.pai.insertBefore(m.no, m.prox); else m.pai.appendChild(m.no);
  }
  es.movidos = [];
  const g = $("#estudio"); if (g) g.remove();
  document.body.classList.remove("estudio");
  if (typeof ed !== "undefined" && ed.proj) desenharTimeline();
}

function esAba(nome) {
  es.aba = nome;
  $$("#estudio [data-es]").forEach((b) => b.classList.toggle("ativa", b.dataset.es === nome));
  $$("#estudio [data-pane]").forEach((p) => p.hidden = p.dataset.pane !== nome);
}

// liga ou desliga conforme o projeto aberto, a largura da tela e a sua escolha
function esDecidir() {
  if (!es.cfg) return;
  const projetoVideo = atual && dados && !$("#projeto").hidden;
  const btn = $("#b-estudio");
  if (btn) btn.hidden = !esCabe();
  if (projetoVideo && esCabe() && esPreferencia()) esMontar(); else esDesmontar();
}

// ---------------------------------------------------------------- conteúdo dos painéis

function esAtualizar() {
  if (!es.ligado || !dados) return;
  esAgentes(); esVersoes(); esFonte(); esAlertas(); esPrevisao(); esResumo(); esMarca();
  const v = (typeof ed !== "undefined" && ed.versao) || "";
  $("#es-versao-nome").textContent = v ? "· " + v : "";
}

function esAgentes() {
  const box = $("#es-agentes"); if (!box) return;
  const agora = Date.now();
  const vivos = es.log.filter((x) => x.vivo);
  const ativos = new Set(vivos.filter((x) => agora - x.ms < 12000).map((x) => x.agente));
  if (jobAtivo && vivos.length) ativos.add(vivos[vivos.length - 1].agente);     // quem escreveu por último segue aceso
  box.innerHTML = (es.cfg.agentes || []).map((a) => `<span class="es-ag ${ativos.has(a.chave) ? "vivo" : ""}" style="--c:${esc(a.cor)}" title="${esc(a.nome)}"><i></i>${esc(a.nome)}</span>`).join("");
  if (es.aviso && agora < es.aviso.ate) { $("#es-estado").innerHTML = es.aviso.html; return; }
  $("#es-estado").innerHTML = jobAtivo ? `<b class="es-ao-vivo">● ao vivo</b> ${ativos.size ? [...ativos].map((k) => esc(esAgente(k).nome)).join(", ") : "trabalhando"}`
    : `<span class="es-prontos">● ${(es.cfg.agentes || []).length} agentes prontos</span>`;
}

function esVersoes() {
  const box = $("#es-versoes"); if (!box) return;
  const prev = ultimasPrevias();
  const fins = dados.saidas.filter((s) => !s.previa);
  if (!prev.length && !fins.length) { box.innerHTML = '<p class="dica">Ainda sem versões. Solte o vídeo bruto e toque em ✦ Edição automática.</p>'; return; }
  const atualV = (typeof ed !== "undefined" && ed.versao) || "";
  box.innerHTML = prev.map((s) => {
    const p = es.previsao[s.versao] || {};
    const fim = p.de_100 ? `👥 ${p.de_100.fim} de 100 até o fim` : "";
    const temFinal = fins.some((f) => f.versao === s.versao);
    return `<button class="es-v ${s.versao === atualV ? "ativa" : ""}" data-v="${esc(s.versao)}">
      <img loading="lazy" src="/miniatura.jpg?p=${encodeURIComponent(atual)}&f=${encodeURIComponent(s.arquivo)}" alt="">
      <span><b>${esc(s.versao)}</b>${temFinal ? ' <em class="es-final">final ✓</em>' : ""}<small>${esc(fim)}</small></span></button>`;
  }).join("");
  $$("#es-versoes [data-v]").forEach((b) => b.onclick = () => {
    if (typeof ed === "undefined") return;
    if (ed.sujo && !confirm("Há ajustes não salvos nesta versão. Trocar mesmo assim?")) return;
    ed.versao = b.dataset.v; window.versaoAjustar = b.dataset.v;
    carregarEditor().catch((e) => console.error(e));
  });
}

function esFonte() {
  const v = $("#es-fonte"); if (!v) return;
  const b = (dados.brutos || []).find((x) => !x.fora) || (dados.brutos || [])[0];
  if (!b) { v.removeAttribute("src"); $("#es-fonte-nome").textContent = "sem vídeo bruto"; return; }
  const src = `/arquivo?p=${encodeURIComponent(atual)}&f=${encodeURIComponent("bruto/" + b.nome)}#t=0.5`;
  if (v.getAttribute("src") !== src) v.setAttribute("src", src);
  $("#es-fonte-nome").textContent = b.nome;
}

function esRapidos() {
  const box = $("#es-rapidos"); if (!box) return;
  box.innerHTML = (es.cfg.efeitos_rapidos || []).map((e) => `<button data-ef="${esc(e.tipo)}"><i class="es-dot ef"></i>${esc(e.rotulo)}</button>`).join("") +
    (es.cfg.sons_rapidos || []).map((n) => `<button data-som="${esc(n)}" title="Ouvir e pôr na agulha"><i class="es-dot som"></i>♪ ${esc(n.replace(/_/g, " ").replace(/ [abc]$/, ""))}</button>`).join("");
  $$("#es-rapidos [data-ef]").forEach((b) => b.onclick = () => {
    if (typeof ed === "undefined" || !ed.proj) return aviso("Abra a linha do tempo primeiro.", "erro");
    const c = TIPOS_NOME()[b.dataset.ef]; if (!c) return;
    const e = { tipo: c.tipo, inicio: agora() };
    for (const f of c.campos) if (OBRIGATORIOS.has(f.campo) && c.exemplo[f.campo] !== undefined) e[f.campo] = c.exemplo[f.campo];
    ed.efeitos.push(e); ed.sel = { tipo: "ef", i: ed.efeitos.length - 1 };
    $("#tl-video").pause(); sujar(); desenharTimeline(); desenharForm();
    esRegistrar("ritmo", `${c.nome} em ${e.inicio.toFixed(1)} s (você)`);
  });
  $$("#es-rapidos [data-som]").forEach((b) => b.onclick = () => {
    if (typeof ed === "undefined" || !ed.proj) return;
    try { const a = new Audio("/sfx.wav?nome=" + encodeURIComponent(b.dataset.som)); a.volume = 0.5; a.play().catch(() => {}); } catch (e) { /* sem som */ }
    ed.sons.push({ nome: b.dataset.som, inicio: agora() }); ed.sel = { tipo: "som", i: ed.sons.length - 1 };
    $("#tl-video").pause(); sujar(); desenharTimeline(); desenharForm();
    esRegistrar("ritmo", `som ${b.dataset.som} em ${agora().toFixed(1)} s (você)`);
  });
}

async function esPrevisao() {
  try { es.previsao = await api("/api/previsao?p=" + encodeURIComponent(atual)); } catch (e) { es.previsao = {}; }
  const v = (typeof ed !== "undefined" && ed.versao) || "V1";
  const p = es.previsao[v] || {};
  $("#es-ret-v").textContent = p.tem ? v : "";
  $("#es-frase").textContent = p.frase || "A retenção prevista aparece depois da primeira prévia.";
  esVersoes(); esDesenharRetencao();
}

function esDesenharRetencao() {
  const cv = $("#es-ret"); if (!cv) return;
  const g = cv.getContext("2d"), W = cv.width, H = cv.height;
  g.clearRect(0, 0, W, H);
  g.strokeStyle = "#ffffff14"; g.lineWidth = 1;
  for (let k = 1; k < 4; k++) { g.beginPath(); g.moveTo(0, (H * k) / 4); g.lineTo(W, (H * k) / 4); g.stroke(); }
  const v = (typeof ed !== "undefined" && ed.versao) || "V1";
  const p = es.previsao[v] || {};
  const curva = p.curva || [], passo = p.passo || 0.5;
  const dur = Math.max((typeof ed !== "undefined" && ed.total) || 0, curva.length * passo, 1);
  const zonas = ((typeof ed !== "undefined" && ed.alertas) || {}).zonas || [];
  g.fillStyle = "#E0866F2a";
  zonas.forEach((z) => g.fillRect((z.ini / dur) * W, 0, ((z.fim - z.ini) / dur) * W, H));
  if (curva.length) {
    const grad = g.createLinearGradient(0, 0, 0, H); grad.addColorStop(0, "#A9C49A55"); grad.addColorStop(1, "#A9C49A00");
    g.beginPath(); g.moveTo(0, H);
    curva.forEach((y, k) => g.lineTo(((k * passo) / dur) * W, H - (y / 100) * (H - 4)));
    g.lineTo(((curva.length - 1) * passo / dur) * W, H); g.closePath(); g.fillStyle = grad; g.fill();
    g.beginPath(); curva.forEach((y, k) => { const x = ((k * passo) / dur) * W, yy = H - (y / 100) * (H - 4); k ? g.lineTo(x, yy) : g.moveTo(x, yy); });
    g.strokeStyle = "#A9C49A"; g.lineWidth = 2; g.stroke();
  }
  const t = $("#tl-video") && $("#tl-video").src ? $("#tl-video").currentTime : 0;
  g.strokeStyle = "#F2D16B"; g.lineWidth = 2; g.beginPath(); g.moveTo((t / dur) * W, 0); g.lineTo((t / dur) * W, H); g.stroke();
}

function esAlertas() {
  const box = $("#es-alertas"); if (!box || typeof ed === "undefined") return;
  const al = ed.alertas || {}, ps = al.pontos || [];
  $("#es-al-n").textContent = ps.length ? `${ps.length} na ${al.versao || ed.versao || ""}` : "";
  box.innerHTML = ps.map((p, i) => `<li data-i="${i}"><span class="i n-${esc(p.nivel)}">!</span><b>${p.t0.toFixed(1)} s</b> ${esc(p.titulo)}</li>`).join("")
    || '<li class="dica">Nenhum ponto de risco nesta versão ✓</li>';
  $$("#es-alertas [data-i]").forEach((li) => li.onclick = () => {
    const p = ps[+li.dataset.i]; irPara(p.t0 + 0.05); mostrarAlerta(p); esAba("ajuste");
  });
}

// resumo do que os agentes fizeram nesta edição (quando não há tarefa rodando)
function esResumo() {
  if (jobAtivo || typeof ed === "undefined" || !ed.proj) return esDesenharLog();
  es.log = es.log.filter((x) => x.vivo || x.voce);
  const r = (ag, txt) => es.log.push({ hora: "resumo", agente: ag, texto: txt, ms: 0 });
  const prev = ultimasPrevias().length, fins = dados.saidas.filter((s) => !s.previa).length;
  if (ed.legLigadas) r("fala", ed.legendas.length ? `${ed.legendas.length} blocos de legenda tirados da fala` : "legenda da fala ligada: aparece na próxima prévia");
  r("roteiro", `${ed.versoes.length || 3} versões com hook próprio · ${ed.mensagens.length} mensagem(ns)`);
  const au = autos();
  r("ritmo", `${ed.efeitos.length} efeito(s) seus · ${au ? au.efeitos.length : 0} automático(s) · ${ed.sons.length + (au ? au.sons.length : 0)} som(ns)`);
  const ps = (ed.alertas || {}).pontos || [];
  const travam = ps.filter((p) => p.nivel === "bloqueia" || p.nivel === "confirmar").length;
  r("compliance", travam ? `${travam} ponto(s) de compliance travam o Aprovar` : "✓ sem trava de compliance nesta versão");
  const p = es.previsao[ed.versao] || {};
  r("previsao", p.de_100 ? `de 100 pessoas: ${p.de_100.passam_3s} passam dos 3 s, ${p.de_100.fim} chegam ao fim · ${ps.length} ponto(s) !` : `${ps.length} ponto(s) ! na linha do tempo`);
  r("render", `${prev} prévia(s) · ${fins} final(is)`);
  esDesenharLog();
}

function esRegistrar(agente, texto, vivo = false) {
  es.log.push({ hora: esHora(), agente, texto, ms: Date.now(), vivo, voce: !vivo });
  if (es.log.length > 300) es.log.splice(0, es.log.length - 300);
  esDesenharLog(); esAgentes();
}

function esDesenharLog() {
  const box = $("#es-log"); if (!box) return;
  box.innerHTML = es.log.slice(-120).map((x) => {
    const a = esAgente(x.agente);
    return `<li><span class="h">${esc(x.hora)}</span><span class="a" style="--c:${esc(a.cor)}">${esc(a.nome)}</span><span class="t">${esc(x.texto)}</span></li>`;
  }).join("");
  box.scrollTop = 1e9;
  $("#es-log-n").textContent = jobAtivo ? "ao vivo" : "";
}

// o registro da tarefa (o mesmo da janela de baixo) vira a atividade dos agentes, linha por linha
new MutationObserver(() => {
  if (!es.ligado) return;
  const linhas = ($("#t-log").textContent || "").split("\n").map((l) => l.trim()).filter(Boolean);
  if (es.ultimoJob !== jobAtivo) { es.ultimoJob = jobAtivo; es.linhasJob = 0; if (jobAtivo) es.log = es.log.filter((x) => x.voce); }
  if (linhas.length < es.linhasJob) es.linhasJob = 0;
  linhas.slice(es.linhasJob).forEach((l) => es.log.push({ hora: esHora(), agente: esClassificar(l), texto: l.slice(0, 160), ms: Date.now(), vivo: true }));
  es.linhasJob = linhas.length;
  esDesenharLog(); esAgentes();
}).observe($("#t-log"), { childList: true, characterData: true, subtree: true });

// ---------------------------------------------------------------- monitor: timecode, cursores dos agentes, scopes, nível

function esLigarVideo() {
  const v = $("#tl-video"); if (!v || v.dataset.estudio) return;
  v.dataset.estudio = "1";
  const passo = () => { if (es.ligado) { esTimecode(); esCursores(); esDesenharRetencao(); esScopes(); } };
  v.addEventListener("timeupdate", passo);
  v.addEventListener("seeked", passo);
  v.addEventListener("loadeddata", passo);
  v.addEventListener("play", () => { esNivelLigar(); requestAnimationFrame(esLaco); });
}

function esLaco(ts) {
  const v = $("#tl-video");
  if (!es.ligado || !v || v.paused) return;
  if (ts - es.scopeT > 110) { es.scopeT = ts; esScopes(); esNivel(); esTimecode(); }
  requestAnimationFrame(esLaco);
}

function esTimecode() {
  const v = $("#tl-video"), t = v && v.src ? v.currentTime : 0;
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = Math.floor(t % 60), f = Math.floor((t % 1) * 30);
  const el = $("#es-tc"); if (el) el.textContent = [h, m, s, f].map((x) => String(x).padStart(2, "0")).join(":");
}

function esCursores() {
  const box = $("#es-cursores"); if (!box || typeof ed === "undefined" || !ed.proj) return;
  const v = $("#tl-video"), t = v.src ? v.currentTime : 0;
  const itens = [];
  const nome = (tipo) => (TIPOS_NOME()[tipo] || {}).nome || tipo;
  ed.mensagens.forEach((m) => { const i = Number(m.inicio); if (!isNaN(i) && m.titulo && t >= i && t < i + 3) itens.push(["roteiro", "Texto · " + m.titulo.replace(/[*\/]/g, " ")]); });
  ed.efeitos.forEach((e) => { const i = Number(e.inicio) || 0; if (e.tipo && t >= i && t < i + duracaoEf(e)) itens.push(["ritmo", "Efeito · " + nome(e.tipo)]); });
  const au = autos();
  if (au) au.efeitos.forEach((e) => { const i = Number(e.inicio) || 0; if (t >= i && t < i + duracaoEf(e)) itens.push(["ritmo", "Ritmo · " + nome(e.tipo)]); });
  const leg = (ed.legendas || []).find((l) => t >= l.inicio && t < l.fim);
  if (leg) itens.push(["legenda", "Legenda · " + leg.texto]);
  ((ed.alertas || {}).pontos || []).forEach((p) => { if (t >= p.t0 && t < Math.max(p.t1, p.t0 + 1.5)) itens.push([p.nivel === "bloqueia" || p.nivel === "confirmar" ? "compliance" : "previsao", "! " + p.titulo]); });
  if (t < hookFim()) itens.unshift(["roteiro", "Hook · 3 primeiros segundos"]);
  box.innerHTML = itens.slice(0, 4).map(([ag, txt], k) => {
    const a = esAgente(ag);
    return `<span class="es-cur p${k}" style="--c:${esc(a.cor)}"><i>➤</i><b>${esc(a.nome)}</b><em>${esc(txt.slice(0, 46))}</em></span>`;
  }).join("");
}

const esTela = document.createElement("canvas"); esTela.width = 48; esTela.height = 86;
function esScopes() {
  const v = $("#tl-video"), onda = $("#es-onda"), vet = $("#es-vetor");
  if (!v || !onda || !vet || v.readyState < 2) return;
  let px;
  try { const g = esTela.getContext("2d", { willReadFrequently: true }); g.drawImage(v, 0, 0, esTela.width, esTela.height); px = g.getImageData(0, 0, esTela.width, esTela.height).data; }
  catch (e) { return; }
  const go = onda.getContext("2d"), W = onda.width, H = onda.height;
  go.fillStyle = "#07080a"; go.fillRect(0, 0, W, H);
  go.strokeStyle = "#ffffff12"; for (let k = 1; k < 4; k++) { go.beginPath(); go.moveTo(0, (H * k) / 4); go.lineTo(W, (H * k) / 4); go.stroke(); }
  const gv = vet.getContext("2d"), R = vet.width / 2;
  gv.fillStyle = "#07080a"; gv.fillRect(0, 0, vet.width, vet.height);
  gv.strokeStyle = "#ffffff22"; gv.beginPath(); gv.arc(R, R, R - 4, 0, Math.PI * 2); gv.stroke();
  gv.beginPath(); gv.moveTo(R, 4); gv.lineTo(R, 2 * R - 4); gv.moveTo(4, R); gv.lineTo(2 * R - 4, R); gv.stroke();
  // linha do tom de pele (referência do vetorscópio)
  gv.strokeStyle = "#E0A86F55"; gv.beginPath(); gv.moveTo(R, R); gv.lineTo(R - (R - 6) * 0.55, R - (R - 6) * 0.84); gv.stroke();
  go.fillStyle = "rgba(140,255,150,.22)"; gv.fillStyle = "rgba(255,230,170,.25)";
  for (let i = 0; i < px.length; i += 4) {
    const r = px[i], g = px[i + 1], b = px[i + 2], n = i / 4, x = n % esTela.width;
    const y = 0.2126 * r + 0.7152 * g + 0.0722 * b;
    go.fillRect((x / esTela.width) * W, H - (y / 255) * (H - 2) - 1, 2, 1.5);
    const cb = -0.1687 * r - 0.3313 * g + 0.5 * b, cr = 0.5 * r - 0.4187 * g - 0.0813 * b;
    gv.fillRect(R + (cb / 128) * (R - 6) * 1.6, R - (cr / 128) * (R - 6) * 1.6, 1.5, 1.5);
  }
}

function esNivelLigar() {
  if (es.audio || !es.ligado) { if (es.audio && es.audio.ctx.state === "suspended") es.audio.ctx.resume().catch(() => {}); return; }
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext; if (!Ctx) return;
    const ctx = new Ctx(), fonte = ctx.createMediaElementSource($("#tl-video")), an = ctx.createAnalyser();
    an.fftSize = 1024; fonte.connect(an); an.connect(ctx.destination);
    es.audio = { ctx, an, buf: new Float32Array(an.fftSize) };
    ctx.resume().catch(() => {});
  } catch (e) { es.audio = null; }
}
function esNivel() {
  const b = $("#es-nivel-b"); if (!b || !es.audio) return;
  es.audio.an.getFloatTimeDomainData(es.audio.buf);
  let s = 0; for (const x of es.audio.buf) s += x * x;
  const db = 20 * Math.log10(Math.sqrt(s / es.audio.buf.length) || 1e-6);
  const h = Math.max(0, Math.min(1, (db + 60) / 60));
  b.style.height = h * 100 + "%";
  b.style.background = db > -6 ? "#E0866F" : db > -14 ? "#F2D16B" : "#A9C49A";
  $("#es-nivel-t").textContent = db > -59 ? db.toFixed(0) + " dB" : "som";
}

// ---------------------------------------------------------------- identidade visual e checklist do algoritmo (config/identidade.yaml)

async function esMarca() {
  const box = $("#es-marca"); if (!box) return;
  const v = (typeof ed !== "undefined" && ed.versao) || "V1";
  let c;
  try { c = await api(`/api/identidade?p=${encodeURIComponent(atual)}&v=${encodeURIComponent(v)}`); } catch (e) { box.innerHTML = `<p class="dica">${esc(e.message)}</p>`; return; }
  $("#es-marca-n").textContent = c.total ? `${c.ok}/${c.total}` : "";
  const grupos = { algoritmo: "Algoritmo", identidade: "Identidade visual", legenda: "Legenda do post", compliance: "Compliance" };
  const icone = (ok) => ok === true ? '<i class="ok">✓</i>' : ok === false ? '<i class="nao">!</i>' : '<i class="nd">·</i>';
  const temCapa = c.itens.some((i) => i.id === "capa" && i.ok);
  box.innerHTML = `<p class="es-marca-resumo"><b>${c.ok} de ${c.total}</b> itens no padrão Divine na ${esc(v)}</p>` +
    Object.entries(grupos).map(([g, nome]) => {
      const its = c.itens.filter((i) => i.grupo === g); if (!its.length) return "";
      return `<div class="es-sub">${nome}</div><ul class="es-check">${its.map((i) =>
        `<li class="${i.ok === false ? "falha" : ""}">${icone(i.ok)}<span><b>${esc(i.titulo)}</b><small>${esc(i.detalhe)}</small></span></li>`).join("")}</ul>`;
    }).join("") +
    `<div class="linha es-capa"><button id="es-capa" class="dourado">📸 Capa neste quadro</button>
      ${temCapa ? `<a class="link" target="_blank" href="/arquivo?p=${encodeURIComponent(atual)}&f=${encodeURIComponent("saida/capa_" + v + ".jpg")}&t=${Date.now()}">ver capa</a>` : ""}</div>
     <p class="dica">Pare o vídeo num quadro em que a pessoa está bonita, de boca fechada e sorrindo: a capa sai com o título do hook e a logo no topo, fora das zonas mortas.</p>`;
  $("#es-capa").onclick = async () => {
    const t = $("#tl-video") && $("#tl-video").src ? $("#tl-video").currentTime : undefined;
    $("#es-capa").disabled = true; $("#es-capa").textContent = "Gerando a capa…";
    try { await api("/api/capa", { p: atual, versao: v, t }); aviso("Capa pronta ✓ (saida/capa_" + v + ".jpg)"); esRegistrar("roteiro", `capa da ${v} em ${(t || 0).toFixed(1)} s`); }
    catch (err) { aviso(err.message, "erro"); }
    esMarca();
  };
}

// ---------------------------------------------------------------- aprovar a versão do monitor e prévia automática

async function esAprovar() {
  const v = (typeof ed !== "undefined" && ed.versao) || "";
  const s = ultimasPrevias().find((x) => x.versao === v);
  if (!s) return aviso("Gere as versões primeiro (✦ Edição automática).", "erro");
  if (typeof ed !== "undefined" && ed.sujo && !confirm("Há ajustes não salvos. Aprovar a versão como está na última prévia?")) return;
  if (!confirm(`Aprovar a ${v} e exportar a versão final?`)) return;
  try {
    const r = await api("/api/aprovar", { p: atual, versao: v, arquivo: s.arquivo });
    esRegistrar("render", `você aprovou a ${v}: exportando a final`);
    if (r.job) acompanhar(r.job, `Exportando a final da ${v}`);
    esAba("fluxo");
  } catch (err) { aviso(err.message, "erro"); }
}

function esAgendarPrevia() {
  if (!es.ligado || !$("#es-auto") || !$("#es-auto").checked) return;
  clearTimeout(es.autoTimer);
  const espera = Math.max(1, Number(es.cfg.previa_automatica.espera_s) || 4) * 1000;
  es.aviso = { html: `<span class="es-prontos">⚡ prévia em ${Math.round(espera / 1000)} s se você parar de mexer…</span>`, ate: Date.now() + espera };
  esAgentes();
  es.autoTimer = setTimeout(async function tentar() {
    if (!es.ligado || !ed.sujo) return;
    if (jobAtivo) { es.autoTimer = setTimeout(tentar, 3000); return; }
    if (ed.efeitos.some((e) => !e.tipo)) { es.autoTimer = setTimeout(tentar, 3000); return; }   // ainda escolhendo o efeito
    await salvarEditor(null);
    if (ed.sujo) return;
    esRegistrar("render", `prévia automática da ${ed.versao || "V1"} (você mexeu na linha do tempo)`);
    rodar("previa", [ed.versao || "V1"]);
  }, espera);
}

// ---------------------------------------------------------------- ganchos nas funções do app (sem mudar o comportamento delas)

(function ganchos() {
  const _abrir = abrir;
  abrir = async function (nome) { const r = await _abrir(nome); esDecidir(); esAtualizar(); return r; };
  const _carregar = carregarEditor;
  carregarEditor = async function () { const r = await _carregar(); if (es.ligado) { esLigarVideo(); desenharTimeline(); esAtualizar(); } return r; };
  const _sujar = sujar;
  sujar = function (sim = true) { _sujar(sim); if (sim) esAgendarPrevia(); };
  const _form = desenharForm;
  desenharForm = function () { _form(); if (es.ligado && ed.sel) esAba("ajuste"); };
  const _mostrarTela = mostrarTela;
  mostrarTela = function (...a) { const r = _mostrarTela(...a); esDecidir(); return r; };
})();

// botão no alto do projeto: liga e desliga o Estúdio
(function botao() {
  const acoes = $("#projeto .cabecalho .acoes"); if (!acoes) return;
  const b = document.createElement("button");
  b.id = "b-estudio"; b.title = "Tela de edição profissional: mídia, monitor, agentes, scopes, inspetor e linha do tempo";
  b.textContent = "▣ Estúdio"; b.hidden = true;
  b.onclick = () => {
    const ligar = !es.ligado;
    try { localStorage.setItem("ds_estudio", ligar ? "1" : "0"); } catch (e) { /* segue */ }
    if (ligar) esMontar(); else esDesmontar();
  };
  acoes.prepend(b);
})();

let esRedim = null;
window.addEventListener("resize", () => { clearTimeout(esRedim); esRedim = setTimeout(esDecidir, 250); });
setInterval(() => {
  if (!es.ligado) return;
  esAgentes();
  if (!jobAtivo && es.estavaRodando) { es.estavaRodando = false; esAba(ultimasPrevias().length ? "fluxo" : es.aba); }
  if (jobAtivo) es.estavaRodando = true;
}, 1500);

api("/api/estudio").then((c) => { es.cfg = c; esDecidir(); if (es.ligado) esAtualizar(); }).catch(() => { /* sem Estúdio: segue a tela simples */ });
