"""Additional nonlinear regression equations (brings the library above 100).

Every equation declares a typical X domain used for automatic initial values and
for the self-test that checks each equation can recover its own parameters.
"""
from __future__ import annotations

import numpy as np
from scipy.special import erf, gammaln

from .models import MODELS, _slope_sign, _span, _x_at_half

# ------------------------------------------------------------------ helpers
_ymin = np.nanmin
_ymax = np.nanmax


def _xr(x):
    return max(float(np.nanmax(x) - np.nanmin(x)), 1e-9)


def _k(x, n=3.0):
    return n / _xr(x)


def _xpeak(x, y):
    return float(x[int(np.nanargmax(y))])


def reg(key, name, group, params, formula, f, guess, domain="pos", example=None):
    MODELS[key] = {"key": key, "name": name, "group": group, "params": params, "formula": formula,
                   "f": f, "guess": guess, "domain": domain, "example": example}


def _pos(x):
    return np.clip(x, 1e-300, None)


# ======================================================== Dose-response — stimulation / inhibition
reg("logagonist_ns", "log(agonist) vs. normalized response (Hill slope = 1)", "Dose-response - Stimulation", ["LogEC50"],
    "Y = 100/(1+10^(LogEC50-X))", lambda x, l: 100 / (1 + 10 ** (l - x)), lambda x, y: [_x_at_half(x, y)], "log", [-7])
reg("loginhibitor3", "log(inhibitor) vs. response (three parameters, Hill slope = -1)", "Dose-response - Inhibition",
    ["Bottom", "Top", "LogIC50"], "Y = Bottom + (Top-Bottom)/(1+10^(X-LogIC50))",
    lambda x, b, t, l: b + (t - b) / (1 + 10 ** (x - l)), lambda x, y: [_ymin(y), _ymax(y), _x_at_half(x, y)], "log", [5, 100, -7])
reg("normresponse_inh", "log(inhibitor) vs. normalized response — variable slope", "Dose-response - Inhibition",
    ["LogIC50", "HillSlope"], "Y = 100/(1+10^((X-LogIC50)*HillSlope))",
    lambda x, l, h: 100 / (1 + 10 ** ((x - l) * h)), lambda x, y: [_x_at_half(x, y), 1.0], "log", [-7, 1.2])
reg("normresponse_inh1", "log(inhibitor) vs. normalized response (Hill slope = 1)", "Dose-response - Inhibition", ["LogIC50"],
    "Y = 100/(1+10^(X-LogIC50))", lambda x, l: 100 / (1 + 10 ** (x - l)), lambda x, y: [_x_at_half(x, y)], "log", [-6.5])
reg("inhibitor_conc", "[Inhibitor] vs. response — variable slope (X as concentration)", "Dose-response - Inhibition",
    ["Bottom", "Top", "IC50", "HillSlope"], "Y = Bottom + (Top-Bottom)/(1+(X/IC50)^HillSlope)",
    lambda x, b, t, ic, h: b + (t - b) / (1 + (_pos(x) / abs(ic)) ** h),
    lambda x, y: [_ymin(y), _ymax(y), max(_x_at_half(x, y), 1e-9), 1.0], "pos", [5, 100, 10, 1.3])
reg("agonist_conc3", "[Agonist] vs. response (three parameters, X as concentration)", "Dose-response - Stimulation",
    ["Bottom", "Top", "EC50"], "Y = Bottom + (Top-Bottom)*X/(EC50+X)",
    lambda x, b, t, ec: b + (t - b) * x / (abs(ec) + x), lambda x, y: [_ymin(y), _ymax(y), max(_x_at_half(x, y), 1e-9)], "pos", [2, 90, 8])
reg("loginhibitor5", "Asymmetric sigmoidal inhibition, 5PL (log X)", "Dose-response - Inhibition",
    ["Bottom", "Top", "LogIC50", "HillSlope", "S"], "Y = Bottom + (Top-Bottom)/(1+10^((X-LogIC50)*HillSlope))^S",
    lambda x, b, t, l, h, s: b + (t - b) / (1 + 10 ** ((x - l) * h)) ** s,
    lambda x, y: [_ymin(y), _ymax(y), _x_at_half(x, y), 1.0, 1.0], "log", [5, 100, -7, 1.1, 0.8])
reg("ecanything", "log(agonist) — find ECanything (F = 80 by default; constrain F)", "Dose-response - Special",
    ["Bottom", "Top", "LogECF", "HillSlope", "F"],
    "logEC50 = LogECF - (1/HillSlope)*log10(F/(100-F)); Y = Bottom + (Top-Bottom)/(1+10^((logEC50-X)*HillSlope))",
    lambda x, b, t, lf, h, F: b + (t - b) / (1 + 10 ** ((lf - (1 / h) * np.log10(np.clip(F, 1e-6, 99.999) / (100 - np.clip(F, 1e-6, 99.999))) - x) * h)),
    lambda x, y: [_ymin(y), _ymax(y), _x_at_half(x, y) + 0.3, 1.0, 80.0], "log", None)
reg("gaddum_schild", "Gaddum/Schild EC50 shift (fixed antagonist; constrain Antag)", "Dose-response - Special",
    ["Bottom", "Top", "LogEC50", "HillSlope", "pA2", "Antag"],
    "EC50' = 10^LogEC50*(1+(Antag/10^-pA2)); Y = Bottom + (Top-Bottom)/(1+(EC50'/10^X)^HillSlope)",
    lambda x, b, t, l, h, pa2, ant: b + (t - b) / (1 + ((10 ** l * (1 + np.abs(ant) / 10 ** (-pa2))) / 10 ** x) ** h),
    lambda x, y: [_ymin(y), _ymax(y), _x_at_half(x, y) - 1, 1.0, 8.0, 1e-8], "log", None)

