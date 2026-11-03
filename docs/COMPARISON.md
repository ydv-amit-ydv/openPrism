# OpenPrism vs. GraphPad Prism — an honest comparison

GraphPad Prism is a mature commercial product with decades of refinement,
validation and support. OpenPrism is a young open source project. This page
says plainly where OpenPrism is already competitive, where it is different, and
where Prism is still clearly ahead.

*(GraphPad Prism is a trademark of GraphPad Software / Dotmatics. OpenPrism is
independent and not affiliated with it. Feature statements about Prism are based
on its public documentation and may be incomplete.)*

## At a glance

| Area | OpenPrism 1.0 | GraphPad Prism |
| --- | --- | --- |
| Price / licence | Free, MIT, source available | Paid subscription per user |
| Platforms | Any modern browser; server on Linux/macOS/Windows; optional desktop window | Windows and macOS desktop app (plus cloud features) |
| Multi-user server, accounts, quotas, admin panel | **Yes** (self-hosted) | Cloud sharing in recent versions; no self-hosted server |
| Data stays on your own infrastructure | **Yes** | Local files; cloud features use vendor servers |
| End-to-end encrypted projects (server cannot read them) | **Yes** (AES-256-GCM, recovery key) | No |
| Data table types | XY, Column, Grouped, Contingency, Survival, Parts of whole, Multiple variables, Nested | Same eight |
| Structured tables, replicates, excluded values, live recalculation | Yes | Yes |
| Scripting / API | Python package + JSON HTTP API | Prism scripting language, limited automation |

## Statistics

