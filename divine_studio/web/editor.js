// Aba "Edição": linha do tempo (efeitos e mensagens no ponto exato), hook e fontes por versão, textos.
// Usa as funções do app.js (api, esc, rodar, atual) e salva só os campos editados (/api/dados).
const ed = { proj: null, efeitos: [], mensagens: [], versoes: [], sons: [], dubs: [], kit: null, sel: null, catalogo: null, fontes: null,
  hooks: [], total: 0, base: 0, fechS: 2.6, intervalo: 1.5, sujo: false, pegandoPonto: null };

const TIPOS_NOME = () => Object.fromEntries((ed.catalogo || []).map((c) => [c.tipo, c]));

function sujar(sim = true) {
  ed.sujo = sim;
  $(".barra-salvar").classList.toggle("sujo", sim);
  $("#ed-status").textContent = sim ? "Alterações não salvas." : "Tudo salvo.";
}

async function carregarEditor() {
  if (!atual) return;
  const [d, cat, fontes] = await Promise.all([
    api("/api/dados?p=" + encodeURIComponent(atual)),
    ed.catalogo ? ed.catalogo : api("/api/efeitos"),
    ed.fontes ? ed.fontes : api("/api/fontes"),
  ]);
  ed.catalogo = cat; ed.fontes = fontes;
  ed.proj = d.projeto; ed.fechS = d.fechamento_s; ed.intervalo = d.intervalo_efeitos;
  ed.efeitos = JSON.parse(JSON.stringify(d.projeto.efeitos || []));
  ed.mensagens = JSON.parse(JSON.stringify(d.projeto.mensagens || []));
  ed.versoes = JSON.parse(JSON.stringify(d.projeto.versoes || []));
  ed.sons = JSON.parse(JSON.stringify(d.projeto.sons || []));
  ed.dubs = JSON.parse(JSON.stringify((d.projeto.audio || {}).dublagem || []));
  ed.clipes = JSON.parse(JSON.stringify(d.projeto.clipes || []));
  ed.clipesInfo = d.clipes_info || []; ed.linhas = d.linhas || {}; ed.corteLimpo = d.corte_limpo;
  ed.atencao = d.atencao || {};
  // a versão da linha do tempo: a que você tocou no passo 3 (window.versaoAjustar) ou a última escolhida aqui
  ed.previasVersao = d.previas_versao || {};
  const vs = Object.keys(ed.previasVersao).sort((a, b) => (a === "IA") - (b === "IA") || a.localeCompare(b));
  const pedida = window.versaoAjustar || ed.versao;
  ed.versao = vs.includes(pedida) ? pedida : (vs[0] || "V1");
  window.versaoAjustar = null;
  ed.alertas = await carregarAlertas();
  ed.legendas = d.legendas_blocos || []; ed.legLigadas = d.legendas_ligadas; ed.correcoes = { ...(d.projeto.correcoes || {}) };
  ed.legEstilo = { ...(d.legenda_estilo || {}) }; ed.legEstiloMudou = false;
  ed.ref = ed.previasVersao[ed.versao] || d.referencia;
  const sel = $("#tl-versao"), selBox = $("#tl-versao-box");
  if (sel && selBox) {
    selBox.hidden = vs.length < 2;
    sel.innerHTML = vs.map((v) => `<option value="${esc(v)}" ${v === ed.versao ? "selected" : ""}>${esc(v)}</option>`).join("");
    sel.onchange = () => { ed.versao = sel.value; carregarEditor(); };
  }
  ed.cfg = { filtros: d.filtros || {}, transicoes: d.transicoes || {}, velocidades: d.velocidades || [1] };
  ed.cor = { ...(d.projeto.cor || {}) };
  ed.audio = { ...(d.projeto.audio || {}) }; ed.licenca = !!d.projeto.musica_licenciada;
  desenharCorAudio();
  $("#tl-sfx-auto").checked = d.projeto.sfx_automaticos !== false;
  if (!ed.kit) ed.kit = await api("/api/sons");
  ed.sel = null;
  const v = $("#tl-video");
  if (ed.ref) {
    v.src = `/arquivo?p=${encodeURIComponent(atual)}&f=${encodeURIComponent(ed.ref)}`;
    $("#tl-dica").innerHTML = "Arraste a linha do tempo para percorrer o vídeo: a agulha branca no meio é o ponto atual. Dois cliques numa faixa (no iPhone, segure o dedo) põem efeito, texto ou som ali; arraste as marcas para mudar o momento. " +
      "<span class='atalhos-tec'>Atalhos: espaço toca/pausa · ← → quadro a quadro · S divide · Delete remove · ⌘S salva · + − zoom</span>";
  } else {
    v.removeAttribute("src"); v.load();
    $("#tl-dica").innerHTML = "Gere as prévias uma vez (ou a <b>edição automática</b>) para ver o vídeo aqui. Dá para adicionar efeitos digitando o segundo.";
  }
  ed.base = d.duracao_base || 0;
  ed.total = ed.base ? ed.base + ed.fechS : 30;
  ed.pps = 0;                                   // zoom inicial: cerca de 10 s na largura da tela
  ed.tiraN = 0;
  $("#ed-selo").value = d.projeto.selo || "";
  const cta = d.projeto.cta_antecipado;
  $("#ed-cta").value = typeof cta === "string" ? cta : (cta && cta.texto) || "";
  $("#ed-fech-frase").value = (d.projeto.fechamento || {}).frase || "";
  $("#ed-fech-cta").value = (d.projeto.fechamento || {}).cta || "Agende sua avaliação";
  if (!ed.hooks.length || ed.hooksTema !== d.projeto.titulo) await buscarHooks(9);
  sujar(false);
  desenharMsgs(); desenharVersoes(); desenharTimeline(); desenharForm();
}

// ---------------------------------------------------------------- linha do tempo

