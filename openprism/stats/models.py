"""Library of nonlinear regression equations.

Each model provides a vectorised function f(x, *params), parameter names and an
initial-guess routine based on the data, similar to Prism's built-in equations.
"""
from __future__ import annotations

import numpy as np


def _span(y):
    return (np.nanmax(y) - np.nanmin(y)) or 1.0


def _x_at_half(x, y):
    mid = (np.nanmax(y) + np.nanmin(y)) / 2
    return x[np.argmin(np.abs(y - mid))]


def _slope_sign(x, y):
    if len(x) < 2:
        return 1.0
    c = np.corrcoef(x, y)[0, 1]
    return 1.0 if not np.isfinite(c) or c >= 0 else -1.0


MODELS = {}


def model(key, name, group, params, formula):
    def deco(fn):
        MODELS[key] = {"key": key, "name": name, "group": group, "params": params, "formula": formula,
                       "f": fn, "guess": None}
        return fn
    return deco


def guess(key):
    def deco(fn):
        MODELS[key]["guess"] = fn
        return fn
    return deco


# --- Lines / polynomials ---------------------------------------------------
@model("line", "Straight line", "Lines", ["YIntercept", "Slope"], "Y = YIntercept + Slope*X")
def _line(x, b0, b1):
    return b0 + b1 * x


@guess("line")
def _g_line(x, y):
    b1, b0 = np.polyfit(x, y, 1)
    return [b0, b1]


@model("poly2", "Second order polynomial (quadratic)", "Polynomial", ["B0", "B1", "B2"], "Y = B0 + B1*X + B2*X^2")
def _poly2(x, b0, b1, b2):
    return b0 + b1 * x + b2 * x ** 2


@guess("poly2")
def _g_poly2(x, y):
    return list(np.polyfit(x, y, 2)[::-1])


@model("poly3", "Third order polynomial (cubic)", "Polynomial", ["B0", "B1", "B2", "B3"],
       "Y = B0 + B1*X + B2*X^2 + B3*X^3")
def _poly3(x, b0, b1, b2, b3):
    return b0 + b1 * x + b2 * x ** 2 + b3 * x ** 3


@guess("poly3")
def _g_poly3(x, y):
    return list(np.polyfit(x, y, 3)[::-1])


# --- Dose response -----------------------------------------------------------
@model("logagonist4", "log(agonist) vs. response -- Variable slope (four parameters)", "Dose-response - Stimulation",
       ["Bottom", "Top", "LogEC50", "HillSlope"], "Y = Bottom + (Top-Bottom)/(1+10^((LogEC50-X)*HillSlope))")
def _la4(x, bottom, top, logec50, hill):
    return bottom + (top - bottom) / (1 + 10 ** ((logec50 - x) * hill))


@guess("logagonist4")
def _g_la4(x, y):
    return [np.nanmin(y), np.nanmax(y), _x_at_half(x, y), 1.0 * _slope_sign(x, y)]


@model("logagonist3", "log(agonist) vs. response (three parameters, Hill slope = 1)", "Dose-response - Stimulation",
       ["Bottom", "Top", "LogEC50"], "Y = Bottom + (Top-Bottom)/(1+10^(LogEC50-X))")
def _la3(x, bottom, top, logec50):
    return bottom + (top - bottom) / (1 + 10 ** (logec50 - x))


@guess("logagonist3")
def _g_la3(x, y):
    lo, hi = np.nanmin(y), np.nanmax(y)
    if _slope_sign(x, y) < 0:
        lo, hi = hi, lo
    return [lo, hi, _x_at_half(x, y)]


@model("loginhibitor4", "log(inhibitor) vs. response -- Variable slope (four parameters)", "Dose-response - Inhibition",
       ["Bottom", "Top", "LogIC50", "HillSlope"], "Y = Bottom + (Top-Bottom)/(1+10^((X-LogIC50)*HillSlope))")
def _li4(x, bottom, top, logic50, hill):
    return bottom + (top - bottom) / (1 + 10 ** ((x - logic50) * hill))


