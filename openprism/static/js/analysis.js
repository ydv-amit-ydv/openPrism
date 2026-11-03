// Analysis dialogs (parameter forms), running analyses and rendering results.
import { P, TABLE_TYPES, commit, emit, getTable, normalizeTable, tableForServer, uid, uniqueName } from './state.js';
import { HELP, helpIcon } from './help.js';
import { recommend } from './learn.js';
import { api, download, h, modal, toast } from './ui.js';

export let CATALOG = { analyses: [], models: [] };
export async function loadCatalog() { CATALOG = await api('/api/catalog'); }

const MC = [['tukey', 'Tukey (compare every mean with every other mean)'], ['holm-sidak', 'Holm-Šídák'], ['sidak', 'Šídák'],
  ['bonferroni', 'Bonferroni'], ['dunnett', 'Dunnett (compare each mean with control)'], ['fisher', "Fisher's LSD (no correction)"],
  ['bh', 'Benjamini-Hochberg FDR'], ['bky', 'Two-stage step-up FDR (BKY)'], ['holm', 'Holm'], ['games-howell', 'Games-Howell (unequal SDs)'], ['t3', 'Dunnett T3 (unequal SDs)'], ['t2', 'Tamhane T2 (unequal SDs)'],
  ['none', 'No multiple comparisons']];
const ALPHA = { key: 'alpha', label: 'Significance level (alpha)', type: 'select', options: [['0.05', '0.05'], ['0.01', '0.01'], ['0.1', '0.10'], ['0.001', '0.001']], def: '0.05', help: 'alpha' };

