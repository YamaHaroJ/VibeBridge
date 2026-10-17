const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const source = fs.readFileSync(path.join(__dirname, "..", "extension", "chatgpt.js"), "utf8");

class Element {
  constructor(tagName = "DIV") {
    this.tagName = tagName;
    this.children = [];
    this.listeners = {};
    this.attributes = {};
    this.dataset = {};
    this.style = {};
    this.disabled = false;
    this.value = "";
    this.innerText = "";
    this.textContent = "";
    this.className = "";
    this.id = "";
  }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  append(...items) { for (const item of items) this.appendChild(item); }
  replaceChildren(...items) { this.children = []; this.textContent = ""; this.append(...items); }
  appendChild(item) { item.parentElement = this; this.children.push(item); return item; }
  insertBefore(item, before) {
    item.parentElement = this;
    const index = this.children.indexOf(before);
    this.children.splice(index < 0 ? 0 : index, 0, item);
    return item;
  }
  remove() { if (this.parentElement) this.parentElement.children = this.parentElement.children.filter(x => x !== this); }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  getAttribute(key) { return this.attributes[key] || null; }
  closest(selector) {
    const selectors = selector.split(",").map(s => s.trim());
    let node = this;
    while (node) {
      for (const sel of selectors) {
        if (sel.startsWith("#") && node.id === sel.slice(1)) return node;
        if (sel.includes("button") && node.tagName === "BUTTON") return node;
        if (sel.startsWith("textarea") && node.tagName === "TEXTAREA") return node;
        if (sel.includes('[contenteditable="true"]') && node.attributes.contenteditable === "true") return node;
      }
      node = node.parentElement || null;
    }
    return null;
  }
  querySelector(selector) {
    const find = node => {
      for (const child of node.children) {
        if (selector.startsWith("#") && child.id === selector.slice(1)) return child;
        const found = find(child);
        if (found) return found;
      }
      return null;
    };
    return find(this);
  }
  querySelectorAll(selector) {
    const found = [];
    const matches = node => {
      if (selector === "pre" || selector === "code") return node.tagName === selector.toUpperCase();
      const attr = selector.match(/^\[([^=]+)="([^"]+)"\]$/);
      return !!attr && node.getAttribute(attr[1]) === attr[2];
    };
    const visit = node => {
      for (const child of node.children) {
        if (matches(child)) found.push(child);
        visit(child);
      }
    };
    visit(this);
    return found;
  }
  after(item) { item.parentElement = this.parentElement; if (this.parentElement) this.parentElement.appendChild(item); }
  focus() {}
  select() {}
  click() {
    this.clickCount = (this.clickCount || 0) + 1;
    for (const fn of (this.listeners.click || [])) fn({target:this, preventDefault(){}, stopPropagation(){}, stopImmediatePropagation(){}});
    if (typeof this.onclick === "function") this.onclick();
  }
  dispatchEvent() { return true; }
}

