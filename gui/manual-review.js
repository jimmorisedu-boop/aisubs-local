let manualJob = null;
let manualSelectedId = null;
let manualTranscript = null;
let manualFilter = "all";
let manualPatchTimer = null;
let manualPendingPatches = new Map();
let manualPendingItemId = null;
let manualSaveChain = Promise.resolve();
const manualTranscripts = new Map();

const MANUAL_STATUS = {
  queued: ["○", "В очереди"], transcribing: ["◐", "Распознаётся"],
  transcribed: ["•", "Нужно проверить"], needs_review: ["•", "Есть правки"],
  approved: ["✓", "Одобрено"], failed: ["✕", "Ошибка"],
  no_speech: ["!", "Речь не найдена"], cancelled: ["■", "Отменено"],
  rendering: ["◐", "Рендер"], completed: ["✓", "Готово"],
  render_failed: ["✕", "Ошибка рендера"],
};

function initManualMode() {
  $("modeAuto").addEventListener("click", () => setAppMode("auto"));
  $("modeManual").addEventListener("click", () => setAppMode("manual"));
  $("manualFilters").querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      manualFilter = button.dataset.filter;
      $("manualFilters").querySelectorAll("button").forEach((candidate) =>
        candidate.classList.toggle("active", candidate === button));
      renderManualQueue();
    });
  });
  $("approveCurrent").addEventListener("click", approveCurrentTranscript);
  $("approveClean").addEventListener("click", approveCleanTranscripts);
  $("nextAttention").addEventListener("click", selectNextAttention);
  $("retryManualFailed").addEventListener("click", retryManualFailures);
  $("retranscribeCurrent").addEventListener("click", retranscribeCurrentItem);
  restoreLatestManualJob();
}

async function restoreLatestManualJob() {
  try {
    const result = await api().latest_manual_job();
    if (!result || !result.ok || !result.job) return;
    manualJob = result.job;
    queue = manualJob.items.map((item) => ({
      path: item.path, name: item.name, status: item.state === "completed" ? "done" : "pending",
      progress: item.progress || 0, output: item.output || null,
    }));
    $("dropzone").classList.add("hidden");
    $("videoWrapHidden").classList.remove("hidden");
    appMode = "manual";
    setAppMode("manual");
    renderManualJob();
    hydrateManualTranscripts();
    showToast("Восстановлен последний пакет Manual Mode");
  } catch (error) { /* first launch or bridge not ready */ }
}

function setAppMode(mode) {
  if (isRunning && mode !== appMode) {
    showToast("Дождитесь окончания текущего этапа или остановите очередь");
    return;
  }
  appMode = mode;
  $("modeAuto").classList.toggle("active", mode === "auto");
  $("modeManual").classList.toggle("active", mode === "manual");
  const reviewing = mode === "manual" && manualJob;
  $("autoWorkspace").classList.toggle("hidden", reviewing);
  $("manualWorkspace").classList.toggle("hidden", !reviewing);
  renderQueue();
  updateManualRunButton();
}

function runCurrentMode() {
  if (appMode === "auto") return runPipeline();
  if (!manualJob) return startManualTranscription();
  const gate = ManualState.renderGate(manualJob);
  if (gate.enabled) return startManualRender();
}

async function startManualTranscription() {
  if (!queue.length) { pickVideos(); return; }
  isRunning = true;
  $("runBtn").disabled = true;
  $("cancelBtn").disabled = false;
  $("cancelBtn").textContent = "Остановить после файла";
  $("cancelBtn").classList.remove("hidden");
  setProgress("Запускаем пакетную транскрибацию…", 0);
  queue.forEach((item) => { item.status = "pending"; item.progress = 0; item.output = null; });
  renderQueue();
  const result = await api().start_manual_job({
    videos: queue.map((item) => item.path),
    model: $("modelSize").value,
    language: $("language").value,
    device: $("device").value,
  });
  if (!result || !result.ok) {
    isRunning = false;
    $("runBtn").disabled = false;
    showToast("Не удалось начать Manual Mode: " + ((result && result.error) || "неизвестная ошибка"));
    return;
  }
  manualJob = result.job;
  setAppMode("manual");
  renderManualJob();
}

window.onManualJobUpdated = function (snapshot) {
  if (!snapshot || (manualJob && snapshot.job_id !== manualJob.job_id)) return;
  manualJob = snapshot;
  snapshot.items.forEach((item, index) => {
    if (!queue[index]) return;
    queue[index].progress = ManualState.pipelineProgress(
      queue[index].progress, item.stage, item.progress || 0
    );
    queue[index].status = item.state === "completed" ? "done"
      : ["failed", "render_failed", "no_speech"].includes(item.state) ? "failed"
      : ["transcribing", "rendering"].includes(item.state) ? "running" : "pending";
    if (item.output) queue[index].output = item.output;
  });
  isRunning = snapshot.items.some((item) => ["queued", "transcribing", "rendering"].includes(item.state));
  $("cancelBtn").classList.toggle("hidden", !isRunning);
  renderManualJob();
  hydrateManualTranscripts();
};

