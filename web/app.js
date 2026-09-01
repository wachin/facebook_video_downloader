/* Facebook Collections Downloader — lógica de la interfaz */
"use strict";

/* ============================================================ utilidades */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

const STATUS_LABEL = {
  pending: "Pendiente",
  transcribing: "Transcribiendo",
  done: "Transcrita",
  error: "Error",
};

function fmtDuration(seconds) {
  if (!seconds) return "";
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const pad = (n) => String(n).padStart(2, "0");
  return h ? `${h}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`;
}

async function api(path, opts = {}) {
  const isForm = opts.body instanceof FormData;
  const res = await fetch(path, {
    ...opts,
    headers: opts.body && !isForm ? { "Content-Type": "application/json" } : {},
  });
  if (!res.ok) {
    let message = res.statusText;
    try {
      const j = await res.json();
      if (j.error) message = j.error;
    } catch (_) { /* sin cuerpo JSON */ }
    throw new Error(message);
  }
  return res.json();
}

function toast(message, type = "ok") {
  const wrap = $("#toasts");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `<svg viewBox="0 0 24 24">${
    type === "err"
      ? '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>'
      : '<circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.5 2.5L16 9"/>'
  }</svg><span>${esc(message)}</span>`;
  wrap.appendChild(el);
  setTimeout(() => {
    el.classList.add("leaving");
    setTimeout(() => el.remove(), 260);
  }, 3400);
}

