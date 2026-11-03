"""Exact-input, high-precision least squares.

Ill-conditioned regressions (high-order polynomials, nearly collinear
predictors) lose most of their significant digits in double precision. Here
the data are taken from the original decimal text of the cells, the normal
equations are formed and solved in 80-digit decimal arithmetic, and only the
final results are rounded to doubles. This reproduces the NIST StRD certified
values (e.g. the Filip 10th-degree polynomial) to essentially full double
precision.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext

import numpy as np

PREC = 80


def to_dec(text, fallback):
    try:
        d = Decimal(str(text).strip())
        if d.is_finite():
            return d
    except (InvalidOperation, ValueError):
        pass
    return Decimal(float(fallback))


def _solve_inverse(A):
    """Inverse of a symmetric positive-definite matrix by Gauss-Jordan with partial pivoting."""
    n = len(A)
    M = [row[:] + [Decimal(int(i == j)) for j in range(n)] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if M[piv][c] == 0:
            raise ZeroDivisionError("singular design matrix (a predictor is a linear combination of others)")
        M[c], M[piv] = M[piv], M[c]
        pv = M[c][c]
        M[c] = [v / pv for v in M[c]]
        for r in range(n):
            if r != c and M[r][c] != 0:
                f = M[r][c]
                M[r] = [a - f * b for a, b in zip(M[r], M[c])]
    return [row[n:] for row in M]


def exact_ols(y, X, intercept=True):
    """y: list of Decimal (n); X: list of rows (n × p) of Decimal. Returns floats."""
    with localcontext() as ctx:
        ctx.prec = PREC
        rows = [([Decimal(1)] if intercept else []) + list(r) for r in X]
        n, p = len(rows), len(rows[0])
        XtX = [[sum((rows[k][i] * rows[k][j] for k in range(n)), Decimal(0)) for j in range(p)] for i in range(p)]
        Xty = [sum((rows[k][i] * y[k] for k in range(n)), Decimal(0)) for i in range(p)]
        inv = _solve_inverse(XtX)
        beta = [sum((inv[i][j] * Xty[j] for j in range(p)), Decimal(0)) for i in range(p)]
        fitted = [sum((r[j] * beta[j] for j in range(p)), Decimal(0)) for r in rows]
        resid = [a - b for a, b in zip(y, fitted)]
        rss = sum((e * e for e in resid), Decimal(0))
        ybar = sum(y, Decimal(0)) / n
        tss = sum(((v - ybar) ** 2 for v in y), Decimal(0)) if intercept else sum((v * v for v in y), Decimal(0))
        df = n - p
        s2 = rss / df if df > 0 else Decimal("NaN")
        se = [(inv[i][i] * s2).sqrt() if df > 0 else Decimal("NaN") for i in range(p)]
        cov = [[float(inv[i][j] * s2) for j in range(p)] for i in range(p)] if df > 0 else None
        return {"beta": np.array([float(b) for b in beta]), "se": np.array([float(s) for s in se]), "cov": np.array(cov) if cov else None,
                "rss": float(rss), "tss": float(tss), "df": df, "n": n, "p": p, "r2": float(1 - rss / tss) if tss > 0 else float("nan"),
                "fitted": np.array([float(f) for f in fitted]), "resid": np.array([float(e) for e in resid]),
                "sy_x": float(s2.sqrt()) if df > 0 else float("nan")}


def scaled_condition(X):
    """Condition number of the column-scaled design matrix (with intercept)."""
    Z = np.column_stack([np.ones(len(X)), X]) if X.ndim == 2 else np.column_stack([np.ones(len(X)), X])
    norms = np.linalg.norm(Z, axis=0)
    norms[norms == 0] = 1
    try:
        return float(np.linalg.cond(Z / norms))
    except np.linalg.LinAlgError:
        return float("inf")
