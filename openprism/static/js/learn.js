// Help for newcomers: plain-language explanations of table types and graph types,
// small example tables, and "recommended for your data" suggestions.
import { h } from './ui.js';

/** Each table type in everyday words, with a tiny example of what the data look like. */
export const TABLE_PLAIN = {
  column: { title: 'Groups side by side', say: 'Each column is one group; the numbers below are measurements of that group.',
    use: 'Compare groups: t test, ANOVA, dot or bar charts.', ex: [['Control', 'Drug A', 'Drug B'], ['12.1', '15.3', '18.2'], ['11.8', '14.9', '19.1']] },
  xy: { title: 'X and Y values', say: 'The first column is X (dose, time, concentration…); the other columns are Y values measured at each X.',
    use: 'Curves and lines: dose-response, standard curves, time courses, correlation.', ex: [['Dose (X)', 'Response'], ['0.1', '5'], ['1', '20'], ['10', '60']] },
  grouped: { title: 'Two ways of grouping', say: 'Rows are one grouping (e.g. male / female), columns another (e.g. control / drug).',
    use: 'Two-way ANOVA, grouped or stacked bars.', ex: [['', 'Control', 'Drug'], ['Male', '25', '30'], ['Female', '20', '27']] },
  contingency: { title: 'Counts in categories', say: 'How many subjects fall into each combination of two categories.',
    use: 'Chi-square / Fisher test, relative risk, odds ratio.', ex: [['', 'Disease', 'Healthy'], ['Smoker', '30', '70'], ['Non-smoker', '10', '90']] },
  survival: { title: 'Time until an event', say: 'X is the follow-up time; each group column holds 1 if the event happened, 0 if the subject was still event-free (censored).',
    use: 'Kaplan-Meier survival curves, log-rank test.', ex: [['Days (X)', 'Treated', 'Control'], ['120', '1', ''], ['300', '0', ''], ['45', '', '1']] },
  parts: { title: 'Parts of a whole', say: 'Amounts that add up to a total.', use: 'Pie and donut charts, percentages.', ex: [['', 'Amount'], ['T cells', '45'], ['B cells', '30']] },
  multi: { title: 'Several variables per subject', say: 'Each row is one subject (patient, sample); each column is a different measurement.',
    use: 'Regression with several predictors, correlation matrix, PCA, logistic and Cox regression.', ex: [['Age', 'BMI', 'Smoker', 'Chol.'], ['45', '24.5', '1', '210'], ['52', '28.1', '0', '240']] },
  nested: { title: 'Groups → subjects → repeats', say: 'Each group has several subjects, and each subject was measured several times.',
    use: 'Nested t test / ANOVA (avoids counting repeats as separate subjects).', ex: [['Control: mouse 1', 'mouse 2'], ['3.1', '2.8'], ['3.4', '2.9']] },
  summary: { title: 'Only mean, SD and n', say: 'One row per group with its mean, standard deviation (or SEM) and number of values — e.g. taken from a paper.',
    use: 't test and ANOVA without the raw data.', ex: [['', 'Mean', 'SD', 'N'], ['Control', '10.2', '2.1', '12'], ['Drug', '13.5', '2.4', '11']] },
};

/** A small picture of the data layout. */
export function exampleTable(rows) {
  return h('table', { class: 'mini-ex' }, h('tbody', {}, rows.map((r, i) => h('tr', {}, r.map((c) => h(i ? 'td' : 'th', {}, c))))));
}

