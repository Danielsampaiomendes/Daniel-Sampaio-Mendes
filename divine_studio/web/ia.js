// Chat com a IA (no projeto e na tela IA e ideias) e tela de Referências.
let iaEstado = null;

const ATALHOS_PROJETO = [
  ["Melhorar os hooks", "Proponha 3 hooks mais fortes para este vídeo (um positivo, um de curiosidade, um negativo), no padrão Divine, e aplique nas versões."],
  ["Ajustar a ideia", "Como deixar a ideia deste vídeo mais forte e com um objetivo só? Proponha o ajuste e as mensagens."],
  ["Olhar o vídeo", "Olhe os quadros da versão mais recente e diga o que prende e o que solta a atenção, com 3 ajustes concretos."],
  ["Roteiro de gravação", "Monte o roteiro de gravação deste vídeo seguindo a skill divine-sequencia-gravacao (planos, entrada com movimento, texto de impacto)."],
  ["Legenda", "Escreva a legenda do post seguindo a skill divine-instagram-pro (gancho na dobra de 125 caracteres, um CTA, aviso e RT)."],
];
const ATALHOS_GERAL = [
  ["Ideias da semana", "Me dê 5 ideias de Reels para esta semana, equilibrando salvar e enviar, cada uma com hook e objetivo."],
  ["Transformar em vídeo", "Quero transformar a melhor ideia desta conversa em projeto: monte o hook das 3 versões, mensagens, objetivo e roteiro."],
  ["Trend da vez", "Que formato está funcionando no Instagram que dá para adaptar ao padrão Divine sem perder a elegância?"],
];

async function estadoIA() {
  if (!iaEstado) iaEstado = await api("/api/ia/estado");
  return iaEstado;
}

async function montarChat(caixa, opts) {
  const est = await estadoIA();
  const atalhos = opts.p ? ATALHOS_PROJETO : ATALHOS_GERAL;
  caixa.innerHTML = `${est.ok ? "" : `<p class="aviso-ia">${esc(est.motivo)}</p>`}
    <div class="msgs"></div>
    <div class="rapidos">${atalhos.map(([r, t]) => `<button data-t="${esc(t)}" data-olhar="${r === "Olhar o vídeo" ? 1 : ""}">${esc(r)}</button>`).join("")}
      <button class="link" data-nova>nova conversa</button></div>
    <div class="entrada"><textarea placeholder="Fale com a IA: o que precisa melhorar, uma ideia para discutir, um hook para ajustar…"></textarea>
      <button class="dourado" data-enviar>Enviar</button></div>`;
  const msgs = caixa.querySelector(".msgs"), campo = caixa.querySelector("textarea");
  const q = `?${opts.p ? "p=" + encodeURIComponent(opts.p) : ""}${opts.c ? "&c=" + opts.c : ""}`;
  const desenhar = (lista) => {
    msgs.innerHTML = lista.map((m) => `<div class="msg ${m.papel}">${esc(m.texto)}${m.sugestao ? sugestaoHtml(m.sugestao, opts) : ""}</div>`).join("")
      || '<p class="dica">Comece por um dos atalhos ou escreva o que quiser.</p>';
    msgs.scrollTop = 1e9;
    msgs.querySelectorAll("[data-aplicar]").forEach((b) => b.onclick = () => aplicarSugestao(JSON.parse(b.dataset.aplicar), opts));
  };
  desenhar(await api("/api/ia/conversa" + q));
  const enviar = async (texto, olhar) => {
    if (!texto.trim()) return;
    msgs.insertAdjacentHTML("beforeend", `<div class="msg user">${esc(texto)}</div><div class="msg assistant">pensando…</div>`);
    msgs.scrollTop = 1e9; campo.value = "";
    caixa.querySelectorAll("button").forEach((b) => b.disabled = true);
    try {
      await api("/api/ia/mensagem", { p: opts.p, c: opts.c, mensagem: texto, olhar_video: !!olhar });
      desenhar(await api("/api/ia/conversa" + q));
    } catch (err) {
      msgs.lastElementChild.textContent = err.message;
    } finally { caixa.querySelectorAll("button").forEach((b) => b.disabled = false); }
  };
  caixa.querySelector("[data-enviar]").onclick = () => enviar(campo.value);
  campo.onkeydown = (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) enviar(campo.value); };
  caixa.querySelectorAll("[data-t]").forEach((b) => b.onclick = () => enviar(b.dataset.t, b.dataset.olhar));
  caixa.querySelector("[data-nova]").onclick = async () => {
    if (!confirm("Começar uma conversa nova? A atual fica guardada em _arquivo/.")) return;
    await api("/api/ia/nova_conversa", { p: opts.p, c: opts.c }); montarChat(caixa, opts);
  };
}

