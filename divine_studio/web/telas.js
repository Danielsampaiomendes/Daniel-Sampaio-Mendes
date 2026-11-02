// Telas do topo: Projetos, Programação, IA e ideias, Referências, Biblioteca.
const TELAS = ["inicio", "nova", "projetos", "galeria", "programacao", "ia", "referencias", "biblioteca"];

function mostrarTela(nome) {
  $$(".topo nav button").forEach((b) => b.classList.toggle("ativa", b.dataset.tela === nome));
  const secoes = { inicio: "#vazio", nova: "#nova", galeria: "#galeria", programacao: "#programacao", ia: "#ia",
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
  const carregar = { inicio: carregarInicio, nova: montarNovaEdicao, galeria: window.carregarGaleria, programacao: carregarProgramacao, ia: window.carregarIA, referencias: window.carregarReferencias,
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

let galFiltro = "", vidEstado = null;
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
  const busca = ($("#gal-busca").value || "").toLowerCase();
  const filtroEstado = { melhores: melhor, finais: (i) => !i.previa, previas: (i) => i.previa, postados: (i) => i.status === "postado", todos: () => true }[vidEstado];
  const lista = itens.filter(filtroEstado).filter((i) => !galFiltro || i.categoria === galFiltro)
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
          <button data-a="validar">${i.validado ? "★ Tirar dos melhores" : "★ Validar"}</button><button data-a="fechar" class="link">fechar</button></div></div></div>`;
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
  m.innerHTML = `<div class="cartao" style="max-width:440px"><h2>📱 Abrir no iPhone</h2>${c.ativo
    ? `<p>No Safari do iPhone, no <b>mesmo Wi-Fi</b>:</p><p class="endereco">${esc(c.endereco)}</p>
       ${c.codigo ? `<p>Código de acesso: <b class="endereco">${esc(c.codigo)}</b></p>` : ""}
       <p class="dica">Depois: Compartilhar > Adicionar à Tela de Início. O Mac precisa ficar ligado com o painel aberto.</p>`
    : `<p>O painel está aberto só neste Mac. Feche e abra com <b>Divine Studio iPhone.command</b>: ele mostra o endereço e o código para o celular.</p>`}
    <button class="dourado" data-f>Fechar</button></div>`;
  document.body.appendChild(m);
  m.onclick = (e) => { if (e.target === m || e.target.dataset.f !== undefined) m.remove(); };
};

// ---------------------------------------------------------------- Instagram
async function estadoInstagram() {
  const c = await api("/api/instagram").catch(() => ({}));
  $("#pg-insta").textContent = c.conectado ? `📷 @${c.usuario || "conectado"}` : "Conectar Instagram";
  $("#pg-insta").classList.toggle("dourado", !c.conectado);
  $("#pg-sinc").hidden = !c.conectado;
  return c;
}
$("#pg-sinc").onclick = async () => {
  const b = $("#pg-sinc"); b.disabled = true; b.textContent = "Puxando…";
  try { const r = await api("/api/instagram/sincronizar", {}); alert(`${r.atualizadas} post(s) atualizado(s) com as métricas do Instagram.`); carregarProgramacao(); }
  catch (err) { alert(err.message); }
  b.disabled = false; b.textContent = "↻ Puxar métricas";
};
$("#pg-insta").onclick = async () => {
  const c = await estadoInstagram();
  const m = document.createElement("div");
  m.className = "modal";
  m.innerHTML = `<div class="cartao insta" style="max-width:560px">${c.conectado
    ? `<h2>📷 Instagram conectado</h2><p>Conta <b>@${esc(c.usuario)}</b>. O app puxa views, alcance, curtidas, comentários, envios e
       salvamentos dos posts marcados como ✓ Postei (com o link) e aprende com eles.</p>
       <div class="linha"><button class="dourado" data-sinc>↻ Puxar métricas agora</button><button data-sair class="link">desconectar</button>
       <button data-f class="link">fechar</button></div>`
    : `<h2>📷 Conectar o Instagram</h2>
       <ol class="passo-a-passo">
         <li>A conta <b>@dvmedicalspa</b> precisa ser <b>profissional</b> (Empresa ou Criador) e estar ligada a uma <b>Página do Facebook</b>.</li>
         <li>No computador, abra <b>developers.facebook.com</b> > Meus apps > Criar app (tipo "Empresa").</li>
         <li>No app, adicione o produto <b>"Instagram"</b> e, em <b>Ferramentas > Explorador da API do Graph</b>, gere um token com:
           <code>instagram_basic</code>, <code>instagram_manage_insights</code>, <code>pages_show_list</code>, <code>pages_read_engagement</code>.</li>
         <li>Troque por um token de <b>longa duração</b> (60 dias): no Explorador, ícone "i" > Abrir no Depurador de token > Estender.</li>
         <li>Cole o token aqui embaixo. O app acha a conta sozinho.</li>
       </ol>
       <textarea id="insta-token" placeholder="EAA..." rows="3"></textarea>
       <p class="dica">O token fica só no seu Mac (~/.divine_studio/instagram.json), nunca vai para o GitHub.</p>
       <div class="linha"><button class="dourado" data-ok>Conectar</button><button data-f class="link">fechar</button></div>
       <p id="insta-msg" class="dica"></p>`}</div>`;
  document.body.appendChild(m);
  const fechar = () => { m.remove(); estadoInstagram(); };
  m.onclick = (e) => { if (e.target === m || e.target.dataset.f !== undefined) fechar(); };
  const ok = m.querySelector("[data-ok]");
  if (ok) ok.onclick = async () => {
    ok.disabled = true; m.querySelector("#insta-msg").textContent = "Testando o token…";
    try {
      const r = await api("/api/instagram/conectar", { token: m.querySelector("#insta-token").value });
      m.querySelector("#insta-msg").textContent = `Conectado: @${r.usuario}. ` + (r.sincronizado ? `${r.sincronizado.atualizadas} post(s) com métricas.` : (r.aviso || ""));
      setTimeout(fechar, 2500); carregarProgramacao();
    } catch (err) { m.querySelector("#insta-msg").textContent = err.message; ok.disabled = false; }
  };
  const sinc = m.querySelector("[data-sinc]");
  if (sinc) sinc.onclick = () => { fechar(); $("#pg-sinc").click(); };
  const sair = m.querySelector("[data-sair]");
  if (sair) sair.onclick = async () => { if (confirm("Desconectar o Instagram deste Mac?")) { await api("/api/instagram/desconectar", {}); fechar(); } };
};
const _carregarProg = carregarProgramacao;
carregarProgramacao = async function () { estadoInstagram(); return _carregarProg(); };
