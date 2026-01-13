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

function getSessionToken() {
  let token = localStorage.getItem("session_token") || "";
  if (!token) {
    const match = document.cookie.match(new RegExp("(^| )session_token=([^;]*)"));
    token = match ? decodeURIComponent(match[2]) : "";
  }
  return token;
}

async function fetchCities(query) {
  const token = getSessionToken();
  const resp = await fetch(`/api/dictionaries/points?name=${encodeURIComponent(query)}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!resp.ok) return [];
  const data = await resp.json().catch(() => ({}));
  return Array.isArray(data.data) ? data.data : [];
}

async function fetchTruckTypes() {
  const token = getSessionToken();
  const resp = await fetch("/api/dictionaries/truck_types", {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!resp.ok) return [];
  const data = await resp.json().catch(() => ({}));
  return Array.isArray(data.data) ? data.data : [];
}

async function fetchLoadTypes() {
  const token = getSessionToken();
  const resp = await fetch("/api/dictionaries/load_types", {
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
    div.textContent = String(it.name || "");
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

  const loadTypesDropdown = document.getElementById("load-types-dropdown");
  const loadTypesToggle = document.getElementById("load-types-toggle");
  const loadTypesMenu = document.getElementById("load-types-menu");
  const loadTypesValue = document.getElementById("load_types");

  const truckTypesDropdown = document.getElementById("truck-types-dropdown");
  const truckTypesToggle = document.getElementById("truck-types-toggle");
  const truckTypesMenu = document.getElementById("truck-types-menu");
  const truckTypesValue = document.getElementById("truck_types");

  const startSuggest = "start_city_suggest";
  const finishSuggest = "finish_city_suggest";

  let loadTypesItems = null;
  let truckTypesItems = null;

  function parseCsvIds(value) {
    const raw = String(value || "");
    const parts = raw
      .split(",")
      .map((s) => s.trim())
      .filter((s) => /^\d+$/.test(s));

    const seen = new Set();
    const out = [];
    parts.forEach((id) => {
      if (seen.has(id)) return;
      seen.add(id);
      out.push(id);
    });
    return out;
  }

  function formatLoadTypesLabel(ids) {
    if (!ids.length) return { text: "Любой", title: "" };

    if (!Array.isArray(loadTypesItems) || !loadTypesItems.length) {
      return { text: `Выбрано: ${ids.length}`, title: ids.join(",") };
    }

    const byId = new Map(loadTypesItems.map((it) => [String(it.id), it]));
    const selected = ids.map((id) => byId.get(String(id))).filter(Boolean);
    if (!selected.length) return { text: `Выбрано: ${ids.length}`, title: ids.join(",") };

    const full = selected.map((it) => it.name || it.short_name || String(it.id)).filter(Boolean);
    const short = selected.map((it) => it.short_name || it.name || String(it.id)).filter(Boolean);

    return { text: short.join(", "), title: full.join(", ") };
  }

  function formatTruckTypesLabel(ids) {
    if (!ids.length) return { text: "Любой", title: "" };

    if (!Array.isArray(truckTypesItems) || !truckTypesItems.length) {
      return { text: `Выбрано: ${ids.length}`, title: ids.join(",") };
    }

    const byId = new Map(truckTypesItems.map((it) => [String(it.id), it]));
    const selected = ids.map((id) => byId.get(String(id))).filter(Boolean);
    if (!selected.length) return { text: `Выбрано: ${ids.length}`, title: ids.join(",") };

    const full = selected.map((it) => it.name || it.short_name || String(it.id)).filter(Boolean);
    const short = selected.map((it) => it.short_name || it.name || String(it.id)).filter(Boolean);

    return { text: short.join(", "), title: full.join(", ") };
  }

  function syncLoadTypesUIFromValue() {
    const selectedIds = parseCsvIds(loadTypesValue?.value);
    const { text, title } = formatLoadTypesLabel(selectedIds);
    if (loadTypesToggle) {
      loadTypesToggle.textContent = text;
      loadTypesToggle.title = title;
    }

    if (!loadTypesMenu || !Array.isArray(loadTypesItems) || !loadTypesItems.length) return;
    const selectedSet = new Set(selectedIds);
    loadTypesMenu.querySelectorAll("input[type='checkbox']").forEach((el) => {
      el.checked = selectedSet.has(String(el.value));
    });
  }

  function syncTruckTypesUIFromValue() {
    const selectedIds = parseCsvIds(truckTypesValue?.value);
    const { text, title } = formatTruckTypesLabel(selectedIds);
    if (truckTypesToggle) {
      truckTypesToggle.textContent = text;
      truckTypesToggle.title = title;
    }

    if (!truckTypesMenu || !Array.isArray(truckTypesItems) || !truckTypesItems.length) return;
    const selectedSet = new Set(selectedIds);
    truckTypesMenu.querySelectorAll("input[type='checkbox']").forEach((el) => {
      el.checked = selectedSet.has(String(el.value));
    });
  }

  function renderLoadTypesMenu(items) {
    if (!loadTypesMenu) return;
    const fragment = document.createDocumentFragment();

    items.forEach((it) => {
      const row = document.createElement("label");
      row.className = "dropdown-item";

      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = String(it.id);
      cb.addEventListener("change", () => {
        const selected = Array.from(loadTypesMenu.querySelectorAll("input[type='checkbox']:checked")).map((el) => el.value);
        if (loadTypesValue) loadTypesValue.value = selected.join(",");
        syncLoadTypesUIFromValue();
      });

      const span = document.createElement("span");
      span.textContent = it.name || it.short_name || String(it.id);

      row.appendChild(cb);
      row.appendChild(span);
      fragment.appendChild(row);
    });

    loadTypesMenu.replaceChildren(fragment);
  }

  function renderTruckTypesMenu(items) {
    if (!truckTypesMenu) return;
    const fragment = document.createDocumentFragment();

    items.forEach((it) => {
      const row = document.createElement("label");
      row.className = "dropdown-item";

      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = String(it.id);
      cb.addEventListener("change", () => {
        const selected = Array.from(truckTypesMenu.querySelectorAll("input[type='checkbox']:checked")).map(
          (el) => el.value
        );
        if (truckTypesValue) truckTypesValue.value = selected.join(",");
        syncTruckTypesUIFromValue();
      });

      const span = document.createElement("span");
      span.textContent = it.name || it.short_name || String(it.id);

      row.appendChild(cb);
      row.appendChild(span);
      fragment.appendChild(row);
    });

    truckTypesMenu.replaceChildren(fragment);
  }

  function openLoadTypesMenu() {
    if (!loadTypesMenu || !loadTypesToggle) return;
    loadTypesMenu.hidden = false;
    loadTypesToggle.setAttribute("aria-expanded", "true");
  }

  function closeLoadTypesMenu() {
    if (!loadTypesMenu || !loadTypesToggle) return;
    loadTypesMenu.hidden = true;
    loadTypesToggle.setAttribute("aria-expanded", "false");
  }

  function openTruckTypesMenu() {
    if (!truckTypesMenu || !truckTypesToggle) return;
    truckTypesMenu.hidden = false;
    truckTypesToggle.setAttribute("aria-expanded", "true");
  }

  function closeTruckTypesMenu() {
    if (!truckTypesMenu || !truckTypesToggle) return;
    truckTypesMenu.hidden = true;
    truckTypesToggle.setAttribute("aria-expanded", "false");
  }

  async function ensureLoadTypesLoaded() {
    if (!loadTypesMenu || loadTypesItems) return;
    loadTypesMenu.innerHTML = '<div class="muted" style="padding:10px 12px;">Загрузка…</div>';

    const items = await fetchLoadTypes().catch(() => []);
    loadTypesItems = items;

    if (!Array.isArray(items) || !items.length) {
      loadTypesMenu.innerHTML = '<div class="muted" style="padding:10px 12px;">Не удалось загрузить</div>';
      return;
    }

    renderLoadTypesMenu(items);
    syncLoadTypesUIFromValue();
  }

  async function ensureTruckTypesLoaded() {
    if (!truckTypesMenu || truckTypesItems) return;
    truckTypesMenu.innerHTML = '<div class="muted" style="padding:10px 12px;">Загрузка…</div>';

    const items = await fetchTruckTypes().catch(() => []);
    truckTypesItems = items;

    if (!Array.isArray(items) || !items.length) {
      truckTypesMenu.innerHTML = '<div class="muted" style="padding:10px 12px;">Не удалось загрузить</div>';
      return;
    }

    renderTruckTypesMenu(items);
    syncTruckTypesUIFromValue();
  }

  loadTypesToggle?.addEventListener("click", async (evt) => {
    evt.preventDefault();
    evt.stopPropagation();

    if (loadTypesMenu?.hidden === false) {
      closeLoadTypesMenu();
      return;
    }

    closeTruckTypesMenu();
    openLoadTypesMenu();
    await ensureLoadTypesLoaded();
  });

  loadTypesMenu?.addEventListener("click", (evt) => {
    evt.stopPropagation();
  });

  truckTypesToggle?.addEventListener("click", async (evt) => {
    evt.preventDefault();
    evt.stopPropagation();

    if (truckTypesMenu?.hidden === false) {
      closeTruckTypesMenu();
      return;
    }

    closeLoadTypesMenu();
    openTruckTypesMenu();
    await ensureTruckTypesLoaded();
  });

  truckTypesMenu?.addEventListener("click", (evt) => {
    evt.stopPropagation();
  });

  document.addEventListener("click", (evt) => {
    if (loadTypesDropdown && loadTypesMenu && loadTypesMenu.hidden === false) {
      const target = evt.target;
      if (!(target && loadTypesDropdown.contains(target))) {
        closeLoadTypesMenu();
      }
    }

    if (!truckTypesDropdown || !truckTypesMenu || truckTypesMenu.hidden) return;
    const target = evt.target;
    if (target && truckTypesDropdown.contains(target)) return;
    closeTruckTypesMenu();
  });

  loadTypesValue?.addEventListener("input", syncLoadTypesUIFromValue);
  loadTypesValue?.addEventListener("change", syncLoadTypesUIFromValue);
  syncLoadTypesUIFromValue();

  truckTypesValue?.addEventListener("input", syncTruckTypesUIFromValue);
  truckTypesValue?.addEventListener("change", syncTruckTypesUIFromValue);
  syncTruckTypesUIFromValue();

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
      if (targetId === "load_types") {
        closeLoadTypesMenu();
        loadTypesToggle?.focus();
      } else if (targetId === "truck_types") {
        closeTruckTypesMenu();
        truckTypesToggle?.focus();
      } else if (typeof input.focus === "function") {
        input.focus();
      }
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
  const modeInput = document.getElementById("mode");
  const modeToggle = document.getElementById("mode-toggle");

  function setMode(value) {
    const normalized = value === "all" ? "all" : "my";
    const previous = modeInput ? String(modeInput.value || "") : "";
    if (modeInput) modeInput.value = normalized;
    if (modeToggle) modeToggle.classList.toggle("is-all", normalized === "all");

    if (!modeToggle) return;
    modeToggle.querySelectorAll("button[data-mode-value]").forEach((btn) => {
      const isActive = btn.getAttribute("data-mode-value") === normalized;
      btn.classList.toggle("is-active", isActive);
      btn.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
    return previous !== normalized;
  }

  modeToggle?.addEventListener("click", (evt) => {
    const btn = evt.target && evt.target.closest ? evt.target.closest("button[data-mode-value]") : null;
    if (!btn) return;
    evt.preventDefault();
    const changed = setMode(btn.getAttribute("data-mode-value"));
    if (changed && applyBtn && !applyBtn.disabled) {
      applyBtn.click();
    }
  });

  setMode(modeInput?.value || "my");

  function setApplyLoading(isLoading) {
    if (!applyBtn) return;
    applyBtn.disabled = Boolean(isLoading);
    applyBtn.classList.toggle("is-loading", Boolean(isLoading));
    applyBtn.setAttribute("aria-busy", isLoading ? "true" : "false");

    if (modeToggle) {
      modeToggle.querySelectorAll("button[data-mode-value]").forEach((btn) => {
        btn.disabled = Boolean(isLoading);
      });
    }
  }

  function isCargoListRequest(evt) {
    const target = evt?.detail?.target;
    if (!target || !(target instanceof Element)) return false;
    return target.id === "cargo-list";
  }

  document.body.addEventListener("htmx:afterRequest", (evt) => {
    if (!applyBtn || !applyBtn.classList.contains("is-loading")) return;
    if (!isCargoListRequest(evt)) return;
    setApplyLoading(false);
  });

  document.body.addEventListener("htmx:afterSwap", (evt) => {
    if (!applyBtn || !applyBtn.classList.contains("is-loading")) return;
    if (!isCargoListRequest(evt)) return;
    setApplyLoading(false);
  });

  document.body.addEventListener("htmx:responseError", (evt) => {
    if (!applyBtn || !applyBtn.classList.contains("is-loading")) return;
    if (!isCargoListRequest(evt)) return;
    setApplyLoading(false);
  });

  applyBtn?.addEventListener("click", async () => {
    setApplyLoading(true);
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
      mode: document.getElementById("mode")?.value,
    };

    try {
      CargoApp.loadCargos(qs(params));
    } catch (e) {
      setApplyLoading(false);
    }
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
    setMode("my");
    document.getElementById("start_city_suggest")?.replaceChildren();
    document.getElementById("finish_city_suggest")?.replaceChildren();
    closeLoadTypesMenu();
    syncLoadTypesUIFromValue();
    closeTruckTypesMenu();
    syncTruckTypesUIFromValue();
    CargoApp.loadCargos("");
  });
});
