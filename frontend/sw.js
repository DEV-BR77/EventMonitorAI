self.addEventListener("push", (event) => {
  const data = event.data?.json() || {};
  event.waitUntil(self.registration.showNotification(data.title || "EventMonitorAI", {
    body: data.body || "Neues Lärmereignis",
    icon: "/icon.svg",
    badge: "/icon.svg",
    tag: `event-${data.event_id}`,
    requireInteraction: true,
    actions: [
      { action: "confirmed", title: "Bestätigen" },
      { action: "rejected", title: "Ablehnen" }
    ],
    data
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const data = event.notification.data || {};
  if (event.action === "confirmed" || event.action === "rejected") {
    const url = `/push/respond?token=${encodeURIComponent(data.response_token)}&response=${event.action}`;
    event.waitUntil(fetch(url, { method: "POST" }).then(() => self.registration.showNotification(
      event.action === "confirmed" ? "Als Zeuge bestätigt" : "Ereignis abgelehnt",
      { body: `Ereignis #${data.event_id}`, icon: "/icon.svg", tag: `response-${data.event_id}` }
    )));
    return;
  }
  event.waitUntil(clients.openWindow(`/?event=${encodeURIComponent(data.event_id || "")}`));
});
