// Tela de carrossel: cards com prévia, editor do card, estilo/fórmula/fontes, exportação em PNG.
const cr = { d: null, sel: 0, cfg: null, fontes: null, timer: null, versao: Date.now() };

const CR_CAMPOS = {
  capa: [["titulo", "Título (promessa que abre o loop)"], ["apoio", "Apoio em cursiva"], ["foto", "foto"]],
  texto: [["titulo", "Título"], ["texto", "Texto (um ponto só, lido em 2 s)", "area"], ["foto", "foto"]],
  lista: [["titulo", "Título"], ["itens", "Itens (um por linha)", "linhas"]],
  mito_verdade: [["mito", "Mito (ou expectativa)", "area"], ["verdade", "Verdade (ou realidade)", "area"]],
  citacao: [["texto", "Frase", "area"], ["pessoa", "Quem", "pessoa"]],
  cta: [["titulo", "Título final (resumo)"], ["pedido", "Um pedido só (salvar, enviar...)"]],
};
const CR_LAYOUTS = { capa: "Capa", texto: "Texto", lista: "Lista", mito_verdade: "Mito x Verdade", citacao: "Citação", cta: "Final (CTA)" };

async function abrirCarrossel(d) {
  cr.d = d; cr.sel = Math.min(cr.sel, Math.max(0, d.cards.length - 1));
  if (!cr.cfg) cr.cfg = await api("/api/carrossel/config");
  if (!cr.fontes) cr.fontes = await api("/api/fontes");
  const ePost = d.tipo === "post";
  $("#cr-titulo").textContent = d.titulo;
  $("#cr-pasta").textContent = "projetos/" + d.nome + (ePost ? " · post estático (imagem única)" : " · " + d.cards.length + " cards");
  $("#cr-formula").closest("label").hidden = ePost; $("#cr-rascunho").hidden = ePost;
  $("#cr-formatos").hidden = !ePost;
  $("#cr-exportar").textContent = ePost ? "Exportar imagens (PNG)" : "Exportar cards (PNG)";
  $("#cr-legenda").closest(".cartao").querySelector("h2").textContent = ePost ? "Legenda do post" : "Legenda do carrossel";
  if (ePost) {
    const fs = d.formatos && d.formatos.length ? d.formatos : ["feed45"];
    $$("[data-crfmt]").forEach((c) => c.checked = fs.includes(c.dataset.crfmt));
    const nomes = { feed45: "Feed 4:5", feed11: "Feed 1:1", stories: "Stories", tv: "TV" };
    const atualFmt = cr.fmt && fs.includes(cr.fmt) ? cr.fmt : fs[0];
    $("#cr-fmt-prev").innerHTML = fs.map((f) => `<option value="${f}" ${f === atualFmt ? "selected" : ""}>prévia: ${nomes[f] || f}</option>`).join("");
    cr.fmt = atualFmt;
  } else cr.fmt = "";
  if (window.pedidosHtml) $("#cr-pedidos").innerHTML = pedidosHtml(d.pedidos_imagem);
  $("#cr-estilo").innerHTML = Object.entries(cr.cfg.estilos).map(([k, v]) => `<option value="${k}" ${k === d.estilo ? "selected" : ""}>${esc(v)}</option>`).join("");
  $("#cr-formula").innerHTML = Object.entries(cr.cfg.formulas).map(([k, v]) => `<option value="${k}" ${k === d.formula ? "selected" : ""}>${esc(v)}</option>`).join("");
  $("#cr-fontes").innerHTML = `<option value="">rodízio</option>` + cr.fontes.map((f) => `<option value="${f.codigo}" ${f.codigo === d.fontes ? "selected" : ""}>${f.codigo} · ${esc(f.nome)}</option>`).join("");
  const z = $("#cr-zip"); z.hidden = !d.zip;
  if (d.zip) z.href = `/arquivo?p=${encodeURIComponent(atual)}&f=${encodeURIComponent(d.zip)}`;
  $("#cr-legenda").textContent = d.legenda || "A legenda sai junto com a exportação.";
  crDesenharCards(); crDesenharForm();
}

const crImg = (i, w = 360) => `/carrossel.jpg?p=${encodeURIComponent(atual)}&i=${i}&w=${w}&v=${cr.versao}${cr.fmt ? "&fmt=" + cr.fmt : ""}`;

function crDesenharCards() {
  $("#cr-cards").innerHTML = cr.d.cards.map((c, i) => `<div class="cr-card ${i === cr.sel ? "sel" : ""}" data-i="${i}">
      <img loading="lazy" src="${crImg(i, 240)}" alt="${esc(CR_LAYOUTS[c.layout] || c.layout)}">
      <div class="cr-mini">${i ? `<button data-mv="-1" title="subir">↑</button>` : ""}${i < cr.d.cards.length - 1 ? `<button data-mv="1" title="descer">↓</button>` : ""}
      <button data-rm title="remover">✕</button></div></div>`).join("") + (cr.d.tipo === "post" ? "" : `<div class="cr-add" id="cr-add">+ card</div>`);
  $$(".cr-card").forEach((el) => el.onclick = (e) => {
    const i = +el.dataset.i;
    if (e.target.dataset.mv) { const j = i + +e.target.dataset.mv; [cr.d.cards[i], cr.d.cards[j]] = [cr.d.cards[j], cr.d.cards[i]]; cr.sel = j; return crSalvar(); }
    if (e.target.dataset.rm !== undefined) { if (!confirm("Remover este card?")) return; cr.d.cards.splice(i, 1); cr.sel = Math.max(0, i - 1); return crSalvar(); }
    cr.sel = i; crDesenharCards(); crDesenharForm();
  });
  if ($("#cr-add")) $("#cr-add").onclick = () => { cr.d.cards.splice(cr.d.cards.length - 1, 0, { layout: "texto", titulo: "Novo *ponto*", texto: "" }); cr.sel = cr.d.cards.length - 2; crSalvar(); };
}

