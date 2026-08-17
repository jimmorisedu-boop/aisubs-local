// value -> [css font-family, css font-weight]
const FONT_FAMILY_MAP = {
  "fonts/Montserrat-var.ttf#ExtraBold": ["Montserrat", 800],
  "fonts/Montserrat-var.ttf#Bold": ["Montserrat", 700],
  "fonts/FiraSans-ExtraBold.ttf": ["Fira Sans ExtraBold", 400],
  "fonts/FiraSans-Black.ttf": ["Fira Sans Black", 400],
  "fonts/FiraSans-Medium.ttf": ["Fira Sans Medium", 400],
  "fonts/Oswald-var.ttf#Bold": ["Oswald", 700],
  "fonts/Rubik-var.ttf#ExtraBold": ["Rubik", 800],
  "fonts/PTSans-Bold.ttf": ["PT Sans Bold", 400],
  "fonts/BebasNeue-Regular.ttf": ["Bebas Neue", 400],
  "fonts/Poppins-ExtraBold.ttf": ["Poppins ExtraBold", 400],
  "fonts/Poppins-Black.ttf": ["Poppins Black", 400],
  "fonts/Anton-Regular.ttf": ["Anton", 400],
  "fonts/ArchivoBlack-Regular.ttf": ["Archivo Black", 400],
  "fonts/Bangers-Regular.ttf": ["Bangers", 400],
};

// Filled from Python with every bundled + system face.
let fontCatalog = [];
const fontByValue = new Map();

// Presets saved before text_case existed carry a boolean `uppercase`.
function textCaseOf(s) {
  if (s.text_case) return s.text_case;
  return s.uppercase ? "upper" : "none";
}

// Fonts loaded straight from their file, keyed by the style value.
const loadedFontFaces = new Map();
let fontFaceSeq = 0;

// Chromium ignores fonts installed for the current user only, so naming them
// in CSS silently renders a substitute. Loading the file itself is the only
// way the preview can be trusted to show the real typeface.
function ensureFontFace(value) {
  if (!value) return null;
  if (loadedFontFaces.has(value)) return loadedFontFaces.get(value);

  const alias = `aisubs-face-${++fontFaceSeq}`;
  loadedFontFaces.set(value, alias);

  (async () => {
    try {
      const url = await api().font_url(value);
      if (!url) return;
      const style = document.createElement("style");
      style.textContent = `@font-face{font-family:"${alias}";src:url("${url}");font-display:block;}`;
      document.head.appendChild(style);
      // Nudge a redraw once the file is in.
      if (document.fonts && document.fonts.load) {
        await document.fonts.load(`16px "${alias}"`);
        updatePreview();
        renderPresetGrid();
      }
    } catch (e) { /* fall back to the system name below */ }
  })();

  return alias;
}

// Returns [css font-family list, weight, italic]. The loaded file comes first;
// system names stay as fallbacks while it is still downloading.
function fontCss(value) {
  const alias = ensureFontFace(value);
  const f = fontByValue.get(value);
  if (f) {
    const names = (f.css_stack && f.css_stack.length ? f.css_stack : [f.css_family])
      .map((n) => `"${n}"`);
    if (alias) names.unshift(`"${alias}"`);
    return [names.join(", "), f.css_weight, f.css_italic];
  }
  const legacy = FONT_FAMILY_MAP[value];
  const fallback = legacy ? `"${legacy[0]}"` : `"UI Sans"`;
  return [alias ? `"${alias}", ${fallback}` : fallback, legacy ? legacy[1] : 400, false];
}

const DEFAULT_STYLE = {
  font: "fonts/Montserrat-var.ttf#ExtraBold",
  font_size: 84,
  text_case: "upper",   // "upper" | "lower" | "none"
  text_color: "#FFFFFF",
  stroke_color: "#000000",
  stroke_width: 0,
  shadow_enabled: true,
  shadow_color: "#000000",
  shadow_opacity: 0.45,
  shadow_blur: 6,
  shadow_offset: [0, 3],
  highlight_style: "box",
  word_highlight_color: "#3FA9E8",
  active_text_color: "#FFFFFF",
  box_color: "#3FA9E8",
  box_opacity: 1.0,
  box_radius: 16,
  box_padding_x: 20,
  box_padding_y: 10,
  line_count: 1,
  max_width_ratio: 0.86,
  line_spacing: 1.18,
  position: "bottom",
  position_margin: 190,
};

