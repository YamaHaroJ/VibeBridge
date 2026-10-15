(() => {
  if (window.__vibeBridgeInstalled) return;
  window.__vibeBridgeInstalled = true;
  let bypassNextSend = false;
  let busy = false;
  const marker = "VIBEBRIDGE PROJECT CONTEXT";
  const commandMarker = "VIBEBRIDGE LOCAL COMMAND";
  const processedBlocks = new WeakSet();

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
    return /\b(project|repo|repository|code|coding|vibe ?code|extension|app|website|site|bug|fix|update|build|implement|deploy|terminal|github|continue|resume|again|that|this|it|same|okay|ok)\b/i.test(text);
  }

  function showNotice(text) {
    let node = document.getElementById("vibebridge-notice");
    if (!node) {
      node = document.createElement("div");
      node.id = "vibebridge-notice";
      node.style.cssText = "position:fixed;z-index:999999;right:18px;bottom:88px;max-width:360px;padding:10px 14px;border-radius:10px;background:#172033;color:#fff;font:13px system-ui;box-shadow:0 4px 18px #0005";
      document.body.appendChild(node);
    }
    node.textContent = text;
    node.style.display = "block";
    clearTimeout(node.__timer);
    node.__timer = setTimeout(() => { node.style.display = "none"; }, 5000);
  }

  function addCommandControls() {
    const blocks = document.querySelectorAll('[data-message-author-role="assistant"] pre');
    for (const pre of blocks) {
      if (processedBlocks.has(pre)) continue;
      const code = pre.querySelector("code");
      const className = (code?.className || "") + " " + (pre.className || "");
      if (!/language-vibebridge-run|vibebridge-run/i.test(className)) continue;
      processedBlocks.add(pre);

      let payload;
      try {
        payload = JSON.parse((code?.textContent || pre.textContent || "").trim());
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

  const observer = new MutationObserver(() => addCommandControls());
  observer.observe(document.documentElement, {childList: true, subtree: true});
  addCommandControls();

  document.addEventListener("click", async event => {
    const button = event.target.closest('button[data-testid="send-button"], button[aria-label*="Send"], button[type="submit"]');
    if (!button || bypassNextSend || busy) return;
    const composer = composerFor(button);
    const original = readComposer(composer).trim();
    if (!original || original.includes(marker)) return;
    if (!shouldResolve(original)) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    busy = true;
    button.disabled = true;
    try {
      const result = await chrome.runtime.sendMessage({type: "VIBEBRIDGE_RESOLVE_CONTEXT", text: original});
      const rememberMatch = original.match(/remember (?:for this project|this for the project|that for this project)[:\-]?\s*(.+)/i);
      if (rememberMatch && rememberMatch[1]) {
        const saved = await chrome.runtime.sendMessage({type: "VIBEBRIDGE_REMEMBER", note: rememberMatch[1].trim()});
        if (saved?.saved) showNotice("Saved a note to " + saved.project + " project memory");
        else if (saved?.error) showNotice("VibeBridge memory: " + saved.error);
      }
      if (result?.matched && result.context) {
        const addition = marker + "\nThe following is persistent context from the user's local project. Treat it as background information, verify implementation against code when needed, and do not assume planned features are implemented.\n\n" + result.context + "\n\nEND " + marker + "\n\nUSER REQUEST:\n";
        writeComposer(composer, addition + original);
        showNotice("VibeBridge attached context for " + result.project.name);
      } else if (result?.ambiguous) {
        showNotice("VibeBridge found multiple possible projects. Mention the exact project name.");
      } else if (result?.error) {
        showNotice("VibeBridge: " + result.error);
      }
    } catch (error) {
      showNotice("VibeBridge couldn't load project context: " + error.message);
    } finally {
      busy = false;
      button.disabled = false;
      bypassNextSend = true;
      button.click();
      setTimeout(() => { bypassNextSend = false; }, 800);
    }
  }, true);
})();
