const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const source = fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");

async function harness({storage = {token: "test-token"}, fetchImpl} = {}) {
  let listener;
  const calls = [];
  const chrome = {
    runtime: {onMessage: {addListener(fn) { listener = fn; }}},
    storage: {local: {
      async get() { return {...storage}; },
      async set(values) { Object.assign(storage, values); }
    }}
  };
  const context = {
    chrome,
    fetch: async (url, options = {}) => {
      calls.push({url, options});
      if (fetchImpl) return fetchImpl(url, options);
      return {ok: true, async json() { return {matched: true, context: "MOCK PROJECT HANDOFF", projects: [{name:"VibeBridge", path:"github:YamaHaroJ/VibeBridge"}], saved:true}; }};
    },
    URL, console, setTimeout, clearTimeout
  };
  vm.runInNewContext(source, context, {filename:"background.js"});
  async function send(message) {
    return await new Promise((resolve, reject) => {
      let returned;
      try { returned = listener(message, {}, resolve); }
      catch (e) { reject(e); return; }
      if (returned !== true && returned !== undefined) resolve(returned);
      setTimeout(() => reject(new Error("background listener timed out")), 500);
    });
  }
  return {send, calls, storage};
}

(async () => {
  {
    const h = await harness();
    const result = await h.send({type:"VIBEBRIDGE_RESOLVE_CONTEXTS", text:"continue VibeBridge", projects:[]});
    assert.equal(result.matched, true);
    assert.match(result.context, /MOCK PROJECT HANDOFF/);
    assert.equal(h.calls[0].url, "http://127.0.0.1:43127/contexts");
    assert.equal(h.storage.activeProject, "github:YamaHaroJ/VibeBridge");
  }
  {
    const h = await harness();
    const payload = JSON.stringify({projects:[{repository:"YamaHaroJ/VibeBridge",summary:"summary",handoff:"handoff",todos:[{task:"test",status:"open"}],decisions:["separate memory"]}]});
    const result = await h.send({type:"VIBEBRIDGE_CHECKPOINT_MESSAGE",payload:{summary:payload,conversation:"conv-1"}});
    assert.equal(result.saved, true);
    assert.equal(h.calls[0].url, "http://127.0.0.1:43127/checkpoint");
    assert.equal(h.calls[0].options.headers.Authorization, "Bearer test-token");
    const body = JSON.parse(h.calls[0].options.body);
    assert.equal(body.summary, payload);
    assert.equal(body.conversation, "conv-1");
  }
  // Save a handoff, then resolve a separate conversation against the mocked
  // persisted checkpoint to prove the bridge can carry it across conversations.
  {
    let savedCheckpoint = "";
    const h = await harness({fetchImpl: async (url, options = {}) => {
      if (url.endsWith("/checkpoint")) {
        savedCheckpoint = JSON.parse(options.body).summary;
        return {ok:true, async json() { return {saved:true}; }};
      }
      if (url.endsWith("/contexts")) {
        const memory = JSON.parse(savedCheckpoint || '{"projects":[]}');
        const handoff = memory.projects?.[0]?.handoff || "NO SAVED HANDOFF";
        return {ok:true, async json() { return {matched:true, context:"Recovered handoff: " + handoff, projects:[{name:"VibeBridge",path:"github:YamaHaroJ/VibeBridge"}]}; }};
      }
      throw new Error("Unexpected mocked endpoint: " + url);
    }});
    const memory = JSON.stringify({projects:[{repository:"YamaHaroJ/VibeBridge",summary:"Durable summary",handoff:"resume at integration tests",todos:[{task:"DOM simulation",status:"open"}],decisions:["separate project memory"]}]});
    const saved = await h.send({type:"VIBEBRIDGE_CHECKPOINT_MESSAGE",payload:{summary:memory,conversation:"conversation-one"}});
    assert.equal(saved.saved, true);
    const recovered = await h.send({type:"VIBEBRIDGE_RESOLVE_CONTEXTS",text:"continue in a new conversation",projects:[]});
    assert.match(recovered.context, /resume at integration tests/);
    assert.match(recovered.context, /Recovered handoff/);
  }

  {
    const h = await harness({storage:{}});
    const result = await h.send({type:"VIBEBRIDGE_CHECKPOINT_MESSAGE",payload:{summary:"{}"}});
    assert.match(result.error, /token missing/i);
    assert.equal(h.calls.length, 0);
  }
  {
    const h = await harness({fetchImpl: async () => { throw new Error("Failed to fetch"); }});
    const result = await h.send({type:"VIBEBRIDGE_RESOLVE_CONTEXTS",text:"continue"});
    assert.equal(result.ok, false);
    assert.match(result.error, /Failed to fetch/);
  }
  {
    const h = await harness({fetchImpl: async () => ({ok:false, async json() { return {error:"GitHub save failed"}; }})});
    const result = await h.send({type:"VIBEBRIDGE_CHECKPOINT_MESSAGE",payload:{summary:"{}",conversation:"conv-1"}});
    assert.equal(result.ok, false);
    assert.match(result.error, /GitHub save failed/);
  }
  console.log("background bridge integration: 6 scenarios passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
