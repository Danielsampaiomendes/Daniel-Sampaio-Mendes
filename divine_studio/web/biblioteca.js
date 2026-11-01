// Biblioteca de imagens (logos, pessoas, tecnologias, clínica, produtos), pedidos de imagem e antes e depois.

async function enviarBib(cat, arquivo, item) {
  const r = await fetch(`/api/biblioteca/upload?cat=${cat}&nome=${encodeURIComponent(arquivo.name)}${item ? "&item=" + encodeURIComponent(item) : ""}`,
    { method: "POST", body: arquivo });
  const j = await r.json();
  if (!r.ok) throw new Error(j.erro || "falha no envio");
  return j;
}

// aviso "me mande esta foto" (projeto, carrossel, post e na própria Biblioteca)
window.pedidosHtml = (lista) => {
  if (!lista || !lista.length) return "";
  return `<div class="cartao pedidos"><h2>📷 Me mande estas imagens para a peça ficar completa</h2><ul>${lista.map((p) =>
    `<li><b>${esc(p.nome)}</b>${p.por_que ? ` · ${esc(p.por_que)}` : ""}
      <label class="botao link">enviar<input type="file" accept="image/*" hidden data-pcat="${p.categoria}" data-pitem="${esc(p.arquivo)}"></label>
      <div class="dica">${esc(p.dica)}</div></li>`).join("")}</ul></div>`;
};
document.addEventListener("change", async (e) => {
  const inp = e.target;
  if (!inp.dataset || !inp.dataset.pcat || !inp.files[0]) return;
  try {
    await enviarBib(inp.dataset.pcat, inp.files[0], inp.dataset.pitem);
    if (!$("#biblioteca").hidden) window.carregarBiblioteca(); else if (atual) abrir(atual);
  } catch (err) { alert(err.message); }
});

window.carregarBiblioteca = async () => {
  const cats = await api("/api/biblioteca");
  const faltam = cats.reduce((s, c) => s + c.faltam_obrigatorios, 0);
  $("#bib-resumo").textContent = faltam ? `Faltam ${faltam} imagem(ns) essencial(is)` : "Essenciais completos ✓";
  const essenciais = cats.flatMap((c) => c.itens.filter((i) => !i.tem && i.obrigatorio)
    .map((i) => ({ categoria: c.chave, arquivo: i.arquivo, nome: i.nome, por_que: i.uso || "", dica: c.dica })));
  $("#bib-pedidos").innerHTML = pedidosHtml(essenciais);
  const img = (cat, f) => `/biblioteca.img?cat=${cat}&f=${encodeURIComponent(f)}&w=320&v=${Date.now()}`;
  $("#bib-cats").innerHTML = cats.map((c) => `<div class="cartao">
      <div class="linha-titulo"><h2>${esc(c.nome)}</h2><span class="dica">${c.itens.length - c.faltam}/${c.itens.length} · <code>${esc(c.pasta)}</code></span>
        <label class="botao">+ outra imagem<input type="file" accept="image/*" multiple hidden data-bcat="${c.chave}"></label></div>
      <p class="dica">${esc(c.dica)}</p>
      <div class="bib-itens">${c.itens.map((i) => `<label class="bib-item ${i.tem ? "tem" : "falta"} ${i.obrigatorio ? "obrig" : ""}" title="${i.tem ? "Clique para trocar (a anterior vai para _arquivo/)" : "Clique para enviar"}">
          ${i.tem ? `<img loading="lazy" src="${img(c.chave, i.tem)}" alt="">` : '<div class="vazio-img">+</div>'}
          <div>${esc(i.nome)}${i.obrigatorio && !i.tem ? " ·  <b>essencial</b>" : ""}</div>
          ${i.uso ? `<div class="uso">${esc(i.uso)}</div>` : ""}
          <input type="file" accept="image/*" data-bcat="${c.chave}" data-bitem="${esc(i.arquivo)}"></label>`).join("")}
        ${c.extras.map((f) => `<div class="bib-item tem"><img loading="lazy" src="${img(c.chave, f)}" alt=""><div>${esc(f)}</div></div>`).join("")}</div>
    </div>`).join("");
  $$("[data-bcat]").forEach((inp) => inp.onchange = async () => {
    try {
      for (const f of inp.files) await enviarBib(inp.dataset.bcat, f, inp.dataset.bitem);
      window.carregarBiblioteca();
    } catch (err) { alert(err.message); }
  });
};

// ---------------------------------------------------------------- antes e depois (uso interno)

const ad = { d: null, versao: Date.now(), timer: null };

async function abrirAntesDepois(d) {
  ad.d = d;
  $("#ad-titulo").textContent = d.titulo;
  $("#ad-pasta").textContent = "projetos/" + d.nome + " · antes e depois · uso interno";
  $("#ad-t").value = d.titulo || ""; $("#ad-sub").value = d.subtitulo || ""; $("#ad-cta").value = d.cta || "";
  $("#ad-aut").value = d.autorizacao_imagem === "sim" ? "sim" : "pendente";
  $$("[data-adfmt]").forEach((c) => c.checked = (d.formatos || []).includes(c.dataset.adfmt));
  $("#ad-video").checked = d.video !== false;
  adPares(); adPrevia();
  const arqs = (d.imagens || []);
  $("#ad-arquivos").innerHTML = arqs.length ? `<p class="dica">Gerados:</p>` + arqs.map((f) =>
    `<button class="pb" data-adarq="${esc(f)}">⤓ ${esc(f.split("/").pop())}</button>`).join(" ") : "";
  $$("[data-adarq]").forEach((b) => b.onclick = () => salvarNaGaleria(`/arquivo?p=${encodeURIComponent(atual)}&f=${encodeURIComponent(b.dataset.adarq)}`, b.dataset.adarq.split("/").pop()));
}

