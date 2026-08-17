const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const modulePath = path.join(__dirname, "..", "gui", "creator-channel.js");
const channel = fs.existsSync(modulePath) ? require(modulePath) : {};

test("exports the creator channel action", () => {
  assert.equal(typeof channel.openCreatorChannel, "function");
});

test("keeps the app quiet when the browser opens", async () => {
  const notices = [];

  const result = await channel.openCreatorChannel(
    { open_creator_channel: async () => ({ ok: true }) },
    (message) => notices.push(message),
  );

  assert.deepEqual(result, { ok: true });
  assert.deepEqual(notices, []);
});

test("shows a non-blocking notice when Windows refuses the browser", async () => {
  const notices = [];

  const result = await channel.openCreatorChannel(
    { open_creator_channel: async () => ({ ok: false, error: "нет браузера" }) },
    (message) => notices.push(message),
  );

  assert.deepEqual(result, { ok: false, error: "нет браузера" });
  assert.deepEqual(notices, ["Не удалось открыть @daipotestit: нет браузера"]);
});

test("turns bridge exceptions into a non-blocking notice", async () => {
  const notices = [];

  const result = await channel.openCreatorChannel(
    { open_creator_channel: async () => { throw new Error("bridge offline"); } },
    (message) => notices.push(message),
  );

  assert.deepEqual(result, { ok: false, error: "Error: bridge offline" });
  assert.deepEqual(notices, ["Не удалось открыть @daipotestit: Error: bridge offline"]);
});
