# Simulate the 2026 finals, fast enough to be interactive.
#
# Why simulate at all
# -------------------
# A knockout bracket has sequential dependence: who you meet in week three
# depends on who won weeks one and two. For this bracket -- a wildcard round, a
# double-chance path, re-seeding, and a home ground that changes with every
# possible pairing -- chaining those conditional probabilities by hand is
# hopeless. Playing September out many times and counting is exact up to Monte
# Carlo error and stays readable.
#
# Why VECTORISED
# --------------
# The first version looped over simulations, one tournament at a time. That
# took about 7 seconds for 20,000 runs -- fine for a report, useless for a
# what-if explorer where someone drags a control and expects the numbers to
# move. This version carries all simulations through the bracket at once as
# integer vectors of team indices, so the whole tournament is about thirty
# vector operations regardless of how many times it is run.
#
# The bracket (2026)
# ------------------
# Wildcard: 7 hosts 10, 8 hosts 9. Winners take seeds 7 and 8, ordered by
#           original ladder position. Losers out. Seeds 1-6 skip the week.
# Week 1:   QF1 1v4, QF2 2v3 (winners: week off, then host a preliminary final)
#           EF1 5v8, EF2 6v7 (losers out)
# Week 2:   SF1 = QF1 loser v EF1 winner, SF2 = QF2 loser v EF2 winner
# Week 3:   PF1 = QF1 winner v SF2 winner, PF2 = QF2 winner v SF1 winner
# Week 4:   Grand Final, at the MCG whoever is in it.

source(file.path(PROJ, "R", "02_model.R"))

MCG <- "M.C.G."

build_ladder <- function(m, season) {
  ha <- m[m$season == season & m$stage == "home_and_away", ]
  to_long(ha) %>%
    group_by(team) %>%
    summarise(played = n(), won = sum(margin > 0), lost = sum(margin < 0),
              drawn = sum(margin == 0), pf = sum(score), pa = sum(conceded),
              .groups = "drop") %>%
    # 4 points a win, 2 a draw. The tiebreak is PERCENTAGE -- points for divided
    # by points against -- which is a ratio, not a differential.
    mutate(pts = 4 * won + 2 * drawn, percentage = 100 * pf / pa) %>%
    arrange(desc(pts), desc(percentage)) %>%
    mutate(pos = row_number())
}

home_venues <- function(m, season) {
  ha <- m[m$season == season & m$stage == "home_and_away", ]
  tapply(ha$venue, ha$home, function(v) names(sort(table(v), decreasing = TRUE))[1])
}

known_results <- function(m, season) {
  code <- c(wildcard_final = "WC", qualifying_final = "QF",
            elimination_final = "EF", semi_final = "SF",
            preliminary_final = "PF", grand_final = "GF")
  f <- m[m$season == season & m$stage != "home_and_away" & m$margin != 0, ]
  if (!nrow(f)) return(list())
  # A LIST, not a named vector: x[["missing"]] returns NULL on a list but throws
  # "subscript out of bounds" on an atomic vector, and the lookup below relies
  # on the NULL to mean "not played yet".
  as.list(setNames(ifelse(f$margin > 0, f$home, f$away),
                   paste0(code[f$stage], "|", pmin(f$home, f$away), "|",
                          pmax(f$home, f$away))))
}

# Pairwise win-probability matrix over the finals field, computed once. P[i, j]
# is the chance team i beats team j with i hosting at i's home ground; PG is the
# same at the MCG for the grand final.
finals_prob_matrix <- function(model, field, venues, nsim = 4000L) {
  n <- length(field)
  grid <- expand.grid(hi = seq_len(n), ai = seq_len(n))
  grid <- grid[grid$hi != grid$ai, ]
  ven <- function(t) if (!is.na(venues[t])) unname(venues[t]) else MCG

  nd <- make_fixture(field[grid$hi], field[grid$ai],
                     vapply(field[grid$hi], ven, character(1)))
  ndg <- make_fixture(field[grid$hi], field[grid$ai], rep(MCG, nrow(grid)))

  P <- matrix(0.5, n, n, dimnames = list(field, field))
  PG <- P
  P[cbind(grid$hi, grid$ai)]  <- model$predict(nd,  n = nsim)$prob
  PG[cbind(grid$hi, grid$ai)] <- model$predict(ndg, n = nsim)$prob
  list(P = P, PG = PG, field = field)
}

