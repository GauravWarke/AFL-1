"""Is the finals engine calibrated, or just confident?

Step 1 of run_finals.py raised a flag: across 2016-2025 the model's favourite
won the premiership once, when the sum of the probabilities it gave those
favourites was 3.24. That is either bad luck or overconfidence, and the
difference matters -- an overconfident model understates how open a finals
series is, which is exactly the thing a finals dashboard exists to convey.

Three tests, because any one of them alone is weak on ten seasons:

  1. Poisson-binomial test on the favourite. Each season is an independent
     Bernoulli with its own probability, so the count of favourite wins has a
     known distribution and an exact p-value is available. No normal
     approximation on n=10.

  2. Reliability across all 80 team-seasons, not just the ten favourites.
     Bucket by predicted probability and compare to the realised rate. This
     uses eight times as much information.

  3. Brier score against two baselines a model must beat to be worth having:
     a uniform 1-in-8, and the historical base rate by ladder position.

    PYTHONPATH=src python src/validate_engine.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ida_afl import load, long_form
from run_finals import DECAY, HGA_MODEL, home_venue, ladder, \
    rating_uncertainty_inflation
from sportspred import bracket, ratings

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"


def poisson_binomial_pmf(ps: np.ndarray) -> np.ndarray:
    """Exact distribution of the number of successes for independent,
    non-identical Bernoulli trials. Built by convolution."""
    dist = np.array([1.0])
    for p in ps:
        dist = np.convolve(dist, [1 - p, p])
    return dist


def collect(df: pd.DataFrame) -> pd.DataFrame:
    """Per team-season: predicted premiership probability, and what happened."""
    ha = df[df.stage == "home_and_away"]
    finals = df[df.stage != "home_and_away"]
    drift_sd = float(pd.read_csv(ROOT / "data" / "processed" /
                                 "model_params_2026.csv").iloc[0].drift_sd)
    rows = []
    for season in range(2016, 2026):
        m = ratings.fit(ha[ha.season <= season], hga_model=HGA_MODEL,
                        decay=DECAY)
        sigma = rating_uncertainty_inflation(m["sigma"], drift_sd)
        lad = ladder(ha, season)
        gf = finals[(finals.season == season) &
                    (finals.stage == "grand_final")]
        if gf.empty or len(lad) < 8:
            continue
        g = gf.iloc[0]
        premier = g.home if g.margin > 0 else g.away

        sim = bracket.FinalsSimulator(
            m["strengths"], sigma, m["hga"],
            lambda h, a, v, _m=m: ratings.predict_margin(_m, h, a, v,
                                                         HGA_MODEL),
            rng=np.random.default_rng(5000 + season))
        proj = sim.simulate(list(lad.team), home_venue(ha, season),
                            n_sims=20_000, wildcard=False)
        proj["season"] = season
        proj["won"] = (proj.team == premier).astype(int)
        rows.append(proj)
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    df = load()
    d = collect(df)
    d.to_csv(OUT / "calibration_raw.csv", index=False)

    # ------------------------------------------------------------ test 1
    print("=" * 72)
    print("1. Did the favourite win as often as claimed?")
    print("=" * 72)
    fav = d.loc[d.groupby("season").p_premier.idxmax()]
    ps = fav.p_premier.to_numpy()
    wins = int(fav.won.sum())
    pmf = poisson_binomial_pmf(ps)
    exp = ps.sum()
    sd = np.sqrt((ps * (1 - ps)).sum())
    p_le = pmf[: wins + 1].sum()

    print(f"  seasons                {len(ps)}")
    print(f"  favourite won          {wins}")
    print(f"  expected               {exp:.2f}  (sd {sd:.2f})")
    print(f"  P(<= {wins} | model true)  {p_le:.3f}")
    verdict = ("consistent with the model" if p_le > 0.05
               else "the model looks overconfident")
    print(f"  -> {verdict}")

    # ------------------------------------------------------------ test 2
    print("\n" + "=" * 72)
    print("2. Reliability across all 80 team-seasons")
    print("=" * 72)
    bins = [0, .02, .05, .10, .20, .35, 1.0]
    d["bucket"] = pd.cut(d.p_premier, bins, include_lowest=True)
    tab = d.groupby("bucket", observed=True).agg(
        n=("won", "size"), predicted=("p_premier", "mean"),
        actual=("won", "mean"), wins=("won", "sum")).reset_index()
    print(f"{'predicted band':<18}{'n':>5}{'mean pred':>11}"
          f"{'actual':>9}{'wins':>7}")
    print("-" * 52)
    for _, r in tab.iterrows():
        print(f"{str(r.bucket):<18}{r.n:>5}{r.predicted:>11.3f}"
              f"{r.actual:>9.3f}{int(r.wins):>7}")
    # Overall: predicted total must equal 1 per season by construction, so
    # the informative comparison is band by band, not in aggregate.

    # ------------------------------------------------------------ test 3
    print("\n" + "=" * 72)
    print("3. Brier score vs baselines  (lower is better)")
    print("=" * 72)
    y = d.won.to_numpy(dtype=float)
    model = float(np.mean((d.p_premier - y) ** 2))
    uniform = float(np.mean((np.full(len(d), 1 / 8) - y) ** 2))
    # Base rate by ladder position, leave-one-season-out so a season never
    # informs its own baseline.
    base = np.empty(len(d))
    for i, (s, pos) in enumerate(zip(d.season, d.ladder_pos)):
        other = d[(d.season != s) & (d.ladder_pos == pos)]
        base[i] = other.won.mean() if len(other) else 1 / 8
    base_rate = float(np.mean((base - y) ** 2))

    print(f"  our model                {model:.5f}")
    print(f"  uniform 1-in-8           {uniform:.5f}")
    print(f"  ladder-position base     {base_rate:.5f}")
    skill_u = 1 - model / uniform
    skill_b = 1 - model / base_rate
    print(f"\n  skill score vs uniform   {skill_u:+.3f}")
    print(f"  skill score vs base rate {skill_b:+.3f}")
    print("\n  (A positive skill score means the model beats that baseline.")
    print("   Beating the ladder-position base rate is the harder test: it")
    print("   says the ratings add something the ladder alone does not.)")

    tab.to_csv(OUT / "calibration_table.csv", index=False)
    print("\nwrote outputs/calibration_raw.csv, outputs/calibration_table.csv")


if __name__ == "__main__":
    main()
