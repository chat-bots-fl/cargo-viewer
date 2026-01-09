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
  const token = localStorage.getItem("session_token") || "";
  const resp = await fetch(`/api/dictionaries/points?name=${encodeURIComponent(query)}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!resp.ok) return [];
  const data = await resp.json().catch(() => ({}));
  return Array.isArray(data.data) ? data.data : [];
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
  const finishId = document.getElementById("finish_point_id");

  const startSuggest = "start_city_suggest";
  const finishSuggest = "finish_city_suggest";

  const onStartInput = debounce(async () => {
    const q = (startQ?.value || "").trim();
    if (q.length < 2) return renderSuggest(startSuggest, [], () => {});
    const items = await fetchCities(q);
    renderSuggest(startSuggest, items, (it) => {
      if (startQ) startQ.value = it.name;
      if (startId) startId.value = it.id;
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
      renderSuggest(finishSuggest, [], () => {});
    });
  }, 250);

  startQ?.addEventListener("input", onStartInput);
  finishQ?.addEventListener("input", onFinishInput);

  const applyBtn = document.getElementById("apply-filters");
  const resetBtn = document.getElementById("reset-filters");

  applyBtn?.addEventListener("click", () => {
    const params = {
      start_point_id: document.getElementById("start_point_id")?.value,
      finish_point_id: document.getElementById("finish_point_id")?.value,
      start_date: document.getElementById("start_date")?.value,
      weight_volume: document.getElementById("weight_volume")?.value,
      load_types: document.getElementById("load_types")?.value,
      truck_types: document.getElementById("truck_types")?.value,
    };
    CargoApp.loadCargos(qs(params));
  });

  resetBtn?.addEventListener("click", () => {
    ["start_city_query", "finish_city_query", "start_point_id", "finish_point_id", "start_date", "weight_volume", "load_types", "truck_types"].forEach(
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
