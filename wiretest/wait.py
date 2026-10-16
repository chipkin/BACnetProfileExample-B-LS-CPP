# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""Waiting for a running example to reach a state (came from B-BC's tests, wiretest 0.6.0)."""
import time


def wait_until(check, seconds, interval=0.2):
    """Call `check()` until it returns something truthy or `seconds` pass; return its last
    result. A test that needs a value the example reaches only after a tick or a timer
    polls for it this way instead of sleeping a fixed time."""
    deadline = time.monotonic() + seconds
    while True:
        result = check()
        if result or time.monotonic() >= deadline:
            return result
        time.sleep(interval)
