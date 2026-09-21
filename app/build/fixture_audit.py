"""THE FIXTURE AUDIT — is the AFL draw measurably unequal, and by how much?

The AFL plays 23 rounds against 17 opponents, so every club plays 6 opponents
twice and 11 once. Which 6 is decided commercially, for broadcast. Travel is
also uneven by geography: a WA club flies for most away games; a Victorian club
often does not leave Melbourne even when listed away. Clubs complain every year.
The league says the fixture is fair. Nobody publishes a number.

This prices it.

Design. One row per match, margin from the home side's perspective. Team
strength enters as a SIGNED season-specific dummy (+1 home, -1 away), which is
the standard paired ratings design -- it removes the antisymmetry that makes a
long-format fit rank-deficient, and it identifies each fixture cost as a
DIFFERENCE between the two sides. Errors are heteroskedasticity-robust, and the
club-level totals are bootstrapped over matches so the headline numbers carry
intervals rather than false precision.
"""
import json, sys
import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
SEASON = 2026
B = 400                                    # bootstrap replicates

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

m = pd.read_csv(f"{ROOT}/data/processed/matches.csv")
m["date"] = pd.to_datetime(m["date"])
m = m[m.stage == "home_and_away"].copy()
m["venState"] = m.venue.map(VENUE_STATE)
m = m[m.venState.notna()].copy()

# rest days need the long view first
rest = {}
for side in ("home", "away"):
    tmp = m[[f"{side}", "season", "date"]].rename(columns={side: "team"})
    tmp["side"] = side
    rest[side] = tmp
R = pd.concat(rest.values(), ignore_index=True).sort_values(["team", "season", "date"])
R["restDays"] = R.groupby(["team", "season"])["date"].diff().dt.days
restmap = {(r.team, r.date): r.restDays for r in R.itertuples()}

def side_feats(team_col, side):
    st = m[team_col].map(TEAM_STATE)
    travelled = (st != m.venState).astype(float)
    tz = np.array([abs(TZ.get(v, 10) - TZ.get(s, 10)) for s, v in zip(st, m.venState)])
    home_ground = ((side == "home") & (st == m.venState)).astype(float)
    rd = np.array([restmap.get((t, d), np.nan) for t, d in zip(m[team_col], m.date)])
    short = np.where(np.isnan(rd), 0.0, (rd <= 6).astype(float))
    return travelled.values, tz, np.asarray(home_ground, dtype=float), short

hT, hTz, hHG, hS = side_feats("home", "home")
aT, aTz, aHG, aS = side_feats("away", "away")

# ------------------------------------------------------------------ design
teams = sorted(set(m.home) | set(m.away))
seasons = sorted(m.season.unique())
keys = [f"{t}_{s}" for s in seasons for t in teams]
idx = {k: i for i, k in enumerate(keys)}
n, K = len(m), len(keys)

S = np.zeros((n, K))
hk = (m.home + "_" + m.season.astype(str)).values
ak = (m.away + "_" + m.season.astype(str)).values
for i in range(n):
    S[i, idx[hk[i]]] += 1.0
    S[i, idx[ak[i]]] -= 1.0
# one reference team per season, else each season's block is shift-invariant
drop = [idx[f"{teams[0]}_{s}"] for s in seasons]
keep = [j for j in range(K) if j not in drop]
S = S[:, keep]
kept_keys = [keys[j] for j in keep]

FX_NAMES = ["home ground", "travelled", "time-zone hour", "6-day break"]
F = np.column_stack([hHG - aHG, hT - aT, hTz - aTz, hS - aS])
X = np.column_stack([S, F])
y = m.margin.values.astype(float)

fit = sm.OLS(y, X).fit(cov_type="HC1")
p0 = S.shape[1]
beta = fit.params[p0:]
ci = fit.conf_int()[p0:]
pv = fit.pvalues[p0:]

print(f"{n:,} matches, {seasons[0]}-{seasons[-1]}  |  R2 = {fit.rsquared:.3f}")
print(f"home side travelled on {hT.mean()*100:.0f}% of matches; "
      f"away side on {aT.mean()*100:.0f}%")
print("\nWHAT THE FIXTURE IS WORTH  (points of margin, both sides' strength held fixed)")
print(f"{'term':17s} {'effect':>8s} {'95% CI':>18s} {'p':>9s}   verdict")
for i, nm in enumerate(FX_NAMES):
    sig = "real" if pv[i] < 0.05 else "NOT SUPPORTED"
    print(f"{nm:17s} {beta[i]:+8.2f}  [{ci[i][0]:+6.2f},{ci[i][1]:+6.2f}] {pv[i]:9.4f}   {sig}")

wa = beta[1] + 2 * beta[2]
print(f"\na trip to Perth from the eastern states costs {abs(wa):.1f} points "
      f"(travel {abs(beta[1]):.1f} + two time-zone hours {abs(2*beta[2]):.1f})")

# ------------------------------------------- price each club's actual fixture
strength = {k: fit.params[j] for j, k in enumerate(kept_keys)}
for s in seasons:
    strength.setdefault(f"{teams[0]}_{s}", 0.0)

