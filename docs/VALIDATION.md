# Validation report

*Generated 2026-11-03 by `validation/run_validation.py`.*

OpenPrism's statistical results were evaluated in four independent ways:

1. **Accuracy against certified values.** The NIST Statistical Reference Datasets (StRD) give certified results computed with
   500-digit arithmetic for deliberately difficult problems: univariate statistics, one-way ANOVA, linear regression (including the
   ill-conditioned 10th-degree Filip polynomial and the Longley data) and 26 nonlinear regression problems, each from two starting points.
   Accuracy is reported as the log relative error (LRE), the number of correct significant digits (McCullough 1998, 1999).
2. **Agreement with R.** About 290 results from base R 4.x and established CRAN packages (survival, MASS, metafor, psych, car,
   lmtest, quantreg, circular, nlme, coin) on classic datasets. Where R itself is known to be inexact (root-finding tolerances,
   `1 − pchisq()` cancellation, coarse numerical Hessians), the result is additionally checked against its *defining equation*
   evaluated in exact or 50-digit arithmetic.
3. **Statistical calibration.** Monte-Carlo simulation through the application's own code: tests must reject at the nominal
   rate when the null hypothesis is true, and 95% confidence intervals must cover the true value 95% of the time.
4. **Reproducibility.** Every analysis gives bit-identical output when repeated and in a fresh process (resampling methods use
   fixed seeds), and invariances that must hold mathematically (shift, scale, ordering, relabelling) hold to ≥ 9 digits.

All checks run through `openprism.stats.run`, the same code path the application uses, with full-precision output.
Rerun everything with `python validation/run_validation.py`; the automated test-suite runs the same checks.

## Summary

| Suite | Checks | Passed | Median LRE | Minimum LRE |
| --- | ---: | ---: | ---: | ---: |
| Accuracy: NIST Statistical Reference Datasets | 349 | 349 | 14.0 | 2.6 |
| Agreement with R and established CRAN packages | 403 | 403 | 14.8 | 1.0 |
| Statistical calibration (Monte-Carlo) | 25 | 25 | — | — |
| Reproducibility and invariance | 31 | 31 | 15.0 | 14.3 |

**808 of 808 checks passed.** LRE = number of correct significant digits (15 = identical in double precision).

## Problems found and fixed

While building this suite the following problems were found **and fixed**:

* Derived data tables (outputs of transforms, normalization, residuals…) were stored with only 6 significant digits; they now keep 15.
* Data with a large constant part (e.g. 1 000 000 000 000.4) lost up to 10 digits in ANOVA, t tests and SDs, because such numbers
  cannot be held exactly in binary. Values are now centred on a common offset in exact decimal arithmetic before conversion
  (NIST SmLs07–09: from 3 to 15 correct digits).
* Polynomial and ill-conditioned multiple regression lost all digits on NIST Filip. These fits are now solved from the exact
  decimal data in 80-digit arithmetic (Filip: from 0 to ≥ 10.5 digits for every coefficient).
* The nonlinear fitter failed to converge on two NIST problems from the first starting values and stopped early on others.
  It now combines Levenberg-Marquardt and a trust-region method and keeps the best solution: all 52 NIST nonlinear fits converge
  to the certified solution (≥ 5 digits for every parameter, median 8.5).
* Mann-Whitney and Wilcoxon P values were labelled "exact" when ties forced an approximation; both now compute the exact
  conditional distribution with ties (as StatXact / R `coin`) and label the method truthfully.
* The Peto-Peto weighted log-rank test used Peto's survival estimate at the previous event time instead of the current one
  (Klein & Moeschberger §7.3); it now agrees with an independent implementation to 15 digits.
* The aligned-rank-transform ANOVA could break ties between values that are equal in exact arithmetic but differ by one unit
  in the last place after alignment; aligned values are now rounded to 12 significant digits before ranking (ARTool agreement:
  from 2.5 to 14.7 digits).
* Numbers were parsed leniently ("1,5" was read as 15). Only the strict mathematical format is now accepted (decimal point, no
  thousands separators); anything else is flagged and reported, never reinterpreted.

## Software

* **OpenPrism:** 1.0.0
* **Python:** 3.13.18
* **NumPy:** 2.5.4
* **SciPy:** 1.18.1
* **statsmodels:** 0.15.0
* **Platform:** Linux x86_64
* **R reference:** R version 4.3.3 (2024-02-29) (generated 2026-11-03)
* **R packages:** survival 3.5.8, MASS 7.3.60.0.1, metafor 4.4.0, psych 2.4.1, car 3.1.2, lmtest 0.9.40, quantreg 5.97, circular 0.5.0, nlme 3.1.164, coin 1.4.3

## Accuracy: NIST Statistical Reference Datasets

### Univariate summary statistics (18/18 passed — LRE min 15.0, median 15.0)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| Lew (lower) | Mean | -177.435 | -177.435 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Lew (lower) | Standard deviation | 277.332168 | 277.332168 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Lottery (lower) | Mean | 518.9587156 | 518.9587156 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Lottery (lower) | Standard deviation | 291.6997275 | 291.6997275 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Mavro (lower) | Mean | 2.001856 | 2.001856 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Mavro (lower) | Standard deviation | 0.000429123454 | 0.000429123454 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Michelso (average) | Mean | 299.8524 | 299.8524 | 15 | 8 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Michelso (average) | Standard deviation | 0.07901054782 | 0.07901054782 | 15 | 8 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| NumAcc1 (lower) | Mean | 10000002 | 10000002 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| NumAcc1 (lower) | Standard deviation | 1 | 1 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| NumAcc2 (average) | Mean | 1.2 | 1.2 | 15 | 8 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| NumAcc2 (average) | Standard deviation | 0.1 | 0.1 | 15 | 8 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| NumAcc3 (average) | Mean | 1000000.2 | 1000000.2 | 15 | 8 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| NumAcc3 (average) | Standard deviation | 0.1 | 0.1 | 15 | 8 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| NumAcc4 (higher) | Mean | 10000000.2 | 10000000.2 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| NumAcc4 (higher) | Standard deviation | 0.1 | 0.1 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| PiDigits (lower) | Mean | 4.5348 | 4.5348 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| PiDigits (lower) | Standard deviation | 2.86733906 | 2.86733906 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |

### One-way ANOVA (55/55 passed — LRE min 14.5, median 15.0)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| AtmWtAg (average) | Between-groups SS | 3.638341875e-09 | 3.638341875e-09 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| AtmWtAg (average) | Within-groups SS | 1.049517292e-08 | 1.049517292e-08 | 14.5 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| AtmWtAg (average) | F statistic | 15.94673357 | 15.94673357 | 14.65 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| AtmWtAg (average) | R² | 0.2574265445 | 0.2574265445 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| AtmWtAg (average) | Residual SD | 1.510483144e-05 | 1.510483144e-05 | 14.65 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SiRstv (lower) | Between-groups SS | 0.0511462616 | 0.0511462616 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SiRstv (lower) | Within-groups SS | 0.21663656 | 0.21663656 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SiRstv (lower) | F statistic | 1.180462374 | 1.180462374 | 14.73 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SiRstv (lower) | R² | 0.1909990391 | 0.1909990391 | 14.8 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SiRstv (lower) | Residual SD | 0.1040760683 | 0.1040760683 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs01 (lower) | Between-groups SS | 1.68 | 1.68 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs01 (lower) | Within-groups SS | 1.8 | 1.8 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs01 (lower) | F statistic | 21 | 21 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs01 (lower) | R² | 0.4827586207 | 0.4827586207 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs01 (lower) | Residual SD | 0.1 | 0.1 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs02 (lower) | Between-groups SS | 16.08 | 16.08 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs02 (lower) | Within-groups SS | 18 | 18 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs02 (lower) | F statistic | 201 | 201 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs02 (lower) | R² | 0.4718309859 | 0.4718309859 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs02 (lower) | Residual SD | 0.1 | 0.1 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs03 (lower) | Between-groups SS | 160.08 | 160.08 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs03 (lower) | Within-groups SS | 180 | 180 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs03 (lower) | F statistic | 2001 | 2001 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs03 (lower) | R² | 0.4707127735 | 0.4707127735 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs03 (lower) | Residual SD | 0.1 | 0.1 | 15 | 9 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs04 (average) | Between-groups SS | 1.68 | 1.68 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs04 (average) | Within-groups SS | 1.8 | 1.8 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs04 (average) | F statistic | 21 | 21 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs04 (average) | R² | 0.4827586207 | 0.4827586207 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs04 (average) | Residual SD | 0.1 | 0.1 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs05 (average) | Between-groups SS | 16.08 | 16.08 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs05 (average) | Within-groups SS | 18 | 18 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs05 (average) | F statistic | 201 | 201 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs05 (average) | R² | 0.4718309859 | 0.4718309859 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs05 (average) | Residual SD | 0.1 | 0.1 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs06 (average) | Between-groups SS | 160.08 | 160.08 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs06 (average) | Within-groups SS | 180 | 180 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs06 (average) | F statistic | 2001 | 2001 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs06 (average) | R² | 0.4707127735 | 0.4707127735 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs06 (average) | Residual SD | 0.1 | 0.1 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs07 (higher) | Between-groups SS | 1.68 | 1.68 | 15 | 5 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs07 (higher) | Within-groups SS | 1.8 | 1.8 | 15 | 5 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs07 (higher) | F statistic | 21 | 21 | 15 | 5 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs07 (higher) | R² | 0.4827586207 | 0.4827586207 | 15 | 5 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs07 (higher) | Residual SD | 0.1 | 0.1 | 15 | 5 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs08 (higher) | Between-groups SS | 16.08 | 16.08 | 15 | 5 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs08 (higher) | Within-groups SS | 18 | 18 | 15 | 5 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs08 (higher) | F statistic | 201 | 201 | 15 | 5 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs08 (higher) | R² | 0.4718309859 | 0.4718309859 | 15 | 5 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs08 (higher) | Residual SD | 0.1 | 0.1 | 15 | 5 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs09 (higher) | Between-groups SS | 160.08 | 160.08 | 15 | 5 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs09 (higher) | Within-groups SS | 180 | 180 | 15 | 5 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs09 (higher) | F statistic | 2001 | 2001 | 15 | 5 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs09 (higher) | R² | 0.4707127735 | 0.4707127735 | 15 | 5 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| SmLs09 (higher) | Residual SD | 0.1 | 0.1 | 15 | 5 | ✓ | NIST StRD (certified, 500-digit arithmetic) |

### Linear regression (120/120 passed — LRE min 10.5, median 15.0)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| Filip (higher) | B0 estimate | -1467.489614 | -1467.489614 | 14.55 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B0 standard error | 298.084531 | 298.084531 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B1 estimate | -2772.179592 | -2772.179592 | 14.83 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B1 standard error | 559.7798655 | 559.7798655 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B2 estimate | -2316.371082 | -2316.371082 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B2 standard error | 466.4775721 | 466.4775721 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B3 estimate | -1127.973941 | -1127.973941 | 14.42 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B3 standard error | 227.2042745 | 227.2042745 | 14.86 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B4 estimate | -354.4782337 | -354.4782337 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B4 standard error | 71.64786609 | 71.64786609 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B5 estimate | -75.12420174 | -75.12420174 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B5 standard error | 15.28971787 | 15.28971787 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B6 estimate | -10.87531804 | -10.87531804 | 14.34 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B6 standard error | 2.236911598 | 2.236911598 | 14.86 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B7 estimate | -1.062214986 | -1.062214986 | 14.64 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B7 standard error | 0.2216243219 | 0.2216243219 | 14.73 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B8 estimate | -0.06701911546 | -0.06701911546 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B8 standard error | 0.01423637632 | 0.01423637632 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B9 estimate | -0.002467810783 | -0.002467810783 | 14.8 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B9 standard error | 0.0005356174089 | 0.0005356174089 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B10 estimate | -4.029625251e-05 | -4.029625251e-05 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | B10 standard error | 8.966328374e-06 | 8.966328374e-06 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | Residual SD | 0.003348010513 | 0.003348010513 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Filip (higher) | R² | 0.9967274162 | 0.9967274162 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Longley (higher) | B0 estimate | -3482258.635 | -3482258.635 | 12.22 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Longley (higher) | B0 standard error | 890420.3836 | 890420.3836 | 12.67 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Longley (higher) | B1 estimate | 15.06187227 | 15.06187227 | 10.83 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Longley (higher) | B1 standard error | 84.91492577 | 84.91492577 | 11.98 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Longley (higher) | B2 estimate | -0.03581917929 | -0.03581917929 | 11.67 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Longley (higher) | B2 standard error | 0.03349100777 | 0.03349100777 | 13.14 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Longley (higher) | B3 estimate | -2.020229804 | -2.020229804 | 12.51 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Longley (higher) | B3 standard error | 0.4883996817 | 0.4883996817 | 12.44 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Longley (higher) | B4 estimate | -1.033226867 | -1.033226867 | 12.98 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Longley (higher) | B4 standard error | 0.2142741632 | 0.2142741632 | 12.52 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Longley (higher) | B5 estimate | -0.05110410565 | -0.05110410565 | 11.64 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Longley (higher) | B5 standard error | 0.2260732001 | 0.2260732001 | 12.5 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Longley (higher) | B6 estimate | 1829.151465 | 1829.151465 | 12.22 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Longley (higher) | B6 standard error | 455.4784991 | 455.4784991 | 12.68 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Longley (higher) | Residual SD | 304.8540736 | 304.8540736 | 12.73 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Longley (higher) | R² | 0.9954790046 | 0.9954790046 | 14.87 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| NoInt1 (average) | B1 estimate | 2.074380165 | 2.074380165 | 14.72 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| NoInt1 (average) | B1 standard error | 0.01652892562 | 0.01652892562 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| NoInt1 (average) | Residual SD | 3.56753034 | 3.56753034 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| NoInt1 (average) | R² | 0.9993654923 | 0.9993654923 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| NoInt2 (average) | B1 estimate | 0.7272727273 | 0.7272727273 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| NoInt2 (average) | B1 standard error | 0.04208273181 | 0.04208273181 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| NoInt2 (average) | Residual SD | 0.3692744729 | 0.3692744729 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| NoInt2 (average) | R² | 0.9933481153 | 0.9933481153 | 15 | 7 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Norris (lower) | B0 estimate | -0.2623230738 | -0.2623230738 | 13.33 | 8 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Norris (lower) | B0 standard error | 0.2328182343 | 0.2328182343 | 10.47 | 8 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Norris (lower) | B1 estimate | 1.002116818 | 1.002116818 | 14.35 | 8 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Norris (lower) | B1 standard error | 0.0004297968482 | 0.0004297968482 | 10.47 | 8 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Norris (lower) | Residual SD | 0.8847963961 | 0.8847963961 | 14.04 | 8 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Norris (lower) | R² | 0.9999937459 | 0.9999937459 | 15 | 8 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Pontius (lower) | B0 estimate | 0.0006735657895 | 0.0006735657895 | 15 | 8 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Pontius (lower) | B0 standard error | 0.000107938612 | 0.000107938612 | 15 | 8 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Pontius (lower) | B1 estimate | 7.320591604e-07 | 7.320591604e-07 | 15 | 8 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Pontius (lower) | B1 standard error | 1.578174e-10 | 1.578174e-10 | 14.67 | 8 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Pontius (lower) | B2 estimate | -3.160818713e-15 | -3.160818713e-15 | 15 | 8 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Pontius (lower) | B2 standard error | 4.8665285e-17 | 4.8665285e-17 | 15 | 8 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Pontius (lower) | Residual SD | 0.0002051774241 | 0.0002051774241 | 14.77 | 8 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Pontius (lower) | R² | 0.9999999002 | 0.9999999002 | 15 | 8 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler1 (higher) | B0 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler1 (higher) | B1 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler1 (higher) | B2 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler1 (higher) | B3 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler1 (higher) | B4 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler1 (higher) | B5 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler1 (higher) | Residual SD | 0 | 2.610729113e-68 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler1 (higher) | R² | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler2 (higher) | B0 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler2 (higher) | B1 estimate | 0.1 | 0.1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler2 (higher) | B2 estimate | 0.01 | 0.01 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler2 (higher) | B3 estimate | 0.001 | 0.001 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler2 (higher) | B4 estimate | 0.0001 | 0.0001 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler2 (higher) | B5 estimate | 1e-05 | 1e-05 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler2 (higher) | Residual SD | 0 | 4.043576666e-73 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler2 (higher) | R² | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler3 (higher) | B0 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler3 (higher) | B0 standard error | 2152.326247 | 2152.326247 | 14.83 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler3 (higher) | B1 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler3 (higher) | B1 standard error | 2363.551735 | 2363.551735 | 14.72 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler3 (higher) | B2 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler3 (higher) | B2 standard error | 779.3435243 | 779.3435243 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler3 (higher) | B3 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler3 (higher) | B3 standard error | 101.4755076 | 101.4755076 | 14.46 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler3 (higher) | B4 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler3 (higher) | B4 standard error | 5.645665122 | 5.645665122 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler3 (higher) | B5 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler3 (higher) | B5 standard error | 0.1123248547 | 0.1123248547 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler3 (higher) | Residual SD | 2360.145024 | 2360.145024 | 14.81 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler3 (higher) | R² | 0.999995559 | 0.999995559 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler4 (higher) | B0 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler4 (higher) | B0 standard error | 215232.6247 | 215232.6247 | 14.83 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler4 (higher) | B1 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler4 (higher) | B1 standard error | 236355.1735 | 236355.1735 | 14.68 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler4 (higher) | B2 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler4 (higher) | B2 standard error | 77934.35243 | 77934.35243 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler4 (higher) | B3 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler4 (higher) | B3 standard error | 10147.55076 | 10147.55076 | 14.47 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler4 (higher) | B4 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler4 (higher) | B4 standard error | 564.5665122 | 564.5665122 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler4 (higher) | B5 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler4 (higher) | B5 standard error | 11.23248547 | 11.23248547 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler4 (higher) | Residual SD | 236014.5024 | 236014.5024 | 14.83 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler4 (higher) | R² | 0.9574784408 | 0.9574784408 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler5 (higher) | B0 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler5 (higher) | B0 standard error | 21523262.47 | 21523262.47 | 14.81 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler5 (higher) | B1 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler5 (higher) | B1 standard error | 23635517.35 | 23635517.35 | 14.69 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler5 (higher) | B2 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler5 (higher) | B2 standard error | 7793435.243 | 7793435.243 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler5 (higher) | B3 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler5 (higher) | B3 standard error | 1014755.076 | 1014755.076 | 14.46 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler5 (higher) | B4 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler5 (higher) | B4 standard error | 56456.65122 | 56456.65122 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler5 (higher) | B5 estimate | 1 | 1 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler5 (higher) | B5 standard error | 1123.248547 | 1123.248547 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler5 (higher) | Residual SD | 23601450.24 | 23601450.24 | 14.85 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Wampler5 (higher) | R² | 0.002246689216 | 0.002246689216 | 15 | 6 | ✓ | NIST StRD (certified, 500-digit arithmetic) |

