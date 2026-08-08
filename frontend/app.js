const $ = (s) => document.querySelector(s);
const state = { token: localStorage.getItem("em_token"), socket: null, audioSocket: null, audioContext: null, nextAudioTime: 0, devices: [], audioDevices: [], eventClasses: [], soundMap: [], telemetry: [], role: null, reviewClass: "", reviewEvents: [] };
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
  stopAudio();
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
    $("#audio-permissions").classList.toggle("hidden", me.role !== "admin");
    $("#admin-nav").classList.toggle("hidden", me.role !== "admin");
    $("#review-nav").classList.toggle("hidden", me.role === "viewer");
    await loadDevices();
    await loadEventClasses();
    await Promise.all([loadTelemetry(), loadCalibrations(), loadLiveAudioDevices(), loadSoundMap(), loadRecentEvents(), refresh(), loadEvents(), loadRules(), ...(me.role === "viewer" ? [] : [loadReview()]), ...(me.role === "admin" ? [loadAudioPermissions(), loadUsers()] : [])]);
    await preparePush().catch(() => {});
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

async function loadLiveAudioDevices() {
  state.audioDevices = await api("/api/live-audio/devices");
  $("#audio-nav").classList.toggle("hidden", !state.audioDevices.length);
  $("#audio-device").innerHTML = state.audioDevices.map((item) => `<option value="${escapeHtml(item.device_id)}">${escapeHtml(item.name)}</option>`).join("");
}

async function loadSoundMap() {
  state.soundMap = await api(`/api/sound-map?days=${days()}&threshold_db=55`);
  renderSoundMap();
}

function renderSoundMap() {
  const stage = $("#map-stage");
  const canvas = $("#map-heatmap");
  if (!stage.clientWidth) return;
  const scale = 0.3;
  canvas.width = Math.max(1, Math.round(stage.clientWidth * scale));
  canvas.height = Math.max(1, Math.round(stage.clientHeight * scale));
  const context = canvas.getContext("2d");
  const image = context.createImageData(canvas.width, canvas.height);
  const positioned = state.soundMap.filter((item) => item.position_x != null && item.position_y != null);
  for (let y = 0; y < canvas.height; y++) {
    for (let x = 0; x < canvas.width; x++) {
      let weightedLevel = 0;
      let weightSum = 0;
      for (const point of positioned) {
        const dx = x / canvas.width - point.position_x / 100;
        const dy = y / canvas.height - point.position_y / 100;
        const weight = Math.exp(-(dx * dx + dy * dy) / 0.025);
        const level = point.current_db ?? point.average_db ?? 0;
        weightedLevel += level * weight;
        weightSum += weight;
      }
      if (!weightSum) continue;
      const level = weightedLevel / weightSum;
      const intensity = Math.max(0, Math.min(1, (level - 35) / 45));
      const offset = (y * canvas.width + x) * 4;
      image.data[offset] = Math.round(57 + intensity * 187);
      image.data[offset + 1] = Math.round(217 - intensity * 126);
      image.data[offset + 2] = Math.round(138 - intensity * 33);
      image.data[offset + 3] = Math.round(Math.min(175, weightSum * 150));
    }
  }
  context.putImageData(image, 0, 0);
  $("#map-markers").innerHTML = positioned.map((point) => `
    <div class="map-marker" style="left:${point.position_x}%;top:${point.position_y}%">
      <strong>${escapeHtml(point.name)}</strong>
      <span>${point.current_db == null ? "Kein Live-Pegel" : `${point.current_db.toFixed(1)} dB aktuell`}</span>
      <span>${point.exceedances} Überschreitungen · Max ${point.maximum_db?.toFixed(1) ?? "–"} dB</span>
    </div>`).join("");
  const unpositioned = state.soundMap.filter((item) => item.position_x == null || item.position_y == null);
  $("#map-unpositioned").textContent = unpositioned.length ? `Noch ohne Kartenposition: ${unpositioned.map((item) => item.name).join(", ")}` : "";
  $("#sound-map-period").textContent = `letzte ${days()} Tage · Überschreitung ab 55 dB`;
}

async function loadAudioPermissions() {
  const permissions = await api("/api/live-audio/permissions");
  $("#audio-permission-list").innerHTML = permissions.map((permission) => `
    <form class="permission-editor" data-user-id="${permission.user_id}">
      <div><strong>${escapeHtml(permission.username)}</strong><small>${escapeHtml(permission.role)}</small></div>
      <div class="permission-devices">${state.devices.map((device) => `<label><input type="checkbox" name="device_ids" value="${escapeHtml(device.device_id)}" ${permission.device_ids.includes(device.device_id) ? "checked" : ""}> ${escapeHtml(device.name)}</label>`).join("")}</div>
      <button type="submit">Freigaben speichern</button>
    </form>`).join("");
}

