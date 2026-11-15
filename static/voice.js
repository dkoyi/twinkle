/* The real call behind the phone page: microphone in, Twinkle's voice out, over /ws/voice.
 *
 * phone.js only shows the call. It calls window.TwinkleVoice.start / stop / mute / speaker, and
 * goes live when the server publishes call_started on /ws/dashboard. The audio code is
 * Maulik's from voice_demo/talk.js (AudioWorklet capture, 16-bit PCM playback, played marks).
 */
(function () {
  'use strict';
  var socket = null, context = null, stream = null, capture = null, microphone = null, silentGain = null, out = null;
  var ready = false, muted = false, speakerOn = true, callSid = null, heartbeat = null;
  var nextPlayback = 0, generation = 0, lastSource = null, sources = new Set();

  function send(data) { if (socket && socket.readyState === WebSocket.OPEN) socket.send(data); }

  function clearPlayback() {
    sources.forEach(function (s) { s.onended = null; try { s.stop(); } catch (e) { /* already stopped */ } });
    sources.clear(); lastSource = null;
    nextPlayback = context ? context.currentTime : 0;
  }

  function playAudio(ev) {
    if (!context || ev.generation < generation) return;
    generation = ev.generation;
    var bytes = Uint8Array.from(atob(ev.data), function (c) { return c.charCodeAt(0); });
    var view = new DataView(bytes.buffer);
    var buffer = context.createBuffer(1, bytes.length / 2, ev.rate);
    var data = buffer.getChannelData(0);
    for (var i = 0; i < data.length; i++) data[i] = view.getInt16(i * 2, true) / 32768;
    var source = context.createBufferSource();
    source.buffer = buffer; source.connect(out);
    sources.add(source); lastSource = source;
    source.onended = function () { sources.delete(source); };
    var when = Math.max(nextPlayback, context.currentTime + 0.025);
    source.start(when); nextPlayback = when + buffer.duration;
  }

  function markPlayed(ev) {
    if (ev.generation !== generation) return;
    var current = socket;
    var ack = function () { if (socket === current && generation === ev.generation) send(JSON.stringify({ type: 'played', mark: ev.mark })); };
    if (!lastSource || !sources.has(lastSource)) ack();
    else { var prev = lastSource.onended; lastSource.onended = function () { if (prev) prev(); ack(); }; }
  }

  function onMessage(m) {
    var ev = JSON.parse(m.data);
    if (ev.type === 'voice_ready') { ready = true; callSid = ev.call_sid; }
    else if (ev.type === 'audio') playAudio(ev);
    else if (ev.type === 'audio_end') markPlayed(ev);
    else if (ev.type === 'clear') { generation = ev.generation; clearPlayback(); }
  }

  function cleanup() {
    clearInterval(heartbeat); heartbeat = null; ready = false;
    if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
    stream = null;
    if (capture) { capture.port.onmessage = null; capture.disconnect(); capture = null; }
    if (microphone) { microphone.disconnect(); microphone = null; }
    if (silentGain) { silentGain.disconnect(); silentGain = null; }
    clearPlayback();
    var c = context; context = null; out = null;
    if (c && c.state !== 'closed') c.close().catch(function () {});
  }

  async function start() {
    if (socket) return;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia)
      throw new Error('Open this page at http://localhost:8000/talk to use your microphone.');
    generation = 0;
    context = new AudioContext();               // created inside the button press so audio may play
    await context.resume();
    out = context.createGain(); out.gain.value = speakerOn ? 1 : 0; out.connect(context.destination);
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    } catch (e) { cleanup(); throw e; }      // NotAllowedError: the phone page sends the person to help#mic
    await context.audioWorklet.addModule('/voice-demo/microphone.js');
    microphone = context.createMediaStreamSource(stream);
    capture = new AudioWorkletNode(context, 'microphone-capture');
    silentGain = context.createGain(); silentGain.gain.value = 0;
    microphone.connect(capture); capture.connect(silentGain); silentGain.connect(context.destination);

    var ws = new WebSocket((location.protocol === 'https:' ? 'wss' : 'ws') + '://' + location.host + '/ws/voice');
    socket = ws;
    capture.port.onmessage = function (e) {
      if (!ready || ws.readyState !== WebSocket.OPEN || ws.bufferedAmount > 64000) return;
      ws.send(muted ? new ArrayBuffer(e.data.byteLength) : e.data);
    };
    ws.onmessage = function (m) { if (socket === ws) { try { onMessage(m); } catch (e) { stop(); } } };
    ws.onclose = function () { if (socket === ws) { socket = null; callSid = null; cleanup(); } };
    heartbeat = setInterval(function () { send(JSON.stringify({ type: 'ping' })); }, 10000);
  }

  function stop() {
    var sid = callSid; callSid = null;
    send(JSON.stringify({ type: 'end' }));
    var ws = socket; socket = null;
    if (ws) ws.close();
    cleanup();
    if (sid) fetch('/api/voice/end', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ call_sid: sid }), keepalive: true }).catch(function () {});
  }

  function mute(on) { muted = !!on; if (stream) stream.getAudioTracks().forEach(function (t) { t.enabled = !muted; }); }
  function speaker(on) { speakerOn = !!on; if (out) out.gain.value = speakerOn ? 1 : 0; }

  window.addEventListener('pagehide', function () {
    if (callSid && navigator.sendBeacon) navigator.sendBeacon('/api/voice/end', JSON.stringify({ call_sid: callSid }));
    send(JSON.stringify({ type: 'end' }));
  });

  window.TwinkleVoice = { start: start, stop: stop, mute: mute, speaker: speaker };
})();
