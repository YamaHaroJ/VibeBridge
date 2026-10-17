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
  const CHECKPOINT_MESSAGE_INTERVAL = 6;
  const CHECKPOINT_TIME_INTERVAL_MS = 10 * 60 * 1000;
  window.addEventListener("pageshow", reportHeartbeatFromThisFile);
  const commandMarker = "VIBEBRIDGE LOCAL COMMAND";
  const processedBlocks = new WeakSet();
  // Never replay commands embedded in conversation history when a tab opens.
  // Hands-off execution is reserved for command blocks that appear after startup.
  let allowAutomaticExecution = false;

  // Save only explicit checkpoint blocks; never upload raw messages.
  const processedMemoryBlocks = new WeakSet();

  // A brand-new chat has no "/c/<id>" in its URL until after the first
  // message is actually sent and ChatGPT creates the conversation. Returning
  // a shared fallback like "chat" here made every new conversation's first
  // message collide in storage with every other new conversation's first
  // message — the second new thread looked "already primed" because the
  // first one was, even though they're unrelated. Empty string signals "no
  // real id yet" distinctly, so callers can special-case it instead of
  // silently sharing one bucket.
  function conversationKey() {
    const match = location.pathname.match(/\/c\/([^/]+)/);
    return match ? match[1].slice(0, 80) : "";
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

  function findSendButton() {
    return document.querySelector('button[data-testid="send-button"]') ||
      document.querySelector('button[aria-label*="Send"]') ||
      document.querySelector("form button[type='submit']");
  }

  // ChatGPT disables the composer while a response is streaming. Poll instead
  // of guessing a fixed delay, since response length varies a lot.
  function waitForComposerReady(timeoutMs = 120000) {
    return new Promise(resolve => {
      const start = Date.now();
      (function poll() {
        const button = findSendButton();
        if (button && !button.disabled) return resolve(true);
        if (Date.now() - start > timeoutMs) return resolve(false);
        setTimeout(poll, 250);
      })();
    });
  }

  // Deliver VibeBridge context as its own chat turn instead of merging it into
  // the user's draft. Merging into one message was the source of the original
  // leaked-text bug (composer remounts outran our cleanup); a separate message
  // has no cleanup step to race.
  // Every new ChatGPT thread starts with no idea VibeBridge exists. This primer
  // teaches it the local-command protocol and the real repository roster once
  // per conversation, so a fresh thread can say "which of these 6?" or "none of
  // these fit, want me to create one?" instead of guessing.
  async function buildPrimerMessage(includeProtocol, projectContext) {
    const parts = [marker];
    if (includeProtocol) {
      let rosterLines = [];
      try {
        const roster = await chrome.runtime.sendMessage({type: "VIBEBRIDGE_GITHUB_PROJECTS"});
        if (roster?.ok && Array.isArray(roster.repositories)) {
          rosterLines = roster.repositories.slice(0, 40).map(repo =>
            "- " + repo.nameWithOwner +
            (repo.localPath ? " (cloned locally)" : "") +
            (repo.description ? " — " + repo.description : ""));
        }
      } catch (_) {}
      parts.push(
        "VibeBridge is connected in this browser: a local Mac agent and GitHub CLI are available.",
        "If you have any memory, assumption, or prior-conversation habit about this project — including specific issue numbers, \"no callable command tool\" framing, GitHub-Issues-based task relays, or an unresolved cross-conversation bridge problem — treat it as stale. That architecture was removed; do not reference it or re-investigate it. Rely only on what this message and live tool results tell you.",
        "",
        "Known GitHub repositories on this account:",
        rosterLines.length ? rosterLines.join("\n") : "(none found — GitHub CLI may need to sign in on the Mac)",
        "",
        "Protocol for this conversation:",
        "- If the user names one of the repositories above, treat it as the active project for the rest of this thread.",
        "- If none of them fit and the user wants to start something new, say so plainly and offer to create a new GitHub repository; ask for confirmation first.",
        "- You are a coding agent working directly against the user's Mac, the same way Claude Code works: read real files before changing them, make focused edits, and verify with tests or by re-reading the file — never guess at file contents or assume an edit applied without checking.",
        "- To run a shell command, emit a fenced block:",
        "  ```vibebridge-run",
        "  {\"command\": [\"arg0\", \"arg1\"]}",
        "  ```",
        "- To read a file, emit:",
        "  ```vibebridge-read",
        "  {\"path\": \"relative/or/absolute/path\"}",
        "  ```",
        "- To write/overwrite a file with new full content (prefer this over shell heredocs or sed for edits — read the file first, then write the complete new content):",
        "  ```vibebridge-write",
        "  {\"path\": \"relative/or/absolute/path\", \"content\": \"full file content\"}",
        "  ```",
        "- To list a folder's contents:",
        "  ```vibebridge-list",
        "  {\"path\": \"relative/or/absolute/path\"}",
        "  ```",
        "  (path is optional for vibebridge-list; omitting it lists the user's home folder.)",
        "- Only report a command/file action as completed if its result was actually returned in this conversation. Never assume a prior conversation's state.",
        "- VibeBridge will periodically ask you to checkpoint this conversation so its state survives into the next thread. When asked (or whenever real progress/decisions happen), emit a fenced block exactly like this:",
        "  ```vibebridge-memory",
        "  {\"projects\": [{\"repository\": \"owner/repo\", \"summary\": \"short durable summary\", \"handoff\": \"exactly where things stand right now\", \"todos\": [\"next step 1\", \"next step 2\"], \"decisions\": [\"decision made and why\"]}]}",
        "  ```",
        "- The checkpoint is saved silently to GitHub and reappears as \"LATEST CROSS-CONVERSATION HANDOFFS AND LIVING TODOS\" the next time this project's context is loaded. Write the handoff/todos as if briefing someone with no memory of this thread."
      );
    }
    if (projectContext) parts.push("", "Current project context:", projectContext);
    parts.push("END " + marker);
    return parts.join("\n");
  }

  // After this sends, restore restoreText into the composer so the user's
  // actual message (still pending in the outer send flow) goes out next,
  // instead of leaving the composer empty or holding the primer text.
  // ChatGPT's composer is a ProseMirror editor whose React layer reads its
  // own submission state from the input event asynchronously. Clicking Send
  // immediately after writeComposer() can fire before that state catches up
  // with the DOM, submitting whatever text was there before our write. Poll
  // until the rendered text matches, then give React a couple of frames to
  // finish syncing before anything reads from it.
  function waitForComposerText(el, expectedText, timeoutMs = 2000) {
    return new Promise(resolve => {
      const start = Date.now();
      (function poll() {
        if (readComposer(el).trim() === expectedText.trim()) {
          requestAnimationFrame(() => requestAnimationFrame(resolve));
          return;
        }
        if (Date.now() - start > timeoutMs) return resolve();
        setTimeout(poll, 30);
      })();
    });
  }

  async function sendAsSeparateMessage(text, restoreText) {
    const button = findSendButton();
    const composer = composerFor(button);
    if (!composer) return false;
    writeComposer(composer, text);
    await waitForComposerText(composer, text);
    // The outer send handler disables this same button for the duration of its
    // own work (busy guard). Clear that here so our own synthetic click isn't
    // blocked by a flag we set ourselves; ChatGPT disables it again natively
    // once generation starts, which is the signal waitForComposerReady needs.
    if (button) button.disabled = false;
    const clicked = clickCurrentSendButton();
    if (clicked) {
      await new Promise(r => setTimeout(r, 400));
      await waitForComposerReady();
    }
    const current = composerFor(findSendButton());
    if (current && restoreText !== undefined) {
      writeComposer(current, restoreText);
      await waitForComposerText(current, restoreText);
    }
    return clicked;
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
  // Four action kinds, mirroring the tools an actual coding agent uses:
  // run (shell), read/write (file content), list (directory). Read/write/list
  // exist so file edits go through a clean overwrite instead of ChatGPT having
  // to construct shell heredocs/sed one-liners for every change.
  const ACTIONS = {
    run: {
      label: "command",
      buttonLabel: "Run on my Mac",
      runningLabel: "Running…",
      confirm: payload => "Run this command on your Mac inside the active project folder?\n\n" + payload.command.join(" "),
      describe: () => "VibeBridge can run this command in the active local project.",
      validate: payload => !!payload && Array.isArray(payload.command) && payload.command.length > 0 &&
        payload.command.every(part => typeof part === "string"),
      send: payload => ({type: "VIBEBRIDGE_RUN_COMMAND", command: payload.command}),
      resultMarker: "VIBEBRIDGE COMMAND RESULT",
      describeInResult: payload => "Command: " + payload.command.join(" ")
    },
    read: {
      label: "file read",
      buttonLabel: "Read file",
      runningLabel: "Reading…",
      confirm: payload => "Read this file on your Mac?\n\n" + payload.path,
      describe: () => "VibeBridge can read this file from the active local project.",
      validate: payload => !!payload && typeof payload.path === "string" && payload.path.trim().length > 0,
      send: payload => ({type: "VIBEBRIDGE_FILESYSTEM_READ", path: payload.path}),
      resultMarker: "VIBEBRIDGE FILE READ RESULT",
      describeInResult: payload => "Path: " + payload.path
    },
    write: {
      label: "file write",
      buttonLabel: "Write file",
      runningLabel: "Writing…",
      confirm: payload => "Write to this file on your Mac? This overwrites the existing content.\n\n" + payload.path,
      describe: () => "VibeBridge can write this file in the active local project. This overwrites existing content.",
      validate: payload => !!payload && typeof payload.path === "string" && payload.path.trim().length > 0 &&
        typeof payload.content === "string",
      send: payload => ({type: "VIBEBRIDGE_FILESYSTEM_WRITE", path: payload.path, content: payload.content}),
      resultMarker: "VIBEBRIDGE FILE WRITE RESULT",
      describeInResult: payload => "Path: " + payload.path
    },
    list: {
      label: "folder listing",
      buttonLabel: "List folder",
      runningLabel: "Listing…",
      confirm: payload => "List this folder on your Mac?\n\n" + (payload.path || "(home folder)"),
      describe: () => "VibeBridge can list this folder in the active local project.",
      validate: payload => !!payload && (payload.path === undefined || typeof payload.path === "string"),
      send: payload => ({type: "VIBEBRIDGE_FILESYSTEM_LIST", path: payload.path || ""}),
      resultMarker: "VIBEBRIDGE FOLDER LISTING RESULT",
      describeInResult: payload => "Path: " + (payload.path || "(home folder)")
    }
  };

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
      const hasShellLanguage = /language-(bash|sh|zsh|shell)\b/i.test(className);
      // Some ChatGPT render paths drop custom fence classes but retain the
      // literal fence label as the first rendered line. Preserve hands-off
      // behavior only for that explicit VibeBridge label, never generic JSON.
      let kind = markedBlock ? "run" : null;
      if (!kind) {
        for (const candidate of Object.keys(ACTIONS)) {
          const fence = "vibebridge-" + candidate;
          if (new RegExp("language-" + fence + "\\b", "i").test(className) ||
              new RegExp("^" + fence + "(?:\\s|$)", "i").test(normalizedBlock)) {
            kind = candidate;
            break;
          }
        }
      }
      const explicitlyMarked = !!kind;
      let payload = null;
      // Handle ChatGPT rendering custom vibebridge-* fences as plain text, including
      // an opening "vibebridge-<kind> id=..." line before the JSON payload.
      if (!kind && hasShellLanguage) {
        kind = "run";
        payload = {command: ["bash", "-lc", rawBlock.replace(/^\s*```(?:bash|sh|zsh|shell)\s*/i, "").replace(/\s*```$/, "").trim()]};
      } else if (!kind) {
        const jsonStart = normalizedBlock.indexOf("{");
        const jsonEnd = normalizedBlock.lastIndexOf("}");
        if (jsonStart >= 0 && jsonEnd > jsonStart) {
          try {
            const candidate = JSON.parse(normalizedBlock.slice(jsonStart, jsonEnd + 1));
            if (candidate && Array.isArray(candidate.command) && candidate.command.length &&
                candidate.command.every(part => typeof part === "string")) { kind = "run"; payload = candidate; }
            else if (candidate && typeof candidate.command === "string" && candidate.command.trim()) {
              kind = "run"; payload = {command: ["bash", "-lc", candidate.command]};
            }
          } catch {}
        }
        if (!kind) continue; // not a VibeBridge block at all; leave it alone
      }
      if (kind && !payload) {
        try {
          let jsonText = markedBlock
            ? normalizedBlock.slice(commandMarker.length).trim()
            : explicitlyMarked
              ? normalizedBlock.replace(new RegExp("^vibebridge-" + kind + "[^\\r\\n]*(?:\\r?\\n|$)", "i"), "").trim()
              : rawBlock;
          jsonText = jsonText.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "").trim();
          payload = JSON.parse(jsonText);
        } catch {
          // The assistant may still be streaming this block. Leave it unprocessed
          // so the next DOM mutation can retry parsing the completed JSON.
          continue;
        }
      }
      const action = ACTIONS[kind];
      if (!action || !action.validate(payload)) {
        processedBlocks.add(pre);
        processedBlocks.add(target);
        const warning = document.createElement("div");
        warning.textContent = "VibeBridge " + (action ? action.label : "block") + " has an invalid payload.";
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
      description.textContent = action.describe();
      description.style.marginBottom = "8px";
      const run = document.createElement("button");
      run.type = "button";
      run.textContent = action.buttonLabel;
      run.style.cssText = "padding:7px 10px;border-radius:6px;cursor:pointer";
      const output = document.createElement("pre");
      output.style.cssText = "white-space:pre-wrap;overflow-wrap:anywhere;max-height:260px;overflow:auto;display:none;margin-top:8px";
      const insert = document.createElement("button");
      insert.type = "button";
      insert.textContent = "Add result to ChatGPT prompt";
      insert.style.cssText = "padding:7px 10px;border-radius:6px;cursor:pointer;display:none;margin-top:8px";
      let resultText = "";

      const executeAction = async (automatic = false) => {
        if (run.disabled) return;
        const license = await chrome.runtime.sendMessage({type: "VIBEBRIDGE_LICENSE_STATUS"}).catch(() => ({active: false}));
        if (!license?.active) {
          output.style.display = "block";
          output.textContent = "VibeBridge Pro is not active. Open the extension popup to start a trial or subscribe.";
          return;
        }
        if (!automatic && !confirm(action.confirm(payload))) return;
        run.disabled = true;
        run.textContent = action.runningLabel;
        output.style.display = "block";
        output.textContent = "Waiting for the local agent…";
        try {
          const result = await chrome.runtime.sendMessage(action.send(payload));
          resultText = JSON.stringify(result, null, 2);
          output.textContent = resultText;
          run.textContent = result?.ok ? "Run again" : "Retry";
          run.disabled = false;
          insert.style.display = "inline-block";
          showNotice(result?.ok ? "VibeBridge " + action.label + " finished." : "VibeBridge " + action.label + " failed. See result.");
          if (automatic) {
            const composer = document.querySelector("#prompt-textarea") || document.querySelector('textarea[placeholder]') || document.querySelector('[contenteditable="true"][role="textbox"]');
            if (!composer) throw new Error(action.label + " ran, but ChatGPT prompt field was not found. Result is shown below.");
            // Never overwrite, append to, or send a pre-existing user draft during
            // automatic execution. Leave the result visible and let the explicit
            // "Add result to ChatGPT prompt" control handle insertion.
            if (readComposer(composer).trim()) {
              description.textContent = action.label.charAt(0).toUpperCase() + action.label.slice(1) + " finished. Your existing draft was preserved; use Add result to ChatGPT prompt if you want to include the result.";
              return;
            }
            const addition = action.resultMarker + "\n" + action.describeInResult(payload) + "\nResult JSON:\n" + resultText +
              "\n\nInspect this result and continue development. If another local action is needed, emit another vibebridge-run/read/write/list block.";
            writeComposer(composer, addition);
            const send = document.querySelector('button[data-testid="send-button"]') || document.querySelector('button[aria-label*="Send"]');
            if (send && !send.disabled) { bypassNextSend = true; send.click(); setTimeout(() => { bypassNextSend = false; }, 800); } else { showNotice("Result is ready in the prompt; send it to continue."); }
          }
        } catch (error) {
          const message = error?.message || String(error);
          if (/extension context invalidated|context invalidated|receiving end does not exist/i.test(message)) {
            output.textContent = "VibeBridge's extension context was invalidated by an extension reload. Reload this ChatGPT tab, then resend your message. This " + action.label + " was not confirmed as completed.";
            run.textContent = "Reload ChatGPT tab";
            run.disabled = false;
            run.onclick = () => location.reload();
            showNotice("Extension updated. Reload this ChatGPT tab before continuing.");
            return;
          }
          output.textContent = message;
          run.textContent = "Retry";
          run.disabled = false;
        }
      };
      run.addEventListener("click", () => executeAction(false));
      // Automatic execution requires an explicit VibeBridge fence/marker.
      // Generic JSON and ordinary shell code blocks are manual-only, even in hands-off mode.
      chrome.storage.local.get(["autoRunCommands"], settings => {
        // Hands-off by default: the entire point of VibeBridge is a Claude
        // Code-like loop (propose an action, run it, see the result, keep
        // going) instead of a chatbot with a confirmation button on every
        // step. Explicit opt-out via the popup still fully disables this.
        if (allowAutoRun && explicitlyMarked && allowAutomaticExecution && settings.autoRunCommands !== false) {
          description.textContent = "Hands-off mode is enabled: this " + action.label + " will run automatically on your Mac. If the prompt already contains a draft, VibeBridge will preserve it and show the result for optional insertion.";
          run.textContent = "Running automatically";
          executeAction(true);
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
        const addition = "\n\n" + action.resultMarker + "\n" + action.describeInResult(payload) +
          "\nResult JSON:\n" + resultText + "\n\nPlease inspect this result and continue development.";
        writeComposer(composer, current + addition);
        showNotice("Result added to your prompt. Review and send it to continue.");
      });

      panel.append(description, run, output, insert);
      target.after(panel);
    }
  }

  // Keep diagnostics in memory/console only; never overlay the user's ChatGPT page.
  function ensureBridgeStatus() {}
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
      return !node?.closest?.(".vibebridge-injected-control");
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
      // Context priming, checkpointing, and command execution are VibeBridge
      // Pro features. An expired/missing license still sends the user's
      // message normally; it just skips VibeBridge's own additions.
      const license = await chrome.runtime.sendMessage({type: "VIBEBRIDGE_LICENSE_STATUS"}).catch(() => ({active: false}));
      if (!license?.active) {
        showNotice("VibeBridge Pro is not active. Open the extension popup to start a trial or subscribe.");
        return;
      }
      const requestedCreate = original.match(/\b(?:create|make)\s+(?:a\s+)?(?:new\s+)?(?:github\s+)?(?:repo|repository)\s+(?:named|called)\s+["\x27`]?([A-Za-z0-9][A-Za-z0-9_.-]{0,99})/i);
      let createdRepository = null;
      let result;
      let knownProjects = [];
      let activeProject = "";
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
        knownProjects = (Array.isArray(prior) ? prior : [prior]).filter(Boolean);
        // The server resolves every explicitly mentioned project. Preserve only
        // this conversation's known project set for short follow-ups; no global
        // active-project default and no single-project fallback may override it.
        activeProject = knownProjects.length ? knownProjects[knownProjects.length - 1] : "";
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
      const conversation = conversationKey();
      const primedState = await chrome.storage.local.get(["primedConversations"]);
      const primedList = Array.isArray(primedState.primedConversations) ? primedState.primedConversations : [];
      // No real id yet (brand-new chat, first message) means this conversation
      // cannot possibly have been primed before — never treat it as a cache hit.
      const isFreshConversation = !conversation || !primedList.includes(conversation);
      // The real "/c/<id>" only appears in the URL after the first message is
      // sent. Re-read it once sending is done instead of trusting the
      // (possibly still-empty) value captured before anything was sent, so the
      // primed record lands on the conversation it actually describes.
      async function markConversationPrimed() {
        const resolved = conversationKey();
        if (!resolved) return;
        await chrome.storage.local.set({primedConversations: [...primedList, resolved].slice(-50)});
      }

      if (result?.matched && result.context) {
        const savedConversation = await chrome.storage.local.get(["conversationProjects"]);
        const conversationProjects = savedConversation.conversationProjects || {};
        const previous = conversationProjects[conversation] || [];
        const merged = (Array.isArray(previous) ? previous : [previous]).filter(Boolean);
        const resolvedProjects = Array.isArray(result.projects) ? result.projects : (result.project ? [result.project] : []);
        const newlyKnownProjects = resolvedProjects.filter(project => project?.path && !merged.includes(project.path));
        for (const project of resolvedProjects) {
          if (project?.path && !merged.includes(project.path)) merged.push(project.path);
        }
        // Same empty-id collision risk as priming: a conversation with no real
        // id yet has no stable bucket of its own. Skip persisting rather than
        // writing into a "" bucket every brand-new chat's first message would
        // share and pollute for each other.
        if (conversation) {
          conversationProjects[conversation] = merged.slice(-8);
          await chrome.storage.local.set({conversationProjects});
        }

        // Deliver context as a separate, visible chat turn (never merged into the
        // user's draft) whenever this thread hasn't seen it yet, or a new project
        // just entered this conversation.
        if (isFreshConversation || newlyKnownProjects.length) {
          const primer = await buildPrimerMessage(isFreshConversation, result.context);
          const sent = await sendAsSeparateMessage(primer, original);
          if (sent && isFreshConversation) {
            await markConversationPrimed();
          }
        }
      } else if (result?.ambiguous) {
        showNotice("VibeBridge found multiple possible projects. Mention the exact project name.");
        if (isFreshConversation) {
          const sent = await sendAsSeparateMessage(await buildPrimerMessage(true, ""), original);
          if (sent) await markConversationPrimed();
        }
      } else if (result?.error) {
        showNotice("VibeBridge: " + result.error + "\nYour original message will still be sent. Check the local agent and GitHub CLI connection in the extension popup.");
      } else {
        // No specific project matched, but ChatGPT still needs to know what
        // projects exist so it can ask "which one?" or offer to create one,
        // instead of guessing or claiming it has no way to find out.
        showNotice("VibeBridge did not attach project context. Reason: " + (result?.reason || (result?.error ? "agent-error: " + result.error : "no-match")) + ". Active project: " + (activeProject || "(none)") + ". Conversation projects: " + (knownProjects.join(", ") || "(none)") + ". Agent endpoint: 127.0.0.1:43127. Your original message will still be sent. Copy this diagnostic if the issue continues.");
        if (isFreshConversation) {
          const sent = await sendAsSeparateMessage(await buildPrimerMessage(true, ""), original);
          if (sent) await markConversationPrimed();
        }
      }

      // A long back-and-forth accumulates state (decisions, progress, the exact
      // next step) that lives only in this thread. Without an active nudge, that
      // state is gone the moment a new thread starts — ChatGPT cannot be trusted
      // to remember a standing "checkpoint periodically" instruction on its own
      // for an entire conversation. Force it on a schedule instead.
      const checkpointStore = await chrome.storage.local.get(["conversationCheckpoints"]);
      const checkpoints = checkpointStore.conversationCheckpoints || {};
      const checkpointEntry = checkpoints[conversation] || {count: 0, lastAt: 0};
      const dueByCount = checkpointEntry.count >= CHECKPOINT_MESSAGE_INTERVAL;
      const dueByTime = checkpointEntry.lastAt && (Date.now() - checkpointEntry.lastAt) >= CHECKPOINT_TIME_INTERVAL_MS;
      if (checkpointEntry.lastAt && (dueByCount || dueByTime)) {
        await sendAsSeparateMessage(
          marker + "\nPlease checkpoint now: emit a fenced ```vibebridge-memory block for the active project(s) " +
          "summarizing exactly where things stand (current state, decisions made, the exact next step) so this " +
          "survives into the next conversation. Use the format described earlier in this thread.\nEND " + marker,
          original
        );
        checkpoints[conversation] = {count: 0, lastAt: Date.now()};
      } else {
        checkpoints[conversation] = {count: checkpointEntry.count + 1, lastAt: checkpointEntry.lastAt || Date.now()};
      }
      await chrome.storage.local.set({conversationCheckpoints: checkpoints});
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