// Parameter forms for each analysis
export const FORMS = {
  descriptive: [{ key: 'ci', label: 'Confidence level', type: 'select', options: [['0.95', '95%'], ['0.99', '99%'], ['0.9', '90%']], def: '0.95' }],
  normality: [
    { key: 'tests', label: 'Tests', type: 'multi', options: [['shapiro', 'Shapiro-Wilk'], ['dagostino', "D'Agostino-Pearson omnibus"], ['ks', 'Kolmogorov-Smirnov (Lilliefors)'], ['anderson', 'Anderson-Darling']], def: ['shapiro', 'dagostino', 'ks', 'anderson'] },
    { key: 'lognormal', label: 'Also test for lognormal distribution', type: 'check', def: false }, ALPHA],
  one_sample: [
    { key: 'test', label: 'Test', type: 'select', options: [['t', 'One sample t test'], ['wilcoxon', 'Wilcoxon signed-rank test']], def: 't' },
    { key: 'mu', label: 'Hypothetical value', type: 'number', def: 0 }, ALPHA],
  ttest: [
    { key: 'paired', help: 'paired', label: 'Experimental design', type: 'select', options: [['false', 'Unpaired'], ['true', 'Paired']], def: 'false', bool: true },
    { key: 'parametric', help: 'parametric', label: 'Assume Gaussian distribution?', type: 'select', options: [['true', 'Yes — use parametric test'], ['false', 'No — use nonparametric test']], def: 'true', bool: true },
    { key: 'welch', label: "Welch's correction (do not assume equal SDs)", type: 'check', def: false, show: (p) => p.paired !== 'true' && p.parametric !== 'false' },
    { key: 'alternative', label: 'P value', type: 'select', options: [['two-sided', 'Two-tailed'], ['greater', 'One-tailed (B > A)'], ['less', 'One-tailed (B < A)']], def: 'two-sided' }, ALPHA],
  one_way: [
    { key: 'repeated', label: 'Experimental design', type: 'select', options: [['false', 'No matching or pairing'], ['true', 'Each row represents matched (repeated measures) data']], def: 'false', bool: true },
    { key: 'parametric', help: 'parametric', label: 'Assume Gaussian distribution?', type: 'select', options: [['true', 'Yes — ANOVA'], ['false', 'No — nonparametric (Kruskal-Wallis / Friedman)']], def: 'true', bool: true },
    { key: 'mixed', help: 'mixed-models', label: 'Fit a mixed-effects model (keeps subjects with missing values)', type: 'check', def: false, show: (p) => p.repeated === 'true' && p.parametric !== 'false' },
    { key: 'geisser', help: 'geisser', label: 'Geisser-Greenhouse correction (no sphericity)', type: 'check', def: true, show: (p) => p.repeated === 'true' && p.parametric !== 'false' },
    { key: 'welch', label: "Also report Welch's ANOVA (unequal SDs)", type: 'check', def: false, show: (p) => p.repeated !== 'true' && p.parametric !== 'false' },
    { key: 'comparison', label: 'Multiple comparisons', type: 'select', options: MC, def: 'tukey', help: 'multiple-comparisons' },
    { key: 'control', label: 'Control group', type: 'dataset', def: 0, show: (p) => p.comparison === 'dunnett' }, ALPHA],
  outliers: [
    { key: 'method', label: 'Method', type: 'select', options: [['grubbs', "Grubbs' test (iterative)"], ['rout', 'ROUT-like robust (median/MAD, FDR Q)'], ['iqr', 'Tukey fences (IQR)']], def: 'grubbs' },
    { key: 'alpha', label: 'Alpha (Grubbs)', type: 'number', def: 0.05, show: (p) => p.method === 'grubbs' },
    { key: 'q', label: 'Q (ROUT) %', type: 'number', def: 0.01, show: (p) => p.method === 'rout' },
    { key: 'k', label: 'IQR multiplier', type: 'number', def: 1.5, show: (p) => p.method === 'iqr' }],
  frequency: [
    { key: 'binWidth', label: 'Bin width (blank = automatic)', type: 'text', def: '' },
    { key: 'binStart', label: 'First bin starts at (blank = auto)', type: 'text', def: '' },
    { key: 'mode', label: 'Tabulate', type: 'select', options: [['count', 'Number of values'], ['percent', 'Relative frequency (%)'], ['fraction', 'Relative frequency (fraction)']], def: 'count' },
    { key: 'cumulative', label: 'Cumulative', type: 'check', def: false }],
  roc: [{ key: 'direction', label: 'Patients have values that are', type: 'select', options: [['higher', 'Higher than controls'], ['lower', 'Lower than controls']], def: 'higher' }],
  two_way: [
    { key: 'comparison', label: 'Multiple comparisons (within each row)', type: 'select', options: MC.filter(([k]) => !['dunnett', 'games-howell', 't2', 't3'].includes(k)), def: 'sidak' },
    { key: 'compareWithin', label: 'Compare', type: 'select', options: [['rows', 'Columns within each row'], ['cols', 'Rows within each column']], def: 'rows' },
    { key: 'interaction', label: 'Fit interaction term (needs replicates)', type: 'check', def: true }, ALPHA],
  multiple_t: [
    { key: 'correction', label: 'Correction for multiple comparisons', type: 'select', options: [['holm-sidak', 'Holm-Šídák'], ['bonferroni', 'Bonferroni'], ['bh', 'False discovery rate (BH)'], ['none', 'None']], def: 'holm-sidak' },
    { key: 'welch', label: "Welch's correction", type: 'check', def: false }, ALPHA],
  nonlinear: [
    { key: 'model', label: 'Equation', type: 'model', def: 'logagonist4', help: 'nonlinear' },
    { key: 'equation', label: 'Your equation', type: 'equation', def: 'Y = Bottom + (Top - Bottom)*X^h/(K^h + X^h)', show: (p) => p.model === 'custom', help: 'custom-equation' },
    { key: 'initial', label: 'Initial values (e.g. Top=100, K=1)', type: 'text', def: '', show: (p) => p.model === 'custom', help: 'custom-equation' },
    { key: 'constraints', label: 'Constrain parameters (constant value)', type: 'constraints', def: {}, help: 'constraints' },
    { key: 'shared', label: 'Global fit: share parameters across data sets', type: 'shared', def: [], help: 'global-fit' },
    { key: 'weights', label: 'Weighting', type: 'select', options: [['none', 'No weighting (least squares)'], ['1/Y^2', 'Relative weighting (1/Y²)'], ['1/Y', 'Poisson weighting (1/Y)']], def: 'none', help: 'weighting' },
    { key: 'fitMeans', label: 'Fit only the mean Y of replicates', type: 'check', def: false },
    { key: 'compareModel', label: 'Compare with alternative model (F test / AICc)', type: 'model', allowNone: true, def: '', help: 'compare-models', show: (p) => p.model !== 'custom' },
    { key: 'interpolate', label: 'Interpolate X from these Y values (comma separated)', type: 'text', def: '', help: 'interpolate' },
    { key: 'ci', label: 'Confidence level', type: 'select', options: [['0.95', '95%'], ['0.99', '99%'], ['0.9', '90%']], def: '0.95' },
    { key: 'profile', label: 'Also compute profile-likelihood confidence intervals', type: 'check', def: false, help: 'profile-ci' },
    { key: 'plotBand', label: 'Plot confidence band', type: 'check', def: false },
    { key: 'residualTable', label: 'Create table of residuals', type: 'check', def: false },
    { key: 'rout', label: 'Robust fit & remove outliers (ROUT)', type: 'check', def: false, help: 'rout' },
    { key: 'routQ', label: 'ROUT Q (%)', type: 'number', def: 1, show: (p) => !!p.rout }],
  linear: [
    { key: 'throughOrigin', label: 'Force line through origin (X=0, Y=0)', type: 'check', def: false },
    { key: 'fitMeans', label: 'Fit only the mean Y of replicates', type: 'check', def: false },
    { key: 'ci', label: 'Confidence level', type: 'select', options: [['0.95', '95%'], ['0.99', '99%']], def: '0.95' },
    { key: 'plotBand', label: 'Plot confidence bands', type: 'check', def: false }],
  correlation: [
    { key: 'method', label: 'Correlation coefficient', type: 'select', options: [['pearson', 'Pearson (assume Gaussian)'], ['spearman', 'Spearman (nonparametric)']], def: 'pearson' },
    { key: 'matrix', label: 'Compute full correlation matrix of all Y columns', type: 'check', def: false }, ALPHA],
  auc: [{ key: 'baseline', label: 'Baseline Y value', type: 'number', def: 0 }],
  contingency: [{ key: 'yates', label: "Yates' continuity correction (2×2)", type: 'check', def: false }, ALPHA],
  survival: [{ key: 'ci', label: 'Confidence level', type: 'select', options: [['0.95', '95%'], ['0.99', '99%']], def: '0.95' }, ALPHA],
  parts: [{ key: 'chiSquare', label: 'Chi-square goodness of fit vs. equal proportions', type: 'check', def: false }],
  transform: [
    { key: 'function', label: 'Y transform', type: 'select', options: [['log10', 'Y = log10(Y)'], ['ln', 'Y = ln(Y)'], ['pow10', 'Y = 10^Y'], ['exp', 'Y = e^Y'], ['sqrt', 'Y = √Y'], ['square', 'Y = Y²'], ['reciprocal', 'Y = 1/Y'], ['abs', 'Y = |Y|'], ['times', 'Y = Y × K'], ['plus', 'Y = Y + K'], ['logit', 'Y = logit(Y)'], ['zscore', 'Z score (per data set)']], def: 'log10' },
    { key: 'xFunction', label: 'X transform', type: 'select', options: [['none', 'None'], ['log10', 'X = log10(X)'], ['ln', 'X = ln(X)'], ['reciprocal', 'X = 1/X'], ['times', 'X = X × K']], def: 'none' },
    { key: 'k', label: 'K', type: 'number', def: 1 }],
  normalize: [
    { key: 'zero', label: 'Define 0% as', type: 'select', options: [['min', 'Smallest mean in each data set'], ['first', 'First value in each data set'], ['value', 'A value']], def: 'min' },
    { key: 'zeroValue', label: '0% value', type: 'number', def: 0, show: (p) => p.zero === 'value' },
    { key: 'hundred', label: 'Define 100% as', type: 'select', options: [['max', 'Largest mean in each data set'], ['last', 'Last value in each data set'], ['value', 'A value']], def: 'max' },
    { key: 'hundredValue', label: '100% value', type: 'number', def: 100, show: (p) => p.hundred === 'value' },
    { key: 'result', label: 'Present results as', type: 'select', options: [['percent', 'Percentages'], ['fraction', 'Fractions']], def: 'percent' }],
  baseline: [{ key: 'baseline', label: 'Baseline', type: 'select', options: [['first', 'First row of each data set'], ['firstcol', 'First data set (column A)']], def: 'first' }],
  transpose: [],
  bland_altman: [{ key: 'difference', label: 'Plot', type: 'select', options: [['diff', 'Difference (A − B) vs. average'], ['ratio', 'Ratio (A / B) vs. average'], ['percent', '% difference vs. average']], def: 'diff' }],
  smooth: [
    { key: 'operation', label: 'Operation', type: 'select', options: [['lowess', 'LOWESS smoothing'], ['moving', 'Moving average'], ['derivative', 'Derivative (dY/dX)'], ['integral', 'Cumulative integral']], def: 'lowess' },
    { key: 'frac', label: 'LOWESS span (fraction of points, 0.1-1)', type: 'number', def: 0.4, show: (p) => p.operation === 'lowess' },
    { key: 'window', label: 'Window (points)', type: 'number', def: 3, show: (p) => p.operation === 'moving' }],
  multiple_regression: [
    { key: 'dependent', label: 'Dependent variable (Y)', type: 'dataset', def: 0 },
    { key: 'predictors', label: 'Independent variables (X)', type: 'variables', def: [] }, ALPHA],
  logistic: [
    { key: 'dependent', label: 'Outcome variable (0/1)', type: 'dataset', def: 0 },
    { key: 'predictors', label: 'Independent variables (X)', type: 'variables', def: [] },
    { key: 'cutoff', label: 'Classification cutoff', type: 'number', def: 0.5 }, ALPHA],
  cox: [
    { key: 'timeVar', label: 'Time variable', type: 'dataset', def: 0 },
    { key: 'eventVar', label: 'Event variable (1 = event, 0 = censored)', type: 'dataset', def: 1 },
    { key: 'predictors', label: 'Covariates', type: 'variables', def: [] }, ALPHA],
  fine_gray: [
    { key: 'timeVar', label: 'Time variable', type: 'dataset', def: 0 },
    { key: 'eventVar', label: 'Event code (0 = censored, 1 = event of interest, 2 = competing)', type: 'dataset', def: 1 },
    { key: 'cause', label: 'Event of interest (code)', type: 'number', def: 1 },
    { key: 'predictors', label: 'Covariates', type: 'variables', def: [] }, ALPHA],
  mixed_one_way: [{ key: 'comparison', label: 'Multiple comparisons', type: 'select', options: MC.filter(([k]) => !['dunnett', 'games-howell', 't2', 't3'].includes(k)), def: 'tukey', help: 'multiple-comparisons' }, ALPHA],
  two_way_rm: [
    { key: 'rm', label: 'Repeated measures', type: 'select', help: 'mixed-models', options: [['rows', 'Across rows — each subcolumn is one subject measured at every row'], ['cols', 'Across data sets — replicate k of a row is the same subject in every data set'], ['both', 'Both factors — subcolumn k is the same subject everywhere']], def: 'rows' },
    { key: 'comparison', label: 'Multiple comparisons (within each row)', type: 'select', options: MC.filter(([k]) => !['dunnett', 'games-howell', 'tukey', 't2', 't3'].includes(k)), def: 'sidak' }, ALPHA],
  nested: [{ key: 'comparison', label: 'Multiple comparisons (3+ groups)', type: 'select', options: MC.filter(([k]) => !['dunnett', 'games-howell', 't2', 't3'].includes(k)), def: 'tukey' }, ALPHA],
  factorial: [
    { key: 'dependent', label: 'Dependent variable (Y)', type: 'dataset', def: 0 },
    { key: 'factors', label: 'Categorical factors (2-4 for two/three/four-way)', type: 'variables', emptyDefault: true, def: [] },
    { key: 'covariates', label: 'Continuous covariates (ANCOVA, optional)', type: 'variables', emptyDefault: true, def: [] },
    { key: 'interactions', label: 'Model', type: 'select', options: [['all', 'Main effects and all interactions'], ['main', 'Main effects only']], def: 'all' }, ALPHA],
  poisson: [
    { key: 'dependent', label: 'Count variable (Y)', type: 'dataset', def: 0 },
    { key: 'predictors', label: 'Independent variables (X)', type: 'variables', def: [] }],
  deming: [{ key: 'ratio', label: 'SD of Y error ÷ SD of X error', type: 'number', def: 1 }],
  passing_bablok: [],
  equivalence: [
    { key: 'lower', label: 'Lower equivalence margin', type: 'number', def: -1 },
    { key: 'upper', label: 'Upper equivalence margin', type: 'number', def: 1 }, ALPHA],
  bayes_t: [
    { key: 'paired', label: 'Experimental design', type: 'select', options: [['false', 'Unpaired'], ['true', 'Paired']], def: 'false' },
    { key: 'rscale', label: 'Prior scale r (0.707 = medium)', type: 'number', def: 0.707 }],
  bootstrap: [
    { key: 'statistic', label: 'Statistic', type: 'select', options: [['mean', 'Mean'], ['median', 'Median'], ['sd', 'Standard deviation']], def: 'mean' },
    { key: 'resamples', label: 'Resamples (200-20 000)', type: 'number', def: 5000 },
    { key: 'ci', label: 'Confidence level', type: 'select', options: [['0.95', '95%'], ['0.99', '99%'], ['0.9', '90%']], def: '0.95' }],
  permutation: [{ key: 'statistic', label: 'Statistic', type: 'select', options: [['mean', 'Difference of means'], ['median', 'Difference of medians']], def: 'mean' }],
  pca: [{ key: 'scale', label: 'Variables', type: 'select', options: [['standardize', 'Standardize (correlation matrix) — recommended'], ['center', 'Center only (covariance matrix)']], def: 'standardize' }],
};
const CI = (def = '0.95') => ({ key: 'ci', label: 'Confidence level', type: 'select', options: [['0.95', '95%'], ['0.99', '99%'], ['0.9', '90%']], def });
const ADJ = [['holm', 'Holm'], ['bonferroni', 'Bonferroni'], ['bh', 'Benjamini-Hochberg FDR'], ['hochberg', 'Hochberg'], ['none', 'None']];
const DEP = (label = 'Dependent variable (Y)') => ({ key: 'dependent', label, type: 'dataset', def: 0 });
const PRED = { key: 'predictors', label: 'Independent variables (X)', type: 'variables', def: [] };
Object.assign(FORMS, {
  variance_tests: [ALPHA],
  distribution_tests: [ALPHA],
  robust_compare: [{ key: 'trim', label: 'Trimming per tail (0.2 = 20% trimmed mean)', type: 'select', options: [['0.2', '20% (recommended)'], ['0.1', '10%'], ['0.25', '25%'], ['0', '0% (Welch on means)']], def: '0.2' }, ALPHA],
  trend_tests: [
    { key: 'repeated', label: 'Rows are matched subjects (also run Page’s L test)', type: 'check', def: false },
    { key: 'permutations', label: 'Permutations for exact Jonckheere-Terpstra P (0 = none)', type: 'number', def: 9999 }, ALPHA],
  np_posthoc: [
    { key: 'method', label: 'Post hoc test', type: 'select', options: [['dunn', "Dunn's test (most common)"], ['conover', 'Conover-Iman (more powerful)'], ['dscf', 'Dwass-Steel-Critchlow-Fligner (pairwise ranking)'], ['mw', 'Pairwise Mann-Whitney']], def: 'dunn' },
    { key: 'adjust', label: 'Adjust P values', type: 'select', options: ADJ, def: 'holm', show: (p) => p.method !== 'dscf' }, ALPHA],
  rm_nonparametric: [ALPHA],
  effect_sizes: [ALPHA],
  one_sample_more: [
    { key: 'median', label: 'Hypothetical median (sign test)', type: 'number', def: 0 },
    { key: 'sd0', label: 'Hypothetical SD (chi-square test; blank = skip)', type: 'text', def: '' },
    { key: 'quantile', label: 'Percentile for its CI (0.5 = median)', type: 'number', def: 0.5 },
    { key: 'coverage', label: 'Tolerance interval: proportion of population covered', type: 'number', def: 0.95 },
    { key: 'confidence', label: 'Tolerance interval: confidence', type: 'number', def: 0.95 }, ALPHA],
  randomness: [{ key: 'lags', label: 'Ljung-Box lags (blank = automatic)', type: 'text', def: '' }, ALPHA],
  circular: [
    { key: 'unit', label: 'Values are', type: 'select', options: [['degrees', 'Angles in degrees (0-360)'], ['hours', 'Clock times in hours (0-24)'], ['radians', 'Angles in radians'], ['custom', 'Other cyclic unit']], def: 'degrees' },
    { key: 'period', label: 'Length of one cycle', type: 'number', def: 24, show: (p) => p.unit === 'custom' },
    { key: 'expected', label: 'Expected direction for the V test (blank = skip)', type: 'text', def: '' }, ALPHA],
  reliability: [ALPHA],
  p_adjust: [{ key: 'lambda', label: 'Storey λ (for π0)', type: 'number', def: 0.5 }, ALPHA],
  two_way_np: [ALPHA],
  polynomial: [
    { key: 'order', label: 'Order', type: 'select', options: [...Array(10)].map((_, i) => [String(i + 1), ['1 (straight line)', '2 (quadratic)', '3 (cubic)'][i] || String(i + 1)]), def: '2' },
    { key: 'plotBand', label: 'Plot confidence band', type: 'check', def: false }, ALPHA],
  robust_regression: [{ key: 'quantile', label: 'Quantile for quantile regression (0.5 = median)', type: 'number', def: 0.5 }, ALPHA],
  trend_mk: [ALPHA],
  cosinor: [
    { key: 'period', label: 'Period (in X units, e.g. 24 h)', type: 'number', def: 24 },
    { key: 'harmonics', label: 'Harmonics', type: 'select', options: [['1', '1 (single cosine)'], ['2', '2'], ['3', '3']], def: '1' }, ALPHA],
  contingency_more: [ALPHA],
  risk: [ALPHA],
  diagnostic: [
    { key: 'ciMethod', label: 'Confidence intervals', type: 'select', options: [['wilson', 'Wilson (recommended)'], ['clopper', 'Clopper-Pearson (exact)'], ['jeffreys', 'Jeffreys'], ['agresti', 'Agresti-Coull']], def: 'wilson' },
    { key: 'prevalence', label: 'Prevalence in your population (0-1, blank = skip)', type: 'text', def: '' }, ALPHA],
  kappa: [ALPHA],
  proportion: [{ key: 'p0', label: 'Hypothetical proportion (binomial test)', type: 'number', def: 0.5 }, ALPHA],
  cmh: [{ key: 'correction', label: 'Continuity correction', type: 'check', def: false }, ALPHA],
  survival_more: [{ key: 'tau', label: 'RMST time horizon τ (blank = shortest follow-up)', type: 'text', def: '' }, ALPHA],
  glm: [DEP(), PRED,
    { key: 'family', label: 'Distribution of Y', type: 'select', options: [['gaussian', 'Normal (Gaussian)'], ['binomial', 'Binomial (0/1 or proportions)'], ['poisson', 'Poisson (counts)'], ['negbin', 'Negative binomial (over-dispersed counts)'], ['gamma', 'Gamma (positive, right-skewed)'], ['invgauss', 'Inverse Gaussian']], def: 'gaussian' },
    { key: 'link', label: 'Link function', type: 'select', options: [['', 'Default (canonical)'], ['identity', 'Identity'], ['log', 'Log'], ['logit', 'Logit'], ['probit', 'Probit'], ['cloglog', 'Complementary log-log'], ['inverse_power', 'Inverse'], ['sqrt', 'Square root']], def: '' }, ALPHA],
  summary_describe: [{ key: 'ci', label: 'Confidence level', type: 'select', options: [['0.95', '95%'], ['0.99', '99%'], ['0.9', '90%']], def: '0.95' }],
  summary_ttest: [{ key: 'welch', label: "Welch's correction (do not assume equal SDs)", type: 'check', def: true }, ALPHA],
  summary_anova: [{ key: 'comparison', label: 'Multiple comparisons', type: 'select', options: MC.filter(([k]) => !['t2', 't3'].includes(k)), def: 'tukey', help: 'multiple-comparisons' },
    { key: 'control', label: 'Control group (row number, 0 = first)', type: 'number', def: 0, show: (p) => p.comparison === 'dunnett' }, ALPHA],
  mixed_model: [DEP('Outcome (Y)'), { key: 'group', label: 'Subject / cluster column (codes)', type: 'dataset', def: 1 },
    { key: 'fixed', label: 'Fixed effects', type: 'variables', emptyDefault: true, def: [] },
    { key: 'factors', label: '…of which categorical (factors)', type: 'variables', emptyDefault: true, def: [] },
    { key: 'randomSlope', label: 'Random slope for', type: 'dataset', allowNone: '(none — random intercept only)', def: '', help: 'mixed-models' },
    { key: 'method', label: 'Estimation', type: 'select', options: [['reml', 'REML (recommended for estimates)'], ['ml', 'Maximum likelihood (compare models, AIC)']], def: 'reml' },
    { key: 'ddf', label: 'P values', type: 'select', options: [['satterthwaite', 'Satterthwaite degrees of freedom (small samples; as lmerTest / SAS)'], ['z', 'Large-sample z tests']], def: 'satterthwaite' }, ALPHA],
  competing_risks: [{ key: 'horizon', label: 'Report cumulative incidence at time (optional)', type: 'text', def: '' }],
  ordinal: [DEP('Ordered outcome (category codes 1, 2, 3…)'), PRED,
    { key: 'distr', label: 'Link', type: 'select', options: [['logit', 'Logit (proportional odds)'], ['probit', 'Probit']], def: 'logit' }, ALPHA],
  regression_diagnostics: [DEP(), PRED, ALPHA],
  manova: [{ key: 'group', label: 'Grouping variable (group codes)', type: 'dataset', def: 0 },
    { key: 'dependents', label: 'Dependent variables', type: 'variables', def: [] }, ALPHA],
  partial_correlation: [{ key: 'method', label: 'Coefficient', type: 'select', options: [['pearson', 'Pearson'], ['spearman', 'Spearman (ranks)']], def: 'pearson' }, ALPHA],
  cluster: [
    { key: 'method', label: 'Method', type: 'select', options: [['ward', 'Hierarchical, Ward linkage (recommended)'], ['average', 'Hierarchical, average linkage'], ['complete', 'Hierarchical, complete linkage'], ['single', 'Hierarchical, single linkage'], ['kmeans', 'k-means']], def: 'ward' },
    { key: 'k', label: 'Number of clusters', type: 'number', def: 3 },
    { key: 'standardize', label: 'Standardize variables (recommended when units differ)', type: 'check', def: true }],
  meta: [
    { key: 'format', label: 'Columns contain (in this order)', type: 'select', options: [['es_se', 'Effect, standard error'], ['es_ci', 'Effect, lower CI, upper CI'], ['means', 'Mean₁, SD₁, n₁, Mean₂, SD₂, n₂'], ['counts', 'Events₁, Total₁, Events₂, Total₂']], def: 'es_se' },
    { key: 'measure', label: 'Effect measure', type: 'select', options: [['smd', "Standardized mean difference (Hedges' g)"], ['md', 'Mean difference']], def: 'smd', show: (p) => p.format === 'means' },
    { key: 'measure', label: 'Effect measure', type: 'select', options: [['or', 'Odds ratio'], ['rr', 'Risk ratio'], ['rd', 'Risk difference']], def: 'or', show: (p) => p.format === 'counts' },
    { key: 'logScale', label: 'Effects are ratios (OR, RR, HR): pool on the log scale', type: 'check', def: false, show: (p) => p.format === 'es_se' || p.format === 'es_ci' },
    { key: 'method', label: 'Model', type: 'select', options: [['reml', 'Random effects, REML (recommended)'], ['dl', 'Random effects, DerSimonian-Laird'], ['pm', 'Random effects, Paule-Mandel'], ['fixed', 'Fixed effect (common effect)']], def: 'reml' },
    { key: 'hartungKnapp', label: 'Hartung-Knapp adjustment (recommended for few studies)', type: 'check', def: false, show: (p) => p.method !== 'fixed' }, ALPHA],
});
FORMS.correlation[0].options.push(['kendall', 'Kendall τ-b (nonparametric, robust to ties)']);
FORMS.normality[0].options.push(['jb', 'Jarque-Bera'], ['sf', 'Shapiro-Francia']);
FORMS.outliers[0].options.push(['esd', 'Generalized ESD (Rosner, several outliers)'], ['hampel', 'Hampel filter (median ± t·MAD)']);
FORMS.outliers.push({ key: 'maxOutliers', label: 'Maximum number of outliers (blank = 10%)', type: 'text', def: '', show: (p) => p.method === 'esd' },
  { key: 't', label: 'Threshold (MADs)', type: 'number', def: 3, show: (p) => p.method === 'hampel' }, { key: 'alpha', label: 'Alpha', type: 'number', def: 0.05, show: (p) => p.method === 'esd' });
