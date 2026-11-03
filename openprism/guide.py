"""Structured guide to every analysis: what it is, when to use it, how to lay
out the data, how to run it, how to read the results, assumptions and
alternatives. One source feeds the analysis dialog ("About this analysis"),
the catalog API and the manual (tools/build_manual.py).

Fields
    what     one-paragraph description
    when     typical questions / situations it answers
    data     table type and layout
    how      steps / important options
    results  how to read the main numbers
    assume   assumptions (and how to check them)
    alt      what to use instead when assumptions fail or for related questions
    ref      key references
"""
from __future__ import annotations

G: dict[str, dict[str, str]] = {}


def g(key, what, when, data, how, results, assume, alt, ref=""):
    G[key] = {"what": what, "when": when, "data": data, "how": how, "results": results, "assume": assume, "alt": alt, "ref": ref}


# ============================================================ describing data
g("descriptive",
  "Summarizes each data set: number of values, mean, SD, SEM, confidence interval of the mean, median with its confidence interval, quartiles, range, coefficient of variation, geometric mean and SD factor, skewness and kurtosis.",
  "Always — before any test, to know your data. Use it to report n, central tendency and spread, and to spot entry errors (impossible minima/maxima).",
  "Column table: one data set per column (replicates as rows). Also works on XY, grouped and multiple-variables tables.",
  "Choose the data sets and the confidence level. Results update automatically when values change.",
  "Report mean ± SD to describe variability of individuals; mean ± SEM or a 95% CI to describe how precisely the mean is known. For skewed data report the median and quartiles (or the geometric mean and geometric SD factor for log-normal data).",
  "None for the numbers themselves. The CI of the mean assumes approximately Gaussian data or a large sample; the CI of the median is distribution-free.",
  "Frequency distribution (histogram) to see the shape; normality tests; bootstrap CIs for any statistic.",
  "Altman & Bland (2005) BMJ 331:903 (SD vs SEM).")

g("normality",
  "Tests whether values plausibly come from a Gaussian (normal) distribution: Shapiro-Wilk, D'Agostino-Pearson omnibus (skewness + kurtosis), Kolmogorov-Smirnov with the Lilliefors correction, Anderson-Darling, Jarque-Bera and Shapiro-Francia; optionally the same tests on log-transformed values (lognormality). A Q-Q plot is drawn.",
  "Before choosing between a parametric test (t test, ANOVA) and a nonparametric one, or to check residuals of a model.",
  "Column table (one data set per column); also XY/grouped/multi tables.",
  "Pick the tests (Shapiro-Wilk is the best general choice for n ≤ 5000; D'Agostino-Pearson needs n ≥ 8). Tick 'lognormal' when values are positive and skewed.",
  "'Passed' (P ≥ α) means there is no evidence against normality — not proof of normality. With small n the tests have little power; with very large n they flag trivial departures. Always look at the Q-Q plot: points close to the line mean near-Gaussian data.",
  "Independent values.",
  "If clearly non-Gaussian: transform (log), use a nonparametric test, a robust test (trimmed means) or a GLM with a suitable distribution.",
  "Shapiro & Wilk (1965) Biometrika 52:591; D'Agostino et al. (1990) Am Stat 44:316.")

g("one_sample",
  "Compares the mean (one-sample t test) or median (Wilcoxon signed-rank test) of one data set with a hypothetical value.",
  "Is the mean response different from 0 (or 100%, or a reference value)? Example: is a normalized ratio different from 1?",
  "Column table, one data set.",
  "Choose the test and enter the hypothetical value.",
  "P < α: the population mean (median) differs from the hypothetical value. Report the difference with its 95% CI.",
  "t test: independent values from an approximately Gaussian population. Wilcoxon: symmetric distribution around the median.",
  "Sign test (no symmetry assumption) — see 'Sign test, SD test, percentile CI…'.",
  "")

g("one_sample_more",
  "A set of one-sample procedures: the exact sign test of a median, a chi-square test that the SD equals a given value, the confidence interval of the SD, a distribution-free confidence interval of any percentile, a normal tolerance interval (Howe) and a prediction interval for one new value.",
  "Quality control and reference ranges: 'Between which limits do 95% of individuals fall, with 95% confidence?' (tolerance interval); 'Where will the next measurement fall?' (prediction interval); 'Is the median different from X?' without assuming symmetry (sign test).",
  "Column table, one data set per column.",
  "Enter the hypothetical median, optionally a hypothetical SD, the percentile of interest and the coverage/confidence of the tolerance interval.",
  "A tolerance interval is wider than a prediction interval, which is wider than a CI of the mean: they answer different questions (population range, next value, mean).",
  "Sign test and percentile CI: independent values only. SD test, tolerance and prediction intervals: Gaussian data — check normality first.",
  "One-sample t / Wilcoxon for the mean / symmetric median; bootstrap CIs.",
  "Howe (1969) JASA 64:610; Hahn & Meeker (1991) Statistical Intervals.")

g("frequency",
  "Builds a frequency distribution (histogram) of the values — counts, relative or cumulative frequencies — as a new data table that can be graphed.",
  "To see the shape of a distribution (skewness, several modes, outliers) or to compare distributions between groups.",
  "Column table.",
  "Choose a bin width (or leave automatic) and whether to tabulate counts, percentages or cumulative values.",
  "The output table is linked to the data: it updates when the data change.",
  "None.",
  "Normality tests and Q-Q plots for formal checks; box or violin plots for comparisons.",
  "")

g("outliers",
  "Identifies outliers by Grubbs' test (one or iteratively several), generalized ESD (Rosner; several outliers at once, avoids masking), ROUT-like robust detection (median/MAD with FDR control), Tukey's IQR fences or the Hampel filter (median ± t·MAD); writes a cleaned copy of the data.",
  "When a value might be a technical error. Never remove a value only because it is inconvenient — record and justify every exclusion.",
  "Column table (or multiple-variables table).",
  "Choose the method: generalized ESD when there may be several outliers, Grubbs for a single suspect value, IQR/Hampel for a quick robust screen.",
  "Listed values are statistically unusual given the others; whether to exclude them is a scientific decision.",
  "Grubbs and ESD assume the non-outlying values are Gaussian. IQR and Hampel make no distributional assumption.",
  "Robust methods (trimmed means, rank tests, robust regression) that are insensitive to outliers instead of removing them.",
  "Rosner (1983) Technometrics 25:165; Motulsky & Brown (2006) BMC Bioinformatics 7:123.")

# ============================================================ comparing two groups
g("ttest",
  "Compares two groups: unpaired t test (optionally with Welch's correction for unequal SDs), paired t test, Mann-Whitney test or Wilcoxon matched-pairs signed-rank test. Reports the difference with its CI, Cohen's d, Hedges' g with CI, a Bayes factor and, for unpaired data, an F test of equal variances. Mann-Whitney and Wilcoxon P values are exact (also with ties) up to n = 50.",
  "Is the mean (or distribution) of group B different from group A? Treated vs control; before vs after on the same subjects (paired).",
  "Column table with two data sets (A and B). For paired data, values on the same row belong to the same subject.",
  "Choose paired/unpaired, parametric/nonparametric; consider Welch's correction (recommended by default when group SDs or sizes differ); choose one- or two-tailed P values (two-tailed unless the direction was fixed before seeing the data).",
  "Report the difference with its 95% CI and the P value. The CI shows the size and precision of the effect; a P value alone does not.",
  "Independent observations (or independent pairs). t tests: Gaussian populations (or differences, if paired); Student's t also equal SDs. Mann-Whitney: tests whether one group tends to have larger values; it compares medians only if the shapes are equal.",
  "Welch t (unequal SDs); Yuen trimmed-means test (outliers, heavy tails); Brunner-Munzel (unequal shapes); permutation test; equivalence test (TOST) to show similarity; Bayesian t test for evidence for H0.",
  "Delacre, Lakens & Leys (2017) Int Rev Soc Psychol 30:92 (use Welch by default).")

g("paired", "", "", "", "", "", "", "")
del G["paired"]

