const API = "http://127.0.0.1:43127";

// Recover heartbeat automatically across every ChatGPT tab without reloading pages.
async function ensureChatGPTTabHeartbeat(tabId) {
  try {
    const tab = await chrome.tabs.get(tabId);
    const url = new URL(tab.url || "");
    if (!["chatgpt.com", "chat.openai.com"].includes(url.hostname)) return;
    await chrome.scripting.executeScript({target: {tabId}, files: ["chatgpt.js"]});
  } catch (_) {
    // Chrome may reject restricted, closing, or not-yet-ready tabs; later events retry.
  }
}
async function recoverOpenChatGPTTabs() {
  try {
    const tabs = await chrome.tabs.query({url: ["https://chatgpt.com/*", "https://chat.openai.com/*"]});
    await Promise.all(tabs.map(tab => ensureChatGPTTabHeartbeat(tab.id)));
  } catch (_) {}
}
chrome.runtime.onInstalled?.addListener?.(() => { recoverOpenChatGPTTabs(); });
chrome.runtime.onStartup?.addListener?.(() => { recoverOpenChatGPTTabs(); });
chrome.tabs?.onUpdated?.addListener?.((tabId, changeInfo) => {
  if (changeInfo.status === "complete") ensureChatGPTTabHeartbeat(tabId);
});

