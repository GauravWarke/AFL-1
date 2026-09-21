# Two tabs to paste into shiny/app.R.
#
# SETUP
# -----
# 1. Near the top, after the existing source() line, add:
#
#       source(file.path(PROJ, "R", "07_grand_final.R"))
#
# 2. In R/05_app_data.R, add two entries to the list that build_app_data()
#    returns, so the Grand Final section can reach the raw table and the
#    fitted model:
#
#       m_raw = m, model = model,
#
#    Then rebuild the data once:  source("R/05_app_data.R"); save_app_data()
#
# 3. Add these two panels inside tabsetPanel(...):
#
#       tabPanel("Grand Final", br(), uiOutput("gf")),
#       tabPanel("Who's asking?", br(), uiOutput("lens")),
#
# 4. Paste everything below into server(input, output, session) { ... }


# =====================================================================
# GRAND FINAL
# =====================================================================
output$gf <- renderUI({
  # Until the finalists are locked in, show the two most likely. Replace these
  # two lines with the actual teams once the preliminary finals are done.
  gfs  <- D$proj[order(-D$proj$p_grand_final), ]
  home <- gfs$team[1]
  away <- gfs$team[2]

  brief <- gf_special(D$m_raw, D$model, home, away, gf_date = "2026-09-26")

  tagList(
    div(class = "card good",
        h4(sprintf("%s v %s", home, away)),
        p(class = "note", style = "margin:0 0 10px; font-size:15px",
          brief$countdown),
        p(class = "note", style = "margin:0", brief$explain)),

    div(class = "card",
        h4("How long they have waited"),
        p(class = "note", style = "margin:0 0 4px", brief$drought$home$line),
        p(class = "note", style = "margin:0", brief$drought$away$line)),

    div(class = "card",
        h4("Been here before"),
        p(class = "note", style = "margin:0 0 4px", brief$experience$home$line),
        p(class = "note", style = "margin:0", brief$experience$away$line),
        p(class = "note", style = "margin:10px 0 0; font-style:italic",
          "We report this, but we do not let it change the prediction. When you test for a big-game advantage in the data, it is not there.")),

    div(class = "card warn",
        h4("Do teams go to pieces on the day?"),
        p(class = "note", style = "margin:0", brief$pressure$line))
  )
})


# =====================================================================
# WHO'S ASKING?  Same numbers, three translations.
# =====================================================================
output$lens <- renderUI({
  tagList(
    div(class = "card",
        h4("Same model, three ways of reading it"),
        p(class = "note",
          "A supporter, a football department and a commercial team all want something different from the same set of numbers. Pick who you are and the page rewrites itself. Nothing underneath changes."),
        fluidRow(
          column(6, selectInput("lens_who", "I am a...",
                                choices = c("Supporter"        = "fan",
                                            "Football club"    = "club",
                                            "Business partner" = "business"),
                                selected = "fan")),
          column(6, conditionalPanel(
            "input.lens_who != 'business'",
            selectInput("lens_team", "Team",
                        choices = sort(D$proj$team),
                        selected = D$proj$team[which.max(D$proj$p_premier)]))))),

    uiOutput("lens_body")
  )
})

output$lens_body <- renderUI({
  who  <- input$lens_who %||% "fan"
  team <- input$lens_team %||% D$proj$team[1]

  if (who == "fan") {
    div(class = "card good",
        h4(sprintf("%s, in plain terms", team)),
        p(style = "font-size:15px; line-height:1.7; margin:0",
          read_as_fan(D$proj, D$luck, team)))

  } else if (who == "club") {
    div(class = "card",
        h4(sprintf("%s: what holds up and what was luck", team)),
        p(style = "font-size:15px; line-height:1.7; margin:0",
          read_as_club(D$teams, D$luck, team)))

  } else {
    div(class = "card",
        h4("Where the season is heading"),
        p(style = "font-size:15px; line-height:1.7; margin:0",
          read_as_business(D$proj, D$venues)))
  }
})

`%||%` <- function(a, b) if (is.null(a)) b else a
