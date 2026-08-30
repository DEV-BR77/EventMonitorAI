const $ = (s) => document.querySelector(s);
function loadListenedEvents() {
  try { return new Set(JSON.parse(localStorage.getItem("em_listened_events") || "[]").map(String)); }
  catch (_) { return new Set(); }
}
const state = { token: localStorage.getItem("em_token"), socket: null, audioSocket: null, audioContext: null, audioGain: null, audioHighpass: null, audioLowpass: null, audioElement: null, audioDestination: null, audioPackets: 0, clipSource: null, clipContext: null, clipButton: null, clipAudioElement: null, clipAudioDestination: null, clipNoiseReduction: localStorage.getItem("em_clip_noise_filter") !== "false", nextAudioTime: 0, devices: [], audioDevices: [], eventClasses: [], soundMap: [], telemetry: [], calibrations: [], calibrationDrafts: new Map(), telemetryLoading: false, people: [], personMediaUrls: [], speakerClusters: [], speakerClusterId: null, speakerSampleOffset: 0, speakerSampleTotal: 0, calibrationRuns: [], role: null, reviewClass: "", reviewEvents: [], liveEvents: [], classificationDrafts: new Map(), listenedEvents: loadListenedEvents(), kpiInitialized: false };
const days = () => $("#days-filter").value;
const device = () => $("#device-filter").value;
const localDate = (value) => value.toLocaleDateString("sv-SE");
function selectedRange() {
  const today = new Date(); today.setHours(12, 0, 0, 0);
  let from = new Date(today), to = new Date(today);
  if (["3", "7", "30", "90"].includes(days())) from.setDate(from.getDate() - Number(days()) + 1);
  if (days() === "single") {
    const chosen = $("#date-from-filter").value || localDate(today);
    return { from: chosen, to: chosen, days: 1 };
  }
  if (days() === "range") {
    const start = $("#date-from-filter").value || localDate(today);
    const end = $("#date-to-filter").value || start;
    const ordered = start <= end ? [start, end] : [end, start];
    return { from: ordered[0], to: ordered[1], days: Math.floor((new Date(`${ordered[1]}T12:00:00`) - new Date(`${ordered[0]}T12:00:00`)) / 86400000) + 1 };
  }
  return { from: localDate(from), to: localDate(to), days: Number(days()) || 1 };
}
function rangeQuery() {
  const range = selectedRange();
  const query = new URLSearchParams({ days: String(Math.min(366, range.days)), date_from: range.from, date_to: range.to });
  if (device()) query.set("device", device());
  return query;
}
function eventRangeQuery() {
  const range = selectedRange();
  const end = new Date(`${range.to}T12:00:00`); end.setDate(end.getDate() + 1);
  return { start: `${range.from}T00:00:00`, end: `${localDate(end)}T00:00:00` };
}
function rangeLabel() {
  const range = selectedRange();
  return range.from === range.to ? new Date(`${range.from}T12:00:00`).toLocaleDateString("de-DE") : `${new Date(`${range.from}T12:00:00`).toLocaleDateString("de-DE")}–${new Date(`${range.to}T12:00:00`).toLocaleDateString("de-DE")}`;
}
const categoryNames = { DEVICE: "Geräuschquelle", VOCALIZATION: "Lautäußerung", VOICE: "Stimme", HUMAN_SOUND: "Menschliches Geräusch", HOUSEHOLD: "Haushalt/Alltag", ANIMAL: "Tier", AMBIENT: "Umgebung", MUSIC: "Musik", VEHICLE: "Fahrzeug", IMPACT: "Schlag/Aufprall", OTHER: "Sonstiges" };

function markEventListened(eventId, button) {
  const key = String(eventId);
  state.listenedEvents.delete(key);
  state.listenedEvents.add(key);
  while (state.listenedEvents.size > 2000) state.listenedEvents.delete(state.listenedEvents.values().next().value);
  localStorage.setItem("em_listened_events", JSON.stringify([...state.listenedEvents]));
  button.closest(".event-row,.recent-event,.review-event")?.classList.add("listened");
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const requestToken = state.token;
  if (requestToken) headers.Authorization = `Bearer ${requestToken}`;
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401 && requestToken && requestToken === state.token) {
    const error = new Error("Sitzung abgelaufen");
    error.status = 401;
    throw error;
  }
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
  stopEventClip();
  $("#app").classList.add("hidden");
  $("#auth").classList.remove("hidden");
}

const activeView = () => document.querySelector(".nav.active")?.dataset.view || "overview";

async function loadView(view) {
  const tasks = {
    overview: [refresh, loadRecentEvents, ...(state.role === "admin" ? [loadAdminNotifications] : [])],
    kpis: [loadKpis],
    "sound-map": [loadSoundMap],
    audio: [loadLiveAudioDevices],
    live: [loadLiveLevels, loadEvents, loadCalibrations],
    rules: [loadRules],
    support: [loadSupport],
    account: [loadAccount],
    administration: [loadUsers, loadAssessmentConfig, loadAudioPermissions, ...(state.role === "admin" ? [loadTenants, loadWebsiteAnalytics] : [])],
    devices: [loadTelemetry, loadCalibrations, loadCalibrationReferenceRuns],
    people: [loadPeople, loadSpeakerClusters, loadSpeakerAnalysisProgress],
    review: [loadReview],
  }[view] || [];
  const results = await Promise.allSettled(tasks.map((task) => task()));
  const rejected = results.filter((result) => result.status === "rejected");
  if (rejected.some((result) => result.reason?.status === 401)) throw rejected.find((result) => result.reason?.status === 401).reason;
  if (rejected.length) console.warn(`${view} teilweise geladen`, rejected.map((result) => result.reason));
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
    $("#admin-navigation").classList.toggle("hidden", me.role !== "admin");
    $("#admin-notification-center").classList.toggle("hidden", me.role !== "admin");
    $("#tenant-management").classList.toggle("hidden", me.role !== "admin" || me.tenant_id !== 1);
    $("#website-analytics").classList.toggle("hidden", me.role !== "admin" || me.tenant_id !== 1);
    $("#map-positioning").classList.toggle("hidden", me.role !== "admin");
    $("#map-stage").classList.toggle("positioning", me.role === "admin");
    const today = new Date().toLocaleDateString("sv-SE");
    if (!$("#date-from-filter").value) $("#date-from-filter").value = today;
    if (!$("#date-to-filter").value) $("#date-to-filter").value = today;
    await loadDevices();
    await loadLiveAudioDevices();
    await loadTelemetry().catch(() => {});
    await loadEventClasses();
    if (me.role !== "viewer") await loadPeople();
    if (me.role !== "admin" && document.querySelector(".nav.active")?.closest("#admin-navigation")) {
      document.querySelector('.nav[data-view="overview"]').click();
    }
    await loadView(activeView());
    await preparePush().catch(() => {});
    connectLive();
  } catch (error) {
    if (error?.status === 401) logout();
    else console.error("Dashboard konnte nicht vollständig geladen werden", error);
  }
}

function renderSystemStatus(error = null) {
  const indicator = $("#system-status");
  const enabled = state.devices.filter((item) => item.enabled);
  const now = Date.now();
  const telemetryByDevice = new Map(state.telemetry.map((item) => [item.device_id, item]));
  const online = enabled.filter((item) => {
    const seen = telemetryByDevice.get(item.device_id)?.last_seen;
    return seen && now - new Date(seen).valueOf() < 90000;
  });
  let kind = "ok";
  let label = `${online.length}/${enabled.length} Mikrofone online`;
  let detail = enabled.map((item) => {
    const seen = telemetryByDevice.get(item.device_id)?.last_seen;
    if (!seen) return `${item.name}: noch kein Signal`;
    const age = Math.max(0, Math.round((now - new Date(seen).valueOf()) / 1000));
    return `${item.name}: ${age} s seit letztem Signal`;
  }).join(" · ");
  if (error) {
    kind = "error";
    label = "Dashboard-API nicht erreichbar";
    detail = error.message || "Statusabfrage fehlgeschlagen";
  } else if (!enabled.length) {
    kind = "warning";
    label = "Keine Mikrofone aktiviert";
    detail = "In der Mikrofonverwaltung ist kein Gerät aktiv.";
  } else if (!online.length) {
    kind = "error";
    label = `Messung ausgefallen · 0/${enabled.length} online`;
  } else if (online.length < enabled.length) {
    kind = "warning";
    label = `Messung gestört · ${online.length}/${enabled.length} online`;
  }
  indicator.className = `system-status ${kind}`;
  indicator.querySelector("span").textContent = label;
  indicator.title = detail || label;
}

async function loadTelemetry() {
  if (state.telemetryLoading) return;
  state.telemetryLoading = true;
  let telemetry;
  try {
    telemetry = await api("/api/device-telemetry");
  } catch (error) {
    renderSystemStatus(error);
    throw error;
  } finally {
    state.telemetryLoading = false;
  }
  state.telemetry = telemetry;
  renderSystemStatus();
  renderLiveCalibration();
  const now = Date.now();
  $("#device-health").innerHTML = telemetry.length ? telemetry.map((item) => {
    const configured = state.devices.find((device) => device.device_id === item.device_id);
    const ageSeconds = Math.max(0, Math.round((now - new Date(item.last_seen).valueOf()) / 1000));
    const online = ageSeconds < 90;
    const total = item.packets_received + item.packets_lost;
    return `<div class="device-card">
      <div><i class="status-dot ${online && configured?.enabled !== false ? "online" : "offline"}"></i><strong>${escapeHtml(configured?.name || item.device_id)}</strong></div>
      <span>${configured?.enabled === false ? "Administrativ inaktiv" : online ? "Online" : `Seit ${ageSeconds} s ohne Signal`} · ${escapeHtml(configured?.location || item.device_id)}</span>
      <dl><dt>Messwert von</dt><dd>${formatTime(item.last_seen)}</dd><dt>Alter</dt><dd>${ageSeconds} s</dd><dt>Firmware</dt><dd>${escapeHtml(item.firmware_version || "Legacy")}</dd><dt>Quelle</dt><dd>${escapeHtml(item.source_ip)}</dd><dt>Aktueller Pegel</dt><dd>${item.db_level.toFixed(1)} dB</dd><dt>Pakete</dt><dd>${total.toLocaleString("de-DE")}</dd><dt>Verlust</dt><dd>${(item.loss_rate * 100).toFixed(3)} %</dd><dt>Samplerate</dt><dd>${item.sample_rate.toLocaleString("de-DE")} Hz</dd><dt>Peak</dt><dd>${item.peak}</dd></dl>
    </div>`;
  }).join("") : "<p>Noch keine Telemetriedaten. Legacy-Firmware sendet weiterhin Audio, aber noch keinen Gerätestatus.</p>";
}

async function loadCalibrations() {
  const calibrations = await api("/api/device-calibrations");
  state.calibrations = calibrations;
  renderLiveCalibration();
  const value = (reference, measured) => reference == null ? "–" : `${measured.toFixed(1)} / ${reference.toFixed(1)} dB`;
  $("#calibration-list").innerHTML = calibrations.length ? calibrations.map((item) =>
    `<div class="calibration-row"><strong>${escapeHtml(item.device_id)}</strong><span>Leise: ${value(item.low_reference_db, item.low_measured_db)}</span><span>Mittel: ${value(item.medium_reference_db, item.medium_measured_db)}</span><span>Laut: ${value(item.high_reference_db, item.high_measured_db)}</span><b>Aktiv: ${item.applied_offset_db >= 0 ? "+" : ""}${item.applied_offset_db.toFixed(2)} dB<br>Empfohlen: ${item.recommended_offset_db >= 0 ? "+" : ""}${item.recommended_offset_db.toFixed(2)} dB${item.reference_points ? `<br>${item.reference_points} Vergleiche · MAE ${item.reference_mae_db.toFixed(2)} dB` : ""}</b></div>`
  ).join("") : "<p>Noch keine Referenzmessung erfasst.</p>";
}

function renderLiveCalibration() {
  const container = $("#live-calibration-devices");
  if (!container) return;
  const enabled = state.devices.filter((item) => item.enabled);
  const editable = state.role === "admin";
  const signature = `${editable}:${enabled.map((item) => item.device_id).join("|")}`;
  if (container.dataset.signature !== signature) {
    container.dataset.signature = signature;
    container.innerHTML = enabled.length ? enabled.map((item) => `<form class="live-calibration-card" data-device-id="${escapeHtml(item.device_id)}">
      <div class="live-calibration-heading"><i class="status-dot"></i><div><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.location || item.device_id)}</small></div></div>
      <div class="live-db-value" data-live-db>–</div>
      <div class="live-db-meta"><span data-live-age>Noch kein Messwert</span><span data-live-offset>Offset wird geladen …</span></div>
      ${editable ? `<div class="live-calibration-controls"><div class="offset-preview" aria-label="Korrektur einstellen"><button type="button" data-offset-adjust="-1" aria-label="Korrektur verringern">−</button><strong data-offset-draft>0,00 dB</strong><button type="button" data-offset-adjust="1" aria-label="Korrektur erhöhen">+</button></div><label>Schrittweite<select name="offset_step"><option value="0.1">0,1 dB</option><option value="0.5" selected>0,5 dB</option><option value="1">1,0 dB</option></select></label><button type="submit">Korrektur übernehmen</button><button type="button" class="secondary" data-offset-reset>Vorschau verwerfen</button></div><small class="live-calibration-status">Plus/Minus verändert nur die Vorschau. Erst „Korrektur übernehmen“ speichert die Änderung.</small>` : "<small class=\"live-calibration-status\">Nur Administratoren können den Offset ändern.</small>"}
    </form>`).join("") : "<p>Keine aktiven Mikrofone eingerichtet.</p>";
  }
  const now = Date.now();
  const telemetry = new Map(state.telemetry.map((item) => [item.device_id, item]));
  const calibrations = new Map(state.calibrations.map((item) => [item.device_id, item]));
  container.querySelectorAll(".live-calibration-card").forEach((card) => {
    const item = telemetry.get(card.dataset.deviceId);
    const calibration = calibrations.get(card.dataset.deviceId);
    const appliedOffset = calibration?.applied_offset_db || 0;
    let draft = state.calibrationDrafts.get(card.dataset.deviceId);
    if (!draft || !draft.dirty) {
      draft = { value: appliedOffset, dirty: false };
      state.calibrationDrafts.set(card.dataset.deviceId, draft);
    }
    const previewDb = item ? Math.max(0, item.db_level + draft.value - appliedOffset) : null;
    const age = item ? Math.max(0, Math.round((now - new Date(item.last_seen).valueOf()) / 1000)) : null;
    card.querySelector(".status-dot").classList.toggle("online", age != null && age < 10);
    card.querySelector("[data-live-db]").textContent = previewDb == null ? "–" : `${previewDb.toFixed(1)} dB(A)`;
    card.querySelector("[data-live-age]").textContent = age == null ? "Noch kein Messwert" : age < 2 ? "Gerade aktualisiert" : `Vor ${age} Sekunden aktualisiert`;
    card.querySelector("[data-live-offset]").textContent = draft.dirty ? `Vorschau · gemeldet ${item ? item.db_level.toFixed(1) : "–"} dB(A)` : `Aktiver Offset: ${appliedOffset >= 0 ? "+" : ""}${appliedOffset.toFixed(2)} dB`;
    const draftLabel = card.querySelector("[data-offset-draft]");
    if (draftLabel) draftLabel.textContent = `${draft.value >= 0 ? "+" : ""}${draft.value.toFixed(2)} dB`;
    card.classList.toggle("previewing", draft.dirty);
  });
}

