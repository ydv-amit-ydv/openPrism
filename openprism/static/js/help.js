// On-the-spot help: small "?" buttons that open a popover with a short
// explanation and a link to the matching section of the full user manual.
import { fitToViewport, h, modal } from './ui.js';

export const MANUAL_URL = '/static/help/manual.html';

/* Each entry: [title, short HTML explanation]. The key is also the anchor id in the manual. */
export const HELP = {
  // ---------------------------------------------------------------- general
  'getting-started': ['Getting started', 'Create a <b>data table</b>, type or paste your numbers, then click <b>Analyze</b> to run a test and <b>New graph</b> to plot it. Graphs and results update automatically when the data change. Combine graphs into a figure with <b>Layouts</b>.'],
  navigator: ['Navigator', 'The left panel lists everything in the project: data tables, notes, results (analyses), graphs and layouts. Click to open, double-click to rename, right-click for duplicate/delete. Drag a graph onto a layout page to place it.'],
  projects: ['Projects & saving', '<b>Save</b> (Ctrl+S) stores the project on the OpenPrism server (projects folder). <b>Download</b> saves a portable <code>.oprism</code> file you can e-mail or archive; open it again with File → Open project file. Your work is also auto-saved in this browser.'],
  undo: ['Undo / redo', 'Ctrl+Z undoes and Ctrl+Y (or Ctrl+Shift+Z) redoes any change to data, analyses, graphs or layouts (up to 80 steps).'],

  // ---------------------------------------------------------------- tables
  'table-types': ['Choosing a table type', 'The table type decides which analyses and graphs are offered. <b>XY</b>: an X value for every point. <b>Column</b>: one group per column. <b>Grouped</b>: two grouping factors. <b>Contingency</b>: counts. <b>Survival</b>: time + event/censored. <b>Parts of whole</b>: fractions of a total. <b>Multiple variables</b>: one row per subject, one column per variable.'],
  'table-xy': ['XY tables', 'Enter X in the yellow column and Y values to the right. Use replicate subcolumns (Y1, Y2, …) for repeated measurements at the same X; graphs then show mean ± error and fits use every replicate (or the means, if you choose).'],
  'table-column': ['Column tables', 'Each column is one group (treatment, genotype, …); each row is one value. Columns may have different numbers of values. For paired or repeated-measures designs, keep matched values on the same row.'],
  'table-grouped': ['Grouped tables', 'Rows are levels of one factor (e.g. time point), data sets (columns) are levels of the second factor (e.g. genotype). Replicate subcolumns hold the individual values for two-way ANOVA.'],
  'table-contingency': ['Contingency tables', 'Enter <b>counts</b> (number of subjects), never percentages or means. Rows are groups (exposure / treatment) and columns are outcomes.'],
  'table-survival': ['Survival tables', 'One row per subject. X = time to event or last follow-up. In the subject’s group column enter <b>1</b> if the event (e.g. death) happened or <b>0</b> if censored; leave other groups blank.'],
  'table-parts': ['Parts of whole', 'Enter category names as row titles and their amounts in the column. Graph as pie, donut or stacked bar; analyze with Fraction of total.'],
  'table-multi': ['Multiple variables tables', 'One row per subject/observation and one column per variable (continuous, or 0/1 for binary outcomes). Used for multiple linear, logistic and Cox regression, PCA and correlation matrices.'],
  'data-entry': ['Entering data', 'Click a cell and type; Enter moves down, Tab moves right. Select a range with drag or Shift+arrows. <b>Ctrl+C / Ctrl+V</b> copy and paste with Excel or Google Sheets. Delete clears. Double-click a column header to rename it; right-click a header for replicates, insert, move or delete.'],
  replicates: ['Replicates (subcolumns)', 'XY and Grouped tables can hold several replicate values per point. Set the number per data set from the header’s right-click menu, or for all data sets via Data → Set replicates.'],
  exclude: ['Excluding values', 'Right-click selected cells → <b>Exclude / include</b>. Excluded values are shown struck through in grey and are ignored by every analysis and graph, but kept in the table so the decision is documented and reversible.'],
  import: ['Importing data', 'File → Import CSV / Excel. The first row must contain column titles. For XY and survival tables the first column becomes X; for grouped, contingency and parts tables it becomes the row titles.'],

  // ---------------------------------------------------------------- analyses
  analyze: ['Analyze dialog', 'Pick an analysis on the left (unavailable ones are greyed out for this table type), tick the data sets to include, and set the options. Results appear under <b>Results</b> and recalculate when the data change. Use <b>Parameters…</b> on a result to change options later.'],
  results: ['Reading results', 'Results are grouped in sections (summary, tables of statistics, multiple comparisons). P value summaries use: ns P ≥ 0.05, * P < 0.05, ** P < 0.01, *** P < 0.001, **** P < 0.0001. Copy (tab-delimited, pastes into Excel) or Export the tables.'],
  'p-values': ['P values & significance', 'A P value is the probability of observing a difference at least this large if the null hypothesis were true. It is not the probability that the null hypothesis is true. Report effect sizes and confidence intervals alongside P values.'],
  alpha: ['Significance level (alpha)', 'The threshold below which a P value is called “significant”. 0.05 is conventional. Changing alpha changes the conclusions and the width of the reported confidence intervals for multiple comparisons.'],
  descriptive: ['Descriptive statistics', 'N, mean, SD, SEM, 95% CI of the mean, median and its CI, quartiles, range, CV, geometric mean and SD factor, skewness and kurtosis for each data set.'],
  normality: ['Normality tests', 'Tests whether values are consistent with a Gaussian distribution (Shapiro-Wilk is recommended; D’Agostino-Pearson needs n ≥ 8). A “passed” test does not prove normality — with small n the tests have little power. A Q-Q plot is produced as an analysis plot.'],
  one_sample: ['One-sample test', 'Compares the mean (t test) or median (Wilcoxon signed rank) of each column against a hypothetical value you enter.'],
  ttest: ['t tests', '<b>Unpaired</b>: two independent groups. <b>Welch</b>: unpaired without assuming equal SDs (recommended when SDs differ). <b>Paired</b>: matched values on the same row. Nonparametric alternatives: Mann-Whitney (unpaired) and Wilcoxon matched pairs. Uses the first two ticked data sets.'],
  paired: ['Paired vs. unpaired', 'Choose paired when each value in one group is matched with a value in the other (same subject before/after, siblings, same experiment run). Pairing removes between-subject variability and increases power.'],
  parametric: ['Parametric vs. nonparametric', 'Parametric tests assume sampling from Gaussian populations and compare means. Nonparametric tests (ranks) make fewer assumptions and compare distributions/medians, but have less power with small samples.'],
  one_way: ['One-way ANOVA', 'Compares three or more groups. Ordinary ANOVA assumes Gaussian data with equal SDs (check Brown-Forsythe); Welch ANOVA relaxes equal SDs; repeated measures uses matched rows; Kruskal-Wallis and Friedman are nonparametric. Follow with multiple comparisons.'],
  'multiple-comparisons': ['Multiple comparisons', '<b>Tukey</b>: every mean vs every other. <b>Dunnett</b>: each vs a control. <b>Šídák / Holm-Šídák / Bonferroni</b>: a chosen family of comparisons (Holm-Šídák has the most power). <b>Fisher LSD</b>: no correction. <b>BH</b>: controls the false discovery rate. All control error across the family of comparisons.'],
  geisser: ['Geisser-Greenhouse correction', 'Repeated-measures ANOVA assumes sphericity (equal variances of all pairwise differences). The correction (epsilon) reduces the degrees of freedom when this is violated; leave it on unless you have a reason not to.'],
  welch: ['Welch correction', 'Does not assume that the groups have equal standard deviations. Recommended by default when group sizes or SDs differ.'],
  two_way: ['Two-way ANOVA', 'For grouped tables: tests the row factor, the column factor and their interaction (needs replicates). Multiple comparisons compare columns within each row (or rows within each column) using the pooled error term.'],
  multiple_t: ['Multiple t tests', 'One unpaired t test per row of a grouped table (first two data sets), with correction for multiple testing (Holm-Šídák, Bonferroni or FDR).'],
  outliers: ['Identify outliers', 'Grubbs’ test (iterative, assumes Gaussian), a robust ROUT-like method based on median/MAD with false discovery rate Q, or Tukey IQR fences. Produces a cleaned table. Never delete outliers without a documented reason.'],
  frequency: ['Frequency distribution', 'Bins values into a histogram (counts, percentages or fractions, optionally cumulative). The result is a new XY table that you can graph as bars.'],
  roc: ['ROC curve', 'First ticked data set = controls, second = patients. Reports AUC with 95% CI and P value (vs 0.5), and a sensitivity/specificity table for every cutoff. A separate ROC graph is created automatically.'],
  bland_altman: ['Bland-Altman', 'Method comparison for two columns measured on the same samples. Plots difference vs average and reports bias and 95% limits of agreement (bias ± 1.96 SD) with confidence intervals and a test for proportional bias.'],
  nonlinear: ['Nonlinear regression', 'Fits an equation to XY data by least squares. Choose a built-in model or write your own. Reports best-fit values, SE, CI, R², Sy.x and AICc, flags ambiguous fits, and draws the curve on the graph.'],
  'custom-equation': ['User-defined equations', 'Write one or more lines, the last one defining Y, e.g.<br><code>Span = Top - Bottom<br>Y = Bottom + Span*X/(K + X)</code><br>Use X, ^ for powers, and exp, ln, log10, sqrt, abs, sin, cos, erf … Every other name becomes a fitted parameter. Give initial values like <code>Top=100, K=1</code>.'],
  constraints: ['Constraining parameters', 'Type a number to fix a parameter to a constant (e.g. Bottom = 0, HillSlope = 1). Fewer free parameters make fits more stable when data do not define a plateau.'],
  'global-fit': ['Global fitting (shared parameters)', 'Fit all data sets together while sharing chosen parameters (e.g. Top, Bottom and HillSlope shared, LogEC50 individual). An extra sum-of-squares F test tells you whether the shared parameters really differ between data sets.'],
  weighting: ['Weighting', 'Use relative weighting (1/Y²) when the scatter is proportional to Y (common in biology); Poisson (1/Y) for counts. Otherwise use ordinary least squares.'],
  interpolate: ['Interpolating unknowns', 'Type Y values (e.g. signals of unknown samples) separated by commas to read their X (e.g. concentrations) off the fitted standard curve.'],
  'compare-models': ['Comparing models', 'Fits a second equation and compares the two with the extra sum-of-squares F test (for nested models) and Akaike’s criterion (AICc) — e.g. one-phase vs two-phase decay.'],
  linear: ['Linear regression', 'Fits a straight line; reports slope, intercepts, R², a test of slope ≠ 0 and a runs test for linearity. With several data sets it tests whether slopes (and then intercepts) differ.'],
  correlation: ['Correlation', 'Pearson r (assumes bivariate Gaussian) or Spearman rank correlation, with confidence intervals and P values. Tick “full matrix” for all pairs; a correlation-matrix heat map is available as an analysis plot.'],
  auc: ['Area under curve', 'Trapezoid area above a baseline for each data set, with its SE and CI (from replicate SDs), number of peaks and the peak position.'],
  smooth: ['Smooth, differentiate, integrate', 'LOWESS or moving-average smoothing (curve drawn on the graph), numerical derivative (dY/dX), or cumulative integral. Results become a new XY table.'],
  contingency: ['Chi-square & Fisher', 'Tests association between rows and columns of counts. For 2×2 tables Fisher’s exact test is preferred; odds ratio, relative risk, sensitivity, specificity and NNT are reported. Chi-square for trend for ordered rows.'],
  survival: ['Survival analysis', 'Kaplan-Meier survival curves with 95% CIs, median survival, log-rank (Mantel-Cox) and Gehan-Breslow-Wilcoxon tests, hazard ratio for two groups and pairwise comparisons for more.'],
  parts: ['Fraction of total', 'Each value as a fraction and percent of the column total, optionally with a chi-square goodness-of-fit test against equal proportions.'],
  multiple_regression: ['Multiple linear regression', 'Predicts one continuous variable from several others. Reports coefficients with CI and P, VIF (multicollinearity), R², adjusted R², an overall F test and residual normality, plus actual-vs-predicted, residual and Q-Q plots.'],
  logistic: ['Logistic regression', 'Predicts a 0/1 outcome. Coefficients are reported as odds ratios per unit change, with CI and P; goodness of fit (Tjur R², likelihood ratio test, AUC) and a classification table.'],
  cox: ['Cox regression', 'Proportional hazards model: choose the time variable, the event variable (1 = event, 0 = censored) and covariates. Reports hazard ratios with CI and P, the likelihood-ratio test and Harrell’s C.'],
  pca: ['Principal component analysis', 'Reduces correlated variables to a few components. Reports eigenvalues, % variance, loadings and scores (new table); scree plot with parallel analysis, biplot and loadings plot. Standardize when variables are on different scales.'],
  transform: ['Transform', 'Creates a new table with Y (and optionally X) transformed: logs, powers, reciprocal, Y×K, Y+K, logit or Z scores.'],
  normalize: ['Normalize', 'Rescales each data set so that a chosen value is 0% and another is 100% (e.g. smallest and largest mean).'],
  baseline: ['Remove baseline', 'Subtracts the first row of each data set, or the first data set from all others.'],
  transpose: ['Transpose', 'Swaps rows and columns (row titles become data-set names).'],
  power: ['Sample size & power', 'Fill in either the sample size (to get power) or the desired power (to get the sample size). The effect size is computed from the difference and SD, proportions, Cohen’s f or r. The curve shows power for a range of sample sizes.'],

  // ---------------------------------------------------------------- graphs
  'graph-type': ['Graph type', 'Choose how the table is drawn. All types use the same data, so you can switch freely. <b>Analysis plot</b> draws plots produced by analyses (Q-Q, PCA, Bland-Altman, regression diagnostics, correlation heat map).'],
  'error-bars': ['Error bars', '<b>SD</b> shows the scatter of the data; <b>SEM</b> shows how precisely the mean is known; <b>95% CI</b> is usually the most informative. State in the legend which one you plotted.'],
  significance: ['Significance brackets', 'Brackets with asterisks (or P values) are drawn from linked t test, ANOVA, Kruskal-Wallis or two-way ANOVA results. Turn them off or include “ns” comparisons here.'],
  'linked-analyses': ['Showing analysis results on the graph', 'Tick an analysis to overlay its output: fitted curves (nonlinear/linear regression, smoothing), significance brackets or ROC curves. Analyses run on the same data table are listed.'],
  'graph-axes': ['Axes', 'Set the axis style (classic L-shaped, frame or gridlines), fixed ranges (leave blank for automatic), logarithmic scales and horizontal orientation for column/grouped graphs.'],
  'graph-appearance': ['Appearance', 'Font, sizes, symbol size, line thickness, bar width, spread of scatter points, background and graph dimensions (in pixels at 96 dpi). Drag the blue square at the bottom-right of the graph to resize it.'],
  'graph-series': ['Data set colors & symbols', 'Choose a color scheme, then override the color or symbol of individual data sets. Untick a data set to hide it from this graph without changing the data.'],
  annotations: ['Text labels', 'Add free text anywhere on the graph (e.g. n values, “P = 0.03”, arrows described in text). Drag labels on the graph to move them; edit or delete them here.'],
  'fit-equation': ['Equation on graph', 'Shows the fitted equation or key parameters (EC50, Km, R²…) of linked regressions in the corner of the graph. Drag them to reposition.'],
  'analysis-plot': ['Analysis plot', 'Draws a plot produced by an analysis. When an analysis offers several plots (e.g. PCA: scree, biplot, loadings) choose which one here. Titles left blank are filled in automatically.'],
  'var-scatter': ['Variables scatter', 'For multiple-variables tables: pick which variable goes on X and Y, and optionally color the points by a third variable.'],
  'graph-export': ['Exporting graphs', 'Export… opens the full dialog: TIFF, PNG, PDF, SVG, JPEG or WEBP; size in inches, cm or pixels; any resolution from 72 to 2400 dpi (embedded in TIFF/PNG/JPEG files); grayscale; transparent background. Quick buttons export TIFF/PNG at 300 dpi, vector PDF or SVG.'],

  'graph-presets': ['Quick styles & format tools', 'One click applies a complete look (Classic, Journal, Slides, Minimal, Boxed, Grayscale) without touching data or titles. <b>Copy format</b> / <b>Paste format</b> move formatting between graphs; <b>Apply to all graphs</b> gives every graph of the same table type this look; <b>Reset</b> restores defaults.'],
  'ref-lines': ['Reference lines', 'Add horizontal (Y = value) or vertical (X = value) lines with an optional label — e.g. 100% of control, a detection limit, a threshold or the time of treatment.'],
  'graph-legend': ['Legend', 'Show or hide the legend, choose a position (outside right, top, bottom or inside a corner) or drag it on the graph, and optionally draw a frame around it.'],

  // ---------------------------------------------------------------- accounts & storage
  accounts: ['Accounts & privacy', 'Each person signs in with a user ID and password. Projects saved on the server belong to that account only — no other user can list, open, change or delete them, and administrators see only names and sizes, never contents. Passwords are stored as salted scrypt hashes. There is no e-mail recovery: ask an administrator for a one-time password if you forget it.'],
  'project-browser': ['My projects', 'All projects stored on the server for your account (end-to-end encrypted). Open, rename, copy, download (⤓) or delete them. Projects auto-save a few seconds after each change; the status next to the project name shows when it was last saved.'],
  quota: ['Storage quota', 'Each account has a storage quota (256 MB by default). From half of the quota (128 MB) you are asked to offload: download older projects to your computer (optionally encrypted) and delete them from the server. You can upload them again at any time (File → Open / upload project file) to view or edit them.'],
  'encryption': ['End-to-end encryption', 'All projects you save on the server — contents and names — are encrypted in your browser with your personal data key (AES-256-GCM). Your password never leaves the browser; the server stores only ciphertext and cannot read your work. Downloads can additionally be encrypted with a file password.'],
  'admin': ['Administration', 'Administrators work in a separate administration console that only opens on the server computer itself (localhost, a different port). There they set up the server on first start, create and delete accounts, issue one-time passwords, set limits and the registration policy. They can never open users’ projects.'],
  security: ['Security', 'Sessions use HttpOnly SameSite=Strict cookies; requests are checked against cross-site forgery; failed sign-ins are throttled; strict Content-Security-Policy; size, rate, RAM and CPU limits per user; every project query is scoped to its owner.'],

  'table-nested': ['Nested tables', 'Each data set is a group; its subcolumns are the subjects (e.g. animals, patients, culture plates) in that group; each row is a replicate measurement of a subject. Analyze with the nested t test / nested ANOVA, which treats the subject — not the replicate — as the experimental unit.'],
  'mixed-models': ['Mixed-effects models', 'A mixed-effects model estimates the treatment effects (fixed effects) while modelling the variability between subjects as a random effect. Unlike repeated-measures ANOVA it keeps subjects with missing values. OpenPrism fits it by REML and tests fixed effects with Wald tests.'],
  'mixed_one_way': ['Repeated measures by mixed model', 'Same design as repeated-measures one-way ANOVA (rows = subjects, columns = treatments) but analyzed with a mixed-effects model, so subjects with a missing value are not discarded. Reports Wald tests, variance components and model-based multiple comparisons.'],
  'two_way_rm': ['Two-way repeated measures', 'Two-way ANOVA for designs where the same subjects are measured repeatedly (across rows, across data sets, or both), fitted as a mixed-effects model with a random intercept per subject. Handles missing values.'],
  'nested': ['Nested t test / ANOVA', 'Compares groups when each subject was measured several times. A mixed-effects model treats subjects as the experimental unit, avoiding the false positives of treating technical replicates as independent. Reports the intraclass correlation.'],
  'factorial': ['Three-way / n-way ANOVA & ANCOVA', 'Analyzes a dependent variable with up to four categorical factors (e.g. three-way ANOVA) and optional continuous covariates (ANCOVA), using Type III sums of squares. Enter one row per observation in a multiple-variables table, factors coded as numbers or labels.'],
  'poisson': ['Poisson regression', 'For count outcomes (number of colonies, events, cells). Coefficients are reported as rate ratios. A dispersion well above 1 warns of over-dispersion.'],
  'deming': ['Deming regression', 'Compares two measurement methods when both have measurement error (ordinary regression assumes X is exact). Enter method 1 as X and method 2 as Y. A slope CI containing 1 and an intercept CI containing 0 indicate agreement.'],
  'passing_bablok': ['Passing-Bablok regression', 'A robust, nonparametric method-comparison regression based on the median of all pairwise slopes; insensitive to outliers and to the error distribution.'],
  'equivalence': ['Equivalence test (TOST)', 'Tests whether two groups are equivalent — their difference lies within margins you set in advance — with two one-sided tests. A non-significant ordinary t test does not show equivalence; this test can.'],
  'bayes_t': ['Bayesian t test', 'Reports a Bayes factor (BF10): how many times more likely the data are if there is a difference than if there is none. BF10 > 3 supports a difference, BF10 < 1/3 supports the absence of a difference.'],
  'bootstrap': ['Bootstrap confidence intervals', 'Resamples your data thousands of times to obtain confidence intervals for the mean, median or SD (and their differences) without assuming a distribution.'],
  'permutation': ['Permutation test', 'Compares two groups by shuffling group labels; exact for small samples. No assumption about the distribution of the data.'],
  'rout': ['ROUT outlier removal', 'Fits the curve robustly (Lorentzian/Cauchy loss), flags points whose residuals are too large at a false discovery rate Q (1% is typical), and fits again without them. The removed points are listed in the results.'],
  'axis-break': ['Axis break', 'Splits the Y axis into a lower and an upper part with a gap between “Break from” and “Break to”, so that very large values do not compress the rest of the data. Break marks are drawn on the axis.'],
  'recovery-key': ['Recovery key', 'Shown once when you create your account. If you forget your password, an administrator can let you sign in with a one-time password, but only the recovery key can unlock your existing projects. Store it safely; you can create a new one in My account.'],
  'profile-ci': ['Profile-likelihood confidence intervals', 'For each parameter, OpenPrism fixes it at trial values, refits the others and finds where the fit becomes significantly worse (sum of squares above SSmin·(1+F/df)). These intervals can be asymmetric and are more accurate than the usual (asymptotic) intervals for nonlinear models; “unbounded” means the data do not define that limit.'],
  'export': ['Exporting graphs and layouts', 'Choose the format (TIFF, PNG, PDF, SVG, EPS, EMF, JPEG, WEBP), the printed size in inches, cm or pixels, and the resolution (72–2400 dpi). TIFF and PNG files carry the resolution in their metadata. PDF, SVG, EPS and EMF stay vector with editable text (EPS for Illustrator/LaTeX, EMF for Word/PowerPoint). “Export all graphs” saves every graph in one ZIP file.'],
  'embedded-tables': ['Results tables on layouts', 'Add any section of an analysis result (e.g. the ANOVA table or best-fit values) to a layout page. It updates when the analysis re-runs and is exported as real text (vector) in PDF and SVG.'],
  // ---------------------------------------------------------------- layouts
  layouts: ['Layouts (figures)', 'Arrange several graphs and text on a page. Drag to move, drag handles to resize (Shift keeps proportions), arrow keys nudge, Delete removes. Add panel labels A, B, C…, auto-arrange in a grid, and export PNG (300 dpi), SVG or PDF.'],
  shortcuts: ['Keyboard shortcuts', 'Ctrl+T new table · Ctrl+K analyze · Ctrl+G new graph · Ctrl+L new layout · Ctrl+S save · Ctrl+O open · Ctrl+Z / Ctrl+Y undo / redo · F2 rename · Ctrl+C / Ctrl+V copy / paste cells.'],
};

