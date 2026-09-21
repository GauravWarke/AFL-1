# Shared setup: paths, packages, helpers.
# Sourced by every other script. Nothing here does work of its own.

PROJ <- "C:/Users/GAURAV/OneDrive/Desktop/AFL"

suppressPackageStartupMessages({
  library(dplyr)
  library(tidyr)
})

p_data  <- function(...) file.path(PROJ, "data", "processed", ...)
p_out   <- function(...) file.path(PROJ, "outputs", ...)
p_fig   <- function(...) file.path(PROJ, "outputs", "figures", ...)
for (d in c(p_data(), p_out(), p_fig())) dir.create(d, recursive = TRUE,
                                                    showWarnings = FALSE)

# --- scoring rules -----------------------------------------------------
# These are the four numbers every model is judged on. Log-loss is the one
# that matters most here: the finals simulator consumes PROBABILITIES, so a
# model that picks winners well but states its confidence badly will produce
# a badly wrong premiership table. Tipping percentage is reported because it
# is what the public leaderboards quote, not because it is the best measure --
# it throws away everything except the sign.

log_loss <- function(p, y) {
  p <- pmin(pmax(p, 1e-9), 1 - 1e-9)
  -mean(y * log(p) + (1 - y) * log(1 - p))
}

brier <- function(p, y) mean((p - y)^2)

# Draws score half a tip, which is the convention Squiggle's leaderboard uses,
# so our numbers are comparable with theirs.
tip_rate <- function(pred_margin, actual_margin) {
  hit <- ifelse(actual_margin == 0, 0.5,
                as.numeric(sign(pred_margin) == sign(actual_margin)))
  mean(hit)
}

margin_mae <- function(pred_margin, actual_margin) {
  mean(abs(pred_margin - actual_margin))
}

# Normal CDF turning an expected margin into a win probability. sigma is the
# model's own residual spread, so a model that fits tightly is allowed to be
# more confident -- and is punished by log-loss if that confidence is false.
prob_from_margin <- function(margin, sigma) pnorm(margin / sigma)

# --- small utilities ---------------------------------------------------
`%||%` <- function(a, b) if (is.null(a)) b else a

banner <- function(txt) {
  cat("\n", strrep("=", 70), "\n", txt, "\n", strrep("=", 70), "\n", sep = "")
}

fmt_row <- function(...) cat(sprintf(...), "\n", sep = "")