async function loadUsers() {
  const users = await api("/auth/users");
  $("#user-list").innerHTML = users.map((user) => `
    <form class="user-editor" data-user-id="${user.id}">
      <div><strong>${escapeHtml(user.username)}</strong><small>Seit ${formatTime(user.created_at)}</small></div>
      <label>Rolle<select name="role"><option value="viewer" ${user.role === "viewer" ? "selected" : ""}>Betrachter</option><option value="operator" ${user.role === "operator" ? "selected" : ""}>Operator</option><option value="admin" ${user.role === "admin" ? "selected" : ""}>Administrator</option></select></label>
      <label class="active-toggle"><input name="active" type="checkbox" ${user.active ? "checked" : ""}> Aktiv</label>
      <label>Neues Passwort<input name="password" type="password" minlength="10" placeholder="unverändert"></label>
      <button type="submit">Speichern</button>
    </form>`).join("");
}

async function loadEventClasses() {
  state.eventClasses = await api("/api/event-classes");
  const bases = state.eventClasses.filter((item) => item.level === "base");
  const parentOptions = `<option value="">Keine</option>${bases.map((item) => `<option value="${escapeHtml(item.code)}">${escapeHtml(item.name)}</option>`).join("")}`;
  $("#class-parent").innerHTML = parentOptions;
  $("#class-list").innerHTML = state.eventClasses.map((item) => `
    <form class="class-editor" data-class-id="${item.id}" data-sort-order="${item.sort_order}">
      <strong>${escapeHtml(item.code)}</strong>
      <label>Name<input name="name" value="${escapeHtml(item.name)}" maxlength="120" required></label>
      <label>Ebene<select name="level"><option value="base" ${item.level === "base" ? "selected" : ""}>Basis</option><option value="fine" ${item.level === "fine" ? "selected" : ""}>Fein</option></select></label>
      <label>Basisklasse<select name="parent_code">${parentOptions.replace(`value="${item.parent_code || ""}"`, `value="${item.parent_code || ""}" selected`)}</select></label>
      <label class="active-toggle"><input name="active" type="checkbox" ${item.active ? "checked" : ""}> Aktiv</label>
      <label class="active-toggle"><input name="trainable" type="checkbox" ${item.trainable ? "checked" : ""}> Trainierbar</label>
      <button type="submit">Speichern</button>
    </form>`).join("");
}

async function startAudio() {
  const deviceId = $("#audio-device").value;
  if (!deviceId) return;
  stopAudio();
  state.audioContext = new AudioContext();
  await state.audioContext.resume();
  state.nextAudioTime = state.audioContext.currentTime + 0.1;
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  state.audioSocket = new WebSocket(`${scheme}://${location.host}/ws/audio/${encodeURIComponent(deviceId)}?token=${encodeURIComponent(state.token)}`);
  state.audioSocket.binaryType = "arraybuffer";
  state.audioSocket.onopen = () => { $("#audio-status").textContent = "Verbunden – Audiopuffer wird gefüllt"; $("#audio-toggle").textContent = "Wiedergabe stoppen"; };
  state.audioSocket.onmessage = (message) => {
    if (typeof message.data === "string" || !state.audioContext) return;
    const samples = new Int16Array(message.data);
    const buffer = state.audioContext.createBuffer(1, samples.length, 16000);
    const channel = buffer.getChannelData(0);
    for (let index = 0; index < samples.length; index++) channel[index] = samples[index] / 32768;
    const source = state.audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(state.audioContext.destination);
    state.nextAudioTime = Math.max(state.nextAudioTime, state.audioContext.currentTime + 0.05);
    source.start(state.nextAudioTime);
    state.nextAudioTime += buffer.duration;
    $("#audio-status").textContent = "Live-Wiedergabe aktiv";
  };
  state.audioSocket.onclose = () => { if (state.audioContext) stopAudio("Verbindung beendet"); };
}

function stopAudio(message = "Wiedergabe gestoppt") {
  const socket = state.audioSocket;
  state.audioSocket = null;
  if (socket) socket.onclose = null;
  socket?.close();
  state.audioContext?.close();
  state.audioContext = null;
  state.nextAudioTime = 0;
  if ($("#audio-status")) $("#audio-status").textContent = message;
  if ($("#audio-toggle")) $("#audio-toggle").textContent = "Wiedergabe starten";
}