/** Graph types in everyday words. */
export const GRAPH_PLAIN = {
  scatter: 'Every value is a dot, with a line at the mean (or median). Best for small groups: readers see all the data.',
  bar: 'A bar shows the mean of each group with an error bar (SD, SEM or CI). Familiar, but hides individual values — consider dots on top.',
  meanerror: 'Only the mean and its error bar for each group — compact when there are many groups.',
  box: 'Box = middle half of the values with the median line; whiskers = the range. Good for larger groups and skewed data.',
  violin: 'Like a box plot, but the width shows where values are concentrated. Good for larger groups.',
  beforeafter: 'Lines connect the values of the same subject before and after — for paired data.',
  roc: 'The ROC curve of a diagnostic marker (run the ROC analysis first).',
  'xy-points': 'Each X with the mean of its Y values and an error bar. Add a curve fit or regression line from Analyze.',
  'xy-line': 'Points joined by lines — time courses and profiles.',
  'xy-all': 'Every replicate shown as its own point.',
  'xy-lineonly': 'Just the line, no symbols — for dense data.',
  'xy-area': 'Line with the area below it filled.',
  'grouped-bar': 'Bars side by side for each row — compare columns within each row group.',
  'stacked-bar': 'Bars stacked on top of each other — shows totals and their parts.',
  'stacked-percent': 'Stacked bars scaled to 100 % — compares proportions.',
  'grouped-scatter': 'Dots for each value, grouped by row and column.',
  'grouped-line': 'One line per column across the rows (e.g. across time points).',
  'grouped-box': 'Box plots for each row × column combination.',
  heatmap: 'Colours show the size of each value — good for big tables.',
  km: 'Kaplan-Meier staircase: the fraction still event-free over time; ticks mark censored subjects.',
  pie: 'Slices show each part’s share of the total.',
  donut: 'A pie with a hole — the same information, easier to label.',
  'parts-bar': 'Horizontal bars of each part — easier to compare than pie slices.',
  'parts-stacked': 'One bar divided into the parts.',
  'var-scatter': 'Choose two variables to plot against each other (X vs. Y), optionally coloured by a third.',
  'var-box': 'Box plots of several variables side by side.',
  'nested-scatter': 'Dots grouped by subject within each group, so repeats of one subject are visible.',
  'analysis-plot': 'A plot produced by an analysis (Q-Q plot, PCA, Bland-Altman, regression diagnostics…).',
};

const filled = (t, i) => t.cells.some((r) => {
  let off = 0;
  for (let j = 0; j < i; j++) off += t.datasets[j].reps || 1;
  for (let k = 0; k < (t.datasets[i].reps || 1); k++) if (String(r[off + k] ?? '').trim() !== '') return true;
  return false;
});

/** Suggested analyses for this table: [{key, why}] — the first is the best starting point. */
export function recommend(t) {
  const n = t.datasets.filter((_, i) => filled(t, i)).length;
  const rows = t.cells.filter((r) => r.some((c) => String(c ?? '').trim() !== '')).length;
  const R = [];
  const add = (key, why) => R.push({ key, why });
  switch (t.type) {
    case 'column':
      if (n <= 1) { add('descriptive', 'you have one group: describe it'); add('one_sample', 'compare its average with a known value'); }
      else if (n === 2) { add('ttest', 'you have two groups: are they different?'); add('descriptive', 'summarise each group'); }
      else { add('one_way', `you have ${n} groups: are they different, and which ones?`); add('descriptive', 'summarise each group'); }
      add('normality', 'check whether the values look bell-shaped (helps choose between tests)');
      break;
    case 'xy':
      add('nonlinear', 'fit a curve such as dose-response or decay');
      add('linear', 'fit a straight line');
      add('correlation', 'are X and Y related?');
      add('auc', 'area under the curve');
      break;
    case 'grouped':
      add('two_way', 'two grouping factors: does each matter, and do they interact?');
      add('multiple_t', 'compare two columns separately in each row');
      add('descriptive', 'summarise each column');
      break;
    case 'contingency':
      add('contingency', 'are the two categories related?');
      if (n === 2 && rows === 2) add('risk', 'how much higher is the risk (relative risk, odds ratio)?');
      add('proportion', 'fractions with confidence intervals');
      break;
    case 'survival': {
      const codes = new Set(t.cells.flat().map((c) => String(c ?? '').trim()).filter(Boolean));
      add('survival', 'Kaplan-Meier curves and the log-rank test');
      if ([...codes].some((c) => !['0', '1'].includes(c))) add('competing_risks', 'there are event codes other than 0/1 (competing events)');
      break;
    }
    case 'parts': add('parts', 'fraction of the total for each part'); break;
    case 'summary':
      add(rows === 2 ? 'summary_ttest' : 'summary_anova', rows === 2 ? 'two groups: are they different?' : 'several groups: are they different?');
      add('summary_describe', 'confidence intervals of each mean');
      break;
    case 'nested': add('nested', 'compare groups while respecting that repeats come from the same subject'); break;
    case 'multi':
      add('correlation', 'which variables go up and down together?');
      add('multiple_regression', 'predict one variable from the others');
      add('logistic', 'predict a yes/no (0/1) variable');
      add('pca', 'find the main patterns among many variables');
      break;
    default: break;
  }
  return R;
}
