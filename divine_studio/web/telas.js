// Telas do topo: Projetos, Programação, IA e ideias, Referências, Biblioteca.
const TELAS = ["inicio", "nova", "projetos", "galeria", "lab", "crescimento", "programacao", "ia", "referencias", "biblioteca"];

function mostrarTela(nome) {
  $$(".topo nav button").forEach((b) => b.classList.toggle("ativa", b.dataset.tela === nome));
  const secoes = { inicio: "#vazio", nova: "#nova", galeria: "#galeria", lab: "#lab", crescimento: "#crescimento", programacao: "#programacao", ia: "#ia",
                   referencias: "#referencias", biblioteca: "#biblioteca" };
  ["#escolha", "#projeto", "#carrossel", "#antesdepois", ...Object.values(secoes)].forEach((s) => { const el = $(s); if (el) el.hidden = true; });
  document.body.classList.toggle("com-lista", nome === "projetos");
  if (nome !== "projetos") document.body.classList.remove("projeto-aberto");
  if (nome === "projetos") {
    if (atual) abrir(atual); else { $("#escolha").hidden = false; document.body.classList.remove("projeto-aberto"); }
    return;
  }
  window.scrollTo(0, 0);
  const el = $(secoes[nome]); if (el) el.hidden = false;
  const carregar = { inicio: carregarInicio, nova: montarNovaEdicao, lab: () => window.carregarLab(), crescimento: () => window.carregarCrescimento(), galeria: window.carregarGaleria, programacao: carregarProgramacao, ia: window.carregarIA, referencias: window.carregarReferencias,
                     biblioteca: window.carregarBiblioteca }[nome];
  if (carregar) carregar();
}
$$(".topo nav button").forEach((b) => b.onclick = () => mostrarTela(b.dataset.tela));

// ---------------------------------------------------------------- Programação

const COLUNAS = [
  ["aprovado", "Para postar", (p) => p.status === "aprovado" && !["tv", "consulta"].includes(p.rede)],
  ["agendado", "Agendados", (p) => p.status === "agendado"],
  ["postado", "Postados", (p) => p.status === "postado" && !["tv", "consulta"].includes(p.rede)],
  ["tv", "Na TV da clínica", (p) => p.rede === "tv" && ["aprovado", "postado"].includes(p.status)],
  ["consulta", "Uso interno (consulta)", (p) => p.rede === "consulta"],
];