void CI;

// analyses whose result is mainly a plot get their own "Analysis plot" graph automatically
export const PLOT_ANALYSES = new Set(['normality', 'bland_altman', 'multiple_regression', 'logistic', 'cox', 'fine_gray', 'competing_risks', 'pca', 'meta', 'regression_diagnostics', 'cluster', 'randomness', 'survival_more']);

function defaults(key) {
  const p = {};
  for (const f of FORMS[key] || []) p[f.key] = Array.isArray(f.def) ? [...f.def] : (typeof f.def === 'object' ? { ...f.def } : f.def);
  return p;
}

/** Convert form values to the API types. */
export function toApiParams(key, p) {
  const out = {};
  for (const f of FORMS[key] || []) {
    let v = p[f.key];
    if (f.bool) v = v === 'true' || v === true;
    else if (f.type === 'number') v = v === '' || v === undefined ? undefined : Number(v);
    else if (f.type === 'dataset') v = f.allowNone && (v === '' || v === undefined || v === null) ? undefined : Number(v);
    else if (f.type === 'variables') v = (v || []).map(Number);
    if (v !== undefined) out[f.key] = v;
  }
  if (p.datasets) out.datasets = p.datasets;
  return out;
}

/** Show the "Analyze" dialog. Resolves with created analysis or null. */
export function analyzeDialog(table, preset, existing) {
  return new Promise((resolve) => {
    const avail = CATALOG.analyses;
    let key = preset || existing?.key || avail.find((a) => a.tableTypes.includes(table.type))?.key;
    let params = existing ? JSON.parse(JSON.stringify(existing.params)) : { ...defaults(key) };
    const pickDefault = () => (['ttest', 'roc', 'equivalence', 'bayes_t', 'permutation', 'bland_altman', 'effect_sizes'].includes(key) ? [0, 1] : table.datasets.map((_, i) => i)).filter((i) => i < table.datasets.length);
    if (!params.datasets) params.datasets = pickDefault();
    const left = h('div', { class: 'pick-list' });
    const right = h('div');
    const cats = [...new Set(avail.map((a) => a.category))];
    const pref = (k, d) => { try { const v = localStorage.getItem(`openprism.pref.${k}`); return v === null ? d : v === '1'; } catch (_) { return d; } };
    const setPref = (k, v) => { try { localStorage.setItem(`openprism.pref.${k}`, v ? '1' : '0'); } catch (_) { /* ignore */ } };
    let showAdvanced = pref('showAdvanced', false);
    let showOther = false;
    const recs = existing ? [] : recommend(table).filter((r) => avail.some((a) => a.key === r.key && a.tableTypes.includes(table.type)));
    const pick = (k) => { key = k; params = { ...defaults(key) }; params.datasets = pickDefault(); drawList(); drawForm(); };
    if (!preset && !existing && recs.length) { key = recs[0].key; params = { ...defaults(key) }; params.datasets = pickDefault(); }
    function drawList() {
      left.innerHTML = '';
      if (recs.length) {
        left.append(h('div', { class: 'cat rec' }, '⭐ Recommended for your data'));
        for (const r of recs) {
          const a = avail.find((x) => x.key === r.key);
          left.append(h('button', { class: `rec-item ${a.key === key ? 'on' : ''}`, title: a.plain?.question || '', onclick: () => pick(a.key) },
            h('span', {}, a.label.replace(/\s*\(.*\)\s*$/, '')), h('small', {}, r.why)));
        }
      }
      left.append(h('div', { class: 'pick-toggles' },
        h('label', {}, h('input', { type: 'checkbox', checked: showAdvanced, onchange: (e) => { showAdvanced = e.target.checked; setPref('showAdvanced', showAdvanced); drawList(); } }), 'Show advanced analyses'),
        h('label', {}, h('input', { type: 'checkbox', checked: showOther, onchange: (e) => { showOther = e.target.checked; drawList(); } }), 'Show analyses for other table types')));
      let hidden = 0;
      for (const c of cats) {
        const items = avail.filter((x) => x.category === c).filter((a) => {
          const ok = a.tableTypes.includes(table.type);
          const show = a.key === key || ((ok || showOther) && (showAdvanced || a.plain?.level !== 'advanced'));
          if (!show && ok) hidden++;
          return show;
        });
        if (!items.length) continue;
        left.append(h('div', { class: 'cat' }, c));
        for (const a of items) {
          const ok = a.tableTypes.includes(table.type);
          left.append(h('button', {
            class: a.key === key ? 'on' : '', disabled: !ok || (existing && a.key !== existing.key),
            title: ok ? (a.plain?.question || '') : `Needs a ${TABLE_TYPES[a.tableTypes[0]]?.label || ''} table — not available for ${TABLE_TYPES[table.type].label} tables`,
            onclick: () => pick(a.key),
          }, a.label));
        }
      }
      if (hidden && !showAdvanced) left.append(h('div', { class: 'hint pick-more' }, `${hidden} more advanced analyses fit this table — tick “Show advanced analyses”.`));
    }
    function drawForm() {
      right.innerHTML = '';
      const a = avail.find((x) => x.key === key);
      if (!a) return;
      right.append(h('h3', { style: { marginTop: 0, fontSize: '14px', display: 'flex', alignItems: 'center' } }, a.label, HELP[key] ? helpIcon(key) : null));
      right.append(h('div', { class: 'hint' }, `Analyze data table “${table.name}” (${TABLE_TYPES[table.type].label}).`));
      right.append(plainBox(a, table, params));
      if (a.guide) right.append(aboutPanel(a));
      const dsBox = h('div', { class: 'ds-checks' }, table.datasets.map((d, i) => h('label', {},
        h('input', { type: 'checkbox', checked: params.datasets.includes(i), onchange: (e) => {
          params.datasets = e.target.checked ? [...new Set([...params.datasets, i])].sort((x, y) => x - y) : params.datasets.filter((x) => x !== i);
          const pb = right.querySelector('.plain-box');
          if (pb) pb.replaceWith(plainBox(a, table, params));
        } }), `${String.fromCharCode(65 + (i % 26))}: ${d.name}`)));
      if (!['multiple_regression', 'logistic', 'cox', 'fine_gray', 'factorial', 'poisson', 'glm', 'ordinal', 'regression_diagnostics', 'manova', 'mixed_model', 'summary_describe', 'summary_ttest', 'summary_anova'].includes(key)) right.append(h('div', { class: 'field' }, h('label', {}, table.type === 'multi' ? 'Variables to analyze' : 'Data sets to analyze'), dsBox));
      for (const f of FORMS[key] || []) {
        if (f.show && !f.show(params)) continue;
        right.append(renderField(f));
      }
    }
    function renderField(f) {
      const out = renderField0(f);
      if (f.help && out.querySelector('label')) out.querySelector('label').append(helpIcon(f.help));
      return out;
    }
    function renderField0(f) {
      const set = (v) => { params[f.key] = v; drawForm(); };
      let input;
      const v = params[f.key];
      if (f.type === 'select') input = h('select', { onchange: (e) => set(e.target.value) }, f.options.map(([k, l]) => h('option', { value: k, selected: String(v) === String(k) }, l)));
      else if (f.type === 'number') input = h('input', { type: 'number', step: 'any', value: v ?? '', oninput: (e) => { params[f.key] = e.target.value; } });
      else if (f.type === 'text') input = h('input', { type: 'text', value: v ?? '', oninput: (e) => { params[f.key] = e.target.value; } });
      else if (f.type === 'check') return h('div', { class: 'field check' }, h('label', {}, h('input', { type: 'checkbox', checked: !!v, onchange: (e) => set(e.target.checked) }), f.label));
      else if (f.type === 'multi') input = h('div', { class: 'ds-checks' }, f.options.map(([k, l]) => h('label', {}, h('input', { type: 'checkbox', checked: (v || []).includes(k), onchange: (e) => { params[f.key] = e.target.checked ? [...(v || []), k] : (v || []).filter((x) => x !== k); } }), l)));
      else if (f.type === 'dataset') input = h('select', { onchange: (e) => set(e.target.value) }, f.allowNone ? h('option', { value: '', selected: v === '' || v === undefined }, f.allowNone) : null,
        table.datasets.map((d, i) => h('option', { value: i, selected: v !== '' && v !== undefined && +v === i }, d.name)));
      else if (f.type === 'variables') {
        const excl = ['dependent', 'timeVar', 'eventVar', 'group'].map((k2) => +params[k2]).filter((x) => !Number.isNaN(x));
        const cur = (v && v.length ? v : f.emptyDefault ? [] : table.datasets.map((_, i) => i).filter((i) => !excl.includes(i))).map(Number);
        params[f.key] = cur.filter((i) => !excl.includes(i));
        input = h('div', { class: 'ds-checks' }, table.datasets.map((d, i) => (excl.includes(i) ? null : h('label', {},
          h('input', { type: 'checkbox', checked: cur.includes(i), onchange: (e) => { params[f.key] = e.target.checked ? [...new Set([...params[f.key], i])] : params[f.key].filter((x) => x !== i); } }), d.name))));
      } else if (f.type === 'equation') {
        input = h('textarea', { class: 'eq-input', spellcheck: 'false', oninput: (e) => { params[f.key] = e.target.value; } });
        input.value = v ?? '';
      } else if (f.type === 'shared') {
        const m = CATALOG.models.find((x) => x.key === params.model);
        if (!m || params.model === 'custom') {
          input = h('input', { type: 'text', placeholder: 'parameter names, comma separated (blank = fit each data set separately)', value: Array.isArray(v) ? v.join(', ') : (v || ''), oninput: (e) => { params[f.key] = e.target.value.split(',').map((x) => x.trim()).filter(Boolean); } });
        } else {
          const cur = Array.isArray(v) ? v : [];
          input = h('div', { class: 'ds-checks' }, m.params.map((pn) => h('label', {}, h('input', { type: 'checkbox', checked: cur.includes(pn), onchange: (e) => { params[f.key] = e.target.checked ? [...new Set([...(params[f.key] || []), pn])] : (params[f.key] || []).filter((x) => x !== pn); } }), pn)));
        }
      }
      else if (f.type === 'model') {
        const groups = [...new Set(CATALOG.models.map((m) => m.group))];
        input = h('select', { onchange: (e) => set(e.target.value) },
          f.allowNone ? h('option', { value: '' }, '(none)') : null,
          groups.map((gname) => h('optgroup', { label: gname }, CATALOG.models.filter((m) => m.group === gname).map((m) => h('option', { value: m.key, selected: v === m.key }, m.name)))),
          f.allowNone ? null : h('optgroup', { label: 'User-defined' }, h('option', { value: 'custom', selected: v === 'custom' }, 'Write your own equation…')));
        if (!f.allowNone) {
          const m = CATALOG.models.find((x) => x.key === v);
          return h('div', {}, h('div', { class: 'field' }, h('label', {}, f.label), input), m ? h('div', { class: 'hint', style: { fontFamily: 'var(--mono)', marginLeft: '206px' } }, m.formula) : null);
        }
      } else if (f.type === 'constraints') {
        const m = CATALOG.models.find((x) => x.key === params.model);
        if (!m) {
          if (params.model !== 'custom') return h('div');
          input = h('input', { type: 'text', placeholder: 'e.g. Bottom=0, h=1', value: Object.entries(params.constraints || {}).map(([k2, x]) => `${k2}=${x}`).join(', '),
            oninput: (e) => { params.constraints = Object.fromEntries(e.target.value.split(',').map((x) => x.split('=').map((y) => y.trim())).filter((x) => x.length === 2 && x[0] && x[1] !== '')); } });
          return h('div', { class: 'field' }, h('label', {}, f.label), input);
        }
        params.constraints = Object.fromEntries(Object.entries(params.constraints || {}).filter(([k2]) => m.params.includes(k2)));
        input = h('div', { class: 'ds-checks' }, m.params.map((pn) => h('label', {}, pn, h('input', {
          type: 'text', placeholder: 'free', value: params.constraints[pn] ?? '', style: { width: '70px', padding: '2px 4px' },
          oninput: (e) => { if (e.target.value === '') delete params.constraints[pn]; else params.constraints[pn] = e.target.value; },
        }))));
      }
      return h('div', { class: 'field' }, h('label', {}, f.label), input);
    }
    drawList(); drawForm();
    let done = false;
    modal({
      title: existing ? 'Change analysis parameters' : 'Analyze data', wide: true,
      body: h('div', { class: 'two-col' }, left, right),
      buttons: [{ label: 'Cancel' }, { label: existing ? 'Update' : 'Analyze', primary: true, onClick: () => {
        if (!params.datasets.length) { toast('Select at least one data set', 'err'); return false; }
        done = true;
        resolve({ key, params });
      } }],
      onClose: () => { if (!done) resolve(null); },
    });
  });
}

