let sessionId = null;
let eventSource = null;

const sessionLabel = document.getElementById("session-id");
const createSessionButton = document.getElementById("create-session");
const sendMessageButton = document.getElementById("send-message");
const sendEventButton = document.getElementById("send-event");
const messageInput = document.getElementById("message");
const eventInput = document.getElementById("event");
const eventsBox = document.getElementById("events");

function logEvent(text) {
  eventsBox.textContent += `${text}\n`;
}

async function createSession() {
  const response = await fetch("/sessions", { method: "POST" });
  const data = await response.json();
  sessionId = data.id;
  sessionLabel.textContent = sessionId;
  setupEventStream();
}

function setupEventStream() {
  if (!sessionId) return;
  if (eventSource) eventSource.close();
  eventSource = new EventSource(`/sessions/${sessionId}/events`);
  eventSource.onmessage = (event) => {
    logEvent(event.data);
  };
  eventSource.onerror = () => {
    logEvent("event stream error");
  };
}

async function sendMessage() {
  if (!sessionId) return;
  const content = messageInput.value.trim();
  if (!content) return;
  await fetch(`/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role: "user", content }),
  });
  messageInput.value = "";
}

async function sendEvent() {
  if (!sessionId) return;
  const message = eventInput.value.trim();
  if (!message) return;
  await fetch(`/sessions/${sessionId}/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  eventInput.value = "";
}

createSessionButton.addEventListener("click", createSession);
sendMessageButton.addEventListener("click", sendMessage);
sendEventButton.addEventListener("click", sendEvent);
