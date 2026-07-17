(() => {
  "use strict";

  const GLOBAL_KEY = "__douyinFavoritesCapture";
  const VERSION = "1.0.0";
  const TARGET = "/aweme/v1/web/aweme/listcollection/";

  if (window[GLOBAL_KEY]?.version === VERSION) return;

  const state = {
    installedAt: new Date().toISOString(),
    responses: [],
    items: new Map(),
    errors: [],
    requestCount: 0,
    firstResponseAt: null,
    lastResponseAt: null,
    hasMore: null,
    cursors: [],
  };

  const clone = (value) => {
    try {
      return structuredClone(value);
    } catch (_) {
      return JSON.parse(JSON.stringify(value));
    }
  };

  function findAwemeLists(value, depth = 0, seen = new Set()) {
    if (!value || typeof value !== "object" || depth > 7 || seen.has(value)) return [];
    seen.add(value);
    const lists = [];
    if (Array.isArray(value.aweme_list)) lists.push(value.aweme_list);
    for (const child of Object.values(value)) {
      if (child && typeof child === "object") {
        lists.push(...findAwemeLists(child, depth + 1, seen));
      }
    }
    return lists;
  }

  function findScalar(value, keys, depth = 0, seen = new Set()) {
    if (!value || typeof value !== "object" || depth > 5 || seen.has(value)) return null;
    seen.add(value);
    for (const key of keys) {
      if (Object.prototype.hasOwnProperty.call(value, key) && value[key] != null) return value[key];
    }
    for (const child of Object.values(value)) {
      const found = findScalar(child, keys, depth + 1, seen);
      if (found != null) return found;
    }
    return null;
  }

  function ingest(payload, meta = {}) {
    const capturedAt = new Date().toISOString();
    const lists = findAwemeLists(payload);
    if (lists.length === 0) return { lists: 0, added: 0, unique: state.items.size };
    let added = 0;
    for (const list of lists) {
      for (const item of list) {
        const id = item?.aweme_id == null ? "" : String(item.aweme_id);
        if (!id) continue;
        if (!state.items.has(id)) added += 1;
        state.items.set(id, clone(item));
      }
    }
    const hasMore = findScalar(payload, ["has_more"]);
    const cursor = findScalar(payload, ["cursor", "max_cursor", "min_cursor"]);
    if (hasMore != null) state.hasMore = Boolean(hasMore);
    if (cursor != null) state.cursors.push(cursor);
    state.requestCount += 1;
    state.firstResponseAt ||= capturedAt;
    state.lastResponseAt = capturedAt;
    state.responses.push({
      captured_at: capturedAt,
      url: meta.url || "",
      transport: meta.transport || "unknown",
      item_count: lists.reduce((total, list) => total + list.length, 0),
      added_unique: added,
      has_more: hasMore,
      cursor,
      payload: clone(payload),
    });
    return { lists: lists.length, added, unique: state.items.size };
  }

  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await originalFetch(...args);
    const url = String(args[0]?.url || args[0] || response.url || "");
    if (url.includes(TARGET)) {
      response.clone().json()
        .then((payload) => ingest(payload, { url, transport: "fetch" }))
        .catch((error) => state.errors.push({ at: new Date().toISOString(), source: "fetch", message: String(error) }));
    }
    return response;
  };

  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this.__douyinCaptureUrl = String(url || "");
    return originalOpen.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.send = function (...args) {
    if (this.__douyinCaptureUrl?.includes(TARGET)) {
      this.addEventListener("load", () => {
        try {
          let payload = this.response;
          if (typeof payload === "string") payload = JSON.parse(payload);
          if (payload && typeof payload === "object") {
            ingest(payload, { url: this.__douyinCaptureUrl, transport: "xhr" });
          }
        } catch (error) {
          state.errors.push({ at: new Date().toISOString(), source: "xhr", message: String(error) });
        }
      }, { once: true });
    }
    return originalSend.apply(this, args);
  };

  function collectBootstrap() {
    let parsed = 0;
    let added = 0;
    const scripts = document.querySelectorAll('script[type="application/json"], script:not([src])');
    for (const script of scripts) {
      const text = script.textContent?.trim();
      if (!text || text.length < 2 || (!text.startsWith("{") && !text.startsWith("["))) continue;
      try {
        const result = ingest(JSON.parse(text), { url: location.href, transport: "bootstrap" });
        if (result.lists > 0) parsed += 1;
        added += result.added;
      } catch (_) {
        // Inline scripts that are not pure JSON are intentionally ignored.
      }
    }
    return { parsed_scripts: parsed, added_unique: added, unique: state.items.size };
  }

  function findScrollContainer() {
    const preferred = document.querySelector(".route-scroll-container");
    if (preferred && preferred.scrollHeight > preferred.clientHeight) return preferred;
    const candidates = [...document.querySelectorAll("body *")]
      .filter((element) => element.scrollHeight > element.clientHeight + 100)
      .sort((a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight));
    return candidates[0] || document.scrollingElement || document.documentElement;
  }

  async function scroll(options = {}) {
    const intervalMs = Number(options.interval_ms || 600);
    const stepPx = Number(options.step_px || 800);
    const maxDurationMs = Number(options.max_duration_ms || 120000);
    const idleRoundsLimit = Number(options.idle_rounds || 8);
    const container = findScrollContainer();
    const started = Date.now();
    let idleRounds = 0;
    let previousUnique = state.items.size;
    let previousTop = -1;

    while (Date.now() - started < maxDurationMs) {
      const beforeTop = container.scrollTop;
      container.scrollBy({ top: stepPx, behavior: "auto" });
      await new Promise((resolve) => setTimeout(resolve, intervalMs));
      const unique = state.items.size;
      const atBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 4;
      const progressed = unique > previousUnique || container.scrollTop > beforeTop || container.scrollTop > previousTop;
      idleRounds = progressed ? 0 : idleRounds + 1;
      previousUnique = unique;
      previousTop = container.scrollTop;
      if (state.hasMore === false && atBottom) break;
      if (atBottom && idleRounds >= idleRoundsLimit) break;
    }
    return status();
  }

  function status() {
    return {
      version: VERSION,
      installed_at: state.installedAt,
      first_response_at: state.firstResponseAt,
      last_response_at: state.lastResponseAt,
      request_count: state.requestCount,
      captured_unique: state.items.size,
      has_more: state.hasMore,
      last_cursor: state.cursors.at(-1) ?? null,
      errors: clone(state.errors),
      page_url: location.href,
    };
  }

  function exportData(meta = {}) {
    return {
      schema_version: 1,
      exported_at: new Date().toISOString(),
      capture: status(),
      displayed_total: meta.displayed_total ?? null,
      collection: meta.collection || "",
      page_complete: meta.page_complete ?? (state.hasMore === false),
      aweme_list: [...state.items.values()].map(clone),
      responses: clone(state.responses),
    };
  }

  function download(filename = "douyin-favorites.json", meta = {}) {
    const blob = new Blob([JSON.stringify(exportData(meta), null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  }

  window[GLOBAL_KEY] = Object.freeze({
    version: VERSION,
    ingest,
    collectBootstrap,
    scroll,
    status,
    exportData,
    download,
  });
})();
