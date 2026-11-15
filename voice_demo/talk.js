'use strict';
const $ = id => document.getElementById(id);
let socket, context, stream, capture, microphone, silentGain;
let active = false, ready = false, ending = false, failed = false;
let nextPlayback = 0, generation = 0, lastSource = null;
const sources = new Set();
const bubbles = {caller: null, techtwin: null};

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
      $('connection').textContent = 'Connected';
      status('I’m listening', 'Say hello, or tell me what you need help with.');
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
      status(message.speaking ? 'TechTwin is speaking' : 'I’m listening', 'You can speak at any time.');
      break;
    case 'needs_approval': notice(message.question); break;
    case 'blocked': notice(message.reason, true); break;
    case 'task_finished': notice(message.summary); break;
    case 'error':
      failed = true;
      notice(message.message, true);
      status('Let’s try again', 'End this conversation, then start again.');
      break;
  }
}
async function cleanup() {
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
  $('orb').classList.remove('active');
  $('connection').textContent = 'Not connected';
  if (!failed) status('Ready when you are', 'Use your laptop’s microphone and speakers.');
}
async function end() {
  if (ending) return;
  ending = true;
  send(JSON.stringify({type: 'end'}));
  const previous = socket; socket = null;
  previous?.close();
  await cleanup();
  ending = false;
}
$('start').addEventListener('click', async () => {
  if (active || ending) return;
  active = true; failed = false; generation = 0;
  $('start').disabled = true;
  notice('');
  status('Connecting…', 'Allow your microphone when your browser asks.');
  try {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('Open this page at http://localhost:8000/talk to use your microphone.');
    // Create/resume directly within the button gesture to enable browser playback.
    context = new AudioContext();
    await context.resume();
    stream = await navigator.mediaDevices.getUserMedia({audio: {
      channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true
    }});
    await context.audioWorklet.addModule('/voice-demo/microphone.js');
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
      } else current.send(event.data);
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
      status('Conversation ended', 'Press Start talking to try again.');
      void cleanup();
    };
    $('start').hidden = true;
    $('end').hidden = false;
    $('stop').hidden = false;
    $('orb').classList.add('active');
    status('Connecting…', 'Getting TechTwin ready to talk.');
  } catch (error) {
    failed = true;
    notice(error.name === 'NotAllowedError' ? 'Microphone access is off. Allow the microphone for this page, then try again.' : error.message, true);
    status('Let’s try again');
    await end();
  }
});
$('end').addEventListener('click', () => { void end(); });
$('stop').addEventListener('click', () => {
  clearPlayback();
  send(JSON.stringify({type: 'stop'}));
  notice('Stop requested. You can keep talking to TechTwin.');
});
window.addEventListener('pagehide', () => {
  stream?.getTracks().forEach(track => track.stop());
  socket?.close();
});
