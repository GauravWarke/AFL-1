"""Sport definitions.

Everything the ratings model and bracket simulator need to know about the
competition lives here as data rather than in the model, so a rule change means
editing a value, not the estimator.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SportConfig:
    key: str
    name: str

    # --- scoring -----------------------------------------------------------
    # AFL scores are two-tier: a goal is 6 points, a behind is 1. Most sports
    # have a single scoring event, in which case points_per_goal is 1 and
    # behinds simply do not exist.
    points_per_goal: int
    points_per_behind: int
    has_scoring_shots: bool

    # --- competition structure --------------------------------------------
    n_teams: int
    games_per_team: int
    draws_possible: bool

    # Ladder points: the AFL awards 4 for a win and 2 for a draw. Kept
    # explicit rather than hard-coded so the standings code stays readable.
    pts_win: int
    pts_draw: int

    # How teams are ranked once competition points are equal. The AFL uses
    # PERCENTAGE = 100 * points_for / points_against, which is a RATIO, not a
    # difference. That is not cosmetic: a ratio is asymmetric and unbounded
    # above, so a model trained on margins does not translate to it directly.
    # See docs/afl-domain-notes.md.
    tiebreak: str

    # --- model priors ------------------------------------------------------
    # Season-to-season drift in true team strength, in points. Estimated by
    # variance decomposition on independent single-season fits, in
    # sportspred.reliability.
    drift_prior: float | None = None

    # Whether home advantage is a single league-wide number or varies by venue.
    # The AFL needs the venue form: interstate travel to Perth is a three-hour
    # flight and a two-hour time change, while several Melbourne clubs share the
    # MCG and gain almost nothing from "hosting". See sportspred.hga.
    hga_model: str = "scalar"

    aliases: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------

AFL = SportConfig(
    key="afl",
    name="Australian Football League",
    points_per_goal=6,
    points_per_behind=1,
    has_scoring_shots=True,
    n_teams=18,
    games_per_team=23,
    draws_possible=True,
    pts_win=4,
    pts_draw=2,
    tiebreak="percentage",
    drift_prior=None,          # estimated from data, never assumed
    hga_model="venue",
    aliases={
        # Squiggle is internally consistent, but AFL Tables and fitzRoy are not,
        # and a student cloning this repo will hit both. Normalise on ingest.
        "Brisbane": "Brisbane Lions",
        "GWS": "Greater Western Sydney",
        "GWS Giants": "Greater Western Sydney",
        "Footscray": "Western Bulldogs",
        "Kangaroos": "North Melbourne",
    },
)

SPORTS = {s.key: s for s in (AFL,)}


def get(key: str) -> SportConfig:
    if key not in SPORTS:
        raise KeyError(f"unknown sport {key!r}; have {sorted(SPORTS)}")
    return SPORTS[key]
