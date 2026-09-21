# Live results from the AFL, via the {fitzRoy} package.
#
# WHY this exists alongside data/processed/matches.csv
# ----------------------------------------------------
# The CSV is what every model is fitted and checked against. It is frozen,
# validated on load, and reproducible. But during finals the results change
# week to week, and hand-editing a CSV during Grand Final week is how you end
# up with a typo in your training data.
#
# So this file is the one place that talks to the outside world. It pulls
# results, translates them into exactly the schema matches.csv already uses,
# and appends only the games that are genuinely new. Nothing downstream
# depends on it. If fitzRoy is not installed, or the AFL is not answering,
# everything else still runs off the CSV untouched.
#
#     source("R/06_live_data.R")
#     preview_new_results(2026)        # look before you leap
#     refresh_current_season(2026)     # append what is actually new
#
# A note on the column mapping below. fitzRoy returns the AFL's own field
# names, which differ from this project's in three ways: team names carry
# their nicknames ("Sydney Swans" rather than "Sydney"), venues use current
# commercial names ("Optus Stadium" rather than "Perth Stadium"), and finals
# are grouped by week rather than by type. All three are translated here, and
# here only, so that if the AFL renames a stadium next season this is the one
# file that needs touching.

PROJ <- if (exists("PROJ")) PROJ else "C:/Users/GAURAV/OneDrive/Desktop/AFL"
source(file.path(PROJ, "R", "00_setup.R"))

.has_fitzroy <- function() requireNamespace("fitzRoy", quietly = TRUE)

# --- name translation --------------------------------------------------
API_TEAM <- c(
  "Adelaide Crows" = "Adelaide", "Brisbane Lions" = "Brisbane Lions",
  "Carlton" = "Carlton", "Collingwood" = "Collingwood",
  "Essendon" = "Essendon", "Fremantle" = "Fremantle",
  "Geelong Cats" = "Geelong", "Gold Coast SUNS" = "Gold Coast",
  "GWS GIANTS" = "Greater Western Sydney", "Hawthorn" = "Hawthorn",
  "Melbourne" = "Melbourne", "North Melbourne" = "North Melbourne",
  "Port Adelaide" = "Port Adelaide", "Richmond" = "Richmond",
  "St Kilda" = "St Kilda", "Sydney Swans" = "Sydney",
  "West Coast Eagles" = "West Coast", "Western Bulldogs" = "Western Bulldogs"
)

# Left side is what the AFL calls it today; right side is the name this
# project has used since 2015, which keeps the venue-to-state lookup in
# 01_data.R working.
API_VENUE <- c(
  "MCG" = "M.C.G.", "SCG" = "S.C.G.",
  "Marvel Stadium" = "Docklands", "GMHBA Stadium" = "Kardinia Park",
  "Optus Stadium" = "Perth Stadium", "ENGIE Stadium" = "Sydney Showground",
  "People First Stadium" = "Carrara", "Ninja Stadium" = "Bellerive Oval",
  "UTAS Stadium" = "York Park", "TIO Traeger Park" = "Traeger Park",
  "TIO Stadium" = "Marrara Oval", "Corroboree Group Oval Manuka" = "Manuka Oval",
  "Adelaide Oval" = "Adelaide Oval", "Gabba" = "Gabba",
  "Norwood Oval" = "Norwood Oval", "Barossa Park" = "Barossa Park",
  "Hands Oval" = "Hands Oval"
)

.translate <- function(x, map, what) {
  out <- unname(map[x])
  if (any(is.na(out))) {
    warning(sprintf("Unrecognised %s from the AFL feed: %s. Add it to the map in R/06_live_data.R.",
                    what, paste(unique(x[is.na(out)]), collapse = ", ")), call. = FALSE)
    out[is.na(out)] <- x[is.na(out)]   # pass through rather than silently drop
  }
  out
}

# The AFL groups qualifying and elimination finals into a single round ("QE"),
# but the bracket simulator has to tell them apart. Qualifying finals are the
# ones contested by the top four seeds, so the ladder resolves it.
.split_qe <- function(home, away, top4) {
  ifelse(home %in% top4 & away %in% top4, "qualifying_final", "elimination_final")
}

.reshape_fitzroy <- function(raw, top4 = character(0)) {
  get <- function(col, default = NA) if (col %in% names(raw)) raw[[col]] else default

  home <- .translate(get("match.homeTeam.name"), API_TEAM, "team name")
  away <- .translate(get("match.awayTeam.name"), API_TEAM, "team name")
  abbr <- as.character(get("round.abbreviation"))

  stage <- dplyr::case_when(
    abbr == "WF" ~ "wildcard_final",
    abbr == "SF" ~ "semi_final",
    abbr == "PF" ~ "preliminary_final",
    abbr == "GF" ~ "grand_final",
    abbr == "QE" ~ .split_qe(home, away, top4),
    TRUE         ~ "home_and_away"
  )

  hg <- as.integer(get("homeTeamScore.matchScore.goals"))
  hb <- as.integer(get("homeTeamScore.matchScore.behinds"))
  ag <- as.integer(get("awayTeamScore.matchScore.goals"))
  ab <- as.integer(get("awayTeamScore.matchScore.behinds"))

  out <- data.frame(
    game_id      = as.character(get("match.matchId")),
    season       = as.integer(get("round.year")),
    round        = as.integer(get("round.roundNumber")),
    round_name   = as.character(get("round.name")),
    stage        = stage,
    date         = as.Date(substr(as.character(get("match.date")), 1, 10)),
    venue        = .translate(get("venue.name"), API_VENUE, "venue"),
    home = home, away = away,
    home_goals = hg, home_behinds = hb,
    away_goals = ag, away_behinds = ab,
    stringsAsFactors = FALSE
  )

  # Everything below is derived, never read from the feed, so it cannot
  # disagree with itself the way two independently-supplied score columns can.
  out$home_score <- out$home_goals * 6 + out$home_behinds
  out$away_score <- out$away_goals * 6 + out$away_behinds
  out$home_shots <- out$home_goals + out$home_behinds
  out$away_shots <- out$away_goals + out$away_behinds
  out$home_accuracy <- out$home_goals / pmax(out$home_shots, 1)
  out$away_accuracy <- out$away_goals / pmax(out$away_shots, 1)
  out$margin      <- out$home_score - out$away_score
  out$shot_margin <- out$home_shots - out$away_shots
  out$is_draw     <- as.integer(out$margin == 0)

  status <- as.character(get("match.status", "CONCLUDED"))
  out <- out[status == "CONCLUDED" & !is.na(out$home_goals) & !is.na(out$away_goals), ]
  rownames(out) <- NULL
  out
}