/** "In plain words": the question the analysis answers, an example, and whether it suits this table. */
export function plainBox(a, table, params) {
  const p = a.plain;
  const notes = [];
  if (!a.tableTypes.includes(table.type)) notes.push(['bad', `This analysis needs a ${a.tableTypes.map((t) => TABLE_TYPES[t]?.label).join(' or ')} table; yours is a ${TABLE_TYPES[table.type].label} table.`]);
  const nsel = (params.datasets || []).length;
  if (['ttest', 'permutation', 'bayes_t', 'equivalence', 'bland_altman', 'roc'].includes(a.key) && nsel !== 2) notes.push(['bad', `Tick exactly two data sets below (now ${nsel}).`]);
  if (a.key === 'one_way' && nsel === 2) notes.push(['tip', 'With only two groups a t test gives the same answer and is simpler to report.']);
  if (a.key === 'ttest' && table.datasets.length > 2) notes.push(['tip', 'You have more than two groups: one-way ANOVA compares them all at once (testing pairs one by one inflates false positives).']);
  if (!notes.length && a.tableTypes.includes(table.type)) notes.push(['ok', 'Suitable for this table.']);
  return h('div', { class: 'plain-box' },
    p ? h('div', { class: 'plain-q' }, h('span', { class: 'plain-tag' }, 'In plain words'), p.question) : null,
    p ? h('div', { class: 'plain-ex' }, h('b', {}, 'Example: '), p.example) : null,
    p?.level === 'advanced' ? h('div', { class: 'plain-lvl' }, 'Advanced / specialist method') : null,
    notes.map(([k, t]) => h('div', { class: `plain-note ${k}` }, { ok: '✓ ', bad: '⚠ ', tip: '💡 ' }[k], t)));
}