let style = Object.assign({}, DEFAULT_STYLE);
let queue = [];           // [{path, name, status: 'pending'|'running'|'done'|'failed', progress, output}]
let previewIndex = null;  // which queued file is shown in the video element
let previewVideo = null;  // {width, height, duration} of that file, for 1:1 preview scaling
let lastOutputPath = null;
let presets = [];
let isRunning = false;
let appMode = "auto";

const $ = (id) => document.getElementById(id);

function api() {
  return window.pywebview && window.pywebview.api;
}

// ---------------- control <-> state binding ----------------

function bindRange(id, valId, key, fmt) {
  const el = $(id);
  el.addEventListener("input", () => {
    const raw = parseFloat(el.value);
    style[key] = fmt ? fmt(raw) : raw;
    $(valId).textContent = fmt ? Math.round(raw) : raw;
    updatePreview();
  });
}

function bindColor(colorId, hexId, key, alsoKey) {
  const colorEl = $(colorId), hexEl = $(hexId);
  colorEl.addEventListener("input", () => {
    hexEl.value = colorEl.value.toUpperCase();
    style[key] = colorEl.value.toUpperCase();
    if (alsoKey) style[alsoKey] = style[key];
    updatePreview();
  });
  hexEl.addEventListener("change", () => {
    let v = hexEl.value.trim();
    if (!v.startsWith("#")) v = "#" + v;
    if (/^#[0-9A-Fa-f]{6}$/.test(v)) {
      colorEl.value = v;
      style[key] = v.toUpperCase();
      if (alsoKey) style[alsoKey] = style[key];
      updatePreview();
    }
  });
}

function setupBindings() {
  $("s_font").addEventListener("change", () => { style.font = $("s_font").value; updatePreview(); });
  $("fontSearch").addEventListener("input", renderFontOptions);
  $("fontCyrillicOnly").addEventListener("change", renderFontOptions);
  bindRange("s_font_size", "v_font_size", "font_size");
  setupToggleGroup("textCaseGroup", (val) => { style.text_case = val; updatePreview(); });
  bindColor("s_text_color", "s_text_color_hex", "text_color");

  bindRange("s_stroke_width", "v_stroke_width", "stroke_width");
  bindColor("s_stroke_color", "s_stroke_color_hex", "stroke_color");

  $("s_shadow_enabled").addEventListener("change", () => { style.shadow_enabled = $("s_shadow_enabled").checked; updatePreview(); });
  bindRange("s_shadow_blur", "v_shadow_blur", "shadow_blur");
  bindRange("s_shadow_opacity", "v_shadow_opacity", "shadow_opacity", (v) => v / 100);

  bindColor("s_box_color", "s_box_color_hex", "box_color");
  bindColor("s_active_text_color", "s_active_text_color_hex", "active_text_color");
  bindRange("s_box_radius", "v_box_radius", "box_radius");
  bindRange("s_box_padding_x", "v_box_padding_x", "box_padding_x");
  bindRange("s_box_padding_y", "v_box_padding_y", "box_padding_y");

  bindColor("s_word_highlight_color", "s_word_highlight_color_hex", "word_highlight_color");

  bindRange("s_position_margin", "v_position_margin", "position_margin");
  bindRange("s_line_count", "v_line_count", "line_count");
  bindRange("s_max_width_ratio", "v_max_width_ratio", "max_width_ratio", (v) => v / 100);

  setupToggleGroup("highlightStyleGroup", (val) => {
    style.highlight_style = val;
    $("boxParams").classList.toggle("hidden", val !== "box");
    $("colorParams").classList.toggle("hidden", val !== "color");
    updatePreview();
  });

  setupToggleGroup("positionGroup", (val) => {
    style.position = val;
    updatePreview();
  });

  $("dropzone").addEventListener("click", pickVideos);
}