let pgPerfil = "";
async function carregarProgramacao() {
  const r = await api("/api/programacao");
  const aprendi = r.aprendi;
  const perfisUsados = [...new Set(r.pecas.map((p) => p.conta).filter(Boolean))];
  $("#pg-perfis").innerHTML = perfisUsados.length > 1 ? [["", "Todos os perfis"], ...perfisUsados.map((u) => [u, "@" + u])].map(([u, n]) =>
    `<button class="chip ${u === pgPerfil ? "ativo" : ""}" data-u="${esc(u)}">${esc(n)} <span>${u ? r.pecas.filter((p) => p.conta === u).length : r.pecas.length}</span></button>`).join("") : "";
  $$("#pg-perfis .chip").forEach((b) => b.onclick = () => { pgPerfil = b.dataset.u; carregarProgramacao(); });
  const pecas = r.pecas.filter((p) => !pgPerfil || p.conta === pgPerfil);
  const fmt = (d) => d ? d.split("-").reverse().join("/") : "";
  // próximos 7 dias: o que está agendado em cada dia
  const hoje = new Date(); hoje.setHours(0, 0, 0, 0);
  const dias = [...Array(7)].map((_, k) => { const d = new Date(hoje); d.setDate(d.getDate() + k); return d; });
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const nomeDia = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
  $("#pg-semana").innerHTML = dias.map((d, k) => {
    const doDia = pecas.filter((p) => p.status === "agendado" && p.data_agendada === iso(d));
    return `<div class="dia ${k === 0 ? "hoje" : ""} ${doDia.length ? "cheio" : ""}"><b>${k === 0 ? "hoje" : nomeDia[d.getDay()]}</b><span>${d.getDate()}/${d.getMonth() + 1}</span>
      ${doDia.map((p) => `<div class="ag" data-p="${esc(p.projeto)}" title="${esc(p.titulo)}">${esc(p.titulo)}<small>${p.conta ? "@" + esc(p.conta) : ""}</small></div>`).join("") || '<i>livre</i>'}</div>`;
  }).join("");
  $$("#pg-semana .ag").forEach((el) => el.onclick = () => { mostrarTela("projetos"); abrir(el.dataset.p); });
  $("#pg-colunas").innerHTML = COLUNAS.map(([id, nome, f]) => {
    let lista = pecas.filter(f);
    if (id === "agendado") lista.sort((a, b) => (a.data_agendada || "").localeCompare(b.data_agendada || ""));
    if (id === "postado") lista.sort((a, b) => (b.data_postagem || "").localeCompare(a.data_postagem || ""));
    return `<div class="prog-col cartao"><h2>${nome} <span>${lista.length}</span></h2>${lista.map((p) => {
      const m = p.metricas || {};
      return `<div class="peca" data-p="${esc(p.projeto)}" data-v="${esc(p.versao)}">
        <div class="t">${esc(p.titulo)} · <b>${esc(p.versao)}</b></div>
        ${p.conta ? `<div class="perfil">@${esc(p.conta)}</div>` : ""}
        <div class="m">${esc(p.tipo === "carrossel" ? "carrossel" : p.tipo === "antes_depois" ? "antes e depois" : p.tipo === "post" ? "post " + p.versao : p.formato)}${p.data_agendada && id === "agendado" ? " · " + fmt(p.data_agendada) : ""}${p.data_postagem && id !== "agendado" ? " · postado " + fmt(p.data_postagem) : ""}${p.gostei ? " · ♥" : ""}</div>
        ${p.tags && p.tags.length ? `<div>${p.tags.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>` : ""}
        ${id === "postado" ? `<div class="metricas" title="Métricas do Instagram (o app aprende com elas)">
          ${[["alcance", "alcance"], ["curtidas", "curtidas"], ["comentarios", "coment."], ["compartilhamentos", "envios"], ["salvamentos", "salvos"], ["views", "views"]]
            .map(([k, r]) => `<input type="number" min="0" data-m="${k}" placeholder="${r}" value="${m[k] ?? ""}">`).join("")}</div>` : ""}
        ${id === "aprovado" || id === "agendado" ? `<div class="redes">
          <label><input type="checkbox" data-rede="instagram" ${(p.redes || ["instagram"]).includes("instagram") ? "checked" : ""}> Instagram</label>
          <label><input type="checkbox" data-rede="tiktok" ${(p.redes || []).includes("tiktok") ? "checked" : ""}> TikTok</label>
          ${id === "agendado" ? `<label title="Publica sozinho no horário (o revisor roda antes)"><input type="checkbox" data-auto ${p.auto_postar ? "checked" : ""}> 🤖 postar sozinho${p.hora_agendada ? " às " + esc(p.hora_agendada) : ""}</label>` : ""}</div>` : ""}
        <div class="pub">${id === "aprovado" || id === "agendado" ? '<button class="pb" data-a="publicar">🚀 Publicar agora</button><button class="pb" data-a="postei">✓ Postei</button>' : ""}
          ${id === "aprovado" ? '<button class="pb" data-a="agendar">📅 Agendar</button>' : ""}
          ${p.arquivo ? '<button class="pb" data-a="salvar">⤓ Salvar</button>' : ""}
          ${p.entrega ? '<button class="pb" data-a="pasta">Pasta</button>' : ""}
          ${id !== "consulta" ? '<button class="pb" data-a="legenda" title="Copiar a legenda do post">Legenda</button>' : ""}</div></div>`;
    }).join("") || '<p class="dica">Nada aqui.</p>'}</div>`;
  }).join("");
  $("#pg-aprendi").innerHTML = aprendi.map((a) => `<li>${esc(a)}</li>`).join("") || '<li class="dica">Ainda sem histórico.</li>';
  const pecaDe = (el) => pecas.find((x) => x.projeto === el.dataset.p && x.versao === el.dataset.v);
  $$(".peca .t").forEach((t) => t.onclick = () => { mostrarTela("projetos"); abrir(t.closest(".peca").dataset.p); });
  $$(".peca .metricas input").forEach((inp) => inp.onchange = async () => {
    const el = inp.closest(".peca");
    await api("/api/publicacao", { p: el.dataset.p, versao: el.dataset.v, campos: { metricas: { [inp.dataset.m]: Number(inp.value) || 0 } } });
  });
  $$(".peca [data-rede]").forEach((c) => c.onchange = async () => {
    const el = c.closest(".peca");
    const redes = [...el.querySelectorAll("[data-rede]")].filter((x) => x.checked).map((x) => x.dataset.rede);
    await api("/api/publicacao", { p: el.dataset.p, versao: el.dataset.v, campos: { redes } });
  });
  $$(".peca [data-auto]").forEach((c) => c.onchange = async () => {
    const el = c.closest(".peca");
    await api("/api/publicacao", { p: el.dataset.p, versao: el.dataset.v, campos: { auto_postar: c.checked } });
    aviso(c.checked ? "Vai postar sozinho no horário, se passar no revisor." : "Postagem automática desligada.");
  });
  $$(".peca [data-a]").forEach((b) => b.onclick = async () => {
    const el = b.closest(".peca"), p = pecaDe(el);
    if (b.dataset.a === "salvar") return salvarNaGaleria(`/arquivo?p=${encodeURIComponent(p.projeto)}&f=${encodeURIComponent(p.arquivo)}`, p.arquivo.split("/").pop());
    if (b.dataset.a === "legenda") {
      const d = await api("/api/projeto?p=" + encodeURIComponent(p.projeto));
      if (!d.legenda) return alert("Este projeto ainda não tem legenda (gere em Relatório e legenda).");
      try { await copiar(d.legenda); b.textContent = "Copiada ✓"; }
      catch (e) { prompt("Copie a legenda:", d.legenda); }
      return;
    }
    if (b.dataset.a === "pasta") return api("/api/abrir_pasta", { caminho: p.entrega }).catch((e) => alert(e.message));
    if (b.dataset.a === "publicar") {
      const redes = (p.redes || ["instagram"]).join(" e ");
      if (!confirm(`Publicar agora no ${redes}?\n${p.titulo} · ${p.versao}\nO revisor de compliance roda antes.`)) return;
      b.disabled = true; b.textContent = "Publicando…";
      try {
        const r = await api("/api/publicar", { p: p.projeto, versao: p.versao });
        alert(Object.entries(r).map(([k, v]) => `${k}: ${v}`).join("\n"));
      } catch (err) { alert(err.message); }
      return carregarProgramacao();
    }
    let campos;
    if (b.dataset.a === "postei") {
      const link = prompt("Link do post (opcional):", ""); if (link === null) return;
      campos = { status: "postado", link: link || undefined };
    } else {
      const d = prompt("Data e hora da postagem (DD/MM HH:MM; sem hora = 19:00):", ""); if (!d) return;
      const [data, hora] = d.trim().split(/\s+/);
      const [dia, mes, ano] = data.split("/");
      campos = { status: "agendado", data_agendada: `${ano || new Date().getFullYear()}-${mes.padStart(2, "0")}-${dia.padStart(2, "0")}` };
      if (hora && /^\d{1,2}:\d{2}$/.test(hora)) campos.hora_agendada = hora.padStart(5, "0");
      campos.auto_postar = confirm("Postar sozinho nesse horário? (o app publica com o painel aberto no Mac; o revisor roda antes)");
    }
    await api("/api/publicacao", { p: p.projeto, versao: p.versao, campos });
    carregarProgramacao();
  });
}
$("#pg-entregas").onclick = () => api("/api/abrir_pasta", { caminho: "entregas" }).catch((e) => alert(e.message));

