// Sample size / power calculator (Tools menu).
import { helpIcon } from './help.js';
import { api, debounce, h, modal } from './ui.js';

const TESTS = [
  ['ttest2', 'Unpaired t test (two independent groups)'],
  ['paired', 'Paired t test'],
  ['onesample', 'One-sample t test'],
  ['anova', 'One-way ANOVA'],
  ['prop2', 'Compare two proportions'],
  ['corr', 'Correlation (Pearson r ≠ 0)'],
  ['mannwhitney', 'Mann-Whitney test (two groups, nonparametric)'],
  ['logrank', 'Survival: log-rank test / hazard ratio'],
  ['mcnemar', 'Paired proportions (McNemar)'],
  ['oneprop', 'One proportion vs. a hypothetical value'],
];

export function powerDialog() {
  const p = { test: 'ttest2', difference: 10, sd: 15, p1: 0.3, p2: 0.5, f: 0.25, r: 0.3, groups: 3, ratio: 1, alpha: 0.05, tails: '2', power: 0.8, n: '', hr: 0.6, pevent: 0.5, p10: 0.15, p01: 0.05, p0: 0.5 };
  let solveFor = 'n';
  const form = h('div');
  const out = h('div');
  const chart = h('div', { style: { height: '260px' } });

  const fieldRow = (label, key, extra = {}) => h('div', { class: 'field' }, h('label', {}, label),
    h('input', { type: 'number', step: 'any', value: p[key], ...extra, oninput: (e) => { p[key] = e.target.value; calc(); } }));

  function drawForm() {
    form.innerHTML = '';
    form.append(h('div', { class: 'field' }, h('label', { class: 'with-help' }, 'Design', helpIcon('power')),
      h('select', { onchange: (e) => { p.test = e.target.value; drawForm(); calc(); } }, TESTS.map(([k, l]) => h('option', { value: k, selected: k === p.test }, l)))));
    if (['ttest2', 'paired', 'onesample'].includes(p.test)) {
      form.append(fieldRow(p.test === 'paired' ? 'Mean of differences to detect' : 'Difference between means to detect', 'difference'));
      form.append(fieldRow(p.test === 'paired' ? 'SD of the differences' : 'Standard deviation', 'sd'));
    } else if (p.test === 'anova') {
      form.append(fieldRow('Number of groups', 'groups', { step: 1, min: 2 }));
      form.append(fieldRow("Effect size Cohen's f (0.1 small, 0.25 medium, 0.4 large)", 'f'));
    } else if (p.test === 'prop2') {
      form.append(fieldRow('Proportion in group 1 (0-1)', 'p1'));
      form.append(fieldRow('Proportion in group 2 (0-1)', 'p2'));
    } else if (p.test === 'corr') {
      form.append(fieldRow('Correlation coefficient r to detect', 'r'));
    } else if (p.test === 'mannwhitney') {
      form.append(fieldRow('Shift between groups to detect', 'difference'));
      form.append(fieldRow('Standard deviation', 'sd'));
    } else if (p.test === 'logrank') {
      form.append(fieldRow('Hazard ratio to detect (e.g. 0.6 = 40% lower risk)', 'hr'));
      form.append(fieldRow('Probability that a subject has the event during the study (0-1)', 'pevent'));
    } else if (p.test === 'mcnemar') {
      form.append(fieldRow('Proportion of pairs positive only in condition 1 (p10)', 'p10'));
      form.append(fieldRow('Proportion of pairs positive only in condition 2 (p01)', 'p01'));
    } else if (p.test === 'oneprop') {
      form.append(fieldRow('Hypothetical proportion (null)', 'p0'));
      form.append(fieldRow('Expected true proportion', 'p1'));
    }
    if (['ttest2', 'prop2', 'mannwhitney', 'logrank'].includes(p.test)) form.append(fieldRow('Ratio of group sizes (n2 / n1)', 'ratio'));
    form.append(fieldRow('Significance level (alpha)', 'alpha'));
    form.append(h('div', { class: 'field' }, h('label', {}, 'Tails'), h('select', { onchange: (e) => { p.tails = e.target.value; calc(); } },
      h('option', { value: '2', selected: p.tails === '2' }, 'Two-tailed'), h('option', { value: '1', selected: p.tails === '1' }, 'One-tailed'))));
    form.append(h('div', { class: 'field' }, h('label', {}, 'Calculate'), h('div', { class: 'seg' },
      h('button', { class: solveFor === 'n' ? 'on' : '', onclick: () => { solveFor = 'n'; drawForm(); calc(); } }, 'Sample size'),
      h('button', { class: solveFor === 'power' ? 'on' : '', onclick: () => { solveFor = 'power'; if (!p.n) p.n = 20; drawForm(); calc(); } }, 'Power'))));
    form.append(solveFor === 'n' ? fieldRow('Desired power (0-1)', 'power') : fieldRow(['anova', 'ttest2', 'prop2', 'mannwhitney', 'logrank'].includes(p.test) ? 'Sample size per group' : p.test === 'mcnemar' ? 'Number of pairs' : 'Sample size (n)', 'n', { step: 1 }));
  }

  const calc = debounce(async () => {
    const body = { ...p, [solveFor === 'n' ? 'n' : 'power']: '' };
    try {
      const r = await api('/api/power', body);
      out.innerHTML = '';
      const perGroup = r.perGroup ? ' per group' : '';
      out.append(h('div', { class: 'power-result' },
        solveFor === 'n' ? h('div', {}, 'Required sample size: ', h('b', {}, `${r.n}${perGroup}`), r.perGroup ? ` (total ${r.total})` : '')
          : h('div', {}, 'Power: ', h('b', {}, `${(r.power * 100).toFixed(1)}%`)),
        h('div', { class: 'hint' }, `${r.effectLabel} = ${r.effectSize.toFixed(3)} · achieved power at n = ${r.n}: ${(r.power * 100).toFixed(1)}%`),
        r.events ? h('div', {}, 'Events needed: ', h('b', {}, r.events), ' (Schoenfeld) — the study must run until this many events have occurred.') : null));
      out.append(h('div', { class: 'hint' }, 'Assumes Gaussian data for t tests/ANOVA and independent observations. Add extra subjects for expected drop-outs.'));
      Plotly.react(chart, [
        { x: r.curve.n, y: r.curve.power.map((v) => v * 100), mode: 'lines', line: { color: '#2f6fdb', width: 2.5 }, name: 'Power' },
        { x: [r.n], y: [r.power * 100], mode: 'markers', marker: { size: 10, color: '#c0392b' }, name: 'Design' },
      ], {
        margin: { l: 50, r: 10, t: 10, b: 45 }, showlegend: false, paper_bgcolor: '#fff', plot_bgcolor: '#fff',
        xaxis: { title: { text: r.perGroup ? 'Sample size per group' : 'Sample size' }, showline: true, ticks: 'outside', zeroline: false },
        yaxis: { title: { text: 'Power (%)' }, range: [0, 102], showline: true, ticks: 'outside', zeroline: false },
        shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 80, y1: 80, line: { dash: 'dot', color: '#999', width: 1 } }],
      }, { displayModeBar: false, responsive: true });
    } catch (e) {
      out.innerHTML = '';
      out.append(h('div', { class: 'errbox', style: { margin: '8px 0' } }, e.message));
    }
  }, 250);

  drawForm();
  modal({ title: 'Sample size & power calculator', wide: true, body: h('div', { class: 'power-grid' }, form, h('div', {}, out, chart)), buttons: [{ label: 'Close', primary: true }] });
  calc();
}
