// Storyboard: a edição real em quadros, antes do render. Responda "aprovado" ou "4B: troca o título por ...".
let sbVersao = "V1";

function sbImg(rel, t) {
  return `/arquivo?p=${encodeURIComponent(atual)}&f=${encodeURIComponent(rel)}&t=${t}`;
}

function fmtS(x) { return Number(x).toFixed(1).replace(".", ",") + " s"; }

async function carregarStoryboard(v) {
  if (!atual) return;
  let r;
  try { r = await api(`/api/storyboard?p=${encodeURIComponent(atual)}${v ? "&v=" + encodeURIComponent(v) : ""}`); }
  catch (err) { $("#sb-meta").textContent = err.message; return; }
  sbVersao = r.versao;
  $("#sb-versoes").innerHTML = (r.versoes || []).map((x) =>
    `<button class="${x === sbVersao ? "dourado" : ""}" data-sbv="${esc(x)}">${esc(x)}</button>`).join("");
  $$("#sb-versoes [data-sbv]").forEach((b) => b.onclick = () => carregarStoryboard(b.dataset.sbv));
  const d = r.dados || {};
  if (!d.cenas) {
    $("#sb-meta").textContent = "Ainda não gerado. Toque em ▦ Storyboard (leva segundos, nada é renderizado).";
    $("#sb-regua").innerHTML = $("#sb-cenas").innerHTML = "";
    return;
  }
  const marca = Date.now();
  $("#sb-meta").innerHTML = `Estilo ${esc(d.estilo)} · ${fmtS(d.duracao)} · ${d.cenas_total} cenas · ${d.momentos_total} momentos · gerado em ${esc(d.gerado_em)}`
    + (r.aprovado ? ' · <b class="ok">aprovado ✓</b>' : "");
  const todos = d.cenas.flatMap((c) => c.momentos);
  $("#sb-regua").innerHTML = `<div class="sb-trilho">${todos.map((m) =>
    `<span class="sb-tique" style="left:${(100 * m.t / d.duracao).toFixed(2)}%" title="${esc(m.codigo)} · ${fmtS(m.t)}" data-cod="${esc(m.codigo)}"><i>${esc(m.codigo)}</i></span>`).join("")}</div>`;
  $("#sb-cenas").innerHTML = d.cenas.map((c) => `
    <div class="sb-cena">
      <div class="sb-cena-topo"><b>Cena ${c.numero}</b> <span class="dica">${fmtS(c.inicio)} – ${fmtS(c.fim)}</span></div>
      ${c.fala ? `<p class="sb-fala">“${esc(c.fala)}”</p>` : ""}
      <div class="sb-quadros">${c.momentos.map((m) => `
        <figure class="sb-quadro ${m.tipo}" data-cod="${esc(m.codigo)}">
          ${m.quadro ? `<img loading="lazy" src="${sbImg(m.quadro, marca)}" data-grande="${esc(m.quadro_grande || m.quadro)}" alt="">` : '<div class="sb-vazio"></div>'}
          <figcaption><b class="sb-cod">${esc(m.codigo)}</b> <span class="dica">${fmtS(m.t)} · ${esc(rotuloSb(m))}</span>
            <span>${esc((m.texto || "").replace(/\*/g, "").replace(/ \/ /g, " "))}</span></figcaption>
        </figure>`).join("")}</div>
    </div>`).join("");
  $$("#sb-cenas .sb-quadro img").forEach((img) => img.onclick = (e) => { e.stopPropagation(); ampliarSb(img.dataset.grande, marca); });
  $$("#sb-cenas .sb-cod, #sb-regua .sb-tique").forEach((el) => el.onclick = () => {
    const cod = el.closest("[data-cod]").dataset.cod;
    const t = $("#sb-texto");
    t.value = (t.value && !t.value.endsWith("\n") ? t.value + "\n" : t.value) + cod + ": ";
    t.focus();
  });
}

function rotuloSb(m) {
  return { hook: "hook", mensagem: "texto", chamada: "chamada", efeito: m.auto ? "efeito automático" : "efeito",
           corte: "corte", fechamento: "fechamento", cena: "cena" }[m.tipo] || m.tipo;
}

function ampliarSb(rel, marca) {
  const m = document.createElement("div");
  m.className = "modal";
  m.innerHTML = `<img class="sb-ampliado" src="${sbImg(rel, marca)}" alt="">`;
  m.onclick = () => m.remove();
  document.body.appendChild(m);
}

async function responderSb(texto) {
  if (!atual || !texto.trim()) return;
  try {
    const r = await api("/api/storyboard", { p: atual, v: sbVersao, resposta: texto });
    const linhas = [];
    if (r.aprovado) linhas.push('<p class="ok">✓ Aprovado. Exportando a final…</p>');
    (r.aplicados || []).forEach((x) => linhas.push(`<p class="ok">✓ ${esc(x)}</p>`));
    (r.avisos || []).forEach((x) => linhas.push(`<p class="estado-erro">! ${esc(x)}</p>`));
    (r.nao_entendi || []).forEach((x) => linhas.push(`<p class="dica">? ${esc((x.codigo ? x.codigo + ": " : "") + x.pedido)}: ${esc(x.motivo || "não entendi")}</p>`));
    if ((r.nao_entendi || []).length) linhas.push('<p class="dica">Exemplos: 4B: troca o título por "..." · 7: tira · 2A: entra mais cedo · 3: mais longo 1s · 5B: troca o efeito por flash · 2: em cima · 1: sem som · 3: troca a fonte</p>');
    $("#sb-retorno").innerHTML = linhas.join("");
    if (r.job) {
      $("#sb-texto").value = "";
      acompanhar(r.job, r.aprovado ? "Exportando a final" : "Refazendo o storyboard com as mudanças");
    }
  } catch (err) { aviso(err.message, "erro"); }
}

async function gerarStoryboard() {
  if (!atual) return;
  if (typeof ed !== "undefined" && ed.sujo && !confirm("A aba Edição tem alterações não salvas (elas ficam de fora). Seguir mesmo assim?")) return;
  try {
    const r = await api("/api/storyboard", { p: atual, gerar: true });
    $('[data-aba="storyboard"]').click();
    acompanhar(r.job, "Montando o storyboard (nada é renderizado)");
  } catch (err) { aviso(err.message, "erro"); }
}

$("#b-storyboard").onclick = gerarStoryboard;
$("#sb-gerar").onclick = gerarStoryboard;
$("#sb-aplicar").onclick = () => responderSb($("#sb-texto").value);
$("#sb-aprovar").onclick = () => responderSb("aprovado");
$("#sb-texto").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) responderSb($("#sb-texto").value);
});
$('[data-aba="storyboard"]').addEventListener("click", () => carregarStoryboard(sbVersao));