function confirmDialog(message, { danger = false, confirmLabel = "Confirmar" } = {}) {
  /* Diálogo propio de la app: window.confirm() no funciona en WebKitGTK. */
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `
      <div class="modal-box">
        <p>${esc(message)}</p>
        <div class="modal-actions">
          <button class="btn btn-ghost" data-act="no">Cancelar</button>
          <button class="btn ${danger ? "btn-danger" : "btn-primary"}" data-act="yes">${esc(confirmLabel)}</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const done = (value) => { overlay.remove(); resolve(value); };
    const onKey = (e) => {
      if (e.key === "Escape") {
        document.removeEventListener("keydown", onKey);
        done(false);
      }
    };
    overlay.querySelector('[data-act="yes"]').addEventListener("click", () => done(true));
    overlay.querySelector('[data-act="no"]').addEventListener("click", () => done(false));
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) done(false);
    });
    document.addEventListener("keydown", onKey);
    overlay.querySelector('[data-act="yes"]').focus();
  });
}

function copyText(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
  }
  return Promise.resolve(fallbackCopy(text));
}
function fallbackCopy(text) {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand("copy"); } catch (_) { /* sin soporte */ }
  ta.remove();
}

/* ============================================================ estado */

const state = {
  view: "library",
  recipes: [],
  stats: { total: 0, done: 0, pending: 0, transcribing: 0, error: 0 },
  categories: [],
  settings: null,
  hadJobs: false,
  search: "",
  category: "",
  statusFilter: "all",
  editorId: null,
  editorDirty: false,
  fbCaptured: [],
  fbDownload: null,
  fbDoneNotified: false,
};

let fbBookmarklet = "";

const native = () => !!(window.pywebview && window.pywebview.api);

/* ============================================================ arranque */

async function boot() {
  bindStatic();
  try {
    state.settings = await api("/api/settings");
  } catch (_) {
    toast("No se pudo conectar con el servidor local.", "err");
  }
  renderSettings();
  await refreshAll();
  const tab = new URLSearchParams(location.search).get("tab");
  if (tab === "facebook") setView("facebook");
  setInterval(tick, 1500);
}

async function refreshAll() {
  const [recipes, stats, categories] = await Promise.all([
    api("/api/recipes"),
    api("/api/stats"),
    api("/api/categories"),
  ]);
  state.recipes = recipes;
  state.stats = stats;
  state.categories = categories;
  renderSidebarStats();
  if (state.view === "library") renderLibrary();
  if (state.view === "queue") renderQueue();
  renderCategoryDatalist();
}

/* ============================================================ barra lateral */

function renderSidebarStats() {
  const s = state.stats;
  $("#nav-count").textContent = s.total || "";
  const badge = $("#nav-badge");
  const n = (s.pending || 0) + (s.error || 0) + (s.transcribing || 0);
  badge.textContent = n;
  badge.classList.toggle("hidden", n === 0);
  $("#side-stats").innerHTML = `
    <div class="side-stat total"><b>${s.total}</b><span>Recetas</span></div>
    <div class="side-stat done"><b>${s.done}</b><span>Listas</span></div>
    <div class="side-stat pending"><b>${(s.pending || 0) + (s.transcribing || 0)}</b><span>Cola</span></div>`;
}

/* ============================================================ vistas */

function setView(name) {
  state.view = name;
  $$(".nav-item").forEach((el) => el.classList.toggle("active", el.dataset.view === name));
  $("#view-library").classList.toggle("hidden", name !== "library");
  $("#view-queue").classList.toggle("hidden", name !== "queue");
  $("#view-facebook").classList.toggle("hidden", name !== "facebook");
  $("#view-settings").classList.toggle("hidden", name !== "settings");
  if (name === "library") renderLibrary();
  if (name === "queue") renderQueue();
  if (name === "facebook") renderFacebook();
}

/* ---------------- biblioteca ---------------- */

function filteredRecipes() {
  let list = state.recipes;
  const q = state.search.trim().toLowerCase();
  if (q) {
    list = list.filter((r) =>
      `${r.title} ${r.file_name} ${r.transcript} ${r.category} ${r.tags.join(" ")}`
        .toLowerCase().includes(q));
  }
  if (state.category) {
    list = list.filter((r) => r.category.toLowerCase() === state.category.toLowerCase());
  }
  if (state.statusFilter !== "all") {
    list = list.filter((r) =>
      state.statusFilter === "pending"
        ? r.status === "pending" || r.status === "transcribing"
        : r.status === state.statusFilter);
  }
  return list;
}

function renderFilterRow() {
  const s = state.stats;
  const chips = (label, count, value, kind) =>
    `<button class="chip ${state[kind] === value ? "active" : ""}" data-${kind}="${esc(value)}">${label} <b>${count}</b></button>`;
  const cats = state.categories
    .map((c) => chips(esc(c.name), c.count, c.name, "category"))
    .join("");
  $("#filter-row").innerHTML = `
    ${chips("Todas", s.total, "all", "statusFilter")}
    ${chips("Transcritas", s.done, "done", "statusFilter")}
    ${chips("Pendientes", (s.pending || 0) + (s.transcribing || 0), "pending", "statusFilter")}
    ${chips("Errores", s.error, "error", "statusFilter")}
    <span class="chip-sep"></span>
    <button class="chip ${state.category === "" ? "active" : ""}" data-category="">Todas las categorías</button>
    ${cats}`;
}

function cardHTML(r) {
  const badge =
    r.status === "done"
      ? '<span class="card-status st-done">✓ Transcrita</span>'
      : r.status === "transcribing"
        ? `<span class="card-status st-transcribing"><span class="dot"></span>${Math.round(r.progress)}%</span>`
        : r.status === "error"
          ? '<span class="card-status st-error">⚠ Error</span>'
          : '<span class="card-status st-pending"><span class="dot"></span>Pendiente</span>';
  const dur = fmtDuration(r.duration);
  return `
  <article class="card" data-id="${r.id}" tabindex="0" role="button" aria-label="Abrir ${esc(r.title || r.file_name)}">
    <div class="card-thumb">
      <img loading="lazy" src="/media/thumb/${r.id}" alt=""
        onerror="this.style.display='none';this.parentElement.classList.add('no-thumb');this.parentElement.textContent='🍳'">
      ${dur ? `<span class="card-duration">${dur}</span>` : ""}
    </div>
    <div class="card-actions">
      <button class="card-act" data-act="transcribe" title="Transcribir vídeo"
        ${r.status === "transcribing" ? "disabled" : ""}>
        <svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
      </button>
      <button class="card-act danger" data-act="delete" title="Eliminar del recetario">
        <svg viewBox="0 0 24 24"><path d="M4 7h16M9 7V5h6v2m-8 0l1 13h8l1-13"/></svg>
      </button>
    </div>
    ${badge}
    ${r.status === "transcribing" ? `<div class="progress-mini"><i style="width:${Math.max(3, r.progress)}%"></i></div>` : ""}
    <div class="card-body">
      <div class="card-title">${esc(r.title || r.file_name)}</div>
      <div class="card-meta">
        ${r.category ? `<span class="cat-chip">${esc(r.category)}</span>` : ""}
        ${r.tags.slice(0, 3).map((t) => `<span class="tag-chip">${esc(t)}</span>`).join("")}
      </div>
    </div>
  </article>`;
}

function renderLibrary() {
  renderFilterRow();
  const list = filteredRecipes();
  const grid = $("#library-grid");
  grid.innerHTML = list.map(cardHTML).join("");
  const empty = $("#empty-state");
  if (state.recipes.length === 0) {
    empty.innerHTML = `
      <span class="empty-emoji">🍽️</span>
      <h3>Tu recetario está vacío</h3>
      <p>Descarga los vídeos de tu colección de Facebook, déjalos en tu carpeta de vídeos
      (o arrástralos aquí) y pulsa «Escanear». Cada vídeo se convertirá en una receta.</p>
      <button class="btn btn-primary" id="empty-open-folder">
        <svg viewBox="0 0 24 24"><path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
        Abrir carpeta de vídeos
      </button>`;
    empty.classList.remove("hidden");
  } else if (list.length === 0) {
    empty.innerHTML = `
      <span class="empty-emoji">🔍</span>
      <h3>Sin resultados</h3>
      <p>Ninguna receta coincide con tu búsqueda o filtros.</p>`;
    empty.classList.remove("hidden");
  } else {
    empty.classList.add("hidden");
  }
}

/* ---------------- cola ---------------- */

function queueRowHTML(r) {
  const isBusy = r.status === "transcribing";
  const isError = r.status === "error";
  const pct = Math.round(r.progress || 0);
  const thumb = r.thumbnail
    ? `<img src="/media/thumb/${r.id}" alt="">`
    : '<div class="no-thumb">🍳</div>';
  const actions = isBusy
    ? `<button class="btn btn-mini" data-act="cancel"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>Cancelar</button>`
    : `<button class="btn btn-mini" data-act="transcribe" ${isError ? 'title="Reintentar"' : ""}><svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>${isError ? "Reintentar" : "Transcribir"}</button>`;
  return `
  <div class="queue-row ${isBusy ? "transcribing" : ""}" data-id="${r.id}">
    <div class="queue-thumb">${thumb}</div>
    <div class="queue-info">
      <div class="queue-name">${esc(r.title || r.file_name)}</div>
      <div class="queue-sub">${esc(r.file_name)} · ${fmtDuration(r.duration) || "duración desconocida"}</div>
      ${isError ? `<div class="queue-err">${esc(r.error || "Error de transcripción")}</div>` : ""}
      ${isBusy ? `
        <div class="queue-progress"><i style="width:${Math.max(3, pct)}%"></i></div>` : ""}
    </div>
    <div class="queue-pct">${isBusy ? `${pct}%` : STATUS_LABEL[r.status]}</div>
    <div class="queue-actions">
      ${actions}
      <button class="btn btn-mini" data-act="open"><svg viewBox="0 0 24 24"><path d="M9 5h10v10M5 19L19 5"/></svg>Abrir</button>
      <button class="btn btn-mini" data-act="delete" title="Eliminar del recetario">
        <svg viewBox="0 0 24 24"><path d="M4 7h16M9 7V5h6v2m-8 0l1 13h8l1-13"/></svg>
      </button>
    </div>
  </div>`;
}

function renderQueue() {
  const list = state.recipes.filter((r) => r.status !== "done");
  const wrap = $("#queue-list");
  if (list.length === 0) {
    wrap.innerHTML = `
      <div class="empty">
        <span class="empty-emoji">🎉</span>
        <h3>¡Cola vacía!</h3>
        <p>No hay vídeos pendientes de transcripción. Importa vídeos nuevos desde la Biblioteca.</p>
      </div>`;
    return;
  }
  wrap.innerHTML = list.map(queueRowHTML).join("");
}

/* ---------------- ajustes ---------------- */

function renderSettings() {
  const s = state.settings || {};
  const useNative = native();
  $("#settings-form").innerHTML = `
    <div class="settings-card">
      <h3>
        <svg viewBox="0 0 24 24"><path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
        Carpeta de vídeos
      </h3>
      <p class="card-desc">Aquí dejas los vídeos descargados de Facebook. El programa detecta los
      nuevos al escanear y los convierte en recetas.</p>
      <div class="field">
        <label for="set-folder">Ruta de la carpeta</label>
        <div class="folder-row">
          <input type="text" id="set-folder" value="${esc(s.watch_folder || "")}" spellcheck="false">
          <button class="btn btn-ghost" id="btn-pick-folder" ${useNative ? "" : "disabled"}>
            <svg viewBox="0 0 24 24"><path d="M4 7h5l2 2h9v10H4z"/></svg>
            Examinar…
          </button>
        </div>
        <div style="font-size:11.5px;color:var(--faint);margin-top:6px" id="folder-hint"></div>
      </div>
    </div>

    <div class="settings-card">
      <h3>
        <svg viewBox="0 0 24 24"><path d="M4 5h16v14H4z"/><path d="M8 9h8M8 13h8M8 17h5"/></svg>
        Transcripción (Whisper)
      </h3>
      <p class="card-desc">Se ejecuta 100% en tu equipo: tus vídeos nunca salen de tu ordenador.
      El primer uso descarga el modelo elegido.</p>
      <div class="field">
        <label for="set-model">Modelo</label>
        <select id="set-model">
          <option value="tiny" ${s.whisper_model === "tiny" ? "selected" : ""}>tiny — muy rápido, menos preciso</option>
          <option value="base" ${s.whisper_model === "base" ? "selected" : ""}>base — rápido</option>
          <option value="small" ${s.whisper_model === "small" ? "selected" : ""}>small — equilibrio (recomendado)</option>
          <option value="medium" ${s.whisper_model === "medium" ? "selected" : ""}>medium — muy preciso, más lento en CPU</option>
        </select>
      </div>
      <div class="field">
        <label for="set-lang">Idioma de los vídeos</label>
        <select id="set-lang">
          <option value="es" ${s.language === "es" ? "selected" : ""}>Español</option>
          <option value="auto" ${s.language === "auto" ? "selected" : ""}>Auto (detectar)</option>
          <option value="en" ${s.language === "en" ? "selected" : ""}>Inglés</option>
          <option value="pt" ${s.language === "pt" ? "selected" : ""}>Portugués</option>
          <option value="fr" ${s.language === "fr" ? "selected" : ""}>Francés</option>
          <option value="it" ${s.language === "it" ? "selected" : ""}>Italiano</option>
          <option value="de" ${s.language === "de" ? "selected" : ""}>Alemán</option>
          <optgroup label="Más idiomas (Whisper)">
          <option value="af" ${s.language === "af" ? "selected" : ""}>Afrikáans</option>
          <option value="sq" ${s.language === "sq" ? "selected" : ""}>Albanés</option>
          <option value="am" ${s.language === "am" ? "selected" : ""}>Amárico</option>
          <option value="ar" ${s.language === "ar" ? "selected" : ""}>Árabe</option>
          <option value="hy" ${s.language === "hy" ? "selected" : ""}>Armenio</option>
          <option value="as" ${s.language === "as" ? "selected" : ""}>Asamés</option>
          <option value="az" ${s.language === "az" ? "selected" : ""}>Azerí</option>
          <option value="ba" ${s.language === "ba" ? "selected" : ""}>Baskir</option>
          <option value="bn" ${s.language === "bn" ? "selected" : ""}>Bengalí</option>
          <option value="be" ${s.language === "be" ? "selected" : ""}>Bielorruso</option>
          <option value="my" ${s.language === "my" ? "selected" : ""}>Birmano</option>
          <option value="bs" ${s.language === "bs" ? "selected" : ""}>Bosnio</option>
          <option value="br" ${s.language === "br" ? "selected" : ""}>Bretón</option>
          <option value="bg" ${s.language === "bg" ? "selected" : ""}>Búlgaro</option>
          <option value="km" ${s.language === "km" ? "selected" : ""}>Camboyano (jemer)</option>
          <option value="kn" ${s.language === "kn" ? "selected" : ""}>Canarés</option>
          <option value="yue" ${s.language === "yue" ? "selected" : ""}>Cantonés</option>
          <option value="ca" ${s.language === "ca" ? "selected" : ""}>Catalán</option>
          <option value="cs" ${s.language === "cs" ? "selected" : ""}>Checo</option>
          <option value="zh" ${s.language === "zh" ? "selected" : ""}>Chino (mandarín)</option>
          <option value="si" ${s.language === "si" ? "selected" : ""}>Cingalés</option>
          <option value="ko" ${s.language === "ko" ? "selected" : ""}>Coreano</option>
          <option value="ht" ${s.language === "ht" ? "selected" : ""}>Criollo haitiano</option>
          <option value="hr" ${s.language === "hr" ? "selected" : ""}>Croata</option>
          <option value="da" ${s.language === "da" ? "selected" : ""}>Danés</option>
          <option value="sk" ${s.language === "sk" ? "selected" : ""}>Eslovaco</option>
          <option value="sl" ${s.language === "sl" ? "selected" : ""}>Esloveno</option>
          <option value="et" ${s.language === "et" ? "selected" : ""}>Estonio</option>
          <option value="eu" ${s.language === "eu" ? "selected" : ""}>Euskera</option>
          <option value="fo" ${s.language === "fo" ? "selected" : ""}>Feroés</option>
          <option value="fi" ${s.language === "fi" ? "selected" : ""}>Finés</option>
          <option value="gl" ${s.language === "gl" ? "selected" : ""}>Gallego</option>
          <option value="cy" ${s.language === "cy" ? "selected" : ""}>Galés</option>
          <option value="ka" ${s.language === "ka" ? "selected" : ""}>Georgiano</option>
          <option value="el" ${s.language === "el" ? "selected" : ""}>Griego</option>
          <option value="gu" ${s.language === "gu" ? "selected" : ""}>Guyaratí</option>
          <option value="ha" ${s.language === "ha" ? "selected" : ""}>Hausa</option>
          <option value="haw" ${s.language === "haw" ? "selected" : ""}>Hawaiano</option>
          <option value="he" ${s.language === "he" ? "selected" : ""}>Hebreo</option>
          <option value="hi" ${s.language === "hi" ? "selected" : ""}>Hindi</option>
          <option value="hu" ${s.language === "hu" ? "selected" : ""}>Húngaro</option>
          <option value="id" ${s.language === "id" ? "selected" : ""}>Indonesio</option>
          <option value="is" ${s.language === "is" ? "selected" : ""}>Islandés</option>
          <option value="ja" ${s.language === "ja" ? "selected" : ""}>Japonés</option>
          <option value="jw" ${s.language === "jw" ? "selected" : ""}>Javanés</option>
          <option value="kk" ${s.language === "kk" ? "selected" : ""}>Kazajo</option>
          <option value="lo" ${s.language === "lo" ? "selected" : ""}>Laosiano</option>
          <option value="la" ${s.language === "la" ? "selected" : ""}>Latín</option>
          <option value="lv" ${s.language === "lv" ? "selected" : ""}>Letón</option>
          <option value="ln" ${s.language === "ln" ? "selected" : ""}>Lingala</option>
          <option value="lt" ${s.language === "lt" ? "selected" : ""}>Lituano</option>
          <option value="lb" ${s.language === "lb" ? "selected" : ""}>Luxemburgués</option>
          <option value="mk" ${s.language === "mk" ? "selected" : ""}>Macedonio</option>
          <option value="mg" ${s.language === "mg" ? "selected" : ""}>Malgache</option>
          <option value="ms" ${s.language === "ms" ? "selected" : ""}>Malayo</option>
          <option value="ml" ${s.language === "ml" ? "selected" : ""}>Malayalam</option>
          <option value="mt" ${s.language === "mt" ? "selected" : ""}>Maltés</option>
          <option value="mr" ${s.language === "mr" ? "selected" : ""}>Maratí</option>
          <option value="mi" ${s.language === "mi" ? "selected" : ""}>Maorí</option>
          <option value="mn" ${s.language === "mn" ? "selected" : ""}>Mongol</option>
          <option value="ne" ${s.language === "ne" ? "selected" : ""}>Nepalí</option>
          <option value="nl" ${s.language === "nl" ? "selected" : ""}>Neerlandés</option>
          <option value="no" ${s.language === "no" ? "selected" : ""}>Noruego</option>
          <option value="nn" ${s.language === "nn" ? "selected" : ""}>Noruego (nynorsk)</option>
          <option value="oc" ${s.language === "oc" ? "selected" : ""}>Occitano</option>
          <option value="pa" ${s.language === "pa" ? "selected" : ""}>Panyabí</option>
          <option value="ps" ${s.language === "ps" ? "selected" : ""}>Pastún</option>
          <option value="fa" ${s.language === "fa" ? "selected" : ""}>Persa</option>
          <option value="pl" ${s.language === "pl" ? "selected" : ""}>Polaco</option>
          <option value="ro" ${s.language === "ro" ? "selected" : ""}>Rumano</option>
          <option value="ru" ${s.language === "ru" ? "selected" : ""}>Ruso</option>
          <option value="sa" ${s.language === "sa" ? "selected" : ""}>Sánscrito</option>
          <option value="sd" ${s.language === "sd" ? "selected" : ""}>Sindhi</option>
          <option value="sr" ${s.language === "sr" ? "selected" : ""}>Serbio</option>
          <option value="sn" ${s.language === "sn" ? "selected" : ""}>Shona</option>
          <option value="so" ${s.language === "so" ? "selected" : ""}>Somalí</option>
          <option value="sw" ${s.language === "sw" ? "selected" : ""}>Suajili</option>
          <option value="su" ${s.language === "su" ? "selected" : ""}>Sundanés</option>
          <option value="sv" ${s.language === "sv" ? "selected" : ""}>Sueco</option>
          <option value="tl" ${s.language === "tl" ? "selected" : ""}>Tagalo</option>
          <option value="ta" ${s.language === "ta" ? "selected" : ""}>Tamil</option>
          <option value="tt" ${s.language === "tt" ? "selected" : ""}>Tártaro</option>
          <option value="tg" ${s.language === "tg" ? "selected" : ""}>Tayiko</option>
          <option value="te" ${s.language === "te" ? "selected" : ""}>Telugu</option>
          <option value="bo" ${s.language === "bo" ? "selected" : ""}>Tibetano</option>
          <option value="tk" ${s.language === "tk" ? "selected" : ""}>Turcomano</option>
          <option value="tr" ${s.language === "tr" ? "selected" : ""}>Turco</option>
          <option value="uk" ${s.language === "uk" ? "selected" : ""}>Ucraniano</option>
          <option value="ur" ${s.language === "ur" ? "selected" : ""}>Urdu</option>
          <option value="uz" ${s.language === "uz" ? "selected" : ""}>Uzbeko</option>
          <option value="vi" ${s.language === "vi" ? "selected" : ""}>Vietnamita</option>
          <option value="yi" ${s.language === "yi" ? "selected" : ""}>Yidis</option>
          <option value="yo" ${s.language === "yo" ? "selected" : ""}>Yoruba</option>
          </optgroup>
        </select>
      </div>
      <div class="field">
        <label>Hilos de CPU: <span class="range-value" id="threads-val">${s.cpu_threads || 4}</span></label>
        <div class="range-row">
          <input type="range" id="set-threads" min="1" max="8" value="${s.cpu_threads || 4}">
        </div>
      </div>
      <label class="check-row">
        <input type="checkbox" id="set-vad" ${s.vad ? "checked" : ""}>
        <span>Filtrar silencios y música de fondo (recomendado en cocinas)</span>
      </label>
      <button class="btn btn-primary" id="btn-save-settings">
        <svg viewBox="0 0 24 24"><path d="M5 3h11l5 5v13H5z"/><path d="M8 3v6h7V3M8 21v-7h8v7"/></svg>
        Guardar ajustes
      </button>
    </div>

    <div class="settings-card">
      <h3>
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>
        Almacenamiento
      </h3>
      <p class="card-desc">Todo se guarda localmente en estas rutas.</p>
      <div class="info-row"><span>Base de datos</span><code>data/recipes.db</code></div>
      <div class="info-row"><span>Miniaturas</span><code>data/thumbs/</code></div>
      <div class="info-row"><span>Carpeta de vídeos</span><code>${esc(s.watch_folder || "—")}</code></div>
      <div class="info-row"><span>Vídeos en recetario</span><code>${state.stats.total} recetas</code></div>
    </div>

    <div class="settings-card danger-zone">
      <h3>
        <svg viewBox="0 0 24 24"><path d="M12 9v4m0 4h.01M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/></svg>
        Zona de peligro
      </h3>
      <p class="card-desc">Elimina todas las recetas del recetario. Los vídeos originales en tu
      carpeta <b>no</b> se borran.</p>
      <button class="btn btn-ghost" id="btn-wipe" style="color:var(--danger);border-color:rgba(226,84,75,.4)">
        Vaciar biblioteca
      </button>
    </div>`;

  $("#set-threads").addEventListener("input", (e) => {
    $("#threads-val").textContent = e.target.value;
  });
  $("#btn-save-settings").addEventListener("click", saveSettings);
  $("#btn-pick-folder").addEventListener("click", pickFolder);
  $("#btn-wipe").addEventListener("click", wipeLibrary);
  updateFolderHint();
}

function updateFolderHint() {
  const hint = $("#folder-hint");
  if (!hint) return;
  const folder = ($("#set-folder") || {}).value || state.settings?.watch_folder;
  if (native()) {
    hint.textContent = "Pulsa «Examinar…» para elegir la carpeta con el diálogo nativo.";
  } else {
    hint.innerHTML = "Modo navegador: escribe la ruta a mano (p. ej. <code>/home/usuario/Videos/Recetas</code>).";
  }
  void folder;
}

async function saveSettings() {
  const data = {
    watch_folder: $("#set-folder").value.trim(),
    whisper_model: $("#set-model").value,
    language: $("#set-lang").value,
    cpu_threads: parseInt($("#set-threads").value, 10) || 4,
    vad: $("#set-vad").checked,
  };
  try {
    state.settings = await api("/api/settings", {
      method: "POST",
      body: JSON.stringify(data),
    });
    toast("Ajustes guardados.");
    await refreshAll();
  } catch (e) {
    toast(`No se pudieron guardar: ${e.message}`, "err");
  }
}

async function pickFolder() {
  try {
    const picked = await window.pywebview.api.pick_folder();
    if (picked) {
      $("#set-folder").value = picked;
      updateFolderHint();
    }
  } catch (_) {
    toast("El selector de carpetas no está disponible; escribe la ruta a mano.", "err");
  }
}

async function wipeLibrary() {
  const btn = $("#btn-wipe");
  if (btn.dataset.arm !== "1") {
    btn.dataset.arm = "1";
    btn.textContent = "¿Seguro? Pulsa otra vez para vaciar";
    setTimeout(() => {
      btn.dataset.arm = "";
      btn.textContent = "Vaciar biblioteca";
    }, 4000);
    return;
  }
  try {
    await Promise.all(state.recipes.map((r) =>
      api(`/api/recipes/${r.id}`, { method: "DELETE" })));
    toast("Biblioteca vaciada.");
    await refreshAll();
  } catch (e) {
    toast(`Error: ${e.message}`, "err");
  }
}

/* ---------------- facebook ---------------- */

async function renderFacebook() {
  await loadCaptured();
  await checkYtdlp();
  // Consulta siempre el estado de descarga al entrar en la pestaña: una
  // descarga iniciada desde Facebook (canal nativo) puede estar en curso sin
  // que el frontend lo sepa todavía.
  pollFbStatus();
}

async function loadCaptured() {
  try {
    state.fbCaptured = await api("/api/fb/captured");
  } catch (_) {
    state.fbCaptured = [];
  }
  const list = $("#fb-list");
  if (!list) return;
  list.innerHTML = state.fbCaptured.map(fbItemHTML).join("");
  const n = state.fbCaptured.length;
  $("#fb-count").textContent = n ? `${n} vídeo${n === 1 ? "" : "s"} capturado${n === 1 ? "" : "s"}` : "";
  $("#fb-download").disabled = n === 0;
}

function fbItemHTML(item) {
  const kindLabel = item.kind === "video" ? "Vídeo directo" : "Enlace";
  return `
  <div class="fb-item" data-id="${item.id}">
    <label class="fb-check"><input type="checkbox" value="${item.id}" checked></label>
    <div class="fb-item-info">
      <div class="fb-item-title">${esc(item.title)}</div>
      <div class="fb-item-url" title="${esc(item.url)}">${esc(item.url)}</div>
    </div>
    <span class="fb-kind ${item.kind}">${kindLabel}</span>
    <button class="btn-mini" data-act="del" title="Quitar de la lista">
      <svg viewBox="0 0 24 24"><path d="M4 7h16M9 7V5h6v2m-8 0l1 13h8l1-13"/></svg>
    </button>
  </div>`;
}

async function checkYtdlp() {
  const hint = $("#fb-open-hint");
  if (!hint) return;
  try {
    const info = await api("/api/fb/ytdlp");
    hint.innerHTML = info.available
      ? (native()
          ? "Se abre en una ventana nueva; Facebook Collections Downloader se queda abierto."
          : "Se abre en tu navegador (usa el bookmarklet del paso 2).")
      : "⚠ Falta <code>yt-dlp</code>: instálalo con <code>sudo apt install yt-dlp</code> para poder descargar.";
  } catch (_) { /* servidor aún arrancando */ }
}

async function openFacebook() {
  if (native()) {
    try {
      await window.pywebview.api.open_facebook();
      toast("Abriendo Facebook en una ventana nueva. Facebook Collections Downloader se queda abierto para ver el progreso.");
    } catch (_) {
      window.open("https://www.facebook.com/saved/", "_blank");
    }
  } else {
    window.open("https://www.facebook.com/saved/", "_blank");
    toast("Facebook abierto en tu navegador. Captura con el bookmarklet del paso 2.");
  }
}

async function captureNow() {
  if (!native()) {
    toast("En modo navegador usa el bookmarklet del paso 2.", "ok");
    return;
  }
  const ok = await window.pywebview.api.capture_now();
  if (ok) toast("Captura lanzada. Si estás en una página de Facebook, mira abajo a la derecha.");
  else toast("No se pudo capturar. Abre primero Facebook con el botón del paso 1.", "err");
}

function fbBookmarkletSource() {
  // El bookmarklet solo carga el script desde el servidor local (con una
  // etiqueta <script>, que no está sujeta a CORS ni a contenido mixto por ser
  // 127.0.0.1). Así siempre usa la versión actual, con el botón de descargar
  // la colección entera incluido, sin duplicar el código aquí.
  const origin = location.origin;
  return `(function(){
    var s=document.createElement('script');
    s.src=${JSON.stringify(origin)}+'/api/fb/script';
    document.documentElement.appendChild(s);
  })();`;
}

function initBookmarklet() {
  fbBookmarklet = "javascript:" + fbBookmarkletSource();
  const link = $("#fb-bookmark-link");
  const code = $("#fb-bookmark-code");
  link.href = fbBookmarklet;
  code.value = fbBookmarklet;
  link.style.cursor = "grab";
}

async function downloadSelected() {
  const ids = $$("#fb-list input[type=checkbox]:checked").map((el) => +el.value);
  if (!ids.length) {
    toast("Marca al menos un vídeo para descargar.", "err");
    return;
  }
  try {
    const res = await api("/api/fb/download", {
      method: "POST",
      body: JSON.stringify({ ids }),
    });
    toast(res.message);
    pollFbStatus();
  } catch (e) {
    toast(e.message, "err");
  }
}

function pollFbStatus() {
  api("/api/fb/status")
    .then((d) => {
      state.fbDownload = d;
      renderFbStatus();
      if (d.running) {
        state.fbDoneNotified = false;
        setTimeout(pollFbStatus, 1200);
        return;
      }
      // El trabajo terminado queda en el estado del servidor, así que el aviso
      // «Descarga terminada» solo debe salir UNA vez (y no cada 1,5 s).
      if (!state.fbDoneNotified && d.items.some((i) => i.status === "done")) {
        state.fbDoneNotified = true;
        refreshAll();
        loadCaptured().catch(() => {});
        toast("Descarga terminada. Los vídeos están en tu Biblioteca.");
      }
    })
    .catch(() => { /* servidor aún arrancando */ });
}

function renderFbStatus() {
  const wrap = $("#fb-download-progress");
  const d = state.fbDownload;
  renderFbMini(d);
  if (!d || !d.items.length) {
    wrap.innerHTML = "";
    return;
  }
  const rows = d.items.map((it) => {
    let label;
    if (it.status === "queued") label = "En cola…";
    else if (it.status === "downloading") label = `Descargando… ${Math.round(it.progress)}%`;
    else if (it.status === "done") label = `✓ ${esc(it.filename || "listo")}`;
    else if (it.status === "error") label = `⚠ ${esc(it.error)}`;
    else if (it.status === "cancelled") label = "Cancelado";
    else label = it.status;
    const bar = it.status === "downloading"
      ? `<div class="queue-progress"><i style="width:${Math.max(3, Math.round(it.progress))}%"></i></div>`
      : "";
    return `<div class="fb-dl-row">
      <div class="fb-dl-title">${esc(it.title)}</div>
      <div class="fb-dl-label">${label}</div>${bar}</div>`;
  }).join("");
  wrap.innerHTML = `<div class="fb-dl-box"><h4>Descargas</h4>${rows}</div>`;
}

/* Indicador global de descarga: visible desde CUALQUIER pestaña (abajo, en
   medio). Al hacer clic, te lleva a la pestaña Facebook, donde está la lista
   completa con el progreso de cada vídeo. */
function renderFbMini(d) {
  const pill = $("#fb-mini-progress");
  if (!pill) return;
  const active = d && d.items.find((it) => it.status === "downloading");
  if (!(d && d.running) || !active) {
    pill.classList.add("hidden");
    return;
  }
  const pct = Math.round(active.progress || 0);
  pill.classList.remove("hidden");
  pill.innerHTML = `
    <div class="fb-mini-icon">⬇️</div>
    <div class="fb-mini-body">
      <div class="fb-mini-label">Descargando… ${pct}%</div>
      <div class="fb-mini-bar"><i style="width:${Math.max(3, pct)}%"></i></div>
    </div>`;
  pill.onclick = () => setView("facebook");
}

async function removeCaptured(id) {
  try {
    await api(`/api/fb/captured/${id}`, { method: "DELETE" });
    await loadCaptured();
  } catch (e) {
    toast(e.message, "err");
  }
}

async function clearCaptured() {
  const ok = await confirmDialog("¿Vaciar la lista de vídeos capturados?");
  if (!ok) return;
  try {
    await api("/api/fb/clear", { method: "POST" });
    await loadCaptured();
  } catch (e) {
    toast(e.message, "err");
  }
}

/* ============================================================ editor */

async function openEditor(id) {
  state.editorId = id;
  state.editorDirty = false;
  $("#editor").classList.remove("hidden");
  document.body.style.overflow = "hidden";
  try {
    const r = await api(`/api/recipes/${id}`);
    fillEditor(r);
  } catch (e) {
    toast(e.message, "err");
    closeEditor();
  }
}

async function closeEditor() {
  if (state.editorDirty
      && !(await confirmDialog("Tienes cambios sin guardar. ¿Descartarlos?",
                               { confirmLabel: "Descartar cambios" }))) {
    return;
  }
  state.editorId = null;
  state.editorDirty = false;
  $("#editor").classList.add("hidden");
  document.body.style.overflow = "";
  const video = $("#ed-video");
  video.pause();
  video.removeAttribute("src");
  video.load();
}

function fillEditor(r) {
  $("#ed-title").value = r.title || "";
  $("#ed-category").value = r.category || "";
  $("#ed-tags").value = (r.tags || []).join(", ");
  $("#ed-notes").value = r.notes || "";
  $("#ed-transcript").value = r.transcript || "";
  $("#ed-trans-meta").textContent = r.transcript
    ? `${r.transcript.split(/\s+/).filter(Boolean).length} palabras`
    : "";
  renderEditorLists(r);
  updateEditorStatus(r);
  $("#ed-source").innerHTML =
    `<span>${esc(r.file_name)}</span>` +
    (native()
      ? ` · <a href="#" data-reveal="${esc(r.video_path)}">abrir carpeta</a>`
      : "");
  const video = $("#ed-video");
  video.src = r.file_exists ? `/media/video/${r.id}` : "";
  video.poster = r.thumbnail ? `/media/thumb/${r.id}` : "";
  $("#ed-video-missing").classList.toggle("hidden", r.file_exists);
  renderCategoryDatalist();
}

function renderCategoryDatalist() {
  const names = new Set(state.recipes.map((r) => r.category).filter(Boolean));
  $("#cat-list").innerHTML = [...names]
    .map((n) => `<option value="${esc(n)}">`).join("");
}

function renderEditorLists(r) {
  const ings = r.ingredients || [];
  const steps = r.steps || [];
  $("#ed-ingredients").innerHTML = ings
    .map((item, i) => listItemHTML("ing", i, item, false))
    .join("");
  $("#ed-steps").innerHTML = steps
    .map((item, i) => listItemHTML("step", i, item, true))
    .join("");
}

function listItemHTML(kind, i, value, numbered) {
  return `
  <div class="list-item" data-kind="${kind}">
    <span class="list-num">${numbered ? i + 1 : "•"}</span>
    <input type="text" value="${esc(value)}" placeholder="${kind === "ing" ? "1 taza de harina…" : "Describe el paso…"}">
    <button class="btn-mini" data-act="up" title="Subir"><svg viewBox="0 0 24 24"><path d="M12 19V5m0 0l-5 5m5-5l5 5"/></svg></button>
    <button class="btn-mini" data-act="down" title="Bajar"><svg viewBox="0 0 24 24"><path d="M12 5v14m0 0l-5-5m5 5l5-5"/></svg></button>
    <button class="btn-mini" data-act="del" title="Eliminar"><svg viewBox="0 0 24 24"><path d="M4 7h16M9 7V5h6v2m-8 0l1 13h8l1-13"/></svg></button>
  </div>`;
}

function collectEditor() {
  const list = (kind) => $$(`#ed-${kind} .list-item input`)
    .map((el) => el.value.trim()).filter(Boolean);
  return {
    title: $("#ed-title").value.trim(),
    category: $("#ed-category").value.trim(),
    tags: $("#ed-tags").value.split(",").map((t) => t.trim()).filter(Boolean),
    transcript: $("#ed-transcript").value,
    ingredients: list("ingredients"),
    steps: list("steps"),
    notes: $("#ed-notes").value,
  };
}

