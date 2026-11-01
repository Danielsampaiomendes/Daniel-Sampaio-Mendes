// Telas do topo: Projetos, Programação, IA e ideias, Referências, Biblioteca.
const TELAS = ["projetos", "programacao", "ia", "referencias", "biblioteca"];

function mostrarTela(nome) {
  $$(".topo nav button").forEach((b) => b.classList.toggle("ativa", b.dataset.tela === nome));
  const secoes = { programacao: "#programacao", ia: "#ia", referencias: "#referencias", biblioteca: "#biblioteca" };
  ["#vazio", "#projeto", "#carrossel", "#antesdepois", ...Object.values(secoes)].forEach((s) => { const el = $(s); if (el) el.hidden = true; });
  if (nome === "projetos") {
    if (atual) abrir(atual); else $("#vazio").hidden = false;
    return;
  }
  const el = $(secoes[nome]); if (el) el.hidden = false;
  const carregar = { programacao: carregarProgramacao, ia: window.carregarIA, referencias: window.carregarReferencias,
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
          ${p.entrega ? '<button class="pb" data-a="pasta">Pasta</button>' : ""}</div></div>`;
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
