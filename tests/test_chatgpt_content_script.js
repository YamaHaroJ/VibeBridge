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
    if (selector.includes("button") && this.tagName === "BUTTON") return this;
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

async function runScenario(sendMessage) {
  const composer = new Element("TEXTAREA");
  composer.id = "prompt-textarea";
  composer.value = "Continue VibeBridge";
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
      const all = {enabled:true, token:"mock-token", activeProject:"/Users/test/VibeBridge", autoRunCommands:false};
      return Object.fromEntries(keys.filter(k => k in all).map(k => [k, all[k]]));
    },
    async set() {}
  };
  const chrome = {
    runtime: {getManifest:()=>({version:"test"}), onMessage:{addListener(){}}, async sendMessage(message) {
      notices.push(message);
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
  };
  context.window.document = document;
  vm.runInNewContext(source, context, {filename:"chatgpt.js"});

  const handler = docListeners.click[0];
  assert.ok(handler, "content script registered send handler");
  const event = {
    target:send,
    preventDefault(){this.prevented=true;},
    stopPropagation(){},
    stopImmediatePropagation(){}
  };
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
    assert.match(h.composer.value, /MOCK PROJECT CONTEXT/, "detected project context is attached automatically");
    assert.ok(h.composer.value.endsWith("Continue VibeBridge"), "the original user message remains verbatim at the end");
    assert.doesNotMatch(h.composer.value, /USER REQUEST:|VIBEBRIDGE PROJECT CONTINUITY|END VIBEBRIDGE PROJECT CONTEXT/, "internal wrapper labels are never sent");
    assert.equal(h.getCurrentSend().clickCount, 1, "matched context sends automatically exactly once");
    assert.equal(h.document.getElementById("vibebridge-context-choice"), null, "automatic flow has no extra choice step");
  }
  {
    const h = await runScenario(async message => {
      if (message.type === "VIBEBRIDGE_RESOLVE_CONTEXTS") return {matched:false, reason:"no-match"};
      throw new Error("Unexpected message " + message.type);
    });
    assert.equal(h.composer.value, "Continue VibeBridge", "no-match preserves the original draft");
    assert.equal(h.getCurrentSend().clickCount, 1, "no-match sends original text automatically");
    assert.equal(h.document.getElementById("vibebridge-notice"), null, "no-match creates no banner");
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
  console.log("ChatGPT content-script DOM simulation: 4 scenarios passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