async function preparePush() {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;
  const config = await api("/push/config");
  if (!config.enabled) return;
  const registration = await navigator.serviceWorker.register("/sw.js");
  const existing = await registration.pushManager.getSubscription();
  if (existing) {
    await savePushSubscription(existing);
    $("#push-enable").textContent = "Push aktiv";
  } else {
    $("#push-enable").textContent = "Push aktivieren";
  }
  $("#push-enable").classList.remove("hidden");
  $("#push-enable").dataset.publicKey = config.public_key;
}

function decodePushKey(value) {
  const padding = "=".repeat((4 - value.length % 4) % 4);
  const raw = atob((value + padding).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (character) => character.charCodeAt(0));
}

async function savePushSubscription(subscription) {
  const data = subscription.toJSON();
  await api("/push/subscriptions", { method: "POST", body: JSON.stringify({
    endpoint: data.endpoint,
    p256dh: data.keys.p256dh,
    auth: data.keys.auth,
  }) });
}

async function enablePush() {
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("Benachrichtigungen wurden nicht freigegeben.");
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: decodePushKey($("#push-enable").dataset.publicKey),
  });
  await savePushSubscription(subscription);
  $("#push-enable").textContent = "Push aktiv";
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

async function loadRecentEvents() {
  const entries = await api("/push/noise-log?limit=5");
  $("#recent-events").innerHTML = entries.length ? entries.map((entry) => {
    const witnesses = entry.witnesses.length ? entry.witnesses.map((item) => `<span class="witness ${item.response}">${escapeHtml(item.username)}: ${item.response === "confirmed" ? "bestätigt" : "abgelehnt"}</span>`).join("") : "<span class=\"witness pending\">Keine Zeugenreaktion</span>";
    const bases = state.eventClasses.filter((item) => item.active && item.level === "base");
    const primaryOptions = bases.map((item) => `<option value="${escapeHtml(item.code)}" ${entry.primary_class_code === item.code ? "selected" : ""}>${escapeHtml(item.name)}</option>`).join("");
    const correction = state.role === "viewer" ? "" : `<form class="classification-editor" data-event-id="${entry.event_id}"><select name="primary_class_code">${primaryOptions}</select><select name="subclass_code" data-current="${escapeHtml(entry.subclass_code || "")}"></select><input name="reason" minlength="3" placeholder="Korrekturgrund" required><button type="submit">Zuordnung speichern</button></form>`;
    return `<div class="recent-event"><time>${formatTime(entry.timestamp)}</time><strong>${escapeHtml(entry.label)}</strong><span>${escapeHtml(entry.device)} · ${entry.db_level.toFixed(1)} dB<br>${escapeHtml(entry.classification_status === "manual" ? `manuell durch ${entry.corrected_by}` : "automatisch")}</span><div>${witnesses}${correction}</div></div>`;
  }).join("") : "<p>Noch keine Ereignisse erfasst.</p>";
  document.querySelectorAll(".classification-editor").forEach((form) => populateSubclassOptions(form));
}

function populateSubclassOptions(form) {
  const primaryCode = form.elements.primary_class_code.value;
  const current = form.elements.subclass_code.dataset.current;
  const fine = state.eventClasses.filter((item) => item.active && item.level === "fine" && (item.parent_code == null || item.parent_code === primaryCode));
  form.elements.subclass_code.innerHTML = `<option value="">Keine Feinzuordnung</option>${fine.map((item) => `<option value="${escapeHtml(item.code)}" ${current === item.code ? "selected" : ""}>${escapeHtml(item.name)}</option>`).join("")}`;
}

function reviewSubclassOptions() {
  const primary = $("#review-primary").value;
  const fine = state.eventClasses.filter((item) => item.active && item.level === "fine" && (item.parent_code == null || item.parent_code === primary));
  $("#review-subclass").innerHTML = `<option value="">Keine Feinzuordnung</option>${fine.map((item) => `<option value="${escapeHtml(item.code)}">${escapeHtml(item.name)}</option>`).join("")}`;
}