### Nonlinear regression (156/156 passed — LRE min 2.6, median 8.5)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| Bennett5 (higher), start 1 | all 3 parameters (minimum LRE) | -2523.505804 | -2523.502839 | 5.93 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Bennett5 (higher), start 1 | standard errors (minimum LRE) | 297.1517541 | 297.1512578 | 5.78 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Bennett5 (higher), start 1 | Residual sum of squares | 0.0005240474407 | 0.0005240474407 | 11.17 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Bennett5 (higher), start 2 | all 3 parameters (minimum LRE) | -2523.505804 | -2523.506437 | 6.6 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Bennett5 (higher), start 2 | standard errors (minimum LRE) | 297.1517541 | 297.1518577 | 6.46 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Bennett5 (higher), start 2 | Residual sum of squares | 0.0005240474407 | 0.0005240474407 | 11.13 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| BoxBOD (higher), start 1 | all 2 parameters (minimum LRE) | 213.8094089 | 213.8094084 | 7.94 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| BoxBOD (higher), start 1 | standard errors (minimum LRE) | 12.35451518 | 12.35451509 | 7.89 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| BoxBOD (higher), start 1 | Residual sum of squares | 1168.008877 | 1168.008877 | 10.42 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| BoxBOD (higher), start 2 | all 2 parameters (minimum LRE) | 213.8094089 | 213.8094089 | 9.14 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| BoxBOD (higher), start 2 | standard errors (minimum LRE) | 12.35451518 | 12.35451517 | 9.1 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| BoxBOD (higher), start 2 | Residual sum of squares | 1168.008877 | 1168.008877 | 10.42 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Chwirut1 (lower), start 1 | all 3 parameters (minimum LRE) | 0.1902781837 | 0.1902781836 | 8.4 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Chwirut1 (lower), start 1 | standard errors (minimum LRE) | 0.02193855704 | 0.02193855701 | 9 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Chwirut1 (lower), start 1 | Residual sum of squares | 2384.477139 | 2384.477139 | 11.41 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Chwirut1 (lower), start 2 | all 3 parameters (minimum LRE) | 0.1902781837 | 0.1902781831 | 8.26 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Chwirut1 (lower), start 2 | standard errors (minimum LRE) | 0.02193855704 | 0.02193855699 | 8.68 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Chwirut1 (lower), start 2 | Residual sum of squares | 2384.477139 | 2384.477139 | 11.41 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Chwirut2 (lower), start 1 | all 3 parameters (minimum LRE) | 0.1665766654 | 0.1665766654 | 9.06 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Chwirut2 (lower), start 1 | standard errors (minimum LRE) | 0.03830328681 | 0.03830328681 | 9.73 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Chwirut2 (lower), start 1 | Residual sum of squares | 513.0480294 | 513.0480294 | 11.21 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Chwirut2 (lower), start 2 | all 3 parameters (minimum LRE) | 0.1665766654 | 0.1665766656 | 8.79 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Chwirut2 (lower), start 2 | standard errors (minimum LRE) | 0.03830328681 | 0.03830328683 | 9.27 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Chwirut2 (lower), start 2 | Residual sum of squares | 513.0480294 | 513.0480294 | 11.21 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| DanWood (lower), start 1 | all 2 parameters (minimum LRE) | 0.7688622618 | 0.768862262 | 9.49 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| DanWood (lower), start 1 | standard errors (minimum LRE) | 0.01828197386 | 0.01828197386 | 9.66 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| DanWood (lower), start 1 | Residual sum of squares | 0.004317308408 | 0.004317308408 | 11.68 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| DanWood (lower), start 2 | all 2 parameters (minimum LRE) | 0.7688622618 | 0.7688622599 | 8.61 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| DanWood (lower), start 2 | standard errors (minimum LRE) | 0.01828197386 | 0.01828197382 | 8.69 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| DanWood (lower), start 2 | Residual sum of squares | 0.004317308408 | 0.004317308408 | 11.68 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| ENSO (average), start 1 | all 9 parameters (minimum LRE) | 10.51074919 | 10.51074921 | 6.18 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| ENSO (average), start 1 | standard errors (minimum LRE) | 0.1748883247 | 0.1748883249 | 6.84 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| ENSO (average), start 1 | Residual sum of squares | 788.5397867 | 788.5397867 | 11.43 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| ENSO (average), start 2 | all 9 parameters (minimum LRE) | 10.51074919 | 10.5107492 | 6.51 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| ENSO (average), start 2 | standard errors (minimum LRE) | 0.1748883247 | 0.1748883248 | 7.18 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| ENSO (average), start 2 | Residual sum of squares | 788.5397867 | 788.5397867 | 11.43 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Eckerle4 (higher), start 1 | all 3 parameters (minimum LRE) | 1.554382718 | 1.554382718 | 9.9 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Eckerle4 (higher), start 1 | standard errors (minimum LRE) | 0.01540805116 | 0.01540805116 | 6.95 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Eckerle4 (higher), start 1 | Residual sum of squares | 0.001463588749 | 0.001463588749 | 10.73 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Eckerle4 (higher), start 2 | all 3 parameters (minimum LRE) | 1.554382718 | 1.554382718 | 9.26 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Eckerle4 (higher), start 2 | standard errors (minimum LRE) | 0.01540805116 | 0.01540805117 | 6.95 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Eckerle4 (higher), start 2 | Residual sum of squares | 0.001463588749 | 0.001463588749 | 10.73 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Gauss1 (lower), start 1 | all 8 parameters (minimum LRE) | 98.77821087 | 98.77821062 | 8.06 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Gauss1 (lower), start 1 | standard errors (minimum LRE) | 0.5752731273 | 0.5752731261 | 7.89 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Gauss1 (lower), start 1 | Residual sum of squares | 1315.822243 | 1315.822243 | 11.59 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Gauss1 (lower), start 2 | all 8 parameters (minimum LRE) | 98.77821087 | 98.77821064 | 8.09 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Gauss1 (lower), start 2 | standard errors (minimum LRE) | 0.5752731273 | 0.5752731262 | 7.91 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Gauss1 (lower), start 2 | Residual sum of squares | 1315.822243 | 1315.822243 | 11.59 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Gauss2 (lower), start 1 | all 8 parameters (minimum LRE) | 99.01832841 | 99.01832838 | 9.02 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Gauss2 (lower), start 1 | standard errors (minimum LRE) | 0.5374876688 | 0.5374876685 | 8.83 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Gauss2 (lower), start 1 | Residual sum of squares | 1247.528209 | 1247.528209 | 10.6 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Gauss2 (lower), start 2 | all 8 parameters (minimum LRE) | 99.01832841 | 99.01832837 | 9.06 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Gauss2 (lower), start 2 | standard errors (minimum LRE) | 0.5374876688 | 0.5374876685 | 8.79 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Gauss2 (lower), start 2 | Residual sum of squares | 1247.528209 | 1247.528209 | 10.6 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Gauss3 (average), start 1 | all 8 parameters (minimum LRE) | 98.94036897 | 98.94036893 | 8.78 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Gauss3 (average), start 1 | standard errors (minimum LRE) | 0.5300519283 | 0.530051928 | 8.54 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Gauss3 (average), start 1 | Residual sum of squares | 1244.484636 | 1244.484636 | 10.98 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Gauss3 (average), start 2 | all 8 parameters (minimum LRE) | 98.94036897 | 98.94036893 | 8.91 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Gauss3 (average), start 2 | standard errors (minimum LRE) | 0.5300519283 | 0.5300519279 | 8.32 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Gauss3 (average), start 2 | Residual sum of squares | 1244.484636 | 1244.484636 | 10.98 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Hahn1 (average), start 1 | all 7 parameters (minimum LRE) | 1.077635173 | 1.077634334 | 5.89 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Hahn1 (average), start 1 | standard errors (minimum LRE) | 0.1707015474 | 0.1707015344 | 6.99 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Hahn1 (average), start 1 | Residual sum of squares | 1.532438285 | 1.532438285 | 10.59 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Hahn1 (average), start 2 | all 7 parameters (minimum LRE) | 1.077635173 | 1.077641941 | 5.01 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Hahn1 (average), start 2 | standard errors (minimum LRE) | 0.1707015474 | 0.1707017261 | 5.81 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Hahn1 (average), start 2 | Residual sum of squares | 1.532438285 | 1.532438285 | 10.84 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Kirby2 (average), start 1 | all 5 parameters (minimum LRE) | 1.674506306 | 1.674505825 | 6.54 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Kirby2 (average), start 1 | standard errors (minimum LRE) | 0.08798963434 | 0.08798962966 | 6.81 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Kirby2 (average), start 1 | Residual sum of squares | 3.905073962 | 3.905073962 | 11.74 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Kirby2 (average), start 2 | all 5 parameters (minimum LRE) | 1.674506306 | 1.674508757 | 5.83 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Kirby2 (average), start 2 | standard errors (minimum LRE) | 0.08798963434 | 0.08798965466 | 6.17 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Kirby2 (average), start 2 | Residual sum of squares | 3.905073962 | 3.905073962 | 11.11 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Lanczos1 (average), start 1 | all 6 parameters (minimum LRE) | 0.09510000003 | 0.09510000003 | 10.56 | 4 | ✓ | terms are exchangeable: best-matching ordering compared — NIST StRD (certified, 500-digit arithmetic) |
| Lanczos1 (average), start 1 | standard errors (minimum LRE) | 5.334730423e-11 | 5.329316623e-11 | 2.99 | 2 | ✓ | Standard errors are proportional to √RSS (see the RSS note), so they inherit its round-off limit. — NIST StRD (certified, 500-digit arithmetic) |
| Lanczos1 (average), start 1 | Residual sum of squares | 1.430786772e-25 | 1.427884344e-25 | 2.69 | 2 | ✓ | The certified RSS is 1.4e-25: the residuals (~1e-13) are at the round-off level of the data (~4e-16 × \|y\|), so only 2-3 digits of the RSS are representable in double precision. The parameters themselves agree to 10.5 digits. — NIST StRD (certified, 500-digit arithmetic) |
| Lanczos1 (average), start 2 | all 6 parameters (minimum LRE) | 0.09510000003 | 0.09510000003 | 10.55 | 4 | ✓ | terms are exchangeable: best-matching ordering compared — NIST StRD (certified, 500-digit arithmetic) |
| Lanczos1 (average), start 2 | standard errors (minimum LRE) | 5.334730423e-11 | 5.328295963e-11 | 2.92 | 2 | ✓ | Standard errors are proportional to √RSS (see the RSS note), so they inherit its round-off limit. — NIST StRD (certified, 500-digit arithmetic) |
| Lanczos1 (average), start 2 | Residual sum of squares | 1.430786772e-25 | 1.427337428e-25 | 2.62 | 2 | ✓ | The certified RSS is 1.4e-25: the residuals (~1e-13) are at the round-off level of the data (~4e-16 × \|y\|), so only 2-3 digits of the RSS are representable in double precision. The parameters themselves agree to 10.5 digits. — NIST StRD (certified, 500-digit arithmetic) |
| Lanczos2 (average), start 1 | all 6 parameters (minimum LRE) | 0.09625102994 | 0.09625103695 | 7.14 | 4 | ✓ | terms are exchangeable: best-matching ordering compared — NIST StRD (certified, 500-digit arithmetic) |
| Lanczos2 (average), start 1 | standard errors (minimum LRE) | 0.0006677057548 | 0.0006677057756 | 7.04 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Lanczos2 (average), start 1 | Residual sum of squares | 2.229942812e-11 | 2.229942812e-11 | 9.91 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Lanczos2 (average), start 2 | all 6 parameters (minimum LRE) | 0.09625102994 | 0.09625101535 | 6.82 | 4 | ✓ | terms are exchangeable: best-matching ordering compared — NIST StRD (certified, 500-digit arithmetic) |
| Lanczos2 (average), start 2 | standard errors (minimum LRE) | 0.0006677057548 | 0.000667705704 | 6.71 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Lanczos2 (average), start 2 | Residual sum of squares | 2.229942812e-11 | 2.229942812e-11 | 9.98 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Lanczos3 (lower), start 1 | all 6 parameters (minimum LRE) | 0.08681641498 | 0.08681640403 | 6.9 | 4 | ✓ | terms are exchangeable: best-matching ordering compared — NIST StRD (certified, 500-digit arithmetic) |
| Lanczos3 (lower), start 1 | standard errors (minimum LRE) | 0.01719790886 | 0.01719790923 | 6.84 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Lanczos3 (lower), start 1 | Residual sum of squares | 1.611719359e-08 | 1.611719359e-08 | 10.55 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Lanczos3 (lower), start 2 | all 6 parameters (minimum LRE) | 0.08681641498 | 0.08681638971 | 6.54 | 4 | ✓ | terms are exchangeable: best-matching ordering compared — NIST StRD (certified, 500-digit arithmetic) |
| Lanczos3 (lower), start 2 | standard errors (minimum LRE) | 0.01719790886 | 0.01719790702 | 6.66 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Lanczos3 (lower), start 2 | Residual sum of squares | 1.611719359e-08 | 1.611719359e-08 | 10.56 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| MGH09 (higher), start 1 | all 4 parameters (minimum LRE) | 0.1928069346 | 0.1928069345 | 7.62 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| MGH09 (higher), start 1 | standard errors (minimum LRE) | 0.01143531223 | 0.01143531215 | 7.67 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| MGH09 (higher), start 1 | Residual sum of squares | 0.0003075056039 | 0.0003075056038 | 11.61 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| MGH09 (higher), start 2 | all 4 parameters (minimum LRE) | 0.1928069346 | 0.1928069348 | 8.07 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| MGH09 (higher), start 2 | standard errors (minimum LRE) | 0.01143531223 | 0.01143531221 | 8.36 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| MGH09 (higher), start 2 | Residual sum of squares | 0.0003075056039 | 0.0003075056038 | 11.61 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| MGH10 (higher), start 1 | all 3 parameters (minimum LRE) | 0.005609636471 | 0.005609636283 | 7.48 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| MGH10 (higher), start 1 | standard errors (minimum LRE) | 0.0001568789247 | 0.0001568789183 | 7.39 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| MGH10 (higher), start 1 | Residual sum of squares | 87.94585517 | 87.94585517 | 11.25 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| MGH10 (higher), start 2 | all 3 parameters (minimum LRE) | 0.005609636471 | 0.005609636901 | 7.12 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| MGH10 (higher), start 2 | standard errors (minimum LRE) | 0.0001568789247 | 0.0001568789335 | 7.25 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| MGH10 (higher), start 2 | Residual sum of squares | 87.94585517 | 87.94585517 | 11.22 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| MGH17 (average), start 1 | all 5 parameters (minimum LRE) | 0.3754100521 | 0.3754100504 | 6.9 | 4 | ✓ | terms are exchangeable: best-matching ordering compared — NIST StRD (certified, 500-digit arithmetic) |
| MGH17 (average), start 1 | standard errors (minimum LRE) | 0.002072315355 | 0.002072315364 | 6.46 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| MGH17 (average), start 1 | Residual sum of squares | 5.464894697e-05 | 5.464894697e-05 | 11.5 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| MGH17 (average), start 2 | all 5 parameters (minimum LRE) | 0.3754100521 | 0.3754100511 | 7.08 | 4 | ✓ | terms are exchangeable: best-matching ordering compared — NIST StRD (certified, 500-digit arithmetic) |
| MGH17 (average), start 2 | standard errors (minimum LRE) | 0.002072315355 | 0.002072315358 | 6.64 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| MGH17 (average), start 2 | Residual sum of squares | 5.464894697e-05 | 5.464894697e-05 | 11.5 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1a (lower), start 1 | all 2 parameters (minimum LRE) | 238.9421292 | 238.9421271 | 7.98 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1a (lower), start 1 | standard errors (minimum LRE) | 2.707007524 | 2.707007469 | 7.69 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1a (lower), start 1 | Residual sum of squares | 0.1245513889 | 0.1245513889 | 10.45 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1a (lower), start 2 | all 2 parameters (minimum LRE) | 238.9421292 | 238.9421255 | 7.74 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1a (lower), start 2 | standard errors (minimum LRE) | 2.707007524 | 2.707007429 | 7.46 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1a (lower), start 2 | Residual sum of squares | 0.1245513889 | 0.1245513889 | 10.45 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1b (lower), start 1 | all 2 parameters (minimum LRE) | 337.9974616 | 337.9974539 | 7.57 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1b (lower), start 1 | standard errors (minimum LRE) | 3.164395021 | 3.164394865 | 7.31 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1b (lower), start 1 | Residual sum of squares | 0.07546468153 | 0.07546468153 | 11.26 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1b (lower), start 2 | all 2 parameters (minimum LRE) | 337.9974616 | 337.9974613 | 8.93 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1b (lower), start 2 | standard errors (minimum LRE) | 3.164395021 | 3.164395013 | 8.61 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1b (lower), start 2 | Residual sum of squares | 0.07546468153 | 0.07546468153 | 11.3 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1c (average), start 1 | all 2 parameters (minimum LRE) | 636.4272581 | 636.4272537 | 8.09 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1c (average), start 1 | standard errors (minimum LRE) | 4.663832657 | 4.663832594 | 7.87 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1c (average), start 1 | Residual sum of squares | 0.04096683697 | 0.04096683697 | 11.1 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1c (average), start 2 | all 2 parameters (minimum LRE) | 636.4272581 | 636.4272517 | 7.93 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1c (average), start 2 | standard errors (minimum LRE) | 4.663832657 | 4.663832562 | 7.69 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1c (average), start 2 | Residual sum of squares | 0.04096683697 | 0.04096683697 | 11.11 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1d (average), start 1 | all 2 parameters (minimum LRE) | 437.3697075 | 437.3697085 | 8.58 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1d (average), start 1 | standard errors (minimum LRE) | 3.648917434 | 3.648917452 | 8.32 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1d (average), start 1 | Residual sum of squares | 0.05641929528 | 0.05641929528 | 11.2 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1d (average), start 2 | all 2 parameters (minimum LRE) | 437.3697075 | 437.3697061 | 8.4 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1d (average), start 2 | standard errors (minimum LRE) | 3.648917434 | 3.648917409 | 8.16 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Misra1d (average), start 2 | Residual sum of squares | 0.05641929528 | 0.05641929528 | 11.2 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Rat42 (higher), start 1 | all 3 parameters (minimum LRE) | 72.46223758 | 72.46223797 | 7.85 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Rat42 (higher), start 1 | standard errors (minimum LRE) | 1.73402834 | 1.734028392 | 7.52 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Rat42 (higher), start 1 | Residual sum of squares | 8.056522934 | 8.056522934 | 11.85 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Rat42 (higher), start 2 | all 3 parameters (minimum LRE) | 72.46223758 | 72.46223786 | 7.97 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Rat42 (higher), start 2 | standard errors (minimum LRE) | 1.73402834 | 1.734028379 | 7.65 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Rat42 (higher), start 2 | Residual sum of squares | 8.056522934 | 8.056522934 | 11.85 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Rat43 (higher), start 1 | all 4 parameters (minimum LRE) | 699.6415127 | 699.6415129 | 8.86 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Rat43 (higher), start 1 | standard errors (minimum LRE) | 16.30229782 | 16.30229785 | 8.76 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Rat43 (higher), start 1 | Residual sum of squares | 8786.404908 | 8786.404908 | 11.38 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Rat43 (higher), start 2 | all 4 parameters (minimum LRE) | 699.6415127 | 699.6415122 | 7.76 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Rat43 (higher), start 2 | standard errors (minimum LRE) | 16.30229782 | 16.30229774 | 7.89 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Rat43 (higher), start 2 | Residual sum of squares | 8786.404908 | 8786.404908 | 11.38 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Roszman1 (average), start 1 | all 4 parameters (minimum LRE) | 0.201968664 | 0.2019686655 | 7.34 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Roszman1 (average), start 1 | standard errors (minimum LRE) | 0.01917266602 | 0.0191726661 | 7.97 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Roszman1 (average), start 1 | Residual sum of squares | 0.0004948484733 | 0.0004948484733 | 12.2 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Roszman1 (average), start 2 | all 4 parameters (minimum LRE) | 0.201968664 | 0.2019686597 | 6.96 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Roszman1 (average), start 2 | standard errors (minimum LRE) | 0.01917266602 | 0.01917266606 | 7.53 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Roszman1 (average), start 2 | Residual sum of squares | 0.0004948484733 | 0.0004948484733 | 12.2 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Thurber (higher), start 1 | all 7 parameters (minimum LRE) | 1288.13968 | 1288.139679 | 7.19 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Thurber (higher), start 1 | standard errors (minimum LRE) | 4.664796334 | 4.664796341 | 6.58 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Thurber (higher), start 1 | Residual sum of squares | 5642.70824 | 5642.70824 | 11.23 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Thurber (higher), start 2 | all 7 parameters (minimum LRE) | 1288.13968 | 1288.13968 | 7.57 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Thurber (higher), start 2 | standard errors (minimum LRE) | 4.664796334 | 4.664796335 | 6.89 | 3 | ✓ | NIST StRD (certified, 500-digit arithmetic) |
| Thurber (higher), start 2 | Residual sum of squares | 5642.70824 | 5642.70824 | 11.23 | 4 | ✓ | NIST StRD (certified, 500-digit arithmetic) |