async function loadCalibrationReferenceRuns() {
  state.calibrationRuns = await api("/api/device-calibrations/reference-runs");
  $("#calibration-reference-runs").innerHTML = state.calibrationRuns.length ? state.calibrationRuns.map((run) => `<div class="reference-run"><strong>${escapeHtml(run.filename)}</strong><span> · ${run.reference_points} CSV-Werte · ${formatTime(run.started_at)} bis ${formatTime(run.ended_at)}</span>${run.results.map((item) => `<div class="reference-result"><strong>${escapeHtml(item.device_id)}</strong><span>${item.matched_points} Treffer</span><span>Referenz Ø ${item.mean_reference_db.toFixed(1)} dB</span><span>Mikrofon Ø ${item.mean_measured_db.toFixed(1)} dB</span><span>Abweichung ${item.mean_difference_db >= 0 ? "+" : ""}${item.mean_difference_db.toFixed(2)} dB · MAE ${item.mae_db.toFixed(2)} dB</span>${state.role === "admin" ? `<button type="button" data-apply-offset="${escapeHtml(item.device_id)}">Offset ${item.recommended_offset_db >= 0 ? "+" : ""}${item.recommended_offset_db.toFixed(2)} dB anwenden</button>` : ""}</div>`).join("")}</div>`).join("") : "<p>Noch keine CSV-Referenzmessung importiert.</p>";
}

async function loadDevices() {
  state.devices = await api("/api/devices");
  const options = state.devices.map((d) => `<option value="${escapeHtml(d.device_id)}">${escapeHtml(d.name)}</option>`).join("");
  $("#device-filter").innerHTML = `<option value="">Alle Geräte</option>${options}`;
  $("#rule-device").innerHTML = `<option value="*">Alle Geräte</option>${options}`;
  $("#import-device").innerHTML = options;
  $("#calibration-reference-devices").innerHTML = state.devices.map((d) => `<label><input type="checkbox" name="calibration_device" value="${escapeHtml(d.device_id)}" ${d.enabled ? "checked" : ""}> ${escapeHtml(d.name)}</label>`).join("");
  const currentMapDevice = $("#map-position-device").value;
  $("#map-position-device").innerHTML = state.devices.map((d) => `<option value="${escapeHtml(d.device_id)}" ${d.device_id === currentMapDevice ? "selected" : ""}>${escapeHtml(d.name)}${d.position_x == null || d.position_y == null ? " · noch nicht platziert" : ""}</option>`).join("");
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
      ${state.role === "admin" ? `<button type="button" data-device-credential="${escapeHtml(d.device_id)}">Internetzugang neu ausstellen</button>` : ""}
    </form>`).join("") : "<p>Noch keine Mikrofone registriert.</p>";
}

async function loadLiveAudioDevices() {
  state.audioDevices = await api("/api/live-audio/devices");
  $("#audio-nav").classList.toggle("hidden", !state.audioDevices.length);
  $("#audio-device").innerHTML = state.audioDevices.map((item) => `<option value="${escapeHtml(item.device_id)}">${escapeHtml(item.name)}</option>`).join("");
}

async function loadSoundMap() {
  const query = rangeQuery(); query.set("threshold_db", "55");
  state.soundMap = await api(`/api/sound-map?${query}`);
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
  $("#sound-map-period").textContent = `${rangeLabel()} · Überschreitung ab 55 dB`;
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
      <label>Passwort bestätigen<input name="password_confirm" type="password" minlength="10" placeholder="unverändert"></label>
      <button type="submit">Speichern</button>
    </form>`).join("");
}

async function loadAssessmentConfig() {
  const config = await api("/api/assessment-config");
  state.assessmentConfig = config;
  $("#surcharge-db").value = config.sensitive_surcharge_db;
  $("#surcharge-live").checked = config.apply_to_live;
  renderAssessmentClassRules();
}

function renderAssessmentClassRules() {
  const target = $("#assessment-class-list");
  if (!target || !state.assessmentConfig || !state.eventClasses.length) return;
  const rules = state.assessmentConfig.class_rules || {};
  const included = (item) => Object.hasOwn(rules, item.code)
    ? rules[item.code]
    : (item.parent_code && Object.hasOwn(rules, item.parent_code) ? rules[item.parent_code] : true);
  const rows = (level) => state.eventClasses.filter((item) => item.level === level).map((item) => `
    <label class="assessment-class-rule ${item.active ? "" : "inactive"}">
      <input type="checkbox" data-assessment-class="${escapeHtml(item.code)}" ${included(item) ? "checked" : ""}>
      <span><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.code)}${item.parent_code ? ` · unter ${escapeHtml(state.eventClasses.find((parent) => parent.code === item.parent_code)?.name || item.parent_code)}` : ""}${item.active ? "" : " · inaktiv"}</small></span>
      <em>${included(item) ? "fließt ein" : "ausgeschlossen"}</em>
    </label>`).join("");
  target.innerHTML = `<section><h3>Hauptkategorien</h3>${rows("base")}</section><section><h3>Feinklassen</h3>${rows("fine")}</section>`;
}

function fileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1]);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
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
      <label>Zugeordnet zu<select name="parent_code" title="Nur bei Feinzuordnungen: zugehörige Basisklasse">${parentOptions.replace(`value="${item.parent_code || ""}"`, `value="${item.parent_code || ""}" selected`)}</select></label>
      <label class="active-toggle" title="In Zuordnungs-Auswahlfeldern verfügbar"><input name="active" type="checkbox" ${item.active ? "checked" : ""}> Aktiv</label>
      <label class="active-toggle" title="Bestätigte Beispiele dürfen zum KI-Training verwendet werden"><input name="trainable" type="checkbox" ${item.trainable ? "checked" : ""}> Trainierbar</label>
      <label class="active-toggle" title="Treffer standardmäßig aus Lagebild und Live-Strom ausblenden"><input name="hidden_by_default" type="checkbox" ${item.hidden_by_default ? "checked" : ""}> Ausblenden</label>
      <button type="submit">Speichern</button>
    </form>`).join("");
  renderAssessmentClassRules();
}

async function initializeAudioOutput() {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) throw new Error("Dieser Browser unterstützt keine Audioausgabe.");
  if (state.audioContext) return;
  state.audioContext = new AudioContextClass({ sampleRate: 16000 });
  state.audioGain = state.audioContext.createGain();
  state.audioHighpass = state.audioContext.createBiquadFilter();
  state.audioHighpass.type = "highpass";
  state.audioHighpass.frequency.value = 80;
  state.audioLowpass = state.audioContext.createBiquadFilter();
  state.audioLowpass.type = "lowpass";
  state.audioLowpass.frequency.value = 6500;
  state.audioGain.gain.value = Number($("#audio-volume").value);
  updateAudioFilterChain();
  const mobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
  if (mobile && state.audioContext.createMediaStreamDestination) {
    try {
      state.audioDestination = state.audioContext.createMediaStreamDestination();
      state.audioLowpass.connect(state.audioDestination);
      state.audioElement = new Audio();
      state.audioElement.autoplay = true;
      state.audioElement.playsInline = true;
      state.audioElement.srcObject = state.audioDestination.stream;
      await state.audioElement.play();
    } catch (_) {
      state.audioLowpass.disconnect();
      state.audioLowpass.connect(state.audioContext.destination);
      state.audioElement = null;
      state.audioDestination = null;
    }
  } else {
    state.audioLowpass.connect(state.audioContext.destination);
  }
  await state.audioContext.resume();
  if (state.audioContext.state !== "running") throw new Error("Audio wurde vom Browser blockiert. Bitte erneut tippen.");
}

function updateAudioFilterChain() {
  if (!state.audioGain || !state.audioHighpass || !state.audioLowpass) return;
  state.audioGain.disconnect();
  state.audioHighpass.disconnect();
  if ($("#audio-noise-filter").checked) {
    state.audioGain.connect(state.audioHighpass);
    state.audioHighpass.connect(state.audioLowpass);
  } else {
    state.audioGain.connect(state.audioLowpass);
  }
}

async function startAudio() {
  const deviceId = $("#audio-device").value;
  if (!deviceId) return;
  stopAudio();
  await initializeAudioOutput();
  state.audioPackets = 0;
  state.nextAudioTime = state.audioContext.currentTime + 0.1;
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  state.audioSocket = new WebSocket(`${scheme}://${location.host}/ws/audio/${encodeURIComponent(deviceId)}?token=${encodeURIComponent(state.token)}`);
  state.audioSocket.binaryType = "arraybuffer";
  state.audioSocket.onopen = () => { $("#audio-status").textContent = "Verbunden – Audiopuffer wird gefüllt"; $("#audio-toggle").textContent = "Wiedergabe stoppen"; };
  state.audioSocket.onmessage = (message) => {
    if (typeof message.data === "string" || !state.audioContext) return;
    const data = new DataView(message.data);
    const sampleCount = Math.floor(data.byteLength / 2);
    const buffer = state.audioContext.createBuffer(1, sampleCount, 16000);
    const channel = buffer.getChannelData(0);
    for (let index = 0; index < sampleCount; index++) {
      channel[index] = data.getInt16(index * 2, true) / 32768;
    }
    const source = state.audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(state.audioGain);
    state.nextAudioTime = Math.max(state.nextAudioTime, state.audioContext.currentTime + 0.05);
    source.start(state.nextAudioTime);
    state.nextAudioTime += buffer.duration;
    state.audioPackets += 1;
    $("#audio-status").textContent = `Live-Wiedergabe aktiv · ${state.audioPackets} Audiopakete`;
  };
  state.audioSocket.onerror = () => { $("#audio-status").textContent = "Fehler bei der Audioverbindung"; };
  state.audioSocket.onclose = () => { if (state.audioContext) stopAudio("Verbindung beendet"); };
}

function stopAudio(message = "Wiedergabe gestoppt") {
  const socket = state.audioSocket;
  state.audioSocket = null;
  if (socket) socket.onclose = null;
  socket?.close();
  if (state.audioElement) {
    state.audioElement.pause();
    state.audioElement.srcObject = null;
  }
  state.audioContext?.close();
  state.audioContext = null;
  state.audioGain = null;
  state.audioHighpass = null;
  state.audioLowpass = null;
  state.audioElement = null;
  state.audioDestination = null;
  state.audioPackets = 0;
  state.nextAudioTime = 0;
  if ($("#audio-status")) $("#audio-status").textContent = message;
  if ($("#audio-toggle")) $("#audio-toggle").textContent = "Wiedergabe starten";
}

