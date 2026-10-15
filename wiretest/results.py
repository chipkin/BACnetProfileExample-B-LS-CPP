# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""Pass/fail bookkeeping shared by every wire test."""

RESULTS = []
GAPS = []


def record(name, ok, detail=""):
    """One checked requirement. A wire test exits non-zero if any record() is False."""
    ok = bool(ok)
    RESULTS.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""), flush=True)
    return ok


def known_gap(name, ok, cause):
    """A requirement the example cannot meet yet because of a defect OUTSIDE it (the stack or
    common/), named by `cause`. Reported on every run but not counted as a failure, so record()
    keeps gating what the example itself does. When one starts passing, the defect is fixed:
    turn it into a record() check and drop its TODO.md entry."""
    ok = bool(ok)
    if ok:
        print(f"[GAP CLOSED] {name} - now passes; make it a checked requirement ({cause})", flush=True)
    else:
        GAPS.append(name)
        print(f"[KNOWN GAP] {name} - {cause}", flush=True)
    return ok


def summary():
    """Print the totals; returns the process exit code (0 = every check passed)."""
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} checks passed" +
          (f"; {len(GAPS)} known gap(s), see TODO.md" if GAPS else ""))
    return 0 if RESULTS and all(RESULTS) else 1
