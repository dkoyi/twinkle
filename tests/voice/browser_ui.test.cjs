// Run with: node --test tests/voice/browser_ui.test.cjs
// Browser audio and permission prompts are stubbed; no microphone is recorded.
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function setup(getMicrophone) {
  const elements = new Map();
  class Element {
    constructor() {
      this.hidden = false; this.textContent = ''; this.dataset = {}; this.listeners = {};
      this.attributes = {}; this.children = []; this.classList = {add(){},remove(){},toggle(){}};
      this.span = {textContent:''};
    }
    addEventListener(type, fn) { this.listeners[type] = fn; }
    setAttribute(name, value) { this.attributes[name] = value; }
    querySelector() { return this.span; }
    append(...children) { this.children.push(...children); this.lastChild = children.at(-1); }
    replaceChildren() { this.children = []; }
    remove() {}
  }
  const element = id => {
    if (!elements.has(id)) elements.set(id, new Element());
    return elements.get(id);
  };
  const tracks = [{enabled:true,stopped:false,stop(){this.stopped=true;}}];
  const media = {getTracks:()=>tracks,getAudioTracks:()=>tracks};
  const contexts = [], sockets = [], timers = new Map();
  let timerId = 0;
  class AudioContext {
    constructor() {
      contexts.push(this); this.state='running'; this.currentTime=0;
      this.audioWorklet={addModule:async()=>{}}; this.destination={};
    }
    async resume() {}
    createMediaStreamSource(){return {connect(){},disconnect(){}};}
    createGain(){return {gain:{value:1},connect(){},disconnect(){}};}
    async close(){this.state='closed';}
  }
  class AudioWorkletNode {
    constructor(){this.port={};}
    connect(){} disconnect(){}
  }
  class WebSocket {
    static OPEN=1;
    constructor(){this.readyState=1;this.bufferedAmount=0;this.sent=[];sockets.push(this);}
    send(data){this.sent.push(data);}
    close(){this.readyState=3;this.onclose?.();}
  }
  const sandbox = {
    document:{getElementById:element,createElement:()=>new Element(),body:new Element()},
    navigator:{mediaDevices:{getUserMedia:()=>getMicrophone ? getMicrophone(media) : Promise.resolve(media)}},
    AudioContext,AudioWorkletNode,WebSocket,Date,ArrayBuffer,Uint8Array,DataView,
    location:{protocol:'http:',host:'localhost:8000'},
    window:{addEventListener(){}},
    fetch:async()=>({ok:true,json:async()=>({voice_ready:true,helper_connected:false})}),
    setInterval:fn=>{const id=++timerId;timers.set(id,fn);return id;},
    clearInterval:id=>timers.delete(id),
    atob:text=>Buffer.from(text,'base64').toString('binary')
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../voice_demo/talk.js'),'utf8'),sandbox);
  return {element,tracks,contexts,sockets,timers,sandbox};
}

const flush = () => new Promise(resolve => setImmediate(resolve));

test('phone call connects, mutes, hangs up, and releases audio resources',async()=>{
  const app=setup();
  await app.element('start').listeners.click();
  assert.equal(app.sandbox.document.body.dataset.phase,'dialing');
  const socket=app.sockets[0];
  socket.onmessage({data:JSON.stringify({type:'voice_ready'})});
  assert.equal(app.sandbox.document.body.dataset.phase,'connected');
  assert.equal(app.element('duration').textContent,'00:00');
  app.element('mute').listeners.click();
  assert.equal(app.tracks[0].enabled,false);
  assert.equal(app.element('mute').attributes['aria-pressed'],'true');
  app.element('end').listeners.click();
  await flush();
  assert.equal(socket.readyState,3);
  assert.equal(app.tracks[0].stopped,true);
  assert.equal(app.contexts[0].state,'closed');
  assert.equal(app.sandbox.document.body.dataset.phase,'ended');
  assert.equal(app.element('start').hidden,false);
  assert.equal(app.timers.size,1); // Only the helper-status refresh remains.
});

test('hanging up during microphone permission cannot start a late call',async()=>{
  let resolveMicrophone;
  const app=setup(media=>new Promise(resolve=>{resolveMicrophone=()=>resolve(media);}));
  const pending=app.element('start').listeners.click();
  await flush();
  app.element('end').listeners.click();
  await flush();
  resolveMicrophone();
  await pending;
  assert.equal(app.sockets.length,0);
  assert.equal(app.tracks[0].stopped,true);
  assert.equal(app.contexts[0].state,'closed');
  assert.equal(app.element('start').hidden,false);
});

test('microphone denial leaves a retryable phone screen',async()=>{
  const app=setup(()=>Promise.reject(Object.assign(new Error(),{name:'NotAllowedError'})));
  await app.element('start').listeners.click();
  assert.equal(app.sandbox.document.body.dataset.phase,'error');
  assert.match(app.element('notice').textContent,/Allow the microphone/);
  assert.equal(app.element('start').hidden,false);
  assert.equal(app.sockets.length,0);
});
