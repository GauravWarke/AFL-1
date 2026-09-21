import json
import numpy as np
import pandas as pd

U = "/mnt/user-data/uploads/AFL"
par = json.load(open("/home/claude/model_params.json"))
m = pd.read_csv(f"{U}/data/processed/matches.csv")
lad = pd.read_csv(f"{U}/data/processed/ladder_2026.csv")
proj = pd.read_csv(f"{U}/outputs/finals_projection_2026_R.csv")
calib = pd.read_csv(f"{U}/outputs/calibration_table.csv")
scores = pd.read_csv(f"{U}/outputs/model_scores.csv")
bake = pd.read_csv(f"{U}/outputs/bakeoff_preds_2026.csv")

SEASON = 2026
ha = m[(m.season == SEASON) & (m.stage == "home_and_away")]

long = pd.concat([
    pd.DataFrame({"team": ha.home, "shots": ha.home_shots, "goals": ha.home_goals,
                  "opp_shots": ha.away_shots, "pf": ha.home_score, "pa": ha.away_score}),
    pd.DataFrame({"team": ha.away, "shots": ha.away_shots, "goals": ha.away_goals,
                  "opp_shots": ha.home_shots, "pf": ha.away_score, "pa": ha.home_score}),
])
season = long.groupby("team").agg(
    games=("shots", "size"), created=("shots", "mean"), allowed=("opp_shots", "mean"),
    g=("goals", "sum"), s=("shots", "sum"), pf=("pf", "mean"), pa=("pa", "mean"))
season["accuracy"] = season.g / season.s
season["edge"] = season.created - season.allowed

teams = []
lm = lad.set_index("team")
for t in sorted(par["attack"]):
    r = season.loc[t]
    l = lm.loc[t] if t in lm.index else None
    teams.append({
        "name": t,
        "attack": round(par["attack"][t], 6),
        "defence": round(par["defence"][t], 6),
        "acc": round(par["accuracy"][t], 6),
        "created": round(float(r.created), 2),
        "allowed": round(float(r.allowed), 2),
        "rawAcc": round(float(r.accuracy), 4),
        "edge": round(float(r.edge), 2),
        "pf": round(float(r.pf), 1),
        "pa": round(float(r.pa), 1),
        "won": int(l.won) if l is not None else 0,
        "played": int(l.played) if l is not None else 0,
        "pts": int(l.pts) if l is not None else 0,
        "pct": round(float(l.percentage), 1) if l is not None else 0,
    })

# finals already played this season
fin = m[(m.season == SEASON) & (m.stage != "home_and_away")].sort_values("date")
played = [{
    "stage": r.stage.replace("_", " "),
    "date": str(r.date)[:10],
    "home": r.home, "away": r.away,
    "hg": int(r.home_goals), "hb": int(r.home_behinds), "hs": int(r.home_score),
    "ag": int(r.away_goals), "ab": int(r.away_behinds), "as": int(r.away_score),
    "winner": r.home if r.margin > 0 else r.away,
    "margin": int(abs(r.margin)),
} for r in fin.itertuples()]

# beat-the-model ledger: the winning model's own 2026 walk-forward predictions
sh = bake[bake.model == "shots"].copy()
mm = m.set_index("game_id")
ledger = []
for r in sh.itertuples():
    g = mm.loc[r.game_id]
    ledger.append({
        "id": int(r.game_id), "rd": int(r.round),
        "home": g.home, "away": g.away,
        "p": round(float(r.prob), 4),
        "won": int(r.home_win),
        "hs": int(g.home_score), "as": int(g.away_score),
    })

out = {
    "meta": {
        "season": SEASON,
        "asAt": "2026-09-05",
        "grandFinal": "2026-09-26",
        "model": "Scoring shots + shrunk accuracy",
        "logloss": 0.5212,
        "nMatches": 211,
        "squigglePlace": "12th of 38",
        "reliability": {"created": 0.88, "allowed": 0.87, "accuracy": 0.32},
        "intercept": round(par["intercept"], 6),
        "home": round(par["home"], 6),
        "theta": round(par["theta"], 2),
        "leagueAcc": round(par["league_acc"], 6),
    },
    "teams": teams,
    "projection": [{
        "pos": int(r.ladder_pos), "team": r.team,
        "prelim": round(float(r.p_prelim), 4),
        "gf": round(float(r.p_grand_final), 4),
        "flag": round(float(r.p_premier), 4),
    } for r in proj.itertuples() if r.p_premier > 0],
    "bakeoff": [{
        "model": {"shots": "Scoring shots + accuracy", "ridge": "Ridge margin",
                  "elo": "Elo", "bayes": "Bayesian hierarchical",
                  "bt": "Bradley-Terry", "xgb": "Gradient boosting",
                  "rf": "Random forest"}[r.model],
        "key": r.model,
        "logloss": round(float(r.logloss), 4),
        "brier": round(float(r.brier), 4),
        "tip": round(float(r.tip), 1),
        "mae": round(float(r.mae), 2),
        "calib": round(float(r.calib), 3),
    } for r in scores.itertuples()],
    "calibration": [{
        "bucket": r.bucket, "n": int(r.n),
        "predicted": round(float(r.predicted), 4),
        "actual": round(float(r.actual), 4),
    } for r in calib.itertuples()],
    "played": played,
    "ledger": ledger,
}

with open("/home/claude/afl.json", "w") as f:
    json.dump(out, f, separators=(",", ":"))
print("teams", len(teams), "ledger", len(ledger), "played", len(played))
print("bytes", len(json.dumps(out, separators=(",", ":"))))
