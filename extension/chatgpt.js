(() => {
  if (window.__vibeBridgeInstalled) return;
  window.__vibeBridgeInstalled = true;
  let bypassNextSend = false;
  let busy = false;
  const marker = "VIBEBRIDGE PROJECT CONTEXT";

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
      const rememberMatch = original.match(/remember (?:for this project|this for the project|that for this project)[:\\-]?\\s*(.+)/i);
      if (rememberMatch && rememberMatch[1]) {
        const saved = await chrome.runtime.sendMessage({type: "VIBEBRIDGE_REMEMBER", note: rememberMatch[1].trim()});
        if (saved?.saved) showNotice("Saved a note to " + saved.project + " project memory");
        else if (saved?.error) showNotice("VibeBridge memory: " + saved.error);
      }
      const result = await chrome.runtime.sendMessage({type: "VIBEBRIDGE_RESOLVE_CONTEXT", text: original});
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
