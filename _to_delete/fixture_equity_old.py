"""Is the AFL fixture measurably unequal, and by how much?

The AFL plays 23 rounds against 17 opponents, so every club plays 6 opponents
twice and 11 once. Which 6 is decided commercially. Travel is also wildly
uneven: a WA club flies for most away games, a Victorian club often does not
leave Melbourne. The league asserts the fixture is fair. Nobody arbitrates it
with a number.

This measures the three structural costs a club has no control over -- travel,
time-zone shift, and the short turnaround -- and then prices each club's actual
draw against a balanced one, in ladder points.
"""
import json, sys
import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
m = pd.read_csv(f"{ROOT}/data/processed/matches.csv")
m["date"] = pd.to_datetime(m["date"])
m = m[m.stage == "home_and_away"].copy()

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

rows = []
for side, opp in (("home", "away"), ("away", "home")):
    rows.append(pd.DataFrame({
        "season": m.season, "round": m["round"], "date": m.date, "venue": m.venue,
        "team": m[side], "opp": m[opp], "listed_home": int(side == "home"),
        "shots": m[f"{side}_shots"], "oppShots": m[f"{opp}_shots"],
        "score": m[f"{side}_score"], "conceded": m[f"{opp}_score"],
    }))
L = pd.concat(rows, ignore_index=True)
L["teamState"] = L.team.map(TEAM_STATE)
L["venState"] = L.venue.map(VENUE_STATE)
L = L[L.venState.notna()].copy()

# TRAVELLED is not the same as "away". Ten Victorian clubs share Melbourne
# grounds, so a Victorian playing a Victorian at the MCG travels nowhere
# regardless of who is listed at home. This distinction is the whole point.
L["travelled"] = (L.teamState != L.venState).astype(float)
L["tz"] = [abs(TZ.get(v, 10) - TZ.get(t, 10)) for t, v in zip(L.teamState, L.venState)]
L["homeGround"] = ((L.listed_home == 1) & (L.teamState == L.venState)).astype(float)
L = L.sort_values(["team", "season", "date"])
L["restDays"] = L.groupby(["team", "season"])["date"].diff().dt.days
L["short"] = ((L.restDays <= 6) & L.restDays.notna()).astype(float)
L["margin"] = L.score - L.conceded
L["shotDiff"] = L.shots - L.oppShots

print(f"{len(L):,} team-matches, {L.season.min()}-{L.season.max()}")
print(f"travelled on {L.travelled.mean()*100:.1f}% of matches; "
      f"short break on {L['short'].mean()*100:.1f}%")

# --------------------------------------------------------------- the model
# Margin ~ own strength + opponent strength + the three fixture costs.
# Team strength is a per-season fixed effect, so the fixture terms are
# identified off variation WITHIN a club's own season.
L["ts"] = L.team + "_" + L.season.astype(str)
L["os"] = L.opp + "_" + L.season.astype(str)
X = pd.get_dummies(L.ts, prefix="t", drop_first=True).astype(float)
Xo = pd.get_dummies(L.os, prefix="o", drop_first=True).astype(float)
X = pd.concat([X, Xo], axis=1)
X["homeGround"] = L.homeGround.values
X["travelled"] = L.travelled.values
X["tz"] = L.tz.values
X["short"] = L["short"].values
X = sm.add_constant(X)

res = sm.OLS(L.margin.values, X.values).fit(cov_type="HC1")
names = list(X.columns)
def eff(n):
    i = names.index(n)
    return res.params[i], res.bse[i], res.pvalues[i], res.conf_int()[i]

print("\nFIXTURE COSTS  (points of margin, opponent and own strength held fixed)")
print(f"{'term':14s} {'effect':>8s} {'se':>6s} {'95% CI':>18s} {'p':>8s}")
FX = {}
for n, lab in [("homeGround", "home ground"), ("travelled", "travelled"),
               ("tz", "per tz hour"), ("short", "6-day break")]:
    b, se, p, ci = eff(n)
    FX[n] = b
    print(f"{lab:14s} {b:+8.2f} {se:6.2f}  [{ci[0]:+6.2f},{ci[1]:+6.2f}] {p:8.4f}")

# --------------------------------------------- price each club's actual draw
# A club's fixture burden = the sum of the structural costs it was handed,
# versus what an average club carried that season.
L["burden"] = (FX["travelled"] * L.travelled + FX["tz"] * L.tz
               + FX["short"] * L["short"] + FX["homeGround"] * L.homeGround)

# opponent quality actually faced, from the same fit
opp_str = {}
for n in names:
    if n.startswith("o_"):
        opp_str[n[2:]] = res.params[names.index(n)]
season_mean = {}
for s in sorted(L.season.unique()):
    vals = [v for k, v in opp_str.items() if k.endswith(f"_{s}")]
    season_mean[s] = np.mean(vals) if vals else 0.0
L["oppQ"] = [opp_str.get(o, season_mean[s]) - season_mean[s]
             for o, s in zip(L.os, L.season)]

SEASON = 2026
cur = L[L.season == SEASON]
g = cur.groupby("team").agg(games=("margin", "size"), burden=("burden", "sum"),
                            oppQ=("oppQ", "sum"), trips=("travelled", "sum"),
                            tz=("tz", "sum"), short=("short", "sum"),
                            homeG=("homeGround", "sum"))
g["burdenVsAvg"] = g.burden - g.burden.mean()
# opponent quality faced: a NEGATIVE opponent coefficient means the opponent is
# strong (they suppress your margin), so facing strong sides is a cost.
g["drawVsAvg"] = g.oppQ - g.oppQ.mean()
g["totalPts"] = g.burdenVsAvg + g.drawVsAvg
g["perGame"] = g.totalPts / g.games

print(f"\nFIXTURE EQUITY {SEASON}  (points of margin over the season vs an average draw)")
print(f"{'club':24s} {'trips':>5s} {'tzhrs':>5s} {'6day':>4s} {'travel+rest':>11s} "
      f"{'opponents':>9s} {'TOTAL':>7s} {'/game':>6s}")
for t, r in g.sort_values("totalPts").iterrows():
    print(f"{t:24s} {r.trips:5.0f} {r.tz:5.0f} {r['short']:4.0f} "
          f"{r.burdenVsAvg:+11.1f} {r.drawVsAvg:+9.1f} {r.totalPts:+7.1f} {r.perGame:+6.2f}")

spread = g.totalPts.max() - g.totalPts.min()
print(f"\nspread between the best and worst draw: {spread:.1f} points of margin "
      f"over {int(g.games.mean())} matches")
print(f"that is {spread/int(g.games.mean()):.2f} points per match between the "
      f"most and least favoured club")

out = {"effects": {k: round(float(v), 3) for k, v in FX.items()},
       "ci": {n: [round(float(eff(n)[3][0]), 3), round(float(eff(n)[3][1]), 3)]
              for n in FX},
       "p": {n: float(eff(n)[2]) for n in FX},
       "n": int(len(L)),
       "season": SEASON,
       "clubs": [{"team": t, "trips": int(r.trips), "tz": float(r.tz),
                  "short": int(r['short']), "homeG": int(r.homeG),
                  "travelRest": round(float(r.burdenVsAvg), 1),
                  "opponents": round(float(r.drawVsAvg), 1),
                  "total": round(float(r.totalPts), 1),
                  "perGame": round(float(r.perGame), 2)}
                 for t, r in g.sort_values("totalPts").iterrows()]}
with open(f"{ROOT}/outputs/fixture_equity.json", "w") as f:
    json.dump(out, f, indent=1)
print(f"\nwrote {ROOT}/outputs/fixture_equity.json")
