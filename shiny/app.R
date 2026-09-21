# AFL 2026 Finals Predictor
#
#     shiny::runApp("shiny")
#
# One model. Scoring shots + accuracy, which won a seven-way bake-off on 211
# matches (docs/model-bakeoff.md). Everything on screen comes from it.
#
# The app never fits a model. It loads a prepared object and, for the what-if
# explorer, runs the simulator live off a precomputed win-probability matrix --
# 20,000 tournaments in a fraction of a second.

library(shiny)
library(ggplot2)
library(dplyr)

PROJ <- "C:/Users/GAURAV/OneDrive/Desktop/AFL"
source(file.path(PROJ, "R", "04_insights.R"))
D <- readRDS(file.path(PROJ, "outputs", "app_data.rds"))

INK <- "#15171c"; MUTED <- "#6b7280"; ACCENT <- "#0b6fb0"
WARM <- "#c0392b"; GOOD <- "#1e8449"; LINE <- "#e4e6eb"

theme_afl <- function() {
  theme_minimal(base_size = 13) +
    theme(panel.grid.minor = element_blank(),
          panel.grid.major.y = element_blank(),
          panel.grid.major.x = element_line(colour = "#f0f1f4"),
          axis.title = element_text(colour = MUTED, size = 11),
          axis.text = element_text(colour = INK),
          plot.title = element_text(face = "bold", size = 14, colour = INK),
          plot.subtitle = element_text(colour = MUTED, size = 11),
          plot.margin = margin(6, 14, 6, 6))
}

pct <- function(p, d = 0) sprintf(paste0("%.", d, "f%%"), 100 * p)

# Ladder positions read as ordinals everywhere else on the page, so they
# should here too: "they finished 10" is not how anyone says it.
ord <- function(n) {
  suffix <- if (n %% 100 %in% 11:13) "th"
            else switch(as.character(n %% 10), "1" = "st", "2" = "nd", "3" = "rd", "th")
  paste0(n, suffix)
}

