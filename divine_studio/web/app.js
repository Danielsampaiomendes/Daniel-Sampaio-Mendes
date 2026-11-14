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
  // agendar num dia em que o perfil (ou a collab) já tem post de feed: pergunta antes (config/identidade.yaml)
  if (r.status === 409 && j.conflito && caminho === "/api/publicacao" && corpo && !corpo.forcar) {
    if (confirm(j.erro)) return api(caminho, { ...corpo, forcar: true });
    throw new Error("Agendamento cancelado: escolha outro dia (no máximo 1 post de feed por dia por perfil).");
  }
  if (!r.ok) throw new Error(j.erro || r.statusText);
  return j;
}

const NO_IPHONE = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
if (NO_IPHONE) document.documentElement.classList.add("iphone");

// copiar texto: área de transferência moderna quando o Safari deixa (https); senão, o jeito clássico (funciona no iPhone)
async function copiar(texto) {
  texto = String(texto ?? "");
  try {
    if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(texto); return true; }
  } catch (e) { /* tenta o clássico */ }
  const ta = document.createElement("textarea");
  ta.value = texto; ta.setAttribute("readonly", ""); ta.style.cssText = "position:fixed;top:0;left:0;opacity:0;font-size:16px";
  document.body.appendChild(ta);
  const sel = document.getSelection(); const antes = sel && sel.rangeCount ? sel.getRangeAt(0) : null;
  ta.focus(); ta.select(); ta.setSelectionRange(0, texto.length);
  let ok = false;
  try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
  ta.remove(); if (antes && sel) { sel.removeAllRanges(); sel.addRange(antes); }
  if (!ok) throw new Error("não deu para copiar");
  return true;
}

// envio de arquivo com barra de progresso (vídeo do iPhone pode ter centenas de MB)
function enviarArquivo(projeto, f, aoProgresso) {
  return new Promise((ok, falha) => {
    const x = new XMLHttpRequest();
    x.open("POST", `/api/upload?p=${encodeURIComponent(projeto)}&nome=${encodeURIComponent(f.name)}`);
    x.upload.onprogress = (e) => { if (e.lengthComputable && aoProgresso) aoProgresso(e.loaded / e.total); };
    x.onload = () => {
      let j = {}; try { j = JSON.parse(x.responseText || "{}"); } catch (e) { /* sem corpo */ }
      if (x.status >= 200 && x.status < 300) ok(j); else falha(new Error(j.erro || `falha no envio (${x.status})`));
    };
    x.onerror = () => falha(new Error("o envio caiu. No iPhone, deixe a tela acesa e o Safari aberto até terminar."));
    x.send(f);
  });
}

// avisos discretos no canto (no lugar das janelas que travam a tela); toque para fechar
const _alertaNativo = window.alert.bind(window);
function aviso(msg, tipo = "") {
  let caixa = document.querySelector(".toasts");
  if (!caixa) { caixa = document.createElement("div"); caixa.className = "toasts"; document.body.appendChild(caixa); }
  const t = document.createElement("div");
  t.className = "toast " + tipo;
  t.textContent = String(msg);
  t.onclick = () => t.remove();
  caixa.appendChild(t);
  setTimeout(() => t.classList.add("sai"), Math.min(9000, 3500 + String(msg).length * 40));
  setTimeout(() => t.remove(), Math.min(9600, 4100 + String(msg).length * 40));
}
window.alert = (msg) => { try { aviso(msg, /erro|falh|não |nao |recus|precisa|bloque/i.test(String(msg)) ? "erro" : ""); } catch (e) { _alertaNativo(msg); } };

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

