# The bake-off: which model actually predicts AFL matches best?
#
# Protocol
# --------
# Walk-forward through the 2026 season, one round at a time. Before each round,
# every model is refitted from scratch on every match played before it -- all
# prior seasons plus the current season to date. No model ever sees a result it
# is being asked to predict.
#
# 2026 is the evaluation window because that is the window the 31 public models
# on Squiggle are scored over, so our numbers and theirs are directly
# comparable. Comparing a model tested on 2018-2026 against a leaderboard
# covering 2026 alone would be meaningless.
#
# Scoring
# -------
# LOG-LOSS is the headline. This system feeds a Monte Carlo simulator, so what
# matters is whether the stated probabilities are right, not just whether the
# favourite is picked. A model that says 90% when it means 60% will produce a
# confidently wrong premiership table.
#
# Tipping percentage is reported because it is what the public leaderboards
# quote, but it is a poor primary metric: it collapses a probability to its
# sign and throws the rest away.

source(file.path(PROJ, "R", "02_models.R"))

run_bakeoff <- function(eval_season = 2026, models = MODELS, verbose = TRUE) {
  feat <- build_features(load_matches())
  ev <- feat[feat$season == eval_season, ]
  rounds <- sort(unique(ev$round))

  preds <- list()
  for (rnd in rounds) {
    test  <- ev[ev$round == rnd, ]
    train <- feat[feat$season < eval_season |
                  (feat$season == eval_season & feat$round < rnd), ]
    train <- train[train$stage == "home_and_away", ]
    if (nrow(train) < 400 || nrow(test) == 0) next

    for (nm in names(models)) {
      out <- try({
        fm <- suppressWarnings(models[[nm]](train))
        pr <- fm$predict(test)
        data.frame(model = nm, round = rnd, game_id = test$game_id,
                   margin_pred = pr$margin, prob = pr$prob,
                   margin_act = test$margin, home_win = test$home_win)
      }, silent = TRUE)
      if (!inherits(out, "try-error")) preds[[length(preds) + 1]] <- out
    }
    if (verbose) cat("round", rnd, "done\n")
  }
  bind_rows(preds)
}

# Resumable version. Refitting seven models for every round of a season takes
# minutes, and a single long-running call blocks the R session. This writes one
# file per round as it goes, skips rounds already done, and can therefore be
# called repeatedly until it reports complete. It also means a crash costs one
# round rather than the whole run.
bakeoff_chunk <- function(eval_season = 2026, max_rounds = 4L,
                          models = MODELS) {
  dir.create(p_out("bakeoff"), showWarnings = FALSE, recursive = TRUE)
  feat <- build_features(load_matches())
  ev <- feat[feat$season == eval_season, ]
  rounds <- sort(unique(ev$round))

  done <- gsub("^r|\\.rds$", "",
               list.files(p_out("bakeoff"), pattern = "^r.*\\.rds$"))
  todo <- setdiff(as.character(rounds), done)
  if (!length(todo)) return(list(complete = TRUE, remaining = 0))

  for (rs in head(todo, max_rounds)) {
    rnd <- as.numeric(rs)
    test  <- ev[ev$round == rnd, ]
    train <- feat[(feat$season < eval_season |
                   (feat$season == eval_season & feat$round < rnd)) &
                  feat$stage == "home_and_away", ]
    if (nrow(train) < 400 || nrow(test) == 0) {
      saveRDS(data.frame(), p_out("bakeoff", paste0("r", rs, ".rds")))
      next
    }
    acc <- list()
    for (nm in names(models)) {
      out <- try({
        fm <- suppressWarnings(models[[nm]](train))
        pr <- fm$predict(test)
        data.frame(model = nm, round = rnd, game_id = test$game_id,
                   margin_pred = pr$margin, prob = pr$prob,
                   margin_act = test$margin, home_win = test$home_win)
      }, silent = TRUE)
      if (!inherits(out, "try-error")) acc[[nm]] <- out
    }
    saveRDS(bind_rows(acc), p_out("bakeoff", paste0("r", rs, ".rds")))
  }

  done2 <- length(list.files(p_out("bakeoff"), pattern = "^r.*\\.rds$"))
  list(complete = done2 >= length(rounds),
       remaining = length(rounds) - done2)
}

collect_bakeoff <- function() {
  fs <- list.files(p_out("bakeoff"), pattern = "^r.*\\.rds$", full.names = TRUE)
  bind_rows(lapply(fs, readRDS))
}

score_bakeoff <- function(preds) {
  preds %>%
    group_by(model) %>%
    summarise(
      n       = n(),
      logloss = log_loss(prob, home_win),
      brier   = brier(prob, home_win),
      tip     = 100 * tip_rate(margin_pred, margin_act),
      mae     = margin_mae(margin_pred, margin_act),
      # Calibration slope: regress the outcome on the stated log-odds. 1.0 is
      # perfect. Below 1 means the model is overconfident -- its probabilities
      # are too far from 50% -- which matters more here than raw accuracy,
      # because overconfidence compounds across four knockout rounds.
      calib   = tryCatch({
        lo <- log(pmin(pmax(prob, 1e-6), 1 - 1e-6) /
                  (1 - pmin(pmax(prob, 1e-6), 1 - 1e-6)))
        as.numeric(coef(glm(home_win ~ lo, family = binomial))[2])
      }, error = function(e) NA_real_),
      .groups = "drop") %>%
    arrange(logloss)
}

# Paired bootstrap over matches: is the gap between two models real, or is it
# the sample? The models are scored on the SAME matches, so their errors are
# dependent and separate confidence intervals would be misleading.
compare_models <- function(preds, a, b, B = 2000L) {
  wide <- preds %>%
    filter(model %in% c(a, b)) %>%
    select(model, game_id, prob, home_win) %>%
    pivot_wider(names_from = model, values_from = prob) %>%
    filter(!is.na(.data[[a]]), !is.na(.data[[b]]))

  d_obs <- log_loss(wide[[a]], wide$home_win) - log_loss(wide[[b]], wide$home_win)
  n <- nrow(wide)
  d <- replicate(B, {
    i <- sample.int(n, n, replace = TRUE)
    log_loss(wide[[a]][i], wide$home_win[i]) -
      log_loss(wide[[b]][i], wide$home_win[i])
  })
  list(a = a, b = b, diff = d_obs,
       lo = unname(quantile(d, 0.025)), hi = unname(quantile(d, 0.975)),
       p = 2 * min(mean(d <= 0), mean(d >= 0)))
}
