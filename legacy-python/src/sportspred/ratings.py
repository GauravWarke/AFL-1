"""Ridge-penalised team strength from match margins.

This is a weighted least-squares ratings estimator, written to be reusable
so both sports share it, with one addition: home advantage is a design-matrix
block rather than a single scalar, because the AFL needs it to vary.

The model
---------
For a match between home team h and away team a,

    margin = strength[h] - strength[a] + (home advantage terms) + error

Strengths are estimated with an L2 penalty. The penalty is not an arbitrary
regularisation choice: with a Gaussian prior on strengths, ridge with

    lambda = sigma^2 / tau^2

is exactly the posterior mean, where sigma is match-level noise and tau is the
spread of true team strength. So the penalty is empirical Bayes, and it does
the same job as partial pooling -- a team with a small or unbalanced sample is
pulled toward the league mean by an amount the data itself sets.

Recency weighting uses exponential decay. Note the sigma correction: when rows
are weighted, the residual sum of squares is already weighted, so dividing by
the raw row count understates sigma. This was caught by
a Q-Q plot and is guarded against here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import geography


def build_design(
    df: pd.DataFrame, teams: list[str], hga_model: str = "venue"
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Design matrix, response, and column names.

    Column layout: one column per team (+1 home, -1 away), then the home
    advantage block.
    """
    idx = {t: i for i, t in enumerate(teams)}
    n, p = len(df), len(teams)

    hga_cols: list[str] = []
    if hga_model == "scalar":
        hga_cols = ["hga"]
    elif hga_model == "venue":
        # Three interpretable terms rather than a free parameter per
        # team-venue pair. Many pairs have only a handful of matches, and an
        # unpooled per-pair estimate would be mostly noise.
        hga_cols = ["hga_base", "away_interstate", "away_tz_shift"]
    else:
        raise ValueError(hga_model)

    X = np.zeros((n, p + len(hga_cols)))
    y = df["margin"].to_numpy(dtype=float)

    # Vectorised rather than row-wise: the walk-forward validation refits once
    # per round per season per configuration, so a per-row Python loop here
    # dominates the entire runtime.
    rows = np.arange(n)
    X[rows, df["home"].map(idx).to_numpy()] = 1.0
    X[rows, df["away"].map(idx).to_numpy()] = -1.0

    if hga_model == "scalar":
        X[:, p] = 1.0
    else:
        home_tr = _travel_frame(df["home"], df["venue"])
        away_tr = _travel_frame(df["away"], df["venue"])
        # Base home advantage applies only when the home side is actually at
        # home -- i.e. did not itself travel interstate. This is what makes
        # relocated and neutral-venue "home" games behave correctly instead of
        # quietly inflating the estimate.
        X[:, p + 0] = 1.0 - home_tr["interstate"]
        X[:, p + 1] = away_tr["interstate"]
        X[:, p + 2] = away_tr["tz_shift"]

    return X, y, list(teams) + hga_cols


def _travel_frame(teams: pd.Series, venues: pd.Series) -> dict:
    """Vectorised geography.travel over two aligned Series."""
    ts = teams.map(geography.TEAM_STATE)
    vs = venues.map(geography.VENUE_STATE)
    unknown = ts.isna() | vs.isna() | (vs == "OS")
    interstate = np.where(unknown, 1.0, (ts != vs).astype(float))
    tz = np.where(
        unknown, 0.0,
        np.abs(ts.map(geography.STATE_TZ).fillna(10).to_numpy(dtype=float)
               - vs.map(geography.STATE_TZ).fillna(10).to_numpy(dtype=float)),
    )
    return dict(interstate=interstate, tz_shift=tz)


