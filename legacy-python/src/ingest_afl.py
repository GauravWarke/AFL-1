"""Fetch AFL match results from the Squiggle API and build the match table.

Squiggle (https://api.squiggle.com.au) is the public API behind squiggle.com.au,
which aggregates AFL tipping models. It is the same underlying data fitzRoy
reads, but as JSON rather than scraped HTML, so it is far less brittle.

The API asks callers to identify themselves in the User-Agent header. That is a
condition of use, not a suggestion — set IDENTITY below to your own contact.

Usage
-----
    python src/ingest_afl.py --seasons 2015-2026

Writes
------
    data/raw/games_<year>.json     one file per season, cached
    data/processed/matches.csv     one row per match, both teams' figures
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

from sportspred import config

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"

API = "https://api.squiggle.com.au/"
IDENTITY = "afl-season-predictor (student project; gauravwarke8@gmail.com)"

# Squiggle's is_final codes. Confirmed against the 2026 fixture rather than
# assumed: round 26 contained Fremantle(1) v Hawthorn(4) and Sydney(2) v
# Brisbane(3) coded 3, and Geelong(5) v Carlton(8) and Adelaide(6) v
# Bulldogs(7) coded 2. Under the AFL final-eight system the 1v4 and 2v3
# matches are the qualifying finals, so 3 = qualifying and 2 = elimination.
FINAL_TYPES = {
    0: "home_and_away",
    2: "elimination_final",
    3: "qualifying_final",
    4: "semi_final",
    5: "preliminary_final",
    6: "grand_final",
    7: "wildcard_final",
}


def _get(params: str, tries: int = 3) -> dict:
    url = f"{API}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": IDENTITY})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def fetch_season(year: int, refresh: bool = False) -> list[dict]:
    """One season of matches.

    Fetched round by round rather than in one call. A whole season in a single
    response is large enough that some HTTP clients truncate it, and a
    truncated JSON array is the kind of failure that produces a plausible but
    incomplete dataset rather than an error.
    """
    RAW.mkdir(parents=True, exist_ok=True)
    cache = RAW / f"games_{year}.json"
    if cache.exists() and not refresh:
        return json.loads(cache.read_text())

    games: list[dict] = []
    seen: set[int] = set()
    empty_streak = 0
    for rnd in range(0, 31):
        batch = _get(f"q=games;year={year};round={rnd}").get("games", [])
        if not batch:
            empty_streak += 1
            # Round 0 (Opening Round) does not exist before 2024, and rounds
            # past the grand final never do. Two consecutive empties after
            # we have started collecting means the season is done.
            if empty_streak >= 2 and games:
                break
            continue
        empty_streak = 0
        for g in batch:
            if g["id"] not in seen:
                seen.add(g["id"])
                games.append(g)
        time.sleep(0.25)  # be polite to a free community API

    cache.write_text(json.dumps(games))
    return games


def to_matches(games: list[dict], cfg=config.AFL) -> pd.DataFrame:
    """Long-form match table with scoring shots derived."""
    rows = []
    for g in games:
        if g.get("complete") != 100:
            continue
        hg, hb = g.get("hgoals"), g.get("hbehinds")
        ag, ab = g.get("agoals"), g.get("abehinds")
        if None in (hg, hb, ag, ab):
            continue

        # Reconcile the stated score against goals and behinds. Squiggle is
        # reliable, but this is a free check on a decoding assumption that
        # everything downstream depends on, so it is worth making.
        if hg * cfg.points_per_goal + hb != g["hscore"]:
            raise ValueError(f"score mismatch in game {g['id']}: home")
        if ag * cfg.points_per_goal + ab != g["ascore"]:
            raise ValueError(f"score mismatch in game {g['id']}: away")

        rows.append(
            dict(
                game_id=g["id"],
                season=g["year"],
                round=g["round"],
                round_name=g.get("roundname"),
                stage=FINAL_TYPES.get(g.get("is_final", 0), "final_other"),
                date=g["date"],
                venue=g["venue"],
                home=cfg.aliases.get(g["hteam"], g["hteam"]),
                away=cfg.aliases.get(g["ateam"], g["ateam"]),
                home_goals=hg,
                home_behinds=hb,
                away_goals=ag,
                away_behinds=ab,
                home_score=g["hscore"],
                away_score=g["ascore"],
            )
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # --- the AFL-specific derivations ------------------------------------
    # A scoring shot is any shot that reached the goal line: a goal or a
    # behind. It measures how often a team got into a scoring position.
    # Accuracy is how often those shots were converted into goals.
    df["home_shots"] = df.home_goals + df.home_behinds
    df["away_shots"] = df.away_goals + df.away_behinds
    df["home_accuracy"] = df.home_goals / df.home_shots
    df["away_accuracy"] = df.away_goals / df.away_shots

    df["margin"] = df.home_score - df.away_score          # home perspective
    df["shot_margin"] = df.home_shots - df.away_shots
    df["is_draw"] = df.margin == 0
    df["date"] = pd.to_datetime(df.date)
    return df.sort_values(["season", "round", "date"]).reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", default="2015-2026",
                    help="e.g. 2015-2026 or 2026")
    ap.add_argument("--refresh", action="store_true",
                    help="ignore the on-disk cache")
    a = ap.parse_args()

    if "-" in a.seasons:
        lo, hi = (int(x) for x in a.seasons.split("-"))
        years = range(lo, hi + 1)
    else:
        years = [int(a.seasons)]

    all_games: list[dict] = []
    for y in years:
        g = fetch_season(y, refresh=a.refresh)
        print(f"  {y}: {len(g):>4} games")
        all_games.extend(g)

    df = to_matches(all_games)
    PROC.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROC / "matches.csv", index=False)
    print(f"\nwrote {len(df)} completed matches -> data/processed/matches.csv")
    print(f"seasons {df.season.min()}-{df.season.max()}, "
          f"{df.venue.nunique()} venues, {df.is_draw.sum()} draws")


if __name__ == "__main__":
    main()
