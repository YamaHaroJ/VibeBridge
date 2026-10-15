const token = document.querySelector("#token");
const project = document.querySelector("#project");
const result = document.querySelector("#result");
const projectList = document.querySelector("#project-list");
const enabled = document.querySelector("#enabled");

chrome.storage.local.get(["enabled"], v => { enabled.checked = v.enabled !== false; });
enabled.addEventListener("change", async () => {
  await chrome.storage.local.set({enabled: enabled.checked});
  result.textContent = enabled.checked ? "VibeBridge is on." : "VibeBridge is off. Your ChatGPT messages will be sent without automatic project context.";
});

document.querySelector("#github-settings").onclick = () => {
  chrome.tabs.create({url: "https://chatgpt.com/#settings/Apps"});
};
document.querySelector("#connection-guide").onclick = async () => {
  try {
    const health = await call("/health");
    const repos = await call("/github-projects");
    result.textContent = "Local agent: connected (" + health.port + ").\nGitHub CLI: connected; " + (repos.repositories || []).length + " repositories visible.\nChatGPT GitHub connector is separate: open ChatGPT Settings → Apps/Connectors and connect GitHub there if you want ChatGPT itself to browse repositories. VibeBridge cannot inspect or change that setting.";
  } catch (e) {
    result.textContent = "Setup check failed: " + e.message + "\nCheck the local agent/token and make sure GitHub CLI is installed and authenticated with `gh auth status`.";
  }
};

chrome.storage.local.get(["token", "project"], v => {
  token.value = v.token || "";
  project.value = v.project || "";
});

document.querySelector("#save").onclick = () =>
  chrome.storage.local.set({token: token.value.trim(), project: project.value.trim()}, () => {
    result.textContent = "Settings saved locally.";
  });


async function call(path, body) {
  const v = await chrome.storage.local.get(["token", "project"]);
  if (!v.token) throw new Error("Enter your local agent token first.");
  const options = {headers: {"Authorization": "Bearer " + v.token}};
  if (body) {
    options.method = "POST";
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const r = await fetch("http://127.0.0.1:43127" + path, options);
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || "Request failed");
  return data;
}

document.querySelector("#discover").onclick = async () => {
  try {
    const data = await call("/projects");
    projectList.replaceChildren();
    for (const item of data.projects) {
      const option = document.createElement("option");
      option.value = item.name;
      option.label = item.path;
      projectList.appendChild(option);
    }
    result.textContent = data.projects.length
      ? "Found projects:\n" + data.projects.map(p => p.name + " — " + p.path).join("\n")
      : "No projects found in the configured project folders.";
    if (!project.value && data.projects.length === 1) project.value = data.projects[0].name;
  } catch (e) {
    result.textContent = e.message;
  }
};

document.querySelector("#health").onclick = async () => {
  try { result.textContent = JSON.stringify(await call("/health"), null, 2); }
  catch (e) { result.textContent = e.message; }
};

document.querySelector("#diagnostics").onclick = async () => {
  try {
    const v = await chrome.storage.local.get(["project"]);
    result.textContent = JSON.stringify(await call("/diagnostics", {project: v.project}), null, 2);
  } catch (e) {
    result.textContent = e.message;
  }
};


document.querySelector("#github-discover").onclick = async () => {
  const select = document.querySelector("#github-repo");
  try {
    result.textContent = "Loading repositories from your GitHub account…";
    const data = await call("/github-projects");
    select.replaceChildren();
    const repos = data.repositories || [];
    for (const repo of repos) {
      const option = document.createElement("option");
      option.value = repo.nameWithOwner;
      const flags = [
        repo.localPath ? "already local" : "not cloned",
        repo.isPrivate ? "private" : "public",
        repo.isArchived ? "archived" : ""
      ].filter(Boolean).join(" · ");
      option.textContent = repo.nameWithOwner + " — " + flags;
      option.title = repo.description || repo.url || repo.nameWithOwner;
      select.appendChild(option);
    }
    result.textContent = repos.length
      ? "Found " + repos.length + " GitHub repositories visible to your authenticated GitHub CLI account. Select one to clone if it isn't already on this Mac."
      : "No repositories returned by GitHub CLI for the authenticated account.";
  } catch (e) {
    result.textContent = "Could not load GitHub repositories: " + e.message;
  }
};