// ---------------------------------------------------------------- Nova edição (menu por tipo)

const EDICOES = [
  ["video", "🎬", "Vídeo (Reels)", "Envie os brutos: corte, hook em 3 versões, legenda da fala, efeitos e som no padrão viral luxo.", "ex.: Laser de CO2 no rosto"],
  ["epico", "✦", "Vídeo Épico", "A edição mais intensa: abertura em 3D, vertigem, chicote nos cortes, luz dourada e cor de cinema.", "ex.: Por dentro do Endolaser"],
  ["anuncio", "📣", "Anúncio (conversão)", "Vídeo e copy feitos para a paciente tocar em Saiba mais e agendar: dor, solução, prova e um pedido só. Sai em Reels, Stories e Feed.", "ex.: Endolaser nos braços"],
  ["longo", "✂", "Cortes de vídeo longo", "Solte um vídeo longo (podcast, explicação, bastidor): ele vira cortes curtos, médios, longos, melhores momentos e Stories.", "ex.: Podcast Dr. Daniel sobre CO2"],
  ["react", "◧", "Tela dividida (eu analisando)", "Você comentando um vídeo: dividida (vídeo em cima, você embaixo) ou cabecinha no canto. O app escolhe a melhor proporção.", "ex.: Analisando o Reels do CO2"],
  ["stories", "📱", "Stories", "Vídeo vertical para Stories, com área segura, enquete e chamada para o direct.", "ex.: Bastidores da manhã"],
  ["carrossel", "▦", "Carrossel", "Cards no padrão Divine com rascunho por fórmula (lista, mito x verdade, método…).", "ex.: 5 mitos do Laser de CO2"],
  ["post", "▣", "Post (imagem)", "Uma arte só, que sai de uma vez em Feed 4:5, Stories e TV.", "ex.: Endolaser nos braços"],
  ["tv", "📺", "TV da clínica", "Vídeo 16:9 calmo para a recepção, com legenda grande e sem pressa.", "ex.: Spa pedras quentes"],
  ["antes_depois", "◫", "Antes e depois", "Uso interno em consulta (nunca postar): fotos padronizadas em TV, Stories e Feed.", "ex.: Bumbum Up"],
];

const ESSENCIAIS = ["video", "epico"];
let montarNovaEdicao = function () {
  $("#tipos-edicao").innerHTML = EDICOES.map(([k, ic, nome, txt, ex]) => `<form class="tipo-edicao ${k === "epico" ? "epico" : ""} ${ESSENCIAIS.includes(k) ? "" : "so-avancado"}" data-tipo="${k}">
      <div class="ic">${ic}</div><h2>${nome}</h2><p>${txt}</p>
      <div class="linha"><input placeholder="${esc(ex)}" autocomplete="off"><button class="dourado" type="submit">Criar</button></div></form>`).join("");
  $$(".tipo-edicao").forEach((f) => f.onsubmit = async (e) => {
    e.preventDefault();
    const titulo = f.querySelector("input").value.trim();
    if (!titulo) return f.querySelector("input").focus();
    try {
      const r = await api("/api/nova_edicao", { tipo: f.dataset.tipo, titulo });
      await carregarLista(); mostrarTela("projetos"); abrir(r.nome);
    } catch (err) { alert(err.message); }
  });
};
$("#b-nova").onclick = () => mostrarTela("nova");

// modo simples (padrão): só o caminho bruto → edição → aprovar → postar; o resto em "Mais ferramentas"
function aplicarModo() {
  let av = false;
  try { av = localStorage.getItem("ds_avancado") === "1"; } catch (e) { /* sem armazenamento */ }
  document.body.classList.toggle("simples", !av);
  const b = $("#b-modo");
  if (b) b.querySelector("span").textContent = NO_IPHONE ? (av ? "Simples" : "Mais") : (av ? "Modo simples" : "Mais ferramentas");
}
$("#b-modo").onclick = () => {
  let av = false;
  try { av = localStorage.getItem("ds_avancado") === "1"; localStorage.setItem("ds_avancado", av ? "0" : "1"); } catch (e) { /* segue */ }
  aplicarModo();
  if (typeof dados !== "undefined" && dados && atual && !$("#projeto").hidden) abrir(atual);
};
aplicarModo();

// ---------------------------------------------------------------- Galeria (só peças validadas)

let galFiltro = "", vidEstado = null, vidPerfil = "";
const ESTADOS = [["melhores", "★ Melhores"], ["finais", "Finais"], ["previas", "Prévias"], ["postados", "Postados"], ["todos", "Todos"]];
const NOMES_CAT = { video: "Vídeos", stories: "Stories", carrossel: "Carrosséis", post: "Posts", tv: "TV" };
const urlPeca = (i) => `/arquivo?p=${encodeURIComponent(i.projeto)}&f=${encodeURIComponent(i.arquivo)}`;
const capaPeca = (i) => `/miniatura.jpg?p=${encodeURIComponent(i.projeto)}&f=${encodeURIComponent(i.arquivo)}`;
const melhor = (i) => i.validado || ["aprovado", "agendado", "postado"].includes(i.status);