async function loadReview() {
  const [summary, runs] = await Promise.all([api("/events/review/summary"), api("/events/review/runs")]);
  $("#r-open-unknown").textContent = summary.open_unknown;
  $("#r-open-recognized").textContent = summary.open_recognized;
  $("#r-done-unknown").textContent = summary.completed_unknown;
  $("#r-done-recognized").textContent = summary.completed_recognized;
  const classes = [{ code: "UNKNOWN", name: "Unbekannt" }, ...state.eventClasses.filter((item) => item.active)];
  $("#review-classes").innerHTML = classes.map((item) => {
    const counts = summary.by_class[item.code] || { open: 0, completed: 0 };
    return `<button type="button" class="class-tile ${state.reviewClass === item.code ? "active" : ""}" data-review-class="${escapeHtml(item.code)}"><strong>${escapeHtml(item.name)}</strong><small>${counts.open} offen · ${counts.completed} erledigt</small></button>`;
  }).join("");
  const bases = state.eventClasses.filter((item) => item.active && item.level === "base");
  $("#review-primary").innerHTML = bases.map((item) => `<option value="${escapeHtml(item.code)}">${escapeHtml(item.name)}</option>`).join("");
  reviewSubclassOptions();
  $("#review-runs").innerHTML = runs.length ? runs.map((run) => {
    const progress = run.total ? Math.round(run.processed / run.total * 100) : 0;
    const action = run.status === "running" || run.status === "pending" ? `<button data-run-pause="${run.id}">Unterbrechen</button>` : run.status === "paused" ? `<button data-run-resume="${run.id}">Fortsetzen</button>` : "";
    return `<div class="review-run"><div><strong>${escapeHtml(run.kind)}</strong><br><small>${escapeHtml(run.status)} · ${run.changed} verbessert</small></div><div><span>${run.processed} / ${run.total}</span><div class="review-progress"><i style="width:${progress}%"></i></div></div>${action}</div>`;
  }).join("") : "<p>Noch kein Prüflauf vorhanden.</p>";
  await loadReviewQueue();
}

async function loadReviewQueue() {
  const query = new URLSearchParams({ status: $("#review-status").value, limit: "500" });
  if (state.reviewClass) query.set("class_code", state.reviewClass);
  state.reviewEvents = await api(`/events/review/queue?${query}`);
  $("#review-events").innerHTML = state.reviewEvents.length ? state.reviewEvents.map((event) => `<label class="review-event"><input type="checkbox" value="${event.id}"><strong>${escapeHtml(event.label_de || event.label)}</strong><span>${escapeHtml(event.device)} · ${event.db_level.toFixed(1)} dB<br>${formatTime(event.timestamp)}</span><span>${escapeHtml(event.subclass_code || event.primary_class_code || "Unbekannt")} · ${Math.round(event.confidence * 100)} %</span></label>`).join("") : "<p>Keine passenden Ereignisse.</p>";
  updateReviewSelection();
}