function setupToggleGroup(groupId, onChange) {
  const group = $(groupId);
  group.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      group.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      onChange(btn.dataset.val);
    });
  });
}

function applyStyleToControls() {
  // rebuild rather than assign: a preset may use a face the filter hides
  if (fontCatalog.length) renderFontOptions(); else $("s_font").value = style.font;
  $("s_font_size").value = style.font_size; $("v_font_size").textContent = style.font_size;
  setActiveToggle("textCaseGroup", textCaseOf(style));
  $("s_text_color").value = style.text_color; $("s_text_color_hex").value = style.text_color.toUpperCase();

  $("s_stroke_width").value = style.stroke_width; $("v_stroke_width").textContent = style.stroke_width;
  $("s_stroke_color").value = style.stroke_color; $("s_stroke_color_hex").value = style.stroke_color.toUpperCase();

  $("s_shadow_enabled").checked = style.shadow_enabled;
  $("s_shadow_blur").value = style.shadow_blur; $("v_shadow_blur").textContent = style.shadow_blur;
  const shadowPct = Math.round(style.shadow_opacity * 100);
  $("s_shadow_opacity").value = shadowPct; $("v_shadow_opacity").textContent = shadowPct;

  $("s_box_color").value = style.box_color; $("s_box_color_hex").value = style.box_color.toUpperCase();
  $("s_active_text_color").value = style.active_text_color; $("s_active_text_color_hex").value = style.active_text_color.toUpperCase();
  $("s_box_radius").value = style.box_radius; $("v_box_radius").textContent = style.box_radius;
  $("s_box_padding_x").value = style.box_padding_x; $("v_box_padding_x").textContent = style.box_padding_x;
  $("s_box_padding_y").value = style.box_padding_y; $("v_box_padding_y").textContent = style.box_padding_y;

  $("s_word_highlight_color").value = style.word_highlight_color; $("s_word_highlight_color_hex").value = style.word_highlight_color.toUpperCase();

  $("s_position_margin").value = style.position_margin; $("v_position_margin").textContent = style.position_margin;
  $("s_line_count").value = style.line_count; $("v_line_count").textContent = style.line_count;
  const mwr = Math.round(style.max_width_ratio * 100);
  $("s_max_width_ratio").value = mwr; $("v_max_width_ratio").textContent = mwr;

  setActiveToggle("highlightStyleGroup", style.highlight_style);
  setActiveToggle("positionGroup", style.position);
  $("boxParams").classList.toggle("hidden", style.highlight_style !== "box");
  $("colorParams").classList.toggle("hidden", style.highlight_style !== "color");
}

function setActiveToggle(groupId, val) {
  const group = $(groupId);
  group.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b.dataset.val === val));
}

// ---------------- live CSS preview ----------------