const px = () => ed.pps || 60;
const FAIXA = { ef: "efeitos", "ef auto": "efeitos", msg: "texto", som: "audio", "som auto": "audio", voz: "audio" };
const faixa = (tipo) => $(`#tl-barra [data-faixa="${FAIXA[tipo] || "efeitos"}"]`);
const mmss = (t) => { t = Math.max(0, t || 0); return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(Math.floor(t % 60)).padStart(2, "0")}`; };

function duracaoEf(e) { return Number(e.duracao) || (TIPOS_NOME()[e.tipo] || {}).duracao || 3; }

function hookFim() {
  const v = ed.versoes[0] || {};
  const h = Array.isArray(v.hook) ? v.hook : [];
  if (!h.length) return 3;
  return h.reduce((s, b) => s + (Number(b.duracao) || Math.max(1.6, (b.titulo || "").split(/\s+/).length / 3.2 + 0.7)), 0);
}

// ---------------------------------------------------------------- automáticos (ritmo e sons) visíveis na linha
function autos() {
  if (ed.proj.ritmo_fixo && ed.proj.sfx_automaticos === false) return null;
  const chaves = Object.keys(ed.linhas || {}).sort((a, b) => (a !== ed.versao) - (b !== ed.versao) || (a !== "V1") - (b !== "V1") || (a === "IA") - (b === "IA") || a.localeCompare(b));
  if (!chaves.length) return null;
  const l = ed.linhas[chaves[0]];
  return { versao: chaves[0], efeitos: ed.proj.ritmo_fixo ? [] : (l.efeitos || []), sons: ed.proj.sfx_automaticos === false ? [] : (l.sons || []) };
}

// ---------------------------------------------------------------- clipes (aparar, dividir, velocidade, reverso, transição)
function duracaoClipe(c, i) {
  const info = ed.clipesInfo[i] || {};
  const fim = c.fim !== undefined && c.fim !== null && c.fim !== "" ? Number(c.fim) : (info.duracao_arquivo || 3);
  return Math.max(0.1, (fim - (Number(c.inicio) || 0)) / (Number(c.velocidade) || 1));
}
function posicoesClipes() {
  let t = 0;
  return ed.clipes.map((c, i) => { const a = t, d = duracaoClipe(c, i); t += d; return [a, d]; });
}
function desenharClipes() {
  const caixa = $("#tl-clipes");
  if (!caixa) return;
  if (ed.corteLimpo) { caixa.innerHTML = '<div class="dica">Corte limpo ligado: os clipes são cortados pela fala. Para aparar à mão, desligue o corte limpo na aba Projeto.</div>'; return; }
  const pos = posicoesClipes(), total = pos.length ? pos[pos.length - 1][0] + pos[pos.length - 1][1] : 1;
  const k = px();
  caixa.innerHTML = ed.clipes.map((c, i) => {
    const [a, d] = pos[i], nomeArq = String(c.arquivo || "").split("/").pop();
    const tags = [Number(c.velocidade || 1) !== 1 ? c.velocidade + "x" : "", c.reverso ? "⟲" : "", c.velocity ? "⚡velocity" : "", c.mudo ? "🔇" : "",
                  c.transicao && c.transicao !== "dissolver" ? "⇢ " + (ed.cfg.transicoes[c.transicao] || c.transicao) : ""].filter(Boolean).join(" ");
    return `<div class="tl-clipe ${ed.sel && ed.sel.tipo === "clip" && ed.sel.i === i ? "sel" : ""} ${(ed.clipesInfo[i] || {}).existe === false ? "falta" : ""}"
      data-i="${i}" style="left:${a * k}px;width:${Math.max(24, d * k - 2)}px" title="${esc(nomeArq)} · ${d.toFixed(1)}s">${esc(nomeArq)}<small>${esc(tags)}</small></div>`;
  }).join("") || '<div class="dica">Sem clipes: solte os vídeos na aba Projeto.</div>';
  caixa.querySelectorAll(".tl-clipe").forEach((el) => el.onclick = () => {
    ed.sel = { tipo: "clip", i: +el.dataset.i }; desenharTimeline(); desenharForm();
    const v = $("#tl-video"); if (v.src) v.currentTime = posicoesClipes()[+el.dataset.i][0] + 0.05;
  });
}

$("#tl-dividir").onclick = () => {
  if (ed.corteLimpo) return alert("Com o corte limpo ligado, os clipes são cortados pela fala. Desligue na aba Projeto para dividir à mão.");
  const t = agora(), pos = posicoesClipes();
  const i = pos.findIndex(([a, d]) => t > a + 0.15 && t < a + d - 0.15);
  if (i < 0) return alert("Pare o vídeo no meio de um clipe para dividir.");
  const c = ed.clipes[i], vel = Number(c.velocidade) || 1;
  const corte = Math.round(((Number(c.inicio) || 0) + (t - pos[i][0]) * vel) * 100) / 100;
  const a = { ...c, fim: corte }, b = { ...c, inicio: corte, transicao: "corte" };
  ed.clipes.splice(i, 1, a, b);
  ed.clipesInfo.splice(i + 1, 0, ed.clipesInfo[i]);
  ed.sel = { tipo: "clip", i: i + 1 }; sujar(); desenharTimeline(); desenharForm();
};

function ajustarEscala() {
  const w = $("#cc-rolagem").clientWidth || 600;
  if (!ed.pps) ed.pps = Math.max(24, Math.min(160, w / Math.min(ed.total || 10, 10)));
  $("#cc-pad").style.paddingLeft = $("#cc-pad").style.paddingRight = (w / 2) + "px";
  $("#tl-barra").style.width = Math.max(1, ed.total * px()) + "px";
  // tira de miniaturas: um quadro a cada ~32 px (proporção do vídeo vertical na altura da faixa)
  const n = Math.max(8, Math.min(160, Math.round(ed.total * px() / 32 / 8) * 8));
  if (ed.ref && n !== ed.tiraN) {
    ed.tiraN = n;
    $("#tl-clipes").style.backgroundImage = `url("/api/tira?p=${encodeURIComponent(atual)}&f=${encodeURIComponent(ed.ref)}&n=${n}")`;
  }
  if (!ed.ref) $("#tl-clipes").style.backgroundImage = "";
}
function desenharRegua() {
  const r = $("#cc-regua"), k = px();
  const passo = k >= 90 ? 1 : k >= 45 ? 2 : k >= 20 ? 5 : 10;
  let h = "";
  for (let t = 0; t <= ed.total + 0.01; t += passo / 2) {
    const grande = Math.abs(t / passo - Math.round(t / passo)) < 0.01;
    h += `<span class="${grande ? "g" : "p"}" style="left:${t * k}px">${grande ? mmss(t) : "·"}</span>`;
  }
  r.innerHTML = h;
}
function desenharLegendas() {
  const f = $('#tl-barra [data-faixa="legendas"]');
  if (!f) return;
  f.querySelectorAll(".cc-leg, .cc-vazio").forEach((x) => x.remove());
  const k = px();
  if (!ed.legendas.length) {
    const v = document.createElement("div");
    v.className = "cc-vazio";
    v.innerHTML = ed.legLigadas ? "As legendas aparecem aqui depois da próxima prévia (com a fala transcrita)."
      : '<button class="link" id="cc-ligar-leg">＋ Ligar legendas automáticas da fala</button>';
    f.appendChild(v);
    const b = v.querySelector("#cc-ligar-leg");
    if (b) b.onclick = (e) => { e.stopPropagation(); ligarLegendas(); };
    return;
  }
  ed.legendas.forEach((l, i) => {
    const el = document.createElement("div");
    el.className = "cc-leg" + (ed.sel && ed.sel.tipo === "leg" && ed.sel.i === i ? " sel" : "");
    el.style.left = l.inicio * k + "px";
    el.style.width = Math.max(14, (l.fim - l.inicio) * k - 2) + "px";
    el.textContent = l.texto;
    el.title = `${l.texto} · ${l.inicio.toFixed(1)}s`;
    el.onpointerdown = (ev) => { ev.stopPropagation(); ed.sel = { tipo: "leg", i }; irPara(l.inicio + 0.05); desenharLegendas(); desenharForm(); };
    f.appendChild(el);
  });
}
async function ligarLegendas() {
  try {
    await api("/api/dados", { p: atual, dados: { legendas: true, corte_limpo: true } });
    ed.legLigadas = true; desenharLegendas();
    aviso("Legendas ligadas. Gere as prévias para ver a fala na faixa Legendas.");
  } catch (err) { aviso(err.message, "erro"); }
}
function irPara(t) {
  t = Math.max(0, Math.min(t, ed.total));
  const v = $("#tl-video"); if (v.src) v.currentTime = t;
  ed.rolandoCodigo = true;
  $("#cc-rolagem").scrollLeft = t * px();
  mostrarTempo(t);
}
function mostrarTempo(t) { $("#cc-tempo").textContent = `${mmss(t)} / ${mmss(ed.total)}`; }

function desenharTimeline() {
  ajustarEscala(); desenharRegua();
  desenharClipes(); desenharLegendas();
  const barra = $("#tl-barra");
  barra.querySelectorAll(".tl-marca, .tl-zona").forEach((x) => x.remove());
  const k = px();
  const zona = (cls, a, b) => { const z = document.createElement("div"); z.className = "tl-zona " + cls;
    z.style.left = a * k + "px"; z.style.width = Math.max(0, b - a) * k + "px"; barra.appendChild(z); };
  zona("hook", 0, Math.min(hookFim(), ed.total));
  // risco de queda da versão escolhida (as zonas vêm junto com os "!" dela)
  (((ed.alertas || {}).zonas) || (ed.atencao || {}).zonas || []).forEach((z) => zona("risco", z.ini, z.fim));
  desenharAlertas(barra, k);
  if (ed.base) zona("fech", ed.base, ed.total);
  const ordem = ed.efeitos.map((e, i) => [Number(e.inicio) || 0, i]).sort((a, b) => a[0] - b[0]);
  const perto = new Set();
  ordem.forEach(([t, i], j) => { if (j && t - ordem[j - 1][0] < ed.intervalo) { perto.add(i); perto.add(ordem[j - 1][1]); } });
  ed.efeitos.forEach((e, i) => marca("ef", i, Number(e.inicio) || 0, duracaoEf(e), (TIPOS_NOME()[e.tipo] || {}).nome || e.tipo, perto.has(i)));
  // mensagem com momento fixo em cima de um efeito de texto: vermelho (as duas disputariam o mesmo lugar)
  const QUADRO_SO = new Set(["zoom_digital", "fundo_pip", "cortina", "filme"]);
  const efs = ed.efeitos.filter((e) => e.tipo && !QUADRO_SO.has(e.tipo)).map((e) => [Number(e.inicio) || 0, (Number(e.inicio) || 0) + duracaoEf(e)]);
  ed.sons.forEach((s, i) => marca("som", i, Number(s.inicio) || 0, 0.6, "♪", false));
  ed.dubs.forEach((d, i) => marca("voz", i, Number(d.inicio) || 0, Number(d.dur) || 3, "🎙 voz", false));
  const au = autos();
  $("#tl-auto-info").hidden = !au || !(au.efeitos.length + au.sons.length);
  if (au) {
    au.efeitos.forEach((e, i) => marca("ef auto", i, Number(e.inicio) || 0, duracaoEf(e), "✦ " + ((TIPOS_NOME()[e.tipo] || {}).nome || e.tipo), false));
    au.sons.forEach((x, i) => marca("som auto", i, Number(x.inicio) || 0, 0.6, "♪", false));
    $("#tl-auto-info").innerHTML = `${au.efeitos.length} efeito(s) e ${au.sons.length} som(ns) automáticos da ${esc(au.versao)} estão tracejados na linha.
      <button class="link" id="tl-fixar">Trazer para a linha do tempo e editar</button>`;
    $("#tl-fixar").onclick = fixarAutos;
  }
  // hook da V1 na faixa Texto (como os textos no CapCut); tocar leva até ele e abre as versões
  const v1 = ed.versoes[0] || {}, beats = Array.isArray(v1.hook) ? v1.hook : [];
  let th = 0;
  beats.forEach((bt) => {
    const d = Number(bt.duracao) || Math.max(1.6, (bt.titulo || "").split(/\s+/).length / 3.2 + 0.7);
    const el = document.createElement("div");
    el.className = "tl-marca msg hookb";
    el.style.left = th * px() + "px"; el.style.width = Math.max(18, d * px() - 2) + "px";
    el.textContent = "Hook: " + (bt.titulo || "").replace(/[*\/]/g, "");
    el.title = "Hook da V1 (edite em Versões: hook e fontes)";
    const ini = th;
    el.onpointerdown = (ev) => { ev.stopPropagation(); irPara(ini + 0.05); };
    faixa("msg").appendChild(el);
    th += d;
  });
  if (!beats.length && (v1.hook_id || v1.hook === "auto")) {
    const el = document.createElement("div");
    el.className = "tl-marca msg hookb"; el.style.left = "0px"; el.style.width = Math.max(18, hookFim() * px() - 2) + "px";
    el.textContent = v1.hook_id ? `Hook ${v1.hook_id}` : "Hook sorteado do banco";
    faixa("msg").appendChild(el);
  }
  ed.mensagens.forEach((m, i) => { if (m.inicio !== undefined && m.inicio !== null && m.inicio !== "") {
    const a = Number(m.inicio), d = Math.max(1.6, (m.titulo || "").split(/\s+/).length / 3.2 + 0.7);
    const bate = efs.some(([x, y]) => a < y && a + d > x);
    marca("msg", i, a, d, (m.titulo || "").replace(/[*\/]/g, ""), bate);
  } });
}

function marca(tipo, i, t, dur, rotulo, perto) {
  const k = px();
  const el = document.createElement("div");
  el.className = `tl-marca ${tipo}` + (ed.sel && ed.sel.tipo === tipo && ed.sel.i === i ? " sel" : "") + (perto ? " perto" : "");
  el.style.left = t * k + "px";
  el.style.width = Math.max(18, dur * k) + "px";
  el.textContent = rotulo;
  el.title = `${rotulo} · ${t.toFixed(1)}s` + (perto ? (tipo === "ef" ? ` · muito perto de outro efeito (mín. ${ed.intervalo}s)`
    : " · em cima de um efeito: mude o momento") : "");
  el.onpointerdown = (ev) => {
    ev.stopPropagation(); ev.preventDefault();
    if (tipo.endsWith(" auto")) { ed.sel = { tipo, i }; desenharForm(); return; }
    ed.sel = { tipo, i }; desenharTimeline(); desenharForm();
    const lista = { ef: ed.efeitos, msg: ed.mensagens, som: ed.sons, voz: ed.dubs }[tipo];
    const x0 = ev.clientX, t0 = Number(lista[i].inicio) || 0;
    let mexeu = false;
    const mover = (e2) => {
      const nt = Math.max(0, Math.min((ed.base || ed.total) - 0.5, t0 + (e2.clientX - x0) / px()));
      if (Math.abs(e2.clientX - x0) > 3) mexeu = true;
      lista[i].inicio = Math.round(nt * 10) / 10;
      const m = $("#tl-barra .tl-marca.sel"); if (m) m.style.left = lista[i].inicio * px() + "px";
    };
    const soltar = () => { window.removeEventListener("pointermove", mover); window.removeEventListener("pointerup", soltar);
      if (mexeu) { sujar(); desenharTimeline(); desenharForm(); } $("#tl-video").currentTime = lista[i].inicio; };
    window.addEventListener("pointermove", mover); window.addEventListener("pointerup", soltar);
  };
  (faixa(tipo) || $("#tl-barra")).appendChild(el);
}

function itemNoPonto(t, faixaNome) {
  if (faixaNome === "texto") { irPara(t); return $("#tl-add-msg").click(); }
  if (faixaNome === "audio") { irPara(t); return $("#tl-add-som").click(); }
  if (faixaNome === "legendas") { irPara(t); return; }
  efeitoNoPonto(t);
}
function efeitoNoPonto(t) {
  t = Math.round(Math.max(0, Math.min(t, (ed.base || ed.total) - 0.3)) * 10) / 10;
  ed.efeitos.push({ tipo: null, inicio: t });
  ed.sel = { tipo: "ef", i: ed.efeitos.length - 1 };
  const v = $("#tl-video"); v.pause(); if (v.src) v.currentTime = t;
  desenharTimeline(); desenharForm();
  const f = $("#tl-form"); if (f) f.scrollIntoView({ behavior: "smooth", block: "nearest" });
}
let toqueLongo = null, arrasto = null;
$("#tl-barra").onpointerdown = (e) => {
  const r = $("#tl-barra").getBoundingClientRect();
  const t = (e.clientX - r.left) / px();
  const nomeFaixa = (e.target.closest("[data-faixa]") || {}).dataset ? e.target.closest("[data-faixa]").dataset.faixa : "efeitos";
  clearTimeout(toqueLongo);
  if (e.pointerType !== "mouse") { toqueLongo = setTimeout(() => itemNoPonto(t, nomeFaixa), 550); return; }   // iPhone: segure o dedo
  // mouse: arrastar a linha do tempo percorre o vídeo; clique simples leva a agulha até ali
  arrasto = { x: e.clientX, sl: $("#cc-rolagem").scrollLeft, mexeu: false, t };
  const mover = (ev) => {
    if (!arrasto) return;
    if (Math.abs(ev.clientX - arrasto.x) > 4) arrasto.mexeu = true;
    if (arrasto.mexeu) $("#cc-rolagem").scrollLeft = arrasto.sl - (ev.clientX - arrasto.x);
  };
  const soltar = () => {
    window.removeEventListener("pointermove", mover); window.removeEventListener("pointerup", soltar);
    if (arrasto && !arrasto.mexeu) irPara(arrasto.t);
    arrasto = null;
  };
  window.addEventListener("pointermove", mover); window.addEventListener("pointerup", soltar);
};
["pointerup", "pointerleave", "pointercancel"].forEach((n) => $("#tl-barra").addEventListener(n, () => clearTimeout(toqueLongo)));
$("#tl-barra").addEventListener("pointermove", (e) => { if (Math.abs(e.movementX) > 4) clearTimeout(toqueLongo); });
$("#tl-barra").ondblclick = (e) => {
  if (e.target.closest(".tl-marca, .cc-leg, .tl-clipe, button")) return;
  const r = $("#tl-barra").getBoundingClientRect();
  const fx = e.target.closest("[data-faixa]");
  itemNoPonto((e.clientX - r.left) / px(), fx ? fx.dataset.faixa : "efeitos");
};

// rolagem = tempo: arrastar percorre o vídeo; tocando, a linha anda sozinha sob a agulha
$("#cc-rolagem").addEventListener("scroll", () => {
  const t = $("#cc-rolagem").scrollLeft / px();
  mostrarTempo(t);
  if (ed.rolandoCodigo) { ed.rolandoCodigo = false; return; }
  const v = $("#tl-video");
  if (v.src && v.paused) { cancelAnimationFrame(ed.rafBusca); ed.rafBusca = requestAnimationFrame(() => { v.currentTime = Math.min(t, ed.total); }); }
});
function seguirVideo() {
  const v = $("#tl-video");
  if (!v.paused) { ed.rolandoCodigo = true; $("#cc-rolagem").scrollLeft = v.currentTime * px(); mostrarTempo(v.currentTime); requestAnimationFrame(seguirVideo); }
}
const tocar = () => { const v = $("#tl-video"); if (!v.src) return aviso("Gere uma prévia para ver o vídeo aqui."); v.paused ? v.play() : v.pause(); };
$("#cc-play").onclick = tocar;
$("#cc-play-grande").onclick = tocar;
$("#tl-video").addEventListener("play", () => { $("#cc-play").textContent = "❚❚"; $("#cc-play-grande").hidden = true; seguirVideo(); });
$("#tl-video").addEventListener("pause", () => { $("#cc-play").textContent = "▶"; $("#cc-play-grande").hidden = false; });
$("#tl-video").addEventListener("click", () => { if (!ed.pegandoPonto) tocar(); });
function zoom(fator) {
  const t = $("#cc-rolagem").scrollLeft / px();
  ed.pps = Math.max(6, Math.min(400, px() * fator));
  desenharTimeline(); ed.rolandoCodigo = true; $("#cc-rolagem").scrollLeft = t * px();
}
$("#cc-mais").onclick = () => zoom(1.5);
$("#cc-menos").onclick = () => zoom(1 / 1.5);
$("#cc-ajustar").onclick = () => { ed.pps = Math.max(6, ($("#cc-rolagem").clientWidth - 40) / Math.max(1, ed.total)); desenharTimeline(); irPara(0); };
$("#cc-rolagem").addEventListener("wheel", (e) => {
  if (e.ctrlKey || e.metaKey) { e.preventDefault(); zoom(e.deltaY < 0 ? 1.15 : 1 / 1.15); }      // pinça do trackpad = zoom
  else if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) { e.preventDefault(); $("#cc-rolagem").scrollLeft += e.deltaY; }
}, { passive: false });
$("#cc-filtros").onclick = () => { const c = $("#ed-filtro"); if (c) { c.closest(".cartao").scrollIntoView({ behavior: "smooth" }); c.focus(); } };
$("#cc-legendas").onclick = () => {
  if (!ed.legendas.length && !ed.legLigadas) return ligarLegendas();
  const t = $("#cc-rolagem").scrollLeft / px();
  const i = ed.legendas.findIndex((l) => l.fim >= t);
  if (i < 0) { ed.sel = { tipo: "legestilo" }; return desenharForm(); }
  ed.sel = { tipo: "leg", i }; irPara(ed.legendas[i].inicio + 0.05); desenharLegendas(); desenharForm();
};
$("#cc-estilo-leg").onclick = async () => {
  if (!ed.legLigadas) await ligarLegendas();
  ed.sel = { tipo: "legestilo" }; desenharForm();
  $("#tl-form").scrollIntoView({ behavior: "smooth", block: "nearest" });
};
$("#tl-video").ontimeupdate = () => { if ($("#tl-video").paused) mostrarTempo($("#tl-video").currentTime); };
$("#tl-video").onloadedmetadata = () => {
  const d = $("#tl-video").duration;
  if (d && isFinite(d)) { ed.total = d; if (!ed.base) ed.base = Math.max(1, d - ed.fechS); desenharTimeline(); }
};
window.addEventListener("resize", () => { if (ed.proj) desenharTimeline(); });

// clique no vídeo: escolhe o ponto (círculo, zoom)
$("#tl-video").addEventListener("click", (e) => {
  if (!ed.pegandoPonto) return;
  e.preventDefault();
  const r = e.target.getBoundingClientRect();
  const x = Math.round(((e.clientX - r.left) / r.width) * 100) / 100, y = Math.round(((e.clientY - r.top) / r.height) * 100) / 100;
  ed.efeitos[ed.pegandoPonto.i][ed.pegandoPonto.campo] = [x, y];
  ed.pegandoPonto = null; sujar(); mostrarMira(x, y); desenharForm();
});
function mostrarMira(x, y) {
  const m = $("#tl-mira"); m.hidden = false; m.style.left = x * 100 + "%"; m.style.top = y * 100 + "%";
}

function agora() {
  const v = $("#tl-video");
  const t = v.src ? v.currentTime : $("#cc-rolagem").scrollLeft / px();
  return Math.round(t * 10) / 10;
}

$("#tl-add-efeito").onclick = () => {
  ed.efeitos.push({ tipo: null, inicio: agora() });
  ed.sel = { tipo: "ef", i: ed.efeitos.length - 1 };
  $("#tl-video").pause(); desenharForm();
};
$("#tl-add-msg").onclick = () => {
  ed.mensagens.push({ titulo: "", inicio: agora() });
  ed.sel = { tipo: "msg", i: ed.mensagens.length - 1 };
  $("#tl-video").pause(); sujar(); desenharMsgs(); desenharTimeline(); desenharForm();
  setTimeout(() => { const f = $("#tl-form input"); if (f) f.focus(); }, 50);
};

$("#tl-add-som").onclick = () => {
  ed.sons.push({ nome: (ed.kit[0] || {}).nome, inicio: agora() });
  ed.sel = { tipo: "som", i: ed.sons.length - 1 };
  $("#tl-video").pause(); sujar(); desenharTimeline(); desenharForm();
};
$("#tl-sfx-auto").onchange = () => sujar();

// ---------------------------------------------------------------- gravar voz (dublagem / narração)

let gravador = null;
$("#tl-gravar").onclick = () => {
  if (gravador) return gravador.stop();
  mostrarCopy({});
};

// copy sugerida (editável) antes de gravar: lê no teleprompter enquanto o vídeo toca sem som
// ---------------------------------------------------------------- pontos "!" (config/alertas.yaml)
// sempre da versão que está na linha do tempo (ed.versao): cada versão tem hook, efeitos e curva de atenção próprios
function carregarAlertas() {
  return api(`/api/alertas?p=${encodeURIComponent(atual)}&v=${encodeURIComponent(ed.versao || "V1")}`).catch(() => ({ pontos: [] }));
}

function desenharAlertas(barra, k) {
  barra.querySelectorAll(".tl-alerta").forEach((x) => x.remove());
  ((ed.alertas || {}).pontos || []).forEach((p) => {
    const b = document.createElement("button");
    b.className = `tl-alerta n-${p.nivel}`;
    b.style.left = p.t0 * k + "px";
    b.textContent = "!";
    b.title = `${p.titulo} · ${p.t0.toFixed(1)}s`;
    b.setAttribute("aria-label", p.titulo);
    b.onpointerdown = (ev) => { ev.stopPropagation(); ev.preventDefault(); irPara(p.t0 + 0.05); mostrarAlerta(p); };
    barra.appendChild(b);
  });
}

function mostrarAlerta(p) {
  const nivel = ((ed.alertas.niveis || {})[p.nivel] || {}).nome || p.nivel;
  const box = $("#tl-form");
  box.innerHTML = `<h2 class="alerta-tit n-${esc(p.nivel)}"><span class="tl-alerta-i">!</span> ${esc(p.titulo)}</h2>
    <p class="dica">${esc(nivel)} · ${esc(ed.alertas.versao || ed.versao || "")} · ${p.t0.toFixed(1)} a ${p.t1.toFixed(1)} s${p.fonte !== "app" ? " · " + esc(p.fonte) : ""}</p>
    <p>${esc(p.texto)}</p>
    <div class="linha">${p.acoes.map((a, i) => `<button class="${i ? "" : "dourado"}" data-ac="${i}">${esc(a.rotulo)}</button>`).join("")}
      ${p.nivel === "bloqueia" || p.nivel === "confirmar" ? "" : '<button class="link" data-ign>Ignorar este ponto</button>'}</div>`;
  box.querySelectorAll("[data-ac]").forEach((b) => b.onclick = () => executarAlerta(p, p.acoes[+b.dataset.ac]));
  const ign = box.querySelector("[data-ign]");
  if (ign) ign.onclick = () => acaoServidor(p, "ignorar");
}

async function acaoServidor(p, acao) {
  try {
    const r = await api("/api/alertas/acao", { p: atual, versao: ed.alertas.versao || ed.versao || "V1", id: p.id, acao });
    aviso(r.msg);
    carregarEditor();
  } catch (err) { aviso(err.message, "erro"); }
}

function executarAlerta(p, a) {
  // sem "fim" (pedido final): a gravação SOMA à sua voz, nunca cala o vídeo inteiro
  if (a.tipo === "dublar") return mostrarCopy({ copy: a.copy, inicio: a.inicio ?? p.t0, fim: a.fim ?? null, somar: a.fim == null });
  if (a.tipo === "regravar") return mostrarRegravar(p, a);
  if (a.tipo === "corrigir") { irPara((a.inicio ?? p.t0) + 0.05); const i = ed.legendas.findIndex((l) => l.fim >= (a.inicio ?? p.t0));
    if (i >= 0) { ed.sel = { tipo: "leg", i }; desenharLegendas(); desenharForm(); } return; }
  if (a.tipo === "abrir") return irPara((a.inicio ?? p.t0) + 0.05);
  if (a.tipo === "instalar_fala") return rodar("instalar_fala");
  // "Conferi" é uma assinatura: a pergunta é a da regra, e Cancelar (o padrão do iPhone) é o lado seguro
  if (a.tipo === "conferir_fala" && !confirm(`Leia com atenção:\n\n"${a.frase}"\n\nPor que o app perguntou: ${a.motivo || "pode ser promessa"}\n\n` +
    "Esta frase PROMETE um resultado do tratamento (que algo some, melhora, emagrece, rejuvenesce ou muda, ou em quanto tempo)?\n\n" +
    "OK = NÃO promete: explica, fala do pós (inchaço, retorno, exame) ou desmente um mito.\nCancelar = promete ou não tenho certeza: vou tirar ou dublar.")) return;
  return acaoServidor(p, a.tipo);           // efeito, cortar_frase, conferir_fala
}

// regravar = gravar o VÍDEO de novo (abertura mais curta, fala mais devagar): dublar não muda o tempo da imagem
function mostrarRegravar(p, a) {
  const box = $("#tl-form");
  box.innerHTML = `<h2>🎬 Regravar este trecho</h2>
    <p class="dica">Grave de novo com a câmera (de ${p.t0.toFixed(1)} a ${p.t1.toFixed(1)} s) e solte o vídeo novo na aba
      <b>Vídeo</b>, junto dos outros brutos: o corte limpo junta e tira a versão antiga se você tocar em ✂ abaixo.</p>
    <textarea id="rg-texto" rows="3">${esc(a.copy || "")}</textarea>
    <div class="linha"><button class="dourado" id="rg-copiar">📋 Copiar o texto</button></div>`;
  $("#rg-copiar").onclick = () => copiar($("#rg-texto").value).then(() => aviso("Texto copiado"), () => aviso("Selecione e copie o texto", "erro"));
}

async function mostrarCopy(opt = {}) {
  const box = $("#tl-form");
  box.innerHTML = '<p class="dica">Carregando a copy…</p>';
  let c;
  try { c = await api("/api/copy?p=" + encodeURIComponent(atual)); } catch (err) { box.innerHTML = `<p class="dica">${esc(err.message)}</p>`; return; }
  const iaOk = (await estadoIA().catch(() => ({}))).ok;
  const semMic = !navigator.mediaDevices || !window.MediaRecorder;
  box.innerHTML = `<h2>🎙 Copy para gravar</h2>
    <p class="dica">Veio de: ${esc(c.fonte)} · cerca de <b id="cp-seg">${c.segundos}</b> s falando. Edite à vontade: é o que vai aparecer no teleprompter.</p>
    <textarea id="cp-texto" class="copy-voz">${esc(c.copy)}</textarea>
    <p class="aviso-ia" id="cp-longa" hidden></p>
    <label>Velocidade do teleprompter <input id="cp-vel" type="range" min="1.8" max="3.6" step="0.1" value="${localStorage.getItem("tp_vel") || 2.6}"></label>
    ${c.alertas.length ? `<p class="aviso-ia">${c.alertas.map(esc).join("<br>")}</p>` : ""}
    <div class="linha">
      ${iaOk ? '<button id="cp-ia">✦ Melhorar com IA</button>' : ""}
      <button id="cp-sug" class="link">voltar à sugerida</button>
      <button id="cp-salvar" class="link">salvar copy</button></div>
    <label>Entra em (s)<input id="cp-inicio" type="number" step="0.1" value="${agora()}"></label>
    <label class="check"><input type="checkbox" id="cp-subst" checked> substituir o som do vídeo (dublagem). Sem marcar: soma (narração)</label>
    ${semMic ? `<p class="dica">No iPhone pela rede o navegador não libera o microfone: leia a copy, grave no app <b>Gravador</b> e envie aqui.</p>
      <input type="file" id="dub-arq" accept="audio/*">` : '<button class="dourado" id="cp-gravar">● Gravar lendo o teleprompter</button>'}`;
  const campo = $("#cp-texto");
  ed.dubFim = opt.fim ?? null;                 // dublar só um trecho: o som original fica mudo só até aqui
  if (opt.copy) campo.value = opt.copy;
  if (opt.inicio !== undefined && $("#cp-inicio")) $("#cp-inicio").value = Number(opt.inicio).toFixed(1);
  if (opt.somar && $("#cp-subst")) $("#cp-subst").checked = false;
  if (ed.dubFim !== null) box.insertAdjacentHTML("afterbegin", `<p class="aviso-ia">Dublando só de ${Number(opt.inicio).toFixed(1)} a ${Number(ed.dubFim).toFixed(1)} s
    (<b>${(Number(ed.dubFim) - Number(opt.inicio)).toFixed(1)} s</b>, no mesmo ritmo da fala original): o resto do vídeo mantém a sua voz.
    O app tira o silêncio do começo e do fim da gravação e ajusta até 15% de velocidade para caber.</p>`);
  campo.oninput = () => {
    const seg = campo.value.split(/\s+/).filter(Boolean).length / Number($("#cp-vel").value || 2.6);
    $("#cp-seg").textContent = seg.toFixed(1);
    const dur = $("#tl-video").duration, ini = Number($("#cp-inicio") ? $("#cp-inicio").value : 0) || 0;
    const longa = dur && seg > dur - ini;
    $("#cp-longa").hidden = !longa;
    if (longa) $("#cp-longa").textContent = `A copy leva ${seg.toFixed(0)} s e o vídeo tem ${(dur - ini).toFixed(0)} s a partir daqui: corte algumas frases.`;
  };
  $("#cp-vel").oninput = () => { try { localStorage.setItem("tp_vel", $("#cp-vel").value); } catch (e) { /* sem storage */ } campo.oninput(); };
  campo.oninput();
  const salvar = () => api("/api/copy", { p: atual, copy: campo.value });
  $("#cp-salvar").onclick = async () => { await salvar(); $("#ed-status").textContent = "Copy salva no projeto."; };
  $("#cp-sug").onclick = () => { campo.value = c.sugerida; campo.oninput(); };
  if ($("#cp-ia")) $("#cp-ia").onclick = async () => {
    const b = $("#cp-ia"); b.disabled = true; b.textContent = "Reescrevendo…";
    try { campo.value = (await api("/api/copy/ia", { p: atual, copy: campo.value })).copy; campo.oninput(); }
    catch (err) { alert(err.message); }
    b.disabled = false; b.textContent = "✦ Melhorar com IA";
  };
  if ($("#dub-arq")) $("#dub-arq").onchange = async () => {
    const f = $("#dub-arq").files[0]; if (!f) return;
    await salvar();
    const ext = (f.name.split(".").pop() || "m4a").toLowerCase();
    const r = await fetch(`/api/dublagem?p=${encodeURIComponent(atual)}&inicio=${$("#cp-inicio").value || 0}&ext=${ext}&substituir=${$("#cp-subst").checked ? 1 : 0}${ed.dubFim !== null ? "&fim=" + ed.dubFim : ""}`, { method: "POST", body: f });
    const j0 = await r.json();
    if (!r.ok) return alert(j0.erro);
    if (j0.aviso) aviso(j0.aviso, "erro");
    carregarEditor();
  };
  if ($("#cp-gravar")) $("#cp-gravar").onclick = async () => {
    await salvar();
    gravar(Number($("#cp-inicio").value) || 0, $("#cp-subst").checked, campo.value);
  };
}

async function gravar(inicio, substituir, texto) {
  const v = $("#tl-video");
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: false } }); }
  catch (e) { alert("O navegador não liberou o microfone: " + e.message); return; }
  const tipo = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find((t) => MediaRecorder.isTypeSupported(t)) || "";
  const pedacos = [];
  // teleprompter: texto grande rolando no ritmo da fala (~2,6 palavras por segundo), 3 s de contagem antes
  const tp = document.createElement("div");
  tp.className = "teleprompter";
  tp.innerHTML = `<div class="tp-texto">${esc(texto).replace(/\n/g, "<br>")}</div><div class="tp-conta">3</div><button class="tp-parar">■ Parar</button>`;
  document.body.appendChild(tp);
  tp.querySelector(".tp-parar").onclick = () => gravador ? gravador.stop() : tp.remove();
  for (const n of [3, 2, 1]) { tp.querySelector(".tp-conta").textContent = n; await new Promise((r) => setTimeout(r, 800)); }
  tp.querySelector(".tp-conta").remove();
  gravador = new MediaRecorder(stream, tipo ? { mimeType: tipo } : {});
  gravador.ondataavailable = (e) => e.data.size && pedacos.push(e.data);
  gravador.onstop = async () => {
    stream.getTracks().forEach((t) => t.stop());
    v.pause(); v.muted = false; tp.remove();
    $("#tl-gravar").textContent = "🎙 Gravar voz aqui"; $("#tl-gravar").classList.remove("gravando");
    gravador = null;
    const blob = new Blob(pedacos, { type: tipo || "audio/webm" });
    const ext = (tipo || "audio/webm").includes("mp4") ? "m4a" : "webm";
    $("#ed-status").textContent = "Enviando a gravação…";
    const r = await fetch(`/api/dublagem?p=${encodeURIComponent(atual)}&inicio=${inicio}&ext=${ext}&substituir=${substituir ? 1 : 0}${ed.dubFim !== null && ed.dubFim !== undefined ? "&fim=" + ed.dubFim : ""}`, { method: "POST", body: blob });
    ed.dubFim = null;
    const j = await r.json();
    if (!r.ok) return alert(j.erro);
    $("#ed-status").textContent = j.aviso || "Voz gravada. Gere as prévias para ouvir no vídeo.";
    if (j.aviso) aviso(j.aviso, "erro");
    carregarEditor();
  };
  v.muted = true; v.currentTime = inicio;
  gravador.start(250);
  v.play();
  $("#tl-gravar").textContent = "■ Parar gravação"; $("#tl-gravar").classList.add("gravando");
  v.onended = () => gravador && gravador.stop();
  const caixa = tp.querySelector(".tp-texto");
  let vel = 2.6;
  try { vel = Number(localStorage.getItem("tp_vel")) || 2.6; } catch (e) { /* padrão */ }
  const dur = Math.max(4, texto.split(/\s+/).filter(Boolean).length / vel) * 1000, t0 = performance.now();
  const rolar = (agoraMs) => {
    if (!gravador) return;
    caixa.scrollTop = (caixa.scrollHeight - caixa.clientHeight) * Math.min(1, (agoraMs - t0) / dur);
    requestAnimationFrame(rolar);
  };
  requestAnimationFrame(rolar);
}

function mostrarEnvioDeAudio() {
  const box = $("#tl-form");
  box.innerHTML = `<h2>Enviar a sua voz</h2><p class="dica">No iPhone pela rede o navegador não libera o microfone para a página.
    Grave no app <b>Gravador</b> (ou Notas de voz) assistindo ao vídeo e envie aqui. Ela entra no segundo marcado.</p>
    <label>Entra em (s)<input id="dub-inicio" type="number" step="0.1" value="${agora()}"></label>
    <label class="check"><input type="checkbox" id="dub-subst" checked> substituir o som do vídeo</label>
    <input type="file" id="dub-arq" accept="audio/*">`;
  $("#dub-arq").onchange = async () => {
    const f = $("#dub-arq").files[0]; if (!f) return;
    const ext = (f.name.split(".").pop() || "m4a").toLowerCase();
    const r = await fetch(`/api/dublagem?p=${encodeURIComponent(atual)}&inicio=${$("#dub-inicio").value || 0}&ext=${ext}&substituir=${$("#dub-subst").checked ? 1 : 0}`, { method: "POST", body: f });
    const j0 = await r.json();
    if (!r.ok) return alert(j0.erro);
    if (j0.aviso) aviso(j0.aviso, "erro");
    carregarEditor();
  };
}

// ---------------------------------------------------------------- formulário do item selecionado

const OBRIGATORIOS = new Set(["texto", "itens", "marcos", "mensagens", "barras", "de", "ate"]);

function campoHtml(c, valor, exemplo) {
  const id = "f-" + c.campo;
  const ex = exemplo === undefined || exemplo === null ? "" : (Array.isArray(exemplo)
    ? exemplo.map((x) => typeof x === "object" ? (x.de ? `${x.de}: ${x.texto}` : `${x.rotulo} = ${x.valor}`) : x).join("\n") : String(exemplo));
  const ph = ex ? ` placeholder="ex.: ${esc(ex.replace(/\n/g, " · "))}"` : "";
  const [k, opcoes] = c.tipo.split(":");
  if (k === "linhas") return `<label>${esc(c.rotulo)}<textarea id="${id}"${ph}>${esc((valor || []).join("\n"))}</textarea></label>`;
  if (k === "chat") return `<label>${esc(c.rotulo)}<textarea id="${id}">${esc((valor || []).map((m) => `${m.de}: ${m.texto}`).join("\n"))}</textarea></label>`;
  if (k === "barras") return `<label>${esc(c.rotulo)}<textarea id="${id}">${esc((valor || []).map((b) => `${b.rotulo} = ${b.valor}`).join("\n"))}</textarea></label>`;
  if (k === "numero") return `<label>${esc(c.rotulo)}<input id="${id}" type="number" step="0.05" value="${valor ?? ""}"${ph}></label>`;
  if (k === "escolha") return `<label>${esc(c.rotulo)}<select id="${id}"><option value="">padrão</option>${opcoes.split("|").map((o) =>
    `<option ${o === (valor || "") ? "selected" : ""}>${o}</option>`).join("")}</select></label>`;
  if (k === "ponto") return `<label>${esc(c.rotulo)}<div class="linha"><span>${valor ? `x ${valor[0]} · y ${valor[1]}` : "centro"}</span>
    <button type="button" class="link" data-ponto="${c.campo}">escolher no vídeo</button></div></label>`;
  return `<label>${esc(c.rotulo)}<input id="${id}" value="${esc(valor || "")}"${ph}></label>`;
}

function lerCampo(c) {
  const el = document.getElementById("f-" + c.campo); if (!el) return undefined;
  const k = c.tipo.split(":")[0], v = el.value;
  const linhas = v.split("\n").map((x) => x.trim()).filter(Boolean);
  if (k === "linhas") return linhas;
  if (k === "chat") return linhas.map((l) => { const [de, ...r] = l.split(":"); return { de: /cl[ií]nica/i.test(de) ? "clinica" : "paciente", texto: r.join(":").trim() || de }; });
  if (k === "barras") return linhas.map((l) => { const [r, n] = l.split("="); return { rotulo: r.trim(), valor: Math.max(0, Math.min(1, parseFloat(n) || 0.5)) }; });
  if (k === "numero") return v === "" ? undefined : Number(v);
  return v;
}

function formLegenda(box) {
  const l = ed.legendas[ed.sel.i];
  box.innerHTML = `<h2>Legenda · ${l.inicio.toFixed(1)}s</h2>
    <label>Texto como sai no vídeo<input id="lg-texto" value="${esc(l.texto)}"></label>
    <p class="dica">Corrigir aqui ensina o app: a correção vale para este vídeo inteiro (ex.: "divaine" → "Divine").</p>
    <div class="linha"><button class="link" id="lg-estilo">Aa estilo da legenda</button><button class="link" id="lg-prox">próxima ›</button><button id="lg-ok">Aplicar</button></div>`;
  $("#lg-estilo").onclick = () => { ed.sel = { tipo: "legestilo" }; desenharForm(); };
  $("#lg-ok").onclick = () => {
    const novo = $("#lg-texto").value.trim();
    if (novo && novo !== l.texto) { ed.correcoes[l.texto] = novo; l.texto = novo; sujar(); desenharLegendas(); }
  };
  $("#lg-prox").onclick = () => {
    if (ed.sel.i + 1 >= ed.legendas.length) return;
    ed.sel.i += 1; irPara(ed.legendas[ed.sel.i].inicio + 0.05); desenharLegendas(); desenharForm();
  };
}

const CORES_LEG = [["off_white", "#F5F4F1", "Off-white"], ["#FFFFFF", "#FFFFFF", "Branco"], ["dourado", "#CCBD91", "Dourado"],
  ["dourado_destaque", "#D6C08A", "Dourado claro"], ["creme", "#FBF8F1", "Creme"], ["#F7D046", "#F7D046", "Amarelo"],
  ["#111111", "#111111", "Preto"], ["navy", "#0E194A", "Navy"]];
const hexDe = (v) => (CORES_LEG.find((c) => c[0] === v) || [v, String(v || "").startsWith("#") ? v : "#F5F4F1"])[1];

async function formEstiloLegenda(box) {
  if (!ed.fontesLeg) { try { ed.fontesLeg = await api("/api/fontes_legenda"); } catch (e) { ed.fontesLeg = []; } }
  const s = ed.legEstilo;
  const pos = s.posicao ?? 0.66, tam = s.tamanho ?? 58;
  const fundo = s.caixa ? (s.caixa === "creme" ? "creme" : "escura") : "nenhum";
  const amostras = (campo, atual) => CORES_LEG.map(([v, hx, n]) =>
    `<button class="le-cor${hexDe(atual) === hx ? " sel" : ""}" data-campo="${campo}" data-v="${v}" title="${n}" style="background:${hx}"></button>`).join("") +
    `<input type="color" class="le-cor-livre" data-campo="${campo}" value="${hexDe(atual)}" title="Outra cor">`;
  box.innerHTML = `<h2>Estilo da legenda <small class="dica">(vale para o vídeo todo)</small></h2>
    <div class="le-grade">
      <div class="le-previa"><img id="le-prev" alt="Prévia da legenda"><span class="dica">Toque na imagem para pôr a legenda ali.</span></div>
      <div class="le-campos">
        <label>Posição <span id="le-pos-v"></span><input id="le-pos" type="range" min="0.12" max="0.9" step="0.01" value="${pos}"></label>
        <div class="chips"><button data-pos="0.25">Em cima</button><button data-pos="0.5">Meio</button><button data-pos="0.66">Peito</button><button data-pos="0.78">Embaixo</button></div>
        <label>Tamanho <span id="le-tam-v"></span><input id="le-tam" type="range" min="34" max="120" step="1" value="${tam}"></label>
        <label>Fonte<select id="le-fonte">${(ed.fontesLeg || []).map((f) => `<option value="${esc(f.arquivo)}" ${f.arquivo === s.fonte ? "selected" : ""}>${esc(f.nome)}</option>`).join("")}</select></label>
        <div class="le-rotulo">Cor do texto</div><div class="le-cores">${amostras("cor", s.cor || "off_white")}</div>
        <div class="le-rotulo">Cor da palavra-chave</div><div class="le-cores">${amostras("cor_chave", s.cor_chave || "dourado")}</div>
        <label>Fundo<select id="le-fundo"><option value="nenhum">Sem fundo</option><option value="escura">Caixa escura</option><option value="creme">Caixa clara</option></select></label>
        <label>Palavras por vez <span id="le-max-v"></span><input id="le-max" type="range" min="1" max="6" step="1" value="${s.max_palavras ?? 4}"></label>
        <label class="check"><input type="checkbox" id="le-alta" ${s.caixa_alta ? "checked" : ""}> CAIXA ALTA</label>
        <label class="check"><input type="checkbox" id="le-glow" ${s.glow ? "checked" : ""}> Brilho dourado</label>
        <label class="check"><input type="checkbox" id="le-pap" ${s.palavra_a_palavra !== false ? "checked" : ""}> Acende a palavra falada</label>
      </div>
    </div>
    <div class="linha"><button class="link" id="le-padrao">Usar nos próximos vídeos</button><button id="le-ok">Aplicar e salvar</button></div>
    <p class="dica">O quadro acima é a legenda real no ponto da agulha. Depois de salvar, gere a prévia para ver em movimento.</p>`;
  $("#le-fundo").value = fundo;
  let tmr;
  const previa = () => {
    $("#le-pos-v").textContent = `${Math.round((s.posicao ?? pos) * 100)}% da altura`;
    $("#le-tam-v").textContent = String(s.tamanho ?? tam);
    $("#le-max-v").textContent = String(s.max_palavras ?? 4);
    clearTimeout(tmr);
    tmr = setTimeout(() => {
      const v = $("#tl-video"); const t = v && v.src ? v.currentTime : $("#cc-rolagem").scrollLeft / px();
      const img = $("#le-prev"); if (!img) return;
      img.src = `/legenda.jpg?p=${encodeURIComponent(atual)}&t=${t.toFixed(2)}&estilo=${encodeURIComponent(JSON.stringify(s))}`;
    }, 220);
  };
  const mudar = (k, v) => { s[k] = v; ed.legEstiloMudou = true; sujar(); previa(); };
  $("#le-pos").oninput = (e) => mudar("posicao", +e.target.value);
  box.querySelectorAll("[data-pos]").forEach((b) => b.onclick = () => { $("#le-pos").value = b.dataset.pos; mudar("posicao", +b.dataset.pos); });
  $("#le-tam").oninput = (e) => mudar("tamanho", +e.target.value);
  $("#le-max").oninput = (e) => mudar("max_palavras", +e.target.value);
  $("#le-fonte").onchange = (e) => mudar("fonte", e.target.value);
  $("#le-fundo").onchange = (e) => mudar("caixa", e.target.value === "nenhum" ? false : e.target.value === "creme" ? "creme" : true);
  $("#le-alta").onchange = (e) => mudar("caixa_alta", e.target.checked);
  $("#le-glow").onchange = (e) => mudar("glow", e.target.checked ? "dourado" : false);
  $("#le-pap").onchange = (e) => mudar("palavra_a_palavra", e.target.checked);
  box.querySelectorAll(".le-cor").forEach((b) => b.onclick = () => {
    box.querySelectorAll(`.le-cor[data-campo="${b.dataset.campo}"]`).forEach((x) => x.classList.toggle("sel", x === b));
    mudar(b.dataset.campo, b.dataset.v);
  });
  box.querySelectorAll(".le-cor-livre").forEach((i) => i.oninput = () => mudar(i.dataset.campo, i.value.toUpperCase()));
  $("#le-prev").onclick = (e) => {
    const r = e.target.getBoundingClientRect();
    const y = Math.max(0.12, Math.min(0.9, (e.clientY - r.top) / r.height));
    $("#le-pos").value = y.toFixed(2); mudar("posicao", +y.toFixed(2));
  };
  $("#le-ok").onclick = () => salvarEditor(null).then(() => aviso("Estilo da legenda salvo. Gere a prévia para ver em movimento."));
  $("#le-padrao").onclick = async () => {
    try { await api("/api/legenda_padrao", { estilo: s }); aviso("Pronto: os próximos vídeos já saem com esta legenda."); }
    catch (err) { aviso(err.message, "erro"); }
  };
  previa();
}

function desenharForm() {
  const box = $("#tl-form");
  if (!ed.sel) { box.innerHTML = '<p class="dica">Toque num clipe ou numa marca da linha do tempo para editar, ou adicione um efeito no ponto do vídeo.</p>'; return; }
  if (ed.sel.tipo === "leg") return formLegenda(box);
  if (ed.sel.tipo === "legestilo") return formEstiloLegenda(box);
  if (formExtra(box)) return;
  if (ed.sel.tipo === "som") {
    const s = ed.sons[ed.sel.i];
    const grupos = {};
    (ed.kit || []).forEach((k) => (grupos[k.familia] = grupos[k.familia] || { uso: k.uso, nomes: [] }).nomes.push(k.nome));
    box.innerHTML = `<h2>Som</h2>
      <label>Qual som<select id="s-nome">${Object.entries(grupos).map(([f, g]) => `<optgroup label="${esc(f.replace(/_/g, " "))}: ${esc(g.uso)}">${g.nomes.map((n) =>
        `<option ${n === s.nome ? "selected" : ""}>${n}</option>`).join("")}</optgroup>`).join("")}</select></label>
      <div class="linha"><button id="s-ouvir">▶ Ouvir</button></div>
      <label>Volume (sempre baixo, bem abaixo da voz)<input id="s-ganho" type="range" min="-40" max="-12" step="1" value="${s.ganho_db ?? -24}"></label>
      <label>Entra em (s)<input id="s-inicio" type="number" step="0.1" value="${s.inicio}"></label>
      <div class="linha"><button class="link" id="s-del">remover</button><button id="s-ok">Aplicar</button></div>`;
    const tocar = () => { const a = new Audio(`/sfx.wav?nome=${$("#s-nome").value}`); a.volume = Math.pow(10, ($("#s-ganho").value + 18) / 20 / 2); a.play(); };
    $("#s-ouvir").onclick = tocar; $("#s-nome").onchange = tocar;
    $("#s-ok").onclick = () => { s.nome = $("#s-nome").value; s.ganho_db = Number($("#s-ganho").value); s.inicio = Number($("#s-inicio").value) || 0; sujar(); desenharTimeline(); };
    $("#s-del").onclick = () => { ed.sons.splice(ed.sel.i, 1); ed.sel = null; sujar(); desenharTimeline(); desenharForm(); };
    return;
  }
  if (ed.sel.tipo === "voz") {
    const d = ed.dubs[ed.sel.i];
    box.innerHTML = `<h2>Sua voz</h2><audio controls src="/arquivo?p=${encodeURIComponent(atual)}&f=${encodeURIComponent(d.arquivo)}"></audio>
      <label>Entra em (s)<input id="v-inicio" type="number" step="0.1" value="${d.inicio}"></label>
      <label>Volume<input id="v-ganho" type="range" min="-12" max="6" step="1" value="${d.ganho_db ?? 0}"></label>
      <div class="linha"><button class="link" id="v-del">remover</button><button id="v-ok">Aplicar</button></div>`;
    $("#v-ok").onclick = () => { d.inicio = Number($("#v-inicio").value) || 0; d.ganho_db = Number($("#v-ganho").value); sujar(); desenharTimeline(); };
    $("#v-del").onclick = () => { ed.dubs.splice(ed.sel.i, 1); ed.sel = null; sujar(); desenharTimeline(); desenharForm(); };
    return;
  }
  if (ed.sel.tipo === "msg") {
    const m = ed.mensagens[ed.sel.i];
    box.innerHTML = `<h2>Mensagem</h2>
      <label>Título<input id="m-titulo" value="${esc(m.titulo || "")}" placeholder="Frase / com *destaque*"></label>
      <label>Apoio (opcional)<input id="m-apoio" value="${esc(m.apoio || "")}"></label>
      <label>Entra em (s)<input id="m-inicio" type="number" step="0.1" value="${m.inicio ?? ""}"></label>
      <div class="linha"><button class="link" id="m-del">remover</button><button id="m-ok">Aplicar</button></div>`;
    $("#m-ok").onclick = () => { m.titulo = $("#m-titulo").value; m.apoio = $("#m-apoio").value || undefined;
      m.inicio = $("#m-inicio").value === "" ? undefined : Number($("#m-inicio").value); sujar(); desenharMsgs(); desenharTimeline(); };
    $("#m-del").onclick = () => { ed.mensagens.splice(ed.sel.i, 1); ed.sel = null; sujar(); desenharMsgs(); desenharTimeline(); desenharForm(); };
    return;
  }
  const e = ed.efeitos[ed.sel.i];
  if (!e.tipo) {
    const cats = ["Todos", ...new Set(ed.catalogo.map((c) => c.categoria || "Outros"))];
    box.innerHTML = `<h2>Qual efeito em ${(+e.inicio).toFixed(1)}s?</h2>
      <input id="e-busca" class="e-busca" placeholder="Buscar efeito (ex.: zoom, papel, texto, pixel)" autocomplete="off">
      <div class="chips seg cat-ef">${cats.map((c, k) => `<button class="${k ? "" : "dourado"}" data-cat="${esc(c)}">${esc(c)}</button>`).join("")}</div>
      <div class="tipos" id="e-tipos"></div>
      <div class="linha"><button class="link" id="e-cancelar">cancelar</button></div>`;
    let catAtual = "Todos";
    const norm = (x) => (x || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    const listar = () => {
      const q = norm($("#e-busca").value);
      const lista = ed.catalogo.filter((c) => (catAtual === "Todos" || (c.categoria || "Outros") === catAtual)
        && (!q || norm(c.nome + " " + c.tipo + " " + (c.categoria || "")).includes(q)));
      $("#e-tipos").innerHTML = lista.map((c) =>
        `<div class="tipo" data-tipo="${c.tipo}" title="${esc(c.codigos.join(", "))}"><img loading="lazy" src="/efeito.png?tipo=${c.tipo}" alt="">${esc(c.nome)}</div>`).join("")
        || '<p class="dica">Nenhum efeito com esse nome.</p>';
      $$("#e-tipos .tipo").forEach((t) => t.onclick = escolher);
    };
    $$(".cat-ef [data-cat]").forEach((b) => b.onclick = () => {
      catAtual = b.dataset.cat; $$(".cat-ef [data-cat]").forEach((x) => x.classList.toggle("dourado", x === b)); listar();
    });
    $("#e-busca").oninput = listar;
    function escolher(ev) {
      const t = ev.currentTarget;
      const c = TIPOS_NOME()[t.dataset.tipo];
      e.tipo = c.tipo;
      // só o que o efeito precisa para existir vem preenchido; o resto aparece como exemplo apagadinho
      for (const f of c.campos) if (OBRIGATORIOS.has(f.campo) && c.exemplo[f.campo] !== undefined) e[f.campo] = c.exemplo[f.campo];
      sujar(); desenharTimeline(); desenharForm();
    }
    listar();
    setTimeout(() => { const b = $("#e-busca"); if (b && window.innerWidth > 700) b.focus(); }, 30);
    $("#e-cancelar").onclick = () => { ed.efeitos.splice(ed.sel.i, 1); ed.sel = null; desenharTimeline(); desenharForm(); };
    return;
  }
  const c = TIPOS_NOME()[e.tipo];
  box.innerHTML = `<h2>${esc(c.nome)}</h2>${c.campos.map((f) => campoHtml(f, e[f.campo], c.exemplo[f.campo])).join("")}
    <div class="linha"><label>Entra em (s)<input id="e-inicio" type="number" step="0.1" value="${e.inicio}"></label>
    <label>Dura (s)<input id="e-dur" type="number" step="0.1" value="${duracaoEf(e)}"></label></div>
    <div class="linha"><button class="link" id="e-del">remover</button><button class="link" id="e-trocar">trocar efeito</button>
    <button id="e-ok">Aplicar</button></div>`;
  $$("[data-ponto]").forEach((b) => b.onclick = () => {
    ed.pegandoPonto = { i: ed.sel.i, campo: b.dataset.ponto };
    b.textContent = "clique no vídeo…"; $("#tl-video").pause();
  });
  if (e.ponto) mostrarMira(e.ponto[0], e.ponto[1]); else $("#tl-mira").hidden = true;
  $("#e-ok").onclick = () => {
    for (const f of c.campos) {
      if (f.tipo === "ponto") continue;
      const v = lerCampo(f);
      if (v === undefined || v === "" || (Array.isArray(v) && !v.length)) {
        if (OBRIGATORIOS.has(f.campo) && c.exemplo[f.campo] !== undefined) e[f.campo] = c.exemplo[f.campo];   // não deixa o efeito quebrar
        else delete e[f.campo];
      } else e[f.campo] = v;
    }
    e.inicio = Math.max(0, Number($("#e-inicio").value) || 0);
    const d = Number($("#e-dur").value); if (d && Math.abs(d - c.duracao) > 0.01) e.duracao = d; else delete e.duracao;
    sujar(); desenharTimeline(); desenharForm();
  };
  $("#e-del").onclick = () => { ed.efeitos.splice(ed.sel.i, 1); ed.sel = null; sujar(); desenharTimeline(); desenharForm(); };
  $("#e-trocar").onclick = () => { ed.efeitos[ed.sel.i] = { tipo: null, inicio: e.inicio }; desenharForm(); };
}

// ---------------------------------------------------------------- textos

function desenharMsgs() {
  $("#ed-msgs").innerHTML = ed.mensagens.map((m, i) => `<div class="msg-ed" data-i="${i}">
    <input data-k="titulo" value="${esc(m.titulo || "")}" placeholder="Mensagem / com *destaque*">
    <input data-k="apoio" value="${esc(m.apoio || "")}" placeholder="apoio (opcional)">
    <input data-k="inicio" type="number" step="0.1" value="${m.inicio ?? ""}" placeholder="${m.na_fala ? "na fala" : "auto"}" title="Segundo em que entra (vazio: em sequência${m.na_fala ? " ou quando a frase é dita" : ""})">
    <button class="link" data-del="${i}" title="remover">✕</button></div>`).join("") || '<p class="dica">Nenhuma mensagem.</p>';
  $$("#ed-msgs input").forEach((inp) => inp.oninput = () => {
    const m = ed.mensagens[inp.closest(".msg-ed").dataset.i], k = inp.dataset.k;
    if (k === "inicio") { if (inp.value === "") delete m.inicio; else m.inicio = Number(inp.value); }
    else if (inp.value) m[k] = inp.value; else delete m[k];
    sujar(); desenharTimeline();
  });
  $$("#ed-msgs [data-del]").forEach((b) => b.onclick = () => { ed.mensagens.splice(+b.dataset.del, 1); sujar(); desenharMsgs(); desenharTimeline(); });
}
$("#ed-add-msg-fim").onclick = () => { ed.mensagens.push({ titulo: "" }); sujar(); desenharMsgs(); };
["#ed-selo", "#ed-cta", "#ed-fech-frase", "#ed-fech-cta"].forEach((s) => $(s).addEventListener("input", () => sujar()));

// ---------------------------------------------------------------- versões: hook e fontes

async function buscarHooks(n) {
  ed.hooksTema = ed.proj ? ed.proj.titulo : "";
  ed.hooks = await api(`/api/hooks?n=${n}&tema=${encodeURIComponent(ed.hooksTema || "")}`);
}
$("#ed-mais-hooks").onclick = async () => { await buscarHooks(12); desenharVersoes(); };

function textoHook(v) {
  if (Array.isArray(v.hook)) return v.hook.map((b) => b.titulo).join(" → ");
  if (v.hook && v.hook.titulo) return v.hook.titulo;
  return "";
}

function desenharVersoes() {
  const usadas = ed.versoes.map((v) => v.fontes).filter(Boolean);
  $("#ed-versoes").innerHTML = ed.versoes.map((v, i) => {
    const amostra = (textoHook(v).split(" → ")[0] || (ed.hooks[i] && ed.hooks[i].batidas[0]) || "Sua frase / em *destaque.*").slice(0, 60);
    const opcoesHook = [`<option value="__auto" ${v.hook === "auto" && !v.hook_id ? "selected" : ""}>Sortear do banco</option>`]
      .concat(v.hook_id && !ed.hooks.find((h) => h.id === v.hook_id) ? [`<option value="${esc(v.hook_id)}" selected>${esc(v.hook_id)} (atual)</option>`] : [])
      .concat(ed.hooks.map((h) => `<option value="${esc(h.id)}" ${h.id === v.hook_id ? "selected" : ""}>${esc(h.id)} · ${esc(h.tipo)} · ${esc(h.batidas.join(" → ").replace(/\*/g, ""))}</option>`))
      .concat([`<option value="__proprio" ${!v.hook_id && v.hook && v.hook !== "auto" ? "selected" : ""}>Escrever o meu</option>`]).join("");
    const proprio = !v.hook_id && v.hook && v.hook !== "auto";
    return `<div class="ed-versao" data-i="${i}"><h3>${esc(v.nome || "V" + (i + 1))}</h3>
      <label>Hook<select class="h-sel">${opcoesHook}</select></label>
      <label class="h-proprio" ${proprio ? "" : "hidden"}>Seu hook (use → para a 2ª batida)<input class="h-txt" value="${esc(proprio ? textoHook(v) : "")}"></label>
      <label>Fontes ${v.fontes ? `<b>${esc(v.fontes)}</b>` : "(rodízio automático)"}</label>
      <div class="fontes"><div class="fonte auto ${v.fontes ? "" : "sel"}" data-f="">Automático</div>${ed.fontes.map((f) =>
        `<div class="fonte ${v.fontes === f.codigo ? "sel" : ""}" data-f="${f.codigo}" title="${esc(f.nome)}${usadas.includes(f.codigo) && v.fontes !== f.codigo ? " (já usada em outra versão)" : ""}">
          <span>${f.codigo}</span><img loading="lazy" src="/fonte.png?c=${f.codigo}&t=${encodeURIComponent(amostra)}" alt="${esc(f.nome)}"></div>`).join("")}</div></div>`;
  }).join("") || '<p class="dica">Sem versões: use a edição automática ou adicione no projeto.yaml.</p>';
  $$(".ed-versao").forEach((box) => {
    const v = ed.versoes[box.dataset.i];
    box.querySelector(".h-sel").onchange = (e) => {
      const val = e.target.value;
      delete v.hook_id;
      if (val === "__auto") v.hook = "auto";
      else if (val === "__proprio") { v.hook = [{ titulo: "" }]; box.querySelector(".h-proprio").hidden = false; }
      else { v.hook_id = val; delete v.hook; }
      sujar(); if (val !== "__proprio") desenharVersoes();
    };
    box.querySelector(".h-txt").oninput = (e) => {
      v.hook = e.target.value.split("→").map((t) => t.trim()).filter(Boolean).map((t) => ({ titulo: t })); sujar();
    };
    box.querySelectorAll(".fonte").forEach((f) => f.onclick = () => {
      const c = f.dataset.f;
      if (c && ed.versoes.some((o, j) => j != box.dataset.i && o.fontes === c))
        if (!confirm(`A combinação ${c} já está em outra versão. A regra é cada versão com fontes diferentes. Usar mesmo assim?`)) return;
      if (c) v.fontes = c; else delete v.fontes;
      sujar(); desenharVersoes();
    });
  });
}

// ---------------------------------------------------------------- salvar

async function salvarEditor(depois) {
  const fech = { ...(ed.proj.fechamento || {}), frase: $("#ed-fech-frase").value, cta: $("#ed-fech-cta").value };
  const versoes = ed.versoes.map((v) => {
    const o = { ...v };
    if (Array.isArray(o.hook) && !o.hook.some((b) => b.titulo)) o.hook = "auto";
    return o;
  });
  const pendentes = ed.efeitos.filter((e) => !e.tipo).length;
  const efeitos = ed.efeitos.filter((e) => e.tipo);
  const mensagens = ed.mensagens.filter((m) => (m.titulo || "").trim()).map((m) => {
    const o = { ...m }; if (o.inicio === undefined || o.inicio === null || o.inicio === "") delete o.inicio; return o;
  });
  try {
    const audio = { ...(ed.proj.audio || {}), ...ed.audio, dublagem: ed.dubs };
    if (!ed.dubs.length) delete audio.dublagem;
    if (!audio.volume_original_db) delete audio.volume_original_db;
    const extra = ed.corteLimpo || !ed.clipes.length ? {} : { clipes: ed.clipes };
    await api("/api/dados", { p: atual, dados: { efeitos, mensagens, versoes, selo: $("#ed-selo").value,
      cta_antecipado: $("#ed-cta").value, fechamento: fech, sons: ed.sons.filter((x) => x.nome),
      sfx_automaticos: $("#tl-sfx-auto").checked, audio, cor: Object.keys(ed.cor).length ? ed.cor : null,
      musica_licenciada: ed.licenca || null, correcoes: Object.keys(ed.correcoes || {}).length ? ed.correcoes : {}, ...extra,
      ...(ed.legEstiloMudou ? { legendas: { ...(typeof ed.proj.legendas === "object" && ed.proj.legendas ? ed.proj.legendas : {}), ...ed.legEstilo, ativo: true } } : {}) } });
    ed.legEstiloMudou = false;
    ed.efeitos = efeitos;
    sujar(false);
    if (pendentes) $("#ed-status").textContent = "Salvo (efeito sem tipo escolhido ficou de fora).";
    if (depois === true) rodar("previa"); else if (depois !== null) abrir(atual);
  } catch (err) { alert(err.message); }
}
$("#ed-salvar").onclick = () => salvarEditor(false);
$("#ed-salvar-previa").onclick = () => salvarEditor(true);


async function fixarAutos() {
  if (ed.sujo) { await salvarEditor(null); }
  try {
    const r = await api("/api/fixar_linha", { p: atual });
    $("#ed-status").textContent = `Na linha do tempo: ${r.efeitos} efeito(s) e ${r.sons} som(ns) da ${r.versao}. Agora tudo é editável.`;
    await carregarEditor();
  } catch (err) { alert(err.message); }
}

// formulários de clipe e de automático (chamado por desenharForm)
function formExtra(box) {
  if (!ed.sel) return false;
  if (ed.sel.tipo.endsWith(" auto")) {
    const au = autos() || { efeitos: [], sons: [] };
    const item = ed.sel.tipo.startsWith("ef") ? au.efeitos[ed.sel.i] : au.sons[ed.sel.i];
    const nome = ed.sel.tipo.startsWith("ef") ? ((TIPOS_NOME()[item.tipo] || {}).nome || item.tipo) : item.nome;
    box.innerHTML = `<h2>Automático</h2><p><b>${esc(nome)}</b> em ${Number(item.inicio).toFixed(1)}s, colocado pelo ritmo viral (ou pelos sons automáticos).</p>
      <p class="dica">Para mudar o momento, trocar ou tirar, traga os automáticos para a linha do tempo: eles viram itens normais,
        editáveis, e o app para de colocar outros sozinho neste projeto.</p>
      <button class="dourado" id="tl-fixar2">Trazer todos para a linha do tempo</button>`;
    $("#tl-fixar2").onclick = fixarAutos;
    return true;
  }
  if (ed.sel.tipo !== "clip") return false;
  const c = ed.clipes[ed.sel.i], info = ed.clipesInfo[ed.sel.i] || {};
  if (!c) return false;
  const vel = ed.cfg.velocidades.map((x) => `<option value="${x}" ${Number(c.velocidade || 1) === x ? "selected" : ""}>${x}x${x < 1 ? " (câmera lenta)" : ""}</option>`).join("");
  const trans = Object.entries(ed.cfg.transicoes).map(([k, n]) => `<option value="${k}" ${(c.transicao || "dissolver") === k ? "selected" : ""}>${esc(n)}</option>`).join("");
  box.innerHTML = `<h2>Clipe ${ed.sel.i + 1}</h2><p class="dica">${esc(String(c.arquivo).split("/").pop())}${info.duracao_arquivo ? ` · arquivo de ${info.duracao_arquivo.toFixed(1)}s` : ""}</p>
    <div class="grade2"><label>Começa em (s)<input id="c-ini" type="number" step="0.1" min="0" value="${c.inicio ?? 0}"></label>
      <label>Termina em (s)<input id="c-fim" type="number" step="0.1" min="0" value="${c.fim ?? ""}" placeholder="fim do arquivo"></label></div>
    <label>Velocidade<select id="c-vel">${vel}</select></label>
    <label>Transição na entrada<select id="c-trans" ${ed.sel.i === 0 ? "disabled" : ""}>${trans}</select></label>
    <label>Volume do som <span id="c-vol-v">${Math.round((c.volume ?? 1) * 100)}%</span><input id="c-vol" type="range" min="0" max="2" step="0.05" value="${c.volume ?? 1}"></label>
    <label>Zoom <input id="c-zoom" type="range" min="1" max="1.6" step="0.05" value="${c.zoom ?? 1}"></label>
    <label class="check"><input type="checkbox" id="c-velocity" ${c.velocity ? "checked" : ""}> velocity (acelera, câmera lenta, acelera)</label>
    <label class="check"><input type="checkbox" id="c-rev" ${c.reverso ? "checked" : ""}> de trás para frente (reverso)</label>
    <label class="check"><input type="checkbox" id="c-mudo" ${c.mudo ? "checked" : ""}> sem som (b-roll)</label>
    <div class="linha"><button id="c-esq" ${ed.sel.i === 0 ? "disabled" : ""}>◀</button><button id="c-dir" ${ed.sel.i === ed.clipes.length - 1 ? "disabled" : ""}>▶</button>
      <button id="c-dup">Duplicar</button><button id="c-del" class="link">remover</button></div>`;
  const num = (v) => v === "" ? undefined : Math.max(0, Number(v));
  const aplicar = () => {
    c.inicio = num($("#c-ini").value) ?? 0;
    const f = num($("#c-fim").value); if (f === undefined || f <= c.inicio) delete c.fim; else c.fim = f;
    const v = Number($("#c-vel").value); if (v === 1) delete c.velocidade; else c.velocidade = v;
    const t = $("#c-trans").value; if (t === "dissolver" || ed.sel.i === 0) delete c.transicao; else c.transicao = t;
    const vol = Number($("#c-vol").value); if (vol === 1) delete c.volume; else c.volume = vol;
    const z = Number($("#c-zoom").value); if (z === 1) delete c.zoom; else c.zoom = z;
    if ($("#c-rev").checked) c.reverso = true; else delete c.reverso;
    if ($("#c-velocity").checked) c.velocity = true; else delete c.velocity;
    if ($("#c-mudo").checked) c.mudo = true; else delete c.mudo;
    $("#c-vol-v").textContent = Math.round(vol * 100) + "%";
    sujar(); desenharClipes();
  };
  box.querySelectorAll("input, select").forEach((el) => el.addEventListener(el.type === "range" ? "input" : "change", aplicar));
  const mover = (d) => { const i = ed.sel.i, j = i + d; [ed.clipes[i], ed.clipes[j]] = [ed.clipes[j], ed.clipes[i]];
    [ed.clipesInfo[i], ed.clipesInfo[j]] = [ed.clipesInfo[j], ed.clipesInfo[i]]; ed.sel.i = j; sujar(); desenharTimeline(); desenharForm(); };
  $("#c-esq").onclick = () => mover(-1); $("#c-dir").onclick = () => mover(1);
  $("#c-dup").onclick = () => { ed.clipes.splice(ed.sel.i + 1, 0, { ...c }); ed.clipesInfo.splice(ed.sel.i + 1, 0, info); ed.sel.i++; sujar(); desenharTimeline(); desenharForm(); };
  $("#c-del").onclick = () => { if (ed.clipes.length < 2) return alert("O vídeo precisa de pelo menos um clipe.");
    ed.clipes.splice(ed.sel.i, 1); ed.clipesInfo.splice(ed.sel.i, 1); ed.sel = null; sujar(); desenharTimeline(); desenharForm(); };
  return true;
}

// ---------------------------------------------------------------- cor e áudio
function desenharCorAudio() {
  $("#ed-filtro").innerHTML = Object.entries(ed.cfg.filtros).map(([k, n]) => `<option value="${k}" ${(ed.cor.filtro || "natural") === k ? "selected" : ""}>${esc(n)}</option>`).join("");
  ["brilho", "contraste", "saturacao", "temperatura"].forEach((k) => { $("#ed-" + k).value = ed.cor[k] || 0; });
  $("#ed-vol-orig").value = ed.audio.volume_original_db || 0;
  $("#ed-vol-trilha").value = ed.audio.volume_trilha_db ?? -24;
  $("#ed-trilha").checked = ed.audio.trilha !== false;
  $("#ed-licenca").checked = ed.licenca;
  $("#ed-vol-orig-v").textContent = `${ed.audio.volume_original_db || 0} dB`;
  $("#ed-vol-trilha-v").textContent = `${ed.audio.volume_trilha_db ?? -24} dB`;
  $("#ed-musica-atual").textContent = ed.audio.musica ? `Música: ${String(ed.audio.musica).split("/").pop()}` : "Trilha: lounge original Divine (sem direitos autorais).";
  $("#ed-musica-tirar").hidden = !ed.audio.musica;
}
$("#ed-filtro").onchange = (e) => { ed.cor.filtro = e.target.value; sujar(); };
["brilho", "contraste", "saturacao", "temperatura"].forEach((k) => $("#ed-" + k).oninput = (e) => { ed.cor[k] = Number(e.target.value); sujar(); });
$("#ed-cor-zerar").onclick = () => { ed.cor = {}; desenharCorAudio(); sujar(); };
$("#ed-vol-orig").oninput = (e) => { ed.audio.volume_original_db = Number(e.target.value); $("#ed-vol-orig-v").textContent = e.target.value + " dB"; sujar(); };
$("#ed-vol-trilha").oninput = (e) => { ed.audio.volume_trilha_db = Number(e.target.value); $("#ed-vol-trilha-v").textContent = e.target.value + " dB"; sujar(); };
$("#ed-trilha").onchange = (e) => { ed.audio.trilha = e.target.checked; sujar(); };
$("#ed-licenca").onchange = (e) => { ed.licenca = e.target.checked; sujar(); };
$("#ed-musica-tirar").onclick = () => { delete ed.audio.musica; desenharCorAudio(); sujar(); };
$("#ed-musica").onchange = async () => {
  const f = $("#ed-musica").files[0]; if (!f) return;
  if (ed.sujo) await salvarEditor(null);
  $("#ed-status").textContent = "Enviando a música…";
  const r = await fetch(`/api/musica?p=${encodeURIComponent(atual)}&nome=${encodeURIComponent(f.name)}`, { method: "POST", body: f });
  const j = await r.json(); if (!r.ok) return alert(j.erro);
  await carregarEditor();
  $("#ed-status").textContent = "Música no projeto. Marque a licença comercial para poder postar.";
};

// a linha do tempo é desenhada pela largura: redesenha quando a aba aparece ou a tela muda de tamanho
if (window.ResizeObserver) new ResizeObserver(() => { if (ed.proj && $("#cc-rolagem").clientWidth) desenharTimeline(); }).observe($("#cc-rolagem"));


// atalhos de teclado na aba Edição (como no CapCut): espaço toca/pausa, S divide, Delete remove, ⌘/Ctrl+S salva
document.addEventListener("keydown", (e) => {
  if ($("#aba-edicao").hidden || $("#projeto").hidden) return;
  const digitando = /INPUT|TEXTAREA|SELECT/.test((document.activeElement || {}).tagName || "");
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") { e.preventDefault(); salvarEditor(false); return; }
  if (digitando) return;
  const v = $("#tl-video");
  if (e.key === " ") { e.preventDefault(); if (v.src) (v.paused ? v.play() : v.pause()); }
  else if (e.key.toLowerCase() === "s") { e.preventDefault(); $("#tl-dividir").click(); }
  else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
    if (!v.src) return;
    e.preventDefault(); v.currentTime = Math.max(0, v.currentTime + (e.key === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 1 : 1 / 30));
  } else if ((e.key === "Delete" || e.key === "Backspace") && ed.sel && !ed.sel.tipo.endsWith(" auto")) {
    e.preventDefault();
    const listas = { ef: ed.efeitos, msg: ed.mensagens, som: ed.sons, voz: ed.dubs, clip: ed.clipes };
    const l = listas[ed.sel.tipo];
    if (!l || !l[ed.sel.i]) return;
    if (ed.sel.tipo === "clip") { if (ed.clipes.length < 2 || !confirm("Remover este clipe?")) return; ed.clipesInfo.splice(ed.sel.i, 1); }
    l.splice(ed.sel.i, 1); ed.sel = null; sujar(); desenharMsgs(); desenharTimeline(); desenharForm();
  }
});


// 📸 quadro do vídeo para ferramentas externas (Higgsfield, Canva) e Nano Banana direto do app
$("#tl-quadro").onclick = async () => {
  const v = $("#tl-video");
  if (!v.src) return alert("Gere uma prévia primeiro para tirar o quadro.");
  const ref = decodeURIComponent((v.src.match(/[?&]f=([^&]+)/) || [])[1] || "");
  let q;
  try { q = await api("/api/quadro", { p: atual, arquivo: ref, t: v.currentTime }); } catch (err) { return alert(err.message); }
  const integ = await api("/api/integracoes").catch(() => ({}));
  const url = (f) => `/arquivo?p=${encodeURIComponent(atual)}&f=${encodeURIComponent(f)}&v=${Date.now()}`;
  const m = document.createElement("div");
  m.className = "modal";
  m.innerHTML = `<div class="cartao quadro-caixa"><div class="linha-titulo"><h2>📸 Quadro em ${v.currentTime.toFixed(1)}s</h2><button class="link" data-f>fechar</button></div>
    <div class="quadro-grade"><img id="qd-img" src="${url(q.arquivo)}" alt="">
    <div><p class="dica">Salvo em <code>${esc(q.arquivo)}</code>.</p>
      <button data-baixar>⤓ Baixar (para o Higgsfield ou o Canva)</button>
      <p class="dica">No Higgsfield: suba o quadro, escolha um movimento de câmera (dolly, crash zoom, órbita) e solte o vídeo gerado em Vídeos brutos.</p>
      <h3>✦ Nano Banana</h3>
      ${integ.nano_banana ? `<div class="chips">${["Trocar o fundo por uma sala de clínica de luxo", "Melhorar a luz, pele natural, sem exagero",
        "Capa elegante com espaço vazio em cima para o título", "Deixar o aparelho com aparência de produto premium"].map((x) =>
        `<button class="chip" data-pre="${esc(x)}">${esc(x)}</button>`).join("")}</div>
        <textarea id="qd-pedido" rows="3" placeholder="O que fazer com a imagem?"></textarea>
        <button class="dourado" data-nb>Gerar com Nano Banana</button><p class="dica" id="qd-msg"></p>`
      : `<p class="dica">${esc(integ.motivo || "")}</p>`}
    </div></div></div>`;
  document.body.appendChild(m);
  m.onclick = (e) => { if (e.target === m || e.target.dataset.f !== undefined) m.remove(); };
  m.querySelector("[data-baixar]").onclick = () => salvarNaGaleria(url(q.arquivo), q.arquivo.split("/").pop());
  m.querySelectorAll("[data-pre]").forEach((b) => b.onclick = () => { m.querySelector("#qd-pedido").value = b.dataset.pre; });
  const nb = m.querySelector("[data-nb]");
  if (nb) nb.onclick = async () => {
    nb.disabled = true; m.querySelector("#qd-msg").textContent = "Gerando… (até 1 min)";
    try {
      const r = await api("/api/nanobanana", { p: atual, imagem: q.arquivo, pedido: m.querySelector("#qd-pedido").value });
      m.querySelector("#qd-img").src = url(r.arquivo);
      m.querySelector("#qd-msg").innerHTML = `Pronto: <code>${esc(r.arquivo)}</code> (em Vídeos brutos/fotos do projeto; use na capa, carrossel ou post).`;
    } catch (err) { m.querySelector("#qd-msg").textContent = err.message; }
    nb.disabled = false;
  };
};
