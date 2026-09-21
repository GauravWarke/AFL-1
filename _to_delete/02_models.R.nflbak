# The seven candidate models, plus the market baseline.
#
# Every model exposes the SAME interface, which is what makes the bake-off
# honest -- none of them gets a bespoke evaluation that flatters it:
#
#     fit_<name>(train)  ->  list(name, predict = function(newdata) ...)
#
# and predict() returns a data.frame with two columns:
#
#     margin  expected home margin, in points
#     prob    probability the home side wins
#
# A model that only predicts margins still has to state a probability, and a
# model that only predicts probabilities still has to state a margin. Both are
# needed downstream: the simulator consumes probabilities, and fans want to
# hear "by about 20 points".
#
# The families were chosen to be genuinely different from each other. Two
# variants of the same idea would just tell us about tuning.

source(file.path(PROJ, "R", "01_data.R"))

TEAMS <- sort(unique(c(load_matches()$home, load_matches()$away)))

# Shared: build the +1/-1 team design matrix used by the linear-family models.
design_matrix <- function(df, teams = TEAMS) {
  n <- nrow(df)
  X <- matrix(0, n, length(teams) + 3,
              dimnames = list(NULL, c(teams, "hga_base",
                                      "away_interstate", "away_tz")))
  X[cbind(seq_len(n), match(df$home, teams))] <-  1
  X[cbind(seq_len(n), match(df$away, teams))] <- -1
  X[, "hga_base"]        <- df$hga_base
  X[, "away_interstate"] <- df$away_interstate
  X[, "away_tz"]         <- df$away_tz
  X
}

# Recency weights. 0.80 per season was tuned by walk-forward in the Python
# implementation; it is re-tuned here for any model that uses it.
season_weights <- function(df, decay = 0.80) {
  (1 - decay)^(max(df$season) - df$season)
}

# =======================================================================
# 1. Elo
# =======================================================================
# The AFL standard -- most of the public models on Squiggle are Elo variants.
# Ratings update after every match by k * (actual - expected), so it is
# naturally recency-weighted with no explicit decay term.
#
# Two details that the workshop version of this got wrong and are handled
# here: k and the home advantage are TUNED on training data rather than set
# to round numbers, and the rating gap is converted to a margin by fitting
# the scale, not by assuming one.
fit_elo <- function(train, k = NULL, hga = NULL) {
  run_elo <- function(df, k, hga) {
    r <- setNames(rep(1500, length(TEAMS)), TEAMS)
    exp_h <- numeric(nrow(df))
    for (i in seq_len(nrow(df))) {
      h <- df$home[i]; a <- df$away[i]
      adv <- hga * df$hga_base[i] + hga * 0.9 * df$away_interstate[i]
      e <- 1 / (1 + 10^(((r[a]) - (r[h] + adv)) / 400))
      exp_h[i] <- e
      s <- if (df$margin[i] > 0) 1 else if (df$margin[i] < 0) 0 else 0.5
      r[h] <- r[h] + k * (s - e)
      r[a] <- r[a] - k * (s - e)
    }
    list(ratings = r, expected = exp_h)
  }

  if (is.null(k) || is.null(hga)) {
    # Tune by log-loss on the training data's own sequence. Elo is fitted
    # sequentially, so each prediction is already out-of-sample with respect
    # to the match it predicts -- no separate holdout is needed.
    grid <- expand.grid(k = c(10, 15, 20, 25, 30, 40), hga = c(20, 40, 60, 80))
    y <- ifelse(train$margin > 0, 1, ifelse(train$margin < 0, 0, 0.5))
    grid$ll <- apply(grid, 1, function(g) {
      e <- run_elo(train, g[["k"]], g[["hga"]])$expected
      log_loss(e, y)
    })
    best <- grid[which.min(grid$ll), ]
    k <- best$k; hga <- best$hga
  }

  fin <- run_elo(train, k, hga)
  r <- fin$ratings

  # Convert rating gap to points. Fitted, not assumed.
  gap <- r[train$home] - r[train$away] +
    hga * train$hga_base + hga * 0.9 * train$away_interstate
  sc <- lm(train$margin ~ gap)
  sigma <- sd(residuals(sc))

  list(
    name = "Elo",
    k = k, hga = hga, ratings = r, sigma = sigma,
    predict = function(nd) {
      g <- r[nd$home] - r[nd$away] +
        hga * nd$hga_base + hga * 0.9 * nd$away_interstate
      mg <- as.numeric(coef(sc)[1] + coef(sc)[2] * g)
      # Elo's own logistic is used for the probability rather than the normal
      # CDF on the fitted margin: it is the model's native statement of
      # confidence, and converting through margins would discard it.
      data.frame(margin = mg,
                 prob = 1 / (1 + 10^(-as.numeric(g) / 400)))
    }
  )
}

