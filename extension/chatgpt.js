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
  const extensionVersion = chrome.runtime.getManifest?.().version || "unknown";
  const commandMarker = "VIBEBRIDGE LOCAL COMMAND";
  const processedBlocks = new WeakSet();
  // Never replay commands embedded in conversation history when a tab opens.
  // Hands-off execution is reserved for command blocks that appear after startup.
  let allowAutomaticExecution = false;

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

  let scannedBlocks = 0;
  let detectedBlocks = 0;
  function addCommandControls(allowAutoRun = false) {
    // Command blocks only arrive in the newest assistant turn. Avoid rescanning
    // every code block in a long conversation on each streaming mutation.
    const assistantMessages = document.querySelectorAll('[data-message-author-role="assistant"]');
    const latestAssistant = assistantMessages.length ? assistantMessages[assistantMessages.length - 1] : document;
    const blocks = latestAssistant.querySelectorAll('pre, [data-language], code');
    scannedBlocks = blocks.length;
    for (const pre of blocks) {
      const preBlock = pre.tagName === "PRE" ? pre : pre.closest("pre");
      const target = preBlock || pre;
      if (processedBlocks.has(pre) || processedBlocks.has(target)) continue;
      const code = target.querySelector("code") || (pre.tagName === "CODE" ? pre : null);
      const className = (code?.className || "") + " " + (target.className || "") + " " + (pre.className || "") + " " + (target.getAttribute?.("data-language") || "");
      const rawBlock = (code?.textContent || target.textContent || pre.textContent || "").trim();
      if (!rawBlock || rawBlock.length > 200000) continue;
      // ChatGPT may strip custom fence-language classes and preserve whitespace around
      // the marker. Match the marker at the start of the rendered code, then tolerate
      // an optional JSON code fence so the relay never asks the user to paste it in Terminal.
      const normalizedBlock = rawBlock.replace(/^\s+/, "");
      const markedBlock = normalizedBlock.startsWith(commandMarker);
      const hasCommandLanguage = /language-vibebridge-run|vibebridge-run/i.test(className);
      const hasShellLanguage = /language-(bash|sh|zsh|shell)\b/i.test(className);
      let payload = null;
      // Handle ChatGPT rendering custom vibebridge-run fences as plain text, including
      // an opening "vibebridge-run id=..." line before the JSON payload.
      if (!hasCommandLanguage && !markedBlock && !hasShellLanguage) {
        const jsonStart = normalizedBlock.indexOf("{");
        const jsonEnd = normalizedBlock.lastIndexOf("}");
        if (jsonStart >= 0 && jsonEnd > jsonStart) {
          try {
            const candidate = JSON.parse(normalizedBlock.slice(jsonStart, jsonEnd + 1));
            if (candidate && Array.isArray(candidate.command) && candidate.command.length &&
                candidate.command.every(part => typeof part === "string")) payload = candidate;
            else if (candidate && typeof candidate.command === "string" && candidate.command.trim()) {
              payload = {command: ["bash", "-lc", candidate.command]};
            }
          } catch {}
        }
        if (!payload) continue;
      }
      processedBlocks.add(pre);
      processedBlocks.add(target);
      detectedBlocks++;

      if (hasShellLanguage && !hasCommandLanguage && !markedBlock) {
        payload = {command: ["bash", "-lc", rawBlock.replace(/^\s*```(?:bash|sh|zsh|shell)\s*/i, "").replace(/\s*```$/, "").trim()]};
      } else if (!payload) {
        try {
          let jsonText = markedBlock ? normalizedBlock.slice(commandMarker.length).trim() : rawBlock;
          jsonText = jsonText.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "").trim();
          payload = JSON.parse(jsonText);
        } catch {
          const warning = document.createElement("div");
          warning.textContent = "VibeBridge command block is not valid JSON.";
          warning.style.cssText = "color:#b91c1c;font:12px system-ui;margin:6px 0";
          target.after(warning);
          continue;
        }
      }
      if (!payload || !Array.isArray(payload.command) || !payload.command.length ||
          !payload.command.every(part => typeof part === "string")) {
        const warning = document.createElement("div");
        warning.textContent = "VibeBridge command must contain a shell command or JSON command array.";
        warning.style.cssText = "color:#b91c1c;font:12px system-ui;margin:6px 0";
        pre.after(warning);
        continue;
      }

      const panel = document.createElement("div");
      panel.className = "vibebridge-injected-control";
      panel.style.cssText = "margin:8px 0;padding:10px;border:1px solid #64748b;border-radius:8px;font:13px system-ui";
      const description = document.createElement("div");
      description.textContent = "VibeBridge can run this command in the active local project.";
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

      const executeCommand = async (automatic = false) => {
        if (run.disabled) return;
        if (!automatic && !confirm("Run this command on your Mac inside the active project folder?\n\n" + payload.command.join(" "))) return;
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
          if (automatic) {
            const composer = document.querySelector("#prompt-textarea") || document.querySelector('textarea[placeholder]') || document.querySelector('[contenteditable="true"][role="textbox"]');
            if (!composer) throw new Error("Command ran, but ChatGPT prompt field was not found. Result is shown below.");
            const addition = "\n\nVIBEBRIDGE COMMAND RESULT\nCommand: " + payload.command.join(" ") + "\nResult JSON:\n" + resultText + "\n\nInspect this result and continue development. If another local command is needed, emit another VIBEBRIDGE LOCAL COMMAND block.";
            writeComposer(composer, readComposer(composer).trim() + addition);
            const send = document.querySelector('button[data-testid="send-button"]') || document.querySelector('button[aria-label*="Send"]');
            if (send && !send.disabled) { bypassNextSend = true; send.click(); setTimeout(() => { bypassNextSend = false; }, 800); } else { showNotice("Command result is ready in the prompt; send it to continue."); }
          }
        } catch (error) {
          const message = error?.message || String(error);
          if (/extension context invalidated|context invalidated|receiving end does not exist/i.test(message)) {
            output.textContent = "VibeBridge's extension context was invalidated by an extension reload. Reload this ChatGPT tab, then resend your message. This command was not confirmed as executed.";
            run.textContent = "Reload ChatGPT tab";
            run.disabled = false;
            run.onclick = () => location.reload();
            showNotice("Extension updated. Reload this ChatGPT tab before continuing.");
            return;
          }
          output.textContent = message;
          run.textContent = "Retry command";
          run.disabled = false;
        }
      };
      run.addEventListener("click", () => executeCommand(false));
      chrome.storage.local.get(["autoRunCommands"], settings => {
        if (allowAutoRun && allowAutomaticExecution && settings.autoRunCommands === true) {
          description.textContent = "Hands-off mode is enabled: this command will run automatically on your Mac, then its result will be sent back to ChatGPT.";
          run.textContent = "Run automatically";
          executeCommand(true);
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
      target.after(panel);
    }
  }

  // Expose a small live diagnostic so the page proves the current content script loaded.
  function ensureBridgeStatus() {
    let status = document.getElementById("vibebridge-live-status");
    if (!status) {
      status = document.createElement("div");
      status.id = "vibebridge-live-status";
      status.style.cssText = "position:fixed;right:12px;bottom:12px;z-index:999998;padding:5px 8px;border-radius:6px;background:#172033;color:#fff;font:11px system-ui;opacity:.82";
      document.documentElement.appendChild(status);
    }
    const nextText = "VibeBridge " + extensionVersion + " · blocks " + scannedBlocks + " · commands " + detectedBlocks;
    const nextTitle = "Content script active. Scanned code blocks: " + scannedBlocks + ". Recognized command blocks: " + detectedBlocks + ".";
    // Avoid triggering our own subtree MutationObserver indefinitely. Reassigning
    // textContent replaces child nodes even when the displayed string is unchanged.
    if (status.textContent !== nextText) status.textContent = nextText;
    if (status.title !== nextTitle) status.title = nextTitle;
  }
  ensureBridgeStatus();
  addCommandControls(false);

  // ChatGPT streams many DOM mutations per token. Debounce scans so we do not
  // repeatedly traverse the entire conversation tree while a response is rendering.
  let scanTimer = null;
  let scanRunning = false;
  let scanAgain = false;
  async function runScheduledScan() {
    if (scanRunning) { scanAgain = true; return; }
    scanRunning = true;
    try {
      ensureBridgeStatus();
      addCommandControls(true);
      await saveAssistantCheckpoints();
    } finally {
      scanRunning = false;
      if (scanAgain) {
        scanAgain = false;
        scheduleScan();
      }
    }
  }
  function scheduleScan() {
    if (scanTimer !== null) clearTimeout(scanTimer);
    scanTimer = setTimeout(() => {
      scanTimer = null;
      void runScheduledScan();
    }, 180);
  }
  const observer = new MutationObserver((mutations) => {
    // Ignore mutations caused only by our own status badge and injected controls.
    const relevant = mutations.some(mutation => {
      const node = mutation.target?.nodeType === Node.ELEMENT_NODE
        ? mutation.target
        : mutation.target?.parentElement;
      return !node?.closest?.("#vibebridge-live-status, .vibebridge-injected-control");
    });
    if (relevant) scheduleScan();
  });
  observer.observe(document.documentElement, {childList: true, subtree: true, characterData: true});
  // Existing assistant messages are rendered first and only receive manual Run controls.
  // Subsequent command blocks can use hands-off mode.
  addCommandControls(false);
  allowAutomaticExecution = true;

  document.addEventListener("click", async event => {
    const button = event.target.closest('button[data-testid="send-button"], button[aria-label*="Send"], button[type="submit"]');
    if (!button || bypassNextSend || busy) return;
    const composer = composerFor(button);
    const original = readComposer(composer).trim();
    if (!enabledState || !original || original.includes(marker) || original.includes("VIBEBRIDGE DISABLED")) return;
    // When VibeBridge is enabled, resolve context for every user message. Short
    // follow-ups like “you should” and “it should” still depend on project history.

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
        const conversation = conversationKey();
        const savedConversation = await chrome.storage.local.get(["conversationProjects"]);
        const prior = savedConversation.conversationProjects?.[conversation] || [];
        const knownProjects = (Array.isArray(prior) ? prior : [prior]).filter(Boolean);
        result = await chrome.runtime.sendMessage({
          type: "VIBEBRIDGE_RESOLVE_CONTEXTS",
          text: original,
          projects: knownProjects.map(path => ({path})),
          activeProject: knownProjects[0] || ""
        });
      }
      const rememberMatch = original.match(/remember (?:for this project|this for the project|that for this project)[:\-]?\s*(.+)/i);
      if (rememberMatch && rememberMatch[1]) {
        const saved = await chrome.runtime.sendMessage({type: "VIBEBRIDGE_REMEMBER", note: rememberMatch[1].trim()});
        if (saved?.saved) showNotice("Saved a note to " + saved.project + " project memory");
        else if (saved?.error) showNotice("VibeBridge memory: " + saved.error);
      }
      if (result?.matched && result.context) {
        const conversation = conversationKey();
        const savedConversation = await chrome.storage.local.get(["conversationProjects"]);
        const conversationProjects = savedConversation.conversationProjects || {};
        const previous = conversationProjects[conversation] || [];
        const merged = (Array.isArray(previous) ? previous : [previous]).filter(Boolean);
        const resolvedProjects = Array.isArray(result.projects) ? result.projects : (result.project ? [result.project] : []);
        for (const project of resolvedProjects) {
          if (project?.path && !merged.includes(project.path)) merged.push(project.path);
        }
        conversationProjects[conversation] = merged.slice(-8);
        await chrome.storage.local.set({conversationProjects});
        const projectNames = resolvedProjects.map(project => project.name).filter(Boolean);
        const addition = marker + "\nVIBEBRIDGE PROJECT CONTINUITY: The context below may contain multiple projects discussed in this ChatGPT conversation. Keep their memories separate; never merge their decisions or todos across repositories. Use the latest detailed handoff to resume work, including exact stopping point, files changed, tests run and results, unresolved failures, blockers, decisions, open todos, and next action. Keep the durable summary concise but preserve a more detailed rolling handoff and prioritized todo list. Verify code before treating a claim as implemented. Do not ask the user to repeat recorded context.\n\n" + result.context + "\n\nEND " + marker + "\n\nVIBEBRIDGE MEMORY INSTRUCTION: After every response, include a fenced JSON block labelled vibebridge-memory with this schema: {\"projects\":[{\"repository\":\"owner/repo\",\"summary\":\"durable project purpose, architecture, decisions, constraints and current state\",\"handoff\":\"detailed latest stopping point, files changed, tests/results, failures and exact next action\",\"todos\":[{\"task\":\"specific action\",\"status\":\"open|blocked|done\",\"priority\":\"high|medium|low\",\"blocker\":\"reason or empty string\"}],\"decisions\":[\"durable decisions\"],\"updated\":\"ISO-8601 timestamp\"}]}. Include every project materially discussed or changed, using its exact GitHub owner/repository slug. Preserve unfinished todos; mark completed tasks done rather than deleting history without reason. Update the handoff every response, even when the summary barely changes. Never invent repository slugs or test results; omit unknown slugs and explain the gap in normal response. Do not include raw transcripts, secrets, or personal data. This is a rolling handoff, not a transcript.\n\nUSER REQUEST:\n";
        writeComposer(composer, addition + original);
        showNotice(createdRepository ? "Created " + createdRepository.nameWithOwner + " and loaded project context." : "VibeBridge attached context for " + (projectNames.join(", ") || "the current project"));
      } else if (result?.ambiguous) {
        showNotice("VibeBridge found multiple possible projects. Mention the exact project name.");
      } else if (result?.error) {
        showNotice("VibeBridge: " + result.error + "\nYour original message will still be sent. Check the local agent and GitHub CLI connection in the extension popup.");
      } else {
        showNotice("VibeBridge did not attach project context. No matching project was found; your original message will still be sent. Try the exact repository name or owner/repository.");
      }
    } catch (error) {
      const message = String(error?.message || error || "Unknown error");
      const invalidated = /extension context invalidated|context invalidated|extension context.*invalid/i.test(message);
      showNotice(invalidated
        ? "VibeBridge's Chrome extension context was invalidated. This usually happens after an extension update or reload. This page's content script cannot be revived from inside the invalidated context. Refresh this ChatGPT tab to load VibeBridge again, then resend your message. Your original message has not been context-enriched."
        : "VibeBridge could not load project context: " + message + "\nYour original message will still be sent without project context. Check the local agent and GitHub CLI connection in the extension popup.");
    } finally {
      busy = false;
      button.disabled = false;
      bypassNextSend = true;
      button.click();
      setTimeout(() => { bypassNextSend = false; }, 800);
    }
  }, true);
})();