async function hydrateManualTranscripts() {
  if (!manualJob) return;
  for (const item of manualJob.items) {
    if (!["transcribed", "needs_review", "approved", "completed", "rendering", "render_failed"].includes(item.state)) continue;
    const cached = manualTranscripts.get(item.item_id);
    if (cached && cached.revision === item.revision) continue;
    const result = await api().get_transcript(item.item_id);
    if (result && result.ok) {
      manualTranscripts.set(item.item_id, result.transcript);
      if (manualSelectedId === item.item_id) {
        manualTranscript = result.transcript;
        renderManualEditor();
      }
      renderManualQueue();
    }
  }
  if (!manualSelectedId) {
    const first = manualJob.items.find((item) => manualTranscripts.has(item.item_id));
    if (first) selectManualItem(first.item_id);
  }
}

function renderManualJob() {
  if (!manualJob) return;
  $("autoWorkspace").classList.add("hidden");
  $("manualWorkspace").classList.remove("hidden");
  const items = manualJob.items;
  const ready = items.filter((item) => !["queued", "transcribing"].includes(item.state)).length;
  const errors = items.filter((item) => ["failed", "render_failed", "no_speech"].includes(item.state)).length;
  $("manualSummary").textContent = `Готовы ${ready}/${items.length} · Одобрены ${manualJob.approved_count} · Ошибки ${errors}`;
  $("manualLive").textContent = $("manualSummary").textContent;
  renderManualQueue();
  updateManualRunButton();
  const active = items.find((item) => ["transcribing", "rendering"].includes(item.state));
  if (active) {
    const fileProgress = queue[active.index] ? queue[active.index].progress : active.progress || 0;
    const overall = Math.round(((active.index + fileProgress / 100) / items.length) * 100);
    setProgress(`[${active.index + 1}/${items.length}] ${STAGE_LABELS[active.stage] || active.stage}`, overall);
  } else if (manualJob.transcription_settled) {
    setProgress(errors ? `Проверка доступна, ошибок: ${errors}` : "Транскрипция завершена — проверьте и одобрите", 100);
  }
}

function manualNeedsAttention(item) {
  if (["failed", "render_failed", "no_speech"].includes(item.state)) return true;
  const transcript = manualTranscripts.get(item.item_id);
  return transcript ? ManualState.attentionReasons(transcript).length > 0 : false;
}

function itemMatchesManualFilter(item) {
  if (manualFilter === "attention") return manualNeedsAttention(item);
  if (manualFilter === "reviewed") return ["approved", "completed", "rendering"].includes(item.state);
  if (manualFilter === "errors") return ["failed", "render_failed", "no_speech"].includes(item.state);
  return true;
}

function renderManualQueue() {
  if (!manualJob) return;
  const list = $("manualQueueList");
  list.innerHTML = "";
  manualJob.items.filter(itemMatchesManualFilter).forEach((item) => {
    const [icon, label] = MANUAL_STATUS[item.state] || ["•", item.state];
    const button = document.createElement("button");
    button.type = "button";
    button.className = "manual-item" + (item.item_id === manualSelectedId ? " selected" : "");
    const status = document.createElement("span"); status.textContent = icon;
    const text = document.createElement("span"); text.textContent = item.name;
    const small = document.createElement("small");
    small.textContent = item.error || (manualNeedsAttention(item) ? `${label} · есть предупреждения` : label);
    if (item.error) small.className = "error";
    text.appendChild(small);
    const pct = document.createElement("span");
    pct.textContent = ["transcribing", "rendering"].includes(item.state) ? `${item.progress || 0}%` : "";
    button.append(status, text, pct);
    button.addEventListener("click", () => selectManualItem(item.item_id));
    list.appendChild(button);
  });
}

async function selectManualItem(itemId) {
  if (manualSelectedId && manualSelectedId !== itemId) await flushManualPatches();
  manualSelectedId = itemId;
  renderManualQueue();
  const item = manualJob.items.find((candidate) => candidate.item_id === itemId);
  const transcript = manualTranscripts.get(itemId);
  if (!transcript) {
    manualTranscript = null;
    $("manualEditorContent").classList.add("hidden");
    $("manualEmpty").classList.remove("hidden");
    $("manualEmpty").textContent = item.error || "Транскрипт ещё не готов";
    return;
  }
  manualTranscript = transcript;
  const info = await api().video_info(item.path);
  if (manualSelectedId === itemId && info && info.media_url) $("manualVideo").src = info.media_url;
  renderManualEditor();
}

