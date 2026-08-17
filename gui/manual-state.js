(function (root, factory) {
  const value = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = value;
  if (root) root.ManualState = value;
})(typeof window !== "undefined" ? window : globalThis, function () {
  const ACTIVE_TRANSCRIPTION = new Set(["queued", "transcribing"]);

  function renderGate(snapshot) {
    const items = (snapshot && snapshot.items) || [];
    const approved = (snapshot && snapshot.approved_count) || 0;
    if (!snapshot || !snapshot.transcription_settled) {
      const active = items.filter((item) => ACTIVE_TRANSCRIPTION.has(item.state)).length;
      return { enabled: false, label: `Ждём транскрибацию: ${active}` };
    }
    if (!approved) return { enabled: false, label: "Одобрите хотя бы один файл" };
    return { enabled: true, label: `Рендер одобренных (${approved})` };
  }

  function attentionReasons(transcript) {
    const words = ((transcript && transcript.words) || []).filter((word) => !word.deleted);
    const low = words.filter(
      (word) => word.probability !== null && word.probability !== undefined && word.probability < 0.65
    ).length;
    const reasons = [];
    if (low) reasons.push(`Низкая уверенность: ${low} ${low === 1 ? "слово" : "слов"}`);
    if (!words.length) reasons.push("Речь не распознана");
    return reasons;
  }

  function capturePatchBatch(itemId, operations) {
    return { itemId, operations: operations.slice() };
  }

  function pipelineProgress(previous, stage, percent) {
    const pct = Math.max(0, Math.min(100, Number(percent) || 0)) / 100;
    const ranges = {
      downloading_model: [0, 4], loading_model: [4, 5], transcribing: [5, 45],
      preparing: [45, 46], building: [46, 65], compositing: [65, 66],
      rendering: [66, 99], done: [100, 100], completed: [100, 100],
    };
    const range = ranges[stage];
    const mapped = range ? range[0] + (range[1] - range[0]) * pct : Number(percent) || 0;
    return Math.max(Number(previous) || 0, Math.round(mapped));
  }

  return { attentionReasons, capturePatchBatch, pipelineProgress, renderGate };
});
