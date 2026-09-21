/* The Ladder Lies -- application code.

   Reading order:
     1. helpers, and the data handle D
     2. one block per section, each rendering straight from D
     3. the match simulator
     4. the router, which decides which section is on screen

   Everything renders once at load, so switching sections never redraws a chart. */
(function(){
"use strict";
const D = window.__AFL__;
const TEAMS = D.teams.slice();
const T = {}; TEAMS.forEach(t => T[t.team] = t);
const NAMES = TEAMS.map(t => t.team).sort();
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const sgn = (x, d) => (x > 0 ? '+' : x < 0 ? '−' : '') + Math.abs(x).toFixed(d === undefined ? 1 : d);
const short = s => s.replace('Western Bulldogs','Bulldogs').replace('Greater Western Sydney','GWS')
                    .replace('Brisbane Lions','Brisbane').replace('North Melbourne','North Melb');

/* ------------------------------------------------------------------ tooltip */
const tipEl = $('tip');
function bindTip(el, html){
  el.addEventListener('mouseenter', e => { tipEl.innerHTML = html; tipEl.classList.add('on'); move(e); });
  el.addEventListener('mousemove', move);
  el.addEventListener('mouseleave', () => tipEl.classList.remove('on'));
  el.setAttribute('tabindex', '0');
  el.addEventListener('focus', () => { tipEl.innerHTML = html; tipEl.classList.add('on');
    const r = el.getBoundingClientRect(); place(r.left + r.width / 2, r.top); });
  el.addEventListener('blur', () => tipEl.classList.remove('on'));
  function move(e){ place(e.clientX, e.clientY); }
  function place(x, y){
    const w = tipEl.offsetWidth, h = tipEl.offsetHeight;
    tipEl.style.left = Math.max(8, Math.min(x + 14, innerWidth - w - 8)) + 'px';
    tipEl.style.top  = Math.max(8, y - h - 12) + 'px';
  }
}

/* ------------------------------------------------- trust meters (reliability) */
const REL = D.meta.reliability;
const TRUST = [
  ['Chances made',    REL.created.full],
  ['Chances allowed', REL.conceded.full],
  ['Kicking straight', REL.accuracy.full],
];
function trustWord(r){ return r >= 0.75 ? 'mostly real' : r >= 0.45 ? 'half real' : 'mostly noise'; }
function trustColor(r){ return r >= 0.75 ? 'var(--cool)' : r >= 0.45 ? 'var(--ink-3)' : 'var(--warm)'; }
function trustBar(r){
  return '<span class="trust"><span class="bar"><i style="width:' + (r * 100).toFixed(0) +
         '%; background:' + trustColor(r) + '"></i></span>' +
         '<span class="lv">' + r.toFixed(2) + ' · ' + trustWord(r) + '</span></span>';
}


/* -------------------------------------------------- stamp + grand final === */
(function(){
  const M = D.meta, S = D.september;
  // The date is read off the data, not written into the page, so a rebuild
  // updates it and a stale page can never claim to be current.

  if (!S || !S.gf) return;
  const g = S.gf, lead = g.p >= 0.5;
  const line = l => l.g + '.' + l.b + ' (' + l.pts + ')';
  const pos = (a, l) => 'finished ' + a + ' &middot; levelled ' + l;

  $('gfPanel').innerHTML =
    '<div class="gfhead"><h2>The Grand Final, levelled</h2>' +
    '<span class="eyebrow">' + esc(g.venue) + ' &middot; ' + esc(g.when) + ' &middot; neutral ground</span></div>' +
    '<div class="gfbody">' +
      '<div class="gfside' + (lead ? ' lead' : '') + '">' +
        '<p class="eyebrow">' + pos(g.homePos, g.homeLevel) + '</p>' +
        '<p class="nm">' + esc(g.home) + '</p>' +
        '<p class="pp">' + (g.p * 100).toFixed(1) + '%</p>' +
        '<p class="meta">projected ' + line(g.hLine) + '<br>from ' + g.hShots.toFixed(1) + ' scoring shots</p>' +
      '</div>' +
      '<div class="gfvs"><span>V</span></div>' +
      '<div class="gfside r' + (!lead ? ' lead' : '') + '">' +
        '<p class="eyebrow">' + pos(g.awayPos, g.awayLevel) + '</p>' +
        '<p class="nm">' + esc(g.away) + '</p>' +
        '<p class="pp">' + ((1 - g.p) * 100).toFixed(1) + '%</p>' +
        '<p class="meta">projected ' + line(g.aLine) + '<br>from ' + g.aShots.toFixed(1) + ' scoring shots</p>' +
      '</div>' +
    '</div>' +
    '<div class="gfstats">' +
      st('Flag decided by the boot', (g.bootProb * 100).toFixed(0) + '%',
         'chance the premiership goes to the side that creates fewer scoring shots', 'flag') +
      st('Both earned it', '6 of 6',
         'finals these two have played where the side making more chances won') +
      st('September on the boot', S.bootWins + ' of ' + S.nFinals,
         'finals this year won against the chance count') +
      st('Inside a goal', (g.pClose * 100).toFixed(0) + '%',
         'chance the margin finishes six points or closer') +
    '</div>' +
    '<div class="pad"><p class="heronote">' +
      '<b>Neither grand finalist was carried here.</b> In all six finals these two have played, ' +
      'the side creating more scoring shots won.' +
    '</p></div>';

  function st(k, v, w, cls){
    return '<div class="gfstat ' + (cls || '') + '"><span class="k">' + k + '</span>' +
      '<span class="v">' + v + '</span><span class="w">' + w + '</span></div>';
  }
})();

/* ============================================= 1. THREE LADDERS ============ */
(function(){
  const FX = D.fixture;
  const byLevel = TEAMS.slice().sort((a, b) => a.posLevel - b.posLevel);

  // --- hero: the eight that played vs the eight that earned it ---
  const byActual = TEAMS.slice().sort((a, b) => a.posActual - b.posActual);
  const OUT = FX.eightOut, IN = FX.eightIn;
  const li = (t, pos, kind) =>
    '<li class="' + kind + '"><span class="rk">' + pos + '</span>' +
    '<span>' + esc(short(t)) + '</span>' +
    (kind ? '<span class="tag">' + (kind === 'out' ? 'out' : 'in') + '</span>' : '<span></span>') + '</li>';

  $('eights').innerHTML =
    '<div class="col8"><h3>What happened</h3><p class="cap">The eight that played finals</p>' +
    '<ul class="eightlist">' + byActual.slice(0, 8).map(t =>
      li(t.team, t.posActual, OUT.indexOf(t.team) >= 0 ? 'out' : '')).join('') + '</ul></div>' +
    '<div class="eightmid"><span>levelled</span></div>' +
    '<div class="col8 right"><h3>What was earned</h3><p class="cap">Once luck and the draw come out</p>' +
    '<ul class="eightlist">' + byLevel.slice(0, 8).map(t =>
      li(t.team, t.posLevel, IN.indexOf(t.team) >= 0 ? 'in' : '')).join('') + '</ul></div>';

  $('eightNote').innerHTML =
    '<b>Two clubs played September without earning it. Two who earned it stayed home.</b> ' +
    OUT.map(t => esc(short(t))).join(' and ') + ' drop out. ' +
    IN.map(t => esc(short(t))).join(' and ') + ' come in. A finals berth pays for itself several ' +
    'times over: a home final, a fortnight of gate takings, a better draft position. What decided ' +
    'it was goal kicking that does not repeat, sitting on top of a fixture worth <b>' +
    FX.spread.toFixed(0) + ' points of margin</b> between the best draw and the worst.';

  // --- table ---
  $('ladtbl').innerHTML =
    '<thead><tr><th>Level</th><th>Club</th><th>Finished</th><th>Move</th>' +
    '<th>Actual pts</th><th>Level pts</th></tr></thead><tbody>' +
    byLevel.map(t => {
      const spot = (OUT.indexOf(t.team) >= 0 || IN.indexOf(t.team) >= 0) ? ' class="spot"' : '';
      const mv = t.swing === 0 ? '<span class="movechip eq">held</span>'
        : t.swing > 0 ? '<span class="movechip up">\u2191 ' + t.swing + '</span>'
                      : '<span class="movechip dn">\u2193 ' + (-t.swing) + '</span>';
      return '<tr' + spot + '><td class="n">' + t.posLevel + '</td>' +
        '<td><span class="tm">' + esc(t.team) + '</span></td>' +
        '<td class="n">' + t.posActual + '</td><td>' + mv + '</td>' +
        '<td class="n" style="color:var(--ink-3)">' + t.actual + '</td>' +
        '<td class="n" style="font-weight:600">' + t.level + '</td></tr>';
    }).join('') + '</tbody>';

  // --- slope: finished position -> levelled position ---
  const W = 560, ROW = 22, PT = 30, PL = 118, PR = 60;
  const H = PT + TEAMS.length * ROW + 20;
  const xA = PL, xB = W - PR;
  let g = '<text x="' + xA + '" y="14" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="9.5" fill="var(--ink-3)" letter-spacing="1">FINISHED</text>' +
          '<text x="' + xB + '" y="14" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="9.5" fill="var(--ink-3)" letter-spacing="1">LEVELLED</text>';
  byLevel.forEach(t => {
    const yA = PT + (t.posActual - 1) * ROW, yB = PT + (t.posLevel - 1) * ROW;
    const col = t.swing > 0 ? 'var(--cool)' : t.swing < 0 ? 'var(--warm)' : 'var(--ink-3)';
    g += '<line x1="' + xA + '" y1="' + yA + '" x2="' + xB + '" y2="' + yB +
         '" stroke="' + col + '" stroke-width="' + (Math.abs(t.swing) >= 3 ? 2.4 : 1.2) +
         '" opacity="' + (t.swing === 0 ? .3 : .85) + '"/>' +
         '<circle cx="' + xA + '" cy="' + yA + '" r="4" fill="' + col + '" stroke="var(--panel)" stroke-width="1.5"/>' +
         '<circle cx="' + xB + '" cy="' + yB + '" r="4" fill="' + col + '" stroke="var(--panel)" stroke-width="1.5"/>' +
         '<text x="' + (xA - 9) + '" y="' + (yA + 4) + '" text-anchor="end" font-family="Oswald,sans-serif" font-size="11.5" fill="var(--ink)">' +
         esc(short(t.team)) + '</text>' +
         '<text x="' + (xB + 9) + '" y="' + (yB + 4) + '" font-family="IBM Plex Mono,monospace" font-size="10.5" fill="' + col + '">' +
         t.posLevel + '</text>';
  });
  $('slopeChart').innerHTML = '<svg viewBox="0 0 ' + W + ' ' + H +
    '" role="img" aria-label="Each club’s finishing position against its position once kicking luck and the draw are removed">' + g + '</svg>';
  const svg = $('slopeChart').firstChild;
  byLevel.forEach(t => {
    const yA = PT + (t.posActual - 1) * ROW;
    const r = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    r.setAttribute('x', 0); r.setAttribute('y', yA - ROW / 2);
    r.setAttribute('width', W); r.setAttribute('height', ROW);
    r.setAttribute('fill', 'transparent'); r.style.cursor = 'crosshair';
    svg.appendChild(r);
    bindTip(r, '<b>' + esc(t.team) + '</b><br>finished ' + t.posActual + ', levelled ' + t.posLevel +
      '<br>kicking luck ' + sgn(t.earned - t.actual, 0) + ' pts' +
      '<br>fixture ' + sgn(t.fixtureLadderPts, 0) + ' pts' +
      '<br>draw worth ' + sgn(t.drawPts, 0) + ' margin');
  });
})();

/* ================================================= 2. THE DRAW ============ */
(function(){
  const FX = D.fixture;
  $('fxMeta').innerHTML = FX.nMatches.toLocaleString() + ' matches, 2015–2026' +
    '<span class="tech"> · R² ' + FX.r2.toFixed(2) + '</span>';

  $('fxtbl').innerHTML =
    '<thead><tr><th>What was tested</th><th>Worth</th><th class="tech">95% interval</th>' +
    '<th class="tech">p</th><th>Verdict</th></tr></thead><tbody>' +
    FX.effects.map(e =>
      '<tr' + (e.sig ? ' class="spot"' : '') + '><td><span class="tm">' + esc(cap(e.name)) + '</span>' +
      '<br><span class="eyebrow">' + blurb(e.name) + '</span></td>' +
      '<td class="n" style="font-weight:600">' + sgn(e.beta, 2) + '</td>' +
      '<td class="n tech" style="color:var(--ink-3)">' + sgn(e.lo, 1) + ' to ' + sgn(e.hi, 1) + '</td>' +
      '<td class="n tech">' + (e.p < 0.001 ? '&lt;0.001' : e.p.toFixed(3)) + '</td>' +
      '<td><span class="hitchip ' + (e.sig ? 'h' : 'm') + '">' + (e.sig ? 'real' : 'no effect') + '</span></td></tr>'
    ).join('') + '</tbody>';

  function cap(s){ return s.charAt(0).toUpperCase() + s.slice(1); }
  function blurb(n){
    return { 'home ground': 'listed at home, on a ground in your own state',
             'travelled': 'the match sits outside your home state',
             'time-zone hour': 'every hour the clock moves, on top of the flight',
             '6-day break': 'six days or fewer between matches' }[n] || '';
  }

  // diverging draw chart
  const sorted = TEAMS.slice().sort((a, b) => a.drawPts - b.drawPts);
  const mx = Math.max.apply(null, TEAMS.map(t => Math.abs(t.drawPts)));
  const W = 560, ROW = 21, PT = 26, PL = 122, PR = 48;
  const H = PT + sorted.length * ROW + 26;
  const half = (W - PL - PR) / 2, mid = PL + half, sc = v => (v / mx) * half;
  let g = '';
  [-80, -40, 0, 40, 80].forEach(v => {
    if (Math.abs(v) > mx) return;
    const x = mid + sc(v);
    g += '<line x1="' + x.toFixed(1) + '" y1="' + (PT - 6) + '" x2="' + x.toFixed(1) + '" y2="' +
      (PT + sorted.length * ROW) + '" stroke="var(--grid)"' +
      (v === 0 ? ' stroke-width="1.5"' : ' stroke-dasharray="2 3"') + '/>' +
      '<text x="' + x.toFixed(1) + '" y="' + (H - 8) + '" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="10" fill="var(--ink-3)">' +
      (v > 0 ? '+' + v : v) + '</text>';
  });
  sorted.forEach((t, i) => {
    const y = PT + i * ROW, w = Math.abs(sc(t.drawPts));
    const x = t.drawPts >= 0 ? mid : mid - w;
    const col = t.drawPts > 0 ? 'var(--warm)' : 'var(--cool)';
    g += '<text x="' + (PL - 10) + '" y="' + (y + 12) + '" text-anchor="end" font-family="Oswald,sans-serif" font-size="12" fill="var(--ink)">' +
      esc(short(t.team)) + '</text>' +
      '<rect x="' + x.toFixed(1) + '" y="' + (y + 3) + '" width="' + Math.max(1.5, w).toFixed(1) +
      '" height="12" rx="3" fill="' + col + '"/>' + label(t.drawPts, x, w, y, col);
  });
  function label(v, x, w, y, col){
    const inside = w > 52;                      // long bar: sit the value inside it
    const lx = v >= 0 ? (inside ? x + w - 6 : x + w + 6) : (inside ? x + 6 : x - 6);
    const anc = v >= 0 ? (inside ? 'end' : 'start') : (inside ? 'start' : 'end');
    return '<text x="' + lx.toFixed(1) + '" y="' + (y + 12) + '" text-anchor="' + anc +
      '" font-family="IBM Plex Mono,monospace" font-size="10.5" font-weight="' +
      (inside ? '600' : '400') + '" fill="' + (inside ? 'var(--panel)' : col) + '">' +
      sgn(v, 0) + '</text>';
  }
  $('drawChart').innerHTML = '<svg viewBox="0 0 ' + W + ' ' + H +
    '" role="img" aria-label="What each club’s draw was worth in points of margin">' +
    '<text x="' + PL + '" y="12" font-family="IBM Plex Mono,monospace" font-size="9.5" fill="var(--ink-3)" letter-spacing="1">HARDER DRAW ←      → EASIER DRAW</text>' +
    g + '</svg>';

  $('drawSplit').innerHTML =
    '<thead><tr><th>Club</th><th>Travel</th><th>Opponents</th><th>Ladder pts</th></tr></thead><tbody>' +
    TEAMS.slice().sort((a, b) => a.drawPts - b.drawPts).map(t =>
      '<tr><td><span class="tm">' + esc(short(t.team)) + '</span></td>' +
      '<td class="n" style="color:' + (t.travelPts >= 0 ? 'var(--warm)' : 'var(--cool)') + '">' + sgn(t.travelPts, 0) + '</td>' +
      '<td class="n" style="color:' + (t.oppPts >= 0 ? 'var(--warm)' : 'var(--cool)') + '">' + sgn(t.oppPts, 0) + '</td>' +
      '<td class="n">' + sgn(t.fixtureLadderPts, 0) + '</td></tr>').join('') + '</tbody>';
})();

/* ======================================================= 2. CLUB ROOM ====== */
(function(){
  const sel = $('club');
  NAMES.forEach(n => sel.insertAdjacentHTML('beforeend', '<option>' + esc(n) + '</option>'));
  sel.value = 'Western Bulldogs';

  function render(){
    const t = T[sel.value];
    $('clubName').textContent = t.team;
    $('clubPos').textContent = 'ladder ' + t.pos + ' · earned ' + t.realPos +
      (t.move === 0 ? ' · held' : t.move > 0 ? ' · up ' + t.move : ' · down ' + (-t.move));
    $('clubStrap').textContent = t.won + ' wins from ' + t.games + ' · ' + t.pts +
      ' points · percentage ' + t.pct.toFixed(1) + ' · ' + t.trips + ' interstate trips';

    $('clubTiles').innerHTML =
      ti('Chances made', t.created.toFixed(1), 'shots at goal, per game') +
      ti('Chances allowed', t.conceded.toFixed(1), 'shots the opposition gets, per game') +
      ti('Chance edge', sgn(t.chanceDiff, 2), 'made minus allowed. The one number to look at first', '') +
      ti('Luck', sgn(t.luckPts, 0) + ' pts', (t.luckPts > 0 ? 'above' : 'below') +
         ' what the chances earned', t.luckPts > 0 ? 'up' : 'dn');

    const acc = t.accuracy, lg = D.meta.leagueAcc;
    const accPP = (acc - lg) * 100;
    const rank = k => TEAMS.slice().sort((a, b) => b[k] - a[k]).findIndex(x => x.team === t.team) + 1;
    const rankAsc = k => TEAMS.slice().sort((a, b) => a[k] - b[k]).findIndex(x => x.team === t.team) + 1;
    const ord = n => n + (['th','st','nd','rd'][(n % 100 - n % 10 !== 10) * 1 && n % 10] || 'th');

    $('clubVerdicts').innerHTML =
      whatThisChanges(t) +
      vr('Attack', 'A shot at goal <b>' + t.created.toFixed(1) + '</b> times a game, ' +
         ord(rank('created')) + ' in the competition. ' +
         (t.created >= 27 ? 'This is a real scoring side.' :
          t.created >= 24 ? 'Mid-table. Enough to win games, not enough to frighten anyone.' :
          'Manufacturing a shot is a struggle, and that is the hardest thing on this page to fix.'),
         t.created.toFixed(1), REL.created.full) +
      vr('Defence', 'They hand over <b>' + t.conceded.toFixed(1) + '</b> shots a game, ' +
         ord(rankAsc('conceded')) + ' best. ' +
         (t.conceded <= 23 ? 'Hard to score against. Of everything a club owns, this is the most dependable.' :
          t.conceded <= 26 ? 'Leaky in patches, but not broken.' :
          'The defence is the problem. Bad defences tend to stay bad, so do not wait for this one to fix itself.'),
         t.conceded.toFixed(1), REL.conceded.full) +
      vr('Kicking', '<b>' + (acc * 100).toFixed(1) + '%</b> of shots become goals against a league rate of ' +
         (lg * 100).toFixed(1) + '%, worth <b>' + sgn(t.kickingPts, 0) + '</b> points over the season. ' +
         (Math.abs(accPP) < 1.2 ? 'Dead average. Nothing to read into.' :
          accPP > 0 ? 'Do not bank on it holding. Goal kicking barely carries from one half of a season to the next, so expect it to drift back.' :
          'Ignore the boos. Poor conversion is mostly noise, and it tends to fix itself.'),
         sgn(accPP, 1) + 'pp', REL.accuracy.full) +
      vr('Draw', 'Their opponents averaged <b>' + sgn(t.sos, 2) + '</b> chance differential. ' +
         (t.sos > 0.4 ? 'A hard draw. Everything above was earned against better sides than most clubs faced.' :
          t.sos < -0.4 ? 'A soft draw, so the numbers above flatter them a little.' :
          'A fair draw, near enough to neutral.'),
         sgn(t.sos, 2), null) +
      vr('Form', 'The last five matches ran at <b>' + sgn(t.form5, 2) + '</b> against a season figure of ' +
         sgn(t.chanceDiff, 2) + '. ' +
         (t.formDelta > 1.5 ? 'Peaking at the right end of the year.' :
          t.formDelta < -1.5 ? 'Fading. The recent football is worse than what they averaged all year.' :
          'Steady enough. No real trend either way.'),
         sgn(t.formDelta, 2), null) +
      vr('Close games', '<b>' + t.closeGames + '</b> matches finished inside two goals. They won <b>' +
         t.closeWon + '</b>. ' +
         (t.closeGames === 0 ? 'No close games at all this year.' :
          t.closeWon / t.closeGames > 0.65 ? 'A strong record in tight games is usually a coin landing the same way a few times, not a skill you can budget for.' :
          t.closeWon / t.closeGames < 0.35 ? 'Unlucky rather than soft. Close games are near enough to random.' :
          'About what chance alone would hand you.'),
         t.closeWon + '/' + t.closeGames, null);

    drawLog(t);
    drawQuad(t);
  }

  function ti(k, v, w, cls){
    return '<div class="tile"><span class="k">' + k + '</span><span class="v ' + (cls || '') + '">' +
      v + '</span><span class="w">' + w + '</span></div>';
  }
  /* The sentence a football department actually repeats in a meeting.
     Everything else in this panel describes what happened; this says what it
     means for the list, because the argument clubs have internally every
     November is whether a finish reflects the players or the fixture.

     The decomposition is done in premiership points, where it is exact:
         actual -> earned   is goal-kicking luck        (t.luckPts)
         earned -> level    is the fixture              (t.level - t.earned)
     drawPts is a separate quantity measured in MARGIN, and it deliberately is
     not converted into ladder points here. Margin only moves a ladder when it
     flips a result, so a club can have the hardest draw in the league and
     still barely move once it is levelled out. Hawthorn is exactly that: a
     draw worth +34 points of margin that changes their ladder total by zero.
     Presenting one number as if it converted into the other would not survive
     the first question from anyone numerate.

     Sign convention, checked against strength of schedule (r = -0.96):
     NEGATIVE drawPts means a HARDER draw that cost them points. */
  function ordn(n){
    const s = ['th','st','nd','rd'], v = n % 100;
    return n + (s[(v - 20) % 10] || s[v] || s[0]);
  }
  function whatThisChanges(t){
    const fin = ordn(t.posActual), lvl = ordn(t.posLevel);
    const swing = t.posActual - t.posLevel;   /* positive: levelling promotes them */
    const luck  = t.luckPts;                  /* + : kicking flattered them        */
    const fix   = t.level - t.earned;         /* + : the draw had been costing them */
    const marg  = Math.round(t.drawPts);
    const w = n => { const v = Math.abs(n) / 4;
      return v === 0.5 ? 'half a win'
           : v === 1   ? 'a win'
           : (Number.isInteger(v) ? v : v.toFixed(1)) + ' wins'; };

    const head = swing === 0
      ? 'Finished ' + fin + ', and that is where the list belongs.'
      : 'A ' + lvl + '-place list that finished ' + fin + '.';

    const luckTxt = luck > 0
      ? 'Goal kicking flattered them by ' + luck + ' premiership points, worth ' + w(luck)
      : luck < 0
        ? 'Goal kicking cost them ' + (-luck) + ' premiership points, worth ' + w(luck)
        : 'Goal kicking came out level';

    const drawTxt = marg < 0
      ? 'their draw was the harder side of neutral, worth ' + (-marg) + ' points of margin against them'
      : marg > 0
        ? 'their draw was the easier side of neutral, worth ' + marg + ' points of margin in their favour'
        : 'their draw was as close to neutral as the fixture gets';

    /* Margin and ladder points can point opposite ways, because margin only
       changes a ladder when it flips a result. A club can carry the harder
       draw and still lose points on the level field if the burden fell in
       matches they lost anyway. Where that happens, say so, rather than
       joining two contradictory-sounding clauses with "and". */
    const agrees = (marg < 0 && fix > 0) || (marg > 0 && fix < 0) || marg === 0 || fix === 0;
    const fixTxt = fix === 0
      ? ', though it never flipped a result, so the ladder does not move for it'
      : agrees
        ? (fix > 0 ? ', and the level field hands ' + fix + ' ladder points back'
                   : ', and the level field takes ' + (-fix) + ' ladder points off')
        : (fix > 0
            ? '. It fell mostly in matches that were already decided, so the level field still hands ' + fix + ' ladder points back'
            : '. It fell mostly in matches that were already decided, so the level field still takes ' + (-fix) + ' ladder points off');

    const act = swing < 0 ? ' Plan against the ' + lvl + '-place list, not the ' + fin + '-place finish.'
              : swing > 0 ? ' The list is better than the finish, and the gap is not personnel.'
              : ' The finish is honest.';

    return '<div class="vr" style="border-left:3px solid var(--ink-1)">' +
      '<span class="lab">What this changes<br>' +
      '<span class="eyebrow" style="letter-spacing:.06em">list vs draw</span></span>' +
      '<span class="say"><b>' + head + '</b> ' + luckTxt + '. And ' + drawTxt + fixTxt + '.' + act + '</span>' +
      '<span class="num">' + (swing === 0 ? 'held' : (swing > 0 ? '+' : '') + swing) + '</span></div>';
  }

  function vr(lab, say, num, rel){
    return '<div class="vr"><span class="lab">' + lab + '<br>' +
      (rel === null ? '<span class="eyebrow" style="letter-spacing:.06em">context</span>' : trustBar(rel)) +
      '</span><span class="say">' + say + '</span><span class="num">' + num + '</span></div>';
  }

  function drawLog(t){
    const L = t.log, W = 620, H = 210, PL = 34, PR = 16, PT = 22, PB = 30;
    const iw = W - PL - PR, ih = H - PT - PB, bw = iw / L.length;
    const mx = Math.max(12, Math.max.apply(null, L.map(d => Math.abs(d.sf - d.sa))));
    const y0 = PT + ih / 2, sc = v => (v / mx) * (ih / 2);
    let g = '<line x1="' + PL + '" y1="' + y0 + '" x2="' + (W - PR) + '" y2="' + y0 +
            '" stroke="var(--line)" stroke-width="1.5"/>';
    L.forEach((d, i) => {
      const v = d.sf - d.sa, h = Math.abs(sc(v));
      const x = PL + i * bw + 1.5, w = Math.max(2, bw - 3);
      const col = v >= 0 ? 'var(--cool)' : 'var(--warm)';
      g += '<rect x="' + x.toFixed(1) + '" y="' + (v >= 0 ? y0 - h : y0).toFixed(1) +
           '" width="' + w.toFixed(1) + '" height="' + Math.max(1.5, h).toFixed(1) +
           '" rx="2" fill="' + col + '" opacity="0.88"/>';
      // dot = actual result
      const rc = d.act > 0 ? 'var(--cool)' : d.act === 0 ? 'var(--ink-3)' : 'var(--warm)';
      g += '<circle cx="' + (x + w / 2).toFixed(1) + '" cy="' + (PT + ih + 11) +
           '" r="3.6" fill="' + rc + '" stroke="var(--panel)" stroke-width="1.6"/>';
    });
    $('gameLog').innerHTML = '<svg viewBox="0 0 ' + W + ' ' + H +
      '" role="img" aria-label="Chance differential by match with the result actually achieved">' +
      '<text x="' + PL + '" y="11" font-family="IBM Plex Mono,monospace" font-size="9.5" fill="var(--ink-3)" letter-spacing="1">CHANCE DIFFERENTIAL BY MATCH</text>' +
      g + '</svg>';
    // hover targets
    const svg = $('gameLog').firstChild;
    L.forEach((d, i) => {
      const r = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      r.setAttribute('x', PL + i * bw); r.setAttribute('y', PT);
      r.setAttribute('width', bw); r.setAttribute('height', ih + 18);
      r.setAttribute('fill', 'transparent'); r.style.cursor = 'crosshair';
      svg.appendChild(r);
      bindTip(r, '<b>' + esc(short(d.opp)) + '</b> ' + (d.h ? '(H)' : '(A)') + '<br>' +
        'shots ' + d.sf + ' v ' + d.sa + '<br>' +
        'score ' + d.pf + ' v ' + d.pa + '<br>' +
        'earned ' + sgn(d.exp, 0) + ' · got ' + sgn(d.act, 0) +
        (d.trav ? '<br>interstate trip' : ''));
    });
  }

  function drawQuad(sel){
    const W = 420, H = 340, P = 46, PT = 24, PB = 40;
    const xs = TEAMS.map(t => t.created), ys = TEAMS.map(t => t.conceded);
    const x0 = Math.min.apply(null, xs) - 0.6, x1 = Math.max.apply(null, xs) + 0.6;
    const y0 = Math.min.apply(null, ys) - 0.6, y1 = Math.max.apply(null, ys) + 0.6;
    const iw = W - P - 16, ih = H - PT - PB;
    const X = v => P + (v - x0) / (x1 - x0) * iw;
    const Y = v => PT + (v - y0) / (y1 - y0) * ih;   // more conceded = lower on screen
    const mxC = xs.reduce((a, b) => a + b, 0) / xs.length;
    const myC = ys.reduce((a, b) => a + b, 0) / ys.length;
    let g = '<line x1="' + X(mxC).toFixed(1) + '" y1="' + PT + '" x2="' + X(mxC).toFixed(1) +
            '" y2="' + (PT + ih) + '" stroke="var(--grid)" stroke-dasharray="3 3"/>' +
            '<line x1="' + P + '" y1="' + Y(myC).toFixed(1) + '" x2="' + (W - 16) +
            '" y2="' + Y(myC).toFixed(1) + '" stroke="var(--grid)" stroke-dasharray="3 3"/>' +
            '<text x="' + (W - 18) + '" y="' + (PT + 12) + '" text-anchor="end" font-family="IBM Plex Mono,monospace" font-size="9" fill="var(--ink-3)">GOOD BOTH ENDS</text>' +
            '<text x="' + (P + 4) + '" y="' + (PT + ih - 4) + '" font-family="IBM Plex Mono,monospace" font-size="9" fill="var(--ink-3)">BAD BOTH ENDS</text>';
    $('quad').innerHTML = '<svg viewBox="0 0 ' + W + ' ' + H +
      '" role="img" aria-label="Every club: chances made against chances allowed">' + g +
      '<text x="' + (P + iw / 2) + '" y="' + (H - 6) + '" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="9.5" fill="var(--ink-3)" letter-spacing="1">CHANCES MADE PER GAME →</text>' +
      '<text transform="translate(12,' + (PT + ih / 2) + ') rotate(-90)" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="9.5" fill="var(--ink-3)" letter-spacing="1">← FEWER ALLOWED</text>' +
      '</svg>';
    const svg = $('quad').firstChild;
    TEAMS.forEach(t => {
      const on = t.team === sel.team;
      const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      c.setAttribute('cx', X(t.created).toFixed(1)); c.setAttribute('cy', Y(t.conceded).toFixed(1));
      c.setAttribute('r', on ? 7.5 : 4.5);
      c.setAttribute('fill', on ? 'var(--warm)' : 'var(--cool)');
      c.setAttribute('fill-opacity', on ? '1' : '.45');
      c.setAttribute('stroke', 'var(--panel)'); c.setAttribute('stroke-width', '2');
      c.style.cursor = 'pointer';
      svg.appendChild(c);
      bindTip(c, '<b>' + esc(t.team) + '</b><br>made ' + t.created.toFixed(1) +
        '<br>allowed ' + t.conceded.toFixed(1) + '<br>edge ' + sgn(t.chanceDiff, 2));
      if (on){
        const lb = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        lb.setAttribute('x', X(t.created).toFixed(1)); lb.setAttribute('y', (Y(t.conceded) - 12).toFixed(1));
        lb.setAttribute('text-anchor', 'middle'); lb.setAttribute('font-family', 'Oswald,sans-serif');
        lb.setAttribute('font-size', '12'); lb.setAttribute('fill', 'var(--ink)');
        lb.textContent = short(t.team); svg.appendChild(lb);
      }
    });
  }

  sel.addEventListener('change', render);
  render();
})();

/* ======================================================== 3. MATCH LAB ===== */
let s0 = 20260926 >>> 0;
function rnd(){ s0 ^= s0 << 13; s0 >>>= 0; s0 ^= s0 >> 17; s0 ^= s0 << 5; s0 >>>= 0; return s0 / 4294967296; }
function poisson(l){ const L = Math.exp(-l); let k = 0, p = 1; do { k++; p *= rnd(); } while (p > L); return k - 1; }
function binom(n, p){ let c = 0; for (let i = 0; i < n; i++) if (rnd() < p) c++; return c; }

(function(){
  const selH = $('home'), selA = $('away');
  NAMES.forEach(n => {
    selH.insertAdjacentHTML('beforeend', '<option>' + esc(n) + '</option>');
    selA.insertAdjacentHTML('beforeend', '<option>' + esc(n) + '</option>');
  });
  selH.value = 'Hawthorn'; selA.value = 'Fremantle';

  function lam(att, def, home){ return Math.exp(D.meta.intercept + att + def + (home ? D.meta.home : 0)); }

  function sim(hn, an, neutral, n){
    const h = T[hn], a = T[an];
    const lh = lam(h.attack, a.defence, !neutral), la = lam(a.attack, h.defence, false);
    const margins = new Int16Array(n);
    let win = 0, draw = 0, sH = 0, sA = 0, gH = 0, gA = 0;
    for (let i = 0; i < n; i++){
      const sh = poisson(lh), sa = poisson(la);
      const gh = binom(sh, h.acc), ga = binom(sa, a.acc);
      const ph = gh * 6 + (sh - gh), pa = ga * 6 + (sa - ga);
      margins[i] = ph - pa;
      if (ph > pa) win++; else if (ph === pa) draw++;
      sH += ph; sA += pa; gH += gh; gA += ga;
    }
    return { p: (win + .5 * draw) / n, margins, hPts: sH / n, aPts: sA / n,
             hG: gH / n, aG: gA / n, hSh: lh, aSh: la };
  }

  function line(pts, goals){
    const g = Math.round(goals), b = Math.max(0, Math.round(pts) - g * 6);
    return g + '.' + b + ' (' + Math.round(pts) + ')';
  }
  function freq(p){
    if (p > .44 && p < .56) return 'near enough to a coin toss';
    if (p >= .095) return 'about ' + Math.round(p * 10) + ' times in 10';
    if (p >= .02) return 'about ' + Math.round(p * 100) + ' times in 100';
    return 'fewer than 1 time in 50';
  }

  function hist(margins){
    const W = 640, H = 180, PL = 30, PR = 14, PT = 10, PB = 32;
    const BIN = 12, LO = -108, HI = 108, nb = (HI - LO) / BIN;
    const c = new Array(nb).fill(0);
    for (let i = 0; i < margins.length; i++)
      c[Math.floor((Math.min(HI - 1, Math.max(LO, margins[i])) - LO) / BIN)]++;
    const mx = Math.max.apply(null, c) || 1, iw = W - PL - PR, ih = H - PT - PB, bw = iw / nb;
    let g = '';
    [-96, -48, 0, 48, 96].forEach(v => {
      const x = PL + ((v - LO) / (HI - LO)) * iw;
      g += '<line x1="' + x.toFixed(1) + '" y1="' + PT + '" x2="' + x.toFixed(1) + '" y2="' + (PT + ih) +
        '" stroke="var(--grid)"' + (v === 0 ? ' stroke-width="1.5"' : ' stroke-dasharray="2 3"') + '/>' +
        '<text x="' + x.toFixed(1) + '" y="' + (H - 11) + '" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="10" fill="var(--ink-3)">' +
        (v === 0 ? '0' : (v > 0 ? '+' + v : '−' + Math.abs(v))) + '</text>';
    });
    for (let i = 0; i < nb; i++){
      const x = PL + i * bw, h = (c[i] / mx) * ih, mid = LO + i * BIN + BIN / 2;
      g += '<rect x="' + (x + 1).toFixed(1) + '" y="' + (PT + ih - h).toFixed(1) +
        '" width="' + (bw - 2).toFixed(1) + '" height="' + Math.max(1, h).toFixed(1) +
        '" rx="2" fill="' + (mid > 0 ? 'var(--cool)' : 'var(--warm)') + '" opacity="0.88"/>';
    }
    return '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Distribution of simulated margins">' +
      g + '<line x1="' + PL + '" y1="' + (PT + ih) + '" x2="' + (W - PR) + '" y2="' + (PT + ih) +
      '" stroke="var(--line)"/></svg>';
  }


  /* ------------------------------------------------------------------ sims --
     The run size used to be the literal 20000, printed in the prose as a fixed
     claim. It is a parameter, so it is now on screen as one.

     Raising it is not free and not magic: a Monte Carlo estimate converges at
     1/sqrt(n), so the standard error on the win probability falls by about a
     third each time the run quadruples. Showing that number next to the run
     time is the honest way to present a simulation -- it tells you when more
     sims stop buying precision, which for a two-team margin is well before
     100,000. The readout is measured, never asserted. */
  const N_STEPS = [2000, 10000, 20000, 50000, 100000];
  function currentN(){
    const el = document.getElementById('simN');
    const v = el ? parseInt(el.value, 10) : 20000;
    return (isFinite(v) && v > 0) ? v : 20000;
  }
  function fmtN(n){ return n.toLocaleString(); }
  function reportRun(r, n, ms){
    const se = Math.sqrt(Math.max(r.p * (1 - r.p), 1e-9) / n);   // binomial SE
    const lo = Math.max(0, r.p - 1.96 * se), hi = Math.min(1, r.p + 1.96 * se);
    const out = document.getElementById('simStat');
    if (out) out.innerHTML =
      '<span class="sm"><b>' + fmtN(n) + '</b> simulations</span>' +
      '<span class="sm">&plusmn;<b>' + (se * 100).toFixed(2) + '%</b> standard error</span>' +
      '<span class="sm">95% CI <b>' + (lo * 100).toFixed(1) + '&ndash;' + (hi * 100).toFixed(1) + '%</b></span>' +
      '<span class="sm"><b>' + ms.toFixed(0) + ' ms</b> to run</span>';
    const lbl = document.getElementById('simNLabel');
    if (lbl) lbl.textContent = fmtN(n);
    document.querySelectorAll('.simN-text').forEach(function(e){ e.textContent = fmtN(n); });
  }

  function run(){
    const hn = selH.value, an = selA.value;
    if (hn === an){
      $('verdict').innerHTML = '<div class="side" style="grid-column:1/-1"><p class="role">Pick two different clubs</p></div>';
      $('hist').innerHTML = ''; $('whyRows').innerHTML = ''; $('whysub').textContent = ''; return;
    }
    const neu = $('neutral').checked;
    const nSims = currentN();
    const t0 = (performance && performance.now) ? performance.now() : Date.now();
    const r = sim(hn, an, neu, nSims);
    const ms = ((performance && performance.now) ? performance.now() : Date.now()) - t0;
    reportRun(r, nSims, ms);
    const h = T[hn], a = T[an], hFav = r.p >= .5;
    const card = (nm, role, p, fav, ln, sh) =>
      '<div class="side' + (fav ? ' fav' : '') + '"><p class="role">' + role + '</p>' +
      '<p class="tm">' + esc(nm) + '</p><p class="p">' + (p * 100).toFixed(1) + '<small>%</small></p>' +
      '<p class="freq">wins ' + freq(p) + '</p>' +
      '<p class="line">projected <b>' + ln + '</b> from ' + sh.toFixed(1) + ' shots</p></div>';
    $('verdict').innerHTML =
      card(hn, neu ? 'listed home' : 'at home', r.p, hFav, line(r.hPts, r.hG), r.hSh) +
      card(an, neu ? 'listed away' : 'away', 1 - r.p, !hFav, line(r.aPts, r.aG), r.aSh);
    $('hist').innerHTML = hist(r.margins);
    const em = r.hPts - r.aPts;
    $('whysub').textContent = 'expected margin ' + short(em >= 0 ? hn : an) + ' by ' + Math.abs(em).toFixed(0);

    const row = (lab, say, num, rel) =>
      '<div class="vr"><span class="lab">' + lab + '<br>' +
      (rel === null ? '<span class="eyebrow" style="letter-spacing:.06em">setting</span>' : trustBar(rel)) +
      '</span><span class="say">' + say + '</span><span class="num">' + num + '</span></div>';
    const accH = (h.accuracy - D.meta.leagueAcc) * 100, accA = (a.accuracy - D.meta.leagueAcc) * 100;
    $('whyRows').innerHTML =
      row('Chances made', short(hn) + ' makes <b>' + h.created.toFixed(1) + '</b> a game, ' +
          short(an) + ' <b>' + a.created.toFixed(1) + '</b>.', sgn(h.created - a.created, 1), REL.created.full) +
      row('Chances allowed', short(hn) + ' concedes <b>' + h.conceded.toFixed(1) + '</b>, ' +
          short(an) + ' <b>' + a.conceded.toFixed(1) + '</b>. Fewer is better.',
          sgn(a.conceded - h.conceded, 1), REL.conceded.full) +
      row('Kicking', short(hn) + ' is <b>' + sgn(accH, 1) + 'pp</b> on the league rate, ' +
          short(an) + ' <b>' + sgn(accA, 1) + 'pp</b>. The model keeps about a quarter of each.',
          sgn(accH - accA, 1) + 'pp', REL.accuracy.full) +
      row('Home ground', neu ? 'Switched off for a neutral venue.' :
          'Worth roughly <b>' + ((Math.exp(D.meta.home) - 1) * 100).toFixed(1) +
          '%</b> more shots to the home side. Beyond that, this model knows nothing about the venue or the trip.',
          neu ? 'off' : 'on', null) +
      row('Expected shots', 'What all of that adds up to before a ball is kicked.',
          r.hSh.toFixed(1) + ' v ' + r.aSh.toFixed(1), null);
  }

  const PRE = (D.live && D.live.gf ? D.live.gf : []).map(g => [g.home, g.away, 'Grand final: ' + short(g.home) + ' v ' + short(g.away)]);
  PRE.push(['Hawthorn', 'Fremantle', 'Top two, levelled']);
  $('presets').innerHTML = '<span class="lbl">Try</span>' + PRE.map((p, i) =>
    '<button class="chip" type="button" data-i="' + i + '">' + esc(p[2]) + '</button>').join('');
  $('presets').addEventListener('click', e => {
    const b = e.target.closest('.chip'); if (!b) return;
    const p = PRE[+b.dataset.i];
    selH.value = p[0]; selA.value = p[1]; $('neutral').checked = true; run();
  });

  $('run').addEventListener('click', run);
  $('swap').addEventListener('click', () => { const v = selH.value; selH.value = selA.value; selA.value = v; run(); });
  [selH, selA, $('neutral'), $('simN')].forEach(e => e.addEventListener('change', run));
  run();
})();

/* ====================================================== 5. STRAIGHT TALK === */
(function(){
  const H = D.meta.holdout;
  $('accCopy').innerHTML =
    'The forecaster only ever sees home-and-away football, which makes every final a genuine test. ' +
    'Across the ' + H.n + ' ' + D.meta.season + ' finals it scores <b style="color:var(--ink)">' +
    H.logloss.toFixed(3) + '</b>. Over the regular season it scores <b style="color:var(--ink)">' +
    D.meta.logloss.toFixed(3) + '</b>. Pure guesswork scores <b style="color:var(--ink)">' +
    H.coin.toFixed(3) + '</b>. Lower is better.';
  $('accTiles').innerHTML =
    '<div class="tile"><span class="k">Regular season</span><span class="v">' +
      D.meta.logloss.toFixed(3) + '</span><span class="w">across ' + D.meta.nMatches + ' matches</span></div>' +
    '<div class="tile"><span class="k">Finals, unseen</span><span class="v up">' +
      H.logloss.toFixed(3) + '</span><span class="w">' + H.n + ' matches it never trained on</span></div>' +
    '<div class="tile"><span class="k">Guessing</span><span class="v" style="color:var(--ink-3)">0.693</span>' +
      '<span class="w">the floor it has to beat</span></div>' +
    '<div class="tile"><span class="k">Finals tipped</span><span class="v">' + H.tip.toFixed(0) +
      '%</span><span class="w">' + Math.round(H.tip * H.n / 100) + ' of ' + H.n + '</span></div>';

  const G = [
    ['Scoring shot', 'Any shot that reaches the goal line, goal or behind. Everything on this site is built out of these.', '—', null],
    ['Chances made', 'Shots a side gets away per game. Attack, measured without caring whether the kick went through.', D.meta.reliability.created.full.toFixed(2), REL.created.full],
    ['Chances allowed', 'Shots the opposition gets. This is defence, and no other number a club owns is as dependable.', D.meta.reliability.conceded.full.toFixed(2), REL.conceded.full],
    ['Chance edge', 'Made minus allowed. If you only have time for one number, use this one.', '—', null],
    ['Kicking straight', 'The share of shots that become goals. It feels like the most important thing in football. It is the least predictable thing on this page.', D.meta.reliability.accuracy.full.toFixed(2), REL.accuracy.full],
    ['Earned points', 'The points a club would hold if every match were settled on chances alone, with all 18 sides kicking at the league average.', '—', null],
    ['Luck', 'Actual points minus earned points. Four points is one win. A positive figure means the ball went your way.', '—', null],
    ['Percentage', 'Points scored divided by points conceded, times 100. The AFL separates clubs on it, so it drags along every bit of the kicking noise above.', '—', null],
  ];
  $('glossary').innerHTML = G.map(r =>
    '<div class="vr"><span class="lab">' + r[0] + '<br>' +
    (r[3] === null ? '<span class="eyebrow" style="letter-spacing:.06em">definition</span>' : trustBar(r[3])) +
    '</span><span class="say">' + r[1] + '</span><span class="num">' + r[2] + '</span></div>').join('');

  // ten real matches
  const pool = D.ledger.slice();
  for (let i = pool.length - 1; i > 0; i--){ const j = Math.floor(rnd() * (i + 1)); const t = pool[i]; pool[i] = pool[j]; pool[j] = t; }
  const N = 10; let idx = 0, locked = false, mine = 0, model = 0; const res = [];
  const ll = (p, y) => -(y * Math.log(Math.max(1e-9, p)) + (1 - y) * Math.log(Math.max(1e-9, 1 - p)));

  function draw(){
    const g = pool[idx];
    $('fixture').innerHTML = '<p class="eyebrow">Round ' + g.rd + ' · match ' + (idx + 1) + ' of ' + N + '</p>' +
      '<p class="mu">' + esc(short(g.home)) + ' <em>v</em> ' + esc(short(g.away)) + '</p>' +
      '<p class="eyebrow" style="margin-top:6px">' + esc(short(g.home)) + ' at home</p>';
    $('prange').value = 50; $('pval').textContent = '50%'; $('prange').disabled = false;
    $('pcap').textContent = 'your chance that ' + short(g.home) + ' wins';
    $('reveal').hidden = true; $('lock').hidden = false; $('next').hidden = true; locked = false;
    tally();
  }
  function tally(){
    let h = '<span class="eyebrow" style="margin-right:4px">Scorecard</span>';
    for (let i = 0; i < N; i++) h += '<span class="pip' + (res[i] === undefined ? '' : (res[i] ? ' w' : ' l')) + '">' + (i + 1) + '</span>';
    $('tally').innerHTML = h;
    const n = res.length;
    $('running').innerHTML = n === 0
      ? 'Say 90% and be wrong, and it stings about four times as much as saying 60% and being wrong. That imbalance is the point. Confidence has to be earned before you spend it.'
      : 'After ' + n + ': you <b style="color:var(--ink)">' + (mine / n).toFixed(3) + '</b>, model <b style="color:var(--ink)">' + (model / n).toFixed(3) + '</b>. Lower wins.' +
        (n === N ? ' ' + (mine / n < model / n
          ? 'You beat it across ten matches. Ten is nowhere near enough to prove you would keep beating it.'
          : 'The model is ahead. Not because it knows more football than you, but because it never gets carried away.') : '');
  }
  $('prange').addEventListener('input', e => $('pval').textContent = e.target.value + '%');
  $('lock').addEventListener('click', () => {
    if (locked) return; locked = true;
    const g = pool[idx], you = (+$('prange').value) / 100;
    const a = ll(you, g.won), b = ll(g.p, g.won);
    mine += a; model += b; res.push(a < b);
    const win = g.won ? g.home : g.away;
    $('reveal').hidden = false;
    $('reveal').innerHTML =
      '<div class="rv" style="grid-column:1/-1; background:var(--sunk); text-align:left">' +
      '<p class="who">Actual result</p><p style="margin:4px 0 0; font-family:Oswald,sans-serif; font-size:16px; text-transform:uppercase">' +
      esc(short(win)) + ' won ' + Math.max(g.hs, g['as']) + '–' + Math.min(g.hs, g['as']) + '</p></div>' +
      '<div class="rv' + (a < b ? ' better' : ' worse') + '"><p class="who">You</p><p class="n">' + a.toFixed(3) +
      '</p><p class="sub">said ' + (you * 100).toFixed(0) + '%</p></div>' +
      '<div class="rv' + (b < a ? ' better' : ' worse') + '"><p class="who">Model</p><p class="n">' + b.toFixed(3) +
      '</p><p class="sub">said ' + (g.p * 100).toFixed(0) + '%</p></div>';
    $('prange').disabled = true; $('lock').hidden = true;
    if (idx < N - 1) $('next').hidden = false;
    tally();
  });
  $('next').addEventListener('click', () => { idx++; draw(); });
  draw();
})();


/* ------------------------------------------------- audience switch ========= */
/* One set of numbers, three readings. The figures never change; only the way
   they are explained, and how much statistical detail is on screen.           */
(function(){
  const M = D.meta, S = D.september, FX = D.fixture, H = M.holdout;
  const pct = x => (x * 100).toFixed(0) + '%';

  const COPY = {
    fan: {
      note: 'Plain words, no stats background needed.',
      drawGloss: 'Margin is just the winning gap in points. Over a whole season the gap between the easiest and hardest draw adds up to about ' + FX.spread.toFixed(0) + ' points, which is roughly one and a half wins.',
      tech: 'off',
      ldLadder:
        'Three versions of the same season. <strong>Actual</strong> is the ladder you already know. ' +
        '<strong>Earned</strong> replays every game counting shots at goal instead of who kicked straighter, ' +
        'because straight kicking comes and goes but getting shots does not. <strong>Level</strong> ' +
        'goes further again and takes out the draw your club was handed. The third one is the fair comparison.',
      ldDraw:
        'Your club plays 23 games against 17 rivals, so six of them turn up twice. Which six is decided ' +
        'by what the TV wants. Add in who has to fly and who does not, and no two clubs really play the ' +
        'same season. <strong>Everyone argues about this and nobody has ever put a number on it.</strong> Here it is.',
      ldClub: 'Pick your club and read how its year actually went, in plain words.',
      ldLab: 'Pick any two clubs and watch the match played out <strong class="simN-text">20,000</strong> times. ' +
             'Each run gives both sides a number of shots at goal, then sees how many they kick.',
      ldTalk: 'Every number on this site, explained from scratch. The last column tells you ' +
              '<strong>how much of it is real football</strong> and how much is just the ball bouncing.',
      coDraw:
        '<b>Two things every supporter says that the numbers do not back.</b> The six-day break your ' +
        'coach complains about? Worth nothing you can measure. And home ground advantage turns out to ' +
        'be mostly about the trip, not the crowd. Ten Melbourne clubs share the same two grounds, so ' +
        'playing a cross-town rival at "home" barely helps. What hurts is being the side that flew.',
      readClub:
        '<p style="margin:0 0 14px; font-size:15px; color:var(--ink-2)">If your club goes <b style="color:var(--cool)">up</b> ' +
        'on the earned ladder, the ball was cruel to it this year. Some of that comes back on its own.</p>' +
        '<p style="margin:0; font-size:15px; color:var(--ink-2)">If it goes up again on the level ladder, ' +
        'the fixture was rough as well. That is the one worth complaining about.</p>',
      gfNote:
        '<b>Neither of these two was gifted anything.</b> Across the six finals Fremantle and Brisbane ' +
        'have played this month, the side that got more shots at goal won every single time. That is ' +
        'worth saying, because the ladder that set this whole bracket up had two clubs in the eight who ' +
        'had not earned a spot. The finals themselves have been clean. The one thing still left to go ' +
        'wrong is the flag going to whoever kicks straighter on the day, and that sits at about ' +
        '<b>one chance in ' + Math.round(1 / (S && S.gf ? S.gf.bootProb : 0.15)) + '</b>.',
      acc:
        'The forecaster only ever studies regular-season football, so every final is a fresh test it ' +
        'has never seen. It tipped <b style="color:var(--ink)">' + Math.round(H.tip * H.n / 100) +
        ' of ' + H.n + '</b> finals right. On how confident it was, it scored <b style="color:var(--ink)">' +
        H.logloss.toFixed(3) + '</b>, where a coin toss scores ' + H.coin.toFixed(3) + ' and lower is ' +
        'better. So it knows something. In September, not a lot more than a coin.'
    },

    club: {
      note: 'Decision framing, with the statistics left on.',
      drawGloss: 'Points of margin across a season. Converted to the ladder that is up to three competition points before a ball is kicked, which at the edge of the eight is decisive.',
      tech: 'on',
      ldLadder:
        'Three readings of the same season. <strong>Actual</strong> is the published ladder. ' +
        '<strong>Earned</strong> re-decides every match on scoring shots with conversion held at the ' +
        'league rate, since accuracy repeats at 0.25 and chance creation repeats at 0.88. ' +
        '<strong>Level</strong> then removes the fixture each club was given. Use the third for any ' +
        'list, coaching or review conversation, because it is the only one that compares like with like.',
      ldDraw:
        '23 rounds against 17 opponents forces six double-ups per club, allocated commercially. Travel ' +
        'is allocated by geography. <strong>No audited figure for either has ever been published.</strong> ' +
        'What follows is a fixed-effects estimate over 2,291 matches, with the terms the data does not ' +
        'support left in and marked rather than quietly dropped.',
      ldClub: 'A full club review: attack, defence, conversion, draw difficulty, form and close games, ' +
              'each with the reliability of the measure attached.',
      ldLab: 'Any two clubs, simulated <strong class="simN-text">20,000</strong> times. Scoring shots are drawn per side, ' +
             'then converted, which is the same two-step structure the whole system rests on.',
      ldTalk: 'Definitions, and the split-half reliability behind each one. The reliability column is ' +
              'what should decide how much weight a number carries in a review.',
      coDraw:
        '<b>Two widely held beliefs this data does not support.</b> The six-day turnaround is not ' +
        'distinguishable from zero once opposition strength is controlled for, so it is weak ground for ' +
        'a fixture submission. Home ground advantage also loses significance once travel is separated ' +
        'from it, which follows from ten Victorian clubs sharing venues. The recoverable cost is the ' +
        'opponent’s travel, and that one is worth 5.8 points and holds at p&nbsp;&lt;&nbsp;0.001.',
      readClub:
        '<p style="margin:0 0 14px; font-size:15px; color:var(--ink-2)">A club rising on <b style="color:var(--cool)">earned</b> ' +
        'has been underpaid by conversion variance. Expect regression in its favour without any change ' +
        'to the game plan, and set internal expectations accordingly.</p>' +
        '<p style="margin:0; font-size:15px; color:var(--ink-2)">A club rising again on <b style="color:var(--cool)">level</b> ' +
        'also carried a harder fixture. That is the part with a named decision-maker attached, and the ' +
        'only part worth putting in a submission.</p>',
      gfNote:
        '<b>Neither grand finalist has been carried by variance.</b> In all six finals these two have ' +
        'played, the side creating more scoring shots won. That is a clean bracket sitting on top of a ' +
        'home-and-away ladder that placed two unearned clubs in the eight. The remaining exposure is a ' +
        'conversion-driven result on the day, which the model puts at ' +
        pct(S && S.gf ? S.gf.bootProb : 0.15) + '.',
      acc:
        'The model trains on home-and-away matches only, so every final is genuine holdout. Log-loss ' +
        'across the ' + H.n + ' ' + M.season + ' finals is <b style="color:var(--ink)">' + H.logloss.toFixed(3) +
        '</b> against <b style="color:var(--ink)">' + M.logloss.toFixed(3) + '</b> in the regular season ' +
        'and ' + H.coin.toFixed(3) + ' for an uninformative forecast. Tipping ' + H.tip.toFixed(0) +
        '%. Quote the finals figure in any September context.'
    },

    biz: {
      note: 'What it is worth, and what it puts at risk.',
      drawGloss: 'Points of margin across a season, or up to three competition points once converted. At the edge of the eight that is the difference between a home final and none, with the gate and broadcast value that follows.',
      tech: 'on',
      ldLadder:
        'Three readings of the same season. The published ladder decides finals berths, and a berth ' +
        'carries a home final, additional home gates, broadcast exposure and draft position. ' +
        '<strong>Earned</strong> strips out goal-kicking variance. <strong>Level</strong> also strips ' +
        'out the fixture. Where those three disagree, revenue moved for reasons unconnected to how well ' +
        'a club played.',
      ldDraw:
        'Six of a club’s 23 fixtures are double-ups allocated for broadcast value, and travel falls ' +
        'where geography puts it. Both are commercial decisions with competitive consequences, and ' +
        '<strong>neither has ever been audited in public.</strong> This prices them in on-field terms, ' +
        'which is the input any commercial or governance conversation needs first.',
      ldClub: 'A single-club view suitable for a board pack: performance, the fixture it was dealt, ' +
              'and how much of each number is signal.',
      ldLab: 'A match simulator run <strong class="simN-text">20,000</strong> times per fixture. The output is a ' +
             'probability and a distribution, not a tip, which is the form any pricing or risk ' +
             'conversation needs.',
      ldTalk: 'Definitions and, next to each, how much of the measure repeats. Anything under 0.5 ' +
              'should not carry a decision on its own.',
      coDraw:
        '<b>Two widely held beliefs this data does not support.</b> The six-day break is worth nothing ' +
        'measurable, so scheduling flexibility there costs less competitively than assumed. Home ground ' +
        'advantage is also mostly travel rather than crowd, which matters for any venue or relocation ' +
        'case: moving a fixture between two Melbourne grounds has little competitive effect, while ' +
        'moving one across the country has a large one.',
      readClub:
        '<p style="margin:0 0 14px; font-size:15px; color:var(--ink-2)">A club rising on <b style="color:var(--cool)">earned</b> ' +
        'underperformed its own process. Treat a flat season as more repeatable than the results suggest ' +
        'before writing down forecasts, memberships or sponsorship value.</p>' +
        '<p style="margin:0; font-size:15px; color:var(--ink-2)">A club rising again on <b style="color:var(--cool)">level</b> ' +
        'was also handed the harder schedule. That is an equity question for the league, and a cost ' +
        'the club absorbed without choosing it.</p>',
      gfNote:
        '<b>Both finalists earned the position.</b> In all six finals these two have played, the side ' +
        'creating more scoring shots won, so the bracket has not added distortion to a ladder that ' +
        'already carried some. The live exposure is a single-match conversion result deciding the ' +
        'premiership, which the model puts at ' + pct(S && S.gf ? S.gf.bootProb : 0.15) +
        '. A one-match final is a high-variance way to allocate a season of value, and that is the ' +
        'number to put on it.',
      acc:
        'The model is tested only on matches it never trained on. Across the ' + H.n + ' ' + M.season +
        ' finals it scores <b style="color:var(--ink)">' + H.logloss.toFixed(3) + '</b>, against ' +
        M.logloss.toFixed(3) + ' in the regular season and ' + H.coin.toFixed(3) +
        ' for no information at all. Useful, clearly imperfect, and stated either way. Treat it as ' +
        'directional input, not a pricing model.'
    }
  };

  const IDS = ['ldLadder', 'ldDraw', 'ldClub', 'ldLab', 'ldTalk', 'coDraw', 'readClub', 'drawGloss'];
  const BTN = { fan: 'aud-fan', club: 'aud-club', biz: 'aud-biz' };

  function apply(key){
    const c = COPY[key];
    IDS.forEach(id => { const el = $(id); if (el && c[id]) el.innerHTML = c[id]; });
    const note = $('audNote'); if (note) note.textContent = c.note;
    document.documentElement.setAttribute('data-tech', c.tech);
    const gn = document.querySelector('#gfPanel .heronote'); if (gn) gn.innerHTML = c.gfNote;
    const ac = $('accCopy'); if (ac) ac.innerHTML = c.acc;
    Object.keys(BTN).forEach(k =>
      $(BTN[k]).setAttribute('aria-pressed', k === key ? 'true' : 'false'));
    try { localStorage.setItem('afl-aud', key); } catch (e) {}
  }

  Object.keys(BTN).forEach(k => $(BTN[k]).addEventListener('click', () => apply(k)));

  let start = 'fan';
  try { const v = localStorage.getItem('afl-aud'); if (v && COPY[v]) start = v; } catch (e) {}
  apply(start);
})();

/* ================================================ hero / statband / travel == */
(function(){
  var F = D.fixture, M = D.meta;

  /* Hero effect chips read straight off the model output, so the headline can
     never drift from the numbers underneath it. */
  $('heroEff').innerHTML = F.effects.map(function(e){
    return '<span class="he ' + (e.sig ? 'sig' : 'ns') + '">' +
      '<b>' + sgn(e.beta, 2) + ' pts</b>' + esc(e.name) +
      ' &middot; ' + (e.sig ? 'p = ' + e.p.toFixed(4) : 'n.s.') + '</span>';
  }).join('');

  var trav = F.effects.filter(function(e){ return /travel/i.test(e.name); })[0];
  /* Travel ledger. Same diverging idiom as the draw chart: polarity is carried
     by side of zero and by a signed label, never by colour alone.
     NOTE: Travel calculation is currently simplified (trips × 5.8).
     A more precise destination-weighted calculation exists in the methodology PDF
     but differs from this dashboard output. See afl-draw-methodology.pdf for details. */
  (function(){
    var rows = TEAMS.slice().sort(function(a,b){ return b.travelPts - a.travelPts; });
    var mx = Math.max.apply(null, rows.map(function(t){ return Math.abs(t.travelPts); })) || 1;
    var W = 520, ROW = 20, PT = 26, PL = 118, PR = 62;
    var H = PT + rows.length * ROW + 26;
    var half = (W - PL - PR) / 2, mid = PL + half;
    var sc = function(v){ return (v / mx) * half; };
    var g = '';
    [-20, -10, 0, 10, 20].forEach(function(v){
      if (Math.abs(v) > mx) return;
      var x = mid + sc(v);
      g += '<line x1="' + x.toFixed(1) + '" y1="' + (PT - 6) + '" x2="' + x.toFixed(1) +
        '" y2="' + (PT + rows.length * ROW) + '" stroke="var(--grid)"' +
        (v === 0 ? ' stroke-width="1.5"' : ' stroke-dasharray="2 3"') + '/>' +
        '<text x="' + x.toFixed(1) + '" y="' + (H - 8) + '" text-anchor="middle" ' +
        'font-family="IBM Plex Mono,monospace" font-size="10" fill="var(--ink-3)">' +
        (v > 0 ? '+' + v : v) + '</text>';
    });
    rows.forEach(function(t, i){
      var y = PT + i * ROW, w = Math.abs(sc(t.travelPts));
      var x = t.travelPts >= 0 ? mid : mid - w;
      var col = t.travelPts >= 0 ? 'var(--cool)' : 'var(--warm)';
      g += '<text x="' + (PL - 10) + '" y="' + (y + 12) + '" text-anchor="end" ' +
        'font-family="Oswald,sans-serif" font-size="11.5" fill="var(--ink)">' + esc(short(t.team)) + '</text>' +
        '<rect x="' + x.toFixed(1) + '" y="' + (y + 3) + '" width="' + Math.max(1.5, w).toFixed(1) +
        '" height="11" rx="3" fill="' + col + '"/>' +
        '<text x="' + (W - 8) + '" y="' + (y + 12) + '" text-anchor="end" ' +
        'font-family="IBM Plex Mono,monospace" font-size="10" fill="var(--ink-3)">' +
        sgn(t.travelPts, 1) + '  &middot; ' + t.trips + ' trips</text>';
    });
    $('travelChart').innerHTML = '<svg viewBox="0 0 ' + W + ' ' + H +
      '" role="img" aria-label="Net travel effect by club, with number of interstate trips flown">' +
      '<text x="' + PL + '" y="12" font-family="IBM Plex Mono,monospace" font-size="9.5" ' +
      'fill="var(--ink-3)" letter-spacing="1">COST BY TRAVEL \u2190      \u2192 GAINED</text>' + g + '</svg>';
  })();
})();

/* ===================================================== sticky club selector == */
(function(){
  var sel = $('clubSel'), strip = $('clubStrip'), row = $('csRow');
  function ord(n){ var a=['th','st','nd','rd'], v=n%100; return n+(a[(v-20)%10]||a[v]||a[0]); }
  var names = NAMES;
  sel.innerHTML = '<option value="">Choose&hellip;</option>' +
    names.map(function(n){ return '<option value="' + esc(n) + '">' + esc(n) + '</option>'; }).join('');

  function paint(name){
    var t = TEAMS.filter(function(x){ return x.team === name; })[0];
    if (!t){ strip.classList.remove('on'); return; }
    var mv = t.posActual - t.posLevel;              // + means climbs once levelled
    var cls = mv > 0 ? 'up' : (mv < 0 ? 'dn' : '');
    var mvTxt = mv === 0 ? 'no change' :
      (Math.abs(mv) + ' place' + (Math.abs(mv) === 1 ? '' : 's') + (mv > 0 ? ' up' : ' down'));
    row.innerHTML =
      '<span class="cname">' + esc(t.team) + '</span>' +
      '<span class="ci">finished<b>' + ord(t.posActual) + '</b></span>' +
      '<span class="ci">levelled<b class="' + cls + '">' + ord(t.posLevel) + '</b></span>' +
      '<span class="ci">that is<b class="' + cls + '">' + mvTxt + '</b></span>' +
      '<span class="ci">draw worth<b>' + sgn(t.drawPts, 1) + ' pts</b></span>' +
      '<span class="ci">travel<b>' + sgn(t.travelPts, 1) + ' pts over ' + t.trips + ' trips</b></span>';
    strip.classList.add('on');
  }

  sel.addEventListener('change', function(){
    paint(sel.value);
    try { sel.value ? localStorage.setItem('afl.club', sel.value) : localStorage.removeItem('afl.club'); }
    catch(e){}
  });

  var saved = null;
  try { saved = localStorage.getItem('afl.club'); } catch(e){}
  if (saved && names.indexOf(saved) > -1){ sel.value = saved; paint(saved); }
})();

/* section nav removed: navigation is now between pages, see afl-nav.js */

})();

