const $ = (s) => document.querySelector(s);
const state = { token: localStorage.getItem("em_token"), socket: null, devices: [], telemetry: [], role: null };
const days = () => $("#days-filter").value;
const device = () => $("#device-filter").value;

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401) logout();
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }
  return response.status === 204 ? null : response.json();
}

async function authenticate(endpoint) {
  $("#auth-error").textContent = "";
  try {
    const result = await api(endpoint, {
      method: "POST",
      body: JSON.stringify({ username: $("#username").value, password: $("#password").value }),
    });
    state.token = result.access_token;
    localStorage.setItem("em_token", state.token);
    await start();
  } catch (error) {
    $("#auth-error").textContent = error.message;
  }
}

function logout() {
  localStorage.removeItem("em_token");
  state.token = null;
  state.socket?.close();
  $("#app").classList.add("hidden");
  $("#auth").classList.remove("hidden");
}

async function start() {
  try {
    const me = await api("/auth/me");
    state.role = me.role;
    $("#identity").textContent = `${me.username} · ${me.role}`;
    $("#auth").classList.add("hidden");
    $("#app").classList.remove("hidden");
    $("#calibration-form").classList.toggle("hidden", me.role === "viewer");
    $("#device-management").classList.toggle("hidden", me.role !== "admin");
    await loadDevices();
    await Promise.all([loadTelemetry(), loadCalibrations(), refresh(), loadEvents(), loadRules()]);
    connectLive();
  } catch (_) {
    logout();
  }
}

async function loadTelemetry() {
  const telemetry = await api("/api/device-telemetry");
  state.telemetry = telemetry;
  const now = Date.now();
  $("#device-health").innerHTML = telemetry.length ? telemetry.map((item) => {
    const configured = state.devices.find((device) => device.device_id === item.device_id);
    const ageSeconds = Math.max(0, Math.round((now - new Date(item.last_seen).valueOf()) / 1000));
    const online = ageSeconds < 90;
    const total = item.packets_received + item.packets_lost;
    return `<div class="device-card">
      <div><i class="status-dot ${online && configured?.enabled !== false ? "online" : "offline"}"></i><strong>${escapeHtml(configured?.name || item.device_id)}</strong></div>
      <span>${configured?.enabled === false ? "Administrativ inaktiv" : online ? "Online" : `Seit ${ageSeconds} s ohne Signal`} · ${escapeHtml(configured?.location || item.device_id)}</span>
      <dl><dt>Firmware</dt><dd>${escapeHtml(item.firmware_version || "Legacy")}</dd><dt>Quelle</dt><dd>${escapeHtml(item.source_ip)}</dd><dt>Aktueller Pegel</dt><dd>${item.db_level.toFixed(1)} dB</dd><dt>Pakete</dt><dd>${total.toLocaleString("de-DE")}</dd><dt>Verlust</dt><dd>${(item.loss_rate * 100).toFixed(3)} %</dd><dt>Samplerate</dt><dd>${item.sample_rate.toLocaleString("de-DE")} Hz</dd><dt>Peak</dt><dd>${item.peak}</dd></dl>
    </div>`;
  }).join("") : "<p>Noch keine Telemetriedaten. Legacy-Firmware sendet weiterhin Audio, aber noch keinen Gerätestatus.</p>";
}

async function loadCalibrations() {
  const calibrations = await api("/api/device-calibrations");
  const value = (reference, measured) => reference == null ? "–" : `${measured.toFixed(1)} / ${reference.toFixed(1)} dB`;
  $("#calibration-list").innerHTML = calibrations.length ? calibrations.map((item) =>
    `<div class="calibration-row"><strong>${escapeHtml(item.device_id)}</strong><span>Leise: ${value(item.low_reference_db, item.low_measured_db)}</span><span>Mittel: ${value(item.medium_reference_db, item.medium_measured_db)}</span><span>Laut: ${value(item.high_reference_db, item.high_measured_db)}</span><b>Empfohlener Offset: ${item.recommended_offset_db >= 0 ? "+" : ""}${item.recommended_offset_db.toFixed(2)} dB</b></div>`
  ).join("") : "<p>Noch keine Referenzmessung erfasst.</p>";
}

async function loadDevices() {
  state.devices = await api("/api/devices");
  const options = state.devices.map((d) => `<option value="${escapeHtml(d.device_id)}">${escapeHtml(d.name)}</option>`).join("");
  $("#device-filter").innerHTML = `<option value="">Alle Geräte</option>${options}`;
  $("#rule-device").innerHTML = `<option value="*">Alle Geräte</option>${options}`;
  renderDeviceManagement();
}