function updateReviewSelection() {
  const count = document.querySelectorAll("#review-events input:checked").length;
  $("#review-selection").textContent = `${count} ausgewählt`;
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
  state.socket.onmessage = (message) => { addEvent(JSON.parse(message.data)); refresh(); loadRecentEvents(); };
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
$("#push-enable").addEventListener("click", () => enablePush().catch((error) => { $("#push-enable").textContent = error.message; }));
$("#days-filter").addEventListener("change", () => Promise.all([refresh(), loadSoundMap()]));
$("#device-filter").addEventListener("change", () => Promise.all([refresh(), loadEvents()]));
document.querySelectorAll(".nav").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".nav").forEach((n) => n.classList.toggle("active", n === button));
  document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
  $(`#${button.dataset.view}`).classList.remove("hidden");
  $("#title").textContent = button.textContent.trim();
}));
$("#audio-toggle").addEventListener("click", () => state.audioSocket ? stopAudio() : startAudio().catch((error) => stopAudio(error.message)));
$("#audio-device").addEventListener("change", () => stopAudio("Mikrofon ausgewählt – bereit"));
$("#review-classes").addEventListener("click", async (e) => {
  const tile = e.target.closest("[data-review-class]");
  if (!tile) return;
  state.reviewClass = state.reviewClass === tile.dataset.reviewClass ? "" : tile.dataset.reviewClass;
  await loadReview();
});
$("#review-status").addEventListener("change", loadReviewQueue);
$("#review-primary").addEventListener("change", reviewSubclassOptions);
$("#review-events").addEventListener("change", updateReviewSelection);
$("#review-select-all").addEventListener("click", () => {
  document.querySelectorAll("#review-events input").forEach((item) => { item.checked = true; });
  updateReviewSelection();
});
$("#review-bulk-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const eventIds = Array.from(document.querySelectorAll("#review-events input:checked"), (item) => Number(item.value));
  if (!eventIds.length) { $("#review-status-text").textContent = "Bitte mindestens ein Ereignis auswählen."; return; }
  try {
    await api("/events/review/bulk-classification", { method: "POST", body: JSON.stringify({ event_ids: eventIds, primary_class_code: $("#review-primary").value, subclass_code: $("#review-subclass").value || null, reason: $("#review-reason").value }) });
    $("#review-status-text").textContent = `${eventIds.length} Ereignisse bestätigt.`;
    await Promise.all([loadReview(), loadRecentEvents(), loadEvents()]);
  } catch (error) { $("#review-status-text").textContent = error.message; }
});
$("#review-run").addEventListener("click", async () => {
  try { await api("/events/review/runs", { method: "POST", body: JSON.stringify({ kind: "automatic" }) }); await loadReview(); }
  catch (error) { $("#review-status-text").textContent = error.message; }
});
$("#review-runs").addEventListener("click", async (e) => {
  const pause = e.target.dataset.runPause;
  const resume = e.target.dataset.runResume;
  if (pause) await api(`/events/review/runs/${pause}/pause`, { method: "POST" });
  if (resume) await api(`/events/review/runs/${resume}/resume`, { method: "POST" });
  if (pause || resume) await loadReview();
});
$("#audio-permission-list").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target.closest(".permission-editor");
  if (!form) return;
  const deviceIds = Array.from(form.querySelectorAll("input[name=device_ids]:checked"), (item) => item.value);
  try {
    await api(`/api/live-audio/permissions/${form.dataset.userId}`, { method: "PUT", body: JSON.stringify({ device_ids: deviceIds }) });
    $("#audio-permission-status").textContent = "Freigaben gespeichert.";
    await loadAudioPermissions();
  } catch (error) { $("#audio-permission-status").textContent = error.message; }
});
$("#user-create-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/auth/users", { method: "POST", body: JSON.stringify({ username: $("#new-username").value, password: $("#new-password").value, role: $("#new-role").value }) });
    e.target.reset();
    $("#user-create-status").textContent = "Benutzer angelegt.";
    await Promise.all([loadUsers(), loadAudioPermissions()]);
  } catch (error) { $("#user-create-status").textContent = error.message; }
});
$("#user-list").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target.closest(".user-editor");
  if (!form) return;
  try {
    await api(`/auth/users/${form.dataset.userId}`, { method: "PATCH", body: JSON.stringify({ role: form.elements.role.value, active: form.elements.active.checked, password: form.elements.password.value || null }) });
    $("#user-status").textContent = "Benutzer aktualisiert.";
    await Promise.all([loadUsers(), loadAudioPermissions()]);
  } catch (error) { $("#user-status").textContent = error.message; }
});
$("#class-create-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/api/event-classes", { method: "POST", body: JSON.stringify({ code: $("#class-code").value.toUpperCase(), name: $("#class-name").value, level: $("#class-level").value, parent_code: $("#class-parent").value || null }) });
    e.target.reset();
    $("#class-status").textContent = "Klasse angelegt.";
    await loadEventClasses();
  } catch (error) { $("#class-status").textContent = error.message; }
});
$("#class-list").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target.closest(".class-editor");
  if (!form) return;
  try {
    await api(`/api/event-classes/${form.dataset.classId}`, { method: "PATCH", body: JSON.stringify({ name: form.elements.name.value, level: form.elements.level.value, parent_code: form.elements.parent_code.value || null, active: form.elements.active.checked, trainable: form.elements.trainable.checked, sort_order: Number(form.dataset.sortOrder) }) });
    $("#class-status").textContent = "Klasse aktualisiert.";
    await loadEventClasses();
  } catch (error) { $("#class-status").textContent = error.message; }
});
$("#recent-events").addEventListener("change", (e) => {
  const form = e.target.closest(".classification-editor");
  if (form && e.target.name === "primary_class_code") {
    form.elements.subclass_code.dataset.current = "";
    populateSubclassOptions(form);
  }
});
$("#recent-events").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target.closest(".classification-editor");
  if (!form) return;
  try {
    await api(`/events/${form.dataset.eventId}/classification`, { method: "PATCH", body: JSON.stringify({ primary_class_code: form.elements.primary_class_code.value, subclass_code: form.elements.subclass_code.value || null, reason: form.elements.reason.value }) });
    await Promise.all([loadRecentEvents(), loadEvents()]);
  } catch (error) { form.elements.reason.setCustomValidity(error.message); form.reportValidity(); }
});
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
    await loadSoundMap();
  } catch (error) { $("#device-management-status").textContent = error.message; }
});
function formatTime(value) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("de-DE"); }
function escapeHtml(value) { const node = document.createElement("span"); node.textContent = String(value); return node.innerHTML; }
if (state.token) start();
setInterval(() => { if (state.token) loadTelemetry().catch(() => {}); }, 30000);
window.addEventListener("resize", () => { if (state.token) renderSoundMap(); });
