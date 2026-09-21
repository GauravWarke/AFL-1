"""THE LEVEL PLAYING FIELD LADDER.

Three ladders, one screen.

  1. ACTUAL      what the AFL publishes.
  2. EARNED      re-decide every match on scoring shots, everyone kicking at the
                 league rate. Removes goal-kicking luck, which does not repeat.
  3. LEVEL       also remove the fixture: the travel each club was handed, and
                 the strength of the opponents it was drawn to play twice.

Nobody publishes 3. Clubs argue about the draw every October with anecdotes;
the league says it is fair; there is no number. This is the number.
"""
import json, sys
import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
SEASON = 2026

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
    "Mars Stadium": "VIC", "Eureka": "VIC", "Adelaide Oval": "SA",
    "Football Park": "SA", "Norwood Oval": "SA", "Summit Sports Park": "SA",
    "Barossa Park": "SA", "Gabba": "QLD", "Carrara": "QLD",
    "Cazaly's Stadium": "QLD", "Riverway Stadium": "QLD", "Metricon Stadium": "QLD",
    "S.C.G.": "NSW", "Sydney Showground": "NSW", "Blacktown": "NSW",
    "Stadium Australia": "NSW", "Manuka Oval": "ACT", "Perth Stadium": "WA",
    "Subiaco": "WA", "York Park": "TAS", "Bellerive Oval": "TAS",
    "North Hobart": "TAS", "Traeger Park": "NT", "Marrara Oval": "NT",
    "TIO Stadium": "NT", "Jiangwan Stadium": "OS", "Wellington": "OS",
}
TZ = {"VIC": 10, "NSW": 10, "QLD": 10, "SA": 9.5, "WA": 8, "TAS": 10,
      "ACT": 10, "NT": 9.5, "OS": 8}

m = pd.read_csv(f"{ROOT}/data/processed/matches.csv")
m["date"] = pd.to_datetime(m["date"])
m = m[m.stage == "home_and_away"].copy()
m["venState"] = m.venue.map(VENUE_STATE)
m = m[m.venState.notna()].reset_index(drop=True)

# rest days
R = pd.concat([m[[s, "season", "date"]].rename(columns={s: "team"}) for s in ("home", "away")],
              ignore_index=True).sort_values(["team", "season", "date"])
R["rd"] = R.groupby(["team", "season"])["date"].diff().dt.days
restmap = {(r.team, r.date): r.rd for r in R.itertuples()}

def feats(col, side):
    st = m[col].map(TEAM_STATE)
    trav = (st != m.venState).astype(float).values
    tz = np.array([abs(TZ.get(v, 10) - TZ.get(s, 10)) for s, v in zip(st, m.venState)])
    hg = np.asarray(((side == "home") & (st == m.venState)).astype(float))
    rd = np.array([restmap.get((t, d), np.nan) for t, d in zip(m[col], m.date)])
    sh = np.where(np.isnan(rd), 0.0, (rd <= 6).astype(float))
    return trav, tz, hg, sh

hT, hTz, hHG, hS = feats("home", "home")
aT, aTz, aHG, aS = feats("away", "away")

# ---- paired ratings design: signed team-season dummies -----------------------
teams = sorted(set(m.home) | set(m.away)); seasons = sorted(m.season.unique())
keys = [f"{t}_{s}" for s in seasons for t in teams]; idx = {k: i for i, k in enumerate(keys)}
n = len(m); S = np.zeros((n, len(keys)))
hk = (m.home + "_" + m.season.astype(str)).values
ak = (m.away + "_" + m.season.astype(str)).values
for i in range(n):
    S[i, idx[hk[i]]] += 1.0; S[i, idx[ak[i]]] -= 1.0
drop = {idx[f"{teams[0]}_{s}"] for s in seasons}
keep = [j for j in range(len(keys)) if j not in drop]
S = S[:, keep]; kept = [keys[j] for j in keep]

F = np.column_stack([hHG - aHG, hT - aT, hTz - aTz, hS - aS])
X = np.column_stack([S, F])
fit = sm.OLS(m.margin.values.astype(float), X).fit(cov_type="HC1")
p0 = S.shape[1]; beta = fit.params[p0:]; ci = fit.conf_int()[p0:]; pv = fit.pvalues[p0:]
NAMES = ["home ground", "travelled", "time-zone hour", "6-day break"]
print(f"{n:,} matches, {seasons[0]}-{seasons[-1]}, R2={fit.rsquared:.3f}")
for i, nm in enumerate(NAMES):
    print(f"  {nm:16s} {beta[i]:+6.2f}  [{ci[i][0]:+6.2f},{ci[i][1]:+6.2f}]  p={pv[i]:.4f}"
          f"   {'REAL' if pv[i] < .05 else 'not supported'}")

strength = {k: fit.params[j] for j, k in enumerate(kept)}
for s in seasons: strength.setdefault(f"{teams[0]}_{s}", 0.0)

# ---- per-match fixture burden, signed to each side --------------------------
# Only terms the data supports are applied. Applying an insignificant coefficient
# would be dressing noise up as an adjustment.
use = np.array([1.0 if pv[i] < 0.05 else 0.0 for i in range(4)])
bal = beta * use
burden_home = bal[0]*(hHG-aHG) + bal[1]*(hT-aT) + bal[2]*(hTz-aTz) + bal[3]*(hS-aS)
print(f"\napplying only: {', '.join(NAMES[i] for i in range(4) if use[i])}")

# ---- this season ------------------------------------------------------------
cur = m[m.season == SEASON].reset_index(drop=True)
cmask = (m.season == SEASON).values
bh = burden_home[cmask]

