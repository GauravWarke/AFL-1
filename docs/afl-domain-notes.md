# AFL domain notes

Everything here was measured on 2,468 matches (2015–2026, Squiggle API) using
the scripts in `src/`. Where a claim is an inference rather than a measurement,
it says so. Where a plausible claim turned out to be **wrong**, it is kept in
with the evidence, because the wrong ones were the most useful.

---

## 1. How AFL scoring works, and why it matters statistically

A **goal** is 6 points, a **behind** is 1. Scores read `15.10 (100)`.

A **scoring shot** is any shot that reached the goal line — a goal or a behind.
It measures how often a team got into a scoring position. **Accuracy** is the
share converted into goals.

The league converts **52.86%** of scoring shots. A typical match is around 25
scoring shots a side.

This creates the structural feature that defines the sport statistically: a
team can comprehensively out-play an opponent and still lose, purely by kicking
badly. Few other codes separate chance creation from conversion so cleanly.

---

## 2. Accuracy is mostly luck. Scoring shots are mostly skill.

Measured two independent ways on 216 team-seasons.

| metric | reliability | method |
|---|---|---|
| goal accuracy | **0.32** | binomial: `1 − E[p(1−p)/n] / var(observed)` |
| goal accuracy | **0.25** | split-half (odd vs even games), Spearman-Brown |
| scoring shots generated | **0.88** | split-half |
| scoring shots conceded | **0.87** | split-half |

Reliability is the share of observed spread that is repeatable skill rather
than noise. So roughly **two-thirds to three-quarters of the spread in team
goal accuracy is luck**, while shot generation and shot prevention are strongly
repeatable.

The two accuracy estimates agree closely (0.32 vs 0.25), which also tells us
the binomial assumption is roughly sound — shots within a match are not wildly
dependent on each other.

**Consequence for fans:** when a team loses having had more scoring shots, the
useful thing to say is not "they were unlucky" as a platitude but as a
measurement — most of the accuracy gap will not repeat next week.

---

## 3. The claim that did NOT survive contact with the data

> **Wrong:** "Because accuracy is noisy, rating teams on scoring shots will
> predict future results better than rating them on points."

This is the expected-goals argument imported from soccer. It is intuitive, it
follows from section 2, and **it is false for the AFL.**

Design: rate each team on the first half of a season, score how well that
rating predicts their margins in the second half. 216 team-seasons, no overlap.

| predictor | r with future margin | r² |
|---|---|---|
| points differential | **+0.710** | 0.504 |
| scoring-shot differential | +0.702 | 0.493 |
| expected margin (shots at league conversion) | +0.702 | 0.493 |
| expected margin, accuracy shrunk by its reliability | +0.709 | 0.503 |

Paired bootstrap on the *difference* in correlations (they are computed on the
same rows, so they are dependent and cannot be compared as independent
intervals):

| challenger vs points differential | Δr | 95% CI | p |
|---|---|---|---|
| scoring-shot differential | −0.008 | [−0.034, +0.019] | 0.54 |
| expected margin | −0.008 | [−0.034, +0.019] | 0.55 |
| expected margin, shrunk | −0.001 | [−0.023, +0.023] | 0.94 |

All four are statistically indistinguishable. **Nothing beats plain points
differential.**

*Why the soccer result does not transfer* — an inference, not a measurement:
in soccer, goals are rare (~2.7 a game), so conversion noise is enormous
relative to signal and stripping it out helps a lot. In the AFL a side takes
~25 scoring shots a game, so over eleven games that is ~280 Bernoulli trials
and accuracy noise largely averages itself out. And a missed shot in the AFL
still scores a point, so the penalty for inaccuracy is far smaller than
soccer's zero.

**This is why the model works on margins and scoring shots rather than on wins.**
A win discards the size of the win; margins keep it, and scoring shots keep the
part of the margin that repeats.

---

## 4. Home advantage: real, large, and mostly about interstate travel

Estimated as three terms rather than one scalar:

| term | estimate |
|---|---|
| base home advantage (host is genuinely at home) | **+2.53 pts** |
| away side travelled interstate | **+6.25 pts** |
| per hour of timezone shift for the away side | +1.25 pts |

Worked example:

| fixture | home advantage |
|---|---|
| a Victorian side hosting a Victorian side at the MCG | **+2.5 pts** |
| Fremantle hosting a Victorian side in Perth | **+11.3 pts** |

So a Perth home final is worth roughly **four and a half times** an MCG home
final between two Melbourne clubs. Interstate travel does nearly all the work;
the timezone term adds only about +2.5 points on top for the Perth trip.

### The second claim that did not survive

> **Wrong:** "AFL home advantage cannot be modelled as a scalar."

It can, for *prediction*. Walk-forward comparison, refitting every round:

| HGA model | decay | MAE | tip % |
|---|---|---|---|
| scalar | 0.80 | **26.36** | 68.25 |
| venue-aware | 0.80 | 26.43 | 67.79 |

The venue model does **not** predict better. The reason is that team strength
absorbs it: WA sides play half their matches in Perth, so a scalar-HGA model
quietly credits their travel advantage to their rating instead. The two models
disagree about *why* Fremantle wins in Perth but agree about *whether*.

The venue model is kept anyway, for two defensible reasons: it is what makes
the +11.3 vs +2.5 comparison sayable at all, and finals venues differ
systematically from home-and-away venues, so the decomposition matters more in
September than the season-long MAE suggests.

