/* TechTwin dashboard logic.
 *
 * Talks to the backend only through the event contract in docs/BACKEND_HANDOFF.md:
 *   WS  /ws/dashboard   -> {"type":"snapshot", ...} then live events
 *   POST /api/confirm | /api/cancel | /api/reset | /api/stop(optional)
 * Unknown event types are ignored, so a backend change can never break the page.
 */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const el = {
    body: document.body,
    callChip: $("callChip"), callChipText: $("callChipText"),
    link: $("linkState"), practice: $("practiceBtn"),
    stop: $("stopBtn"), reset: $("resetBtn"),
    address: $("address"), screen: $("screen"), empty: $("screenEmpty"),
    shotA: $("shotA"), shotB: $("shotB"), ripple: $("ripple"),
    ask: $("askSheet"), askQ: $("askQuestion"), yes: $("yesBtn"), no: $("noBtn"),
    stopSheet: $("stopSheet"), stopReason: $("stopReason"),
    voice: $("voice"), nowLine: $("nowLine"), nowSub: $("nowSub"),
    bubbles: $("bubbles"), talkEmpty: $("talkEmpty"),
    film: $("film"), filmEmpty: $("filmEmpty"),
  };

  const state = fresh();
  function fresh() {
    return { call: null, task: null, steps: [], transcript: [], pending: null,
             blocked: null, speaking: false, address: "", doneFlash: false };
  }

  /* ---------- small helpers ---------- */
  function domainOf(u) {
    try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return u || ""; }
  }
  function mmss(sec) {
    sec = Math.max(0, Math.round(sec));
    return Math.floor(sec / 60) + ":" + String(sec % 60).padStart(2, "0");
  }
  async function post(path, body) {
    if (demo.active) return Promise.resolve();
    const error = $("controlError");
    error.hidden = true;
    try {
      const response = await fetch(path, { method: "POST",
        ...(body ? {headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)} : {}) });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Please describe what you need help with.");
      return result;
    } catch (failure) {
      error.textContent = failure.message || "Could not reach TechTwin. Please try again.";
      error.hidden = false;
    }
  }

  /* ---------- overall mood (drives the aura colour) ---------- */
  function mood() {
    if (state.blocked) return "blocked";
    if (state.pending) return "waiting";
    if (state.task && !state.task.finished) return "working";
    if (state.doneFlash) return "done";
    if (state.call) return "listening";
    return "idle";
  }

  /* ---------- renderers ---------- */
  function renderMood() {
    el.body.dataset.state = mood();
    renderNow();
    renderCall();
  }

  let callTimer = null;
  function renderCall() {
    const c = state.call;
    el.callChip.classList.toggle("live", !!c);
    if (!c) {
      el.callChipText.textContent = "Waiting for a call";
      clearInterval(callTimer); callTimer = null;
      return;
    }
    const tick = () => {
      const who = c.from ? "Call from ••• " + c.from : "On a call";
      el.callChipText.textContent = who + "  ·  " + mmss(Date.now() / 1000 - c.ts);
    };
    tick();
    if (!callTimer) callTimer = setInterval(tick, 1000);
  }

  function nowCopy() {
    if (state.blocked) return ["I stopped here.", state.blocked.reason];
    if (state.pending) return [state.pending.question, "Waiting for a spoken “yes”."];
    const t = state.task;
    if (t && !t.finished) {
      const last = [...state.steps].reverse().find((s) => s.status === "running" || s.status === "done");
      return [last ? last.summary : "Getting started…", t.goal ? "Helping with: " + t.goal : ""];
    }
    if (t && t.finished) return [t.summary || "All done.", "Is there anything else?"];
    if (state.call) return ["I’m listening.", "Say what you’d like help with."];
    return ["Ready to help.", "Open Talk to TechTwin to start a conversation."];
  }
  let lastNow = "";
  function renderNow() {
    const [line, sub] = nowCopy();
    el.nowSub.textContent = sub || "";
    if (line === lastNow) return;
    lastNow = line;
    el.nowLine.classList.add("swap");
    setTimeout(() => { el.nowLine.textContent = line; el.nowLine.classList.remove("swap"); }, 160);
  }

  function renderVoice() { el.voice.classList.toggle("talk", state.speaking); }

  function renderApproval() {
    const p = state.pending;
    if (p) el.askQ.textContent = p.question;
    el.ask.classList.toggle("show", !!p);
    el.ask.setAttribute("aria-hidden", p ? "false" : "true");
  }
  function renderBlocked() {
    const b = state.blocked;
    if (b) el.stopReason.textContent = b.reason;
    el.stopSheet.classList.toggle("show", !!b);
    el.stopSheet.setAttribute("aria-hidden", b ? "false" : "true");
  }

  function renderAddress() {
    el.address.textContent = domainOf(state.address) || (state.task ? "Opening…" : "Waiting to start");
  }

  /* transcript */
  function bubbleNode(m) {
    const li = document.createElement("li");
    li.className = "bubble " + m.who + (m.final ? "" : " partial");
    li.dataset.who = m.who;
    li.innerHTML = "<small></small><span></span>";
    li.querySelector("small").textContent = m.who === "caller" ? "You" : "TechTwin";
    li.querySelector("span").textContent = m.text;
    return li;
  }
  function renderTranscript(rebuild) {
    el.talkEmpty.classList.toggle("hide", state.transcript.length > 0);
    if (rebuild) {
      el.bubbles.innerHTML = "";
      state.transcript.forEach((m) => el.bubbles.appendChild(bubbleNode(m)));
    }
    el.bubbles.scrollTop = el.bubbles.scrollHeight;
  }
  function addTranscript(ev) {
    const partialIndex = state.transcript.findLastIndex((m) => m.who === ev.who && !m.final);
    const last = state.transcript[partialIndex];
    const node = el.bubbles.children[partialIndex];
    if (last && !last.final && last.who === ev.who) {
      last.text = ev.text; last.final = !!ev.final;
      node.className = "bubble " + last.who + (last.final ? "" : " partial");
      node.querySelector("span").textContent = last.text;
    } else {
      const m = { who: ev.who, text: ev.text, final: !!ev.final };
      state.transcript.push(m);
      el.bubbles.appendChild(bubbleNode(m));
    }
    el.talkEmpty.classList.add("hide");
    el.bubbles.scrollTop = el.bubbles.scrollHeight;
  }

  /* steps */
  const ICON = {
    done: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
    failed: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    waiting: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M12 6v7M12 17.5v.5"/></svg>',
    blocked: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><circle cx="12" cy="12" r="8"/><path d="M6.5 6.5l11 11"/></svg>',
  };
  function stepNode(s) {
    const li = document.createElement("li");
    li.dataset.n = s.n;
    paintStep(li, s);
    return li;
  }
  function paintStep(li, s) {
    li.className = "step " + s.status;
    const badge = s.status === "running" ? "<span>" + s.n + "</span>"
      : s.status === "done" ? ICON.done
      : s.status === "failed" ? ICON.failed
      : s.status === "waiting" ? ICON.waiting
      : s.status === "blocked" ? ICON.blocked : s.n;
    li.innerHTML = '<div class="badge">' + badge + '</div><div class="txt"><div class="what"></div><div class="when"></div></div>';
    li.querySelector(".what").textContent = s.summary;
    li.querySelector(".when").textContent = s.when;
  }
  function stepWhen(ts) {
    const t0 = state.task ? state.task.ts : ts;
    return mmss(ts - t0);
  }
  function upsertStep(s) {
    const i = state.steps.findIndex((x) => x.key === s.key);
    if (i >= 0) {
      Object.assign(state.steps[i], s);
      const li = el.film.querySelector('[data-n="' + CSS.escape(String(state.steps[i].n)) + '"]');
      if (li) paintStep(li, state.steps[i]);
    } else {
      state.steps.push(s);
      el.film.appendChild(stepNode(s));
    }
    el.filmEmpty.classList.add("hide");
    el.film.scrollLeft = el.film.scrollWidth;
  }
  function renderSteps() {
    el.film.innerHTML = "";
    state.steps.forEach((s) => el.film.appendChild(stepNode(s)));
    el.filmEmpty.classList.toggle("hide", state.steps.length > 0);
    el.film.scrollLeft = el.film.scrollWidth;
  }

  /* screenshots: preload, then cross-fade so it never flickers */
  let front = el.shotA, back = el.shotB, shotSeq = 0;
  function showShot(url) {
    if (!url) return;
    const seq = ++shotSeq;
    const probe = new Image();
    probe.onload = () => {
      if (seq !== shotSeq) return;
      back.src = url;
      back.classList.add("on");
      front.classList.remove("on");
      [front, back] = [back, front];
      el.empty.classList.add("hide");
    };
    probe.onerror = () => {};
    probe.src = url;
  }
  function clearShot() {
    shotSeq++;
    el.shotA.classList.remove("on"); el.shotB.classList.remove("on");
    el.empty.classList.remove("hide");
  }
  function pingAt(pt) {
    if (!pt || typeof pt.x !== "number") return;
    el.ripple.style.left = (pt.x * 100) + "%";
    el.ripple.style.top = (pt.y * 100) + "%";
    el.ripple.classList.remove("go");
    void el.ripple.offsetWidth;
    el.ripple.classList.add("go");
  }

  /* ---------- applying data ---------- */
  function applySnapshot(s) {
    Object.assign(state, fresh());
    if (s.call && s.call.type !== "call_ended") state.call = Object.assign({ ts: Date.now() / 1000 }, s.call);
    if (s.task) state.task = s.task;
    state.pending = s.pending_approval || null;
    state.blocked = s.blocked || null;
    state.speaking = !!s.speaking;
    state.address = s.page_url || "";
    state.transcript = (s.transcript || []).map((m) => ({ who: m.who, text: m.text, final: m.final !== false }));
    state.steps = (s.steps || []).map((x) => ({
      key: "s" + x.n, n: x.n, summary: x.summary, status: x.status,
      when: stepWhen(x.ts || Date.now() / 1000),
    }));
    renderTranscript(true);
    renderSteps();
    renderApproval();
    renderBlocked();
    renderAddress();
    renderVoice();
    if (s.screenshot_url) showShot(s.screenshot_url); else clearShot();
    renderMood();
  }

  function handle(ev) {
    if (!ev || !ev.type) return;
    switch (ev.type) {
      case "snapshot": applySnapshot(ev); return;

      case "reset":
        Object.assign(state, fresh());
        clearShot(); renderTranscript(true); renderSteps();
        renderApproval(); renderBlocked(); renderAddress(); renderVoice(); renderMood();
        return;

      case "call_started":
        state.call = { ts: ev.ts, from: ev.from, sid: ev.call_sid };
        break;
      case "call_ended":
        state.call = null; state.speaking = false; renderVoice();
        break;

      case "transcript":
        addTranscript(ev);
        break;

      case "task_started":
        state.task = { id: ev.task_id, goal: ev.goal, ts: ev.ts, finished: false };
        state.steps = []; state.blocked = null; state.pending = null; state.doneFlash = false;
        state.address = "";
        renderSteps(); renderBlocked(); renderApproval(); renderAddress();
        break;

      case "step": {
        const s = { key: "s" + ev.n, n: ev.n, summary: ev.summary, status: ev.status, when: stepWhen(ev.ts) };
        upsertStep(s);
        if (ev.url) { state.address = ev.url; renderAddress(); }
        if (ev.point) pingAt(ev.point);
        break;
      }

      case "screenshot":
        if (ev.page_url) { state.address = ev.page_url; renderAddress(); }
        showShot(ev.url);
        return;

      case "needs_approval":
        state.pending = { question: ev.question, reason: ev.reason, stepN: ev.step_n };
        if (ev.step_n != null) {
          const cur = state.steps.find((x) => x.n === ev.step_n);
          if (cur) upsertStep({ key: cur.key, status: "waiting" });
        }
        renderApproval();
        break;

      case "approval_result": {
        const n = state.pending && state.pending.stepN;
        state.pending = null;
        if (n != null) {
          const cur = state.steps.find((x) => x.n === n);
          if (cur) upsertStep({ key: cur.key, status: ev.approved ? "running" : "failed" });
        }
        renderApproval();
        break;
      }

      case "blocked": {
        state.blocked = { reason: ev.reason, url: ev.url };
        state.pending = null;
        upsertStep({ key: "blocked", n: state.steps.length + 1, summary: "Stopped: " + ev.reason, status: "blocked",
                     when: stepWhen(ev.ts) });
        renderApproval(); renderBlocked();
        break;
      }

      case "task_finished":
        if (state.task) {
          state.task.finished = true;
          state.task.summary = ev.summary;
          state.task.outcome = ev.outcome;
        }
        state.pending = null;
        renderApproval();
        if (ev.outcome === "done") {
          state.doneFlash = true;
          setTimeout(() => { state.doneFlash = false; renderMood(); }, 5000);
        }
        break;

      case "agent_speaking":
        state.speaking = !!ev.speaking; renderVoice();
        return;

      case "error":
        if (window.console) console.warn("[TechTwin]", ev.where, ev.message);
        return;

      default: return; // unknown event: ignore, never crash
    }
    renderMood();
  }

  /* ---------- buttons ---------- */
  el.yes.addEventListener("click", () => demo.active ? demo.answer(true) : post("/api/confirm"));
  el.no.addEventListener("click", () => demo.active ? demo.answer(false) : post("/api/cancel"));
  el.stop.addEventListener("click", () => demo.active ? demo.stop() : post("/api/stop"));
  el.reset.addEventListener("click", () => demo.active ? demo.stop(true) : post("/api/reset"));
  el.practice.addEventListener("click", () => demo.start(handle));
  $("safetyDemoBtn").addEventListener("click", () => {
    if (!demo.active) post('/api/start_task', {goal: 'Open http://localhost:8000/static/safety-demo.html'});
  });
  $("taskForm").addEventListener("submit", (event) => {
    event.preventDefault();
    if (!demo.active) post("/api/start_task", {goal: $("taskGoal").value});
  });

  /* ---------- connection with automatic reconnect ---------- */
  const demo = window.TechTwinDemo || { active: false, start() {}, stop() {}, answer() {} };
  let ws = null, retry = 0, everConnected = false;

  function connect() {
    if (demo.active) return;
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    try { ws = new WebSocket(proto + "//" + location.host + "/ws/dashboard"); }
    catch (e) { scheduleRetry(); return; }

    ws.onopen = () => { retry = 0; everConnected = true; el.link.hidden = true; el.practice.hidden = true; };
    ws.onmessage = (m) => { try { handle(JSON.parse(m.data)); } catch (e) { /* ignore bad frame */ } };
    ws.onclose = () => { if (!demo.active) scheduleRetry(); };
    ws.onerror = () => { try { ws.close(); } catch (e) {} };
  }
  function scheduleRetry() {
    el.link.hidden = !everConnected;
    el.practice.hidden = false;
    retry = Math.min(retry + 1, 6);
    setTimeout(connect, Math.min(500 * retry, 3000));
  }

  /* ---------- go ---------- */
  renderMood(); renderTranscript(true); renderSteps();
  const params = new URLSearchParams(location.search);
  if (params.has("demo")) {
    el.practice.hidden = false;
    demo.start(handle, params.get("demo") || "dal");
  } else {
    connect();
  }

  window.TechTwinDashboard = { handle };
})();
