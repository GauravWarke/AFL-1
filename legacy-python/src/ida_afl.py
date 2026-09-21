"""Initial data analysis, and the one question that shapes the whole model.

Run this before trusting anything downstream. It answers, from data rather than
from folklore:

  1. Is the match table internally consistent?
  2. Is goal accuracy a repeatable team skill, or is it noise?
  3. Does scoring-shot differential predict future results better than points
     differential does?

Question 3 is the one that matters. If the answer is yes, then the AFL ladder --
which is built on points -- is a partly-noisy ranking, and a model that rates
teams on scoring shots should beat one that rates them on score.

    PYTHONPATH=src python src/ida_afl.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from sportspred.reliability import binomial_reliability, split_half_reliability

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs"


def load() -> pd.DataFrame:
    df = pd.read_csv(PROC / "matches.csv", parse_dates=["date"])
    return df


def long_form(df: pd.DataFrame) -> pd.DataFrame:
    """One row per team per match."""
    h = df.assign(
        team=df.home, opp=df.away, at_home=True,
        goals=df.home_goals, behinds=df.home_behinds, shots=df.home_shots,
        score=df.home_score, conceded=df.away_score,
        opp_shots=df.away_shots, margin=df.margin,
    )
    a = df.assign(
        team=df.away, opp=df.home, at_home=False,
        goals=df.away_goals, behinds=df.away_behinds, shots=df.away_shots,
        score=df.away_score, conceded=df.home_score,
        opp_shots=df.home_shots, margin=-df.margin,
    )
    cols = ["game_id", "season", "round", "stage", "date", "venue", "team",
            "opp", "at_home", "goals", "behinds", "shots", "score",
            "conceded", "opp_shots", "margin"]
    return pd.concat([h[cols], a[cols]], ignore_index=True)


def section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def main() -> None:
    df = load()
    tl = long_form(df)
    ha = tl[tl.stage == "home_and_away"]

    # ------------------------------------------------------------------ 1
    section("1. Integrity")
    print(f"matches                 {len(df)}")
    print(f"seasons                 {df.season.min()}-{df.season.max()}")
    print(f"draws                   {df.is_draw.sum()} "
          f"({100 * df.is_draw.mean():.2f}% of matches)")
    print(f"missing cells           {int(df.isna().sum().sum())}")
    dupes = df.game_id.duplicated().sum()
    print(f"duplicate game_ids      {dupes}")
    assert dupes == 0, "duplicate matches would double-count teams"

    # Every home-and-away season should give each team the same schedule
    # length. Where it does not, say so rather than silently averaging over it.
    gp = (ha.groupby(["season", "team"]).size()
            .groupby("season").agg(["min", "max"]))
    odd = gp[gp["min"] != gp["max"]]
    print(f"seasons w/ uneven games {len(odd)}"
          + (f"  -> {list(odd.index)}" if len(odd) else ""))

    # ------------------------------------------------------------------ 2
    section("2. Is goal accuracy a skill?")
    ts = (ha.groupby(["season", "team"])
            .agg(goals=("goals", "sum"), shots=("shots", "sum"),
                 score=("score", "sum"), conceded=("conceded", "sum"),
                 opp_shots=("opp_shots", "sum"), games=("game_id", "size"))
            .reset_index())
    ts["accuracy"] = ts.goals / ts.shots

    acc = binomial_reliability(ts.goals.values, ts.shots.values)
    print("Accuracy (goals / scoring shots), by team-season")
    print(f"  team-seasons          {acc['n_units']}")
    print(f"  league mean accuracy  {acc['mean_rate']:.4f}")
    print(f"  observed spread (sd)  {acc['observed_sd']:.4f}")
    print(f"  binomial noise  (sd)  {acc['noise_sd']:.4f}")
    print(f"  implied skill   (sd)  {acc['skill_sd']:.4f}")
    print(f"  RELIABILITY           {acc['reliability']:.3f}")

    # Compare against a metric that should be strongly skill-driven, as a
    # control. If shot generation also came out near zero, the method would be
    # broken rather than the metric being noisy.
    ha_ = ha.copy()
    ha_["one"] = 1.0
    sh = split_half_reliability(ha_, unit="team_season", order="date",
                                value="shots", weight="one") \
        if "team_season" in ha_ else None
    ha_["team_season"] = ha_.season.astype(str) + "-" + ha_.team
    print("\nSplit-half (odd vs even games within a team-season), "
          "Spearman-Brown corrected")
    for label, val, wt in [
        ("goal accuracy", "goals", "shots"),
        ("scoring shots per game", "shots", "one"),
        ("scoring shots conceded", "opp_shots", "one"),
    ]:
        r = split_half_reliability(ha_, "team_season", "date", val, wt)
        print(f"  {label:<24} r={r['half_r']:+.3f}  "
              f"reliability={r['spearman_brown']:.3f}  (n={r['n_units']})")

    # ------------------------------------------------------------------ 3
    section("3. Which differential predicts the future better?")
    # Honest design: rate each team on the FIRST half of a season, then score
    # how well that rating predicts their margins in the SECOND half. No
    # overlap, so no leakage, and it is the question a club actually faces --
    # what we know now versus what happens next.
    rows = []
    for (season, team), g in ha.groupby(["season", "team"]):
        g = g.sort_values("date")
        k = len(g) // 2
        if k < 5:
            continue
        first, second = g.iloc[:k], g.iloc[k:]
        rows.append(dict(
            season=season, team=team,
            pts_diff=(first.score - first.conceded).mean(),
            shot_diff=(first.shots - first.opp_shots).mean(),
            future_margin=second.margin.mean(),
        ))
    pred = pd.DataFrame(rows)

    print(f"team-seasons used       {len(pred)}")
    for name, col in [("points differential  ", "pts_diff"),
                      ("scoring-shot diff    ", "shot_diff")]:
        r = np.corrcoef(pred[col], pred.future_margin)[0, 1]
        print(f"  {name} vs future margin: r = {r:+.3f}   r2 = {r ** 2:.3f}")

    # Both at once: if shot differential carries information that points
    # differential does not, its coefficient survives when both are included.
    X = np.column_stack([np.ones(len(pred)), pred.pts_diff, pred.shot_diff])
    y = pred.future_margin.values
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = len(y) - X.shape[1]
    se = np.sqrt(np.diag(np.linalg.pinv(X.T @ X)) * (resid @ resid) / dof)
    print("\n  Both predictors together (future margin per game):")
    for nm, b, s in zip(["intercept", "pts_diff ", "shot_diff"], beta, se):
        star = "  <- significant" if abs(b / s) > 2 else ""
        print(f"    {nm}  {b:+7.3f}  (se {s:.3f}, t {b / s:+.2f}){star}")

    OUT.mkdir(parents=True, exist_ok=True)
    ts.to_csv(OUT / "team_season_summary.csv", index=False)
    pred.to_csv(OUT / "predictive_check.csv", index=False)
    print(f"\nwrote outputs/team_season_summary.csv, outputs/predictive_check.csv")


if __name__ == "__main__":
    main()