# ======================================================== Enzyme kinetics
reg("mm_baseline", "Michaelis-Menten with baseline", "Enzyme kinetics", ["Vmax", "Km", "Baseline"], "Y = Baseline + Vmax*X/(Km+X)",
    lambda x, v, k, b: b + v * x / (k + x), lambda x, y: [_span(y), max(_x_at_half(x, y), 1e-9), _ymin(y)], "pos", [100, 5, 10])
reg("noncomp_fixed", "Noncompetitive inhibition at fixed [I] (constrain I)", "Enzyme kinetics", ["Vmax", "Km", "Ki", "I"],
    "Y = Vmax/(1+I/Ki)*X/(Km+X)", lambda x, v, k, ki, i: v / (1 + abs(i) / abs(ki)) * x / (k + x),
    lambda x, y: [_ymax(y) * 2, max(_x_at_half(x, y), 1e-9), 1.0, 1.0], "pos", None)
reg("comp_fixed", "Competitive inhibition at fixed [I] (constrain I)", "Enzyme kinetics", ["Vmax", "Km", "Ki", "I"],
    "Y = Vmax*X/(Km*(1+I/Ki)+X)", lambda x, v, k, ki, i: v * x / (k * (1 + abs(i) / abs(ki)) + x),
    lambda x, y: [_ymax(y) * 1.2, max(_x_at_half(x, y), 1e-9) / 2, 1.0, 1.0], "pos", None)
reg("uncomp_fixed", "Uncompetitive inhibition at fixed [I] (constrain I)", "Enzyme kinetics", ["Vmax", "Km", "Ki", "I"],
    "Y = Vmax*X/(Km+X*(1+I/Ki))", lambda x, v, k, ki, i: v * x / (k + x * (1 + abs(i) / abs(ki))),
    lambda x, y: [_ymax(y) * 2, max(_x_at_half(x, y), 1e-9), 1.0, 1.0], "pos", None)
reg("mixed_fixed", "Mixed-model inhibition at fixed [I] (constrain I)", "Enzyme kinetics", ["Vmax", "Km", "Ki", "Alpha", "I"],
    "VmaxApp=Vmax/(1+I/(Alpha*Ki)); KmApp=Km*(1+I/Ki)/(1+I/(Alpha*Ki)); Y=VmaxApp*X/(KmApp+X)",
    lambda x, v, k, ki, a, i: (v / (1 + abs(i) / (abs(a) * abs(ki)))) * x / (k * (1 + abs(i) / abs(ki)) / (1 + abs(i) / (abs(a) * abs(ki))) + x),
    lambda x, y: [_ymax(y) * 2, max(_x_at_half(x, y), 1e-9), 1.0, 1.0, 1.0], "pos", None)
reg("hill_baseline", "Allosteric sigmoidal with baseline", "Enzyme kinetics", ["Vmax", "Khalf", "h", "Baseline"],
    "Y = Baseline + Vmax*X^h/(Khalf^h + X^h)", lambda x, v, k, h, b: b + v * _pos(x) ** h / (abs(k) ** h + _pos(x) ** h),
    lambda x, y: [_span(y), max(_x_at_half(x, y), 1e-9), 1.0, _ymin(y)], "pos", [80, 6, 2, 5])
reg("substrate_depletion_rate", "Michaelis-Menten (kcat form with enzyme concentration, constrain Et)", "Enzyme kinetics",
    ["kcat", "Km", "Et"], "Y = Et*kcat*X/(Km+X)", lambda x, kc, k, et: et * kc * x / (k + x),
    lambda x, y: [_ymax(y) * 1.1, max(_x_at_half(x, y), 1e-9), 1.0], "pos", None)

# ======================================================== Binding
reg("onesite_ns", "One site — nonspecific binding only (line through origin)", "Binding - Saturation", ["NS"], "Y = NS*X",
    lambda x, ns: ns * x, lambda x, y: [float(np.nansum(x * y) / max(np.nansum(x * x), 1e-12))], "pos", [0.8])
reg("onesite_total_ns", "One site — total and nonspecific binding (Hill = 1)", "Binding - Saturation", ["Bmax", "Kd", "NS"],
    "Y = Bmax*X/(Kd+X) + NS*X", lambda x, b, k, ns: b * x / (k + x) + ns * x,
    lambda x, y: [_ymax(y) * 0.8, max(_x_at_half(x, y), 1e-9), 0.01], "pos", [100, 4, 0.5])
reg("fit_ki", "One site — Fit Ki (competitive; constrain HotNM and HotKdNM)", "Binding - Competitive",
    ["Bottom", "Top", "LogKi", "HotNM", "HotKdNM"],
    "logEC50 = log10(10^LogKi*(1+HotNM/HotKdNM)); Y = Bottom + (Top-Bottom)/(1+10^(X-logEC50))",
    lambda x, b, t, lk, hot, kd: b + (t - b) / (1 + 10 ** (x - np.log10(10 ** lk * (1 + abs(hot) / abs(kd))))),
    lambda x, y: [_ymin(y), _ymax(y), _x_at_half(x, y) - 0.3, 1.0, 1.0], "log", None)