/* Landing-page figures + cross-page club memory.
   Runs after afl.js. Everything here reads from window.__AFL__ so the numbers
   on the front page cannot disagree with the ones inside the sections. */
(function(){
  "use strict";
  var D = window.__AFL__; if (!D) return;
  var M = D.meta, F = D.fixture, T = D.teams;
  var $ = function(id){ return document.getElementById(id); };
  var esc = function(s){ return String(s).replace(/[&<>"]/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); };
  var sgn = function(x,d){ return (x>0?'+':x<0?'−':'') + Math.abs(x).toFixed(d==null?1:d); };

  /* ---- hero capsule: the reference's countdown block, pointed at real output */
  var cap = $('heroCapsule');
  if (cap){
    var trav = F.effects.filter(function(e){ return /travel/i.test(e.name); })[0];
    cap.innerHTML = [
      [F.nMatches.toLocaleString(), 'matches'],
      [trav ? sgn(trav.beta,1) : '–', 'pts per flight', true],
      [F.spread, 'pts of draw spread'],
      [M.seasons.replace('–','&ndash;'), 'seasons']
    ].map(function(r){
      return '<div class="c"><b' + (r[2] ? ' class="acc"' : '') + '>' + r[0] + '</b><span>' + r[1] + '</span></div>';
    }).join('');
  }

  /* ---- lime figure stack */
  var lf = $('limeFigs');
  if (lf){
    lf.innerHTML = [
      [Math.round(M.reliability.created.full*100) + '%', 'chance creation repeats'],
      [Math.round(M.reliability.accuracy.full*100) + '%', 'goal accuracy repeats'],
      [M.logloss.toFixed(4), 'log-loss over ' + M.nMatches + ' games']
    ].map(function(r){ return '<div class="f"><b>' + r[0] + '</b><span>' + r[1] + '</span></div>'; }).join('');
  }

  /* ---- club selector persists across pages, so picking once follows you */
  var sel = $('clubSel'), strip = $('clubStrip'), row = $('csRow');
  if (!sel) return; // only return if club selector missing, hero already rendered above
  function ord(n){ var a=['th','st','nd','rd'], v=n%100; return n+(a[(v-20)%10]||a[v]||a[0]); }
  var names = T.map(function(t){ return t.team; }).sort();
  sel.innerHTML = '<option value="">Choose&hellip;</option>' +
    names.map(function(n){ return '<option value="'+esc(n)+'">'+esc(n)+'</option>'; }).join('');

  function paint(name){
    var t = T.filter(function(x){ return x.team === name; })[0];
    if (!t || !row){ if (strip) strip.classList.remove('on'); return; }
    var mv = t.posActual - t.posLevel, cls = mv>0?'up':(mv<0?'dn':'');
    var mvTxt = mv === 0 ? 'no change'
      : Math.abs(mv) + ' place' + (Math.abs(mv)===1?'':'s') + (mv>0?' up':' down');
    row.innerHTML =
      '<span class="cname">'+esc(t.team)+'</span>'+
      '<span class="ci">finished<b>'+ord(t.posActual)+'</b></span>'+
      '<span class="ci">levelled<b class="'+cls+'">'+ord(t.posLevel)+'</b></span>'+
      '<span class="ci">that is<b class="'+cls+'">'+mvTxt+'</b></span>'+
      '<span class="ci">draw worth<b>'+sgn(t.drawPts,1)+' pts</b></span>'+
      '<span class="ci">travel<b>'+sgn(t.travelPts,1)+' pts over '+t.trips+' trips</b></span>';
    strip.classList.add('on');
  }
  sel.addEventListener('change', function(){
    paint(sel.value);
    try { sel.value ? localStorage.setItem('afl.club', sel.value)
                    : localStorage.removeItem('afl.club'); } catch(e){}
  });
  var saved = null; try { saved = localStorage.getItem('afl.club'); } catch(e){}
  if (saved && names.indexOf(saved) > -1){ sel.value = saved; paint(saved); }
})();

/* ------------------------------------------------------------------ router --
   Sections are routes, not anchors: one is in the flow at a time, so the page
   opens on a single idea rather than five stacked ones. The URL carries the
   route (#draw), so a link to a section still lands on that section, and
   back/forward behave because hashchange fires on both.

   Everything is rendered once at load while all sections are still in the DOM;
   routing only toggles visibility. That keeps charts off the critical path of
   a click -- no re-render, no flash. */
(function(){
  var routes = [].slice.call(document.querySelectorAll('[data-route]'));
  var links  = [].slice.call(document.querySelectorAll('[data-nav]'));
  var names  = routes.map(function(s){ return s.getAttribute('data-route'); });

  function go(name, push){
    if (names.indexOf(name) < 0) name = 'overview';
    routes.forEach(function(s){
      s.classList.toggle('active', s.getAttribute('data-route') === name);
    });
    links.forEach(function(a){
      a.setAttribute('aria-current', a.getAttribute('data-nav') === name ? 'page' : 'false');
    });
    document.title = (name === 'overview' ? 'The Ladder Lies'
                                          : name.charAt(0).toUpperCase() + name.slice(1)
                                            + ' \u00b7 The Ladder Lies');
    if (push && location.hash !== '#' + name) history.pushState(null, '', '#' + name);
    window.scrollTo(0, 0);
  }

  /* Intercept in-page links rather than relying on the browser's anchor jump,
     which would scroll to a hidden element and land nowhere. */
  document.addEventListener('click', function(e){
    var a = e.target.closest && e.target.closest('a[href^="#"]');
    if (!a) return;
    var name = a.getAttribute('href').slice(1);
    if (names.indexOf(name) < 0) return;
    e.preventDefault();
    go(name, true);
  });

  window.addEventListener('hashchange', function(){ go(location.hash.slice(1), false); });
  window.addEventListener('popstate',  function(){ go(location.hash.slice(1), false); });
  go(location.hash.slice(1) || 'overview', false);
})();
