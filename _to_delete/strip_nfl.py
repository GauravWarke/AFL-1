"""Remove every NFL reference from the project.

Deletes the NFL SportConfig object outright and rewrites the comparative
comments so they stand on their own AFL terms rather than pointing at a sibling
project that is not part of this repo.
"""
import re, shutil, sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")

EDITS = {
"legacy-python/src/sportspred/config.py": [
 ("""This is the seam that lets one engine serve both the NFL project and this one.
Everything the ratings model and bracket simulator need to know about a sport
lives here as data, so adding a third sport means adding a SportConfig, not
editing the model.

The NFL numbers are carried over from nfl-season-predictor so the two projects
can be compared directly; they are documented there and are not re-derived here.
""",
  """Everything the ratings model and bracket simulator need to know about the
competition lives here as data rather than in the model, so a rule change means
editing a value, not the estimator.
"""),
 ("""    # Ladder points. The AFL awards 4 for a win and 2 for a draw; the NFL
    # counts wins directly. Kept explicit so the standings code is shared.""",
  """    # Ladder points: the AFL awards 4 for a win and 2 for a draw. Kept
    # explicit rather than hard-coded so the standings code stays readable."""),
 ("""    # How teams are ranked once competition points are equal. The AFL uses
    # PERCENTAGE = 100 * points_for / points_against, which is a RATIO. The NFL
    # uses point DIFFERENTIAL. This distinction is not cosmetic: a ratio is
    # asymmetric and unbounded above, so a model trained on margins does not
    # translate to it directly. See docs/afl-domain-notes.md.""",
  """    # How teams are ranked once competition points are equal. The AFL uses
    # PERCENTAGE = 100 * points_for / points_against, which is a RATIO, not a
    # difference. That is not cosmetic: a ratio is asymmetric and unbounded
    # above, so a model trained on margins does not translate to it directly.
    # See docs/afl-domain-notes.md."""),
 ("""    # Season-to-season drift in true team strength, in points. For the NFL this
    # was estimated at 4.07 via variance decomposition on independent
    # single-season fits. The AFL value is estimated the same way in
    # sportspred.reliability and should not be assumed equal.""",
  """    # Season-to-season drift in true team strength, in points. Estimated by
    # variance decomposition on independent single-season fits, in
    # sportspred.reliability."""),
 ("""    # Whether home advantage is a single league-wide number or varies by venue.
    # The NFL model uses a scalar (2.24 points). The AFL cannot: interstate
    # travel to Perth is a three-hour flight and a two-hour time change, while
    # several Melbourne clubs share the MCG and gain almost nothing from
    # "hosting". See sportspred.hga.""",
  """    # Whether home advantage is a single league-wide number or varies by venue.
    # The AFL needs the venue form: interstate travel to Perth is a three-hour
    # flight and a two-hour time change, while several Melbourne clubs share the
    # MCG and gain almost nothing from "hosting". See sportspred.hga."""),
 ("""NFL = SportConfig(
    key="nfl",
    name="National Football League",
    points_per_goal=1,
    points_per_behind=0,
    has_scoring_shots=False,
    n_teams=32,
    games_per_team=17,
    draws_possible=True,       # rare, but they happen
    pts_win=1,
    pts_draw=0,
    tiebreak="differential",
    drift_prior=4.07,          # measured in nfl-season-predictor
    hga_model="scalar",
)

SPORTS = {s.key: s for s in (AFL, NFL)}""",
  """SPORTS = {s.key: s for s in (AFL,)}"""),
],
"legacy-python/src/sportspred/ratings.py": [
 ("This is the same estimator as nfl-season-predictor/src/predictor.py, lifted out",
  "This is a weighted least-squares ratings estimator, written to be reusable"),
 ("the raw row count understates sigma. This bug was caught in the NFL project by",
  "the raw row count understates sigma. This was caught by"),
 ("    the NFL model's prediction intervals too narrow -- they covered 62.5% of",
  "    the prediction intervals too narrow -- they covered 62.5% of"),
],
"legacy-python/src/run_finals.py": [
 ("    NFL model's 80% intervals cover 62.5%. Two ratings each carry error, and",
  "    uncorrected 80% intervals cover only 62.5%. Two ratings each carry error, and"),
],
"R/01_reliability.R": [
 ("# different language, on purpose. Several bugs in the sibling NFL project were",
  "# different language, on purpose. Several bugs in an earlier version were"),
],
"R/02_models.R": [
 ("  # NFL project.", "  # earlier work."),
],
}


def apply(path, pairs):
    f = ROOT / path
    if not f.exists():
        print(f"  skip (absent): {path}"); return
    src = f.read_text(encoding="utf-8"); orig = src
    misses = []
    for old, new in pairs:
        if old in src:
            src = src.replace(old, new)
        else:
            misses.append(old.split("\n")[0][:60])
    if src != orig:
        shutil.copy2(f, f.with_suffix(f.suffix + ".nflbak"))
        f.write_text(src, encoding="utf-8")
        print(f"  cleaned {path}" + (f"  ({len(misses)} not matched)" if misses else ""))
    for mmiss in misses:
        print(f"      NOT MATCHED: {mmiss}...")


print("Stripping NFL references")
for p, pairs in EDITS.items():
    apply(p, pairs)

# stale bytecode holding the old strings
for pyc in ROOT.rglob("*.pyc"):
    if "_to_delete" not in str(pyc):
        pyc.unlink(); print(f"  removed stale {pyc.relative_to(ROOT)}")
