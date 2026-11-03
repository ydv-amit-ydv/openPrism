"""User-defined equations for nonlinear regression.

Equations are written like in a lab notebook, e.g.::

    Span = Top - Bottom
    Y = Bottom + Span/(1 + 10^((LogEC50 - X)*HillSlope))

They are parsed into a Python AST and evaluated by a small whitelisted
interpreter (no ``eval``), so arbitrary code can never run on the server.
Every identifier that is not X, an intermediate variable, a function or a
constant becomes a fitted parameter.
"""
from __future__ import annotations

import ast
import re

import numpy as np

from .common import AnalysisError

FUNCS = {
    "exp": np.exp, "ln": np.log, "log": np.log, "log10": np.log10, "log2": np.log2, "sqrt": np.sqrt,
    "abs": np.abs, "sin": np.sin, "cos": np.cos, "tan": np.tan, "arctan": np.arctan, "atan": np.arctan,
    "sinh": np.sinh, "cosh": np.cosh, "tanh": np.tanh, "erf": None, "min": np.minimum, "max": np.maximum,
    "pow": np.power,
}
CONSTS = {"pi": np.pi, "e": np.e}
BINOPS = {ast.Add: np.add, ast.Sub: np.subtract, ast.Mult: np.multiply, ast.Div: np.divide, ast.Pow: np.power,
          ast.Mod: np.mod}
CMPOPS = {ast.Lt: np.less, ast.LtE: np.less_equal, ast.Gt: np.greater, ast.GtE: np.greater_equal}

try:  # scipy's erf for cumulative-Gaussian style models
    from scipy.special import erf as _erf
    FUNCS["erf"] = _erf
except Exception:  # pragma: no cover
    FUNCS.pop("erf")


MAX_EQ_CHARS = 2000
MAX_EQ_NODES = 600


def _parse_lines(text: str):
    if not isinstance(text, str) or len(text) > MAX_EQ_CHARS:
        raise AnalysisError(f"The equation must be text of at most {MAX_EQ_CHARS} characters.")
    text = text.replace("^", "**").replace("×", "*").replace("−", "-")
    lines = [ln.strip() for ln in re.split(r"[\n;]+", text) if ln.strip() and not ln.strip().startswith("#")]
    if not lines:
        raise AnalysisError("The equation is empty.")
    stmts = []
    for ln in lines:
        m = re.match(r"^\s*([A-Za-z_]\w*)\s*=(?!=)(.*)$", ln)
        if not m:
            raise AnalysisError(f"Each line must look like 'Name = expression' (problem: {ln!r}).")
        name, expr = m.group(1), m.group(2)
        try:
            tree = ast.parse(expr.strip(), mode="eval")
        except SyntaxError as e:
            raise AnalysisError(f"Syntax error in {expr.strip()!r}: {e.msg}") from None
        _validate(tree.body)
        stmts.append((name, tree.body))
    if stmts[-1][0].upper() != "Y":
        raise AnalysisError("The last line must define Y, e.g. 'Y = Bottom + (Top-Bottom)*X/(K+X)'.")
    return stmts


def _validate(node):
    if sum(1 for _ in ast.walk(node)) > MAX_EQ_NODES:
        raise AnalysisError("The equation is too long or complex.")
    allowed = (ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Call, ast.IfExp, ast.Compare, ast.Load,
               ast.USub, ast.UAdd, ast.operator, ast.cmpop)
    for n in ast.walk(node):
        if not isinstance(n, allowed):
            raise AnalysisError(f"Unsupported syntax in equation: {type(n).__name__}")
        if isinstance(n, ast.Call):
            if not isinstance(n.func, ast.Name) or n.func.id.lower() not in FUNCS or n.keywords:
                raise AnalysisError(f"Unknown function. Allowed: {', '.join(sorted(FUNCS))}")
        if isinstance(n, ast.BinOp) and type(n.op) not in BINOPS:
            raise AnalysisError("Only + - * / ^ and % operators are allowed.")
        if isinstance(n, ast.Compare) and (len(n.ops) != 1 or type(n.ops[0]) not in CMPOPS):
            raise AnalysisError("Only simple comparisons (<, <=, >, >=) are allowed in 'a if cond else b'.")
        if isinstance(n, ast.Constant) and not isinstance(n.value, (int, float)):
            raise AnalysisError("Only numeric constants are allowed.")


def _ev(node, env):
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id in env:
            return env[node.id]
        low = node.id.lower()
        if low in CONSTS:
            return CONSTS[low]
        raise AnalysisError(f"Unknown name {node.id}")
    if isinstance(node, ast.BinOp):
        return BINOPS[type(node.op)](_ev(node.left, env), _ev(node.right, env))
    if isinstance(node, ast.UnaryOp):
        v = _ev(node.operand, env)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.Call):
        return FUNCS[node.func.id.lower()](*[_ev(a, env) for a in node.args])
    if isinstance(node, ast.Compare):
        return CMPOPS[type(node.ops[0])](_ev(node.left, env), _ev(node.comparators[0], env))
    if isinstance(node, ast.IfExp):
        return np.where(_ev(node.test, env), _ev(node.body, env), _ev(node.orelse, env))
    raise AnalysisError("Unsupported expression")


def parse_initial(text) -> dict:
    """'Top=100, Bottom=0' -> {'Top': 100.0, 'Bottom': 0.0} (also accepts a dict)."""
    if isinstance(text, dict):
        return {k: float(v) for k, v in text.items() if str(v).strip() != ""}
    out = {}
    for part in re.split(r"[,;\n]+", str(text or "")):
        if "=" in part:
            k, v = part.split("=", 1)
            try:
                out[k.strip()] = float(v)
            except ValueError:
                raise AnalysisError(f"Initial value for {k.strip()} is not a number.") from None
    return out


def custom_model(equation: str, initial=None) -> dict:
    stmts = _parse_lines(equation)
    assigned = set()
    params = []
    for name, node in stmts:
        func_names = {n.func.id for n in ast.walk(node) if isinstance(n, ast.Call)}
        for nm in [n.id for n in ast.walk(node) if isinstance(n, ast.Name)]:
            if nm in func_names or nm == "X" or nm in assigned or nm.lower() in CONSTS or nm in params:
                continue
            params.append(nm)
        assigned.add(name)
    if not params:
        raise AnalysisError("The equation has no parameters to fit.")
    if not any(n.id == "X" for _, node in stmts for n in ast.walk(node) if isinstance(n, ast.Name)):
        raise AnalysisError("The equation must use X (case-sensitive).")
    init = parse_initial(initial)

    def f(x, *p):
        env = dict(zip(params, p))
        env["X"] = np.asarray(x, float)
        with np.errstate(all="ignore"):
            for name, node in stmts:
                env[name] = _ev(node, env)
        return np.broadcast_to(np.asarray(env[stmts[-1][0]], float), np.shape(x)).astype(float)

    def guess(x, y):
        out = []
        for p in params:
            if p in init:
                out.append(init[p])
            elif p.lower() in ("top", "plateau", "max", "ymax", "vmax", "bmax", "amplitude", "ym"):
                out.append(float(np.nanmax(y)))
            elif p.lower() in ("bottom", "min", "ymin", "baseline", "y0"):
                out.append(float(np.nanmin(y)))
            else:
                out.append(1.0)
        return out

    formula = "; ".join(ast.unparse(node).join([f"{name} = ", ""]) for name, node in stmts)
    return {"key": "custom", "name": "User-defined equation", "group": "User", "params": params,
            "formula": formula, "f": f, "guess": guess}
