/* global htmx */

const CargoApp = (() => {
  const tokenKey = "session_token";

  function getToken() {
    // Try localStorage first, fallback to cookie
    let token = localStorage.getItem(tokenKey) || "";
    if (!token) {
      const match = document.cookie.match(new RegExp('(^| )' + tokenKey + '=([^;]*)'));
      token = match ? decodeURIComponent(match[1]) : "";
    }
    console.log("[CargoApp] getToken() - token exists:", !!token, "length:", token.length, "source:", localStorage.getItem(tokenKey) ? "localStorage" : "cookie");
    return token;
  }

  function setToken(token) {
    console.log("[CargoApp] setToken() - token:", token ? token.substring(0, 20) + "..." : "null");
    if (!token) return;
    
    // Save to both localStorage and cookie for Telegram WebApp compatibility
    localStorage.setItem(tokenKey, token);
    document.cookie = `${tokenKey}=${encodeURIComponent(token)}; path=/; max-age=86400; SameSite=Lax`;
    console.log("[CargoApp] setToken() - saved to localStorage and cookie");
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
    console.log("[CargoApp] loginWithInitData called");
    console.log("[CargoApp] initData length:", initData.length);
    console.log("[CargoApp] initData prefix:", initData.substring(0, 100));
    
    const payload = { init_data: initData };
    console.log("[CargoApp] Sending payload:", JSON.stringify(payload).substring(0, 200));
    
    const data = await postJson("/api/auth/telegram", payload);
    console.log("[CargoApp] Login response:", data);
    console.log("[CargoApp] Login response.session_token:", data.session_token);
    console.log("[CargoApp] Login response.driver:", data.driver);
    
    if (!data.session_token) {
      console.error("[CargoApp] ERROR: No session_token in response!");
      throw new Error("No session token in response");
    }
    
    setToken(data.session_token);
    console.log("[CargoApp] Token set, verifying...");
    
    const verifyToken = getToken();
    console.log("[CargoApp] Verified token:", verifyToken ? verifyToken.substring(0, 20) + "..." : "null");
    
    const driverNameEl = document.getElementById("driver-name");
    if (driverNameEl && data.driver) {
      const name = data.driver.first_name || data.driver.username || `#${data.driver.driver_id}`;
      driverNameEl.textContent = name;
      console.log("[CargoApp] Driver name set to:", name);
    }
    return data.session_token;
  }

  async function ensureSession() {
    const existing = getToken();
    if (existing) {
      console.log("[CargoApp] Using existing token:", existing.substring(0, 10) + "...");
      return existing;
    }

    console.log("[CargoApp] Checking for Telegram WebApp...");
    console.log("[CargoApp] window.Telegram:", typeof window.Telegram);
    console.log("[CargoApp] window.Telegram.WebApp:", typeof window.Telegram?.WebApp);
    
    const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
    
    if (tg) {
      console.log("[CargoApp] Telegram WebApp found");
      console.log("[CargoApp] initData:", tg.initData ? tg.initData.substring(0, 50) + "..." : "not available");
      
      if (tg.initData) {
        console.log("[CargoApp] Logging in with initData...");
        return loginWithInitData(tg.initData);
      } else {
        console.warn("[CargoApp] Telegram WebApp found but no initData available");
      }
    } else {
      console.warn("[CargoApp] Telegram WebApp not detected");
    }

    const devAuth = document.getElementById("dev-auth");
    if (devAuth) {
      console.log("[CargoApp] Showing dev auth section");
      devAuth.classList.remove("hidden");
    }
    
    throw new Error("Telegram WebApp not detected or no initData. Provide initData in Dev auth.");
  }

  function configureHtmxAuth() {
    document.body.addEventListener("htmx:configRequest", (evt) => {
      const token = getToken();
      console.log("[CargoApp] htmx:configRequest - token exists:", !!token, "length:", token.length);
      if (!token) {
        console.warn("[CargoApp] htmx:configRequest - no token available");
        return;
      }
      evt.detail.headers["Authorization"] = `Bearer ${token}`;
      console.log("[CargoApp] htmx:configRequest - Authorization header set");
    });

    document.body.addEventListener("htmx:afterRequest", (evt) => {
      const xhr = evt.detail && evt.detail.xhr ? evt.detail.xhr : null;
      if (!xhr || !xhr.getResponseHeader) return;
      const refreshed = xhr.getResponseHeader("X-Session-Token");
      if (refreshed) {
        console.log("[CargoApp] htmx:afterRequest - token refreshed");
        setToken(refreshed);
      }
    });

    document.body.addEventListener("htmx:responseError", (evt) => {
      const xhr = evt.detail && evt.detail.xhr ? evt.detail.xhr : null;
      if (!xhr) return;
      
      if (xhr.status === 401) {
        console.error("[CargoApp] htmx:responseError - 401 Unauthorized, clearing token");
        localStorage.removeItem(tokenKey);
        document.cookie = `${tokenKey}=; path=/; max-age=0; SameSite=Lax`;
        
        // Show error message to user
        const cargoList = document.getElementById("cargo-list");
        if (cargoList) {
          cargoList.innerHTML = `
            <div class="alert alert-warning">
              <strong>Сессия истекла</strong><br>
              Пожалуйста, перезагрузите страницу для повторной авторизации.
            </div>
          `;
        }
        
        // Try to re-authenticate if Telegram WebApp is available
        const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
        if (tg && tg.initData) {
          console.log("[CargoApp] Attempting to re-authenticate with Telegram...");
          loginWithInitData(tg.initData).then(() => {
            console.log("[CargoApp] Re-authentication successful, reloading cargos");
            loadCargos("");
          }).catch((e) => {
            console.error("[CargoApp] Re-authentication failed:", e);
          });
        }
      }
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
