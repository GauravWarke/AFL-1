# Grand Final week, and the "who's asking?" layer.
#
# Two things live in this file.
#
# The first is the Grand Final section, which only matters for one week a year
# and is worth having for exactly that reason. It answers the three things
# people argue about on Grand Final morning: how long has this club been
# waiting, have they been here before, and do teams really go to pieces under
# pressure.
#
# The second is the part that makes this dashboard different from every other
# footy predictor. The same numbers get read very differently depending on who
# is looking. A supporter wants to know if their team can win. A football
# department wants to know what is repeatable and what was noise. Someone on
# the commercial side wants to know how many more weeks of finals content they
# are likely to get. Same model, same numbers, three translations. Nobody has
# to learn statistics to get something useful out of it.
#
# Nothing here changes a prediction. It is all read-only reporting over the
# match table and the model output.

source(file.path(PROJ, "R", "04_insights.R"))

# =======================================================================
# The drought clock
# =======================================================================
# Years since this club last won a flag. Purely descriptive, but it is the
# one number every supporter wants framed properly on the day.
gf_drought <- function(m, team, as_of = Sys.Date()) {
  gfs <- m[m$stage == "grand_final" & m$margin != 0, ]
  won <- gfs[ifelse(gfs$margin > 0, gfs$home, gfs$away) == team, ]
  if (!nrow(won)) {
    return(list(team = team, last_flag = NA, years = NA,
      line = sprintf("%s have not won a premiership in the years covered here.", team)))
  }
  last <- max(won$season)
  yrs <- as.integer(format(as_of, "%Y")) - last
  list(team = team, last_flag = last, years = yrs,
       line = if (yrs == 0) sprintf("%s are the reigning premiers.", team)
              else sprintf("%s last won a flag in %d. That is %d year%s of waiting.",
                           team, last, yrs, if (yrs == 1) "" else "s"))
}

# =======================================================================
# Been here before?
# =======================================================================
# Grand Final appearances in recent seasons. Reported as background, not as a
# thumb on the scale. The model does not give anyone an experience bonus,
# because when you actually test for one it is not there (see the pressure
# check below). Saying so plainly is more useful than quietly adding a number
# nobody can see.
gf_experience <- function(m, team, season, lookback = 10L) {
  gfs <- m[m$stage == "grand_final" &
           m$season >= season - lookback & m$season < season, ]
  apps <- gfs[gfs$home == team | gfs$away == team, ]
  wins <- sum((apps$home == team & apps$margin > 0) |
              (apps$away == team & apps$margin < 0))
  list(team = team, appearances = nrow(apps), wins = wins,
       line = if (!nrow(apps))
         sprintf("%s have not played a Grand Final in the last %d seasons.",
                 team, lookback)
       else sprintf("%s have played %d Grand Final%s in the last %d seasons and won %d.",
                    team, nrow(apps), if (nrow(apps) == 1) "" else "s",
                    lookback, wins))
}

# =======================================================================
# Do teams go to pieces on the big stage?
# =======================================================================
# Everyone says it. Almost nobody checks it. We can, because the model already
# runs on scoring shots and goals, so comparing conversion in Grand Finals
# against conversion in ordinary season games is a straight comparison of two
# rates.
#
# One caveat that matters. This pools every club together rather than singling
# one out, because any individual side has played a handful of Grand Finals at
# most. Drawing a conclusion about one club from three matches is the exact
# mistake the rest of this project is built to avoid.
gf_pressure_accuracy <- function(m) {
  gf <- m[m$stage == "grand_final", ]
  ha <- m[m$stage == "home_and_away", ]

  n_gf <- sum(gf$home_shots + gf$away_shots)
  n_ha <- sum(ha$home_shots + ha$away_shots)
  x_gf <- sum(gf$home_goals + gf$away_goals)
  x_ha <- sum(ha$home_goals + ha$away_goals)

  gf_acc <- x_gf / n_gf
  ha_acc <- x_ha / n_ha
  delta  <- gf_acc - ha_acc

  # Is the gap bigger than you would expect from ordinary week-to-week
  # variation? Standard two-proportion test.
  p  <- (x_gf + x_ha) / (n_gf + n_ha)
  se <- sqrt(p * (1 - p) * (1 / n_gf + 1 / n_ha))
  z  <- delta / se
  pval <- 2 * pnorm(-abs(z))
  real <- pval < 0.05

  list(
    gf_acc = gf_acc, ha_acc = ha_acc, delta = delta,
    p_value = pval, n_gf_shots = n_gf, significant = real,
    line = sprintf(
      "In Grand Finals, sides have kicked %.1f%% of their chances as goals. In ordinary season games it is %.1f%%. %s",
      100 * gf_acc, 100 * ha_acc,
      if (real && delta < 0)
        sprintf("That is a real drop of about %.1f points, and it is bigger than normal week-to-week variation. The nerves are not imaginary.",
                100 * abs(delta))
      else if (real && delta > 0)
        sprintf("Sides have actually kicked %.1f points better, which is the opposite of the usual story.",
                100 * delta)
      else
        sprintf("The gap of %.1f points is small enough that it is indistinguishable from ordinary variation. On this evidence, the big-stage nerves story does not hold up.",
                100 * abs(delta))))
}

gf_countdown <- function(gf_date) {
  d <- ceiling(as.numeric(difftime(as.Date(gf_date), Sys.Date(), units = "days")))
  if (d < 0) return("The Grand Final has been played.")
  if (d == 0) return("Grand Final day.")
  if (d == 1) return("One day until the first bounce.")
  sprintf("%d days until the first bounce.", d)
}