# Vectorised match: home and away are integer vectors of team indices, one entry
# per simulation. Returns winner and loser indices.
vplay <- function(home, away, P, stage, known, field, rng_draw) {
  n <- length(home)
  p <- P[cbind(home, away)]
  # Overwrite with reality wherever this exact fixture has already been played.
  if (length(known)) {
    a <- field[home]; b <- field[away]
    k <- paste0(stage, "|", pmin(a, b), "|", pmax(a, b))
    hit <- k %in% names(known)
    if (any(hit)) {
      w <- unlist(known[k[hit]], use.names = FALSE)
      p[hit] <- as.numeric(w == a[hit])   # 1 if the home side really won, else 0
    }
  }
  hw <- rng_draw < p
  list(w = ifelse(hw, home, away), l = ifelse(hw, away, home))
}

simulate_finals <- function(model, ladder, venues, known = list(),
                            n_sims = 20000L, wildcard = TRUE, seed = 20260905,
                            probs = NULL, force = list()) {
  set.seed(seed)
  need <- if (wildcard) 10L else 8L
  field <- head(ladder$team, need)
  stopifnot(length(field) == need)

  if (is.null(probs)) probs <- finals_prob_matrix(model, field, venues)
  P <- probs$P; PG <- probs$PG
  # `force` lets the app ask "what if Geelong wins?" -- it is merged in exactly
  # like a real result, so a hypothetical and a fact are handled by one path.
  known <- c(as.list(known), as.list(force))

  N <- n_sims
  idx <- function(t) match(t, field)
  R <- function() runif(N)

  cnt <- matrix(0L, need, 6,
                dimnames = list(field, c("finals", "week2", "bye", "prelim",
                                         "grand_final", "premier")))
  bump <- function(v, col) {
    tb <- tabulate(v, nbins = need)
    cnt[, col] <<- cnt[, col] + tb
  }
  # A team may reach a stage by more than one route within a single simulation
  # only if the bracket is wrong, so counting with tabulate over the winner
  # vectors is safe and is what makes this vectorisable.

  if (wildcard) {
    wc1 <- vplay(rep(idx(field[7]), N), rep(idx(field[10]), N), P, "WC",
                 known, field, R())
    wc2 <- vplay(rep(idx(field[8]), N), rep(idx(field[9]), N), P, "WC",
                 known, field, R())
    # Winners take seeds 7 and 8 ordered by original ladder position.
    s7 <- pmin(wc1$w, wc2$w); s8 <- pmax(wc1$w, wc2$w)
    seed7 <- s7; seed8 <- s8
  } else {
    seed7 <- rep(idx(field[7]), N); seed8 <- rep(idx(field[8]), N)
  }
  eight <- cbind(rep(idx(field[1]), N), rep(idx(field[2]), N),
                 rep(idx(field[3]), N), rep(idx(field[4]), N),
                 rep(idx(field[5]), N), rep(idx(field[6]), N), seed7, seed8)
  for (j in 1:8) bump(eight[, j], "finals")

  qf1 <- vplay(eight[, 1], eight[, 4], P, "QF", known, field, R())
  qf2 <- vplay(eight[, 2], eight[, 3], P, "QF", known, field, R())
  ef1 <- vplay(eight[, 5], eight[, 8], P, "EF", known, field, R())
  ef2 <- vplay(eight[, 6], eight[, 7], P, "EF", known, field, R())

  for (v in list(qf1$w, qf2$w, qf1$l, qf2$l, ef1$w, ef2$w)) bump(v, "week2")
  bump(qf1$w, "bye"); bump(qf2$w, "bye")

  # Semi-final pairing: QF1 loser meets EF1 winner, QF2 loser meets EF2
  # winner. There is no crossover at this stage -- the crossover happens a
  # week later, at the preliminary finals.
  #
  # An earlier version had these swapped (QF1 loser v EF2 winner). It looked
  # plausible and it survived the invariant checks, because swapping two
  # symmetric branches still produces a valid bracket where every probability
  # sums correctly. What it did NOT do was match the fixtures the AFL
  # actually played, so once real semi-final results arrived the simulator
  # could not find them in `known` and quietly re-simulated games that had
  # already been decided. Teams that were out of the competition kept
  # showing a premiership chance. Structural checks cannot catch this; only
  # comparing against the real draw can.
  sf1 <- vplay(qf1$l, ef1$w, P, "SF", known, field, R())
  sf2 <- vplay(qf2$l, ef2$w, P, "SF", known, field, R())
  for (v in list(qf1$w, qf2$w, sf1$w, sf2$w)) bump(v, "prelim")

  pf1 <- vplay(qf1$w, sf2$w, P, "PF", known, field, R())
  pf2 <- vplay(qf2$w, sf1$w, P, "PF", known, field, R())
  bump(pf1$w, "grand_final"); bump(pf2$w, "grand_final")

  gf <- vplay(pf1$w, pf2$w, PG, "GF", known, field, R())
  bump(gf$w, "premier")

  out <- data.frame(ladder_pos = seq_along(field), team = field,
                    as.data.frame(cnt / N), row.names = NULL)
  names(out)[3:8] <- paste0("p_", names(out)[3:8])
  out
}