function updatePreview() {
  const stage = $("previewStage");
  const line = $("previewLine");

  // Scale against the real frame width so what you see matches the render.
  const videoWidth = (previewVideo && previewVideo.width) || 1080;
  const scale = stage.clientWidth / videoWidth;

  const words = PREVIEW_SAMPLE;
  const activeIdx = 1;
  const [family, weight, italic] = fontCss(style.font);

  line.style.fontFamily = family;
  line.style.fontWeight = weight;
  line.style.fontStyle = italic ? "italic" : "normal";
  line.style.fontSize = Math.max(10, style.font_size * scale) + "px";
  line.style.color = style.text_color;
  const textCase = textCaseOf(style);
  line.style.textTransform = textCase === "upper" ? "uppercase" : textCase === "lower" ? "lowercase" : "none";
  line.style.textShadow = style.shadow_enabled
    ? `${style.shadow_offset[0]*scale}px ${style.shadow_offset[1]*scale}px ${style.shadow_blur*scale}px rgba(0,0,0,${style.shadow_opacity})`
    : "none";
  line.style.setProperty("-webkit-text-stroke", style.stroke_width > 0 ? `${style.stroke_width*scale}px ${style.stroke_color}` : "0px transparent");

  // Margins are in source pixels, same as the renderer treats them.
  stage.style.alignItems = style.position === "top" ? "flex-start" : style.position === "center" ? "center" : "flex-end";
  line.style.marginBottom = style.position === "bottom" ? (style.position_margin * scale) + "px" : "0px";
  line.style.marginTop = style.position === "top" ? (style.position_margin * scale) + "px" : "0px";
  line.style.maxWidth = (style.max_width_ratio * 100) + "%";

  updateTextBox(stage, line, scale, videoWidth);

  line.innerHTML = "";
  words.forEach((w, i) => {
    const span = document.createElement("span");
    span.className = "preview-word";
    span.textContent = w;
    if (i === activeIdx) {
      if (style.highlight_style === "box") {
        const padX = style.box_padding_x * scale;
        const padY = style.box_padding_y * scale;
        span.style.background = style.box_color;
        span.style.color = style.active_text_color;
        span.style.borderRadius = (style.box_radius*scale) + "px";
        span.style.padding = `${padY}px ${padX}px`;
        // Cancel the padding in layout: the renderer paints the pill around the
        // word without widening the line, and the preview must wrap at the same
        // point or it under-reports how many words fit.
        span.style.margin = `-${padY}px -${padX}px`;
        span.style.webkitTextStroke = "0px transparent";
      } else if (style.highlight_style === "color") {
        span.style.color = style.word_highlight_color;
      }
    }
    line.appendChild(span);
  });

  trimToLineCount(line);
}

// ---------------- fonts ----------------

async function loadFonts() {
  try {
    fontCatalog = await api().list_fonts();
  } catch (e) {
    fontCatalog = [];
  }
  fontByValue.clear();
  fontCatalog.forEach((f) => fontByValue.set(f.path, f));
  renderFontOptions();
}

function renderFontOptions() {
  const select = $("s_font");
  const query = ($("fontSearch").value || "").trim().toLowerCase();
  const cyrillicOnly = $("fontCyrillicOnly").checked;

  const matches = (f) =>
    (!cyrillicOnly || f.cyrillic) && (!query || f.label.toLowerCase().includes(query));

  // The face in use always stays selectable, even if filtered out.
  const visible = fontCatalog.filter((f) => matches(f) || f.path === style.font);

  const groups = [
    ["Из комплекта", visible.filter((f) => f.source === "bundled")],
    ["Системные", visible.filter((f) => f.source === "system")],
  ];

  select.innerHTML = "";
  groups.forEach(([name, items]) => {
    if (!items.length) return;
    const group = document.createElement("optgroup");
    group.label = `${name} — ${items.length}`;
    items.forEach((f) => {
      const opt = document.createElement("option");
      opt.value = f.path;
      opt.textContent = f.cyrillic ? f.label : `${f.label} (без кириллицы)`;
      // System names only here - loading a file per option would fetch
      // hundreds of fonts just to draw the dropdown.
      opt.style.fontFamily = (f.css_stack && f.css_stack.length ? f.css_stack : [f.css_family])
        .map((n) => `"${n}"`).join(", ");
      opt.style.fontWeight = f.css_weight;
      opt.style.fontStyle = f.css_italic ? "italic" : "normal";
      group.appendChild(opt);
    });
    select.appendChild(group);
  });

  if (!visible.length) {
    const opt = document.createElement("option");
    opt.textContent = "ничего не найдено";
    opt.disabled = true;
    select.appendChild(opt);
  }

  select.value = style.font;
  $("fontCount").textContent = `— ${visible.length}`;
}

// ---------------- presets ----------------

async function loadPresets() {
  try {
    presets = await api().list_presets();
  } catch (e) {
    presets = [];
  }
  renderPresetGrid();
}