## Agreement with R and established CRAN packages

### t tests and rank tests (15/15 passed — LRE min 14.6, median 15.0)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| sleep: Student t test | |t| | 1.860813467 | 1.860813467 | 14.78 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep: Student t test | P value | 0.07918671422 | 0.07918671422 | 14.61 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep: Student t test | 95% CI lower | -0.2038740323 | -0.2038740323 | 14.59 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep: Student t test | 95% CI upper | 3.363874032 | 3.363874032 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep: Welch t test | |t| | 1.860813467 | 1.860813467 | 14.78 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep: Welch t test | df | 17.77647352 | 17.77647352 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep: Welch t test | P value | 0.07939414019 | 0.07939414019 | 14.76 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep: paired t test | |t| | 4.062127683 | 4.062127683 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep: paired t test | P value | 0.002832890197 | 0.002832890197 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep: paired t test | 95% CI lower | 0.7001142367 | 0.7001142367 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep: paired t test | 95% CI upper | 2.459885763 | 2.459885763 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep: Mann-Whitney (ties) | Exact conditional P value | 0.0658165364 | 0.0658165364 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — coin::wilcox_test (exact) |
| sleep: Wilcoxon signed-rank (ties, a zero) | Exact conditional P value | 0.00390625 | 0.00390625 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — coin::wilcoxsign_test (exact) |
| sleep: Wilcoxon signed-rank (ties, a zero) | V (sum of positive ranks) | 45 | 45 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep: one-sample t test of differences | P value | 0.002832890197 | 0.002832890197 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |

### Normality (4/4 passed — LRE min 14.5, median 14.9)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| sleep group 1: Shapiro-Wilk | W | 0.9258060289 | 0.9258060289 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep group 1: Shapiro-Wilk | P value | 0.4079287964 | 0.4079287964 | 14.79 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep group 2: Shapiro-Wilk | W | 0.9192977013 | 0.9192977013 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep group 2: Shapiro-Wilk | P value | 0.3511346854 | 0.3511346854 | 14.5 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |

### Descriptive statistics (7/7 passed — LRE min 14.9, median 15.0)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| sleep group 2 | Mean | 2.33 | 2.33 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep group 2 | SD | 2.002248736 | 2.002248736 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep group 2 | 25% Percentile (R quantile type 6) | 0.625 | 0.625 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep group 2 | Median (R quantile type 6) | 1.75 | 1.75 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep group 2 | 75% Percentile (R quantile type 6) | 4.45 | 4.45 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep group 2 | 95% CI of mean (lower) | 0.8976775394 | 0.8976775394 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep group 2 | 95% CI of mean (upper) | 3.762322461 | 3.762322461 | 14.93 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |

### Variances (2/2 passed — LRE min 15.0, median 15.0)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| sleep: F test | F | 1.252595036 | 1.252595036 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| sleep: F test | P value | 0.7427199317 | 0.7427199317 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |

### Distributions and variances (13/13 passed — LRE min 14.3, median 15.0)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| two samples: Kolmogorov-Smirnov | D | 0.3151260504 | 0.3151260504 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| two samples: Kolmogorov-Smirnov | Exact P value | 0.3404691882 | 0.3404691882 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| two samples: Ansari-Bradley | AB | 114 | 114 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| two samples: Ansari-Bradley | P value | 0.9307962883 | 0.9307962883 | 15 | 4 | ✓ | both programs use the exact distribution — R version 4.3.3 (2024-02-29) — base R |
| two samples: Mood scale test | Z | 0.4571983384 | 0.4571983384 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| two samples: Mood scale test | P value | 0.6475284926 | 0.6475284926 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| three samples: Fligner-Killeen | Statistic | 2.287769007 | 2.287769007 | 14.63 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| three samples: Fligner-Killeen | P value | 0.3185790935 | 0.3185790935 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| three samples: Bartlett | Statistic | 2.821300394 | 2.821300394 | 14.9 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| three samples: Bartlett | P value | 0.2439845935 | 0.2439845935 | 14.35 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| three samples: Brown-Forsythe | F | 1.236891629 | 1.236891629 | 14.79 | 6 | ✓ | R version 4.3.3 (2024-02-29) — car::leveneTest(center = median) |
| three samples: Brown-Forsythe | P value | 0.3011486329 | 0.3011486329 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — car::leveneTest |
| three samples: Levene | F | 1.453382288 | 1.453382288 | 14.77 | 6 | ✓ | R version 4.3.3 (2024-02-29) — car::leveneTest(center = mean) |

### Effect sizes (6/6 passed — LRE min 11.5, median 14.8)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| two samples | Cohen's d | 0.309848268 | 0.309848268 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — formula + uniroot(pt(ncp)) |
| two samples | 95% CI of d, lower (noncentral t) | -0.4045800698 | -0.4045800698 | 11.54 | 5 | ✓ | R version 4.3.3 (2024-02-29) — uniroot on pt(ncp) |
| two samples | 95% CI of d, upper (noncentral t) | 1.019022425 | 1.019022425 | 12.44 | 5 | ✓ | R version 4.3.3 (2024-02-29) — uniroot on pt(ncp) |
| two samples | Hedges' g | 0.3017534772 | 0.3017534772 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| two samples | Glass's Δ | 0.3135090714 | 0.3135090714 | 14.91 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| two samples | Cliff's δ | 0.2016806723 | 0.2016806723 | 14.61 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |

