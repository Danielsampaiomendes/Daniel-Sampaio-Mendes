// Telas do topo: Projetos, Programação, IA e ideias, Referências, Biblioteca.
const TELAS = ["projetos", "nova", "galeria", "programacao", "ia", "referencias", "biblioteca"];

function mostrarTela(nome) {
  $$(".topo nav button").forEach((b) => b.classList.toggle("ativa", b.dataset.tela === nome));
  const secoes = { nova: "#nova", galeria: "#galeria", programacao: "#programacao", ia: "#ia", referencias: "#referencias",
                   biblioteca: "#biblioteca" };
  ["#vazio", "#projeto", "#carrossel", "#antesdepois", ...Object.values(secoes)].forEach((s) => { const el = $(s); if (el) el.hidden = true; });
  if (nome === "projetos") {
    if (atual) abrir(atual); else $("#vazio").hidden = false;
    return;
  }
  const el = $(secoes[nome]); if (el) el.hidden = false;
  if (el && matchMedia("(max-width: 700px)").matches) el.scrollIntoView({ behavior: "smooth" });   // celular: vai direto
  const carregar = { nova: montarNovaEdicao, galeria: window.carregarGaleria, programacao: carregarProgramacao, ia: window.carregarIA, referencias: window.carregarReferencias,
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

async function carregarProgramacao() {
  const { pecas, aprendi } = await api("/api/programacao");
  const fmt = (d) => d ? d.split("-").reverse().join("/") : "";
  $("#pg-colunas").innerHTML = COLUNAS.map(([id, nome, f]) => {
    let lista = pecas.filter(f);
    if (id === "agendado") lista.sort((a, b) => (a.data_agendada || "").localeCompare(b.data_agendada || ""));
    if (id === "postado") lista.sort((a, b) => (b.data_postagem || "").localeCompare(a.data_postagem || ""));
    return `<div class="prog-col cartao"><h2>${nome} <span>${lista.length}</span></h2>${lista.map((p) => {
      const m = p.metricas || {};
      return `<div class="peca" data-p="${esc(p.projeto)}" data-v="${esc(p.versao)}">
        <div class="t">${esc(p.titulo)} · <b>${esc(p.versao)}</b></div>
        <div class="m">${esc(p.tipo === "carrossel" ? "carrossel" : p.tipo === "antes_depois" ? "antes e depois" : p.tipo === "post" ? "post " + p.versao : p.formato)}${p.data_agendada && id === "agendado" ? " · " + fmt(p.data_agendada) : ""}${p.data_postagem && id !== "agendado" ? " · postado " + fmt(p.data_postagem) : ""}${p.gostei ? " · ♥" : ""}</div>
        ${p.tags && p.tags.length ? `<div>${p.tags.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>` : ""}
        ${id === "postado" ? `<div class="metricas" title="Métricas do Instagram (o app aprende com elas)">
          ${[["alcance", "alcance"], ["curtidas", "curtidas"], ["comentarios", "coment."], ["compartilhamentos", "envios"], ["salvamentos", "salvos"], ["views", "views"]]
            .map(([k, r]) => `<input type="number" min="0" data-m="${k}" placeholder="${r}" value="${m[k] ?? ""}">`).join("")}</div>` : ""}
        <div class="pub">${id === "aprovado" || id === "agendado" ? '<button class="pb" data-a="postei">✓ Postei</button>' : ""}
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
  $$(".peca [data-a]").forEach((b) => b.onclick = async () => {
    const el = b.closest(".peca"), p = pecaDe(el);
    if (b.dataset.a === "salvar") return salvarNaGaleria(`/arquivo?p=${encodeURIComponent(p.projeto)}&f=${encodeURIComponent(p.arquivo)}`, p.arquivo.split("/").pop());
    if (b.dataset.a === "legenda") {
      const d = await api("/api/projeto?p=" + encodeURIComponent(p.projeto));
      if (!d.legenda) return alert("Este projeto ainda não tem legenda (gere em Relatório e legenda).");
      try { await navigator.clipboard.writeText(d.legenda); b.textContent = "Copiada ✓"; }
      catch (e) { prompt("Copie a legenda:", d.legenda); }
      return;
    }
    if (b.dataset.a === "pasta") return api("/api/abrir_pasta", { caminho: p.entrega }).catch((e) => alert(e.message));
    let campos;
    if (b.dataset.a === "postei") {
      const link = prompt("Link do post (opcional):", ""); if (link === null) return;
      campos = { status: "postado", link: link || undefined };
    } else {
      const d = prompt("Data da postagem (DD/MM):", ""); if (!d) return;
      const [dia, mes, ano] = d.split("/");
      campos = { status: "agendado", data_agendada: `${ano || new Date().getFullYear()}-${mes.padStart(2, "0")}-${dia.padStart(2, "0")}` };
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
  ["stories", "📱", "Stories", "Vídeo vertical para Stories, com área segura, enquete e chamada para o direct.", "ex.: Bastidores da manhã"],
  ["carrossel", "▦", "Carrossel", "Cards no padrão Divine com rascunho por fórmula (lista, mito x verdade, método…).", "ex.: 5 mitos do Laser de CO2"],
  ["post", "▣", "Post (imagem)", "Uma arte só, que sai de uma vez em Feed 4:5, Stories e TV.", "ex.: Endolaser nos braços"],
  ["tv", "📺", "TV da clínica", "Vídeo 16:9 calmo para a recepção, com legenda grande e sem pressa.", "ex.: Spa pedras quentes"],
  ["antes_depois", "◫", "Antes e depois", "Uso interno em consulta (nunca postar): fotos padronizadas em TV, Stories e Feed.", "ex.: Bumbum Up"],
];

let montarNovaEdicao = function () {
  $("#tipos-edicao").innerHTML = EDICOES.map(([k, ic, nome, txt, ex]) => `<form class="tipo-edicao ${k === "epico" ? "epico" : ""}" data-tipo="${k}">
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

// ---------------------------------------------------------------- Galeria (só peças validadas)

let galFiltro = "";
window.carregarGaleria = async () => {
  const itens = await api("/api/galeria");
  const nomes = { video: "Vídeos", stories: "Stories", carrossel: "Carrosséis", post: "Posts", tv: "TV" };
  const cats = Object.keys(nomes).filter((c) => itens.some((i) => i.categoria === c));
  $("#gal-filtro").innerHTML = [["", "Tudo"], ...cats.map((c) => [c, nomes[c]])].map(([c, n]) =>
    `<button class="chip ${c === galFiltro ? "ativo" : ""}" data-c="${c}">${n}</button>`).join("");
  $$("#gal-filtro .chip").forEach((b) => b.onclick = () => { galFiltro = b.dataset.c; window.carregarGaleria(); });
  const busca = ($("#gal-busca").value || "").toLowerCase();
  const lista = itens.filter((i) => !galFiltro || i.categoria === galFiltro)
    .filter((i) => !busca || (i.titulo + " " + (i.tags || []).join(" ") + " " + i.versao).toLowerCase().includes(busca));
  if ($("#gal-ordem").value === "views") lista.sort((a, b) => (b.views || 0) - (a.views || 0));
  const url = (i) => `/arquivo?p=${encodeURIComponent(i.projeto)}&f=${encodeURIComponent(i.arquivo)}`;
  const capa = (i) => `/miniatura.jpg?p=${encodeURIComponent(i.projeto)}&f=${encodeURIComponent(i.arquivo)}`;
  const selo = { postado: "postado", agendado: "agendado", aprovado: "pronto" };
  $("#gal-grade").innerHTML = lista.map((i, k) => `<figure class="gal-item ${i.categoria === "tv" ? "deitado" : ""}" data-k="${k}">
      <div class="gal-capa"><img loading="lazy" src="${capa(i)}" alt="">${i.video ? '<span class="play">▶</span>' : ""}
        <span class="gal-status">${selo[i.status] || "★ validado"}</span></div>
      <figcaption><b>${esc(i.titulo)}</b><span>${esc(i.versao)}${i.views ? " · " + Number(i.views).toLocaleString("pt-BR") + " views" : ""}</span></figcaption>
    </figure>`).join("") || '<p class="dica">A galeria mostra só o que chegou a uma boa edição. Nas versões do projeto, clique em ★ Validar (ou exporte a final).</p>';
  $$(".gal-item").forEach((el) => {
    const i = lista[+el.dataset.k];
    const cap = el.querySelector(".gal-capa");
    if (i.video && matchMedia("(hover: hover)").matches) {       // no Mac: passa o mouse e o vídeo toca
      el.onmouseenter = () => { if (!cap.querySelector("video")) cap.insertAdjacentHTML("beforeend", `<video src="${url(i)}" muted autoplay loop playsinline></video>`); };
      el.onmouseleave = () => { const v = cap.querySelector("video"); if (v) v.remove(); };
    }
    el.onclick = () => abrirPeca(i, url(i));
  });
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
          <button data-a="tirar" class="link">tirar da galeria</button><button data-a="fechar" class="link">fechar</button></div></div></div>`;
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
  m.querySelector('[data-a="tirar"]').onclick = async () => {
    await api("/api/publicacao", { p: i.projeto, versao: i.versao, campos: { validado: null, ...(i.status === "aprovado" ? { status: "rascunho" } : {}) } });
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
  m.innerHTML = `<div class="cartao" style="max-width:440px"><h2>📱 Abrir no iPhone</h2>${c.ativo
    ? `<p>No Safari do iPhone, no <b>mesmo Wi-Fi</b>:</p><p class="endereco">${esc(c.endereco)}</p>
       ${c.codigo ? `<p>Código de acesso: <b class="endereco">${esc(c.codigo)}</b></p>` : ""}
       <p class="dica">Depois: Compartilhar > Adicionar à Tela de Início. O Mac precisa ficar ligado com o painel aberto.</p>`
    : `<p>O painel está aberto só neste Mac. Feche e abra com <b>Divine Studio iPhone.command</b>: ele mostra o endereço e o código para o celular.</p>`}
    <button class="dourado" data-f>Fechar</button></div>`;
  document.body.appendChild(m);
  m.onclick = (e) => { if (e.target === m || e.target.dataset.f !== undefined) m.remove(); };
};