reg("competitive_hill", "One site competitive — variable slope", "Binding - Competitive", ["Bottom", "Top", "LogIC50", "HillSlope"],
    "Y = Bottom + (Top-Bottom)/(1+10^((X-LogIC50)*HillSlope))", lambda x, b, t, l, h: b + (t - b) / (1 + 10 ** ((x - l) * h)),
    lambda x, y: [_ymin(y), _ymax(y), _x_at_half(x, y), 1.0], "log", [100, 5, -7, -0.8])
reg("homologous", "Homologous competitive binding (one site; constrain HotNM)", "Binding - Competitive", ["Bmax", "LogKd", "NS", "HotNM"],
    "Kd=10^LogKd; Y = (Bmax*HotNM)/(HotNM + 10^X*1e9 + Kd*1e9) + NS",
    lambda x, b, lk, ns, hot: (b * abs(hot)) / (abs(hot) + 10 ** x * 1e9 + 10 ** lk * 1e9) + ns,
    lambda x, y: [_ymax(y) * 2, _x_at_half(x, y), _ymin(y), 1.0], "log", None)
reg("assoc_one_conc", "Association kinetics — one concentration of hot ligand", "Binding - Kinetics", ["Ymax", "Kob"],
    "Y = Ymax*(1-exp(-Kob*X))", lambda x, ym, k: ym * (1 - np.exp(-k * x)), lambda x, y: [_ymax(y), _k(x)], "time", [100, 0.1])
reg("dissociation", "Dissociation kinetics — one phase", "Binding - Kinetics", ["Y0", "NS", "Koff"], "Y = (Y0-NS)*exp(-Koff*X) + NS",
    lambda x, y0, ns, k: (y0 - ns) * np.exp(-k * x) + ns, lambda x, y: [y[int(np.argmin(x))], _ymin(y), _k(x)], "time", [100, 10, 0.08])
reg("assoc_two_conc", "Association kinetics — two concentrations (global; constrain Hot)", "Binding - Kinetics", ["Kon", "Koff", "Bmax", "Hot"],
    "Kob=Kon*Hot+Koff; Occ=Hot/(Hot+Koff/Kon); Y=Bmax*Occ*(1-exp(-Kob*X))",
    lambda x, kon, koff, bm, hot: bm * (abs(hot) / (abs(hot) + abs(koff) / max(abs(kon), 1e-30))) * (1 - np.exp(-(abs(kon) * abs(hot) + abs(koff)) * x)),
    lambda x, y: [1e7, _k(x) / 2, _ymax(y) * 1.5, 1e-8], "time", None)
reg("langmuir", "Langmuir isotherm", "Binding - Saturation", ["Qmax", "K"], "Y = Qmax*K*X/(1+K*X)",
    lambda x, q, k: q * k * x / (1 + k * x), lambda x, y: [_ymax(y) * 1.1, 1 / max(_x_at_half(x, y), 1e-9)], "pos", [50, 0.2])
reg("freundlich", "Freundlich isotherm", "Binding - Saturation", ["Kf", "n"], "Y = Kf*X^(1/n)",
    lambda x, kf, n: kf * _pos(x) ** (1 / n), lambda x, y: [max(_ymax(y) / max(_ymax(x), 1e-9) ** 0.5, 1e-6), 2.0], "pos", [3, 2.5])

# ======================================================== Exponential
reg("exp_decay3", "Three phase decay", "Exponential", ["Y0", "Plateau", "PercentFast", "PercentSlow", "KFast", "KMedium", "KSlow"],
    "Span=Y0-Plateau; Y=Plateau + Span*(PF*exp(-KFast*X) + PS*exp(-KSlow*X) + (100-PF-PS)*exp(-KMedium*X))/100",
    lambda x, y0, pl, pf, ps, kf, km, ks: pl + (y0 - pl) * (pf * np.exp(-kf * x) + ps * np.exp(-ks * x) + (100 - pf - ps) * np.exp(-km * x)) / 100,
    lambda x, y: [y[int(np.argmin(x))], _ymin(y), 33, 33, _k(x, 30), _k(x, 6), _k(x, 1)], "time", None)
reg("exp_assoc3", "Three phase association", "Exponential", ["Y0", "Plateau", "PercentFast", "PercentSlow", "KFast", "KMedium", "KSlow"],
    "Span=Plateau-Y0; Y=Y0 + Span*(PF*(1-exp(-KFast*X)) + PS*(1-exp(-KSlow*X)) + (100-PF-PS)*(1-exp(-KMedium*X)))/100",
    lambda x, y0, pl, pf, ps, kf, km, ks: y0 + (pl - y0) * (pf * (1 - np.exp(-kf * x)) + ps * (1 - np.exp(-ks * x)) + (100 - pf - ps) * (1 - np.exp(-km * x))) / 100,
    lambda x, y: [y[int(np.argmin(x))], _ymax(y), 33, 33, _k(x, 30), _k(x, 6), _k(x, 1)], "time", None)
reg("exp_decay_offset", "Exponential decay to zero (no plateau)", "Exponential", ["Y0", "K"], "Y = Y0*exp(-K*X)",
    lambda x, y0, k: y0 * np.exp(-k * x), lambda x, y: [y[int(np.argmin(x))], _k(x)], "time", [100, 0.07])