---

## 5. Model parameters

| quantity | AFL |
|---|---|
| match-level residual σ | 32.5 pts |
| season-to-season drift in true strength | 9.72 pts |
| drift as a share of σ | **0.30** | **0.30** |

The absolute numbers differ by a factor of ~2.4 because AFL scores are bigger.
Scaled by match noise the two competitions are almost identical — teams change
by about a third of a match's worth of randomness from one year to the next.

Drift is estimated by subtracting estimation error, not from raw year-on-year
change:

```
var(observed change) = 2 × var(estimation error) + var(true drift)
13.73²                = 2 × 9.70²/2                + 9.72²
```

Skipping that subtraction is what made an earlier version's 80% intervals cover
only 62.5% of outcomes.

**Recency weighting: 0.80 per season.** Tuned by walk-forward, refitting every
round. The optimum is interior — 0.85 and 0.90 are worse — so it is a real
optimum, not a grid edge. At 0.80, last season carries 20% of current-season
weight and two seasons ago 4%. AFL lists turn over fast.

---

## 6. The finals are close to a lottery, and this is the headline

Brier score for predicting the premier, 2016–2025, 80 team-seasons:

| | Brier | skill score |
|---|---|---|
| our model | 0.10758 | — |
| uniform 1-in-8 | 0.10938 | **+0.016** |
| historical base rate by ladder position | 0.11111 | **+0.032** |

The model beats both baselines, but by very little. Our favourite won 1 of 10
premierships against an expected 3.24 (exact Poisson-binomial p = 0.114 — bad
luck rather than demonstrable overconfidence, but only just).

This is not a broken model. It is a fact about the competition. A premiership
requires winning four knockout matches; with σ = 32.5 points and typical
finalist rating gaps of 5–15 points, every one of those is much closer to a
coin toss than the ladder suggests. **Any AFL model claiming high confidence in
a premier is overselling.**

The right way to present this to fans is as frequencies, not decimals: a 29%
favourite is *"wins about three Septembers in ten"*.

---

## 7. The 2026 format change

First change to the AFL finals system since 2000. Ten finalists instead of
eight, over five weeks.

- **Wildcard round:** 7th hosts 10th, 8th hosts 9th. Winners take seeds 7 and 8,
  ordered by original ladder position. Losers are out. Seeds 1–6 skip the week.
- Then the standard final-eight system, unchanged.

*Confirmed rather than assumed*: in 2026, 8th (Western Bulldogs) and 10th
(Carlton) both won their wildcard finals, and the Bulldogs were seeded above
Carlton — so re-seeding follows ladder position, not wildcard bracket.

The AFL Fans Association opposed it; a sports rights analyst attributed it to
protecting the $4.5bn broadcast deal by reducing dead rubbers late in the year.

**This creates a genuine methodological problem:** the format has no history, so
the bracket cannot be backtested. The project separates the two things being
tested — the *engine* is validated on 2015–2025 under the old format, and the
*format* is checked against structural invariants (premiers sum to 1, grand
finalists to 2, preliminary finalists to 4, byes to 2, wildcard teams claim
exactly 2 of the eight places). See `src/sportspred/bracket.py`.

Also new in 2026: the centre bounce was abolished (ball thrown up) and the
substitute rule replaced with a five-player interchange. Both plausibly shift
match distributions, so pooling 2026 with earlier seasons is an assumption that
has not yet been tested here. **Listed as an open item, not a settled one.**

---

## 8. Things that will bite you

- **Percentage, not differential.** The ladder tiebreaker is
  `100 × points_for / points_against` — a *ratio*, asymmetric and unbounded
  above. Do not port a margin model's intuitions onto it.
- **Draws happen.** 21 in 2,468 matches (0.85%). Home-and-away matches can end
  level; finals go to extra time. A binary win model silently mislabels them.
  Squiggle's tipping convention scores a draw as half a tip.
- **The schedule is unbalanced.** 23 matches, 18 teams — nobody plays everyone
  twice, so the ladder is a biased ranking and strength of schedule is real.
- **Shared home grounds.** Ten of eighteen clubs are Victorian and most play at
  the MCG or Docklands. "Home" means much less to them than to Fremantle.
- **Venue names change with sponsors.** Squiggle uses traditional names
  (`Perth Stadium`, not `Optus Stadium`), which is what makes a 12-year history
  joinable at all.

---

## Sources

- Match data: [Squiggle API](https://api.squiggle.com.au) (same underlying data
  as `fitzRoy`/AFL Tables, served as JSON).
- [2026 AFL season](https://en.wikipedia.org/wiki/2026_AFL_season) — format
  change, rule changes, wildcard structure.
- [Biggest finals shake-up in 25 years as Wildcard Round introduced](https://www.afl.com.au/news/1451972/biggest-finals-shake-up-in-25-years-as-wildcard-round-introduced),
  afl.com.au, 10 November 2025.
- [AFL gives teams finishing 10th chance to win premiership through wildcard round](https://www.abc.net.au/news/2025-11-10/afl-introduces-wildcard-round-to-finals/105990434),
  ABC News, 10 November 2025.
- [Shots at goal in Australian Football: historical trends, determinants of accuracy and common strategies](https://www.sciencedirect.com/science/article/pii/S1440244024000756),
  *Journal of Science and Medicine in Sport* — confirms distance, angle and
  player type drive accuracy, and notes that the professional league's own
  expected-score model is unpublished.