@guess("loginhibitor4")
def _g_li4(x, y):
    return [np.nanmin(y), np.nanmax(y), _x_at_half(x, y), 1.0 * -_slope_sign(x, y)]


@model("normresponse", "log(agonist) vs. normalized response -- Variable slope", "Dose-response - Stimulation",
       ["LogEC50", "HillSlope"], "Y = 100/(1+10^((LogEC50-X)*HillSlope))")
def _nr(x, logec50, hill):
    return 100 / (1 + 10 ** ((logec50 - x) * hill))


@guess("normresponse")
def _g_nr(x, y):
    return [_x_at_half(x, y), _slope_sign(x, y)]


@model("agonist_conc", "[Agonist] vs. response -- Variable slope (Hill, X is concentration)", "Dose-response - Stimulation",
       ["Bottom", "Top", "EC50", "HillSlope"], "Y = Bottom + (Top-Bottom)*X^HillSlope/(EC50^HillSlope + X^HillSlope)")
def _ac(x, bottom, top, ec50, hill):
    xx = np.clip(x, 0, None)
    return bottom + (top - bottom) * xx ** hill / (np.abs(ec50) ** hill + xx ** hill)


@guess("agonist_conc")
def _g_ac(x, y):
    return [np.nanmin(y), np.nanmax(y), max(_x_at_half(x, y), 1e-12), 1.0]


@model("biphasic", "Biphasic dose-response", "Dose-response - Special",
       ["Bottom", "Top", "Frac", "LogEC50_1", "LogEC50_2", "nH1", "nH2"],
       "Span=Top-Bottom; Y=Bottom + Span*Frac/(1+10^((LogEC50_1-X)*nH1)) + Span*(1-Frac)/(1+10^((LogEC50_2-X)*nH2))")
def _biph(x, bottom, top, frac, l1, l2, n1, n2):
    span = top - bottom
    return bottom + span * frac / (1 + 10 ** ((l1 - x) * n1)) + span * (1 - frac) / (1 + 10 ** ((l2 - x) * n2))


@guess("biphasic")
def _g_biph(x, y):
    m = _x_at_half(x, y)
    rng = (np.nanmax(x) - np.nanmin(x)) / 4
    return [np.nanmin(y), np.nanmax(y), 0.5, m - rng, m + rng, 1.0, 1.0]


# --- Enzyme kinetics --------------------------------------------------------
@model("mm", "Michaelis-Menten", "Enzyme kinetics", ["Vmax", "Km"], "Y = Vmax*X/(Km + X)")
def _mm(x, vmax, km):
    return vmax * x / (km + x)


@guess("mm")
def _g_mm(x, y):
    return [np.nanmax(y) * 1.1, max(_x_at_half(x, y), 1e-9)]


@model("hill", "Allosteric sigmoidal (Hill)", "Enzyme kinetics", ["Vmax", "Khalf", "h"],
       "Y = Vmax*X^h/(Khalf^h + X^h)")
def _hill(x, vmax, khalf, h):
    xx = np.clip(x, 0, None)
    return vmax * xx ** h / (np.abs(khalf) ** h + xx ** h)


@guess("hill")
def _g_hill(x, y):
    return [np.nanmax(y) * 1.1, max(_x_at_half(x, y), 1e-9), 1.0]


@model("substrate_inhibition", "Substrate inhibition", "Enzyme kinetics", ["Vmax", "Km", "Ki"],
       "Y = Vmax*X/(Km + X*(1+X/Ki))")
def _si(x, vmax, km, ki):
    return vmax * x / (km + x * (1 + x / ki))


@guess("substrate_inhibition")
def _g_si(x, y):
    return [np.nanmax(y) * 2, max(_x_at_half(x, y), 1e-9), np.nanmax(x)]


# --- Binding ----------------------------------------------------------------
@model("onesite_total", "One site -- Specific binding", "Binding - Saturation", ["Bmax", "Kd"], "Y = Bmax*X/(Kd + X)")
def _osb(x, bmax, kd):
    return bmax * x / (kd + x)


@guess("onesite_total")
def _g_osb(x, y):
    return [np.nanmax(y) * 1.1, max(_x_at_half(x, y), 1e-9)]