function cartaoVideo(i, k) {
  const selo = i.status === "postado" ? "postado" : i.validado ? "★ validado" : i.previa ? "prévia" : i.status === "agendado" ? "agendado" : "final";
  return `<figure class="gal-item ${i.categoria === "tv" ? "deitado" : ""}" data-k="${k}">
      <div class="gal-capa"><img loading="lazy" src="${capaPeca(i)}" alt=""><span class="play">▶</span>
        <span class="gal-status ${melhor(i) ? "bom" : ""}">${selo}</span></div>
      <figcaption><b>${esc(i.titulo)}</b><span>${esc(i.versao)}${i.views ? " · " + Number(i.views).toLocaleString("pt-BR") + " views" : ""}</span></figcaption>
    </figure>`;
}

function ligarCartoes(raiz, lista) {
  raiz.querySelectorAll(".gal-item").forEach((el) => {
    const i = lista[+el.dataset.k];
    const cap = el.querySelector(".gal-capa");
    if (matchMedia("(hover: hover)").matches) {       // no Mac: passa o mouse e o vídeo toca
      el.onmouseenter = () => { if (!cap.querySelector("video")) cap.insertAdjacentHTML("beforeend", `<video src="${urlPeca(i)}" muted autoplay loop playsinline></video>`); };
      el.onmouseleave = () => { const v = cap.querySelector("video"); if (v) v.remove(); };
    }
    el.onclick = () => abrirPeca(i, urlPeca(i));
  });
}

window.carregarGaleria = async () => {
  const itens = (await api("/api/videos")).map((i) => ({ ...i, video: true }));
  if (vidEstado === null) vidEstado = itens.some(melhor) ? "melhores" : "todos";
  const contar = { melhores: itens.filter(melhor).length, finais: itens.filter((i) => !i.previa).length,
                   previas: itens.filter((i) => i.previa).length, postados: itens.filter((i) => i.status === "postado").length, todos: itens.length };
  $("#vid-estado").innerHTML = ESTADOS.map(([k, n]) => `<button class="chip ${k === vidEstado ? "ativo" : ""}" data-e="${k}">${n} <span>${contar[k]}</span></button>`).join("");
  $$("#vid-estado .chip").forEach((b) => b.onclick = () => { vidEstado = b.dataset.e; window.carregarGaleria(); });
  const cats = Object.keys(NOMES_CAT).filter((c) => itens.some((i) => i.categoria === c));
  $("#gal-filtro").innerHTML = cats.length > 1 ? [["", "Todos os tipos"], ...cats.map((c) => [c, NOMES_CAT[c]])].map(([c, n]) =>
    `<button class="chip ${c === galFiltro ? "ativo" : ""}" data-c="${c}">${n}</button>`).join("") : "";
  $$("#gal-filtro .chip").forEach((b) => b.onclick = () => { galFiltro = b.dataset.c; window.carregarGaleria(); });
  const perfis = [...new Set(itens.map((i) => i.conta).filter(Boolean))];
  $("#vid-perfil").innerHTML = perfis.length > 1 ? [["", "Todos os perfis"], ...perfis.map((u) => [u, "@" + u])].map(([u, n]) =>
    `<button class="chip ${u === vidPerfil ? "ativo" : ""}" data-u="${esc(u)}">${esc(n)}</button>`).join("") : "";
  $$("#vid-perfil .chip").forEach((b) => b.onclick = () => { vidPerfil = b.dataset.u; window.carregarGaleria(); });
  const busca = ($("#gal-busca").value || "").toLowerCase();
  const filtroEstado = { melhores: melhor, finais: (i) => !i.previa, previas: (i) => i.previa, postados: (i) => i.status === "postado", todos: () => true }[vidEstado];
  const lista = itens.filter(filtroEstado).filter((i) => !galFiltro || i.categoria === galFiltro).filter((i) => !vidPerfil || i.conta === vidPerfil)
    .filter((i) => !busca || (i.titulo + " " + (i.tags || []).join(" ") + " " + i.versao).toLowerCase().includes(busca));
  if ($("#gal-ordem").value === "views") lista.sort((a, b) => (b.views || 0) - (a.views || 0));
  const vazio = vidEstado === "melhores"
    ? '<p class="dica">Ainda não há vídeos validados. Nas versões de um projeto, toque em ★ Validar no vídeo que ficou bom.</p>'
    : '<p class="dica">Nenhum vídeo aqui ainda. Crie uma edição em <b>Nova edição</b> ou importe a pasta antiga.</p>';
  const grade = $("#gal-grade");
  if (!lista.length) { grade.className = "galeria"; grade.innerHTML = vazio; return; }
  if ($("#gal-agrupar").checked) {
    const grupos = [];
    lista.forEach((i, k) => { let g = grupos.find((x) => x.projeto === i.projeto); if (!g) grupos.push(g = { projeto: i.projeto, titulo: i.titulo, itens: [] }); g.itens.push([i, k]); });
    grade.className = "galeria-grupos";
    grade.innerHTML = grupos.map((g) => `<div class="grupo"><div class="linha-titulo"><h3>${esc(g.titulo)} <span class="dica">${g.itens.length}</span></h3>
        <button class="link" data-abrir="${esc(g.projeto)}">abrir projeto</button></div>
        <div class="galeria faixa">${g.itens.map(([i, k]) => cartaoVideo(i, k)).join("")}</div></div>`).join("");
    $$("[data-abrir]").forEach((b) => b.onclick = () => { mostrarTela("projetos"); abrir(b.dataset.abrir); });
  } else {
    grade.className = "galeria";
    grade.innerHTML = lista.map(cartaoVideo).join("");
  }
  ligarCartoes(grade, lista);
};