reg("exp_growth_dbl", "Exponential growth — fit doubling time", "Exponential", ["Y0", "Td"], "Y = Y0*2^(X/Td)",
    lambda x, y0, td: y0 * 2 ** (x / td), lambda x, y: [max(y[int(np.argmin(x))], 1e-9), _xr(x) / 3], "time", [5, 20])
reg("exp_growth_offset", "Exponential growth with offset", "Exponential", ["Y0", "K", "Baseline"], "Y = Baseline + Y0*exp(K*X)",
    lambda x, y0, k, b: b + y0 * np.exp(k * x), lambda x, y: [max(_span(y) / 20, 1e-9), _k(x), _ymin(y)], "time", [2, 0.05, 10])
reg("exp_base", "Exponential: Y = A·B^X", "Exponential", ["A", "B"], "Y = A*B^X",
    lambda x, a, b: a * np.abs(b) ** x, lambda x, y: [max(y[int(np.argmin(x))], 1e-9), 1.05], "time", [10, 1.04])
reg("exp_linear", "Exponential plus linear term", "Exponential", ["Y0", "Plateau", "K", "Slope"], "Y = Plateau + (Y0-Plateau)*exp(-K*X) + Slope*X",
    lambda x, y0, pl, k, s: pl + (y0 - pl) * np.exp(-k * x) + s * x, lambda x, y: [y[int(np.argmin(x))], _ymin(y), _k(x), 0.0], "time", [100, 20, 0.15, 0.5])
reg("pseudo_first", "Pseudo-first-order kinetics", "Exponential", ["Ymax", "k", "Lag"], "Y = Ymax*(1-exp(-k*(X-Lag))) for X > Lag, else 0",
    lambda x, ym, k, lag: np.where(x > lag, ym * (1 - np.exp(-k * (x - lag))), 0.0),
    lambda x, y: [_ymax(y), _k(x), float(np.nanmin(x))], "time", [80, 0.1, 5])

# ======================================================== Pharmacokinetics
reg("pk_iv1", "One-compartment, IV bolus", "Pharmacokinetics", ["C0", "Ke"], "Y = C0*exp(-Ke*X)",
    lambda x, c0, ke: c0 * np.exp(-ke * x), lambda x, y: [_ymax(y), _k(x)], "time", [50, 0.12])
reg("pk_oral1", "One-compartment, first-order absorption (oral)", "Pharmacokinetics", ["A", "Ka", "Ke"],
    "Y = A*Ka/(Ka-Ke)*(exp(-Ke*X)-exp(-Ka*X))",
    lambda x, a, ka, ke: a * ka / (ka - ke + 1e-12) * (np.exp(-ke * x) - np.exp(-ka * x)),
    lambda x, y: [_ymax(y) * 1.5, 1 / max(_xpeak(x, y), 1e-9) * 2, 1 / max(_xpeak(x, y), 1e-9) / 3], "time", [100, 0.5, 0.08])
reg("pk_iv2", "Two-compartment, IV bolus (biexponential)", "Pharmacokinetics", ["A", "Alpha", "B", "Beta"],
    "Y = A*exp(-Alpha*X) + B*exp(-Beta*X)",
    lambda x, a, al, b, be: a * np.exp(-al * x) + b * np.exp(-be * x),
    lambda x, y: [_ymax(y) * 0.7, _k(x, 15), _ymax(y) * 0.3, _k(x, 1.5)], "time", [80, 0.5, 20, 0.04])
reg("pk_infusion", "One-compartment, constant infusion (plateau)", "Pharmacokinetics", ["Css", "Ke"], "Y = Css*(1-exp(-Ke*X))",
    lambda x, c, ke: c * (1 - np.exp(-ke * x)), lambda x, y: [_ymax(y), _k(x)], "time", [40, 0.1])

# ======================================================== Growth
reg("logistic4", "Logistic (4 parameters, X linear)", "Growth", ["Bottom", "Top", "Xmid", "Scale"], "Y = Bottom + (Top-Bottom)/(1+exp((Xmid-X)/Scale))",
    lambda x, b, t, xm, sc: b + (t - b) / (1 + np.exp((xm - x) / sc)),
    lambda x, y: [_ymin(y), _ymax(y), _x_at_half(x, y), _xr(x) / 10], "time", [5, 100, 30, 6])
reg("gompertz4", "Gompertz (4 parameters, with lag)", "Growth", ["A", "Mu", "Lambda", "Y0"],
    "Y = Y0 + A*exp(-exp(Mu*e/A*(Lambda-X)+1)) (Zwietering)",
    lambda x, a, mu, lam, y0: y0 + a * np.exp(-np.exp(mu * np.e / a * (lam - x) + 1)),
    lambda x, y: [_span(y), _span(y) / _xr(x) * 2, float(np.nanpercentile(x, 20)), _ymin(y)], "time", [8, 0.6, 8, 1])
reg("von_bertalanffy", "Von Bertalanffy growth", "Growth", ["Linf", "K", "T0"], "Y = Linf*(1-exp(-K*(X-T0)))",
    lambda x, li, k, t0: li * (1 - np.exp(-k * (x - t0))), lambda x, y: [_ymax(y) * 1.1, _k(x, 2), float(np.nanmin(x)) - 1], "time", [120, 0.08, -2])
reg("monomolecular", "Monomolecular (Mitscherlich) growth", "Growth", ["A", "B", "K"], "Y = A*(1 - B*exp(-K*X))",
    lambda x, a, b, k: a * (1 - b * np.exp(-k * x)), lambda x, y: [_ymax(y) * 1.05, 0.9, _k(x)], "time", [100, 0.9, 0.1])
