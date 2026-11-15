/* Twinkle practice mode. Plays a scripted fake call through the SAME handle(event)
   function the WebSocket uses, so the screen can be designed, tested and demoed with no backend.
   API: window.TwinkleDemo = { active, scenario, start(handle, scenario), stop(reset), answer(bool) }
   Scenarios: "dal" (play a video, with a spoken-style approval) and "iphone" (safety stop).
   The fake screenshots are inline SVG data URIs of generic pages: no real brands or logos. */
(function () {
  'use strict';

  /* ---------- fake screenshots (1280 x 800) ---------- */
  var FONT = "font-family='Helvetica, Arial, sans-serif'";
  function svg(inner) {
    return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(
      "<svg xmlns='http://www.w3.org/2000/svg' width='1280' height='800' viewBox='0 0 1280 800' " + FONT + ">" +
      "<defs>" +
      "<linearGradient id='g1' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='#F7C59F'/><stop offset='1' stop-color='#EF8F6B'/></linearGradient>" +
      "<linearGradient id='g2' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='#9BD0C8'/><stop offset='1' stop-color='#4F9FA3'/></linearGradient>" +
      "<linearGradient id='g3' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='#F6E3A1'/><stop offset='1' stop-color='#E8B94A'/></linearGradient>" +
      "<linearGradient id='g4' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='#C9D7F2'/><stop offset='1' stop-color='#8FA8DA'/></linearGradient>" +
      "<linearGradient id='g5' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='#3a2a22'/><stop offset='1' stop-color='#7a4a30'/></linearGradient>" +
      "</defs>" +
      "<rect width='1280' height='800' fill='#ffffff'/>" + inner + "</svg>");
  }
  function t(x, y, size, weight, fill, text, anchor) {
    return "<text x='" + x + "' y='" + y + "' font-size='" + size + "' font-weight='" + weight + "' fill='" + fill + "'" +
      (anchor ? " text-anchor='" + anchor + "'" : '') + ">" + text + "</text>";
  }
  function r(x, y, w, h, rx, fill, extra) {
    return "<rect x='" + x + "' y='" + y + "' width='" + w + "' height='" + h + "' rx='" + rx + "' fill='" + fill + "' " + (extra || '') + "/>";
  }
  function topBar(query, brand) {
    return r(0, 0, 1280, 84, 0, '#F4F5F7') +
      "<circle cx='60' cy='42' r='18' fill='#D0412F'/><polygon points='54,34 54,50 68,42' fill='#fff'/>" +
      t(92, 52, 28, 700, '#222', brand || 'Watchbox') +
      r(380, 20, 520, 44, 22, '#fff', "stroke='#cfd3da' stroke-width='2'") +
      t(408, 49, 22, 400, query ? '#222' : '#8a8f98', query || 'Search videos') +
      r(900, 20, 70, 44, 22, '#E9ECF1', "stroke='#cfd3da' stroke-width='2'") +
      "<circle cx='930' cy='41' r='9' fill='none' stroke='#555' stroke-width='3'/><line x1='937' y1='48' x2='945' y2='56' stroke='#555' stroke-width='3'/>" +
      "<circle cx='1220' cy='42' r='18' fill='#CBD2DD'/>";
  }
  function thumb(x, y, w, h, g, label) {
    return r(x, y, w, h, 14, 'url(#' + g + ')') +
      "<circle cx='" + (x + w / 2) + "' cy='" + (y + h / 2) + "' r='22' fill='rgba(255,255,255,.85)'/>" +
      "<polygon points='" + (x + w / 2 - 7) + "," + (y + h / 2 - 12) + " " + (x + w / 2 - 7) + "," + (y + h / 2 + 12) + " " + (x + w / 2 + 14) + "," + (y + h / 2) + "' fill='#444'/>" +
      (label ? r(x + w - 70, y + h - 34, 58, 24, 6, 'rgba(0,0,0,.7)') + t(x + w - 41, y + h - 16, 16, 700, '#fff', label, 'middle') : '');
  }
  var SHOTS = {
    search: function () {
      var s = topBar('', 'Watchbox');
      s += t(640, 280, 44, 700, '#222', 'What would you like to watch?', 'middle');
      s += r(300, 320, 680, 70, 35, '#fff', "stroke='#bfc5ce' stroke-width='3'");
      s += t(340, 365, 28, 400, '#8a8f98', 'Search videos');
      var chips = ['Cooking', 'Music', 'News', 'Gardening', 'Walks'];
      chips.forEach(function (c, i) { s += r(300 + i * 140, 430, 124, 44, 22, '#EEF0F4') + t(362 + i * 140, 459, 20, 700, '#333', c, 'middle'); });
      [['g1', 0], ['g2', 1], ['g3', 2], ['g4', 3]].forEach(function (a) { s += thumb(130 + a[1] * 280, 540, 250, 140, a[0], ''); });
      return svg(s);
    },
    typed: function () {
      var s = topBar('', 'Watchbox');
      s += t(640, 280, 44, 700, '#222', 'What would you like to watch?', 'middle');
      s += r(300, 320, 680, 70, 35, '#fff', "stroke='#1F8A8F' stroke-width='4'");
      s += t(340, 365, 28, 500, '#222', 'easy dal recipe video');
      s += r(300, 400, 680, 170, 20, '#fff', "stroke='#e0e3e8' stroke-width='2'");
      ['easy dal recipe video', 'easy dal recipe for beginners', 'dal tadka step by step'].forEach(function (q, i) {
        s += t(340, 445 + i * 48, 24, 400, i === 0 ? '#111' : '#555', q);
      });
      return svg(s);
    },
    results: function () {
      var s = topBar('easy dal recipe video', 'Watchbox');
      var rows = [
        ['g3', 'Easy dal tadka, step by step', 'Kitchen Stories  ·  1.2M views', true, '12:08'],
        ['g1', 'Five dals for a quick dinner', 'Home Cooking Club  ·  310K views', false, '8:44'],
        ['g2', 'Dal for beginners: the basics', 'Pan and Pot  ·  96K views', false, '15:30']
      ];
      rows.forEach(function (row, i) {
        var y = 120 + i * 220;
        if (row[3]) s += r(90, y - 14, 1100, 206, 22, '#FFF7E0', "stroke='#F4B52E' stroke-width='4'");
        s += thumb(120, y, 320, 180, row[0], row[4]);
        s += t(470, y + 50, 34, 700, '#1a1a1a', row[1]);
        s += t(470, y + 94, 22, 400, '#666', row[2]);
        s += r(470, y + 120, 520, 14, 7, '#EEF0F4') + r(470, y + 146, 380, 14, 7, '#EEF0F4');
      });
      return svg(s);
    },
    player: function () {
      var s = r(0, 0, 1280, 800, 0, '#16181d');
      s += r(60, 40, 800, 450, 18, 'url(#g5)');
      s += "<circle cx='260' cy='260' r='90' fill='#F4B52E' opacity='.9'/><rect x='320' y='300' width='360' height='150' rx='18' fill='#D0412F' opacity='.85'/>";
      s += r(60, 466, 800, 8, 4, '#4a4f58') + r(60, 466, 210, 8, 4, '#D0412F') + "<circle cx='270' cy='470' r='11' fill='#D0412F'/>";
      s += t(60, 540, 34, 700, '#fff', 'Easy dal tadka, step by step');
      s += t(60, 584, 22, 400, '#b9bec8', 'Kitchen Stories  ·  1.2M views');
      s += r(60, 620, 250, 56, 28, '#2a2e36') + t(185, 656, 22, 700, '#fff', 'Playing now', 'middle');
      for (var i = 0; i < 3; i++) {
        var y = 40 + i * 160;
        s += r(900, y, 250, 140, 12, ['#7a5a3c', '#3c6a6e', '#6a5a2c'][i]);
        s += r(1166, y + 10, 90, 14, 7, '#3a3f48') + r(1166, y + 36, 70, 14, 7, '#2e323a');
      }
      return svg(s);
    },
    store: function () {
      var s = r(0, 0, 1280, 84, 0, '#fff') + r(0, 84, 1280, 2, 0, '#e5e7eb');
      s += "<circle cx='60' cy='42' r='16' fill='#2C8F5E'/>" + t(90, 52, 28, 700, '#222', 'Orchard Store');
      ['Phones', 'Laptops', 'Watches', 'Support'].forEach(function (c, i) { s += t(520 + i * 130, 51, 21, 500, '#444', c); });
      s += r(1150, 22, 90, 40, 20, '#EEF0F4') + t(1195, 49, 20, 700, '#333', 'Bag', 'middle');
      s += r(170, 140, 420, 560, 40, 'url(#g4)');
      s += r(300, 190, 160, 460, 28, '#1d2330') + r(312, 206, 136, 420, 16, '#6C86C6') + "<circle cx='380' cy='610' r='10' fill='#fff' opacity='.7'/>";
      s += t(680, 230, 26, 500, '#7a808c', 'New');
      s += t(680, 290, 64, 800, '#161a22', 'Pocket Phone 17');
      s += t(680, 345, 28, 400, '#555', 'Bright screen. Big battery. Easy to hold.');
      s += t(680, 430, 40, 700, '#161a22', 'From $999');
      ['Blue', 'Sand', 'Slate'].forEach(function (c, i) { s += "<circle cx='" + (700 + i * 60) + "' cy='490' r='20' fill='" + ['#6C86C6', '#D9CFC0', '#59606e'][i] + "'/>"; });
      s += r(680, 550, 360, 76, 38, '#1F5FD0') + t(860, 598, 28, 700, '#fff', 'Add to bag', 'middle');
      return svg(s);
    },
    checkout: function () {
      var s = r(0, 0, 1280, 84, 0, '#fff') + r(0, 84, 1280, 2, 0, '#e5e7eb');
      s += "<circle cx='60' cy='42' r='16' fill='#2C8F5E'/>" + t(90, 52, 28, 700, '#222', 'Orchard Store');
      s += t(120, 150, 52, 800, '#161a22', 'Checkout');
      var f = function (y, label, val) {
        return t(120, y, 22, 700, '#444', label) + r(120, y + 14, 640, 58, 12, '#fff', "stroke='#bfc5ce' stroke-width='2'") + t(144, y + 52, 24, 400, '#888', val);
      };
      s += f(210, 'Email', 'grandma@example.com');
      s += f(310, 'Password', '••••••••');
      s += f(410, 'Card number', '1234  5678  9012  3456');
      s += t(120, 530, 22, 700, '#444', 'Expiry') + r(120, 544, 300, 58, 12, '#fff', "stroke='#bfc5ce' stroke-width='2'");
      s += t(460, 530, 22, 700, '#444', 'Security code (CVV)') + r(460, 544, 300, 58, 12, '#fff', "stroke='#bfc5ce' stroke-width='2'");
      s += r(120, 640, 640, 72, 36, '#1F5FD0') + t(440, 686, 28, 700, '#fff', 'Pay $999', 'middle');
      s += r(860, 150, 300, 340, 24, '#F4F5F7') + t(890, 200, 26, 700, '#222', 'Your bag') + t(890, 250, 22, 400, '#555', 'Pocket Phone 17') + t(890, 290, 22, 400, '#555', 'Total  $999');
      return svg(s);
    }
  };

  /* ---------- player ---------- */
  var run = 0;
  var approvalResolve = null;
  var approvalTimer = null;
  var D = (window.TwinkleDemo = {
    active: false,
    scenario: 'dal',
    start: start,
    stop: stop,
    answer: answer
  });

  function now() { return Date.now() / 1000; }
  function sleep(ms, id) {
    return new Promise(function (res, rej) {
      setTimeout(function () { if (id !== run) rej(new Error('stopped')); else res(); }, ms);
    });
  }
  function answer(yes) {
    if (approvalTimer) { clearTimeout(approvalTimer); approvalTimer = null; }
    if (approvalResolve) { var f = approvalResolve; approvalResolve = null; f(!!yes); }
  }
  function waitApproval(id) {
    return new Promise(function (res, rej) {
      approvalResolve = function (v) { if (id !== run) rej(new Error('stopped')); else res({ yes: v, by: 'dashboard' }); };
      approvalTimer = setTimeout(function () {   // pretend the caller said "yes" out loud
        approvalTimer = null;
        if (approvalResolve) { var f = approvalResolve; approvalResolve = null; if (id !== run) rej(new Error('stopped')); else res({ yes: true, by: 'voice' }); }
      }, 8000);
    });
  }

  function stop(reset) {
    run++;
    D.active = false;
    answer(false);
    approvalResolve = null;
    if (reset && D._handle) D._handle({ type: 'reset', ts: now() });
    else if (D._handle && !reset) D._handle({ type: 'task_finished', ts: now(), task_id: 'demo', outcome: 'cancelled', summary: 'Okay, I stopped.', duration_s: 0, steps: 0 });
    D._handle && D._handle({ type: 'agent_speaking', ts: now(), speaking: false });
  }

  function start(handle, scenario) {
    handle = handle || (window.TT && window.TT.handle);
    if (!handle) return;
    D._handle = handle;
    D.scenario = scenario === 'iphone' ? 'iphone' : 'dal';
    D.active = true;
    var id = ++run;
    var send = function (type, data) {
      if (id !== run) return;
      var ev = { type: type, ts: now() };
      for (var k in data) if (Object.prototype.hasOwnProperty.call(data, k)) ev[k] = data[k];
      handle(ev);
    };
    var shotN = 0;
    var shot = function (taskId, n, key, pageUrl) {
      shotN++;
      send('screenshot', { task_id: taskId, n: n, url: SHOTS[key](), page_url: pageUrl });
    };
    var speak = function (who, text) {
      var words = text.split(' ');
      var cut = words.length < 4 ? [words.length] : [Math.ceil(words.length / 3), Math.ceil(words.length * 2 / 3), words.length];
      var chain = Promise.resolve();
      if (who === 'twinkle') chain = chain.then(function () { send('agent_speaking', { speaking: true }); });
      cut.forEach(function (c, i) {
        chain = chain.then(function () { return sleep(who === 'twinkle' ? 520 : 380, id); }).then(function () {
          send('transcript', { who: who, text: words.slice(0, c).join(' '), final: i === cut.length - 1 });
        });
      });
      if (who === 'twinkle') chain = chain.then(function () { return sleep(300, id); }).then(function () { send('agent_speaking', { speaking: false }); });
      return chain;
    };
    var T0;

    var scenarioA = function () {
      return sleep(500, id)
        .then(function () { send('call_started', { call_sid: 'demo', from: '4821' }); return sleep(700, id); })
        .then(function () { return speak('twinkle', "Hi, it's Twinkle! What can I help you with today?"); })
        .then(function () { return sleep(900, id); })
        .then(function () { return speak('caller', 'I want to watch the dal recipe video my daughter told me about.'); })
        .then(function () { return sleep(500, id); })
        .then(function () { return speak('twinkle', "You'd like to play a dal recipe video. Is that right?"); })
        .then(function () { return sleep(500, id); })
        .then(function () { return speak('caller', 'Yes.'); })
        .then(function () {
          T0 = now();
          send('task_started', { task_id: 't1', goal: 'Play a dal recipe video' });
          return sleep(500, id);
        })
        .then(function () { send('step', { task_id: 't1', n: 1, action: 'open_url', summary: 'Opening YouTube', status: 'running', url: 'https://www.youtube.com/' }); return sleep(900, id); })
        .then(function () { shot('t1', 1, 'search', 'https://www.youtube.com/'); return sleep(500, id); })
        .then(function () { send('step', { task_id: 't1', n: 1, action: 'open_url', summary: 'Opened YouTube', status: 'done', url: 'https://www.youtube.com/' }); return speak('twinkle', "I'm opening YouTube now."); })
        .then(function () { send('step', { task_id: 't1', n: 2, action: 'type', summary: 'Typing the name of the video', status: 'running', point: { x: 0.45, y: 0.46 } }); return sleep(1000, id); })
        .then(function () { shot('t1', 2, 'typed', 'https://www.youtube.com/'); return sleep(500, id); })
        .then(function () { send('step', { task_id: 't1', n: 2, action: 'type', summary: 'Typed the name of the video in the search box', status: 'done' }); return sleep(700, id); })
        .then(function () { send('step', { task_id: 't1', n: 3, action: 'click', summary: 'Looking for the right video', status: 'running', point: { x: 0.35, y: 0.1 } }); return sleep(1000, id); })
        .then(function () { shot('t1', 3, 'results', 'https://www.youtube.com/results'); return sleep(600, id); })
        .then(function () { send('step', { task_id: 't1', n: 3, action: 'click', summary: 'Found a video that looks right', status: 'done', point: { x: 0.2, y: 0.28 } }); return sleep(700, id); })
        .then(function () { send('step', { task_id: 't1', n: 4, action: 'click', summary: 'Getting ready to press play', status: 'running' }); return sleep(500, id); })
        .then(function () {
          send('needs_approval', { task_id: 't1', step_n: 4, question: 'I found it. Shall I press play?', reason: 'Pressing play starts the video.' });
          var ap = waitApproval(id); ap.catch(function () {});
          return speak('twinkle', 'I found it. Shall I press play?').then(function () { return ap; });
        })
        .then(function (res) {
          send('approval_result', { task_id: 't1', approved: res.yes, by: res.by });
          if (!res.yes) {
            send('task_finished', { task_id: 't1', outcome: 'cancelled', summary: "Okay, I didn't press play.", duration_s: now() - T0, steps: 3 });
            return speak('twinkle', "Okay, I didn't press play. Is there anything else?");
          }
          return speak('caller', 'Yes, please.').then(function () {
            send('step', { task_id: 't1', n: 4, action: 'click', summary: 'Pressing play', status: 'running', point: { x: 0.2, y: 0.28 } });
            return sleep(900, id);
          }).then(function () {
            shot('t1', 4, 'player', 'https://www.youtube.com/watch');
            send('step', { task_id: 't1', n: 4, action: 'click', summary: 'Pressed play', status: 'done' });
            return sleep(500, id);
          }).then(function () {
            send('task_finished', { task_id: 't1', outcome: 'done', summary: 'The video is playing now.', duration_s: now() - T0, steps: 4 });
            return speak('twinkle', 'The video is playing now. Is there anything else?');
          });
        });
    };

    var scenarioB = function () {
      return sleep(500, id)
        .then(function () { send('call_started', { call_sid: 'demo', from: '4821' }); return sleep(600, id); })
        .then(function () { return speak('twinkle', "Hi, it's Twinkle! What can I help you with today?"); })
        .then(function () { return sleep(700, id); })
        .then(function () { return speak('caller', 'Buy me the new iPhone.'); })
        .then(function () {
          T0 = now();
          send('task_started', { task_id: 't2', goal: 'Buy the new phone' });
          return sleep(500, id);
        })
        .then(function () { send('step', { task_id: 't2', n: 1, action: 'open_url', summary: 'Opening a store page', status: 'running', url: 'https://www.apple.com/' }); return sleep(900, id); })
        .then(function () { shot('t2', 1, 'store', 'https://www.apple.com/'); send('step', { task_id: 't2', n: 1, action: 'open_url', summary: 'Opened a store page', status: 'done' }); return speak('twinkle', "I'm opening a store page."); })
        .then(function () { send('step', { task_id: 't2', n: 2, action: 'click', summary: 'Adding it to the bag', status: 'running', point: { x: 0.58, y: 0.74 } }); return sleep(500, id); })
        .then(function () {
          send('needs_approval', { task_id: 't2', step_n: 2, question: 'Shall I add it to the bag?', reason: 'This is a buying step.' });
          var ap = waitApproval(id); ap.catch(function () {});
          return speak('twinkle', 'Shall I add it to the bag?').then(function () { return ap; });
        })
        .then(function (res) {
          send('approval_result', { task_id: 't2', approved: res.yes, by: res.by });
          if (!res.yes) {
            send('task_finished', { task_id: 't2', outcome: 'cancelled', summary: 'Okay, I stopped.', duration_s: now() - T0, steps: 1 });
            return speak('twinkle', 'Okay, I stopped.');
          }
          send('step', { task_id: 't2', n: 2, action: 'click', summary: 'Added it to the bag', status: 'done' });
          return sleep(700, id).then(function () {
            send('step', { task_id: 't2', n: 3, action: 'click', summary: 'Going to the checkout', status: 'running', url: 'https://www.apple.com/shop/checkout', point: { x: 0.9, y: 0.07 } });
            return sleep(900, id);
          }).then(function () {
            shot('t2', 3, 'checkout', 'https://www.apple.com/shop/checkout');
            send('blocked', { task_id: 't2', reason: "This page asks for card details. This part needs you or a family member. I won't type payment details.", url: 'https://www.apple.com/shop/checkout' });
            send('task_finished', { task_id: 't2', outcome: 'blocked', summary: 'I stopped at the checkout.', duration_s: now() - T0, steps: 3 });
            return speak('twinkle', "I stopped here. This page asks for card details, and I won't type payment details.");
          });
        });
    };

    var p = D.scenario === 'iphone' ? scenarioB() : scenarioA();
    p.catch(function () { /* stopped on purpose */ });
  }
})();
