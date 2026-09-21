"""SEPTEMBER, LEVELLED — the same lens applied to the finals series.

Every final, with the margin the chances earned set against the margin that
actually went up on the board. Finals won by the side that created fewer shots
are the ones the boot decided rather than the football.
"""
import json, sys
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/claude/proj")
from realtime import fit_shots, predict  # noqa

ROOT = "."
m = pd.read_csv(f"{ROOT}/data/processed/matches.csv")
S = 2026
ha = m[(m.season == S) & (m.stage == "home_and_away")]
LG = float((ha.home_goals.sum() + ha.away_goals.sum()) /
           (ha.home_shots.sum() + ha.away_shots.sum()))
PPS = 6 * LG + (1 - LG)

fin = m[(m.season == S) & (m.stage != "home_and_away")].sort_values("date")
NAME = {"wildcard_final": "Wildcard", "qualifying_final": "Qualifying",
        "elimination_final": "Elimination", "semi_final": "Semi",
        "preliminary_final": "Preliminary", "grand_final": "Grand Final"}

rows = []
for g in fin.itertuples():
    earned = (g.home_shots - g.away_shots) * PPS
    winner = g.home if g.margin > 0 else g.away
    deserved = g.home if earned > 0 else g.away
    rows.append(dict(
        date=str(g.date)[:10], stage=NAME.get(g.stage, g.stage),
        home=g.home, away=g.away,
        hg=int(g.home_goals), hb=int(g.home_behinds), hs=int(g.home_score),
        ag=int(g.away_goals), ab=int(g.away_behinds), aslot=int(g.away_score),
        hsh=int(g.home_shots), ash=int(g.away_shots),
        act=int(g.margin), earned=round(float(earned), 1),
        winner=winner, deserved=deserved,
        onBoot=bool(winner != deserved)))
F = pd.DataFrame(rows)

boot = int(F.onBoot.sum())
print(f"league accuracy {LG:.4f} -> {PPS:.3f} pts per scoring shot\n")
print(f"{'date':11s} {'stage':13s} {'match':44s} {'shots':>9s} {'actual':>7s} {'earned':>7s}  decided by")
for r in F.itertuples():
    mt = f"{r.home} {r.hs} d {r.aslot} {r.away}" if r.act > 0 else f"{r.away} {r.aslot} d {r.hs} {r.home}"
    print(f"{r.date:11s} {r.stage:13s} {mt:44s} {r.hsh:4d}-{r.ash:<4d} "
          f"{r.act:+7d} {r.earned:+7.1f}  {'THE BOOT' if r.onBoot else 'the football'}")

print(f"\n{boot} of {len(F)} finals were won by the side that created FEWER scoring shots.")
print(f"that is {boot/len(F)*100:.0f}% of September decided by conversion, not chance creation.")

# --- the Grand Final, levelled -------------------------------------------
par = fit_shots(m[m.stage == 'home_and_away'])   # same training set as the rest of the system
GF_H, GF_A = "Fremantle", "Brisbane Lions"   # MCG, neither side at home
pr = predict(par, GF_H, GF_A, home_adv=False, nsim=60000)

lf = json.load(open(f"{ROOT}/outputs/level_field.json"))
club = {c["team"]: c for c in lf["clubs"]}
h, a = club[GF_H], club[GF_A]

def sl(pts, goals):
    g = round(goals); return {"g": g, "b": max(0, round(pts) - g * 6), "pts": round(pts)}

print(f"\nGRAND FINAL  {GF_H} v {GF_A}  |  M.C.G., 26 September, neutral")
print(f"  model: {GF_H} {pr['prob']*100:.1f}%   {GF_A} {(1-pr['prob'])*100:.1f}%")
print(f"  projected {sl(pr['hPts'],pr['hG'])['g']}.{sl(pr['hPts'],pr['hG'])['b']} ({round(pr['hPts'])})"
      f" v {sl(pr['aPts'],pr['aG'])['g']}.{sl(pr['aPts'],pr['aG'])['b']} ({round(pr['aPts'])})")
for c in (h, a):
    print(f"  {c['team']:16s} ladder {c['posActual']:2d}  levelled {c['posLevel']:2d}  "
          f"draw worth {c['drawPts']:+6.1f}")

out = dict(
    pps=round(PPS, 3), leagueAcc=round(LG, 4),
    finals=rows, bootWins=boot, nFinals=len(F),
    gf=dict(home=GF_H, away=GF_A, venue="M.C.G.", when="26 September",
            p=round(pr["prob"], 4), margin=round(pr["margin"], 1),
            hLine=sl(pr["hPts"], pr["hG"]), aLine=sl(pr["aPts"], pr["aG"]),
            hShots=round(pr["hShots"], 1), aShots=round(pr["aShots"], 1),
            homePos=h["posActual"], homeLevel=h["posLevel"], homeDraw=h["drawPts"],
            awayPos=a["posActual"], awayLevel=a["posLevel"], awayDraw=a["drawPts"]))
json.dump(out, open(f"{ROOT}/outputs/september.json", "w"), separators=(",", ":"))
print(f"\nwrote outputs/september.json")