async function fetchAgent(path, options = {}, timeoutMs = 20000) {
  const controller = new AbortController();
  let timeout;
  const clearRequestTimeout = () => clearTimeout(timeout);
  timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(API + path, {...options, signal: controller.signal});
    // Keep the deadline active while the response body is being read, not just
    // until headers arrive. Every current caller consumes JSON via response.json().
    const readJson = response.json.bind(response);
    response.json = async (...args) => {
      try {
        return await readJson(...args);
      } catch (error) {
        if (error.name === "AbortError") {
          throw new Error("VibeBridge local agent timed out while reading " + path + ".");
        }
        throw error;
      } finally {
        clearRequestTimeout();
      }
    };
    return response;
  } catch (error) {
    clearRequestTimeout();
    if (error.name === "AbortError") {
      throw new Error("VibeBridge local agent timed out while handling " + path + ".");
    }
    throw error;
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const supported = [
    "VIBEBRIDGE_RESOLVE_CONTEXT",
    "VIBEBRIDGE_RESOLVE_CONTEXTS",
    "VIBEBRIDGE_REMEMBER",
    "VIBEBRIDGE_RUN_COMMAND",
    "VIBEBRIDGE_CREATE_REPOSITORY",
    "VIBEBRIDGE_FILESYSTEM_LIST",
    "VIBEBRIDGE_FILESYSTEM_READ",
    "VIBEBRIDGE_FILESYSTEM_WRITE",
    "VIBEBRIDGE_FILESYSTEM_MKDIR",
    "VIBEBRIDGE_CHECKPOINT_MESSAGE",
    "VIBEBRIDGE_BROWSER_HEARTBEAT",
    "VIBEBRIDGE_BROWSER_STATUS",
    "VIBEBRIDGE_PROBE_CHATGPT_TABS",
    "VIBEBRIDGE_LOCAL_DIAGNOSTICS"
  ];
  if (!supported.includes(message?.type)) return;

  if (message?.type === "VIBEBRIDGE_PROBE_CHATGPT_TABS") {
    chrome.tabs.query({url: ["https://chatgpt.com/*", "https://chat.openai.com/*"]}, async tabs => {
      const results = await Promise.all(tabs.map(async tab => {
        const ping = async () => {
          try { return await chrome.tabs.sendMessage(tab.id, {type: "VIBEBRIDGE_CONTENT_SCRIPT_PING"}); }
          catch (_) { return null; }
        };
        let reply = await ping();
        let recovered = false;
        if (!reply?.alive) {
          try {
            await chrome.scripting.executeScript({target: {tabId: tab.id}, files: ["chatgpt.js"]});
            recovered = true;
            reply = await ping();
          } catch (_) {
            // Restricted pages, tab navigations, or Chrome policy can block injection.
          }
        }
        return {host: new URL(tab.url).hostname, contentScript: reply?.alive === true, version: reply?.version || null, recovered};
      }));
      sendResponse({tabs: results, extensionVersion: chrome.runtime.getManifest().version});
    });
    return true;
  }

  (async () => {
    const saved = await chrome.storage.local.get(["token", "activeProject", "project"]);
    if (!saved.token) {
      return {matched: false, error: "VibeBridge token missing. Open the extension popup and save your token."};
    }
    const active = message.activeProject || saved.activeProject || saved.project || "";

    if (message.type === "VIBEBRIDGE_BROWSER_HEARTBEAT") {
      let host = "";
      try { host = new URL(sender && sender.tab ? sender.tab.url : "").hostname; } catch (_) {}
      const response = await fetchAgent("/extension-status", {
        method: "POST",
        headers: {"Authorization": "Bearer " + saved.token, "Content-Type": "application/json"},
        body: JSON.stringify({version: chrome.runtime.getManifest().version, host, tabId: sender?.tab?.id})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not report browser extension status");
      return data;
    }
    if (message.type === "VIBEBRIDGE_BROWSER_STATUS") {
      const response = await fetchAgent("/diagnostics/local", {
        headers: {"Authorization": "Bearer " + saved.token},
        cache: "no-store"
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not read local diagnostics");
      return data.browserExtension || {connected: false, version: null, host: null, lastSeen: null};
    }

    if (message.type === "VIBEBRIDGE_LOCAL_DIAGNOSTICS") {
      const response = await fetchAgent("/diagnostics/local", {
        headers: {"Authorization": "Bearer " + saved.token}
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not inspect local VibeBridge services");
      return data;
    }

    if (message.type === "VIBEBRIDGE_CHECKPOINT_MESSAGE") {
      const payload = message.payload || {};
      const response = await fetchAgent("/checkpoint", {
        method: "POST",
        headers: {"Authorization": "Bearer " + saved.token, "Content-Type": "application/json"},
        body: JSON.stringify({
          summary: payload.summary,
          conversation: payload.conversation || "chat"
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Automatic checkpoint failed");
      return data;
    }

    if (message.type === "VIBEBRIDGE_FILESYSTEM_LIST") {
      const target = message.path || "";
      const url = new URL(API + "/filesystem/list");
      if (target) url.searchParams.set("path", target);
      const response = await fetchAgent(url.pathname + url.search, {
        headers: {"Authorization": "Bearer " + saved.token}
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not list folder");
      return {ok: true, ...data};
    }

    if (message.type === "VIBEBRIDGE_FILESYSTEM_READ") {
      if (typeof message.path !== "string" || !message.path) {
        throw new Error("A file path is required.");
      }
      const url = new URL(API + "/filesystem/read");
      url.searchParams.set("path", message.path);
      const response = await fetchAgent(url.pathname + url.search, {
        headers: {"Authorization": "Bearer " + saved.token}
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not read file");
      return {ok: true, ...data};
    }

    if (message.type === "VIBEBRIDGE_FILESYSTEM_WRITE") {
      if (typeof message.path !== "string" || !message.path ||
          typeof message.content !== "string") {
        throw new Error("A file path and text content are required.");
      }
      const response = await fetchAgent("/filesystem/write", {
        method: "POST",
        headers: {"Authorization": "Bearer " + saved.token, "Content-Type": "application/json"},
        body: JSON.stringify({path: message.path, content: message.content})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not write file");
      return {ok: true, ...data};
    }

    if (message.type === "VIBEBRIDGE_FILESYSTEM_MKDIR") {
      if (typeof message.path !== "string" || !message.path) {
        throw new Error("A folder path is required.");
      }
      const response = await fetchAgent("/filesystem/mkdir", {
        method: "POST",
        headers: {"Authorization": "Bearer " + saved.token, "Content-Type": "application/json"},
        body: JSON.stringify({path: message.path})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not create folder");
      return {ok: true, ...data};
    }

    if (message.type === "VIBEBRIDGE_CREATE_REPOSITORY") {
      const payload = message.payload || {};
      const response = await fetchAgent("/create-repository", {
        method: "POST",
        headers: {"Authorization": "Bearer " + saved.token, "Content-Type": "application/json"},
        body: JSON.stringify({name: payload.name, description: payload.description || "", private: payload.private !== false})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not create GitHub repository");
      const selected = data.project?.path || "github:" + data.repository.nameWithOwner;
      await chrome.storage.local.set({activeProject: selected, project: selected});
      return {ok: true, ...data};
    }

    if (message.type === "VIBEBRIDGE_REMEMBER") {
      if (!active) return {saved: false, error: "No active project. Mention its name first."};
      const response = await fetchAgent("/remember", {
        method: "POST",
        headers: {"Authorization": "Bearer " + saved.token, "Content-Type": "application/json"},
        body: JSON.stringify({project: active, note: message.note || ""})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not save project note");
      return data;
    }

    if (message.type === "VIBEBRIDGE_RUN_COMMAND") {
      if (!active) return {ok: false, error: "No active local project. Select one in the VibeBridge popup first."};
      const command = message.command;
      if (!Array.isArray(command) || !command.length ||
          command.length > 40 || !command.every(part => typeof part === "string" && part.length <= 4000)) {
        return {ok: false, error: "Invalid command. Expected an array of up to 40 text arguments."};
      }
      // This message is only sent after the user explicitly clicks Run in the ChatGPT page.
      const response = await fetchAgent("/run", {
        method: "POST",
        headers: {"Authorization": "Bearer " + saved.token, "Content-Type": "application/json"},
        body: JSON.stringify({project: active, command})
      }, 150000);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Local command failed");
      // HTTP 200 means the agent handled the request, not that the command succeeded.
      // Preserve stdout/stderr while exposing the process exit status to the UI.
      return {...data, ok: data.exitCode === 0};
    }

    const multiProject = message.type === "VIBEBRIDGE_RESOLVE_CONTEXTS";
    const response = await fetchAgent((multiProject ? "/contexts" : "/context"), {
      method: "POST",
      headers: {"Authorization": "Bearer " + saved.token, "Content-Type": "application/json"},
      body: JSON.stringify({
        message: message.text || "",
        active: message.activeProject || active,
        projects: Array.isArray(message.projects) ? message.projects.slice(0, 8) : []
      })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load project context");
    if (data.matched && data.project?.path) {
      await chrome.storage.local.set({activeProject: data.project.path, project: data.project.path});
    } else if (data.matched && Array.isArray(data.projects) && data.projects.length) {
      // Keep the first resolved project as the legacy active project for commands
      // and older popup features; conversation context itself can contain many.
      await chrome.storage.local.set({activeProject: data.projects[0].path, project: data.projects[0].path});
    }
    return data;
  })().then(sendResponse).catch(error => sendResponse({matched: false, ok: false, error: error.message}));
  return true;
});