### ANOVA (28/28 passed — LRE min 10.4, median 14.7)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| PlantGrowth: one-way ANOVA | F | 4.846087862 | 4.846087862 | 14.89 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| PlantGrowth: one-way ANOVA | P value | 0.01590995833 | 0.01590995833 | 14.58 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| PlantGrowth: one-way ANOVA | SS between | 3.76634 | 3.76634 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| PlantGrowth: one-way ANOVA | SS within | 10.49209 | 10.49209 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| PlantGrowth: Tukey trt1-ctrl | Mean difference | -0.371 | -0.371 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| PlantGrowth: Tukey trt1-ctrl | Simultaneous CI (lower) | -1.062216051 | -1.062216051 | 11.15 | 5 | ✓ | studentized range quantile (numerical integration) — R version 4.3.3 (2024-02-29) — base R |
| PlantGrowth: Tukey trt1-ctrl | Adjusted P value | 0.3908711442 | 0.3908711442 | 13.31 | 4 | ✓ | studentized range distribution: different numerical integration in R and SciPy — R version 4.3.3 (2024-02-29) — base R |
| PlantGrowth: Tukey trt2-ctrl | Mean difference | 0.494 | 0.494 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| PlantGrowth: Tukey trt2-ctrl | Simultaneous CI (lower) | -0.1972160514 | -0.1972160514 | 10.41 | 5 | ✓ | studentized range quantile (numerical integration) — R version 4.3.3 (2024-02-29) — base R |
| PlantGrowth: Tukey trt2-ctrl | Adjusted P value | 0.1979959913 | 0.1979959913 | 12.16 | 4 | ✓ | studentized range distribution: different numerical integration in R and SciPy — R version 4.3.3 (2024-02-29) — base R |
| PlantGrowth: Tukey trt2-trt1 | Mean difference | 0.865 | 0.865 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| PlantGrowth: Tukey trt2-trt1 | Simultaneous CI (lower) | 0.1737839486 | 0.1737839486 | 10.36 | 5 | ✓ | studentized range quantile (numerical integration) — R version 4.3.3 (2024-02-29) — base R |
| PlantGrowth: Tukey trt2-trt1 | Adjusted P value | 0.01200642398 | 0.01200642398 | 11.47 | 4 | ✓ | studentized range distribution: different numerical integration in R and SciPy — R version 4.3.3 (2024-02-29) — base R |
| PlantGrowth: Kruskal-Wallis | H | 7.988228749 | 7.988228749 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| PlantGrowth: Kruskal-Wallis | P value | 0.01842375573 | 0.01842375573 | 14.73 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| PlantGrowth: Welch ANOVA | F | 5.180972408 | 5.180972408 | 14.99 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| PlantGrowth: Welch ANOVA | Denominator df | 17.12841862 | 17.12841862 | 14.73 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| PlantGrowth: Welch ANOVA | P value | 0.01739282149 | 0.01739282149 | 14.59 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| RoundingTimes: Friedman | χ² | 11.14285714 | 11.14285714 | 14.54 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| RoundingTimes: Friedman | P value | 0.003805040776 | 0.003805040776 | 14.22 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| RoundingTimes: Quade | F | 7.042265115 | 7.042265115 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| RoundingTimes: Quade | P value | 0.002304253635 | 0.002304253635 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| ToothGrowth two-way: Column Factor | F | 15.57197945 | 15.57197945 | 14.6 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| ToothGrowth two-way: Column Factor | P value | 0.0002311828098 | 0.0002311828098 | 14.12 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| ToothGrowth two-way: Row Factor | F | 91.99996489 | 91.99996489 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| ToothGrowth two-way: Row Factor | P value | 4.046291196e-18 | 4.046291196e-18 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| ToothGrowth two-way: Interaction | F | 4.106991094 | 4.106991094 | 14.76 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| ToothGrowth two-way: Interaction | P value | 0.02186026896 | 0.02186026896 | 13.94 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |

### Regression (18/18 passed — LRE min 12.4, median 15.0)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| cars: linear regression | Slope | 3.932408759 | 3.932408759 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| cars: linear regression | Intercept | -17.57909489 | -17.57909489 | 14.58 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| cars: linear regression | Slope SE | 0.4155127767 | 0.4155127767 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| cars: linear regression | Intercept SE | 6.758440169 | 6.758440169 | 14.98 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| cars: linear regression | R² | 0.6510793808 | 0.6510793808 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| cars: linear regression | Residual SD | 15.37958675 | 15.37958675 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| cars: linear regression | F | 89.56710654 | 89.56710654 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| mtcars: multiple regression | Intercept coefficient | 27.61052686 | 27.61052686 | 14.14 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| mtcars: multiple regression | Intercept SE | 8.419928477 | 8.419928477 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| mtcars: multiple regression | wt coefficient | -4.3587972 | -4.3587972 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| mtcars: multiple regression | wt SE | 0.7527003922 | 0.7527003922 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| mtcars: multiple regression | hp coefficient | -0.01782227161 | -0.01782227161 | 12.45 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| mtcars: multiple regression | hp SE | 0.01498116885 | 0.01498116885 | 14.37 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| mtcars: multiple regression | qsec coefficient | 0.5108336942 | 0.5108336942 | 13.89 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| mtcars: multiple regression | qsec SE | 0.439221532 | 0.439221532 | 14.72 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| mtcars: multiple regression | R² | 0.8347677617 | 0.8347677617 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| mtcars: multiple regression | Adjusted R² | 0.8170643076 | 0.8170643076 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| mtcars: multiple regression | F | 47.1528187 | 47.1528187 | 14.59 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |

### Correlation (11/11 passed — LRE min 13.8, median 15.0)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| cars: pearson | Coefficient | 0.8068949007 | 0.8068949007 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| cars: pearson | P value | 1.489836496e-12 | 1.489836496e-12 | 13.82 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| cars: pearson | 95% CI lower | 0.6816422221 | 0.6816422221 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| cars: pearson | 95% CI upper | 0.8862036285 | 0.8862036285 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| cars: spearman | Coefficient | 0.8303568388 | 0.8303568388 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| cars: spearman | P value | 8.824558438e-14 | 8.824558438e-14 | 13.77 | 4 | ✓ | normal approximation with tie correction in both programs — R version 4.3.3 (2024-02-29) — base R |
| cars: kendall | Coefficient | 0.66899015 | 0.66899015 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| cars: kendall | P value | 2.638270848e-11 | 2.638270848e-11 | 14.66 | 4 | ✓ | normal approximation with tie correction in both programs — R version 4.3.3 (2024-02-29) — base R |
| mtcars: partial correlation mpg–wt | hp | Partial r | -0.751204905 | -0.751204905 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — residual method with lm() |
| mtcars: partial correlation mpg–hp | wt | Partial r | -0.5469926242 | -0.5469926242 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — residual method with lm() |
| mtcars: partial correlation wt–hp | mpg | Partial r | -0.04690019017 | -0.04690019017 | 14.05 | 6 | ✓ | R version 4.3.3 (2024-02-29) — residual method with lm() |

### Robust regression (5/5 passed — LRE min 5.3, median 6.9)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| cars: Theil-Sen | Slope | 3.666666667 | 3.666666667 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — median of pairwise slopes |
| cars: Huber M-estimator | Slope | 3.77331268 | 3.773320794 | 5.67 | 4 | ✓ | IRLS with MAD scale; convergence tolerances differ — R version 4.3.3 (2024-02-29) — MASS::rlm |
| cars: Huber M-estimator | Intercept | -16.52634764 | -16.52642932 | 5.31 | 4 | ✓ | IRLS with MAD scale — R version 4.3.3 (2024-02-29) — MASS::rlm |
| cars: median (LAD) regression | Slope | 3.4 | 3.400000064 | 7.73 | 5 | ✓ | R version 4.3.3 (2024-02-29) — quantreg::rq |
| cars: median (LAD) regression | Intercept | -11.6 | -11.60000139 | 6.92 | 5 | ✓ | R version 4.3.3 (2024-02-29) — quantreg::rq |

### Regression diagnostics (6/6 passed — LRE min 10.9, median 14.0)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| cars: Breusch-Pagan (studentized) | Statistic | 3.214879927 | 3.214879927 | 14.54 | 6 | ✓ | R version 4.3.3 (2024-02-29) — lmtest::bptest |
| cars: Breusch-Pagan (studentized) | P value | 0.07297154505 | 0.07297154505 | 14.2 | 6 | ✓ | R version 4.3.3 (2024-02-29) — lmtest::bptest |
| cars: Durbin-Watson | Statistic | 1.676225323 | 1.676225323 | 14.84 | 6 | ✓ | R version 4.3.3 (2024-02-29) — lmtest::dwtest |
| cars: Ramsey RESET (powers 2-3) | F | 1.555397542 | 1.555397542 | 11.04 | 6 | ✓ | R version 4.3.3 (2024-02-29) — lmtest::resettest |
| cars: Ramsey RESET (powers 2-3) | P value | 0.2220035545 | 0.2220035545 | 10.87 | 6 | ✓ | R version 4.3.3 (2024-02-29) — lmtest::resettest |
| cars: Breusch-Godfrey (lag 1) | LM statistic | 1.290801635 | 1.290801635 | 13.84 | 6 | ✓ | R version 4.3.3 (2024-02-29) — lmtest::bgtest |

### Nonlinear regression (6/6 passed — LRE min 5.6, median 6.2)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| Puromycin (treated): Michaelis-Menten | Vm | 212.6836299 | 212.6837436 | 6.27 | 5 | ✓ | R's nls stops at a relative offset of 1e-5; OpenPrism's residual SS is lower (checked below) — R version 4.3.3 (2024-02-29) — nls() |
| Puromycin (treated): Michaelis-Menten | SE of Vm | 6.94714885 | 6.947155186 | 6.04 | 5 | ✓ | R version 4.3.3 (2024-02-29) — nls() |
| Puromycin (treated): Michaelis-Menten | K | 0.06412110532 | 0.06412128242 | 5.56 | 5 | ✓ | R's nls stops at a relative offset of 1e-5; OpenPrism's residual SS is lower (checked below) — R version 4.3.3 (2024-02-29) — nls() |
| Puromycin (treated): Michaelis-Menten | SE of K | 0.008280930582 | 0.008280949578 | 5.64 | 5 | ✓ | R version 4.3.3 (2024-02-29) — nls() |
| Puromycin (treated): Michaelis-Menten | Residual SD | 10.93365819 | 10.93365819 | 10.69 | 6 | ✓ | R version 4.3.3 (2024-02-29) — nls() |
| Puromycin: is OpenPrism's optimum at least as good as R's? | residual SS (OpenPrism ≤ R) | 1195.448814 | 1195.448814 | 15 | 1 | ✓ | OpenPrism 1195.4488144393592 vs R 1195.4488144883592 — direct evaluation of the sum of squares |

### Rhythms (4/4 passed — LRE min 14.5, median 14.9)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| simulated 24 h rhythm: cosinor | MESOR | 10.25819583 | 10.25819583 | 14.46 | 6 | ✓ | R version 4.3.3 (2024-02-29) — lm(y ~ cos + sin) |
| simulated 24 h rhythm: cosinor | Amplitude | 2.499705633 | 2.499705633 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — lm(y ~ cos + sin) |
| simulated 24 h rhythm: cosinor | Zero-amplitude F | 88.06277105 | 88.06277105 | 14.75 | 6 | ✓ | R version 4.3.3 (2024-02-29) — lm(y ~ cos + sin) |
| simulated 24 h rhythm: cosinor | Time of peak | 7.876072663 | 7.876072663 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — atan2 of lm coefficients |