async function playAudioTestTone() {
  if (!state.audioContext) await initializeAudioOutput();
  const oscillator = state.audioContext.createOscillator();
  const gain = state.audioContext.createGain();
  oscillator.frequency.value = 440;
  gain.gain.setValueAtTime(0.12, state.audioContext.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, state.audioContext.currentTime + 0.6);
  oscillator.connect(gain);
  gain.connect(state.audioGain);
  oscillator.start();
  oscillator.stop(state.audioContext.currentTime + 0.6);
  $("#audio-status").textContent = "Testton wird abgespielt";
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
  const query = rangeQuery();
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

async function loadAccount() {
  const account = await api("/api/account");
  $("#account-tenant").textContent = account.tenant_name;
  $("#account-role").textContent = account.role;
  $("#account-plan").textContent = account.plan;
  $("#account-subscription").textContent = account.subscription_status;
  $("#account-devices").textContent = account.device_count;
  $("#account-device-limit").textContent = `von ${account.max_devices}`;
  $("#account-events").textContent = account.event_count.toLocaleString("de-DE");
  $("#account-retention").textContent = account.retention_days;
}

async function loadTenants() {
  const tenants = await api("/api/platform/tenants");
  $("#tenant-list").innerHTML = tenants.map((tenant) => `<div class="rule"><div><strong>${escapeHtml(tenant.name)}</strong><p>${escapeHtml(tenant.slug)} · ${escapeHtml(tenant.subscription?.plan || "kein Tarif")} · ${escapeHtml(tenant.subscription?.status || "inaktiv")} · ${tenant.subscription?.max_devices || 0} Mikrofone · ${tenant.subscription?.retention_days || 0} Tage</p></div></div>`).join("") || "<p>Noch keine Kundenbereiche.</p>";
}

async function loadWebsiteAnalytics() {
  const data = await api("/api/platform/website-visits?days=30");
  $("#website-analytics-summary").innerHTML = `<article><span>Seitenaufrufe</span><strong>${data.views}</strong><small>30 Tage</small></article><article><span>Unterschiedliche Besucher</span><strong>${data.visitors}</strong><small>täglich pseudonymisiert</small></article>`;
  $("#website-analytics-list").innerHTML = data.recent.length ? data.recent.map((item) => `<div class="reference-result"><strong>${escapeHtml(item.masked_ip)}</strong><span>${item.views} Aufruf${item.views === 1 ? "" : "e"}</span><span>Erster Zugriff ${formatTime(item.first_seen_at)}</span><span>Zuletzt ${formatTime(item.last_seen_at)}</span></div>`).join("") : "<p>Noch keine öffentlichen Zugriffe erfasst.</p>";
}

function mediaMime(file, kind) {
  if (file.type) return file.type;
  const suffix = file.name.toLowerCase().split(".").pop();
  const types = kind === "video" ? { mp4: "video/mp4", mov: "video/quicktime", webm: "video/webm" } : { jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png" };
  return types[suffix] || "application/octet-stream";
}

function renderRanked(target, values, translate = false) {
  const entries = Object.entries(values || {});
  const maximum = Math.max(1, ...entries.map(([, count]) => count));
  $(target).innerHTML = entries.length ? entries.map(([name, count]) => `<div class="category"><span>${escapeHtml(translate ? (categoryNames[name] || name) : name)}</span><b>${count}</b><div class="category-track"><div class="category-fill" style="width:${count / maximum * 100}%"></div></div></div>`).join("") : "<p>Keine Daten im Zeitraum.</p>";
}

function syncKpiDatesFromGlobal() {
  const range = selectedRange();
  $("#kpi-date-from").value = range.from;
  $("#kpi-date-to").value = range.to;
  state.kpiInitialized = true;
}

function initializeKpiFilters() {
  if (!$("#kpi-hour-from").options.length) {
    $("#kpi-hour-from").innerHTML = Array.from({ length: 24 }, (_, hour) => `<option value="${hour}">${String(hour).padStart(2, "0")}:00</option>`).join("");
    $("#kpi-hour-to").innerHTML = Array.from({ length: 24 }, (_, hour) => `<option value="${hour}">${hour === 0 ? "24:00" : `${String(hour).padStart(2, "0")}:00`}</option>`).join("");
  }
  if (!state.kpiInitialized) syncKpiDatesFromGlobal();
}

function kpiQuery() {
  initializeKpiFilters();
  const from = $("#kpi-date-from").value;
  const to = $("#kpi-date-to").value || from;
  const ordered = from <= to ? [from, to] : [to, from];
  const dayCount = Math.floor((new Date(`${ordered[1]}T12:00:00`) - new Date(`${ordered[0]}T12:00:00`)) / 86400000) + 1;
  const query = new URLSearchParams({
    days: String(Math.min(366, dayCount)), date_from: ordered[0], date_to: ordered[1],
    start_hour: $("#kpi-hour-from").value, end_hour: $("#kpi-hour-to").value,
  });
  if (device()) query.set("device", device());
  if ($("#kpi-category").value) query.set("category", $("#kpi-category").value);
  return query;
}

function renderKpiChart(target, data, series, mode = "line", suffix = "") {
  const element = $(target);
  if (!data.length) { element.innerHTML = "<p>Keine Daten für diese Auswahl.</p>"; return; }
  const width = 840, height = 250, left = 48, right = 16, top = 18, bottom = 34;
  const plotWidth = width - left - right, plotHeight = height - top - bottom;
  const values = data.flatMap((item) => series.map((entry) => Number(item[entry.key] ?? 0)));
  const maximum = Math.max(1, ...values);
  const x = (index) => left + (data.length === 1 ? plotWidth / 2 : index / (data.length - 1) * plotWidth);
  const y = (value) => top + plotHeight - Number(value || 0) / maximum * plotHeight;
  const labelIndexes = new Set(Array.from({ length: Math.min(6, data.length) }, (_, index) => Math.round(index * (data.length - 1) / Math.max(1, Math.min(6, data.length) - 1))));
  const grid = [0, .25, .5, .75, 1].map((ratio) => `<line class="chart-grid" x1="${left}" y1="${top + ratio * plotHeight}" x2="${left + plotWidth}" y2="${top + ratio * plotHeight}"/><text class="chart-axis" x="2" y="${top + ratio * plotHeight + 4}">${(maximum * (1 - ratio)).toFixed(maximum < 10 ? 1 : 0)}</text>`).join("");
  let graphics = "";
  if (mode === "bar") {
    const groupWidth = Math.max(1.5, Math.min(24, plotWidth / data.length * .72));
    const barWidth = groupWidth / series.length;
    graphics = data.map((item, index) => series.map((entry, seriesIndex) => {
      const value = Number(item[entry.key] || 0); const barHeight = Math.max(value ? 2 : 0, plotHeight - (y(value) - top));
      return `<rect x="${x(index) - groupWidth / 2 + seriesIndex * barWidth}" y="${top + plotHeight - barHeight}" width="${Math.max(1, barWidth - 1)}" height="${barHeight}" rx="2" fill="${entry.color}"><title>${escapeHtml(item.tooltip || item.label)}: ${entry.name} ${value}${suffix}</title></rect>`;
    }).join("")).join("");
  } else {
    graphics = series.map((entry) => {
      const points = data.map((item, index) => `${x(index).toFixed(1)},${y(item[entry.key]).toFixed(1)}`).join(" ");
      return `<polyline class="kpi-line" style="stroke:${entry.color}" points="${points}"/>${data.map((item, index) => `<circle cx="${x(index)}" cy="${y(item[entry.key])}" r="2.5" fill="${entry.color}"><title>${escapeHtml(item.tooltip || item.label)}: ${entry.name} ${item[entry.key]}${suffix}</title></circle>`).join("")}`;
    }).join("");
  }
  const labels = data.map((item, index) => labelIndexes.has(index) ? `<text class="chart-axis" text-anchor="${index === 0 ? "start" : index === data.length - 1 ? "end" : "middle"}" x="${x(index)}" y="${height - 8}">${escapeHtml(item.label)}</text>` : "").join("");
  const legend = series.map((entry, index) => `<g transform="translate(${left + index * 170},4)"><circle cx="4" cy="4" r="4" fill="${entry.color}"/><text class="chart-axis" x="13" y="8">${escapeHtml(entry.name)}</text></g>`).join("");
  element.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img">${grid}${graphics}${labels}${legend}</svg>`;
}

function updateKpiCategories(items) {
  const select = $("#kpi-category"); const selected = select.value;
  select.innerHTML = `<option value="">Alle Kategorien</option>${items.map((item) => `<option value="${escapeHtml(item.code)}">${escapeHtml(categoryNames[item.code] || item.code)} (${item.count})</option>`).join("")}`;
  if ([...select.options].some((option) => option.value === selected)) select.value = selected;
}

async function loadKpis() {
  initializeKpiFilters();
  const data = await api(`/api/kpis?${kpiQuery()}`);
  updateKpiCategories(data.available_categories);
  $("#k-total").textContent = data.total.toLocaleString("de-DE");
  $("#k-exceeded").textContent = data.exceeded.toLocaleString("de-DE");
  $("#k-exceeded-rate").textContent = `${Math.round(data.exceeded_rate * 100)} % der Ereignisse`;
  $("#k-average").textContent = `${data.average_db.toFixed(1)} dB`;
  $("#k-maximum").textContent = `${data.maximum_db.toFixed(1)} dB`;
  $("#k-p95").textContent = `${data.p95_db.toFixed(1)} dB`;
  $("#k-duration").textContent = data.total_duration_seconds >= 3600 ? `${(data.total_duration_seconds / 3600).toFixed(1)} h` : `${Math.round(data.total_duration_seconds / 60)} min`;
  $("#kpi-selection-label").textContent = `${new Date(`${data.filters.date_from}T12:00:00`).toLocaleDateString("de-DE")} – ${new Date(`${data.filters.date_to}T12:00:00`).toLocaleDateString("de-DE")} · ${String(data.filters.start_hour).padStart(2, "0")}:00–${data.filters.end_hour === 0 ? "24:00" : `${String(data.filters.end_hour).padStart(2, "0")}:00`}`;
  renderRanked("#kpi-labels", data.labels);
  renderRanked("#kpi-categories", data.categories, true);
  renderRanked("#kpi-devices", data.devices);
  $("#kpi-top-hour").textContent = data.top_hour == null ? "keine Daten" : `Spitze ${String(data.top_hour).padStart(2, "0")}:00 · ${data.top_hour_events}`;
  const hours = data.hours.map((item) => ({ ...item, label: String(item.hour).padStart(2, "0"), tooltip: `${String(item.hour).padStart(2, "0")}:00 Uhr` }));
  const timeline = data.hourly_timeline.map((item) => ({ ...item, label: new Date(item.timestamp).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit" }), tooltip: new Date(item.timestamp).toLocaleString("de-DE") }));
  renderKpiChart("#kpi-level-timeline", timeline, [{ key: "average_db", name: "Ø dB(A)", color: "#70e0ae" }], "line", " dB");
  renderKpiChart("#kpi-hours", hours, [{ key: "count", name: "Ereignisse", color: "#72a7ff" }], "bar");
  renderKpiChart("#kpi-event-timeline", timeline, [{ key: "count", name: "Ereignisse", color: "#72a7ff" }, { key: "exceeded", name: "Überschreitungen", color: "#ee6c67" }], "bar");
  renderKpiChart("#kpi-hour-share", hours.map((item) => ({ ...item, share_percent: Math.round(item.share * 1000) / 10 })), [{ key: "share_percent", name: "Anteil", color: "#f6bd60" }], "bar", " %");
  const dailyMax = Math.max(1, ...data.daily.map((item) => item.total));
  $("#kpi-daily").innerHTML = data.daily.length ? `<div class="daily-bars">${data.daily.map((item) => `<div title="${new Date(`${item.date}T12:00:00`).toLocaleDateString("de-DE")}: ${item.total} Ereignisse, ${item.exceeded} Überschreitungen, Ø ${item.average_db} dB"><span style="height:${Math.max(2, item.total / dailyMax * 100)}%"><i style="height:${item.total ? item.exceeded / item.total * 100 : 0}%"></i></span><small>${item.date.slice(5)}</small></div>`).join("")}</div>` : "<p>Keine Daten im Zeitraum.</p>";
}

async function downloadKpiExport(format) {
  const response = await fetch(`/api/kpis/export?format=${format}&${kpiQuery()}`, { headers: { Authorization: `Bearer ${state.token}` } });
  if (!response.ok) throw new Error(`Export fehlgeschlagen (HTTP ${response.status})`);
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const filename = disposition.match(/filename="([^"]+)"/)?.[1] || `eventmonitor-kpis.${format}`;
  const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

function renderTimeline(data) {
  const countByDate = new Map(data.map((item) => [item.date, item.total]));
  const entries = [];
  const range = selectedRange();
  const today = new Date(`${range.to}T12:00:00`);
  const dayCount = range.days;
  for (let offset = dayCount - 1; offset >= 0; offset--) {
    const date = new Date(today);
    date.setHours(12, 0, 0, 0);
    date.setDate(today.getDate() - offset);
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
    entries.push({ date, key, total: countByDate.get(key) || 0 });
  }
  const width = 800, height = 145, left = 38, right = 12, top = 10, bottom = 25;
  const plotWidth = width - left - right, plotHeight = height - top - bottom;
  const maximum = Math.max(1, ...entries.map((item) => item.total));
  const points = entries.map((item, index) => ({
    ...item,
    x: left + (entries.length === 1 ? plotWidth / 2 : index / (entries.length - 1) * plotWidth),
    y: top + plotHeight - item.total / maximum * plotHeight,
  }));
  const line = points.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
  const area = `${left},${top + plotHeight} ${line} ${left + plotWidth},${top + plotHeight}`;
  const labelIndexes = new Set([0, Math.floor((entries.length - 1) / 2), entries.length - 1]);
  $("#timeline").innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Ereignisse pro Tag">
    <defs><linearGradient id="timeline-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#70e0ae" stop-opacity=".45"/><stop offset="1" stop-color="#70e0ae" stop-opacity=".02"/></linearGradient></defs>
    ${[0, .5, 1].map((ratio) => `<line class="chart-grid" x1="${left}" y1="${top + ratio * plotHeight}" x2="${left + plotWidth}" y2="${top + ratio * plotHeight}"/><text class="chart-axis" x="0" y="${top + ratio * plotHeight + 4}">${Math.round(maximum * (1 - ratio))}</text>`).join("")}
    <polygon class="timeline-area" points="${area}"/><polyline class="timeline-line" points="${line}"/>
    ${points.map((point, index) => `<circle class="timeline-point" cx="${point.x}" cy="${point.y}" r="3"><title>${point.date.toLocaleDateString("de-DE")}: ${point.total} Ereignisse</title></circle>${labelIndexes.has(index) ? `<text class="chart-axis" text-anchor="${index === 0 ? "start" : index === entries.length - 1 ? "end" : "middle"}" x="${point.x}" y="${height - 5}">${point.date.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}</text>` : ""}`).join("")}
  </svg>`;
}

async function loadLiveLevels() {
  const minutes = Number($("#level-minutes").value);
  const query = device() ? `?minutes=${minutes}&device=${encodeURIComponent(device())}` : `?minutes=${minutes}`;
  const points = await api(`/api/device-levels${query}`);
  renderLiveLevels(points, minutes);
}

function renderLiveLevels(points, minutes) {
  const width = 900, height = 260, left = 42, right = 12, top = 12, bottom = 28;
  const plotWidth = width - left - right, plotHeight = height - top - bottom;
  const end = Date.now(), start = end - minutes * 60 * 1000;
  const maximum = Math.max(80, ...points.map((point) => point.maximum_db));
  const minimum = Math.min(30, ...points.map((point) => point.average_db));
  const range = Math.max(20, maximum - minimum);
  const colors = ["#70e0ae", "#f6bd60", "#72a7ff", "#ee6c67"];
  const groups = new Map();
  points.forEach((point) => {
    if (!groups.has(point.device_id)) groups.set(point.device_id, { name: point.name, points: [] });
    groups.get(point.device_id).points.push(point);
  });
  const x = (timestamp) => left + Math.max(0, Math.min(1, (new Date(timestamp).valueOf() - start) / (end - start))) * plotWidth;
  const y = (level) => top + plotHeight - (level - minimum) / range * plotHeight;
  const lines = Array.from(groups.values()).map((group, index) => `<polyline class="level-line" stroke="${colors[index % colors.length]}" points="${group.points.map((point) => `${x(point.timestamp).toFixed(1)},${y(point.average_db).toFixed(1)}`).join(" ")}"/>`).join("");
  $("#level-chart").innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Lautstärkepegel der letzten ${minutes} Minuten">
    ${[0, .25, .5, .75, 1].map((ratio) => `<line class="chart-grid" x1="${left}" y1="${top + ratio * plotHeight}" x2="${left + plotWidth}" y2="${top + ratio * plotHeight}"/><text class="chart-axis" x="0" y="${top + ratio * plotHeight + 4}">${Math.round(maximum - ratio * range)} dB</text>`).join("")}
    ${[0, .5, 1].map((ratio) => `<text class="chart-axis" text-anchor="${ratio === 0 ? "start" : ratio === 1 ? "end" : "middle"}" x="${left + ratio * plotWidth}" y="${height - 5}">${new Date(start + ratio * (end - start)).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}</text>`).join("")}
    ${lines}
  </svg>`;
  $("#level-legend").innerHTML = Array.from(groups.values()).map((group, index) => `<span><i style="background:${colors[index % colors.length]}"></i>${escapeHtml(group.name)}</span>`).join("") || "Messwerte werden gesammelt …";
  $("#level-chart-title").textContent = `Lautstärkepegel – letzte ${minutes} Minuten`;
  $("#level-chart-status").textContent = `${points.length} Fünf-Sekunden-Werte · aktualisiert ${new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`;
}

function renderCategories(categories, total) {
  const entries = Object.entries(categories).sort((a, b) => b[1] - a[1]);
  $("#categories").innerHTML = entries.length ? entries.map(([name, count]) =>
    `<div class="category"><span>${escapeHtml(categoryNames[name] || name)}</span><strong>${count}</strong><div class="category-track"><div class="category-fill" style="width:${count / total * 100}%"></div></div></div>`
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
  const entries = new Map(data.map((item) => [item.date, item]));
  const range = selectedRange();
  const cards = [];
  const cursor = new Date(`${range.from}T12:00:00`);
  const end = new Date(`${range.to}T12:00:00`);
  while (cursor <= end) {
    const key = localDate(cursor);
    const entry = entries.get(key) || { total: 0, exceeded: 0 };
    cards.push(`<div class="day calendar-summary"><strong>${cursor.toLocaleDateString("de-DE", { weekday: "long", day: "2-digit", month: "long", year: "numeric" })}</strong><span><b>${entry.total}</b> Lärmaktivitäten gemessen</span><span class="calendar-exceeded"><b>${entry.exceeded || 0}</b> oberhalb des zulässigen Beurteilungspegels</span></div>`);
    cursor.setDate(cursor.getDate() + 1);
  }
  $("#calendar").innerHTML = cards.join("");
}

async function loadRecentEvents() {
  const range = eventRangeQuery();
  const entries = await api(`/push/noise-log?limit=5&start=${encodeURIComponent(range.start)}&end=${encodeURIComponent(range.end)}`);
  $("#recent-events").innerHTML = entries.length ? entries.map((entry) => {
    const witnesses = entry.witnesses.length ? entry.witnesses.map((item) => `<span class="witness ${item.response}">${escapeHtml(item.username)}: ${item.response === "confirmed" ? "bestätigt" : "abgelehnt"}</span>`).join("") : "<span class=\"witness pending\">Keine Zeugenreaktion</span>";
    const bases = state.eventClasses.filter((item) => item.active && item.level === "base");
    const primaryOptions = `<option value="" ${entry.primary_class_code ? "" : "selected"}>Kategorie wählen</option>${bases.map((item) => `<option value="${escapeHtml(item.code)}" ${entry.primary_class_code === item.code ? "selected" : ""}>${escapeHtml(item.name)}</option>`).join("")}`;
    const play = state.role === "viewer" ? `<span class="clip-unavailable">Keine Audioberechtigung</span>` : entry.audio_available ? `<button type="button" class="ghost" data-play-event="${entry.event_id}">▶ Anhören</button>` : `<span class="clip-unavailable">Ohne Aufnahme · nicht akustisch prüfbar</span>`;
    const resolved = ["manual", "learned", "context_only"].includes(entry.classification_status);
    const correction = state.role === "viewer" || !entry.audio_available ? play : `<form class="classification-editor ${resolved ? "confirmed" : ""}" data-event-id="${entry.event_id}">${play}<select name="primary_class_code">${primaryOptions}</select><select name="subclass_code" data-current="${escapeHtml(entry.subclass_code || "")}"></select>${secondaryClassEditor(entry)}<button type="submit">${resolved ? "Korrigieren" : "Übernehmen"}</button></form>`;
    const statusText = entry.classification_status === "manual" ? `bestätigt durch ${entry.corrected_by}` : entry.classification_status === "learned" ? "automatisch gelernt" : entry.classification_status === "context_only" ? "nur Metadaten-/Kontextwertung · kein akustischer Nachweis" : "automatisch";
    return `<div class="recent-event ${resolved ? "confirmed" : ""} ${state.listenedEvents.has(String(entry.event_id)) ? "listened" : ""}"><time>Start ${formatTime(entry.timestamp)}<br>Ende ${formatTime(entry.end_timestamp || entry.timestamp)}<br>${formatDuration(entry.duration_seconds)}</time><strong>${escapeHtml(entry.label)}</strong><span>${escapeHtml(entry.device)} · ${entry.db_level.toFixed(1)} dB<br>${escapeHtml(statusText)}</span><div>${witnesses}${correction}</div></div>`;
  }).join("") : "<p>Noch keine Ereignisse erfasst.</p>";
  document.querySelectorAll(".classification-editor").forEach((form) => populateSubclassOptions(form));
}

function populateSubclassOptions(form) {
  const primaryCode = form.elements.primary_class_code.value;
  const current = form.elements.subclass_code.dataset.current;
  const fine = state.eventClasses.filter((item) => item.active && item.level === "fine" && (item.parent_code == null || item.parent_code === primaryCode));
  form.elements.subclass_code.innerHTML = `<option value="">Keine Feinzuordnung</option>${fine.map((item) => `<option value="${escapeHtml(item.code)}" ${current === item.code ? "selected" : ""}>${escapeHtml(item.name)}</option>`).join("")}`;
  if (!current && fine.length === 1) form.elements.subclass_code.value = fine[0].code;
}

function secondaryClassEditor(event) {
  const selected = new Set(event.secondary_class_codes || []);
  const approved = new Set(event.secondary_learning_approved_codes || []);
  const fine = state.eventClasses.filter((item) => item.active && item.level === "fine");
  return `<details class="secondary-editor"><summary>Nebenquellen${selected.size ? ` (${selected.size})` : ""}</summary><div class="secondary-options">${fine.map((item) => `<label><input type="checkbox" name="secondary_class_codes" value="${escapeHtml(item.code)}" ${selected.has(item.code) ? "checked" : ""}> ${escapeHtml(item.name)} <span><input type="checkbox" name="secondary_learning_approved_codes" value="${escapeHtml(item.code)}" ${approved.has(item.code) ? "checked" : ""} ${selected.has(item.code) ? "" : "disabled"}> lernen</span></label>`).join("")}</div><label><input type="checkbox" name="primary_learning_approved" ${event.primary_learning_approved !== false ? "checked" : ""}> Hauptklasse lernen</label><small>Gemischte Clips werden nur für ausdrücklich freigegebene Klassen gelernt.</small></details>`;
}

function reviewSubclassOptions() {
  const primary = $("#review-primary").value;
  const fine = state.eventClasses.filter((item) => item.active && item.level === "fine" && (item.parent_code == null || item.parent_code === primary));
  $("#review-subclass").innerHTML = `<option value="">Keine Feinzuordnung</option>${fine.map((item) => `<option value="${escapeHtml(item.code)}">${escapeHtml(item.name)}</option>`).join("")}`;
  if (fine.length === 1) $("#review-subclass").value = fine[0].code;
}

async function loadReview() {
  const range = eventRangeQuery();
  const [summary, runs] = await Promise.all([api(`/events/review/summary?start=${encodeURIComponent(range.start)}&end=${encodeURIComponent(range.end)}`), api("/events/review/runs"), loadPeople()]);
  $("#r-open-unknown").textContent = summary.open_unknown;
  $("#r-open-recognized").textContent = summary.open_recognized;
  $("#r-done-unknown").textContent = summary.completed_unknown;
  $("#r-done-recognized").textContent = summary.completed_recognized;
  $("#r-context-only").textContent = summary.excluded_context_only;
  const classes = [{ code: "UNKNOWN", name: "Unbekannt" }, ...state.eventClasses.filter((item) => item.active)];
  $("#review-classes").innerHTML = classes.map((item) => {
    const counts = summary.by_class[item.code] || { open: 0, completed: 0 };
    return `<button type="button" class="class-tile ${state.reviewClass === item.code ? "active" : ""}" data-review-class="${escapeHtml(item.code)}"><strong>${escapeHtml(item.name)}</strong><small>${counts.open} offen · ${counts.completed} erledigt</small></button>`;
  }).join("");
  const bases = state.eventClasses.filter((item) => item.active && item.level === "base");
  $("#review-primary").innerHTML = bases.map((item) => `<option value="${escapeHtml(item.code)}">${escapeHtml(item.name)}</option>`).join("");
  $("#review-secondary").innerHTML = state.eventClasses.filter((item) => item.active && item.level === "fine").map((item) => `<option value="${escapeHtml(item.code)}">${escapeHtml(item.name)}</option>`).join("");
  reviewSubclassOptions();
  $("#review-runs").innerHTML = runs.length ? runs.map((run) => {
    const progress = run.total ? Math.round(run.processed / run.total * 100) : 0;
    const action = run.status === "running" || run.status === "pending" ? `<button data-run-pause="${run.id}">Unterbrechen</button>` : run.status === "paused" ? `<button data-run-resume="${run.id}">Fortsetzen</button>` : "";
    const timing = run.finished_at ? `Beendet: ${formatTime(run.finished_at)}` : run.started_at ? `Gestartet: ${formatTime(run.started_at)}` : `Angelegt: ${formatTime(run.created_at)}`;
    return `<div class="review-run"><div><strong>${escapeHtml(run.kind)}</strong><br><small>${escapeHtml(run.status)} · ${run.changed} verbessert<br>${timing}</small></div><div><span>${run.processed} / ${run.total}</span><div class="review-progress"><i style="width:${progress}%"></i></div></div>${action}</div>`;
  }).join("") : "<p>Noch kein Prüflauf vorhanden.</p>";
  await loadReviewQueue();
}

async function loadReviewQueue() {
  const query = new URLSearchParams({ status: $("#review-status").value, limit: "500" });
  const range = eventRangeQuery(); query.set("start", range.start); query.set("end", range.end);
  if (state.reviewClass) query.set("class_code", state.reviewClass);
  state.reviewEvents = await api(`/events/review/queue?${query}`);
  const personOptions = `<option value="">Keine Person</option>${state.people.filter((person) => person.active).map((person) => `<option value="${person.id}">${escapeHtml(person.name)}</option>`).join("")}`;
  $("#review-events").innerHTML = state.reviewEvents.length ? state.reviewEvents.map((event) => `<label class="review-event"><input type="checkbox" value="${event.id}"><button type="button" class="ghost" data-play-event="${event.id}">${"▶ Anhören"}</button><strong>${escapeHtml(event.label_de || event.label)}</strong><span>${escapeHtml(event.device)} · ${event.db_level.toFixed(1)} dB<br>Start ${formatTime(event.timestamp)}<br>Ende ${formatTime(event.end_timestamp || event.timestamp)} · ${formatDuration(event.duration_seconds)}</span><span>${escapeHtml(event.subclass_code || event.primary_class_code || "Unbekannt")} · ${Math.round(event.confidence * 100)} %${event.secondary_class_codes?.length ? `<small>Nebenquellen: ${event.secondary_class_codes.map((code) => escapeHtml(state.eventClasses.find((item) => item.code === code)?.name || code)).join(", ")}</small>` : ""}<select data-person-event="${event.id}">${personOptions.replace(`value="${event.person_id || ""}"`, `value="${event.person_id || ""}" selected`)}</select>${event.assessment_excluded ? '<small class="person-monitoring-status excluded">Aus Lärmbewertung ausgeschlossen</small>' : ""}</span></label>`).join("") : "<p>Keine passenden Ereignisse.</p>";
  updateReviewSelection();
}

async function loadPeople() {
  state.personMediaUrls.forEach((url) => URL.revokeObjectURL(url));
  state.personMediaUrls = [];
  state.people = await api("/api/people");
  $("#people-list").innerHTML = state.people.length ? state.people.map((person) => `<article class="person-card" data-person-id="${person.id}"><div class="person-photo">${person.photo_available ? `<img data-person-photo="${person.id}" alt="Profilbild von ${escapeHtml(person.name)}">` : `<span>Kein Bild</span>`}</div><div class="person-summary"><span>${person.frequency} bestätigte Ereignisse · ${person.total_duration_seconds.toFixed(1)} s</span><small>${Object.entries(person.categories).map(([category, count]) => `${categoryNames[category] || category}: ${count}`).join(" · ") || "Noch keine Zuordnung"}</small><small>${person.video_voice_similarity == null ? "Noch kein Videostimmen-Vergleich" : `Videostimme ↔ ${escapeHtml(person.video_voice_cluster_name || "Stimmgruppe")}: ${Math.round(person.video_voice_similarity * 100)} % Ähnlichkeit`}</small></div><form class="person-editor"><label>Name<input name="name" value="${escapeHtml(person.name)}" maxlength="100" required></label><label class="active-toggle"><input name="active" type="checkbox" ${person.active ? "checked" : ""}> Profil aktiv</label><label class="active-toggle"><input name="monitoring_enabled" type="checkbox" ${person.monitoring_enabled ? "checked" : ""}> In Lärmüberwachung einbeziehen</label><button type="submit">Profil speichern</button></form><form class="person-photo-upload"><label>Profilbild aktualisieren<input name="photo" type="file" accept="image/jpeg,image/png" required></label><button type="submit">Bild speichern</button></form><form class="person-video-upload"><label>Kurzes Prüfvideo<input name="video" type="file" accept="video/mp4,video/quicktime,video/webm" required></label><button type="submit">Video importieren</button></form>${person.video_available ? `<button type="button" class="ghost" data-open-person-video="${person.id}">Video und Stimmprobe prüfen</button>` : ""}<div class="person-video-review hidden"><video controls playsinline preload="metadata"></video><audio controls preload="none" class="hidden"></audio><div><button type="button" data-capture-person-photo="${person.id}">Aktuellen Videoframe als Bild übernehmen</button></div></div><span class="person-media-status"></span></article>`).join("") : "<p>Noch keine Personenprofile angelegt oder erkannt.</p>";
  await Promise.all(state.people.filter((person) => person.photo_available).map(async (person) => {
    const image = document.querySelector(`[data-person-photo="${person.id}"]`);
    if (image) image.src = await authorizedMediaUrl(`/api/people/${person.id}/media/photo`).catch(() => "");
  }));
}

async function authorizedMediaUrl(path) {
  const response = await fetch(path, { headers: { Authorization: `Bearer ${state.token}` } });
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `HTTP ${response.status}`);
  const url = URL.createObjectURL(await response.blob());
  state.personMediaUrls.push(url);
  return url;
}

async function loadSpeakerClusters() {
  state.speakerClusters = await api("/api/speaker-clusters");
  const people = `<option value="">Noch keiner bekannten Person zugeordnet</option>${state.people.filter((item) => item.active).map((item) => `<option value="${item.id}">${escapeHtml(item.name)}</option>`).join("")}`;
  $("#speaker-clusters").innerHTML = state.speakerClusters.length ? state.speakerClusters.map((cluster) => `<form class="speaker-cluster" data-cluster-id="${cluster.id}"><div><strong>${escapeHtml(cluster.name)}</strong><small>${cluster.sample_count} Aufnahmen · Ø ${Math.round(cluster.average_similarity * 100)} % Ähnlichkeit<br>${cluster.pending_count} ungeprüft · ${cluster.confirmed_count} bestätigt · ${cluster.rejected_count} ausgeschlossen<br>${cluster.first_seen ? `${formatTime(cluster.first_seen)} bis ${formatTime(cluster.last_seen)}` : "Keine Aufnahme"}</small></div><label>Bezeichnung<input name="name" value="${escapeHtml(cluster.name)}" maxlength="100" required></label><label>Bekannte Person<select name="person_id">${people.replace(`value="${cluster.person_id || ""}"`, `value="${cluster.person_id || ""}" selected`)}</select></label><div class="speaker-cluster-actions"><button type="button" data-review-speaker="${cluster.id}">Aufnahmen prüfen</button><button type="submit">Speichern</button></div></form>`).join("") : "<p>Noch keine automatische Stimmgruppierung ausgeführt.</p>";
  if (state.speakerClusterId && !state.speakerClusters.some((item) => item.id === state.speakerClusterId)) closeSpeakerReview();
}

async function loadAdminNotifications() {
  const items = await api("/api/admin-notifications");
  const unread = items.filter((item) => !item.read_at).length;
  $("#notification-count").textContent = unread;
  $("#notification-list").innerHTML = items.length ? items.map((item) => `<article class="admin-notification ${item.read_at ? "" : "unread"}" data-notification-id="${item.id}"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.message)}</span><small>${formatTime(item.created_at)}</small></article>`).join("") : "<p>Keine neuen Benachrichtigungen.</p>";
}

let speakerProgressTimer = null;
async function loadSpeakerAnalysisProgress() {
  const run = await api("/api/speaker-analysis/runs/latest");
  const panel = $("#speaker-analysis-progress");
  if (!run) { panel.classList.add("hidden"); return; }
  panel.classList.remove("hidden");
  const active = run.status === "pending" || run.status === "running";
  const percent = run.total ? Math.round(run.processed / run.total * 100) : 0;
  $("#speaker-progress-title").textContent = { pending: "Analyse wartet", running: "Analyse läuft", completed: "Analyse abgeschlossen", failed: "Analyse fehlgeschlagen" }[run.status] || run.status;
  $("#speaker-progress-value").textContent = run.total ? `${run.processed} / ${run.total} (${percent} %)` : "Modell wird vorbereitet";
  $("#speaker-progress-bar").style.width = `${percent}%`;
  $("#speaker-progress-detail").textContent = `${run.message} · ${run.clustered} Gruppen · ${run.skipped} übersprungen`;
  $("#speaker-analyze").disabled = active;
  $("#speaker-analyze").textContent = active ? "Stimmanalyse läuft …" : "Separate Stimmanalyse starten";
  clearTimeout(speakerProgressTimer);
  if (active) speakerProgressTimer = setTimeout(() => loadSpeakerAnalysisProgress().catch((error) => { $("#speaker-status").textContent = error.message; }), 2000);
  if (run.status === "completed") await loadSpeakerClusters();
}

function speakerStatusName(status) {
  return { pending: "Ungeprüft", confirmed: "Bestätigt", rejected: "Nicht passend", no_voice: "Keine Stimme" }[status] || status;
}

function closeSpeakerReview() {
  state.speakerClusterId = null;
  state.speakerSampleOffset = 0;
  $("#speaker-review").classList.add("hidden");
  $("#speaker-samples").innerHTML = "";
}

async function loadSpeakerSamples(append = false) {
  if (!state.speakerClusterId) return;
  if (!append) state.speakerSampleOffset = 0;
  const query = new URLSearchParams({ review_status: $("#speaker-review-filter").value, limit: "50", offset: String(state.speakerSampleOffset) });
  const result = await api(`/api/speaker-clusters/${state.speakerClusterId}/samples?${query}`);
  state.speakerSampleTotal = result.total;
  const targetOptions = state.speakerClusters.filter((item) => item.id !== state.speakerClusterId).map((item) => `<option value="${item.id}">${escapeHtml(item.name)}</option>`).join("");
  const rows = result.items.map((sample) => `<article class="speaker-sample ${sample.review_status}" data-speaker-event="${sample.event_id}"><div><strong>${escapeHtml(sample.label)}</strong><small>${formatTime(sample.timestamp)} · ${escapeHtml(sample.device)} · ${sample.db_level.toFixed(1)} dB · ${Math.round(sample.similarity * 100)} % ähnlich</small><span>${speakerStatusName(sample.review_status)}${sample.reviewed_by ? ` · ${escapeHtml(sample.reviewed_by)}` : ""}</span></div><button type="button" class="ghost" data-play-event="${sample.event_id}" ${sample.audio_available ? "" : "disabled"}>${sample.audio_available ? "▶ Anhören" : "Kein Clip"}</button><div class="speaker-sample-actions"><button type="button" data-speaker-action="confirm">Bestätigen</button><button type="button" class="ghost" data-speaker-action="reject">Nicht passend</button><button type="button" class="ghost" data-speaker-action="no_voice">Keine Stimme</button><select aria-label="Andere Stimmgruppe">${targetOptions || '<option value="">Keine weitere Gruppe</option>'}</select><button type="button" class="ghost" data-speaker-action="move" ${targetOptions ? "" : "disabled"}>Verschieben</button><button type="button" class="ghost" data-speaker-action="new_cluster">Neue Gruppe</button></div></article>`).join("");
  if (append) $("#speaker-samples").insertAdjacentHTML("beforeend", rows); else $("#speaker-samples").innerHTML = rows || "<p>Keine Aufnahmen mit diesem Prüfstatus.</p>";
  state.speakerSampleOffset += result.items.length;
  const cluster = state.speakerClusters.find((item) => item.id === state.speakerClusterId);
  $("#speaker-review-title").textContent = `${cluster?.name || "Stimmgruppe"} prüfen`;
  $("#speaker-review-count").textContent = `${Math.min(state.speakerSampleOffset, result.total)} von ${result.total}`;
  $("#speaker-review-more").classList.toggle("hidden", state.speakerSampleOffset >= result.total);
  $("#speaker-review").classList.remove("hidden");
}

function updateReviewSelection() {
  const count = document.querySelectorAll("#review-events input:checked").length;
  $("#review-selection").textContent = `${count} ausgewählt`;
}

async function loadEvents() {
  const range = eventRangeQuery();
  const query = new URLSearchParams({ limit: "1000", start: range.start, end: range.end });
  if (device()) query.set("device", device());
  const events = await api(`/events?${query}`);
  state.liveEvents = events;
  updateLiveFilterOptions();
  renderEvents();
}

function eventMatchesBaseFilters(event) {
  const resolved = ["manual", "learned", "context_only"].includes(event.classification_status);
  return ($("#show-resolved-events").checked || !resolved)
    && ($("#clip-filter").value !== "clips" || event.audio_available);
}

function updateCategoryFilter() {
  const select = $("#category-filter");
  const selected = select.value !== "all" ? select.value : localStorage.getItem("em_category_filter") || "all";
  const selectedEvent = $("#event-filter").value;
  const counts = new Map();
  const known = new Set();
  for (const event of state.liveEvents) {
    if (selectedEvent !== "all" && eventFilterKey(event) !== selectedEvent) continue;
    const key = event.category || "OTHER";
    known.add(key);
    if (!eventMatchesBaseFilters(event)) continue;
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  if (selected !== "all" && known.has(selected) && !counts.has(selected)) counts.set(selected, 0);
  const options = [...counts.entries()].sort((a, b) => (categoryNames[a[0]] || a[0]).localeCompare(categoryNames[b[0]] || b[0], "de"));
  const openTotal = [...counts.values()].reduce((total, count) => total + count, 0);
  select.innerHTML = `<option value="all">Alle Kategorien (${openTotal})</option>${options.map(([key, count]) => `<option value="${escapeHtml(key)}">${escapeHtml(categoryNames[key] || key)} (${count})</option>`).join("")}`;
  select.value = known.has(selected) ? selected : "all";
  localStorage.setItem("em_category_filter", select.value);
}

function eventFilterKey(event) {
  if (event.subclass_code) return `class:${event.subclass_code}`;
  if (event.primary_class_code) return `class:${event.primary_class_code}`;
  return `label:${String(event.label_de || event.label || "Unbekannt").trim().toLocaleLowerCase("de-DE")}`;
}

function eventFilterName(event) {
  const code = event.subclass_code || event.primary_class_code;
  return state.eventClasses.find((item) => item.code === code)?.name || event.label_de || event.label || "Unbekannt";
}

function updateEventFilter() {
  const select = $("#event-filter");
  const selected = select.value !== "all" ? select.value : localStorage.getItem("em_event_filter") || "all";
  const groups = new Map();
  const known = new Map();
  const selectedCategory = $("#category-filter").value;
  for (const event of state.liveEvents) {
    if (selectedCategory !== "all" && (event.category || "OTHER") !== selectedCategory) continue;
    const key = eventFilterKey(event);
    known.set(key, eventFilterName(event));
    if (!eventMatchesBaseFilters(event)) continue;
    const current = groups.get(key) || { name: eventFilterName(event), count: 0 };
    current.count += 1;
    groups.set(key, current);
  }
  if (selected !== "all" && known.has(selected) && !groups.has(selected)) groups.set(selected, { name: known.get(selected), count: 0 });
  const options = [...groups.entries()].sort((a, b) => a[1].name.localeCompare(b[1].name, "de"));
  const openTotal = [...groups.values()].reduce((total, item) => total + item.count, 0);
  select.innerHTML = `<option value="all">Alle Ereignisse (${openTotal})</option>${options.map(([key, item]) => `<option value="${escapeHtml(key)}">${escapeHtml(item.name)} (${item.count})</option>`).join("")}`;
  select.value = known.has(selected) ? selected : "all";
  localStorage.setItem("em_event_filter", select.value);
}

function updateLiveFilterOptions() {
  updateCategoryFilter();
  updateEventFilter();
  updateCategoryFilter();
}

function eventMatchesLiveFilters(event) {
  const selectedEvent = $("#event-filter").value;
  const selectedCategory = $("#category-filter").value;
  return eventMatchesBaseFilters(event)
    && (selectedCategory === "all" || (event.category || "OTHER") === selectedCategory)
    && (selectedEvent === "all" || eventFilterKey(event) === selectedEvent);
}

function renderEvents() {
  $("#events").innerHTML = "";
  state.liveEvents.filter(eventMatchesLiveFilters).slice().reverse().forEach(addEvent);
}

function addEvent(event) {
  const resolved = ["manual", "learned", "context_only"].includes(event.classification_status);
  if (!eventMatchesLiveFilters(event)) return;
  $("#events").querySelector(`[data-event-id="${event.id}"]`)?.remove();
  const row = document.createElement("div");
  row.className = `event-row ${resolved ? "confirmed" : ""} ${state.listenedEvents.has(String(event.id)) ? "listened" : ""}`;
  row.dataset.eventId = event.id;
  const draft = state.classificationDrafts.get(String(event.id));
  const selectedPrimary = draft?.primary_class_code || event.primary_class_code;
  const selectedSubclass = draft?.subclass_code ?? event.subclass_code;
  const bases = state.eventClasses.filter((item) => item.active && item.level === "base");
  const primaryOptions = `<option value="" ${selectedPrimary ? "" : "selected"}>Kategorie wählen</option>${bases.map((item) => `<option value="${escapeHtml(item.code)}" ${selectedPrimary === item.code ? "selected" : ""}>${escapeHtml(item.name)}</option>`).join("")}`;
  const actions = state.role === "viewer" ? "" : !event.audio_available ? `<span class="clip-unavailable">Ohne Aufnahme · nicht akustisch prüfbar</span>` : `<form class="live-actions" data-event-id="${event.id}">
    <button type="button" class="ghost" data-play-event="${event.id}">▶ Anhören</button>
    <select name="primary_class_code">${primaryOptions}</select>
    <select name="subclass_code" data-current="${escapeHtml(selectedSubclass || "")}"></select>
    ${secondaryClassEditor(event)}
    <button type="submit">${resolved ? "Korrigieren" : "Übernehmen"}</button>
  </form>`;
  row.innerHTML = `<span>Start ${formatTime(event.timestamp)}<br>Ende ${formatTime(event.end_timestamp || event.timestamp)}<br>${formatDuration(event.duration_seconds)}</span><span>${escapeHtml(event.device)}</span><span class="badge">${escapeHtml(event.label_de || event.label)}</span><span>${event.db_level.toFixed(1)} dB</span><span>${Math.round(event.confidence * 100)} %</span>${actions}`;
  const classification = row.querySelector(".live-actions");
  if (classification) populateSubclassOptions(classification);
  $("#events").prepend(row);
  while ($("#events").children.length > 200) $("#events").lastElementChild.remove();
}

function stopEventClip() {
  if (state.clipSource) {
    state.clipSource.onended = null;
    try { state.clipSource.stop(); } catch (_) { /* already stopped */ }
  }
  state.clipContext?.close().catch(() => {});
  if (state.clipAudioElement) {
    state.clipAudioElement.pause();
    state.clipAudioElement.srcObject = null;
  }
  if (state.clipButton) state.clipButton.textContent = "▶ Anhören";
  state.clipSource = null;
  state.clipContext = null;
  state.clipButton = null;
  state.clipAudioElement = null;
  state.clipAudioDestination = null;
}

function decodePcmWav(payload, context) {
  const view = new DataView(payload);
  if (view.byteLength < 44 || view.getUint32(0, false) !== 0x52494646 || view.getUint32(8, false) !== 0x57415645) throw new Error("Ungültige WAV-Datei");
  let offset = 12, format = null, dataOffset = 0, dataSize = 0;
  while (offset + 8 <= view.byteLength) {
    const chunkId = view.getUint32(offset, false);
    const chunkSize = view.getUint32(offset + 4, true);
    const content = offset + 8;
    if (chunkId === 0x666d7420 && content + 16 <= view.byteLength) format = { audioFormat: view.getUint16(content, true), channels: view.getUint16(content + 2, true), sampleRate: view.getUint32(content + 4, true), bits: view.getUint16(content + 14, true) };
    if (chunkId === 0x64617461) { dataOffset = content; dataSize = Math.min(chunkSize, view.byteLength - content); break; }
    offset = content + chunkSize + (chunkSize % 2);
  }
  if (!format || format.audioFormat !== 1 || format.channels !== 1 || format.bits !== 16 || !dataOffset || dataSize < 2) throw new Error("Nicht unterstütztes WAV-Format");
  const sampleCount = Math.floor(dataSize / 2);
  const buffer = context.createBuffer(1, sampleCount, format.sampleRate);
  const channel = buffer.getChannelData(0);
  for (let index = 0; index < sampleCount; index++) channel[index] = view.getInt16(dataOffset + index * 2, true) / 32768;
  return buffer;
}

function connectStoredAudio(source, context, destination) {
  if (!state.clipNoiseReduction) {
    source.connect(destination);
    return;
  }
  const highpass = context.createBiquadFilter();
  highpass.type = "highpass";
  highpass.frequency.value = 80;
  const lowpass = context.createBiquadFilter();
  lowpass.type = "lowpass";
  lowpass.frequency.value = 6500;
  source.connect(highpass);
  highpass.connect(lowpass);
  lowpass.connect(destination);
}

async function playEventClip(eventId, button) {
  if (state.clipSource && state.clipButton === button) { stopEventClip(); return; }
  stopEventClip();
  button.textContent = "Lädt …";
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) throw new Error("Audioausgabe nicht unterstützt");
  const context = new AudioContextClass();
  state.clipContext = context;
  state.clipButton = button;
  await context.resume();
  let destination = context.destination;
  const mobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
  if (mobile && context.createMediaStreamDestination) {
    const streamDestination = context.createMediaStreamDestination();
    const audioElement = new Audio();
    audioElement.autoplay = true;
    audioElement.playsInline = true;
    audioElement.srcObject = streamDestination.stream;
    try {
      await audioElement.play();
      state.clipAudioDestination = streamDestination;
      state.clipAudioElement = audioElement;
      destination = streamDestination;
    } catch (_) {
      audioElement.srcObject = null;
    }
  }
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 15_000);
  let response;
  try {
    response = await fetch(`/events/${eventId}/audio`, {
      headers: { Authorization: `Bearer ${state.token}` },
      signal: controller.signal,
    });
  } catch (error) {
    if (error?.name === "AbortError") throw new Error("Der Audioabruf hat zu lange gedauert. Bitte erneut versuchen.");
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }
  const payload = await response.arrayBuffer();
  let audioBuffer;
  try { audioBuffer = await context.decodeAudioData(payload.slice(0)); }
  catch (_) { audioBuffer = decodePcmWav(payload, context); }
  const source = context.createBufferSource();
  source.buffer = audioBuffer;
  connectStoredAudio(source, context, destination);
  source.onended = () => { if (state.clipSource === source) stopEventClip(); };
  state.clipSource = source;
  if (context.state !== "running") await context.resume();
  source.start();
  markEventListened(eventId, button);
  button.textContent = "■ Stoppen";
}

function showClipError(button, error) {
  stopEventClip();
  button.textContent = "Wiedergabe fehlgeschlagen";
  button.title = error?.message || String(error);
  window.setTimeout(() => {
    button.textContent = "▶ Anhören";
    button.title = "";
  }, 4000);
}

async function saveClassification(form, reason) {
  const button = form.querySelector("button[type=submit]");
  const primary = form.elements.primary_class_code.value;
  const subclass = form.elements.subclass_code.value || null;
  const secondary = Array.from(form.querySelectorAll('input[name="secondary_class_codes"]:checked'), (item) => item.value);
  const approvedSecondary = Array.from(form.querySelectorAll('input[name="secondary_learning_approved_codes"]:checked:not(:disabled)'), (item) => item.value);
  const primaryLearning = form.querySelector('input[name="primary_learning_approved"]')?.checked ?? !secondary.length;
  if (!primary) return;
  if (primary === "NO_NOISE") {
    try {
      await api(`/events/${form.dataset.eventId}/ignore`, { method: "POST" });
      await Promise.all([loadRecentEvents(), loadEvents(), loadReview(), refresh(), loadSoundMap()]);
    } catch (error) { button.textContent = error.message; }
    return;
  }
  const fine = state.eventClasses.filter((item) => item.active && item.level === "fine" && (item.parent_code == null || item.parent_code === primary));
  if (fine.length > 1 && !subclass) {
    button.textContent = "Feinzuordnung wählen";
    return;
  }
  try {
    await api(`/events/${form.dataset.eventId}/classification`, { method: "PATCH", body: JSON.stringify({ primary_class_code: primary, subclass_code: subclass, secondary_class_codes: secondary, secondary_learning_approved_codes: approvedSecondary, primary_learning_approved: primaryLearning, reason }) });
    state.classificationDrafts.delete(String(form.dataset.eventId));
    form.classList.add("confirmed");
    form.closest(".event-row,.recent-event")?.classList.add("confirmed");
    button.textContent = "Korrigieren";
    await Promise.all([loadRecentEvents(), loadEvents(), loadReview()]);
  } catch (error) { button.textContent = error.message; }
}

function connectLive() {
  state.socket?.close();
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  state.socket = new WebSocket(`${scheme}://${location.host}/ws/events?token=${encodeURIComponent(state.token)}`);
  state.socket.onopen = () => { $("#connection").textContent = "Live verbunden"; $("#live-dot").style.background = "var(--accent)"; };
  state.socket.onmessage = (message) => {
    addEvent(JSON.parse(message.data));
    if (activeView() === "overview") loadRecentEvents().catch(() => {});
  };
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
$("#show-register").addEventListener("click", () => { $("#login-form").classList.add("hidden"); $("#register-form").classList.remove("hidden"); });
$("#show-login").addEventListener("click", () => { $("#register-form").classList.add("hidden"); $("#login-form").classList.remove("hidden"); });
$("#register-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const password = $("#register-password").value;
  if (password !== $("#register-password-confirm").value) { $("#register-status").textContent = "Die Passwörter stimmen nicht überein."; return; }
  try {
    const result = await api("/auth/register", { method: "POST", body: JSON.stringify({ email: $("#register-email").value, password }) });
    $("#register-status").textContent = `${result.message}. Bitte Posteingang und Spamordner prüfen.`;
    event.target.reset();
  } catch (error) { $("#register-status").textContent = error.message; }
});
$("#notification-toggle").addEventListener("click", () => $("#notification-list").classList.toggle("hidden"));
$("#notification-list").addEventListener("click", async (event) => {
  const item = event.target.closest("[data-notification-id]");
  if (!item || !item.classList.contains("unread")) return;
  await api(`/api/admin-notifications/${item.dataset.notificationId}/read`, { method: "POST" });
  await loadAdminNotifications();
});
$("#logout").addEventListener("click", logout);
$("#push-enable").addEventListener("click", () => enablePush().catch((error) => { $("#push-enable").textContent = error.message; }));
$("#kpi-filter-form").addEventListener("submit", (event) => { event.preventDefault(); loadKpis().catch((error) => { $("#kpi-selection-label").textContent = error.message; }); });
document.querySelectorAll("[data-kpi-days]").forEach((button) => button.addEventListener("click", () => {
  const to = new Date(); to.setHours(12, 0, 0, 0); const from = new Date(to);
  from.setDate(from.getDate() - Number(button.dataset.kpiDays) + 1);
  $("#kpi-date-from").value = localDate(from); $("#kpi-date-to").value = localDate(to);
  document.querySelectorAll("[data-kpi-days]").forEach((item) => item.classList.toggle("active", item === button));
  loadKpis().catch((error) => { $("#kpi-selection-label").textContent = error.message; });
}));
for (const [selector, format] of [["#kpi-export-csv", "csv"], ["#kpi-export-xlsx", "xlsx"]]) {
  $(selector).addEventListener("click", async (event) => {
    const button = event.currentTarget; const label = button.textContent; button.disabled = true; button.textContent = "Export wird erstellt…";
    try { await downloadKpiExport(format); } catch (error) { $("#kpi-selection-label").textContent = error.message; }
    finally { button.disabled = false; button.textContent = label; }
  });
}
async function applyGlobalFilter() {
  const custom = days() === "single" || days() === "range";
  const today = localDate(new Date());
  if (custom && !$("#date-from-filter").value) $("#date-from-filter").value = today;
  if (days() === "range" && !$("#date-to-filter").value) $("#date-to-filter").value = $("#date-from-filter").value;
  $("#date-from-filter").classList.toggle("hidden", !custom);
  $("#date-to-filter").classList.toggle("hidden", days() !== "range");
  if (activeView() === "kpis") syncKpiDatesFromGlobal();
  await loadView(activeView());
}

async function loadSupport() {
  const config = await api("/api/support-config");
  const euro = new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" });
  $("#support-collected").textContent = euro.format(config.collected_eur);
  $("#support-open").textContent = `Noch offen: ${euro.format(config.open_eur)}`;
  $("#support-progress").style.width = `${Math.round(config.progress * 100)}%`;
  const link = $("#support-link");
  if (!config.enabled) return;
  link.href = config.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.classList.remove("disabled");
  link.removeAttribute("aria-disabled");
  link.textContent = "Projekt freiwillig unterstützen";
}
$("#days-filter").addEventListener("change", () => applyGlobalFilter().catch(() => {}));
$("#date-from-filter").addEventListener("change", () => applyGlobalFilter().catch(() => {}));
$("#date-to-filter").addEventListener("change", () => applyGlobalFilter().catch(() => {}));
$("#device-filter").addEventListener("change", () => Promise.all([applyGlobalFilter(), loadLiveLevels()]));
$("#clip-filter").addEventListener("change", () => { updateLiveFilterOptions(); renderEvents(); });
$("#category-filter").addEventListener("change", () => {
  localStorage.setItem("em_category_filter", $("#category-filter").value);
  updateEventFilter();
  updateCategoryFilter();
  renderEvents();
});
$("#event-filter").addEventListener("change", () => {
  localStorage.setItem("em_event_filter", $("#event-filter").value);
  updateCategoryFilter();
  updateEventFilter();
  renderEvents();
});
$("#show-resolved-events").addEventListener("change", () => { updateLiveFilterOptions(); renderEvents(); });
for (const picker of [$("#date-from-filter"), $("#date-to-filter")]) picker.addEventListener("click", () => picker.showPicker?.());
$("#level-minutes").addEventListener("change", loadLiveLevels);
document.querySelectorAll(".nav").forEach((button) => button.addEventListener("click", () => {
  if (button.closest("#admin-navigation") && state.role !== "admin") return;
  document.querySelectorAll(".nav").forEach((n) => n.classList.toggle("active", n === button));
  document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
  $(`#${button.dataset.view}`).classList.remove("hidden");
  $("#title").textContent = button.textContent.trim();
  $(".filters").classList.toggle("hidden", button.dataset.view === "support");
  if (button.dataset.view === "sound-map") requestAnimationFrame(renderSoundMap);
  loadView(button.dataset.view).catch((error) => {
    if (error?.status === 401) logout();
    else console.error(`${button.dataset.view} konnte nicht geladen werden`, error);
  });
}));
$("#audio-toggle").addEventListener("click", () => state.audioSocket ? stopAudio() : startAudio().catch((error) => stopAudio(error.message)));
$("#audio-test").addEventListener("click", () => playAudioTestTone().catch((error) => stopAudio(error.message)));
$("#audio-volume").addEventListener("input", () => { if (state.audioGain) state.audioGain.gain.value = Number($("#audio-volume").value); });
$("#audio-noise-filter").addEventListener("change", updateAudioFilterChain);
for (const checkbox of document.querySelectorAll("[data-clip-noise-filter]")) {
  checkbox.checked = state.clipNoiseReduction;
  checkbox.addEventListener("change", (event) => {
    state.clipNoiseReduction = event.target.checked;
    localStorage.setItem("em_clip_noise_filter", String(state.clipNoiseReduction));
    document.querySelectorAll("[data-clip-noise-filter]").forEach((item) => { item.checked = state.clipNoiseReduction; });
  });
}
$("#audio-device").addEventListener("change", () => stopAudio("Mikrofon ausgewählt – bereit"));
$("#events").addEventListener("change", (e) => {
  const form = e.target.closest(".live-actions");
  if (form && e.target.name === "primary_class_code") {
    form.elements.subclass_code.dataset.current = "";
    populateSubclassOptions(form);
    state.classificationDrafts.set(String(form.dataset.eventId), { primary_class_code: form.elements.primary_class_code.value, subclass_code: form.elements.subclass_code.value || null });
    if (form.elements.subclass_code.options.length === 2) saveClassification(form, "Im Live-Ereignisstrom automatisch übernommen");
  } else if (form && e.target.name === "subclass_code" && e.target.value) {
    state.classificationDrafts.set(String(form.dataset.eventId), { primary_class_code: form.elements.primary_class_code.value, subclass_code: form.elements.subclass_code.value });
    saveClassification(form, "Im Live-Ereignisstrom automatisch übernommen");
  } else if (form && e.target.name === "secondary_class_codes") {
    const learning = form.querySelector(`input[name="secondary_learning_approved_codes"][value="${CSS.escape(e.target.value)}"]`);
    learning.disabled = !e.target.checked;
    if (!e.target.checked) learning.checked = false;
    if (e.target.checked) form.querySelector('input[name="primary_learning_approved"]').checked = false;
  }
});
$("#events").addEventListener("click", async (e) => {
  const button = e.target.closest("[data-play-event]");
  if (!button) return;
  try { await playEventClip(button.dataset.playEvent, button); }
  catch (error) { showClipError(button, error); }
});
$("#events").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target.closest(".live-actions");
  if (!form) return;
  await saveClassification(form, "Im Live-Ereignisstrom bestätigt oder korrigiert");
});
$("#map-stage").addEventListener("click", async (e) => {
  if (state.role !== "admin") return;
  const deviceId = $("#map-position-device").value;
  const configured = state.devices.find((item) => item.device_id === deviceId);
  if (!configured) return;
  const bounds = e.currentTarget.getBoundingClientRect();
  const positionX = Math.max(0, Math.min(100, (e.clientX - bounds.left) / bounds.width * 100));
  const positionY = Math.max(0, Math.min(100, (e.clientY - bounds.top) / bounds.height * 100));
  try {
    await api(`/api/devices/${encodeURIComponent(deviceId)}`, { method: "PATCH", body: JSON.stringify({
      name: configured.name,
      location: configured.location,
      position_x: Number(positionX.toFixed(1)),
      position_y: Number(positionY.toFixed(1)),
      enabled: configured.enabled,
    }) });
    $("#map-unpositioned").textContent = `${configured.name} wurde bei X ${positionX.toFixed(1)} %, Y ${positionY.toFixed(1)} % gespeichert.`;
    await loadDevices();
    await loadSoundMap();
  } catch (error) { $("#map-unpositioned").textContent = error.message; }
});
$("#review-classes").addEventListener("click", async (e) => {
  const tile = e.target.closest("[data-review-class]");
  if (!tile) return;
  state.reviewClass = state.reviewClass === tile.dataset.reviewClass ? "" : tile.dataset.reviewClass;
  await loadReview();
});
$("#review-status").addEventListener("change", loadReviewQueue);
$("#review-primary").addEventListener("change", reviewSubclassOptions);
$("#review-secondary").addEventListener("change", () => {
  const selected = Array.from($("#review-secondary").selectedOptions, (item) => item.value);
  $("#review-primary-learning").checked = selected.length === 0;
  $("#review-secondary-learning").innerHTML = selected.map((code) => `<label><input type="checkbox" value="${escapeHtml(code)}"> ${escapeHtml(state.eventClasses.find((item) => item.code === code)?.name || code)} als Lernbeispiel freigeben</label>`).join("");
});
$("#review-events").addEventListener("change", updateReviewSelection);
$("#review-events").addEventListener("change", async (e) => {
  const select = e.target.closest("[data-person-event]");
  if (!select) return;
  try {
    await api(`/events/${select.dataset.personEvent}/person`, { method: "PUT", body: JSON.stringify({ person_id: select.value ? Number(select.value) : null }) });
    $("#people-status").textContent = "Personenzuordnung gespeichert.";
    await loadPeople();
  } catch (error) { $("#people-status").textContent = error.message; }
});
$("#review-select-all").addEventListener("click", () => {
  document.querySelectorAll("#review-events input").forEach((item) => { item.checked = true; });
  updateReviewSelection();
});
$("#review-bulk-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const eventIds = Array.from(document.querySelectorAll("#review-events input:checked"), (item) => Number(item.value));
  if (!eventIds.length) { $("#review-status-text").textContent = "Bitte mindestens ein Ereignis auswählen."; return; }
  try {
    if ($("#review-primary").value === "NO_NOISE") {
      await Promise.all(eventIds.map((id) => api(`/events/${id}/ignore`, { method: "POST" })));
      $("#review-status-text").textContent = `${eventIds.length} Ereignisse als kein Lärm verworfen.`;
    } else {
      const assessmentExcluded = $("#review-assessment-excluded").checked;
      const secondary = Array.from($("#review-secondary").selectedOptions, (item) => item.value);
      const approvedSecondary = Array.from(document.querySelectorAll("#review-secondary-learning input:checked"), (item) => item.value);
      await api("/events/review/bulk-classification", { method: "POST", body: JSON.stringify({ event_ids: eventIds, primary_class_code: $("#review-primary").value, subclass_code: $("#review-subclass").value || null, secondary_class_codes: secondary, secondary_learning_approved_codes: approvedSecondary, primary_learning_approved: $("#review-primary-learning").checked, reason: $("#review-reason").value, assessment_excluded: assessmentExcluded, assessment_exclusion_reason: assessmentExcluded ? $("#review-assessment-reason").value : null }) });
      $("#review-status-text").textContent = `${eventIds.length} Ereignisse bestätigt.`;
    }
    await Promise.all([loadReview(), loadRecentEvents(), loadEvents()]);
  } catch (error) { $("#review-status-text").textContent = error.message; }
});
$("#review-run").addEventListener("click", async () => {
  try { await api("/events/review/runs", { method: "POST", body: JSON.stringify({ kind: "automatic" }) }); await loadReview(); }
  catch (error) { $("#review-status-text").textContent = error.message; }
});
$("#historical-import-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const files = Array.from($("#import-files").files || []);
  const total = files.reduce((sum, file) => sum + file.size, 0);
  if (!files.length || total > 50 * 1024 * 1024) { $("#import-status").textContent = "Bitte 1–20 Dateien mit insgesamt höchstens 50 MB auswählen."; return; }
  $("#import-status").textContent = "Dateien werden eingelesen …";
  try {
    const payload = await Promise.all(files.map(async (file) => ({ name: file.name, content_base64: await fileAsBase64(file) })));
    const result = await api("/events/review/import", { method: "POST", body: JSON.stringify({ device_id: $("#import-device").value, files: payload }) });
    $("#import-status").textContent = `${result.imported_events} Ereignisse importiert, davon ${result.imported_audio} mit Wiedergabe; ${result.skipped} übersprungen.${result.messages.length ? ` ${result.messages.join(" · ")}` : ""}`;
    e.target.reset();
    await Promise.all([loadReview(), loadEvents(), loadRecentEvents(), refresh()]);
  } catch (error) { $("#import-status").textContent = error.message; }
});
$("#person-create-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/api/people", { method: "POST", body: JSON.stringify({ name: $("#person-name").value, active: true }) });
    e.target.reset();
    $("#people-status").textContent = "Personenprofil angelegt.";
    await loadReview();
  } catch (error) { $("#people-status").textContent = error.message; }
});
$("#people-list").addEventListener("submit", async (e) => {
  const editor = e.target.closest(".person-editor");
  if (editor) {
    e.preventDefault();
    const card = editor.closest("[data-person-id]");
    const status = card.querySelector(".person-media-status");
    try {
      await api(`/api/people/${card.dataset.personId}`, { method: "PATCH", body: JSON.stringify({ name: editor.elements.name.value, active: editor.elements.active.checked, monitoring_enabled: editor.elements.monitoring_enabled.checked }) });
      await Promise.all([loadPeople(), refresh(), loadKpis(), loadSoundMap()]);
      $("#people-status").textContent = "Personenprofil und Einbeziehung in die Lärmüberwachung gespeichert.";
    } catch (error) { status.textContent = error.message; }
    return;
  }
  const photoForm = e.target.closest(".person-photo-upload");
  if (photoForm) {
    e.preventDefault();
    const card = photoForm.closest("[data-person-id]");
    const file = photoForm.elements.photo.files?.[0];
    const status = card.querySelector(".person-media-status");
    if (!file || file.size > 5 * 1024 * 1024) { status.textContent = "Bitte ein JPEG- oder PNG-Bild mit höchstens 5 MB auswählen."; return; }
    try {
      await api(`/api/people/${card.dataset.personId}/media`, { method: "POST", body: JSON.stringify({ media_type: "photo", filename: file.name, mime_type: mediaMime(file, "photo"), content_base64: await fileAsBase64(file) }) });
      await loadPeople();
      $("#people-status").textContent = "Profilbild aktualisiert.";
    } catch (error) { status.textContent = error.message; }
    return;
  }
  const form = e.target.closest(".person-video-upload");
  if (!form) return;
  e.preventDefault();
  const card = form.closest("[data-person-id]");
  const file = form.elements.video.files?.[0];
  const status = card.querySelector(".person-media-status");
  if (!file || file.size > 50 * 1024 * 1024) { status.textContent = "Bitte ein Video mit höchstens 50 MB auswählen."; return; }
  const button = form.querySelector("button");
  button.disabled = true; status.textContent = "Video wird gespeichert, Tonspur extrahiert und verglichen …";
  try {
    const result = await api(`/api/people/${card.dataset.personId}/media`, { method: "POST", body: JSON.stringify({ media_type: "video", filename: file.name, mime_type: mediaMime(file, "video"), content_base64: await fileAsBase64(file) }) });
    await loadPeople();
    $("#people-status").textContent = `${result.message}${result.similarity == null ? "" : ` · ${Math.round(result.similarity * 100)} % Ähnlichkeit zu ${result.cluster_name}`}`;
  } catch (error) { status.textContent = error.message; button.disabled = false; }
});
$("#people-list").addEventListener("click", async (e) => {
  const open = e.target.closest("[data-open-person-video]");
  if (open) {
    const card = open.closest("[data-person-id]");
    const review = card.querySelector(".person-video-review");
    const video = review.querySelector("video");
    const audio = review.querySelector("audio");
    review.classList.remove("hidden");
    if (!video.src) video.src = await authorizedMediaUrl(`/api/people/${card.dataset.personId}/media/video`);
    const person = state.people.find((item) => item.id === Number(card.dataset.personId));
    if (person?.video_audio_available && !audio.src) {
      audio.src = await authorizedMediaUrl(`/api/people/${card.dataset.personId}/media/voice`);
      audio.classList.remove("hidden");
    }
    return;
  }
  const capture = e.target.closest("[data-capture-person-photo]");
  if (!capture) return;
  const card = capture.closest("[data-person-id]");
  const video = card.querySelector("video");
  const status = card.querySelector(".person-media-status");
  if (!video.videoWidth || !video.videoHeight) { status.textContent = "Bitte das Video zuerst starten und am gewünschten Bild anhalten."; return; }
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth; canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
  if (!blob) { status.textContent = "Das Einzelbild konnte nicht erstellt werden."; return; }
  capture.disabled = true; status.textContent = "Profilbild wird gespeichert …";
  try {
    await api(`/api/people/${card.dataset.personId}/media`, { method: "POST", body: JSON.stringify({ media_type: "photo", filename: "videoframe.jpg", mime_type: "image/jpeg", content_base64: await fileAsBase64(blob) }) });
    await loadPeople();
    $("#people-status").textContent = "Videoframe als Profilbild gespeichert.";
  } catch (error) { status.textContent = error.message; capture.disabled = false; }
});
$("#speaker-analyze").addEventListener("click", async () => {
  const button = $("#speaker-analyze");
  button.disabled = true; button.textContent = "Stimmanalyse wird gestartet …";
  try {
    await api("/api/speaker-analysis/runs", { method: "POST" });
    $("#speaker-status").textContent = "Der Hintergrundlauf wurde gestartet. Mikrofone und Dashboard arbeiten normal weiter.";
    await loadSpeakerAnalysisProgress();
  } catch (error) { $("#speaker-status").textContent = error.message; }
  finally { if (!button.disabled) button.textContent = "Separate Stimmanalyse starten"; }
});
$("#speaker-clusters").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target.closest(".speaker-cluster");
  if (!form) return;
  try {
    await api(`/api/speaker-clusters/${form.dataset.clusterId}`, { method: "PATCH", body: JSON.stringify({ name: form.elements.name.value, person_id: form.elements.person_id.value ? Number(form.elements.person_id.value) : null }) });
    $("#speaker-status").textContent = "Stimmgruppe gespeichert.";
    await Promise.all([loadSpeakerClusters(), loadPeople()]);
  } catch (error) { $("#speaker-status").textContent = error.message; }
});
$("#speaker-clusters").addEventListener("click", async (e) => {
  const button = e.target.closest("[data-review-speaker]");
  if (!button) return;
  state.speakerClusterId = Number(button.dataset.reviewSpeaker);
  await loadSpeakerSamples();
  $("#speaker-review").scrollIntoView({ behavior: "smooth", block: "start" });
});
$("#speaker-review-close").addEventListener("click", closeSpeakerReview);
$("#speaker-review-filter").addEventListener("change", () => loadSpeakerSamples().catch((error) => { $("#speaker-status").textContent = error.message; }));
$("#speaker-review-more").addEventListener("click", () => loadSpeakerSamples(true).catch((error) => { $("#speaker-status").textContent = error.message; }));
$("#speaker-review").addEventListener("click", async (e) => {
  const play = e.target.closest("[data-play-event]");
  if (play) {
    try { await playEventClip(play.dataset.playEvent, play); } catch (error) { showClipError(play, error); }
    return;
  }
  const actionButton = e.target.closest("[data-speaker-action]");
  if (!actionButton) return;
  const row = actionButton.closest("[data-speaker-event]");
  const payload = { action: actionButton.dataset.speakerAction };
  if (payload.action === "move") payload.target_cluster_id = Number(row.querySelector("select").value);
  actionButton.disabled = true;
  try {
    await api(`/api/speaker-clusters/${state.speakerClusterId}/samples/${row.dataset.speakerEvent}`, { method: "PATCH", body: JSON.stringify(payload) });
    await loadSpeakerClusters();
    await loadSpeakerSamples();
    $("#speaker-status").textContent = "Prüfentscheidung gespeichert und Stimmprofil aktualisiert.";
  } catch (error) {
    $("#speaker-status").textContent = error.message;
    actionButton.disabled = false;
  }
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
$("#tenant-create-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const tenant = await api("/api/platform/tenants", { method: "POST", body: JSON.stringify({ name: $("#tenant-name").value, slug: $("#tenant-slug").value, admin_username: $("#tenant-admin").value, admin_password: $("#tenant-password").value, plan: $("#tenant-plan").value, max_devices: Number($("#tenant-max-devices").value), retention_days: Number($("#tenant-retention").value) }) });
    e.target.reset();
    $("#tenant-status").textContent = `Kundenbereich ${tenant.name} mit Administrator ${tenant.admin_username} angelegt.`;
    await loadTenants();
  } catch (error) { $("#tenant-status").textContent = error.message; }
});
$("#user-create-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    if ($("#new-password").value !== $("#new-password-confirm").value) throw new Error("Die Passwörter stimmen nicht überein.");
    await api("/auth/users", { method: "POST", body: JSON.stringify({ username: $("#new-username").value, password: $("#new-password").value, role: $("#new-role").value }) });
    e.target.reset();
    $("#user-create-status").textContent = "Benutzer angelegt.";
    await Promise.all([loadUsers(), loadAudioPermissions()]);
  } catch (error) { $("#user-create-status").textContent = error.message; }
});
$("#assessment-config-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const classRules = Object.fromEntries(Array.from(document.querySelectorAll("[data-assessment-class]"), (item) => [item.dataset.assessmentClass, item.checked]));
    state.assessmentConfig = await api("/api/assessment-config", { method: "PUT", body: JSON.stringify({ sensitive_surcharge_db: Number($("#surcharge-db").value), apply_to_live: $("#surcharge-live").checked, class_rules: classRules }) });
    $("#assessment-config-status").textContent = "Beurteilungseinstellung gespeichert.";
    renderAssessmentClassRules();
    await refresh();
  } catch (error) { $("#assessment-config-status").textContent = error.message; }
});
$("#user-list").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target.closest(".user-editor");
  if (!form) return;
  try {
    if (form.elements.password.value !== form.elements.password_confirm.value) throw new Error("Die Passwörter stimmen nicht überein.");
    await api(`/auth/users/${form.dataset.userId}`, { method: "PATCH", body: JSON.stringify({ role: form.elements.role.value, active: form.elements.active.checked, password: form.elements.password.value || null }) });
    $("#user-status").textContent = "Benutzer aktualisiert.";
    await Promise.all([loadUsers(), loadAudioPermissions()]);
  } catch (error) { $("#user-status").textContent = error.message; }
});
$("#class-create-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/api/event-classes", { method: "POST", body: JSON.stringify({ code: $("#class-code").value.toUpperCase(), name: $("#class-name").value, level: $("#class-level").value, parent_code: $("#class-parent").value || null, hidden_by_default: $("#class-hidden").checked }) });
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
    await api(`/api/event-classes/${form.dataset.classId}`, { method: "PATCH", body: JSON.stringify({ name: form.elements.name.value, level: form.elements.level.value, parent_code: form.elements.parent_code.value || null, active: form.elements.active.checked, trainable: form.elements.trainable.checked, hidden_by_default: form.elements.hidden_by_default.checked, sort_order: Number(form.dataset.sortOrder) }) });
    $("#class-status").textContent = "Klasse aktualisiert.";
    await loadEventClasses();
  } catch (error) { $("#class-status").textContent = error.message; }
});
$("#recent-events").addEventListener("change", (e) => {
  const form = e.target.closest(".classification-editor");
  if (form && e.target.name === "primary_class_code") {
    form.elements.subclass_code.dataset.current = "";
    populateSubclassOptions(form);
    if (form.elements.subclass_code.options.length === 2) saveClassification(form, "In der Übersicht automatisch übernommen");
  } else if (form && e.target.name === "subclass_code" && e.target.value) {
    saveClassification(form, "In der Übersicht automatisch übernommen");
  } else if (form && e.target.name === "secondary_class_codes") {
    const learning = form.querySelector(`input[name="secondary_learning_approved_codes"][value="${CSS.escape(e.target.value)}"]`);
    learning.disabled = !e.target.checked;
    if (!e.target.checked) learning.checked = false;
    if (e.target.checked) form.querySelector('input[name="primary_learning_approved"]').checked = false;
  }
});
$("#assessment-class-list").addEventListener("change", (e) => {
  if (!e.target.matches("[data-assessment-class]")) return;
  const status = e.target.closest(".assessment-class-rule").querySelector("em");
  status.textContent = e.target.checked ? "fließt ein" : "ausgeschlossen";
});
$("#recent-events").addEventListener("click", async (e) => {
  const button = e.target.closest("[data-play-event]");
  if (!button) return;
  try { await playEventClip(button.dataset.playEvent, button); } catch (error) { showClipError(button, error); }
});
$("#review-events").addEventListener("click", async (e) => {
  const button = e.target.closest("[data-play-event]");
  if (!button) return;
  e.preventDefault();
  try { await playEventClip(button.dataset.playEvent, button); } catch (error) { showClipError(button, error); }
});
$("#recent-events").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target.closest(".classification-editor");
  if (!form) return;
  await saveClassification(form, "In der Übersicht bestätigt oder korrigiert");
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
$("#live-calibration-devices").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target.closest(".live-calibration-card");
  if (!form) return;
  const button = form.querySelector('button[type="submit"]');
  const status = form.querySelector(".live-calibration-status");
  const draft = state.calibrationDrafts.get(form.dataset.deviceId);
  const targetOffset = draft?.value ?? 0;
  button.disabled = true;
  status.textContent = "Korrektur wird gespeichert und auf frühere Messwerte angewendet …";
  try {
    const calibration = await api("/api/device-calibrations/set-offset", { method: "POST", body: JSON.stringify({ device_id: form.dataset.deviceId, target_offset_db: targetOffset }) });
    state.calibrationDrafts.set(form.dataset.deviceId, { value: calibration.applied_offset_db, dirty: false });
    status.textContent = `Gespeichert: aktiver Offset ${calibration.applied_offset_db >= 0 ? "+" : ""}${calibration.applied_offset_db.toFixed(2)} dB. Frühere und neue Messwerte wurden angepasst.`;
    await Promise.all([loadTelemetry(), loadCalibrations(), loadLiveLevels()]);
  } catch (error) {
    status.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
$("#live-calibration-devices").addEventListener("click", (e) => {
  const form = e.target.closest(".live-calibration-card");
  if (!form) return;
  const calibration = state.calibrations.find((item) => item.device_id === form.dataset.deviceId);
  const appliedOffset = calibration?.applied_offset_db || 0;
  if (e.target.closest("[data-offset-reset]")) {
    state.calibrationDrafts.set(form.dataset.deviceId, { value: appliedOffset, dirty: false });
    form.querySelector(".live-calibration-status").textContent = "Vorschau verworfen. Die gespeicherte Korrektur bleibt unverändert.";
    renderLiveCalibration();
    return;
  }
  const adjust = e.target.closest("[data-offset-adjust]");
  if (!adjust) return;
  const direction = Number(adjust.dataset.offsetAdjust);
  const step = Number(form.elements.offset_step.value);
  const current = state.calibrationDrafts.get(form.dataset.deviceId)?.value ?? appliedOffset;
  const value = Math.max(-30, Math.min(30, Math.round((current + direction * step) * 100) / 100));
  state.calibrationDrafts.set(form.dataset.deviceId, { value, dirty: value !== appliedOffset });
  form.querySelector(".live-calibration-status").textContent = value === appliedOffset ? "Die Vorschau entspricht wieder der gespeicherten Korrektur." : "Vorschau aktiv. Beobachten Sie den Live-Wert; gespeichert ist noch nichts.";
  renderLiveCalibration();
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
$("#calibration-import-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const file = $("#calibration-file").files?.[0];
  const deviceIds = Array.from(document.querySelectorAll('input[name="calibration_device"]:checked'), (item) => item.value);
  if (!file || file.size > 2 * 1024 * 1024) { $("#calibration-import-status").textContent = "Bitte eine CSV mit höchstens 2 MB auswählen."; return; }
  if (!deviceIds.length) { $("#calibration-import-status").textContent = "Bitte mindestens ein Mikrofon auswählen."; return; }
  $("#calibration-import-status").textContent = "Referenzwerte werden zeitlich abgeglichen …";
  try {
    const run = await api("/api/device-calibrations/reference-import", { method: "POST", body: JSON.stringify({ filename: file.name, content_base64: await fileAsBase64(file), device_ids: deviceIds, tolerance_seconds: Number($("#calibration-tolerance").value) }) });
    $("#calibration-import-status").textContent = `${run.reference_points} Referenzwerte importiert und mit ${run.results.reduce((sum, item) => sum + item.matched_points, 0)} Mikrofonwerten verglichen.`;
    e.target.reset();
    await Promise.all([loadCalibrations(), loadCalibrationReferenceRuns()]);
  } catch (error) { $("#calibration-import-status").textContent = error.message; }
});
$("#calibration-reference-runs").addEventListener("click", async (e) => {
  const deviceId = e.target.dataset.applyOffset;
  if (!deviceId) return;
  try {
    await api("/api/device-calibrations/apply-offsets", { method: "POST", body: JSON.stringify({ device_ids: [deviceId] }) });
    $("#calibration-import-status").textContent = `Kalibrier-Offset für ${deviceId} ist ab dem nächsten Messwert aktiv.`;
    await Promise.all([loadCalibrations(), loadCalibrationReferenceRuns()]);
  } catch (error) { $("#calibration-import-status").textContent = error.message; }
});
$("#open-people").addEventListener("click", () => {
  const button = document.querySelector('.nav[data-view="people"]');
  if (button) button.click();
  $("#person-name").focus();
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
$("#device-management-list").addEventListener("click", async (e) => {
  const button = e.target.closest("[data-device-credential]");
  if (!button) return;
  try {
    const result = await api(`/api/devices/${encodeURIComponent(button.dataset.deviceCredential)}/credential`, { method: "POST" });
    $("#device-management-status").innerHTML = `Neuer Gerätezugang erstellt. Das Geheimnis wird nur einmal angezeigt:<br><code>${escapeHtml(result.secret)}</code><br>Geräte-ID: <code>${escapeHtml(result.device_id)}</code>`;
  } catch (error) { $("#device-management-status").textContent = error.message; }
});
function formatTime(value) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("de-DE"); }
function formatDuration(value) { const seconds = Math.max(0, Number(value) || 0); return seconds >= 60 ? `${Math.floor(seconds / 60)} min ${Math.round(seconds % 60)} s` : `${seconds.toFixed(seconds < 10 ? 1 : 0)} s`; }
function escapeHtml(value) { const node = document.createElement("span"); node.textContent = String(value); return node.innerHTML; }
const initialFilterDate = localDate(new Date());
$("#date-from-filter").value = initialFilterDate;
$("#date-to-filter").value = initialFilterDate;
if (state.token) start();
const verificationResult = new URLSearchParams(location.search).get("verification");
if (verificationResult) $("#auth-error").textContent = verificationResult === "success" ? "E-Mail bestätigt. Sie können sich jetzt anmelden." : "Der Bestätigungslink ist ungültig oder abgelaufen.";
if (new URLSearchParams(location.search).get("register") === "1") $("#show-register").click();
window.addEventListener("resize", () => requestAnimationFrame(renderSoundMap));
$("#system-status").addEventListener("click", () => {
  const devicesNavigation = document.querySelector('.nav[data-view="devices"]');
  if (state.role === "admin" && devicesNavigation) devicesNavigation.click();
});
setInterval(() => { if (state.token) loadTelemetry().catch(() => {}); }, 30000);
setInterval(() => { if (state.token && activeView() === "live") loadTelemetry().catch(() => {}); }, 2000);
setInterval(() => { if (state.token && activeView() === "live") loadLiveLevels().catch(() => {}); }, 5000);
window.addEventListener("resize", () => { if (state.token) renderSoundMap(); });
