/* ==========================================================================
   Twinkle phone page: an iPhone call, nothing else.
   poster (one "Call Twinkle" button) -> calling -> in-call screen -> End -> dashboard.

   Real call wiring (voice/backend team). This file only shows state. It calls these if present:
     window.TwinkleVoice = { start(), stop(), mute(bool), speaker(bool), dtmf(digit) }   (dtmf optional)
     start() may return a promise; a "NotAllowedError" sends the person to help.html#mic.
   and fires window events: twinkle:talk, twinkle:end, twinkle:mute {muted}, twinkle:speaker {on}.
   The phone goes live on the backend's call_started event and ends on call_ended
   (websocket /ws/dashboard). Transcript, approvals and safety stops are NOT shown here;
   they live on the dashboard. "stop" posts /api/cancel then /api/reset.
   With no backend (opened from disk, ?practice, or window.TT_NO_WS) Call runs a practice call.
   After the call ends the page goes to body[data-next] (default dashboard.html).
   ========================================================================== */
(function () {
  'use strict';
  var TT = window.TT = window.TT || {};
  function $(id) { return document.getElementById(id); }
  var dev = $('device'), shell = $('shell'), B = location.protocol === 'file:' ? './' : '/static/';
  var qs = location.search;
  var PRACTICE = location.protocol === 'file:' || !location.host || window.TT_NO_WS || /[?&]practice/.test(qs);
  var NEXT = (document.body.getAttribute('data-next') || 'dashboard.html');

  /* ---------- icons (filled, SF Symbols-like) ---------- */
  function svg(inner) { return '<svg viewBox="0 0 24 24" aria-hidden="true">' + inner + '</svg>'; }
  var IC = {
    phone: '<path d="M6.6 10.8a15.1 15.1 0 006.6 6.6l2.2-2.2a1 1 0 011-.25 11.4 11.4 0 003.6.57 1 1 0 011 1V20a1 1 0 01-1 1A17 17 0 013 4a1 1 0 011-1h3.5a1 1 0 011 1c0 1.25.2 2.45.57 3.6a1 1 0 01-.25 1z"/>',
    speaker: '<path d="M3 9.5v5h3.6L11.5 19V5L6.6 9.5H3z"/><path d="M14.4 8.6a4.8 4.8 0 010 6.8l-1.3-1.3a2.9 2.9 0 000-4.2zM17.2 5.8a8.8 8.8 0 010 12.4l-1.3-1.3a6.9 6.9 0 000-9.8z"/>',
    speakeroff: '<path d="M3 9.5v5h3.6L11.5 19V5L6.6 9.5H3z"/>',
    video: '<path d="M3 7.5A2.5 2.5 0 015.5 5h8A2.5 2.5 0 0116 7.5v9a2.5 2.5 0 01-2.5 2.5h-8A2.5 2.5 0 013 16.5v-9zM17.5 10.4l3.6-2.3a.8.8 0 011.2.7v6.4a.8.8 0 01-1.2.7l-3.6-2.3z"/>',
    mute: '<path d="M12 14.5a3 3 0 003-3V6a3 3 0 00-6 0v5.5a3 3 0 003 3z"/><path d="M6.2 11a1 1 0 00-2 0 7.8 7.8 0 006.8 7.7V21h2v-2.3A7.8 7.8 0 0019.8 11a1 1 0 10-2 0 5.8 5.8 0 01-11.6 0z"/>',
    muteoff: '<path d="M15 9.34V6a3 3 0 00-5.94-.6L15 9.34z"/><path d="M4.27 3L3 4.27l6 6V11a3 3 0 003.7 2.92l1.5 1.5A5.8 5.8 0 016.2 11a1 1 0 00-2 0 7.8 7.8 0 006.8 7.7V21h2v-2.3c1.2-.15 2.3-.6 3.2-1.2l3.5 3.5L21 19.7z"/><path d="M17.8 11a5.7 5.7 0 01-.7 2.7l1.5 1.5A7.7 7.7 0 0019.8 11a1 1 0 10-2 0z"/>',
    stop: '<path d="M8 3.5a1.5 1.5 0 011.5 1.5v5h.5V3a1.5 1.5 0 013 0v7h.5V4.5a1.5 1.5 0 013 0V10h.5V7.5a1.5 1.5 0 013 0v6.2c0 4.4-3.4 7.8-7.8 7.8h-.4a6.8 6.8 0 01-5.5-2.8L3.6 14a1.5 1.5 0 012.3-1.9L6.5 13V5A1.5 1.5 0 018 3.5z"/>',
    end: '<path d="M12 8.5c-3.2 0-6.2 1-8.5 2.8a1.4 1.4 0 00-.1 2.1l1.6 1.6a1.4 1.4 0 001.8.1l2-1.4a1.4 1.4 0 00.6-1.2v-1.3a9.5 9.5 0 014.2 0v1.3a1.4 1.4 0 00.6 1.2l2 1.4a1.4 1.4 0 001.8-.1l1.6-1.6a1.4 1.4 0 00-.1-2.1C18.2 9.5 15.2 8.5 12 8.5z"/>',
    keypad: '<circle cx="5" cy="4.5" r="2"/><circle cx="12" cy="4.5" r="2"/><circle cx="19" cy="4.5" r="2"/><circle cx="5" cy="11" r="2"/><circle cx="12" cy="11" r="2"/><circle cx="19" cy="11" r="2"/><circle cx="5" cy="17.5" r="2"/><circle cx="12" cy="17.5" r="2"/><circle cx="19" cy="17.5" r="2"/><circle cx="12" cy="23" r="1.4"/>'
  };
  var muted = false, speakerOn = true;
  $('talkIco').innerHTML = svg(IC.phone); $('watchIco').innerHTML = svg(IC.video); $('stopIco').innerHTML = svg(IC.stop);
  $('endIco').innerHTML = svg(IC.end); $('endIco2').innerHTML = svg(IC.end); $('keyIco').innerHTML = svg(IC.keypad);
  function setSpk() { $('spkIco').innerHTML = svg(speakerOn ? IC.speaker : IC.speakeroff); }
  function setMute() { $('muteIco').innerHTML = svg(muted ? IC.muteoff : IC.mute); }
  setSpk(); setMute();

  /* ---------- fit the phone to the window ---------- */
  function fit() {
    var w = window.innerWidth, h = window.innerHeight;
    if (w <= 520) { shell.style.removeProperty('--k'); return; }
    var k = Math.min((h - 64) / 852, (w - 90) / 393, 1.4);
    shell.style.setProperty('--k', Math.max(.4, k).toFixed(3));
  }
  window.addEventListener('resize', fit); fit();
  function clock() { var d = new Date(), m = d.getMinutes(), h = d.getHours() % 12 || 12; $('clock').textContent = h + ':' + (m < 10 ? '0' : '') + m; }
  clock(); setInterval(clock, 20000);

  /* Twinkle is a still picture on the phone. She only animates on the website. */
  var still = window.TT_MASCOT || (B + 'assets/twinkle-idle-still.svg');
  $('posterImg').src = still; $('mascotImg').src = still;

  /* ---------- keypad ---------- */
  var KEYS = [['1', ''], ['2', 'ABC'], ['3', 'DEF'], ['4', 'GHI'], ['5', 'JKL'], ['6', 'MNO'], ['7', 'PQRS'], ['8', 'TUV'], ['9', 'WXYZ'], ['*', ''], ['0', '+'], ['#', '']];
  var typed = '';
  KEYS.forEach(function (k) {
    var b = document.createElement('button'); b.type = 'button'; b.className = 'key'; b.tabIndex = -1;
    b.innerHTML = '<span>' + k[0] + '</span><small>' + k[1] + '</small>';
    b.addEventListener('click', function () {
      typed = (typed + k[0]).slice(-14); $('kdisp').textContent = typed;
      try { if (window.TwinkleVoice && window.TwinkleVoice.dtmf) window.TwinkleVoice.dtmf(k[0]); } catch (x) { /* ignore */ }
    });
    $('kgrid').appendChild(b);
  });
  function keypad(on) {
    var kp = $('keypad'); kp.classList.toggle('open', on); kp.setAttribute('aria-hidden', on ? 'false' : 'true');
    Array.prototype.forEach.call(kp.querySelectorAll('button'), function (b) { b.tabIndex = on ? 0 : -1; });
    if (!on) { typed = ''; $('kdisp').innerHTML = '&nbsp;'; }
  }

  /* ---------- the call ---------- */
  var voice = 'idle', t0 = 0, clk = null, connTimer = null, ringTimer = null, ringCtx = null, ended = false;
  function setView(v) { dev.setAttribute('data-view', v); }
  function setVoice(v) { voice = v; dev.setAttribute('data-voice', v); }
  function tick() { var s = Math.max(0, Math.round((Date.now() - t0) / 1000)); $('timer').textContent = Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2); }
  function ring() {                      // two soft ring-ring tones, like dialling a person
    try {
      var AC = window.AudioContext || window.webkitAudioContext; if (!AC) return;
      ringCtx = ringCtx || new AC(); var c = ringCtx, now = c.currentTime;
      [0, .5, 2.2, 2.7].forEach(function (d) {
        var o = c.createOscillator(), g = c.createGain(); o.type = 'sine'; o.frequency.value = 440;
        g.gain.setValueAtTime(0, now + d); g.gain.linearRampToValueAtTime(.06, now + d + .03); g.gain.linearRampToValueAtTime(0, now + d + .4);
        o.connect(g); g.connect(c.destination); o.start(now + d); o.stop(now + d + .45);
      });
    } catch (e) { /* sound is optional */ }
  }
  function startCall() {
    if (voice === 'calling' || voice === 'live') return;
    ended = false; setView('call'); setVoice('calling'); $('timer').textContent = 'calling…'; ring();
    if (PRACTICE) { ringTimer = setTimeout(goLive, 3200); return; }
    var p; try { p = window.TwinkleVoice && window.TwinkleVoice.start && window.TwinkleVoice.start(); } catch (e) { p = Promise.reject(e); }
    if (p && p.catch) p.catch(function (e) { if (e && e.name === 'NotAllowedError') location.href = B + 'help.html#mic'; else fail(); });
    window.dispatchEvent(new CustomEvent('twinkle:talk'));
    clearTimeout(connTimer); connTimer = setTimeout(function () { if (voice === 'calling') fail(); }, 12000);
  }
  function fail() { setVoice('error'); $('timer').textContent = 'call failed'; }
  function goLive() {
    if (voice === 'live') return;
    clearTimeout(connTimer); clearTimeout(ringTimer);
    setVoice('live'); t0 = Date.now(); tick(); clearInterval(clk); clk = setInterval(tick, 1000);
    if (PRACTICE && window.TwinkleDemo) window.TwinkleDemo.start(handle, ((qs.match(/[?&]scenario=(\w+)/) || [])[1]) || 'dal');
  }
  function finish() {
    if (ended) return; ended = true; clearInterval(clk); clearTimeout(connTimer); clearTimeout(ringTimer);
    if (window.TwinkleDemo && window.TwinkleDemo.active) window.TwinkleDemo.stop(true);
    try { if (window.TwinkleVoice && window.TwinkleVoice.stop) window.TwinkleVoice.stop(); } catch (e) { /* ignore */ }
    window.dispatchEvent(new CustomEvent('twinkle:end'));
    keypad(false); setVoice('idle'); setView('ended');
    if (voice !== 'error') $('timer').textContent = 'call ended';
    setTimeout(function () {
      if (window.TT_NO_NAV) { ended = false; setView('poster'); setVoice('idle'); return; }
      location.href = B.replace('./', '') + NEXT;
    }, 1300);
  }
  function post(path) { try { return fetch(path, { method: 'POST' }).catch(function () {}); } catch (e) { return null; } }

  /* Only the call itself matters here. Everything else goes to the dashboard. */
  function handle(ev) {
    if (!ev || typeof ev !== 'object') return;
    if (ev.type === 'call_started') goLive();
    else if (ev.type === 'call_ended' && (voice === 'live' || voice === 'calling')) finish();
  }
  TT.handle = handle;

  document.addEventListener('click', function (e) {
    var t = e.target && e.target.closest ? e.target.closest('[data-act]') : null; if (!t) return;
    switch (t.getAttribute('data-act')) {
      case 'talk': startCall(); break;
      case 'end': finish(); break;
      case 'keypad': keypad(!$('keypad').classList.contains('open')); break;
      case 'speaker':
        speakerOn = !speakerOn; setSpk(); dev.setAttribute('data-spk', speakerOn ? 'on' : 'off'); $('spkBtn').setAttribute('aria-pressed', speakerOn ? 'true' : 'false');
        try { if (window.TwinkleVoice && window.TwinkleVoice.speaker) window.TwinkleVoice.speaker(speakerOn); } catch (x) { /* ignore */ }
        window.dispatchEvent(new CustomEvent('twinkle:speaker', { detail: { on: speakerOn } })); break;
      case 'mute':
        muted = !muted; setMute(); dev.setAttribute('data-muted', muted ? 'on' : 'off'); $('muteBtn').setAttribute('aria-pressed', muted ? 'true' : 'false');
        try { if (window.TwinkleVoice && window.TwinkleVoice.mute) window.TwinkleVoice.mute(muted); } catch (x) { /* ignore */ }
        window.dispatchEvent(new CustomEvent('twinkle:mute', { detail: { muted: muted } })); break;
      case 'watch': window.open(B.replace('./', '') + 'dashboard.html', '_blank', 'noopener'); break;
      case 'stop':
        if (window.TwinkleDemo && window.TwinkleDemo.active) window.TwinkleDemo.stop(false);
        else { var p = post('/api/cancel'); if (p && p.then) p.then(function () { post('/api/reset'); }); }
        break;
      default: break;
    }
  });

  /* ---------- real backend: same websocket as the dashboard ---------- */
  var backoff = 500;
  function connect() {
    if (PRACTICE) return;
    var ws; try { ws = new WebSocket((location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + location.host + '/ws/dashboard'); } catch (e) { return retry(); }
    ws.onopen = function () { backoff = 500; };
    ws.onmessage = function (m) { var ev; try { ev = JSON.parse(m.data); } catch (e) { return; } handle(ev); };
    ws.onclose = retry; ws.onerror = function () { try { ws.close(); } catch (e) { /* ignore */ } };
  }
  function retry() { setTimeout(connect, backoff); backoff = Math.min(3000, Math.round(backoff * 1.6)); }
  connect();
  if (/[?&]autocall/.test(qs)) setTimeout(startCall, 600);
  TT.phone = { start: startCall, end: finish };
})();