function abrirPeca(i, url) {
  const m = document.createElement("div");
  m.className = "modal";
  m.innerHTML = `<div class="modal-caixa ${i.categoria === "tv" ? "deitado" : ""}">
      ${i.video ? `<video src="${url}" controls autoplay playsinline loop></video>`
        : `<img src="/miniatura.jpg?p=${encodeURIComponent(i.projeto)}&f=${encodeURIComponent(i.arquivo)}" alt="">`}
      <div class="modal-info"><h2>${esc(i.titulo)}</h2><p class="dica">${esc(i.versao)} · ${esc(i.status || "validado")}</p>
        <div class="linha"><button class="dourado" data-a="editar">✎ Editar</button><button data-a="salvar">⤓ Salvar</button>
          ${i.status !== "postado" ? '<button data-a="postei">✓ Postei</button>' : ""}
          <button data-a="validar">${i.validado ? "★ Tirar dos melhores" : "★ Validar"}</button>
          <button data-a="tv">${i.na_tv || (i.categoria === "tv" && !i.previa && i.na_tv !== false) ? "📺 Tirar da TV" : "📺 Na TV"}</button><button data-a="fechar" class="link">fechar</button></div></div></div>`;
  document.body.appendChild(m);
  const fechar = () => m.remove();
  m.onclick = (e) => { if (e.target === m) fechar(); };
  m.querySelector('[data-a="fechar"]').onclick = fechar;
  m.querySelector('[data-a="editar"]').onclick = () => { fechar(); mostrarTela("projetos"); abrir(i.projeto); };
  m.querySelector('[data-a="salvar"]').onclick = () => salvarNaGaleria(url, i.arquivo.split("/").pop());
  const pb = m.querySelector('[data-a="postei"]');
  if (pb) pb.onclick = async () => {
    const link = prompt("Link do post (opcional):", ""); if (link === null) return;
    await api("/api/publicacao", { p: i.projeto, versao: i.versao, campos: { status: "postado", link: link || undefined } });
    fechar(); window.carregarGaleria();
  };
  m.querySelector('[data-a="tv"]').onclick = async () => {
    const naTv = i.na_tv || (i.categoria === "tv" && !i.previa && i.na_tv !== false);
    await api("/api/publicacao", { p: i.projeto, versao: i.versao, arquivo: i.arquivo, campos: { na_tv: !naTv } });
    alert(naTv ? "Saiu da Divine TV." : "Entrou na Divine TV (endereço /tv).");
    fechar(); window.carregarGaleria();
  };
  m.querySelector('[data-a="validar"]').onclick = async () => {
    await api("/api/publicacao", { p: i.projeto, versao: i.versao, arquivo: i.arquivo,
                                   campos: i.validado ? { validado: null } : { validado: true, gostei: true } });
    fechar(); window.carregarGaleria();
  };
}

// ---------------------------------------------------------------- importar a pasta antiga
async function importar(simular) {
  const out = $("#imp-resultado");
  out.innerHTML = '<p class="dica">Lendo a pasta…</p>';
  try {
    const r = await api("/api/importar", { origem: $("#imp-origem").value.trim(), copiar: $("#imp-copiar").checked, simular });
    out.innerHTML = `<p class="dica">${esc(r.origem)} · ${esc(r.modo)} · ${r.projetos.length} projeto(s)</p><ul class="aprendi">${r.projetos.map((x) =>
      `<li><b>${esc(x.titulo)}</b>: ${x.editados} editado(s), ${x.brutos} bruto(s)${x.prontos ? `, ${x.prontos} pronto(s) para postar` : ""}${x.uso_interno ? " · uso interno" : ""}</li>`).join("")}</ul>`;
    if (!simular) carregarLista();
  } catch (err) { out.innerHTML = `<p class="aviso-ia">${esc(err.message)}</p>`; }
}
$("#imp-simular").onclick = () => importar(true);
$("#imp-ok").onclick = () => importar(false);

$("#gal-busca").oninput = () => window.carregarGaleria();
$("#gal-ordem").onchange = () => window.carregarGaleria();
$("#gal-agrupar").onchange = () => window.carregarGaleria();

// ---------------------------------------------------------------- Início
// um passo só: soltou o vídeo bruto, o app cria o projeto, envia e já começa a edição automática
async function edicaoRapida(arquivos) {
  arquivos = [...arquivos].filter((f) => f.type.startsWith("video") || /\.(mov|mp4|m4v)$/i.test(f.name));
  if (!arquivos.length) return aviso("Escolha um vídeo (.mov ou .mp4).", "erro");
  const d = new Date();
  const titulo = $("#ini-tema").value.trim() || `Vídeo ${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}h${String(d.getMinutes()).padStart(2, "0")}`;
  const msg = $("#ini-envio");
  try {
    const { nome } = await api("/api/nova_edicao", { tipo: $("#ini-epico").checked ? "epico" : "video", titulo });
    for (const [k, f] of arquivos.entries()) {
      const mb = (f.size / 1e6).toFixed(0);
      await enviarArquivo(nome, f, (x) => {
        msg.innerHTML = `<div class="barra-envio"><i style="width:${Math.round(x * 100)}%"></i></div>
          Enviando ${esc(f.name)} (${k + 1} de ${arquivos.length}): ${Math.round(x * 100)}% de ${mb} MB${NO_IPHONE ? "<br><b>Deixe a tela acesa e o Safari aberto até terminar.</b>" : ""}`;
      });
    }
    msg.textContent = "Enviado. Começando a edição automática…";
    const { job } = await api("/api/acao", { p: nome, acao: "auto" });
    await carregarLista(); mostrarTela("projetos"); await abrir(nome);
    acompanhar(job, "Edição automática: transcrevendo, cortando e montando as 3 versões");
    msg.textContent = "";
  } catch (err) { msg.textContent = ""; aviso(err.message, "erro"); }
}
(() => {
  const z = $("#ini-soltar"); if (!z) return;
  $("#ini-arquivos").onchange = (e) => edicaoRapida(e.target.files);
  ["dragenter", "dragover"].forEach((ev) => z.addEventListener(ev, (e) => { e.preventDefault(); z.classList.add("sobre"); }));
  ["dragleave", "drop"].forEach((ev) => z.addEventListener(ev, (e) => { e.preventDefault(); z.classList.remove("sobre"); }));
  z.addEventListener("drop", (e) => edicaoRapida(e.dataTransfer.files));
})();