reg("chapman_richards", "Chapman-Richards growth", "Growth", ["A", "K", "P"], "Y = A*(1-exp(-K*X))^P",
    lambda x, a, k, p: a * (1 - np.exp(-k * np.clip(x, 0, None))) ** p, lambda x, y: [_ymax(y) * 1.05, _k(x, 2), 2.0], "time", [100, 0.08, 2.5])
reg("baranyi_simple", "Logistic growth with lag (Baranyi-type, log counts)", "Growth", ["Y0", "Ymax", "Mu", "Lag"],
    "Y = Y0 + Mu*A - ln(1+(exp(Mu*A)-1)/exp(Ymax-Y0)), A = X + ln(exp(-Mu*X)+exp(-Mu*Lag)-exp(-Mu*(X+Lag)))/Mu",
    lambda x, y0, ymx, mu, lag: (lambda A: y0 + mu * A - np.log1p((np.exp(mu * A) - 1) / np.exp(ymx - y0)))(
        x + np.log(np.exp(-mu * x) + np.exp(-mu * lag) - np.exp(-mu * (x + lag))) / mu),
    lambda x, y: [_ymin(y), _ymax(y), _span(y) / _xr(x) * 3, float(np.nanpercentile(x, 20))], "time", [2, 9, 0.5, 6])
reg("mmf", "Morgan-Mercer-Flodin growth", "Growth", ["Y0", "Ymax", "K", "D"], "Y = (Y0*K + Ymax*X^D)/(K + X^D)",
    lambda x, y0, ym, k, d: (y0 * k + ym * _pos(x) ** d) / (k + _pos(x) ** d),
    lambda x, y: [_ymin(y), _ymax(y), max(_x_at_half(x, y), 1e-9) ** 2, 2.0], "pos", [5, 100, 50, 2])
reg("malthus", "Malthusian (exponential) population growth", "Growth", ["N0", "R"], "Y = N0*exp(R*X)",
    lambda x, n0, r: n0 * np.exp(r * x), lambda x, y: [max(y[int(np.argmin(x))], 1e-9), _k(x, 1)], "time", [10, 0.04])

# ======================================================== Sigmoidal / other
reg("boltzmann_nobottom", "Boltzmann sigmoid (bottom = 0)", "Sigmoidal", ["Top", "V50", "Slope"], "Y = Top/(1+exp((V50-X)/Slope))",
    lambda x, t, v, s: t / (1 + np.exp((v - x) / s)), lambda x, y: [_ymax(y), _x_at_half(x, y), _slope_sign(x, y) * _xr(x) / 10], "any", [100, 0, 2])
reg("hill_linear", "Hill equation (X linear, 4 parameters)", "Sigmoidal", ["Bottom", "Top", "X50", "n"], "Y = Bottom + (Top-Bottom)*X^n/(X50^n + X^n)",
    lambda x, b, t, x50, n: b + (t - b) * _pos(x) ** n / (abs(x50) ** n + _pos(x) ** n),
    lambda x, y: [_ymin(y), _ymax(y), max(_x_at_half(x, y), 1e-9), 2.0], "pos", [2, 95, 12, 2.5])
reg("logistic_cdf", "Logistic cumulative distribution", "Sigmoidal", ["Amplitude", "Mu", "S"], "Y = Amplitude/(1+exp(-(X-Mu)/S))",
    lambda x, a, mu, s: a / (1 + np.exp(-(x - mu) / s)), lambda x, y: [_ymax(y), _x_at_half(x, y), _xr(x) / 10], "any", [1, 0.5, 1.5])
reg("lognormal_cdf", "Lognormal cumulative distribution", "Sigmoidal", ["Amplitude", "GeoMean", "GeoSD"],
    "Y = Amplitude*0.5*(1+erf(ln(X/GeoMean)/(ln(GeoSD)*sqrt(2))))",
    lambda x, a, gm, gs: a * 0.5 * (1 + erf(np.log(_pos(x) / abs(gm)) / (np.log(abs(gs) + 1e-12) * np.sqrt(2)))),
    lambda x, y: [_ymax(y), max(_x_at_half(x, y), 1e-9), 2.0], "pos", [100, 10, 2.2])
reg("weibull_cdf4", "Weibull cumulative (4 parameters, with offset)", "Sigmoidal", ["Bottom", "Top", "Lambda", "k"],
    "Y = Bottom + (Top-Bottom)*(1-exp(-(X/Lambda)^k))",
    lambda x, b, t, lam, k: b + (t - b) * (1 - np.exp(-(np.clip(x, 0, None) / abs(lam)) ** k)),
    lambda x, y: [_ymin(y), _ymax(y), max(_x_at_half(x, y), 1e-9), 1.5], "pos", [5, 100, 20, 2])
reg("gumbel_cdf", "Extreme value (Gumbel) cumulative", "Sigmoidal", ["Amplitude", "Mu", "Beta"], "Y = Amplitude*exp(-exp(-(X-Mu)/Beta))",
    lambda x, a, mu, b: a * np.exp(-np.exp(-(x - mu) / b)), lambda x, y: [_ymax(y), _x_at_half(x, y), _xr(x) / 8], "any", [100, 0, 2])
