"""Every analysis added in 0.6 runs on representative data and returns JSON-serializable results."""
import json

import numpy as np
import pytest

from openprism.guide import G
from openprism.stats import ANALYSES, catalog, run
from openprism.tables import make_table, parse_table

rng=np.random.default_rng(1)
def col(*cols, reps=1):
    n=max(len(c) for c in cols); return make_table("t","column",[{"name":f"G{i}","reps":1} for i in range(len(cols))],[[ (c[i] if i<len(c) else None) for c in cols] for i in range(n)])
def multi(M, names=None, rows=None):
    return make_table("m","multi",[{"name":(names or [f"V{i}" for i in range(M.shape[1])])[i],"reps":1} for i in range(M.shape[1])], M.tolist(), row_labels=rows)
def xy(x, ys):
    return make_table("x","xy",[{"name":f"S{i}","reps":1} for i in range(len(ys))], np.column_stack(ys).tolist(), x=x)
def ct(M): return make_table("c","contingency",[{"name":f"O{i}","reps":1} for i in range(M.shape[1])], M.tolist(), row_labels=[f"R{i}" for i in range(M.shape[0])])
g=[rng.normal(m,s,n) for m,s,n in [(10,2,12),(12,3,11),(15,2.5,12),(16,4,10)]]
M=rng.normal(size=(40,4)); M[:,0]+=M[:,1]*0.8
x=np.linspace(0,48,25)
cases={
 'variance_tests':(col(*g[:2]),{}), 'variance_tests_k':(col(*g),{}),
 'distribution_tests':(col(*g[:2]),{}), 'distribution_tests_k':(col(*g),{}),
 'robust_compare':(col(*g[:2]),{}), 'robust_compare_k':(col(*g),{}),
 'trend_tests':(col(*g),{}), 'np_posthoc':(col(*g),{'method':'dunn'}), 'np_posthoc_c':(col(*g),{'method':'conover'}),'np_posthoc_d':(col(*g),{'method':'dscf'}),'np_posthoc_m':(col(*g),{'method':'mw'}),
 'rm_nonparametric':(col(*[v[:10] for v in g]),{}), 'effect_sizes':(col(*g[:2][::-1][::-1]),{}),'effect_sizes_k':(col(*g),{}),
 'one_sample_more':(col(g[0]),{'median':9,'sd0':2}), 'randomness':(col(rng.normal(size=40).cumsum()),{}),
 'circular':(col(rng.vonmises(1,3,30)*180/np.pi%360, rng.vonmises(2,3,25)*180/np.pi%360),{'expected':60}),
 'reliability':(col(*(M[:,:3].T+rng.normal(0,.3,(3,40)))),{}), 'p_adjust':(col(np.array([0.001,0.01,0.02,0.04,0.3,0.8])),{}),
 'two_way_np':(make_table("g","grouped",[{"name":"A","reps":3},{"name":"B","reps":3}], rng.normal(size=(3,6)).tolist(), row_labels=["r1","r2","r3"]),{}),
 'robust_regression':(xy(x,[2*x+rng.normal(0,3,25)]),{}), 'trend_mk':(xy(x,[0.2*x+rng.normal(0,3,25)]),{}),
 'cosinor':(xy(x,[10+3*np.cos(2*np.pi*(x-8)/24)+rng.normal(0,.5,25)]),{'period':24}),
 'contingency_more':(ct(np.array([[12,5],[3,15]])),{}),'contingency_more_rc':(ct(np.array([[12,5,3],[3,15,4],[2,3,9]])),{}),
 'risk':(ct(np.array([[12,38],[25,25]])),{}),'diagnostic':(ct(np.array([[90,15],[10,185]])),{'prevalence':0.02}),
 'kappa':(ct(np.array([[20,5,1],[3,18,4],[1,2,22]])),{}),'proportion':(ct(np.array([[12,38],[0,20]])),{}),
 'cmh':(ct(np.array([[10,20],[5,25],[12,18],[8,22]])),{}),
 'survival_more':(make_table("s","survival",[{"name":"A","reps":1},{"name":"B","reps":1}],[[1,None],[1,None],[0,None],[1,None],[None,1],[None,0],[None,1],[None,1],[1,None],[None,1]],x=[5,8,9,12,3,4,6,7,20,2]),{}),
 'glm':(multi(np.column_stack([rng.poisson(np.exp(0.5+0.3*M[:,1])),M[:,1:3]])),{'family':'poisson','dependent':0}),
 'glm_nb':(multi(np.column_stack([rng.negative_binomial(3,0.3,40),M[:,1:3]])),{'family':'negbin','dependent':0}),
 'glm_bin':(multi(np.column_stack([(M[:,1]+rng.normal(size=40)>0).astype(float),M[:,1:3]])),{'family':'binomial','link':'probit','dependent':0}),
 'ordinal':(multi(np.column_stack([np.digitize(M[:,1]+rng.normal(size=40),[-1,0,1]),M[:,1:3]])),{'dependent':0}),
 'regression_diagnostics':(multi(M),{'dependent':0}),
 'manova':(multi(np.column_stack([np.repeat([1,2,3],[13,13,14]),M[:,:3]+np.repeat([0,0.5,1],[13,13,14])[:,None]])),{'group':0}),
 'partial_correlation':(multi(M),{}),'cluster':(multi(M[:,:3]),{'method':'ward','k':3}),'cluster_k':(multi(M[:,:3]),{'method':'kmeans','k':3}),
 'meta':(multi(np.array([[0.3,0.1],[0.5,0.15],[0.1,0.2],[0.7,0.25],[0.4,0.12]]),rows=list('ABCDE')),{'format':'es_se','method':'reml'}),
 'meta_counts':(multi(np.array([[12,50,20,50],[5,40,9,41],[30,100,42,98]]),rows=list('ABC')),{'format':'counts','measure':'or','method':'dl'}),
 'normality':(col(*g),{'tests':['shapiro','jb','sf']}),'outliers':(col(np.r_[g[0],30]),{'method':'esd'}),'outliers_h':(col(np.r_[g[0],30]),{'method':'hampel'}),
 'correlation':(multi(M),{'method':'kendall','matrix':True}),
}