g("effect_sizes",
  "Effect sizes with confidence intervals. Two groups: Cohen's d (CI from the noncentral t distribution), Hedges' g, Glass's Δ, d_av, point-biserial r, common-language effect size P(B > A), Cliff's δ (with bootstrap CI), ratio of means, variance ratio; paired d_z and d_rm. Several groups: η² (with CI), ω², ε², Cohen's f and rank ε².",
  "Whenever you report a test: journals increasingly require effect sizes; they are needed for meta-analyses and power calculations.",
  "Column table: two data sets (or more for η², ω²).",
  "Select the groups (A = control/reference first).",
  "Prefer Hedges' g over d for small samples. Cliff's δ and P(B > A) are robust, rank-based alternatives. Cohen's benchmarks (0.2/0.5/0.8) are only a last resort — interpret against effects known in your field.",
  "d, g and η² CIs assume Gaussian data with equal SDs (Glass's Δ does not assume equal SDs). Cliff's δ: independent values only.",
  "Bootstrap CIs for other statistics; power calculator to plan a study from an expected effect size.",
  "Lakens (2013) Front Psychol 4:863; Cliff (1993) Psychol Bull 114:494.")

g("variance_tests",
  "Tests whether groups have equal variances (SDs): F test (two groups, with CI of the ratio), Levene, Brown-Forsythe (median-centred Levene), Bartlett, Fligner-Killeen, and for two groups the Ansari-Bradley and Mood scale tests.",
  "When the variability itself is of interest (precision of two methods, heterogeneity of responses), or to decide on Welch's correction.",
  "Column table, one group per column.",
  "Select the groups. The Brown-Forsythe test is the recommended general-purpose test.",
  "P < α: the SDs differ. Do not use these tests as a gate before a t test — use Welch's t test routinely instead.",
  "F and Bartlett: Gaussian data (very sensitive to non-normality). Levene/Brown-Forsythe: robust. Fligner-Killeen, Ansari-Bradley, Mood: nonparametric; Ansari-Bradley and Mood assume equal medians.",
  "Welch t test / Welch ANOVA when SDs differ; transform data (log) when SD grows with the mean.",
  "Brown & Forsythe (1974) JASA 69:364; Conover, Johnson & Johnson (1981) Technometrics 23:351.")

g("distribution_tests",
  "Tests whether groups come from the same distribution (any difference in location, spread or shape): Kolmogorov-Smirnov, Cramér-von Mises, Epps-Singleton, Brunner-Munzel and Mann-Whitney (two groups); Anderson-Darling k-sample (permutation P) and Mood's median test (any number of groups), with Holm-adjusted pairwise KS tests.",
  "When the question is 'do the distributions differ?' rather than 'do the means differ?', e.g. comparing cell-size distributions, reaction-time distributions or particle-size spectra.",
  "Column table, one group per column.",
  "Select two or more groups. Permutation P values use 9 999 resamples with a fixed seed (reproducible).",
  "KS is most sensitive in the middle of the distributions; Anderson-Darling and Cramér-von Mises also detect differences in the tails. Brunner-Munzel tests P(X < Y) = ½ even when shapes differ.",
  "Independent observations. KS P values are exact for small samples without ties.",
  "t test / Mann-Whitney for location only; compare variances for spread only.",
  "Scholz & Stephens (1987) JASA 82:918; Brunner & Munzel (2000) Biom J 42:17.")

g("robust_compare",
  "Compares groups using trimmed means (by default 20% from each tail), which are insensitive to outliers and heavy tails: Yuen-Welch test for two groups, Wilcox's heteroscedastic one-way ANOVA of trimmed means for three or more, with Holm-adjusted pairwise Yuen tests.",
  "Data with outliers or long tails where the mean is unrepresentative but you still want a test of 'typical' values with good power — often more powerful than both the t test and the Mann-Whitney test in that situation.",
  "Column table, one group per column (≥ 4 values per group).",
  "Choose the amount of trimming (20% recommended; 0% gives Welch's t test).",
  "Reports trimmed means, their difference with CI, the Welch-type t (or F) and P.",
  "Independent observations; does not assume normality or equal variances.",
  "Mann-Whitney / Kruskal-Wallis; bootstrap; permutation test.",
  "Yuen (1974) Biometrika 61:165; Wilcox (2017) Introduction to Robust Estimation and Hypothesis Testing, 4th ed.")

g("permutation",
  "Permutation (randomization) test of the difference between two groups in mean or median: the observed difference is compared with the differences obtained after reshuffling group labels.",
  "Small samples where distributional assumptions are doubtful; any statistic of interest.",
  "Column table, two groups.",
  "Choose the statistic. Resampling uses a fixed seed, so results are reproducible.",
  "P is the fraction of reshuffles at least as extreme as the observed difference.",
  "Exchangeability under H0 (the groups have the same distribution).",
  "t test, Mann-Whitney, bootstrap CI of the difference.",
  "Good (2005) Permutation, Parametric and Bootstrap Tests of Hypotheses.")

g("bootstrap",
  "Bootstrap confidence interval (percentile and BCa) for the mean, median or SD of each data set, from thousands of resamples with a fixed seed.",
  "When no formula-based CI is available or its assumptions are doubtful (e.g. CI of a median of skewed data).",
  "Column or multiple-variables table.",
  "Choose the statistic, number of resamples and confidence level.",
  "Report the BCa interval; with very small samples (n < 10) bootstrap intervals are too narrow.",
  "Independent values representative of the population.",
  "Exact CI of the median (descriptive statistics), permutation tests.",
  "Efron & Tibshirani (1993) An Introduction to the Bootstrap.")

g("equivalence",
  "Two one-sided tests (TOST) of equivalence: shows that the difference between two means lies within a margin you consider negligible.",
  "Showing that two methods, formulations or batches are equivalent — a non-significant t test does NOT show this.",
  "Column table, two groups.",
  "Enter lower and upper equivalence margins chosen before the experiment on scientific grounds.",
  "Equivalent if the (1 − 2α) CI of the difference lies entirely within the margins (both one-sided P < α).",
  "As for the t test.",
  "Bayesian t test (Bayes factor for H0); Bland-Altman for method agreement.",
  "Schuirmann (1987) J Pharmacokinet Biopharm 15:657; Lakens (2017) SPPS 8:355.")

g("bayes_t",
  "Bayesian t test with the JZS (Cauchy) prior: Bayes factor BF10 quantifies the evidence for a difference versus no difference.",
  "When you need evidence FOR the null hypothesis as well as against it, or want a continuous measure of evidence.",
  "Column table, two groups (paired or unpaired).",
  "Set the prior scale r (0.707 'medium' is the default; 1 'wide').",
  "BF10 > 3 moderate, > 10 strong evidence for a difference; BF10 < 1/3 moderate evidence for no difference.",
  "As for the t test.",
  "Equivalence test (TOST).",
  "Rouder et al. (2009) Psychon Bull Rev 16:225.")

g("roc",
  "Receiver-operating-characteristic curve of a continuous marker for distinguishing patients from controls, with the area under the curve (AUC) and its CI, and sensitivity/specificity at every cutoff.",
  "Evaluating a diagnostic marker or choosing a cutoff.",
  "Column table: controls in column A, patients in column B.",
  "Say whether patients have higher or lower values.",
  "AUC 0.5 = useless, 1 = perfect. Choose cutoffs from the sensitivity/specificity table according to the clinical cost of false positives vs false negatives.",
  "Independent subjects; a representative spectrum of patients and controls.",
  "Diagnostic test accuracy (2 × 2) once a cutoff has been chosen; logistic regression for several markers.",
  "Hanley & McNeil (1982) Radiology 143:29.")