async function saveEditor(close = false) {
  if (!state.editorId) return;
  const data = collectEditor();
  const current = state.recipes.find((r) => r.id === state.editorId);
  if (current && current.status === "transcribing") {
    // Mientras el trabajo transcribe, él es el dueño del texto: no enviamos
    // la transcripción para no pisar sus actualizaciones en vivo.
    delete data.transcript;
  }
  try {
    const saved = await api(`/api/recipes/${state.editorId}`, {
      method: "POST",
      body: JSON.stringify(data),
    });
    state.editorDirty = false;
    toast("Receta guardada.");
    state.recipes = state.recipes.map((r) => (r.id === saved.id ? saved : r));
    if (state.view === "library") renderLibrary();
    if (state.view === "queue") renderQueue();
    renderSidebarStats();
    if (close) closeEditor();
  } catch (e) {
    toast(`No se pudo guardar: ${e.message}`, "err");
  }
}

async function startTranscription(id) {
  try {
    await api(`/api/recipes/${id}/transcribe`, { method: "POST" });
    toast("Transcripción iniciada.");
  } catch (e) {
    toast(e.message, "err");
  }
}

function updateEditorStatus(r) {
  const el = $("#ed-trans-status");
  const btn = $("#ed-transcribe");
  if (!el || !btn) return;
  if (r.status === "transcribing") {
    el.textContent = `Transcribiendo… ${Math.round(r.progress)}%`;
    el.className = "trans-status busy";
    btn.disabled = true;
  } else if (r.status === "done") {
    el.textContent = "✓ Transcrita";
    el.className = "trans-status ok";
    btn.disabled = false;
  } else if (r.status === "error") {
    el.textContent = `⚠ ${r.error || "Error"}`;
    el.className = "trans-status";
    btn.disabled = false;
  } else {
    el.textContent = "";
    el.className = "trans-status";
    btn.disabled = false;
  }
}

