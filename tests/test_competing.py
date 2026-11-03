"""Gray's test and Fine-Gray regression against R cmprsk 2.2 (cuminc / crr, gtol = 1e-12)."""
import numpy as np
import pytest

from openprism.stats.competing import fine_gray, gray_test
from openprism.stats import run
from openprism.tables import make_table, parse_table

T = np.array([1.2, 2.5, 3.1, 3.1, 4.0, 4.4, 5.2, 5.9, 6.3, 7.0, 7.7, 8.1, 8.8, 9.4, 10.2, 11.0, 11.5, 12.3, 13.1, 14.0,
              15.2, 16.4, 17.0, 18.3, 19.9, 21.0, 22.5, 24.1, 26.0, 28.4])
S = np.array([1, 2, 1, 0, 1, 2, 1, 0, 1, 1, 2, 0, 1, 2, 1, 0, 2, 1, 1, 0, 2, 1, 0, 1, 2, 0, 1, 0, 1, 0])
G = np.tile([0, 1, 2], 10)
X = np.array([0.5, -1.2, 0.3, 1.8, -0.4, 0.9, -1.5, 0.2, 1.1, -0.7, 0.6, -0.1, 1.4, -0.9, 0.0, 0.8, -1.1, 0.4, 1.6, -0.3,
              0.7, -1.4, 0.1, 1.2, -0.6, 0.3, -0.8, 1.0, -0.2, 0.5])


def test_gray_three_groups_matches_cmprsk():
    assert gray_test(T, S, G, 1)[0] == pytest.approx(3.84749760028507, rel=1e-12)
    assert gray_test(T, S, G, 2)[0] == pytest.approx(3.22212844024006, rel=1e-12)


def test_gray_two_groups_matches_cmprsk():
    m = G < 2
    assert gray_test(T[m], S[m], G[m], 1)[0] == pytest.approx(5.12921802923555, rel=1e-12)
    assert gray_test(T[m], S[m], G[m], 2)[0] == pytest.approx(2.75897776867181, rel=1e-12)


def test_gray_scores_sum_to_zero_and_covariance_is_singular():
    chi, df, p, z, V, labels = gray_test(T, S, G, 1)
    assert df == 2 and abs(z.sum()) < 1e-12
    assert np.allclose(V.sum(1), 0, atol=1e-10)


def test_fine_gray_matches_crr():
    f = fine_gray(T, S, np.column_stack([X, G == 1]))
    assert f["beta"] == pytest.approx([-0.166243106016216, -1.48727995202272], rel=1e-7)
    assert np.sqrt(np.diag(f["var"])) == pytest.approx([0.239840559458396, 0.714648168440543], rel=1e-7)
    assert f["loglik"] == pytest.approx(-37.7738431856493, rel=1e-12)
    f2 = fine_gray(T, S, X[:, None], cause=2)
    assert f2["beta"][0] == pytest.approx(-0.475925418443747, rel=1e-7)
    assert np.sqrt(f2["var"][0, 0]) == pytest.approx(0.441776293538879, rel=1e-7)


def test_analyses_through_the_api():
    cells = [[None] * 3 for _ in T]
    for i, (g, s) in enumerate(zip(G, S)):
        cells[i][g] = int(s)
    r = run("competing_risks", parse_table(make_table("cr", "survival", [{"name": f"G{k}", "reps": 1} for k in range(3)], cells, x=T.tolist())), {"_digits": "full"})
    gray = next(s for s in r["sections"] if s["title"].startswith("Gray"))
    assert float(gray["rows"][0][1]) == pytest.approx(3.84749760028507, rel=1e-10)
    tab = make_table("fg", "multi", [{"name": n, "reps": 1} for n in ["time", "status", "x", "g1"]],
                     [[float(a), int(b), float(c), int(d == 1)] for a, b, c, d in zip(T, S, X, G)])
    r = run("fine_gray", parse_table(tab), {"timeVar": 0, "eventVar": 1, "_digits": "full"})
    shr = r["sections"][0]["rows"]
    assert float(shr[0][1]) == pytest.approx(-0.166243106016216, rel=1e-7)
    assert r["overlay"]["kind"] == "plot"


def test_gray_holds_its_level():
    rng = np.random.default_rng(1)
    p = []
    for _ in range(300):
        n = 60
        g = rng.integers(0, 2, n)
        t1, t2 = rng.exponential(16, n), rng.exponential(12, n)
        c = np.where(g == 1, rng.uniform(2, 12, n), rng.uniform(3, 40, n))   # unequal censoring is allowed under H0
        t = np.minimum(np.minimum(t1, t2), c)
        s = np.where(np.minimum(t1, t2) > c, 0, np.where(t1 < t2, 1, 2))
        p.append(gray_test(t, s, g, 1)[2])
    assert 0.02 < np.mean(np.array(p) < 0.05) < 0.09
