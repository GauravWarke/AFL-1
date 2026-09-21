"""Finals simulation for the AFL, including the 2026 Wildcard format.

The validation problem
----------------------
The 2026 finals format is new -- the first change to the AFL finals system
since 2000 -- so there is no history of it to backtest against. Simply
asserting that the simulator is correct because it runs would be worthless.

The way out is to separate the two things being tested:

  * the ENGINE (rate teams, turn a rating gap into a win probability,
    walk a bracket, aggregate) -- this is format-independent, and can be
    validated against 2015-2025 using the OLD final-eight format, where 11
    seasons of real outcomes exist.

  * the FORMAT (who plays whom, who hosts, who advances) -- this cannot be
    validated against history, so it is instead encoded declaratively and
    checked against structural invariants: exactly one premier, every path
    reachable, probabilities summing to the field size.

Validate the engine on the old format, then swap the format in. That is the
only honest order of operations.

The AFL final-eight system
--------------------------
Week 1: QF1 1v4, QF2 2v3, EF1 5v8, EF2 6v7.
        Qualifying winners go straight to the preliminary finals (a week off).
        Qualifying losers drop to the semi-finals.
        Elimination losers are out.
Week 2: SF1 = QF1 loser v EF2 winner, SF2 = QF2 loser v EF1 winner.
Week 3: PF1 = QF1 winner v (a semi-final winner), PF2 = QF2 winner v the other.
Week 4: Grand Final, at the MCG.

2026 adds a week in front:
Week 0: WC1 7v10, WC2 8v9. Winners take seeds 7 and 8, ordered by their
        original ladder position. Losers are out. Seeds 1-6 skip this week.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MCG = "M.C.G."


def win_probability(margin: float, sigma: float) -> float:
    """P(home wins) from an expected margin.

    A normal CDF on the expected margin. sigma is the residual match-level
    standard deviation from the ratings fit, inflated by the caller to account
    for uncertainty in the ratings themselves -- otherwise the simulator is
    overconfident, which is the single most common way a bracket simulator
    goes wrong.
    """
    from math import erf, sqrt
    return 0.5 * (1.0 + erf(margin / (sigma * sqrt(2.0))))


class FinalsSimulator:
    """Monte Carlo over a finals bracket."""

    def __init__(self, ratings: pd.Series, sigma: float, hga: dict,
                 predict_fn, rng: np.random.Generator | None = None,
                 known: dict | None = None):
        self.ratings = ratings
        self.sigma = sigma
        self.hga = hga
        self.predict = predict_fn
        self.rng = rng or np.random.default_rng(20260904)
        # (stage, frozenset({team_a, team_b})) -> winner, for finals already
        # played. Keyed by stage as well as pair because two sides can meet
        # twice in one series -- a qualifying final and then the grand final.
        self.known = known or {}

    def _p_home(self, home: str, away: str, venue: str) -> float:
        return win_probability(self.predict(home, away, venue), self.sigma)

    def _play(self, home: str, away: str, venue: str,
              stage: str = "") -> tuple[str, str]:
        """Returns (winner, loser). Finals cannot be drawn -- extra time.

        If this exact fixture has already been played in real life, the real
        result is used instead of a coin from the model. This is what makes
        the projection a LIVE one: mid-series, some of the bracket is fact and
        only the remainder is uncertain, and a simulator that re-rolls settled
        matches is answering a question nobody asked.
        """
        key = (stage, frozenset((home, away)))
        if key in self.known:
            w = self.known[key]
            return (w, away if w == home else home)
        p = self._p_home(home, away, venue)
        return (home, away) if self.rng.random() < p else (away, home)

    # -- formats ---------------------------------------------------------
    def _final_eight(self, seeds: dict[int, str], venues: dict[str, str],
                     record: dict) -> str:
        """seeds: 1..8 -> team. Returns the premier."""
        v = lambda t: venues.get(t, MCG)  # noqa: E731  higher seed hosts

        qf1_w, qf1_l = self._play(seeds[1], seeds[4], v(seeds[1]), "QF")
        qf2_w, qf2_l = self._play(seeds[2], seeds[3], v(seeds[2]), "QF")
        ef1_w, ef1_l = self._play(seeds[5], seeds[8], v(seeds[5]), "EF")
        ef2_w, ef2_l = self._play(seeds[6], seeds[7], v(seeds[6]), "EF")

        for t in (qf1_w, qf2_w, qf1_l, qf2_l, ef1_w, ef2_w):
            record["week2"].add(t)
        # Qualifying winners get the week off and a home preliminary final.
        for t in (qf1_w, qf2_w):
            record["bye"].add(t)

        # Semi-finals: the qualifying loser hosts.
        sf1_w, _ = self._play(qf1_l, ef2_w, v(qf1_l), "SF")
        sf2_w, _ = self._play(qf2_l, ef1_w, v(qf2_l), "SF")
        for t in (sf1_w, sf2_w, qf1_w, qf2_w):
            record["prelim"].add(t)

        # Preliminary finals: qualifying winners host. Pairing keeps the two
        # qualifying winners apart, so QF1's winner meets the semi-final
        # winner from the other side of the draw.
        pf1_w, _ = self._play(qf1_w, sf2_w, v(qf1_w), "PF")
        pf2_w, _ = self._play(qf2_w, sf1_w, v(qf2_w), "PF")
        for t in (pf1_w, pf2_w):
            record["grand_final"].add(t)

        # The Grand Final is at the MCG regardless of who is in it.
        premier, _ = self._play(pf1_w, pf2_w, MCG, "GF")
        return premier

    def simulate(self, ladder: list[str], venues: dict[str, str],
                 n_sims: int = 50_000, wildcard: bool = True) -> pd.DataFrame:
        """ladder: teams in finishing order, 1st first.

        wildcard=True  -> 2026 format, needs the top 10.
        wildcard=False -> pre-2026 format, needs the top 8.
        """
        need = 10 if wildcard else 8
        if len(ladder) < need:
            raise ValueError(f"need at least {need} teams, got {len(ladder)}")
        field = ladder[:need]

        counts = {t: dict(finals=0, week2=0, bye=0, prelim=0,
                          grand_final=0, premier=0) for t in field}

        for _ in range(n_sims):
            rec = {k: set() for k in ("week2", "bye", "prelim", "grand_final")}

            if wildcard:
                # 7 hosts 10, 8 hosts 9. Winners take seeds 7 and 8, ordered
                # by original ladder position -- confirmed against the 2026
                # draw, where 8th (Western Bulldogs) was seeded above 10th
                # (Carlton) after both won their wildcard finals.
                w1, _ = self._play(field[6], field[9], venues.get(field[6], MCG), "WC")
                w2, _ = self._play(field[7], field[8], venues.get(field[7], MCG), "WC")
                survivors = sorted([w1, w2], key=field.index)
                eight = field[:6] + survivors
                for t in eight:
                    counts[t]["finals"] += 1
            else:
                eight = field[:8]
                for t in eight:
                    counts[t]["finals"] += 1

            seeds = {i + 1: t for i, t in enumerate(eight)}
            premier = self._final_eight(seeds, venues, rec)

            for stage, teams in rec.items():
                for t in teams:
                    counts[t][stage] += 1
            counts[premier]["premier"] += 1

        rows = []
        for i, t in enumerate(field):
            c = counts[t]
            rows.append(dict(
                ladder_pos=i + 1, team=t,
                p_finals=c["finals"] / n_sims,
                p_week2=c["week2"] / n_sims,
                p_bye=c["bye"] / n_sims,
                p_prelim=c["prelim"] / n_sims,
                p_grand_final=c["grand_final"] / n_sims,
                p_premier=c["premier"] / n_sims,
                rating=float(self.ratings.get(t, 0.0)),
            ))
        return pd.DataFrame(rows)


def check_invariants(df: pd.DataFrame, wildcard: bool) -> list[str]:
    """Structural checks that hold for ANY correct bracket.

    These are what stand in for a backtest of the 2026 format. Each is a
    statement about the tournament graph, not about football.
    """
    problems = []
    tol = 0.02

    if abs(df.p_premier.sum() - 1.0) > 1e-9:
        problems.append(f"premiers sum to {df.p_premier.sum():.4f}, not 1")

    if abs(df.p_grand_final.sum() - 2.0) > tol:
        problems.append(
            f"grand finalists sum to {df.p_grand_final.sum():.3f}, not 2")

    if abs(df.p_prelim.sum() - 4.0) > tol:
        problems.append(f"preliminary finalists sum to "
                        f"{df.p_prelim.sum():.3f}, not 4")

    # Exactly two teams get the week-one bye (the qualifying-final winners).
    if abs(df.p_bye.sum() - 2.0) > tol:
        problems.append(f"byes sum to {df.p_bye.sum():.3f}, not 2")

    expect_finals = 8.0
    if abs(df.p_finals.sum() - expect_finals) > tol:
        problems.append(f"final-eight places sum to "
                        f"{df.p_finals.sum():.3f}, not {expect_finals}")

    # Monotonicity is NOT asserted. A lower-seeded team can legitimately have
    # a higher premiership probability than a higher-seeded one if it is the
    # better side; asserting otherwise would bake the ladder into the model.
    # But nobody can win without reaching the grand final.
    bad = df[df.p_premier > df.p_grand_final + 1e-9]
    if len(bad):
        problems.append(f"{len(bad)} teams win more often than they "
                        f"reach the grand final")

    if wildcard:
        # Seeds 1-6 are already in the eight, so their p_finals must be 1.
        top6 = df[df.ladder_pos <= 6]
        if not np.allclose(top6.p_finals, 1.0):
            problems.append("top six do not have guaranteed final-eight spots")
        # Seeds 7-10 must sum to exactly 2 places.
        wc = df[df.ladder_pos > 6].p_finals.sum()
        if abs(wc - 2.0) > tol:
            problems.append(f"wildcard teams claim {wc:.3f} places, not 2")

    return problems
