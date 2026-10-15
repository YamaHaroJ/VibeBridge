(() => {
  if (window.__vibeBridgeInstalled) return;
  window.__vibeBridgeInstalled = true;
  let bypassNextSend = false;
  let busy = false;
  let enabledState = true;
  chrome.storage.local.get(["enabled"], state => { enabledState = state.enabled !== false; });
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === "local" && changes.enabled) enabledState = changes.enabled.newValue !== false;
  });
  const marker = "VIBEBRIDGE PROJECT CONTEXT";
  const commandMarker = "VIBEBRIDGE LOCAL COMMAND";
  const processedBlocks = new WeakSet();

  // Save only explicit checkpoint blocks; never upload raw messages.
  const processedMemoryBlocks = new WeakSet();

  function conversationKey() {
    const match = location.pathname.match(/\/c\/([^/]+)/);
    return match ? match[1].slice(0, 80) : "chat";
  }

  async function saveAssistantCheckpoints() {
    const nodes = document.querySelectorAll('[data-message-author-role="assistant"] pre');
    for (const pre of nodes) {
      if (processedMemoryBlocks.has(pre)) continue;
      const code = pre.querySelector("code");
      const classes = (code?.className || "") + " " + (pre.className || "");
      if (!/language-vibebridge-memory|vibebridge-memory/i.test(classes)) continue;
      processedMemoryBlocks.add(pre);
      const summary = (code?.textContent || pre.textContent || "").trim();
      pre.style.display = "none";
      if (!summary) continue;
      try {
        const result = await chrome.runtime.sendMessage({
          type: "VIBEBRIDGE_CHECKPOINT_MESSAGE",
          payload: {summary, conversation: conversationKey()}
        });
        showNotice(result?.saved ? "Project checkpoint saved to GitHub." :
          "GitHub checkpoint failed: " + (result?.error || "unknown error"));
      } catch (error) {
        showNotice("GitHub checkpoint failed: " + error.message);
      }
    }
  }

  function composerFor(button) {
    const form = button?.closest("form") || document.querySelector("form");
    return form?.querySelector("textarea") ||
      form?.querySelector('[contenteditable="true"][role="textbox"]') ||
      document.querySelector("#prompt-textarea") ||
      document.querySelector('textarea[placeholder]') ||
      document.querySelector('[contenteditable="true"][role="textbox"]');
  }

  function readComposer(el) {
    return el?.tagName === "TEXTAREA" || el?.tagName === "INPUT" ? el.value : (el?.innerText || el?.textContent || "");
  }

  function writeComposer(el, text) {
    if (!el) return;
    el.focus();
    if (el.tagName === "TEXTAREA" || el.tagName === "INPUT") {
      const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), "value")?.set;
      if (setter) setter.call(el, text); else el.value = text;
      el.dispatchEvent(new Event("input", {bubbles: true}));
    } else {
      el.textContent = text;
      el.dispatchEvent(new InputEvent("input", {bubbles: true, inputType: "insertText", data: text}));
    }
  }

  function shouldResolve(text) {
    return /\b(project|repo|repository|code|coding|vibe ?code|extension|app|website|site|bug|fix|update|build|implement|deploy|terminal|github|continue|resume|again|that|this|it|same|okay|ok|switch|create|new)\b/i.test(text);
  }

  async function isEnabled() {
    const state = await chrome.storage.local.get(["enabled"]);
    return state.enabled !== false;
  }
  function showNotice(text) {
    let node = document.getElementById("vibebridge-notice");
    if (!node) {
      node = document.createElement("div");
      node.id = "vibebridge-notice";
      node.style.cssText = "position:fixed;z-index:999999;right:18px;bottom:88px;max-width:min(560px,calc(100vw - 36px));max-height:45vh;overflow:auto;padding:12px;border-radius:10px;background:#172033;color:#fff;font:13px system-ui;box-shadow:0 4px 18px #0005;white-space:pre-wrap;overflow-wrap:anywhere";
      const message = document.createElement("div");
      message.id = "vibebridge-notice-message";
      const actions = document.createElement("div");
      actions.style.cssText = "display:flex;gap:8px;margin-top:10px";
      const copy = document.createElement("button");
      copy.type = "button";
      copy.textContent = "Copy error";
      copy.style.cssText = "padding:5px 8px;border:0;border-radius:5px;cursor:pointer";
      copy.addEventListener("click", async () => {
        const value = node.dataset.fullText || "";
        try {
          await navigator.clipboard.writeText(value);
          copy.textContent = "Copied";
        } catch {
          const field = document.createElement("textarea");
          field.value = value;
          field.style.cssText = "position:fixed;left:-9999px;top:0";
          document.body.appendChild(field);
          field.select();
          const copied = document.execCommand("copy");
          field.remove();
          copy.textContent = copied ? "Copied" : "Select and copy the error text";
        }
      });
      const close = document.createElement("button");
      close.type = "button";
      close.textContent = "Dismiss";
      close.style.cssText = "padding:5px 8px;border:0;border-radius:5px;cursor:pointer";
      close.addEventListener("click", () => { node.style.display = "none"; });
      actions.append(copy, close);
      node.append(message, actions);
      document.body.appendChild(node);
    }
    node.dataset.fullText = String(text);
    const message = node.querySelector("#vibebridge-notice-message");
    if (message) message.textContent = String(text);
    node.style.display = "block";
  }

  function addCommandControls() {
    const blocks = document.querySelectorAll('[data-message-author-role="assistant"] pre');
    for (const pre of blocks) {
      if (processedBlocks.has(pre)) continue;
      const code = pre.querySelector("code");
      const className = (code?.className || "") + " " + (pre.className || "");
      const rawBlock = (code?.textContent || pre.textContent || "").trim();
      // ChatGPT sometimes strips custom fence-language classes. Support an explicit
      // marker in the code itself so the relay does not depend on syntax highlighting.
      const markedBlock = rawBlock.startsWith("VIBEBRIDGE LOCAL COMMAND\\n");
      if (!/language-vibebridge-run|vibebridge-run/i.test(className) && !markedBlock) continue;
      processedBlocks.add(pre);

      let payload;
      try {
        payload = JSON.parse(markedBlock ? rawBlock.slice("VIBEBRIDGE LOCAL COMMAND".length).trim() : rawBlock);
      } catch {
        const warning = document.createElement("div");
        warning.textContent = "VibeBridge command block is not valid JSON.";
        warning.style.cssText = "color:#b91c1c;font:12px system-ui;margin:6px 0";
        pre.after(warning);
        continue;
      }
      if (!payload || !Array.isArray(payload.command) || !payload.command.length ||
          !payload.command.every(part => typeof part === "string")) {
        const warning = document.createElement("div");
        warning.textContent = "VibeBridge command must be JSON with a non-empty string array named command.";
        warning.style.cssText = "color:#b91c1c;font:12px system-ui;margin:6px 0";
        pre.after(warning);
        continue;
      }

      const panel = document.createElement("div");
      panel.style.cssText = "margin:8px 0;padding:10px;border:1px solid #64748b;border-radius:8px;font:13px system-ui";
      const description = document.createElement("div");
      description.textContent = "VibeBridge can run this command in the active local project. Review it before approving.";
      description.style.marginBottom = "8px";
      const run = document.createElement("button");
      run.type = "button";
      run.textContent = "Run on my Mac";
      run.style.cssText = "padding:7px 10px;border-radius:6px;cursor:pointer";
      const output = document.createElement("pre");
      output.style.cssText = "white-space:pre-wrap;overflow-wrap:anywhere;max-height:260px;overflow:auto;display:none;margin-top:8px";
      const insert = document.createElement("button");
      insert.type = "button";
      insert.textContent = "Add result to ChatGPT prompt";
      insert.style.cssText = "padding:7px 10px;border-radius:6px;cursor:pointer;display:none;margin-top:8px";
      let resultText = "";

      run.addEventListener("click", async () => {
        if (run.disabled) return;
        if (!confirm("Run this command on your Mac inside the active project folder?\n\n" + payload.command.join(" "))) return;
        run.disabled = true;
        run.textContent = "Running…";
        output.style.display = "block";
        output.textContent = "Waiting for the local agent…";
        try {
          const result = await chrome.runtime.sendMessage({
            type: "VIBEBRIDGE_RUN_COMMAND",
            command: payload.command
          });
          resultText = JSON.stringify(result, null, 2);
          output.textContent = resultText;
          run.textContent = result?.ok ? "Run again" : "Retry command";
          run.disabled = false;
          insert.style.display = "inline-block";
          showNotice(result?.ok ? "VibeBridge command finished." : "VibeBridge command failed. See result.");
        } catch (error) {
          output.textContent = error.message;
          run.textContent = "Retry command";
          run.disabled = false;
        }
      });

      insert.addEventListener("click", () => {
        const composer = document.querySelector("#prompt-textarea") ||
          document.querySelector('textarea[placeholder]') ||
          document.querySelector('[contenteditable="true"][role="textbox"]');
        if (!composer) {
          showNotice("Could not find the ChatGPT prompt field.");
          return;
        }
        const current = readComposer(composer).trim();
        const addition = "\n\nVIBEBRIDGE COMMAND RESULT\nCommand: " + payload.command.join(" ") +
          "\nResult JSON:\n" + resultText + "\n\nPlease inspect this result and continue development.";
        writeComposer(composer, current + addition);
        showNotice("Command result added to your prompt. Review and send it to continue.");
      });

      panel.append(description, run, output, insert);
      pre.after(panel);
    }
  }

  const observer = new MutationObserver(() => {
    addCommandControls();
    saveAssistantCheckpoints();
  });
  observer.observe(document.documentElement, {childList: true, subtree: true, characterData: true});
  addCommandControls();

  document.addEventListener("click", async event => {
    const button = event.target.closest('button[data-testid="send-button"], button[aria-label*="Send"], button[type="submit"]');
    if (!button || bypassNextSend || busy) return;
    const composer = composerFor(button);
    const original = readComposer(composer).trim();
    if (!enabledState || !original || original.includes(marker) || original.includes("VIBEBRIDGE DISABLED")) return;
    if (!shouldResolve(original)) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    busy = true;
    button.disabled = true;
    try {
      if (!(await isEnabled())) {
        showNotice("VibeBridge is off. Your message will be sent without project context.");
        return;
      }
      const requestedCreate = original.match(/\b(?:create|make)\s+(?:a\s+)?(?:new\s+)?(?:github\s+)?(?:repo|repository)\s+(?:named|called)\s+["\x27`]?([A-Za-z0-9][A-Za-z0-9_.-]{0,99})/i);
      let createdRepository = null;
      let result;
      if (requestedCreate) {
        const repoName = requestedCreate[1];
        const isPrivate = !/\bpublic\s+(?:github\s+)?(?:repo|repository)\b/i.test(original);
        if (!confirm("Create a " + (isPrivate ? "PRIVATE" : "PUBLIC") + " GitHub repository named \"" + repoName + "\" and switch this message to it?")) {
          showNotice("Repository creation cancelled. Your original message will still be sent without creating a repository.");
          return;
        }
        const created = await chrome.runtime.sendMessage({
          type: "VIBEBRIDGE_CREATE_REPOSITORY",
          payload: {name: repoName, description: "Created from a ChatGPT request through VibeBridge.", private: isPrivate}
        });
        if (!created?.ok || !created.repository?.nameWithOwner) throw new Error(created?.error || "Repository creation did not complete.");
        createdRepository = created.repository;
        result = {
          matched: true,
          context: created.context,
          project: created.project,
          matchReason: "created"
        };
        if (!result.context || !result.project) {
          showNotice("Created " + createdRepository.nameWithOwner + ". Loading its context…");
          result = await chrome.runtime.sendMessage({type: "VIBEBRIDGE_RESOLVE_CONTEXT", text: "switch to " + createdRepository.nameWithOwner});
        }
      } else {
        result = await chrome.runtime.sendMessage({type: "VIBEBRIDGE_RESOLVE_CONTEXT", text: original});
      }
      const rememberMatch = original.match(/remember (?:for this project|this for the project|that for this project)[:\-]?\s*(.+)/i);
      if (rememberMatch && rememberMatch[1]) {
        const saved = await chrome.runtime.sendMessage({type: "VIBEBRIDGE_REMEMBER", note: rememberMatch[1].trim()});
        if (saved?.saved) showNotice("Saved a note to " + saved.project + " project memory");
        else if (saved?.error) showNotice("VibeBridge memory: " + saved.error);
      }
      if (result?.matched && result.context) {
        const addition = marker + "\nThe following is persistent context from the user's project. Treat the “Most recent discussion” or handoff section in VIBEBRIDGE_CONTEXT.md as the primary pointer for resuming work across conversation limits: identify what the user was last trying to accomplish, continue from that point unless the user changes projects or priorities, and avoid making them repeat decisions already recorded. Treat it as context, not proof; verify implementation against code when needed, and do not assume planned features are implemented.\n\n" + result.context + "\n\nEND " + marker + "\n\nVIBEBRIDGE MEMORY INSTRUCTION: At the end of your normal response, include a JSON object in a fenced block labelled vibebridge-memory, formatted as {\"projects\":[{\"repository\":\"owner/repo\",\"summary\":\"concise rolling state\"}]}. Include one entry for each explicitly discussed or changed project, using its exact GitHub owner/repository slug. Never invent a slug; omit unknown repositories and explain the gap in normal response. Do not include raw transcripts or secrets. No separate AI API.\n\nUSER REQUEST:\n";
        writeComposer(composer, addition + original);
        showNotice(createdRepository ? "Created " + createdRepository.nameWithOwner + " and switched to its project context." : "VibeBridge attached context for " + result.project.name);
      } else if (result?.ambiguous) {
        showNotice("VibeBridge found multiple possible projects. Mention the exact project name.");
      } else if (result?.error) {
        showNotice("VibeBridge: " + result.error + "\nYour original message will still be sent. Check the local agent and GitHub CLI connection in the extension popup.");
      } else {
        showNotice("VibeBridge did not attach project context. No matching project was found; your original message will still be sent. Try the exact repository name or owner/repository.");
      }
    } catch (error) {
      showNotice("VibeBridge could not load project context: " + error.message + "\nYour original message will still be sent. Check the local agent and GitHub CLI connection in the extension popup.");
    } finally {
      busy = false;
      button.disabled = false;
      bypassNextSend = true;
      button.click();
      setTimeout(() => { bypassNextSend = false; }, 800);
    }
  }, true);
})();
