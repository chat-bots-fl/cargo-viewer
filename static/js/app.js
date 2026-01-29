/* global htmx */

const CargoApp = (() => {
  const tokenKey = "session_token";
  let modalDefaults = null;
  let activeModalRequestId = null;
  let modalRequestSeq = 0;
  let activeListRequestId = null;
  let listRequestSeq = 0;
  let loadMoreObserver = null;
  let loadMoreObservedEl = null;
  let priceRefreshTimer = null;
  let priceRefreshRequestSeq = 0;

  function setCargoListLoading(message = "Загрузка…") {
    const cargoList = document.getElementById("cargo-list");
    if (!cargoList) return;

    const cargoCount = document.getElementById("cargo-count");
    if (cargoCount) cargoCount.textContent = "";

    cargoList.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;">
        <div class="spinner" aria-label="Loading"></div>
        <div class="muted">${message}</div>
      </div>
    `;
  }

  function buildCurrentCargosQuery() {
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

    const usp = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === null) return;
      const s = String(value).trim();
      if (!s) return;
      usp.set(key, s);
    });
    return usp.toString();
  }

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
    const header = document.getElementById("modal-header");
    const body = document.getElementById("modal-body");
    if (!root || !header || !body) return;

    modalRequestSeq += 1;
    activeModalRequestId = modalRequestSeq;

    if (modalDefaults) {
      header.className = modalDefaults.headerClassName;
      header.removeAttribute("hx-swap-oob");
      header.innerHTML = modalDefaults.headerHtml;

      body.className = modalDefaults.bodyClassName;
      body.innerHTML = modalDefaults.bodyHtml;

      const modal = root.querySelector(".modal");
      if (modal) modal.scrollTop = 0;
    }
    root.classList.remove("hidden");
    root.setAttribute("aria-hidden", "false");

    let requestUrl = url;
    try {
      const u = new URL(url, window.location.origin);
      u.searchParams.set("_rid", String(activeModalRequestId));
      requestUrl = `${u.pathname}${u.search}${u.hash}`;
    } catch (e) {
      requestUrl = `${url}${url.includes("?") ? "&" : "?"}_rid=${encodeURIComponent(String(activeModalRequestId))}`;
    }

    htmx.ajax("GET", requestUrl, { target: "#modal-body", swap: "innerHTML" });
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

    document.body.addEventListener("htmx:beforeSwap", (evt) => {
      const target = evt.detail && evt.detail.target ? evt.detail.target : null;
      if (!target) return;

      if (target.id === "modal-body" || target.id === "modal-header") {
        const root = document.getElementById("modal-root");
        if (root && root.classList.contains("hidden")) {
          evt.detail.shouldSwap = false;
          return;
        }

        const xhr = evt.detail && evt.detail.xhr ? evt.detail.xhr : null;
        const responseUrl = xhr && xhr.responseURL ? String(xhr.responseURL) : "";
        if (!responseUrl) return;

        let rid = null;
        try {
          rid = new URL(responseUrl, window.location.origin).searchParams.get("_rid");
        } catch (e) {
          rid = null;
        }

        if (!rid || activeModalRequestId === null) return;
        if (String(activeModalRequestId) !== String(rid)) {
          evt.detail.shouldSwap = false;
        }
        return;
      }

      if (
        target.id !== "cargo-list" &&
        target.id !== "cargo-cards" &&
        target.id !== "cargo-count" &&
        target.id !== "load-more"
      ) {
        return;
      }

      const xhr = evt.detail && evt.detail.xhr ? evt.detail.xhr : null;
      const responseUrl = xhr && xhr.responseURL ? String(xhr.responseURL) : "";
      if (!responseUrl) return;

      let rid = null;
      try {
        rid = new URL(responseUrl, window.location.origin).searchParams.get("_rid");
      } catch (e) {
        rid = null;
      }

      if (!rid || activeListRequestId === null) return;
      if (String(activeListRequestId) !== String(rid)) {
        evt.detail.shouldSwap = false;
      }
    });
  }

  function loadCargos(queryString = "") {
    const target = document.getElementById("cargo-list");
    if (!target) return;

    listRequestSeq += 1;
    activeListRequestId = listRequestSeq;

    setCargoListLoading("Загрузка…");

    const u = new URL("/api/cargos/", window.location.origin);
    if (queryString) {
      u.search = queryString.startsWith("?") ? queryString : `?${queryString}`;
    }
    u.searchParams.set("_rid", String(activeListRequestId));

    const url = `${u.pathname}${u.search}`;
    htmx.ajax("GET", url, { target: "#cargo-list", swap: "innerHTML" });
  }

  function getPriceRefreshSink() {
    let sink = document.getElementById("price-refresh-sink");
    if (sink) return sink;

    sink = document.createElement("div");
    sink.id = "price-refresh-sink";
    sink.className = "hidden";
    sink.setAttribute("aria-hidden", "true");
    document.body.appendChild(sink);
    return sink;
  }

  function getDisplayedCargoCount() {
    return document.querySelectorAll(".cargo-card").length;
  }

  function getDisplayedCargoIds(maxItems = 200) {
    const cards = document.querySelectorAll(".cargo-card[data-cargo-open]");
    const out = [];
    const seen = new Set();

    for (const card of cards) {
      const raw = card.getAttribute("data-cargo-open");
      if (!raw) continue;
      const id = String(raw).trim();
      if (!id) continue;
      if (!/^\d+$/.test(id)) continue;
      if (seen.has(id)) continue;

      seen.add(id);
      out.push(id);

      if (out.length >= maxItems) break;
    }

    return out;
  }

  function refreshVisiblePrices() {
    if (document.hidden) return;

    const token = getToken();
    if (!token) return;

    const ids = getDisplayedCargoIds(200);
    if (!ids.length) return;

    const query = buildCurrentCargosQuery();

    const u = new URL("/api/cargos/prices/", window.location.origin);
    if (query) {
      u.search = query.startsWith("?") ? query : `?${query}`;
    }
    u.searchParams.set("seen_ids", ids.join(","));
    priceRefreshRequestSeq += 1;
    u.searchParams.set("_rid", String(priceRefreshRequestSeq));

    const url = `${u.pathname}${u.search}`;
    getPriceRefreshSink();
    htmx.ajax("GET", url, { target: "#price-refresh-sink", swap: "innerHTML" });
  }

  function startPriceAutoRefresh() {
    if (priceRefreshTimer) return;

    const intervalMs = 30000;
    priceRefreshTimer = window.setInterval(refreshVisiblePrices, intervalMs);

    // Prime a first refresh soon after initial list render.
    window.setTimeout(refreshVisiblePrices, 5000);

    // Also refresh shortly after list mutations (filters applied / load more).
    document.body.addEventListener("htmx:afterSwap", (evt) => {
      const target = evt.detail && evt.detail.target ? evt.detail.target : null;
      if (!target) return;
      if (target.id === "cargo-list" || target.id === "cargo-cards") {
        window.setTimeout(refreshVisiblePrices, 1200);
      }
    });
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

  function _autoTriggerLoadMore(buttonEl) {
    if (!buttonEl) return;
    if (buttonEl.disabled) return;
    if (buttonEl.classList && buttonEl.classList.contains("htmx-request")) return;
    if (buttonEl.dataset && buttonEl.dataset.autoloadTriggered === "1") return;

    buttonEl.dataset.autoloadTriggered = "1";
    window.requestAnimationFrame(() => {
      try {
        buttonEl.click();
      } catch (e) {
      }
    });
  }

  function _observeLoadMoreButton() {
    const buttonEl = document.querySelector("button[data-load-more='1']");
    if (!buttonEl) {
      if (loadMoreObserver && loadMoreObservedEl) {
        try {
          loadMoreObserver.unobserve(loadMoreObservedEl);
        } catch (e) {
        }
      }
      loadMoreObservedEl = null;
      return;
    }

    if (loadMoreObservedEl === buttonEl) return;

    if (loadMoreObserver && loadMoreObservedEl) {
      try {
        loadMoreObserver.unobserve(loadMoreObservedEl);
      } catch (e) {
      }
    }

    if (!loadMoreObserver && "IntersectionObserver" in window) {
      loadMoreObserver = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (!entry.isIntersecting) continue;
            _autoTriggerLoadMore(entry.target);
          }
        },
        { root: null, rootMargin: "0px 0px 700px 0px", threshold: 0.01 }
      );
    }

    loadMoreObservedEl = buttonEl;
    if (loadMoreObserver) {
      loadMoreObserver.observe(buttonEl);
      return;
    }

    const rect = buttonEl.getBoundingClientRect();
    const viewportH = window.innerHeight || document.documentElement.clientHeight;
    if (rect.top <= viewportH + 700) {
      _autoTriggerLoadMore(buttonEl);
    }
  }

  function bindInfiniteScroll() {
    const schedule = () => window.requestAnimationFrame(_observeLoadMoreButton);

    window.addEventListener("scroll", schedule, { passive: true });
    document.body.addEventListener("htmx:afterSwap", schedule);
    document.body.addEventListener("htmx:afterSettle", schedule);
    document.body.addEventListener("htmx:oobAfterSwap", schedule);

    schedule();
  }

  async function bootstrap() {
    const header = document.getElementById("modal-header");
    const body = document.getElementById("modal-body");
    if (header && body) {
      modalDefaults = {
        headerClassName: header.className,
        headerHtml: header.innerHTML,
        bodyClassName: body.className,
        bodyHtml: body.innerHTML,
      };
    }
    configureHtmxAuth();
    bindModal();
    bindCargoClicks();
    bindInfiniteScroll();

    try {
      setCargoListLoading("Авторизация…");
      await ensureSession();
      loadCargos(buildCurrentCargosQuery());
      startPriceAutoRefresh();
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
          loadCargos(buildCurrentCargosQuery());
          startPriceAutoRefresh();
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