| Analysis | OpenPrism | Prism |
| --- | --- | --- |
| Descriptive stats, normality tests (SW, D'Agostino, KS, AD), Q-Q plots | ✓ | ✓ |
| t tests (unpaired, Welch, paired), Mann-Whitney, Wilcoxon | ✓ | ✓ |
| One-way ANOVA (ordinary, Welch, RM with Geisser-Greenhouse), Kruskal-Wallis, Friedman | ✓ | ✓ (+ Brown-Forsythe ANOVA) |
| Multiple comparisons: Tukey, Dunnett, Šídák, Holm, Holm-Šídák, Bonferroni, Fisher, BH-FDR, two-stage FDR (BKY), Games-Howell, Dunnett T3, Tamhane T2, Dunn | ✓ | ✓ |
| Two-way ANOVA (type III, interaction) | ✓ ordinary and repeated measures (mixed-effects model) | ✓ ordinary, RM, mixed-effects |
| Three-way ANOVA, nested t test / nested ANOVA, ANCOVA | ✓ (n-way ANOVA/ANCOVA via multiple-variables table) | ✓ |
| Nonlinear regression: built-in equations | 119 + user-defined | 100+ |
| User-defined equations | ✓ (safe parser) | ✓ (with per-data-set rules, initial-value rules) |
| Global fitting / shared parameters + F test | ✓ | ✓ (more flexible constraints, e.g. per-set ranges) |
| Model comparison (extra SS F test, AICc), interpolation, weighting, ambiguity detection, ROUT robust fitting, profile-likelihood CIs | ✓ | ✓ |
| Linear regression, slope comparison, runs test, Deming regression | ✓ (+ Passing-Bablok) | ✓ |
| Correlation (Pearson/Spearman, matrix) | ✓ | ✓ |
| Multiple linear / logistic / Poisson regression, Cox regression, PCA | ✓ | ✓ (more diagnostics) |
| Contingency (Fisher, chi², trend, OR, RR) | ✓ | ✓ |
| Kaplan-Meier, log-rank, Gehan-Breslow-Wilcoxon, hazard ratio, number-at-risk tables | ✓ | ✓ |
| ROC, Bland-Altman, AUC, smoothing/derivatives | ✓ | ✓ |
| Outliers | Grubbs, ROUT (curve fits), robust MAD/FDR, IQR | Grubbs, ROUT |
| Power / sample size | ✓ built in | Separate tool (GraphPad StatMate) |
| Equivalence (TOST), Bayes factors, bootstrap CIs, permutation tests, Passing-Bablok | **✓** | ✗ / limited |
| Validation | Automated tests against SciPy/statsmodels/textbook values | Extensive vendor validation, long track record |

## Graphs and figures

| Feature | OpenPrism | Prism |
| --- | --- | --- |
| Scatter dot, bar, box, violin, before-after, XY, grouped/stacked, KM, pie, heat map, forest/Q-Q/Bland-Altman/PCA plots | ✓ | ✓ |
| Automatic significance brackets from analyses | ✓ | ✓ (pairwise comparison annotations) |
| Style presets, copy/paste format, apply to all graphs | ✓ | ✓ (magic / templates, more mature) |
| Axis control: ranges, ticks, number format, log, reverse, minor ticks, gridlines, **axis breaks**, right Y axis | ✓ | ✓ (+ offset axes, multiple segments) |
| Reference lines, text labels with arrows, equations on graph, hatch patterns, value labels, embedded results tables | ✓ | ✓ (+ freehand shapes) |
| Interactive graphs (hover values, zoom) | **✓** | Limited |
| Multi-panel layouts, panel labels, shapes/arrows/brackets; TIFF/PNG/JPEG at user-chosen dpi (72–2400, embedded in the file), vector PDF/SVG/EPS/EMF, ZIP of all graphs | ✓ | ✓ |
| Graph style templates (save, apply to all, share as a file) | ✓ | ✓ (+ portfolio of example graphs) |
| Import / export GraphPad Prism .pzfx data | **✓** | ✓ (native) |
| Data entered as mean, SD/SEM, n (t test, ANOVA, graphs) | ✓ | ✓ |
| Calculated columns (formulas) | ✓ | ✓ (transforms / row statistics) |
| Images on layouts | ✓ | ✓ |
| Share projects with colleagues | **✓ end-to-end encrypted, self-hosted** | Prism Cloud (vendor-hosted) |
| Live calculation indicator with per-calculation timing log | **✓** | ✗ |

## Usability

| | OpenPrism | Prism |
| --- | --- | --- |
| Guided workflow (table → analysis → graph → layout) | ✓ | ✓ |
| On-the-spot help and full manual | ✓ "?" on every option + manual | ✓ excellent statistics guide |
| Undo/redo, autosave, conflict detection | ✓ | ✓ undo; autosave in recent versions |
| Analysis checklists, "analyze this" wizard, family/sheet linking | ✓ guided test chooser + "About this analysis" in every dialog; no sheet families | ✓ |
| Command palette, full-screen / focus mode | **✓** | ✗ |
| Published accuracy validation you can rerun (NIST StRD, R, calibration) | **✓ 808 checks, open source** | Vendor validation documents |
| Reproducibility record (versions + data fingerprint) and methods text per result | **✓** | Partial (analysis info) |
| Polish, speed with very large tables, offline use without a server | Good / browser-based | Excellent native app |

## New statistics in 0.6 that Prism does not offer (as of its public documentation)

Linear mixed models with random slopes and Satterthwaite degrees of freedom; competing-risks cumulative incidence with Gray's test and Fine-Gray regression; meta-analysis with forest/funnel plots; circular statistics; cosinor rhythm analysis; intraclass correlations, Cronbach's α,
Lin's CCC and Fleiss' κ; generalized linear models (negative binomial, gamma, inverse Gaussian) and ordinal regression; MANOVA;
cluster analysis; robust trimmed-means tests (Yuen, Wilcox) and robust/quantile regression; aligned-rank-transform two-way ANOVA;
Jonckheere-Terpstra and Page trend tests; Conover-Iman and DSCF post hoc tests; Quade test; Barnard/Boschloo exact tests,
Fisher-Freeman-Halton, Bowker and Stuart-Maxwell; Cochran-Mantel-Haenszel; weighted log-rank family and RMST; regression
diagnostics (Breusch-Pagan, White, RESET, Breusch-Godfrey, Cook's distance); stationarity and randomness tests; Storey q-values;
tolerance and prediction intervals; exact polynomial regression; exact rank tests with ties.

## Summary — is it better than Prism?

**In statistical breadth, openness and verifiability: yes.** OpenPrism 0.6 has 68 analyses covering everything in Prism's
statistics menus plus about 30 families of methods Prism does not have, 119 curve equations, and an accuracy record anyone can
rerun: 349 NIST certified-value checks (including the hardest problems, where double-precision programs often fail), 403
comparisons with R, 25 Monte-Carlo calibration checks and 31 reproducibility checks — all passing. It is free, self-hosted,
multi-user and end-to-end encrypted.

**Where Prism is still better:** the polish of a mature native desktop application (offline use without starting a server),
graph-editing finesse (freehand drawing, a portfolio of example graphs, sheet "families"), decades of real-world use and a track record that journals and regulators know, and professional support.
"Orders of magnitude better" is not a claim either program can honestly make; for regulated (GLP/GMP/clinical) work, validate
the analyses you rely on against your reference software whichever program you use.