lg_acc = float((m[m.season == SEASON].home_goals.sum() + m[m.season == SEASON].away_goals.sum()) /
               (m[m.season == SEASON].home_shots.sum() + m[m.season == SEASON].away_shots.sum()))
PPS = 6*lg_acc + (1-lg_acc)
print(f"league accuracy {lg_acc:.4f} -> {PPS:.3f} points per scoring shot")

rec = {t: dict(actual=0, earned=0, level=0, g=0, burden=0.0, opp=0.0,
               trips=0, tz=0.0, short=0) for t in teams}
detail = {t: [] for t in teams}
for i, r in cur.iterrows():
    h, a = r.home, r.away
    act = r.margin
    earned = (r.home_shots - r.away_shots) * PPS          # kicking luck removed
    level = earned - bh[i]                                # fixture removed too
    for team, sign in ((h, 1), (a, -1)):
        rec[team]["g"] += 1
        rec[team]["actual"] += 4 if act*sign > 0 else (2 if act == 0 else 0)
        rec[team]["earned"] += 4 if earned*sign > 0 else (2 if earned == 0 else 0)
        rec[team]["level"]  += 4 if level*sign > 0 else (2 if level == 0 else 0)
        rec[team]["burden"] += bh[i]*sign
        rec[team]["opp"]    -= strength.get(f"{a if team==h else h}_{SEASON}", 0.0)
    gi = m.index[cmask][i]
    rec[h]["trips"] += int(hT[gi]); rec[h]["tz"] += hTz[gi]; rec[h]["short"] += int(hS[gi])
    rec[a]["trips"] += int(aT[gi]); rec[a]["tz"] += aTz[gi]; rec[a]["short"] += int(aS[gi])
    detail[h].append(dict(opp=a, h=1, act=float(act), earned=float(earned),
                          level=float(level), burden=float(bh[i])))
    detail[a].append(dict(opp=h, h=0, act=float(-act), earned=float(-earned),
                          level=float(-level), burden=float(-bh[i])))

mb = np.mean([v["burden"] for v in rec.values()])
mo = np.mean([v["opp"] for v in rec.values()])
rows = []
for t in teams:
    v = rec[t]
    rows.append(dict(team=t, games=v["g"], actual=v["actual"], earned=v["earned"],
                     level=v["level"], trips=v["trips"], tz=v["tz"], short=v["short"],
                     travelPts=round(v["burden"]-mb, 1), oppPts=round(v["opp"]-mo, 1),
                     drawPts=round((v["burden"]-mb)+(v["opp"]-mo), 1)))
Tb = pd.DataFrame(rows)
for col, nm in (("actual", "posActual"), ("earned", "posEarned"), ("level", "posLevel")):
    Tb[nm] = Tb[col].rank(ascending=False, method="first").astype(int)
Tb["swing"] = Tb.posActual - Tb.posLevel

print(f"\nTHREE LADDERS {SEASON}")
print(f"{'club':24s} {'ACT':>4s} {'EARN':>5s} {'LEVEL':>6s} | {'pos':>3s}{'>':>2s}{'pos':>4s} "
      f"{'swing':>6s} | {'draw pts':>9s}")
for r in Tb.sort_values("posLevel").itertuples():
    sw = "-" if r.swing == 0 else (f"up {r.swing}" if r.swing > 0 else f"down {-r.swing}")
    print(f"{r.team:24s} {r.actual:4d} {r.earned:5d} {r.level:6d} | "
          f"{r.posActual:3d} {'->':>2s} {r.posLevel:3d} {sw:>7s} | {r.drawPts:+9.1f}")

eight_a = set(Tb.sort_values("posActual").team[:8])
eight_l = set(Tb.sort_values("posLevel").team[:8])
print(f"\nFINALS EIGHT changes by {len(eight_a - eight_l)} club(s):")
print(f"  out: {', '.join(sorted(eight_a - eight_l)) or 'none'}")
print(f"  in : {', '.join(sorted(eight_l - eight_a)) or 'none'}")

spread = Tb.drawPts.max() - Tb.drawPts.min()
sigma = float(np.std(m[m.season == SEASON].margin))
print(f"\ndraw spread {spread:.0f} pts of margin over {int(Tb.games.mean())} matches")
print(f"match-to-match sd {sigma:.1f} -> the draw is worth roughly "
      f"{spread/int(Tb.games.mean())/sigma*23*0.4:.1f} wins across a season")

out = dict(season=SEASON, nMatches=int(n), r2=round(float(fit.rsquared), 4),
           pps=round(PPS, 3), leagueAcc=round(lg_acc, 4),
           effects=[dict(name=NAMES[i], beta=round(float(beta[i]), 2),
                         lo=round(float(ci[i][0]), 2), hi=round(float(ci[i][1]), 2),
                         p=float(pv[i]), sig=bool(pv[i] < .05)) for i in range(4)],
           applied=[NAMES[i] for i in range(4) if use[i]],
           spread=round(float(spread), 1),
           clubs=[{k: (float(v) if isinstance(v, (np.floating,)) else
                       int(v) if isinstance(v, (np.integer,)) else v)
                   for k, v in r._asdict().items() if k != "Index"}
                  for r in Tb.itertuples()],
           detail={t: detail[t] for t in teams})
with open(f"{ROOT}/outputs/level_field.json", "w") as f:
    json.dump(out, f, separators=(",", ":"))
print(f"\nwrote {ROOT}/outputs/level_field.json "
      f"({len(json.dumps(out, separators=(',',':')))} bytes)")
