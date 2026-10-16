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
  }
  dispatchEvent() { return true; }
}

async function runScenario(sendMessage) {
  const composer = new Element("TEXTAREA");
  composer.id = "prompt-textarea";
  composer.value = "Continue VibeBridge";
  const send = new Element("BUTTON");
  send.setAttribute("data-testid", "send-button");
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
      if (selector === 'button[data-testid="send-button"]' || selector === 'button[aria-label*="Send"]') return send;
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
    runtime: {getManifest:()=>({version:"test"}), async sendMessage(message) {
      notices.push(message);
      return await sendMessage(message);
    }},
    storage: {local:storage, onChanged:{addListener(){}}}
  };
  class MutationObserver { constructor(fn) { this.fn = fn; } observe() {} disconnect() {} }
  const context = {
    window:{__vibeBridgeInstalled:false, getSelection:()=>({removeAllRanges(){},addRange(){}})},
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
  await new Promise(resolve => setTimeout(resolve, 0));
  return {composer, send, notices, event, body, document};
}

(async () => {
  {
    const h = await runScenario(async message => {
      if (message.type === "VIBEBRIDGE_RESOLVE_CONTEXTS") {
        return {matched:true, context:"MOCK PROJECT CONTEXT", projects:[{name:"VibeBridge",path:"/Users/test/VibeBridge"}]};
      }
      throw new Error("Unexpected message " + message.type);
    });
    assert.match(h.composer.value, /MOCK PROJECT CONTEXT/, "resolved project context is attached to the outgoing prompt");
    assert.match(h.composer.value, /Continue VibeBridge/, "original user request remains present");
    assert.equal((h.composer.value.match(/VIBEBRIDGE PROJECT CONTEXT/g) || []).length, 2, "context wrapper appears exactly once with matching end marker");
    assert.equal(h.send.clickCount, 1, "original send is replayed exactly once");
    assert.ok(h.notices.some(m => m.type === "VIBEBRIDGE_RESOLVE_CONTEXTS"));
    const notice = h.document.getElementById("vibebridge-notice-message");
    assert.match(notice.textContent, /context attached for this message/i);
  }
  {
    const h = await runScenario(async () => { throw new Error("Extension context invalidated."); });
    assert.equal(h.composer.value, "Continue VibeBridge", "invalidated context leaves original prompt intact");
    assert.equal(h.send.clickCount, undefined, "invalidated extension must not replay/send the prompt");
    const notice = h.document.getElementById("vibebridge-notice-message");
    assert.match(notice.textContent, /Reload this tab to reconnect/i);
  }
  {
    const h = await runScenario(async () => { throw new Error("Failed to fetch"); });
    assert.equal(h.composer.value, "Continue VibeBridge");
    assert.equal(h.send.clickCount, 1, "recoverable agent error still replays the original send once");
    const notice = h.document.getElementById("vibebridge-notice-message");
    assert.match(notice.textContent, /original message will still be sent/i);
  }
  console.log("ChatGPT content-script DOM simulation: 3 scenarios passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
