# Precompute everything the app needs, so the app itself never fits a model.
#
# Two reasons for the split. A dashboard that refits on startup is unusable,
# and separating compute from display means whatever is on screen came from a
# run that was checked.
#
# The one thing the app DOES do live is run the simulator, because the what-if
# explorer needs it. That is affordable because the expensive part -- the
# pairwise win-probability matrix -- is computed here once and shipped with the
# data. Simulating 20,000 tournaments from a ready matrix takes a fraction of a
# second.
#
#     source("R/05_app_data.R"); save_app_data()

source(file.path(PROJ, "R", "04_insights.R"))

build_app_data <- function(season = 2026, n_sims = 20000L) {
  m <- load_matches()
  train <- m[m$stage == "home_and_away", ]
  model <- fit_model(train)

  lad <- build_ladder(m, season)
  ven <- home_venues(m, season)
  kn  <- known_results(m, season)
  field <- head(lad$team, 10)

  probs <- finals_prob_matrix(model, field, ven)
  proj  <- simulate_finals(model, lad, ven, kn, n_sims = n_sims, probs = probs)

  bad <- check_invariants(proj, wildcard = TRUE)
  if (length(bad)) stop("bracket invariants failed: ", paste(bad, collapse = "; "))

  # A side can have made the eight and still be knocked out. Without this the
  # table shows "100% made finals, 0% flag", which reads as a bug.
  proj$alive   <- proj$p_prelim > 0 | proj$p_premier > 0
  proj$freq    <- as_frequency(proj$p_premier)
  # How many sides can still win it decides which vocabulary makes sense.
  proj$verdict <- confidence_words(proj$p_premier, n_left = sum(proj$p_premier > 0))

  fx <- remaining_fixtures(lad, kn, ven)

  # Win probability and a plain-English reason for every fixture, played or not.
  if (nrow(fx)) {
    fx$p_home <- NA_real_; fx$exp_margin <- NA_real_; fx$why <- NA_character_
    for (i in seq_len(nrow(fx))) {
      nd <- make_fixture(fx$home[i], fx$away[i], fx$venue[i])
      pr <- model$predict(nd, n = 3000L)
      fx$p_home[i]     <- pr$prob
      fx$exp_margin[i] <- pr$margin
      fx$why[i]        <- model$explain(fx$home[i], fx$away[i], fx$venue[i])
    }
  }

  # --- per-team season numbers, in the app's vocabulary ---------------
  ha <- m[m$season == season & m$stage == "home_and_away", ]
  tm <- to_long(ha) %>%
    group_by(team) %>%
    summarise(games = n(),
              chances_created = mean(shots),
              chances_allowed = mean(opp_shots),
              accuracy = sum(goals) / sum(shots),
              points_for = mean(score), points_against = mean(conceded),
              .groups = "drop") %>%
    mutate(chance_edge = chances_created - chances_allowed)

  luck <- luck_ladder(m, season)
  stories <- setNames(
    vapply(lad$team, function(t) team_story(m, season, t, luck), character(1)),
    lad$team)

  # --- finals already played ------------------------------------------
  fin <- m[m$season == season & m$stage != "home_and_away", ]
  fin <- fin[order(fin$date), ]
  played <- data.frame(
    stage = gsub("_", " ", fin$stage), date = as.character(fin$date),
    venue = fin$venue, home = fin$home, away = fin$away,
    home_score = fin$home_score, away_score = fin$away_score,
    home_shots = fin$home_shots, away_shots = fin$away_shots,
    winner = ifelse(fin$margin > 0, fin$home, fin$away),
    margin = abs(fin$margin), stringsAsFactors = FALSE)

  # --- the model's own track record, so the app can be honest ---------
  track <- if (file.exists(p_out("engine_validation_R.csv")))
    read.csv(p_out("engine_validation_R.csv"), stringsAsFactors = FALSE) else NULL
  scores <- if (file.exists(p_out("model_scores.csv")))
    read.csv(p_out("model_scores.csv"), stringsAsFactors = FALSE) else NULL

  list(
    generated = format(Sys.time(), "%d %B %Y, %I:%M%p AEST"),
    season = season, n_sims = n_sims,
    model_name = model$name, theta = model$theta,
    league_acc = model$league_acc,
    accuracy_reliability = ACCURACY_RELIABILITY,
    probs = probs, ladder = lad, venues = ven, known = kn,
    proj = proj, fixtures = fx, teams = tm, luck = luck,
    stories = stories, played = played, track = track, scores = scores,

    # The Grand Final section needs the raw match table (for drought and
    # historical Grand Final records, which reach back well before this
    # season) and the fitted model itself (to price a fixture between two
    # sides who have not met in the finals yet).
    #
    # Shipping the model means shipping its closures, and a closure carries
    # its enclosing environment with it -- including the glm and the training
    # frame. That is what makes the .rds a few megabytes rather than a few
    # hundred kilobytes. It is a fair trade: the app still never fits
    # anything, it just has the fitted object on hand.
    m_raw = m, model = model
  )
}

save_app_data <- function(...) {
  d <- build_app_data(...)
  saveRDS(d, p_out("app_data.rds"))
  cat("wrote outputs/app_data.rds\n")
  cat("  model:", d$model_name, "| teams:", nrow(d$proj),
      "| finals played:", nrow(d$played),
      "| still to play:", sum(!d$fixtures$played), "\n")
  invisible(d)
}
