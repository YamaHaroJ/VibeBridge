const toggle = document.querySelector("#enabled");
const title = document.querySelector("#state-title");
const copy = document.querySelector("#state-copy");
const status = document.querySelector("#status");
const statusText = document.querySelector("#status-text");

let ready = false;

function renderEnabled(value) {
  toggle.setAttribute("aria-checked", String(value));
  title.textContent = value ? "VibeBridge is on" : "VibeBridge is off";
  copy.textContent = value
    ? "Project context is added automatically."
    : "ChatGPT messages are sent without project context.";
}

function renderStatus(state, message) {
  status.dataset.state = state;
  statusText.textContent = message;
}

async function callHealth(token) {
  const response = await fetch("http://127.0.0.1:43127/health", {
    headers: { Authorization: "Bearer " + token }
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Local agent unavailable");
  return data;
}

async function initialize() {
  toggle.disabled = true;
  renderStatus("checking", "Checking local connection");
  try {
    const saved = await chrome.storage.local.get(["token", "enabled"]);
    if (!saved.token) {
      ready = false;
      renderEnabled(false);
      copy.textContent = "Setup needs to be completed first.";
      renderStatus("setup", "Local agent setup incomplete");
      return;
    }
    await callHealth(saved.token);
    ready = true;
    const isEnabled = saved.enabled !== false;
    renderEnabled(isEnabled);
    toggle.disabled = false;
    renderStatus("ready", "Local agent connected");
  } catch (error) {
    ready = false;
    renderEnabled(false);
    copy.textContent = "Waiting for the local agent to be ready.";
    renderStatus("setup", "Local agent not connected");
  }
}

toggle.addEventListener("click", async () => {
  if (!ready || toggle.disabled) return;
  const next = toggle.getAttribute("aria-checked") !== "true";
  await chrome.storage.local.set({ enabled: next });
  renderEnabled(next);
});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "local") return;
  if (changes.token) initialize();
  if (changes.enabled && ready) renderEnabled(changes.enabled.newValue !== false);
});

initialize();
