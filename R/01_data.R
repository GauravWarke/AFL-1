# Load the match table and build the features every model draws on.
#
# One rule governs this file: a feature attached to match M may only use
# information available BEFORE match M was played. Everything is built with
# cumulative-then-lagged operations for that reason. The most common way a
# football model produces impossible accuracy is a feature that quietly
# includes the result it is predicting.

source(file.path(PROJ, "R", "00_setup.R"))

# --- geography ---------------------------------------------------------
# Mirrors src/sportspred/geography.py. Home advantage in the AFL is mostly a
# travel penalty: interstate flights, and a two-hour time change for Perth.
TEAM_STATE <- c(
  "Adelaide" = "SA", "Port Adelaide" = "SA",
  "Brisbane Lions" = "QLD", "Gold Coast" = "QLD",
  "Sydney" = "NSW", "Greater Western Sydney" = "NSW",
  "West Coast" = "WA", "Fremantle" = "WA",
  "Carlton" = "VIC", "Collingwood" = "VIC", "Essendon" = "VIC",
  "Geelong" = "VIC", "Hawthorn" = "VIC", "Melbourne" = "VIC",
  "North Melbourne" = "VIC", "Richmond" = "VIC", "St Kilda" = "VIC",
  "Western Bulldogs" = "VIC"
)

VENUE_STATE <- c(
  "M.C.G." = "VIC", "Docklands" = "VIC", "Kardinia Park" = "VIC",
  "Marvel Stadium" = "VIC", "Princes Park" = "VIC", "Eureka Stadium" = "VIC",
  "Mars Stadium" = "VIC", "Eureka" = "VIC",
  "Adelaide Oval" = "SA", "Football Park" = "SA", "Norwood Oval" = "SA",
  "Summit Sports Park" = "SA", "Barossa Park" = "SA",
  "Gabba" = "QLD", "Carrara" = "QLD", "Cazaly's Stadium" = "QLD",
  "Riverway Stadium" = "QLD", "Metricon Stadium" = "QLD",
  "S.C.G." = "NSW", "Sydney Showground" = "NSW", "Blacktown" = "NSW",
  "Stadium Australia" = "NSW", "Manuka Oval" = "ACT",
  "Perth Stadium" = "WA", "Subiaco" = "WA",
  "York Park" = "TAS", "Bellerive Oval" = "TAS", "North Hobart" = "TAS",
  "Traeger Park" = "NT", "Marrara Oval" = "NT", "TIO Stadium" = "NT",
  "Jiangwan Stadium" = "OS", "Wellington" = "OS"
)

STATE_TZ <- c(VIC = 10, NSW = 10, QLD = 10, SA = 9.5, WA = 8,
              TAS = 10, ACT = 10, NT = 9.5)

travel_flags <- function(team, venue) {
  ts <- unname(TEAM_STATE[team]); vs <- unname(VENUE_STATE[venue])
  unknown <- is.na(ts) | is.na(vs) | vs == "OS"
  list(
    interstate = ifelse(unknown, 1, as.numeric(ts != vs)),
    tz = ifelse(unknown, 0,
                abs(ifelse(is.na(STATE_TZ[ts]), 10, STATE_TZ[ts]) -
                    ifelse(is.na(STATE_TZ[vs]), 10, STATE_TZ[vs])))
  )
}

# --- load --------------------------------------------------------------
load_matches <- function() {
  m <- read.csv(p_data("matches.csv"), stringsAsFactors = FALSE)

  # Independent integrity check. Cheap, and it catches a corrupted or
  # half-written CSV before any model is fitted on it.
  stopifnot(
    all(m$home_goals * 6 + m$home_behinds == m$home_score),
    all(m$away_goals * 6 + m$away_behinds == m$away_score),
    !any(duplicated(m$game_id))
  )

  m$date <- as.Date(m$date)
  th <- travel_flags(m$home, m$venue)
  ta <- travel_flags(m$away, m$venue)
  m$home_interstate <- th$interstate
  m$away_interstate <- ta$interstate
  m$away_tz         <- ta$tz
  # Base home advantage only counts when the host has not itself travelled --
  # otherwise relocated and neutral-venue games silently inflate it.
  m$hga_base        <- 1 - th$interstate

  m <- m[order(m$season, m$date, m$game_id), ]
  rownames(m) <- NULL
  m
}

# --- long form: one row per team per match -----------------------------
to_long <- function(m) {
  h <- m %>% transmute(
    game_id, season, round, stage, date, venue,
    team = home, opp = away, at_home = 1L,
    score = home_score, conceded = away_score,
    shots = home_shots, opp_shots = away_shots,
    goals = home_goals, margin = margin)
  a <- m %>% transmute(
    game_id, season, round, stage, date, venue,
    team = away, opp = home, at_home = 0L,
    score = away_score, conceded = home_score,
    shots = away_shots, opp_shots = home_shots,
    goals = away_goals, margin = -margin)
  bind_rows(h, a) %>% arrange(season, date, game_id)
}

# --- rolling form, strictly lagged -------------------------------------
# Each team's form as it stood BEFORE each match. lag() after the rolling
# mean is what enforces that; without it the current result leaks in.
add_form <- function(long, window = 6L) {
  roll_lagged <- function(x, k) {
    n <- length(x)
    out <- rep(NA_real_, n)
    if (n > 1) {
      for (i in 2:n) {
        lo <- max(1, i - k)
        out[i] <- mean(x[lo:(i - 1)])
      }
    }
    out
  }
  long %>%
    group_by(team) %>%
    arrange(date, .by_group = TRUE) %>%
    mutate(
      form_margin  = roll_lagged(margin, window),
      form_score   = roll_lagged(score, window),
      form_conc    = roll_lagged(conceded, window),
      form_shots   = roll_lagged(shots, window),
      form_oshots  = roll_lagged(opp_shots, window),
      form_acc     = roll_lagged(goals / pmax(shots, 1), window),
      games_played = row_number() - 1L
    ) %>%
    ungroup()
}

# Fold team form back onto the match table as home-minus-away differences.
# Differences rather than levels: they are more stable, and they encode the
# symmetry of the problem, so a tree model does not have to learn it.
build_features <- function(m, window = 6L) {
  f <- add_form(to_long(m), window) %>%
    select(game_id, team, form_margin, form_score, form_conc,
           form_shots, form_oshots, form_acc, games_played)

  hf <- f %>% rename_with(~ paste0("h_", .x), -c(game_id, team))
  af <- f %>% rename_with(~ paste0("a_", .x), -c(game_id, team))

  m %>%
    left_join(hf, by = c("game_id", "home" = "team")) %>%
    left_join(af, by = c("game_id", "away" = "team")) %>%
    mutate(
      d_form_margin = h_form_margin - a_form_margin,
      d_form_score  = h_form_score  - a_form_score,
      d_form_conc   = h_form_conc   - a_form_conc,
      d_form_shots  = h_form_shots  - a_form_shots,
      d_form_oshots = h_form_oshots - a_form_oshots,
      d_form_acc    = h_form_acc    - a_form_acc,
      home_win      = as.numeric(margin > 0)
    )
}

FEATURES <- c("d_form_margin", "d_form_score", "d_form_conc",
              "d_form_shots", "d_form_oshots", "d_form_acc",
              "hga_base", "away_interstate", "away_tz")
