/* global CargoApp */

function qs(params) {
  const usp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null) return;
    const s = String(v).trim();
    if (!s) return;
    usp.set(k, s);
  });
  return usp.toString();
}

async function fetchCities(query) {
  // Keep this token lookup in sync with CargoApp.getToken() (localStorage + cookie fallback).
  let token = localStorage.getItem("session_token") || "";
  if (!token) {
    const match = document.cookie.match(new RegExp("(^| )session_token=([^;]*)"));
    token = match ? decodeURIComponent(match[2]) : "";
  }
  const resp = await fetch(`/api/dictionaries/points?name=${encodeURIComponent(query)}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!resp.ok) return [];
  const data = await resp.json().catch(() => ({}));
  return Array.isArray(data.data) ? data.data : [];
}

async function resolveCityToPoint(query) {
  const q = String(query || "").trim();
  if (!q) return null;
  const items = await fetchCities(q);
  if (!items.length) return null;

  const qLower = q.toLowerCase();
  const exact = items.find((it) => String(it?.name || "").trim().toLowerCase() === qLower);
  if (exact) return exact;

  const startsWithComma = items.find((it) => String(it?.name || "").trim().toLowerCase().startsWith(`${qLower},`));
  if (startsWithComma) return startsWithComma;

  const sortedByNameLen = items
    .filter((it) => it && typeof it === "object")
    .slice()
    .sort((a, b) => String(a.name || "").length - String(b.name || "").length);
  return sortedByNameLen[0] || items[0];
}

function renderSuggest(containerId, items, onPick) {
  const container = document.getElementById(containerId);
  if (!container) return;
  if (!items.length) {
    container.innerHTML = "";
    return;
  }
  const list = document.createElement("div");
  list.className = "suggest-list";
  items.slice(0, 10).forEach((it) => {
    const div = document.createElement("div");
    div.className = "suggest-item";
    div.textContent = `${it.name} (id: ${it.id})`;
    div.addEventListener("click", () => onPick(it));
    list.appendChild(div);
  });
  container.innerHTML = "";
  container.appendChild(list);
}

function debounce(fn, ms) {
  let t = null;
  return (...args) => {
    if (t) clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

document.addEventListener("DOMContentLoaded", () => {
  const startQ = document.getElementById("start_city_query");
  const finishQ = document.getElementById("finish_city_query");
  const startId = document.getElementById("start_point_id");
  const startType = document.getElementById("start_point_type");
  const finishId = document.getElementById("finish_point_id");
  const finishType = document.getElementById("finish_point_type");

  const startSuggest = "start_city_suggest";
  const finishSuggest = "finish_city_suggest";

  document.querySelectorAll("[data-clear-target]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-clear-target");
      if (!targetId) return;
      const input = document.getElementById(targetId);
      if (!input) return;

      input.value = "";
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));

      if (targetId === "start_city_query") document.getElementById(startSuggest)?.replaceChildren();
      if (targetId === "finish_city_query") document.getElementById(finishSuggest)?.replaceChildren();
      if (typeof input.focus === "function") input.focus();
    });
  });

  const onStartInput = debounce(async () => {
    const q = (startQ?.value || "").trim();
    if (q.length < 2) return renderSuggest(startSuggest, [], () => {});
    const items = await fetchCities(q);
    renderSuggest(startSuggest, items, (it) => {
      if (startQ) startQ.value = it.name;
      if (startId) startId.value = it.id;
      if (startType) startType.value = it.type;
      renderSuggest(startSuggest, [], () => {});
    });
  }, 250);

  const onFinishInput = debounce(async () => {
    const q = (finishQ?.value || "").trim();
    if (q.length < 2) return renderSuggest(finishSuggest, [], () => {});
    const items = await fetchCities(q);
    renderSuggest(finishSuggest, items, (it) => {
      if (finishQ) finishQ.value = it.name;
      if (finishId) finishId.value = it.id;
      if (finishType) finishType.value = it.type;
      renderSuggest(finishSuggest, [], () => {});
    });
  }, 250);

  startQ?.addEventListener("input", () => {
    if (startId) startId.value = "";
    if (startType) startType.value = "";
    onStartInput();
  });
  finishQ?.addEventListener("input", () => {
    if (finishId) finishId.value = "";
    if (finishType) finishType.value = "";
    onFinishInput();
  });

  const applyBtn = document.getElementById("apply-filters");
  const resetBtn = document.getElementById("reset-filters");

  applyBtn?.addEventListener("click", async () => {
    const startCityText = document.getElementById("start_city_query")?.value;
    const finishCityText = document.getElementById("finish_city_query")?.value;

    // If user typed a city but didn't pick from suggestions, try to resolve to point_id automatically.
    if (startCityText && startId && !startId.value) {
      const resolved = await resolveCityToPoint(startCityText).catch(() => null);
      if (resolved) {
        startId.value = resolved.id;
        if (startQ) startQ.value = resolved.name;
        if (startType) startType.value = resolved.type;
      }
    }
    if (finishCityText && finishId && !finishId.value) {
      const resolved = await resolveCityToPoint(finishCityText).catch(() => null);
      if (resolved) {
        finishId.value = resolved.id;
        if (finishQ) finishQ.value = resolved.name;
        if (finishType) finishType.value = resolved.type;
      }
    }

    const params = {
      start_point_id: document.getElementById("start_point_id")?.value,
      start_point_type: document.getElementById("start_point_type")?.value,
      finish_point_id: document.getElementById("finish_point_id")?.value,
      finish_point_type: document.getElementById("finish_point_type")?.value,
      start_date: document.getElementById("start_date")?.value,
      weight_volume: document.getElementById("weight_volume")?.value,
      load_types: document.getElementById("load_types")?.value,
      truck_types: document.getElementById("truck_types")?.value,
    };
    CargoApp.loadCargos(qs(params));
  });

  resetBtn?.addEventListener("click", () => {
    [
      "start_city_query",
      "finish_city_query",
      "start_point_id",
      "start_point_type",
      "finish_point_id",
      "finish_point_type",
      "start_date",
      "weight_volume",
      "load_types",
      "truck_types",
    ].forEach(
      (id) => {
        const el = document.getElementById(id);
        if (el) el.value = "";
      }
    );
    document.getElementById("start_city_suggest")?.replaceChildren();
    document.getElementById("finish_city_suggest")?.replaceChildren();
    CargoApp.loadCargos("");
  });
});
