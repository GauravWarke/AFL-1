"""Validate the bracket engine on history, then project the 2026 finals.

Order of operations, and it matters:

  1. Calibrate and validate the ENGINE against 2015-2025 using the old
     final-eight format, where real outcomes exist.
  2. Only then swap in the 2026 Wildcard format and project.

    PYTHONPATH=src python src/run_finals.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ida_afl import load, long_form
from sportspred import bracket, ratings

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs"

DECAY = 0.80          # chosen by walk-forward in fit_ratings.py
HGA_MODEL = "venue"
N_SIMS = 50_000


def home_venue(ha: pd.DataFrame, season: int) -> dict[str, str]:
    """Each team's most-used home ground that season."""
    s = ha[ha.season == season]
    return (s.groupby("home").venue
             .agg(lambda x: x.value_counts().idxmax()).to_dict())


def ladder(ha: pd.DataFrame, season: int) -> pd.DataFrame:
    """Reconstruct the ladder: 4 points a win, 2 a draw, percentage tiebreak."""
    tl = long_form(ha[ha.season == season])
    g = tl.groupby("team").agg(
        played=("game_id", "size"),
        won=("margin", lambda m: int((m > 0).sum())),
        drawn=("margin", lambda m: int((m == 0).sum())),
        pf=("score", "sum"), pa=("conceded", "sum")).reset_index()
    g["pts"] = 4 * g.won + 2 * g.drawn
    g["percentage"] = 100 * g.pf / g.pa
    return g.sort_values(["pts", "percentage"], ascending=False) \
            .reset_index(drop=True)


STAGE_CODE = {
    "wildcard_final": "WC", "qualifying_final": "QF", "elimination_final": "EF",
    "semi_final": "SF", "preliminary_final": "PF", "grand_final": "GF",
}


def known_results(finals: pd.DataFrame, season: int) -> dict:
    """Finals already played this season, in the form the simulator wants.

    Everything already decided is treated as fact rather than re-simulated.
    Mid-series this is most of the value: after the wildcard round and one
    qualifying final, four of the nine matches are settled, and the remaining
    uncertainty is much narrower than a pre-finals projection would suggest.
    """
    out = {}
    for _, g in finals[finals.season == season].iterrows():
        code = STAGE_CODE.get(g.stage)
        if code is None or g.margin == 0:
            continue
        winner = g.home if g.margin > 0 else g.away
        out[(code, frozenset((g.home, g.away)))] = winner
    return out


def rating_uncertainty_inflation(sigma: float, drift_sd: float) -> float:
    """Widen sigma to account for not knowing the ratings exactly.

    The residual sigma from the fit is the spread of match outcomes GIVEN the
    ratings. Simulating with that alone treats the ratings as known truth and
    produces intervals that are too narrow -- the exact failure that made the
    uncorrected 80% intervals cover only 62.5%. Two ratings each carry error, and
    finals sit at the end of a season during which strength has drifted.
    """
    return float(np.sqrt(sigma ** 2 + 2 * (drift_sd / 2) ** 2))


