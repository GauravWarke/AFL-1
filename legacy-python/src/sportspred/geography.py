"""Where clubs are based and where they play.

This exists because AFL home advantage is not a league-wide constant. Two facts
make it a team-venue property instead:

  * Distance. Perth to Melbourne is roughly 2,700 km and a two-hour time change
    in summer. A Victorian side flying west plays a genuinely harder fixture
    than one crossing Melbourne.

  * Shared grounds. Ten of the eighteen clubs are Victorian and most of them
    play "home" games at the MCG or Docklands. When Collingwood hosts Carlton
    at the MCG, both sides know the ground equally well and neither travels.
    Calling that a home game in the same sense as Fremantle at Optus Stadium
    would be a category error.

State is the practical unit: within a state, travel is short and grounds are
familiar; across states it is a flight. Timezone is tracked separately because
the Perth trip costs a time change on top of the distance.
"""

# UTC offsets are the standard (non-DST) ones. Only the WA gap is large enough
# to matter for a match played in the evening.
STATE_TZ = {"VIC": 10, "NSW": 10, "QLD": 10, "SA": 9.5, "WA": 8, "TAS": 10,
            "ACT": 10, "NT": 9.5}

TEAM_STATE = {
    "Adelaide": "SA", "Port Adelaide": "SA",
    "Brisbane Lions": "QLD", "Gold Coast": "QLD",
    "Sydney": "NSW", "Greater Western Sydney": "NSW",
    "West Coast": "WA", "Fremantle": "WA",
    "Carlton": "VIC", "Collingwood": "VIC", "Essendon": "VIC",
    "Geelong": "VIC", "Hawthorn": "VIC", "Melbourne": "VIC",
    "North Melbourne": "VIC", "Richmond": "VIC", "St Kilda": "VIC",
    "Western Bulldogs": "VIC",
}

# Venue names as Squiggle reports them. Squiggle uses traditional ground names
# rather than current sponsor names, which is a mercy -- sponsor names change
# every few seasons and would fragment the history.
VENUE_STATE = {
    "M.C.G.": "VIC", "Docklands": "VIC", "Kardinia Park": "VIC",
    "Marvel Stadium": "VIC", "Princes Park": "VIC", "Eureka Stadium": "VIC",
    "Mars Stadium": "VIC",
    "Adelaide Oval": "SA", "Football Park": "SA", "Norwood Oval": "SA",
    "Gabba": "QLD", "Carrara": "QLD", "Cazaly's Stadium": "QLD",
    "Riverway Stadium": "QLD", "Metricon Stadium": "QLD",
    "S.C.G.": "NSW", "Sydney Showground": "NSW", "Blacktown": "NSW",
    "Manuka Oval": "ACT", "Stadium Australia": "NSW",
    "Perth Stadium": "WA", "Subiaco": "WA",
    "York Park": "TAS", "Bellerive Oval": "TAS", "North Hobart": "TAS",
    "Traeger Park": "NT", "Marrara Oval": "NT", "TIO Stadium": "NT",
    "Jiangwan Stadium": "OS", "Wellington": "OS", "Eureka": "VIC",
    "Summit Sports Park": "SA", "Barossa Park": "SA",
}


def venue_state(venue: str) -> str | None:
    return VENUE_STATE.get(venue)


def team_state(team: str) -> str | None:
    return TEAM_STATE.get(team)


def travel(team: str, venue: str) -> dict:
    """How far a given team is from a given venue, in model terms."""
    ts, vs = team_state(team), venue_state(venue)
    if ts is None or vs is None or vs == "OS":
        # Unknown or overseas: treat as interstate for both sides, which is
        # the honest default, and flag it so it can be counted.
        return dict(interstate=1, tz_shift=0.0, known=False)
    return dict(
        interstate=int(ts != vs),
        tz_shift=abs(STATE_TZ.get(ts, 10) - STATE_TZ.get(vs, 10)),
        known=True,
    )