@model("onesite_competitive", "One site -- Fit logIC50 (competitive binding)", "Binding - Competitive",
       ["Bottom", "Top", "LogIC50"], "Y = Bottom + (Top-Bottom)/(1+10^(X-LogIC50))")
def _osc(x, bottom, top, logic50):
    return bottom + (top - bottom) / (1 + 10 ** (x - logic50))


@guess("onesite_competitive")
def _g_osc(x, y):
    return [np.nanmin(y), np.nanmax(y), _x_at_half(x, y)]


# --- Exponential ------------------------------------------------------------
@model("exp_decay1", "One phase decay", "Exponential", ["Y0", "Plateau", "K"], "Y = (Y0 - Plateau)*exp(-K*X) + Plateau")
def _ed1(x, y0, plateau, k):
    return (y0 - plateau) * np.exp(-k * x) + plateau


@guess("exp_decay1")
def _g_ed1(x, y):
    return [y[np.argmin(x)], np.nanmin(y), 1.0 / max((np.nanmax(x) - np.nanmin(x)) / 3, 1e-9)]


@model("exp_decay2", "Two phase decay", "Exponential", ["Y0", "Plateau", "PercentFast", "KFast", "KSlow"],
       "SpanFast=(Y0-Plateau)*PercentFast*.01; SpanSlow=(Y0-Plateau)*(100-PercentFast)*.01; "
       "Y=Plateau + SpanFast*exp(-KFast*X) + SpanSlow*exp(-KSlow*X)")
def _ed2(x, y0, plateau, pf, kf, ks):
    span = y0 - plateau
    return plateau + span * pf * 0.01 * np.exp(-kf * x) + span * (100 - pf) * 0.01 * np.exp(-ks * x)


@guess("exp_decay2")
def _g_ed2(x, y):
    k = 1.0 / max((np.nanmax(x) - np.nanmin(x)) / 3, 1e-9)
    return [y[np.argmin(x)], np.nanmin(y), 50, 5 * k, k / 2]


@model("exp_assoc1", "One phase association", "Exponential", ["Y0", "Plateau", "K"],
       "Y = Y0 + (Plateau - Y0)*(1 - exp(-K*X))")
def _ea1(x, y0, plateau, k):
    return y0 + (plateau - y0) * (1 - np.exp(-k * x))


@guess("exp_assoc1")
def _g_ea1(x, y):
    return [y[np.argmin(x)], np.nanmax(y), 1.0 / max((np.nanmax(x) - np.nanmin(x)) / 3, 1e-9)]


@model("exp_growth", "Exponential growth equation", "Exponential", ["Y0", "K"], "Y = Y0*exp(K*X)")
def _eg(x, y0, k):
    return y0 * np.exp(k * x)


@guess("exp_growth")
def _g_eg(x, y):
    pos = y > 0
    if pos.sum() >= 2:
        k, ly0 = np.polyfit(x[pos], np.log(y[pos]), 1)
        return [np.exp(ly0), k]
    return [np.nanmean(y), 0.1]


@model("logistic_growth", "Logistic growth", "Growth", ["YM", "Y0", "K"], "Y = YM*Y0/((YM-Y0)*exp(-K*X) + Y0)")
def _lg(x, ym, y0, k):
    return ym * y0 / ((ym - y0) * np.exp(-k * x) + y0)


@guess("logistic_growth")
def _g_lg(x, y):
    return [np.nanmax(y) * 1.05, max(y[np.argmin(x)], 1e-6), 4.0 / max(np.nanmax(x) - np.nanmin(x), 1e-9)]


@model("gompertz", "Gompertz growth", "Growth", ["YM", "Y0", "K"], "Y = YM*(Y0/YM)^(exp(-K*X))")
def _gz(x, ym, y0, k):
    return ym * (np.abs(y0 / ym)) ** np.exp(-k * x)


@guess("gompertz")
def _g_gz(x, y):
    return [np.nanmax(y) * 1.05, max(y[np.argmin(x)], 1e-6), 2.0 / max(np.nanmax(x) - np.nanmin(x), 1e-9)]


