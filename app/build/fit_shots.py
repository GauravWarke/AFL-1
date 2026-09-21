"""Refit the winning 'shots + accuracy' model and export coefficients as JSON.

Mirrors R/02_models.R::fit_shots exactly:
  shots ~ team + opp + is_home, negative binomial, exponential season decay 0.80
  accuracy = league_acc + 0.324 * (team_acc - league_acc)
"""
import json
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.optimize import minimize_scalar

DECAY = 0.80
RELIABILITY = 0.324
SEASON = 2026

m = pd.read_csv("/mnt/user-data/uploads/AFL/data/processed/matches.csv")


def to_long(df):
    h = pd.DataFrame({
        "season": df.season, "team": df.home, "opp": df.away, "is_home": 1,
        "shots": df.home_shots, "goals": df.home_goals,
        "opp_shots": df.away_shots, "score": df.home_score,
        "conceded": df.away_score})
    a = pd.DataFrame({
        "season": df.season, "team": df.away, "opp": df.home, "is_home": 0,
        "shots": df.away_shots, "goals": df.away_goals,
        "opp_shots": df.home_shots, "score": df.away_score,
        "conceded": df.home_score})
    return pd.concat([h, a], ignore_index=True)


def fit_shots(train):
    long = to_long(train)
    long["w"] = (1 - DECAY) ** (long.season.max() - long.season)

    teams = sorted(set(long.team) | set(long.opp))
    ref = teams[0]
    X = pd.DataFrame(index=long.index)
    X["intercept"] = 1.0
    for t in teams[1:]:
        X[f"team_{t}"] = (long.team == t).astype(float)
    for t in teams[1:]:
        X[f"opp_{t}"] = (long.opp == t).astype(float)
    X["is_home"] = long.is_home.astype(float)

    y = long.shots.values
    w = long.w.values

    def negll(log_alpha):
        alpha = np.exp(log_alpha)
        fam = sm.families.NegativeBinomial(alpha=alpha)
        try:
            r = sm.GLM(y, X.values, family=fam, freq_weights=w).fit()
            return -r.llf
        except Exception:
            return 1e12

    opt = minimize_scalar(negll, bounds=(-8, 2), method="bounded")
    alpha = float(np.exp(opt.x))
    theta = 1.0 / alpha
    res = sm.GLM(y, X.values, family=sm.families.NegativeBinomial(alpha=alpha),
                 freq_weights=w).fit()

    coefs = dict(zip(X.columns, res.params))
    attack = {ref: 0.0}
    defence = {ref: 0.0}
    for t in teams[1:]:
        attack[t] = float(coefs[f"team_{t}"])
        defence[t] = float(coefs[f"opp_{t}"])

    acc_tab = long.groupby("team").agg(g=("goals", "sum"), s=("shots", "sum"))
    league_acc = float(acc_tab.g.sum() / acc_tab.s.sum())
    accuracy = {t: league_acc + RELIABILITY * (r.g / r.s - league_acc)
                for t, r in acc_tab.iterrows()}

    return {
        "intercept": float(coefs["intercept"]),
        "home": float(coefs["is_home"]),
        "theta": theta,
        "league_acc": league_acc,
        "attack": attack,
        "defence": {k: float(v) for k, v in defence.items()},
        "accuracy": {k: float(v) for k, v in accuracy.items()},
        "teams": teams,
        "reference_team": ref,
    }


def predict(par, home, away, nsim=20000, rng=None):
    rng = rng or np.random.default_rng(7)
    lh = np.exp(par["intercept"] + par["attack"][home] + par["defence"][away] + par["home"])
    la = np.exp(par["intercept"] + par["attack"][away] + par["defence"][home])
    ah = par["accuracy"].get(home, par["league_acc"])
    aa = par["accuracy"].get(away, par["league_acc"])
    th = par["theta"]
    p_h = th / (th + lh)
    p_a = th / (th + la)
    sh = rng.negative_binomial(th, p_h, nsim)
    sa = rng.negative_binomial(th, p_a, nsim)
    gh = rng.binomial(sh, ah)
    ga = rng.binomial(sa, aa)
    mg = (gh * 6 + (sh - gh)) - (ga * 6 + (sa - ga))
    return float(mg.mean()), float((mg > 0).mean() + 0.5 * (mg == 0).mean())


if __name__ == "__main__":
    train = m[m.stage == "home_and_away"]
    par = fit_shots(train)
    print(f"theta={par['theta']:.3f}  league_acc={par['league_acc']:.4f}  "
          f"home={par['home']:.4f}  intercept={par['intercept']:.4f}")

    # expected shots for each team at home vs an average opponent
    print("\nteam                       att      def   acc")
    for t in sorted(par["attack"], key=lambda x: -par["attack"][x]):
        print(f"{t:24s} {par['attack'][t]:+.3f}  {par['defence'][t]:+.3f}  "
              f"{par['accuracy'][t]:.3f}")

    with open("/home/claude/model_params.json", "w") as f:
        json.dump(par, f, indent=1)
