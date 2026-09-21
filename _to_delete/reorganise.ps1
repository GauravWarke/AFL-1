# reorganise.ps1 - separate the legacy Python implementation from the live R
# project, and clear out generated caches and duplicate archives.
#
# Run from the AFL folder:   powershell -ExecutionPolicy Bypass -File .\reorganise.ps1
# Add -WhatIf to see what it would do without touching anything:
#     powershell -ExecutionPolicy Bypass -File .\reorganise.ps1 -WhatIf
#
# Nothing is deleted outright. Everything removable is moved into _to_delete\
# so you can inspect it and delete the folder yourself once you are happy.

[CmdletBinding(SupportsShouldProcess = $true)]
param()

$root = $PSScriptRoot
if (-not $root) { $root = (Get-Location).Path }
Set-Location $root

Write-Host "Reorganising: $root" -ForegroundColor Cyan

function New-Dir($p) {
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
}

function Move-Safe($from, $to) {
    if (-not (Test-Path $from)) { Write-Host "  skip (absent): $from" -ForegroundColor DarkGray; return }
    New-Dir (Split-Path $to -Parent)
    if ($PSCmdlet.ShouldProcess($from, "move to $to")) {
        Move-Item -LiteralPath $from -Destination $to -Force
        Write-Host "  moved: $from  ->  $to" -ForegroundColor Green
    }
}

# ---------------------------------------------------------------------------
# 1. Legacy Python implementation
#
# The Python pipeline (ingest, ratings, bracket, static dashboard) is the older
# version of this project. It is self-contained and shares nothing with the R
# code except the data folder, so it moves as a unit.
# ---------------------------------------------------------------------------
Write-Host "`n[1] Legacy Python implementation -> legacy-python\" -ForegroundColor Yellow
New-Dir "$root\legacy-python"
Move-Safe "$root\src"              "$root\legacy-python\src"
Move-Safe "$root\web"              "$root\legacy-python\web"
Move-Safe "$root\requirements.txt" "$root\legacy-python\requirements.txt"

# Python-produced outputs, so they sit with the code that made them.
New-Dir "$root\legacy-python\outputs"
foreach ($f in @(
    "engine_validation.csv",
    "finals_projection_2026.csv",
    "dashboard_data.json",
    "artifact.html",
    "predictive_check.csv",
    "shot_vs_points.csv",
    "team_season_summary.csv",
    "calibration_raw.csv"
)) {
    Move-Safe "$root\outputs\$f" "$root\legacy-python\outputs\$f"
}

# ---------------------------------------------------------------------------
# 2. Generated caches and byte-identical archives
#
# R\archive\ holds exact copies of R\02_models.R and R\03_bakeoff.R.
# __pycache__ and .Rhistory are regenerated on every run.
# ---------------------------------------------------------------------------
Write-Host "`n[2] Caches and duplicate archives -> _to_delete\" -ForegroundColor Yellow
New-Dir "$root\_to_delete"
Move-Safe "$root\R\archive"            "$root\_to_delete\R-archive"
Move-Safe "$root\src\__pycache__"      "$root\_to_delete\src-pycache"
Move-Safe "$root\legacy-python\src\__pycache__"                "$root\_to_delete\src-pycache"
Move-Safe "$root\legacy-python\src\sportspred\__pycache__"     "$root\_to_delete\sportspred-pycache"
Move-Safe "$root\shiny\.Rhistory"      "$root\_to_delete\.Rhistory"

# ---------------------------------------------------------------------------
# 3. Web app folder
# ---------------------------------------------------------------------------
Write-Host "`n[3] Standalone web app -> app\" -ForegroundColor Yellow
New-Dir "$root\app"

Write-Host "`nDone." -ForegroundColor Cyan
Write-Host "Review _to_delete\ and remove it when you are satisfied nothing there is needed."
Write-Host ""
Write-Host "NOT changed by this script - decide with R running:" -ForegroundColor Magenta
Write-Host "  R\ still holds two chains that collide on function names."
Write-Host "    bake-off:   02_models.R -> 03_bakeoff.R -> 04_simulate.R"
Write-Host "    production: 02_model.R  -> 03_simulate.R -> 04_insights.R -> 05_app_data.R"
Write-Host "  Both define simulate_finals, build_ladder and check_invariants."
Write-Host "  99_run_all.R sources the bake-off chain first, so the production"
Write-Host "  definitions overwrite it. See docs\r-chain-collision.md."
