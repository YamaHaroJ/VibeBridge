const toggle = document.querySelector("#enabled");
const title = document.querySelector("#state-title");
const copy = document.querySelector("#state-copy");
const status = document.querySelector("#status");
const statusText = document.querySelector("#status-text");
const githubStatus = document.querySelector("#github-status");
const githubStatusText = document.querySelector("#github-status-text");
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
function renderStatus(element, label, state, message) {
  element.dataset.state = state;
  label.textContent = message;
}
async function callAgent(path, token) {
  const response = await fetch("http://127.0.0.1:43127" + path, {
    headers: {Authorization: "Bearer " + token}
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}
async function initialize() {
  toggle.disabled = true;
  connect.classList.add("hidden");
  renderStatus(status, statusText, "checking", "Checking local connection");
  renderStatus(githubStatus, githubStatusText, "checking", "Checking GitHub connection");
  try {
    const saved = await chrome.storage.local.get(["token", "enabled"]);
    if (!saved.token) {
      ready = false;
      renderEnabled(false);
      copy.textContent = "Connect once to finish setup.";
      renderStatus(status, statusText, "setup", "Local connection needs setup");
      renderStatus(githubStatus, githubStatusText, "setup", "GitHub check waiting for local connection");
      connect.classList.remove("hidden");
      return;
    }
    await callAgent("/health", saved.token);
    renderStatus(status, statusText, "ready", "Local agent connected");
    try {
      const data = await callAgent("/github-projects", saved.token);
      const count = (data.repositories || []).length;
      renderStatus(githubStatus, githubStatusText, "ready", "GitHub connected · " + count + " repositories");
      ready = true;
      renderEnabled(saved.enabled !== false);
      toggle.disabled = false;
    } catch {
      ready = false;
      renderEnabled(false);
      copy.textContent = "Sign in to GitHub on this Mac to finish setup.";
      renderStatus(githubStatus, githubStatusText, "setup", "GitHub sign-in required");
      connect.classList.remove("hidden");
    }
  } catch {
    ready = false;
    renderEnabled(false);
    copy.textContent = "Start the local agent to finish setup.";
    renderStatus(status, statusText, "setup", "Local agent not connected");
    renderStatus(githubStatus, githubStatusText, "setup", "GitHub check waiting for local connection");
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
    const existing = await chrome.storage.local.get(["token"]);
    let token = existing.token;
    if (!token) {
      const response = await fetch("http://127.0.0.1:43127/pair", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({})
      });
      const data = await response.json();
      if (!response.ok || !data.token) throw new Error(data.error || "Could not connect to the local agent.");
      token = data.token;
      await chrome.storage.local.set({token});
    }
    await callAgent("/health", token);
    await chrome.storage.local.set({connectionConsent: true});
    consent.classList.add("hidden");
    await initialize();
  } catch (error) {
    consent.classList.add("hidden");
    renderStatus(status, statusText, "setup", error.message);
    copy.textContent = "Finish the one-time pairing, then connect again.";
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
