// Painel do Divine Studio: fala com divine_studio/painel.py (mesma máquina).
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
let atual = null;          // nome do projeto aberto
let dados = null;          // detalhe do projeto
let jobAtivo = null;

async function api(caminho, corpo) {
  const r = await fetch(caminho, corpo === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo),
  });
  const j = await r.json();
  if (!r.ok) throw new Error(j.erro || r.statusText);
  return j;
}

function esc(t) {
  return String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

// markdown simples: títulos, tabelas, listas, negrito e código
function md(texto) {
  if (!texto) return '<p class="dica">Nada ainda.</p>';
  const linhas = texto.split("\n");
  let html = "", tabela = null, lista = false;
  const inline = (s) => esc(s).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
  const fechar = () => {
    if (tabela) { html += "<table>" + tabela.join("") + "</table>"; tabela = null; }
    if (lista) { html += "</ul>"; lista = false; }
  };
  for (const ln of linhas) {
    if (/^\|/.test(ln)) {
      if (/^\|[-| ]+\|$/.test(ln)) continue;
      const cel = ln.split("|").slice(1, -1).map((c) => `<td>${inline(c.trim())}</td>`).join("");
      (tabela = tabela || []).push(`<tr>${cel}</tr>`);
      continue;
    }
    if (/^\s*- /.test(ln)) {
      if (tabela) fechar();
      if (!lista) { html += "<ul>"; lista = true; }
      html += `<li>${inline(ln.replace(/^\s*- /, ""))}</li>`;
      continue;
    }
    fechar();
    const h = ln.match(/^(#+)\s+(.*)/);
    if (h) html += `<h3>${inline(h[2])}</h3>`;
    else if (ln.trim()) html += `<p>${inline(ln)}</p>`;
  }
  fechar();
  return html;
}

// ---------------------------------------------------------------- lista de projetos

async function carregarLista() {
  const lista = await api("/api/projetos");
  const filtro = $("#filtro").value.toLowerCase();
  $("#lista").innerHTML = lista
    .filter((p) => !filtro || (p.titulo + p.nome).toLowerCase().includes(filtro))
    .map((p) => `<li data-nome="${esc(p.nome)}" class="${p.nome === atual ? "ativo" : ""} ${p.pacote ? "peca" : ""}">
        <div class="t">${esc(p.titulo)}${p.aprovado ? '<span class="selo">aprovado</span>' : ""}</div>
        <div class="m">${esc(p.template)} · ${p.brutos} bruto(s) · ${p.previas} prévia(s) · ${p.finais} final(is)</div>
      </li>`).join("") || '<li class="m">Nenhum projeto ainda.</li>';
  $$("#lista li[data-nome]").forEach((li) => li.onclick = () => abrir(li.dataset.nome));
}

$("#filtro").oninput = carregarLista;

$("#form-novo").onsubmit = async (e) => {
  e.preventDefault();
  const nome = $("#novo-nome").value.trim();
  if (!nome) return;
  try {
    const r = await api("/api/novo", { nome });
    $("#novo-nome").value = "";
    await carregarLista();
    abrir(r.nome);
  } catch (err) { alert(err.message); }
};

// ---------------------------------------------------------------- projeto

async function abrir(nome) {
  atual = nome;
  history.replaceState(null, "", "#" + encodeURIComponent(nome));
  dados = await api("/api/projeto?p=" + encodeURIComponent(nome));
  $("#vazio").hidden = true;
  $("#projeto").hidden = false;
  $("#p-titulo").textContent = dados.titulo;
  $("#p-pasta").textContent = "projetos/" + dados.nome;
  $("#c-template").innerHTML = dados.templates.map((t) => `<option ${t === dados.template ? "selected" : ""}>${t}</option>`).join("");
  $("#c-formato").value = dados.formato;
  $("#c-autorizacao").value = dados.autorizacao_imagem;
  $("#yaml").value = dados.yaml;
  $("#yaml-erro").textContent = dados.erro_yaml;
  $("#brutos").innerHTML = dados.brutos.map((b) => `<li><span>${esc(b.nome)}</span>${b.no_projeto
      ? '<span class="no">no projeto</span>' : `<button class="link" data-clipe="${esc(b.nome)}">usar como clipe</button>`}</li>`).join("");
  $$("[data-clipe]").forEach((b) => b.onclick = () => usarClipe(b.dataset.clipe));
  $("#relatorio").innerHTML = md(dados.relatorio);
  $("#cortes").innerHTML = md(dados.cortes);
  $("#legenda").textContent = dados.legenda || "A legenda sai sozinha na primeira prévia (ou clique em Gerar).";
  desenharVideos();
  carregarLista();
  if (dados.job && !jobAtivo) acompanhar(dados.job, "tarefa em andamento");
}

async function trocarCampo(campo, valor) {
  try { await api("/api/campo", { p: atual, campo, valor }); abrir(atual); }
  catch (err) { alert(err.message); }
}
$("#c-template").onchange = (e) => trocarCampo("template", e.target.value);
$("#c-formato").onchange = (e) => trocarCampo("formato", e.target.value);
$("#c-autorizacao").onchange = (e) => trocarCampo("autorizacao_imagem", e.target.value);

$("#b-salvar").onclick = async () => {
  try {
    await api("/api/salvar", { p: atual, yaml: $("#yaml").value });
    $("#yaml-erro").textContent = "";
    abrir(atual);
  } catch (err) { $("#yaml-erro").textContent = err.message; }
};
document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "s" && atual) { e.preventDefault(); $("#b-salvar").click(); }
});

