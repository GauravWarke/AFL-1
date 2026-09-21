# THE model. One model, chosen on evidence, and nothing else in the live system.
#
# Scoring shots + accuracy. It won a seven-way bake-off on 211 matches of the
# 2026 season with a log-loss of 0.5212, ahead of ridge margin (0.5348), Elo
# (0.5382), Bayesian hierarchical (0.5473), Bradley-Terry (0.5647), gradient
# boosting (0.5948) and random forest (0.6417). The full comparison, including
# the paired bootstrap showing the top three are statistically tied, is in
# docs/model-bakeoff.md. The six losing models are kept in R/archive/ purely as
# the record of how this one was chosen -- nothing in the app touches them.
#
# HOW IT WORKS, in one paragraph
# ------------------------------
# A team's score in Australian football is built in two steps: first you get
# the ball into a scoring position, then you either kick it straight or you
# don't. So the model has two steps too.
#
#   1. SHOTS. How many scoring shots does this side generate, and how many does
#      it concede? A count model with a team attack effect, an opponent defence
#      effect, and home ground.
#
#      A note on Poisson vs negative binomial, because the obvious answer is
#      wrong. Pooled across 2015-2026, scoring shots look clearly over-dispersed
#      (Pearson dispersion 1.41 after modelling team, opponent and venue), which
#      says "use negative binomial". But almost all of that is unmodelled TREND,
#      not genuine over-dispersion: a single team coefficient averaged over
#      twelve seasons fits no individual season well, and that misfit shows up
#      as extra spread. Once the recency weights are applied -- which is how the
#      model is actually fitted -- weighted dispersion falls to 0.92, slightly
#      UNDER Poisson. So the negative binomial has nothing left to do, and its
#      theta runs off to infinity.
#
#      The code below therefore measures the weighted dispersion and only
#      reaches for the negative binomial if it is genuinely needed. On current
#      data it uses Poisson, and the difference is negligible: on a 24-versus-22
#      chances fixture the two give the same win probability to three decimals.
#
#   2. CONVERSION. What share of those shots become goals (6 points) rather than
#      behinds (1 point)? Modelled as binomial.
#
# The crucial detail is that step 2 is SHRUNK. Across 216 team-seasons, only
# about a third of the spread in goal accuracy carries over from one half of a
# season to the other (reliability 0.32), while shots created and conceded carry
# over at 0.88 and 0.87. So a team keeps only a third of its accuracy edge and
# the rest is pulled back to the league average. Trusting a hot-kicking team to
# stay hot is the single most common way to be wrong about the AFL.
#
# Because the score is a compound distribution -- a count of shots, each then
# converted or not -- there is no tidy closed form for P(win). It is obtained by
# simulation, which is exact up to Monte Carlo error and takes milliseconds.

source(file.path(PROJ, "R", "01_data.R"))

# Measured in src/ida_afl.py and cross-checked in R/01_reliability.R. Two
# independent methods -- a binomial variance decomposition and an odd/even
# split-half -- agree at 0.32 and 0.25.
ACCURACY_RELIABILITY <- 0.324