# =======================================================================
# Who's asking? Same numbers, three translations.
# =======================================================================
# The bit that makes this more than a scoreboard. Every figure below comes
# from the same model run. What changes is which figures matter and how they
# are worded.

# For supporters. Plain, short, no jargon, and honest about how much of this
# is out of anyone's hands.
read_as_fan <- function(proj, luck, team) {
  r <- proj[proj$team == team, ]
  L <- luck[luck$team == team, ]
  if (!nrow(r)) return(sprintf("%s are not in the finals.", team))

  chance <- as_frequency(r$p_premier)
  bits <- c(
    sprintf("%s win the flag in %s of the seasons we simulated.", team, chance),
    if (r$p_premier < 0.05)
      "It would take a lot going their way, but teams have done it from here."
    else if (r$p_premier > 0.30)
      "They are as well placed as anyone left in it."
    else "They are live, without being favourites.",
    if (nrow(L) == 1 && !is.na(L$luck_places) && abs(L$luck_places) >= 2)
      sprintf("Worth knowing: kicking %s them about %d ladder place%s this year.",
              if (L$luck_places > 0) "gained" else "cost",
              abs(L$luck_places), if (abs(L$luck_places) == 1) "" else "s")
    else "Their kicking has been roughly what you would expect all year.",
    "One more thing. Finals are close to a coin toss more often than the ladder makes it look, so treat all of this as a guide rather than a forecast."
  )
  paste(bits[nzchar(bits)], collapse = " ")
}

# For football departments. What is repeatable, what was noise, and what that
# means for where you would spend your time.
read_as_club <- function(teams, luck, team) {
  t <- teams[teams$team == team, ]
  L <- luck[luck$team == team, ]
  if (!nrow(t)) return(sprintf("No season data on file for %s.", team))

  edge <- t$chance_edge
  bits <- c(
    sprintf("%s generated %.1f scoring chances a game and conceded %.1f, a difference of %+.1f.",
            team, t$chances_created, t$chances_allowed, edge),
    if (edge > 1.5)
      "That gap is the part of a season that tends to hold up. It is the strongest signal in the whole dataset that the team is genuinely good."
    else if (edge < -1.5)
      "Conceding more than you create is the hardest thing to turn around, and it usually persists into the following season. It is where the work is."
    else "Chances created and conceded are close to level, so the season has largely turned on conversion.",
    sprintf("Conversion sat at %.1f%%.", 100 * t$accuracy),
    "Only about a third of any conversion edge carries into the next block of games, so planning around this year's accuracy holding up is planning around luck.",
    if (nrow(L) == 1 && !is.na(L$luck_places) && L$luck_places >= 2)
      sprintf("The luck-neutral ladder has them %d place%s lower, which is worth factoring into any review of the season.",
              L$luck_places, if (L$luck_places == 1) "" else "s")
    else if (nrow(L) == 1 && !is.na(L$luck_places) && L$luck_places <= -2)
      sprintf("The luck-neutral ladder has them %d place%s higher. The underlying football was better than the finish suggests.",
              abs(L$luck_places), if (abs(L$luck_places) == 1) "" else "s")
    else ""
  )
  paste(bits[nzchar(bits)], collapse = " ")
}

# For the commercial side. How many more weeks of football are likely, which
# markets stay engaged, and how confident anyone should be about it.
read_as_business <- function(proj, venues) {
  alive <- proj[proj$p_premier > 0, ]
  alive <- alive[order(-alive$p_premier), ]
  if (!nrow(alive)) return("No teams remain in contention.")

  top <- alive$team[1]
  spread <- alive$p_premier[1] - alive$p_premier[min(2, nrow(alive))]
  interstate <- sum(!is.na(venues[alive$team]) &
                    !grepl("M.C.G.|Docklands|Marvel|Kardinia|Princes",
                           venues[alive$team]))

  bits <- c(
    sprintf("%d team%s still in contention.", nrow(alive),
            if (nrow(alive) == 1) "" else "s"),
    sprintf("%s lead at %s, %s.", top, as_frequency(alive$p_premier[1]),
            tolower(confidence_words(alive$p_premier[1]))),
    if (spread < 0.08)
      "The field is tight, which usually means a longer run of genuinely competitive matches and stronger neutral audience interest."
    else "There is clear separation at the top, which tends to concentrate attention on one or two clubs.",
    if (interstate >= 2)
      sprintf("%d of the remaining sides are based outside Victoria, so interstate broadcast and travel markets stay live for now.", interstate)
    else "The remaining field is heavily Victorian, which narrows the geographic spread of interest.",
    "Every figure here is a probability, not a schedule. Plan for the range, not the headline number."
  )
  paste(bits[nzchar(bits)], collapse = " ")
}

# =======================================================================
# The whole Grand Final brief in one call
# =======================================================================
gf_special <- function(m, model, team_home, team_away, venue = "M.C.G.",
                       gf_date = NULL,
                       season = as.integer(format(Sys.Date(), "%Y"))) {
  dh <- gf_drought(m, team_home); da <- gf_drought(m, team_away)
  eh <- gf_experience(m, team_home, season); ea <- gf_experience(m, team_away, season)
  press <- gf_pressure_accuracy(m)
  pred  <- model$predict(make_fixture(team_home, team_away, venue), n = 4000L)

  list(
    countdown  = if (!is.null(gf_date)) gf_countdown(gf_date) else NULL,
    drought    = list(home = dh, away = da),
    experience = list(home = eh, away = ea),
    pressure   = press,
    prediction = pred,
    explain    = model$explain(team_home, team_away, venue),
    summary    = paste(sprintf("%s play %s at %s.", team_home, team_away, venue),
                       dh$line, da$line, eh$line, ea$line, press$line)
  )
}

