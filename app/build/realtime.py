"""Refit the winning shots model and test it on the 2026 finals it never trained on.

The model is fitted on home-and-away matches only, so every final is a clean
holdout. Also produces the live prediction for the remaining bracket.
"""
import json, sys
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.optimize import minimize_scalar

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
DECAY, RELIABILITY = 0.80, 0.324
m = pd.read_csv(f"{ROOT}/data/processed/matches.csv")


def to_long(df):
    h = pd.DataFrame({"season": df.season, "team": df.home, "opp": df.away, "is_home": 1,
                      "shots": df.home_shots, "goals": df.home_goals,
                      "opp_shots": df.away_shots, "score": df.home_score, "conceded": df.away_score})
    a = pd.DataFrame({"season": df.season, "team": df.away, "opp": df.home, "is_home": 0,
                      "shots": df.away_shots, "goals": df.away_goals,
                      "opp_shots": df.home_shots, "score": df.away_score, "conceded": df.home_score})
    return pd.concat([h, a], ignore_index=True)


def fit_shots(train):
    long = to_long(train)
    long["w"] = (1 - DECAY) ** (long.season.max() - long.season)
    teams = sorted(set(long.team) | set(long.opp)); ref = teams[0]
    X = pd.DataFrame(index=long.index); X["intercept"] = 1.0
    for t in teams[1:]: X[f"team_{t}"] = (long.team == t).astype(float)
    for t in teams[1:]: X[f"opp_{t}"] = (long.opp == t).astype(float)
    X["is_home"] = long.is_home.astype(float)
    y, w = long.shots.values, long.w.values

    def negll(la):
        try: return -sm.GLM(y, X.values, family=sm.families.NegativeBinomial(alpha=np.exp(la)),
                            freq_weights=w).fit().llf
        except Exception: return 1e12
    opt = minimize_scalar(negll, bounds=(-8, 2), method="bounded")
    alpha = float(np.exp(opt.x)); theta = 1.0 / alpha
    res = sm.GLM(y, X.values, family=sm.families.NegativeBinomial(alpha=alpha), freq_weights=w).fit()
    c = dict(zip(X.columns, res.params))
    attack = {ref: 0.0}; defence = {ref: 0.0}
    for t in teams[1:]:
        attack[t] = float(c[f"team_{t}"]); defence[t] = float(c[f"opp_{t}"])
    at = long.groupby("team").agg(g=("goals", "sum"), s=("shots", "sum"))
    league = float(at.g.sum() / at.s.sum())
    acc = {t: league + RELIABILITY * (r.g / r.s - league) for t, r in at.iterrows()}
    return {"intercept": float(c["intercept"]), "home": float(c["is_home"]), "theta": theta,
            "league_acc": league, "attack": attack, "defence": {k: float(v) for k, v in defence.items()},
            "accuracy": {k: float(v) for k, v in acc.items()}, "teams": teams, "reference_team": ref}


def predict(p, home, away, home_adv=True, nsim=60000, seed=11):
    rng = np.random.default_rng(seed)
    lh = np.exp(p["intercept"] + p["attack"][home] + p["defence"][away] + (p["home"] if home_adv else 0))
    la = np.exp(p["intercept"] + p["attack"][away] + p["defence"][home])
    th = p["theta"]
    sh = rng.negative_binomial(th, th / (th + lh), nsim)
    sa = rng.negative_binomial(th, th / (th + la), nsim)
    gh = rng.binomial(sh, p["accuracy"].get(home, p["league_acc"]))
    ga = rng.binomial(sa, p["accuracy"].get(away, p["league_acc"]))
    hp, ap = gh * 6 + (sh - gh), ga * 6 + (sa - ga)
    mg = hp - ap
    return {"prob": float((mg > 0).mean() + 0.5 * (mg == 0).mean()),
            "margin": float(mg.mean()), "hPts": float(hp.mean()), "aPts": float(ap.mean()),
            "hG": float(gh.mean()), "aG": float(ga.mean()),
            "hShots": float(lh), "aShots": float(la)}


ll = lambda p, y: -(y * np.log(max(1e-9, p)) + (1 - y) * np.log(max(1e-9, 1 - p)))