g("bland_altman",
  "Bland-Altman analysis of agreement between two measurement methods: bias (mean difference) and 95% limits of agreement, with a plot of difference vs average.",
  "Can method B replace method A? Correlation is NOT the right tool for this question.",
  "Column table: method A in column A, method B in column B, one subject per row.",
  "Choose difference, ratio or % difference (ratio when the error grows with magnitude).",
  "Judge whether the limits of agreement are clinically acceptable; check the plot for trends (proportional bias).",
  "Differences approximately Gaussian and unrelated to magnitude (otherwise use ratios).",
  "Deming or Passing-Bablok regression; Lin's concordance correlation (reliability analysis).",
  "Bland & Altman (1986) Lancet 1:307.")

# ============================================================ several groups
g("one_way",
  "One-way ANOVA (ordinary, Welch, Brown-Forsythe, repeated measures with Geisser-Greenhouse correction or a mixed model) or the nonparametric Kruskal-Wallis / Friedman tests, followed by multiple comparisons (Tukey, Dunnett, Šídák, Holm-Šídák, Bonferroni, Fisher LSD, FDR, Games-Howell, Dunnett T3, Tamhane T2, Dunn).",
  "Do three or more group means differ? Which groups differ from which (or from a control)?",
  "Column table, one group per column. For repeated measures, each row is one subject measured under every condition.",
  "Choose matching (repeated measures), Gaussian vs nonparametric, then the multiple-comparison method: Tukey for all pairs, Dunnett vs a control, Games-Howell/T3 if SDs differ.",
  "The overall F test asks whether any means differ; multiple comparisons tell which. Report adjusted P values and simultaneous CIs of differences.",
  "Independent groups (or independent subjects); Gaussian residuals; equal SDs for ordinary ANOVA (check the Brown-Forsythe test, or use Welch ANOVA); sphericity for repeated measures (use the Geisser-Greenhouse correction).",
  "Welch ANOVA + Games-Howell (unequal SDs); robust trimmed-means ANOVA; Kruskal-Wallis + Dunn; mixed model when repeated-measures data have missing values; test for trend for ordered groups.",
  "Maxwell, Delaney & Kelley (2018) Designing Experiments and Analyzing Data, 3rd ed.")

g("np_posthoc",
  "Nonparametric multiple comparisons after a Kruskal-Wallis test: Dunn's test, Conover-Iman, Dwass-Steel-Critchlow-Fligner (pairwise ranking, family-wise error built in) or pairwise Mann-Whitney tests, with Holm, Bonferroni, Hochberg or FDR adjustment.",
  "Which groups differ when the data are not Gaussian?",
  "Column table, three or more groups.",
  "Choose the post hoc test and the adjustment. Dunn's test is the most widely reported; Conover-Iman is more powerful; DSCF re-ranks each pair so it does not depend on the other groups.",
  "Adjusted P < α: the pair differs in mean rank (stochastic dominance).",
  "Independent observations; similar shapes for interpretation as differences in medians.",
  "Robust trimmed-means comparisons; Games-Howell after a Welch ANOVA.",
  "Dunn (1964) Technometrics 6:241; Conover & Iman (1979) LA-7677-MS; Critchlow & Fligner (1991) Commun Stat 20:127.")

g("rm_nonparametric",
  "Nonparametric tests for repeated measures (each row a subject): Friedman with Kendall's W, Quade, Page's L test of an ordered trend, Cochran's Q for 0/1 outcomes, and post hoc Nemenyi and Holm-adjusted Wilcoxon comparisons (Wilcoxon and sign tests for two conditions).",
  "The same subjects measured under several conditions when values are ranks, scores or clearly non-Gaussian; binary outcomes (yes/no) measured repeatedly (Cochran's Q).",
  "Column table: one condition per column, one subject per row (rows with missing values are dropped).",
  "Select the conditions (in their natural order for Page's test).",
  "Friedman/Quade P < α: conditions differ. Kendall's W (0–1) measures how consistently subjects rank the conditions.",
  "Independent subjects. Quade assumes values can be compared across subjects (it weights by each subject's range).",
  "Repeated-measures ANOVA or a mixed model for Gaussian data; trend tests.",
  "Quade (1979) JASA 74:680; Page (1963) JASA 58:216.")

g("trend_tests",
  "Tests for a monotonic trend across ordered groups (dose levels, time points, severity grades): ANOVA post test for linear trend (with the test of nonlinear variation), Jonckheere-Terpstra (normal approximation and exact permutation P), Spearman and Kendall correlation with group order, and Page's L for repeated measures.",
  "When groups have a natural order — a trend test is more powerful than an ANOVA that ignores the order.",
  "Column table with the groups ordered left to right.",
  "Order the columns, optionally declare rows as matched subjects.",
  "Significant linear trend: means change steadily with group order (report the slope). Significant nonlinear variation: the change is not a straight line.",
  "Linear-trend test: as for ANOVA. Jonckheere-Terpstra: independent observations, nonparametric.",
  "Linear or nonlinear regression when the groups have numeric doses (XY table).",
  "Jonckheere (1954) Biometrika 41:133.")

g("mixed_one_way",
  "Repeated-measures one-way analysis by a linear mixed-effects model (random intercept per subject, REML). Unlike classic repeated-measures ANOVA, subjects with missing values are kept.",
  "Repeated measures where some subjects miss some time points.",
  "Column table: one condition per column, one subject per row (blanks allowed).",
  "Choose multiple comparisons.",
  "Fixed-effect Wald test of the conditions; SD of subjects and residual; intraclass correlation.",
  "Gaussian random effects and residuals; values missing at random.",
  "Repeated-measures ANOVA when complete; Friedman for non-Gaussian data.",
  "Pinheiro & Bates (2000) Mixed-Effects Models in S and S-PLUS.")

g("mixed_model",
  "General linear mixed-effects model: any numeric or categorical fixed effects, a random intercept for each subject (or plate, litter, centre…), and optionally a random slope so that each subject may respond differently to a predictor. Fixed effects with GLS standard errors and t tests with Satterthwaite degrees of freedom (as lmerTest and SAS PROC MIXED; F tests for factors by the Fai-Cornelius method), random-effect SDs and correlation, residual SD, ICC, REML or ML, and a likelihood-ratio test of whether the random slope is needed. Validated against R's nlme::lme and lmerTest.",
  "Repeated or clustered measurements in long format: growth curves (size vs. age per animal), dose-response per subject, multi-centre studies, any design where observations within the same unit are correlated and some units have missing measurements.",
  "Multiple-variables table in long format: one row per observation; a column with the outcome, one with the subject (group) code, and one per predictor.",
  "Choose the outcome, the subject column, the fixed effects (mark categorical ones as factors), and optionally the predictor with a random slope. Use REML for estimates; ML to compare models with different fixed effects (AIC/BIC).",
  "Fixed effects are interpreted like regression coefficients, for an average subject. The random-slope SD shows how much individual slopes vary; the likelihood-ratio test tells whether that variation is real.",
  "Gaussian random effects and residuals, linear relationships, observations missing at random.",
  "Repeated-measures ANOVA (complete, balanced data); nested ANOVA; GLM for non-Gaussian outcomes.",
  "Pinheiro & Bates (2000) Mixed-Effects Models in S and S-PLUS; Laird & Ware (1982) Biometrics 38:963.")

for _k, _what, _how in [
        ("summary_describe", "Shows each group's mean, SD, SEM, confidence interval of the mean and CV from summary data.", "Choose the confidence level."),
        ("summary_ttest", "Unpaired t test (Student or Welch) computed from two groups' means, SDs (or SEMs) and sample sizes, with the CI of the difference, Cohen's d, Hedges' g and an F test of equal variances. Identical to the t test on the raw data.", "Enter two rows (groups); keep Welch's correction unless you know the SDs are equal."),
        ("summary_anova", "One-way ANOVA from summary data with Welch's ANOVA and every multiple-comparison method (Tukey, Dunnett, Šídák, Holm-Šídák, Bonferroni, FDR, Games-Howell). Identical to the analysis of the raw data.", "One row per group; choose the post test (Dunnett: give the control's row number, 0 = first).")]:
    g(_key := _k, _what,
      "When only summary statistics are available — results reported in a paper, a lab notebook or a Prism table entered as mean, SD, N — and you want the same test you would run on the raw data.",
      "Summary data table: one row per group (row title = group name), columns Mean, SD and N. Rename the SD column to “SEM” if you have standard errors; they are converted with SD = SEM·√n.",
      _how,
      "Interpret exactly as the corresponding analysis of raw data. Normality and outliers cannot be checked from summaries — consider whether the original data were roughly Gaussian.",
      "As for the t test / ANOVA on raw data (independent observations, approximately Gaussian groups; equal SDs unless Welch / Games-Howell).",
      "The analyses of raw data whenever the raw values are available (they also allow normality checks, nonparametric and robust tests).",
      "")