# --- Gaussian / sigmoid -----------------------------------------------------
@model("gaussian", "Gaussian", "Gaussian", ["Amplitude", "Mean", "SD"], "Y = Amplitude*exp(-0.5*((X-Mean)/SD)^2)")
def _gauss(x, amp, mean, sd):
    return amp * np.exp(-0.5 * ((x - mean) / sd) ** 2)


@guess("gaussian")
def _g_gauss(x, y):
    j = int(np.nanargmax(y))
    return [y[j], x[j], max((np.nanmax(x) - np.nanmin(x)) / 6, 1e-9)]


@model("lognormal", "Lognormal", "Gaussian", ["Amplitude", "GeoMean", "GeoSD"],
       "Y = (Amplitude/X)*exp(-0.5*(ln(X/GeoMean)/ln(GeoSD))^2)")
def _logn(x, amp, gm, gsd):
    xx = np.clip(x, 1e-300, None)
    return (amp / xx) * np.exp(-0.5 * (np.log(xx / gm) / np.log(gsd)) ** 2)


@guess("lognormal")
def _g_logn(x, y):
    j = int(np.nanargmax(y))
    return [y[j] * max(x[j], 1e-9), max(x[j], 1e-9), 2.0]


@model("boltzmann", "Boltzmann sigmoidal", "Sigmoidal", ["Bottom", "Top", "V50", "Slope"],
       "Y = Bottom + (Top-Bottom)/(1+exp((V50-X)/Slope))")
def _boltz(x, bottom, top, v50, slope):
    return bottom + (top - bottom) / (1 + np.exp((v50 - x) / slope))


@guess("boltzmann")
def _g_boltz(x, y):
    return [np.nanmin(y), np.nanmax(y), _x_at_half(x, y),
            _slope_sign(x, y) * max((np.nanmax(x) - np.nanmin(x)) / 10, 1e-9)]


@model("power", "Power series (Y = A*X^B)", "Power", ["A", "B"], "Y = A*X^B")
def _power(x, a, b):
    return a * np.power(np.abs(x), b)


@guess("power")
def _g_power(x, y):
    m = (x > 0) & (y > 0)
    if m.sum() >= 2:
        b, la = np.polyfit(np.log(x[m]), np.log(y[m]), 1)
        return [np.exp(la), b]
    return [1.0, 1.0]


@model("sine", "Sine wave", "Periodic", ["Amplitude", "Wavelength", "PhaseShift", "Baseline"],
       "Y = Baseline + Amplitude*sin((2*pi*X/Wavelength) + PhaseShift)")
def _sine(x, amp, wl, ph, base):
    return base + amp * np.sin(2 * np.pi * x / wl + ph)


@guess("sine")
def _g_sine(x, y):
    return [_span(y) / 2, max(np.nanmax(x) - np.nanmin(x), 1e-9) / 2, 0.0, np.nanmean(y)]


# ------------------------------------------------------------------ more equations
@model("logagonist5", "Asymmetric sigmoidal, 5PL (log X)", "Dose-response - Special", ["Bottom", "Top", "LogEC50", "HillSlope", "S"],
       "Y = Bottom + (Top-Bottom)/(1+10^((LogEC50-X)*HillSlope))^S")
def _la5(x, bottom, top, logec50, hill, s_):
    return bottom + (top - bottom) / (1 + 10 ** ((logec50 - x) * hill)) ** s_


@guess("logagonist5")
def _g_la5(x, y):
    return [np.nanmin(y), np.nanmax(y), _x_at_half(x, y), _slope_sign(x, y), 1.0]


@model("bell", "Bell-shaped dose-response", "Dose-response - Special", ["Dip", "Bottom", "Top", "LogEC50_1", "LogEC50_2", "nH1", "nH2"],
       "Span1=Dip-Bottom; Span2=Top-Dip; Y=Bottom + Span1/(1+10^((LogEC50_1-X)*nH1)) + Span2/(1+10^((X-LogEC50_2)*nH2))")
