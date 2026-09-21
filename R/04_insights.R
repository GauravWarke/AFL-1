# The features that make this more than a leaderboard.
#
# Every one of these falls out of the same measured fact that drives the model:
# creating chances is a skill that repeats (reliability 0.88), converting them
# is mostly luck (0.32). Once you believe that, several things a fan or a coach
# would want to know become computable.

source(file.path(PROJ, "R", "03_simulate.R"))

# =======================================================================
# The Luck Ladder
# =======================================================================
# Re-run the season with every side kicking at the league-average conversion
# rate, keeping the scoring shots they actually generated and conceded. Any
# difference between where a team finished and where it lands here is
# attributable to kicking accuracy -- theirs and their opponents'.
#
# This is NOT "the ladder they deserved". Accuracy is about a third skill, so a
# genuinely accurate side is being slightly penalised. It IS the answer to
# "how much of our season came down to how straight we kicked", which is a
# question no public AFL ladder answers.
luck_ladder <- function(m, season) {
  ha <- m[m$season == season & m$stage == "home_and_away", ]
  league_acc <- sum(ha$home_goals + ha$away_goals) /
                sum(ha$home_shots + ha$away_shots)

  # Replay each match at league-average conversion. Shots stay exactly as they
  # were; only the kicking changes.
  hs <- ha$home_shots; as_ <- ha$away_shots
  h_adj <- hs * (league_acc * 6 + (1 - league_acc))
  a_adj <- as_ * (league_acc * 6 + (1 - league_acc))
  adj_margin <- h_adj - a_adj

  res <- bind_rows(
    data.frame(team = ha$home, pf = h_adj, pa = a_adj, mar = adj_margin),
    data.frame(team = ha$away, pf = a_adj, pa = h_adj, mar = -adj_margin)
  ) %>%
    group_by(team) %>%
    summarise(
      played = n(),
      # A margin of exactly zero is vanishingly unlikely once scores are
      # continuous, so draws are counted with a small tolerance rather than
      # equality -- otherwise the adjusted ladder never has any.
      won = sum(mar > 0.5), drawn = sum(abs(mar) <= 0.5),
      pf = sum(pf), pa = sum(pa), .groups = "drop") %>%
    mutate(pts_adj = 4 * won + 2 * drawn,
           pct_adj = 100 * pf / pa) %>%
    arrange(desc(pts_adj), desc(pct_adj)) %>%
    mutate(pos_adj = row_number())

  real <- build_ladder(m, season) %>% select(team, pos, pts, percentage)
  out <- real %>%
    left_join(res %>% select(team, pos_adj, pts_adj, pct_adj), by = "team") %>%
    mutate(
      # luck_places: how many places HIGHER a side actually finished than the
      # luck-neutral ladder puts them. Positive = flattered by kicking.
      #
      # Defined as pos_adj - pos, not the other way round, because ladder
      # positions run backwards (1 is best) and the intuitive direction keeps
      # getting lost. An earlier version used pos - pos_adj and every verdict
      # came out inverted: the Western Bulldogs, who finished 8th on a
      # percentage of 95 and land 15th once kicking is neutralised, were
      # labelled unlucky.
      luck_places = pos_adj - pos,
      pts_gap = pts - pts_adj,
      verdict = case_when(
        luck_places >= 2  ~ "rode their luck",
        luck_places <= -2 ~ "kicked themselves out of it",
        TRUE              ~ "about right"
      )) %>%
    arrange(pos)
  attr(out, "league_acc") <- league_acc
  out
}

# =======================================================================
# What has to happen for my team to win the flag
# =======================================================================
# Inverse reasoning. Instead of "here is your probability", answer "here is the
# path". For each remaining match, compare the team's premiership chance in the
# simulations where result A happened against those where result B did. The gap
# is how much that single match matters to them -- which is a far more useful
# thing to tell a supporter than a single number.
path_to_flag <- function(model, ladder, venues, known, team,
                         n_sims = 20000L, probs = NULL) {
  fx <- remaining_fixtures(ladder, known, venues)
  fx <- fx[!fx$played, ]
  if (!nrow(fx)) return(data.frame())

  base <- simulate_finals(model, ladder, venues, known, n_sims = n_sims,
                          probs = probs)
  p0 <- base$p_premier[match(team, base$team)]

  rows <- list()
  for (i in seq_len(nrow(fx))) {
    f <- fx[i, ]
    k <- paste0(f$stage, "|", min(f$home, f$away), "|", max(f$home, f$away))
    ph <- simulate_finals(model, ladder, venues, known, n_sims = n_sims,
                          probs = probs, force = setNames(list(f$home), k))
    pa <- simulate_finals(model, ladder, venues, known, n_sims = n_sims,
                          probs = probs, force = setNames(list(f$away), k))
    rows[[i]] <- data.frame(
      match = sprintf("%s v %s", f$home, f$away),
      venue = f$venue, label = f$label,
      if_home_wins = ph$p_premier[match(team, ph$team)],
      if_away_wins = pa$p_premier[match(team, pa$team)],
      stringsAsFactors = FALSE)
  }
  out <- bind_rows(rows)
  out$swing <- abs(out$if_home_wins - out$if_away_wins)
  out$baseline <- p0
  out[order(-out$swing), ]
}