### Generalized linear models (47/47 passed — LRE min 2.3, median 6.7)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| mtcars am ~ wt + hp: logit | Intercept β | 18.86629872 | 18.86629872 | 13.55 | 4 | ✓ | iteratively reweighted least squares — R version 4.3.3 (2024-02-29) — glm() |
| mtcars am ~ wt + hp: logit | Intercept SE | 7.44355806 | 7.44355806 | 13.43 | 4 | ✓ | R version 4.3.3 (2024-02-29) — glm() |
| mtcars am ~ wt + hp: logit | wt β | -8.083475182 | -8.083475182 | 13.91 | 4 | ✓ | iteratively reweighted least squares — R version 4.3.3 (2024-02-29) — glm() |
| mtcars am ~ wt + hp: logit | wt SE | 3.068675113 | 3.068675113 | 13.76 | 4 | ✓ | R version 4.3.3 (2024-02-29) — glm() |
| mtcars am ~ wt + hp: logit | hp β | 0.03625559608 | 0.03625559608 | 13.61 | 4 | ✓ | iteratively reweighted least squares — R version 4.3.3 (2024-02-29) — glm() |
| mtcars am ~ wt + hp: logit | hp SE | 0.01773415365 | 0.01773415365 | 13.43 | 4 | ✓ | R version 4.3.3 (2024-02-29) — glm() |
| mtcars am ~ wt + hp: logit | Deviance | 10.05911047 | 10.05911047 | 14.91 | 5 | ✓ | R version 4.3.3 (2024-02-29) — glm() |
| mtcars am ~ wt + hp: probit | Intercept β | 10.40551955 | 10.40554612 | 5.59 | 4 | ✓ | iteratively reweighted least squares — R version 4.3.3 (2024-02-29) — glm() |
| mtcars am ~ wt + hp: probit | Intercept SE | 3.620339725 | 3.62051042 | 4.33 | 4 | ✓ | R version 4.3.3 (2024-02-29) — glm() |
| mtcars am ~ wt + hp: probit | wt β | -4.542191518 | -4.542205723 | 5.5 | 4 | ✓ | iteratively reweighted least squares — R version 4.3.3 (2024-02-29) — glm() |
| mtcars am ~ wt + hp: probit | wt SE | 1.512052935 | 1.512139763 | 4.24 | 4 | ✓ | R version 4.3.3 (2024-02-29) — glm() |
| mtcars am ~ wt + hp: probit | hp β | 0.02125896084 | 0.02125904919 | 5.38 | 4 | ✓ | iteratively reweighted least squares — R version 4.3.3 (2024-02-29) — glm() |
| mtcars am ~ wt + hp: probit | hp SE | 0.009190388858 | 0.009190836238 | 4.31 | 4 | ✓ | R version 4.3.3 (2024-02-29) — glm() |
| mtcars am ~ wt + hp: probit | Deviance | 9.860507139 | 9.860507139 | 10.83 | 5 | ✓ | R version 4.3.3 (2024-02-29) — glm() |
| mtcars: logistic regression analysis | wt β | -8.083475182 | -8.083475182 | 14.66 | 4 | ✓ | R version 4.3.3 (2024-02-29) — glm(binomial) |
| mtcars: logistic regression analysis | AIC | 16.05911047 | 16.05911047 | 15 | 5 | ✓ | R version 4.3.3 (2024-02-29) — glm(binomial) |
| mtcars mpg ~ wt + hp: Gamma (log) | Intercept β | 3.825870173 | 3.825870597 | 6.96 | 5 | ✓ | R version 4.3.3 (2024-02-29) — glm(Gamma) |
| mtcars mpg ~ wt + hp: Gamma (log) | Intercept SE | 0.07113839693 | 0.07113840122 | 7.22 | 4 | ✓ | dispersion = Pearson χ²/df in both — R version 4.3.3 (2024-02-29) — glm(Gamma) |
| mtcars mpg ~ wt + hp: Gamma (log) | wt β | -0.196986666 | -0.1969867716 | 6.27 | 5 | ✓ | R version 4.3.3 (2024-02-29) — glm(Gamma) |
| mtcars mpg ~ wt + hp: Gamma (log) | wt SE | 0.02815361354 | 0.02815361524 | 7.22 | 4 | ✓ | dispersion = Pearson χ²/df in both — R version 4.3.3 (2024-02-29) — glm(Gamma) |
| mtcars mpg ~ wt + hp: Gamma (log) | hp β | -0.001560105129 | -0.001560105702 | 6.44 | 5 | ✓ | R version 4.3.3 (2024-02-29) — glm(Gamma) |
| mtcars mpg ~ wt + hp: Gamma (log) | hp SE | 0.000401778883 | 0.0004017789072 | 7.22 | 4 | ✓ | dispersion = Pearson χ²/df in both — R version 4.3.3 (2024-02-29) — glm(Gamma) |
| warpbreaks: Poisson | Intercept β | 3.691963145 | 3.691963145 | 11.45 | 5 | ✓ | R version 4.3.3 (2024-02-29) — glm(poisson) |
| warpbreaks: Poisson | Intercept SE | 0.0454106926 | 0.0454107925 | 5.66 | 5 | ✓ | R version 4.3.3 (2024-02-29) — glm(poisson) |
| warpbreaks: Poisson | woolB β | -0.2059884426 | -0.2059884426 | 10.3 | 5 | ✓ | R version 4.3.3 (2024-02-29) — glm(poisson) |
| warpbreaks: Poisson | woolB SE | 0.05157116865 | 0.05157124131 | 5.85 | 5 | ✓ | R version 4.3.3 (2024-02-29) — glm(poisson) |
| warpbreaks: Poisson | tensionM β | -0.3213204316 | -0.3213204316 | 11.88 | 5 | ✓ | R version 4.3.3 (2024-02-29) — glm(poisson) |
| warpbreaks: Poisson | tensionM SE | 0.06026580193 | 0.0602659149 | 5.73 | 5 | ✓ | R version 4.3.3 (2024-02-29) — glm(poisson) |
| warpbreaks: Poisson | tensionH β | -0.5184884965 | -0.5184884965 | 10.95 | 5 | ✓ | R version 4.3.3 (2024-02-29) — glm(poisson) |
| warpbreaks: Poisson | tensionH SE | 0.06395944331 | 0.06395951781 | 5.93 | 5 | ✓ | R version 4.3.3 (2024-02-29) — glm(poisson) |
| warpbreaks: Poisson | Deviance | 210.3918888 | 210.3918888 | 15 | 5 | ✓ | R version 4.3.3 (2024-02-29) — glm(poisson) |
| warpbreaks: Poisson | AIC | 493.0559664 | 493.0559664 | 15 | 5 | ✓ | R version 4.3.3 (2024-02-29) — glm(poisson) |
| quine: negative binomial | α = 1/θ | 0.8536722882 | 0.8536726043 | 6.43 | 4 | ✓ | maximum likelihood of θ — R version 4.3.3 (2024-02-29) — MASS::glm.nb |
| quine: negative binomial | Intercept β | 2.962991699 | 2.962991616 | 7.55 | 4 | ✓ | R version 4.3.3 (2024-02-29) — MASS::glm.nb |
| quine: negative binomial | Intercept SE | 0.1350731105 | 0.1350731301 | 6.84 | 3 | ✓ | SE conditional on θ in both — R version 4.3.3 (2024-02-29) — MASS::glm.nb |
| quine: negative binomial | EthN β | -0.5738107335 | -0.5738109328 | 6.46 | 4 | ✓ | R version 4.3.3 (2024-02-29) — MASS::glm.nb |
| quine: negative binomial | EthN SE | 0.1588381731 | 0.1588382034 | 6.72 | 3 | ✓ | SE conditional on θ in both — R version 4.3.3 (2024-02-29) — MASS::glm.nb |
| quine: negative binomial | SexM β | 0.213485016 | 0.2134854322 | 5.71 | 4 | ✓ | R version 4.3.3 (2024-02-29) — MASS::glm.nb |
| quine: negative binomial | SexM SE | 0.1593664733 | 0.1593665034 | 6.72 | 3 | ✓ | SE conditional on θ in both — R version 4.3.3 (2024-02-29) — MASS::glm.nb |
| mtcars gear ~ wt + hp: proportional odds | wt β | -3.309989962 | -3.310004219 | 5.37 | 4 | ✓ | quasi-Newton maximum likelihood — R version 4.3.3 (2024-02-29) — MASS::polr |
| mtcars gear ~ wt + hp: proportional odds | wt SE | 0.9870972266 | 0.9858037761 | 2.88 | 2 | ✓ | polr's Hessian comes from optim() finite differences with step 1e-3; see the independent check — R version 4.3.3 (2024-02-29) — MASS::polr |
| mtcars gear ~ wt + hp: proportional odds | wt SE vs. independent Richardson-extrapolated Hessian | 0.9858035659 | 0.9858037761 | 6.67 | 5 | ✓ | log-likelihood written independently; Hessian by Richardson extrapolation of central differences — R version 4.3.3 (2024-02-29) — independent computation |
| mtcars gear ~ wt + hp: proportional odds | hp β | 0.02124382302 | 0.02124388891 | 5.51 | 4 | ✓ | quasi-Newton maximum likelihood — R version 4.3.3 (2024-02-29) — MASS::polr |
| mtcars gear ~ wt + hp: proportional odds | hp SE | 0.008841628688 | 0.008796265932 | 2.29 | 2 | ✓ | polr's Hessian comes from optim() finite differences with step 1e-3; see the independent check — R version 4.3.3 (2024-02-29) — MASS::polr |
| mtcars gear ~ wt + hp: proportional odds | hp SE vs. independent Richardson-extrapolated Hessian | 0.008796254736 | 0.008796265932 | 5.9 | 5 | ✓ | log-likelihood written independently; Hessian by Richardson extrapolation of central differences — R version 4.3.3 (2024-02-29) — independent computation |
| mtcars gear ~ wt + hp: proportional odds | threshold 1 | -7.694824228 | -7.694862271 | 5.31 | 4 | ✓ | R version 4.3.3 (2024-02-29) — MASS::polr |
| mtcars gear ~ wt + hp: proportional odds | threshold 2 | -4.491294424 | -4.491321694 | 5.22 | 4 | ✓ | R version 4.3.3 (2024-02-29) — MASS::polr |

### Contingency tables and proportions (37/37 passed — LRE min 2.2, median 15.0)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| Fisher's tea tasting | Fisher exact P | 0.4857142857 | 0.4857142857 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| Fisher's tea tasting | Conditional MLE odds ratio | 6.408308867 | 6.408319658 | 5.77 | 4 | ✓ | R's fisher.test finds these roots with uniroot's default tolerance (≈1e-4); see the exact checks below — R version 4.3.3 (2024-02-29) — fisher.test |
| Fisher's tea tasting | Exact CI of OR (lower) | 0.2117329153 | 0.2117355954 | 4.9 | 4 | ✓ | R's fisher.test finds these roots with uniroot's default tolerance (≈1e-4); see the exact checks below — R version 4.3.3 (2024-02-29) — fisher.test |
| Fisher's tea tasting | Exact CI of OR (upper) | 621.9337505 | 626.2435306 | 2.16 | 2 | ✓ | R's fisher.test finds these roots with uniroot's default tolerance (≈1e-4); see the exact checks below — R version 4.3.3 (2024-02-29) — fisher.test |
| Fisher's tea tasting: defining equation of the exact CI | |P(X ≥ 3; ψ_lower) − 0.025| | 0 | 2.393918397e-16 | 15 | 10 | ✓ | evaluated independently in exact or 50-digit arithmetic — defining equation (independent exact computation) |
| Fisher's tea tasting: defining equation of the exact CI | |P(X ≤ 3; ψ_upper) − 0.025| | 0 | 3.469446952e-18 | 15 | 10 | ✓ | evaluated independently in exact or 50-digit arithmetic — defining equation (independent exact computation) |
| Fisher's tea tasting: defining equation of the conditional MLE | |E[X; ψ̂] − 3| | 0 | 8.881784197e-16 | 15 | 10 | ✓ | evaluated independently in exact or 50-digit arithmetic — defining equation (independent exact computation) |
| Presidential approval (paired) | McNemar χ² (corrected) | 16.81779661 | 16.81779661 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| Presidential approval (paired) | McNemar P (corrected) | 4.114562281e-05 | 4.114562281e-05 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| Presidential approval (paired) | McNemar χ² (uncorrected) | 17.3559322 | 17.3559322 | 14.73 | 6 | ✓ | R version 4.3.3 (2024-02-29) — base R |
| 3 × 3 paired table: Bowker symmetry | χ² | 1.628571429 | 1.628571429 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — mcnemar.test (Bowker) |
| 3 × 3 paired table: Bowker symmetry | P value | 0.6529289314 | 0.6529289314 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — mcnemar.test (Bowker) |
| 3 × 3 table: Pearson χ² | χ² | 34.40737107 | 34.40737107 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — chisq.test |
| 3 × 3 table: Pearson χ² | P value | 6.147430524e-07 | 6.147430524e-07 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — chisq.test |
| Smokers by group: Cochran-Armitage trend | χ² = z² | 8.224922285 | 8.224922285 | 14.67 | 6 | ✓ | R version 4.3.3 (2024-02-29) — prop.trend.test |
| Smokers by group: Cochran-Armitage trend | P value | 0.004131897478 | 0.004131897478 | 13.97 | 6 | ✓ | R version 4.3.3 (2024-02-29) — prop.trend.test |
| 682 of 925: exact binomial test vs 0.75 | P value | 0.3824915596 | 0.3824915596 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — binom.test |
| 682 of 925: Clopper-Pearson CI | lower | 0.7076682641 | 0.7076682641 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — binom.test |
| 682 of 925: Clopper-Pearson CI | upper | 0.7654065582 | 0.7654065582 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — binom.test |
| 682 of 925: Wilson CI | lower | 0.7079959876 | 0.7079959876 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — prop.test(correct = FALSE) |
| 682 of 925: Wilson CI | upper | 0.764635801 | 0.764635801 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — prop.test(correct = FALSE) |
| 682 of 925: Jeffreys CI | lower | 0.7082258165 | 0.7082258165 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — qbeta |
| 682 of 925: Jeffreys CI | upper | 0.7648864607 | 0.7648864607 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — qbeta |
| UCB admissions: Cochran-Mantel-Haenszel | CMH χ² | 1.52460666 | 1.52460666 | 14.54 | 6 | ✓ | R version 4.3.3 (2024-02-29) — mantelhaen.test |
| UCB admissions: Cochran-Mantel-Haenszel | P value | 0.2169236971 | 0.2169236971 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — mantelhaen.test |
| UCB admissions: Cochran-Mantel-Haenszel | MH odds ratio | 0.9046968283 | 0.9046968283 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — mantelhaen.test |
| UCB admissions: Cochran-Mantel-Haenszel | CI lower (Robins-Breslow-Greenland) | 0.7719073618 | 0.7719073618 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — mantelhaen.test |
| UCB admissions: Cochran-Mantel-Haenszel | CI upper | 1.060329764 | 1.060329764 | 14.4 | 6 | ✓ | R version 4.3.3 (2024-02-29) — mantelhaen.test |
| 3-category agreement: Cohen's κ | κ | 0.6405228758 | 0.6405228758 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::cohen.kappa |
| 3-category agreement: weighted κ (quadratic) | κw | 0.7416666667 | 0.7416666667 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::cohen.kappa |
| 2 × 2 risk table | Relative risk | 0.5 | 0.5 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — formula |
| 2 × 2 risk table | RR CI lower (Katz log) | 0.2872194531 | 0.2872194531 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — formula |
| 2 × 2 risk table | Odds ratio (sample) | 0.4117647059 | 0.4117647059 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — formula |
| 2 × 2 risk table | Odds ratio (conditional MLE) | 0.4135967427 | 0.4135982522 | 5.44 | 4 | ✓ | fisher.test's uniroot tolerance (≈1e-4) limits R's agreement — R version 4.3.3 (2024-02-29) — fisher.test |
| 2 × 2 risk table | Exact OR CI upper | 0.8664538267 | 0.8664418586 | 4.86 | 4 | ✓ | fisher.test's uniroot tolerance (≈1e-4) limits R's agreement — R version 4.3.3 (2024-02-29) — fisher.test |
| 682 of 925: Agresti-Coull CI | lower | 0.7079790582 | 0.7079790582 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::BinomCI |
| 682 of 925: Agresti-Coull CI | upper | 0.7646527304 | 0.7646527304 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::BinomCI |

### Multiplicity (6/6 passed — LRE min 14.5, median 15.0)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| 10 P values: Bonferroni | all adjusted P values (minimum LRE) | 0.001 | 0.001 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — p.adjust |
| 10 P values: Holm | all adjusted P values (minimum LRE) | 0.001 | 0.001 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — p.adjust |
| 10 P values: Hochberg | all adjusted P values (minimum LRE) | 0.001 | 0.001 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — p.adjust |
| 10 P values: Hommel | all adjusted P values (minimum LRE) | 0.001 | 0.001 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — p.adjust |
| 10 P values: Benjamini-Hochberg (FDR) | all adjusted P values (minimum LRE) | 0.001 | 0.001 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — p.adjust |
| 10 P values: Benjamini-Yekutieli (FDR, any dependence) | all adjusted P values (minimum LRE) | 0.002928968254 | 0.002928968254 | 14.46 | 6 | ✓ | R version 4.3.3 (2024-02-29) — p.adjust |