def _bell(x, dip, bottom, top, l1, l2, n1, n2):
    return bottom + (dip - bottom) / (1 + 10 ** ((l1 - x) * n1)) + (top - dip) / (1 + 10 ** ((x - l2) * n2))


@guess("bell")
def _g_bell(x, y):
    j = int(np.nanargmax(y))
    return [np.nanmax(y), np.nanmin(y), np.nanmin(y), x[max(0, j - 2)], x[min(len(x) - 1, j + 2)], 1.0, 1.0]


@model("operational", "Operational model (agonist, Black & Leff)", "Dose-response - Special", ["Basal", "Emax", "LogKA", "LogTau"],
       "Y = Basal + (Emax-Basal)*Tau*A/(KA + A*(1+Tau)), A=10^X")
def _oper(x, basal, emax, logka, logtau):
    a = 10.0 ** x
    tau = 10.0 ** logtau
    return basal + (emax - basal) * tau * a / (10 ** logka + a * (1 + tau))


@guess("operational")
def _g_oper(x, y):
    return [np.nanmin(y), np.nanmax(y) * 1.2, _x_at_half(x, y) + 0.5, 0.5]


@model("two_sites_binding", "Two sites — specific binding", "Binding - Saturation", ["Bmax1", "Kd1", "Bmax2", "Kd2"],
       "Y = Bmax1*X/(Kd1+X) + Bmax2*X/(Kd2+X)")
def _tsb(x, b1, k1, b2, k2):
    return b1 * x / (k1 + x) + b2 * x / (k2 + x)


@guess("two_sites_binding")
def _g_tsb(x, y):
    m = max(_x_at_half(x, y), 1e-9)
    return [np.nanmax(y) / 2, m / 5, np.nanmax(y) / 2, m * 5]


@model("total_binding", "One site — total binding (specific + nonspecific)", "Binding - Saturation", ["Bmax", "Kd", "NS", "Background"],
       "Y = Bmax*X/(Kd+X) + NS*X + Background")
def _tb(x, bmax, kd, ns, bg):
    return bmax * x / (kd + x) + ns * x + bg


@guess("total_binding")
def _g_tb(x, y):
    return [np.nanmax(y) * 0.8, max(_x_at_half(x, y), 1e-9), 0.0, np.nanmin(y)]


@model("specific_hill", "Specific binding with Hill slope", "Binding - Saturation", ["Bmax", "Kd", "h"], "Y = Bmax*X^h/(Kd^h + X^h)")
def _sbh(x, bmax, kd, h_):
    xx = np.clip(x, 0, None)
    return bmax * xx ** h_ / (np.abs(kd) ** h_ + xx ** h_)


@guess("specific_hill")
def _g_sbh(x, y):
    return [np.nanmax(y) * 1.1, max(_x_at_half(x, y), 1e-9), 1.0]


@model("two_sites_competitive", "Two sites — competitive binding (Fit logIC50)", "Binding - Competitive",
       ["Bottom", "Top", "Fraction1", "LogIC50_1", "LogIC50_2"],
       "Y = Bottom + (Top-Bottom)*(Fraction1/(1+10^(X-LogIC50_1)) + (1-Fraction1)/(1+10^(X-LogIC50_2)))")
def _tsc(x, bottom, top, f1, l1, l2):
    return bottom + (top - bottom) * (f1 / (1 + 10 ** (x - l1)) + (1 - f1) / (1 + 10 ** (x - l2)))


@guess("two_sites_competitive")
def _g_tsc(x, y):
    m = _x_at_half(x, y)
    return [np.nanmin(y), np.nanmax(y), 0.5, m - 1, m + 1]


@model("exp_assoc2", "Two phase association", "Exponential", ["Y0", "Plateau", "PercentFast", "KFast", "KSlow"],
       "Y = Y0 + SpanFast*(1-exp(-KFast*X)) + SpanSlow*(1-exp(-KSlow*X))")
def _ea2(x, y0, plateau, pf, kf, ks):
    span = plateau - y0
    return y0 + span * pf * 0.01 * (1 - np.exp(-kf * x)) + span * (100 - pf) * 0.01 * (1 - np.exp(-ks * x))