function renderDeviceManagement() {
  $("#device-management-list").innerHTML = state.devices.length ? state.devices.map((d) => `
    <form class="device-editor" data-device-id="${escapeHtml(d.device_id)}">
      <div class="device-identity"><strong>${escapeHtml(d.device_id)}</strong><small>${d.last_seen ? `Zuletzt gesehen: ${formatTime(d.last_seen)}` : "Noch nicht gesehen"}</small></div>
      <label>Name<input name="name" value="${escapeHtml(d.name)}" maxlength="120" required></label>
      <label>Standort<input name="location" value="${escapeHtml(d.location)}" maxlength="160"></label>
      <label>Position X (%)<input name="position_x" type="number" min="0" max="100" step="0.1" value="${d.position_x ?? ""}"></label>
      <label>Position Y (%)<input name="position_y" type="number" min="0" max="100" step="0.1" value="${d.position_y ?? ""}"></label>
      <label class="active-toggle"><input name="enabled" type="checkbox" ${d.enabled ? "checked" : ""}> Aktiv</label>
      <button type="submit">Speichern</button>
    </form>`).join("") : "<p>Noch keine Mikrofone registriert.</p>";
}

async function refresh() {
  const query = `days=${days()}${device() ? `&device=${encodeURIComponent(device())}` : ""}`;
  const [stats, heatmap, calendar] = await Promise.all([
    api(`/api/statistics?${query}`), api(`/api/heatmap?${query}`), api(`/api/calendar?${query}`),
  ]);
  $("#m-total").textContent = stats.total.toLocaleString("de-DE");
  $("#m-average").textContent = stats.average_db;
  $("#m-max").textContent = stats.max_db;
  $("#m-confidence").textContent = `${Math.round(stats.average_confidence * 100)} %`;
  renderTimeline(calendar);
  renderCategories(stats.categories, stats.total);
  renderHeatmap(heatmap);
  renderCalendar(calendar);
}

function renderTimeline(data) {
  const max = Math.max(1, ...data.map((d) => d.total));
  $("#timeline").innerHTML = data.length ? data.map((d) =>
    `<div class="bar" style="height:${Math.max(3, d.total / max * 100)}%" data-tip="${d.date}: ${d.total}"></div>`
  ).join("") : "<span>Keine Ereignisse im Zeitraum</span>";
}

function renderCategories(categories, total) {
  const entries = Object.entries(categories).sort((a, b) => b[1] - a[1]);
  $("#categories").innerHTML = entries.length ? entries.map(([name, count]) =>
    `<div class="category"><span>${escapeHtml(name)}</span><strong>${count}</strong><div class="category-track"><div class="category-fill" style="width:${count / total * 100}%"></div></div></div>`
  ).join("") : "<span>Keine Daten</span>";
}

function renderHeatmap(data) {
  const lookup = new Map(data.map((c) => [`${c.weekday}-${c.hour}`, c.count]));
  const max = Math.max(1, ...data.map((c) => c.count));
  const labels = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
  let html = `<span></span>${Array.from({ length: 24 }, (_, h) => `<span>${h}</span>`).join("")}`;
  labels.forEach((label, weekday) => {
    html += `<span class="heat-label">${label}</span>`;
    for (let hour = 0; hour < 24; hour++) {
      const count = lookup.get(`${weekday}-${hour}`) || 0;
      const alpha = count ? 0.18 + count / max * 0.82 : 0;
      html += `<i class="heat-cell" title="${label} ${hour}:00 · ${count}" style="background:rgba(112,224,174,${alpha})"></i>`;
    }
  });
  $("#heatmap").innerHTML = html;
}

function renderCalendar(data) {
  $("#calendar").innerHTML = data.length ? data.map((d) =>
    `<div class="day">${new Date(`${d.date}T12:00:00`).toLocaleDateString("de-DE", { day: "2-digit", month: "short" })}<strong>${d.total}</strong></div>`
  ).join("") : "<span>Keine Kalendereinträge</span>";
}

async function loadEvents() {
  const query = `${device() ? `?device=${encodeURIComponent(device())}&` : "?"}limit=200`;
  const events = await api(`/events${query}`);
  $("#events").innerHTML = "";
  events.reverse().forEach(addEvent);
}

function addEvent(event) {
  const row = document.createElement("div");
  row.className = "event-row";
  row.innerHTML = `<span>${formatTime(event.timestamp)}</span><span>${escapeHtml(event.device)}</span><span class="badge">${escapeHtml(event.label_de || event.label)}</span><span>${event.db_level.toFixed(1)} dB</span><span>${Math.round(event.confidence * 100)} %</span>`;
  $("#events").prepend(row);
  while ($("#events").children.length > 200) $("#events").lastElementChild.remove();
}