reg("arrhenius", "Arrhenius (rate vs. temperature in K)", "Other", ["A", "Ea_R"], "Y = A*exp(-Ea_R/X)",
    lambda x, a, ea: a * np.exp(-ea / _pos(x)), lambda x, y: [_ymax(y) * 10, float(np.nanmean(x))], "kelvin", [1e6, 4000])
reg("q10", "Q10 temperature coefficient", "Other", ["R0", "Q10", "T0"], "Y = R0*Q10^((X-T0)/10)  (constrain T0)",
    lambda x, r0, q, t0: r0 * np.abs(q) ** ((x - t0) / 10), lambda x, y: [float(np.nanmedian(y)), 2.0, float(np.nanmedian(x))], "any", None)

# ======================================================== Lines / polynomials / simple
reg("line_origin", "Straight line through origin", "Lines", ["Slope"], "Y = Slope*X",
    lambda x, s: s * x, lambda x, y: [float(np.nansum(x * y) / max(np.nansum(x * x), 1e-12))], "any", [2.5])
reg("poly2_origin", "Second order polynomial through origin", "Polynomial", ["B1", "B2"], "Y = B1*X + B2*X^2",
    lambda x, b1, b2: b1 * x + b2 * x ** 2, lambda x, y: [1.0, 0.0], "any", [2, 0.3])
reg("poly5", "Fifth order polynomial", "Polynomial", ["B0", "B1", "B2", "B3", "B4", "B5"], "Y = B0 + B1*X + … + B5*X^5",
    lambda x, *b: sum(c * x ** i for i, c in enumerate(b)), lambda x, y: list(np.polyfit(x, y, 5)[::-1]), "any", None)
reg("poly6", "Sixth order polynomial", "Polynomial", ["B0", "B1", "B2", "B3", "B4", "B5", "B6"], "Y = B0 + B1*X + … + B6*X^6",
    lambda x, *b: sum(c * x ** i for i, c in enumerate(b)), lambda x, y: list(np.polyfit(x, y, 6)[::-1]), "any", None)
reg("centered_poly2", "Centered second order polynomial", "Polynomial", ["B0", "B1", "B2", "Xmean"], "Y = B0 + B1*(X-Xmean) + B2*(X-Xmean)^2 (constrain Xmean)",
    lambda x, b0, b1, b2, xm: b0 + b1 * (x - xm) + b2 * (x - xm) ** 2, lambda x, y: [float(np.nanmean(y)), 1.0, 0.0, float(np.nanmean(x))], "any", None)
reg("hyperbola", "Hyperbola (Y = A + B/X)", "Lines", ["A", "B"], "Y = A + B/X",
    lambda x, a, b: a + b / np.where(np.abs(x) < 1e-12, 1e-12, x), lambda x, y: [_ymin(y), _span(y)], "pos", [5, 40])
reg("power_offset", "Power with offset (Y = A + B·X^C)", "Power", ["A", "B", "C"], "Y = A + B*X^C",
    lambda x, a, b, c: a + b * _pos(x) ** c, lambda x, y: [_ymin(y), 1.0, 1.0], "pos", [3, 2, 0.7])
reg("log10_line", "Semilog line (Y = A + B·log10 X)", "Lines", ["A", "B"], "Y = A + B*log10(X)",
    lambda x, a, b: a + b * np.log10(_pos(x)), lambda x, y: [float(np.nanmean(y)), 1.0], "pos", [10, 5])
reg("sqrt_model", "Square-root model (Y = A + B·√X)", "Lines", ["A", "B"], "Y = A + B*sqrt(X)",
    lambda x, a, b: a + b * np.sqrt(np.clip(x, 0, None)), lambda x, y: [_ymin(y), 1.0], "pos", [2, 4])
reg("segmental3", "Segmental linear regression (three segments)", "Lines", ["Y0", "Slope1", "Slope2", "Slope3", "X1", "X2"],
    "Three connected straight lines with breakpoints X1 < X2",
    lambda x, y0, s1, s2, s3, x1, x2: np.where(x < x1, y0 + s1 * x, np.where(x < x2, y0 + s1 * x1 + s2 * (x - x1), y0 + s1 * x1 + s2 * (x2 - x1) + s3 * (x - x2))),
    lambda x, y: [float(y[int(np.argmin(x))]), 1.0, 0.0, -1.0, float(np.nanpercentile(x, 33)), float(np.nanpercentile(x, 66))], "any", None)
reg("hockey_stick", "Plateau then line (hockey stick)", "Lines", ["Plateau", "X0", "Slope"], "Y = Plateau if X < X0 else Plateau + Slope*(X-X0)",
    lambda x, p, x0, s: np.where(x < x0, p, p + s * (x - x0)), lambda x, y: [_ymin(y), float(np.nanmedian(x)), 1.0], "any", [10, 1, 3])

# ======================================================== Gaussian / peaks / periodic / distributions
reg("two_gaussians", "Sum of two Gaussians", "Gaussian", ["Amp1", "Mean1", "SD1", "Amp2", "Mean2", "SD2"],
    "Y = Amp1*exp(-0.5*((X-Mean1)/SD1)^2) + Amp2*exp(-0.5*((X-Mean2)/SD2)^2)",
    lambda x, a1, m1, s1, a2, m2, s2: a1 * np.exp(-0.5 * ((x - m1) / s1) ** 2) + a2 * np.exp(-0.5 * ((x - m2) / s2) ** 2),
    lambda x, y: [_ymax(y), float(np.nanpercentile(x, 30)), _xr(x) / 8, _ymax(y) / 2, float(np.nanpercentile(x, 70)), _xr(x) / 8], "any", None)