let tagFiltro = "", tipoFiltro = "";
const CATEGORIAS = { video: "Vídeos", stories: "Stories", carrossel: "Carrosséis", post: "Posts", tv: "TV", antes_depois: "Antes e depois" };
async function carregarLista() {
  const lista = await api("/api/projetos");
  window._listaProjetos = lista;
  const filtro = $("#filtro").value.toLowerCase();
  const todas = [...new Set(lista.flatMap((p) => p.tags))].sort();
  $("#filtro-tags").innerHTML = todas.map((t) => `<button class="chip ${t === tagFiltro ? "ativo" : ""}" data-tag="${esc(t)}">${esc(t)}</button>`).join("");
  $$("#filtro-tags .chip").forEach((c) => c.onclick = () => { tagFiltro = tagFiltro === c.dataset.tag ? "" : c.dataset.tag; carregarLista(); });
  const cats = Object.keys(CATEGORIAS).filter((c) => lista.some((p) => p.categoria === c));
  $("#filtro-tipo").innerHTML = cats.length > 1 ? cats.map((c) => `<button class="chip ${c === tipoFiltro ? "ativo" : ""}" data-cat="${c}">${CATEGORIAS[c]} <span>${lista.filter((p) => p.categoria === c).length}</span></button>`).join("") : "";
  $$("#filtro-tipo .chip").forEach((c) => c.onclick = () => { tipoFiltro = tipoFiltro === c.dataset.cat ? "" : c.dataset.cat; carregarLista(); });
  $("#tags-existentes").innerHTML = todas.map((t) => `<option value="${esc(t)}">`).join("");
  $("#lista").innerHTML = lista
    .filter((p) => !filtro || (p.titulo + p.nome + p.tags.join(" ")).toLowerCase().includes(filtro))
    .filter((p) => !tagFiltro || p.tags.includes(tagFiltro))
    .filter((p) => !tipoFiltro || p.categoria === tipoFiltro)
    .map((p) => `<li data-nome="${esc(p.nome)}" class="${p.nome === atual ? "ativo" : ""} ${p.pacote ? "peca" : ""}">
        <div class="t">${p.epico ? '<span class="epico">✦</span> ' : ""}${esc(p.titulo)}${p.conta && p.conta !== "dvmedicalspa" ? ` <span class="perfil">@${esc(p.conta)}</span>` : ""}${p.aprovado ? '<span class="selo">aprovado</span>' : ""}</div>
        <div class="m">${({ carrossel: "carrossel", post: "post", antes_depois: "antes e depois · uso interno", stories: "stories · " + esc(p.template), tv: "TV" })[p.categoria] || esc(p.template)} · ${p.brutos} bruto(s) · ${p.previas} prévia(s) · ${p.finais} final(is)</div>
        ${p.tags.length ? `<div>${p.tags.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>` : ""}
        <button class="lixo" data-excluir title="Excluir (vai para a Lixeira do Mac)">🗑</button>
      </li>`).join("") || '<li class="m">Nenhum projeto ainda.</li>';
  $$("#lista li[data-nome]").forEach((li) => li.onclick = () => abrir(li.dataset.nome));
  $$("#lista [data-excluir]").forEach((b) => b.onclick = (e) => { e.stopPropagation(); excluirProjeto(b.closest("li").dataset.nome); });
}

$("#filtro").oninput = carregarLista;


// ---------------------------------------------------------------- projeto

async function abrir(nome) {
  atual = nome;
  history.replaceState(null, "", "#" + encodeURIComponent(nome));
  dados = await api("/api/projeto?p=" + encodeURIComponent(nome));
  $("#vazio").hidden = true; $("#escolha").hidden = true;
  $$(".tela").forEach((s) => s.hidden = true);
  document.body.classList.add("com-lista", "projeto-aberto");
  $$(".topo nav button").forEach((b) => b.classList.toggle("ativa", b.dataset.tela === "projetos"));
  $("#antesdepois").hidden = true;
  if (dados.tipo === "carrossel" || dados.tipo === "post") {   // carrossel e post têm tela própria (carrossel.js)
    $("#projeto").hidden = true; $("#carrossel").hidden = false;
    carregarLista();
    return abrirCarrossel(dados);
  }
  if (dados.tipo === "antes_depois") {                         // biblioteca.js
    $("#projeto").hidden = true; $("#carrossel").hidden = true; $("#antesdepois").hidden = false;
    carregarLista();
    return abrirAntesDepois(dados);
  }
  $("#carrossel").hidden = true;
  if (window.pedidosHtml) $("#p-pedidos").innerHTML = pedidosHtml(dados.pedidos_imagem);
  if ((dados.tags || []).includes("vídeo longo")) {
    $("#p-pedidos").insertAdjacentHTML("afterbegin", `<div class="cartao destaque-longo"><b>✂ Vídeo longo</b>
      <span>${dados.brutos.length ? "Pronto: gere os cortes curtos, médios, longos, melhores momentos e Stories." : "Solte o vídeo longo em Vídeos brutos (aba Projeto) e depois gere os cortes."}</span>
      ${dados.brutos.length ? '<button class="dourado" id="b-cortes">Gerar cortes</button>' : ""}</div>`);
    if ($("#b-cortes")) $("#b-cortes").onclick = () => rodar("cortes");
  }
  $("#projeto").hidden = false;
  desenharPassos();
  $("#p-titulo").textContent = dados.titulo;
  $("#p-pasta").textContent = "projetos/" + dados.nome + (dados.corte ? ` · trecho ${dados.corte.de} a ${dados.corte.ate} (${Math.round(dados.corte.duracao_s)} s)` : "");
  $("#c-template").innerHTML = dados.templates.map((t) => `<option ${t === dados.template ? "selected" : ""}>${t}</option>`).join("");
  $("#c-formato").value = dados.formato;
  $("#c-autorizacao").value = dados.autorizacao_imagem;
  $("#c-tags").value = (dados.tags || []).join(", ");
  $("#c-objetivo").value = dados.objetivo || "";
  $("#anuncio-cartao").hidden = !dados.anuncio;
  if (dados.anuncio) {
    const an = dados.anuncio;
    $("#an-objetivo").innerHTML = Object.entries(an.objetivos).map(([k, n]) => `<option value="${k}" ${k === an.objetivo ? "selected" : ""}>${esc(n)}</option>`).join("");
    $("#an-servico").value = an.servico || ""; $("#an-dor").value = an.dor || ""; $("#an-beneficio").value = an.beneficio || "";
    $("#an-copy").innerHTML = (an.erros.length ? `<p class="aviso-ia">${an.erros.map(esc).join("<br>")}</p>` : "") +
      an.copy.map((v, k) => `<details class="an-var" ${k ? "" : "open"}><summary>Variação ${v.variacao} · ${esc(v.titulo)}</summary>
        <pre class="legenda">${esc(v.texto_principal)}</pre><p><b>Título:</b> ${esc(v.titulo)} · <b>Descrição:</b> ${esc(v.descricao)} · <b>Botão:</b> ${esc(v.botao)}</p>
        <button data-copiar="${k}">Copiar texto principal</button></details>`).join("");
    $$("[data-copiar]").forEach((b) => b.onclick = async () => {
      const t = an.copy[+b.dataset.copiar].texto_principal;
      try { await copiar(t); b.textContent = "Copiado ✓"; } catch (e) { prompt("Copie:", t); }
    });
  }
  $("#react-cartao").hidden = !dados.react;
  if (dados.react) {
    $("#react-layout").value = dados.react.layout || "auto";
    $("#react-credito").value = dados.react.credito || "";
    $("#react-refs").innerHTML = dados.react.referencias.length ? "Vídeo analisado: <b>" + dados.react.referencias.map((r) => esc(r.split("/").pop())).join(", ") + "</b>" : "Ainda sem o vídeo analisado.";
  }
  $("#c-conta").innerHTML = `<option value="">Automático pelo template (@${esc(dados.conta || "nenhum")})</option>` +
    Object.entries(dados.perfis || {}).map(([u, n]) => `<option value="${esc(u)}" ${dados.conta_definida === u ? "selected" : ""}>@${esc(u)} · ${esc(n)}</option>`).join("");
  $("#c-ritmo").value = dados.epico ? "epico" : (dados.ritmo || "viral");
  $("#c-estilo-edicao").innerHTML = (dados.estilos_edicao || []).map((e) =>
    `<option value="${esc(e.chave)}" ${e.chave === dados.estilo_edicao ? "selected" : ""}>${esc(e.nome)}</option>`).join("");
  const infoEstilo = () => {
    const e = (dados.estilos_edicao || []).find((x) => x.chave === $("#c-estilo-edicao").value);
    $("#c-estilo-info").textContent = e ? e.descricao : "";
  };
  infoEstilo();
  $("#c-estilo-edicao").onchange = (ev) => {
    infoEstilo();
    api("/api/dados", { p: atual, dados: { estilo_edicao: ev.target.value } })
      .then(() => aviso("Estilo trocado. Gere o storyboard para ver os quadros."))
      .catch((err) => alert(err.message));
  };
  $("#c-qualidade").checked = !!dados.qualidade;
  $("#c-qualidade-info").textContent = dados.qualidade_info || "";
  $$(".formatos input").forEach((c) => c.checked = (dados.formatos || []).includes(c.value) && c.value !== dados.formato);
  $$(".formatos input").forEach((c) => c.disabled = c.value === dados.formato);
  $("#yaml").value = dados.yaml;
  $("#yaml-erro").textContent = dados.erro_yaml;
  desenharBrutos();
  $("#relatorio").innerHTML = md(dados.relatorio);
  $("#cortes").innerHTML = md(dados.cortes);
  $("#legenda").textContent = dados.legenda || "A legenda sai sozinha na primeira prévia (ou clique em Gerar).";
  desenharVideos();
  carregarLista();
  if (typeof carregarEditor === "function") carregarEditor().catch((e) => console.error(e));
  if (dados.job && !jobAtivo) acompanhar(dados.job, "tarefa em andamento");
}

async function trocarCampo(campo, valor) {
  try { await api("/api/campo", { p: atual, campo, valor }); abrir(atual); }
  catch (err) { alert(err.message); }
}
$("#c-template").onchange = (e) => trocarCampo("template", e.target.value);
$("#c-formato").onchange = (e) => trocarCampo("formato", e.target.value);
$("#c-autorizacao").onchange = (e) => trocarCampo("autorizacao_imagem", e.target.value);
$("#c-objetivo").onchange = async (e) => {
  try { await api("/api/dados", { p: atual, dados: { objetivo: e.target.value } }); abrir(atual); } catch (err) { alert(err.message); }
};
$("#c-tags").onchange = async (e) => {
  const tags = [...new Set(e.target.value.split(",").map((t) => t.trim().toLowerCase()).filter(Boolean))];
  try { await api("/api/dados", { p: atual, dados: { tags } }); abrir(atual); } catch (err) { alert(err.message); }
};
$("#c-conta").onchange = (e) => api("/api/dados", { p: atual, dados: { conta: e.target.value || null } }).then(() => carregarLista()).catch((err) => alert(err.message));
$("#c-ritmo").onchange = (e) => api("/api/dados", { p: atual, dados: { ritmo: e.target.value, epico: null } }).catch((err) => alert(err.message));
$("#c-qualidade").onchange = (e) => api("/api/dados", { p: atual, dados: { qualidade: e.target.checked ? "maxima" : null } }).catch((err) => alert(err.message));
$$(".formatos input").forEach((c) => c.onchange = async () => {
  const formatos = $$(".formatos input").filter((x) => x.checked).map((x) => x.value);
  try { await api("/api/dados", { p: atual, dados: { formatos } }); } catch (err) { alert(err.message); }
});

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

// ---------------------------------------------------------------- vídeos brutos: assistir, usar, tirar, descartar
function desenharBrutos() {
  const seg = (d) => d ? `${Math.floor(d / 60)}:${String(Math.round(d % 60)).padStart(2, "0")}` : "";
  $("#brutos").innerHTML = dados.brutos.map((b) => `<li class="bruto ${b.fora ? "fora" : ""}" data-nome="${esc(b.nome)}">
      <video preload="metadata" controls playsinline src="/arquivo?p=${encodeURIComponent(atual)}&f=${encodeURIComponent("bruto/" + b.nome)}#t=0.5"></video>
      <div class="bruto-info"><b title="${esc(b.nome)}">${esc(b.nome)}</b><span class="dica">${seg(b.duracao)}</span>
        <span class="estado ${b.fora ? "fora" : "dentro"}">${b.fora ? "fora da edição" : "na edição"}</span></div>
      <div class="bruto-acoes">${b.fora ? '<button data-b="usar" class="dourado">✓ Usar na edição</button>'
        : '<button data-b="tirar">Tirar da edição</button>'}<button class="link" data-b="descartar">descartar</button></div></li>`).join("");
  $$("#brutos [data-b]").forEach((bt) => bt.onclick = async () => {
    const nome = bt.closest("[data-nome]").dataset.nome, acao = bt.dataset.b;
    if (acao === "descartar" && !confirm(`Descartar ${nome}?\nEle vai para a pasta _arquivo do projeto (nada é apagado).`)) return;
    try { const r = await api("/api/bruto", { p: atual, nome, acao }); aviso(r.msg); abrir(atual); }
    catch (err) { aviso(err.message, "erro"); }
  });
  desenharProximoPasso();
}

// o que fazer agora (guia passo a passo do projeto)
function desenharProximoPasso() {
  const caixa = $("#proximo-passo"); if (!caixa) return;
  const dentro = dados.brutos.filter((b) => !b.fora).length;
  const previas = dados.saidas.filter((s) => s.previa).length, finais = dados.saidas.filter((s) => !s.previa).length;
  let h;
  const ef = dados.entende_fala || {};
  const alertaFala = ef.transcricao ? "" : (ef.precisa_reiniciar
      ? `<div class="pp-alerta">✓ A transcrição já está instalada no Python novo do app. Falta só reabrir o painel nele.
          <div class="pp-linha"><button class="dourado" id="pp-reiniciar">↻ Reabrir o painel agora</button></div></div>`
      : `<div class="pp-alerta">⚠ <b>O app ainda não entende a sua fala</b> (falta a transcrição), então a edição sai com textos genéricos.
          <div class="pp-linha"><button class="dourado" id="pp-instalar">⬇ Instalar a transcrição agora</button>
          <span class="dica">Uma vez só: 2 a 5 minutos, precisa de internet. O painel reabre sozinho no fim.${previas || finais ? " Depois, toque em ✦ Edição automática de novo." : ""}</span></div></div>`);
  if (!dados.brutos.length) {
    h = `<b>1. Solte os vídeos brutos</b> no quadro acima (ou clique nele para escolher). Pode soltar vários de uma vez.`;
  } else if (!previas && !finais) {
    const alerta = alertaFala ? "" : !ef.ia ? `<div class="dica so-avancado">A fala é transcrita e vira legenda, ganchos e mensagens. Para o Claude escrever as 3 versões
        (como no chat), ligue a IA com a chave da API (Ideias e IA) ou use o botão <b>Pedir a edição ao Claude</b> abaixo.</div>` : "";
    h = (dados.job || jobAtivo) ? `<div class="pp-rodando"><span class="giro"></span><div><b>Editando o seu vídeo…</b><br>
        <span class="dica">O app está transcrevendo a fala, cortando as pausas, escrevendo os textos e gerando as versões. Leva alguns minutos;
        pode sair desta tela, o aviso chega quando ficar pronto.</span></div></div>`
      : alerta + `<div><b>2. Crie a edição</b> <span class="dica">${dentro} vídeo(s) vão entrar. Quer deixar algum de fora? Toque em <i>Tirar da edição</i> no cartão do vídeo, mais abaixo.</span></div>
      <div class="pp-linha"><button class="dourado" id="pp-auto">✦ Criar edição automática</button>
        <label class="check"><input type="checkbox" id="pp-epico" ${dados.epico ? "checked" : ""}> ✦ Vídeo Épico (mais intenso)</label></div>
      <div class="dica">O app transcreve a sua fala, corta, escreve hooks e textos sobre o que você falou, põe legenda, efeitos e som e gera as versões.</div>
      <div class="so-avancado"><button id="pp-claude">✦ Pedir a edição ao Claude (como no chat)</button></div>`;
  } else if (!finais) {
    const barrada = (v) => ((dados.publicacoes || []).find((p) => p.versao === v) || {}).aprovacao_barrada || "";
    h = `<b>3. Assista e aprove a melhor</b> <span class="dica">Um toque em <i>Aprovar esta</i>: o app exporta a final e aprende o que você gostou.
      Quer mudar algo antes? Aba <a href="#" data-aba-link="edicao">Ajustar</a> (textos, legenda, efeitos).</span>
      ${dados.autorizacao_imagem === "pendente" ? `<div class="pp-linha"><b>Quem aparece no vídeo?</b>
        <select id="pp-autoriz"><option value="">escolha…</option><option value="proprio">Só a equipe Divine (Dr. Daniel, George, eu)</option>
        <option value="sim">Paciente, com autorização assinada</option><option value="nao_aparece">Ninguém aparece</option></select>
        <span class="dica">(compliance: sem isso a final sai marcada "autorização pendente")</span></div>` : ""}
      <div class="pp-versoes">${ultimasPrevias().map((s) => `<div class="pp-v" data-v="${esc(s.versao)}" data-arq="${esc(s.arquivo)}">
        <video src="/arquivo?p=${encodeURIComponent(atual)}&f=${encodeURIComponent(s.arquivo)}#t=1" controls playsinline preload="metadata"></video>
        <b>${esc(s.versao)}${s.versao === "IA" ? " · a aposta do app (tenta superar as outras)" : ""}</b>
        <div class="pp-prev" data-prev="${esc(s.versao)}"></div>
        <div class="pp-alertas" data-pontos="${esc(s.versao)}" hidden></div>
        <details class="pp-marca" data-marca="${esc(s.versao)}" hidden></details>
        ${barrada(s.versao) ? `<div class="pp-barrada">A final da ${esc(s.versao)} não saiu: o revisor achou ${esc(barrada(s.versao))}. Ela não contou como aprovada. Resolva o ! e aprove de novo.</div>` : ""}
        <button class="dourado" data-aprovar>✓ Aprovar esta</button></div>`).join("")}</div>
      ${ef.transcricao && ef.preciso === false ? `<div class="pp-linha dica">A fala foi transcrita com o modelo rápido.
        <button id="pp-fala-precisa">🎯 Transcrição mais precisa</button> baixa 1,6 GB uma vez (5 a 20 min, Mac ligado); vale para os próximos vídeos.</div>` : ""}`;
    setTimeout(carregarPontos, 0);
  } else {
    const fin = dados.saidas.filter((s) => !s.previa).sort((a, b) => b.quando - a.quando)[0];
    const pub = (dados.publicacoes || []).find((p) => p.versao === fin.versao) || {};
    h = `<b>4. Postar</b> <span class="dica">${pub.status === "postado" ? "Postado ✓" : "A final está pronta. Baixe, copie a legenda e poste."}</span>
      <div class="pp-postar"><video src="/arquivo?p=${encodeURIComponent(atual)}&f=${encodeURIComponent(fin.arquivo)}#t=1" controls playsinline preload="metadata"></video>
        <div class="pp-postar-acoes">
          <button class="dourado" id="pp-baixar">⤓ Baixar o vídeo ${esc(fin.versao)}</button>
          <button id="pp-legenda">📋 Copiar a legenda do post</button>
          <button id="pp-postei">${pub.status === "postado" ? "✓ Postado" : "✓ Já postei"}</button>
          <button class="link" id="pp-outra">aprovar outra versão</button>
        </div></div>
      <div class="pp-sug" id="pp-sug"><b>💡 Para a próxima ficar ainda melhor</b><span class="dica"> carregando…</span></div>`;
    setTimeout(() => carregarSugestoes(fin), 0);
  }
  caixa.innerHTML = (dados.job || jobAtivo ? "" : alertaFala) + h;
  const az = $("#pp-autoriz");
  if (az) az.onchange = async () => {
    if (!az.value) return;
    try { await api("/api/campo", { p: atual, campo: "autorizacao_imagem", valor: az.value }); dados.autorizacao_imagem = az.value; aviso("Anotado."); }
    catch (err) { aviso(err.message, "erro"); }
  };
  $$("#proximo-passo [data-aprovar]").forEach((b) => b.onclick = async () => {
    if ($("#pp-autoriz") && !$("#pp-autoriz").value && !confirm("Você não disse quem aparece no vídeo: a final vai sair marcada como \"autorização pendente\". Continuar?")) return;
    const c = b.closest(".pp-v");
    try {
      const r = await api("/api/aprovar", { p: atual, versao: c.dataset.v, arquivo: c.dataset.arq });
      aviso(`${c.dataset.v}: exportando a final. Assim que ela passar pelo revisor, conta como aprovada e o app aprende o que você gostou.`);
      acompanhar(r.job, "Exportando a final");
    } catch (err) { aviso(err.message, "erro"); }
  });
  $$("#proximo-passo video").forEach((v) => v.onplay = () => $$("#proximo-passo video").forEach((o) => o !== v && o.pause()));
  if ($("#pp-baixar")) {
    const fin = dados.saidas.filter((s) => !s.previa).sort((a, b) => b.quando - a.quando)[0];
    // baixar para postar é uma saída da final como o Publicar: a fala dela é lida uma vez antes (telas.js > leuAFala)
    $("#pp-baixar").onclick = async () => { if (!(await leuAFala(atual, fin.versao, "salvar"))) return;
      salvarNaGaleria(`/arquivo?p=${encodeURIComponent(atual)}&f=${encodeURIComponent(fin.arquivo)}`, fin.arquivo.split("/").pop()); };
    $("#pp-legenda").onclick = async () => {
      const t = dados.legenda || "";
      if (!t) return aviso("A legenda do post ainda não foi gerada.", "erro");
      try { await copiar(t); aviso("Legenda copiada: cole no Instagram."); } catch (e) { prompt("Copie a legenda:", t); }
    };
    $("#pp-postei").onclick = async () => {
      const link = prompt("Link do post (opcional, ajuda o app a aprender com as visualizações):", "");
      if (link === null) return;
      await marcarPub(fin.versao, { status: "postado", link: link || undefined, rede: "instagram" }, fin.arquivo);
      aviso("Marcado como postado."); abrir(atual);
    };
    $("#pp-outra").onclick = () => $('[data-aba="versoes"]').click();
  }
  const ep = $("#pp-epico");
  if (ep) ep.onchange = () => api("/api/dados", { p: atual, dados: { ritmo: ep.checked ? "epico" : "viral", epico: null } })
    .then(() => { dados.epico = ep.checked; aviso(ep.checked ? "Vídeo Épico ligado" : "Padrão viral luxo"); });
  const au = $("#pp-auto"); if (au) au.onclick = () => rodar("auto");
  const pi = $("#pp-instalar"); if (pi) pi.onclick = () => {
    pi.closest(".pp-alerta").innerHTML = `<div class="pp-rodando"><span class="giro"></span><div><b>Instalando a transcrição…</b><br>
      <span class="dica">2 a 5 minutos. Deixe o Mac ligado; o painel reabre sozinho quando terminar. Só depois crie a edição.</span></div></div>`;
    const au2 = $("#pp-auto"); if (au2) au2.disabled = true;
    if (!previas && !finais) { try { localStorage.setItem("ds_auto_depois", atual); } catch (e) { /* segue */ } }
    rodar("instalar_fala");
  };
  const pr = $("#pp-reiniciar"); if (pr) pr.onclick = () => reabrirPainel();
  const fp = $("#pp-fala-precisa"); if (fp) fp.onclick = () => { fp.disabled = true; rodar("fala_precisa"); };
  const pc = $("#pp-claude"); if (pc) pc.onclick = async () => {
    const t = `Edite o vídeo do projeto projetos/${atual} do Divine Studio, do mesmo jeito que você edita aqui no chat.
1. Leia o CLAUDE.md e as skills divine-* (vídeo, sequência de gravação, modelos de Reels).
2. Transcreva os brutos: python3 -m divine_studio transcrever projetos/${atual}
3. Escreva o projeto.yaml com 3 versões que tenham tudo a ver com a fala: hooks tirados do que eu falo, mensagens com na_fala,
   efeitos com na_fala só onde reforçam a fala, legenda do post, corte_limpo e legendas ligados. Compliance CFM/Anvisa.
4. Rode o storyboard (python3 -m divine_studio storyboard projetos/${atual}) e me mostre os quadros para eu aprovar.`;
    try { await copiar(t); aviso("Copiado: cole no Claude (app do Mac ou Cowork) com a pasta do Divine Studio liberada."); }
    catch (e) { prompt("Copie e cole no Claude:", t); }
  };
  $$("#proximo-passo [data-aba-link]").forEach((a) => a.onclick = (e) => { e.preventDefault(); $(`[data-aba="${a.dataset.abaLink}"]`).click(); });
}

function ultimasPrevias() {
  const vistos = new Set();
  return dados.saidas.filter((s) => s.previa).sort((a, b) => b.quando - a.quando)
    .filter((s) => (vistos.has(s.versao) ? false : vistos.add(s.versao)))
    .sort((a, b) => (a.versao === "IA") - (b.versao === "IA") || a.versao.localeCompare(b.versao));
}

// passo 3: os pontos "!" e a previsão de público de CADA versão, para escolher e corrigir antes de aprovar
async function carregarPontos() {
  const cards = $$("[data-pontos]");
  const [pv, ...als] = await Promise.all([
    api("/api/previsao?p=" + encodeURIComponent(atual)).catch(() => ({})),
    ...cards.map((c) => api(`/api/alertas?p=${encodeURIComponent(atual)}&v=${encodeURIComponent(c.dataset.pontos)}`).catch(() => null)),
  ]);
  // checklist do algoritmo e da identidade visual de cada versão (config/identidade.yaml)
  $$("[data-marca]").forEach(async (el) => {
    let c; try { c = await api(`/api/identidade?p=${encodeURIComponent(atual)}&v=${encodeURIComponent(el.dataset.marca)}`); } catch (e) { return; }
    const falhas = c.itens.filter((i) => i.ok === false);
    el.hidden = false;
    el.innerHTML = `<summary>${falhas.length ? "◇" : "✓"} Padrão Divine: ${c.ok} de ${c.total}${falhas.length ? ` · ${falhas.length} para ajustar` : ""}</summary>
      <ul>${falhas.map((i) => `<li><b>${esc(i.titulo)}</b><br><small>${esc(i.detalhe)}</small></li>`).join("") || "<li>Tudo no padrão.</li>"}</ul>`;
  });
  $$("[data-prev]").forEach((el) => {
    const x = pv[el.dataset.prev]; if (!x || !x.frase) { el.textContent = ""; return; }
    const saem = (x.saidas || []).map((q) => `${q.t.toFixed(0)} s (${q.motivo})`).join(" · ");
    const quem = (x.personas || []).map((q) => `${q.nome}: cerca de ${q.fim} em 100`).join(" · ");
    el.innerHTML = `👥 ${esc(x.frase)}${saem ? `<br><small>Onde mais saem: ${esc(saem)}</small>` : ""}${quem ? `<br><small>Estimativa por público, até o fim: ${esc(quem)}</small>` : ""}`;
  });
  cards.forEach((box, i) => {
    const al = als[i]; if (!al || !al.pontos.length) return;
    const nomes = al.niveis || {};
    const travam = al.pontos.filter((p) => p.nivel === "bloqueia" || p.nivel === "confirmar").length;
    box.hidden = false;
    box.innerHTML = `<b>${al.pontos.length} ponto(s) "!" na ${esc(al.versao)}</b>${travam ? ` <span class="trava">· ${travam} de compliance (travam o Aprovar)</span>` : ""}
      <ul>${al.pontos.slice(0, 3).map((p) => `<li><span class="i n-${esc(p.nivel)}">!</span><b>${p.t0.toFixed(0)} s · ${esc(p.titulo)}</b>
        <span class="dica"> ${esc((nomes[p.nivel] || {}).nome || "")}</span></li>`).join("")}</ul>
      <a href="#" class="link" data-ir-ajustar="${esc(al.versao)}">Resolver na linha do tempo da ${esc(al.versao)} ›</a>`;
  });
  $$("[data-ir-ajustar]").forEach((a) => a.onclick = (e) => {
    e.preventDefault(); window.versaoAjustar = a.dataset.irAjustar;
    const aba = $('[data-aba="edicao"]'); if (aba) aba.click();
    if (typeof carregarEditor === "function") carregarEditor().catch((err) => console.error(err));   // já aberto: troca a versão
  });
}

async function carregarSugestoes(fin) {
  const box = $("#pp-sug"); if (!box) return;
  let r = { sugestoes: [] };
  try { r = await api("/api/sugestoes?p=" + encodeURIComponent(atual)); } catch (e) { /* segue */ }
  const item = (s) => `<li class="sug-${esc(s.tipo)}"><b>${esc(s.titulo)}</b>${s.fonte ? ` <small>(${esc(s.fonte)})</small>` : ""}<br><span>${esc(s.texto)}</span></li>`;
  box.innerHTML = `<b>💡 Para a próxima ficar ainda melhor</b>
    <ul class="sug-lista">${r.sugestoes.map(item).join("") || "<li>Nada importante a mudar: a fala e a edição estão no padrão. Siga gravando!</li>"}</ul>
    <div class="linha"><button id="sug-ia">✦ Pedir mais ideias ao Claude</button>
      <button id="sug-hf" title="O Virality Predictor do Higgsfield lê o vídeo e prevê gancho, retenção e risco de queda">🔮 Análise de viralidade (Higgsfield)</button></div>`;
  $("#sug-ia").onclick = async () => {
    $("#sug-ia").disabled = true; $("#sug-ia").textContent = "Pensando…";
    try {
      const x = await api("/api/sugestoes/ia", { p: atual });
      box.querySelector(".sug-lista").insertAdjacentHTML("beforeend", x.sugestoes.map(item).join(""));
      $("#sug-ia").textContent = "✓ Ideias do Claude na lista";
    } catch (err) { aviso(err.message, "erro"); $("#sug-ia").disabled = false; $("#sug-ia").textContent = "✦ Pedir mais ideias ao Claude"; }
  };
  $("#sug-hf").onclick = async () => {
    try {
      const x = await api("/api/sugestoes/higgsfield", { p: atual, arquivo: fin.arquivo });
      try { await copiar(x.instrucao); } catch (e) { prompt("Copie e cole no Claude:", x.instrucao); }
      aviso("Pedido copiado: cole no Claude (com o Higgsfield conectado). A leitura volta para cá como sugestão.");
    } catch (err) { aviso(err.message, "erro"); }
  };
}

// ---------------------------------------------------------------- envio dos brutos

const zona = $("#soltar");
zona.onclick = () => $("#arquivos").click();
$("#arquivos").onchange = (e) => enviar([...e.target.files]);
["dragenter", "dragover"].forEach((ev) => zona.addEventListener(ev, (e) => { e.preventDefault(); zona.classList.add("sobre"); }));
["dragleave", "drop"].forEach((ev) => zona.addEventListener(ev, (e) => { e.preventDefault(); zona.classList.remove("sobre"); }));
zona.addEventListener("drop", (e) => enviar([...e.dataTransfer.files]));

async function enviar(arquivos) {
  for (const f of arquivos) {
    const mb = (f.size / 1e6).toFixed(0);
    try {
      await enviarArquivo(atual, f, (x) => { $("#envio").textContent = `Enviando ${f.name}: ${Math.round(x * 100)}% de ${mb} MB${NO_IPHONE ? " · deixe a tela acesa" : ""}`; });
    } catch (err) { alert(`${f.name}: ${err.message}`); }
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
  const pubs = Object.fromEntries((dados.publicacoes || []).map((p) => [p.versao, p]));
  $("#n-versoes").textContent = ultimas.length ? `(${ultimas.length})` : "";
  $("#videos").innerHTML = ultimas.map((s) => { const pub = pubs[s.versao] || {}; return `<div class="video ${s.versao === "IA" ? "ia" : ""}" data-v="${esc(s.versao)}" data-arq="${esc(s.arquivo)}">
      ${s.versao === "IA" ? '<div class="selo-ia">✦ versão IA: a que o app acredita ser a melhor</div>' : ""}
      <video src="/arquivo?p=${encodeURIComponent(atual)}&f=${encodeURIComponent(s.arquivo)}" controls playsinline preload="metadata" loop></video>
      <div class="rotulo"><span class="v">${esc(s.versao)} ${s.previa ? "· prévia" : "· final"}</span>
        <label class="check"><input type="checkbox" class="aprova" value="${esc(s.versao)}"> aprovar</label></div>
      <div class="nome">${esc(s.nome)} · ${s.mb} MB</div>
      ${ns[s.versao] ? `<div class="nota">${esc(ns[s.versao])}</div>` : ""}
      <div class="pub">
        <button class="pb conversa ${pub.feedback ? "on" : ""}" data-pub="conversa" title="O que o app acha e o que você acha desta versão">💬 ${pub.feedback ? "Sua opinião" : "Conversar"}</button>
        <button class="pb ${pub.validado ? "on" : ""}" data-pub="validar" title="Validar: entra na Galeria (dá para editar depois)">★ ${pub.validado ? "Na galeria" : "Validar"}</button>
        <button class="pb ${pub.gostei ? "on" : ""}" data-pub="gostei" title="Gostei: o app aprende com isso">♥ Gostei</button>
        <button class="pb ${pub.status === "postado" ? "on" : ""}" data-pub="postei" title="Marcar como postado">✓ Postei</button>
        <button class="pb ${pub.status === "agendado" ? "on" : ""}" data-pub="agendar" title="Agendar postagem">📅 ${pub.data_agendada ? esc(pub.data_agendada.slice(5).split("-").reverse().join("/")) : "Agendar"}</button>
        <button class="pb" data-pub="salvar" title="Salvar na galeria / compartilhar">⤓ Salvar</button>
      </div>
      ${pub.status ? `<div class="status st-${esc(pub.status)}">${esc(pub.status)}${pub.link ? ` · <a href="${esc(pub.link)}" target="_blank">ver post</a>` : ""}</div>` : ""}
    </div>`; }).join("") || '<p class="dica">Nenhuma versão ainda. Clique em "Gerar prévias".</p>';
  $$("#videos .pb").forEach((b) => b.onclick = () => acaoPublicacao(b.closest(".video"), b.dataset.pub));
  $$(".aprova").forEach((c) => c.onchange = () => c.closest(".video").classList.toggle("escolhido", c.checked));
  // tocar uma pausa as outras
  $$("#videos video").forEach((v) => v.onplay = () => $$("#videos video").forEach((o) => o !== v && o.pause()));
}
$("#so-previas").onchange = desenharVideos;

async function marcarPub(versao, campos, arquivo) {
  await api("/api/publicacao", { p: atual, versao, campos, arquivo });
}

async function acaoPublicacao(card, acao) {
  const versao = card.dataset.v, arq = card.dataset.arq;
  const pub = (dados.publicacoes || []).find((p) => p.versao === versao) || {};
  try {
    if (acao === "gostei") await marcarPub(versao, { gostei: !pub.gostei }, arq);
    else if (acao === "conversa") return abrirConversa(versao);
    else if (acao === "validar") await marcarPub(versao, pub.validado ? { validado: null } : { validado: true, gostei: true }, arq);
    else if (acao === "postei") {
      const link = prompt("Link do post (opcional, ajuda a puxar as métricas depois):", pub.link || "");
      if (link === null) return;
      await marcarPub(versao, { status: "postado", link: link || undefined, rede: dados.formato === "tv" ? "tv" : "instagram" }, arq);
    } else if (acao === "agendar") {
      const d = prompt("Data da postagem (DD/MM, ou DD/MM/AAAA):", pub.data_agendada ? pub.data_agendada.split("-").reverse().join("/") : "");
      if (!d) return;
      const [dia, mes, ano] = d.split("/");
      const iso = `${ano || new Date().getFullYear()}-${mes.padStart(2, "0")}-${dia.padStart(2, "0")}`;
      await marcarPub(versao, { status: "agendado", data_agendada: iso }, arq);
    } else if (acao === "salvar") {
      if (!(await leuAFala(atual, versao, "salvar"))) return;
      return salvarNaGaleria(`/arquivo?p=${encodeURIComponent(atual)}&f=${encodeURIComponent(arq)}`, arq.split("/").pop());
    }
    abrir(atual);
  } catch (err) { alert(err.message); }
}

// iPhone: abre a folha de compartilhar (Salvar vídeo / Salvar imagem); Mac: baixa o arquivo
async function salvarNaGaleria(url, nome) {
  try {
    if (navigator.canShare) {
      const blob = await (await fetch(url)).blob();
      const arquivo = new File([blob], nome, { type: blob.type });
      if (navigator.canShare({ files: [arquivo] })) return await navigator.share({ files: [arquivo], title: nome });
    }
  } catch (e) { if (e.name === "AbortError") return; }
  if (NO_IPHONE) {
    window.open(url, "_blank");      // no Safari: botão compartilhar > Salvar vídeo
    aviso("No vídeo que abriu: toque em Compartilhar (⬆) e depois em Salvar Vídeo. Ele vai para o app Fotos.");
    return;
  }
  const a = document.createElement("a"); a.href = url; a.download = nome; document.body.appendChild(a); a.click(); a.remove();
}

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
  await copiar($("#legenda").textContent);
  $("#b-copiar").textContent = "Copiado";
  setTimeout(() => $("#b-copiar").textContent = "Copiar", 1500);
};

const NOMES = { formatos: "Outros formatos (prévias)", formatos_final: "Outros formatos (final)", auto: "Edição automática (montagem + 3 prévias)", revisar: "Revisão de compliance", cortar: "Corte limpo", previa: "Gerando prévias", final: "Exportando a final", storyboard: "Montando o storyboard (nada é renderizado)",
  legenda: "Legenda do post", pacote: "Pacote por categorias", transcrever: "Transcrição" };

async function rodar(acao, versoes) {
  if (!atual) return;
  if (acao === "auto") {
    if (!dados.brutos.length) return alert("Solte os vídeos brutos primeiro.");
    if (!confirm("Montar a edição automaticamente a partir dos vídeos e gerar as 3 prévias?\n" +
                 "O projeto.yaml atual fica guardado em trabalho/projeto.yaml.anterior.")) return;
  }
  if ($("#yaml").value !== dados.yaml && !confirm("O projeto.yaml tem alterações não salvas. Rodar mesmo assim?")) return;
  if (typeof ed !== "undefined" && ed.sujo && ["previa", "final", "auto"].includes(acao) &&
      !confirm("A aba Edição tem alterações não salvas (elas ficam de fora). Rodar mesmo assim?")) return;
  try {
    const r = await api("/api/acao", { p: atual, acao, versoes });
    acompanhar(r.job, NOMES[acao] || acao);
  } catch (err) { alert(err.message); }
}

$("#t-detalhes").onclick = () => $("#tarefa").classList.toggle("com-detalhes");

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible") return;
  if (atual && !$("#projeto").hidden && !jobAtivo) abrir(atual).catch(() => {});
});

