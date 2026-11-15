/*
   TT.mascot(expr)  -> SVG string. expr: idle | listening | talking | careful
   TT.icon(name)    -> SVG string (rounded 3px strokes, one family)
   TT.markSVG       -> the twin logo mark (two overlapping rings)
   Colours read CSS variables with the same hex as fallback, so the SVG also works standalone. */
(function () {
  'use strict';
  var TT = (window.TT = window.TT || {});

  function v(name, fallback) { return 'var(--' + name + ',' + fallback + ')'; }

  /* ---------- Twinkle: a friendly pair of round glasses ----------
     The two lenses are the twin rings from the logo (teal and butter). The lenses do the acting.
     expr: idle | listening | talking | thinking | asking | success | oops | careful        */
  var NAMES = { idle: 1, listening: 1, talking: 1, thinking: 1, asking: 1, success: 1, oops: 1, careful: 1 };
  TT.TWINKLE_EXPRESSIONS = ['idle', 'listening', 'talking', 'thinking', 'asking', 'success', 'oops', 'careful'];

  function starPath(r) {   // four-point sparkle centred on 0,0
    var a = r, b = r * 0.26;
    return 'M0 ' + (-a) + ' L' + b + ' ' + (-b) + ' L' + a + ' 0 L' + b + ' ' + b + ' L0 ' + a + ' L' + (-b) + ' ' + b + ' L' + (-a) + ' 0 L' + (-b) + ' ' + (-b) + 'Z';
  }

  TT.mascot = function (expr) {
    if (!NAMES[expr]) expr = 'idle';
    var teal = v('teal', '#1F8A8F'), butter = v('butter', '#F4B52E'), cream = v('paper', '#FFFDF8');
    var ink = v('ink', '#1F3A44'), peach = v('peach', '#FFE2CC'), red = v('red', '#D0412F'), deep = v('teal-deep', '#136A70');
    var CY = 52, XL = 46, XR = 114, R = 29;

    var look = { idle: [0, 1], listening: [7, -1], talking: [0, 1], thinking: [5, 4], asking: [0, 0], success: [0, 0], oops: [0, 8], careful: [0, 1] }[expr];
    var pr = expr === 'asking' ? 6.5 : 10;

    function pupil(cx) {
      if (expr === 'success') {
        return '<g transform="translate(' + cx + ' ' + CY + ')"><path class="tw-star" d="' + starPath(15) + '" style="fill:' + butter + ';stroke:' + ink + ';stroke-width:1.6;stroke-linejoin:round"/></g>';
      }
      var x = cx + look[0], y = CY + look[1];
      return '<g class="tw-blink"><circle cx="' + x + '" cy="' + y + '" r="' + pr + '" style="fill:' + ink + '"/>' +
        '<circle cx="' + (x + pr * 0.35) + '" cy="' + (y - pr * 0.4) + '" r="' + (pr * 0.32) + '" fill="#fff"/></g>';
    }
    function lid(cx, off) {    // upper lid: covers the lens above a chord
      var rr = R - 4, hw = Math.sqrt(rr * rr - off * off), y = CY + off;
      return '<path d="M' + (cx - hw) + ' ' + y + ' A' + rr + ' ' + rr + ' 0 0 1 ' + (cx + hw) + ' ' + y + ' Z" style="fill:' + peach + '"/>' +
        '<path d="M' + (cx - hw) + ' ' + y + ' L' + (cx + hw) + ' ' + y + '" stroke-width="3" stroke-linecap="round" stroke="#D9A07E"/>';
    }
    function brow(d) { return '<path d="' + d + '" fill="none" stroke-width="4.6" stroke-linecap="round" style="stroke:' + ink + '"/>'; }

    var g = '';
    // temples and bridge
    g += '<path d="M17 46 L2 40 M143 46 L158 40" fill="none" stroke-width="5" stroke-linecap="round" style="stroke:' + deep + '"/>';
    g += '<path d="M75 46 Q80 38 85 46" fill="none" stroke-width="5.5" stroke-linecap="round" style="stroke:' + deep + '"/>';
    // glass + rims
    [[XL, teal], [XR, butter]].forEach(function (l) {
      g += '<circle cx="' + l[0] + '" cy="' + CY + '" r="' + R + '" stroke-width="8" style="fill:' + cream + ';stroke:' + l[1] + '"/>';
      g += '<path d="M' + (l[0] - 17) + ' ' + (CY - 9) + ' Q' + (l[0] - 12) + ' ' + (CY - 18) + ' ' + (l[0] - 3) + ' ' + (CY - 20) + '" fill="none" stroke-width="3" stroke-linecap="round" stroke="#fff" opacity=".85"/>';
    });
    // eyes
    g += pupil(XL) + pupil(XR);
    // lids and brows by mood
    if (expr === 'thinking') { g += lid(XL, -3) + lid(XR, -3) + brow('M' + (XR - 16) + ' 14 Q' + XR + ' 5 ' + (XR + 16) + ' 12'); }
    if (expr === 'oops') {
      g += lid(XL, -9) + lid(XR, -9);
      g += brow('M' + (XL - 18) + ' 19 L' + (XL + 16) + ' 10') + brow('M' + (XR - 16) + ' 10 L' + (XR + 18) + ' 19');
    }
    if (expr === 'asking') { g += brow('M' + (XL - 17) + ' 13 Q' + XL + ' 3 ' + (XL + 17) + ' 13') + brow('M' + (XR - 17) + ' 13 Q' + XR + ' 3 ' + (XR + 17) + ' 13'); }
    if (expr === 'careful') { g += brow('M' + (XL - 18) + ' 17 L' + (XL + 16) + ' 11') + brow('M' + (XR - 16) + ' 11 L' + (XR + 18) + ' 17'); }
    if (expr === 'oops') g += '<path d="M' + (XR + 12) + ' ' + (CY + 14) + ' q-5 8 0 11 q5 -3 0 -11z" style="fill:#9CD5D8"/>';

    var tf = '';
    if (expr === 'listening') tf = ' transform="rotate(-7 80 52)"';
    if (expr === 'oops') tf = ' transform="translate(0 7) rotate(4 80 52)"';
    if (expr === 'asking') tf = ' transform="translate(80 52) scale(1.07) translate(-80 -52)"';
    var cls = expr === 'idle' ? 'tw-bob' : expr === 'talking' ? 'tw-talk' : '';

    var out = '<svg class="mascot-svg" data-expr="' + expr + '" viewBox="-12 -4 184 112" role="img" aria-label="Twinkle" xmlns="http://www.w3.org/2000/svg">';
    out += '<g' + tf + '><g class="' + cls + '">' + g + '</g></g>';

    function sparkle(x, y, r, d) {
      return '<g transform="translate(' + x + ' ' + y + ')"><path class="tw-star" style="fill:' + butter + ';animation-delay:' + d + 's" d="' + starPath(r) + '"/></g>';
    }
    if (expr === 'idle') out += sparkle(146, 14, 7, 0);
    if (expr === 'success') out += sparkle(80, 8, 9, 0) + sparkle(152, 16, 7, .5) + sparkle(8, 20, 6, 1);
    if (expr === 'talking') {
      out += '<path class="tw-wave" d="M152 40 Q159 52 152 64" fill="none" stroke-width="4" stroke-linecap="round" style="stroke:' + teal + '"/>';
      out += '<path class="tw-wave tw-wave2" d="M159 33 Q171 52 159 71" fill="none" stroke-width="4" stroke-linecap="round" style="stroke:' + teal + '"/>';
    }
    if (expr === 'listening') {
      out += '<path class="tw-wave" d="M6 40 Q-1 52 6 64" fill="none" stroke-width="4" stroke-linecap="round" style="stroke:' + teal + '"/>';
      out += '<path class="tw-wave tw-wave2" d="M-1 33 Q-11 52 -1 71" fill="none" stroke-width="4" stroke-linecap="round" style="stroke:' + teal + '"/>';
    }
    if (expr === 'thinking') {
      out += '<circle class="tw-dot" cx="144" cy="16" r="3" style="fill:' + ink + '"/><circle class="tw-dot tw-dot2" cx="153" cy="10" r="4" style="fill:' + ink + '"/><circle class="tw-dot tw-dot3" cx="164" cy="4" r="5" style="fill:' + ink + '"/>';
    }
    if (expr === 'careful') {
      out += '<g transform="translate(150 -2)"><path d="M0 0 l11 4 v9 c0 7 -5 12 -11 14 c-6 -2 -11 -7 -11 -14 v-9z" stroke-width="2.4" stroke-linejoin="round" style="fill:' + red + ';stroke:' + red + '"/><path d="M-5 13 l4 4 l7 -8" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></g>';
    }
    out += '</svg>';
    return out;
  };

  /* the logo mark: Twinkle's glasses with the star that is her name.
     Lens colours and star read the brand variables; hex fallbacks keep it working standalone. */
  TT.markSVG =
    '<svg class="tt-mark" viewBox="0 0 64 40" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M28 28 Q32 22 36 28" fill="none" stroke-width="3.6" stroke-linecap="round" style="stroke:' + v('teal-deep', '#136A70') + '"/>' +
    '<circle cx="17" cy="28" r="11" fill="none" stroke-width="5.6" style="stroke:' + v('teal', '#1F8A8F') + '"/>' +
    '<circle cx="47" cy="28" r="11" fill="none" stroke-width="5.6" style="stroke:' + v('butter', '#F4B52E') + '"/>' +
    '<g transform="translate(32 9)"><path class="tt-star" d="' + starPath(9) + '" stroke-width="1.4" stroke-linejoin="round" style="fill:' + v('butter', '#F4B52E') + ';stroke:' + v('butter-deep', '#D99A12') + '"/></g>' +
    '</svg>';

  var P = 'fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"';
  var ICONS = {
    check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    x: '<path d="M6 6l12 12M18 6L6 18"/>',
    bang: '<path d="M12 5v9"/><path d="M12 19v.01"/>',
    ban: '<circle cx="12" cy="12" r="8.5"/><path d="M6 6l12 12"/>',
    ask: '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5"/><path d="M12 16.6v.01"/>',
    hand: '<path d="M8 12V6.5a1.5 1.5 0 013 0V11m0-5.5a1.5 1.5 0 013 0V11m0-3.5a1.5 1.5 0 013 0V14a6 6 0 01-6 6h-.6A5.4 5.4 0 019 17.6L6.2 13.4a1.5 1.5 0 012.3-1.9L9 12"/>',
    monitor: '<rect x="3" y="4" width="18" height="12" rx="3"/><path d="M9 20h6M12 16v4"/>',
    reset: '<path d="M4.5 12a7.5 7.5 0 107.5-7.5c-2.2 0-4.2.9-5.6 2.4"/><path d="M4.5 4v4.5H9"/>',
    stop: '<rect x="6" y="6" width="12" height="12" rx="3"/>',
    play: '<path d="M8 5.5v13l11-6.5z"/>'
  };
  TT.icon = function (name) {
    return '<svg viewBox="0 0 24 24" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" ' + P + '>' + (ICONS[name] || '') + '</svg>';
  };
  TT.shieldSVG =
    '<svg class="banner-icon" viewBox="0 0 64 72" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M32 6l22 8v18c0 16-9.5 27-22 33C19.5 59 10 48 10 32V14z"/><path d="M22 35l7 7 14-15"/></svg>';

})();
/*
   and runs a small "life" loop: random blinks, look-around, head tilts, idle fidgets, and
   a pop with confetti when something goes well.
     var t = TT.twinkle.mount(hostElement);   // returns a controller
     t.set('thinking');                       // idle | listening | talking | thinking | asking | success | oops | careful
     t.pop();                                 // jump + confetti (set('success') does this for you)
     t.fx('wiggle');                          // one-shot: pop | hop | wiggle | shake | gasp | nod
     t.destroy();
   TT.twinkle.svg(expr, {standalone:true})    // markup string (used to build the standalone files) */
