"""Separating repeatable skill from luck.

The core identity is

    var(observed) = var(true skill) + var(noise)

so if the noise variance can be derived from first principles, the skill share
follows by subtraction:

    reliability = 1 - E[var(noise)] / var(observed)

Reliability near 1 means the metric measures something about the team that will
still be there next week. Near 0 means this week's value tells you almost
nothing about next week's, and ranking teams by it is ranking them by luck.

For a *rate* built from a count of Bernoulli trials -- goal accuracy is exactly
this: n scoring shots, each converted or not -- the noise variance is known
analytically, p(1-p)/n. That is a stronger test than split-half correlation
because it needs no arbitrary split, so both are computed and compared. If they
disagree, the binomial assumption is wrong (shots within a match are not
independent) and that is itself worth knowing.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def binomial_reliability(successes: np.ndarray, trials: np.ndarray) -> dict:
    """Skill share of an observed conversion rate.

    successes / trials, one row per unit (e.g. one team-season).
    """
    successes = np.asarray(successes, dtype=float)
    trials = np.asarray(trials, dtype=float)
    if np.any(trials <= 1):
        raise ValueError("every unit needs at least 2 trials")

    rate = successes / trials
    observed_var = rate.var(ddof=1)

    # Pool the rate to estimate the binomial noise. Using each unit's own rate
    # would bias the noise estimate upward for units that got lucky, which is
    # precisely the quantity being measured.
    p_pool = successes.sum() / trials.sum()
    noise_var = float(np.mean(p_pool * (1 - p_pool) / trials))

    skill_var = observed_var - noise_var
    return dict(
        n_units=len(rate),
        mean_rate=float(p_pool),
        observed_sd=float(np.sqrt(observed_var)),
        noise_sd=float(np.sqrt(noise_var)),
        # Clipped at 0: a negative estimate means the observed spread is
        # smaller than binomial noise alone, i.e. no detectable skill.
        skill_sd=float(np.sqrt(max(skill_var, 0.0))),
        reliability=float(max(skill_var, 0.0) / observed_var),
    )


def split_half_reliability(
    df: pd.DataFrame, unit: str, order: str, value: str, weight: str | None = None
) -> dict:
    """Correlate each unit's odd-numbered games against its even-numbered ones.

    Odd/even rather than first-half/second-half on purpose: a team's form
    genuinely drifts across a season, and a chronological split would charge
    that real change to unreliability.

    The raw correlation measures half-length samples, so it is stepped up to
    full length with the Spearman-Brown formula.
    """
    out = []
    for u, g in df.groupby(unit):
        g = g.sort_values(order)
        a, b = g.iloc[0::2], g.iloc[1::2]
        if len(a) < 3 or len(b) < 3:
            continue
        if weight:
            va = a[value].sum() / a[weight].sum()
            vb = b[value].sum() / b[weight].sum()
        else:
            va, vb = a[value].mean(), b[value].mean()
        out.append((va, vb))

    if len(out) < 5:
        raise ValueError("too few units for a stable split-half estimate")

    arr = np.array(out)
    r = float(np.corrcoef(arr[:, 0], arr[:, 1])[0, 1])
    sb = 2 * r / (1 + r) if r > -1 else float("nan")
    return dict(n_units=len(arr), half_r=r, spearman_brown=float(sb))
