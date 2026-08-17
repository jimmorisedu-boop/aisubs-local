const test = require('node:test');
const assert = require('node:assert/strict');

const { attentionReasons, capturePatchBatch, pipelineProgress, renderGate } = require('../gui/manual-state.js');

test('render gate explains how many transcriptions are still active', () => {
  const gate = renderGate({
    transcription_settled: false,
    approved_count: 2,
    items: [{ state: 'transcribing' }, { state: 'queued' }, { state: 'approved' }],
  });

  assert.deepEqual(gate, { enabled: false, label: 'Ждём транскрибацию: 2' });
});

test('render gate allows one batch action for approved files', () => {
  const gate = renderGate({
    transcription_settled: true,
    approved_count: 7,
    items: [{ state: 'approved' }],
  });

  assert.deepEqual(gate, { enabled: true, label: 'Рендер одобренных (7)' });
});

test('low confidence is attention but not a blocking validation error', () => {
  const reasons = attentionReasons({
    words: [
      { word: ' хорошо', probability: 0.9, deleted: false },
      { word: ' неясно', probability: 0.42, deleted: false },
    ],
  });

  assert.deepEqual(reasons, ['Низкая уверенность: 1 слово']);
});

test('autosave batch keeps the item selected when editing began', () => {
  const batch = capturePatchBatch('item-a', [{ op: 'replace', word_id: 'w1', text: ' правка' }]);
  const currentlySelectedLater = 'item-b';

  assert.equal(batch.itemId, 'item-a');
  assert.notEqual(batch.itemId, currentlySelectedLater);
  assert.equal(batch.operations[0].word_id, 'w1');
});

test('auto pipeline progress remains monotonic across stage resets', () => {
  let progress = 0;
  progress = pipelineProgress(progress, 'transcribing', 100);
  const afterTranscription = progress;
  progress = pipelineProgress(progress, 'preparing', 0);
  const afterPreparing = progress;
  progress = pipelineProgress(progress, 'building', 50);
  const afterBuilding = progress;
  progress = pipelineProgress(progress, 'rendering', 10);

  assert.equal(afterTranscription, 45);
  assert.ok(afterPreparing >= afterTranscription);
  assert.ok(afterBuilding >= afterPreparing);
  assert.ok(progress >= afterBuilding);
  assert.ok(progress < 100);
});
