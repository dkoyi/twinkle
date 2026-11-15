'use strict';
const $ = id => document.getElementById(id);
let socket, context, stream, capture, microphone, silentGain;
let active = false, ready = false, ending = false, failed = false;
let nextPlayback = 0, generation = 0, lastSource = null;
let muted = false, callStarted = null, callTimer = null, heartbeat = null, attempt = 0;
const sources = new Set();
const bubbles = {caller: null, techtwin: null};

function phase(value) { document.body.dataset.phase = value; }
function duration() {
  const seconds = callStarted ? Math.floor((Date.now() - callStarted) / 1000) : 0;
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}
function mute(value) {
  muted = value;
  stream?.getAudioTracks().forEach(track => { track.enabled = !value; });
  $('mute').setAttribute('aria-pressed', String(value));
  $('mute').setAttribute('aria-label', value ? 'Unmute microphone' : 'Mute microphone');
  $('mute').querySelector('span').textContent = value ? 'Unmute' : 'Mute';
}
async function helperStatus() {
  try {
    const response = await fetch('/api/voice/status');
    if (!response.ok) throw new Error('Status unavailable');
    const state = await response.json();
    $('helperStatus').textContent = state.helper_connected ? 'Laptop helper connected' : 'Laptop helper not connected';
    $('helperStatus').classList.toggle('online', state.helper_connected);
    if (!state.helper_connected) $('taskDetail').textContent = state.voice_ready
      ? 'Voice is ready. Laptop actions need the computer helper.'
      : 'Add a Gemini key on the server to enable voice.';
    if (!state.voice_ready && !active) notice('Add your Gemini key on the server before calling Agent 1.', true);
  } catch {
    $('helperStatus').textContent = 'Helper status unavailable';
  }
}
function showLaptop(url) {
  if (!url || !url.startsWith('/api/screenshot')) return;
  const image = $('laptopShot');
  image.onload = () => { image.hidden = false; $('laptopEmpty').hidden = true; };
  image.onerror = () => { image.hidden = true; $('laptopEmpty').hidden = false; };
  image.src = url;
}