function renderManualEditor() {
  if (!manualTranscript || !manualJob) return;
  const item = manualJob.items.find((candidate) => candidate.item_id === manualSelectedId);
  if (!item) return;
  $("manualEmpty").classList.add("hidden");
  $("manualEditorContent").classList.remove("hidden");
  $("manualFileName").textContent = item.name;
  $("approveCurrent").textContent = item.state === "approved" ? "Одобрено" : "Одобрить файл";
  $("approveCurrent").disabled = item.state === "approved";
  const reasons = ManualState.attentionReasons(manualTranscript);
  $("manualAttention").classList.toggle("hidden", !reasons.length);
  $("manualAttention").textContent = reasons.join(" · ");

  const list = $("manualWordList");
  list.innerHTML = "";
  manualTranscript.words.forEach((word) => {
    const row = document.createElement("div");
    row.className = "word-row" + (word.deleted ? " deleted" : "")
      + (word.probability != null && word.probability < 0.65 ? " low-confidence" : "");
    const text = document.createElement("input");
    text.type = "text"; text.value = word.word; text.disabled = word.deleted;
    text.setAttribute("aria-label", "Текст слова");
    text.addEventListener("focus", () => { $("manualVideo").currentTime = word.start; });
    text.addEventListener("input", () => queueManualPatch(`text:${word.id}`, {
      op: "replace", word_id: word.id, text: text.value,
    }));
    const start = timingInput(word.start, "Начало слова");
    const end = timingInput(word.end, "Конец слова");
    const timingChanged = () => queueManualPatch(`timing:${word.id}`, {
      op: "set_timing", word_id: word.id, start: Number(start.value), end: Number(end.value),
    });
    start.addEventListener("input", timingChanged); end.addEventListener("input", timingChanged);
    const actions = document.createElement("span"); actions.className = "word-actions";
    const remove = document.createElement("button"); remove.type = "button";
    remove.textContent = word.deleted ? "↶" : "×";
    remove.title = word.deleted ? "Восстановить" : "Удалить слово";
    remove.addEventListener("click", () => saveManualPatchNow([{
      op: word.deleted ? "restore" : "delete", word_id: word.id,
    }], true));
    const insert = document.createElement("button"); insert.type = "button"; insert.textContent = "+";
    insert.title = "Вставить слово после";
    insert.addEventListener("click", () => insertWordAfter(word));
    actions.append(remove, insert);
    row.append(text, start, end, actions);
    list.appendChild(row);
  });
}

function timingInput(value, label) {
  const input = document.createElement("input");
  input.type = "number"; input.step = "0.01"; input.min = "0";
  input.className = "word-time"; input.value = Number(value).toFixed(2);
  input.setAttribute("aria-label", label);
  return input;
}

function queueManualPatch(key, operation) {
  if (!manualPendingItemId) manualPendingItemId = manualSelectedId;
  manualPendingPatches.set(key, operation);
  $("manualSaveState").textContent = "Есть несохранённые изменения";
  clearTimeout(manualPatchTimer);
  manualPatchTimer = setTimeout(flushManualPatches, 650);
}

function flushManualPatches() {
  clearTimeout(manualPatchTimer);
  if (!manualPendingPatches.size) return manualSaveChain;
  const batch = ManualState.capturePatchBatch(
    manualPendingItemId, Array.from(manualPendingPatches.values())
  );
  manualPendingPatches.clear();
  manualPendingItemId = null;
  return saveManualPatchNow(batch.operations, false, batch.itemId);
}

function saveManualPatchNow(operations, rerender, targetItemId) {
  const itemId = targetItemId || manualSelectedId;
  manualSaveChain = manualSaveChain.then(async () => {
    const targetTranscript = manualTranscripts.get(itemId);
    if (!targetTranscript) return;
    if (itemId === manualSelectedId) $("manualSaveState").textContent = "Сохраняем…";
    const result = await api().apply_transcript_patch(itemId, targetTranscript.revision, operations);
    if (!result || !result.ok) {
      if (itemId === manualSelectedId) $("manualSaveState").textContent = result && result.code === "revision_conflict"
          ? "Версия изменилась — перезагрузите файл" : "Ошибка сохранения";
      if (result && result.code === "revision_conflict") manualTranscripts.delete(itemId);
      return;
    }
    manualTranscripts.set(itemId, result.transcript);
    if (itemId === manualSelectedId) {
      manualTranscript = result.transcript;
      $("manualSaveState").textContent = "Сохранено";
      if (rerender) renderManualEditor();
    }
  });
  return manualSaveChain;
}