g("nested",
  "Nested t test / nested one-way ANOVA: compares groups when each group contains several subjects (e.g. animals) with several measurements each (e.g. cells), treating subjects as a random effect.",
  "Avoids pseudo-replication: measurements within the same subject are not independent.",
  "Nested table: subcolumns = subjects, rows = replicate measurements.",
  "Choose multiple comparisons for 3+ groups.",
  "Inference is about groups at the subject level; the intraclass correlation shows how much variation is between subjects.",
  "Gaussian random effects and residuals.",
  "Average the replicates per subject and run an ordinary t test / ANOVA (equivalent for balanced designs).",
  "Lazic (2010) BMC Neurosci 11:5.")

g("two_way",
  "Two-way ANOVA (type III sums of squares) of two factors and their interaction, with multiple comparisons within rows or columns.",
  "Effects of two factors (e.g. genotype × treatment) and whether the effect of one depends on the other (interaction).",
  "Grouped table: rows = levels of one factor, data sets = levels of the other, subcolumns = replicates.",
  "Fit the interaction when there are replicates; choose comparisons within rows or columns.",
  "Interpret the interaction first: if significant, describe simple effects rather than main effects.",
  "Independent observations, Gaussian residuals, equal variances.",
  "Two-way repeated measures (mixed model); nonparametric aligned-rank-transform ANOVA; n-way ANOVA for 3+ factors.",
  "")

g("two_way_rm",
  "Two-way repeated-measures analysis by a mixed-effects model: repeated across rows, across data sets, or both.",
  "Each subject measured at several time points under one or several treatments.",
  "Grouped table: see the option text for the exact layout.",
  "Choose which factor is repeated.",
  "As for two-way ANOVA, with subject variation removed.",
  "Gaussian random effects and residuals.",
  "Ordinary two-way ANOVA (no matching); nonparametric ART ANOVA.",
  "")

g("two_way_np",
  "Nonparametric two-way ANOVA by the aligned rank transform (ART; Wobbrock et al.), which tests main effects and the interaction validly, plus the classic Scheirer-Ray-Hare test.",
  "Two-factor designs with non-Gaussian data, ordinal ratings or outliers.",
  "Grouped table with at least two replicates per cell.",
  "Nothing to set.",
  "Interpret like a two-way ANOVA. Prefer the ART results; Scheirer-Ray-Hare has low power and an unreliable interaction test.",
  "Independent observations.",
  "Two-way ANOVA after a transformation; GLM for counts or proportions.",
  "Wobbrock et al. (2011) Proc CHI 143; Scheirer, Ray & Hare (1976) Biometrics 32:429.")

g("factorial",
  "Three-way and higher n-way ANOVA and ANCOVA from a multiple-variables table, with any number of categorical factors and continuous covariates.",
  "Designs with three or more factors, or adjusting group comparisons for a covariate (e.g. baseline value).",
  "Multiple-variables table: one column per factor (codes), covariate and outcome; one row per observation.",
  "Pick the outcome, factors and covariates; choose all interactions or main effects only.",
  "Type III F tests for each term.",
  "As for ANOVA; for ANCOVA, parallel slopes (no covariate × group interaction).",
  "GLM for non-Gaussian outcomes; mixed models for repeated factors.",
  "")

g("multiple_t",
  "Separate t tests for every row of a grouped table, with Holm-Šídák, Bonferroni or FDR correction.",
  "Many independent comparisons (e.g. many genes or time points analyzed separately).",
  "Grouped table: two data sets, one comparison per row.",
  "Choose the correction (FDR when many rows and discoveries are screened).",
  "Adjusted P values per row.",
  "As for the t test, within each row.",
  "Two-way ANOVA when rows are levels of a factor.",
  "")

# ============================================================ regression & curves
g("linear",
  "Simple linear regression: slope and intercept with SEs and CIs, R², Sy.x, F test of zero slope, runs test, comparison of slopes and intercepts between data sets, confidence bands.",
  "Straight-line relationships, standard curves, rates.",
  "XY table: X values in the X column, one or more Y data sets (replicates allowed).",
  "Optionally force the line through the origin, fit only the means, plot bands.",
  "Report the slope with its CI. The runs test checks whether points systematically deviate from the line (try a curve if P is small).",
  "X known without error; independent Y with Gaussian scatter of constant SD around the line.",
  "Deming / Passing-Bablok when X has error; robust regression for outliers; polynomial or nonlinear regression for curves.",
  "")

g("polynomial",
  "Polynomial regression of order 1–10, solved exactly from the decimal data in 80-digit arithmetic (passes the NIST Filip benchmark with ≥ 10 correct digits), with coefficient SEs and CIs, R², AICc and an extra-sum-of-squares F test against the next lower order.",
  "Empirical curves without a mechanistic model, e.g. calibration curves with slight curvature.",
  "XY table.",
  "Choose the order. Start low; increase only if the F test for the extra term is significant.",
  "Coefficients of high-order polynomials are rarely interpretable; use the curve for interpolation within the data range only.",
  "As for linear regression.",
  "Nonlinear regression with a mechanistic model; spline/LOWESS smoothing.",
  "NIST StRD Filip data set.")

g("nonlinear",
  "Nonlinear regression (curve fitting) with 119 built-in equations or your own, constraints, shared (global) parameters, weighting, model comparison (extra-SS F test and AICc), interpolation of unknowns, asymptotic and profile-likelihood CIs, ROUT robust fitting and outlier removal. The fitter combines Levenberg-Marquardt and a trust-region method and keeps the best solution (all NIST StRD problems pass).",
  "Dose-response (EC50), binding (Kd, Bmax), enzyme kinetics (Km, Vmax), decay and growth rates, any mechanistic model.",
  "XY table (replicates allowed).",
  "Pick the equation, constrain parameters fixed by the design (e.g. Bottom = 0), consider weighting when scatter grows with Y, compare models when unsure.",
  "Check that the curve goes through the data and that CIs are finite and narrow; 'ambiguous' means the data do not define a parameter. Prefer profile-likelihood CIs for nonlinear parameters.",
  "Correct model; X without error; independent Gaussian scatter (or as weighted).",
  "Polynomial regression; robust fitting (ROUT); cosinor for rhythms.",
  "Motulsky & Christopoulos (2004) Fitting Models to Biological Data Using Linear and Nonlinear Regression.")

g("correlation",
  "Pearson, Spearman or Kendall τ-b correlation with CIs and P values, or a full correlation matrix with a heat map.",
  "How strongly do two variables vary together? (Not: can one method replace another — use Bland-Altman.)",
  "XY table (X vs each Y), column or multiple-variables table.",
  "Pick Pearson (linear, Gaussian), Spearman (monotonic, ranks) or Kendall (ranks, robust to ties, better CIs for small n).",
  "r ranges −1…1; r² = fraction of shared variance. Correlation is not causation.",
  "Pearson: bivariate Gaussian, linear relationship, independent pairs.",
  "Partial correlation (adjusting for other variables); regression to predict Y from X.",
  "Bonett & Wright (2000) Psychometrika 65:23.")

g("partial_correlation",
  "Partial correlation of each pair of variables controlling for all other selected variables (Pearson or Spearman), with CIs and tests, and the partial correlation matrix.",
  "Is the association between A and B explained by a third variable C?",
  "Multiple-variables table, one column per variable, one row per subject.",
  "Select ≥ 3 variables.",
  "Compare ordinary and partial r: a large drop means the association is (partly) explained by the controlled variables.",
  "As for Pearson/Spearman correlation; linear relationships with the controlled variables.",
  "Multiple regression.",
  "")

