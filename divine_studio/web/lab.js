// Laboratório viral: plano de testes, Radar (o que viraliza lá fora), placar dos formatos, caixa de entrada,
// TikTok e automações.
let labDados = null;

function modal(html, largura = 640) {
  const m = document.createElement("div");
  m.className = "modal";
  m.innerHTML = `<div class="cartao" style="max-width:${largura}px;width:100%;max-height:90vh;overflow:auto">${html}</div>`;
  m.onclick = (e) => { if (e.target === m || e.target.dataset.fechar !== undefined) m.remove(); };
  document.body.appendChild(m);
  return m;
}

window.carregarLab = async function () {
  const conta = $("#lab-conta").value;
  try { labDados = await api("/api/lab" + (conta ? "?conta=" + encodeURIComponent(conta) : "")); }
  catch (err) { aviso(err.message, "erro"); return; }
  const d = labDados;
  $("#lab-plano").innerHTML = d.plano.map((x) => `<div class="lab-dia">
      <div class="dica">${esc(x.dia)} · ${esc(x.ata || "")}</div><b>${esc(x.nome)}</b>
      <p class="g">“${esc(x.gancho)}”</p><p class="dica">${esc(x.motivo)}</p>
      <p class="dica">medir: ${esc(x.medir)}${x.edicao && x.edicao.estilo_edicao ? " · estilo " + esc(x.edicao.estilo_edicao) : ""}</p>
      <button class="dourado" data-criar="${esc(x.formato)}">Criar este teste</button></div>`).join("");
  $$("#lab-plano [data-criar]").forEach((b) => b.onclick = () => criarTeste(b.dataset.criar));

  $("#lab-placar").innerHTML = `<table><tr><th>Formato</th><th>Status</th><th>Testes</th><th>Vitórias</th><th>Alcance</th>
      <th>Envios %</th><th>Salvos %</th><th>Retenção</th><th>Seguidores %</th><th>Radar</th></tr>${d.placar.map((x) => `<tr class="st-${esc(x.status.split(" ")[0])}">
      <td>${esc(x.nome)}</td><td>${esc(x.status)}</td><td>${x.testes}</td><td>${x.vitorias}</td><td>${x.alcance_medio ?? "-"}</td>
      <td>${x.envios ?? "-"}</td><td>${x.salvos ?? "-"}</td><td>${x.retencao != null ? Math.round(x.retencao * 100) + "%" : "-"}</td>
      <td>${x.seguidores ?? "-"}</td><td>${x.radar || ""}</td></tr>`).join("")}</table>`;

  const nomes = Object.fromEntries(d.placar.map((x) => [x.formato, x.nome]));
  $("#rd-lista").innerHTML = d.radar.length ? d.radar.map((i) => `<div class="rd-item" data-id="${esc(i.id)}">
      <div class="rd-num">${i.outlier ? esc(String(i.outlier)) + "x" : "·"}</div>
      <div class="rd-txt"><b>${esc(nomes[i.formato_viral] || "formato a classificar")}</b> · ${esc(i.rede || "")} · @${esc(i.conta || "")}
        ${i.views ? " · " + Math.round(i.views).toLocaleString("pt-BR") + " views" : ""}
        <div>${esc(i.gancho || i.legenda || "")}</div>${i.por_que ? `<div class="dica">${esc(i.por_que)}</div>` : ""}</div>
      <div class="rd-acoes">${i.link ? `<a class="link" href="${esc(i.link)}" target="_blank" rel="noopener">ver</a>` : ""}
        <button data-roteiro>Roteiro para a Divine</button><button class="link" data-descartar>descartar</button></div></div>`).join("")
    : '<p class="dica">Vazio. Rode a missão no Claude no Chrome e cole o resultado, ou busque pela API do Instagram.</p>';
  $$("#rd-lista [data-roteiro]").forEach((b) => b.onclick = () => roteiroRadar(b.closest(".rd-item").dataset.id));
  $$("#rd-lista [data-descartar]").forEach((b) => b.onclick = async () => {
    await api("/api/radar/marcar", { id: b.closest(".rd-item").dataset.id, descartado: true }); window.carregarLab();
  });

  const en = d.entrada;
  $("#en-pastas").innerHTML = en.pastas.map((p) => `<li><code>${esc(p)}</code></li>`).join("") || '<li class="dica">Nenhuma pasta encontrada.</li>';
  $("#en-recentes").innerHTML = (en.pendentes.length ? `<p>Esperando: ${en.pendentes.map(esc).join(", ")}</p>` : "")
    + en.recentes.map((r) => r.projeto ? `<div class="mini-peca" data-p="${esc(r.projeto)}"><b>${esc(r.projeto)}</b><span>${esc(r.em)}</span></div>`
      : `<div class="mini-peca"><b>${esc((r.origem || "").split("/").pop())}</b><span class="estado-erro">${esc(r.erro || "")}</span></div>`).join("");
  $$("#en-recentes .mini-peca[data-p]").forEach((el) => el.onclick = () => { mostrarTela("projetos"); abrir(el.dataset.p); });

  const tt = d.tiktok;
  $("#tt-estado").innerHTML = tt.conectado ? `<p>Conectado${tt.usuario ? ": @" + esc(tt.usuario) : ""} · envio em modo <b>${esc(tt.modo)}</b></p>
      <button id="tt-sair" class="link">desconectar</button>`
    : tt.app ? `<p>App do TikTok salvo.</p><button id="tt-conectar" class="dourado">Conectar TikTok</button>`
    : `<p class="dica">1. Crie um app em developers.tiktok.com com Login Kit e Content Posting API.<br>
        2. Cadastre a URL de retorno: <code>${esc(tt.retorno)}</code><br>3. Cole a chave e o segredo do app (ficam só no Mac).</p>
       <input id="tt-key" placeholder="Client key"><input id="tt-secret" placeholder="Client secret" type="password">
       <button id="tt-salvar" class="dourado">Salvar app</button>`;
  if ($("#tt-salvar")) $("#tt-salvar").onclick = async () => {
    await api("/api/tiktok/app", { client_key: $("#tt-key").value, client_secret: $("#tt-secret").value }).catch((e) => aviso(e.message, "erro"));
    window.carregarLab();
  };
  if ($("#tt-conectar")) $("#tt-conectar").onclick = async () => {
    try { const r = await api("/api/tiktok/conectar"); window.open(r.link, "_blank"); } catch (e) { aviso(e.message, "erro"); }
  };
  if ($("#tt-sair")) $("#tt-sair").onclick = async () => { await api("/api/tiktok/desconectar", {}); window.carregarLab(); };
  carregarAutomacoes();
};