/* ============================================================ polling */

async function tick() {
  try {
    const jobs = await api("/api/transcription/jobs");
    const wasActive = state.hadJobs;
    state.hadJobs = jobs.length > 0;

    if (state.hadJobs) {
      // Refrescar progreso en vivo.
      const [recipes, stats] = await Promise.all([
        api("/api/recipes"),
        api("/api/stats"),
      ]);
      state.recipes = recipes;
      state.stats = stats;
      renderSidebarStats();
      if (state.view === "library") renderLibrary();
      if (state.view === "queue") renderQueue();
      if (state.editorId) {
        const r = recipes.find((x) => x.id === state.editorId);
        if (r) {
          updateEditorStatus(r);
          syncLiveTranscript(r);
        }
      }
    }

    if (wasActive && !state.hadJobs) {
      await refreshAll();
      if (state.editorId) {
        const r = state.recipes.find((x) => x.id === state.editorId);
        if (r) {
          fillEditor(r);
          toast("Transcripción completada.");
        }
      } else {
        toast("Transcripción completada.");
      }
    }

    if (state.view === "facebook") {
      loadCaptured().catch(() => {});
    }
    // El estado de descarga se consulta SIEMPRE (no solo en la pestaña
    // Facebook): una descarga puede iniciarse desde la ventana de Facebook y
    // el indicador de progreso debe verse estés donde estés.
    pollFbStatus();
  } catch (_) { /* el servidor aún arrancando */ }
}

