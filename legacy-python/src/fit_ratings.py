"""Fit team ratings, test whether venue-aware home advantage earns its keep.

    PYTHONPATH=src python src/fit_ratings.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ida_afl import load
from sportspred import ratings

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"
PROC = ROOT / "data" / "processed"


def walk_forward(df: pd.DataFrame, hga_model: str, decay: float,
                 first_test: int = 2018, rolling: bool = True) -> dict:
    """Honest test: fit on everything before round R, predict round R.

    Refitting each ROUND rather than each season matters here. A season-level
    walk-forward asks "how good was this team last year", which is not the
    question a finals predictor faces -- by September we have 23 rounds of
    current-season evidence and it would be perverse to ignore it. Rolling
    within the season also means the recency decay is being tuned for the job
    it will actually do.

    No information from the match being predicted ever reaches the model.
    """
    err, hits, total = [], 0.0, 0
    ha = df[df.stage == "home_and_away"]
    for season in sorted(ha.season.unique()):
        if season < first_test:
            continue
        rounds = sorted(ha[ha.season == season]["round"].unique())
        for rnd in rounds:
            test = ha[(ha.season == season) & (ha["round"] == rnd)]
            train = ha[(ha.season < season)
                       | ((ha.season == season) & (ha["round"] < rnd))]
            if len(train) < 300 or test.empty:
                continue
            if not rolling:
                train = ha[ha.season < season]
            m = ratings.fit(train, hga_model=hga_model, decay=decay)
            for _, g in test.iterrows():
                pred = ratings.predict_margin(m, g.home, g.away, g.venue,
                                              hga_model)
                err.append(pred - g.margin)
                # Tipping: did we pick the winner? Draws score a half, which
                # is the convention Squiggle's public leaderboard uses.
                if g.margin == 0:
                    hits += 0.5
                elif np.sign(pred) == np.sign(g.margin):
                    hits += 1
                total += 1

    e = np.array(err)
    return dict(
        n=total,
        mae=float(np.abs(e).mean()),
        rmse=float(np.sqrt((e ** 2).mean())),
        bias=float(e.mean()),
        tip=hits / total if total else float("nan"),
    )


def main() -> None:
    df = load()
    ha = df[df.stage == "home_and_away"]

    print("=" * 72)
    print("Does venue-aware home advantage beat a single league-wide number?")
    print("=" * 72)
    print("Walk-forward: fit on all prior seasons, predict the next one.\n")
    print(f"{'HGA model':<10}{'decay':>7}{'MAE':>9}{'RMSE':>9}"
          f"{'bias':>9}{'tip %':>9}")
    print("-" * 60)
    best = None
    # The grid runs to 0.8 deliberately. An earlier version stopped at 0.30 and
    # picked 0.30 -- but an optimum sitting on the edge of a grid is not an
    # optimum, it is a signal that the grid is too small.
    grid = (0.0, 0.15, 0.30, 0.45, 0.60, 0.70, 0.80)
    for hga_model in ("scalar", "venue"):
        for decay in grid:
            r = walk_forward(df, hga_model, decay)
            print(f"{hga_model:<10}{decay:>7.2f}{r['mae']:>9.3f}"
                  f"{r['rmse']:>9.3f}{r['bias']:>+9.3f}{100 * r['tip']:>9.2f}")
            if best is None or r["mae"] < best[0]:
                best = (r["mae"], hga_model, decay)

    _, hga_model, decay = best
    print(f"\nbest by MAE: hga={hga_model}, decay={decay}")
    if decay in (grid[0], grid[-1]):
        print("  WARNING: optimum is on the edge of the search grid.")

    # ---- final model on everything up to and including the 2026 season ----
    print("\n" + "=" * 72)
    print("Home advantage, estimated (points)")
    print("=" * 72)
    full = ratings.fit(ha, hga_model="venue", decay=decay)
    for k, v in full["hga"].items():
        print(f"  {k:<20}{v:+7.2f}")
    print(f"\n  sigma (match noise)  {full['sigma']:.2f} points")
    print(f"  lambda (ridge)       {full['lam']:.2f}")

    hb = full["hga"]["hga_base"]
    ai = full["hga"]["away_interstate"]
    tz = full["hga"]["away_tz_shift"]
    print("\n  Worked example -- what the venue model is actually saying:")
    print(f"    Vic side hosting a Vic side at the MCG:   "
          f"{hb:+.2f} pts")
    print(f"    Fremantle hosting a Vic side in Perth:    "
          f"{hb + ai + 2 * tz:+.2f} pts")
    print(f"    difference:                               "
          f"{ai + 2 * tz:+.2f} pts")

    print("\n" + "=" * 72)
    print("Season-to-season drift in true strength")
    print("=" * 72)
    d = ratings.estimate_drift(df)
    print(f"  team-season pairs      {d['n_pairs']}")
    print(f"  observed change   (sd) {d['observed_sd']:.2f}")
    print(f"  estimation error  (sd) {d['estimation_sd']:.2f}")
    print(f"  TRUE DRIFT        (sd) {d['drift_sd']:.2f} points")

    # ---- 2026 ratings going into the finals -----------------------------
    cur = ha[ha.season <= 2026]
    m26 = ratings.fit(cur, hga_model="venue", decay=decay)
    s = m26["strengths"].rename("rating").reset_index()
    s.columns = ["team", "rating"]
    s["rank"] = range(1, len(s) + 1)

    OUT.mkdir(parents=True, exist_ok=True)
    PROC.mkdir(parents=True, exist_ok=True)
    s.to_csv(PROC / "ratings_2026.csv", index=False)
    pd.DataFrame([dict(sigma=m26["sigma"], lam=m26["lam"], decay=decay,
                       hga_model="venue", drift_sd=d["drift_sd"],
                       **m26["hga"])]).to_csv(
        PROC / "model_params_2026.csv", index=False)

    print("\n" + "=" * 72)
    print("Ratings going into the 2026 finals (points vs an average team)")
    print("=" * 72)
    for _, r in s.iterrows():
        bar = "#" * int(round(abs(r.rating)))
        side = " " * 22 if r.rating < 0 else ""
        print(f"  {r['rank']:>2}. {r.team:<24}{r.rating:+7.2f}  {bar}")

    print("\nwrote data/processed/ratings_2026.csv, model_params_2026.csv")


if __name__ == "__main__":
    main()
