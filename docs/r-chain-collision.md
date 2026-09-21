# The two R chains, and why they collide

## What is there

`R/` contains two independent pipelines that share the same function names.

**Bake-off chain** — all seven models, used to prove which one wins.

```
00_setup.R -> 01_data.R -> 02_models.R -> 03_bakeoff.R
                        -> 02_models.R -> 04_simulate.R
```

**Production chain** — the winning model only, used to build the app data.

```
00_setup.R -> 01_data.R -> 02_model.R -> 03_simulate.R -> 04_insights.R -> 05_app_data.R
```

`02_model.R` (singular) is the newer, winner-only refit. `02_models.R` (plural)
holds all seven behind the shared `fit(train) -> predict(newdata)` interface.

## The collision

`03_simulate.R` and `04_simulate.R` both define, at top level:

- `build_ladder`
- `home_venues`
- `known_results`
- `finals_prob_matrix`
- `simulate_finals`
- `check_invariants`
- `remaining_fixtures`

`R` has no namespacing for sourced scripts. Whichever file is sourced last wins,
silently — no warning, no error.

`99_run_all.R` sources in this order:

```r
source("R/03_bakeoff.R")    # pulls 02_models.R
source("R/04_simulate.R")   # pulls 02_models.R, defines simulate_finals (A)
source("R/05_app_data.R")   # pulls 04_insights -> 03_simulate -> 02_model,
                            # redefines simulate_finals (B) over (A)
```

So after `source("R/99_run_all.R")`, every one of those seven names refers to the
**production** version, and `04_simulate.R`'s definitions are unreachable.

## Why the output is still correct today

`run_all()` calls the bake-off before it calls the app build. The bake-off closes
over `02_models.R`'s fitted objects, which were captured while those definitions
were live. The clobber happens after the work that depends on the overwritten
names is already done.

That is a property of the current call order, not of the design. Reorder two
lines in `run_all()`, or call `simulate_finals()` directly from a fresh session
expecting the bake-off version, and it silently returns the other model's answer.

## The fix, in order of effort

1. **Rename** (smallest change). Prefix the bake-off copies:
   `bakeoff_simulate_finals`, `bakeoff_build_ladder`, and so on. One find-and-replace
   in `04_simulate.R` and its callers. The collision disappears and both chains
   stay sourceable together.

2. **Deduplicate** (best, more work). The seven functions are near-identical
   between the two files. Move the shared ones into a single `R/03_bracket.R`
   that both chains source, and leave only the genuinely model-specific parts
   behind. Removes the duplication rather than renaming around it.

3. **Separate environments** (most correct, most disruptive). Source each chain
   into its own environment with `local()` or `sys.source(envir = new.env())`,
   or convert the project to a package. Overkill for a project this size.

Option 1 is the right trade. Do it with R running so you can re-run
`run_all(season = 2026)` and confirm the bake-off numbers still reconcile against
`outputs/model_scores.csv` — the winning model must still score **0.5212**.

## What was deliberately not changed

No R file was moved or renamed by `reorganise.ps1`. Moving them breaks every
`source(file.path(PROJ, "R", ...))` path, and that change cannot be verified
without an R session. Do it yourself, in RStudio, one chain at a time.