// painel reabre no Python novo (depois de instalar a transcrição) e a página volta sozinha
async function reabrirPainel() {
  aviso("Reabrindo o painel no Python novo…");
  try { await api("/api/reiniciar", {}); } catch (e) { /* o painel caiu para reabrir */ }
  const esperar = async (n) => {
    await new Promise((r) => setTimeout(r, 1500));
    try { await api("/api/projetos"); location.reload(); } catch (e) { if (n > 0) esperar(n - 1); else aviso("O painel não voltou: abra de novo o Divine Studio.command no Mac.", "erro"); }
  };
  esperar(20);
}

function acompanhar(job, titulo) {
  jobAtivo = job;
  $("#tarefa").hidden = false;
  $("#t-titulo").textContent = titulo;
  $$("[data-acao], #b-aprovar").forEach((b) => b.disabled = true);
  const liberar = (msg) => {
    jobAtivo = null;
    $$("[data-acao], #b-aprovar").forEach((b) => b.disabled = false);
    $("#t-tempo").innerHTML = `<span class="estado-erro">${esc(msg)}</span>`;
  };
  const tick = async () => {
    if (jobAtivo !== job) return;
    let e;
    try { e = await api("/api/job?id=" + job); }
    catch (err) {
      if (/não encontrada/.test(err.message)) return liberar("a tarefa não existe mais (o painel foi reiniciado?)");
      setTimeout(tick, 4000);          // sem conexão por um momento: tenta de novo
      return;
    }
    $("#t-log").textContent = e.log;
    $("#t-log").scrollTop = 1e9;
    $("#t-tempo").innerHTML = e.estado === "rodando" ? `${e.segundos}s`
      : `<span class="estado-${e.estado}">${e.estado === "ok" ? "pronto" : "parou com erro"}</span> em ${e.segundos}s`;
    $("#t-barra").style.width = e.progresso ? `${Math.min(100, 100 * e.progresso[0] / e.progresso[1])}%` : (e.estado === "rodando" ? "8%" : "100%");
    if (e.estado === "rodando") setTimeout(tick, 1200);
    else {
      jobAtivo = null;
      avisarFim(titulo, e.estado === "ok");
      $$("[data-acao], #b-aprovar").forEach((b) => b.disabled = false);
      if (atual) abrir(atual);
      const simples = document.body.classList.contains("simples");
      if (e.estado === "ok" && ["previa", "final", "auto"].includes(e.acao)) {
        if (simples) { $('[data-aba="config"]').click(); $("#proximo-passo").scrollIntoView({ behavior: "smooth" }); setTimeout(() => { if (!jobAtivo) $("#tarefa").hidden = true; }, 4000); }
        else $('[data-aba="versoes"]').click();
      }
      if (e.acao === "storyboard" && typeof carregarStoryboard === "function") { $('[data-aba="storyboard"]').click(); carregarStoryboard(); }
      if (e.estado === "ok" && (e.acao.startsWith("formatos") || e.acao === "cortes" || e.acao === "pacote")) carregarLista();
      if (e.estado === "ok" && e.acao === "cortes") alert("Cortes prontos: estão na lista de projetos, logo abaixo deste vídeo.");
      if (e.estado === "ok" && e.acao === "final" && !simples) setTimeout(() => abrirConversa((e.versoes && e.versoes[0]) || "V1").catch(() => {}), 1200);
      if (e.estado === "ok" && e.acao === "instalar_fala") { aviso("Transcrição instalada ✓"); reabrirPainel(); }
      if (e.estado === "erro" && e.acao === "instalar_fala") { $("#tarefa").classList.add("com-detalhes"); aviso("A instalação parou: o passo a passo está na janela da tarefa. Mande um print para o Claude.", "erro"); }
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
  if (h) abrir(h).catch(() => mostrarTela("inicio"));
  else mostrarTela("inicio");
});

// passo a passo do projeto: mostra onde você está e leva para a aba certa
function desenharPassos() {
  const brutos = (dados.brutos || []).length, previas = dados.saidas.filter((s) => s.previa).length;
  const finais = dados.saidas.filter((s) => !s.previa).length;
  const postado = (dados.publicacoes || []).some((p) => p.status === "postado");
  const passos = [
    ["Vídeos brutos", brutos > 0, "config", brutos ? `${brutos} enviado(s)` : "solte os vídeos"],
    ["Ajustes e textos", previas > 0 || !!dados.storyboard, "edicao", "hooks, efeitos, sons e voz"],
    ["Storyboard", !!dados.storyboard_aprovado || finais > 0, "storyboard", dados.storyboard ? (dados.storyboard_aprovado ? "aprovado ✓" : "responda ou aprove") : "veja os quadros antes do render"],
    ["Prévias", previas > 0, "versoes", previas ? `${previas} prévia(s)` : "gere as 3 versões"],
    ["Escolher e exportar", finais > 0, "versoes", finais ? `${finais} final(is)` : "aprove a melhor"],
    ["Postar", postado, "programacao", postado ? "postado ✓" : "agende ou marque Postei"],
  ];
  if (document.body.classList.contains("simples")) {
    passos.splice(0, passos.length,
      ["Vídeo bruto", brutos > 0, "config", brutos ? `${brutos} enviado(s)` : "solte o vídeo"],
      ["Edição automática", previas > 0 || finais > 0, "config", previas ? "versões prontas" : "um toque"],
      ["Aprovar a melhor", finais > 0, "config", finais ? "final exportada ✓" : "assista e aprove"],
      ["Postar", postado, "config", postado ? "postado ✓" : "baixe e poste"]);
  }
  const atualIdx = passos.findIndex((p) => !p[1]);
  $("#p-passos").innerHTML = passos.map(([n, ok, aba, sub], i) => `<li class="${ok ? "feito" : ""} ${i === atualIdx ? "agora" : ""}" data-aba-ir="${aba}">
      <b>${ok ? "✓" : i + 1}</b><span>${n}<small>${esc(sub)}</small></span></li>`).join("");
  $$("#p-passos li").forEach((li) => li.onclick = () => {
    if (li.dataset.abaIr === "programacao") return mostrarTela("programacao");
    $(`[data-aba="${li.dataset.abaIr}"]`).click();
  });
}

$$("[data-voltar]").forEach((b) => b.onclick = () => {
  atual = null; history.replaceState(null, "", "#");
  document.body.classList.remove("projeto-aberto");
  mostrarTela("projetos"); carregarLista();
});
document.addEventListener("click", (e) => {
  const ir = e.target.closest("[data-ir]");
  if (ir) mostrarTela(ir.dataset.ir);
  if (!e.target.closest("details.mais")) $$("details.mais[open]").forEach((d) => d.removeAttribute("open"));
});

// aviso de tarefa pronta: título da aba, vibração no iPhone e um "ding" suave
function avisarFim(titulo, ok) {
  const antes = document.title;
  document.title = (ok ? "✓ " : "⚠ ") + titulo;
  setTimeout(() => { document.title = antes; }, 8000);
  try { navigator.vibrate && navigator.vibrate(ok ? 80 : [60, 60, 60]); } catch (e) { /* sem vibração */ }
  try { const a = new Audio("/sfx.wav?nome=ding_suave_a"); a.volume = 0.35; a.play().catch(() => {}); } catch (e) { /* sem som */ }
}

async function renomear() {
  const novo = prompt("Novo nome do projeto:", dados.titulo || "");
  if (!novo || !novo.trim() || novo.trim() === dados.titulo) return;
  try {
    await api("/api/dados", { p: atual, dados: { titulo: novo.trim() } });
    aviso("Projeto renomeado."); await carregarLista(); abrir(atual);
  } catch (err) { aviso(err.message, "erro"); }
}
$("#b-renomear").onclick = renomear;
$("#p-titulo").onclick = renomear;

$("#b-duplicar").onclick = async () => {
  try { const r = await api("/api/duplicar", { p: atual }); await carregarLista(); abrir(r.nome); }
  catch (err) { alert(err.message); }
};
async function excluirProjeto(nome) {
  const p = (window._listaProjetos || []).find((x) => x.nome === nome) || {};
  if (!confirm(`Excluir "${p.titulo || nome}"?\nVai para a Lixeira do Mac (dá para recuperar até você esvaziar a Lixeira).`)) return;
  try {
    const r = await api("/api/excluir", { p: nome });
    if (atual === nome) { atual = null; history.replaceState(null, "", "#"); document.body.classList.remove("projeto-aberto"); mostrarTela("projetos"); }
    await carregarLista();
    aviso(`Excluído: foi para a ${r.destino}.`);
  } catch (err) { aviso(err.message, "erro"); }
}
$("#b-excluir").onclick = () => excluirProjeto(atual);

$("#b-arquivar").onclick = async () => {
  if (!confirm("Excluir este projeto da lista?\nPor segurança ele não é apagado: vai para a pasta _arquivo/projetos/ (dá para recuperar).")) return;
  try {
    const r = await api("/api/arquivar", { p: atual });
    atual = null; history.replaceState(null, "", "#"); await carregarLista();
    document.body.classList.remove("projeto-aberto"); mostrarTela("projetos");
    alert("Guardado em " + r.destino);
  } catch (err) { alert(err.message); }
};


// ---------------------------------------------------------------- conversa sobre a versão: o app x você
async function abrirConversa(versao) {
  const d = await api(`/api/opiniao?p=${encodeURIComponent(atual)}&v=${encodeURIComponent(versao)}`);
  const iaOk = (await estadoIA().catch(() => ({}))).ok;
  const sel = new Set((d.sua.reacoes || []));
  const m = document.createElement("div");
  m.className = "modal";
  const app = d.app;
  m.innerHTML = `<div class="cartao conversa-caixa">
    <div class="linha-titulo"><h2>💬 ${esc(versao)}: o que eu acho e o que você acha</h2><button class="link" data-f>fechar</button></div>
    <div class="dois-lados">
      <div class="lado lado-app"><h3>✦ O app</h3>${app.tem ? `
        <div class="nota-grande ${app.viraliza ? "boa" : ""}">${app.nota}<small>/10</small></div>
        <p><b>${esc(app.veredito)}</b></p>
        <div class="barras">${Object.entries(app.notas).map(([k, v]) => `<div><span>${esc(k)}</span><i style="width:${v * 10}%"></i><b>${v}</b></div>`).join("")}</div>
        ${app.sugestoes.length ? `<p class="dica">O que eu mudaria:</p><ul>${app.sugestoes.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
        <p class="dica">${esc(app.proximo)}</p>
        ${app.atencao && app.atencao.curva.length ? `<p class="dica">Atenção prevista ao longo do vídeo:</p>${curvaAtencao(app.atencao, app.riscos)}` : ""}
        ${app.riscos && app.riscos.length ? `<ul class="riscos">${app.riscos.map((r) => `<li>⚠ ${esc(r.texto)}
          ${r.i !== undefined ? `<button class="pb" data-aplicar-risco="${r.i}">Aplicar</button>` : ""}</li>`).join("")}</ul>` : ""}
        ${app.real ? `<p class="real">📊 ${esc(app.real)}</p>` : ""}` : '<p class="dica">Gere a prévia desta versão para eu dar a minha nota.</p>'}
        ${iaOk ? `<button data-ia>${d.comentario_ia ? "✦ Pedir outro comentário da IA" : "✦ Pedir comentário da IA (olha o vídeo)"}</button>` : ""}
        <div class="ia-texto md">${d.comentario_ia ? md(d.comentario_ia) : ""}</div>
      </div>
      <div class="lado voce"><h3>Você</h3>
        <div class="reacoes">${Object.entries(d.reacoes).map(([k, n]) => `<button class="chip ${sel.has(k) ? "ativo" : ""}" data-r="${k}">${esc(n)}</button>`).join("")}</div>
        <label>Nota (1 a 5)<div class="estrelas">${[1, 2, 3, 4, 5].map((n) => `<button data-n="${n}" class="${(d.sua.nota_usuario || 0) >= n ? "on" : ""}">★</button>`).join("")}</div></label>
        <label>Observações (escreva do seu jeito: "achei lento", "faltou som", "texto pequeno"...)
          <textarea id="cv-texto" rows="3">${esc(d.sua.texto || "")}</textarea></label>
        <button class="dourado" data-enviar>Enviar minha opinião</button>
        <div class="resposta" id="cv-resp">${d.ajustes ? `<p class="dica">Nos próximos vídeos: ${d.ajustes.map(esc).join(" · ")}</p>` : ""}</div>
      </div>
    </div></div>`;
  document.body.appendChild(m);
  let nota = d.sua.nota_usuario || null;
  const fechar = () => { m.remove(); abrir(atual); };
  m.onclick = (e) => { if (e.target === m || e.target.dataset.f !== undefined) fechar(); };
  m.querySelectorAll("[data-r]").forEach((b) => b.onclick = () => { b.classList.toggle("ativo"); sel.has(b.dataset.r) ? sel.delete(b.dataset.r) : sel.add(b.dataset.r); });
  m.querySelectorAll("[data-n]").forEach((b) => b.onclick = () => { nota = +b.dataset.n; m.querySelectorAll("[data-n]").forEach((x) => x.classList.toggle("on", +x.dataset.n <= nota)); });
  m.querySelector("[data-enviar]").onclick = async () => {
    try {
      const r = await api("/api/opiniao", { p: atual, versao, reacoes: [...sel], texto: m.querySelector("#cv-texto").value, nota });
      const conc = r.concordam === null ? "" : r.concordam ? "<p>🤝 Concordamos sobre viralizar.</p>"
        : "<p>🤔 Discordamos sobre viralizar: as métricas vão dizer quem acertou, e eu aprendo com isso.</p>";
      m.querySelector("#cv-resp").innerHTML = `${conc}${r.lidas_do_texto.length ? `<p class="dica">Entendi do seu texto: ${r.lidas_do_texto.map((x) => esc(d.reacoes[x])).join(", ")}</p>` : ""}
        <p><b>Nos próximos vídeos:</b> ${r.explicacao.map(esc).join(" · ")}</p>`;
    } catch (err) { alert(err.message); }
  };
  m.querySelectorAll("[data-aplicar-risco]").forEach((b) => b.onclick = async () => {
    try {
      const r = await api("/api/atencao/aplicar", { p: atual, versao, i: +b.dataset.aplicarRisco });
      b.textContent = "Aplicado ✓"; b.disabled = true;
      alert(`Coloquei ${r.efeito.tipo.replace("_", " ")} em ${r.efeito.inicio}s. Gere a prévia de novo para ver.`);
    } catch (err) { alert(err.message); }
  });
  const bia = m.querySelector("[data-ia]");
  if (bia) bia.onclick = async () => {
    bia.disabled = true; bia.textContent = "Olhando o vídeo… (até 1 min)";
    try { const r = await api("/api/opiniao/ia", { p: atual, versao }); m.querySelector(".ia-texto").innerHTML = md(r.texto); }
    catch (err) { alert(err.message); }
    bia.disabled = false; bia.textContent = "✦ Pedir outro comentário da IA";
  };
}


// tela dividida: vídeo analisado, layout e crédito
$("#react-layout").onchange = (e) => api("/api/dados", { p: atual, dados: { layout: e.target.value } }).catch((err) => alert(err.message));
$("#react-credito").onchange = (e) => api("/api/dados", { p: atual, dados: { credito: e.target.value.trim() || null } }).catch((err) => alert(err.message));
$("#react-arq").onchange = async () => {
  const f = $("#react-arq").files[0]; if (!f) return;
  $("#react-refs").textContent = "Enviando…";
  const r = await fetch(`/api/upload?p=${encodeURIComponent(atual)}&nome=${encodeURIComponent(f.name)}`, { method: "POST", body: f });
  const j = await r.json(); if (!r.ok) return alert(j.erro);
  await api("/api/clipe", { p: atual, arquivo: f.name, referencia: true });
  abrir(atual);
};

$("#b-tv").onclick = () => window.open("/tv", "_blank");


// anúncio: objetivo, serviço, dor e benefício viram roteiro e copy
async function salvarAnuncio() {
  const anuncio = { objetivo: $("#an-objetivo").value, servico: $("#an-servico").value.trim(), dor: $("#an-dor").value.trim(),
                    beneficio: $("#an-beneficio").value.trim() };
  await api("/api/dados", { p: atual, dados: { anuncio } });
}
["#an-objetivo", "#an-servico", "#an-dor", "#an-beneficio"].forEach((s) => $(s).onchange = () => salvarAnuncio().then(() => abrir(atual)).catch((err) => alert(err.message)));
$("#an-roteiro").onclick = async () => {
  if (!confirm("Refazer os ganchos, as mensagens, a chamada e o final do vídeo com estes dados?")) return;
  try { await salvarAnuncio(); await api("/api/anuncio/roteiro", { p: atual }); alert("Roteiro do anúncio atualizado. Gere as prévias."); abrir(atual); }
  catch (err) { alert(err.message); }
};


// curva de atenção prevista (verde = segura, vermelho = risco de queda)
function curvaAtencao(at, riscos) {
  const w = 320, h = 60, n = at.curva.length, dur = n * at.passo;
  const pts = at.curva.map((v, k) => `${(k / Math.max(1, n - 1)) * w},${h - v * (h - 6) - 3}`).join(" ");
  const zonas = (riscos || []).filter((r) => r.ini !== undefined).map((r) =>
    `<rect x="${(r.ini / dur) * w}" y="0" width="${((r.fim - r.ini) / dur) * w}" height="${h}" fill="#E0866F33"/>`).join("");
  return `<svg viewBox="0 0 ${w} ${h}" class="curva-atencao">${zonas}<polyline points="${pts}" fill="none" stroke="#CCBD91" stroke-width="2"/></svg>
    <div class="eixo"><span>0 s</span><span>${dur.toFixed(0)} s</span></div>`;
}

$("#react-reusar").onchange = async () => {
  const f = $("#react-reusar").files[0]; if (!f) return;
  try {
    const { nome } = await api("/api/duplicar", { p: atual });
    const r = await fetch(`/api/upload?p=${encodeURIComponent(nome)}&nome=${encodeURIComponent(f.name)}`, { method: "POST", body: f });
    const j = await r.json(); if (!r.ok) throw new Error(j.erro);
    await api("/api/clipe", { p: nome, arquivo: f.name, referencia: true });
    await carregarLista(); abrir(nome);
    alert("Pronto: a mesma reação com o vídeo novo. Ajuste o crédito e gere as prévias.");
  } catch (err) { alert(err.message); }
};
