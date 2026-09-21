# What the 2026 AFL draw was worth

**A method note on separating list quality from fixture quality.**

Gaurav Warke · September 2026 · Season 2026, 2,291 matches

---

This note exists so the numbers can be checked by someone who was not in the room
when they were presented. It states what was estimated, what came back
significant, what did not, and where the method stops being reliable. The nulls
are reported alongside the findings, because a method that only reports what it
found is not a method.

## The question

Two clubs finish a season four places apart. How much of that gap is the players
and how much is the fixture? Every club argues this internally in November. The
argument is usually settled by whoever is most senior in the room, because nobody
has a number.

This estimates the number.

## Data and model

Every men's AFL match from 2015 to 2026, 2,291 games, from the AFL's own match
records via the `fitzRoy` R package. The outcome modelled is **match margin in
points**. The fixture variables are attached to each team-match and are known
before the game is played, so none of them can absorb the result they are
predicting.

A linear model on margin, with team and opponent strength controlled, leaves four
fixture effects to estimate:

| Effect | Points of margin | 95% CI | p | Verdict |
|---|---:|:---:|---:|:---|
| Playing on your own ground | **+1.75** | −0.56 to +4.06 | 0.138 | not significant |
| Having travelled interstate | **−5.80** | −9.08 to −2.53 | **0.0005** | **significant** |
| Each hour of time-zone change | **−1.50** | −3.52 to +0.53 | 0.147 | not significant |
| Coming off a six-day break | **+0.90** | −1.42 to +3.21 | 0.449 | not significant |

Model R² = 0.446 on n = 2,291.

**One of these four is real.** Only the travel term is applied in everything
downstream. The other three are reported and then set to zero, rather than kept
in at a small value because the sign looked plausible.

## The three findings, in order of how well they hold up

### 1. The six-day break is worth nothing

+0.9 points, confidence interval spanning zero in both directions, p = 0.45. On
this data a club coming off five days' rest and a club coming off nine are
indistinguishable once you know who they are playing and where.

This is the most robust claim in the note because it is a null. It does not
depend on a modelling choice going a particular way; the effect simply is not
large enough to detect in 2,291 games. If a six-day break were worth even two
goals, this sample would see it.

### 2. Home ground advantage is mostly not the ground

Playing at your own venue is worth +1.75 points and is not statistically
distinguishable from zero. Having flown interstate to get to a match costs 5.8
points, and that one is solid (p = 0.0005).

Home ground advantage in the AFL is therefore better described as an *away*
disadvantage. It is not familiarity with the ground, the crowd, or the goal
posts. It is that the other side got on a plane. A Melbourne club hosting another
Melbourne club at the MCG has almost no edge at all, and that is exactly what the
data shows.

### 3. The two Perth clubs are the biggest winners from travel

A trip to Perth costs a visiting side **8.8 points** — the most expensive journey
in the competition.

West Coast and Fremantle each made 10 interstate trips in 2026, more than any
Victorian club. They still finish first and third on the travel ledger:

| Club | Net travel effect | Interstate trips |
|---|---:|---:|
| West Coast | **+20.7** | 10 |
| Port Adelaide | +18.8 | 10 |
| Fremantle | **+17.4** | 10 |
| Adelaide | +11.7 | 10 |
| … | | |
| North Melbourne | −23.7 | 8 |
| Hawthorn | −28.5 | 10 |

The reason is one-sided accounting. The Perth clubs pay the travel cost on their
own trips, but every visitor to Perth pays the largest penalty on the schedule.
They fly a great deal and still come out ahead, because the flight they impose on
others is worse than the flight they take themselves.

A caveat that belongs with this finding: the *net* season effect for both Perth
clubs has a confidence interval crossing zero (West Coast +23.6, CI −3.0 to
+48.6; Fremantle +9.7, CI −23.8 to +49.3). The direction is consistent and the
mechanism is clear, but the total is not individually significant for either
club. The travel term underneath it is.

## The three ladders

Three ladders are produced, and the distinction matters more than any single
position.

| Ladder | What is removed | Answers |
|---|---|---|
| **Actual** | nothing | What happened |
| **Earned** | goal-kicking luck | What their football won |
| **Level field** | kicking luck *and* the fixture | What the list is worth |

"Earned" replaces each match result with the scoring-shot differential, on the
basis that creating shots repeats from one half of a season to the next
(reliability 0.88) while converting them barely does (0.25). "Level field" then
removes the fixture burden on top.

**The level-field ladder is the one to quote.** It is the complete adjustment.
The earned ladder is an intermediate step shown for transparency, and a club will
sometimes sit a place apart on the two.

Across the competition the draw was worth a spread of **135.8 points of margin**
between the most and least favoured club — an average of 5.9 points a game.

## Limitations

**The level-field ladder is a counterfactual, not a result.** It says what the
ladder would look like if every club had faced an identical schedule. No club
played that season. Treat it as a way of comparing lists, not as a claim that a
different team deserved the flag.

**The travel coefficient is an average.** It does not distinguish a Thursday
night flight from a Saturday morning one, a charter from a commercial service, or
a club with a settled interstate routine from one without. Clubs hold the data
that would separate these; this note does not.

**Opponent strength is measured within the same season.** Strength of schedule is
therefore partly circular: a club looks to have had a hard draw partly because
the sides it played won games, some of which were against that club.

**The prediction model is good, not remarkable.** Walking forward through the
2026 season it scores a log-loss of 0.5229 over 217 matches, against 0.693 for
a coin toss, and tips at 69.4%. It beat six alternatives, but only three of
those gaps are statistically real: ridge regression (p = 0.18) and Elo
(p = 0.28) are tied with it on this sample.

**And it has been overconfident about premierships.** Replaying 2016 to 2025
under the old finals system, the side it installed as favourite won 2 flags out
of 10, against 3.7 expected. That is not damning on ten observations
(P(≤2) = 0.22) but it points one way, and September is the part of the year
this model finds hardest.

**Nothing here is causal.** These are associations measured on observational
data. The fixture is not randomly assigned: the AFL schedules blockbusters,
protects broadcast windows, and gives travel concessions. Some of what is
attributed to travel may be scheduling that correlates with it.

## Reproducing this

All figures come from `outputs/fixture_equity.json` and
`outputs/level_field.json`, produced by `app/build/fixture_audit.py` and
`app/build/level_field.py`. Data is refreshed from the AFL via
`R/06_live_data.R`. The model bake-off that selected the prediction engine is
documented separately in `docs/model-bakeoff.md`.

Figures in this note were generated on 21 September 2026 from data current to the
2026 preliminary finals.

---

*Questions, corrections and arguments are all welcome. The corrections are the
most useful.*
