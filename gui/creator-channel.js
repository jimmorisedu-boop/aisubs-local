(function (root, factory) {
  const creatorChannel = factory();
  if (typeof module === "object" && module.exports) module.exports = creatorChannel;
  root.CreatorChannel = creatorChannel;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  async function openCreatorChannel(api, notify) {
    try {
      const result = await api.open_creator_channel();
      if (!result || !result.ok) {
        const error = (result && result.error) || "неизвестная ошибка";
        notify("Не удалось открыть @daipotestit: " + error);
      }
      return result;
    } catch (error) {
      const message = String(error);
      notify("Не удалось открыть @daipotestit: " + message);
      return { ok: false, error: message };
    }
  }

  return { openCreatorChannel };
});