function renderPresetGrid() {
  const grid = $("presetGrid");
  grid.innerHTML = "";
  presets.forEach((p) => {
    const card = document.createElement("div");
    card.className = "preset-card";
    const [family, weight] = fontCss(p.font);
    const thumbColor = p.highlight_style === "box" ? p.box_color : p.word_highlight_color;
    card.innerHTML = `
      <div class="preset-thumb"><span class="preset-sample">Аа</span></div>
      <div class="preset-name">${p.name || p.filename}</div>
      <button class="preset-del" title="Удалить пресет">×</button>
    `;

    // Styled through the DOM, not inside the markup: font stacks contain
    // quotes, and those terminate a style="..." attribute early, silently
    // dropping every declaration after the font name.
    const sample = card.querySelector(".preset-sample");
    sample.style.fontFamily = family;
    sample.style.fontWeight = weight;
    sample.style.fontSize = "15px";
    sample.style.textTransform = textCaseOf(p) === "upper" ? "uppercase"
      : textCaseOf(p) === "lower" ? "lowercase" : "none";
    if (p.highlight_style === "box") {
      sample.style.background = thumbColor;
      sample.style.color = p.active_text_color;
      sample.style.padding = "3px 8px";
      sample.style.borderRadius = Math.min(p.box_radius, 10) + "px";
    } else {
      sample.style.color = thumbColor;
    }
    card.addEventListener("click", () => {
      style = Object.assign({}, DEFAULT_STYLE, p);
      applyStyleToControls();
      updatePreview();
      document.querySelectorAll(".preset-card").forEach((c) => c.classList.remove("active"));
      card.classList.add("active");
    });
    card.querySelector(".preset-del").addEventListener("click", (e) => {
      e.stopPropagation();
      deletePreset(p, card);
    });
    grid.appendChild(card);
  });
}

async function deletePreset(preset, card) {
  // Two-step confirm inside the card, so no modal is needed.
  const button = card.querySelector(".preset-del");
  if (!card.classList.contains("confirm-delete")) {
    document.querySelectorAll(".preset-card.confirm-delete").forEach((c) => {
      c.classList.remove("confirm-delete");
      c.querySelector(".preset-del").textContent = "×";
    });
    card.classList.add("confirm-delete");
    button.textContent = "Удалить?";
    setTimeout(() => {
      card.classList.remove("confirm-delete");
      button.textContent = "×";
    }, 4000);
    return;
  }

  const result = await api().delete_preset(preset.filename);
  if (result && result.ok) {
    await loadPresets();
  } else {
    showToast("Не удалось удалить пресет: " + ((result && result.error) || "неизвестная ошибка"));
  }
}

async function savePreset() {
  const name = $("presetSaveName").value.trim();
  if (!name) return;
  const toSave = Object.assign({}, style, { name });
  await api().save_preset(name, toSave);
  await loadPresets();
}

// ---------------- video queue ----------------

// The dialog runs on the UI thread and answers via window.onVideosPicked,
// so this call returns immediately instead of blocking the window.
function pickVideos() {
  api().pick_videos();
}

// Called from Python: file dialog result, or a native drag & drop.
window.onVideosPicked = function (paths) {
  if (!paths || !paths.length) return;
  addVideos(paths);
};

function addVideos(paths) {
  const existing = new Set(queue.map((f) => f.path));
  let added = 0;
  paths.forEach((p) => {
    if (existing.has(p)) return;
    queue.push({ path: p, name: p.split(/[\\/]/).pop(), status: "pending", progress: 0, output: null });
    added++;
  });
  if (!added) return;

  $("dropzone").classList.add("hidden");
  $("videoWrapHidden").classList.remove("hidden");
  $("resultActions").classList.add("hidden");
  lastOutputPath = null;

  if (previewIndex === null && queue.length) showInPreview(0);
  renderQueue();
}

// ---------------- drag & drop ----------------

window.onDragEnter = function () {
  document.body.classList.add("dragging");
};

window.onDragLeave = function () {
  document.body.classList.remove("dragging");
};

