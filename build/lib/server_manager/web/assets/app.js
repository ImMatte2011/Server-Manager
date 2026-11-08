"use strict";

(() => {
  const IDLE_LIMIT_MS = 15 * 60 * 1000;
  const ui = Object.fromEntries(
    [
      "login-view", "dashboard-view", "login-form", "token-input", "login-button", "login-message",
      "transport-warning", "connection-state", "connection-label", "session-actions", "app-footer",
      "refresh-button", "lock-button", "notice", "last-updated", "view-title", "system-metrics",
      "services-list", "service-count", "schedule-form", "schedule-service", "schedule-kind",
      "weekday-field", "schedules-list", "audit-list", "confirm-dialog", "confirm-title",
      "confirm-copy", "confirm-action",
    ].map((id) => [id, document.getElementById(id)]),
  );

  const state = {
    token: null,
    sessionVersion: 0,
    refreshSequence: 0,
    idleTimer: null,
    refreshTimer: null,
    noticeTimer: null,
    controllers: new Set(),
    services: [],
    schedules: [],
    audit: [],
    summary: null,
    currentView: "services",
    busyServices: new Set(),
    refreshing: false,
  };

  class ApiError extends Error {
    constructor(code, message, status) {
      super(message);
      this.code = code;
      this.status = status;
    }
  }

  function apiRequest(path, options = {}) {
    if (!state.token) return Promise.reject(new ApiError("locked", "Sessione bloccata."));
    const version = state.sessionVersion;
    const controller = new AbortController();
    state.controllers.add(controller);
    const headers = new Headers({
      Accept: "application/json",
      Authorization: `Bearer ${state.token}`,
    });
    if (options.body !== undefined) headers.set("Content-Type", "application/json");
    if (options.method && options.method !== "GET") headers.set("X-Server-Manager-Source", "Web UI");

    return fetch(path, {
      method: options.method || "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      mode: "same-origin",
      credentials: "omit",
      cache: "no-store",
      redirect: "error",
      referrerPolicy: "no-referrer",
      signal: controller.signal,
    }).then(async (response) => {
      if (version !== state.sessionVersion) throw new ApiError("locked", "Sessione scaduta.");
      const payload = await response.json().catch(() => null);
      if (response.status === 401) {
        lockSession("Token rifiutato. Accedi di nuovo.");
        throw new ApiError("unauthorized", "Token rifiutato.", 401);
      }
      if (!response.ok) {
        const error = payload && payload.error;
        throw new ApiError(
          error && typeof error.code === "string" ? error.code : "request_failed",
          error && typeof error.message === "string" ? error.message : `Richiesta non riuscita (${response.status}).`,
          response.status,
        );
      }
      return payload;
    }).catch((error) => {
      if (error instanceof ApiError || error.name === "AbortError") throw error;
      throw new ApiError("network_error", "Server non raggiungibile. Verifica Tailscale e connessione.");
    }).finally(() => {
      state.controllers.delete(controller);
    });
  }

  function setLoginMessage(message, isError = true) {
    ui["login-message"].textContent = message;
    ui["login-message"].classList.toggle("is-success", !isError);
  }

  function showNotice(message, kind = "success") {
    window.clearTimeout(state.noticeTimer);
    ui.notice.textContent = message;
    ui.notice.className = `app-notice is-${kind}`;
    ui.notice.hidden = false;
    state.noticeTimer = window.setTimeout(() => {
      ui.notice.hidden = true;
      ui.notice.textContent = "";
    }, 6500);
  }

  function armIdleLock() {
    window.clearTimeout(state.idleTimer);
    if (!state.token) return;
    state.idleTimer = window.setTimeout(() => lockSession("Sessione bloccata per inattività."), IDLE_LIMIT_MS);
  }

  function lockSession(message = "", options = {}) {
    state.sessionVersion += 1;
    state.token = null;
    window.clearTimeout(state.idleTimer);
    window.clearInterval(state.refreshTimer);
    state.refreshSequence += 1;
    state.refreshing = false;
    for (const controller of state.controllers) controller.abort();
    state.controllers.clear();
    state.services = [];
    state.schedules = [];
    state.audit = [];
    state.summary = null;
    state.busyServices.clear();
    ui["token-input"].value = "";
    ui["dashboard-view"].hidden = true;
    ui["session-actions"].hidden = true;
    ui["app-footer"].hidden = true;
    ui["login-view"].hidden = false;
    ui["connection-state"].classList.remove("is-secure");
    ui["connection-label"].textContent = "Disconnesso";
    ui["connection-state"].setAttribute("aria-label", "Disconnesso");
    if (message) setLoginMessage(message);
    renderAll();
    if (options.focus !== false) ui["token-input"].focus();
  }

  async function signIn(event) {
    event.preventDefault();
    if (!window.isSecureContext) {
      setLoginMessage("Usa l’indirizzo HTTPS privato del tailnet.");
      return;
    }
    const token = ui["token-input"].value.trim();
    if (!token) return;
    ui["login-button"].disabled = true;
    setLoginMessage("Verifica in corso…", false);
    state.token = token;
    state.sessionVersion += 1;
    ui["token-input"].value = "";
    try {
      const payload = await apiRequest("/api/services");
      state.services = Array.isArray(payload.services) ? payload.services : [];
      ui["login-view"].hidden = true;
      ui["dashboard-view"].hidden = false;
      ui["session-actions"].hidden = false;
      ui["app-footer"].hidden = false;
      ui["connection-state"].classList.add("is-secure");
      const isHttps = location.protocol === "https:";
      ui["connection-label"].textContent = isHttps ? "HTTPS" : "Locale";
      ui["connection-state"].setAttribute("aria-label", isHttps ? "Connessione HTTPS" : "Connessione locale di sviluppo");
      setLoginMessage("");
      armIdleLock();
      renderAll();
      await refreshData();
      if (state.token) {
        window.clearInterval(state.refreshTimer);
        state.refreshTimer = window.setInterval(() => refreshData(), 30_000);
        ui["refresh-button"].focus();
      }
    } catch (error) {
      if (state.token && error.code !== "unauthorized" && error.code !== "locked") {
        lockSession(error.message || "Accesso non riuscito.");
      }
    } finally {
      ui["login-button"].disabled = false;
    }
  }

  async function refreshData() {
    if (!state.token || state.refreshing) return;
    state.refreshing = true;
    const sequence = ++state.refreshSequence;
    ui["refresh-button"].disabled = true;
    const version = state.sessionVersion;
    try {
      const settled = await Promise.allSettled([
        apiRequest("/api/resources/summary"),
        apiRequest("/api/schedules"),
        apiRequest("/api/audit?limit=60"),
      ]);
      if (version !== state.sessionVersion || !state.token) return;

      const [summaryResult, schedulesResult, auditResult] = settled;
      if (summaryResult.status === "fulfilled") state.summary = summaryResult.value;
      else if (["unauthorized", "locked"].includes(summaryResult.reason.code)) return;
      if (schedulesResult.status === "fulfilled") {
        state.schedules = Array.isArray(schedulesResult.value.schedules) ? schedulesResult.value.schedules : [];
      } else if (["unauthorized", "locked"].includes(schedulesResult.reason.code)) return;
      if (auditResult.status === "fulfilled") state.audit = Array.isArray(auditResult.value.events) ? auditResult.value.events : [];
      else if (["unauthorized", "locked"].includes(auditResult.reason.code)) return;

      renderAll();
      ui["last-updated"].textContent = `Aggiornato alle ${new Date().toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })}`;
      if (settled.some((result) => result.status === "rejected")) {
        showNotice("Alcuni dati non sono disponibili. Verifica la connessione o i provider.", "error");
      }
    } finally {
      if (sequence === state.refreshSequence) {
        state.refreshing = false;
        ui["refresh-button"].disabled = false;
      }
    }
  }

  function renderAll() {
    renderMetrics();
    renderServices();
    renderSchedules();
    renderAudit();
    renderTabs();
  }

  function renderMetrics() {
    const host = state.summary && state.summary.system;
    ui["system-metrics"].replaceChildren();
    if (!host) {
      for (const label of ["CPU", "Memoria", "Disco", "Uptime"]) {
        ui["system-metrics"].append(metricElement(label, "—"));
      }
      return;
    }
    const metrics = [
      ["CPU", percent(host.cpu_percent)],
      ["Memoria", percent(host.memory && host.memory.percent)],
      ["Disco", percent(host.disk && host.disk.percent)],
      ["Uptime", formatUptime(host.uptime_seconds)],
    ];
    if (host.temperature_celsius !== null && host.temperature_celsius !== undefined) {
      metrics.push(["Temperatura", `${Number(host.temperature_celsius).toFixed(1)} °C`]);
    }
    for (const [label, value] of metrics) ui["system-metrics"].append(metricElement(label, value));
  }

  function metricElement(label, value) {
    const block = document.createElement("div");
    block.className = "metric";
    const name = document.createElement("span");
    name.textContent = label;
    const amount = document.createElement("strong");
    amount.textContent = value;
    block.append(name, amount);
    return block;
  }

  function renderServices() {
    ui["service-count"].textContent = `${state.services.length} in registry`;
    ui["services-list"].replaceChildren();
    if (!state.services.length) {
      ui["services-list"].append(emptyState("Nessun servizio registrato."));
      return;
    }
    const monitored = new Map(((state.summary && state.summary.services) || []).map((item) => [item.service_id, item]));
    for (const service of state.services) {
      ui["services-list"].append(serviceCard(service, monitored.get(service.id)));
    }
  }

  function serviceCard(service, monitored) {
    const row = document.createElement("article");
    row.className = "service-row";
    const main = document.createElement("div");
    main.className = "service-main";
    const titleLine = document.createElement("div");
    titleLine.className = "service-title-line";
    const title = document.createElement("h3");
    title.textContent = service.name || service.id;
    titleLine.append(title, stateTag(monitored && monitored.status ? monitored.status.state : service.availability));
    const id = document.createElement("p");
    id.className = "service-id";
    id.textContent = service.id;
    const meta = document.createElement("div");
    meta.className = "service-meta";
    meta.append(tag(service.type === "docker_compose" ? "Docker Compose" : service.type || "Non valido"));
    meta.append(tag(availabilityLabel(service.availability)));
    main.append(titleLine, id, meta);

    const resources = document.createElement("div");
    resources.className = "resource-line";
    if (monitored && monitored.cpu_percent !== undefined) {
      resources.append(textSpan(`CPU ${percent(monitored.cpu_percent)}`));
      resources.append(textSpan(`RAM ${formatBytes(monitored.memory_bytes)}`));
    } else {
      resources.append(textSpan("Risorse non disponibili"));
    }

    const actions = document.createElement("div");
    actions.className = "service-actions";
    for (const [operation, icon, label] of [
      ["start", "▶", "Avvia"],
      ["stop", "■", "Arresta"],
      ["restart", "↻", "Riavvia"],
    ]) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "operation-button";
      button.dataset.operation = operation;
      button.dataset.serviceId = service.id;
      button.title = `${label} ${service.name || service.id}`;
      const glyph = document.createElement("span");
      glyph.setAttribute("aria-hidden", "true");
      glyph.textContent = icon;
      button.append(glyph, document.createTextNode(label));
      const allowed = service.capabilities && service.capabilities[operation];
      const available = service.config_status === "valid" && service.enabled && !["disabled", "unavailable"].includes(service.availability);
      button.disabled = !allowed || !available || state.busyServices.has(service.id);
      button.addEventListener("click", () => performOperation(service, operation));
      actions.append(button);
    }
    row.append(main, resources, actions);
    return row;
  }

  function renderSchedules() {
    const eligible = state.services.filter((service) =>
      service.config_status === "valid" && service.enabled &&
      !["disabled", "unavailable"].includes(service.availability) &&
      service.capabilities && ["start", "stop", "restart"].some((op) => service.capabilities[op]),
    );
    const select = ui["schedule-service"];
    const previous = select.value;
    select.replaceChildren();
    for (const service of eligible) {
      const option = document.createElement("option");
      option.value = service.id;
      option.textContent = service.name || service.id;
      select.append(option);
    }
    if (eligible.some((service) => service.id === previous)) select.value = previous;
    const submit = ui["schedule-form"].querySelector("button[type=submit]");
    submit.disabled = eligible.length === 0;
    ui["schedules-list"].replaceChildren();
    if (!state.schedules.length) {
      ui["schedules-list"].append(emptyState("Nessuna pianificazione."));
    } else {
      for (const schedule of state.schedules) ui["schedules-list"].append(scheduleCard(schedule));
    }
  }

  function scheduleCard(schedule) {
    const row = document.createElement("article");
    row.className = "schedule-row";
    const copy = document.createElement("div");
    copy.className = "schedule-copy";
    const service = state.services.find((item) => item.id === schedule.service_id);
    const title = document.createElement("strong");
    title.textContent = `${operationLabel(schedule.operation)} · ${service ? service.name : schedule.service_id}`;
    const detail = document.createElement("span");
    const weekdays = (schedule.weekdays || []).map(weekdayLabel).join(", ");
    detail.textContent = `${String(schedule.hour).padStart(2, "0")}:${String(schedule.minute).padStart(2, "0")} · ${schedule.kind === "weekly" ? weekdays : "Ogni giorno"}`;
    copy.append(title, detail);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "delete-button";
    remove.textContent = "Elimina";
    remove.addEventListener("click", () => deleteSchedule(schedule));
    row.append(copy, remove);
    return row;
  }

  function renderAudit() {
    ui["audit-list"].replaceChildren();
    if (!state.audit.length) {
      ui["audit-list"].append(emptyState("Nessun evento registrato."));
      return;
    }
    for (const event of state.audit) {
      const row = document.createElement("article");
      row.className = "audit-row";
      const copy = document.createElement("div");
      copy.className = "audit-copy";
      const title = document.createElement("strong");
      title.textContent = `${operationLabel(event.action)}${event.service_id ? ` · ${event.service_id}` : ""}`;
      const meta = document.createElement("span");
      meta.textContent = `${event.actor || "—"} · ${event.source || "API"}`;
      const result = document.createElement("span");
      result.className = `audit-result ${event.success ? "ok" : "failed"}`;
      result.textContent = event.success ? "Completato" : "Non riuscito";
      copy.append(title, meta, document.createElement("br"), result);
      const time = document.createElement("time");
      time.className = "audit-meta";
      time.dateTime = event.timestamp || "";
      time.textContent = formatTimestamp(event.timestamp);
      row.append(copy, time);
      ui["audit-list"].append(row);
    }
  }

  function renderTabs() {
    const titles = { services: "Servizi", schedules: "Pianificazioni", audit: "Audit" };
    ui["view-title"].textContent = titles[state.currentView];
    for (const button of document.querySelectorAll(".tab-button")) {
      const active = button.dataset.view === state.currentView;
      button.classList.toggle("is-active", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    }
    for (const view of ["services", "schedules", "audit"]) {
      document.getElementById(`${view}-view`).hidden = view !== state.currentView;
    }
  }

  async function performOperation(service, operation) {
    if (["stop", "restart"].includes(operation)) {
      const accepted = await askConfirmation(
        `${operationLabel(operation)} ${service.name || service.id}?`,
        `Questa operazione verrà inviata al servizio ${service.id}.`,
        operationLabel(operation),
      );
      if (!accepted) return;
    }
    state.busyServices.add(service.id);
    renderServices();
    try {
      await apiRequest(`/api/services/${encodeURIComponent(service.id)}/${operation}`, { method: "POST" });
      showNotice(`${operationLabel(operation)} inviato per ${service.name || service.id}.`);
      await refreshData();
    } catch (error) {
      if (error.code !== "unauthorized" && error.code !== "locked") showNotice(error.message, "error");
    } finally {
      state.busyServices.delete(service.id);
      renderServices();
    }
  }

  async function deleteSchedule(schedule) {
    const accepted = await askConfirmation(
      "Eliminare la pianificazione?",
      `${operationLabel(schedule.operation)} · ${schedule.service_id}`,
      "Elimina",
    );
    if (!accepted) return;
    try {
      await apiRequest(`/api/schedules/${encodeURIComponent(schedule.id)}`, { method: "DELETE" });
      showNotice("Pianificazione eliminata.");
      await refreshData();
    } catch (error) {
      if (error.code !== "unauthorized" && error.code !== "locked") showNotice(error.message, "error");
    }
  }

  function askConfirmation(title, copy, action) {
    ui["confirm-title"].textContent = title;
    ui["confirm-copy"].textContent = copy;
    ui["confirm-action"].textContent = action;
    ui["confirm-dialog"].showModal();
    return new Promise((resolve) => {
      ui["confirm-dialog"].addEventListener("close", () => {
        resolve(ui["confirm-dialog"].returnValue === "confirm");
      }, { once: true });
    });
  }

  async function createSchedule(event) {
    event.preventDefault();
    const form = new FormData(ui["schedule-form"]);
    const [hour, minute] = String(form.get("time") || "08:00").split(":").map(Number);
    const kind = String(form.get("kind"));
    const weekdays = kind === "weekly" ? form.getAll("weekday").map(String) : [];
    if (kind === "weekly" && weekdays.length === 0) {
      showNotice("Seleziona almeno un giorno della settimana.", "error");
      return;
    }
    try {
      await apiRequest("/api/schedules", {
        method: "POST",
        body: {
          service_id: String(form.get("service_id")),
          operation: String(form.get("operation")),
          kind,
          hour,
          minute,
          weekdays,
        },
      });
      showNotice("Pianificazione creata.");
      ui["schedule-form"].reset();
      ui["schedule-form"].elements.time.value = "08:00";
      ui["schedule-kind"].value = "daily";
      ui["weekday-field"].hidden = true;
      await refreshData();
    } catch (error) {
      if (error.code !== "unauthorized" && error.code !== "locked") showNotice(error.message, "error");
    }
  }

  function emptyState(message) {
    const node = document.createElement("div");
    node.className = "empty-state";
    node.textContent = message;
    return node;
  }

  function tag(label) {
    const node = document.createElement("span");
    node.className = "tag";
    node.textContent = label;
    return node;
  }

  function stateTag(value) {
    const node = document.createElement("span");
    const stateName = String(value || "unknown").toLowerCase();
    node.className = `state-tag state-${stateName}`;
    node.textContent = stateLabel(stateName);
    return node;
  }

  function textSpan(value) {
    const node = document.createElement("span");
    node.textContent = value;
    return node;
  }

  function stateLabel(value) {
    return ({
      running: "Attivo", stopped: "Fermo", starting: "Avvio", stopping: "Arresto",
      restarting: "Riavvio", failed: "Errore", unknown: "Sconosciuto", unavailable: "Non disponibile",
      disabled: "Disabilitato", invalid: "Configurazione non valida", available: "Disponibile",
    })[value] || value;
  }

  function availabilityLabel(value) {
    return ({ available: "Disponibile", unknown: "Verifica runtime", unavailable: "Non disponibile", disabled: "Disabilitato" })[value] || value || "—";
  }

  function operationLabel(value) {
    return ({ start: "Avvio", stop: "Arresto", restart: "Riavvio", "schedule.create": "Pianificazione creata", "schedule.delete": "Pianificazione eliminata" })[value] || value || "Evento";
  }

  function weekdayLabel(value) {
    return ({ mon: "Lun", tue: "Mar", wed: "Mer", thu: "Gio", fri: "Ven", sat: "Sab", sun: "Dom" })[value] || value;
  }

  function percent(value) {
    if (value === null || value === undefined || value === "") return "—";
    return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}%` : "—";
  }

  function formatBytes(value) {
    if (value === null || value === undefined || value === "") return "—";
    if (!Number.isFinite(Number(value))) return "—";
    const bytes = Number(value);
    if (bytes < 1024) return `${bytes} B`;
    const units = ["KB", "MB", "GB", "TB"];
    let amount = bytes;
    let index = -1;
    do { amount /= 1024; index += 1; } while (amount >= 1024 && index < units.length - 1);
    return `${amount.toFixed(1)} ${units[index]}`;
  }

  function formatUptime(value) {
    if (!Number.isFinite(Number(value))) return "—";
    let remaining = Math.max(0, Math.floor(Number(value)));
    const days = Math.floor(remaining / 86400);
    remaining %= 86400;
    const hours = Math.floor(remaining / 3600);
    remaining %= 3600;
    const minutes = Math.floor(remaining / 60);
    return days ? `${days}g ${hours}h` : `${hours}h ${minutes}m`;
  }

  function formatTimestamp(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" });
  }

  ui["login-form"].addEventListener("submit", signIn);
  ui["refresh-button"].addEventListener("click", refreshData);
  ui["lock-button"].addEventListener("click", () => lockSession());
  ui["schedule-form"].addEventListener("submit", createSchedule);
  ui["schedule-kind"].addEventListener("change", () => {
    ui["weekday-field"].hidden = ui["schedule-kind"].value !== "weekly";
  });
  for (const button of document.querySelectorAll(".tab-button")) {
    button.addEventListener("click", () => {
      state.currentView = button.dataset.view;
      renderTabs();
      armIdleLock();
    });
  }
  for (const eventName of ["pointerdown", "keydown", "touchstart"]) {
    document.addEventListener(eventName, () => armIdleLock(), { passive: true });
  }
  window.addEventListener("pagehide", () => lockSession("", { focus: false }));

  ui["transport-warning"].hidden = window.isSecureContext;
  ui["login-button"].disabled = !window.isSecureContext;
  if (window.isSecureContext && "serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {});
  }
  renderAll();
})();