function syncLiveTranscript(r) {
  const ta = $("#ed-transcript");
  if (!ta || document.activeElement === ta) return;
  if (r.transcript !== ta.value) {
    ta.value = r.transcript;
    $("#ed-trans-meta").textContent = r.transcript
      ? `${r.transcript.split(/\s+/).filter(Boolean).length} palabras`
      : "";
  }
}

/* ============================================================ eventos */

function bindStatic() {
  // Navegación
  $$(".nav-item").forEach((el) =>
    el.addEventListener("click", () => setView(el.dataset.view)));

  // Búsqueda con debounce
  let debounce;
  $("#search-input").addEventListener("input", (e) => {
    clearTimeout(debounce);
    debounce = setTimeout(() => {
      state.search = e.target.value;
      renderLibrary();
    }, 180);
  });

  // Filtros (delegación)
  $("#filter-row").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    if (chip.dataset.statusFilter !== undefined) {
      state.statusFilter = chip.dataset.statusFilter;
    }
    if (chip.dataset.category !== undefined) {
      state.category = chip.dataset.category;
    }
    renderLibrary();
  });

  // Tarjetas
  $("#library-grid").addEventListener("click", (e) => {
    const card = e.target.closest(".card");
    if (!card) return;
    const act = e.target.closest("[data-act]");
    if (act) {
      e.stopPropagation();
      const id = +card.dataset.id;
      if (act.dataset.act === "transcribe") startTranscription(id);
      if (act.dataset.act === "delete") deleteRecipe(id);
      return;
    }
    openEditor(+card.dataset.id);
  });
  $("#library-grid").addEventListener("keydown", (e) => {
    const card = e.target.closest(".card");
    if (card && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      openEditor(+card.dataset.id);
    }
  });

  // Escanear e importar
  $("#btn-rescan").addEventListener("click", async () => {
    const res = await api("/api/rescan", { method: "POST" });
    toast(res.new > 0
      ? `${res.new} vídeo${res.new === 1 ? "" : "s"} nuevo${res.new === 1 ? "" : "s"} encontrado${res.new === 1 ? "" : "s"}.`
      : "Carpeta escaneada: sin vídeos nuevos.");
    await refreshAll();
  });
  $("#btn-import").addEventListener("click", () => $("#file-input").click());
  $("#file-input").addEventListener("change", (e) => {
    if (e.target.files.length) uploadFiles(e.target.files);
    e.target.value = "";
  });

  // Arrastrar y soltar
  const dz = $("#dropzone");
  ["dragenter", "dragover"].forEach((ev) =>
    dz.addEventListener(ev, (e) => {
      e.preventDefault();
      dz.classList.add("dragging");
    }));
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, (e) => {
      e.preventDefault();
      dz.classList.remove("dragging");
    }));
  dz.addEventListener("drop", (e) => {
    const files = [...(e.dataTransfer?.files || [])].filter((f) => f.type.startsWith("video/"));
    if (files.length) uploadFiles(files);
    else toast("Solo se aceptan archivos de vídeo.", "err");
  });

  // Cola
  $("#queue-list").addEventListener("click", (e) => {
    const row = e.target.closest(".queue-row");
    if (!row) return;
    const id = +row.dataset.id;
    const act = e.target.closest("[data-act]")?.dataset.act;
    if (act === "transcribe") startTranscription(id);
    if (act === "cancel") cancelTranscription(id);
    if (act === "open") openEditor(id);
    if (act === "delete") deleteRecipe(id);
  });
  $("#btn-transcribe-all").addEventListener("click", transcribeAll);

  // Editor
  $("#ed-close").addEventListener("click", closeEditor);
  $("#ed-cancel").addEventListener("click", closeEditor);
  $("#ed-save").addEventListener("click", () => saveEditor(true));
  $("#ed-transcribe").addEventListener("click", () => startTranscription(state.editorId));
  $("#ed-export").addEventListener("click", () => {
    if (state.editorId) window.location.href = `/api/export/${state.editorId}`;
  });
  $("#ed-copy-trans").addEventListener("click", () => {
    copyText($("#ed-transcript").value).then(() => toast("Transcripción copiada."));
  });
  $("#ed-add-ing").addEventListener("click", () =>
    $("#ed-ingredients").insertAdjacentHTML("beforeend", listItemHTML("ing", 999, "", false)));
  $("#ed-add-step").addEventListener("click", () =>
    $("#ed-steps").insertAdjacentHTML("beforeend", listItemHTML("step", 999, "", true)));
  ["#ed-ingredients", "#ed-steps"].forEach((sel) => {
    $(sel).addEventListener("click", (e) => {
      const btn = e.target.closest("[data-act]");
      if (!btn) return;
      const item = e.target.closest(".list-item");
      const kind = item.dataset.kind;
      const box = item.parentElement;
      if (btn.dataset.act === "del") item.remove();
      if (btn.dataset.act === "up" && item.previousElementSibling) {
        box.insertBefore(item, item.previousElementSibling);
      }
      if (btn.dataset.act === "down" && item.nextElementSibling) {
        box.insertBefore(item.nextElementSibling, item);
      }
      renumber(box, kind === "step");
      state.editorDirty = true;
    });
  });
  // Marcar como modificado
  $("#editor").addEventListener("input", (e) => {
    if (e.target.closest("#editor")) state.editorDirty = true;
  });

  // Enlaces del editor
  $("#ed-source").addEventListener("click", async (e) => {
    const a = e.target.closest("[data-reveal]");
    if (a) {
      e.preventDefault();
      try { await window.pywebview.api.reveal_in_file_manager(a.dataset.reveal); }
      catch (_) { toast("No disponible en modo navegador.", "err"); }
    }
  });

  // Carpeta desde la barra lateral / estado vacío
  $("#btn-open-folder").addEventListener("click", openWatchFolder);
  document.addEventListener("click", (e) => {
    if (e.target.id === "empty-open-folder") openWatchFolder();
  });

  // Facebook
  $("#fb-open").addEventListener("click", openFacebook);
  $("#fb-capture").addEventListener("click", captureNow);
  $("#fb-download").addEventListener("click", downloadSelected);
  $("#fb-clear").addEventListener("click", clearCaptured);
  $("#fb-bookmark-toggle").addEventListener("click", () => {
    const box = $("#fb-bookmark");
    box.classList.toggle("hidden");
    if (!box.classList.contains("hidden")) initBookmarklet();
  });
  $("#fb-bookmark-copy").addEventListener("click", () =>
    copyText($("#fb-bookmark-code").value).then(() => toast("Código copiado.")));
  $("#fb-list").addEventListener("click", (e) => {
    const btn = e.target.closest('[data-act="del"]');
    if (btn) removeCaptured(+e.target.closest(".fb-item").dataset.id);
  });

  // Teclado global
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && state.editorId) closeEditor();
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      if (state.editorId) saveEditor(false);
    }
  });
}

