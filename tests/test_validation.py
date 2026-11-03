"""Runs the scientific validation suite (validation/) as part of the tests:
NIST StRD certified values, agreement with R, reproducibility/invariance and
a reduced Monte-Carlo calibration. Full report: python validation/run_validation.py"""
import sys
import warnings
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "validation"))


def _failures(checks):
    return [f"{c['area']} | {c['case']} | {c['quantity']}: LRE {c.get('lre')} < {c['required']} ({c.get('note', '')})" for c in checks if not c["pass"]]


@pytest.fixture(autouse=True)
def _quiet():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        yield


def test_nist_strd_certified_values():
    import nist
    checks = nist.run_all()
    assert len(checks) > 340
    assert not _failures(checks)


def test_agreement_with_r():
    import rcases
    checks = rcases.run_all()
    assert len(checks) > 280
    assert not _failures(checks)


def test_reproducibility_and_invariance():
    import reproducibility
    assert not _failures(reproducibility.run_all())


def test_calibration_smoke():
    import calibration
    checks = calibration.run_all(reps=150)
    assert not _failures(checks)
