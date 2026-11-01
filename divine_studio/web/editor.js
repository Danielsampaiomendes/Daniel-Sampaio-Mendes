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
  $("#tl-sfx-auto").checked = d.projeto.sfx_automaticos !== false;
  if (!ed.kit) ed.kit = await api("/api/sons");
  ed.sel = null;
  const v = $("#tl-video");
  if (d.referencia) {
    v.src = `/arquivo?p=${encodeURIComponent(atual)}&f=${encodeURIComponent(d.referencia)}`;
    $("#tl-dica").innerHTML = "Dê play, pause no ponto que quiser e clique em <b>+ Efeito aqui</b> ou <b>+ Mensagem aqui</b>. Arraste as marcas para mudar o momento.";
  } else {
    v.removeAttribute("src"); v.load();
    $("#tl-dica").innerHTML = "Gere as prévias uma vez (ou a <b>edição automática</b>) para ver o vídeo aqui. Dá para adicionar efeitos digitando o segundo.";
  }
  ed.base = d.duracao_base || 0;
  ed.total = ed.base ? ed.base + ed.fechS : 30;
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

const px = () => $("#tl-barra").clientWidth / Math.max(1, ed.total);

function duracaoEf(e) { return Number(e.duracao) || (TIPOS_NOME()[e.tipo] || {}).duracao || 3; }

function hookFim() {
  const v = ed.versoes[0] || {};
  const h = Array.isArray(v.hook) ? v.hook : [];
  if (!h.length) return 3;
  return h.reduce((s, b) => s + (Number(b.duracao) || Math.max(1.6, (b.titulo || "").split(/\s+/).length / 3.2 + 0.7)), 0);
}

function desenharTimeline() {
  const barra = $("#tl-barra");
  barra.querySelectorAll(".tl-marca, .tl-zona").forEach((x) => x.remove());
  const k = px();
  const zona = (cls, a, b) => { const z = document.createElement("div"); z.className = "tl-zona " + cls;
    z.style.left = a * k + "px"; z.style.width = Math.max(0, b - a) * k + "px"; barra.appendChild(z); };
  zona("hook", 0, Math.min(hookFim(), ed.total));
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
  $("#tl-barra").appendChild(el);
}

$("#tl-barra").onpointerdown = (e) => {
  const r = $("#tl-barra").getBoundingClientRect();
  const t = (e.clientX - r.left) / px();
  const v = $("#tl-video"); if (v.src) v.currentTime = Math.max(0, Math.min(t, ed.total));
};
$("#tl-video").ontimeupdate = () => { $("#tl-cursor").style.left = $("#tl-video").currentTime * px() + "px"; };
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

function agora() { const v = $("#tl-video"); return Math.round((v.src ? v.currentTime : 0) * 10) / 10; }

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
  mostrarCopy();
};

// copy sugerida (editável) antes de gravar: lê no teleprompter enquanto o vídeo toca sem som
async function mostrarCopy() {
  const box = $("#tl-form");
  box.innerHTML = '<p class="dica">Carregando a copy…</p>';
  let c;
  try { c = await api("/api/copy?p=" + encodeURIComponent(atual)); } catch (err) { box.innerHTML = `<p class="dica">${esc(err.message)}</p>`; return; }
  const iaOk = (await estadoIA().catch(() => ({}))).ok;
  const semMic = !navigator.mediaDevices || !window.MediaRecorder;
  box.innerHTML = `<h2>🎙 Copy para gravar</h2>
    <p class="dica">Veio de: ${esc(c.fonte)} · cerca de <b id="cp-seg">${c.segundos}</b> s falando. Edite à vontade: é o que vai aparecer no teleprompter.</p>
    <textarea id="cp-texto" class="copy-voz">${esc(c.copy)}</textarea>
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
  campo.oninput = () => { $("#cp-seg").textContent = (campo.value.split(/\s+/).filter(Boolean).length / 2.6).toFixed(1); };
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
    const r = await fetch(`/api/dublagem?p=${encodeURIComponent(atual)}&inicio=${$("#cp-inicio").value || 0}&ext=${ext}&substituir=${$("#cp-subst").checked ? 1 : 0}`, { method: "POST", body: f });
    if (!r.ok) return alert((await r.json()).erro);
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
    const r = await fetch(`/api/dublagem?p=${encodeURIComponent(atual)}&inicio=${inicio}&ext=${ext}&substituir=${substituir ? 1 : 0}`, { method: "POST", body: blob });
    const j = await r.json();
    if (!r.ok) return alert(j.erro);
    $("#ed-status").textContent = "Voz gravada. Gere as prévias para ouvir no vídeo.";
    carregarEditor();
  };
  v.muted = true; v.currentTime = inicio;
  gravador.start(250);
  v.play();
  $("#tl-gravar").textContent = "■ Parar gravação"; $("#tl-gravar").classList.add("gravando");
  v.onended = () => gravador && gravador.stop();
  const caixa = tp.querySelector(".tp-texto");
  const dur = Math.max(4, texto.split(/\s+/).filter(Boolean).length / 2.6) * 1000, t0 = performance.now();
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
    if (!r.ok) return alert((await r.json()).erro);
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

function desenharForm() {
  const box = $("#tl-form");
  if (!ed.sel) { box.innerHTML = '<p class="dica">Clique numa marca da linha do tempo para editar, ou adicione um efeito no ponto do vídeo.</p>'; return; }
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
    box.innerHTML = `<h2>Qual efeito em ${(+e.inicio).toFixed(1)}s?</h2><div class="tipos">${ed.catalogo.map((c) =>
      `<div class="tipo" data-tipo="${c.tipo}" title="${esc(c.codigos.join(", "))}"><img loading="lazy" src="/efeito.png?tipo=${c.tipo}" alt="">${esc(c.nome)}</div>`).join("")}</div>
      <div class="linha"><button class="link" id="e-cancelar">cancelar</button></div>`;
    $$(".tipo").forEach((t) => t.onclick = () => {
      const c = TIPOS_NOME()[t.dataset.tipo];
      e.tipo = c.tipo;
      // só o que o efeito precisa para existir vem preenchido; o resto aparece como exemplo apagadinho
      for (const f of c.campos) if (OBRIGATORIOS.has(f.campo) && c.exemplo[f.campo] !== undefined) e[f.campo] = c.exemplo[f.campo];
      sujar(); desenharTimeline(); desenharForm();
    });
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
    const audio = { ...(ed.proj.audio || {}), dublagem: ed.dubs };
    if (!ed.dubs.length) delete audio.dublagem;
    await api("/api/dados", { p: atual, dados: { efeitos, mensagens, versoes, selo: $("#ed-selo").value,
      cta_antecipado: $("#ed-cta").value, fechamento: fech, sons: ed.sons.filter((x) => x.nome),
      sfx_automaticos: $("#tl-sfx-auto").checked, audio } });
    ed.efeitos = efeitos;
    sujar(false);
    if (pendentes) $("#ed-status").textContent = "Salvo (efeito sem tipo escolhido ficou de fora).";
    if (depois) rodar("previa"); else abrir(atual);
  } catch (err) { alert(err.message); }
}
$("#ed-salvar").onclick = () => salvarEditor(false);
$("#ed-salvar-previa").onclick = () => salvarEditor(true);
