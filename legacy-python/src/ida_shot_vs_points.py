"""Does rating teams on scoring shots beat rating them on points?

The received wisdom, imported from soccer's expected-goals literature, says yes:
conversion is noisy, so strip it out and rate teams on chances created. The
first pass of ida_afl.py found the opposite, but by a margin (r = .710 vs .702)
far too small to call from a point estimate. This script settles it.

Three things are done that the first pass did not:

  1. A PAIRED bootstrap over team-seasons. The two correlations are computed on
     the same rows, so they are dependent; comparing them needs the sampling
     distribution of the DIFFERENCE, not two separate confidence intervals.

  2. A third candidate -- expected margin -- which is the actual soccer-style
     construction and the one the folklore really refers to: value each team's
     shots at the LEAGUE-AVERAGE conversion rate, so shot volume is kept and
     the team's own accuracy is discarded as noise.

  3. A shrunk version, which keeps a fraction of the team's own accuracy equal
     to the reliability measured in ida_afl.py, rather than discarding it
     entirely. If accuracy is 32% skill, throwing away 100% of it is an
     overcorrection.

    PYTHONPATH=src python src/ida_shot_vs_points.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ida_afl import load, long_form
from sportspred.reliability import binomial_reliability

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"
RNG = np.random.default_rng(20260904)
GOAL = 6


def build(ha: pd.DataFrame, reliability: float, league_acc: float) -> pd.DataFrame:
    rows = []
    for (season, team), g in ha.groupby(["season", "team"]):
        g = g.sort_values("date")
        k = len(g) // 2
        if k < 5:
            continue
        f, s = g.iloc[:k], g.iloc[k:]

        # Team's own conversion over the first half, shrunk toward the league
        # mean by its measured reliability. reliability=0 gives the league
        # rate for everyone; reliability=1 gives the team's raw rate.
        own_acc = f.goals.sum() / f.shots.sum()
        shrunk = league_acc + reliability * (own_acc - league_acc)
        opp_acc_own = f.goals.sum() / f.shots.sum()  # placeholder, unused

        sf, sa = f.shots.mean(), f.opp_shots.mean()
        rows.append(dict(
            season=season, team=team,
            # (a) plain points differential
            pts_diff=(f.score - f.conceded).mean(),
            # (b) plain scoring-shot differential, in shots
            shot_diff=sf - sa,
            # (c) expected margin: both teams' shots at league conversion,
            #     converted to points. Own accuracy discarded entirely.
            xmargin=(sf - sa) * (league_acc * GOAL + (1 - league_acc)),
            # (d) shrunk: own shots at own partially-trusted accuracy,
            #     shots conceded at league conversion.
            xmargin_shrunk=(sf * (shrunk * GOAL + (1 - shrunk))
                            - sa * (league_acc * GOAL + (1 - league_acc))),
            future_margin=s.margin.mean(),
        ))
    return pd.DataFrame(rows)


def paired_bootstrap(df: pd.DataFrame, a: str, b: str, n: int = 10000) -> dict:
    """Sampling distribution of corr(a, y) - corr(b, y), resampling rows."""
    y = df.future_margin.values
    xa, xb = df[a].values, df[b].values
    obs = np.corrcoef(xa, y)[0, 1] - np.corrcoef(xb, y)[0, 1]
    idx = RNG.integers(0, len(df), size=(n, len(df)))
    diffs = np.empty(n)
    for i, ix in enumerate(idx):
        diffs[i] = (np.corrcoef(xa[ix], y[ix])[0, 1]
                    - np.corrcoef(xb[ix], y[ix])[0, 1])
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return dict(observed=obs, lo=lo, hi=hi,
                p_two_sided=2 * min((diffs <= 0).mean(), (diffs >= 0).mean()))


def main() -> None:
    ha = long_form(load()).query("stage == 'home_and_away'")

    ts = ha.groupby(["season", "team"]).agg(
        goals=("goals", "sum"), shots=("shots", "sum")).reset_index()
    rel = binomial_reliability(ts.goals.values, ts.shots.values)
    reliability, league_acc = rel["reliability"], rel["mean_rate"]
    print(f"accuracy reliability {reliability:.3f}, "
          f"league conversion {league_acc:.4f}\n")

    df = build(ha, reliability, league_acc)
    print(f"team-seasons: {len(df)}   "
          f"(rate first half of a season, score the second half)\n")

    print(f"{'predictor':<24}{'r':>8}{'r2':>8}")
    print("-" * 40)
    cands = ["pts_diff", "shot_diff", "xmargin", "xmargin_shrunk"]
    for c in cands:
        r = np.corrcoef(df[c], df.future_margin)[0, 1]
        print(f"{c:<24}{r:>+8.3f}{r ** 2:>8.3f}")

    print("\nPaired bootstrap against points differential")
    print("(positive difference = the challenger is better)")
    print(f"{'challenger':<20}{'diff in r':>11}{'95% CI':>20}{'p':>8}")
    print("-" * 60)
    for c in cands[1:]:
        b = paired_bootstrap(df, c, "pts_diff")
        ci = f"[{b['lo']:+.3f}, {b['hi']:+.3f}]"
        print(f"{c:<20}{b['observed']:>+11.3f}{ci:>20}{b['p_two_sided']:>8.3f}")

    # Note on units: shot_diff is measured in shots and the others in points,
    # so their correlations are comparable but their regression coefficients
    # are not. Correlation is scale-free, which is why it is used here.
    df.to_csv(OUT / "shot_vs_points.csv", index=False)
    print("\nwrote outputs/shot_vs_points.csv")


if __name__ == "__main__":
    main()
