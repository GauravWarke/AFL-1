# Which model predicts AFL matches best?

Seven models, one protocol, 211 matches. Everything below was produced by
`R/03_bakeoff.R` and executed in RStudio — no result here is from unrun code.

---

## The protocol

Walk forward through the 2026 season one round at a time. Before each round,
every model is **rebuilt from scratch** on every match played before it — all
prior seasons plus the current season to date — then asked to predict that
round. No model ever sees a result it is being asked to predict.

2026 is the evaluation window because that is exactly the window the 31 public
models on [Squiggle](https://squiggle.com.au) are scored over, so our numbers
and theirs are directly comparable. All seven models are scored on the same
211 matches, so none of them sat an easier exam.

**Log-loss is the headline metric.** This system feeds a Monte Carlo simulator,
so what matters is whether the stated probabilities are honest, not just
whether the favourite got picked. A model that says 90% when it means 60% will
produce a confidently wrong premiership table.

---

## Results

| model | log-loss | Brier | tip % | margin MAE | calibration |
|---|---|---|---|---|---|
| **Scoring shots + accuracy** | **0.5212** | 0.1781 | 68.5 | 25.70 | 1.20 |
| Ridge margin | 0.5348 | 0.1816 | 69.9 | 25.96 | 1.39 |
| Elo | 0.5382 | 0.1833 | 67.1 | 28.44 | 0.95 |
| Bayesian hierarchical | 0.5473 | 0.1857 | 70.4 | 26.12 | 1.58 |
| Bradley-Terry | 0.5647 | 0.1936 | 67.5 | 28.82 | 1.07 |
| Gradient boosting (xgboost) | 0.5948 | 0.2065 | 66.1 | 27.73 | 0.97 |
| Random forest | 0.6417 | 0.2212 | 67.1 | 28.10 | 0.51 |

Calibration is the slope of the outcome regressed on the stated log-odds. 1.00
is perfect; below 1 means overconfident, above 1 means underconfident.

### The winner

**Scoring shots + accuracy** — a negative-binomial model of how many scoring
shots each side generates and concedes, combined with a binomial conversion
step. It builds a score the way the sport actually builds one, and it is the
only entrant that encodes the domain finding directly: shots are skill
(reliability 0.88), accuracy is mostly luck (0.32), so team accuracy is shrunk
hard toward the league mean rather than fitted freely.

### But is it really better? Paired bootstrap on the log-loss difference

The models are scored on the same matches, so their errors are dependent and
separate confidence intervals would mislead. Bootstrapping the *difference*:

| shots vs | Δ log-loss | 95% CI | p | verdict |
|---|---|---|---|---|
| Ridge margin | −0.0136 | [−0.032, +0.006] | 0.158 | **tied** |
| Elo | −0.0170 | [−0.046, +0.009] | 0.209 | **tied** |
| Bayesian hierarchical | −0.0260 | [−0.049, −0.003] | 0.023 | shots better |
| Bradley-Terry | −0.0435 | [−0.071, −0.018] | 0.001 | shots better |
| Gradient boosting | −0.0736 | [−0.115, −0.032] | 0.001 | shots better |
| Random forest | −0.1205 | [−0.191, −0.052] | 0.001 | shots better |

So the honest statement is: **the top three are statistically tied**, and all
three clearly beat the tree ensembles and the win/loss-only model. The shots
model is used because it wins on the point estimate *and* is the most
interpretable to a club — "you created 24 chances and gave up 21" is a
sentence a coach can act on.

---

## Three things that did not go as expected

**1. The tree ensembles lost, badly.** Random forest is the worst model tested,
and it is the one the AFL workshop material reaches for first. Its calibration
slope of 0.51 says it is severely overconfident: it states extreme
probabilities that the results do not support. Trees also cannot extrapolate,
and they get no help from the +1/−1 team structure that the linear models
exploit for free.

**2. Averaging the models made things worse.** Ensembling usually helps, and
Squiggle runs this experiment publicly with its "Aggregate" entry. Averaging
our top four gives log-loss **0.5293** — worse than the best single model at
0.5212. With four models that share most of their information, averaging just
pulled the best one toward the weaker ones.

**3. Tipping percentage and probability quality are different things.** Our
Bayesian model tips the most winners of our seven (70.4%) and ranks fourth on
log-loss. On the public leaderboard the effect is starker: **Holy Grail
Ratings tipped 74.4%, the best of anyone, and had the worst log-loss on the
board (0.5780)** — right often, and overconfident constantly. Any AFL model
judged on tipping percentage alone is being judged on the wrong thing.

---

## Against the 31 public models

Same 211 matches, same season.

| rank | model | tip % | MAE | log-loss |
|---|---|---|---|---|
| 1 | Don't Blame the Data | 72.0 | 25.58 | 0.5114 |
| 2 | Punters | 73.9 | 25.20 | 0.5125 |
| 3 | s10 | 73.9 | 25.07 | 0.5128 |
| … | | | | |
| 11 | ZaphBot | 73.5 | 25.99 | 0.5201 |
| **12** | **Scoring shots + accuracy (ours)** | **68.5** | **25.70** | **0.5212** |
| 13 | Aggregate | 73.0 | 25.13 | 0.5228 |
| … | | | | |
| 22 | Ridge margin (ours) | 69.9 | 25.96 | 0.5348 |
| 23 | Elo (ours) | 67.1 | 28.44 | 0.5382 |

**12th of 38. Beats 20 of the 31 public models (65th percentile).** Public
median log-loss 0.5264; best 0.5114.

Read honestly: our margin error (25.70) is level with the public median
(25.72), and our probabilities are better than most. Our *tipping* percentage
(68.5) is below the public median (71.9) — the model is well calibrated but
picks slightly fewer winners, which is the trade it makes by refusing to state
confidence it cannot support.

---

## Why simulation rather than a formula

A knockout bracket has sequential dependence — who you meet in week three
depends on who won in weeks one and two. Chaining those conditional
probabilities by hand is feasible for a four-team bracket and hopeless for this
one, which has a wildcard round, a double-chance path, re-seeding, and venue
effects that change with every possible pairing.

So the tournament is played out **20,000 times** and the outcomes counted. That
is exact up to Monte Carlo error, and it stays readable.

**Finals already played are treated as fact, not re-rolled.** Mid-series that
is most of the value: with the wildcard round, one qualifying final and one
elimination final decided, four of the nine matches are settled and the
remaining uncertainty is far narrower than a pre-finals projection.

---

## Validating a bracket nobody has played

2026 is the first change to the AFL finals system since 2000, so there is no
history of this format to backtest. The two testable things are separated:

**The engine** — rate teams, convert to probabilities, walk a bracket — is
format-independent, so it is validated on 2015–2025 under the old eight-team
system:

| | |
|---|---|
| seasons tested | 10 |
| our favourite won | 2 |
| expected | 3.69 |
| P(≤2 wins, given the model is right) | **0.219** |
| mean probability given to the actual premier | 0.203 |
| structural invariants | **all pass, all 10 seasons** |

Consistent with the model — bad luck rather than demonstrable overconfidence.
The exact Poisson-binomial is used rather than a normal approximation, since
ten seasons is far too few for the approximation to hold.

**The format** cannot be validated against history, so it is checked against
invariants that must hold for any correct bracket:

- premiership probabilities sum to 1
- grand finalists sum to 2
- preliminary finalists sum to 4
- byes sum to 2
- the top six have guaranteed final-eight places
- the wildcard sides claim exactly 2 of the 8 places
- no side wins the flag more often than it reaches the grand final

All pass. Implemented in `check_invariants()` in `R/04_simulate.R`.

---

## Current projection

As at 5 September 2026, conditioning on four completed finals (Western Bulldogs
def Collingwood, Carlton def Melbourne, **Hawthorn def Fremantle**, Geelong def
Carlton):

| team | ladder | premiership | in plain words |
|---|---|---|---|
| Hawthorn | 4th | **34.9%** | about 3 Septembers in 10 |
| Fremantle | 1st | 18.1% | about 2 Septembers in 10 |
| Sydney | 2nd | 17.6% | about 2 Septembers in 10 |
| Brisbane Lions | 3rd | 17.2% | about 2 Septembers in 10 |
| Geelong | 5th | 10.5% | about 1 September in 10 |
| Adelaide | 6th | 1.5% | fewer than 1 September in 50 |
| Western Bulldogs | 8th | 0.3% | fewer than 1 September in 50 |
| Melbourne, Collingwood, Carlton | — | 0% | eliminated |

Hawthorn leads from fourth because it beat the minor premier in Perth and now
has the week off and a home preliminary final. Fremantle — still the
best-rated side in the competition on margin — has fallen to second favourite
after one loss.

---

## Reproducing this

```r
source("R/99_run_all.R")
run_all(season = 2026)          # chunked and resumable
shiny::runApp("shiny")
```

The bake-off refits seven models before every round, so it takes several
minutes. It writes one file per round to `outputs/bakeoff/` and skips rounds
already done, so it can be interrupted and restarted without losing work.