function sugestaoHtml(s, opts) {
  const partes = [];
  (s.hooks || []).forEach((h) => partes.push(`${h.nome}: ${(h.hook || []).map((b) => b.titulo).join(" → ")}`));
  (s.mensagens || []).forEach((m) => partes.push(`Mensagem: ${m.titulo}${m.apoio ? " (" + m.apoio + ")" : ""}`));
  ["selo", "cta_antecipado", "objetivo"].forEach((k) => s[k] && partes.push(`${k}: ${s[k]}`));
  if (s.fechamento && s.fechamento.frase) partes.push(`Fechamento: ${s.fechamento.frase}`);
  if (s.roteiro) partes.push(`Roteiro:\n${s.roteiro}`);
  if (s.legenda) partes.push(`Legenda:\n${s.legenda}`);
  const dados = esc(JSON.stringify(s));
  const botao = opts.p ? `<button class="dourado" data-aplicar="${dados}">Aplicar no projeto</button>`
    : `<button class="dourado" data-aplicar="${dados}">Criar projeto com esta ideia</button>`;
  return `<div class="sug"><b>Sugestão</b><pre>${esc(partes.join("\n"))}</pre>${botao}</div>`;
}

async function aplicarSugestao(s, opts) {
  try {
    if (opts.p) {
      const r = await api("/api/ia/aplicar", { p: opts.p, sugestao: s });
      alert(`Aplicado: ${r.mudou.join(", ") || "nada mudou"}. Gere as prévias para ver.`);
      abrir(opts.p);
    } else {
      const r = await api("/api/ia/criar_projeto", { sugestao: s });
      await carregarLista(); mostrarTela("projetos"); abrir(r.nome);
    }
  } catch (err) { alert(err.message); }
}

// chat dentro do projeto (aba IA)
document.querySelector('[data-aba="ia"]').addEventListener("click", () => montarChat($("#chat-projeto"), { p: atual }));

// tela IA e ideias
window.carregarIA = () => montarChat($("#chat-geral"), { c: "geral" });
$("#ia-desempenho").onclick = async () => {
  const b = $("#ia-desempenho"); b.disabled = true; b.textContent = "Analisando…";
  try {
    const est = await estadoIA();
    if (est.instagram) await api("/api/instagram/sincronizar", {}).catch(() => {});
    await api("/api/ia/desempenho", {});
    montarChat($("#chat-geral"), { c: "desempenho" });
  } catch (err) { alert(err.message); }
  finally { b.disabled = false; b.textContent = "Analisar desempenho no Instagram"; }
};

// ---------------------------------------------------------------- Referências

window.carregarReferencias = async () => {
  const lista = await api("/api/referencias");
  $("#ref-lista").innerHTML = lista.map((r) => `<div class="cartao ref" data-r="${esc(r.pasta)}">
      <div class="linha-titulo"><h2>${esc(r.titulo || r.pasta)}</h2><span class="tag">${esc(r.status)}</span>
        <button data-acao-ref="analisar">${r.analise ? "Analisar de novo" : "Analisar com IA"}</button>
        ${r.sugestao || r.status === "analisada" ? '<button class="dourado" data-acao-ref="incorporar">Incorporar ao app</button>' : ""}</div>
      ${r.link ? `<a href="${esc(r.link)}" target="_blank">${esc(r.link)}</a>` : ""}
      ${r.nota ? `<p>${esc(r.nota)}</p>` : ""}
      <div class="arqs">${r.arquivos.map((f) => /\.(mp4|mov|m4v|webm)$/i.test(f)
        ? `<video src="/referencia?r=${encodeURIComponent(r.pasta)}&f=${encodeURIComponent(f)}" controls playsinline preload="metadata"></video>`
        : `<img src="/referencia?r=${encodeURIComponent(r.pasta)}&f=${encodeURIComponent(f)}">`).join("")}</div>
      ${r.analise ? `<details><summary>Raio-X da IA</summary><div class="md">${md(r.analise)}</div></details>` : ""}
    </div>`).join("") || '<p class="dica">Nenhuma referência ainda.</p>';
  $$("[data-acao-ref]").forEach((b) => b.onclick = async () => {
    const nome = b.closest(".ref").dataset.r;
    b.disabled = true; b.textContent = b.dataset.acaoRef === "analisar" ? "Analisando… (até 1 min)" : "Incorporando…";
    try {
      const r = await api(`/api/referencias/${b.dataset.acaoRef}`, { nome });
      if (b.dataset.acaoRef === "incorporar") alert(`${r.hooks.length} hook(s) no banco e ${r.ideias} ideia(s) em docs/IDEIAS_DO_APP.md.`);
    } catch (err) { alert(err.message); }
    window.carregarReferencias();
  });
};

$("#ref-form").onsubmit = async (e) => {
  e.preventDefault();
  try {
    const { nome } = await api("/api/referencias/nova", { titulo: $("#ref-titulo").value, link: $("#ref-link").value, nota: $("#ref-nota").value });
    for (const f of $("#ref-arquivos").files) {
      const r = await fetch(`/api/upload?ref=${encodeURIComponent(nome)}&nome=${encodeURIComponent(f.name)}`, { method: "POST", body: f });
      if (!r.ok) alert((await r.json()).erro);
    }
    e.target.reset(); window.carregarReferencias();
  } catch (err) { alert(err.message); }
};