async function showInPreview(index) {
  const item = queue[index];
  if (!item) return;
  previewIndex = index;
  const src = item.output || item.path;
  renderQueue();

  // file:// is unreachable from this page (it is served over http), so both
  // the player and the still frame come from the app's own media server.
  let info = {};
  try {
    info = (await api().video_info(src)) || {};
  } catch (e) {
    info = {};
  }
  if (previewIndex !== index) return;  // user switched while we were waiting

  if (info.media_url) $("preview").src = info.media_url;
  previewVideo = info.width ? info : null;
  applyStageGeometry();

  try {
    const url = await api().frame_url(src, null);
    if (previewIndex === index && url) setStageFrame(url);
  } catch (e) { /* preview keeps the checkerboard */ }
}

function applyStageGeometry() {
  const holder = $("previewHolder");
  const stage = $("previewStage");
  const ratio = (previewVideo && previewVideo.width && previewVideo.height)
    ? previewVideo.width / previewVideo.height
    : 9 / 16;

  // Fit the frame inside the holder, like object-fit: contain. Doing this in JS
  // keeps the box exact, which matters because the caption overlay is scaled
  // from the stage width.
  const availW = holder.clientWidth;
  const availH = holder.clientHeight;
  if (availW > 0 && availH > 0) {
    let w = availW;
    let h = w / ratio;
    if (h > availH) { h = availH; w = h * ratio; }
    stage.style.width = Math.round(w) + "px";
    stage.style.height = Math.round(h) + "px";
  }
  updatePreview();
}

function setStageFrame(url) {
  const stage = $("previewStage");
  stage.style.backgroundImage = `url("${url}")`;
  stage.classList.remove("no-frame");
  updatePreview();
}

function clearStageFrame() {
  const stage = $("previewStage");
  stage.style.backgroundImage = "";
  stage.classList.add("no-frame");
  previewVideo = null;
  applyStageGeometry();
}

// Outlines the area text can occupy, and labels it in source pixels: as wide
// as max_width_ratio allows, as tall as line_count lines.
function updateTextBox(stage, line, scale, videoWidth) {
  const box = $("textBox");
  const stageW = stage.clientWidth;
  const stageH = stage.clientHeight;
  if (!stageW || !stageH) return;

  const boxW = stageW * style.max_width_ratio;
  const lineH = parseFloat(getComputedStyle(line).lineHeight) || style.font_size * scale;
  const boxH = lineH * Math.max(1, style.line_count);

  let top;
  if (style.position === "top") {
    top = style.position_margin * scale;
  } else if (style.position === "center") {
    top = (stageH - boxH) / 2;
  } else {
    top = stageH - style.position_margin * scale - boxH;
  }
  top = Math.max(0, Math.min(top, stageH - boxH));

  box.style.left = ((stageW - boxW) / 2) + "px";
  box.style.top = top + "px";
  box.style.width = boxW + "px";
  box.style.height = boxH + "px";

  const srcW = Math.round(videoWidth * style.max_width_ratio);
  const srcH = Math.round(boxH / scale);
  $("textBoxSize").textContent = `${srcW} × ${srcH}`;
}

const PREVIEW_SAMPLE = ["ЭТО", "ПРИМЕР", "СУБТИТРОВ", "НА", "ВИДЕО"];

// Drops trailing sample words until the block fits within line_count lines,
// mirroring how the renderer packs words into a caption instead of wrapping
// endlessly. Without this the preview shows more text than will ever appear.
function trimToLineCount(line) {
  const lineHeight = parseFloat(getComputedStyle(line).lineHeight) || 1;
  const allowed = Math.max(1, style.line_count);
  let guard = PREVIEW_SAMPLE.length;
  while (guard-- > 0 && line.children.length > 1) {
    const lines = Math.round(line.scrollHeight / lineHeight);
    if (lines <= allowed) break;
    line.removeChild(line.lastElementChild);
  }
}