reg("lorentzian_baseline", "Lorentzian with baseline", "Gaussian", ["Baseline", "Amplitude", "Center", "Width"],
    "Y = Baseline + Amplitude/(1+((X-Center)/Width)^2)",
    lambda x, b, a, c, w: b + a / (1 + ((x - c) / w) ** 2), lambda x, y: [_ymin(y), _span(y), _xpeak(x, y), _xr(x) / 10], "any", [5, 50, 0, 1])
reg("gamma_pdf", "Gamma distribution (scaled)", "Gaussian", ["Amplitude", "Shape", "Scale"], "Y = Amplitude*X^(Shape-1)*exp(-X/Scale)/(Gamma(Shape)*Scale^Shape)",
    lambda x, a, k, th: a * np.exp((k - 1) * np.log(_pos(x)) - _pos(x) / abs(th) - gammaln(abs(k)) - abs(k) * np.log(abs(th))),
    lambda x, y: [float(np.trapezoid(y, x)) if len(x) > 1 else 1.0, 2.0, max(_xpeak(x, y), 1e-6)], "pos", [500, 3, 2])
reg("damped_sine", "Damped sine wave", "Periodic", ["Amplitude", "Wavelength", "PhaseShift", "K", "Baseline"],
    "Y = Baseline + Amplitude*exp(-K*X)*sin(2*pi*X/Wavelength + PhaseShift)",
    lambda x, a, wl, ph, k, b: b + a * np.exp(-k * x) * np.sin(2 * np.pi * x / wl + ph),
    lambda x, y: [_span(y) / 2, _xr(x) / 3, 0.0, _k(x, 0.5), float(np.nanmean(y))], "time", None)
reg("sine_squared", "Sine squared wave", "Periodic", ["Amplitude", "Wavelength", "PhaseShift", "Baseline"],
    "Y = Baseline + Amplitude*sin(pi*X/Wavelength + PhaseShift)^2",
    lambda x, a, wl, ph, b: b + a * np.sin(np.pi * x / wl + ph) ** 2,
    lambda x, y: [_span(y), _xr(x) / 2, 0.0, _ymin(y)], "time", None)
reg("standard_curve_quad", "Standard curve — quadratic through blank (Y = Blank + A·X + B·X²)", "Polynomial", ["Blank", "A", "B"],
    "Y = Blank + A*X + B*X^2", lambda x, bl, a, b: bl + a * x + b * x ** 2, lambda x, y: list(np.polyfit(x, y, 2)[::-1]), "pos", [0.05, 0.4, -0.01])
reg("elisa_4pl_lin", "ELISA 4PL (X = concentration, linear)", "Dose-response - Special", ["A", "B", "C", "D"],
    "Y = D + (A-D)/(1+(X/C)^B)  (A = zero-dose response, D = infinite-dose response)",
    lambda x, a, b, c, d: d + (a - d) / (1 + (_pos(x) / abs(c)) ** b),
    lambda x, y: [_ymin(y), 1.0, max(_x_at_half(x, y), 1e-9), _ymax(y)], "pos", [0.05, 1.2, 15, 2.5])
reg("elisa_5pl_lin", "ELISA 5PL (X = concentration, linear)", "Dose-response - Special", ["A", "B", "C", "D", "G"],
    "Y = D + (A-D)/(1+(X/C)^B)^G",
    lambda x, a, b, c, d, gg: d + (a - d) / (1 + (_pos(x) / abs(c)) ** b) ** gg,
    lambda x, y: [_ymin(y), 1.0, max(_x_at_half(x, y), 1e-9), _ymax(y), 1.0], "pos", [0.05, 1.2, 15, 2.5, 0.8])


DOMAIN_BY_GROUP = {"Dose-response - Stimulation": "log", "Dose-response - Inhibition": "log", "Dose-response - Special": "log",
                   "Binding - Competitive": "log", "Exponential": "time", "Growth": "time", "Pharmacokinetics": "time",
                   "Binding - Kinetics": "time"}
for _m in MODELS.values():
    _m.setdefault("domain", DOMAIN_BY_GROUP.get(_m["group"], "pos"))
    _m.setdefault("example", None)


def x_for_domain(domain, n=24):
    return {"log": np.linspace(-10, -4, n), "time": np.linspace(0, 60, n), "any": np.linspace(-5, 5, n),
            "kelvin": np.linspace(280, 330, n)}.get(domain, np.linspace(0.5, 60, n))