let pop = null;
function closePop() { pop?.remove(); pop = null; document.removeEventListener('mousedown', outside, true); }
function outside(e) { if (pop && !pop.contains(e.target) && !e.target.closest('.help-q')) closePop(); }

/** A small "?" button that shows on-the-spot help for a topic. */
export function helpIcon(topic, opts = {}) {
  const b = h('button', {
    class: `help-q ${opts.class || ''}`, type: 'button', title: `Help: ${HELP[topic]?.[0] || topic}`, 'aria-label': 'Help',
    onclick: (e) => { e.preventDefault(); e.stopPropagation(); showHelp(topic, b); },
  }, '?');
  return b;
}

export function showHelp(topic, anchorEl) {
  closePop();
  const [title, html] = HELP[topic] || ['Help', 'See the user manual.'];
  pop = h('div', { class: 'help-pop', role: 'dialog' },
    h('div', { class: 'help-pop-head' }, h('b', {}, title), h('button', { class: 'x', onclick: closePop, title: 'Close' }, '×')),
    h('div', { class: 'help-pop-body', html }),
    h('div', { class: 'help-pop-foot' },
      h('a', { href: '#', onclick: (e) => { e.preventDefault(); closePop(); openManual(topic); } }, 'Read more in the manual →')));
  document.body.append(pop);
  fitToViewport(pop, anchorEl);
  setTimeout(() => document.addEventListener('mousedown', outside, true), 0);
}

/** Open the full manual (optionally at a section) in a large in-app window. */
export function openManual(topic = '') {
  const src = `${MANUAL_URL}${topic ? `#${topic}` : ''}`;
  modal({
    title: 'OpenPrism user manual', wide: true,
    body: h('div', { class: 'manual-frame-wrap' },
      h('iframe', { class: 'manual-frame', src, title: 'User manual' }),
      h('div', { class: 'hint', style: { marginTop: '6px' } }, h('a', { href: src, target: '_blank', rel: 'noopener' }, 'Open the manual in a new browser tab ↗'))),
    buttons: [{ label: 'Close', primary: true }],
  });
}

/** Label text followed by a help icon. */
export const withHelp = (text, topic) => h('span', { class: 'with-help' }, text, helpIcon(topic));