function removeFromQueue(index, event) {
  event.stopPropagation();
  if (isRunning) return;
  queue.splice(index, 1);
  if (!queue.length) {
    previewIndex = null;
    $("preview").removeAttribute("src");
    clearStageFrame();
    $("dropzone").classList.remove("hidden");
    $("videoWrapHidden").classList.add("hidden");
  } else if (previewIndex !== null) {
    showInPreview(Math.min(previewIndex, queue.length - 1));
    return;
  }
  renderQueue();
}

const STATUS_ICON = { pending: "○", running: "◐", done: "✓", failed: "✕" };

function renderQueue() {
  const list = $("fileList");
  list.innerHTML = "";
  queue.forEach((item, i) => {
    const row = document.createElement("div");
    row.className = "file-row " + item.status + (i === previewIndex ? " selected" : "");
    row.onclick = () => showInPreview(i);
    row.innerHTML = `
      <span class="status">${STATUS_ICON[item.status]}</span>
      <span class="name" title="${item.path}">${item.name}</span>
      ${item.status === "running" ? `<span class="mini-bar"><span class="mini-fill" style="width:${item.progress}%"></span></span>` : ""}
      ${isRunning ? "" : `<button class="remove" title="Убрать">×</button>`}
    `;
    const removeBtn = row.querySelector(".remove");
    if (removeBtn) removeBtn.onclick = (e) => removeFromQueue(i, e);
    list.appendChild(row);
  });

  $("queueCount").textContent = queue.length ? `— ${queue.length}` : "";
  const btn = $("runBtn");
  if (appMode === "auto") {
    btn.textContent = queue.length > 1 ? `Создать субтитры (${queue.length})` : "Создать субтитры";
  } else if (typeof updateManualRunButton === "function") {
    updateManualRunButton();
  }
}

// ---------------- run pipeline ----------------

async function runPipeline() {
  if (!queue.length) { pickVideos(); return; }

  isRunning = true;
  $("runBtn").disabled = true;
  $("cancelBtn").disabled = false;
  $("cancelBtn").textContent = "Остановить после файла";
  $("cancelBtn").classList.remove("hidden");
  $("resultActions").classList.add("hidden");
  queue.forEach((f) => { f.status = "pending"; f.progress = 0; f.output = null; });
  renderQueue();
  setProgress("Подготовка...", 0);

  try {
    await api().run_pipeline({
      videos: queue.map((f) => f.path),
      style: style,
      model: $("modelSize").value,
      language: $("language").value,
      device: $("device").value,
    });
  } catch (e) {
    onQueueDone([]);
    onPipelineError(String(e));
  }
}

const STAGE_LABELS = {
  downloading_model: "Скачивание модели (разово)...",
  loading_model: "Загрузка модели распознавания...",
  transcribing: "Распознавание речи...",
  preparing: "Подготовка рендера...",
  building: "Построение субтитров...",
  compositing: "Сборка видео слоёв...",
  rendering: "Рендер видео...",
  done: "Готово",
};

function setProgress(label, pct) {
  $("progressStage").textContent = label;
  $("progressPct").textContent = pct != null ? pct + "%" : "";
  $("progressFill").style.width = (pct || 0) + "%";
}

// ---- called from Python via window.evaluate_js ----

window.updateProgress = function (stage, pct, index) {
  const label = STAGE_LABELS[stage] || stage;
  if (index == null || !queue.length) {
    setProgress(label, pct);
    return;
  }
  queue[index].progress = ManualState.pipelineProgress(queue[index].progress, stage, pct);
  const prefix = queue.length > 1 ? `[${index + 1}/${queue.length}] ` : "";
  // overall = files fully done + fraction of the current one
  const overall = Math.round(((index + queue[index].progress / 100) / queue.length) * 100);
  setProgress(prefix + label, overall);
  renderQueue();
};

window.onFileStarted = function (index) {
  queue[index].status = "running";
  renderQueue();
};

window.onFileDone = function (index, outputPath) {
  queue[index].status = "done";
  queue[index].output = outputPath;
  queue[index].progress = 100;
  lastOutputPath = outputPath;
  renderQueue();
};

