"""Figures for the AFL finals project.

Each figure carries one finding from docs/afl-domain-notes.md. Nothing here is
decorative: if a chart does not change what a reader believes, it is not in the
set.

    PYTHONPATH=src python src/figures.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ida_afl import load, long_form
from sportspred.reliability import binomial_reliability

ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "outputs" / "figures"
OUT = ROOT / "outputs"

INK, MUTED = "#1d1d1f", "#8a8a8e"
ACCENT, WARN, GOOD = "#0b6fb0", "#c0392b", "#1e8449"
plt.rcParams.update({
    "figure.dpi": 130, "savefig.dpi": 130, "savefig.bbox": "tight",
    "font.size": 9, "axes.edgecolor": "#d0d0d4", "axes.labelcolor": INK,
    "text.color": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": "white", "axes.facecolor": "white",
})


def title(ax, head: str, sub: str = "") -> None:
    ax.set_title(head, loc="left", fontsize=11, fontweight="bold", pad=14 if sub else 8)
    if sub:
        ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=8.5,
                color=MUTED, va="bottom")


def fig_accuracy_is_luck(ha: pd.DataFrame) -> None:
    ts = ha.groupby(["season", "team"]).agg(
        goals=("goals", "sum"), shots=("shots", "sum")).reset_index()
    r = binomial_reliability(ts.goals.values, ts.shots.values)
    acc = (ts.goals / ts.shots).values

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.9),
                                 gridspec_kw={"width_ratios": [1.3, 1]})

    a1.hist(acc, bins=26, color=ACCENT, alpha=.75, edgecolor="white")
    a1.axvline(r["mean_rate"], color=INK, lw=1.4)
    a1.text(r["mean_rate"], a1.get_ylim()[1] * .96,
            f"  league {r['mean_rate']:.1%}", fontsize=8, color=INK, va="top")
    a1.set_xlabel("goal accuracy over a whole season")
    a1.set_ylabel("team-seasons")
    title(a1, "Season-long accuracy varies less than it looks",
          f"{len(acc)} team-seasons, 2015-2026")

    # The decomposition as shares of 100%. Raw variance is in squared
    # accuracy units, which nobody can read; the share is the whole point.
    luck = 1 - r["reliability"]
    skill = r["reliability"]
    a2.barh([0], [luck], color=WARN, height=.42)
    a2.barh([0], [skill], left=[luck], color=GOOD, height=.42)
    a2.text(luck / 2, 0, f"luck\n{luck:.0%}", ha="center", va="center",
            color="white", fontweight="bold", fontsize=10)
    a2.text(luck + skill / 2, 0, f"skill\n{skill:.0%}", ha="center",
            va="center", color="white", fontweight="bold", fontsize=10)
    a2.set_xlim(0, 1)
    a2.set_ylim(-.55, .55)
    a2.set_yticks([])
    a2.set_xticks([])
    for s in ("left", "bottom"):
        a2.spines[s].set_visible(False)
    a2.set_xlabel("spread in season accuracy, split into its two sources")
    title(a2, "Two-thirds of it is luck",
          f"reliability {r['reliability']:.2f} "
          f"(split-half agrees: 0.25)")
    fig.savefig(FIG / "01_accuracy_is_mostly_luck.png")
    plt.close(fig)


def fig_shots_vs_points() -> None:
    df = pd.read_csv(OUT / "shot_vs_points.csv")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.9))

    for ax, col, lab, c in [(a1, "pts_diff", "points differential", ACCENT),
                            (a2, "shot_diff", "scoring-shot differential", GOOD)]:
        r = np.corrcoef(df[col], df.future_margin)[0, 1]
        ax.scatter(df[col], df.future_margin, s=13, alpha=.45, color=c,
                   edgecolor="none")
        z = np.polyfit(df[col], df.future_margin, 1)
        xs = np.linspace(df[col].min(), df[col].max(), 50)
        ax.plot(xs, np.polyval(z, xs), color=INK, lw=1.3)
        ax.axhline(0, color="#e5e5e8", lw=.8, zorder=0)
        ax.axvline(0, color="#e5e5e8", lw=.8, zorder=0)
        ax.set_xlabel(f"{lab}, first half of season")
        ax.set_ylabel("actual margin, second half")
        title(ax, lab.capitalize(), f"r = {r:+.3f}")

    fig.suptitle("Neither predicts the future better than the other",
                 x=.005, ha="left", fontsize=12, fontweight="bold", y=1.06)
    fig.text(.005, .995, "paired bootstrap on the difference: "
                         "95% CI [-0.034, +0.019], p = 0.54",
             fontsize=8.5, color=MUTED, ha="left")
    fig.savefig(FIG / "02_shots_vs_points.png")
    plt.close(fig)


def fig_home_advantage() -> None:
    p = pd.read_csv(ROOT / "data" / "processed" / "model_params_2026.csv").iloc[0]
    base, inter, tz = p.hga_base, p.away_interstate, p.away_tz_shift

    cases = [
        ("Melbourne club hosting\nanother at the MCG", base),
        ("Adelaide hosting\na Victorian side", base + inter + 0.5 * tz),
        ("Brisbane hosting\na Victorian side", base + inter),
        ("Fremantle hosting\na Victorian side in Perth", base + inter + 2 * tz),
    ]
    labels = [c[0] for c in cases]
    vals = [c[1] for c in cases]

    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    cols = [MUTED if v < 5 else ACCENT for v in vals]
    bars = ax.barh(labels, vals, color=cols, height=.6)
    for b, v in zip(bars, vals):
        ax.text(v + .2, b.get_y() + b.get_height() / 2, f"{v:+.1f} pts",
                va="center", fontsize=9, fontweight="bold", color=INK)
    ax.set_xlabel("expected head start, points")
    ax.invert_yaxis()
    ax.set_xlim(0, max(vals) * 1.25)
    title(ax, "Home advantage is really a travel penalty",
          "a Perth home final is worth about 4.5x an MCG one between "
          "two Melbourne clubs")
    fig.savefig(FIG / "03_home_advantage.png")
    plt.close(fig)


def fig_ratings() -> None:
    r = pd.read_csv(ROOT / "data" / "processed" / "ratings_2026.csv")
    lad = pd.read_csv(ROOT / "data" / "processed" / "ladder_2026.csv")
    fin = set(lad.head(10).team)
    r = r.sort_values("rating")

    fig, ax = plt.subplots(figsize=(7.4, 6))
    cols = [ACCENT if t in fin else "#c9c9cf" for t in r.team]
    ax.barh(r.team, r.rating, color=cols, height=.68)
    for _, row in r.iterrows():
        off = .6 if row.rating >= 0 else -.6
        ax.text(row.rating + off, row.team, f"{row.rating:+.1f}",
                va="center", ha="left" if row.rating >= 0 else "right",
                fontsize=8, color=INK)
    ax.axvline(0, color=INK, lw=1)
    ax.set_xlabel("points better or worse than an average side")
    ax.set_xlim(r.rating.min() - 8, r.rating.max() + 8)
    title(ax, "Team strength going into the 2026 finals",
          "blue = made the final ten. Recency-weighted, "
          "travel-adjusted ridge ratings")
    fig.savefig(FIG / "04_ratings.png")
    plt.close(fig)


def fig_premiership_odds() -> None:
    p = pd.read_csv(OUT / "finals_projection_2026.csv")
    p = p[p.p_premier > 0].sort_values("p_premier")

    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    ax.barh(p.team, p.p_premier, color=ACCENT, height=.62)
    for _, r in p.iterrows():
        ax.text(r.p_premier + .006, r.team,
                f"{r.p_premier:.0%}", va="center", fontsize=9,
                fontweight="bold", color=INK)
    ax.set_xlabel("chance of winning the premiership")
    ax.set_xlim(0, p.p_premier.max() * 1.25)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    title(ax, "Premiership chances, conditioned on finals already played",
          "Hawthorn leads despite finishing 4th - it beat Fremantle in "
          "Perth and now has a week off")
    fig.savefig(FIG / "05_premiership_odds.png")
    plt.close(fig)


def fig_calibration() -> None:
    t = pd.read_csv(OUT / "calibration_table.csv")
    fig, ax = plt.subplots(figsize=(5.4, 4.8))
    ax.plot([0, .45], [0, .45], color=MUTED, lw=1, ls="--", zorder=0)
    ax.scatter(t.predicted, t.actual, s=t.n * 9, color=ACCENT, alpha=.75,
               edgecolor="white", zorder=3)
    for _, r in t.iterrows():
        ax.annotate(f"n={int(r.n)}", (r.predicted, r.actual),
                    textcoords="offset points", xytext=(9, -3),
                    fontsize=7.5, color=MUTED)
    ax.set_xlabel("probability the model gave")
    ax.set_ylabel("share that actually won")
    ax.set_xlim(0, .45)
    ax.set_ylim(0, .45)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    title(ax, "Calibration, 2016-2025",
          "on the dashed line = honest. 80 team-seasons, only 10 winners,\n"
          "so every point is noisy")
    fig.savefig(FIG / "06_calibration.png")
    plt.close(fig)


def fig_lottery() -> None:
    """The headline: the finals are close to a coin-toss tournament."""
    p = pd.read_csv(OUT / "finals_projection_2026.csv")
    live = p[p.p_premier > 0].sort_values("p_premier", ascending=False)

    fig, ax = plt.subplots(figsize=(8.2, 3.4))
    left = 0.0
    palette = ["#0b6fb0", "#2e8bc9", "#63a9d8", "#93c5e5", "#b9d9ee",
               "#d4e7f4", "#e6f0f9", "#f2f7fc"]
    for i, (_, r) in enumerate(live.iterrows()):
        ax.barh([0], [r.p_premier], left=left, height=.5,
                color=palette[i % len(palette)], edgecolor="white", lw=1.2)
        if r.p_premier > .05:
            ax.text(left + r.p_premier / 2, 0, r.team.replace(" ", "\n"),
                    ha="center", va="center", fontsize=7.6,
                    color="white" if i < 3 else INK, fontweight="bold")
        left += r.p_premier
    ax.set_xlim(0, 1)
    ax.set_ylim(-.5, .5)
    ax.set_yticks([])
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_xlabel("share of Septembers this team wins")
    for s in ("left", "bottom"):
        ax.spines[s].set_visible(False)
    title(ax, "No side wins even one September in three",
          "the model beats a blind 1-in-8 guess by a Brier skill score of "
          "just +0.016 - the finals really are that open")
    fig.savefig(FIG / "07_open_race.png")
    plt.close(fig)


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    ha = long_form(load()).query("stage == 'home_and_away'")

    fig_accuracy_is_luck(ha)
    fig_shots_vs_points()
    fig_home_advantage()
    fig_ratings()
    fig_premiership_odds()
    fig_calibration()
    fig_lottery()

    made = sorted(FIG.glob("*.png"))
    print(f"wrote {len(made)} figures to outputs/figures/")
    for f in made:
        print(f"  {f.name:<36}{f.stat().st_size / 1024:>7.0f} KB")


if __name__ == "__main__":
    main()