# Structural checks that must hold for ANY correct bracket. These stand in for
# the backtest that a brand-new format cannot have.
check_invariants <- function(proj, wildcard = TRUE, tol = 0.02) {
  bad <- character()
  add <- function(cond, msg) if (!isTRUE(cond)) bad <<- c(bad, msg)
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
      "a side wins more often than it reaches the grand final")
  if (wildcard) {
    add(all(abs(proj$p_finals[proj$ladder_pos <= 6] - 1) < 1e-9),
        "top six not guaranteed a final-eight place")
    add(abs(sum(proj$p_finals[proj$ladder_pos > 6]) - 2) < tol,
        "wildcard sides do not claim exactly 2 places")
  }
  bad
}

# Which matches are still to be played, given what is known. Drives both the
# fixture list and the what-if explorer.
remaining_fixtures <- function(ladder, known, venues) {
  field <- head(ladder$team, 10)
  eight <- field[1:6]
  wcw <- c()
  for (k in names(known)) if (startsWith(k, "WC")) wcw <- c(wcw, known[[k]])
  if (length(wcw) == 2) eight <- c(eight, field[sort(match(wcw, field))])
  if (length(eight) < 8) return(data.frame())

  ven <- function(t) if (!is.na(venues[t])) unname(venues[t]) else MCG
  won <- function(stage, a, b) {
    k <- paste0(stage, "|", min(a, b), "|", max(a, b))
    if (k %in% names(known)) known[[k]] else NA_character_
  }
  loser <- function(a, b, w) if (is.na(w)) NA_character_ else if (w == a) b else a

  rows <- list()
  add <- function(stage, label, a, b, venue) {
    w <- won(stage, a, b)
    rows[[length(rows) + 1]] <<- data.frame(
      stage = stage, label = label, home = a, away = b, venue = venue,
      winner = w, played = !is.na(w), stringsAsFactors = FALSE)
    w
  }
  q1 <- add("QF", "Qualifying Final 1", eight[1], eight[4], ven(eight[1]))
  q2 <- add("QF", "Qualifying Final 2", eight[2], eight[3], ven(eight[2]))
  e1 <- add("EF", "Elimination Final 1", eight[5], eight[8], ven(eight[5]))
  e2 <- add("EF", "Elimination Final 2", eight[6], eight[7], ven(eight[6]))

  # Week 2. Each match can only be named once the week before it is settled,
  # which is why this chains rather than listing everything up front.
  q1l <- loser(eight[1], eight[4], q1); q2l <- loser(eight[2], eight[3], q2)
  s1 <- if (!is.na(q1l) && !is.na(e1)) add("SF", "Semi-Final 1", q1l, e1, ven(q1l)) else NA_character_
  s2 <- if (!is.na(q2l) && !is.na(e2)) add("SF", "Semi-Final 2", q2l, e2, ven(q2l)) else NA_character_

  # Week 3. The crossover: each qualifying-final winner hosts the OTHER
  # semi-final's winner.
  p1 <- if (!is.na(q1) && !is.na(s2)) add("PF", "Preliminary Final 1", q1, s2, ven(q1)) else NA_character_
  p2 <- if (!is.na(q2) && !is.na(s1)) add("PF", "Preliminary Final 2", q2, s1, ven(q2)) else NA_character_

  # Week 4. Always the MCG, whoever is in it. Without this row the Grand
  # Final never appeared in the fixture list at all, so the app showed
  # "0 matches still to play" on Grand Final week.
  if (!is.na(p1) && !is.na(p2)) add("GF", "Grand Final", p1, p2, MCG)

  bind_rows(rows)
}