def fit(
    df: pd.DataFrame,
    hga_model: str = "venue",
    decay: float = 0.0,
    lam: float | None = None,
    teams: list[str] | None = None,
) -> dict:
    """Fit strengths and home advantage.

    decay : per-season exponential weight, 0 = no discounting of old seasons.
    lam   : ridge penalty. None means estimate it by empirical Bayes.
    """
    teams = teams or sorted(set(df.home) | set(df.away))
    X, y, names = build_design(df, teams, hga_model)
    p_team = len(teams)

    weights = np.ones(len(df))
    if decay > 0:
        age = (df["season"].max() - df["season"]).to_numpy(dtype=float)
        weights = (1 - decay) ** age
        w = np.sqrt(weights)
        X, y = X * w[:, None], y * w

    # Penalise team strengths only. Home advantage is a population effect we
    # actually want estimated, not shrunk toward zero.
    pen = np.zeros(X.shape[1])

    def solve(l2: float) -> np.ndarray:
        pen[:p_team] = l2
        A = X.T @ X + np.diag(pen)
        try:
            return np.linalg.solve(A, X.T @ y)
        except np.linalg.LinAlgError:
            # Happens when the fixture graph is disconnected -- early in a
            # season under heavy decay, some teams have not yet played anyone
            # who has played anyone else, so their strengths are not jointly
            # identified. The pseudo-inverse returns the minimum-norm solution,
            # which shrinks the unidentified directions to zero. That is the
            # right behaviour: an unknown team gets the league average.
            return np.linalg.pinv(A) @ (X.T @ y)

    if lam is None:
        # Two-pass empirical Bayes. Start from a weak penalty to get scale
        # estimates, then set lambda = sigma^2 / tau^2 and refit.
        beta0 = solve(1.0)
        r0 = y - X @ beta0
        eff_n = float(weights.sum())
        sigma0_sq = float(r0 @ r0) / max(eff_n - X.shape[1], 1)
        tau0_sq = float(np.var(beta0[:p_team], ddof=1))
        lam = sigma0_sq / max(tau0_sq, 1e-9)

    beta = solve(lam)
    resid = y - X @ beta

    # `resid` is already scaled by sqrt(weight), so resid @ resid is the
    # WEIGHTED sum of squares. Dividing by the raw row count would understate
    # sigma whenever decay > 0.
    eff_n = float(weights.sum())
    sigma = float(np.sqrt(resid @ resid / max(eff_n - X.shape[1] - 1, 1)))

    strengths = pd.Series(beta[:p_team], index=teams).sort_values(ascending=False)
    # Centre so the league mean is zero; only differences are identified.
    strengths = strengths - strengths.mean()

    return dict(
        strengths=strengths,
        hga=dict(zip(names[p_team:], beta[p_team:])),
        sigma=sigma,
        lam=float(lam),
        n_matches=len(df),
        effective_n=eff_n,
        names=names,
        beta=beta,
    )


def predict_margin(model: dict, home: str, away: str, venue: str,
                   hga_model: str = "venue") -> float:
    s = model["strengths"]
    m = float(s.get(home, 0.0) - s.get(away, 0.0))
    h = model["hga"]
    if hga_model == "scalar":
        return m + h.get("hga", 0.0)
    th = geography.travel(home, venue)
    ta = geography.travel(away, venue)
    m += 0.0 if th["interstate"] else h.get("hga_base", 0.0)
    m += ta["interstate"] * h.get("away_interstate", 0.0)
    m += ta["tz_shift"] * h.get("away_tz_shift", 0.0)
    return m


def estimate_drift(df: pd.DataFrame, hga_model: str = "venue") -> dict:
    """Season-to-season change in true team strength, in points.

    Fitting each season independently and taking the variance of the observed
    year-on-year change would overstate drift, because each of the two ratings
    carries its own estimation error:

        var(observed change) = 2 * var(estimation error) + var(true drift)

    So estimation error must be subtracted off. Getting this wrong is what made
    the prediction intervals too narrow -- they covered 62.5% of
    outcomes at a nominal 80% -- so it is measured, not guessed.
    """
    ha = df[df.stage == "home_and_away"]
    fits = {}
    for season, g in ha.groupby("season"):
        if len(g) < 100:
            continue
        f = fit(g, hga_model=hga_model)
        # Standard error of a team rating: sigma / sqrt(games), roughly, since
        # each team appears in ~2*games/n_teams rows with +-1 coding.
        games = g.groupby("home").size().add(
            g.groupby("away").size(), fill_value=0)
        fits[season] = (f["strengths"], f["sigma"], games)

    changes, est_var = [], []
    seasons = sorted(fits)
    for s0, s1 in zip(seasons, seasons[1:]):
        a, sig_a, ga = fits[s0]
        b, sig_b, gb = fits[s1]
        common = a.index.intersection(b.index)
        for t in common:
            changes.append(b[t] - a[t])
            va = sig_a ** 2 / max(ga.get(t, 1), 1)
            vb = sig_b ** 2 / max(gb.get(t, 1), 1)
            est_var.append(va + vb)

    changes = np.array(changes)
    observed = float(changes.var(ddof=1))
    estimation = float(np.mean(est_var))
    true_drift = max(observed - estimation, 0.0)
    return dict(
        n_pairs=len(changes),
        observed_sd=float(np.sqrt(observed)),
        estimation_sd=float(np.sqrt(estimation)),
        drift_sd=float(np.sqrt(true_drift)),
    )