/** "About this analysis": what it does, when to use it, data layout and assumptions. */
export function aboutPanel(a, open = false) {
  const g = a.guide;
  const row = (label, text) => (text ? h('div', { class: 'about-row' }, h('b', {}, label), h('span', {}, text)) : null);
  const d = h('details', { class: 'about-box', open },
    h('summary', {}, 'ℹ About this analysis — what it does, when to use it'),
    row('What it does', g.what), row('When to use it', g.when), row('Data layout', g.data), row('How to run it', g.how),
    row('Reading the results', g.results), row('Assumptions', g.assume), row('Alternatives', g.alt), row('Key references', g.ref),
    h('a', { href: '#', onclick: (e) => { e.preventDefault(); import('./help.js').then((m) => m.openManual(`ref-${a.key}`)); } }, 'Open the full guide in the manual →'));
  try { if (localStorage.getItem('openprism.pref.aboutOpen') === '1') d.open = true; } catch (_) { /* ignore */ }
  d.addEventListener('toggle', () => { try { localStorage.setItem('openprism.pref.aboutOpen', d.open ? '1' : '0'); } catch (_) { /* ignore */ } });
  return d;
}

/** A ready-to-edit methods paragraph for a paper, with software versions. */
export function methodsText(a) {
  const meta = CATALOG.analyses.find((x) => x.key === a.key);
  const pv = a.result?.provenance || {};
  const label = (meta?.label || a.key).replace(/\s*\(.*\)\s*$/, '');
  const opts = describeParams(a);
  const alpha = a.params?.alpha || '0.05';
  const ref = meta?.guide?.ref ? ` (${meta.guide.ref.split(';')[0].trim()})` : '';
  return `Statistical analysis. ${label}${ref} was performed in OpenPrism ${String(pv.software || '').replace('OpenPrism ', '')} `
    + `(Python ${pv.python || '?'}, NumPy ${pv.numpy || '?'}, SciPy ${pv.scipy || '?'}, statsmodels ${pv.statsmodels || '?'})`
    + `${opts ? `; settings: ${opts}` : ''}. P < ${alpha} was considered statistically significant. `
    + `The computation is deterministic (data fingerprint SHA-256 ${String(pv.dataSha256 || '').slice(0, 16)}…), and the software's numerical accuracy is documented `
    + 'by its validation report against NIST certified values and R.';
}