### Survival analysis (35/35 passed — LRE min 3.1, median 14.8)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| aml: log-rank | χ² | 3.396388699 | 3.396388699 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — survival::survdiff |
| aml: Kaplan-Meier median (Maintained) | Median | 31 | 31 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — survival::survfit |
| aml: Kaplan-Meier median (Nonmaintained) | Median | 23 | 23 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — survival::survfit |
| aml: Peto-Peto / Fleming-Harrington G(1,0) | χ² | 2.779279545 | 2.779279545 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — survdiff(rho = 1) |
| aml: RMST up to 40 (Maintained) | RMST | 28.89772727 | 28.89772727 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — print.survfit(rmean = 40) |
| aml: RMST up to 40 (Maintained) | SE | 3.467577679 | 3.467577679 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — print.survfit(rmean = 40) |
| aml: RMST up to 40 (Nonmaintained) | RMST | 21.93055556 | 21.93055556 | 14.71 | 6 | ✓ | R version 4.3.3 (2024-02-29) — print.survfit(rmean = 40) |
| aml: RMST up to 40 (Nonmaintained) | SE | 3.835641163 | 3.835641163 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — print.survfit(rmean = 40) |
| aml: Cox regression (Efron ties) | β | -0.915532575 | -0.915532575 | 13.22 | 5 | ✓ | Newton-Raphson — R version 4.3.3 (2024-02-29) — survival::coxph |
| aml: Cox regression (Efron ties) | SE | 0.5119342752 | 0.5119342752 | 14.06 | 5 | ✓ | R version 4.3.3 (2024-02-29) — survival::coxph |
| aml: Cox regression (Efron ties) | Wald P | 0.07371486064 | 0.07371486064 | 12.69 | 5 | ✓ | R version 4.3.3 (2024-02-29) — survival::coxph |
| aml: Tarone-Ware | χ² | 2.981603622 | 2.981603622 | 15 | 6 | ✓ | hypergeometric variance (Klein & Moeschberger 7.3) — R version 4.3.3 (2024-02-29) — independent R implementation |
| aml: Peto-Peto | χ² | 2.70803502 | 2.70803502 | 14.88 | 6 | ✓ | hypergeometric variance (Klein & Moeschberger 7.3) — R version 4.3.3 (2024-02-29) — independent R implementation |
| aml: Gehan-Breslow-Wilcoxon | χ² | 2.723311547 | 2.723311547 | 15 | 6 | ✓ | hypergeometric variance (Klein & Moeschberger 7.3) — R version 4.3.3 (2024-02-29) — independent R implementation |
| simulated competing risks: cumulative incidence at t = 2 | CIF | 0.1 | 0.1 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — cmprsk::cuminc |
| simulated competing risks: cumulative incidence at t = 5 | CIF | 0.2 | 0.2 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — cmprsk::cuminc |
| simulated competing risks: cumulative incidence at t = 10 | CIF | 0.4461533038 | 0.4461533038 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — cmprsk::cuminc |
| simulated competing risks: cumulative incidence at t = 20 | CIF | 0.5951200586 | 0.5951200586 | 14.77 | 6 | ✓ | R version 4.3.3 (2024-02-29) — cmprsk::cuminc |
| simulated 3 groups (tied times): Gray's test, event of interest | χ² | 9.343687871 | 9.336687631 | 3.13 | 3 | ✓ | many ties (times rounded to 0.1); tie correction differs slightly from cmprsk's unpublished rule — R version 4.3.3 (2024-02-29) — cmprsk::cuminc |
| simulated 3 groups (tied times): Gray's test, competing event | χ² | 4.019512658 | 4.017989079 | 3.42 | 3 | ✓ | many ties (times rounded to 0.1); tie correction differs slightly from cmprsk's unpublished rule — R version 4.3.3 (2024-02-29) — cmprsk::cuminc |
| simulated 3 groups (no ties): Gray's test, event of interest | χ² | 9.319744259 | 9.319744259 | 15 | 9 | ✓ | R version 4.3.3 (2024-02-29) — cmprsk::cuminc |
| simulated 3 groups (no ties): Gray's test, competing event | χ² | 4.005976834 | 4.005976834 | 14.45 | 9 | ✓ | R version 4.3.3 (2024-02-29) — cmprsk::cuminc |
| Fine-Gray (cause 1): x | β | 0.05322693935 | 0.05322693935 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — cmprsk::crr |
| Fine-Gray (cause 1): x | robust SE | 0.1094900063 | 0.1094900063 | 14.42 | 6 | ✓ | sandwich incl. censoring term — R version 4.3.3 (2024-02-29) — cmprsk::crr |
| Fine-Gray (cause 1): g1 | β | 0.5402239107 | 0.5402239107 | 14.13 | 6 | ✓ | R version 4.3.3 (2024-02-29) — cmprsk::crr |
| Fine-Gray (cause 1): g1 | robust SE | 0.2629775894 | 0.2629775894 | 15 | 6 | ✓ | sandwich incl. censoring term — R version 4.3.3 (2024-02-29) — cmprsk::crr |
| Fine-Gray (cause 1): g2 | β | -0.2097908429 | -0.2097908429 | 14 | 6 | ✓ | R version 4.3.3 (2024-02-29) — cmprsk::crr |
| Fine-Gray (cause 1): g2 | robust SE | 0.2920782039 | 0.2920782039 | 14.64 | 6 | ✓ | sandwich incl. censoring term — R version 4.3.3 (2024-02-29) — cmprsk::crr |
| Fine-Gray (cause 2): x | β | -0.04378300636 | -0.0437830064 | 9.12 | 6 | ✓ | R version 4.3.3 (2024-02-29) — cmprsk::crr |
| Fine-Gray (cause 2): x | robust SE | 0.1312595893 | 0.1312595893 | 9.43 | 6 | ✓ | sandwich incl. censoring term — R version 4.3.3 (2024-02-29) — cmprsk::crr |
| Fine-Gray (cause 2): g1 | β | -0.4763134952 | -0.4763134721 | 7.31 | 6 | ✓ | R version 4.3.3 (2024-02-29) — cmprsk::crr |
| Fine-Gray (cause 2): g1 | robust SE | 0.3957302434 | 0.3957302405 | 8.14 | 6 | ✓ | sandwich incl. censoring term — R version 4.3.3 (2024-02-29) — cmprsk::crr |
| Fine-Gray (cause 2): g2 | β | 0.3246434453 | 0.3246434466 | 8.37 | 6 | ✓ | R version 4.3.3 (2024-02-29) — cmprsk::crr |
| Fine-Gray (cause 2): g2 | robust SE | 0.3171081943 | 0.3171081956 | 8.38 | 6 | ✓ | sandwich incl. censoring term — R version 4.3.3 (2024-02-29) — cmprsk::crr |
| Fine-Gray (cause 1) | pseudo log-likelihood | -380.2605808 | -380.2605808 | 15 | 9 | ✓ | R version 4.3.3 (2024-02-29) — cmprsk::crr |

### Reliability and agreement (19/19 passed — LRE min 14.5, median 15.0)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| Shrout & Fleiss data: ICC1 | ICC | 0.1657417684 | 0.1657417684 | 14.55 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::ICC |
| Shrout & Fleiss data: ICC1 | 95% CI lower | -0.1329323249 | -0.1329323249 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::ICC |
| Shrout & Fleiss data: ICC1 | 95% CI upper | 0.7225600623 | 0.7225600623 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::ICC |
| Shrout & Fleiss data: ICC2 | ICC | 0.2897637795 | 0.2897637795 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::ICC |
| Shrout & Fleiss data: ICC2 | 95% CI lower | 0.01878651337 | 0.01878651337 | 14.83 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::ICC |
| Shrout & Fleiss data: ICC2 | 95% CI upper | 0.7610843696 | 0.7610843696 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::ICC |
| Shrout & Fleiss data: ICC3 | ICC | 0.7148407148 | 0.7148407148 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::ICC |
| Shrout & Fleiss data: ICC3 | 95% CI lower | 0.342464765 | 0.342464765 | 14.47 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::ICC |
| Shrout & Fleiss data: ICC3 | 95% CI upper | 0.94585826 | 0.94585826 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::ICC |
| Shrout & Fleiss data: ICC1k | ICC | 0.4427971337 | 0.4427971337 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::ICC |
| Shrout & Fleiss data: ICC1k | 95% CI lower | -0.8844421552 | -0.8844421552 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::ICC |
| Shrout & Fleiss data: ICC1k | 95% CI upper | 0.9124154203 | 0.9124154203 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::ICC |
| Shrout & Fleiss data: ICC2k | ICC | 0.6200505476 | 0.6200505476 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::ICC |
| Shrout & Fleiss data: ICC2k | 95% CI lower | 0.0711368153 | 0.0711368153 | 14.86 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::ICC |
| Shrout & Fleiss data: ICC2k | 95% CI upper | 0.9272320402 | 0.9272320402 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::ICC |
| Shrout & Fleiss data: ICC3k | ICC | 0.9093155424 | 0.9093155424 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::ICC |
| Shrout & Fleiss data: ICC3k | 95% CI lower | 0.6756747138 | 0.6756747138 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::ICC |
| Shrout & Fleiss data: ICC3k | 95% CI upper | 0.9858916782 | 0.9858916782 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::ICC |
| Shrout & Fleiss data | Cronbach's α | 0.9093155424 | 0.9093155424 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — psych::alpha |

### Meta-analysis (25/25 passed — LRE min 4.1, median 14.5)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| BCG vaccine trials (log RR): REML | Pooled log RR | -0.7145323484 | -0.7145323422 | 8.06 | 5 | ✓ | iterative τ² estimator — R version 4.3.3 (2024-02-29) — metafor::rma |
| BCG vaccine trials (log RR): REML | SE | 0.1797815318 | 0.1797815161 | 7.06 | 5 | ✓ | iterative τ² estimator — R version 4.3.3 (2024-02-29) — metafor::rma |
| BCG vaccine trials (log RR): REML | τ² | 0.313243326 | 0.3132432581 | 6.66 | 5 | ✓ | iterative τ² estimator — R version 4.3.3 (2024-02-29) — metafor::rma |
| BCG vaccine trials (log RR): REML | Q | 152.2330081 | 152.2330081 | 14.58 | 6 | ✓ | R version 4.3.3 (2024-02-29) — metafor::rma |
| BCG vaccine trials (log RR): REML | I² (τ²-based, as metafor) | 92.22138607 | 92.22138452 | 7.77 | 5 | ✓ | R version 4.3.3 (2024-02-29) — metafor::rma |
| BCG vaccine trials (log RR): DL | Pooled log RR | -0.7141172221 | -0.7141172221 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — metafor::rma |
| BCG vaccine trials (log RR): DL | SE | 0.1787420895 | 0.1787420895 | 14.96 | 6 | ✓ | R version 4.3.3 (2024-02-29) — metafor::rma |
| BCG vaccine trials (log RR): DL | τ² | 0.3087602629 | 0.3087602629 | 14.9 | 6 | ✓ | R version 4.3.3 (2024-02-29) — metafor::rma |
| BCG vaccine trials (log RR): DL | Q | 152.2330081 | 152.2330081 | 14.58 | 6 | ✓ | R version 4.3.3 (2024-02-29) — metafor::rma |
| BCG vaccine trials (log RR): DL | I² (τ²-based, as metafor) | 92.11734685 | 92.11734685 | 15 | 5 | ✓ | R version 4.3.3 (2024-02-29) — metafor::rma |
| BCG vaccine trials (log RR): PM | Pooled log RR | -0.7149704056 | -0.7149681535 | 5.5 | 3 | ✓ | metafor solves the PM equation to a tolerance of ~1e-5; see the exact check below — R version 4.3.3 (2024-02-29) — metafor::rma |
| BCG vaccine trials (log RR): PM | SE | 0.1808979841 | 0.1808921915 | 4.49 | 3 | ✓ | metafor solves the PM equation to a tolerance of ~1e-5; see the exact check below — R version 4.3.3 (2024-02-29) — metafor::rma |
| BCG vaccine trials (log RR): PM | τ² | 0.3180937119 | 0.3180684522 | 4.1 | 3 | ✓ | metafor solves the PM equation to a tolerance of ~1e-5; see the exact check below — R version 4.3.3 (2024-02-29) — metafor::rma |
| BCG: Paule-Mandel estimating equation | |Q(τ̂²) − (k − 1)| | 0 | 1.776356839e-15 | 14.75 | 10 | ✓ | evaluated independently in exact or 50-digit arithmetic — defining equation (independent exact computation) |
| BCG vaccine trials (log RR): PM | Q | 152.2330081 | 152.2330081 | 14.58 | 6 | ✓ | R version 4.3.3 (2024-02-29) — metafor::rma |
| BCG vaccine trials (log RR): PM | I² (τ²-based, as metafor) | 92.33090029 | 92.33033795 | 5.22 | 5 | ✓ | R version 4.3.3 (2024-02-29) — metafor::rma |
| BCG vaccine trials (log RR): FIXED | Pooled log RR | -0.4302851637 | -0.4302851637 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — metafor::rma |
| BCG vaccine trials (log RR): FIXED | SE | 0.04049875171 | 0.04049875171 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — metafor::rma |
| BCG vaccine trials (log RR): FIXED | Q | 152.2330081 | 152.2330081 | 14.58 | 6 | ✓ | R version 4.3.3 (2024-02-29) — metafor::rma |
| BCG: REML with Hartung-Knapp | SE | 0.1807917455 | 0.1807917441 | 8.1 | 5 | ✓ | R version 4.3.3 (2024-02-29) — metafor::rma(test = 'knha') |
| BCG: REML with Hartung-Knapp | P value | 0.001920015085 | 0.001920015096 | 8.24 | 5 | ✓ | R version 4.3.3 (2024-02-29) — metafor::rma(test = 'knha') |
| BCG: REML prediction interval (normal quantile) | lower (RR scale) | 0.1546342935 | 0.1546343134 | 6.89 | 5 | ✓ | R version 4.3.3 (2024-02-29) — metafor::predict |
| BCG: REML prediction interval (normal quantile) | upper (RR scale) | 1.549028019 | 1.549027839 | 6.93 | 5 | ✓ | R version 4.3.3 (2024-02-29) — metafor::predict |
| BCG: Egger's regression test | t (intercept) | -1.401282002 | -1.401282002 | 14.54 | 6 | ✓ | R version 4.3.3 (2024-02-29) — metafor::regtest(model = 'lm') |
| BCG: Egger's regression test | P value | 0.1887069951 | 0.1887069951 | 14.53 | 6 | ✓ | R version 4.3.3 (2024-02-29) — metafor::regtest(model = 'lm') |

### Circular statistics (5/5 passed — LRE min 1.0, median 13.8)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| von Mises sample: mean direction | degrees | 65.50837623 | 65.50837623 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — circular::mean.circular |
| von Mises sample: mean resultant length | R̄ | 0.7053094196 | 0.7053094196 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — circular::rho.circular |
| von Mises sample: Rayleigh test | P value | 7.85295358e-07 | 7.101316019e-07 | 1.02 | 0.9 | ✓ | two different asymptotic approximations (Zar 2010 vs Greenwood & Durand); they differ only far out in the tail (P ≈ 1e-6 here) — R version 4.3.3 (2024-02-29) — circular::rayleigh.test |
| two samples: Watson-Williams (Zar 2010 form) | F | 0.7080059613 | 0.7080059613 | 13.75 | 6 | ✓ | κ from the within-sample mean resultant length, exact ML (Bessel ratio inverted with uniroot) — R version 4.3.3 (2024-02-29) — besselI + uniroot + formula |
| two samples: Watson-Williams vs circular package | F | 0.7098981135 | 0.7080059613 | 2.57 | 2 | ✓ | circular::watson.williams.test estimates κ from the pooled sample with the Best-Fisher approximation (a different published variant) — R version 4.3.3 (2024-02-29) — circular::watson.williams.test |

### Multivariate (5/5 passed — LRE min 13.2, median 13.6)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| iris: MANOVA | Pillai's trace | 1.132489304 | 1.132489304 | 13.86 | 6 | ✓ | R version 4.3.3 (2024-02-29) — summary.manova |
| iris: MANOVA | Pillai approx. F | 63.53175783 | 63.53175783 | 13.63 | 6 | ✓ | R version 4.3.3 (2024-02-29) — summary.manova |
| iris: MANOVA | Wilks' Λ | 0.03154590103 | 0.03154590103 | 13.15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — summary.manova |
| iris: MANOVA | Wilks approx. F | 223.7959509 | 223.7959509 | 13.38 | 6 | ✓ | R version 4.3.3 (2024-02-29) — summary.manova |
| iris: Ward hierarchical clustering, k = 3 | cluster sizes [30, 49, 71] | 30 | 30 | 15 | 6 | ✓ | R: [30, 49, 71] — R version 4.3.3 (2024-02-29) — hclust(ward.D2) |

