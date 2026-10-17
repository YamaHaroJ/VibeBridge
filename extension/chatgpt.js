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
  let enabledState = true;
  chrome.storage.local.get(["enabled"], state => { enabledState = state.enabled !== false; });
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === "local" && changes.enabled) enabledState = changes.enabled.newValue !== false;
  });
  window.addEventListener("pageshow", reportHeartbeatFromThisFile);
  const commandMarker = "VIBEBRIDGE LOCAL COMMAND";
  const processedBlocks = new WeakSet();
  // Never replay commands already sitting in conversation history when a tab
  // opens. Hands-off execution is reserved for command blocks that appear
  // after startup's initial scan has already run once.
  let allowAutomaticExecution = false;

  // Save only explicit checkpoint blocks; never upload raw messages.
  const processedMemoryBlocks = new WeakSet();
  // Track which assistant messages already got a Terminal-nudge control, so
  // repeated scans of the same still-rendering message don't add it twice.
  const processedNudgeMessages = new WeakSet();

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

  // ChatGPT's DOM changes without notice. Two things broke silently in one
  // such update: `[data-message-author-role="assistant"]` disappeared (the
  // modern equivalent is `[data-dil-message-id]`, confirmed by counting
  // exactly one per actual assistant turn), and the fence language label
  // (e.g. "vibebridge-run") moved from being literal text inside the code
  // block to a separate header element outside it — so checking the code
  // element's own text/class for the label no longer finds anything. These
  // two helpers centralize both lookups so a future DOM change only needs
  // fixing in one place.
  function latestAssistantMessage() {
    const modern = document.querySelectorAll('[data-dil-message-id]');
    if (modern.length) return modern[modern.length - 1];
    const legacy = document.querySelectorAll('[data-message-author-role="assistant"]');
    return legacy.length ? legacy[legacy.length - 1] : null;
  }

  // Given a `<code>` or `<pre>` element, find its outer block wrapper (new
  // `[data-code-block]` or legacy `<pre>`) and the fence label visible
  // anywhere near the top of that wrapper, independent of where ChatGPT
  // currently renders that label.
  function codeBlockContext(el) {
    const wrapper = el.closest("[data-code-block]") || (el.tagName === "PRE" ? el : el.closest("pre")) || el;
    const labelProbe = (wrapper.textContent || "").slice(0, 160);
    return {wrapper, labelProbe};
  }

  // The label header and the code body are separate DOM nodes with no
  // whitespace between them in textContent (e.g. "vibebridge-runset -euo
  // pipefail..."), so a trailing \b after the label never matches -- "run"
  // flows straight into "set" with no boundary there at all. Since the
  // label always renders first, check for it as a prefix instead.
  function labelProbeStartsWith(labelProbe, word) {
    return labelProbe.trim().slice(0, word.length).toLowerCase() === word.toLowerCase();
  }

  async function saveAssistantCheckpoints() {
    // Check only the newest assistant response; scanning historical messages on
    // every streaming mutation scales poorly on long development conversations.
    const latest = latestAssistantMessage();
    if (!latest) return;
    const nodes = latest.querySelectorAll('pre, code');
    for (const pre of nodes) {
      if (processedMemoryBlocks.has(pre)) continue;
      const code = pre.tagName === "CODE" ? pre : pre.querySelector("code");
      if (!code) continue;
      const {wrapper, labelProbe} = codeBlockContext(code);
      const classes = (code.className || "") + " " + (wrapper.className || "");
      if (!/language-vibebridge-memory|vibebridge-memory/i.test(classes) && !labelProbeStartsWith(labelProbe, "vibebridge-memory")) continue;
      processedMemoryBlocks.add(pre);
      processedMemoryBlocks.add(code);
      const summary = (code.textContent || "").trim();
      wrapper.style.display = "none";
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

  // VibeBridge is hands-off on notices: no overlay banners, context-choice
  // buttons, etc. Diagnostics remain available through the browser console.
  function showNotice(_text) {}

  // VibeBridge must never send, write into the composer, or click Send on the
  // user's behalf. It only ever observes: it reads the message the user is
  // about to send (without delaying or altering it) for the explicit
  // "remember" phrase, and it adds Run/Read/Write/List buttons under
  // code blocks ChatGPT already wrote in its own replies.
  function findSendButton() {
    return document.querySelector('button[data-testid="send-button"]') ||
      document.querySelector('button[aria-label*="Send"]') ||
      document.querySelector("form button[type='submit']");
  }

  async function checkForRememberNote(originalText) {
    const rememberMatch = originalText.match(/remember (?:for this project|this for the project|that for this project)[:\-]?\s*(.+)/i);
    if (!rememberMatch || !rememberMatch[1]) return;
    const license = await chrome.runtime.sendMessage({type: "VIBEBRIDGE_LICENSE_STATUS"}).catch(() => ({active: false}));
    if (!license?.active) return;
    try {
      const saved = await chrome.runtime.sendMessage({type: "VIBEBRIDGE_REMEMBER", note: rememberMatch[1].trim()});
      if (saved?.saved) showNotice("Saved a note to " + saved.project + " project memory");
      else if (saved?.error) showNotice("VibeBridge memory: " + saved.error);
    } catch (_) {
      // Best-effort only. The user's message was already sent unmodified by
      // ChatGPT's own native handler; this never affects it either way.
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

  function addCommandControls() {
    // Command blocks only arrive in the newest assistant turn. Avoid rescanning
    // every code block in a long conversation on each streaming mutation.
    const latestAssistant = latestAssistantMessage() || document;
    const blocks = latestAssistant.querySelectorAll('pre, [data-language], code');
    scannedBlocks = blocks.length;
    for (const pre of blocks) {
      const {wrapper, labelProbe} = codeBlockContext(pre);
      const target = wrapper;
      if (processedBlocks.has(pre) || processedBlocks.has(target)) continue;
      const code = target.querySelector("code") || (pre.tagName === "CODE" ? pre : null);
      const className = (code?.className || "") + " " + (target.className || "") + " " + (pre.className || "") + " " + (target.getAttribute?.("data-language") || "");
      const rawBlock = (code?.textContent || pre.textContent || "").trim();
      if (!rawBlock || rawBlock.length > 200000) continue;
      // ChatGPT may strip custom fence-language classes and preserve whitespace around
      // the marker. Match the marker at the start of the rendered code, then tolerate
      // an optional JSON code fence so the relay never asks the user to paste it in Terminal.
      const normalizedBlock = rawBlock.replace(/^\s+/, "");
      const markedBlock = normalizedBlock.startsWith(commandMarker);
      // Same rendering drift as the vibebridge-* fence labels: ChatGPT may show
      // the language name ("Bash") as a separate header outside the code block
      // instead of (or in addition to) a CSS class, so check labelProbe too.
      const hasShellLanguage = /language-(bash|sh|zsh|shell)\b/i.test(className) ||
        ["bash", "sh", "zsh", "shell"].some(word => labelProbeStartsWith(labelProbe, word));
      // The fence label ("vibebridge-run" etc.) can show up in three different
      // places depending on how ChatGPT is currently rendering it: a CSS class,
      // literal leading text inside the code itself, or (current behavior) a
      // separate header element outside the code — hence labelProbe.
      let kind = markedBlock ? "run" : null;
      if (!kind) {
        for (const candidate of Object.keys(ACTIONS)) {
          const fence = "vibebridge-" + candidate;
          if (new RegExp("language-" + fence + "\\b", "i").test(className) ||
              new RegExp("^" + fence + "(?:\\s|$)", "i").test(normalizedBlock) ||
              labelProbeStartsWith(labelProbe, fence)) {
            kind = candidate;
            break;
          }
        }
      }
      // Automatic execution is reserved for an explicit VibeBridge fence.
      // Generic shell/JSON blocks ChatGPT writes incidentally (not through
      // this detection) are manual-only, even though they still get a Run
      // button below.
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
          // Only strip a leading label line when the code text itself actually
          // starts with one (legacy rendering). When the label lives in a
          // separate header (current rendering), rawBlock is already clean JSON.
          let jsonText = markedBlock
            ? normalizedBlock.slice(commandMarker.length).trim()
            : /^vibebridge-[a-z]+\b/i.test(normalizedBlock)
              ? normalizedBlock.replace(/^vibebridge-[a-z]+[^\r\n]*(?:\r?\n|$)/i, "").trim()
              : rawBlock;
          jsonText = jsonText.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "").trim();
          payload = JSON.parse(jsonText);
        } catch {
          // A vibebridge-run fence with a raw shell script instead of the
          // {"command": [...]} JSON it's supposed to use is a real, common
          // mistake (ChatGPT has no standing instructions reminding it of the
          // exact format anymore). Treat it the same as a plain ```bash
          // block rather than silently discarding it forever by assuming
          // it's still streaming -- that previously meant it got zero
          // controls, with no way to ever run it.
          // Only treat it as a raw script when it clearly wasn't attempting
          // JSON at all (doesn't start with "{"). Text that does start with
          // "{" but fails to parse is far more likely mid-stream/incomplete
          // JSON than a deliberate raw script -- keep retrying that case
          // instead of running a truncated fragment as a shell command.
          if (kind === "run" && jsonText.trim() && !jsonText.trim().startsWith("{")) {
            payload = {command: ["bash", "-lc", jsonText]};
          } else {
            continue;
          }
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
        // Hands-off: an explicitly-marked VibeBridge block runs the instant it
        // appears, no click needed. This never writes into the composer or
        // sends anything -- the result only ever lands in the inline panel
        // below, which still requires an explicit "Add result" click to reach
        // the conversation at all.
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
      run.addEventListener("click", () => executeAction());
      // Hands-off by default: the entire point of VibeBridge is a
      // propose-run-see-result-keep-going loop. Only explicitly-marked
      // VibeBridge fences qualify, and only after startup (never replaying
      // commands already sitting in conversation history when a tab opens).
      if (explicitlyMarked && allowAutomaticExecution) {
        description.textContent = "Hands-off mode is enabled: this " + action.label + " ran automatically on your Mac. The result is shown below for you to add to the prompt and send yourself; VibeBridge never sends a message on your behalf.";
        run.textContent = "Running automatically";
        executeAction(true);
      }

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

  // When ChatGPT falls back to a plain "run this in Terminal yourself"
  // instruction instead of an actual VibeBridge action, give a one-click way
  // to ask it to use VibeBridge instead of retyping that correction every
  // time. This never sends anything itself -- it only drafts the request
  // into the composer; sending it is still the user's own explicit action.
  function addTerminalNudgeControl() {
    const latestAssistant = latestAssistantMessage();
    if (!latestAssistant || processedNudgeMessages.has(latestAssistant)) return;
    if (latestAssistant.querySelector(".vibebridge-injected-control")) return;
    const sendButton = findSendButton();
    if (sendButton && sendButton.disabled) return; // still streaming; a later scan will retry
    const text = latestAssistant.textContent || "";
    if (!/\bterminal\b|\bpaste\b|\brun (?:this|the following) (?:command|script)\b/i.test(text)) return;
    processedNudgeMessages.add(latestAssistant);

    const nudge = document.createElement("div");
    nudge.className = "vibebridge-injected-control";
    nudge.style.cssText = "margin:8px 0;padding:10px;border:1px solid #64748b;border-radius:8px;font:13px system-ui";
    const description = document.createElement("div");
    description.textContent = "This looks like a manual Terminal instruction instead of a VibeBridge action.";
    description.style.marginBottom = "8px";
    const nudgeButton = document.createElement("button");
    nudgeButton.type = "button";
    nudgeButton.textContent = "Ask VibeBridge to run this instead";
    nudgeButton.style.cssText = "padding:7px 10px;border-radius:6px;cursor:pointer";
    nudgeButton.addEventListener("click", () => {
      const composer = document.querySelector("#prompt-textarea") ||
        document.querySelector('textarea[placeholder]') ||
        document.querySelector('[contenteditable="true"][role="textbox"]');
      if (!composer) {
        showNotice("Could not find the ChatGPT prompt field.");
        return;
      }
      const current = readComposer(composer).trim();
      const addition = "Use VibeBridge directly for that: emit a fenced ```vibebridge-run (or vibebridge-read/write/list) block for what you just described, instead of asking me to paste anything into Terminal myself.";
      writeComposer(composer, current ? current + "\n\n" + addition : addition);
      showNotice("Added a VibeBridge request to your prompt. Review and send it to continue.");
    });
    nudge.append(description, nudgeButton);
    latestAssistant.after(nudge);
  }

  // Keep diagnostics in memory/console only; never overlay the user's ChatGPT page.
  function ensureBridgeStatus() {}
  addCommandControls();

  // ChatGPT streams many DOM mutations per token. Debounce scans so we do not
  // repeatedly traverse the entire conversation tree while a response is rendering.
  let scanTimer = null;
  let scanRunning = false;
  let scanAgain = false;
  async function runScheduledScan() {
    if (scanRunning) { scanAgain = true; return; }
    scanRunning = true;
    try {
      addCommandControls();
      addTerminalNudgeControl();
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
  // Do not auto-run anything already rendered during this initial pass.
  // Only command blocks that appear from here on are eligible.
  addCommandControls();
  addTerminalNudgeControl();
  allowAutomaticExecution = true;

  // Never intercept, delay, or modify a send in any way. Only read the
  // message that's already going out, unmodified, for the explicit
  // "remember" phrase, as a pure side effect that never touches the chat.
  function observeSendAttempt(button) {
    if (!button || !enabledState) return;
    const composer = composerFor(button);
    const original = readComposer(composer).trim();
    if (!original) return;
    checkForRememberNote(original);
  }
  document.addEventListener("click", event => {
    const button = event.target.closest('button[data-testid="send-button"], button[aria-label*="Send"], button[type="submit"]');
    if (!button) return;
    observeSendAttempt(button);
  }, true);
  document.addEventListener("keydown", event => {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
    if (!event.target.closest('#prompt-textarea, textarea[placeholder], [contenteditable="true"][role="textbox"]')) return;
    observeSendAttempt(findSendButton());
  }, true);
})();