function crDesenharForm() {
  const c = cr.d.cards[cr.sel];
  if (!c) { $("#cr-form").innerHTML = '<p class="dica">Sem cards: clique em "Refazer rascunho".</p>'; return; }
  $("#cr-preview").src = crImg(cr.sel, 720);
  const campos = CR_CAMPOS[c.layout] || [];
  $("#cr-form").innerHTML = `<label>Tipo do card<select id="cr-layout">${Object.entries(CR_LAYOUTS).map(([k, v]) =>
      `<option value="${k}" ${k === c.layout ? "selected" : ""}>${v}</option>`).join("")}</select></label>` +
    campos.map(([k, rot, tipo]) => {
      const v = c[k];
      if (tipo === "area") return `<label>${rot}<textarea data-k="${k}">${esc(v || "")}</textarea></label>`;
      if (tipo === "linhas") return `<label>${rot}<textarea data-k="${k}" data-linhas>${esc((v || []).join("\n"))}</textarea></label>`;
      if (tipo === "pessoa") return `<label>${rot}<select data-k="${k}">${["daniel", "george", "isis"].map((o) => `<option ${o === v ? "selected" : ""}>${o}</option>`).join("")}</select></label>`;
      if (k === "foto") return `<label>Foto de fundo (opcional)<select data-k="foto"><option value="">sem foto</option>${(cr.d.fotos || []).map((f) =>
          `<option value="bruto/${esc(f)}" ${v === "bruto/" + f ? "selected" : ""}>${esc(f)}</option>`).join("")}</select></label>
          <label class="dica">Enviar foto <input type="file" id="cr-foto" accept="image/*"></label>`;
      return `<label>${rot}<input data-k="${k}" value="${esc(v || "")}"></label>`;
    }).join("") + `<p class="dica">*palavra* fica dourada · " / " quebra a linha · sem numeração nos cards</p>`;
  $("#cr-layout").onchange = (e) => { c.layout = e.target.value; crSalvar(); };
  $$("#cr-form [data-k]").forEach((el) => {
    const ev = el.tagName === "SELECT" ? "change" : "input";
    el.addEventListener(ev, () => {
      const k = el.dataset.k;
      if (el.dataset.linhas !== undefined) c[k] = el.value.split("\n").map((x) => x.trim()).filter(Boolean);
      else if (el.value) c[k] = el.value; else delete c[k];
      crSalvarDepois(el.tagName === "SELECT" ? 0 : 700);
    });
  });
  const ff = $("#cr-foto");
  if (ff) ff.onchange = async () => {
    const f = ff.files[0]; if (!f) return;
    $("#cr-status").textContent = "Enviando foto…";
    const r = await fetch(`/api/upload?p=${encodeURIComponent(atual)}&nome=${encodeURIComponent(f.name)}`, { method: "POST", body: f });
    const j = await r.json();
    if (!r.ok) return alert(j.erro);
    c.foto = j.arquivo; cr.d.fotos = [...new Set([...(cr.d.fotos || []), f.name])]; crSalvar();
  };
}

function crSalvarDepois(ms) { clearTimeout(cr.timer); $("#cr-status").textContent = "…"; cr.timer = setTimeout(crSalvar, ms); }

async function crSalvar() {
  try {
    await api("/api/dados", { p: atual, dados: { cards: cr.d.cards, estilo: $("#cr-estilo").value,
      formula: $("#cr-formula").value, fontes: $("#cr-fontes").value || null,
      ...(cr.d.tipo === "post" ? { formatos: $$("[data-crfmt]").filter((c) => c.checked).map((c) => c.dataset.crfmt) } : {}) } });
    cr.versao = Date.now();
    $("#cr-status").textContent = "Salvo.";
    crDesenharCards(); crDesenharForm();
  } catch (err) { $("#cr-status").textContent = err.message; }
}

["#cr-estilo", "#cr-fontes"].forEach((s) => $(s).onchange = () => crSalvar());
$("#cr-formula").onchange = () => crSalvar();
$("#cr-rascunho").onclick = async () => {
  if (!confirm("Refazer todos os cards com a fórmula escolhida? Os textos atuais serão trocados.")) return;
  await api("/api/carrossel/rascunho", { p: atual, formula: $("#cr-formula").value });
  cr.sel = 0; cr.versao = Date.now(); abrir(atual);
};
$("#cr-exportar").onclick = async () => {
  try {
    const post = cr.d.tipo === "post";
    const r = await api("/api/acao", { p: atual, acao: post ? "post" : "carrossel" });
    acompanhar(r.job, post ? "Exportando o post" : "Exportando o carrossel");
  } catch (err) { alert(err.message); }
};
$("#cr-copiar").onclick = async () => { await navigator.clipboard.writeText($("#cr-legenda").textContent); $("#cr-copiar").textContent = "Copiado"; setTimeout(() => $("#cr-copiar").textContent = "Copiar", 1500); };


$$("[data-crfmt]").forEach((c) => c.onchange = async () => {
  cr.d.formatos = $$("[data-crfmt]").filter((x) => x.checked).map((x) => x.dataset.crfmt);
  await crSalvar(); abrirCarrossel(cr.d);
});
$("#cr-fmt-prev").onchange = (e) => { cr.fmt = e.target.value; crDesenharCards(); crDesenharForm(); };