/** Create a new analysis object in the project and run it. */
export async function createAnalysis(table, key, params) {
  const label = CATALOG.analyses.find((a) => a.key === key)?.label || key;
  const short = label.replace(/\s*\(.*\)/, '');
  const a = { id: uid('a'), name: uniqueName(P().analyses, `${short} of ${table.name}`), tableId: table.id, key, params, result: null, rev: 0 };
  P().analyses.push(a);
  await runAnalysis(a);
  return a;
}

export async function runAnalysis(a) {
  const t = getTable(a.tableId);
  if (!t) { a.result = { error: 'The data table was deleted.' }; return a; }
  try {
    a.result = await api('/api/analyze', { analysis: a.key, table: tableForServer(t), params: { ...toApiParams(a.key, a.params), ...(a.fullPrecision ? { _digits: 'full' } : {}) } }, undefined, a.name);
    a.error = null;
  } catch (e) {
    a.result = null;
    a.error = e.message;
  }
  a.rev = t.rev;
  // analyses that produce new tables (transform, normalize, residuals, histogram...)
  if (a.result?.outputTables?.length) {
    a.outputIds ||= [];
    a.result.outputTables.forEach((ot, k) => {
      let tt = getTable(a.outputIds[k]);
      if (!tt) {
        tt = normalizeTable({ ...ot, id: uid('t'), name: uniqueName(P().tables, ot.name), excluded: {}, rev: 1, derivedFrom: a.id });
        P().tables.push(tt);
        a.outputIds[k] = tt.id;
        emit('table-created', tt);
      } else {
        Object.assign(tt, normalizeTable({ ...ot, id: tt.id, name: tt.name, excluded: {}, rev: (tt.rev || 0) + 1, derivedFrom: a.id }));
        emit('table-changed', tt.id);
      }
    });
  }
  return a;
}