### Time series and trends (5/5 passed — LRE min 2.5, median 14.8)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| Nile: Ljung-Box (10 lags) | Q | 88.12687155 | 88.12687155 | 14.79 | 6 | ✓ | R version 4.3.3 (2024-02-29) — Box.test |
| Nile: Ljung-Box (10 lags) | P value | 1.254552018e-14 | 1.258632767e-14 | 2.49 | 2 | ✓ | R's Box.test computes 1 − pchisq(Q), which cancels at P ≈ 1e-14; see the exact check — R version 4.3.3 (2024-02-29) — Box.test |
| Nile: Ljung-Box P value vs closed-form χ²(10) tail in 50-digit arithmetic | relative error | 0 | 0 | 15 | 12 | ✓ | evaluated independently in exact or 50-digit arithmetic — defining equation (independent exact computation) |
| Nile: Mann-Kendall | Kendall τ (tie-adjusted) | -0.2807413347 | -0.2807413347 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — cor.test(method = 'kendall') |
| Nile: Mann-Kendall | P value | 3.658262922e-05 | 3.658262922e-05 | 14.45 | 6 | ✓ | R version 4.3.3 (2024-02-29) — cor.test(exact = FALSE, continuity = TRUE) |

### Mixed models (22/22 passed — LRE min 3.3, median 4.7)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| Orthodont: random intercept (REML) | Residual SD | 1.441688693 | 1.441679124 | 5.18 | 4 | ✓ | REML optimizers differ — R version 4.3.3 (2024-02-29) — nlme::lme |
| Orthodont: random intercept (REML) | Subject SD | 2.113008 | 2.113056634 | 4.64 | 4 | ✓ | R version 4.3.3 (2024-02-29) — nlme::lme |
| Orthodont: random intercept + slope (REML) | Intercept estimate | 15.48974171 | 15.48971067 | 5.7 | 4 | ✓ | REML optimizers differ — R version 4.3.3 (2024-02-29) — nlme::lme |
| Orthodont: random intercept + slope (REML) | Intercept SE | 0.9442533291 | 0.9442864217 | 4.46 | 4 | ✓ | GLS covariance (X'V⁻¹X)⁻¹ given the variance components — R version 4.3.3 (2024-02-29) — nlme::lme |
| Orthodont: random intercept + slope (REML) | age estimate | 0.6601851852 | 0.6601851852 | 14.15 | 4 | ✓ | REML optimizers differ — R version 4.3.3 (2024-02-29) — nlme::lme |
| Orthodont: random intercept + slope (REML) | age SE | 0.07125183043 | 0.07125327539 | 4.69 | 4 | ✓ | GLS covariance (X'V⁻¹X)⁻¹ given the variance components — R version 4.3.3 (2024-02-29) — nlme::lme |
| Orthodont: random intercept + slope (REML) | male estimate | 2.145435856 | 2.145488249 | 4.61 | 4 | ✓ | REML optimizers differ — R version 4.3.3 (2024-02-29) — nlme::lme |
| Orthodont: random intercept + slope (REML) | male SE | 0.7574290255 | 0.7574534542 | 4.49 | 4 | ✓ | GLS covariance (X'V⁻¹X)⁻¹ given the variance components — R version 4.3.3 (2024-02-29) — nlme::lme |
| Orthodont: random intercept + slope (REML) | SD of random intercepts | 2.7966864 | 2.797020772 | 3.92 | 3 | ✓ | R version 4.3.3 (2024-02-29) — nlme::lme |
| Orthodont: random intercept + slope (REML) | SD of random slopes | 0.2264063 | 0.2264278964 | 4.02 | 3 | ✓ | R version 4.3.3 (2024-02-29) — nlme::lme |
| Orthodont: random intercept + slope (REML) | Residual SD | 1.31007203 | 1.310039676 | 4.61 | 4 | ✓ | R version 4.3.3 (2024-02-29) — nlme::lme |
| Orthodont: random intercept + slope (REML) | REML log likelihood | -217.6169288 | -217.6169287 | 9.42 | 5 | ✓ | R version 4.3.3 (2024-02-29) — nlme::lme |
| Orthodont random slope: Satterthwaite df | Intercept df | 33.96136419 | 33.96060863 | 4.65 | 4 | ✓ | numerical derivatives of the REML likelihood in both programs — R version 4.3.3 (2024-02-29) — lmerTest::lmer |
| Orthodont random slope: Satterthwaite P | Intercept P value | 1.040314774e-17 | 1.040826558e-17 | 3.31 | 3 | ✓ | P ≈ 1e-9…1e-17: far in the tail a tiny df difference changes P's later digits — R version 4.3.3 (2024-02-29) — lmerTest::lmer |
| Orthodont random slope: Satterthwaite df | age df | 25.99999533 | 25.99930205 | 4.57 | 4 | ✓ | numerical derivatives of the REML likelihood in both programs — R version 4.3.3 (2024-02-29) — lmerTest::lmer |
| Orthodont random slope: Satterthwaite P | age P value | 1.013243847e-09 | 1.013494249e-09 | 3.61 | 3 | ✓ | P ≈ 1e-9…1e-17: far in the tail a tiny df difference changes P's later digits — R version 4.3.3 (2024-02-29) — lmerTest::lmer |
| Orthodont random slope: Satterthwaite df | male df | 25.0000087 | 25.00002843 | 6.1 | 4 | ✓ | numerical derivatives of the REML likelihood in both programs — R version 4.3.3 (2024-02-29) — lmerTest::lmer |
| Orthodont random slope: Satterthwaite P | male P value | 0.008995398076 | 0.008995411234 | 5.83 | 3 | ✓ | P ≈ 1e-9…1e-17: far in the tail a tiny df difference changes P's later digits — R version 4.3.3 (2024-02-29) — lmerTest::lmer |
| Orthodont: F test of age (4-level factor) | F | 38.03960823 | 38.03963333 | 6.18 | 4 | ✓ | R version 4.3.3 (2024-02-29) — lmerTest anova (Satterthwaite) |
| Orthodont: F test of age (4-level factor) | denominator df | 78.00000003 | 78.00011889 | 5.82 | 4 | ✓ | Fai & Cornelius multi-df Satterthwaite — R version 4.3.3 (2024-02-29) — lmerTest anova (Satterthwaite) |
| Orthodont: F test of male (1 df) | F | 9.292098823 | 9.292079696 | 5.69 | 4 | ✓ | R version 4.3.3 (2024-02-29) — lmerTest anova (Satterthwaite) |
| Orthodont: F test of male (1 df) | denominator df | 24.99999992 | 24.99993712 | 5.6 | 4 | ✓ | R version 4.3.3 (2024-02-29) — lmerTest anova (Satterthwaite) |

### Nonparametric post hoc (12/12 passed — LRE min 10.7, median 14.5)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| PlantGrowth: Dunn trt1-ctrl | unadjusted P | 0.2636842679 | 0.2636842679 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::DunnTest |
| PlantGrowth: Dunn trt2-ctrl | unadjusted P | 0.09116394405 | 0.09116394405 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::DunnTest |
| PlantGrowth: Dunn trt2-trt1 | unadjusted P | 0.00500029037 | 0.00500029037 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::DunnTest |
| PlantGrowth: Conover trt1-ctrl | unadjusted P | 0.2159662428 | 0.2159662428 | 14.81 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::ConoverTest |
| PlantGrowth: Conover trt2-ctrl | unadjusted P | 0.06615055954 | 0.06615055954 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::ConoverTest |
| PlantGrowth: Conover trt2-trt1 | unadjusted P | 0.003661154393 | 0.003661154393 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::ConoverTest |
| PlantGrowth: DSCF trt1-ctrl | P (studentized range) | 0.3821062828 | 0.3821062828 | 14.14 | 4 | ✓ | studentized range with infinite df — R version 4.3.3 (2024-02-29) — PMCMRplus::dscfAllPairsTest |
| PlantGrowth: DSCF trt2-ctrl | P (studentized range) | 0.1415864869 | 0.1415864869 | 14.14 | 4 | ✓ | studentized range with infinite df — R version 4.3.3 (2024-02-29) — PMCMRplus::dscfAllPairsTest |
| PlantGrowth: DSCF trt2-trt1 | P (studentized range) | 0.02744973059 | 0.02744973059 | 11.37 | 4 | ✓ | studentized range with infinite df — R version 4.3.3 (2024-02-29) — PMCMRplus::dscfAllPairsTest |
| RoundingTimes: Nemenyi 1 vs 2 | P | 0.637427167 | 0.637427167 | 13.21 | 4 | ✓ | R version 4.3.3 (2024-02-29) — PMCMRplus::frdAllPairsNemenyiTest |
| RoundingTimes: Nemenyi 1 vs 3 | P | 0.004409820445 | 0.004409820445 | 11.97 | 4 | ✓ | R version 4.3.3 (2024-02-29) — PMCMRplus::frdAllPairsNemenyiTest |
| RoundingTimes: Nemenyi 2 vs 3 | P | 0.06137075926 | 0.06137075925 | 10.7 | 4 | ✓ | R version 4.3.3 (2024-02-29) — PMCMRplus::frdAllPairsNemenyiTest |

### Trend tests (2/2 passed — LRE min 14.8, median 14.9)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| three samples (no ties): Jonckheere-Terpstra | two-sided P (normal approx.) | 0.09342320468 | 0.09342320468 | 14.83 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::JonckheereTerpstraTest |
| three samples (no ties): Jonckheere-Terpstra | J statistic | 380 | 380 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::JonckheereTerpstraTest |

### Robust tests (8/8 passed — LRE min 13.8, median 14.6)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| two samples: Yuen-Welch (20% trimming) | |t| | 1.038684611 | 1.038684611 | 14.29 | 6 | ✓ | R version 4.3.3 (2024-02-29) — WRS2::yuen |
| two samples: Yuen-Welch (20% trimming) | df | 17.61510076 | 17.61510076 | 14.62 | 6 | ✓ | R version 4.3.3 (2024-02-29) — WRS2::yuen |
| two samples: Yuen-Welch (20% trimming) | P value | 0.3129997438 | 0.3129997438 | 14.41 | 6 | ✓ | R version 4.3.3 (2024-02-29) — WRS2::yuen |
| two samples: Yuen-Welch (20% trimming) | difference of trimmed means | -0.7452090909 | -0.7452090909 | 14.65 | 6 | ✓ | R version 4.3.3 (2024-02-29) — WRS2::yuen |
| two samples: Yuen-Welch (20% trimming) | 95% CI lower | -2.254889634 | -2.254889634 | 14.93 | 6 | ✓ | R version 4.3.3 (2024-02-29) — WRS2::yuen |
| PlantGrowth: Wilcox t1way (trimmed means) | F | 8.281813787 | 8.281813787 | 14.67 | 6 | ✓ | R version 4.3.3 (2024-02-29) — WRS2::t1way |
| PlantGrowth: Wilcox t1way (trimmed means) | denominator df | 9.639328472 | 9.639328472 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — WRS2::t1way |
| PlantGrowth: Wilcox t1way (trimmed means) | P value | 0.008068687798 | 0.008068687798 | 13.84 | 6 | ✓ | R version 4.3.3 (2024-02-29) — WRS2::t1way |

### Nonparametric two-way ANOVA (3/3 passed — LRE min 14.7, median 15.0)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| ToothGrowth ART: Column factor | F | 17.63409696 | 17.63409696 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — ARTool::art |
| ToothGrowth ART: Row factor | F | 95.56222688 | 95.56222688 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — ARTool::art |
| ToothGrowth ART: Interaction | F | 3.536359619 | 3.536359619 | 14.72 | 6 | ✓ | R version 4.3.3 (2024-02-29) — ARTool::art |

### Agreement and association (21/21 passed — LRE min 10.5, median 15.0)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| 3-category agreement: Unweighted κ 95% CI | lower | 0.5100132717 | 0.5100132717 | 14.96 | 4 | ✓ | asymptotic SE (Fleiss, Cohen & Everitt) — R version 4.3.3 (2024-02-29) — DescTools::CohenKappa |
| 3-category agreement: Unweighted κ 95% CI | upper | 0.7710324799 | 0.7710324799 | 15 | 4 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::CohenKappa |
| 3-category agreement: Unweighted κ | κ | 0.6405228758 | 0.6405228758 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::CohenKappa |
| 3-category agreement: Linear-weighted κ 95% CI | lower | 0.5688008001 | 0.5688008001 | 15 | 4 | ✓ | asymptotic SE (Fleiss, Cohen & Everitt) — R version 4.3.3 (2024-02-29) — DescTools::CohenKappa |
| 3-category agreement: Linear-weighted κ 95% CI | upper | 0.8123873187 | 0.8123873187 | 15 | 4 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::CohenKappa |
| 3-category agreement: Linear-weighted κ | κ | 0.6905940594 | 0.6905940594 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::CohenKappa |
| 3-category agreement: Quadratic-weighted κ (≈ ICC) 95% CI | lower | 0.6154515703 | 0.6154515703 | 15 | 4 | ✓ | asymptotic SE (Fleiss, Cohen & Everitt) — R version 4.3.3 (2024-02-29) — DescTools::CohenKappa |
| 3-category agreement: Quadratic-weighted κ (≈ ICC) 95% CI | upper | 0.867881763 | 0.867881763 | 15 | 4 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::CohenKappa |
| 3-category agreement: Quadratic-weighted κ (≈ ICC) | κ | 0.7416666667 | 0.7416666667 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::CohenKappa |
| sleep: Lin's concordance correlation | ρc | 0.5706176962 | 0.5706176962 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::CCC |
| sleep: Lin's concordance correlation | 95% CI lower (Fisher z) | 0.1514873636 | 0.1514873636 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::CCC |
| sleep: Lin's concordance correlation | 95% CI upper | 0.8158282782 | 0.8158282782 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::CCC |
| Shrout & Fleiss data: Kendall's W (ties corrected) | W | 0.887037037 | 0.887037037 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::KendallW |
| 3 × 3 table: Goodman-Kruskal γ | γ | 0.5608522932 | 0.5608522932 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::GoodmanKruskalGamma |
| 3 × 3 table: Kendall τ-b | τ-b | 0.3940626776 | 0.3940626776 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::KendallTauB |
| 3 × 3 table: G test | G | 33.76370329 | 33.76370329 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::GTest |
| 3 × 3 table: G test | P value | 8.331390159e-07 | 8.331390159e-07 | 10.47 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::GTest |
| 3 × 3 table: G test with Williams' correction | G | 33.18107221 | 33.18107221 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::GTest |
| 3 × 3 paired table: Stuart-Maxwell | χ² | 0.4761904762 | 0.4761904762 | 14.44 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::StuartMaxwellTest |
| UCB admissions: Breslow-Day (Tarone) homogeneity | χ² | 18.82550125 | 18.82550125 | 13.09 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::BreslowDayTest |
| UCB admissions: Breslow-Day (Tarone) homogeneity | P value | 0.002071401398 | 0.002071401398 | 12.19 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::BreslowDayTest |

### Normality, randomness, one-sample (11/11 passed — LRE min 13.4, median 15.0)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| sleep group 2: Jarque-Bera | JB | 0.9350505904 | 0.9350505904 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::JarqueBeraTest |
| sleep group 2: Jarque-Bera | P value | 0.6265508798 | 0.6265508798 | 14.97 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::JarqueBeraTest |
| 31 values: Shapiro-Francia | W' | 0.968530555 | 0.968530555 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::ShapiroFranciaTest |
| 31 values: Shapiro-Francia | P value (Royston) | 0.406660155 | 0.406660155 | 13.43 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::ShapiroFranciaTest |
| Nile: Wald-Wolfowitz runs test (median) | |z| | 4.221374184 | 4.221374184 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::RunsTest |
| Nile: Wald-Wolfowitz runs test (median) | P value | 2.428174732e-05 | 2.428174732e-05 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::RunsTest |
| Nile: von Neumann ratio | ratio | 0.9776376562 | 0.9776376562 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::VonNeumannTest |
| Nile: von Neumann ratio | P value | 2.424375178e-07 | 2.424375178e-07 | 14.26 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::VonNeumannTest |
| sleep group 2: 95% CI of the SD (χ²) | lower | 1.377217173 | 1.377217173 | 14.47 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::VarCI |
| sleep group 2: 95% CI of the SD (χ²) | upper | 3.65532568 | 3.65532568 | 14.87 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::VarCI |
| sleep group 2: sign test vs median 1 | exact P | 0.34375 | 0.34375 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — DescTools::SignTest |

### Diagnostic accuracy (10/10 passed — LRE min 15.0, median 15.0)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| 2 × 2: Sensitivity | estimate | 0.9 | 0.9 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — epiR::epi.tests |
| 2 × 2: Sensitivity (Clopper-Pearson) | CI lower | 0.8237774023 | 0.8237774023 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — epiR::epi.tests |
| 2 × 2: Sensitivity (Clopper-Pearson) | CI upper | 0.9509953108 | 0.9509953108 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — epiR::epi.tests |
| 2 × 2: Specificity | estimate | 0.925 | 0.925 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — epiR::epi.tests |
| 2 × 2: Specificity (Clopper-Pearson) | CI lower | 0.8793157746 | 0.8793157746 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — epiR::epi.tests |
| 2 × 2: Specificity (Clopper-Pearson) | CI upper | 0.9574171963 | 0.9574171963 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — epiR::epi.tests |
| 2 × 2: Positive likelihood ratio LR+ | estimate | 12 | 12 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — epiR::epi.tests |
| 2 × 2: Positive likelihood ratio LR+ | CI lower (log method) | 7.343591234 | 7.343591234 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — epiR::epi.tests |
| 2 × 2: Negative likelihood ratio LR− | estimate | 0.1081081081 | 0.1081081081 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — epiR::epi.tests |
| 2 × 2: Negative likelihood ratio LR− | CI lower (log method) | 0.05996851773 | 0.05996851773 | 15 | 6 | ✓ | R version 4.3.3 (2024-02-29) — epiR::epi.tests |

### Power and sample size (5/5 passed — LRE min 6.1, median 10.4)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| two-sample t test, n = 20, δ = 1, σ = 1.5 | Power | 0.5377868467 | 0.5377868467 | 11.87 | 6 | ✓ | both rejection tails (strict = TRUE) — R version 4.3.3 (2024-02-29) — power.t.test |
| one-way ANOVA, 4 groups, n = 5, f = 0.5 | Power | 0.3535594238 | 0.3535594237 | 9.58 | 6 | ✓ | R version 4.3.3 (2024-02-29) — power.anova.test |
| log-rank, HR 0.5, 80% power, α 0.05 (Schoenfeld) | events (exact) | 65.34565926 | 65.34565926 | 15 | 6 | ✓ | closed form 4(z₀.₉₇₅ + z₀.₈)² / ln(HR)² = 65.35 → 66 events (Collett 2015) — R version 4.3.3 (2024-02-29) — textbook formula |
| McNemar, p10 0.15 vs p01 0.05, 90% power (Connor) | pairs (exact) | 205.9620841 | 205.9620841 | 10.45 | 6 | ✓ | Connor (1987) formula — R version 4.3.3 (2024-02-29) — textbook formula |
| two-sample t test, power 0.8: n per group | n (exact, before rounding up) | 36.30565846 | 36.30568708 | 6.1 | 4 | ✓ | R's uniroot tolerance — R version 4.3.3 (2024-02-29) — power.t.test |


## Statistical calibration (Monte-Carlo)

### Type I error (α = 0.05) (17/17 passed)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| Student t test (normal, equal SD) | rejection rate under H0 | 0.05 | 0.0555 |  | 0.035–0.067 | ✓ | Monte-Carlo, 2000 samples, seed 20251102 |
| Welch t test (SDs 1 vs 4, n 8 vs 20) | rejection rate under H0 | 0.05 | 0.053 |  | 0.035–0.067 | ✓ | Monte-Carlo, 2000 samples, seed 20251102 |
| Mann-Whitney, exact (exponential data) | rejection rate under H0 | 0.05 | 0.046 |  | ≤ 0.067 | ✓ | rank/exact tests are discrete and therefore conservative by design — Monte-Carlo, 2000 samples, seed 20251102 |
| Wilcoxon signed-rank, exact (t₃ differences) | rejection rate under H0 | 0.05 | 0.056 |  | ≤ 0.067 | ✓ | rank/exact tests are discrete and therefore conservative by design — Monte-Carlo, 2000 samples, seed 20251102 |
| One-way ANOVA, 4 groups | rejection rate under H0 | 0.05 | 0.052 |  | 0.035–0.067 | ✓ | Monte-Carlo, 2000 samples, seed 20251102 |
| Kruskal-Wallis (lognormal data) | rejection rate under H0 | 0.05 | 0.0395 |  | ≤ 0.067 | ✓ | rank/exact tests are discrete and therefore conservative by design — Monte-Carlo, 2000 samples, seed 20251102 |
| Fisher's exact test (2 × 25) | rejection rate under H0 | 0.05 | 0.02 |  | ≤ 0.067 | ✓ | rank/exact tests are discrete and therefore conservative by design — Monte-Carlo, 2000 samples, seed 20251102 |
| Chi-square test 2 × 2 (n = 50) | rejection rate under H0 | 0.05 | 0.0495 |  | 0.035–0.067 | ✓ | Monte-Carlo, 2000 samples, seed 20251102 |
| Log-rank test (exponential, censoring) | rejection rate under H0 | 0.05 | 0.0555 |  | 0.035–0.067 | ✓ | Monte-Carlo, 2000 samples, seed 20251102 |
| Shapiro-Wilk on normal data (n = 20) | rejection rate under H0 | 0.05 | 0.044 |  | 0.035–0.067 | ✓ | Monte-Carlo, 2000 samples, seed 20251102 |
| Pearson correlation test (n = 15) | rejection rate under H0 | 0.05 | 0.047 |  | 0.035–0.067 | ✓ | Monte-Carlo, 2000 samples, seed 20251102 |
| Friedman test (10 × 3) | rejection rate under H0 | 0.05 | 0.0495 |  | ≤ 0.067 | ✓ | rank/exact tests are discrete and therefore conservative by design — Monte-Carlo, 2000 samples, seed 20251102 |
| Poisson GLM Wald test of a null slope | rejection rate under H0 | 0.05 | 0.0495 |  | 0.035–0.067 | ✓ | Monte-Carlo, 2000 samples, seed 20251102 |
| Yuen trimmed-means test (t₂ heavy tails) | rejection rate under H0 | 0.05 | 0.0495 |  | 0.035–0.067 | ✓ | Monte-Carlo, 2000 samples, seed 20251102 |
| Jonckheere-Terpstra (no trend) | rejection rate under H0 | 0.05 | 0.0495 |  | 0.035–0.067 | ✓ | Monte-Carlo, 2000 samples, seed 20251102 |
| Cochran-Mantel-Haenszel (3 strata, OR = 1) | rejection rate under H0 | 0.05 | 0.048 |  | 0.035–0.067 | ✓ | Monte-Carlo, 2000 samples, seed 20251102 |
| Gray's test, 2 groups × 30, unequal censoring | rejection rate under H0 | 0.05 | 0.049 |  | 0.035–0.067 | ✓ | asymptotic χ² test — Monte-Carlo, 2000 samples, seed 20251102 |

### Confidence-interval coverage (95%) (7/7 passed)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| t interval of a mean (n = 9) | coverage of the true value | 0.95 | 0.954 |  | 0.933–0.966 | ✓ | Monte-Carlo, 2000 samples, seed 20251102 |
| Wilson interval, p = 0.1, n = 40 | coverage of the true value | 0.95 | 0.954 |  | 0.933–0.966 | ✓ | Monte-Carlo, 2000 samples, seed 20251102 |
| Cohen's d, noncentral-t interval (n = 15 + 15) | coverage of the true value | 0.95 | 0.9435 |  | 0.933–0.966 | ✓ | Monte-Carlo, 2000 samples, seed 20251102 |
| Michaelis-Menten K, asymptotic interval (7 points) | coverage of the true value | 0.95 | 0.942 |  | 0.933–0.966 | ✓ | asymptotic method: small departures from 95% are expected — Monte-Carlo, 2000 samples, seed 20251102 |
| linear-regression slope (10 points) | coverage of the true value | 0.95 | 0.9485 |  | 0.933–0.966 | ✓ | Monte-Carlo, 2000 samples, seed 20251102 |
| ICC(1) interval, 20 subjects × 3 raters | coverage of the true value | 0.95 | 0.951 |  | 0.933–0.966 | ✓ | Monte-Carlo, 2000 samples, seed 20251102 |
| Clopper-Pearson exact interval, p = 0.1, n = 40 | coverage of the true value | 0.95 | 0.981 |  | ≥ 0.933 | ✓ | exact interval: guaranteed coverage ≥ 95% (conservative) — Monte-Carlo, 2000 samples, seed 20251102 |

### Power calculation vs simulation (1/1 passed)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| two-sample t test, n = 20, δ = 1, σ = 1.5 | simulated power | 0.5377868467 | 0.5385 |  | 0.501–0.575 | ✓ | calculated power 0.5378 — Monte-Carlo, 2000 samples, seed 20251102 |


## Reproducibility and invariance

### Reproducibility (20/20 passed)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| descriptive | bit-identical output when repeated (same process) | 1 | 1 |  | identical | ✓ | repeat |
| t test | bit-identical output when repeated (same process) | 1 | 1 |  | identical | ✓ | repeat |
| Mann-Whitney exact | bit-identical output when repeated (same process) | 1 | 1 |  | identical | ✓ | repeat |
| one-way ANOVA + Tukey | bit-identical output when repeated (same process) | 1 | 1 |  | identical | ✓ | repeat |
| Dunnett | bit-identical output when repeated (same process) | 1 | 1 |  | identical | ✓ | repeat |
| Kruskal-Wallis | bit-identical output when repeated (same process) | 1 | 1 |  | identical | ✓ | repeat |
| distributions (permutation AD) | bit-identical output when repeated (same process) | 1 | 1 |  | identical | ✓ | repeat |
| trend (permutation JT) | bit-identical output when repeated (same process) | 1 | 1 |  | identical | ✓ | repeat |
| effect sizes (bootstrap) | bit-identical output when repeated (same process) | 1 | 1 |  | identical | ✓ | repeat |
| bootstrap CI | bit-identical output when repeated (same process) | 1 | 1 |  | identical | ✓ | repeat |
| permutation test | bit-identical output when repeated (same process) | 1 | 1 |  | identical | ✓ | repeat |
| Fisher-Freeman-Halton Monte Carlo | bit-identical output when repeated (same process) | 1 | 1 |  | identical | ✓ | repeat |
| linear regression | bit-identical output when repeated (same process) | 1 | 1 |  | identical | ✓ | repeat |
| nonlinear regression | bit-identical output when repeated (same process) | 1 | 1 |  | identical | ✓ | repeat |
| polynomial (exact) | bit-identical output when repeated (same process) | 1 | 1 |  | identical | ✓ | repeat |
| k-means | bit-identical output when repeated (same process) | 1 | 1 |  | identical | ✓ | repeat |
| survival | bit-identical output when repeated (same process) | 1 | 1 |  | identical | ✓ | repeat |
| survival extras | bit-identical output when repeated (same process) | 1 | 1 |  | identical | ✓ | repeat |
| meta-analysis | bit-identical output when repeated (same process) | 1 | 1 |  | identical | ✓ | repeat |
| all 19 analyses above | SHA-256 of full-precision output in a fresh process | 1 | 1 |  | identical | ✓ | digest 2988ac92935dd897… — subprocess |

### Invariance (metamorphic tests) (11/11 passed — LRE min 14.3, median 15.0)

| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |
| t test P after adding 10¹² to every value | agreement of the invariant quantity | 0.766591895 | 0.766591895 | 14.38 | 9 | ✓ | values are entered as exact decimal text; exact decimal centering keeps full precision — metamorphic relation |
| t test P after multiplying by 1000 | agreement of the invariant quantity | 0.766591895 | 0.766591895 | 15 | 9 | ✓ | metamorphic relation |
| t test P after swapping the groups | agreement of the invariant quantity | 0.766591895 | 0.766591895 | 15 | 9 | ✓ | metamorphic relation |
| t test P after shuffling values within groups | agreement of the invariant quantity | 0.766591895 | 0.766591895 | 15 | 9 | ✓ | metamorphic relation |
| ANOVA F after adding 10¹² (exact decimal centering) | agreement of the invariant quantity | 2.013043629 | 2.013043629 | 14.81 | 9 | ✓ | metamorphic relation |
| ANOVA F after reversing group order | agreement of the invariant quantity | 2.013043629 | 2.013043629 | 15 | 9 | ✓ | metamorphic relation |
| Kruskal-Wallis P after a monotone transform (exp) | agreement of the invariant quantity | 0.1812106077 | 0.1812106077 | 15 | 12 | ✓ | rank tests depend only on the ordering — metamorphic relation |
| Pearson r(x, y) = r(y, x) | agreement of the invariant quantity | 0.2363039711 | 0.2363039711 | 15 | 9 | ✓ | metamorphic relation |
| |r| after linear rescaling of both variables | agreement of the invariant quantity | 0.2363039711 | 0.2363039711 | 14.27 | 9 | ✓ | metamorphic relation |
| regression slope scales with Y (×10) | agreement of the invariant quantity | 3.216628384 | 3.216628384 | 15 | 9 | ✓ | metamorphic relation |
| Fisher exact P after swapping rows | agreement of the invariant quantity | 0.002045604764 | 0.002045604764 | 15 | 9 | ✓ | metamorphic relation |

## References

* McCullough, B. D. (1998). Assessing the reliability of statistical software: Part I. *The American Statistician* 52, 358–366.
* McCullough, B. D. (1999). Assessing the reliability of statistical software: Part II. *The American Statistician* 53, 149–159.
* NIST Statistical Reference Datasets, https://www.itl.nist.gov/div898/strd/
* R Core Team. R: A language and environment for statistical computing. R Foundation for Statistical Computing, Vienna.