def club_table(bhat, season):
    """Points the fixture handed each club, relative to an average draw."""
    sel = m.season == season
    sub = m[sel]
    hgd, td, tzd, sd = (hHG - aHG)[sel.values], (hT - aT)[sel.values], \
                       (hTz - aTz)[sel.values], (hS - aS)[sel.values]
    rec = {t: {"burden": 0.0, "opp": 0.0, "g": 0, "trips": 0, "tz": 0.0, "short": 0}
           for t in teams}
    hh, aa = sub.home.values, sub.away.values
    for i in range(len(sub)):
        # fixture burden, signed to each side
        b = bhat[0] * hgd[i] + bhat[1] * td[i] + bhat[2] * tzd[i] + bhat[3] * sd[i]
        rec[hh[i]]["burden"] += b;  rec[aa[i]]["burden"] -= b
        rec[hh[i]]["opp"] -= strength.get(f"{aa[i]}_{season}", 0.0)
        rec[aa[i]]["opp"] -= strength.get(f"{hh[i]}_{season}", 0.0)
        rec[hh[i]]["g"] += 1; rec[aa[i]]["g"] += 1
    return rec

base = club_table(beta, SEASON)
sel = (m.season == SEASON).values
for i, (h, a) in enumerate(zip(m.home[sel], m.away[sel])):
    pass
# raw counts for display
cnt = {t: {"trips": 0, "tz": 0.0, "short": 0, "homeG": 0} for t in teams}
sub = m[m.season == SEASON]
for i, gi in enumerate(np.where(sel)[0]):
    h, a = m.home.values[gi], m.away.values[gi]
    cnt[h]["trips"] += int(hT[gi]); cnt[h]["tz"] += hTz[gi]
    cnt[h]["short"] += int(hS[gi]); cnt[h]["homeG"] += int(hHG[gi])
    cnt[a]["trips"] += int(aT[gi]); cnt[a]["tz"] += aTz[gi]
    cnt[a]["short"] += int(aS[gi]); cnt[a]["homeG"] += int(aHG[gi])

mb = np.mean([v["burden"] for v in base.values()])
mo = np.mean([v["opp"] for v in base.values()])
rows = []
for t in teams:
    v = base[t]
    rows.append({"team": t, "games": v["g"],
                 "travelRest": v["burden"] - mb,
                 "opponents": v["opp"] - mo,
                 "total": (v["burden"] - mb) + (v["opp"] - mo), **cnt[t]})

# ------------------------------------------------------------- bootstrap CI
rng = np.random.default_rng(11)
boot = {t: [] for t in teams}
for _ in range(B):
    pick = rng.integers(0, n, n)
    try:
        bfit = np.linalg.lstsq(X[pick], y[pick], rcond=None)[0]
    except np.linalg.LinAlgError:
        continue
    bb = bfit[p0:]
    st = {k: bfit[j] for j, k in enumerate(kept_keys)}
    for s in seasons: st.setdefault(f"{teams[0]}_{s}", 0.0)
    r = {t: 0.0 for t in teams}
    hgd, td, tzd, sd = (hHG - aHG)[sel], (hT - aT)[sel], (hTz - aTz)[sel], (hS - aS)[sel]
    hh, aa = sub.home.values, sub.away.values
    for i in range(len(sub)):
        b = bb[0] * hgd[i] + bb[1] * td[i] + bb[2] * tzd[i] + bb[3] * sd[i]
        r[hh[i]] += b - st.get(f"{aa[i]}_{SEASON}", 0.0)
        r[aa[i]] -= b + st.get(f"{hh[i]}_{SEASON}", 0.0)
    mu = np.mean(list(r.values()))
    for t in teams: boot[t].append(r[t] - mu)

for row in rows:
    q = np.percentile(boot[row["team"]], [2.5, 97.5])
    row["lo"], row["hi"] = float(q[0]), float(q[1])
    row["perGame"] = row["total"] / row["games"]

rows.sort(key=lambda r: r["total"])
print(f"\nFIXTURE EQUITY {SEASON} — points the draw handed each club vs an average one")
print(f"{'club':24s} {'trips':>5s} {'tz':>4s} {'6day':>5s} {'travel':>8s} "
      f"{'oppts':>8s} {'TOTAL':>8s}  95% interval")
for r in rows:
    print(f"{r['team']:24s} {r['trips']:5d} {r['tz']:4.0f} {r['short']:5d} "
          f"{r['travelRest']:+8.1f} {r['opponents']:+8.1f} {r['total']:+8.1f}"
          f"  [{r['lo']:+6.1f}, {r['hi']:+6.1f}]")

spread = rows[-1]["total"] - rows[0]["total"]
gm = rows[0]["games"]
print(f"\nSPREAD: {spread:.0f} points of margin across {gm} matches between the "
      f"best and worst draw\n        = {spread/gm:.1f} points per match, and roughly "
      f"{spread/ (2*abs(beta[0])):.1f} home-ground advantages of difference")

out = {"season": SEASON, "nMatches": int(n), "r2": round(float(fit.rsquared), 4),
       "effects": [{"name": FX_NAMES[i], "beta": round(float(beta[i]), 2),
                    "lo": round(float(ci[i][0]), 2), "hi": round(float(ci[i][1]), 2),
                    "p": float(pv[i]), "sig": bool(pv[i] < 0.05)} for i in range(4)],
       "perthTrip": round(float(abs(wa)), 1),
       "clubs": [{k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items()}
                 for r in rows],
       "spread": round(float(spread), 1), "perGame": round(float(spread / gm), 2)}
with open(f"{ROOT}/outputs/fixture_equity.json", "w") as f:
    json.dump(out, f, indent=1)
print(f"\nwrote {ROOT}/outputs/fixture_equity.json")