# Matching on game_id would not work: the CSV carries AFL Tables ids and the
# feed carries the AFL's own. A game is the same game if the same two sides
# met in the same season at the same stage.
.natural_key <- function(d) {
  paste(d$season, d$stage, pmin(d$home, d$away), pmax(d$home, d$away), sep = "|")
}

.fetch <- function(season) {
  if (!.has_fitzroy()) {
    message("fitzRoy is not installed. Run install.packages('fitzRoy') to enable ",
            "live updates. The static CSV is untouched.")
    return(NULL)
  }
  tryCatch(fitzRoy::fetch_results(season = season, comp = "AFLM"),
           error = function(e) {
             message("Could not reach the AFL feed (", conditionMessage(e),
                     "). Carrying on with the CSV as it stands.")
             NULL
           })
}

# Which sides finished top four? Needed only to tell qualifying finals from
# elimination finals, and read from the CSV so it does not depend on the feed.
.top4 <- function(existing, season) {
  ha <- existing[existing$season == season & existing$stage == "home_and_away", ]
  if (!nrow(ha)) return(character(0))
  lad <- to_long(ha) %>%
    group_by(team) %>%
    summarise(pts = 4 * sum(margin > 0) + 2 * sum(margin == 0),
              pct = 100 * sum(score) / sum(conceded), .groups = "drop") %>%
    arrange(desc(pts), desc(pct))
  head(lad$team, 4)
}

# Show what a refresh would add, and change nothing. Always worth running
# first: a mis-mapped team name shows up here as a brand new fixture rather
# than quietly duplicating a game you already have.
preview_new_results <- function(season = 2026) {
  raw <- .fetch(season); if (is.null(raw)) return(invisible(NULL))
  existing <- read.csv(p_data("matches.csv"), stringsAsFactors = FALSE)
  fresh <- .reshape_fitzroy(raw, .top4(existing, season))
  new <- fresh[!.natural_key(fresh) %in% .natural_key(existing), ]

  if (!nrow(new)) {
    message("Up to date. The feed has ", nrow(fresh), " completed ", season,
            " games and every one of them is already in the CSV.")
    return(invisible(new))
  }
  message(nrow(new), " new result(s):")
  print(new[, c("date", "stage", "home", "home_score", "away", "away_score")],
        row.names = FALSE)
  invisible(new)
}

# Append the new games and write. Running it twice in a row adds nothing the
# second time.
refresh_current_season <- function(season = 2026, write = TRUE) {
  raw <- .fetch(season); if (is.null(raw)) return(invisible(NULL))
  existing <- read.csv(p_data("matches.csv"), stringsAsFactors = FALSE)
  fresh <- .reshape_fitzroy(raw, .top4(existing, season))
  new <- fresh[!.natural_key(fresh) %in% .natural_key(existing), ]

  if (!nrow(new)) {
    message("Already up to date. Nothing added.")
    return(invisible(existing))
  }

  new <- new[, names(existing)]      # column order must match exactly
  combined <- rbind(existing, new)
  combined <- combined[order(combined$season, as.Date(combined$date)), ]

  message("Adding ", nrow(new), " result(s): ",
          paste(sprintf("%s %d d %s %d (%s)", new$home, new$home_score,
                        new$away, new$away_score, gsub("_", " ", new$stage)),
                collapse = "; "))
  if (write) {
    write.csv(combined, p_data("matches.csv"), row.names = FALSE)
    message("Written. Now rebuild the dashboard data: save_app_data()")
  }
  invisible(combined)
}

# When is the next game, and where? Used by the Grand Final countdown so the
# date is not hard-coded anywhere.
next_fixture <- function(season = 2026) {
  if (!.has_fitzroy()) return(NULL)
  fx <- tryCatch(fitzRoy::fetch_fixture(season = season, comp = "AFLM"),
                 error = function(e) NULL)
  if (is.null(fx) || !nrow(fx)) return(NULL)
  dcol <- if ("utcStartTime" %in% names(fx)) "utcStartTime" else "compSeason.startDate"
  fx$.d <- as.Date(substr(as.character(fx[[dcol]]), 1, 10))
  up <- fx[!is.na(fx$.d) & fx$.d >= Sys.Date(), ]
  if (!nrow(up)) return(NULL)
  up[order(up$.d), ][1, ]
}