@guess("exp_assoc2")
def _g_ea2(x, y):
    k = 1.0 / max((np.nanmax(x) - np.nanmin(x)) / 3, 1e-9)
    return [y[np.argmin(x)], np.nanmax(y), 50, 5 * k, k / 2]


@model("plateau_decay", "Plateau followed by one phase decay", "Exponential", ["X0", "Y0", "Plateau", "K"],
       "Y = Y0 if X<X0 else Plateau+(Y0-Plateau)*exp(-K*(X-X0))")
def _pd(x, x0, y0, plateau, k):
    return np.where(x < x0, y0, plateau + (y0 - plateau) * np.exp(-k * (x - x0)))


@guess("plateau_decay")
def _g_pd(x, y):
    return [np.nanpercentile(x, 20), np.nanmax(y), np.nanmin(y), 3.0 / max(np.nanmax(x) - np.nanmin(x), 1e-9)]


@model("exp_plateau", "Exponential plateau (growth towards a maximum)", "Exponential", ["YM", "Y0", "K"], "Y = YM - (YM-Y0)*exp(-K*X)")
def _ep(x, ym, y0, k):
    return ym - (ym - y0) * np.exp(-k * x)


@guess("exp_plateau")
def _g_ep(x, y):
    return [np.nanmax(y), y[np.argmin(x)], 3.0 / max(np.nanmax(x) - np.nanmin(x), 1e-9)]


@model("weibull", "Weibull (cumulative)", "Growth", ["Top", "Lambda", "k"], "Y = Top*(1 - exp(-(X/Lambda)^k))")
def _wb(x, top, lam, k):
    return top * (1 - np.exp(-(np.clip(x, 0, None) / np.abs(lam)) ** k))


@guess("weibull")
def _g_wb(x, y):
    return [np.nanmax(y), max(_x_at_half(x, y), 1e-9), 1.5]


@model("richards", "Richards (generalized logistic) growth", "Growth", ["YM", "K", "Xm", "Nu"],
       "Y = YM/(1+Nu*exp(-K*(X-Xm)))^(1/Nu)")
def _rich(x, ym, k, xm, nu):
    return ym / (1 + nu * np.exp(-k * (x - xm))) ** (1 / nu)


@guess("richards")
def _g_rich(x, y):
    return [np.nanmax(y) * 1.05, 4.0 / max(np.nanmax(x) - np.nanmin(x), 1e-9), _x_at_half(x, y), 1.0]


@model("gaussian_baseline", "Gaussian with baseline", "Gaussian", ["Baseline", "Amplitude", "Mean", "SD"],
       "Y = Baseline + Amplitude*exp(-0.5*((X-Mean)/SD)^2)")
def _gb(x, base, amp, mean, sd):
    return base + amp * np.exp(-0.5 * ((x - mean) / sd) ** 2)


@guess("gaussian_baseline")
def _g_gb(x, y):
    j = int(np.nanargmax(y))
    return [np.nanmin(y), _span(y), x[j], max((np.nanmax(x) - np.nanmin(x)) / 6, 1e-9)]


@model("lorentzian", "Lorentzian", "Gaussian", ["Amplitude", "Center", "Width"], "Y = Amplitude/(1+((X-Center)/Width)^2)")
def _lor(x, amp, c, w):
    return amp / (1 + ((x - c) / w) ** 2)


@guess("lorentzian")
def _g_lor(x, y):
    j = int(np.nanargmax(y))
    return [y[j], x[j], max((np.nanmax(x) - np.nanmin(x)) / 10, 1e-9)]


@model("cum_gaussian", "Cumulative Gaussian", "Gaussian", ["Amplitude", "Mean", "SD"], "Y = Amplitude*0.5*(1+erf((X-Mean)/(SD*sqrt(2))))")
def _cg(x, amp, mean, sd):
    from scipy.special import erf
    return amp * 0.5 * (1 + erf((x - mean) / (sd * np.sqrt(2))))


