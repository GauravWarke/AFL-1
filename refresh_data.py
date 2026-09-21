#!/usr/bin/env python3
"""Refresh match data from the Squiggle API.

This is the LIVE data step for the R pipeline, not legacy code. The fetcher
happens to live under legacy-python/src/ because it shares the sportspred
config module with the old Python analysis.

    python3 refresh_data.py            # all seasons (safe, ~3 min, cached)
    python3 refresh_data.py --current  # 2026 only, force re-fetch

WARNING: do not call ingest_afl.py with `--seasons 2026` directly. It REBUILDS
data/processed/matches.csv from only the seasons named, so a single-season call
silently drops 2015-2025 and leaves the model with no history to weight against.
--current below always rebuilds the full table afterwards.
"""
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "legacy-python" / "src"
ING = SRC / "ingest_afl.py"

def run(args):
    return subprocess.call([sys.executable, str(ING)] + args,
                           env={**__import__("os").environ, "PYTHONPATH": str(SRC)})

if __name__ == "__main__":
    if "--current" in sys.argv:
        # refresh this season's cache, then rebuild the FULL table
        run(["--seasons", "2026", "--refresh"])
        code = run(["--seasons", "2015-2026"])
    else:
        code = run(["--seasons", "2015-2026"])
    sys.exit(code)
