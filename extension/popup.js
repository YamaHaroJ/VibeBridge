const toggle = document.querySelector("#enabled");
const title = document.querySelector("#state-title");
const copy = document.querySelector("#state-copy");
const status = document.querySelector("#status");
const statusText = document.querySelector("#status-text");
const connect = document.querySelector("#connect");
const consent = document.querySelector("#consent");
const consentCheck = document.querySelector("#consent-check");
const confirmConnect = document.querySelector("#confirm");
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
    headers: {Authorization: "Bearer " + token}
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Local agent unavailable");
  return data;
}
async function initialize() {
  toggle.disabled = true;
  connect.classList.add("hidden");
  renderStatus("checking", "Checking local connection");
  try {
    const saved = await chrome.storage.local.get(["token", "enabled", "connectionConsent"]);
    if (!saved.token) {
      ready = false;
      renderEnabled(false);
      copy.textContent = "Connect once to finish setup.";
      renderStatus("setup", "Connection needs setup");
      connect.classList.remove("hidden");
      return;
    }
    await callHealth(saved.token);
    ready = true;
    renderEnabled(saved.enabled !== false);
    toggle.disabled = false;
    renderStatus("ready", "Local agent connected");
  } catch {
    ready = false;
    renderEnabled(false);
    copy.textContent = "Start the local agent to finish setup.";
    renderStatus("setup", "Local agent not connected");
    connect.classList.remove("hidden");
  }
}
connect.addEventListener("click", () => {
  consentCheck.checked = false;
  confirmConnect.disabled = true;
  consent.classList.remove("hidden");
});
consentCheck.addEventListener("change", () => {
  confirmConnect.disabled = !consentCheck.checked;
});
document.querySelector("#cancel").addEventListener("click", () => consent.classList.add("hidden"));
confirmConnect.addEventListener("click", async () => {
  if (!consentCheck.checked) return;
  confirmConnect.disabled = true;
  confirmConnect.textContent = "Connecting…";
  try {
    const saved = await chrome.storage.local.get(["token"]);
    if (!saved.token) {
      throw new Error("The local agent token has not been paired with this extension yet. The installer needs a secure one-time pairing step.");
    }
    await callHealth(saved.token);
    await chrome.storage.local.set({connectionConsent: true});
    consent.classList.add("hidden");
    await initialize();
  } catch (error) {
    consent.classList.add("hidden");
    renderStatus("setup", error.message);
    copy.textContent = "One-time pairing still needs to be completed.";
    connect.classList.remove("hidden");
  } finally {
    confirmConnect.textContent = "Connect";
    confirmConnect.disabled = !consentCheck.checked;
  }
});
toggle.addEventListener("click", async () => {
  if (!ready || toggle.disabled) return;
  const next = toggle.getAttribute("aria-checked") !== "true";
  await chrome.storage.local.set({enabled: next});
  renderEnabled(next);
});
chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "local") return;
  if (changes.token) initialize();
  if (changes.enabled && ready) renderEnabled(changes.enabled.newValue !== false);
});
initialize();