g("robust_regression",
  "Robust and nonparametric straight-line regression: Theil-Sen (median of pairwise slopes), Siegel repeated medians, Huber and Tukey bisquare M-estimators, and quantile (median/LAD) regression, with ordinary least squares for comparison.",
  "Outliers or heavy-tailed scatter that would distort least squares; modelling a percentile (e.g. the 90th) instead of the mean.",
  "XY table.",
  "Choose the quantile for quantile regression (0.5 = median).",
  "Compare the robust slopes with OLS: large differences reveal influential points.",
  "Independent observations; Theil-Sen and Siegel make no distributional assumption.",
  "ROUT robust nonlinear fitting; regression diagnostics.",
  "Sen (1968) JASA 63:1379; Koenker (2005) Quantile Regression.")

g("trend_mk",
  "Mann-Kendall test for a monotonic trend in a series, with Kendall's τ and Sen's slope (with CI).",
  "Environmental and monitoring data: is there an upward or downward trend over time, regardless of its shape?",
  "XY table (X = time) or a column table in time order.",
  "Nothing to set.",
  "Sen's slope = median change per unit X; robust to outliers.",
  "Independent observations (serial correlation inflates false positives — check with the randomness tests).",
  "Linear regression on time; Theil-Sen regression.",
  "Mann (1945) Econometrica 13:245; Kendall (1975) Rank Correlation Methods; Sen (1968).")

g("cosinor",
  "Cosinor analysis of rhythms with a known period (e.g. 24 h): MESOR, amplitude and acrophase (time of peak) with CIs, zero-amplitude F test and percent rhythm; optional harmonics for non-sinusoidal shapes.",
  "Circadian, ultradian or seasonal rhythms in physiology, gene expression or behaviour.",
  "XY table: X = time (any origin), Y = measurements.",
  "Enter the period in X units; add harmonics when the rhythm is asymmetric.",
  "A significant zero-amplitude test means a rhythm with this period is present. The peak time is in X units modulo the period.",
  "Correct period; independent Gaussian residuals.",
  "Nonlinear regression with a custom sine model (to estimate the period); circular statistics for event times.",
  "Cornelissen (2014) Theor Biol Med Model 11:16.")

g("auc",
  "Area under an XY curve by the trapezoid rule, with peaks above a baseline.",
  "Total exposure (pharmacokinetics), response over time.",
  "XY table.",
  "Enter the baseline.",
  "Total and positive/negative areas; peak height and position.",
  "Points connected by straight lines represent the curve.",
  "Smooth/integrate for cumulative curves.",
  "")

g("deming",
  "Deming regression for method comparison when both X and Y have measurement error.",
  "Comparing two analytical methods.",
  "XY table: method X vs method Y.",
  "Enter the ratio of error SDs (1 if both methods are equally precise).",
  "Slope 1 and intercept 0 (within their CIs) mean no proportional or constant bias.",
  "Gaussian errors; known error-variance ratio.",
  "Passing-Bablok (nonparametric); Bland-Altman.",
  "Linnet (1993) Clin Chem 39:424.")

g("passing_bablok",
  "Passing-Bablok nonparametric method-comparison regression with CIs.",
  "Comparing two methods when errors are not Gaussian or outliers are present.",
  "XY table: method X vs method Y.",
  "Nothing to set.",
  "As for Deming regression.",
  "Linear relationship; continuously distributed values.",
  "Deming regression; Bland-Altman.",
  "Passing & Bablok (1983) J Clin Chem Clin Biochem 21:709.")

g("smooth",
  "LOWESS smoothing, moving average, numerical derivative or cumulative integral of an XY curve, written to a new table.",
  "Visualizing trends in noisy data; rates of change; cumulative amounts.",
  "XY table.",
  "Choose the operation and its window.",
  "Smoothed curves are descriptive — do not run tests on smoothed data.",
  "None.",
  "Nonlinear regression for a model-based curve.",
  "Cleveland (1979) JASA 74:829.")

# ============================================================ multiple variables
g("multiple_regression",
  "Multiple linear regression: coefficients with SEs, CIs and VIF, R², adjusted R², AICc, overall F test, residual plots. Ill-conditioned designs are solved exactly in high precision.",
  "Predicting an outcome from several variables or adjusting an effect for confounders.",
  "Multiple-variables table: one column per variable, one row per subject.",
  "Choose the outcome and predictors.",
  "Each coefficient is the change in Y per unit of that predictor with the others held constant. VIF > 10 signals multicollinearity.",
  "Linear relationships, independent Gaussian residuals with constant variance (check with regression diagnostics).",
  "GLM for counts/proportions; regression diagnostics; robust regression.",
  "")

g("regression_diagnostics",
  "Checks the assumptions of a multiple linear regression: Breusch-Pagan and White (heteroscedasticity), Ramsey RESET (functional form), Jarque-Bera and Shapiro-Wilk (normal residuals), Durbin-Watson and Breusch-Godfrey (autocorrelation), VIF/tolerance, condition number, and influential points (Cook's distance, leverage, studentized residuals, DFFITS) with plots.",
  "After fitting a regression, before trusting its P values and CIs.",
  "Multiple-variables table (same layout as multiple regression).",
  "Choose the outcome and predictors.",
  "Significant heteroscedasticity: consider a transformation or GLM; RESET significant: add nonlinear terms; influential points: check them, report results with and without.",
  "—",
  "Robust regression; GLM.",
  "Breusch & Pagan (1979) Econometrica 47:1287; Cook (1977) Technometrics 19:15.")

g("logistic",
  "Multiple logistic regression for a 0/1 outcome: coefficients, odds ratios with CIs, likelihood-ratio test, pseudo-R², classification table and ROC.",
  "Predicting a binary outcome (disease yes/no, response yes/no) from several variables.",
  "Multiple-variables table; outcome column coded 0/1.",
  "Choose the outcome, predictors and classification cutoff.",
  "Odds ratio = multiplicative change in the odds per unit of the predictor.",
  "Independent observations; linearity on the logit scale; ≥ ~10 events per predictor.",
  "GLM with probit or cloglog link; ordinal regression for ordered categories.",
  "")

g("glm",
  "Generalized linear models: Gaussian, binomial (logit, probit, cloglog, log), Poisson, negative binomial (over-dispersion estimated), gamma and inverse Gaussian with any appropriate link; coefficients, exp(β) as rate or odds ratios, deviance, Pearson χ², dispersion, AIC/BIC, likelihood-ratio test.",
  "Outcomes that are counts, proportions, or positive skewed measurements, where ordinary regression is inappropriate.",
  "Multiple-variables table; one row per observation.",
  "Choose the distribution matching the outcome (counts → Poisson, or negative binomial if over-dispersed; positive skewed → gamma) and the link (log for multiplicative effects).",
  "With a log link exp(β) is the ratio of means per unit of X. A Pearson χ²/df much larger than 1 for Poisson means over-dispersion.",
  "Correct distribution family and link; independent observations.",
  "Poisson regression analysis; ordinal regression; transformations + linear regression.",
  "McCullagh & Nelder (1989) Generalized Linear Models.")

g("poisson",
  "Poisson regression for counts with rate ratios, deviance and over-dispersion check.",
  "Counts of events (cells, colonies, lesions) as a function of predictors.",
  "Multiple-variables table.",
  "Choose the count variable and predictors.",
  "exp(β) = rate ratio per unit of the predictor.",
  "Poisson variation (variance = mean).",
  "Negative binomial GLM when over-dispersed.",
  "")

g("ordinal",
  "Ordinal logistic (proportional-odds) or probit regression for ordered categories (e.g. scores 0–4, mild/moderate/severe): coefficients, odds ratios, thresholds, likelihood-ratio test.",
  "Ordered outcomes where the distances between categories are unknown.",
  "Multiple-variables table; outcome coded as ordered numbers.",
  "Choose the outcome, predictors and link.",
  "Odds ratio = factor by which the odds of being in a higher category multiply per unit of the predictor.",
  "Proportional odds (the same effect at every threshold).",
  "Mann-Whitney / Kruskal-Wallis for simple group comparisons of ordinal data.",
  "McCullagh (1980) JRSS B 42:109.")