document.querySelector("#clone-repo").onclick = async () => {
  const select = document.querySelector("#github-repo");
  const repository = select.value;
  if (!repository) {
    result.textContent = "First click Find GitHub repositories and select a repository.";
    return;
  }
  const option = select.options[select.selectedIndex];
  if (option?.textContent.includes("already local")) {
    result.textContent = repository + " is already cloned on this Mac. Use Find local projects to select its local folder.";
    return;
  }
  if (!confirm("Clone " + repository + " into ~/Projects on this Mac?")) return;
  try {
    result.textContent = "Cloning " + repository + "…";
    const data = await call("/clone", {repository});
    project.value = data.project.path;
    await chrome.storage.local.set({project: data.project.path, activeProject: data.project.path});
    result.textContent = "Cloned " + data.repository + " to " + data.project.path + " and selected it as the active project.";
  } catch (e) {
    result.textContent = "Could not clone repository: " + e.message;
  }
};


document.querySelector("#update").onclick = async () => {
  if (!confirm("Update VibeBridge from GitHub? The updater will stop if it detects local uncommitted changes. It will validate the code before restarting the agent.")) return;
  try {
    result.textContent = "Starting safe update…";
    const data = await call("/update", {});
    result.textContent = data.message || "Update started. Click Check update status in a few seconds.";
  } catch (e) {
    result.textContent = "Could not start update: " + e.message;
  }
};

document.querySelector("#update-status").onclick = async () => {
  try {
    const data = await call("/update-status");
    result.textContent = data.log?.length ? data.log.join("\n") : "No update log yet.";
  } catch (e) {
    result.textContent = "Could not read update status: " + e.message;
  }
};

document.querySelector("#create-repo").onclick = async () => {
  const name = prompt("New GitHub repository name (letters, numbers, periods, hyphens, underscores):");
  if (!name) return;
  const description = prompt("Short description (optional):") || "";
  const isPrivate = confirm("Make this repository PRIVATE? Choose Cancel for PUBLIC.");
  if (!confirm("Create GitHub repository \"" + name + "\" as " + (isPrivate ? "PRIVATE" : "PUBLIC") + "?")) return;
  try {
    result.textContent = "Creating GitHub repository…";
    const data = await call("/create-repository", {name, description, private: isPrivate});
    const selected = data.project?.path || "github:" + data.repository.nameWithOwner;
    project.value = selected;
    await chrome.storage.local.set({project: selected, activeProject: selected, lastCreatedRepository: data.repository.nameWithOwner});
    const select = document.querySelector("#github-repo");
    const option = document.createElement("option");
    option.value = data.repository.nameWithOwner;
    option.textContent = data.repository.nameWithOwner + " — created · " + (isPrivate ? "private" : "public") + " · not cloned";
    option.selected = true;
    select.prepend(option);
    result.textContent = data.message + "\n" + data.repository.url + "\n\nSelected as the active project. You can now describe changes directly in ChatGPT."; 
    try { await navigator.clipboard.writeText(data.repository.nameWithOwner); } catch {}
  } catch (e) {
    result.textContent = "Could not create repository: " + e.message;
  }
};
document.querySelector("#test-switch").onclick = async () => {
  const name = prompt("Enter a repository name or owner/repository to test switching:");
  if (!name) return;
  try {
    result.textContent = "Testing project resolution for " + name + "…";
    const first = await call("/context", {message: "Switch to " + name, active: "VibeBridge"});
    if (!first.matched || !first.context) throw new Error(first.error || "The project was not resolved. Details: " + JSON.stringify(first));
    const second = await call("/context", {message: "Switch to VibeBridge", active: first.project.path});
    if (!second.matched || !second.context || !/VibeBridge/i.test(second.project.name || "")) {
      throw new Error("Switch back to VibeBridge failed. Details: " + JSON.stringify(second));
    }
    result.textContent = "PASS: first switch resolved " + first.project.name + " (" + first.matchReason + "), then switched back to " + second.project.name + ".\n\nFirst context preview:\n" + first.context.slice(0, 1200);
  } catch (e) {
    result.textContent = "FAIL: " + e.message + "\n\nCopy this diagnostic text and send it to ChatGPT.";
  }
};