# =======================================================================
# 2. Ridge margin model
# =======================================================================
# The current champion from the Python implementation. Team strengths under an
# L2 penalty, where lambda = sigma^2 / tau^2 makes the penalty the empirical
# Bayes posterior mean rather than an arbitrary tuning knob.
fit_ridge <- function(train, decay = 0.80) {
  X <- design_matrix(train)
  y <- train$margin
  w <- season_weights(train, decay)
  sw <- sqrt(w)
  Xw <- X * sw; yw <- y * sw
  p_team <- length(TEAMS)

  solve_pen <- function(l2) {
    pen <- c(rep(l2, p_team), rep(0, 3))   # never penalise home advantage
    A <- crossprod(Xw) + diag(pen)
    tryCatch(solve(A, crossprod(Xw, yw)),
             error = function(e) MASS::ginv(A) %*% crossprod(Xw, yw))
  }

  b0 <- solve_pen(1)
  r0 <- yw - Xw %*% b0
  eff_n <- sum(w)
  sig2 <- sum(r0^2) / max(eff_n - ncol(X), 1)
  tau2 <- var(b0[seq_len(p_team)])
  lam  <- sig2 / max(tau2, 1e-9)

  b <- solve_pen(lam)
  resid <- yw - Xw %*% b
  # resid is already sqrt-weight-scaled, so this is the WEIGHTED sum of
  # squares. Dividing by nrow() instead of the effective n would understate
  # sigma by ~15% at decay 0.8 -- a bug caught by a Q-Q plot in the sibling
  # NFL project.
  sigma <- sqrt(sum(resid^2) / max(eff_n - ncol(X) - 1, 1))

  strengths <- setNames(as.numeric(b[seq_len(p_team)]), TEAMS)
  strengths <- strengths - mean(strengths)
  hga <- setNames(as.numeric(b[p_team + 1:3]),
                  c("hga_base", "away_interstate", "away_tz"))

  list(
    name = "Ridge margin", lambda = lam, sigma = sigma,
    strengths = strengths, hga = hga,
    predict = function(nd) {
      mg <- strengths[nd$home] - strengths[nd$away] +
        hga["hga_base"] * nd$hga_base +
        hga["away_interstate"] * nd$away_interstate +
        hga["away_tz"] * nd$away_tz
      mg <- as.numeric(mg)
      data.frame(margin = mg, prob = prob_from_margin(mg, sigma))
    }
  )
}

# =======================================================================
# 3. Bradley-Terry (penalised logistic on win/loss)
# =======================================================================
# Throws away the margin and models only who won. That is a real loss of
# information -- a 100-point win and a 1-point win count the same -- so this
# model is here to measure how much that costs. Ridge-penalised via glmnet
# because unpenalised team dummies separate when a side is undefeated.
fit_bt <- function(train, decay = 0.80) {
  tr <- train[train$margin != 0, ]   # draws carry no win/loss signal
  X <- design_matrix(tr)
  y <- as.numeric(tr$margin > 0)
  w <- season_weights(tr, decay)

  pf <- c(rep(1, length(TEAMS)), 0, 0, 0)   # home advantage unpenalised
  cv <- glmnet::cv.glmnet(X, y, family = "binomial", alpha = 0,
                          weights = w, penalty.factor = pf, nfolds = 5)
  b <- as.numeric(coef(cv, s = "lambda.min"))
  names(b) <- c("(Intercept)", colnames(X))

  # A probability model still owes us a margin. Regress observed margins on
  # the fitted log-odds so the two outputs come from the same fit.
  lo <- b["(Intercept)"] + as.numeric(X %*% b[colnames(X)])
  sc <- lm(tr$margin ~ lo)

  list(
    name = "Bradley-Terry", lambda = cv$lambda.min,
    predict = function(nd) {
      Xn <- design_matrix(nd)
      lo <- b["(Intercept)"] + as.numeric(Xn %*% b[colnames(Xn)])
      data.frame(margin = as.numeric(coef(sc)[1] + coef(sc)[2] * lo),
                 prob = 1 / (1 + exp(-lo)))
    }
  )
}

