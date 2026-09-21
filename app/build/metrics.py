"""Build the metric set behind the dashboards.

Every metric here is derivable from what the data actually contains: goals,
behinds, scores, venue, date, teams. Nothing else is available -- there are no
disposals, contested possessions, inside 50s, tackles or player records in this
feed, so no metric here pretends to measure them.
"""
import json, sys
import numpy as np
import pandas as pd

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
SEASON = 2026
m = pd.read_csv(f"{ROOT}/data/processed/matches.csv")
m["date"] = pd.to_datetime(m["date"])

TEAM_STATE = {
    "Adelaide": "SA", "Port Adelaide": "SA", "Brisbane Lions": "QLD",
    "Gold Coast": "QLD", "Sydney": "NSW", "Greater Western Sydney": "NSW",
    "West Coast": "WA", "Fremantle": "WA", "Carlton": "VIC",
    "Collingwood": "VIC", "Essendon": "VIC", "Geelong": "VIC",
    "Hawthorn": "VIC", "Melbourne": "VIC", "North Melbourne": "VIC",
    "Richmond": "VIC", "St Kilda": "VIC", "Western Bulldogs": "VIC",
}
VENUE_STATE = {
    "M.C.G.": "VIC", "Docklands": "VIC", "Kardinia Park": "VIC",
    "Marvel Stadium": "VIC", "Princes Park": "VIC", "Eureka Stadium": "VIC",
    "Mars Stadium": "VIC", "Eureka": "VIC",
    "Adelaide Oval": "SA", "Football Park": "SA", "Norwood Oval": "SA",
    "Summit Sports Park": "SA", "Barossa Park": "SA",
    "Gabba": "QLD", "Carrara": "QLD", "Cazaly's Stadium": "QLD",
    "Riverway Stadium": "QLD", "Metricon Stadium": "QLD",
    "S.C.G.": "NSW", "Sydney Showground": "NSW", "Blacktown": "NSW",
    "Stadium Australia": "NSW", "Manuka Oval": "ACT",
    "Perth Stadium": "WA", "Subiaco": "WA",
    "York Park": "TAS", "Bellerive Oval": "TAS", "North Hobart": "TAS",
    "Traeger Park": "NT", "Marrara Oval": "NT", "TIO Stadium": "NT",
    "Jiangwan Stadium": "OS", "Wellington": "OS",
}
TZ = {"VIC": 10, "NSW": 10, "QLD": 10, "SA": 9.5, "WA": 8, "TAS": 10,
      "ACT": 10, "NT": 9.5, "OS": 8}


def to_long(df):
    """One row per team per match."""
    out = []
    for side, opp in (("home", "away"), ("away", "home")):
        out.append(pd.DataFrame({
            "game_id": df.game_id, "season": df.season, "round": df["round"],
            "date": df.date, "venue": df.venue,
            "team": df[side], "opp": df[opp], "at_home": int(side == "home"),
            "shots": df[f"{side}_shots"], "goals": df[f"{side}_goals"],
            "score": df[f"{side}_score"], "oppShots": df[f"{opp}_shots"],
            "conceded": df[f"{opp}_score"],
        }))
    L = pd.concat(out, ignore_index=True)
    L["margin"] = L.score - L.conceded
    L["shotDiff"] = L.shots - L.oppShots
    return L


# ---------------------------------------------------------------- reliability
# Split each club's season into odd and even matches and correlate the halves.
# This is the measurement that decides how much of each metric to believe.
def reliability(L, metric_fn, seasons):
    a, b = [], []
    for (s, t), g in L[L.season.isin(seasons)].groupby(["season", "team"]):
        g = g.sort_values("date").rename(columns={"round": "rnd"})
        if len(g) < 14: continue
        h1, h2 = g.iloc[::2], g.iloc[1::2]
        va, vb = metric_fn(h1), metric_fn(h2)
        if np.isfinite(va) and np.isfinite(vb): a.append(va); b.append(vb)
    r = float(np.corrcoef(a, b)[0, 1])
    # Spearman-Brown: correct a half-season correlation up to full-season
    return {"half": round(r, 3), "full": round(2 * r / (1 + r), 3), "n": len(a)}


LALL = to_long(m[m.stage == "home_and_away"])
SEASONS = sorted(LALL.season.unique())
REL = {
    "created":  reliability(LALL, lambda g: g.shots.mean(), SEASONS),
    "conceded": reliability(LALL, lambda g: g.oppShots.mean(), SEASONS),
    "accuracy": reliability(LALL, lambda g: g.goals.sum() / max(1, g.shots.sum()), SEASONS),
    "margin":   reliability(LALL, lambda g: g.margin.mean(), SEASONS),
}
print("RELIABILITY (split-half, Spearman-Brown corrected, 2015-2026)")
for k, v in REL.items():
    print(f"  {k:9s} half r={v['half']:+.3f}  full-season r={v['full']:+.3f}  n={v['n']}")

# ------------------------------------------------------------------ this year
ha = m[(m.season == SEASON) & (m.stage == "home_and_away")]
L = to_long(ha)
LEAGUE_ACC = float(L.goals.sum() / L.shots.sum())
PPS = 6 * LEAGUE_ACC + 1 * (1 - LEAGUE_ACC)      # points per scoring shot
print(f"\nleague accuracy {LEAGUE_ACC:.4f} -> {PPS:.3f} points per scoring shot")