def main() -> None:
    df = load()
    ha = df[df.stage == "home_and_away"]
    finals = df[df.stage != "home_and_away"]

    params = pd.read_csv(PROC / "model_params_2026.csv").iloc[0]
    drift_sd = float(params.drift_sd)

    # ---------------------------------------------------------------- 1
    print("=" * 74)
    print("STEP 1  Validate the engine on 2015-2025, old final-eight format")
    print("=" * 74)
    print("The 2026 format has no history. So the engine is tested on the")
    print("format that does, and only the bracket structure changes after.\n")

    rows = []
    for season in range(2016, 2026):
        train = ha[ha.season <= season]
        m = ratings.fit(train, hga_model=HGA_MODEL, decay=DECAY)
        sigma = rating_uncertainty_inflation(m["sigma"], drift_sd)

        lad = ladder(ha, season)
        if len(lad) < 8:
            continue
        venues = home_venue(ha, season)

        sim = bracket.FinalsSimulator(
            m["strengths"], sigma, m["hga"],
            lambda h, a, v, _m=m: ratings.predict_margin(_m, h, a, v, HGA_MODEL),
            rng=np.random.default_rng(1000 + season),
        )
        proj = sim.simulate(list(lad.team), venues, n_sims=10_000,
                            wildcard=False)

        probs = bracket.check_invariants(proj, wildcard=False)
        if probs:
            print(f"  {season}: INVARIANT FAILURE {probs}")

        # Who actually won?
        gf = finals[(finals.season == season) & (finals.stage == "grand_final")]
        if gf.empty:
            continue
        g = gf.iloc[0]
        actual = g.home if g.margin > 0 else g.away
        p = float(proj.loc[proj.team == actual, "p_premier"].iloc[0]) \
            if actual in set(proj.team) else np.nan
        rows.append(dict(season=season, premier=actual, p_assigned=p,
                         favourite=proj.loc[proj.p_premier.idxmax(), "team"],
                         p_favourite=proj.p_premier.max()))

    hist = pd.DataFrame(rows)
    print(f"{'season':>7}  {'actual premier':<24}{'p we gave':>10}"
          f"  {'our favourite':<24}{'p':>7}")
    print("-" * 78)
    for _, r in hist.iterrows():
        print(f"{r.season:>7}  {r.premier:<24}{r.p_assigned:>10.3f}"
              f"  {r.favourite:<24}{r.p_favourite:>7.3f}")

    # Calibration: if the model is honest, the average probability it gave to
    # the eventual premiers should be close to the rate at which its picks won.
    n = len(hist)
    exp_hits = hist.p_assigned.sum()
    act_hits = (hist.premier == hist.favourite).sum()
    print(f"\n  seasons tested            {n}")
    print(f"  favourite won              {act_hits} times")
    print(f"  sum of assigned p          {exp_hits:.2f}")
    print(f"  mean p given to the premier {hist.p_assigned.mean():.3f}")
    print(f"  mean p of our favourite     {hist.p_favourite.mean():.3f}")
    # A premiership is a four-win parlay; nobody should be near certain.
    if hist.p_assigned.mean() < 0.05:
        print("  WARNING: the model is systematically surprised by the winner")

    # ---------------------------------------------------------------- 2
    print("\n" + "=" * 74)
    print("STEP 2  Project the 2026 finals, Wildcard format")
    print("=" * 74)

    m26 = ratings.fit(ha[ha.season <= 2026], hga_model=HGA_MODEL, decay=DECAY)
    sigma26 = rating_uncertainty_inflation(m26["sigma"], drift_sd)
    print(f"match sigma {m26['sigma']:.2f} -> inflated to {sigma26:.2f} "
          f"for simulation (rating uncertainty + drift)\n")

    lad26 = ladder(ha, 2026)
    venues26 = home_venue(ha, 2026)

    known = known_results(finals, 2026)
    if known:
        print(f"conditioning on {len(known)} finals already played:")
        for (code, pair), w in sorted(known.items(), key=lambda kv: kv[0][0]):
            other = next(t for t in pair if t != w)
            print(f"    {code}  {w} def {other}")
        print()

    sim = bracket.FinalsSimulator(
        m26["strengths"], sigma26, m26["hga"],
        lambda h, a, v: ratings.predict_margin(m26, h, a, v, HGA_MODEL),
        rng=np.random.default_rng(20260904),
        known=known,
    )
    proj = sim.simulate(list(lad26.team), venues26, n_sims=N_SIMS,
                        wildcard=True)

    problems = bracket.check_invariants(proj, wildcard=True)
    print("Structural invariants:",
          "all pass" if not problems else f"FAILED -> {problems}")
    assert not problems, problems

    proj = proj.merge(lad26[["team", "pts", "percentage"]], on="team")
    proj = proj.sort_values("p_premier", ascending=False).reset_index(drop=True)

    print(f"\n{'#':>2} {'team':<24}{'rating':>8}{'finals':>8}{'prelim':>8}"
          f"{'GF':>8}{'FLAG':>8}")
    print("-" * 68)
    for _, r in proj.iterrows():
        print(f"{r.ladder_pos:>2} {r.team:<24}{r.rating:>+8.1f}"
              f"{r.p_finals:>8.2f}{r.p_prelim:>8.2f}"
              f"{r.p_grand_final:>8.2f}{r.p_premier:>8.3f}")

    OUT.mkdir(parents=True, exist_ok=True)
    proj.to_csv(OUT / "finals_projection_2026.csv", index=False)
    hist.to_csv(OUT / "engine_validation.csv", index=False)
    lad26.to_csv(PROC / "ladder_2026.csv", index=False)
    print("\nwrote outputs/finals_projection_2026.csv, "
          "outputs/engine_validation.csv, data/processed/ladder_2026.csv")


if __name__ == "__main__":
    main()
