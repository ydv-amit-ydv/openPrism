"""Run computations in a short-lived child process with per-user resource limits.

Each analysis request is executed in a forked worker with
* an address-space (RAM) limit  — RLIMIT_AS = current size + the user's allowance,
* a CPU-time limit               — RLIMIT_CPU,
* a wall-clock timeout           — the parent kills the child,
so a single user (or a malicious request) can never exhaust the server's memory
or CPU. On platforms without ``fork``/``resource`` (Windows) the call runs
in-process with the other (input-size) limits still applied.
"""
from __future__ import annotations

import os
import signal
import threading
import time
import traceback

try:
    import multiprocessing as mp
    import resource
    _CTX = mp.get_context("fork")
    AVAILABLE = os.environ.get("OPENPRISM_SANDBOX", "1") != "0"
except (ImportError, ValueError):  # pragma: no cover - non-POSIX
    AVAILABLE = False


class LimitError(Exception):
    """The computation exceeded the user's resource allocation."""


def _vm_size_bytes():
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmSize:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        pass
    return 0


def _child(conn, fn, args, kwargs, mem_mb, cpu_s):
    try:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        if mem_mb:
            base = _vm_size_bytes()
            limit = base + int(mem_mb) * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        if cpu_s:
            resource.setrlimit(resource.RLIMIT_CPU, (int(cpu_s), int(cpu_s) + 1))
        c0 = time.process_time()
        result = fn(*args, **kwargs)
        cpu = time.process_time() - c0
        try:
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # MB (Linux reports KB)
        except Exception:  # noqa: BLE001
            peak = None
        conn.send((True, (result, cpu, peak)))
    except MemoryError:
        conn.send((False, ("LimitError", "The analysis needed more memory than your account allows.")))
    except BaseException as e:  # noqa: BLE001 - report everything back to the parent
        conn.send((False, (type(e).__name__, str(e), traceback.format_exc(limit=3))))
    finally:
        conn.close()
        os._exit(0)


_stats = threading.local()


def last_stats():
    """Timing of the most recent run_limited call in this thread: {'wall', 'cpu', 'peakMb'}."""
    return getattr(_stats, "value", None)


def run_limited(fn, *args, mem_mb=1024, cpu_s=60, wall_s=None, **kwargs):
    """Call ``fn(*args, **kwargs)`` under resource limits and return its result.

    Raises LimitError when a limit is hit; re-raises AnalysisError/ValueError
    messages from the child as the same exception type when possible.
    """
    t0 = time.perf_counter()
    if not AVAILABLE:
        c0 = time.process_time()
        out = fn(*args, **kwargs)
        _stats.value = {"wall": time.perf_counter() - t0, "cpu": time.process_time() - c0, "peakMb": None}
        return out
    wall_s = wall_s or (cpu_s * 2 + 5)
    parent, child = _CTX.Pipe(duplex=False)
    p = _CTX.Process(target=_child, args=(child, fn, args, kwargs, mem_mb, cpu_s), daemon=True)
    p.start()
    child.close()
    try:
        if not parent.poll(wall_s):
            raise LimitError(f"The analysis took longer than {int(wall_s)} s and was stopped.")
        try:
            ok, payload = parent.recv()
        except (EOFError, OSError):
            raise LimitError("The analysis was stopped because it exceeded your memory or CPU allowance.") from None
    finally:
        if p.is_alive():
            p.kill()
        p.join(2)
        parent.close()
    if ok:
        result, cpu, peak = payload
        _stats.value = {"wall": time.perf_counter() - t0, "cpu": cpu, "peakMb": peak}
        return result
    name, msg = payload[0], payload[1]
    if name == "LimitError":
        raise LimitError(msg)
    if name == "AnalysisError":
        from .stats.common import AnalysisError
        raise AnalysisError(msg)
    if name in ("MemoryError",):
        raise LimitError("The analysis needed more memory than your account allows.")
    raise RuntimeError(f"{name}: {msg}")