def _main():
    # ---- fit on home-and-away only; every final is a holdout --------------------
    train = m[m.stage == "home_and_away"]
    par = fit_shots(train)

    fin = m[(m.season == 2026) & (m.stage != "home_and_away")].sort_values("date")
    rows = []
    for g in fin.itertuples():
        pr = predict(par, g.home, g.away)
        y = 1 if g.margin > 0 else 0
        rows.append({"date": str(g.date)[:10], "stage": g.stage.replace("_", " "),
                     "home": g.home, "away": g.away, "hs": int(g.home_score), "as": int(g.away_score),
                     "p": pr["prob"], "won": y, "ll": ll(pr["prob"], y),
                     "predMargin": pr["margin"], "actMargin": int(g.margin),
                     "tip": int((pr["prob"] > 0.5) == (y == 1))})
    F = pd.DataFrame(rows)

    print("=" * 78)
    print("OUT-OF-SAMPLE: the nine 2026 finals, none of which the model trained on")
    print("=" * 78)
    for r in F.itertuples():
        print(f"{r.date}  {r.stage:18s} {r.home[:17]:17s} {r.hs:3d} v {r._6:3d} {r.away[:17]:17s}"
              f"  p(home)={r.p:.3f}  {'HIT ' if r.tip else 'MISS'}  loss={r.ll:.3f}")
    print("-" * 78)
    print(f"log-loss   {F.ll.mean():.4f}   (home-and-away walk-forward benchmark: 0.5212)")
    print(f"tipping    {F.tip.mean()*100:.1f}%  ({F.tip.sum()}/{len(F)})")
    print(f"margin MAE {(F.predMargin - F.actMargin).abs().mean():.2f}")
    base = -np.mean([np.log(0.5)] * len(F))
    print(f"coin flip  {base:.4f}  -> model is {'BETTER' if F.ll.mean() < base else 'WORSE'}")

    # ---- the live bracket: two games left --------------------------------------
    print()
    print("=" * 78)
    print("LIVE: what is left")
    print("=" * 78)
    prelim = predict(par, "Hawthorn", "Brisbane Lions")            # MCG, Hawthorn home
    gf_haw = predict(par, "Hawthorn", "Fremantle")                 # MCG, prelim winner listed home
    gf_bri = predict(par, "Brisbane Lions", "Fremantle")

    print(f"PRELIM  Hawthorn v Brisbane Lions @ M.C.G. (19 Sep)")
    print(f"        Hawthorn {prelim['prob']*100:.1f}%   projected "
          f"{round(prelim['hG'])}.{round(prelim['hPts'])-6*round(prelim['hG'])} ({round(prelim['hPts'])})"
          f" v {round(prelim['aG'])}.{round(prelim['aPts'])-6*round(prelim['aG'])} ({round(prelim['aPts'])})")
    print(f"GF      if Hawthorn:  Hawthorn {gf_haw['prob']*100:.1f}% v Fremantle {(1-gf_haw['prob'])*100:.1f}%")
    print(f"        if Brisbane:  Brisbane {gf_bri['prob']*100:.1f}% v Fremantle {(1-gf_bri['prob'])*100:.1f}%")

    ph = prelim["prob"]
    flag = {
        "Hawthorn": ph * gf_haw["prob"],
        "Brisbane Lions": (1 - ph) * gf_bri["prob"],
        "Fremantle": ph * (1 - gf_haw["prob"]) + (1 - ph) * (1 - gf_bri["prob"]),
    }
    print()
    print("PREMIERSHIP (exact, no simulation needed - two games remain)")
    for t, p in sorted(flag.items(), key=lambda x: -x[1]):
        print(f"        {t:16s} {p*100:5.1f}%")
    print(f"        sum = {sum(flag.values()):.4f}")

    out = {
        "params": par,
        "finals": rows,
        "holdout": {"logloss": float(F.ll.mean()), "tip": float(F.tip.mean() * 100),
                    "mae": float((F.predMargin - F.actMargin).abs().mean()), "n": int(len(F))},
        "live": {"prelim": prelim, "gf_haw": gf_haw, "gf_bri": gf_bri, "flag": flag},
    }
    with open(f"{ROOT}/outputs/realtime_2026.json", "w") as f:
        json.dump(out, f, indent=1)
    print(f"\nwrote {ROOT}/outputs/realtime_2026.json")


if __name__ == '__main__':
    _main()