g("cox",
  "Cox proportional hazards regression (Efron ties): hazard ratios with CIs, likelihood-ratio test.",
  "Effect of several variables on survival time with censored data.",
  "Multiple-variables table with a time column, an event column (1 = event, 0 = censored) and covariates.",
  "Choose time, event and covariates.",
  "Hazard ratio > 1: higher risk per unit of the covariate.",
  "Proportional hazards; independent censoring.",
  "Log-rank and RMST comparisons (survival table) when there are only groups.",
  "Cox (1972) JRSS B 34:187.")

g("pca",
  "Principal component analysis: eigenvalues, explained variance, loadings, scores, scree plot and biplot.",
  "Reducing many correlated variables to a few components; exploring structure.",
  "Multiple-variables table.",
  "Standardize variables measured in different units.",
  "Components with eigenvalue > 1 (or before the scree-plot elbow) are usually retained.",
  "Linear relationships; complete rows.",
  "Cluster analysis to find groups of observations.",
  "Jolliffe (2002) Principal Component Analysis.")

g("manova",
  "One-way MANOVA with Wilks, Pillai, Hotelling-Lawley and Roy tests, Hotelling's T² for two groups, Box's M test, follow-up univariate ANOVAs and group means.",
  "Do groups differ on several outcome variables considered jointly?",
  "Multiple-variables table: one column of group codes, one column per outcome.",
  "Choose the grouping column and the outcome variables.",
  "Pillai's trace is the most robust statistic. Follow up with univariate ANOVAs or discriminant analysis.",
  "Multivariate Gaussian outcomes; equal covariance matrices (Box's M).",
  "Separate ANOVAs with multiplicity correction.",
  "")

g("cluster",
  "Cluster analysis: hierarchical (Ward, average, complete, single linkage) with dendrogram, or k-means (25 k-means++ starts, fixed seed); silhouette widths, Calinski-Harabasz index, cluster means and membership, PCA plot.",
  "Finding groups of similar observations (samples, patients, compounds).",
  "Multiple-variables table: one row per observation, one column per variable.",
  "Standardize variables in different units; try several k and compare silhouettes.",
  "Mean silhouette > 0.5 suggests a reasonable structure; < 0.25 little structure.",
  "Euclidean distance is meaningful for the variables.",
  "PCA to visualize structure.",
  "Rousseeuw (1987) J Comput Appl Math 20:53.")

g("meta",
  "Meta-analysis: fixed-effect and random-effects pooling (REML, DerSimonian-Laird, Paule-Mandel; optional Hartung-Knapp), heterogeneity (Q, τ², I², H²), prediction interval, Egger and Begg tests, leave-one-out sensitivity, forest and funnel plots. Accepts effects with SEs or CIs, two-group means/SDs (Hedges' g or mean difference) or 2 × 2 counts (OR, RR, RD).",
  "Combining results of several studies or experiments.",
  "Multiple-variables table: one row per study (row labels = study names), columns as chosen under 'Columns contain'.",
  "Choose the input format and effect measure; random effects (REML) with Hartung-Knapp is the safest default.",
  "Report the pooled effect with CI, τ² and I², and the prediction interval (where the effect of a new study is expected to lie).",
  "Independent studies; known within-study variances; random effects: normally distributed true effects.",
  "Narrative synthesis when studies are too heterogeneous.",
  "Borenstein et al. (2009) Introduction to Meta-Analysis; Higgins et al. (2009) JRSS A 172:137.")

g("reliability",
  "Reliability and agreement: all six intraclass correlations (Shrout & Fleiss) with CIs, Cronbach's α (with Feldt CI, item statistics), Lin's concordance correlation (two raters), Kendall's W, and Fleiss' κ for categorical ratings.",
  "Inter-rater or test-retest reliability; internal consistency of a questionnaire.",
  "Column or multiple-variables table: one column per rater/item, one row per subject.",
  "Select the raters/items.",
  "Choose the ICC form that matches the design: ICC(2,1) absolute agreement when raters are a random sample and their bias matters; ICC(3,1) consistency when only ranking matters; ICC(·,k) for the average of k raters. ICC > 0.9 excellent, 0.75–0.9 good.",
  "Gaussian data for ICC CIs; complete rows.",
  "Cohen's kappa for two raters with categories; Bland-Altman for two methods.",
  "Shrout & Fleiss (1979) Psychol Bull 86:420; Koo & Li (2016) J Chiropr Med 15:155.")

g("p_adjust",
  "Adjusts a list of P values for multiple comparisons: Bonferroni, Šídák, Holm, Holm-Šídák, Hochberg, Hommel, Benjamini-Hochberg, Benjamini-Yekutieli, two-stage BKY and Storey q-values.",
  "P values from separate experiments, genes, outcomes or tests that you want to correct together.",
  "Column table: one P value per row (row labels = names).",
  "Nothing to set (Storey λ is optional).",
  "Family-wise methods (Holm, Hochberg, Hommel) control the chance of any false positive; FDR methods (BH, BKY, q) control the expected fraction of false discoveries — better for screening.",
  "Hochberg, Hommel and BH assume independent or positively dependent tests; Holm, Bonferroni and BY hold under any dependence.",
  "—",
  "Benjamini & Hochberg (1995) JRSS B 57:289; Storey (2002) JRSS B 64:479.")

g("randomness",
  "Tests that a sequence of values is random: Wald-Wolfowitz runs test, Ljung-Box test of autocorrelation, von Neumann ratio, Durbin-Watson statistic, augmented Dickey-Fuller and KPSS stationarity tests, with an autocorrelation plot.",
  "Checking independence of repeated measurements, drift of an instrument, or residuals of a model ordered in time.",
  "Column table in measurement order, or XY table ordered by X.",
  "Optionally set the number of lags.",
  "Small P values in runs/Ljung-Box tests indicate dependence (trends, cycles, drift).",
  "Values in their true order.",
  "Mann-Kendall trend test; cosinor for rhythms.",
  "Ljung & Box (1978) Biometrika 65:297.")

g("circular",
  "Circular statistics for angles or times of day: mean direction with CI, mean resultant length, circular SD and variance, κ, circular median, Rayleigh test of uniformity, V test against an expected direction, and the Watson-Williams test comparing mean directions.",
  "Directions (orientation of cells, migration), times of day (onset of activity, time of birth), phases of a cycle — ordinary means are wrong for such data (the mean of 350° and 10° is 0°, not 180°).",
  "Column table, one group per column; values in degrees, hours (0–24), radians or another cycle length.",
  "Choose the unit; optionally enter an expected direction for the V test.",
  "Rayleigh P < α: values are concentrated around a mean direction. R̄ near 1 means tight clustering.",
  "Independent values; Watson-Williams assumes von Mises distributions with equal concentration.",
  "Cosinor analysis when values are measurements over time.",
  "Zar (2010) Biostatistical Analysis, ch. 26–27; Fisher (1993) Statistical Analysis of Circular Data.")

# ============================================================ counts and proportions
g("contingency",
  "Chi-square and Fisher's exact test of association in a contingency table, with odds ratio, relative risk, sensitivity/specificity and chi-square test for trend.",
  "Is the outcome distribution different between groups? (Counts, not percentages or means.)",
  "Contingency table: rows = groups, columns = outcomes, cells = counts.",
  "Yates' correction is optional (conservative).",
  "Use Fisher's exact test for 2 × 2 tables with small expected counts.",
  "Independent subjects, each counted once.",
  "More contingency tests (Barnard, McNemar for paired data, G test, trend, exact r × c).",
  "")

