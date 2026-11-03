"""OpenPrism - an open source scientific graphing and statistics workbench."""

import os as _os

# Single-threaded BLAS: makes forked analysis workers safe and keeps one user's
# computation from using every CPU core.
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")

__version__ = "1.5.0"