@guess("cum_gaussian")
def _g_cg(x, y):
    return [np.nanmax(y), _x_at_half(x, y), max((np.nanmax(x) - np.nanmin(x)) / 6, 1e-9)]


@model("logarithmic", "Semilog line (Y = A + B·ln X)", "Lines", ["A", "B"], "Y = A + B*ln(X)")
def _logline(x, a, b):
    return a + b * np.log(np.clip(x, 1e-300, None))


@guess("logarithmic")
def _g_logline(x, y):
    m = x > 0
    if m.sum() >= 2:
        b, a = np.polyfit(np.log(x[m]), y[m], 1)
        return [a, b]
    return [0.0, 1.0]


@model("segmental", "Segmental linear regression (two lines, breakpoint)", "Lines", ["Y0", "Slope1", "Slope2", "X0"],
       "Y = Y0 + Slope1*X if X<X0 else Y0 + Slope1*X0 + Slope2*(X-X0)")
def _seg(x, y0, s1, s2, x0):
    return np.where(x < x0, y0 + s1 * x, y0 + s1 * x0 + s2 * (x - x0))


@guess("segmental")
def _g_seg(x, y):
    o = np.argsort(x)
    xs, ys = x[o], y[o]
    h_ = max(2, len(xs) // 2)
    s1 = np.polyfit(xs[:h_], ys[:h_], 1)[0] if h_ >= 2 else 1.0
    s2 = np.polyfit(xs[h_ - 1:], ys[h_ - 1:], 1)[0] if len(xs) - h_ >= 1 else 1.0
    return [ys[0] - s1 * xs[0], s1, s2, xs[h_ - 1]]


@model("poly4", "Fourth order polynomial", "Polynomial", ["B0", "B1", "B2", "B3", "B4"], "Y = B0 + B1*X + B2*X^2 + B3*X^3 + B4*X^4")
def _poly4(x, b0, b1, b2, b3, b4):
    return b0 + b1 * x + b2 * x ** 2 + b3 * x ** 3 + b4 * x ** 4


@guess("poly4")
def _g_poly4(x, y):
    return list(np.polyfit(x, y, 4)[::-1])


@model("competitive_inhibition", "Enzyme: competitive inhibition at fixed [S] (X = log[I])", "Enzyme kinetics", ["Top", "Bottom", "LogKi_app"],
       "Y = Bottom + (Top-Bottom)/(1+10^(X-LogKi_app))")
def _ci(x, top, bottom, lk):
    return bottom + (top - bottom) / (1 + 10 ** (x - lk))


@guess("competitive_inhibition")
def _g_ci(x, y):
    return [np.nanmax(y), np.nanmin(y), _x_at_half(x, y)]


@model("kcat", "Enzyme: kcat (Y = Et·kcat·X/(Km+X)), Et = 1", "Enzyme kinetics", ["kcat", "Km"], "Y = kcat*X/(Km+X)")
def _kcat(x, kcat, km):
    return kcat * x / (km + x)


@guess("kcat")
def _g_kcat(x, y):
    return [np.nanmax(y) * 1.1, max(_x_at_half(x, y), 1e-9)]


@model("assoc_dissoc", "Association then dissociation (binding kinetics)", "Binding - Kinetics", ["Kon", "Koff", "Bmax", "Time0", "HotNM"],
       "Association before Time0, exponential dissociation after")
def _ad(x, kon, koff, bmax, t0, hot):
    kob = kon * hot + koff
    occ = hot / (hot + koff / max(kon, 1e-30))
    y_at0 = bmax * occ * (1 - np.exp(-kob * t0))
    return np.where(x < t0, bmax * occ * (1 - np.exp(-kob * x)), y_at0 * np.exp(-koff * (x - t0)))


@guess("assoc_dissoc")
def _g_ad(x, y):
    return [1e8, 0.01, np.nanmax(y) * 1.2, x[int(np.nanargmax(y))], 1e-9]


def model_list():
    from . import models_extra  # noqa: F401  (registers the extended equation library)
    return [{"key": m["key"], "name": m["name"], "group": m["group"], "params": m["params"], "formula": m["formula"]}
            for m in MODELS.values()]
