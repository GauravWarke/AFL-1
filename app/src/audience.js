
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
      ldLab: 'Pick any two clubs and watch the match played out <strong>20,000 times</strong>. ' +
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
      ldLab: 'Any two clubs, simulated <strong>20,000 times</strong>. Scoring shots are drawn per side, ' +
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
      ldLab: 'A match simulator run <strong>20,000 times</strong> per fixture. The output is a ' +
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