async function carregarInicio() {
  const h = new Date().getHours();
  $("#ini-ola").textContent = (h < 12 ? "Bom dia" : h < 18 ? "Boa tarde" : "Boa noite") + ", Renato";
  $("#ini-atalhos").innerHTML = EDICOES.slice(0, 5).map(([k, ic, nome, txt]) =>
    `<button class="atalho ${k === "epico" ? "epico" : ""}" data-tipo="${k}"><i>${ic}</i><b>${nome}</b><span>${esc(txt.split(":")[0].split(".")[0])}</span></button>`).join("")
    + '<button class="atalho" data-tipo="mais"><i>⋯</i><b>Mais tipos</b><span>post, TV, antes e depois, importar</span></button>';
  $$(".atalho").forEach((b) => b.onclick = () => {
    mostrarTela("nova");
    const f = $(`.tipo-edicao[data-tipo="${b.dataset.tipo}"]`);
    if (f) { f.scrollIntoView({ behavior: "smooth", block: "center" }); f.classList.add("destaque"); f.querySelector("input").focus(); setTimeout(() => f.classList.remove("destaque"), 1600); }
  });
  const [projs, prog, vids] = await Promise.all([api("/api/projetos"), api("/api/programacao"), api("/api/videos")]);
  const nomesCat = { video: "Vídeo", stories: "Stories", carrossel: "Carrossel", post: "Post", tv: "TV", antes_depois: "Antes e depois" };
  const recentes = projs.filter((p) => !p.pacote).sort((a, b) => b.nome.localeCompare(a.nome)).slice(0, 6);
  $("#ini-recentes").innerHTML = recentes.map((p) => `<button class="recente" data-p="${esc(p.nome)}">
      <b>${p.epico ? "✦ " : ""}${esc(p.titulo)}</b><span>${nomesCat[p.categoria] || "Vídeo"} · ${p.previas} prévia(s) · ${p.finais} final(is)</span></button>`).join("")
    || '<p class="dica">Nenhum projeto ainda. Comece por um dos atalhos acima.</p>';
  $$(".recente").forEach((b) => b.onclick = () => { mostrarTela("projetos"); abrir(b.dataset.p); });
  const fmt = (d) => d ? d.split("-").reverse().slice(0, 2).join("/") : "";
  const postar = prog.pecas.filter((p) => ["aprovado", "agendado"].includes(p.status) && !["consulta"].includes(p.rede))
    .sort((a, b) => (a.data_agendada || "9").localeCompare(b.data_agendada || "9")).slice(0, 6);
  $("#ini-postar").innerHTML = postar.map((p) => `<div class="mini-peca" data-p="${esc(p.projeto)}"><b>${esc(p.titulo)}</b>
      <span>${esc(p.versao)} · ${p.status === "agendado" ? "📅 " + fmt(p.data_agendada) : "pronto para postar"}</span></div>`).join("")
    || '<p class="dica">Nada esperando. Aprove uma versão e ela aparece aqui.</p>';
  $$(".mini-peca").forEach((el) => el.onclick = () => { mostrarTela("projetos"); abrir(el.dataset.p); });
  const ultimos = vids.slice(0, 10).map((i) => ({ ...i, video: true }));
  $("#ini-videos").innerHTML = ultimos.map(cartaoVideo).join("") || '<p class="dica">Os vídeos gerados aparecem aqui.</p>';
  ligarCartoes($("#ini-videos"), ultimos);
}

// ---------------------------------------------------------------- saúde do app
async function carregarSaude() {
  try {
    const d = await api("/api/diagnostico");
    $("#saude").innerHTML = d.map((x) => `<li>${x.ok ? "✓" : "•"} ${esc(x.item)}${x.ok ? "" : ` <span class="dica">(${esc(x.dica)})</span>`}</li>`).join("");
  } catch (err) { $("#saude").innerHTML = `<li class="dica">${esc(err.message)}</li>`; }
}
const _montarNova = montarNovaEdicao;
montarNovaEdicao = function () { _montarNova(); carregarSaude(); };

// ---------------------------------------------------------------- abrir no iPhone
$("#b-celular").onclick = async () => {
  const c = await api("/api/celular").catch(() => ({}));
  const m = document.createElement("div");
  m.className = "modal";
  const lista = c.enderecos || (c.endereco ? [{ url: c.endereco, onde: "no mesmo Wi-Fi" }] : []);
  const principal = lista[0];
  m.innerHTML = `<div class="cartao celular-modal"><h2>📱 Abrir no iPhone</h2>${c.ativo && principal
    ? `<ol class="celular-passos">
         <li>iPhone no <b>mesmo Wi-Fi</b> do Mac. Abra a <b>Câmera</b> e aponte para o código:</li>
       </ol>
       <img class="celular-qr" src="/qr.svg?u=${encodeURIComponent(principal.url)}" alt="" onerror="this.remove()">
       <p class="endereco">${esc(principal.url)}</p>
       ${c.codigo ? `<p>Código de acesso (só na primeira vez): <b class="endereco">${esc(c.codigo)}</b></p>` : ""}
       <ol class="celular-passos" start="2"><li>No Safari: <b>Compartilhar ⬆ > Adicionar à Tela de Início</b>. Vira um app com o ícone da Divine.</li>
         <li>Pronto: solte o vídeo bruto, aprove e poste pelo iPhone. As versões saem no Mac, que fica acordado enquanto o painel está aberto.</li></ol>
       ${lista.length > 1 ? `<details><summary class="dica">Outros endereços</summary>${lista.slice(1).map((e) => `<p class="dica"><b>${esc(e.url)}</b> · ${esc(e.onde)}</p>`).join("")}</details>` : ""}
       <p class="dica">Fora de casa (4G): mande o vídeo para a pasta <b>Divine Studio/Entrada</b> do Google Drive pelo app do Drive.
         O Mac edita sozinho e as versões esperam você aprovar. Para abrir o painel na rua, instale o Tailscale (grátis) no Mac e no iPhone.</p>`
    : `<p>O painel está aberto só neste Mac. Feche esta janela do Terminal e abra de novo o <b>Divine Studio.command</b>: ele já libera o iPhone.</p>`}
    <button class="dourado" data-f>Fechar</button></div>`;
  document.body.appendChild(m);
  m.onclick = (e) => { if (e.target === m || e.target.dataset.f !== undefined) m.remove(); };
};

