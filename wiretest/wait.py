# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""Waiting for a running example to reach a state, and sampling it over time.

wait_until came from B-BC's tests (wiretest 0.6.0); sample, sleep_until and monotonic from
B-LD's tests/ld_setup.py (0.7.0).
"""
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


def sleep_until(start, seconds):
    """Sleep until `seconds` after the time.monotonic() instant `start` (no sleep if it has passed)."""
    remaining = start + seconds - time.monotonic()
    if remaining > 0:
        time.sleep(remaining)


def sample(read, seconds, interval=0.1):
    """Call `read()` every `interval` s for `seconds`; returns what each call returned. A read
    that takes longer than `interval` delays the next one rather than overlapping it."""
    samples = []
    start = time.monotonic()
    while time.monotonic() - start < seconds:
        sent = time.monotonic()
        samples.append(read())
        sleep_until(sent, interval)
    return samples


def monotonic(values, rising=True):
    """True when every value is a float and none moves the wrong way (equal neighbours allowed)."""
    if not values or not all(isinstance(value, float) for value in values):
        return False
    pairs = list(zip(values, values[1:]))
    return all(later >= earlier for earlier, later in pairs) if rising else \
        all(later <= earlier for earlier, later in pairs)