function connectLive() {
  state.socket?.close();
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  state.socket = new WebSocket(`${scheme}://${location.host}/ws/events?token=${encodeURIComponent(state.token)}`);
  state.socket.onopen = () => { $("#connection").textContent = "Live verbunden"; $("#live-dot").style.background = "var(--accent)"; };
  state.socket.onmessage = (message) => { addEvent(JSON.parse(message.data)); refresh(); };
  state.socket.onclose = () => {
    $("#connection").textContent = "Verbindung unterbrochen";
    $("#live-dot").style.background = "var(--danger)";
    if (state.token) setTimeout(connectLive, 3000);
  };
}

async function loadRules() {
  const rules = await api("/api/notification-rules");
  $("#rule-list").innerHTML = rules.length ? rules.map((r) =>
    `<div class="rule"><div><strong>${escapeHtml(r.name)}</strong><p>${escapeHtml(r.category)} · ab ${Math.round(r.min_confidence * 100)} % · ${r.min_db_level} dB · ${escapeHtml(r.device)}</p></div><button data-delete="${r.id}" title="Löschen">×</button></div>`
  ).join("") : "<p>Noch keine Regeln konfiguriert.</p>";
}

$("#login-form").addEventListener("submit", (e) => { e.preventDefault(); authenticate("/auth/login"); });
$("#bootstrap").addEventListener("click", () => authenticate("/auth/bootstrap"));
$("#logout").addEventListener("click", logout);
$("#days-filter").addEventListener("change", refresh);
$("#device-filter").addEventListener("change", () => Promise.all([refresh(), loadEvents()]));
document.querySelectorAll(".nav").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".nav").forEach((n) => n.classList.toggle("active", n === button));
  document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
  $(`#${button.dataset.view}`).classList.remove("hidden");
  $("#title").textContent = button.textContent.trim();
}));
$("#rule-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  await api("/api/notification-rules", { method: "POST", body: JSON.stringify({
    name: $("#rule-name").value, category: $("#rule-category").value || "*",
    device: $("#rule-device").value, min_confidence: Number($("#rule-confidence").value),
    min_db_level: Number($("#rule-db").value), cooldown_seconds: Number($("#rule-cooldown").value),
  }) });
  e.target.reset(); await loadRules();
});
$("#rule-list").addEventListener("click", async (e) => {
  const id = e.target.dataset.delete;
  if (id) { await api(`/api/notification-rules/${id}`, { method: "DELETE" }); await loadRules(); }
});
$("#calibration-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const enabledIds = new Set(state.devices.filter((item) => item.enabled).map((item) => item.device_id));
  const onlineIds = state.telemetry.filter((item) => enabledIds.has(item.device_id) && Date.now() - new Date(item.last_seen).valueOf() < 90000).map((item) => item.device_id);
  if (!onlineIds.length) { $("#calibration-status").textContent = "Keine Online-Mikrofone gefunden."; return; }
  try {
    await api("/api/device-calibrations/capture", { method: "POST", body: JSON.stringify({ level: $("#calibration-level").value, reference_db: Number($("#calibration-reference").value), device_ids: onlineIds }) });
    $("#calibration-status").textContent = `${onlineIds.length} Mikrofone erfasst.`;
    await loadCalibrations();
  } catch (error) { $("#calibration-status").textContent = error.message; }
});
$("#device-management-list").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target.closest(".device-editor");
  if (!form) return;
  const nullableNumber = (name) => form.elements[name].value === "" ? null : Number(form.elements[name].value);
  try {
    await api(`/api/devices/${encodeURIComponent(form.dataset.deviceId)}`, { method: "PATCH", body: JSON.stringify({
      name: form.elements.name.value,
      location: form.elements.location.value,
      position_x: nullableNumber("position_x"),
      position_y: nullableNumber("position_y"),
      enabled: form.elements.enabled.checked,
    }) });
    $("#device-management-status").textContent = `${form.elements.name.value} gespeichert.`;
    await loadDevices();
  } catch (error) { $("#device-management-status").textContent = error.message; }
});
function formatTime(value) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("de-DE"); }
function escapeHtml(value) { const node = document.createElement("span"); node.textContent = String(value); return node.innerHTML; }
if (state.token) start();
setInterval(() => { if (state.token) loadTelemetry().catch(() => {}); }, 30000);