export function isStale(a) {
  const t = getTable(a.tableId);
  return t && a.rev !== t.rev;
}

// ---------------------------------------------------------------- results ---
export function renderResults(container, a) {
  const box = h('div', { class: 'results' });
  const t = getTable(a.tableId);
  if (a.error) box.append(h('div', { class: 'errbox' }, h('b', {}, 'Analysis could not be completed. '), a.error));
  const r = a.result;
  if (r) {
    box.append(h('h2', { style: { margin: '0 0 2px', fontSize: '17px' } }, r.title));
    box.append(h('div', { class: 'params-line' }, `Data: ${t ? t.name : '(deleted)'} · ${describeParams(a)}`));
    for (const w of r.warnings || []) box.append(h('div', { class: 'warnbox' }, w));
    for (const s of r.sections) {
      box.append(h('h3', {}, s.title));
      if (s.kind === 'kv') {
        box.append(h('table', { class: 'rtable kv' }, h('tbody', {}, s.rows.map(([k, v]) => h('tr', {},
          v === '' ? h('td', { colspan: 2, style: { fontWeight: 600, color: 'var(--text)' } }, k) : [h('td', {}, k), h('td', { class: isNum(v) ? 'num' : '' }, v)])))));
      } else {
        box.append(h('div', { style: { overflowX: 'auto' } }, h('table', { class: 'rtable' },
          h('thead', {}, h('tr', {}, s.columns.map((c) => h('th', {}, c)))),
          h('tbody', {}, s.rows.map((row) => h('tr', {}, row.map((c, j) => h('td', { class: j > 0 && isNum(c) ? 'num' : '' }, c))))))));
      }
    }
    if (r.provenance) {
      const pv = r.provenance;
      box.append(h('div', { class: 'prov' },
        h('span', { title: 'Everything needed to reproduce this result exactly' }, `🔁 Reproducible: ${pv.software} · NumPy ${pv.numpy} · SciPy ${pv.scipy} · statsmodels ${pv.statsmodels} · data SHA-256 ${pv.dataSha256.slice(0, 12)}…`),
        r.fullPrecision ? h('span', { class: 'tag' }, 'all digits shown') : null,
        h('a', { href: '/static/help/validation.html', target: '_blank', rel: 'noopener' }, 'Validation report')));
    }
    if (a.outputIds?.length) {
      box.append(h('h3', {}, 'Output'));
      a.outputIds.forEach((id) => { const ot = getTable(id); if (ot) box.append(h('div', {}, h('a', { href: '#', onclick: (e) => { e.preventDefault(); emit('open', { kind: 'table', id }); } }, `→ Data table “${ot.name}”`))); });
    }
  }
  container.append(box);
}