L["expScore"] = L.shots * PPS
L["expConceded"] = L.oppShots * PPS
L["expMargin"] = L.shotDiff * PPS
L["kickingPts"] = L.score - L.expScore             # what the boot was worth
L["gotPts"] = np.where(L.margin > 0, 4, np.where(L.margin == 0, 2, 0))
L["deservedPts"] = np.where(L.expMargin > 0, 4, np.where(L.expMargin == 0, 2, 0))
L["stolen"] = (L.gotPts > L.deservedPts)           # won without deserving
L["robbed"] = (L.gotPts < L.deservedPts)           # deserved but lost

# travel and rest, per team per match
L["homeState"] = L.team.map(TEAM_STATE)
L["venueState"] = L.venue.map(VENUE_STATE)
L["interstate"] = (L.homeState != L.venueState).astype(int)
L["tzShift"] = [abs(TZ.get(vs, 10) - TZ.get(hs, 10)) for hs, vs in zip(L.homeState, L.venueState)]
L = L.sort_values(["team", "date"])
L["restDays"] = L.groupby("team")["date"].diff().dt.days
L["shortBreak"] = (L.restDays <= 6).astype(float)

# ------------------------------------------------------------ team aggregates
rows = []
for t, g in L.groupby("team"):
    g = g.sort_values("date").rename(columns={"round": "rnd"})
    n = len(g)
    sos = float(L[L.team.isin(g.opp)].groupby("team").shotDiff.mean().reindex(g.opp).mean())
    last5 = g.tail(5)
    rows.append({
        "team": t, "games": n,
        "won": int((g.margin > 0).sum()), "drawn": int((g.margin == 0).sum()),
        "pts": int(g.gotPts.sum()), "deservedPts": int(g.deservedPts.sum()),
        "created": round(float(g.shots.mean()), 2),
        "conceded": round(float(g.oppShots.mean()), 2),
        "chanceDiff": round(float(g.shotDiff.mean()), 2),
        "accuracy": round(float(g.goals.sum() / g.shots.sum()), 4),
        "pf": round(float(g.score.mean()), 1), "pa": round(float(g.conceded.mean()), 1),
        "pct": round(100 * float(g.score.sum() / g.conceded.sum()), 1),
        "expPf": round(float(g.expScore.mean()), 1),
        "expPa": round(float(g.expConceded.mean()), 1),
        "expPct": round(100 * float(g.expScore.sum() / g.expConceded.sum()), 1),
        "kickingPts": round(float(g.kickingPts.sum()), 0),
        "kickingPtsPG": round(float(g.kickingPts.mean()), 1),
        "stolen": int(g.stolen.sum()), "robbed": int(g.robbed.sum()),
        "consistency": round(float(g.shotDiff.std()), 2),
        "sos": round(sos, 2),
        "form5": round(float(last5.shotDiff.mean()), 2),
        "formDelta": round(float(last5.shotDiff.mean() - g.shotDiff.mean()), 2),
        "closeGames": int((g.margin.abs() <= 12).sum()),
        "closeWon": int(((g.margin.abs() <= 12) & (g.margin > 0)).sum()),
        "trips": int(g.interstate.sum()),
        "tzKm": round(float(g.tzShift.sum()), 1),
        "shortBreaks": int(g.shortBreak.sum()),
        "log": [{
            "rd": int(r.rnd), "opp": r.opp, "h": int(r.at_home),
            "venue": r.venue, "sf": int(r.shots), "sa": int(r.oppShots),
            "pf": int(r.score), "pa": int(r.conceded),
            "exp": round(float(r.expMargin), 1), "act": int(r.margin),
            "trav": int(r.interstate), "rest": (None if pd.isna(r.restDays) else int(r.restDays)),
        } for r in g.itertuples(index=False)],
    })
T = pd.DataFrame([{k: v for k, v in r.items() if k != "log"} for r in rows])

# real ladder = ranked on deserved points, then expected percentage
T["luckPts"] = T.pts - T.deservedPts
T = T.sort_values(["pts", "pct"], ascending=False).reset_index(drop=True)
T["pos"] = T.index + 1
real = T.sort_values(["deservedPts", "expPct"], ascending=False).reset_index(drop=True)
real["realPos"] = real.index + 1
T = T.merge(real[["team", "realPos"]], on="team")
T["move"] = T.pos - T.realPos

print("\nTHE REAL LADDER  (ranked on chances, not on what the ball did)")
print(f"{'':2s} {'club':24s} {'pts':>4s} {'real':>5s} {'luck':>5s} {'move':>5s}  {'chance diff':>11s}")
for r in T.sort_values("realPos").itertuples():
    arrow = "-" if r.move == 0 else (f"up {r.move}" if r.move > 0 else f"down {-r.move}")
    print(f"{r.realPos:2d} {r.team:24s} {r.pts:4d} {r.deservedPts:5d} {r.luckPts:+5d} {arrow:>5s}  {r.chanceDiff:+11.2f}")

out = {
    "season": SEASON, "asAt": "2026-09-19",
    "leagueAcc": round(LEAGUE_ACC, 4), "pps": round(PPS, 3),
    "reliability": REL,
    "teams": [{**{k: v for k, v in r.items() if k != "log"},
               "log": r["log"],
               **T[T.team == r["team"]][["pos", "realPos", "move", "luckPts"]].iloc[0].astype(int).to_dict()}
              for r in rows],
}
with open(f"{ROOT}/outputs/metrics_2026.json", "w") as f:
    json.dump(out, f, separators=(",", ":"))
print(f"\nwrote {ROOT}/outputs/metrics_2026.json "
      f"({len(json.dumps(out, separators=(',',':')))} bytes)")