async function usarClipe(nome) {
  try { await api("/api/clipe", { p: atual, arquivo: nome }); abrir(atual); }
  catch (err) { alert(err.message); }
}

$("#b-hooks").onclick = async () => {
  const hs = await api("/api/hooks?n=3&tema=" + encodeURIComponent(dados.titulo));
  $("#hooks-sugeridos").innerHTML = hs.map((h) => `<div class="hook"><b>${esc(h.id)}</b> · ${esc(h.tipo)}<br>${
    esc(h.batidas.join("  →  ")).replace(/\*([^*]+)\*/g, "<b>$1</b>")}</div>`).join("") +
    '<p class="dica">Use no projeto.yaml: - {nome: V1, hook_id: ID} (ou hook: auto).</p>';
};

$("#form-regra").onsubmit = async (e) => {
  e.preventDefault();
  const texto = $("#regra").value.trim();
  if (!texto) return;
  try { await api("/api/regra", { texto }); $("#regra").value = ""; alert("Regra registrada para os próximos vídeos."); }
  catch (err) { alert(err.message); }
};

// ---------------------------------------------------------------- envio dos brutos

const zona = $("#soltar");
zona.onclick = () => $("#arquivos").click();
$("#arquivos").onchange = (e) => enviar([...e.target.files]);
["dragenter", "dragover"].forEach((ev) => zona.addEventListener(ev, (e) => { e.preventDefault(); zona.classList.add("sobre"); }));
["dragleave", "drop"].forEach((ev) => zona.addEventListener(ev, (e) => { e.preventDefault(); zona.classList.remove("sobre"); }));
zona.addEventListener("drop", (e) => enviar([...e.dataTransfer.files]));

async function enviar(arquivos) {
  for (const f of arquivos) {
    $("#envio").textContent = `Enviando ${f.name} (${(f.size / 1e6).toFixed(0)} MB)…`;
    const r = await fetch(`/api/upload?p=${encodeURIComponent(atual)}&nome=${encodeURIComponent(f.name)}`,
      { method: "POST", body: f });
    if (!r.ok) { const j = await r.json(); alert(`${f.name}: ${j.erro}`); }
  }
  $("#envio").textContent = arquivos.length ? `${arquivos.length} arquivo(s) enviados para bruto/.` : "";
  abrir(atual);
}

// ---------------------------------------------------------------- versões lado a lado

function notas() {
  const out = {};
  for (const m of (dados.relatorio || "").matchAll(/\*\*Nota viral (\S+):\*\* ([^\n]+)/g)) out[m[1]] = m[2];
  return out;
}

function desenharVideos() {
  const so = $("#so-previas").checked;
  const lista = dados.saidas.filter((s) => so || !s.previa).sort((a, b) => b.quando - a.quando);
  // uma por versão (a mais recente de cada tipo)
  const vistos = new Set();
  const ultimas = lista.filter((s) => { const k = s.versao + (s.previa ? "p" : "f"); if (vistos.has(k)) return false; vistos.add(k); return true; })
    .sort((a, b) => a.versao.localeCompare(b.versao) || a.previa - b.previa);
  const ns = notas();
  $("#n-versoes").textContent = ultimas.length ? `(${ultimas.length})` : "";
  $("#videos").innerHTML = ultimas.map((s) => `<div class="video" data-v="${esc(s.versao)}">
      <video src="/arquivo?p=${encodeURIComponent(atual)}&f=${encodeURIComponent(s.arquivo)}" controls playsinline preload="metadata" loop></video>
      <div class="rotulo"><span class="v">${esc(s.versao)} ${s.previa ? "· prévia" : "· final"}</span>
        <label class="check"><input type="checkbox" class="aprova" value="${esc(s.versao)}"> aprovar</label></div>
      <div class="nome">${esc(s.nome)} · ${s.mb} MB</div>
      ${ns[s.versao] ? `<div class="nota">${esc(ns[s.versao])}</div>` : ""}
    </div>`).join("") || '<p class="dica">Nenhuma versão ainda. Clique em "Gerar prévias".</p>';
  $$(".aprova").forEach((c) => c.onchange = () => c.closest(".video").classList.toggle("escolhido", c.checked));
  // tocar uma pausa as outras
  $$("#videos video").forEach((v) => v.onplay = () => $$("#videos video").forEach((o) => o !== v && o.pause()));
}
$("#so-previas").onchange = desenharVideos;

