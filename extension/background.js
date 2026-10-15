const API = "http://127.0.0.1:43127";

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "VIBEBRIDGE_RESOLVE_CONTEXT") return;
  (async () => {
    const saved = await chrome.storage.local.get(["token", "activeProject", "project"]);
    if (!saved.token) return {matched: false, error: "VibeBridge token missing. Open the extension popup and save your token."};
    const active = saved.activeProject || saved.project || "";
    const response = await fetch(API + "/context", {
      method: "POST",
      headers: {"Authorization": "Bearer " + saved.token, "Content-Type": "application/json"},
      body: JSON.stringify({message: message.text || "", active})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load project context");
    if (data.matched && data.project?.path) {
      await chrome.storage.local.set({activeProject: data.project.path, project: data.project.path});
    }
    return data;
  })().then(sendResponse).catch(error => sendResponse({matched: false, error: error.message}));
  return true;
});