# =======================================================================
# Beat the Model
# =======================================================================
# Score a user's tips against the model's on the same matches. Log-loss is not
# meaningful for a human who only says "this side wins", so the comparison is
# on tips and on Brier score with the model's probability, plus a plain count
# of where they disagreed and who was right.
score_tips <- function(user_picks, model_probs, actual_winners) {
  ok <- !is.na(actual_winners) & !is.na(user_picks)
  if (!any(ok)) return(NULL)
  u <- user_picks[ok]; a <- actual_winners[ok]; p <- model_probs[ok]
  model_pick <- ifelse(p >= 0.5, names(p), NA)
  list(
    n = sum(ok),
    user_correct = sum(u == a),
    disagreements = sum(u != model_pick, na.rm = TRUE),
    user_right_when_disagreeing = sum(u == a & u != model_pick, na.rm = TRUE)
  )
}

# =======================================================================
# Season fingerprint for one team, in words a supporter would use
# =======================================================================
team_story <- function(m, season, team, luck) {
  ha <- m[m$season == season & m$stage == "home_and_away", ]
  tl <- to_long(ha) %>% filter(team == !!team)
  # The output names here must NOT match the input column names. summarise()
  # evaluates its arguments in order and each one can see the ones before it,
  # so `shots = mean(shots)` followed by `acc = sum(goals) / sum(shots)` sums
  # the scalar mean that was just created rather than the original column.
  # That silently produced a league accuracy of 21798.7% on screen.
  lg <- to_long(ha) %>%
    summarise(mean_shots = mean(shots), mean_opp = mean(opp_shots),
              acc = sum(goals) / sum(shots))
  L <- luck[luck$team == team, ]

  chances <- mean(tl$shots); allowed <- mean(tl$opp_shots)
  acc <- sum(tl$goals) / sum(tl$shots)

  bits <- c(
    sprintf("%s created about %.0f scoring chances a game and gave up about %.0f.",
            team, chances, allowed),
    if (chances - allowed > 1.5)
      "Creating clearly more than they concede is the single most repeatable thing a side can do."
    else if (allowed - chances > 1.5)
      "Conceding more chances than they create is the hardest thing to fix, and it tends to persist."
    else "Chances created and conceded are close to even.",
    sprintf("They kicked %.1f%% of their chances as goals, against a league average of %.1f%%.",
            100 * acc, 100 * lg$acc),
    if (nrow(L) == 1 && !is.na(L$luck_places)) {
      if (L$luck_places >= 2)
        sprintf("Kicking straight was worth about %d ladder places to them.", L$luck_places)
      else if (L$luck_places <= -2)
        sprintf("Poor conversion cost them roughly %d ladder places.", abs(L$luck_places))
      else "Their kicking neither flattered nor cost them much."
    } else "",
    "Only about a third of a team's accuracy carries into the next block of games, so expect most of that gap to close."
  )
  paste(bits[nzchar(bits)], collapse = " ")
}

# =======================================================================
# Plain-language helpers
# =======================================================================
# Fixed denominators, never a best-fit search: a search once rounded 29% up to
# "1 in 3" on the same screen as a caption saying no side was a one-in-three
# chance.
as_frequency <- function(p) {
  vapply(seq_along(p), function(i) {
    x <- p[i]
    if (is.na(x) || x <= 0) return("out of the race")
    if (x >= 0.95) return("almost every year")
    if (x >= 0.10) {
      k <- round(x * 10)
      return(sprintf("about %d September%s in 10", k, if (k == 1) "" else "s"))
    }
    if (x >= 0.02) return(sprintf("about 1 September in %d", round(1 / x)))
    "fewer than 1 September in 50"
  }, character(1))
}

# The thresholds below are calibrated for a full finals field, where holding
# 40% of the premiership is genuinely dominant. Once the field shrinks they
# stop meaning anything: in a Grand Final, both sides clear 40% by
# definition, and calling each of them a "clear favourite" on the same screen
# is the sort of thing that makes a reader stop trusting the whole page.
#
# So when two sides are left, the wording describes the head-to-head instead.
confidence_words <- function(p, n_left = NULL) {
  if (!is.null(n_left) && n_left == 2) {
    return(ifelse(p >= 0.62, "favourite",
           ifelse(p >= 0.545, "slightly favoured",
           ifelse(p > 0.455,  "line ball",
           ifelse(p > 0.38,   "slight underdog", "underdog")))))
  }
  ifelse(p >= 0.40, "clear favourite",
  ifelse(p >= 0.25, "strong chance",
  ifelse(p >= 0.12, "live chance",
  ifelse(p >= 0.04, "outside chance",
  ifelse(p > 0,     "long shot", "eliminated")))))
}
