/* Twinkle dashboard + family page logic. Vanilla JS, no build step.
   One state object, one handle(event) function. The WebSocket and the practice mode
   (demo.js) both call TT.handle(event), so they behave identically.
   Rules: unknown events are ignored, nothing throws, text is always set with textContent. */
(function () {
  'use strict';
  var TT = (window.TT = window.TT || {});
  var PAGE = document.body ? document.body.getAttribute('data-page') : '';

  /* ---------- tiny helpers ---------- */
  function $(id) { return document.getElementById(id); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function fmt(sec) {
    sec = Math.max(0, Math.floor(sec || 0));
    return Math.floor(sec / 60) + ':' + ('0' + (sec % 60)).slice(-2);
  }
  function domainOf(u) {
    try { return new URL(u, location.href).hostname.replace(/^www\./, ''); } catch (e) { return ''; }
  }
  function str(x) { return x == null ? '' : String(x); }
  function setIcon(node, name) { node.innerHTML = TT.icon(name); }   // icon markup is a trusted constant

  /* ---------- factories (also used by components.html) ---------- */
  TT.makeBubble = function (who, text, final) {
    var b = el('div', 'bubble bubble--' + (who === 'caller' ? 'caller' : 'twinkle'));
    b.setAttribute('data-final', final === false ? 'false' : 'true');
    b.appendChild(el('span', 'who', who === 'caller' ? 'You' : 'Twinkle'));
    b.appendChild(el('span', 'text', str(text)));
    return b;
  };

  function badgeFill(badge, status, n) {
    badge.innerHTML = '';
    if (status === 'done') setIcon(badge, 'check');
    else if (status === 'failed') setIcon(badge, 'x');
    else if (status === 'waiting') setIcon(badge, 'bang');
    else if (status === 'blocked') setIcon(badge, 'ban');
    else badge.textContent = str(n);
  }
  TT.makeStep = function (s, t0) {
    var d = el('div', 'step');
    var badge = el('span', 'step-badge');
    var body = el('div', 'step-body');
    body.appendChild(el('div', 'step-title'));
    body.appendChild(el('div', 'step-time'));
    d.appendChild(badge); d.appendChild(body);
    TT.updateStep(d, s, t0);
    return d;
  };
  TT.updateStep = function (d, s, t0) {
    var status = s.status || 'running';
    d.setAttribute('data-status', status);
    badgeFill(d.querySelector('.step-badge'), status, s.n);
    d.querySelector('.step-title').textContent = str(s.summary);
    var t = '';
    if (s.ts && t0) t = fmt(s.ts - t0);
    d.querySelector('.step-time').textContent = t;
  };

  /* ---------- core app: only on dashboard / family ---------- */
  if (PAGE !== 'dashboard' && PAGE !== 'family' && PAGE !== 'stage') return;

  var S = {
    call: null,            // {from, ts}
    task: null,            // {id, goal, ts, finished, summary, outcome}
    steps: [],             // {n, key, summary, status, ts}
    transcript: [],        // {who, text, final}
    pending: null,         // {question, step_n}
    blocked: null,         // {reason, url}
    shot: '',
    address: '',
    speaking: false,
    doneUntil: 0,
    oopsUntil: 0,
    connected: false,
    everConnected: false,
    history: []
  };
  TT.state = S;
  var stepEls = {};        // key -> element
  var bubbleEls = [];      // parallel to S.transcript
  var lastNow = ['', ''];
  var demoMode = false;

  /* ---------- derived state ---------- */
  function mood() {
    if (S.blocked) return 'blocked';
    if (S.pending) return 'waiting';
    if (S.task && !S.task.finished) return 'working';
    if (S.doneUntil > Date.now()) return 'done';
    if (S.call) return 'listening';
    return 'idle';
  }

  function nowText() {
    if (S.blocked) return ['I stopped here.', str(S.blocked.reason)];
    if (S.pending) return [str(S.pending.question), 'Waiting for a spoken “yes”.'];
    if (S.task && !S.task.finished) {
      var latest = '';
      for (var i = S.steps.length - 1; i >= 0; i--) {
        var st = S.steps[i];
        if (st.status === 'running' || st.status === 'done') { latest = st.summary; break; }
      }
      return [latest || 'Getting started.', 'Helping with: ' + str(S.task.goal)];
    }
    if (S.task && S.task.finished) return [S.task.summary || 'All done.', 'Is there anything else?'];
    if (S.call) return ["I'm listening.", "Say what you'd like help with."];
    return ['Ready for a call.', 'Call Twinkle and say what you need.'];
  }

  function familyText() {
    var m = mood();
    if (S.blocked) return ['Twinkle stopped to keep things safe.', str(S.blocked.reason)];
    if (S.pending) return ['Twinkle needs a yes from someone.', str(S.pending.question)];
    if (m === 'working') return ['Twinkle is helping Grandma now.', 'Helping with: ' + str(S.task && S.task.goal)];
    if (S.task && S.task.finished) return [S.task.summary || 'All done.', 'Grandma can ask for anything else.'];
    if (S.call) return ['Grandma is on a call with Twinkle.', "She's saying what she needs."];
    return ['All quiet. Nothing running.', 'You can watch from here when a call starts.'];
  }

  /* ---------- rendering ---------- */
  function renderMood() {
    var m = mood();
    document.body.setAttribute('data-state', m);
    if (m === 'done' && lastMood !== 'done') celebrate();
    lastMood = m;
    var now = $('now');
    if (now) now.setAttribute('data-tone', m);
    renderMascot();
    renderBanners();
    renderNow();
    renderChip();
  }

  function twinkleExpr() {
    var m = mood();
    if (m === 'blocked') return 'careful';
    if (S.oopsUntil > Date.now()) return 'oops';
    if (m === 'waiting') return 'asking';
    if (m === 'done') return 'success';
    if (S.speaking) return 'talking';
    if (m === 'working') return 'thinking';
    if (m === 'listening') return 'listening';
    return 'idle';
  }
  var ctrls = {};
  function ctrlFor(id) {
    if (ctrls[id]) return ctrls[id];
    var h = $(id);
    if (!h || !TT.twinkle) return null;
    ctrls[id] = TT.twinkle.mount(h);
    return ctrls[id];
  }
  function renderMascot() {
    var expr = twinkleExpr();
    ['mascot', 'emptyMascot'].forEach(function (id) { var c = ctrlFor(id); if (c) c.set(expr); });
  }
  var lastMood = '', celTimer = 0;
  function celebrate() {
    var box = $('celebrate'), cm = ctrlFor('celMascot');
    if (!box) return;
    box.classList.add('show');
    if (cm) { cm.set('idle'); setTimeout(function () { cm.set('success'); }, 280); }
    clearTimeout(celTimer);
    celTimer = setTimeout(function () { box.classList.remove('show'); if (cm) setTimeout(function () { cm.set('idle'); }, 700); }, 3400);
  }
  function oops() { S.oopsUntil = Date.now() + 4000; setTimeout(renderMood, 4100); }

  function renderNow() {
    var t = PAGE === 'family' ? familyText() : nowText();
    var mainEl = $(PAGE === 'family' ? 'familyStatus' : 'nowText');
    var subEl = $(PAGE === 'family' ? 'familySub' : 'nowSub');
    if (!mainEl) return;
    if (t[0] === lastNow[0] && t[1] === lastNow[1]) return;
    lastNow = t;
    var apply = function () {
      mainEl.textContent = t[0];
      if (subEl) subEl.textContent = t[1];
      mainEl.classList.remove('swapping');
      if (subEl) subEl.classList.remove('swapping');
    };
    if (!mainEl.textContent) { apply(); return; }       // first paint: no fade
    mainEl.classList.add('swapping');
    if (subEl) subEl.classList.add('swapping');
    setTimeout(apply, 100);                              // quick fade-out, swap, fade-in
  }

  function renderChip() {
    var chip = $('callChip');
    if (!chip) return;
    var txt = $('callChipText');
    if (S.call) {
      chip.setAttribute('data-live', 'true');
      var secs = (Date.now() / 1000) - (S.call.ts || Date.now() / 1000);
      txt.textContent = 'Call from ••• ' + str(S.call.from) + ' · ' + fmt(secs);
    } else {
      chip.setAttribute('data-live', 'false');
      txt.textContent = 'Waiting for a call';
    }
  }
  setInterval(function () { if (S.call) renderChip(); }, 1000);

  function renderBanners() {
    var ask = $('bannerAsk'), stop = $('bannerStop');
    if (!ask || !stop) return;
    var showStop = !!S.blocked;
    var showAsk = !showStop && !!S.pending;      // red wins
    if (showAsk) $('askQuestion').textContent = str(S.pending.question);
    if (showStop) $('stopReason').textContent = str(S.blocked.reason);
    var wasAsk = ask.classList.contains('is-open');
    ask.classList.toggle('is-open', showAsk);
    stop.classList.toggle('is-open', showStop);
    ask.setAttribute('aria-hidden', showAsk ? 'false' : 'true');
    stop.setAttribute('aria-hidden', showStop ? 'false' : 'true');
    ['askYes', 'askNo'].forEach(function (id) { var b = $(id); if (b) b.tabIndex = showAsk ? 0 : -1; });
    if (showAsk && !wasAsk && document.activeElement === document.body) {
      var y = $('askYes');
      if (y) { try { y.focus({ preventScroll: true }); } catch (e) { /* ignore */ } }
    }
  }

  function renderAddress() {
    var a = $('address');
    if (!a) return;
    var d = S.address;
    a.textContent = d || 'Waiting to start';
    a.setAttribute('data-empty', d ? 'false' : 'true');
  }

  function renderConn() {
    var r = $('reconnect');
    if (r) r.hidden = !(S.everConnected && !S.connected && !demoMode);
    var showPractice = !S.connected && !demoMode;
    ['practiceDal', 'practicePhone'].forEach(function (id) { var b = $(id); if (b) b.hidden = !showPractice; });
  }

  /* screenshot cross-fade: two stacked images, newest wins, never a broken flash */
  var shotA, shotB, shotFront = 'A', shotLoading = false, shotPending = '';
  function showShot(url) {
    if (!url) return;
    shotA = shotA || $('shotA'); shotB = shotB || $('shotB');
    if (!shotA || !shotB) return;
    if (shotLoading) { shotPending = url; return; }
    shotLoading = true;
    var pre = new Image();
    var done = function (ok) {
      shotLoading = false;
      if (ok) {
        var next = shotFront === 'A' ? shotB : shotA;
        var prev = shotFront === 'A' ? shotA : shotB;
        next.src = url;
        next.classList.add('on');
        prev.classList.remove('on');
        shotFront = shotFront === 'A' ? 'B' : 'A';
        var screen = $('screen');
        if (screen) screen.setAttribute('data-has-shot', 'true');
        S.shot = url;
      }
      if (shotPending) { var p = shotPending; shotPending = ''; showShot(p); }
    };
    pre.onload = function () { done(true); };
    pre.onerror = function () { done(false); };
    pre.src = url;
  }
  function clearShot() {
    shotPending = '';
    ['shotA', 'shotB'].forEach(function (id) { var i = $(id); if (i) { i.classList.remove('on'); } });
    var screen = $('screen');
    if (screen) screen.setAttribute('data-has-shot', 'false');
    S.shot = '';
  }

  function ripple(pt) {
    var host = $('ripples');
    if (!host || !pt || typeof pt.x !== 'number' || typeof pt.y !== 'number') return;
    var r = el('div', 'ripple');
    r.style.left = Math.max(0, Math.min(1, pt.x)) * 100 + '%';
    r.style.top = Math.max(0, Math.min(1, pt.y)) * 100 + '%';
    host.appendChild(r);
    setTimeout(function () { if (r.parentNode) r.parentNode.removeChild(r); }, 1000);
  }

  /* transcript ------------------------------------------------------------ */
  var convo;
  function scrollList(node, force) {
    if (!node) return;
    var near = node.scrollHeight - node.scrollTop - node.clientHeight < 140;
    if (force || near) node.scrollTop = node.scrollHeight;
  }
  function renderTranscriptEmpty() {
    convo = convo || $('convo');
    if (!convo) return;
    var e = convo.querySelector('.convo-empty');
    if (S.transcript.length && e) e.remove();
    if (!S.transcript.length && !e) convo.appendChild(el('p', 'convo-empty', 'The conversation will show up here, word for word.'));
  }
  function addTranscript(who, text, final) {
    convo = convo || $('convo');
    var wasNear = !convo || (convo.scrollHeight - convo.scrollTop - convo.clientHeight < 160);
    who = who === 'caller' ? 'caller' : 'twinkle';
    var last = -1;
    for (var i = S.transcript.length - 1; i >= 0; i--) { if (S.transcript[i].who === who) { last = i; break; } }
    var item = last >= 0 ? S.transcript[last] : null;
    if (item && item.final === false) {                       // keep editing the live bubble
      item.text = str(text); item.final = final !== false;
      if (bubbleEls[last]) {
        bubbleEls[last].querySelector('.text').textContent = item.text;
        bubbleEls[last].setAttribute('data-final', item.final ? 'true' : 'false');
      }
    } else {
      var rec = { who: who, text: str(text), final: final !== false };
      S.transcript.push(rec);
      var b = TT.makeBubble(who, rec.text, rec.final);
      bubbleEls.push(b);
      if (convo) convo.appendChild(b);
    }
    renderTranscriptEmpty();
    if (convo && wasNear) convo.scrollTop = convo.scrollHeight;
  }

  /* steps ----------------------------------------------------------------- */
  var film;
  function renderStepsEmpty() {
    film = film || $('film');
    if (!film) return;
    var e = film.querySelector('.film-empty');
    if (S.steps.length && e) e.remove();
    if (!S.steps.length && !e) film.appendChild(el('p', 'film-empty', 'Each thing Twinkle does will appear here, one after another.'));
  }
  function t0() { return S.task ? S.task.ts : 0; }
  function upsertStep(rec) {
    film = film || $('film');
    var key = rec.key != null ? rec.key : rec.n;
    var cur = null;
    for (var i = 0; i < S.steps.length; i++) { if (S.steps[i].key === key) { cur = S.steps[i]; break; } }
    if (cur) {
      if (rec.summary != null) cur.summary = rec.summary;
      if (rec.status) cur.status = rec.status;
      if (rec.ts) cur.ts = rec.ts;
      var node = stepEls[key];
      if (node) TT.updateStep(node, cur, t0());
    } else {
      cur = { n: rec.n, key: key, summary: rec.summary, status: rec.status || 'running', ts: rec.ts };
      S.steps.push(cur);
      var d = TT.makeStep(cur, t0());
      stepEls[key] = d;
      if (film) { film.appendChild(d); }
    }
    renderStepsEmpty();
    if (film) film.scrollLeft = film.scrollWidth;
    renderRecentSteps();
  }
  function renderRecentSteps() {
    var list = $('recentSteps');
    if (!list) return;
    list.innerHTML = '';
    var last = S.steps.slice(-3);
    if (!last.length) { list.appendChild(el('li', 'history-empty', 'Nothing yet.')); return; }
    last.forEach(function (s) { var li = el('li'); li.appendChild(TT.makeStep(s, t0())); list.appendChild(li); });
  }

  function settleRunning(outcome) {
    var to = (outcome === 'done' || outcome === 'blocked') ? 'done' : 'failed';
    S.steps.forEach(function (st) { if (st.status === 'running') upsertStep({ n: st.n, key: st.key, status: to }); });
  }
  function clearSteps() {
    S.steps = []; stepEls = {};
    film = film || $('film');
    if (film) film.innerHTML = '';
    renderStepsEmpty();
    renderRecentSteps();
  }
  function clearTranscript() {
    S.transcript = []; bubbleEls = [];
    convo = convo || $('convo');
    if (convo) convo.innerHTML = '';
    renderTranscriptEmpty();
  }

  /* family history -------------------------------------------------------- */
  var OUTCOME = { done: 'Done', cancelled: 'Stopped', blocked: 'Stopped for safety', timeout: 'Took too long', failed: "Didn't work" };
  function loadHistory() {
    try { var raw = localStorage.getItem('twinkle.history'); if (raw) S.history = JSON.parse(raw) || []; } catch (e) { S.history = []; }
    if (!Array.isArray(S.history)) S.history = [];
  }
  function saveHistory() { try { localStorage.setItem('twinkle.history', JSON.stringify(S.history.slice(0, 8))); } catch (e) { /* ignore */ } }
  function renderHistory() {
    var list = $('history');
    if (!list) return;
    list.innerHTML = '';
    if (!S.history.length) { list.appendChild(el('li', 'history-empty', 'Finished help will be listed here.')); return; }
    S.history.slice(0, 6).forEach(function (h) {
      var li = el('li');
      li.appendChild(el('span', '', h.goal || 'Help'));
      li.appendChild(el('span', 'meta', (OUTCOME[h.outcome] || 'Finished') + (h.duration ? ' · ' + fmt(h.duration) : '')));
      list.appendChild(li);
    });
  }

  /* ---------- the one event handler ---------- */
  function fullRender() {
    renderAddress(); renderRecentSteps(); renderHistory(); renderMood(); renderConn();
  }

  function applySnapshot(ev) {
    var root = $('app');
    if (root) root.classList.add('no-anim');
    S.call = ev.call ? { from: ev.call.from, ts: ev.call.ts } : null;
    S.task = ev.task ? { id: ev.task.id, goal: ev.task.goal, ts: ev.task.ts, finished: !!ev.task.finished, summary: ev.task.summary, outcome: ev.task.outcome } : null;
    S.pending = ev.pending_approval ? { question: ev.pending_approval.question, step_n: ev.pending_approval.step_n } : null;
    S.blocked = ev.blocked ? { reason: ev.blocked.reason, url: ev.blocked.url } : null;
    S.speaking = false;
    clearSteps(); clearTranscript();
    (Array.isArray(ev.steps) ? ev.steps : []).forEach(function (s) { upsertStep({ n: s.n, summary: s.summary, status: s.status, ts: s.ts }); });
    if (S.pending) markWaiting(S.pending.step_n, S.pending.question);
    if (S.blocked) upsertStep({ n: '!', key: 'blocked', summary: 'Stopped to keep things safe', status: 'blocked', ts: ev.ts });
    (Array.isArray(ev.transcript) ? ev.transcript : []).forEach(function (t) {
      S.transcript.push({ who: t.who === 'caller' ? 'caller' : 'twinkle', text: str(t.text), final: true });
      var b = TT.makeBubble(t.who, t.text, true); bubbleEls.push(b);
      var c = $('convo'); if (c) c.appendChild(b);
    });
    renderTranscriptEmpty();
    S.address = S.task && S.steps.length ? '' : '';
    if (ev.screenshot_url) showShot(ev.screenshot_url); else clearShot();
    document.body.removeAttribute('data-speaking');
    lastNow = ['', ''];
    fullRender();
    scrollList($('convo'), true);
    setTimeout(function () { if (root) root.classList.remove('no-anim'); }, 700);
  }

  function markWaiting(n, question) {
    var key = n;
    var found = S.steps.some(function (s) { return s.key === key; });
    if (found) upsertStep({ n: n, key: key, status: 'waiting' });
    else upsertStep({ n: n, key: key, summary: question, status: 'waiting', ts: Date.now() / 1000 });
  }

  function handle(ev) {
    try {
      if (!ev || typeof ev !== 'object') return;
      switch (ev.type) {
        case 'snapshot': applySnapshot(ev); break;
        case 'call_started':
          S.call = { from: str(ev.from), ts: ev.ts };
          renderMood(); break;
        case 'call_ended':
          S.call = null; S.speaking = false;
          document.body.removeAttribute('data-speaking');
          renderMood(); break;
        case 'transcript':
          addTranscript(ev.who, ev.text, ev.final); break;
        case 'task_started':
          S.task = { id: ev.task_id, goal: str(ev.goal), ts: ev.ts, finished: false };
          S.pending = null; S.blocked = null; S.doneUntil = 0; S.address = '';
          clearSteps(); renderAddress(); renderMood(); break;
        case 'step': {
          var n = ev.n;
          var status = ev.status === 'done' || ev.status === 'failed' ? ev.status : 'running';
          if (S.pending && S.pending.step_n === n) status = 'waiting';
          upsertStep({ n: n, summary: ev.summary, status: status, ts: ev.ts });
          if (status === 'failed') oops();
          if (ev.url) { S.address = domainOf(ev.url) || S.address; renderAddress(); }
          if (ev.point) ripple(ev.point);
          renderMood(); break;
        }
        case 'screenshot':
          if (ev.page_url) { S.address = domainOf(ev.page_url) || S.address; renderAddress(); }
          showShot(ev.url); break;
        case 'needs_approval':
          S.pending = { question: str(ev.question), step_n: ev.step_n };
          markWaiting(ev.step_n, str(ev.question));
          renderMood(); break;
        case 'approval_result':
          if (S.pending) {
            var key = S.pending.step_n;
            S.pending = null;
            upsertStep({ n: key, key: key, status: ev.approved ? 'running' : 'failed', ts: ev.ts });
          }
          renderMood(); break;
        case 'blocked':
          S.blocked = { reason: str(ev.reason), url: ev.url };
          S.pending = null;
          if (ev.url) { S.address = domainOf(ev.url) || S.address; renderAddress(); }
          settleRunning('blocked');
          upsertStep({ n: '!', key: 'blocked', summary: 'Stopped to keep things safe', status: 'blocked', ts: ev.ts });
          renderMood(); break;
        case 'task_finished':
          if (S.task) { S.task.finished = true; S.task.summary = str(ev.summary); S.task.outcome = ev.outcome; }
          S.pending = null;
          settleRunning(ev.outcome);
          if (ev.outcome === 'failed' || ev.outcome === 'timeout') oops();
          if (ev.outcome === 'done') { S.doneUntil = Date.now() + 5000; setTimeout(renderMood, 5100); }
          S.history.unshift({ goal: S.task ? S.task.goal : 'Help', outcome: ev.outcome, duration: ev.duration_s });
          S.history = S.history.slice(0, 8); saveHistory(); renderHistory();
          renderMood(); break;
        case 'agent_speaking':
          S.speaking = !!ev.speaking;
          document.body.setAttribute('data-speaking', S.speaking ? 'true' : 'false');
          var vl = $('voiceLabel'); if (vl) vl.textContent = S.speaking ? 'Twinkle is talking' : (S.call ? 'Twinkle is listening' : 'Quiet');
          renderMascot(); break;
        case 'error':
          if (window.console && console.info) console.info('[Twinkle]', ev.where, ev.message);
          break;
        case 'reset':
          S.call = null; S.task = null; S.pending = null; S.blocked = null; S.speaking = false; S.doneUntil = 0; S.oopsUntil = 0; S.address = '';
          document.body.setAttribute('data-speaking', 'false');
          clearSteps(); clearTranscript(); clearShot(); renderAddress();
          lastNow = ['', '']; renderMood(); break;
        default: break;     // unknown types are ignored on purpose
      }
    } catch (e) {
      if (window.console && console.warn) console.warn('[Twinkle] ignored a bad message', e);
    }
  }
  TT.handle = handle;

  /* ---------- buttons ---------- */
  function post(path) { try { return fetch(path, { method: 'POST' }).catch(function () {}); } catch (e) { return null; } }
  function demoOn() { return !!(window.TwinkleDemo && window.TwinkleDemo.active); }

  function answer(yes) {
    if (!S.pending) return;
    if (demoOn()) window.TwinkleDemo.answer(!!yes);
    else post(yes ? '/api/confirm' : '/api/cancel');
  }
  function act(name) {
    var D = window.TwinkleDemo;
    switch (name) {
      case 'confirm': answer(true); break;
      case 'cancel': answer(false); break;
      case 'stop':
        if (demoOn()) D.stop(false);
        else { var p = post('/api/cancel'); if (p && p.then) p.then(function () { post('/api/reset'); }); else post('/api/reset'); }
        break;
      case 'reset':
        if (D && (D.active || demoMode)) { var sc = D.scenario || 'dal'; D.stop(true); D.start(handle, sc); }
        else post('/api/reset');
        break;
      case 'practice-dal': startDemo('dal'); break;
      case 'practice-phone': startDemo('iphone'); break;
      default: break;
    }
  }
  function startDemo(sc) {
    if (!window.TwinkleDemo) return;
    demoMode = true;
    if (window.TwinkleDemo.active) window.TwinkleDemo.stop(true);
    window.TwinkleDemo.start(handle, sc);
    renderConn();
  }
  TT.startDemo = startDemo;

  document.addEventListener('click', function (e) {
    var t = e.target && e.target.closest ? e.target.closest('[data-act]') : null;
    if (t) act(t.getAttribute('data-act'));
  });
  document.addEventListener('keydown', function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var tag = (e.target && e.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
    var k = (e.key || '').toLowerCase();
    if (k === 'y' && S.pending) { e.preventDefault(); answer(true); }
    else if (k === 'n' && S.pending) { e.preventDefault(); answer(false); }
  });

  /* ---------- connection ---------- */
  var backoff = 500, ws = null;
  function connect() {
    if (demoMode || window.TT_NO_WS || location.protocol === 'file:' || !location.host) { renderConn(); return; }
    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    try { ws = new WebSocket(proto + '//' + location.host + '/ws/dashboard'); } catch (e) { retry(); return; }
    ws.onopen = function () { S.connected = true; S.everConnected = true; backoff = 500; renderConn(); };
    ws.onmessage = function (m) {
      var ev; try { ev = JSON.parse(m.data); } catch (e) { return; }
      if (!demoOn()) handle(ev);
    };
    ws.onclose = function () { S.connected = false; renderConn(); retry(); };
    ws.onerror = function () { try { ws.close(); } catch (e) { /* ignore */ } };
  }
  function retry() { setTimeout(connect, backoff); backoff = Math.min(3000, Math.round(backoff * 1.6)); }

  /* ---------- start up ---------- */
  function boot() {
    var mount = $('brandMark'); if (mount) mount.innerHTML = TT.markSVG;
    loadHistory();
    renderTranscriptEmpty(); renderStepsEmpty(); renderAddress();
    fullRender();
    var q = (location.search.match(/[?&]demo=([^&]*)/) || [])[1];
    var force = window.TT_FORCE_DEMO;
    var want = q != null ? (q === '' || q === '1' || q === 'true' ? 'dal' : q) : force;
    if (want && window.TwinkleDemo) { startDemo(want === 'iphone' ? 'iphone' : 'dal'); }
    else connect();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
