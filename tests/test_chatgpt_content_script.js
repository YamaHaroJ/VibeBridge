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

async function runScenario(sendMessage, initialDraft = "Continue VibeBridge", license = {active: true, status: "active"}, trigger = "click", enabled = true) {
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
    // Production code calls chrome.storage.local.get both as a promise
    // (`await ...get(keys)`) and in the callback style
    // (`...get(keys, state => {...})`) -- the mock must honor both, or a
    // callback-style read (like the enabledState bootstrap) silently never
    // resolves and the test can't exercise that code path at all.
    get(keys, callback) {
      const all = {enabled, token:"mock-token", activeProject:"/Users/test/VibeBridge"};
      const list = Array.isArray(keys) ? keys : [keys];
      const result = Object.fromEntries(list.filter(k => k in all).map(k => [k, all[k]]));
      if (typeof callback === "function") { callback(result); return undefined; }
      return Promise.resolve(result);
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
    // The baseline contract: VibeBridge must never intercept, delay, or alter
    // a send. This fires VibeBridge's own listener directly (as if a real
    // click/Enter had happened); production code must never itself click the
    // Send button, write into the composer, or send anything to the
    // background script beyond what the user's own message actually
    // requires (nothing, here).
    const h = await runScenario(async message => {
      throw new Error("Unexpected message " + message.type);
    });
    assert.equal(h.composer.value, "Continue VibeBridge", "the composer is never rewritten");
    assert.equal(h.getCurrentSend().clickCount, undefined, "VibeBridge never clicks Send itself; the user's own click (simulated above) is the only one that counts");
    assert.deepEqual(h.notices.filter(n => n.type !== "VIBEBRIDGE_BROWSER_HEARTBEAT"), [], "a plain message triggers no background messages at all besides the routine tab heartbeat");
  }
  {
    // Most users press Enter, not the Send button. This must behave
    // identically to a click: observed, never blocked or altered.
    const h = await runScenario(async message => {
      throw new Error("Unexpected message " + message.type);
    }, "Continue VibeBridge", {active: true, status: "active"}, "enter");
    assert.equal(h.event.prevented, undefined, "Enter's default send behavior is never prevented; VibeBridge only observes");
    assert.equal(h.composer.value, "Continue VibeBridge", "pressing Enter never mutates the composer either");
    assert.deepEqual(h.notices.filter(n => n.type !== "VIBEBRIDGE_BROWSER_HEARTBEAT"), [], "a plain Enter-sent message triggers no background messages besides the routine tab heartbeat");
  }
  {
    // The one narrow exception: an explicit "remember for this project: ..."
    // phrase saves a note via a storage-only side effect. This must never
    // touch the chat transcript itself -- no composer write, no extra send.
    let rememberCalls = 0;
    const h = await runScenario(async message => {
      if (message.type === "VIBEBRIDGE_REMEMBER") {
        rememberCalls++;
        assert.equal(message.note, "the deploy script lives in scripts/deploy.sh");
        return {saved: true, project: "VibeBridge"};
      }
      throw new Error("Unexpected message " + message.type);
    }, "Remember for this project: the deploy script lives in scripts/deploy.sh");
    assert.equal(rememberCalls, 1, "the remember phrase triggers exactly one background save");
    assert.equal(h.composer.value, "Remember for this project: the deploy script lives in scripts/deploy.sh", "the composer and the sent message are never touched");
    assert.equal(h.getCurrentSend().clickCount, undefined, "saving a note never adds an extra send");
  }
  {
    // The remember side effect still requires an active license, same as
    // every other VibeBridge action -- but a missing license must never
    // affect the message that was already sent.
    let rememberCalls = 0;
    const h = await runScenario(async message => {
      if (message.type === "VIBEBRIDGE_REMEMBER") { rememberCalls++; return {saved: true}; }
      throw new Error("Unexpected message " + message.type);
    }, "Remember for this project: nope", {active: false, status: "no-subscription"});
    assert.equal(rememberCalls, 0, "no license means no note is saved");
    assert.equal(h.composer.value, "Remember for this project: nope", "the user's message is sent regardless of license status");
  }
  {
    // When VibeBridge itself is off, it must not observe the send at all --
    // not even for the remember side effect.
    const h = await runScenario(async message => {
      throw new Error("Unexpected message " + message.type);
    }, "Remember for this project: nope", {active: true, status: "active"}, "click", false);
    assert.deepEqual(h.notices.filter(n => n.type !== "VIBEBRIDGE_BROWSER_HEARTBEAT"), [], "a disabled VibeBridge sends no background messages whatsoever besides the routine tab heartbeat");
  }
  // Targeted regression guard: an explicitly-marked VibeBridge block may run
  // automatically (no click, no confirm) or via an explicit Run click (with
  // confirm) -- but either way, running an action must never write into the
  // composer or send anything. Only the result panel updates; reaching the
  // conversation at all still requires an explicit "Add result" click.
  {
    const commandSource = source.slice(source.indexOf('const executeAction = async (automatic = false)'), source.indexOf('insert.addEventListener'));
    assert.notEqual(commandSource, source, "command executor exists");
    assert.match(commandSource, /if \(!automatic && !confirm\(action\.confirm\(payload\)\)\) return;/, "manual runs still require an explicit confirm; automatic runs skip it");
    assert.match(commandSource, /if \(explicitlyMarked && allowAutomaticExecution\)/, "automatic execution is reserved for explicitly-marked VibeBridge fences");
    assert.doesNotMatch(commandSource, /writeComposer/, "running an action -- automatic or manual -- never writes into the composer");
    assert.doesNotMatch(commandSource, /send\.click\(\)|bypassNextSend\s*=\s*true/, "running an action never sends on the user's behalf");
  }
  {
    const insertSource = source.slice(source.indexOf('insert.addEventListener'), source.indexOf('insert.addEventListener') + 800);
    assert.doesNotMatch(insertSource, /send\.click\(\)|bypassNextSend\s*=\s*true/, "the manual insert button only writes the draft; it never sends for the user");
  }
  console.log("ChatGPT content-script DOM simulation: 5 scenarios passed; no-auto-send regression guard passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