const adFotoUrl = (rel) => `/arquivo?p=${encodeURIComponent(atual)}&f=${encodeURIComponent(rel)}`;

function adCampoFoto(i, chave, rotulo, rel) {
  return `<label class="ad-foto">${rel ? `<img src="${adFotoUrl(rel)}" alt="">` : '<div class="vazio-img">+</div>'}${rotulo}
    <input type="file" accept="image/*" data-adi="${i}" data-adk="${chave}"></label>`;
}

function adPares() {
  const pares = ad.d.pares || [];
  $("#ad-pares").innerHTML = pares.map((p, i) => `<div class="ad-par ${p.montagem !== undefined ? "montagem" : ""}">
      ${p.montagem !== undefined ? adCampoFoto(i, "montagem", "Montagem (antes à esquerda, depois à direita)", p.montagem)
        : adCampoFoto(i, "antes", "ANTES", p.antes) + adCampoFoto(i, "depois", "DEPOIS", p.depois)}
      <label>Ângulo<input data-ada="${i}" value="${esc(p.angulo || "")}" placeholder="ex.: perfil" list="ad-angulos"></label>
      <button class="link" data-adrm="${i}">remover</button></div>`).join("") || '<p class="dica">Adicione o primeiro par.</p>'
    + `<datalist id="ad-angulos">${["Frente", "Perfil", "Três quartos", "Posterior", "Lateral"].map((a) => `<option value="${a}">`).join("")}</datalist>`;
  $$("[data-adk]").forEach((inp) => inp.onchange = async () => {
    const f = inp.files[0]; if (!f) return;
    $("#ad-status").textContent = "Enviando foto…";
    const r = await fetch(`/api/upload?p=${encodeURIComponent(atual)}&nome=${encodeURIComponent(f.name)}`, { method: "POST", body: f });
    const j = await r.json();
    if (!r.ok) { $("#ad-status").textContent = ""; return alert(j.erro); }
    ad.d.pares[+inp.dataset.adi][inp.dataset.adk] = j.arquivo;
    adSalvar();
  });
  $$("[data-ada]").forEach((inp) => inp.oninput = () => { ad.d.pares[+inp.dataset.ada].angulo = inp.value; adSalvarDepois(); });
  $$("[data-adrm]").forEach((b) => b.onclick = () => { if (!confirm("Remover este par? (as fotos continuam em bruto/)")) return; ad.d.pares.splice(+b.dataset.adrm, 1); adSalvar(); });
}

function adPrevia() {
  $("#ad-previa").src = `/antesdepois.jpg?p=${encodeURIComponent(atual)}&fmt=${$("#ad-fmt-prev").value}&w=960&v=${ad.versao}`;
}

function adSalvarDepois() { clearTimeout(ad.timer); $("#ad-status").textContent = "…"; ad.timer = setTimeout(adSalvar, 700); }

async function adSalvar() {
  try {
    await api("/api/dados", { p: atual, dados: {
      titulo: $("#ad-t").value, subtitulo: $("#ad-sub").value, cta: $("#ad-cta").value,
      autorizacao_imagem: $("#ad-aut").value, video: $("#ad-video").checked,
      formatos: $$("[data-adfmt]").filter((c) => c.checked).map((c) => c.dataset.adfmt),
      pares: ad.d.pares || [] } });
    ad.versao = Date.now();
    $("#ad-status").textContent = "Salvo.";
    adPares(); adPrevia();
  } catch (err) { $("#ad-status").textContent = err.message; }
}

["#ad-t", "#ad-sub", "#ad-cta"].forEach((s) => $(s).oninput = adSalvarDepois);
["#ad-aut", "#ad-video"].forEach((s) => $(s).onchange = adSalvar);
$$("[data-adfmt]").forEach((c) => c.onchange = adSalvar);
$("#ad-fmt-prev").onchange = adPrevia;
$("#ad-add").onclick = () => { ad.d.pares = [...(ad.d.pares || []), { antes: "", depois: "", angulo: "" }]; adPares(); };
$("#ad-add-m").onclick = () => { ad.d.pares = [...(ad.d.pares || []), { montagem: "", angulo: "" }]; adPares(); };
$("#ad-exportar").onclick = async () => {
  if ($("#ad-aut").value !== "sim" && !confirm("A autorização de imagem está pendente. Ela é obrigatória: marque 'sim' só se a paciente autorizou.")) return;
  try {
    await adSalvar();
    const r = await api("/api/acao", { p: atual, acao: "antesdepois" });
    acompanhar(r.job, "Gerando o antes e depois");
  } catch (err) { alert(err.message); }
};

$("#form-ad").onsubmit = async (e) => {
  e.preventDefault();
  const titulo = $("#novo-ad").value.trim(); if (!titulo) return;
  try {
    const r = await api("/api/antesdepois/novo", { titulo });
    $("#novo-ad").value = ""; await carregarLista(); abrir(r.nome);
  } catch (err) { alert(err.message); }
};