# =======================================================================
# 4. Scoring-shots + accuracy model  (the AFL-native one)
# =======================================================================
# Builds a score the way the sport actually builds one: a team generates
# scoring shots, then converts some of them into goals. Shots are modelled as
# an over-dispersed count (negative binomial), conversion as binomial.
#
# This is the model that most directly encodes the domain finding -- shots are
# skill (reliability 0.88), accuracy is mostly luck (0.32) -- so accuracy is
# pooled hard toward the league mean rather than fitted per team.
fit_shots <- function(train, decay = 0.80, nsim = 400L) {
  long <- to_long(train)
  long$hga_base <- train$hga_base[match(long$game_id, train$game_id)]
  long$is_home  <- long$at_home
  long$w <- (1 - decay)^(max(long$season) - long$season)

  # Attack: shots generated. Defence: shots conceded. Both as team effects.
  nb <- try(MASS::glm.nb(shots ~ team + opp + is_home, data = long,
                         weights = long$w), silent = TRUE)
  if (inherits(nb, "try-error")) {
    nb <- glm(shots ~ team + opp + is_home, family = poisson,
              data = long, weights = long$w)
    theta <- Inf
  } else {
    theta <- nb$theta
  }

  # Accuracy: league rate, with a shrunk team offset. The shrinkage factor is
  # the measured reliability of accuracy, so a team keeps only the third of
  # its accuracy edge that has been shown to repeat.
  acc_tab <- long %>% group_by(team) %>%
    summarise(g = sum(goals), s = sum(shots), .groups = "drop")
  league_acc <- sum(acc_tab$g) / sum(acc_tab$s)
  RELIABILITY <- 0.324
  acc <- setNames(
    league_acc + RELIABILITY * (acc_tab$g / acc_tab$s - league_acc),
    acc_tab$team)

  list(
    name = "Shots + accuracy", theta = theta, league_acc = league_acc,
    predict = function(nd) {
      mk <- function(tm, op, home) data.frame(
        team = factor(tm, levels = levels(factor(long$team))),
        opp  = factor(op, levels = levels(factor(long$opp))),
        is_home = home)
      lh <- predict(nb, mk(nd$home, nd$away, 1L), type = "response")
      la <- predict(nb, mk(nd$away, nd$home, 0L), type = "response")
      ah <- ifelse(is.na(acc[nd$home]), league_acc, acc[nd$home])
      aa <- ifelse(is.na(acc[nd$away]), league_acc, acc[nd$away])

      # Simulate rather than solve: the score is a compound distribution
      # (negative binomial shots, binomial conversion) with no tidy closed
      # form for P(win). Simulation is exact up to Monte Carlo error and
      # takes milliseconds.
      n <- nrow(nd)
      mgs <- matrix(0, nsim, n)
      for (s in seq_len(nsim)) {
        sh <- if (is.finite(theta)) rnbinom(n, mu = lh, size = theta) else rpois(n, lh)
        sa <- if (is.finite(theta)) rnbinom(n, mu = la, size = theta) else rpois(n, la)
        gh <- rbinom(n, sh, ah); ga <- rbinom(n, sa, aa)
        mgs[s, ] <- (gh * 6 + (sh - gh)) - (ga * 6 + (sa - ga))
      }
      data.frame(margin = colMeans(mgs),
                 prob = colMeans(mgs > 0) + 0.5 * colMeans(mgs == 0))
    }
  )
}

# =======================================================================
# 5. Random forest
# =======================================================================
# On lagged form differences. Included because it is what the AFL workshop
# material reaches for, and because it is worth measuring rather than
# assuming whether a flexible learner beats a structured one here.
fit_rf <- function(train, ntree = 400L) {
  d <- train[complete.cases(train[, FEATURES]), ]
  rf <- randomForest::randomForest(
    x = d[, FEATURES], y = d$margin, ntree = ntree, nodesize = 10)
  sigma <- sd(d$margin - predict(rf, d[, FEATURES]))
  list(
    name = "Random forest", sigma = sigma,
    predict = function(nd) {
      x <- nd[, FEATURES]
      for (j in FEATURES) x[[j]][is.na(x[[j]])] <- 0
      mg <- as.numeric(predict(rf, x))
      data.frame(margin = mg, prob = prob_from_margin(mg, sigma))
    }
  )
}

# =======================================================================
# 6. Gradient boosting (xgboost)
# =======================================================================
fit_xgb <- function(train, nrounds = 300L) {
  d <- train[complete.cases(train[, FEATURES]), ]
  dm <- xgboost::xgb.DMatrix(as.matrix(d[, FEATURES]), label = d$margin)
  bst <- xgboost::xgb.train(
    params = list(objective = "reg:squarederror", eta = 0.03,
                  max_depth = 3, subsample = 0.8, colsample_bytree = 0.8,
                  min_child_weight = 10, nthread = 4),
    data = dm, nrounds = nrounds, verbose = 0)
  sigma <- sd(d$margin - predict(bst, as.matrix(d[, FEATURES])))
  list(
    name = "Gradient boosting", sigma = sigma,
    predict = function(nd) {
      x <- nd[, FEATURES]
      for (j in FEATURES) x[[j]][is.na(x[[j]])] <- 0
      mg <- as.numeric(predict(bst, as.matrix(x)))
      data.frame(margin = mg, prob = prob_from_margin(mg, sigma))
    }
  )
}

