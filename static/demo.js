/* Practice mode: plays a scripted fake call through the same handler the real
 * WebSocket uses, so the dashboard can be built and demoed with no backend.
 * Open /static/dashboard.html?demo=dal  or  ?demo=iphone
 */
(function () {
  "use strict";

  /* ---------- fake screenshots (generic pages, no real brands) ---------- */
  const W = 1280, H = 800;
  function svg(inner) {
    const s = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + W + ' ' + H + '" width="' + W + '" height="' + H + '">' +
      '<rect width="100%" height="100%" fill="#fff"/>' + inner + "</svg>";
    return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(s);
  }
  const bar = (label, color) =>
    '<rect width="1280" height="76" fill="' + color + '"/><text x="40" y="49" font-family="Arial" font-size="30" font-weight="700" fill="#fff">' + label + "</text>";
  const thumb = (x, y, c, t, sel) =>
    '<g><rect x="' + x + '" y="' + y + '" width="360" height="200" rx="16" fill="' + c + '"/>' +
    '<circle cx="' + (x + 180) + '" cy="' + (y + 100) + '" r="34" fill="rgba(255,255,255,.85)"/><path d="M' + (x + 170) + " " + (y + 82) + "l30 18l-30 18z\" fill=\"#444\"/>" +
    '<text x="' + x + '" y="' + (y + 236) + '" font-family="Arial" font-size="22" font-weight="700" fill="#222">' + t + "</text>" +
    '<text x="' + x + '" y="' + (y + 264) + '" font-family="Arial" font-size="18" fill="#777">Home Kitchen · 1.2M views</text>' +
    (sel ? '<rect x="' + (x - 8) + '" y="' + (y - 8) + '" width="376" height="292" rx="22" fill="none" stroke="#1f8a8f" stroke-width="6"/>' : "") + "</g>";

  const SHOTS = {
    home: svg(bar("Search", "#3a6ea5") +
      '<text x="640" y="300" text-anchor="middle" font-family="Arial" font-size="84" font-weight="700" fill="#3a6ea5">VideoTube</text>' +
      '<rect x="290" y="360" width="700" height="72" rx="36" fill="#fff" stroke="#c9d3da" stroke-width="3"/>' +
      '<text x="330" y="408" font-family="Arial" font-size="28" fill="#9aa7b0">Search for a video</text>'),
    typed: svg(bar("Search", "#3a6ea5") +
      '<text x="640" y="300" text-anchor="middle" font-family="Arial" font-size="84" font-weight="700" fill="#3a6ea5">VideoTube</text>' +
      '<rect x="290" y="360" width="700" height="72" rx="36" fill="#fff" stroke="#1f8a8f" stroke-width="4"/>' +
      '<text x="330" y="408" font-family="Arial" font-size="28" fill="#222">dal recipe Ranveer Brar</text>'),
    results: svg(bar("Results for “dal recipe Ranveer Brar”", "#3a6ea5") +
      thumb(60, 130, "#e7b36a", "Restaurant style dal tadka", true) +
      thumb(460, 130, "#a8c98b", "Easy moong dal in 20 minutes", false) +
      thumb(860, 130, "#d98f8f", "Dal makhani, slow cooked", false) +
      thumb(60, 440, "#8fb3d9", "Five dals every kitchen needs", false) +
      thumb(460, 440, "#c9a0dc", "Dal fry for beginners", false) +
      thumb(860, 440, "#9ad0c4", "Tadka secrets explained", false)),
    player: svg(bar("Restaurant style dal tadka", "#3a6ea5") +
      '<rect x="120" y="110" width="1040" height="585" rx="18" fill="#2b2b2b"/>' +
      '<circle cx="640" cy="402" r="70" fill="rgba(255,255,255,.9)"/><path d="M618 365l62 37l-62 37z" fill="#2b2b2b"/>' +
      '<rect x="120" y="715" width="1040" height="10" rx="5" fill="#ddd"/><rect x="120" y="715" width="30" height="10" rx="5" fill="#1f8a8f"/>'),
    store: svg(bar("Pear Store", "#444") +
      '<rect x="120" y="140" width="520" height="560" rx="30" fill="#eef1f4"/>' +
      '<rect x="270" y="200" width="220" height="440" rx="40" fill="#3b4350"/><rect x="288" y="222" width="184" height="396" rx="26" fill="#9fb4d4"/>' +
      '<text x="720" y="250" font-family="Arial" font-size="52" font-weight="700" fill="#222">Pear Phone 17</text>' +
      '<text x="720" y="310" font-family="Arial" font-size="34" fill="#555">From $799</text>' +
      '<rect x="720" y="360" width="340" height="76" rx="38" fill="#2f6fdb"/>' +
      '<text x="890" y="410" text-anchor="middle" font-family="Arial" font-size="28" font-weight="700" fill="#fff">Add to bag</text>'),
    bag: svg(bar("Your bag", "#444") +
      '<text x="120" y="190" font-family="Arial" font-size="44" font-weight="700" fill="#222">Review your bag</text>' +
      '<rect x="120" y="230" width="1040" height="130" rx="20" fill="#eef1f4"/>' +
      '<text x="160" y="310" font-family="Arial" font-size="30" fill="#333">Pear Phone 17 · 1 item · $799</text>' +
      '<rect x="120" y="420" width="420" height="80" rx="40" fill="#2f6fdb"/>' +
      '<text x="330" y="472" text-anchor="middle" font-family="Arial" font-size="28" font-weight="700" fill="#fff">Check out</text>'),
    checkout: svg(bar("Checkout", "#444") +
      '<text x="120" y="190" font-family="Arial" font-size="44" font-weight="700" fill="#222">Payment details</text>' +
      '<rect x="120" y="240" width="700" height="72" rx="14" fill="#fff" stroke="#c9d3da" stroke-width="3"/>' +
      '<text x="150" y="288" font-family="Arial" font-size="26" fill="#9aa7b0">Card number</text>' +
      '<rect x="120" y="340" width="330" height="72" rx="14" fill="#fff" stroke="#c9d3da" stroke-width="3"/>' +
      '<text x="150" y="388" font-family="Arial" font-size="26" fill="#9aa7b0">MM / YY</text>' +
      '<rect x="490" y="340" width="330" height="72" rx="14" fill="#fff" stroke="#c9d3da" stroke-width="3"/>' +
      '<text x="520" y="388" font-family="Arial" font-size="26" fill="#9aa7b0">CVV</text>' +
      '<rect x="120" y="470" width="700" height="72" rx="14" fill="#fff" stroke="#c9d3da" stroke-width="3"/>' +
      '<text x="150" y="518" font-family="Arial" font-size="26" fill="#9aa7b0">Password</text>'),
  };

  /* ---------- scripts ---------- */
  const CALLER = "caller", TWIN = "techtwin";

  function dal(h) {
    return [
      [300, () => h({ type: "call_started", call_sid: "demo", from: "4821" })],
      ...say(TWIN, "Hi, I’m TechTwin. What would you like help with on your computer today?", 700),
      [1100, () => {}],
      ...say(CALLER, "My daughter told me about a dal recipe video. Can you play it?", 0),
      ...say(TWIN, "You’d like to watch a dal recipe video on YouTube. Is that right?", 500),
      ...say(CALLER, "Yes please.", 0),
      [400, () => h({ type: "task_started", task_id: "t1", goal: "Play a dal recipe video" })],
      ...say(TWIN, "Lovely. I’m opening YouTube now.", 400),
      ...stepFlow(h, 1, "Opened the video website", "home", "https://www.videotube.example/", { x: 0.5, y: 0.5 }),
      ...say(TWIN, "I’m typing the name of the video in the search box.", 300),
      ...stepFlow(h, 2, "Typed the name of the video", "typed", "https://www.videotube.example/", { x: 0.5, y: 0.52 }),
      ...stepFlow(h, 3, "Found a video that looks right", "results", "https://www.videotube.example/results", { x: 0.2, y: 0.34 }),
      [500, () => h({ type: "step", task_id: "t1", n: 4, action: "click", summary: "Ready to press play", status: "running" })],
      ...say(TWIN, "I found it. There is a play button. Shall I press it?", 300),
      [200, () => h({ type: "needs_approval", task_id: "t1", step_n: 4, question: "I found it. Shall I press play?", reason: "Playing a video" })],
      ["ASK", null],
      [700, () => h({ type: "step", task_id: "t1", n: 4, action: "click", summary: "Pressed play", status: "done", point: { x: 0.5, y: 0.5 } })],
      [200, () => h({ type: "screenshot", task_id: "t1", n: 5, url: SHOTS.player, page_url: "https://www.videotube.example/watch" })],
      ...say(TWIN, "The video is playing now. Is there anything else?", 900),
      [300, () => h({ type: "task_finished", task_id: "t1", outcome: "done", summary: "The video is playing now.", duration_s: 38, steps: 4 })],
    ];
  }

  function iphone(h) {
    return [
      [300, () => h({ type: "call_started", call_sid: "demo", from: "4821" })],
      ...say(TWIN, "Hi, I’m TechTwin. What would you like help with today?", 500),
      ...say(CALLER, "Buy me the new iPhone.", 0),
      ...say(TWIN, "You’d like to buy a new phone. I’ll take a look, and I’ll check with you first.", 400),
      [400, () => h({ type: "task_started", task_id: "t2", goal: "Buy the new phone" })],
      ...stepFlow(h, 1, "Opened a store page", "store", "https://www.pearstore.example/phone", { x: 0.5, y: 0.5 }),
      [500, () => h({ type: "step", task_id: "t2", n: 2, action: "click", summary: "Ready to add it to the bag", status: "running" })],
      [200, () => h({ type: "needs_approval", task_id: "t2", step_n: 2, question: "Shall I add it to the bag?", reason: "Adding to a bag" })],
      ["ASK", null],
      [600, () => h({ type: "step", task_id: "t2", n: 2, action: "click", summary: "Added it to the bag", status: "done", point: { x: 0.7, y: 0.52 } })],
      [200, () => h({ type: "screenshot", task_id: "t2", n: 3, url: SHOTS.bag, page_url: "https://www.pearstore.example/bag" })],
      ...stepFlow(h, 3, "Went to the checkout", "checkout", "https://www.pearstore.example/checkout", { x: 0.25, y: 0.6 }),
      [700, () => h({ type: "blocked", task_id: "t2", reason: "This page asks for card details. This part needs you or a family member. I won’t type payment details.", url: "https://www.pearstore.example/checkout" })],
      ...say(TWIN, "I’ve stopped. This part needs you or a family member. I won’t type passwords or payment details.", 600),
      [300, () => h({ type: "task_finished", task_id: "t2", outcome: "blocked", summary: "Stopped at the payment page.", duration_s: 24, steps: 3 })],
    ];
  }

  // Helpers that return arrays of [delay, fn] entries. `h` is bound by the player.
  let H_ = null;
  function say(who, text, pad) {
    const words = text.split(" ");
    const out = [];
    if (who === TWIN) out.push([200, () => H_({ type: "agent_speaking", speaking: true })]);
    [0.35, 0.7].forEach((f) => {
      out.push([who === TWIN ? 380 : 280, () => H_({ type: "transcript", who, text: words.slice(0, Math.max(2, Math.floor(words.length * f))).join(" "), final: false })]);
    });
    out.push([who === TWIN ? 420 : 300, () => H_({ type: "transcript", who, text, final: true })]);
    if (who === TWIN) out.push([Math.min(1400, 250 + words.length * 70) + (pad || 0), () => H_({ type: "agent_speaking", speaking: false })]);
    else out.push([pad || 200, () => {}]);
    return out;
  }
  function stepFlow(h, n, summary, shot, pageUrl, point) {
    return [
      [500, () => h({ type: "step", task_id: H_.task, n, action: "click", summary, status: "running", point })],
      [900, () => h({ type: "screenshot", task_id: H_.task, n, url: SHOTS[shot], page_url: pageUrl })],
      [500, () => h({ type: "step", task_id: H_.task, n, action: "click", summary, status: "done" })],
    ];
  }

  /* ---------- player ---------- */
  const player = {
    active: false,
    _timers: [], _wait: null, _handle: null, _name: "dal",

    start(handle, name) {
      this.stop(false);
      this._handle = handle;
      this._name = name === "iphone" ? "iphone" : "dal";
      this.active = true;
      handle({ type: "reset" });
      H_ = (ev) => handle(Object.assign({ ts: Date.now() / 1000 }, ev));
      H_.task = this._name === "iphone" ? "t2" : "t1";
      const script = (this._name === "iphone" ? iphone : dal)(H_);
      this._run(script, 0);
    },

    _run(script, i) {
      if (!this.active || i >= script.length) return;
      const [delay, fn] = script[i];
      if (delay === "ASK") {
        // Wait for Yes/No or the Y/N keys; auto-approve after 8 s so a demo never stalls.
        this._wait = (yes) => {
          clearTimeout(auto); this._wait = null;
          H_({ type: "approval_result", task_id: H_.task, approved: yes, by: "dashboard" });
          this._timers.push(setTimeout(() => this._run(script, i + 1), 400));
        };
        const auto = setTimeout(() => this._wait && this._wait(true), 8000);
        this._timers.push(auto);
        return;
      }
      this._timers.push(setTimeout(() => { try { fn(); } catch (e) {} this._run(script, i + 1); }, delay));
    },

    answer(yes) { if (this._wait) this._wait(!!yes); },

    stop(restart) {
      this._timers.forEach(clearTimeout); this._timers = []; this._wait = null;
      const h = this._handle;
      const name = this._name;
      if (restart && h) { this.start(h, name); return; }
      this.active = false;
      if (h) h({ type: "reset" });
    },
  };

  document.addEventListener("keydown", (e) => {
    if (!player.active || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "y" || e.key === "Y") player.answer(true);
    if (e.key === "n" || e.key === "N") player.answer(false);
  });

  window.TechTwinDemo = player;
})();