// ---------------------------------------------------------------- atualizar e reiniciar
$("#b-atualizar").onclick = async () => {
  aviso("Procurando a versão nova...");
  try {
    const r = await api("/api/atualizar", {});
    if (!r.ok) return aviso(r.msg, "erro");
    if (!r.reiniciando) return aviso(r.msg);
    aviso(r.msg + " Reiniciando...");
    const esperar = async (n) => {
      try { await api("/api/projetos"); location.reload(); }
      catch (e) { if (n > 0) setTimeout(() => esperar(n - 1), 1000); }
    };
    setTimeout(() => esperar(30), 2500);
  } catch (err) { aviso(err.message, true); }
};

// ---------------------------------------------------------------- Instagram (várias contas)
async function estadoInstagram() {
  const c = await api("/api/instagram").catch(() => ({ contas: [] }));
  const lig = (c.contas || []).filter((x) => x.conectado);
  $("#pg-insta").textContent = lig.length ? "📷 " + lig.map((x) => "@" + x.usuario).join(" · ") : "Conectar Instagram";
  $("#pg-insta").classList.toggle("dourado", !lig.length);
  $("#pg-sinc").hidden = !lig.length;
  return c;
}
$("#pg-sinc").onclick = async () => {
  const b = $("#pg-sinc"); b.disabled = true; b.textContent = "Puxando…";
  try {
    const r = await api("/api/instagram/sincronizar", {});
    alert(`${r.atualizadas} post(s) com métricas novas.` + (r.erros && r.erros.length ? "\n" + r.erros.join("\n") : ""));
    carregarProgramacao();
  } catch (err) { alert(err.message); }
  b.disabled = false; b.textContent = "↻ Puxar métricas";
};
$("#pg-insta").onclick = async () => {
  const c = await estadoInstagram();
  const m = document.createElement("div");
  m.className = "modal";
  m.innerHTML = `<div class="cartao insta" style="max-width:600px"><h2>📷 Perfis do Instagram</h2>
    <div class="contas-ig">${(c.contas || []).map((x) => `<div class="conta-ig ${x.conectado ? "on" : ""}"><b>@${esc(x.usuario)}</b><span>${esc(x.nome)}</span>
      ${x.conectado ? `<em>conectado</em><button class="link" data-sair="${esc(x.usuario)}">desconectar</button>` : "<em>não conectado</em>"}</div>`).join("")}</div>
    <details ${(c.contas || []).every((x) => x.conectado) ? "" : "open"}><summary>Conectar uma conta</summary>
    <ol class="passo-a-passo">
      <li>Cada perfil (@dvmedicalspa e @drdanielmendess) precisa ser <b>profissional</b> (Empresa ou Criador) e estar ligado a uma <b>Página do Facebook</b>.</li>
      <li>Se as duas Páginas estão no mesmo Facebook (o seu), <b>um token só conecta os dois perfis</b> de uma vez.</li>
      <li>Em <b>developers.facebook.com</b> > Meus apps > Criar app (tipo "Empresa") > produto "Instagram".</li>
      <li><b>Ferramentas > Explorador da API do Graph</b>: gere um token com <code>instagram_basic</code>, <code>instagram_manage_insights</code>,
        <code>pages_show_list</code>, <code>pages_read_engagement</code>, marcando as duas Páginas quando o Facebook perguntar.</li>
      <li>Estenda para <b>60 dias</b> (ícone "i" > Depurador de token > Estender) e cole aqui. Se o Dr. Daniel administra a página dele
        em outro Facebook, gere um segundo token no Facebook dele e cole também: as contas se somam.</li>
    </ol>
    <textarea id="insta-token" placeholder="EAA..." rows="3"></textarea>
    <p class="dica">Os tokens ficam só no seu Mac (~/.divine_studio/instagram.json), nunca vão para o GitHub.</p>
    <div class="linha"><button class="dourado" data-ok>Conectar</button></div></details>
    <p id="insta-msg" class="dica"></p>
    <div class="linha">${(c.contas || []).some((x) => x.conectado) ? '<button data-sinc>↻ Puxar métricas agora</button>' : ""}<button data-f class="link">fechar</button></div></div>`;
  document.body.appendChild(m);
  const fechar = () => { m.remove(); estadoInstagram(); };
  m.onclick = (e) => { if (e.target === m || e.target.dataset.f !== undefined) fechar(); };
  m.querySelector("[data-ok]").onclick = async (e) => {
    const ok = e.target; ok.disabled = true; m.querySelector("#insta-msg").textContent = "Testando o token…";
    try {
      const r = await api("/api/instagram/conectar", { token: m.querySelector("#insta-token").value });
      m.querySelector("#insta-msg").textContent = `Conectado: ${r.novas.map((u) => "@" + u).join(" e ")}. ` +
        (r.sincronizado ? `${r.sincronizado.atualizadas} post(s) com métricas.` : (r.aviso || ""));
      setTimeout(() => { fechar(); $("#pg-insta").click(); }, 2200); carregarProgramacao();
    } catch (err) { m.querySelector("#insta-msg").textContent = err.message; ok.disabled = false; }
  };
  const sinc = m.querySelector("[data-sinc]");
  if (sinc) sinc.onclick = () => { fechar(); $("#pg-sinc").click(); };
  m.querySelectorAll("[data-sair]").forEach((b) => b.onclick = async () => {
    if (!confirm(`Desconectar @${b.dataset.sair} deste Mac?`)) return;
    await api("/api/instagram/desconectar", { usuario: b.dataset.sair }); fechar(); $("#pg-insta").click();
  });
};
const _carregarProg = carregarProgramacao;
carregarProgramacao = async function () { estadoInstagram(); return _carregarProg(); };