const isNum = (v) => typeof v === 'string' && /^[<>~-]?\s?[\d.]+(e[-+]?\d+)?$/i.test(v.trim());

function describeParams(a) {
  const parts = [];
  for (const f of FORMS[a.key] || []) {
    if (f.show && !f.show(a.params)) continue;
    let v = a.params[f.key];
    if (v === undefined || v === '' || (typeof v === 'object' && !Array.isArray(v) && !Object.keys(v).length)) continue;
    if (f.type === 'select') v = (f.options.find(([k]) => String(k) === String(v)) || [0, v])[1];
    else if (f.type === 'model') v = CATALOG.models.find((m) => m.key === v)?.name || v;
    else if (f.type === 'check') { if (!v) continue; v = 'yes'; }
    else if (f.type === 'constraints') v = Object.entries(v).map(([k, x]) => `${k}=${x}`).join(', ');
    else if (f.type === 'variables') v = (v || []).map((i) => getTable(a.tableId)?.datasets[i]?.name).join(', ');
    else if (f.type === 'dataset') v = getTable(a.tableId)?.datasets[+v]?.name ?? v;
    else if (Array.isArray(v)) v = v.join(', ');
    parts.push(`${f.label}: ${v}`);
  }
  return parts.join(' · ');
}

export function resultsToTSV(a) {
  const r = a.result;
  if (!r) return '';
  const lines = [r.title, ''];
  for (const s of r.sections) {
    lines.push(s.title);
    if (s.kind === 'table') lines.push(s.columns.join('\t'));
    s.rows.forEach((row) => lines.push(row.join('\t')));
    lines.push('');
  }
  return lines.join('\n');
}

export function exportResults(a) {
  download(`${a.name}.tsv`, resultsToTSV(a), 'text/tab-separated-values');
}

export function commitAnalysis() { commit('Analysis'); }
