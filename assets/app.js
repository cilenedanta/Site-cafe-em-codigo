(() => {
  "use strict";

  const COLORS = {
    tecnologia: "var(--c-tecnologia)",
    carreira: "var(--c-carreira)",
    ia: "var(--c-ia)",
    dados: "var(--c-dados)",
  };

  const state = { data: null, cat: "all", q: "", lang: "all", win: 30 };
  const FRESH_MIN = 30;
  const $ = (sel) => document.querySelector(sel);

  const fmtTime = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" });
  const fmtDate = new Intl.DateTimeFormat("pt-BR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const rtf = new Intl.RelativeTimeFormat("pt-BR", { numeric: "auto" });

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function safeUrl(u) {
    try {
      const url = new URL(u);
      return url.protocol === "https:" || url.protocol === "http:" ? url.href : "#";
    } catch { return "#"; }
  }

  function ago(iso) {
    if (!iso) return "";
    const diff = (new Date(iso) - Date.now()) / 1000;
    const abs = Math.abs(diff);
    if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
    if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
    return rtf.format(Math.round(diff / 86400), "day");
  }

  function norm(s) {
    return String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  }

  function filtered(cat) {
    const q = norm(state.q);
    return cat.items.filter((i) =>
      (state.lang === "all" || i.lang === state.lang) &&
      inWindow(i.published) &&
      (!q || norm(`${i.title} ${i.summary} ${i.source}`).includes(q))
    );
  }

  function minutesAgo(iso) {
    return iso ? (Date.now() - new Date(iso)) / 60000 : Infinity;
  }

  function inWindow(iso) {
    // sem data de publicação: só aparece na janela máxima
    return iso ? minutesAgo(iso) <= state.win : state.win >= 2880;
  }

  function isFresh(iso) {
    return minutesAgo(iso) <= FRESH_MIN;
  }

  function winLabel() {
    const o = $("#window").selectedOptions[0];
    return o ? o.textContent.toLowerCase() : "";
  }

  function renderKpis() {
    const cats = state.data.categories;
    const total = cats.reduce((n, c) => n + filtered(c).length, 0);
    const okSources = state.data.sources.filter((s) => s.ok).length;
    const tiles = [
      `<button class="kpi" data-cat="all" aria-pressed="${state.cat === "all"}">
         <p class="kpi__label">Total · ${esc(winLabel())}</p>
         <p class="kpi__value">${total}</p>
         <p class="kpi__sub">${okSources}/${state.data.sources.length} fontes ativas</p>
       </button>`,
      ...cats.map((c) => {
        const items = filtered(c);
        const fresh = items.filter((i) => isFresh(i.published)).length;
        return `<button class="kpi" data-cat="${esc(c.id)}" style="--kpi-color:${COLORS[c.id] || "var(--accent)"}" aria-pressed="${state.cat === c.id}">
          <p class="kpi__label">${esc(c.label)}</p>
          <p class="kpi__value">${items.length}</p>
          <p class="kpi__sub">${fresh} nos últimos 30 min</p>
        </button>`;
      }),
    ];
    $("#kpis").innerHTML = tiles.join("");
  }

  function renderChips() {
    const opts = [{ id: "all", label: "Todas" }, ...state.data.categories];
    $("#chips").innerHTML = opts
      .map((c) => `<button class="chip" role="tab" data-cat="${esc(c.id)}" aria-selected="${state.cat === c.id}">${esc(c.label)}</button>`)
      .join("");
  }

  function renderItem(i) {
    const img = i.image
      ? `<img class="item__thumb" src="${esc(safeUrl(i.image))}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">`
      : "";
    const time = i.published
      ? `<time datetime="${esc(i.published)}" title="${esc(new Date(i.published).toLocaleString("pt-BR"))}">${esc(ago(i.published))}</time>`
      : "";
    return `<li class="item">
      <a href="${esc(safeUrl(i.link))}" target="_blank" rel="noopener noreferrer">
        ${img}
        <div class="item__body">
          <div class="item__meta">
            <span class="item__source">${esc(i.source)}</span>
            ${time}
            ${i.lang === "en" ? '<span class="tag">EN</span>' : ""}
            ${isFresh(i.published) ? '<span class="new">• novo</span>' : ""}
          </div>
          <p class="item__title">${esc(i.title)}</p>
          ${i.summary ? `<p class="item__summary">${esc(i.summary)}</p>` : ""}
        </div>
      </a>
    </li>`;
  }

  function renderBoard() {
    const board = $("#board");
    const cats = state.data.categories.filter((c) => state.cat === "all" || c.id === state.cat);
    board.classList.toggle("single", state.cat !== "all");
    const totalRaw = state.data.categories.reduce((n, c) => n + c.items.length, 0);
    if (totalRaw === 0) {
      board.innerHTML = `<div class="notice"><strong>Ainda não há notícias coletadas.</strong>
        Rode <code>python scripts/fetch_news.py</code> ou dispare o workflow <code>Atualizar notícias</code> no GitHub Actions.</div>`;
      return;
    }
    board.innerHTML = cats.map((c) => {
      const items = filtered(c);
      return `<article class="col" style="--cat:${COLORS[c.id] || "var(--accent)"}">
        <header class="col__head">
          <h2 class="col__title"><span class="dot"></span>${esc(c.label)}</h2>
          <span class="count">${items.length}</span>
        </header>
        ${items.length
          ? `<ul class="list">${items.map(renderItem).join("")}</ul>`
          : `<p class="empty">${state.q || state.lang !== "all"
              ? "Nada encontrado com esses filtros."
              : `Nenhuma notícia nova ${esc(winLabel())}.<br>Escolha um período maior no seletor acima.`}</p>`}
      </article>`;
    }).join("");
  }

  function renderSources() {
    const cats = state.data.categories;
    $("#sources").innerHTML = cats.map((c) => {
      const rows = state.data.sources.filter((s) => s.category === c.id).map((s) => {
        let host = s.url;
        try { host = new URL(s.url).hostname.replace(/^www\./, ""); } catch {}
        const status = s.ok === null
          ? `<span class="src-wait">aguardando</span>`
          : s.ok
            ? `<span class="src-ok">${s.items} ✓</span>`
            : `<span class="src-err" title="${esc(s.error || "erro")}">falhou</span>`;
        return `<li><a href="${esc(safeUrl(s.url))}" target="_blank" rel="noopener noreferrer" title="${esc(host)}">${esc(s.name)}</a>${status}</li>`;
      }).join("");
      return `<div class="src-group" style="--cat:${COLORS[c.id] || "var(--accent)"}">
        <h3><span class="dot"></span>${esc(c.label)}</h3>
        <ul>${rows || "<li>—</li>"}</ul>
      </div>`;
    }).join("");
  }

  function renderAll() {
    renderKpis();
    renderChips();
    renderBoard();
  }

  function setCat(cat) {
    state.cat = cat;
    try { localStorage.setItem("cec-cat", cat); } catch {}
    renderAll();
  }

  function bind() {
    document.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-cat]");
      if (btn && (btn.classList.contains("chip") || btn.classList.contains("kpi"))) setCat(btn.dataset.cat);
    });
    let t;
    $("#search").addEventListener("input", (e) => {
      clearTimeout(t);
      t = setTimeout(() => { state.q = e.target.value; renderAll(); }, 120);
    });
    $("#window").addEventListener("change", (e) => {
      state.win = Number(e.target.value);
      try { localStorage.setItem("cec-win", e.target.value); } catch {}
      renderAll();
    });
    $("#lang").addEventListener("change", (e) => {
      state.lang = e.target.value;
      try { localStorage.setItem("cec-lang", state.lang); } catch {}
      renderAll();
    });
  }

  async function init() {
    const today = fmtDate.format(new Date());
    $("#today").textContent = today.charAt(0).toUpperCase() + today.slice(1);
    try {
      state.cat = localStorage.getItem("cec-cat") || "all";
      state.lang = localStorage.getItem("cec-lang") || "all";
      const w = Number(localStorage.getItem("cec-win"));
      if ([30, 120, 360, 1440, 2880].includes(w)) state.win = w;
    } catch {}
    $("#lang").value = state.lang;
    $("#window").value = String(state.win);
    bind();
    await load(true);
    // a janela é relativa ao "agora": re-renderiza a cada minuto e busca dados novos a cada 5 min
    setInterval(() => { if (state.data) { renderAll(); updatedLabel(); } }, 60 * 1000);
    setInterval(() => load(false), 5 * 60 * 1000);
  }

  function updatedLabel() {
    const gen = state.data.generated_at ? new Date(state.data.generated_at) : null;
    $("#updated").textContent = gen
      ? `Coletado ${ago(state.data.generated_at)} (às ${fmtTime.format(gen)}) · nova coleta a cada 30 min`
      : "Aguardando a primeira coleta";
  }

  async function load(first) {
    try {
      const res = await fetch(`data/news.json?t=${Date.now()}`, { cache: "no-store" });
      if (!res.ok) throw new Error(res.status);
      state.data = await res.json();
    } catch (err) {
      if (!first) return; // mantém os dados já exibidos
      $("#updated").textContent = "Não foi possível carregar data/news.json";
      $("#board").innerHTML = `<div class="notice"><strong>Erro ao carregar as notícias.</strong>
        Abra o site por um servidor (ex.: <code>python -m http.server</code>), não direto do arquivo.</div>`;
      return;
    }
    if (!state.data.categories.some((c) => c.id === state.cat)) state.cat = "all";
    updatedLabel();
    renderAll();
    renderSources();
  }

  init();
})();