g("contingency_more",
  "Further contingency-table tests: G test (with Williams' correction), Fisher, Yates, Barnard and Boschloo exact tests, McNemar (paired 2 × 2; corrected and exact), Fisher-Freeman-Halton exact test for r × c (Monte Carlo, fixed seed), Bowker symmetry and Stuart-Maxwell marginal homogeneity (paired k × k), Cochran-Armitage trend, and association measures (Cramér's V, φ, contingency coefficient, Goodman-Kruskal γ, Kendall τ-b, Somers' d).",
  "Small samples (exact tests), paired categorical data (McNemar/Bowker), ordered rows (trend), measuring association strength.",
  "Contingency table. For McNemar/Bowker: rows = result of test/rater 1, columns = result of test/rater 2, one subject per count.",
  "Nothing to set.",
  "Barnard/Boschloo are more powerful than Fisher's test for 2 × 2 tables. McNemar uses only discordant pairs.",
  "Independent subjects (pairs for McNemar).",
  "Logistic regression; Cochran-Mantel-Haenszel for stratified tables.",
  "Agresti (2013) Categorical Data Analysis, 3rd ed.")

g("risk",
  "Risk measures for a 2 × 2 table: risks with Wilson CIs, risk difference (Newcombe CI), number needed to treat/harm, relative risk (Katz), relative risk reduction, odds ratio (Woolf and exact conditional MLE), attributable fraction, Fisher and z tests.",
  "Clinical trials and cohort studies: how much does the treatment/exposure change the risk?",
  "Contingency table: first row = treated/exposed, second = control; first column = event, second = no event.",
  "Nothing to set.",
  "Report absolute (risk difference, NNT) as well as relative measures (RR, OR).",
  "Independent subjects; cohort or trial design for risks (case-control studies: only the OR is meaningful).",
  "Cochran-Mantel-Haenszel for stratified data; logistic regression for adjustment.",
  "Newcombe (1998) Stat Med 17:873.")

g("diagnostic",
  "Diagnostic test accuracy: sensitivity, specificity, predictive values, accuracy, prevalence, likelihood ratios, diagnostic odds ratio and Youden's J with CIs; predictive values at any prevalence.",
  "Evaluating a test against a reference standard.",
  "Contingency table: rows = test positive / negative, columns = disease present / absent.",
  "Choose the CI method and optionally the prevalence in your target population.",
  "Predictive values depend on prevalence: use the prevalence-specific values for your population. LR+ > 10 or LR− < 0.1 change probabilities substantially.",
  "Independent subjects; a correct reference standard.",
  "ROC curve for continuous markers.",
  "Simel, Samsa & Matchar (1991) J Clin Epidemiol 44:763.")

g("kappa",
  "Cohen's kappa for agreement between two raters on categories: unweighted, linear- and quadratic-weighted κ with SEs and CIs, observed and chance agreement, maximum κ and PABAK.",
  "Agreement of two raters, two diagnostic readings or two classifications.",
  "Contingency table: rows = rater 1, columns = rater 2, same categories in the same order.",
  "Nothing to set.",
  "Use weighted κ for ordered categories. Interpret together with the marginal distributions (kappa paradoxes).",
  "Independent subjects.",
  "ICC for continuous ratings; Fleiss' κ for more than two raters (reliability analysis).",
  "Cohen (1960) Educ Psychol Meas 20:37; Fleiss, Levin & Paik (2003) Statistical Methods for Rates and Proportions.")

g("proportion",
  "Proportions with Wilson, Clopper-Pearson, Jeffreys, Agresti-Coull and Wald confidence intervals, and an exact binomial test against a hypothetical proportion.",
  "Reporting a percentage with its uncertainty (e.g. 12 of 40 responded).",
  "Contingency table: one row per group, successes in the first column, failures in the second.",
  "Enter the hypothetical proportion for the test.",
  "Report the Wilson or Jeffreys interval; Clopper-Pearson guarantees coverage but is conservative; never rely on Wald for small n.",
  "Independent trials with the same probability.",
  "Risk measures to compare two proportions.",
  "Brown, Cai & DasGupta (2001) Stat Sci 16:101.")

g("cmh",
  "Cochran-Mantel-Haenszel analysis of stratified 2 × 2 tables: common (Mantel-Haenszel) odds ratio and risk ratio with CI, CMH test, Breslow-Day-Tarone test of homogeneity.",
  "Combining 2 × 2 tables from several centres, batches or strata while controlling for the stratifying variable.",
  "Contingency table with rows in pairs: (exposed, unexposed) for stratum 1, then stratum 2, …; two outcome columns.",
  "Optionally use the continuity correction.",
  "If the Breslow-Day test is significant, the odds ratio differs between strata and the pooled OR may mislead.",
  "Independent subjects; a common OR across strata.",
  "Logistic regression with stratum as a factor; meta-analysis of the strata.",
  "Mantel & Haenszel (1959) JNCI 22:719.")

g("parts",
  "Fraction of total for each category, optionally with a chi-square goodness-of-fit test.",
  "Describing composition (pie or stacked bar charts).",
  "Parts-of-whole table.",
  "Tick the chi-square test to compare with equal proportions.",
  "Fractions and percentages of the total.",
  "Counts for the chi-square test.",
  "",
  "")

# ============================================================ survival
g("survival",
  "Kaplan-Meier survival curves with log-log CIs, median survival, log-rank and Gehan-Breslow-Wilcoxon tests, hazard ratio, pairwise comparisons and number at risk.",
  "Time until an event when some subjects are censored (lost or event-free at the end).",
  "Survival table: X = time; each group column contains 1 (event) or 0 (censored) on the rows of its subjects.",
  "Choose the confidence level.",
  "Report median survival with CI and the hazard ratio; the log-rank test weights all times equally.",
  "Censoring unrelated to prognosis; proportional hazards for the log-rank test to be optimal.",
  "Weighted log-rank tests and RMST (survival extras) when hazards are not proportional; Cox regression for covariates.",
  "Kaplan & Meier (1958) JASA 53:457.")

g("competing_risks",
  "Cumulative incidence of an event when other events can prevent it (Aalen-Johansen estimator), e.g. relapse when patients may also die without relapse; also the incidence of the competing event and, for comparison, the naive 1 − Kaplan-Meier that treats competing events as censored. With two or more groups, Gray's test compares the whole cumulative incidence curves (one test for the event of interest and one for each competing event).",
  "Whenever subjects can experience a different event that precludes the one of interest — the usual Kaplan-Meier curve then overestimates the probability of the event.",
  "Survival table: X = time; each group column holds 1 (event of interest), 2 (competing event) or 0 (censored).",
  "Optionally enter a time at which to report the cumulative incidence.",
  "The cumulative incidence at time t is the probability of having had the event of interest by t in the presence of the competing risk. It is always ≤ 1 − KM.",
  "Independent censoring; competing events are observed and coded.",
  "Fine-Gray regression for covariates (Multiple variables table); cause-specific Cox regression (competing events coded as censored) for effects on the cause-specific hazard.",
  "Putter, Fiocco & Geskus (2007) Stat Med 26:2389; Gray (1988) Ann Stat 16:1141; validated against cmprsk::cuminc.")

g("fine_gray",
  "Fine-Gray proportional subdistribution hazards regression: the effect of covariates on the cumulative incidence of an event in the presence of competing events. Reports subdistribution hazard ratios (SHR) with robust (sandwich) standard errors that account for the estimated censoring distribution, Wald tests and a forest plot.",
  "Prognostic factors for an event when subjects can also experience a competing event (e.g. relapse with death as a competing risk), when the question is about the actual probability (incidence) of the event.",
  "Multiple-variables table: a time column, an event-code column (0 = censored, 1 = event of interest, 2 or more = competing event) and the covariates (code groups as 0/1 dummy columns).",
  "Choose time, event code, the code of the event of interest and the covariates.",
  "SHR > 1: the covariate increases the cumulative incidence of the event of interest. SHRs are not cause-specific hazard ratios: a covariate can raise the incidence of the event simply by lowering the rate of the competing event.",
  "Proportional subdistribution hazards; censoring independent of covariates (the weights use one Kaplan-Meier estimate of the censoring distribution).",
  "Cox regression with competing events coded as censored (cause-specific hazards) to study the event rate itself; report both for a complete picture.",
  "Fine & Gray (1999) JASA 94:496; validated against cmprsk::crr.")

