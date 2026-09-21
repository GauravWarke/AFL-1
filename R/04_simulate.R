# NOTE: every bracket function here is prefixed `bakeoff_` so it cannot
# collide with the production chain's versions in 03_simulate.R. Both
# chains are sourced into the same environment by 99_run_all.R.

# Simulate the 2026 finals thousands of times with the winning model.
#
# Why simulation rather than a formula
# ------------------------------------
# A knockout bracket has sequential dependence: who you meet in week 3 depends
# on who won in weeks 1 and 2. Chaining those conditional probabilities by hand
# is possible for a four-team bracket and hopeless for this one, which has a
# wildcard round, a double-chance path, re-seeding, and venue effects that
# change with every possible pairing. Playing the whole tournament out many
# times and counting is exact up to Monte Carlo error and stays readable.
#
# Validating a format nobody has played
# -------------------------------------
# 2026 is the first change to the AFL finals system since 2000, so there is no
# history of this bracket to test against. The two testable things are split:
#
#   * the ENGINE -- rate teams, convert to probabilities, walk a bracket -- is
#     format-independent, so it is checked on 2015-2025 under the old
#     eight-team system where real outcomes exist;
#   * the FORMAT is checked against invariants that must hold for any correct
#     bracket: premierships sum to 1, grand finalists to 2, preliminary
#     finalists to 4, byes to 2, and the wildcard sides claim exactly 2 of the
#     8 places.
#
# 2026 structure
# --------------
# Wildcard week: 7th hosts 10th, 8th hosts 9th. Winners take seeds 7 and 8,
# ordered by original ladder position. Then the standard final-eight system:
#   QF1 1v4, QF2 2v3 (winners get a week off and host a preliminary final)
#   EF1 5v8, EF2 6v7 (losers are out)
#   SF1 = QF1 loser v EF2 winner, SF2 = QF2 loser v EF1 winner
#   PF1 = QF1 winner v SF2 winner, PF2 = QF2 winner v SF1 winner
#   GF at the MCG regardless of who is in it.

source(file.path(PROJ, "R", "02_models.R"))

MCG <- "M.C.G."

# Ladder: 4 points a win, 2 a draw, percentage (a RATIO, not a differential)
# as the tiebreak.
bakeoff_build_ladder <- function(m, season) {
  ha <- m[m$season == season & m$stage == "home_and_away", ]
  to_long(ha) %>%
    group_by(team) %>%
    summarise(played = n(),
              won = sum(margin > 0), drawn = sum(margin == 0),
              pf = sum(score), pa = sum(conceded), .groups = "drop") %>%
    mutate(pts = 4 * won + 2 * drawn,
           percentage = 100 * pf / pa) %>%
    arrange(desc(pts), desc(percentage))
}

bakeoff_home_venues <- function(m, season) {
  ha <- m[m$season == season & m$stage == "home_and_away", ]
  tapply(ha$venue, ha$home, function(v) names(sort(table(v), decreasing = TRUE))[1])
}

# Finals already played, so settled matches are treated as fact instead of
# being re-rolled. Mid-series this is most of the value: once the wildcard
# round and a qualifying final are done, a third of the bracket is known.
bakeoff_known_results <- function(m, season) {
  code <- c(wildcard_final = "WC", qualifying_final = "QF",
            elimination_final = "EF", semi_final = "SF",
            preliminary_final = "PF", grand_final = "GF")
  f <- m[m$season == season & m$stage != "home_and_away" & m$margin != 0, ]
  if (!nrow(f)) return(list())
  # A LIST, not a named character vector. On an atomic vector, x[["missing"]]
  # throws "subscript out of bounds"; on a list it returns NULL, which is what
  # the lookup in play() relies on to mean "not yet played".
  as.list(setNames(
    ifelse(f$margin > 0, f$home, f$away),
    paste0(code[f$stage], "|", pmin(f$home, f$away), "|", pmax(f$home, f$away))
  ))
}