window.onFileError = function (index, message) {
  queue[index].status = "failed";
  renderQueue();
  showToast(`Ошибка: ${queue[index].name}: ${message}`);
};

window.onQueueDone = function (outputs) {
  isRunning = false;
  $("cancelBtn").classList.add("hidden");
  $("cancelBtn").disabled = false;
  $("runBtn").disabled = false;
  const failed = queue.filter((f) => f.status === "failed").length;
  setProgress(failed ? `Готово, с ошибками: ${failed}` : "Готово", 100);
  if (outputs && outputs.length) {
    lastOutputPath = outputs[outputs.length - 1];
    $("resultActions").classList.remove("hidden");
    const firstDone = queue.findIndex((f) => f.status === "done");
    if (firstDone >= 0) showInPreview(firstDone);
  }
  renderQueue();
  refreshModelHint();   // a model may have just been downloaded
};

function showToast(message) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 6000);
}

async function openCreatorChannel() {
  return CreatorChannel.openCreatorChannel(api(), showToast);
}

window.onPipelineError = function (message) {
  if (!isRunning) $("runBtn").disabled = false;
  setProgress("Ошибка", null);
  showToast("Ошибка: " + message);
};

async function openOutput() {
  await api().open_output_folder(lastOutputPath);
}

function playResult() {
  const doneIndex = queue.findIndex((f) => f.status === "done");
  if (doneIndex >= 0) {
    showInPreview(doneIndex);
  } else if (lastOutputPath) {
    $("preview").src = "file:///" + lastOutputPath.replace(/\\/g, "/");
  }
  $("preview").play();
}

// Approximate download sizes, so the hint can warn before a long wait.
const MODEL_SIZES = {
  "large-v3": "~3 ГБ",
  "distil-large-v3": "~1.5 ГБ",
  "medium": "~1.5 ГБ",
  "small": "~500 МБ",
  "base": "~150 МБ",
};
let modelsCached = {};

// Best first: the dropdown falls back to the best model already on disk.
const MODEL_PREFERENCE = ["large-v3", "distil-large-v3", "medium", "small", "base", "tiny"];

async function refreshModelHint(selectDownloaded) {
  try {
    modelsCached = (await api().models_status()) || {};
  } catch (e) {
    modelsCached = {};
  }

  // On startup, don't leave a 3 GB download queued up behind the default when
  // the user already has a lighter model installed.
  if (selectDownloaded && !modelsCached[$("modelSize").value]) {
    const ready = MODEL_PREFERENCE.find((m) => modelsCached[m] &&
      $("modelSize").querySelector(`option[value="${m}"]`));
    if (ready) $("modelSize").value = ready;
  }

  updateModelHint();
}

function updateModelHint() {
  const size = $("modelSize").value;
  const hint = $("modelHint");
  if (modelsCached[size]) {
    hint.textContent = "Модель уже скачана — начнём сразу.";
    hint.style.color = "";
  } else {
    hint.textContent = `Модель ещё не скачана: при запуске загрузится ${MODEL_SIZES[size] || ""} (разово).`;
    hint.style.color = "var(--accent)";
  }
}

async function refreshGpuBadge() {
  try {
    const info = await api().get_gpu_info();
    $("gpuLabel").textContent = info.name ? `${info.name}` : "CPU режим";
    $("gpuDot").style.background = info.available ? "var(--good)" : "#9099b0";
  } catch (e) {
    $("gpuLabel").textContent = "CPU режим";
  }
}

// ---------------- init ----------------

function init() {
  setupBindings();
  if (typeof initManualMode === "function") initManualMode();
  applyStyleToControls();
  applyStageGeometry();
  loadPresets();
  loadFonts();
  refreshGpuBadge();
  refreshModelHint(true);
  $("modelSize").addEventListener("change", updateModelHint);
}

if (window.pywebview) {
  init();
} else {
  window.addEventListener("pywebviewready", init);
}
window.addEventListener("resize", applyStageGeometry);