fit_model <- function(train, decay = 0.80, nsim = 600L) {
  long <- to_long(train)
  long$is_home <- long$at_home
  # Recency weighting: 0.80 a season, tuned by walk-forward. Last season counts
  # for a fifth of this one; two seasons ago for a twenty-fifth. AFL lists turn
  # over fast and a twelve-year unweighted average would be describing a
  # competition that no longer exists.
  long$w <- (1 - decay)^(max(long$season) - long$season)

  # Step 1: shots. team = attack, opp = defence.
  #
  # Fit Poisson first, then MEASURE whether the extra negative-binomial
  # parameter is warranted rather than assuming it. Reaching straight for
  # glm.nb here is what hides the finding above: it silently returns a theta of
  # several hundred thousand, which is Poisson wearing a disguise, and nothing
  # in the output tells you that happened.
  nb <- glm(shots ~ team + opp + is_home, family = poisson,
            data = long, weights = long$w)
  mu <- fitted(nb)
  dispersion <- sum(long$w * (long$shots - mu)^2 / mu) /
                (sum(long$w) - length(coef(nb)))

  if (dispersion > 1.10) {
    # Genuinely over-dispersed. Method-of-moments theta from var = mu + mu^2/theta,
    # which is stable under fractional weights where glm.nb's ML step is not.
    theta <- mean(mu) / (dispersion - 1)
  } else {
    # Poisson is adequate (or the data is slightly under-dispersed, in which
    # case a negative binomial could only make things worse).
    theta <- Inf
  }

  # Step 2: conversion, shrunk toward the league rate.
  acc_tab <- long %>% group_by(team) %>%
    summarise(g = sum(goals), s = sum(shots), .groups = "drop")
  league_acc <- sum(acc_tab$g) / sum(acc_tab$s)
  raw_acc <- setNames(acc_tab$g / acc_tab$s, acc_tab$team)
  acc <- league_acc + ACCURACY_RELIABILITY * (raw_acc - league_acc)

  team_levels <- levels(factor(long$team))
  opp_levels  <- levels(factor(long$opp))

  expected_shots <- function(nd) {
    mk <- function(tm, op, home) data.frame(
      team = factor(tm, levels = team_levels),
      opp  = factor(op, levels = opp_levels),
      is_home = home)

    # Home advantage belongs to a side playing in its own state, not to
    # whichever side happens to be written first. hga_base is exactly that
    # flag, and make_fixture() has already worked it out.
    #
    # This matters most on the one day it is hardest to get a second look at.
    # A Grand Final between two interstate clubs is played at the MCG, where
    # neither is at home. Reading the nomination instead of the flag handed
    # the listed side a full home-ground bonus it had not earned: Brisbane v
    # Fremantle came out as Brisbane 53% written one way round and Brisbane
    # 35% written the other. Same two teams, same ground, a seventeen-point
    # swing decided by row order.
    #
    # With hga_base, a neutral venue gives neither side the bonus and the
    # answer no longer depends on how the fixture was typed. Ordinary home
    # games are unaffected, because there hga_base is 1 anyway.
    hga <- if (!is.null(nd$hga_base)) as.numeric(nd$hga_base) else 1

    list(
      home = as.numeric(predict(nb, mk(nd$home, nd$away, hga), type = "response")),
      away = as.numeric(predict(nb, mk(nd$away, nd$home, 0L),  type = "response"))
    )
  }

  predict_fn <- function(nd, n = nsim) {
    sh <- expected_shots(nd)
    lh <- sh$home; la <- sh$away
    ah <- ifelse(is.na(acc[nd$home]), league_acc, acc[nd$home])
    aa <- ifelse(is.na(acc[nd$away]), league_acc, acc[nd$away])
    k <- nrow(nd)
    mgs <- matrix(0, n, k)
    for (s in seq_len(n)) {
      s_h <- if (is.finite(theta)) rnbinom(k, mu = lh, size = theta) else rpois(k, lh)
      s_a <- if (is.finite(theta)) rnbinom(k, mu = la, size = theta) else rpois(k, la)
      g_h <- rbinom(k, s_h, ah); g_a <- rbinom(k, s_a, aa)
      mgs[s, ] <- (g_h * 6 + (s_h - g_h)) - (g_a * 6 + (s_a - g_a))
    }
    data.frame(
      margin = colMeans(mgs),
      prob   = colMeans(mgs > 0) + 0.5 * colMeans(mgs == 0),
      # Where the expected margin comes from, so the app can explain any
      # prediction instead of just asserting it.
      exp_shots_home = lh, exp_shots_away = la,
      acc_home = as.numeric(ah), acc_away = as.numeric(aa)
    )
  }

  # Plain-English reason for a single fixture. This is the feature that
  # separates the app from a leaderboard that emits a bare number.
  explain <- function(home, away, venue) {
    nd <- make_fixture(home, away, venue)
    p <- predict_fn(nd, n = 2000L)
    shot_edge <- p$exp_shots_home - p$exp_shots_away
    th <- travel_flags(home, venue); ta <- travel_flags(away, venue)
    parts <- c()
    parts <- c(parts, sprintf(
      "We expect %s to create about %.0f scoring chances and %s about %.0f.",
      home, p$exp_shots_home, away, p$exp_shots_away))

    gap <- round(abs(shot_edge))
    if (gap >= 1) parts <- c(parts, sprintf(
      "That is %d more %s for %s, which is where most of the edge comes from.",
      gap, if (gap == 1) "chance" else "chances",
      if (shot_edge > 0) home else away))
    else parts <- c(parts, "Neither side is expected to create many more chances than the other.")

    # Travel is only an advantage if one side has it and the other does not.
    # On a neutral ground both sides are away from home, and saying "the away
    # team is travelling" there is actively misleading -- it reads as though
    # someone has a home ground when nobody does.
    if (ta$interstate == 1 && th$interstate == 0) parts <- c(parts, sprintf(
      "%s are travelling interstate and %s are not, which is worth several points.",
      away, home))
    else if (ta$interstate == 1 && th$interstate == 1) parts <- c(parts,
      "Both sides are away from home, so neither gets a ground advantage.")
    parts <- c(parts, sprintf(
      "Put together, %s wins this about %d times in 100.",
      if (p$prob >= .5) home else away,
      round(100 * max(p$prob, 1 - p$prob))))
    paste(parts, collapse = " ")
  }

  list(
    name = "Scoring shots + accuracy", dispersion = dispersion,
    theta = theta, league_acc = league_acc,
    accuracy = acc, raw_accuracy = raw_acc,
    predict = predict_fn, explain = explain,
    expected_shots = expected_shots
  )
}

# Build a one-row fixture frame with the travel columns the model needs.
make_fixture <- function(home, away, venue) {
  nd <- data.frame(home = home, away = away, venue = venue,
                   stringsAsFactors = FALSE)
  th <- travel_flags(nd$home, nd$venue); ta <- travel_flags(nd$away, nd$venue)
  nd$hga_base <- 1 - th$interstate
  nd$away_interstate <- ta$interstate
  nd$away_tz <- ta$tz
  nd
}
