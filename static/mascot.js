/* Twinkle mascot + icons. Plain JS, no dependencies.
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

  /* the brand mark: the yellow "twinkle" star. Outline rule: always drawn with the ink outline
     (or a paper outline on ink / teal), so yellow stays visible on any background. */
  var STAR = 'M24 3C25.6 14.6 33.4 22.4 45 24C33.4 25.6 25.6 33.4 24 45C22.4 33.4 14.6 25.6 3 24C14.6 22.4 22.4 14.6 24 3Z';
  TT.starPath = STAR;
  TT.starSVG = function (opt) {
    opt = opt || {};
    var fill = opt.fill || v('butter', '#F4B52E'), line = opt.line || v('ink', '#1F3A44');
    return '<svg class="' + (opt.cls || 'brand-mark') + '" viewBox="0 0 48 48" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">' +
      '<path d="' + STAR + '" fill="' + fill + '" stroke="' + line + '" stroke-width="3" stroke-linejoin="round"/></svg>';
  };
  TT.markSVG = TT.starSVG();

  /* the old twin-rings mark (Twinkle's glasses without the face), kept for stickers */
  TT.glassesMarkSVG =
    '<svg class="brand-mark brand-mark--glasses" viewBox="0 0 54 36" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M25 17 Q27 12.5 29 17" fill="none" stroke-width="3.4" stroke-linecap="round" style="stroke:' + v('teal-deep', '#136A70') + '"/>' +
    '<circle cx="14" cy="19" r="11" fill="none" stroke-width="5.5" style="stroke:' + v('teal', '#1F8A8F') + '"/>' +
    '<circle cx="40" cy="19" r="11" fill="none" stroke-width="5.5" style="stroke:' + v('butter', '#F4B52E') + '"/>' +
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