function renumber(box, numbered) {
  [...box.children].forEach((item, i) => {
    const num = item.querySelector(".list-num");
    if (num) num.textContent = numbered ? i + 1 : "•";
  });
}

async function deleteRecipe(id) {
  const recipe = state.recipes.find((r) => r.id === id);
  const name = recipe?.title || recipe?.file_name || "receta";
  const ok = await confirmDialog(
    `¿Eliminar «${name}» del recetario? El vídeo original no se borra.`,
    { danger: true, confirmLabel: "Eliminar" });
  if (!ok) return;
  try {
    await api(`/api/recipes/${id}`, { method: "DELETE" });
    toast("Receta eliminada.");
    await refreshAll();
  } catch (e) {
    toast(e.message, "err");
  }
}

async function cancelTranscription(id) {
  await api(`/api/transcription/cancel/${id}`, { method: "POST" });
  toast("Cancelando…");
}

async function transcribeAll() {
  const pending = state.recipes.filter((r) =>
    r.status === "pending" || r.status === "error");
  if (!pending.length) {
    toast("No hay vídeos pendientes.");
    return;
  }
  for (const r of pending) {
    await startTranscription(r.id);
  }
}

function uploadFiles(files) {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  $("#busy").classList.remove("hidden");
  api("/api/import", { method: "POST", body: form })
    .then((res) => {
      toast(res.saved.length
        ? `${res.saved.length} vídeo${res.saved.length === 1 ? "" : "s"} importado${res.saved.length === 1 ? "" : "s"}.`
        : "No se importó ningún vídeo.", res.saved.length ? "ok" : "err");
      return refreshAll();
    })
    .catch((e) => toast(e.message, "err"))
    .finally(() => $("#busy").classList.add("hidden"));
}

function openWatchFolder() {
  const folder = state.settings?.watch_folder;
  if (!folder) return;
  if (native()) {
    window.pywebview.api.reveal_in_file_manager(folder);
  } else {
    toast(`Carpeta: ${folder}`, "ok");
  }
}

/* ============================================================ inicio */

document.addEventListener("DOMContentLoaded", boot);
