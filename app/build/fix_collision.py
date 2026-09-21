"""Namespace the bake-off chain's bracket functions so they stop colliding with
the production chain's versions of the same names.

Renames in R/04_simulate.R (definitions and internal calls) and updates the one
call site in R/99_run_all.R. Backs up both files first.
"""
import re
import shutil
import sys
from pathlib import Path

R = Path(sys.argv[1] if len(sys.argv) > 1 else ".") / "R"
NAMES = ["build_ladder", "home_venues", "known_results",
         "finals_prob_matrix", "simulate_finals", "check_invariants",
         "remaining_fixtures"]

sim = R / "04_simulate.R"
run = R / "99_run_all.R"

# Only rename what 04_simulate.R actually defines.
src = sim.read_text(encoding="utf-8")
defined = [n for n in NAMES if re.search(rf"^{n} *<- *function", src, re.M)]
print("defined in 04_simulate.R:", ", ".join(defined))

for f in (sim, run):
    shutil.copy2(f, f.with_suffix(f.suffix + ".bak"))
    print(f"backed up {f.name} -> {f.name}.bak")

# 04_simulate.R: rename definitions and every internal reference.
for n in defined:
    src = re.sub(rf"(?<![A-Za-z0-9_.]){re.escape(n)}(?![A-Za-z0-9_.])",
                 f"bakeoff_{n}", src)
src = ("# NOTE: every bracket function here is prefixed `bakeoff_` so it cannot\n"
       "# collide with the production chain's versions in 03_simulate.R. Both\n"
       "# chains are sourced into the same environment by 99_run_all.R.\n\n") + src
sim.write_text(src, encoding="utf-8")
print(f"rewrote {sim.name}")

# 99_run_all.R: step 3 validates the ENGINE on the old format, so it must use
# the bake-off versions that match the bake-off model objects it passes in.
txt = run.read_text(encoding="utf-8")
before = txt
txt = txt.replace(
    "    pj <- simulate_finals(fv, build_ladder(m, s), home_venues(m, s), list(),\n"
    "                          n_sims = 5000L, wildcard = FALSE, seed = 1000 + s)\n"
    "    bad <- check_invariants(pj, wildcard = FALSE)",
    "    pj <- bakeoff_simulate_finals(fv, bakeoff_build_ladder(m, s),\n"
    "                                  bakeoff_home_venues(m, s), list(),\n"
    "                                  n_sims = 5000L, wildcard = FALSE, seed = 1000 + s)\n"
    "    bad <- bakeoff_check_invariants(pj, wildcard = FALSE)")
if txt == before:
    print("WARNING: step 3 call site not matched verbatim - patch it by hand")
else:
    run.write_text(txt, encoding="utf-8")
    print(f"rewrote {run.name} step 3 call site")

print("\nRemaining references to the production names in 99_run_all.R:")
for i, L in enumerate(run.read_text(encoding="utf-8").split("\n"), 1):
    if any(re.search(rf"(?<![A-Za-z0-9_.]){n}(?![A-Za-z0-9_.])", L) for n in NAMES):
        print(f"  {i}: {L.strip()}")