async function runScenario(sendMessage, initialDraft = "Continue VibeBridge", license = {active: true, status: "active"}, trigger = "click") {
  const composer = new Element("TEXTAREA");
  composer.id = "prompt-textarea";
  composer.value = initialDraft;
  let liveSend = new Element("BUTTON");
  liveSend.setAttribute("data-testid", "send-button");
  const send = liveSend;
  const body = new Element("BODY");
  const root = new Element("HTML");
  root.appendChild(body);
  const docListeners = {};
  const notices = [];
  const document = {
    body, documentElement:root,
    addEventListener(type, fn) { (docListeners[type] ||= []).push(fn); },
    createElement(tag) { return new Element(tag.toUpperCase()); },
    createTextNode(text) { const e = new Element("#TEXT"); e.textContent = text; return e; },
    getElementById(id) {
      const search = node => {
        if (node.id === id) return node;
        for (const child of node.children) { const found = search(child); if (found) return found; }
        return null;
      };
      return search(root);
    },
    querySelector(selector) {
      if (selector.startsWith("#")) {
        const found = this.getElementById(selector.slice(1));
        if (found) return found;
      }
      if (selector === "#prompt-textarea" || selector === 'textarea[placeholder]') return composer;
      if (selector === 'button[data-testid="send-button"]' || selector === 'button[aria-label*="Send"]') return liveSend;
      if (selector === "form") return null;
      return null;
    },
    querySelectorAll(selector) { return root.querySelectorAll(selector); },
    execCommand() { return true; },
    createRange() { return {selectNodeContents(){}, deleteContents(){}, insertNode(){}, setStartAfter(){}, collapse(){}}; }
  };
  const storage = {
    async get(keys) {
      const all = {enabled:true, token:"mock-token", activeProject:"/Users/test/VibeBridge"};
      return Object.fromEntries(keys.filter(k => k in all).map(k => [k, all[k]]));
    },
    async set() {}
  };
  const chrome = {
    runtime: {getManifest:()=>({version:"test"}), onMessage:{addListener(){}}, async sendMessage(message) {
      notices.push(message);
      // Licensing/roster are infra concerns, not what these scenarios test;
      // give sane defaults so each scenario's callback only has to handle
      // the message type it actually cares about.
      if (message?.type === "VIBEBRIDGE_LICENSE_STATUS") return license;
      if (message?.type === "VIBEBRIDGE_GITHUB_PROJECTS") return {ok: true, repositories: []};
      return await sendMessage(message);
    }},
    storage: {local:storage, onChanged:{addListener(){}}}
  };
  class MutationObserver { constructor(fn) { this.fn = fn; } observe() {} disconnect() {} }
  const context = {
    window:{__vibeBridgeInstalled:false, getSelection:()=>({removeAllRanges(){},addRange(){}}), setInterval:()=>0, addEventListener(){}},
    document, location:{pathname:"/c/test-conversation",reload(){}},
    chrome, MutationObserver, Node:{ELEMENT_NODE:1},
    HTMLTextAreaElement:{prototype:{}}, HTMLInputElement:{prototype:{}},
    InputEvent:class {constructor(type, options){this.type=type;Object.assign(this,options);}},
    Event:class {constructor(type){this.type=type;}},
    URL, console, navigator:{clipboard:{writeText:async()=>{}}},
    confirm:()=>true, setTimeout, clearTimeout, queueMicrotask,
    // Real browsers (including content-script isolated worlds) provide these;
    // Node's vm sandbox does not, so the harness must supply its own to match
    // actual Chrome capabilities instead of changing working production code.
    requestAnimationFrame: fn => setTimeout(fn, 0), cancelAnimationFrame: id => clearTimeout(id),
    sessionStorage: {getItem: () => null, setItem() {}, removeItem() {}},
  };
  context.window.document = document;
  vm.runInNewContext(source, context, {filename:"chatgpt.js"});

  const handler = trigger === "enter" ? docListeners.keydown[0] : docListeners.click[0];
  assert.ok(handler, "content script registered " + trigger + " send handler");
  const event = trigger === "enter"
    ? {target:composer, key:"Enter", shiftKey:false, isComposing:false,
       preventDefault(){this.prevented=true;}, stopPropagation(){}, stopImmediatePropagation(){}}
    : {target:send, preventDefault(){this.prevented=true;}, stopPropagation(){}, stopImmediatePropagation(){}};
  const pending = handler(event);
  await pending;
  await new Promise(resolve => setTimeout(resolve, 80));
  return {composer, send, getCurrentSend:() => liveSend, replaceSendButton(){ liveSend = new Element("BUTTON"); liveSend.setAttribute("data-testid", "send-button"); return liveSend; }, notices, event, body, document};
}

