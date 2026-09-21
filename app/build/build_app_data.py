"""Build the web app's data bundle from the refreshed match table."""
import json, sys
import numpy as np
import pandas as pd

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from realtime import fit_shots, predict, to_long, ll  # noqa

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
SEASON = 2026
m = pd.read_csv(f"{ROOT}/data/processed/matches.csv")
train = m[m.stage == "home_and_away"]
par = fit_shots(train)

# ---- team season numbers ---------------------------------------------------
ha = m[(m.season == SEASON) & (m.stage == "home_and_away")]
long = to_long(ha)
season = long.groupby("team").agg(games=("shots", "size"), created=("shots", "mean"),
                                  allowed=("opp_shots", "mean"), g=("goals", "sum"),
                                  s=("shots", "sum"), pf=("score", "mean"), pa=("conceded", "mean"))
season["accuracy"] = season.g / season.s
season["edge"] = season.created - season.allowed

lad = pd.read_csv(f"{ROOT}/data/processed/ladder_2026.csv").set_index("team")
teams = []
for t in sorted(par["attack"]):
    r = season.loc[t]
    l = lad.loc[t] if t in lad.index else None
    teams.append({"name": t, "attack": round(par["attack"][t], 6),
                  "defence": round(par["defence"][t], 6), "acc": round(par["accuracy"][t], 6),
                  "created": round(float(r.created), 2), "allowed": round(float(r.allowed), 2),
                  "rawAcc": round(float(r.accuracy), 4), "edge": round(float(r.edge), 2),
                  "won": int(l.won) if l is not None else 0,
                  "pts": int(l.pts) if l is not None else 0})

# ---- the holdout: every 2026 final, none of them trained on ----------------
fin = m[(m.season == SEASON) & (m.stage != "home_and_away")].sort_values("date")
finals = []
for g in fin.itertuples():
    pr = predict(par, g.home, g.away)
    y = 1 if g.margin > 0 else 0
    finals.append({"date": str(g.date)[:10], "stage": g.stage.replace("_", " "),
                   "home": g.home, "away": g.away,
                   "hg": int(g.home_goals), "hb": int(g.home_behinds), "hs": int(g.home_score),
                   "ag": int(g.away_goals), "ab": int(g.away_behinds), "as": int(g.away_score),
                   "hShots": int(g.home_shots), "aShots": int(g.away_shots),
                   "p": round(pr["prob"], 4), "won": y,
                   "ll": round(ll(pr["prob"], y), 4),
                   "predMargin": round(pr["margin"], 1), "actMargin": int(g.margin),
                   "tip": int((pr["prob"] > 0.5) == (y == 1))})
F = pd.DataFrame(finals)

# ---- live bracket: two games remain, so this is exact ----------------------
prelim = predict(par, "Hawthorn", "Brisbane Lions")
gf_haw = predict(par, "Hawthorn", "Fremantle")
gf_bri = predict(par, "Brisbane Lions", "Fremantle")
ph = prelim["prob"]
flag = {"Fremantle": ph * (1 - gf_haw["prob"]) + (1 - ph) * (1 - gf_bri["prob"]),
        "Hawthorn": ph * gf_haw["prob"],
        "Brisbane Lions": (1 - ph) * gf_bri["prob"]}


def sl(pts, goals):
    g = round(goals); return {"g": g, "b": max(0, round(pts) - g * 6), "pts": round(pts)}


# ---- carried over, still valid --------------------------------------------
scores = pd.read_csv(f"{ROOT}/outputs/model_scores.csv")
calib = pd.read_csv(f"{ROOT}/outputs/calibration_table.csv")
bake = pd.read_csv(f"{ROOT}/outputs/bakeoff_preds_2026.csv")
sh = bake[bake.model == "shots"]
mm = m.set_index("game_id")
ledger = []
for r in sh.itertuples():
    if r.game_id not in mm.index: continue
    g = mm.loc[r.game_id]
    ledger.append({"id": int(r.game_id), "rd": int(r.round), "home": g.home, "away": g.away,
                   "p": round(float(r.prob), 4), "won": int(r.home_win),
                   "hs": int(g.home_score), "as": int(g.away_score)})

NICE = {"shots": "Scoring shots + accuracy", "ridge": "Ridge margin", "elo": "Elo",
        "bayes": "Bayesian hierarchical", "bt": "Bradley-Terry",
        "xgb": "Gradient boosting", "rf": "Random forest"}

out = {
  "meta": {
    "season": SEASON, "asAt": "2026-09-19", "grandFinal": "2026-09-26",
    "logloss": 0.5212, "nMatches": 211, "squigglePlace": "12th of 38",
    "reliability": {"created": 0.88, "allowed": 0.87, "accuracy": 0.32},
    "intercept": round(par["intercept"], 6), "home": round(par["home"], 6),
    "theta": round(par["theta"], 2), "leagueAcc": round(par["league_acc"], 6),
    "holdout": {"logloss": round(float(F.ll.mean()), 4),
                "tip": round(float(F.tip.mean() * 100), 1),
                "mae": round(float((F.predMargin - F.actMargin).abs().mean()), 2),
                "n": int(len(F)), "coin": 0.6931},
  },
  "teams": teams,
  "finals": finals,
  "live": {
    "prelim": {"home": "Hawthorn", "away": "Brisbane Lions", "venue": "M.C.G.",
               "when": "19 Sep, 5:15pm", "p": round(ph, 4),
               "hLine": sl(prelim["hPts"], prelim["hG"]), "aLine": sl(prelim["aPts"], prelim["aG"]),
               "margin": round(prelim["margin"], 1)},
    "gf": [
      {"home": "Hawthorn", "away": "Fremantle", "p": round(gf_haw["prob"], 4),
       "hLine": sl(gf_haw["hPts"], gf_haw["hG"]), "aLine": sl(gf_haw["aPts"], gf_haw["aG"])},
      {"home": "Brisbane Lions", "away": "Fremantle", "p": round(gf_bri["prob"], 4),
       "hLine": sl(gf_bri["hPts"], gf_bri["hG"]), "aLine": sl(gf_bri["aPts"], gf_bri["aG"])},
    ],
    "flag": [{"team": t, "p": round(p, 4)} for t, p in sorted(flag.items(), key=lambda x: -x[1])],
  },
  "bakeoff": [{"model": NICE[r.model], "key": r.model, "logloss": round(float(r.logloss), 4),
               "brier": round(float(r.brier), 4), "tip": round(float(r.tip), 1),
               "mae": round(float(r.mae), 2), "calib": round(float(r.calib), 3)}
              for r in scores.itertuples()],
  "calibration": [{"bucket": r.bucket, "n": int(r.n), "predicted": round(float(r.predicted), 4),
                   "actual": round(float(r.actual), 4)} for r in calib.itertuples()],
  "ledger": ledger,
}

with open(f"{ROOT}/app/afl.json", "w") as f:
    json.dump(out, f, separators=(",", ":"))
print("holdout log-loss", out["meta"]["holdout"]["logloss"],
      "| finals", len(finals), "| ledger", len(ledger))
print("flag:", out["live"]["flag"])
print("bytes", len(json.dumps(out, separators=(",", ":"))))