g("survival_more",
  "More survival analysis: weighted log-rank family (Gehan-Breslow-Wilcoxon, Tarone-Ware, Peto-Peto, Fleming-Harrington G(ρ,γ)), log-rank test for trend, restricted mean survival time (RMST) with difference and ratio, survival quantiles with CIs, and the Nelson-Aalen cumulative hazard.",
  "Curves that cross or separate late (non-proportional hazards); ordered groups; an interpretable effect measure (RMST = mean event-free time up to τ).",
  "Survival table.",
  "Optionally set the RMST horizon τ (default: the shortest group follow-up).",
  "Choose the weighting before looking at the data: G(1,0)/Peto for early differences, G(0,1) for late (delayed) effects.",
  "Independent censoring.",
  "Cox regression for covariates.",
  "Royston & Parmar (2013) BMC Med Res Methodol 13:152; Fleming & Harrington (1991).")

# ============================================================ data processing
for k, w in [("transform", "Applies a transformation (log, square root, reciprocal, logit, z score, …) to Y and/or X and writes a new table."),
             ("normalize", "Normalizes each data set to 0–100% (or fractions) using minima/maxima, first/last values or given values."),
             ("baseline", "Subtracts a baseline (first row or first data set) and writes a new table."),
             ("transpose", "Swaps rows and columns of a table.")]:
    g(k, w, "Preparing data for graphs or analyses (e.g. log-transform skewed data, normalize dose-response curves).",
      "Any XY, column, grouped or multiple-variables table.", "Choose the operation. The output table is linked and updates automatically.",
      "Analyze or graph the new table.", "—", "—", "")

g("power",
  "Sample size and power for t tests, ANOVA, two proportions, correlation, the Mann-Whitney test (Noether), survival / log-rank (Schoenfeld: events and subjects), paired proportions (McNemar, Connor) and one proportion, with power curves.",
  "Planning an experiment: how many subjects are needed to detect an effect of a given size?",
  "No table needed (Tools → Sample size & power).",
  "Enter the effect you want to detect, the variability and α; leave either n or power blank.",
  "Plan for 80–90% power; inflate n for expected dropouts.",
  "Those of the planned test.",
  "",
  "Cohen (1988) Statistical Power Analysis for the Behavioral Sciences.")


# ============================================================ choosing a test
CHOOSER = [
    ("Describe one group", "Descriptive statistics", "Normality test, frequency distribution", "column"),
    ("Compare one group with a hypothetical value", "One-sample t test", "Wilcoxon signed-rank / sign test", "column"),
    ("Compare groups when only mean, SD and n are known", "t test / ANOVA from summary data", "—", "summary"),
    ("Compare two independent groups", "Unpaired t test (Welch)", "Mann-Whitney; Yuen trimmed means; Brunner-Munzel", "column"),
    ("Compare two paired / matched groups", "Paired t test", "Wilcoxon matched-pairs; sign test", "column"),
    ("Compare three or more independent groups", "One-way ANOVA (Welch if SDs differ) + Tukey / Dunnett / Games-Howell", "Kruskal-Wallis + Dunn / Conover; trimmed-means ANOVA", "column"),
    ("Compare three or more matched groups", "Repeated-measures ANOVA (mixed model if values are missing)", "Friedman / Quade + Nemenyi or Wilcoxon-Holm", "column"),
    ("Groups in a natural order (doses, grades)", "Post test for linear trend", "Jonckheere-Terpstra; Page's L (matched)", "column"),
    ("Two factors", "Two-way ANOVA (repeated measures: mixed model)", "Aligned-rank-transform ANOVA", "grouped"),
    ("Three or more factors / adjust for a covariate", "n-way ANOVA / ANCOVA", "GLM", "multi"),
    ("Measurements nested in subjects", "Nested t test / ANOVA", "Average per subject, then t test / ANOVA", "nested"),
    ("Repeated measurements over time per subject (growth, dose per animal)", "Linear mixed-effects model (random intercepts and slopes)", "Repeated-measures ANOVA", "multi"),
    ("Compare variances", "Brown-Forsythe / Levene", "Fligner-Killeen", "column"),
    ("Compare whole distributions", "Kolmogorov-Smirnov / Anderson-Darling", "Cramér-von Mises", "column"),
    ("Show that two groups are equivalent", "Equivalence test (TOST)", "Bayesian t test", "column"),
    ("Association between two continuous variables", "Pearson correlation", "Spearman / Kendall correlation", "xy"),
    ("Association controlling for other variables", "Partial correlation", "Multiple regression", "multi"),
    ("Straight-line relationship / standard curve", "Linear regression", "Theil-Sen, Huber or quantile regression", "xy"),
    ("Curved relationship with a model", "Nonlinear regression (119 equations)", "ROUT robust fit", "xy"),
    ("Empirical curved relationship", "Polynomial regression (exact)", "LOWESS smoothing", "xy"),
    ("Rhythm with a known period", "Cosinor analysis", "Circular statistics (event times)", "xy"),
    ("Trend over time", "Linear regression on time", "Mann-Kendall + Sen's slope", "xy"),
    ("Agreement of two methods", "Bland-Altman", "Deming / Passing-Bablok regression; Lin's CCC", "column"),
    ("Reliability of raters / items", "ICC; Cronbach's α", "Kendall's W; Fleiss' κ", "column"),
    ("Predict a continuous outcome from several variables", "Multiple linear regression + diagnostics", "Robust regression", "multi"),
    ("Predict a binary outcome", "Logistic regression", "GLM (probit, cloglog)", "multi"),
    ("Predict counts / skewed positive values", "GLM: Poisson, negative binomial, gamma", "—", "multi"),
    ("Predict an ordered category", "Ordinal (proportional-odds) regression", "—", "multi"),
    ("Several outcomes at once", "MANOVA", "Separate ANOVAs with correction", "multi"),
    ("Group similar observations / reduce dimensions", "Cluster analysis; PCA", "—", "multi"),
    ("Combine several studies", "Meta-analysis (random effects, REML + Hartung-Knapp)", "Fixed-effect model", "multi"),
    ("Compare proportions between groups (counts)", "Fisher's exact / chi-square", "Barnard / Boschloo exact; G test", "contingency"),
    ("Paired categorical data", "McNemar (2 × 2) / Bowker (k × k)", "Cochran's Q (several conditions, 0/1)", "contingency"),
    ("Stratified 2 × 2 tables", "Cochran-Mantel-Haenszel", "Logistic regression", "contingency"),
    ("Effect size of a treatment on risk", "Risk difference, NNT, relative risk, odds ratio", "—", "contingency"),
    ("Accuracy of a diagnostic test", "Diagnostic accuracy (sens., spec., LR)", "ROC curve (continuous marker)", "contingency"),
    ("Agreement of two raters on categories", "Cohen's κ (weighted for ordered categories)", "—", "contingency"),
    ("A proportion with its CI", "Wilson / Jeffreys interval", "Clopper-Pearson (exact)", "contingency"),
    ("Survival time with censoring", "Kaplan-Meier + log-rank", "Weighted log-rank; RMST", "survival"),
    ("Survival with covariates", "Cox regression", "—", "multi"),
    ("Survival when another event can prevent the event of interest", "Competing risks: cumulative incidence + Gray's test", "Cause-specific Cox regression", "survival"),
    ("Competing risks with covariates", "Fine-Gray regression", "Cause-specific Cox regression", "multi"),
    ("Directions or times of day", "Circular statistics (Rayleigh, Watson-Williams)", "—", "column"),
    ("Many P values", "Holm (family-wise) or Benjamini-Hochberg (FDR)", "Hommel, BY, Storey q", "column"),
    ("Is a sequence random / independent?", "Runs test, Ljung-Box", "Durbin-Watson, ADF/KPSS", "column"),
    ("Plan the sample size", "Power calculator", "—", "—"),
]


def as_dict():
    return {"analyses": G, "chooser": CHOOSER}