CSS <- "
body{background:#fbfbfd;color:#15171c;
 font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
.container-fluid{max-width:1100px}
h1.t{font-size:27px;letter-spacing:-.02em;margin:20px 0 2px;font-weight:700}
.sub{color:#6b7280;font-size:14px;margin-bottom:16px}
.card{background:#fff;border:1px solid #e4e6eb;border-radius:14px;
 padding:18px 20px;margin-bottom:16px}
.card h4{margin:0 0 3px;font-size:17px;font-weight:600}
.note{color:#6b7280;font-size:13px;margin:0 0 14px;line-height:1.55}
.warn{background:#fff8f0;border-color:#f0d9bd}
.good{background:#f2f9f4;border-color:#cfe6d6}
.big{font-size:34px;font-weight:700;letter-spacing:-.02em;line-height:1.1}
.lbl{color:#6b7280;font-size:12.5px}
.kpi{display:flex;gap:34px;flex-wrap:wrap;margin-top:4px}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{text-align:left;padding:7px 9px;border-bottom:1px solid #f1f2f5}
th{color:#6b7280;font-weight:600;font-size:11.5px;text-transform:uppercase;
 letter-spacing:.04em}
td.n{text-align:right;font-variant-numeric:tabular-nums}
.dead{opacity:.42}
.up{color:#1e8449;font-weight:600}
.down{color:#c0392b;font-weight:600}
.pill{display:inline-block;padding:2px 10px;border-radius:999px;
 background:#eef4f9;color:#0b6fb0;font-size:12.5px;font-weight:600}
.match{padding:11px 0;border-bottom:1px solid #f1f2f5}
.match:last-child{border-bottom:0}
.mt{font-size:11.5px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em}
"

alive_teams <- function(D) D$proj$team[D$proj$alive]

ui <- fluidPage(
  tags$head(tags$style(HTML(CSS))),
  titlePanel(NULL, windowTitle = "AFL 2026 Finals Predictor"),
  div(h1(class = "t", "AFL 2026 Finals Predictor"),
      div(class = "sub", textOutput("subtitle", inline = TRUE))),
  tabsetPanel(
    id = "tab",
    tabPanel("The race",     br(), uiOutput("race")),
    tabPanel("My team",      br(), uiOutput("myteam")),
    tabPanel("What if?",     br(), uiOutput("whatif")),
    tabPanel("Luck ladder",  br(), uiOutput("luck")),
    tabPanel("How it works", br(), uiOutput("how"))
  )
)

server <- function(input, output, session) {

  output$subtitle <- renderText(sprintf(
    "%s scoring-shot simulations of September · %d finals played, %d to come · updated %s",
    format(D$n_sims, big.mark = ","), sum(D$fixtures$played),
    sum(!D$fixtures$played), D$generated))

  # ================================================================ RACE
  output$race_plot <- renderPlot({
    live <- D$proj %>% filter(alive) %>% arrange(p_premier)
    ggplot(live, aes(reorder(team, p_premier), p_premier)) +
      geom_col(fill = ACCENT, width = .66) +
      geom_text(aes(label = pct(p_premier)), hjust = -0.18, size = 4.2,
                fontface = "bold", colour = INK) +
      coord_flip() +
      scale_y_continuous(labels = scales::percent,
                         expand = expansion(mult = c(0, .2))) +
      labs(title = "Chance of winning the premiership",
           subtitle = "Out of every 100 ways this September could still unfold",
           x = NULL, y = NULL) +
      theme_afl()
  })

  output$race <- renderUI({
    live <- D$proj %>% filter(alive) %>% arrange(desc(p_premier))
    nxt <- D$fixtures %>% filter(!played)
    tagList(
      div(class = "card",
          h4("Who wins the flag?"),
          p(class = "note",
            "Matches already played are locked in. We only roll the dice on what is left."),
          plotOutput("race_plot", height = 40 + 34 * nrow(live))),

      div(class = "card",
          h4("The same numbers, in words"),
          tags$table(
            tags$thead(tags$tr(tags$th("Team"), tags$th("Finished"),
                               tags$th("How often they'd win it"),
                               tags$th("In short"))),
            tags$tbody(lapply(seq_len(nrow(D$proj)), function(i) {
              r <- D$proj[order(-D$proj$p_premier), ][i, ]
              tags$tr(class = if (!r$alive) "dead" else "",
                tags$td(tags$b(r$team)),
                tags$td(paste0(r$ladder_pos,
                  switch(as.character(min(r$ladder_pos, 4)),
                         "1" = "st", "2" = "nd", "3" = "rd", "th"))),
                tags$td(r$freq), tags$td(r$verdict))
            })))),

      if (nrow(nxt)) div(class = "card",
          h4("Still to play"),
          p(class = "note", "Every prediction comes with the reason behind it."),
          lapply(seq_len(nrow(nxt)), function(i) {
            f <- nxt[i, ]
            div(class = "match",
                div(class = "mt", sprintf("%s · %s", f$label, f$venue)),
                div(style = "margin:3px 0 5px",
                    tags$b(f$home), " v ", f$away,
                    span(class = "pill", style = "margin-left:8px",
                         sprintf("%s %s", if (f$p_home >= .5) f$home else f$away,
                                 pct(max(f$p_home, 1 - f$p_home))))),
                div(class = "note", style = "margin:0", f$why))
          })),

      div(class = "card warn",
          h4("Before you argue with it"),
          p(class = "note", style = "margin:0",
            sprintf("No side is better than a %s chance. That is not the model hedging. A flag means winning knockout games back to back, and a typical final is decided by far more randomness than the ladder suggests. Across the last ten seasons the side this model called favourite won %d of them, against an expected %.1f. Every number here means 'roughly'.",
                    pct(max(D$proj$p_premier)),
                    if (!is.null(D$track)) sum(D$track$premier == D$track$favourite) else 2L,
                    if (!is.null(D$track)) sum(D$track$p_fav) else 3.7))),

      div(class = "card",
          h4("Finals so far"),
          tags$table(
            tags$thead(tags$tr(tags$th("Match"), tags$th("Score"),
                               tags$th(class = "n", "Chances"), tags$th("Result"))),
            tags$tbody(lapply(seq_len(nrow(D$played)), function(i) {
              r <- D$played[i, ]
              tags$tr(
                tags$td(sprintf("%s v %s", r$home, r$away), tags$br(),
                        span(class = "lbl", sprintf("%s · %s", r$stage, r$venue))),
                tags$td(class = "n", sprintf("%d – %d", r$home_score, r$away_score)),
                tags$td(class = "n", sprintf("%d – %d", r$home_shots, r$away_shots)),
                tags$td(sprintf("%s by %d", r$winner, r$margin)))
            }))))
    )
  })

  # ============================================================== MY TEAM
  output$myteam <- renderUI({
    tagList(
      div(class = "card",
          selectInput("team", "Pick a side",
                      choices = D$proj$team[order(D$proj$ladder_pos)],
                      selected = D$proj$team[which.max(D$proj$p_premier)],
                      width = "320px")),
      uiOutput("team_panel")
    )
  })

  team_path <- reactive({
    req(input$team)
    path_to_flag(NULL, D$ladder, D$venues, D$known, input$team,
                 n_sims = 20000L, probs = D$probs)
  })

  output$path_plot <- renderPlot({
    p <- team_path(); req(nrow(p) > 0)
    p %>%
      tidyr::pivot_longer(c(if_home_wins, if_away_wins),
                          names_to = "which", values_to = "prob") %>%
      mutate(who = ifelse(which == "if_home_wins",
                          sub(" v .*", "", match), sub(".* v ", "", match)),
             lbl = paste0(match, "\n"),
             winner_lbl = paste0("if ", who, " win")) %>%
      ggplot(aes(prob, reorder(match, prob))) +
      geom_line(aes(group = match), colour = "#d8dade", linewidth = 2.2) +
      geom_point(aes(colour = which), size = 4.4) +
      geom_text(aes(label = winner_lbl, colour = which),
                vjust = -1.25, size = 3.3, show.legend = FALSE) +
      scale_colour_manual(values = c(if_home_wins = ACCENT, if_away_wins = WARM),
                          guide = "none") +
      scale_x_continuous(labels = scales::percent) +
      labs(title = sprintf("What each remaining match is worth to %s", input$team),
           subtitle = "Their premiership chance depending on how each match goes",
           x = NULL, y = NULL) +
      theme_afl()
  })

  output$team_panel <- renderUI({
    req(input$team)
    r <- D$proj[D$proj$team == input$team, ]
    t <- D$teams[D$teams$team == input$team, ]
    L <- D$luck[D$luck$team == input$team, ]
    p <- team_path()
    tagList(
      div(class = if (r$alive) "card good" else "card",
          div(class = "kpi",
              div(div(class = "big", if (r$alive) pct(r$p_premier) else "Out"),
                  div(class = "lbl", "chance of the flag")),
              div(div(class = "big", pct(r$p_grand_final)),
                  div(class = "lbl", "reach the Grand Final")),
              div(div(class = "big", sprintf("%.1f", t$chance_edge)),
                  div(class = "lbl", "extra chances per game")),
              div(div(class = "big", pct(t$accuracy, 1)),
                  div(class = "lbl", "goal accuracy")))),

      div(class = "card",
          h4("Their season, in plain words"),
          p(class = "note", style = "margin:0", D$stories[[input$team]])),

      if (r$alive && nrow(p)) div(class = "card",
          h4("What has to happen"),
          p(class = "note",
            "The gap between the two dots is how much that single match matters to them. A wide gap is a match to watch; a narrow one barely moves the needle."),
          plotOutput("path_plot", height = 90 + 66 * nrow(p))),

      if (nrow(L) == 1) div(class = "card",
          h4("Did kicking help or hurt them?"),
          p(class = "note", style = "margin:0",
            sprintf("They finished %s. Replayed with every side kicking at the league average, they finish %s — %s.",
                    ord(L$pos), ord(L$pos_adj),
                    if (L$luck_places > 0)
                      sprintf("%d %s lower, so kicking flattered them",
                              L$luck_places, if (L$luck_places == 1) "place" else "places")
                    else if (L$luck_places < 0)
                      sprintf("%d %s higher, so kicking cost them",
                              abs(L$luck_places), if (abs(L$luck_places) == 1) "place" else "places")
                    else "no change at all")))
    )
  })

  # =============================================================== WHAT IF
  whatif_fx <- reactive(D$fixtures %>% filter(!played))

  output$whatif_controls <- renderUI({
    fx <- whatif_fx()
    if (!nrow(fx)) return(p(class = "note", "Nothing left to decide."))
    lapply(seq_len(nrow(fx)), function(i) {
      f <- fx[i, ]
      div(style = "margin-bottom:14px",
          div(class = "mt", f$label),
          radioButtons(paste0("wi_", i), NULL,
            choiceNames = c("let the model decide",
                            sprintf("%s win (%s)", f$home, pct(f$p_home)),
                            sprintf("%s win (%s)", f$away, pct(1 - f$p_home))),
            choiceValues = c("", f$home, f$away),
            selected = "", inline = FALSE))
    })
  })

  whatif_proj <- reactive({
    fx <- whatif_fx()
    force <- list()
    if (nrow(fx)) for (i in seq_len(nrow(fx))) {
      v <- input[[paste0("wi_", i)]]
      if (!is.null(v) && nzchar(v)) {
        f <- fx[i, ]
        k <- paste0(f$stage, "|", min(f$home, f$away), "|", max(f$home, f$away))
        force[[k]] <- v
      }
    }
    list(proj = simulate_finals(NULL, D$ladder, D$venues, D$known,
                                n_sims = 20000L, probs = D$probs, force = force),
         n_forced = length(force))
  })

  output$whatif_plot <- renderPlot({
    w <- whatif_proj()
    cmp <- D$proj %>% select(team, base = p_premier) %>%
      left_join(w$proj %>% select(team, now = p_premier), by = "team") %>%
      filter(base > 0 | now > 0) %>%
      mutate(delta = now - base) %>%
      arrange(now)
    ggplot(cmp, aes(reorder(team, now))) +
      geom_segment(aes(xend = reorder(team, now), y = base, yend = now),
                   colour = "#d8dade", linewidth = 2.2) +
      geom_point(aes(y = base), colour = "#9a9aa2", size = 3.4) +
      geom_point(aes(y = now, colour = delta >= 0), size = 4.6) +
      geom_text(aes(y = now, label = pct(now)), hjust = -0.35, size = 3.8,
                fontface = "bold", colour = INK) +
      scale_colour_manual(values = c(`TRUE` = GOOD, `FALSE` = WARM),
                          guide = "none") +
      coord_flip() +
      scale_y_continuous(labels = scales::percent,
                         expand = expansion(mult = c(0.02, .2))) +
      labs(title = if (w$n_forced == 0) "Nothing forced yet — this is the base case"
                   else sprintf("If those %d result%s go that way", w$n_forced,
                                if (w$n_forced == 1) "" else "s"),
           subtitle = "Grey dot = where they were before you changed anything",
           x = NULL, y = NULL) +
      theme_afl()
  })

  output$whatif <- renderUI({
    tagList(
      div(class = "card",
          h4("Play out September yourself"),
          p(class = "note",
            "Force any result you like and watch the premiership table move. Everything you do not set is still simulated 20,000 times. This is the same machinery the projection uses — a hypothetical and a real result travel through exactly the same path.")),
      fluidRow(
        column(4, div(class = "card", h4("Set the results"), br(),
                      uiOutput("whatif_controls"))),
        column(8, div(class = "card",
                      plotOutput("whatif_plot", height = 420))))
    )
  })

  # ============================================================ LUCK LADDER
  output$luck_plot <- renderPlot({
    D$luck %>%
      mutate(dir = ifelse(luck_places > 0, "flattered",
                   ifelse(luck_places < 0, "robbed", "even"))) %>%
      ggplot(aes(reorder(team, -pos), luck_places)) +
      geom_hline(yintercept = 0, colour = LINE) +
      geom_col(aes(fill = dir), width = .68) +
      geom_text(aes(label = ifelse(luck_places == 0, "",
                                   sprintf("%+d", luck_places)),
                    hjust = ifelse(luck_places > 0, -0.35, 1.35)),
                size = 3.6, colour = INK) +
      scale_fill_manual(values = c(flattered = WARM, robbed = GOOD, even = "#c9c9cf"),
                        guide = "none") +
      coord_flip() +
      labs(title = "How many ladder places kicking was worth",
           subtitle = "Red = finished higher than their scoring shots deserved. Green = kicking cost them.",
           x = NULL, y = "ladder places gained by kicking") +
      theme_afl()
  })

  output$luck <- renderUI({
    L <- D$luck
    tagList(
      div(class = "card",
          h4("The ladder, with the kicking taken out"),
          p(class = "note",
            sprintf("Every match replayed with both sides converting at the league average of %s, keeping the scoring shots they actually created and conceded. Anything that moves is down to how straight the kicking was. This is worth doing because only about %s of a side's accuracy carries into the next block of games — but chances created and conceded carry over at nearly 90%%.",
                    pct(attr(L, "league_acc"), 1),
                    pct(D$accuracy_reliability))),
          plotOutput("luck_plot", height = 460)),

      div(class = "card",
          h4("Side by side"),
          tags$table(
            tags$thead(tags$tr(tags$th("Team"), tags$th(class = "n", "Finished"),
                               tags$th(class = "n", "Points"),
                               tags$th(class = "n", "Would finish"),
                               tags$th(class = "n", "Points"),
                               tags$th(class = "n", "Move"), tags$th("Verdict"))),
            tags$tbody(lapply(seq_len(nrow(L)), function(i) {
              r <- L[i, ]
              tags$tr(
                tags$td(tags$b(r$team)),
                tags$td(class = "n", r$pos), tags$td(class = "n", r$pts),
                tags$td(class = "n", r$pos_adj),
                tags$td(class = "n", round(r$pts_adj)),
                tags$td(class = "n",
                        span(class = if (r$luck_places > 0) "down" else if (r$luck_places < 0) "up" else "",
                             if (r$luck_places == 0) "—" else sprintf("%+d", r$luck_places))),
                tags$td(r$verdict))
            })))),

      div(class = "card warn",
          h4("What this is not"),
          p(class = "note", style = "margin:0",
            "This is not 'the ladder they deserved'. Accuracy is about a third skill, so a genuinely straight-kicking side is being slightly hard done by here. It is the answer to a narrower question: how much of the season came down to how well the ball was kicked, rather than how often it got into range."))
    )
  })

  # ============================================================ HOW IT WORKS
  output$how <- renderUI({
    s <- D$scores
    tagList(
      div(class = "card",
          h4("One model, chosen on evidence"),
          p(class = "note",
            "Australian football builds a score in two steps, so the model has two steps. First: how many scoring shots does a side create, and how many does it give up? Second: how many of those does it kick straight? Chances are modelled as a count, conversion as a coin weighted by the team's accuracy — heavily pulled toward the league average, for the reason below."),
          div(class = "kpi",
              div(div(class = "big", pct(D$league_acc, 1)),
                  div(class = "lbl", "league goal accuracy")),
              div(div(class = "big", "0.88"),
                  div(class = "lbl", "how much chance creation repeats")),
              div(div(class = "big", sprintf("%.2f", D$accuracy_reliability)),
                  div(class = "lbl", "how much accuracy repeats")))),

      div(class = "card",
          h4("Why the accuracy number matters so much"),
          p(class = "note", style = "margin:0",
            "Across 216 team-seasons, only about a third of the spread in goal accuracy carries from one half of a season to the other. Chances created and conceded carry over at 0.88 and 0.87. So a side that has been kicking straight is mostly a side that has been lucky, and trusting it to continue is the most common way to be wrong about the AFL. The model keeps a third of a team's accuracy edge and throws the rest back to the league mean.")),

      if (!is.null(s)) div(class = "card",
          h4("How this model was picked"),
          p(class = "note",
            "Seven models were rebuilt before every round of 2026 and asked to predict it — the same 211 matches for all of them. Log-loss judges whether the stated confidence is honest, not just whether the tip was right, which is what matters when the output feeds a simulator."),
          tags$table(
            tags$thead(tags$tr(tags$th("Model"), tags$th(class = "n", "Log-loss"),
                               tags$th(class = "n", "Tip %"))),
            tags$tbody(lapply(seq_len(nrow(s)), function(i) {
              r <- s[i, ]
              nm <- c(shots = "Scoring shots + accuracy", ridge = "Ridge margin",
                      elo = "Elo", bayes = "Bayesian hierarchical",
                      bt = "Bradley-Terry", xgb = "Gradient boosting",
                      rf = "Random forest")[r$model]
              tags$tr(style = if (i == 1) "background:#f2f9f4" else "",
                      tags$td(if (i == 1) tags$b(nm) else nm),
                      tags$td(class = "n", sprintf("%.4f", r$logloss)),
                      tags$td(class = "n", sprintf("%.1f", r$tip)))
            }))),
          p(class = "note", style = "margin-top:12px",
            "The other six are kept in the repository only as the record of how this one was chosen. Nothing in this app touches them.")),

      div(class = "card warn",
          h4("This finals format has never been played"),
          p(class = "note", style = "margin:0",
            "Ten finalists and a wildcard round is new for 2026, so there is no history to test the bracket against. Instead the engine was tested on 2015–2025 under the old eight-team format, and the new structure is checked against rules that must hold in any correct bracket: premiership chances summing to one, grand finalists to two, wildcard sides claiming exactly two of the eight places. All pass.")),

      div(class = "card",
          h4("Where the data comes from"),
          p(class = "note", style = "margin:0",
            "Match results from the Squiggle API — the same underlying data as fitzRoy and AFL Tables. Not affiliated with the AFL. Nothing here is betting advice: the model's favourite has won two of the last ten premierships, which is roughly what it said would happen."))
    )
  })
}

shinyApp(ui, server)