function insertWordAfter(word) {
  const text = window.prompt("Новое слово:", " ");
  if (!text || !text.trim()) return;
  const active = manualTranscript.words.filter((candidate) => !candidate.deleted);
  const index = active.findIndex((candidate) => candidate.id === word.id);
  const next = active[index + 1];
  const availableEnd = next ? next.start : Math.min(manualTranscript.duration || word.end + 0.5, word.end + 0.5);
  const start = word.end;
  const end = Math.max(start + 0.05, availableEnd);
  saveManualPatchNow([{ op: "insert_after", word_id: word.id, text, start, end }], true);
}

async function approveCurrentTranscript() {
  await flushManualPatches();
  if (!manualTranscript) return;
  const result = await api().approve_transcript(manualSelectedId, manualTranscript.revision);
  if (!result || !result.ok) {
    showToast("Нельзя одобрить: " + ((result && result.error) || "ошибка проверки"));
    return;
  }
  manualTranscript = result.transcript;
  manualTranscripts.set(manualSelectedId, manualTranscript);
  $("manualSaveState").textContent = "Одобрено";
  renderManualEditor();
}

async function approveCleanTranscripts() {
  await flushManualPatches();
  const result = await api().approve_clean_transcripts(manualJob.job_id);
  if (!result || !result.ok) return showToast("Массовое одобрение не выполнено: " + result.error);
  showToast(`Одобрено без предупреждений: ${result.approved.length}`);
}

async function retryManualFailures() {
  const result = await api().retry_manual_transcription(manualJob.job_id, null);
  if (!result || !result.ok) return showToast((result && result.error) || "Повтор не запущен");
  isRunning = true;
  $("cancelBtn").disabled = false;
  $("cancelBtn").textContent = "Остановить после файла";
  $("cancelBtn").classList.remove("hidden");
  showToast(`Повторно запущено: ${result.count}`);
}

async function retranscribeCurrentItem() {
  await flushManualPatches();
  if (!manualSelectedId) return;
  const result = await api().retranscribe_manual_item(manualSelectedId, {
    model: $("modelSize").value, language: $("language").value, device: $("device").value,
  });
  if (!result || !result.ok) return showToast((result && result.error) || "Повтор не запущен");
  manualTranscripts.delete(manualSelectedId);
  manualTranscript = null;
  isRunning = true;
  $("cancelBtn").disabled = false;
  $("cancelBtn").textContent = "Остановить после файла";
  $("cancelBtn").classList.remove("hidden");
  showToast("Создаём новую версию; предыдущая одобренная версия сохранена");
}

function selectNextAttention() {
  const items = manualJob.items.filter(manualNeedsAttention);
  if (!items.length) return showToast("Файлов с предупреждениями нет");
  const current = items.findIndex((item) => item.item_id === manualSelectedId);
  selectManualItem(items[(current + 1) % items.length].item_id);
}

function updateManualRunButton() {
  if (appMode !== "manual") return;
  const button = $("runBtn");
  if (!manualJob) {
    button.disabled = isRunning;
    button.textContent = queue.length > 1 ? `Транскрибировать (${queue.length})` : "Транскрибировать";
    return;
  }
  const gate = ManualState.renderGate(manualJob);
  button.disabled = !gate.enabled || manualJob.items.some((item) => item.state === "rendering");
  button.textContent = gate.label;
}

async function startManualRender() {
  await flushManualPatches();
  const result = await api().start_manual_render({ job_id: manualJob.job_id, style });
  if (!result || !result.ok) return showToast("Рендер не запущен: " + ((result && result.error) || "ошибка"));
  isRunning = true;
  $("runBtn").disabled = true;
  $("cancelBtn").disabled = false;
  $("cancelBtn").textContent = "Остановить после файла";
  $("cancelBtn").classList.remove("hidden");
  setProgress("Запускаем пакетный рендер…", 0);
}

window.onManualRenderDone = function (jobId, result) {
  if (!manualJob || manualJob.job_id !== jobId) return;
  isRunning = false;
  $("cancelBtn").classList.add("hidden");
  const text = `Рендер завершён: ${result.completed}, ошибок: ${result.failed}, пропущено: ${result.skipped}`;
  setProgress(text, 100);
  showToast(text);
  if (result.completed) {
    const done = manualJob.items.find((item) => item.output);
    if (done) lastOutputPath = done.output;
    $("resultActions").classList.remove("hidden");
  }
  updateManualRunButton();
};

async function cancelCurrentQueue() {
  $("cancelBtn").disabled = true;
  $("cancelBtn").textContent = "Останавливаем после файла…";
  await api().cancel_queue();
  showToast("Текущий файл завершится, остальные будут остановлены");
}