async function carregarAutomacoes() {
  const a = await api("/api/automacoes").catch(() => null);
  if (!a) return;
  $("#au-regras").innerHTML = a.regras.map((r) => `<label class="check au-regra"><input type="checkbox" data-i="${r.indice}" ${r.ligado ? "checked" : ""}>
      <b>${esc(r.nome)}</b> <span class="dica">quando ${esc(r.quando)} → ${esc((r.fazer || []).join(", "))}</span></label>`).join("");
  $$("#au-regras input").forEach((c) => c.onchange = () => api("/api/automacoes/ligar", { indice: Number(c.dataset.i), ligado: c.checked })
    .then(() => aviso(c.checked ? "Automação ligada" : "Automação desligada")));
  $("#au-hist").innerHTML = a.historico.map((h) => `<li class="${h.ok ? "" : "estado-erro"}">${esc(h.em)} · ${esc(h.regra)} · ${esc(h.acao)} · ${esc(h.detalhe)}</li>`).join("")
    || '<li class="dica">Nada ainda.</li>';
}

async function criarTeste(formato) {
  const tema = prompt("Tema do vídeo (ex.: Laser de CO2 no rosto):", "");
  if (!tema) return;
  try {
    const r = await api("/api/nova_edicao", { tipo: "video", titulo: tema });
    await api("/api/dados", { p: r.nome, dados: { formato_viral: formato } });
    await carregarLista(); mostrarTela("projetos"); abrir(r.nome);
    aviso("Teste criado. Solte os vídeos e use a Edição automática.");
  } catch (err) { aviso(err.message, "erro"); }
}