function status(text, hint) {
  $('status').textContent = text;
  if (hint) $('hint').textContent = hint;
}
function notice(text, error = false) {
  $('notice').textContent = text;
  $('notice').hidden = !text;
  $('notice').classList.toggle('error', error);
}
function send(data) {
  if (socket?.readyState === WebSocket.OPEN) socket.send(data);
}
function clearPlayback() {
  for (const source of sources) { source.onended = null; try { source.stop(); } catch {} }
  sources.clear();
  lastSource = null;
  nextPlayback = context?.currentTime || 0;
  $('orb').classList.remove('speaking');
}
function playAudio(event) {
  if (!context || event.generation < generation) return;
  generation = event.generation;
  const bytes = Uint8Array.from(atob(event.data), c => c.charCodeAt(0));
  const view = new DataView(bytes.buffer);
  const buffer = context.createBuffer(1, bytes.length / 2, event.rate);
  const output = buffer.getChannelData(0);
  for (let i = 0; i < output.length; i++) output[i] = view.getInt16(i * 2, true) / 32768;
  const source = context.createBufferSource();
  source.buffer = buffer;
  source.connect(context.destination);
  sources.add(source);
  lastSource = source;
  source.onended = () => { sources.delete(source); };
  const when = Math.max(nextPlayback, context.currentTime + .025);
  if (when - context.currentTime > 25) throw new Error('Speech playback fell behind. Please start again.');
  source.start(when);
  nextPlayback = when + buffer.duration;
}
function markPlayed(event) {
  if (event.generation !== generation) return;
  const currentSocket = socket;
  const acknowledge = () => {
    if (socket === currentSocket && generation === event.generation)
      send(JSON.stringify({type: 'played', mark: event.mark}));
  };
  if (!lastSource || !sources.has(lastSource)) acknowledge();
  else {
    const source = lastSource;
    const previous = source.onended;
    source.onended = () => { previous?.(); acknowledge(); };
  }
}
function transcript(event) {
  $('empty')?.remove();
  let row = bubbles[event.who];
  if (!row) {
    row = document.createElement('div');
    row.className = `bubble ${event.who}`;
    const label = document.createElement('strong');
    label.textContent = event.who === 'caller' ? 'You' : 'TechTwin';
    row.append(label, document.createElement('span'));
    $('transcript').append(row);
    bubbles[event.who] = row;
  }
  row.lastChild.textContent = event.text;
  if (event.final) bubbles[event.who] = null;
  $('transcript').scrollTop = $('transcript').scrollHeight;
}
function onMessage(event) {
  const message = JSON.parse(event.data);
  switch (message.type) {
    case 'voice_ready':
      ready = true;
      phase('connected');
      callStarted = Date.now();
      $('duration').textContent = '00:00';
      callTimer = setInterval(() => { $('duration').textContent = duration(); }, 1000);
      $('connection').textContent = 'Call connected';
      status('Agent 1 is listening', 'Say hello, or tell me what you need help with.');
      break;
    case 'audio': playAudio(message); break;
    case 'audio_end': markPlayed(message); break;
    case 'clear':
      generation = message.generation;
      clearPlayback();
      break;
    case 'transcript': transcript(message); break;
    case 'agent_speaking':
      $('orb').classList.toggle('speaking', message.speaking);
      status(message.speaking ? 'Agent 1 is speaking' : 'Agent 1 is listening', muted ? 'Your microphone is muted.' : 'You can speak at any time.');
      break;
    case 'needs_approval': notice(message.question); break;
    case 'blocked': notice(message.reason, true); break;
    case 'task_started':
      $('taskSummary').textContent = message.goal;
      $('taskDetail').textContent = 'The laptop helper is starting.';
      break;
    case 'step':
      $('taskDetail').textContent = message.summary;
      if (message.status === 'done') showLaptop(`/api/screenshot?v=${Date.now()}`);
      break;
    case 'task_finished':
      notice(message.summary);
      $('taskDetail').textContent = message.summary;
      break;
    case 'error':
      failed = true;
      phase('error');
      notice(message.message, true);
      status('Let’s try again', 'End this conversation, then start again.');
      break;
  }
}
async function cleanup() {
  clearInterval(callTimer); callTimer = null;
  clearInterval(heartbeat); heartbeat = null;
  if (callStarted) $('duration').textContent = `Last call · ${duration()}`;
  else $('duration').textContent = 'Voice over your browser';
  callStarted = null;
  active = false;
  ready = false;
  stream?.getTracks().forEach(track => track.stop());
  stream = null;
  if (capture) { capture.port.onmessage = null; capture.disconnect(); capture = null; }
  microphone?.disconnect(); microphone = null;
  silentGain?.disconnect(); silentGain = null;
  clearPlayback();
  const previousContext = context; context = null;
  if (previousContext && previousContext.state !== 'closed') await previousContext.close();
  $('start').hidden = false;
  $('start').disabled = false;
  $('end').hidden = true;
  $('stop').hidden = true;
  $('mute').hidden = true;
  mute(false);
  $('orb').classList.remove('active');
  $('connection').textContent = 'Not connected';
  phase(failed ? 'error' : 'ended');
  if (!failed) status('Call ended', 'Call Agent 1 whenever you need a hand.');
}
async function end() {
  if (ending) return;
  ending = true;
  attempt += 1;
  send(JSON.stringify({type: 'end'}));
  const previous = socket; socket = null;
  previous?.close();
  await cleanup();
  ending = false;
}
$('start').addEventListener('click', async () => {
  if (active || ending) return;
  active = true; failed = false; generation = 0;
  const currentAttempt = ++attempt;
  bubbles.caller = null; bubbles.techtwin = null;
  $('transcript').replaceChildren();
  $('start').hidden = true;
  $('end').hidden = false;
  $('mute').hidden = true;
  $('stop').hidden = true;
  $('orb').classList.add('active');
  $('connection').textContent = 'Calling Agent 1…';
  $('duration').textContent = 'Connecting…';
  phase('dialing');
  notice('');
  status('Calling Agent 1…', 'Allow your microphone when your browser asks.');
  try {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('Open this page at http://localhost:8000/talk to use your microphone.');
    // Create/resume directly within the button gesture to enable browser playback.
    const newContext = new AudioContext();
    context = newContext;
    await newContext.resume();
    if (currentAttempt !== attempt) return;
    const newStream = await navigator.mediaDevices.getUserMedia({audio: {
      channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true
    }});
    if (currentAttempt !== attempt) {
      newStream.getTracks().forEach(track => track.stop());
      return;
    }
    stream = newStream;
    await newContext.audioWorklet.addModule('/voice-demo/microphone.js');
    if (currentAttempt !== attempt) return;
    microphone = context.createMediaStreamSource(stream);
    capture = new AudioWorkletNode(context, 'microphone-capture');
    silentGain = context.createGain();
    silentGain.gain.value = 0;
    microphone.connect(capture); capture.connect(silentGain); silentGain.connect(context.destination);
    socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/voice`);
    const current = socket;
    capture.port.onmessage = event => {
      if (!ready || current.readyState !== WebSocket.OPEN) return;
      if (current.bufferedAmount > 64000) {
        failed = true; notice('The connection is too slow. Please start again.', true); void end();
      } else current.send(muted ? new ArrayBuffer(event.data.byteLength) : event.data);
    };
    current.onmessage = event => {
      if (socket !== current) return;
      try { onMessage(event); }
      catch { failed = true; notice('Audio playback failed. Please start again.', true); void end(); }
    };
    current.onerror = () => {
      if (socket !== current) return;
      failed = true;
      notice('Could not connect. Use localhost:8000/talk on this laptop and check that the server is running.', true);
    };
    current.onclose = () => {
      if (socket !== current) return;
      socket = null;
      if (!failed) { failed = true; notice('The conversation ended. You can start again.', true); }
      status('Call ended', 'Press Call Agent 1 to try again.');
      void cleanup();
    };
    $('start').hidden = true;
    $('end').hidden = false;
    $('stop').hidden = false;
    $('mute').hidden = false;
    $('orb').classList.add('active');
    heartbeat = setInterval(() => send(JSON.stringify({type: 'ping'})), 10000);
    status('Calling Agent 1…', 'Connecting your voice to TechTwin.');
  } catch (error) {
    if (currentAttempt !== attempt) return;
    failed = true;
    notice(error.name === 'NotAllowedError' ? 'Microphone access is off. Allow the microphone for this page, then try again.' : error.message, true);
    status('Let’s try again');
    await end();
  }
});
$('end').addEventListener('click', () => { void end(); });
$('mute').addEventListener('click', () => {
  mute(!muted);
  $('hint').textContent = muted ? 'Your microphone is muted.' : 'You can speak at any time.';
});
$('stop').addEventListener('click', () => {
  clearPlayback();
  send(JSON.stringify({type: 'stop'}));
  notice('Stop requested. You can keep talking to TechTwin.');
});
window.addEventListener('pagehide', () => {
  attempt += 1;
  clearInterval(callTimer); clearInterval(heartbeat);
  stream?.getTracks().forEach(track => track.stop());
  socket?.close();
});
void helperStatus();
setInterval(helperStatus, 10000);
$('clock').textContent = new Date().toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'});