# ------------------------------------------------------------------ examples for the self-test
# key: (domain, example parameters, constraints that an experimenter would fix)
_EXAMPLES = {
    "line": ("any", [2, 3], None), "poly2": ("any", [1, 2, 0.5], None), "poly3": ("any", [1, 2, 0.5, -0.2], None),
    "logagonist4": ("log", [5, 100, -7, 1.1], None), "logagonist3": ("log", [5, 100, -7], None),
    "loginhibitor4": ("log", [5, 100, -7, 1.1], None), "normresponse": ("log", [-7, 1.1], None),
    "agonist_conc": ("pos", [2, 90, 8, 1.3], None), "biphasic": ("log", [0, 100, 0.4, -8, -5.8, 1, 1], None),
    "mm": ("pos", [100, 5], None), "hill": ("pos", [100, 8, 2], None), "substrate_inhibition": ("pos", [100, 3, 40], None),
    "onesite_total": ("pos", [100, 5], None), "onesite_competitive": ("log", [5, 100, -7], None),
    "exp_decay1": ("time", [100, 10, 0.08], None), "exp_decay2": ("time", [100, 5, 60, 0.5, 0.03], None),
    "exp_assoc1": ("time", [5, 100, 0.08], None), "exp_growth": ("time", [5, 0.05], None),
    "logistic_growth": ("time", [100, 2, 0.2], None), "gompertz": ("time", [100, 2, 0.08], None),
    "gaussian": ("any", [50, 0.5, 1.5], None), "lognormal": ("pos", [200, 10, 2], None),
    "boltzmann": ("any", [5, 100, 0.5, 1], None), "power": ("pos", [2, 1.5], None), "sine": ("time", [10, 25, 0.5, 50], None),
    "logagonist5": ("log", [5, 100, -7, 1.2, 0.7], None), "bell": ("log", [100, 0, 20, -8, -5.5, 1.2, 1.2], None),
    "operational": ("log", [0, 100, -6, 0.5], None), "two_sites_binding": ("pos", [60, 1, 40, 30], None),
    "total_binding": ("pos", [100, 5, 0.5, 10], None), "specific_hill": ("pos", [100, 8, 1.8], None),
    "two_sites_competitive": ("log", [5, 100, 0.4, -8.5, -5.5], None), "exp_assoc2": ("time", [0, 100, 60, 0.5, 0.03], None),
    "plateau_decay": ("time", [12, 100, 10, 0.1], None), "exp_plateau": ("time", [100, 5, 0.08], None),
    "weibull": ("time", [100, 20, 2], None), "richards": ("time", [100, 0.15, 30, 0.7], None),
    "gaussian_baseline": ("any", [5, 50, 0.5, 1.5], None), "lorentzian": ("any", [50, 0.5, 1], None),
    "cum_gaussian": ("any", [100, 0.5, 1.5], None), "logarithmic": ("pos", [10, 5], None),
    "segmental": ("pos", [2, 2, -0.5, 30], None), "poly4": ("any", [1, 2, 0.5, -0.2, 0.05], None),
    "competitive_inhibition": ("log", [100, 5, -7], None), "kcat": ("pos", [50, 5], None),
    "assoc_dissoc": ("time", [1e8, 0.05, 100, 30, 1e-9], {"Time0": 30, "HotNM": 1e-9}),
    "ecanything": ("log", [5, 100, -6.6, 1.1, 80], {"F": 80}),
    "gaddum_schild": ("log", [5, 100, -7.5, 1, 8, 1e-7], {"Antag": 1e-7}),
    "noncomp_fixed": ("pos", [100, 5, 2, 1], {"I": 1}), "comp_fixed": ("pos", [100, 5, 2, 1], {"I": 1}),
    "uncomp_fixed": ("pos", [100, 5, 2, 1], {"I": 1}), "mixed_fixed": ("pos", [100, 5, 2, 3, 1], {"I": 1, "Alpha": 3}),
    "substrate_depletion_rate": ("pos", [50, 5, 2], {"Et": 2}),
    "fit_ki": ("log", [5, 100, -7.5, 1, 2], {"HotNM": 1, "HotKdNM": 2}),
    "homologous": ("log", [200, -8.5, 10, 1], {"HotNM": 1}),
    "assoc_two_conc": ("time", [1e7, 0.05, 100, 1e-8], {"Hot": 1e-8}),
    "exp_decay3": ("time", [100, 5, 40, 30, 1.5, 0.2, 0.02], None), "exp_assoc3": ("time", [0, 100, 40, 30, 1.5, 0.2, 0.02], None),
    "q10": ("any", [10, 2.3, 0], {"T0": 0}), "poly5": ("any", [1, 2, 0.5, -0.2, 0.05, 0.01], None),
    "poly6": ("any", [1, 2, 0.5, -0.2, 0.05, 0.01, -0.002], None), "centered_poly2": ("any", [5, 2, 0.5, 0], {"Xmean": 0}),
    "segmental3": ("any", [0, 2, 0.2, -1.5, -1.5, 2], None), "two_gaussians": ("any", [50, -2, 0.7, 30, 2, 0.8], None),
    "damped_sine": ("time", [40, 15, 0.3, 0.04, 50], None), "sine_squared": ("time", [30, 40, 0.2, 10], None),
}
for _key, (_dom, _ex, _con) in _EXAMPLES.items():
    if _key in MODELS:
        MODELS[_key]["domain"] = _dom
        MODELS[_key]["example"] = _ex
        MODELS[_key]["example_constraints"] = _con


def _g_bell(x, y):
    """Bell-shaped: rising half before the peak, falling half after it."""
    o = np.argsort(x)
    xs, ys = x[o], y[o]
    j = int(np.nanargmax(ys))
    dip = float(ys[j])
    bottom, top = float(ys[0]), float(ys[-1])
    lo_half = (bottom + dip) / 2
    hi_half = (top + dip) / 2
    l1 = float(xs[:j + 1][np.argmin(np.abs(ys[:j + 1] - lo_half))]) if j > 0 else float(xs[0])
    l2 = float(xs[j:][np.argmin(np.abs(ys[j:] - hi_half))]) if j < len(xs) - 1 else float(xs[-1])
    return [dip, bottom, top, l1, l2, 1.0, 1.0]


MODELS["bell"]["guess"] = _g_bell