async function roteiroRadar(id) {
  const tema = prompt("Tema da Divine para adaptar este formato (ex.: Endolaser nos braços):", "");
  if (!tema) return;
  aviso("Escrevendo o roteiro...");
  let r;
  try { r = await api("/api/radar/roteiro", { id, tema }); } catch (err) { return aviso(err.message, "erro"); }
  const m = modal(`<h2>Roteiro · ${esc(r.formato_nome)}</h2>
    <p class="dica">Referência: ${r.referencia ? `<a class="link" target="_blank" href="${esc(r.referencia)}">abrir</a>` : "-"} · escrito por ${r.fonte === "ia" ? "Claude" : "modelo do formato"}</p>
    <h3>Ganchos</h3><ul>${(r.ganchos || []).map((g) => `<li>${esc(g)}</li>`).join("")}</ul>
    <h3>Sequência de gravação</h3><ol>${(r.sequencia || []).map((g) => `<li>${esc(g)}</li>`).join("")}</ol>
    <h3>Fala (teleprompter)</h3><p>${esc(r.fala || "")}</p><h3>CTA</h3><p>${esc(r.cta || "")}</p>
    ${r.erros_compliance && r.erros_compliance.length ? `<p class="estado-erro">Revisor: ${r.erros_compliance.map(esc).join("; ")}</p>` : ""}
    <div class="sb-botoes"><button class="dourado" data-criar>Criar projeto com este roteiro</button><button data-fechar>Fechar</button></div>`);
  m.querySelector("[data-criar]").onclick = async () => {
    try {
      const p = await api("/api/radar/projeto", { id, tema });
      m.remove(); await carregarLista(); mostrarTela("projetos"); abrir(p.nome);
      aviso("Projeto criado: o roteiro está em roteiro.md e a fala no teleprompter.");
    } catch (err) { aviso(err.message, "erro"); }
  };
}

$("#lab-conta").onchange = () => window.carregarLab();
$("#rd-buscar").onclick = async () => {
  aviso("Buscando no Instagram...");
  try { const r = await api("/api/radar/buscar", {}); aviso(`${r.virais} viral(is) de ${r.analisados} analisados` + (r.erros.length ? " · " + r.erros.join("; ") : "")); window.carregarLab(); }
  catch (err) { aviso(err.message, "erro"); }
};
$("#rd-missao").onclick = () => {
  const d = labDados || {};
  const m = modal(`<h2>Pesquisa com o Claude no Chrome</h2>
    <p class="dica">1. Abra o Claude no Chrome (extensão) já logado no Instagram ou no TikTok. 2. Cole a missão abaixo e acompanhe enquanto ele navega (só olhando). 3. Copie a resposta dele e toque em "Colar resultado".</p>
    <div class="chips seg"><button class="dourado" data-rede="instagram">Instagram</button><button data-rede="tiktok">TikTok</button></div>
    <textarea id="rd-texto-missao" rows="14" readonly>${esc(d.missao_instagram || "")}</textarea>
    <div class="sb-botoes"><button class="dourado" data-copiar>Copiar missão</button><button data-fechar>Fechar</button></div>`, 760);
  m.querySelectorAll("[data-rede]").forEach((b) => b.onclick = () => {
    m.querySelectorAll("[data-rede]").forEach((x) => x.classList.toggle("dourado", x === b));
    m.querySelector("#rd-texto-missao").value = b.dataset.rede === "tiktok" ? d.missao_tiktok : d.missao_instagram;
  });
  m.querySelector("[data-copiar]").onclick = async () => {
    try { await navigator.clipboard.writeText(m.querySelector("#rd-texto-missao").value); aviso("Missão copiada"); }
    catch (e) { m.querySelector("#rd-texto-missao").select(); }
  };
};
$("#rd-colar").onclick = () => {
  const m = modal(`<h2>Colar resultado da pesquisa</h2>
    <p class="dica">A resposta do Claude no Chrome (o bloco JSON) ou links do Instagram/TikTok com os números, um por linha.</p>
    <textarea id="rd-texto" rows="12" placeholder='[{"link": "...", "conta": "...", "views": "1,2 mi", ...}]'></textarea>
    <div class="sb-botoes"><button class="dourado" data-ok>Adicionar ao Radar</button><button data-fechar>Fechar</button></div>`, 760);
  m.querySelector("[data-ok]").onclick = async () => {
    try { const r = await api("/api/radar/colar", { texto: m.querySelector("#rd-texto").value }); m.remove(); aviso(`${r.novos} novo(s) no Radar`); window.carregarLab(); }
    catch (err) { aviso(err.message, "erro"); }
  };
};
$("#en-varrer").onclick = async () => {
  aviso("Verificando a caixa de entrada e as automações...");
  try { const r = await api("/api/entrada/varrer", {}); aviso(r.rodou.length ? `${r.rodou.length} ação(ões) feitas` : "Nada novo"); window.carregarLab(); }
  catch (err) { aviso(err.message, "erro"); }
};
