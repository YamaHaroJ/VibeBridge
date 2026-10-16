(() => {
  const loadedFileVersion = chrome.runtime.getManifest?.().version || "unknown";
  const extensionVersion = loadedFileVersion;
  window.__vibeBridgeLoadedFileVersion = loadedFileVersion;
  // Keep a lightweight ping/heartbeat endpoint available even when this file is
  // injected into a tab that already has an older content-script instance.
  if (!window.__vibeBridgePingInstalled) {
    window.__vibeBridgePingInstalled = true;
    chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
      if (message?.type !== "VIBEBRIDGE_CONTENT_SCRIPT_PING") return;
      chrome.runtime.sendMessage({type: "VIBEBRIDGE_BROWSER_HEARTBEAT"}).then(() => {
        sendResponse({alive: true, version: window.__vibeBridgeLoadedFileVersion || loadedFileVersion, coreVersion: window.__vibeBridgeInstalledVersion || "not-installed", host: location.hostname});
      }).catch(() => {
        sendResponse({alive: true, version: window.__vibeBridgeLoadedFileVersion || loadedFileVersion, coreVersion: window.__vibeBridgeInstalledVersion || "not-installed", host: location.hostname, heartbeatError: true});
      });
      return true;
    });
  }
  function reportHeartbeatFromThisFile() {
    chrome.runtime.sendMessage({type: "VIBEBRIDGE_BROWSER_HEARTBEAT"}).catch(() => {});
  }
  reportHeartbeatFromThisFile();
  if (window.__vibeBridgeHeartbeatTimer) window.clearInterval(window.__vibeBridgeHeartbeatTimer);
  window.__vibeBridgeHeartbeatTimer = window.setInterval(reportHeartbeatFromThisFile, 30000);
  if (window.__vibeBridgeInstalled) return;
  window.__vibeBridgeInstalled = true;
  window.__vibeBridgeInstalledVersion = loadedFileVersion;
  let bypassNextSend = false;
  let busy = false;
  let enabledState = true;
  chrome.storage.local.get(["enabled"], state => { enabledState = state.enabled !== false; });
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === "local" && changes.enabled) enabledState = changes.enabled.newValue !== false;
  });
  const marker = "VIBEBRIDGE PROJECT CONTEXT";
  window.addEventListener("pageshow", reportHeartbeatFromThisFile);
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
    // Check only the newest assistant response; scanning historical messages on
    // every streaming mutation scales poorly on long development conversations.
    const messages = document.querySelectorAll('[data-message-author-role="assistant"]');
    const latest = messages.length ? messages[messages.length - 1] : null;
    if (!latest) return;
    const nodes = latest.querySelectorAll('pre');
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

  // Never rewrite the user's visible ChatGPT draft to clean up stale context.
  // If a legacy build left a context wrapper in the editor, leave it untouched
  // for explicit user review. Automatic cleanup was itself a composer mutation.
  function sanitizeBridgeComposer(_el) {
    return false;
  }

  function writeComposer(el, text) {
    if (!el) return;
    el.focus();
    if (el.tagName === "TEXTAREA" || el.tagName === "INPUT") {
      const prototype = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
      if (setter) setter.call(el, text); else el.value = text;
      el.dispatchEvent(new InputEvent("input", {bubbles: true, inputType: "insertText", data: text}));
      el.dispatchEvent(new Event("change", {bubbles: true}));
      return;
    }

    // Do not replace contenteditable textContent: that destroys ChatGPT's
    // editor structure and can break subsequent typing/paste. Use the editor's
    // insertion path, then notify React/ProseMirror-style input handlers.
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(el);
    selection?.removeAllRanges();
    selection?.addRange(range);
    let inserted = false;
    try { inserted = document.execCommand("insertText", false, text); } catch {}
    if (!inserted) {
      range.deleteContents();
      const node = document.createTextNode(text);
      range.insertNode(node);
      range.setStartAfter(node);
      range.collapse(true);
      selection?.removeAllRanges();
      selection?.addRange(range);
    }
    el.dispatchEvent(new InputEvent("input", {bubbles: true, inputType: "insertText", data: text}));
  }

  function shouldResolve(text) {
    return /\b(project|repo|repository|code|coding|vibe ?code|extension|app|website|site|bug|fix|update|build|implement|deploy|terminal|github|continue|resume|again|that|this|it|same|okay|ok|switch|create|new)\b/i.test(text);
  }

  async function isEnabled() {
    const state = await chrome.storage.local.get(["enabled"]);
    return state.enabled !== false;
  }
  // VibeBridge is hands-off: no overlay banners, notices, or context-choice buttons.
  // Diagnostics remain available through the browser console when needed.
  function showNotice(_text) {}

  // Context detection and attachment are automatic; never interrupt the send flow.

  // ChatGPT may replace its Send button while the extension resolves context.
  // Always target the currently mounted button instead of a stale element; wait
  // briefly for React to enable it after updating the draft.
  function clickCurrentSendButton(attempt = 0) {
    const current = document.querySelector('button[data-testid="send-button"]') ||
      document.querySelector('button[aria-label*="Send"]') ||
      document.querySelector("form button[type='submit']");
    if (!current) {
      showNotice("VibeBridge could not find ChatGPT's current Send button. Your draft is unchanged; click Send normally.");
      return false;
    }
    if (current.disabled) {
      if (attempt < 10) { setTimeout(() => clickCurrentSendButton(attempt + 1), 50); return true; }
      showNotice("ChatGPT's Send button stayed disabled. Your draft is unchanged; click Send normally.");
      return false;
    }
    bypassNextSend = true;
    current.click();
    setTimeout(() => { bypassNextSend = false; }, 800);
    return true;
  }
  function showReloadNotice(text) {
    showNotice(text);
    const notice = document.getElementById("vibebridge-notice");
    const actions = notice?.querySelector("#vibebridge-notice-actions");
    if (!actions) return;
    let reload = actions.querySelector('[data-vibebridge-reload="true"]');
    if (!reload) {
      reload = document.createElement("button");
      reload.type = "button";
      reload.dataset.vibebridgeReload = "true";
      reload.textContent = "Reload ChatGPT tab";
      reload.style.cssText = "padding:5px 8px;border:0;border-radius:5px;cursor:pointer";
      reload.addEventListener("click", () => location.reload());
      actions.insertBefore(reload, actions.firstChild);
    }
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
      // Some ChatGPT render paths drop custom fence classes but retain the
      // literal fence label as the first rendered line. Preserve hands-off
      // behavior only for that explicit VibeBridge label, never generic JSON.
      const markedFence = /^vibebridge-run(?:\s|$)/i.test(normalizedBlock);
      const hasCommandLanguage = /language-vibebridge-run|vibebridge-run/i.test(className);
      const hasShellLanguage = /language-(bash|sh|zsh|shell)\b/i.test(className);
      let payload = null;
      // Handle ChatGPT rendering custom vibebridge-run fences as plain text, including
      // an opening "vibebridge-run id=..." line before the JSON payload.
      if (!hasCommandLanguage && !markedBlock && !markedFence && !hasShellLanguage) {
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
      if (hasShellLanguage && !hasCommandLanguage && !markedBlock) {
        payload = {command: ["bash", "-lc", rawBlock.replace(/^\s*```(?:bash|sh|zsh|shell)\s*/i, "").replace(/\s*```$/, "").trim()]};
      } else if (!payload) {
        try {
          let jsonText = markedBlock
            ? normalizedBlock.slice(commandMarker.length).trim()
            : markedFence
              ? normalizedBlock.replace(/^vibebridge-run[^\r\n]*(?:\r?\n|$)/i, "").trim()
              : rawBlock;
          jsonText = jsonText.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "").trim();
          payload = JSON.parse(jsonText);
        } catch {
          // The assistant may still be streaming this block. Leave it unprocessed
          // so the next DOM mutation can retry parsing the completed JSON.
          continue;
        }
      }
      if (!payload || !Array.isArray(payload.command) || !payload.command.length ||
          !payload.command.every(part => typeof part === "string")) {
        processedBlocks.add(pre);
        processedBlocks.add(target);
        const warning = document.createElement("div");
        warning.textContent = "VibeBridge command must contain a shell command or JSON command array.";
        warning.style.cssText = "color:#b91c1c;font:12px system-ui;margin:6px 0";
        pre.after(warning);
        continue;
      }

      processedBlocks.add(pre);
      processedBlocks.add(target);
      detectedBlocks++;

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
      // Automatic execution must require an explicit VibeBridge command marker.
      // Generic JSON and ordinary shell code blocks are manual-only, even in hands-off mode.
      const explicitlyMarkedCommand = hasCommandLanguage || markedBlock || markedFence;
      chrome.storage.local.get(["autoRunCommands"], settings => {
        if (allowAutoRun && explicitlyMarkedCommand && allowAutomaticExecution && settings.autoRunCommands === true) {
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
    const nextText = "VibeBridge v" + extensionVersion + " · blocks " + scannedBlocks + " · commands " + detectedBlocks;
    const nextTitle = "Loaded Chrome extension version: " + extensionVersion + ". Scanned code blocks: " + scannedBlocks + ". Recognized command blocks: " + detectedBlocks + ".";
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
    // Do not mutate the visible composer during mutation-observer scans.
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
  // Do not rewrite a pre-filled composer during startup.
  // Existing assistant messages are rendered first and only receive manual Run controls.
  // Subsequent command blocks can use hands-off mode.
  addCommandControls(false);
  allowAutomaticExecution = true;

  document.addEventListener("click", async event => {
    const button = event.target.closest('button[data-testid="send-button"], button[aria-label*="Send"], button[type="submit"]');
    if (!button || bypassNextSend || busy) return;
    const composer = composerFor(button);
    const original = readComposer(composer).trim();
    // Guard any bridge-owned wrapper, including escaped/partially edited variants,
    // so a context-enriched prompt is never wrapped and injected a second time.
    if (!enabledState || !original || /VIBEBRIDGE PROJECT CONTEXT|VIBEBRIDGE PROJECT CONTINUITY|END VIBEBRIDGE PROJECT CONTEXT|VIBEBRIDGE MEMORY CHECKPOINT REQUIREMENT/.test(original) || original.includes("VIBEBRIDGE DISABLED")) return;
    // When VibeBridge is enabled, resolve context for every user message. Short
    // follow-ups like “you should” and “it should” still depend on project history.

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    busy = true;
    button.disabled = true;
    let shouldResumeSend = true;
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
        // The server resolves every explicitly mentioned project. Preserve only
        // this conversation's known project set for short follow-ups; no global
        // active-project default and no single-project fallback may override it.
        const activeProject = knownProjects.length ? knownProjects[knownProjects.length - 1] : "";
        result = await chrome.runtime.sendMessage({
          type: "VIBEBRIDGE_RESOLVE_CONTEXTS",
          text: original,
          projects: knownProjects.map(path => ({path})),
          activeProject
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
        // Context is stored for subsequent resolution, but MUST NOT be written
        // into ChatGPT's visible editor. That mutation is the recurring context
        // leak: React remounts can retain the injected text after our cleanup.
        // Send the user's original request unchanged instead.
      } else if (result?.ambiguous) {
        showNotice("VibeBridge found multiple possible projects. Mention the exact project name.");
      } else if (result?.error) {
        showNotice("VibeBridge: " + result.error + "\nYour original message will still be sent. Check the local agent and GitHub CLI connection in the extension popup.");
      } else {
        showNotice("VibeBridge did not attach project context. Reason: " + (result?.reason || (result?.error ? "agent-error: " + result.error : "no-match")) + ". Active project: " + (activeProject || "(none)") + ". Conversation projects: " + (knownProjects.join(", ") || "(none)") + ". Agent endpoint: 127.0.0.1:43127. Your original message will still be sent. Copy this diagnostic if the issue continues.");
      }
    } catch (error) {
      const message = String(error?.message || error || "Unknown error");
      const invalidated = /extension context invalidated|context invalidated|extension context.*invalid/i.test(message);
      // Do not auto-submit the un-enriched original message after the extension
      // context dies; leave it in the composer so the user can inspect/resend.
      if (invalidated) shouldResumeSend = false;
      const notice = invalidated
        ? "VibeBridge's extension was updated or reloaded while this ChatGPT tab was open. Reload this tab to reconnect. Your message was not sent with project context; check the prompt before resending."
        : "VibeBridge could not load project context: " + message + "\nYour original message will still be sent without project context. Check the local agent and GitHub CLI connection in the extension popup.";
      if (invalidated) showReloadNotice(notice);
      else showNotice(notice);
    } finally {
      busy = false;
      button.disabled = false;
      if (shouldResumeSend) clickCurrentSendButton();
    }
  }, true);
})();