(function () {
  'use strict';
  var TT = (window.TT = window.TT || {});
  var NS = 'http://www.w3.org/2000/svg';
  var EXPR = ['idle', 'listening', 'talking', 'thinking', 'asking', 'success', 'oops', 'careful'];
  var reduce = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  var uid = 0;

  function star(r) {
    var a = r, b = r * 0.26;
    return 'M0 ' + (-a) + ' L' + b + ' ' + (-b) + ' L' + a + ' 0 L' + b + ' ' + b + ' L0 ' + a + ' L' + (-b) + ' ' + b + ' L' + (-a) + ' 0 L' + (-b) + ' ' + (-b) + 'Z';
  }

  /* ---------- markup ---------- */
  function svg(expr, opts) {
    opts = opts || {};
    if (EXPR.indexOf(expr) < 0) expr = 'idle';
    var id = opts.id || 'twr' + (++uid);
    var CY = 52, XL = 46, XR = 114;
    var s = '<svg class="tw-rig' + (opts.standalone ? ' tw-standalone' : '') + '" data-expr="' + expr + '" viewBox="-12 -24 184 132" role="img" aria-label="Twinkle" xmlns="http://www.w3.org/2000/svg">';
    s += '<defs><clipPath id="' + id + 'L"><circle cx="' + XL + '" cy="' + CY + '" r="25"/></clipPath><clipPath id="' + id + 'R"><circle cx="' + XR + '" cy="' + CY + '" r="25"/></clipPath></defs>';
    s += '<g class="tw-pos"><g class="tw-float"><g class="tw-fx">';
    // frame
    s += '<g class="tw-frame"><path d="M17 46 L2 40 M143 46 L158 40" stroke-width="5"/><path d="M75 46 Q80 38 85 46" stroke-width="5.5"/></g>';
    // lenses
    [[XL, 'l', 'L'], [XR, 'r', 'R']].forEach(function (L) {
      var cx = L[0];
      s += '<circle class="tw-glass" cx="' + cx + '" cy="' + CY + '" r="29"/>';
      s += '<g clip-path="url(#' + id + L[2] + ')">';
      s += '<g class="tw-pupil"><circle class="tw-p" cx="' + cx + '" cy="' + CY + '" r="10"/><circle class="tw-shine" cx="' + (cx + 3.5) + '" cy="' + (CY - 4) + '" r="3.2"/></g>';
      s += '<g class="tw-lid"><rect class="tw-lidfill" x="' + (cx - 29) + '" y="21" width="58" height="48"/><path class="tw-lidedge" d="M' + (cx - 27) + ' 69 Q' + cx + ' 74 ' + (cx + 27) + ' 69"/></g>';
      s += '</g>';
      s += '<path class="tw-happy" d="M' + (cx - 14) + ' ' + (CY + 6) + ' Q' + cx + ' ' + (CY - 14) + ' ' + (cx + 14) + ' ' + (CY + 6) + '"/>';
      s += '<circle class="tw-rim tw-rim-' + L[1] + '" cx="' + cx + '" cy="' + CY + '" r="29"/>';
      s += '<path class="tw-glint" d="M' + (cx - 17) + ' 43 Q' + (cx - 12) + ' 34 ' + (cx - 3) + ' 32"/>';
      s += '<path class="tw-brow tw-brow-' + L[1] + '" d="M' + (cx - 17) + ' 14 Q' + cx + ' 7 ' + (cx + 17) + ' 14"/>';
    });
    s += '</g></g></g>';
    // extras (they sit outside the body layers so they do not squash with it)
    s += '<g class="tw-x tw-x-glint" transform="translate(148 12)"><path class="tw-star" d="' + star(7) + '"/></g>';
    s += '<g class="tw-x tw-x-arcsin"><path class="tw-arc" d="M6 40 Q-1 52 6 64"/><path class="tw-arc tw-arc2" d="M-1 33 Q-11 52 -1 71"/></g>';
    s += '<g class="tw-x tw-x-arcsout"><path class="tw-arc" d="M152 40 Q159 52 152 64"/><path class="tw-arc tw-arc2" d="M159 33 Q171 52 159 71"/></g>';
    s += '<g class="tw-x tw-x-dots"><circle class="tw-dot" cx="144" cy="16" r="3"/><circle class="tw-dot tw-dot2" cx="153" cy="10" r="4"/><circle class="tw-dot tw-dot3" cx="164" cy="4" r="5"/></g>';
    s += '<g class="tw-x tw-x-q" transform="translate(143 -8)"><path class="tw-q" d="M0 8 Q0 0 8 0 Q16 0 16 7 Q16 12 8 15 L8 19 M8 26 L8 26.1"/></g>';
    s += '<g class="tw-x tw-x-stars"><g transform="translate(80 -8)"><path class="tw-star" d="' + star(10) + '"/></g><g transform="translate(152 12)"><path class="tw-star tw-s2" d="' + star(8) + '"/></g><g transform="translate(6 16)"><path class="tw-star tw-s3" d="' + star(7) + '"/></g><g transform="translate(126 -14)"><path class="tw-star tw-s4" d="' + star(5) + '"/></g><g transform="translate(34 -14)"><path class="tw-star tw-s2" d="' + star(5) + '"/></g></g>';
    s += '<g class="tw-x tw-x-tear"><path class="tw-tear" d="M126 66 q-5 8 0 11 q5 -3 0 -11z"/></g>';
    s += '<g class="tw-x tw-x-shield" transform="translate(152 -2)"><g><path class="tw-shield" d="M0 0 l11 4 v9 c0 7 -5 12 -11 14 c-6 -2 -11 -7 -11 -14 v-9z"/><path class="tw-shield-tick" d="M-5 13 l4 4 l7 -8"/></g></g>';
    s += '</svg>';
    return s;
  }

  /* ---------- the life loop ---------- */
  var BASE_ROT = { idle: 0, listening: -7, talking: 0, thinking: 0, asking: 0, success: 0, oops: 4, careful: 0 };
  var BASE_BY = { oops: 7 };
  var PALETTE = ['var(--teal,#1F8A8F)', 'var(--butter,#F4B52E)', 'var(--peach,#FFE2CC)', 'var(--go,#2C8F5E)', 'var(--red,#D0412F)', '#7CC4C7'];

  function rnd(a, b) { return a + Math.random() * (b - a); }
  function pick(a) { return a[Math.floor(Math.random() * a.length)]; }

  function mount(host, opts) {
    opts = opts || {};
    host.innerHTML = svg(opts.expr || 'idle');
    var el = host.firstElementChild;
    var T = {};
    var expr = '';
    var alive = true;
    var fxTimer = 0, lookStep = 0;

    function later(name, ms, fn) {
      clearTimeout(T[name]);
      T[name] = setTimeout(function () {
        if (!alive) return;
        if (!el.isConnected) { destroy(); return; }
        fn();
      }, ms);
    }
    function setVar(k, v) { el.style.setProperty(k, v); }

    /* blink: random, sometimes a double blink; never while the eyes are happy arcs */
    function doBlink() { if (expr === 'success') return; el.classList.add('is-blink'); setTimeout(function () { el.classList.remove('is-blink'); }, 130); }
    function blinkLoop() {
      later('blink', expr === 'thinking' ? rnd(2600, 5200) : rnd(1700, 4600), function () {
        doBlink();
        if (Math.random() < 0.2) setTimeout(doBlink, 270);
        blinkLoop();
      });
    }

    /* look side to side: each mood has its own way of glancing */
    function lookTarget() {
      switch (expr) {
        case 'idle': return [rnd(-7, 7), rnd(-3, 3), rnd(1500, 3400)];
        case 'listening': return [rnd(2, 6), rnd(-2, 2), rnd(900, 1900)];
        case 'talking': return [rnd(-2, 2), rnd(-1, 1), rnd(700, 1500)];
        case 'thinking': lookStep++; return [lookStep % 2 ? -7 : 7, rnd(-2, 1), rnd(1100, 1700)];
        case 'asking': return [rnd(-1.5, 1.5), rnd(-1, 1), rnd(1000, 2000)];
        case 'oops': return [rnd(-2, 2), 0, rnd(1800, 3000)];
        case 'careful': return [rnd(-1, 1), 0, rnd(2000, 3500)];
        default: return [0, 0, 2500];
      }
    }
    function lookLoop() {
      var t = lookTarget();
      setVar('--look-t', (expr === 'thinking' ? 0.24 : 0.3) + 's');
      setVar('--lx', t[0].toFixed(1) + 'px');
      setVar('--ly', t[1].toFixed(1) + 'px');
      later('look', t[2], lookLoop);
    }

    /* head tilt: a slow lean to one side, then another */
    function tilt() {
      var base = BASE_ROT[expr] || 0, d = 0, ms = rnd(2400, 4800);
      if (expr === 'idle') d = rnd(-4, 4);
      else if (expr === 'listening') d = rnd(-2.5, 2.5);
      else if (expr === 'talking') { d = rnd(-3, 3); ms = rnd(1000, 1800); }
      else if (expr === 'oops') d = rnd(-1, 1);
      setVar('--rot', (base + d).toFixed(1) + 'deg');
      setVar('--bx', (expr === 'idle' ? rnd(-2, 2) : 0).toFixed(1) + 'px');
      setVar('--by', (BASE_BY[expr] || 0) + 'px');
      later('tilt', ms, tilt);
    }

    /* idle fidgets: a wiggle, a hop, an extra twinkle */
    function fidget() {
      later('fidget', rnd(6000, 12000), function () {
        if (expr === 'idle') { var f = pick(['wiggle', 'hop', 'hop', 'wiggle', 'gasp']); fx(f); if (f === 'hop') doBlink(); }
        fidget();
      });
    }

    function fx(name) {
      if (reduce) return;
      ['pop', 'hop', 'wiggle', 'shake', 'gasp', 'nod'].forEach(function (n) { el.classList.remove('fx-' + n); });
      void el.getBoundingClientRect();
      el.classList.add('fx-' + name);
      clearTimeout(fxTimer);
      fxTimer = setTimeout(function () { el.classList.remove('fx-' + name); }, 1500);
    }

    function confetti() {
      if (reduce) return;
      var g = document.createElementNS(NS, 'g');
      g.setAttribute('transform', 'translate(80 34)');
      var ring = document.createElementNS(NS, 'circle');
      ring.setAttribute('class', 'tw-ring'); ring.setAttribute('r', '20'); g.appendChild(ring);
      for (var i = 0; i < 22; i++) {
        var kind = pick(['rect', 'rect', 'circle', 'star']);
        var p;
        if (kind === 'rect') { p = document.createElementNS(NS, 'rect'); p.setAttribute('width', '6'); p.setAttribute('height', '10'); p.setAttribute('rx', '1.5'); }
        else if (kind === 'circle') { p = document.createElementNS(NS, 'circle'); p.setAttribute('r', '3.6'); }
        else { p = document.createElementNS(NS, 'path'); p.setAttribute('d', star(6)); }
        var ang = rnd(-Math.PI * 0.95, -Math.PI * 0.05), dist = rnd(50, 105);
        p.setAttribute('class', 'tw-cf');
        p.style.setProperty('--dx', (Math.cos(ang) * dist * 1.25).toFixed(0));
        p.style.setProperty('--dy', (Math.sin(ang) * dist).toFixed(0));
        p.style.setProperty('--rot2', rnd(-540, 540).toFixed(0) + 'deg');
        p.style.fill = pick(PALETTE);
        p.style.animationDelay = rnd(0, 0.12).toFixed(2) + 's';
        g.appendChild(p);
      }
      el.appendChild(g);
      setTimeout(function () { if (g.parentNode) g.parentNode.removeChild(g); }, 1700);
    }

    function pop() { fx('pop'); confetti(); }

    var ENTER = { asking: 'gasp', oops: 'shake', careful: 'gasp', listening: 'nod', thinking: 'nod', talking: null, idle: null };

    function set(next) {
      if (EXPR.indexOf(next) < 0) next = 'idle';
      if (next === expr) return;
      var prev = expr;
      expr = next;
      el.setAttribute('data-expr', next);
      lookStep = 0;
      if (reduce) { setVar('--rot', (BASE_ROT[next] || 0) + 'deg'); setVar('--by', (BASE_BY[next] || 0) + 'px'); return; }
      if (next === 'success') pop();
      else if (prev && ENTER[next]) fx(ENTER[next]);
      tilt(); lookLoop();
    }

    function destroy() {
      alive = false;
      Object.keys(T).forEach(function (k) { clearTimeout(T[k]); });
      clearTimeout(fxTimer);
    }

    if (!reduce) { blinkLoop(); fidget(); }
    set(opts.expr || 'idle');
    return { el: el, set: set, pop: pop, fx: fx, destroy: destroy, get expr() { return expr; } };
  }

  TT.twinkle = { mount: mount, svg: svg, expressions: EXPR };
  TT.TWINKLE_EXPRESSIONS = EXPR;
})();
