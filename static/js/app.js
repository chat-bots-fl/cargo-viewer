/* global htmx */

const CargoApp = (() => {
  const tokenKey = "session_token";

  function getToken() {
    return localStorage.getItem(tokenKey) || "";
  }

  function setToken(token) {
    if (!token) return;
    localStorage.setItem(tokenKey, token);
  }

  async function postJson(url, payload) {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const message = data && data.error ? data.error : `HTTP ${resp.status}`;
      throw new Error(message);
    }
    return data;
  }

  async function loginWithInitData(initData) {
    const data = await postJson("/api/auth/telegram", { init_data: initData });
    setToken(data.session_token);
    const driverNameEl = document.getElementById("driver-name");
    if (driverNameEl && data.driver) {
      const name = data.driver.first_name || data.driver.username || `#${data.driver.driver_id}`;
      driverNameEl.textContent = name;
    }
    return data.session_token;
  }

  async function ensureSession() {
    const existing = getToken();
    if (existing) return existing;

    const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
    if (tg && tg.initData) {
      return loginWithInitData(tg.initData);
    }

    const devAuth = document.getElementById("dev-auth");
    if (devAuth) devAuth.classList.remove("hidden");
    throw new Error("Telegram WebApp not detected. Provide initData in Dev auth.");
  }

  function configureHtmxAuth() {
    document.body.addEventListener("htmx:configRequest", (evt) => {
      const token = getToken();
      if (!token) return;
      evt.detail.headers["Authorization"] = `Bearer ${token}`;
    });

    document.body.addEventListener("htmx:afterRequest", (evt) => {
      const xhr = evt.detail && evt.detail.xhr ? evt.detail.xhr : null;
      if (!xhr || !xhr.getResponseHeader) return;
      const refreshed = xhr.getResponseHeader("X-Session-Token");
      if (refreshed) setToken(refreshed);
    });
  }

  function openModalWithUrl(url) {
    const root = document.getElementById("modal-root");
    const body = document.getElementById("modal-body");
    if (!root || !body) return;
    root.classList.remove("hidden");
    root.setAttribute("aria-hidden", "false");
    htmx.ajax("GET", url, { target: "#modal-body", swap: "innerHTML" });
  }

  function closeModal() {
    const root = document.getElementById("modal-root");
    if (!root) return;
    root.classList.add("hidden");
    root.setAttribute("aria-hidden", "true");
  }

  function bindModal() {
    document.body.addEventListener("click", (evt) => {
      const el = evt.target;
      if (!el) return;
      const close = el.closest && el.closest("[data-modal-close='1']");
      if (close) closeModal();
    });
  }

  function loadCargos(queryString = "") {
    const target = document.getElementById("cargo-list");
    if (!target) return;
    const url = `/api/cargos/${queryString ? `?${queryString}` : ""}`;
    htmx.ajax("GET", url, { target: "#cargo-list", swap: "innerHTML" });
  }

  function bindCargoClicks() {
    document.body.addEventListener("click", (evt) => {
      const el = evt.target;
      const card = el && el.closest ? el.closest("[data-cargo-open]") : null;
      if (!card) return;
      const cargoId = card.getAttribute("data-cargo-open");
      if (!cargoId) return;
      openModalWithUrl(`/api/cargos/${encodeURIComponent(cargoId)}/`);
    });
  }

  async function bootstrap() {
    configureHtmxAuth();
    bindModal();
    bindCargoClicks();

    try {
      await ensureSession();
      loadCargos("");
    } catch (e) {
      const cargoList = document.getElementById("cargo-list");
      if (cargoList) cargoList.innerHTML = `<div class="muted">${e.message}</div>`;
    }

    const devBtn = document.getElementById("dev-login");
    const devInput = document.getElementById("dev-initdata");
    if (devBtn && devInput) {
      devBtn.addEventListener("click", async () => {
        try {
          await loginWithInitData(devInput.value.trim());
          document.getElementById("dev-auth")?.classList.add("hidden");
          loadCargos("");
        } catch (e) {
          alert(e.message);
        }
      });
    }
  }

  return {
    bootstrap,
    loadCargos,
  };
})();

document.addEventListener("DOMContentLoaded", () => {
  CargoApp.bootstrap();
});