(async () => {
  {
    const h = await runScenario(async message => {
      if (message.type === "VIBEBRIDGE_RESOLVE_CONTEXTS") {
        return {matched:true, context:"MOCK PROJECT CONTEXT", projects:[{name:"VibeBridge",path:"/Users/test/VibeBridge"}]};
      }
      throw new Error("Unexpected message " + message.type);
    });
    assert.equal(h.composer.value, "Continue VibeBridge", "matched project context never mutates the visible composer");
    assert.doesNotMatch(h.composer.value, /MOCK PROJECT CONTEXT|Project background for continuity|PERSISTENT PROJECT MEMORY/, "project context remains outside the user's message");

    // A fresh conversation now sends two turns: the context primer (its own
    // message, never merged into the user's draft) and then the user's
    // original message, unmodified.
    assert.equal(h.getCurrentSend().clickCount, 2, "fresh conversation sends a context primer, then the original message");
    assert.equal(h.document.getElementById("vibebridge-context-choice"), null, "automatic flow has no extra choice step");
  }
  {
    // Most users press Enter, not the Send button. Without this listener,
    // VibeBridge would silently never see any message sent this way.
    const h = await runScenario(async message => {
      if (message.type === "VIBEBRIDGE_RESOLVE_CONTEXTS") {
        return {matched:true, context:"MOCK PROJECT CONTEXT", projects:[{name:"VibeBridge",path:"/Users/test/VibeBridge"}]};
      }
      throw new Error("Unexpected message " + message.type);
    }, "Continue VibeBridge", {active: true, status: "active"}, "enter");
    assert.equal(h.event.prevented, true, "Enter's default newline insertion is suppressed once VibeBridge takes over the send");
    assert.equal(h.composer.value, "Continue VibeBridge", "pressing Enter never mutates the visible composer either");
    assert.equal(h.getCurrentSend().clickCount, 2, "pressing Enter still primes a fresh conversation, then sends the original message");
  }
  {
    const staleDraft = [
      "Project background for continuity; treat this as reference material, not a new request.",
      "README content with a horizontal rule",
      "---",
      "PERSISTENT PROJECT MEMORY: old context",
      "---",
      "there\'s the user\'s actual request"
    ].join("\n\n");
    const h = await runScenario(async message => {
      if (message.type === "VIBEBRIDGE_RESOLVE_CONTEXTS") return {matched:false, reason:"no-match"};
      throw new Error("Unexpected message " + message.type);
    }, staleDraft);
    assert.equal(h.composer.value, staleDraft, "stale context remains untouched; VibeBridge never rewrites the user's draft");
  }
  {
    const h = await runScenario(async message => {
      if (message.type === "VIBEBRIDGE_RESOLVE_CONTEXTS") return {matched:false, reason:"no-match"};
      throw new Error("Unexpected message " + message.type);
    });
    assert.equal(h.composer.value, "Continue VibeBridge", "no-match preserves the original draft");
    // Even with no project matched, a fresh conversation still gets the roster
    // primer (so ChatGPT can ask "which project?" or offer to create one),
    // followed by the user's original message.
    assert.equal(h.getCurrentSend().clickCount, 2, "no-match still primes a fresh conversation, then sends original text");
    assert.equal(h.document.getElementById("vibebridge-notice"), null, "no-match creates no banner");
  }
  {
    // Without an active license, VibeBridge's own features (priming, command
    // execution) must stay off, but the user's own message still goes out.
    const h = await runScenario(async message => {
      if (message.type === "VIBEBRIDGE_RESOLVE_CONTEXTS") return {matched:true, context:"MOCK PROJECT CONTEXT", projects:[{name:"VibeBridge",path:"/Users/test/VibeBridge"}]};
      throw new Error("Unexpected message " + message.type);
    }, "Continue VibeBridge", {active: false, status: "no-subscription"});
    assert.equal(h.composer.value, "Continue VibeBridge", "unlicensed flow never touches the composer");
    assert.equal(h.getCurrentSend().clickCount, 1, "unlicensed flow sends only the user's original message, no primer");
  }
  {
    const h = await runScenario(async () => { throw new Error("Extension context invalidated."); });
    assert.equal(h.composer.value, "Continue VibeBridge", "invalidated context leaves original prompt intact");
    assert.equal(h.getCurrentSend().clickCount, undefined, "invalidated extension must not replay/send the prompt");
    assert.equal(h.document.getElementById("vibebridge-notice"), null, "even reload errors do not create banners");
  }
  {
    const h = await runScenario(async () => { throw new Error("Failed to fetch"); });
    assert.equal(h.composer.value, "Continue VibeBridge");
    assert.equal(h.getCurrentSend().clickCount, 1, "recoverable agent error still sends the original once");
    assert.equal(h.document.getElementById("vibebridge-notice"), null, "recoverable errors do not create banners");
  }
  // Targeted regression guard: automatic command completion must never write into
  // the composer or click Send on the user's behalf, regardless of draft state.
  // A message that looks like it came from the user but that they never typed
  // is not acceptable at any time. Only the explicit "Add result to ChatGPT
  // prompt" button may write the result, and even that must never auto-send.
  // This complements the DOM send-flow scenarios: command controls are generated
  // by MutationObserver and the mock DOM does not model the full ChatGPT message tree.
  {
    const commandSource = source.slice(source.indexOf('const executeAction = async (automatic = false)'), source.indexOf('insert.addEventListener'));
    assert.notEqual(commandSource, source, "command executor exists");
    assert.ok(/if \(automatic\) \{/.test(commandSource), "automatic completion has its own branch");
    const automaticBranch = commandSource.slice(commandSource.indexOf('if (automatic) {'));
    assert.doesNotMatch(automaticBranch, /writeComposer/, "automatic completion never writes into the composer");
    assert.doesNotMatch(automaticBranch, /send\.click\(\)/, "automatic completion never clicks Send");
    assert.match(commandSource, /VibeBridge never sends a message on your behalf/, "hands-off description accurately sets expectations");
  }
  {
    const insertSource = source.slice(source.indexOf('insert.addEventListener'), source.indexOf('insert.addEventListener') + 800);
    assert.doesNotMatch(insertSource, /send\.click\(\)|bypassNextSend\s*=\s*true/, "the manual insert button only writes the draft; it never sends for the user");
  }
  console.log("ChatGPT content-script DOM simulation: 7 scenarios passed; command draft-safety regression guard passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
