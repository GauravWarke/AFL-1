# The Ladder Lies — what the 2026 AFL draw was worth

**Live:** https://gauravwarke.github.io/AFL-1/

Playing at your own ground is worth **+1.75 points** and cannot be told apart from
zero (p = 0.14). Having flown interstate costs **5.80 points** and is solid
(p = 0.0005). So home ground advantage in the AFL is mostly an *away* disadvantage
— it is the other side's flight, not the ground.

The six-day break every club complains about comes back at +0.9 points with a
confidence interval spanning zero. It is reported here rather than quietly dropped.

## Files

```
index.html          page structure: nav, six sections, footer
css/style.css       all styling
js/data.js          model output from R  (generated, never hand-edited)
js/app.js           charts, sections, simulator, router
og-draw-cost.png    social preview image
afl-draw-methodology.pdf
```

Four files to understand, no build step. Open `index.html` in a browser and it
runs. To deploy, push the folder and enable GitHub Pages.

## How it fits together

`data.js` defines one global, `window.__AFL__`, written by the R pipeline
(`R/05_app_data.R`). `app.js` reads it as `D` and renders every section from it.
Nothing on the page is a typed-in number, which is what stops the writing and the
analysis drifting apart — the failure mode this project exists to point at.

Sections are **routes**, not one long scroll. Only one is in the document at a
time, addressable at `#ladder`, `#draw`, `#club`, `#lab`, `#talk`. Everything
renders once at load and the router only toggles visibility, so switching
sections never redraws a chart.

Reading order in `app.js`: helpers, then one block per section, then the
simulator, then the router.

## Features

**Three ladders.** Actual, earned (goal-kicking luck removed), and level
(kicking luck *and* fixture removed). The third is the one to quote.

**The draw, priced.** Each club's fixture converted into points of margin, plus a
travel ledger.

**Audience switch.** The same figures explained three ways — fan, club, business.
The numbers never change, only the reading. The choice is remembered.

**Match simulator with live convergence.** Any two clubs, any run size. The
readout shows the Monte Carlo standard error and the measured runtime, because a
simulation that hides its precision is asking to be trusted rather than checked.

| Runs | Std. error | Time |
|---:|---:|---:|
| 2,000 | ±1.12% | ~3 ms |
| 20,000 | ±0.35% | ~26 ms |
| 100,000 | ±0.16% | ~145 ms |

Fifty times the runs buys a 7.0× cut in error, against √50 = 7.07 predicted. Past
about 20,000 more runs stop buying anything a reader can use — which is the point
of showing it.

## Two rules worth keeping

**Chart colours.** `--cool` and `--warm` stay distinguishable under colour-vision
deficiency, and every chart also encodes polarity by side-of-zero and a signed
label. Nothing depends on colour alone. Don't repoint them at the theme accent.

**The lime is a fill, never a text colour.** On white it measures 1.26:1, which
fails badly. As a fill against its own dark ink it is 14.07:1.

## Updating the data

Rerun the R pipeline and replace `js/data.js`. Nothing else changes.

## Known issue

`travelPts` here is net trips × 5.8 and is not weighted by destination, so the
four western clubs collapse onto one value. The methodology PDF weights by
destination (West Coast +20.7, Port Adelaide +18.8, Fremantle +17.4). The PDF is
authoritative; this should inherit it.