bakeoff_simulate_finals <- function(model, ladder, venues, known = list(),
                            n_sims = 20000L, wildcard = TRUE, seed = 20260905) {
  set.seed(seed)
  need <- if (wildcard) 10L else 8L
  field <- head(ladder$team, need)
  stopifnot(length(field) == need)

  ven <- function(t) if (!is.na(venues[t])) venues[t] else MCG

  # One vectorised probability lookup per distinct fixture, computed once and
  # reused across all simulations. Calling the model inside the simulation loop
  # would be tens of millions of predict() calls.
  pairs <- expand.grid(home = field, away = field, stringsAsFactors = FALSE)
  pairs <- pairs[pairs$home != pairs$away, ]
  pairs$venue <- vapply(pairs$home, ven, character(1))
  pk <- paste(pairs$home, pairs$away, pairs$venue, sep = "|")
  nd <- data.frame(home = pairs$home, away = pairs$away, venue = pairs$venue,
                   stringsAsFactors = FALSE)
  tr <- travel_flags(nd$home, nd$venue); ta <- travel_flags(nd$away, nd$venue)
  nd$hga_base <- 1 - tr$interstate
  nd$away_interstate <- ta$interstate
  nd$away_tz <- ta$tz
  for (f in FEATURES) if (is.null(nd[[f]])) nd[[f]] <- 0
  PROB <- setNames(model$predict(nd)$prob, pk)

  # Grand final is always at the MCG, whoever is in it.
  gf <- expand.grid(home = field, away = field, stringsAsFactors = FALSE)
  gf <- gf[gf$home != gf$away, ]
  gfk <- paste(gf$home, gf$away, MCG, sep = "|")
  ndg <- data.frame(home = gf$home, away = gf$away, venue = MCG,
                    stringsAsFactors = FALSE)
  trg <- travel_flags(ndg$home, MCG); tag <- travel_flags(ndg$away, MCG)
  ndg$hga_base <- 1 - trg$interstate
  ndg$away_interstate <- tag$interstate
  ndg$away_tz <- tag$tz
  for (f in FEATURES) if (is.null(ndg[[f]])) ndg[[f]] <- 0
  PROB_GF <- setNames(model$predict(ndg)$prob, gfk)

  key <- function(stage, a, b) paste0(stage, "|", min(a, b), "|", max(a, b))

  known <- as.list(known)   # tolerate a named vector being passed in
  play <- function(home, away, stage, at_mcg = FALSE) {
    k <- key(stage, home, away)
    if (k %in% names(known)) return(known[[k]])
    p <- if (at_mcg) PROB_GF[[paste(home, away, MCG, sep = "|")]]
         else PROB[[paste(home, away, ven(home), sep = "|")]]
    if (runif(1) < p) home else away
  }
  other <- function(pair, w) pair[pair != w][1]

  cnt <- matrix(0, need, 6,
                dimnames = list(field, c("finals", "week2", "bye",
                                         "prelim", "grand_final", "premier")))

  for (s in seq_len(n_sims)) {
    if (wildcard) {
      w1 <- play(field[7], field[10], "WC")
      w2 <- play(field[8], field[9], "WC")
      surv <- field[sort(match(c(w1, w2), field))]
      eight <- c(field[1:6], surv)
    } else {
      eight <- field[1:8]
    }
    cnt[eight, "finals"] <- cnt[eight, "finals"] + 1

    qf1w <- play(eight[1], eight[4], "QF"); qf1l <- other(eight[c(1,4)], qf1w)
    qf2w <- play(eight[2], eight[3], "QF"); qf2l <- other(eight[c(2,3)], qf2w)
    ef1w <- play(eight[5], eight[8], "EF")
    ef2w <- play(eight[6], eight[7], "EF")

    wk2 <- unique(c(qf1w, qf2w, qf1l, qf2l, ef1w, ef2w))
    cnt[wk2, "week2"] <- cnt[wk2, "week2"] + 1
    cnt[c(qf1w, qf2w), "bye"] <- cnt[c(qf1w, qf2w), "bye"] + 1

    sf1w <- play(qf1l, ef2w, "SF")
    sf2w <- play(qf2l, ef1w, "SF")
    pl <- unique(c(qf1w, qf2w, sf1w, sf2w))
    cnt[pl, "prelim"] <- cnt[pl, "prelim"] + 1

    pf1w <- play(qf1w, sf2w, "PF")
    pf2w <- play(qf2w, sf1w, "PF")
    cnt[c(pf1w, pf2w), "grand_final"] <- cnt[c(pf1w, pf2w), "grand_final"] + 1

    champ <- play(pf1w, pf2w, "GF", at_mcg = TRUE)
    cnt[champ, "premier"] <- cnt[champ, "premier"] + 1
  }

  data.frame(ladder_pos = seq_along(field), team = field,
             as.data.frame(cnt / n_sims), row.names = NULL) %>%
    rename(p_finals = finals, p_week2 = week2, p_bye = bye,
           p_prelim = prelim, p_grand_final = grand_final,
           p_premier = premier)
}

# Structural checks that must hold for ANY correct bracket. These stand in for
# the backtest the new format cannot have.
bakeoff_check_invariants <- function(proj, wildcard = TRUE, tol = 0.02) {
  bad <- character()
  add <- function(cond, msg) if (!cond) bad <<- c(bad, msg)
  add(abs(sum(proj$p_premier) - 1) < 1e-6,
      sprintf("premiers sum to %.4f", sum(proj$p_premier)))
  add(abs(sum(proj$p_grand_final) - 2) < tol,
      sprintf("grand finalists sum to %.3f", sum(proj$p_grand_final)))
  add(abs(sum(proj$p_prelim) - 4) < tol,
      sprintf("prelim finalists sum to %.3f", sum(proj$p_prelim)))
  add(abs(sum(proj$p_bye) - 2) < tol,
      sprintf("byes sum to %.3f", sum(proj$p_bye)))
  add(abs(sum(proj$p_finals) - 8) < tol,
      sprintf("final-eight places sum to %.3f", sum(proj$p_finals)))
  add(all(proj$p_premier <= proj$p_grand_final + 1e-9),
      "a team wins more often than it reaches the grand final")
  if (wildcard) {
    add(all(abs(proj$p_finals[proj$ladder_pos <= 6] - 1) < 1e-9),
        "top six not guaranteed a final-eight place")
    add(abs(sum(proj$p_finals[proj$ladder_pos > 6]) - 2) < tol,
        "wildcard sides do not claim exactly 2 places")
  }
  bad
}