$("#b-aprovar").onclick = () => {
  const vs = [...new Set($$(".aprova:checked").map((c) => c.value))];
  if (!vs.length) return alert("Marque as versões aprovadas.");
  if (!confirm(`Exportar a versão final de ${vs.join(", ")} e registrar no índice?`)) return;
  rodar("final", vs);
};

// ---------------------------------------------------------------- abas e ações

$$(".abas button").forEach((b) => b.onclick = () => {
  $$(".abas button").forEach((x) => x.classList.toggle("ativa", x === b));
  $$(".aba").forEach((a) => a.hidden = a.id !== "aba-" + b.dataset.aba);
});

$$("[data-acao]").forEach((b) => b.onclick = () => rodar(b.dataset.acao));

$("#b-copiar").onclick = async () => {
  await navigator.clipboard.writeText($("#legenda").textContent);
  $("#b-copiar").textContent = "Copiado";
  setTimeout(() => $("#b-copiar").textContent = "Copiar", 1500);
};

const NOMES = { revisar: "Revisão de compliance", cortar: "Corte limpo", previa: "Gerando prévias", final: "Exportando a final",
  legenda: "Legenda do post", pacote: "Pacote por categorias", transcrever: "Transcrição" };

async function rodar(acao, versoes) {
  if (!atual) return;
  if ($("#yaml").value !== dados.yaml && !confirm("O projeto.yaml tem alterações não salvas. Rodar mesmo assim?")) return;
  try {
    const r = await api("/api/acao", { p: atual, acao, versoes });
    acompanhar(r.job, NOMES[acao] || acao);
  } catch (err) { alert(err.message); }
}

function acompanhar(job, titulo) {
  jobAtivo = job;
  $("#tarefa").hidden = false;
  $("#t-titulo").textContent = titulo;
  $$("[data-acao], #b-aprovar").forEach((b) => b.disabled = true);
  const tick = async () => {
    if (jobAtivo !== job) return;
    const e = await api("/api/job?id=" + job);
    $("#t-log").textContent = e.log;
    $("#t-log").scrollTop = 1e9;
    $("#t-tempo").innerHTML = e.estado === "rodando" ? `${e.segundos}s`
      : `<span class="estado-${e.estado}">${e.estado === "ok" ? "pronto" : "parou com erro"}</span> em ${e.segundos}s`;
    $("#t-barra").style.width = e.progresso ? `${Math.min(100, 100 * e.progresso[0] / e.progresso[1])}%` : (e.estado === "rodando" ? "8%" : "100%");
    if (e.estado === "rodando") setTimeout(tick, 1200);
    else {
      jobAtivo = null;
      $$("[data-acao], #b-aprovar").forEach((b) => b.disabled = false);
      if (atual) abrir(atual);
      if (e.estado === "ok" && (e.acao === "previa" || e.acao === "final")) $('[data-aba="versoes"]').click();
      if (e.estado === "ok" && (e.acao === "cortar" || e.acao === "legenda")) $('[data-aba="relatorio"]').click();
      if (e.estado === "ok" && ["revisar", "legenda", "cortar"].includes(e.acao)) setTimeout(() => { if (!jobAtivo) $("#tarefa").hidden = true; }, 6000);
    }
  };
  tick();
}
$("#t-fechar").onclick = () => { $("#tarefa").hidden = true; };

window.addEventListener("hashchange", () => {
  const h = decodeURIComponent(location.hash.slice(1));
  if (h && h !== atual) abrir(h).catch(() => {});
});

// ---------------------------------------------------------------- início
carregarLista().then(() => {
  const h = decodeURIComponent(location.hash.slice(1));
  if (h) abrir(h).catch(() => {});
});