@pytest.mark.parametrize("name", sorted(cases))
def test_new_analysis_runs(name):
    t, p = cases[name]
    key = name if name in ANALYSES else name.rsplit("_", 1)[0]
    res = run(key, parse_table(t), p)
    json.dumps(res)
    assert res["sections"] and res["provenance"]["dataSha256"]


def test_every_analysis_has_a_guide():
    assert set(ANALYSES) <= set(G)
    for a in catalog()["analyses"]:
        assert a["guide"]["what"] and a["guide"]["when"]


def test_full_precision_mode():
    t = parse_table(make_table("t", "column", [{"name": "a", "reps": 1}], [[1], [2], [4]]))
    rounded = run("descriptive", t, {})
    full = run("descriptive", t, {"_digits": "full"})
    sd = lambda r: next(x[1] for x in r["sections"][0]["rows"] if x[0] == "Std. Deviation")  # noqa: E731
    assert float(sd(full)) == pytest.approx(np.std([1, 2, 4], ddof=1), rel=1e-15) and len(sd(rounded)) < len(sd(full)) >= 15


def test_exact_rank_tests_with_ties():
    from openprism.stats.compare import rank_sum_p, signed_rank_p
    assert rank_sum_p([1, 2, 2, 3], [2, 3, 4, 4, 5])[1] is True
    assert signed_rank_p([1.2, 2.4, 1.3, 1.3, 0, 1.0, 1.8, 0.8, 4.6, 1.4])[0] == pytest.approx(2 / 512)


def test_strict_number_format():
    from openprism.tables import to_float
    ok = {"12.5": 12.5, "-3e-4": -3e-4, ".5": 0.5, "5.": 5.0, "+7": 7.0, " 42 ": 42.0, "1E3": 1000.0}
    for s, v in ok.items():
        assert to_float(s) == v
    for s in ["1,5", "1.234,5", "1,234.5", "1 000", "1_000", "inf", "nan", "0x10", "١٢", "12%", "--1", "1e", "e5"]:
        assert np.isnan(to_float(s)), s
    t = parse_table(make_table("t", "column", [{"name": "a", "reps": 1}], [["1"], ["2,5"], ["3"], ["4"]]))
    res = run("descriptive", t, {})
    assert "not valid numbers" in res["warnings"][0] and "2,5" in res["warnings"][0]
    n = next(r[1] for r in res["sections"][0]["rows"] if r[0] == "Number of values")
    assert n == "3"