// ---------------------------------------------------------------- Crescimento (por perfil)
function sparkline(serie) {
  if (!serie || serie.length < 2) return "";
  const ys = serie.map((x) => x[1]), mn = Math.min(...ys), mx = Math.max(...ys), w = 220, h = 50;
  const pts = ys.map((y, k) => `${(k / (ys.length - 1)) * w},${h - ((y - mn) / Math.max(1, mx - mn)) * (h - 6) - 3}`).join(" ");
  return `<svg viewBox="0 0 ${w} ${h}" class="spark"><polyline points="${pts}" fill="none" stroke="currentColor" stroke-width="2"/></svg>`;
}
window.carregarCrescimento = async () => {
  const r = await api("/api/crescimento");
  $("#cresc-perfis").innerHTML = r.perfis.map((p) => {
    const pr = p.projecao;
    return `<div class="cartao cresc" data-c="${esc(p.conta)}"><div class="linha-titulo"><h2>@${esc(p.conta)}</h2><span class="dica">${esc(p.nome)}</span></div>
      ${pr.tem ? `<div class="cresc-num"><b>${Number(pr.atual).toLocaleString("pt-BR")}</b><span>seguidores</span>${sparkline(pr.serie)}</div>
        <p>Ritmo: <b>${pr.por_mes >= 0 ? "+" : ""}${pr.por_mes}</b>/mês · em 30 dias: <b>${Number(pr.em_30).toLocaleString("pt-BR")}</b> · em 90: <b>${Number(pr.em_90).toLocaleString("pt-BR")}</b></p>
        ${pr.meta_mes ? `<p class="${pr.no_ritmo ? "ok-txt" : "erro-txt"}">${pr.no_ritmo ? "✓ No ritmo da meta" : "Abaixo da meta"} de +${pr.meta_mes}/mês</p>` : ""}`
        : '<p class="dica">Sem histórico ainda: anote os seguidores de hoje.</p>'}
      <div class="linha"><input type="number" min="0" placeholder="seguidores hoje" class="cr-n"><button class="cr-ok">Anotar</button></div>
      <h3>Hoje</h3><ul class="plano">${p.plano.map((x) => `<li ${x.projeto ? `data-p="${esc(x.projeto)}"` : x.ir ? `data-ir="${x.ir}"` : ""}>${esc(x.acao)}
        ${x.stories ? '<button class="pb st-ok">✓ Fiz Stories</button>' : ""}</li>`).join("")}</ul>
      <h3>Metas da semana</h3><ul class="req">${p.requisitos.map((x) => `<li class="${x.ok ? "ok" : "nao"}">${x.ok ? "✓" : "○"} ${esc(x.item)}</li>`).join("")}</ul>
    </div>`;
  }).join("");
  $("#cresc-alg").innerHTML = r.algoritmo.sinais.map((x) => `<li><b>${esc(x.nome)}</b>: ${esc(x.dica)}</li>`).join("");
  $("#cresc-alg-data").innerHTML = `Atualizado em ${esc((r.algoritmo.atualizado_em || "").split("-").reverse().join("/"))} (revisado toda semana). Fontes: ` +
    r.algoritmo.fontes.map((f, k) => `<a href="${esc(f)}" target="_blank">${k + 1}</a>`).join(" · ");
  $$(".cresc").forEach((el) => {
    const conta = el.dataset.c;
    el.querySelector(".cr-ok").onclick = async () => {
      const n = el.querySelector(".cr-n").value; if (!n) return;
      await api("/api/crescimento/seguidores", { conta, n: Number(n) }); window.carregarCrescimento();
    };
    const st = el.querySelector(".st-ok");
    if (st) st.onclick = async (e) => { e.stopPropagation(); await api("/api/crescimento/stories", { conta }); window.carregarCrescimento(); };
    el.querySelectorAll(".plano li[data-p]").forEach((li) => li.onclick = () => { mostrarTela("projetos"); abrir(li.dataset.p); });
  });
};
$("#cr-puxar").onclick = async () => {
  try { const r = await api("/api/crescimento/puxar", {}); alert(Object.keys(r).length ? Object.entries(r).map(([u, n]) => `@${u}: ${n}`).join("\n") : "Conecte o Instagram em Programação para puxar sozinho."); window.carregarCrescimento(); }
  catch (err) { alert(err.message); }
};

// ---------------------------------------------------------------- versão rodando (e de qual pasta)
api("/api/versao").then((v) => {
  const el = $("#versao-app"); if (!el) return;
  el.textContent = v.git ? `· versão de ${v.data}` : "· pasta sem atualização automática";
  el.title = `Pasta: ${v.pasta}\nVersão: ${v.commit || "?"} (${v.ramo || "sem git"})`;
}).catch(() => {});
