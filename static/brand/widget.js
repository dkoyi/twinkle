/* The floating Twinkle: a small helper that stays in the corner of every page.
 *
 * It looks the same wherever you are (phone page, dashboard), shows what Twinkle is doing in one
 * plain sentence, changes mood with the call, and shows Yes / No whenever she is asking first.
 *
 * It is read-only except for Yes / No (POST /api/confirm and /api/cancel, the same calls the
 * dashboard makes). It is skipped inside an iframe, so the phone page's embedded dashboard does not
 * get a second one.
 *
 * Where its events come from:
 *   - a page that sets <body data-feeds-widget> (the dashboard) dispatches "techtwin:event" on
 *     document for every event, including practice mode, so the widget just listens;
 *   - any other page: the widget opens its own read-only /ws/dashboard connection.
 *
 * It also fills two optional spots if the page has them:
 *   #phoneTwinkle  the phone's contact photo (mood follows body[data-phase] and #orb.speaking)
 *   #emptyMascot   the dashboard's empty-screen picture
 */
(function () {
  'use strict';
  var TT = (window.TT = window.TT || {});
  if (!TT.twinkle) return;
  var embedded = false;
  try { embedded = window.self !== window.top; } catch (e) { embedded = true; }

  function $(id) { return document.getElementById(id); }
  function str(x) { return x == null ? '' : String(x); }

  /* ---------- optional spots on the page ---------- */
  var phoneMood = null, emptyMood = null;
  function mountSpots() {
    var p = $('phoneTwinkle'), e = $('emptyMascot');
    if (p) phoneMood = TT.twinkle.mount(p, { expr: 'idle' });
    if (e) emptyMood = TT.twinkle.mount(e, { expr: 'idle' });
    if (p) {
      var sync = function () {
        var phase = document.body.getAttribute('data-phase') || 'idle';
        var orb = $('orb');
        var speaking = !!(orb && orb.classList.contains('speaking'));
        var m = phase === 'error' ? 'oops'
          : phase === 'dialing' ? 'listening'
          : phase === 'connected' ? (speaking ? 'talking' : 'listening')
          : 'idle';
        phoneMood.set(m);
      };
      new MutationObserver(sync).observe(document.body, { attributes: true, attributeFilter: ['data-phase'] });
      var orb = $('orb');
      if (orb) new MutationObserver(sync).observe(orb, { attributes: true, attributeFilter: ['class'] });
      sync();
    }
  }

  if (embedded) { if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mountSpots); else mountSpots(); return; }

  /* ---------- state ---------- */
  var S = { call: null, task: null, steps: [], pending: null, blocked: null, speaking: false, doneUntil: 0, oopsUntil: 0 };
  var dash = document.body && document.body.hasAttribute('data-feeds-widget');
  var phonePage = !!$('start');           // the phone page has the Call button
  var root, bubble, textEl, actions, face, mood, timer = 0, open = true, pinned = false, idleTimer = 0, lastState = '';

  function stateName() {
    if (S.blocked) return 'blocked';
    if (S.pending) return 'waiting';
    if (S.task && !S.task.finished) return 'working';
    if (S.doneUntil > Date.now()) return 'done';
    if (S.call) return 'listening';
    return 'idle';
  }
  function expr(state) {
    if (state === 'blocked') return 'careful';
    if (S.oopsUntil > Date.now()) return 'oops';
    if (state === 'waiting') return 'asking';
    if (state === 'done') return 'success';
    if (S.speaking) return 'talking';
    if (state === 'working') return 'thinking';
    if (state === 'listening') return 'listening';
    return 'idle';
  }
  function words(state) {
    if (state === 'blocked') return str(S.blocked && S.blocked.reason) || 'I stopped to keep things safe.';
    if (state === 'waiting') return str(S.pending && S.pending.question) || 'Shall I go ahead?';
    if (state === 'working') {
      for (var i = S.steps.length - 1; i >= 0; i--) {
        var st = S.steps[i];
        if (st && (st.status === 'running' || st.status === 'done') && st.summary) return str(st.summary);
      }
      return 'Getting started.';
    }
    if (state === 'done') return str(S.task && S.task.summary) || 'All done!';
    if (state === 'listening') return S.speaking ? 'Twinkle is talking.' : 'I’m listening. Tell me what you need.';
    return phonePage ? 'Hi, I’m Twinkle. Press Call Twinkle and tell me what you need.' : 'Hi, I’m Twinkle. I’m here when you need me.';
  }

  /* ---------- the widget ---------- */
  function build() {
    root = document.createElement('div');
    root.id = 'ttw';
    root.className = 'ttw';
    root.setAttribute('role', 'complementary');
    root.setAttribute('aria-label', 'Twinkle, your helper');
    root.innerHTML =
      '<div class="ttw-bubble" id="ttwBubble">' +
        '<p class="ttw-text" id="ttwText" aria-live="polite"></p>' +
        '<div class="ttw-actions" id="ttwActions" hidden>' +
          '<button type="button" class="ttw-yes" id="ttwYes">Yes, go ahead</button>' +
          '<button type="button" class="ttw-no" id="ttwNo">No, don’t</button>' +
        '</div>' +
      '</div>' +
      '<button type="button" class="ttw-face" id="ttwFace" aria-expanded="true" aria-label="Twinkle. Show or hide her message"></button>';
    document.body.appendChild(root);
    bubble = $('ttwBubble'); textEl = $('ttwText'); actions = $('ttwActions'); face = $('ttwFace');
    mood = TT.twinkle.mount(face, { expr: 'idle' });
    try { open = sessionStorage.getItem('ttw.open') !== 'no'; } catch (e) { /* ignore */ }
    face.addEventListener('click', function () {
      if (pinned) return;
      open = !open; clearTimeout(idleTimer); idleTimer = -1;
      try { sessionStorage.setItem('ttw.open', open ? 'yes' : 'no'); } catch (e) { /* ignore */ }
      render();
    });
    $('ttwYes').addEventListener('click', function () { answer(true); });
    $('ttwNo').addEventListener('click', function () { answer(false); });
  }

  function answer(yes) {
    try { fetch(yes ? '/api/confirm' : '/api/cancel', { method: 'POST' }).catch(function () {}); } catch (e) { /* ignore */ }
  }

  var lastText = '';
  function render() {
    if (!root) return;
    var st = stateName();
    pinned = st === 'waiting' || st === 'blocked';     // she is asking or has stopped: never hide that
    root.setAttribute('data-state', st);
    mood.set(expr(st));
    var t = words(st);
    if (t !== lastText) { textEl.textContent = t; lastText = t; }
    // Say hello, then tuck the idle message away; speak up again as soon as something happens.
    if (st !== lastState) {
      if (st !== 'idle') { open = true; clearTimeout(idleTimer); idleTimer = 0; }
      lastState = st;
    }
    if (st === 'idle' && open && !idleTimer) {
      idleTimer = setTimeout(function () { idleTimer = 0; if (stateName() === 'idle') { open = false; render(); } }, 12000);
    }
    var show = pinned || open;
    bubble.hidden = !show;
    face.setAttribute('aria-expanded', show ? 'true' : 'false');
    actions.hidden = st !== 'waiting';
    try { sessionStorage.setItem('ttw.last', JSON.stringify({ t: t, s: st })); } catch (e) { /* ignore */ }
  }

  function refreshLater(ms) { clearTimeout(timer); timer = setTimeout(render, ms); }

  /* ---------- events ---------- */
  function handle(ev) {
    if (!ev || typeof ev !== 'object') return;
    switch (ev.type) {
      case 'snapshot':
        S.call = ev.call && ev.call.type !== 'call_ended' ? ev.call : null;
        S.task = ev.task || null;
        S.steps = Array.isArray(ev.steps) ? ev.steps : [];
        S.pending = ev.pending_approval || null;
        S.blocked = ev.blocked || null;
        S.speaking = !!ev.speaking;
        break;
      case 'reset':
        S = { call: null, task: null, steps: [], pending: null, blocked: null, speaking: false, doneUntil: 0, oopsUntil: 0 };
        break;
      case 'call_started': S.call = { ts: ev.ts }; break;
      case 'call_ended': S.call = null; S.speaking = false; break;
      case 'task_started': S.task = { goal: ev.goal, finished: false }; S.steps = []; S.pending = null; S.blocked = null; S.doneUntil = 0; break;
      case 'step': {
        var found = false;
        for (var i = 0; i < S.steps.length; i++) if (S.steps[i].n === ev.n) { S.steps[i] = { n: ev.n, summary: ev.summary, status: ev.status }; found = true; }
        if (!found) S.steps.push({ n: ev.n, summary: ev.summary, status: ev.status });
        if (ev.status === 'failed') { S.oopsUntil = Date.now() + 4000; refreshLater(4100); }
        break;
      }
      case 'needs_approval': S.pending = { question: ev.question }; break;
      case 'approval_result': S.pending = null; break;
      case 'blocked': S.blocked = { reason: ev.reason }; S.pending = null; break;
      case 'task_finished':
        if (S.task) { S.task.finished = true; S.task.summary = ev.summary; S.task.outcome = ev.outcome; }
        S.pending = null;
        if (ev.outcome === 'done') { S.doneUntil = Date.now() + 6000; refreshLater(6100); }
        if (ev.outcome === 'failed' || ev.outcome === 'timeout') { S.oopsUntil = Date.now() + 4000; refreshLater(4100); }
        break;
      case 'agent_speaking': S.speaking = !!ev.speaking; break;
      default: return;
    }
    render();
  }
  TT.widgetHandle = handle;

  /* own read-only connection, only where the page does not already feed us */
  var ws = null, backoff = 800, everOpen = false, failures = 0;
  function connect() {
    if (location.protocol === 'file:' || !location.host) return;
    try { ws = new WebSocket((location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + location.host + '/ws/dashboard'); }
    catch (e) { return retry(); }
    ws.onopen = function () { backoff = 800; everOpen = true; failures = 0; };
    ws.onmessage = function (m) { var ev; try { ev = JSON.parse(m.data); } catch (e) { return; } handle(ev); };
    ws.onclose = retry;
    ws.onerror = function () { try { ws.close(); } catch (e) { /* ignore */ } };
  }
  function retry() {
    // A static copy of the site (no server) can never answer: stop after a few tries instead of nagging.
    if (!everOpen && ++failures >= 4) return;
    setTimeout(connect, backoff); backoff = Math.min(15000, Math.round(backoff * 1.7));
  }

  function boot() {
    build();
    mountSpots();
    try {                                    // keep what she last said while the page loads, so she looks the same across pages
      var last = JSON.parse(sessionStorage.getItem('ttw.last') || 'null');
      if (last && last.t) { textEl.textContent = last.t; lastText = last.t; }
    } catch (e) { /* ignore */ }
    render();
    if (dash) document.addEventListener('techtwin:event', function (e) { handle(e.detail); });
    else connect();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