# =======================================================================
# 7. Bayesian hierarchical model (Gibbs sampler)
# =======================================================================
# margin ~ Normal(s_home - s_away + HGA, sigma^2),  s_t ~ Normal(0, tau^2)
#
# Written as a conjugate Gibbs sampler rather than fitted with rstanarm or
# brms. Those are not installed, and on Windows they need a Stan toolchain and
# several minutes per fit -- which would be refitted every round here. The
# normal-normal model is fully conjugate, so a sampler is about forty lines and
# runs in a fraction of a second. Nothing is given up: this IS the posterior,
# not an approximation to it.
#
# The payoff over the ridge model is that tau and sigma are learned jointly
# with the strengths and carry their own uncertainty, and the posterior draws
# feed the simulator directly instead of a point estimate plus a guess.
fit_bayes <- function(train, decay = 0.80, iter = 1500L, burn = 500L) {
  X <- design_matrix(train)
  w <- season_weights(train, decay)
  sw <- sqrt(w)
  Xw <- X * sw; yw <- train$margin * sw
  p <- ncol(X); p_team <- length(TEAMS)
  XtX <- crossprod(Xw); Xty <- crossprod(Xw, yw)

  # Weakly informative priors. tau and sigma get inverse-gamma(2, .) priors,
  # which are proper but flat enough that 2,000+ matches dominate them.
  a0 <- 2; b0_sig <- 2 * 30^2; b0_tau <- 2 * 10^2
  beta <- rep(0, p); sigma2 <- 30^2; tau2 <- 10^2
  keep <- matrix(0, iter - burn, p + 2)

  for (it in seq_len(iter)) {
    # beta | rest  -- Gaussian, penalty only on team strengths
    pen <- c(rep(sigma2 / tau2, p_team), rep(1e-8, 3))
    A <- XtX + diag(pen)
    L <- chol(A)
    mu <- backsolve(L, backsolve(L, Xty, transpose = TRUE))
    beta <- as.numeric(mu + backsolve(L, rnorm(p) * sqrt(sigma2)))

    # sigma^2 | rest  -- inverse gamma
    r <- yw - Xw %*% beta
    sigma2 <- 1 / rgamma(1, a0 + sum(w) / 2, b0_sig / 2 + sum(r^2) / 2)

    # tau^2 | rest  -- inverse gamma over the team strengths only
    st <- beta[seq_len(p_team)]
    tau2 <- 1 / rgamma(1, a0 + p_team / 2, b0_tau / 2 + sum(st^2) / 2)

    if (it > burn) keep[it - burn, ] <- c(beta, sigma2, tau2)
  }

  post_beta <- keep[, seq_len(p), drop = FALSE]
  colnames(post_beta) <- colnames(X)
  beta_hat <- colMeans(post_beta)
  sigma_hat <- sqrt(mean(keep[, p + 1]))

  strengths <- beta_hat[seq_len(p_team)]
  strengths <- strengths - mean(strengths)
  # Posterior sd of each team's strength -- the thing the point-estimate
  # models cannot give us.
  strength_sd <- apply(post_beta[, seq_len(p_team), drop = FALSE], 2, sd)

  list(
    name = "Bayesian hierarchical", sigma = sigma_hat,
    strengths = strengths, strength_sd = strength_sd,
    tau = sqrt(mean(keep[, p + 2])), post = post_beta,
    predict = function(nd) {
      Xn <- design_matrix(nd)
      # Posterior predictive: average the win probability over draws rather
      # than computing it once at the posterior mean. That is what makes the
      # intervals honest -- uncertainty about the ratings widens the
      # probability instead of being silently dropped.
      draws <- Xn %*% t(post_beta)                       # n x ndraw
      mg <- rowMeans(draws)
      sd_draw <- sqrt(mean(keep[, p + 1]))
      pr <- rowMeans(pnorm(draws / sd_draw))
      data.frame(margin = as.numeric(mg), prob = as.numeric(pr))
    }
  )
}

# =======================================================================
# Registry
# =======================================================================
MODELS <- list(
  elo      = fit_elo,
  ridge    = fit_ridge,
  bt       = fit_bt,
  shots    = fit_shots,
  rf       = fit_rf,
  xgb      = fit_xgb,
  bayes    = fit_bayes
)
