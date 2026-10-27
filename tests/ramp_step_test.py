#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""B-LS Wire Test: rampTo moves at its ramp rate; the step commands step (cl. 12.54).

    python3 tests/ramp_step_test.py [--exe build/BACnetExampleBLS] [--port 47840]

ANSI/ASHRAE 135-2024 Table 12-67:
  RAMP_TO "continues by changing the physical lighting output proportionally from its
  current value to target-level, with a fixed rate of change defined by ramp-rate.
  While the ramp operation is executing, In_Progress shall be set to RAMP_ACTIVE".
  STEP_UP "writing the Tracking_Value plus step-increment to the specified slot in the
  priority array. If the result of the addition is greater than 100.0%, the value shall
  be set to 100.0%. If the starting level of Tracking_Value is 0.0%, then this operation
  is ignored." STEP_DOWN subtracts, never below 1.0%. STEP_ON is STEP_UP that writes
  1.0% from off; STEP_OFF is STEP_DOWN that writes 0.0% from 1.0%.
Table 12-66: a command without ramp-rate / step-increment uses Default_Ramp_Rate /
Default_Step_Increment.

The Peer ramps the light 0 -> 60% at 30 %/s and measures the rate from its samples (a
light that snapped, or that faded over a fixed time, has the wrong slope), then ramps
with Default_Ramp_Rate, then steps it.
"""
import sys
import time

import lighting_setup as setup
from lighting_setup import (IDLE, RAMP_ACTIVE, RAMP_TO, SLACK, STEP_DOWN, STEP_OFF, STEP_ON, STEP_UP, acked, describe,
                      near)
from wiretest import sleep_until
import wiretest
from wiretest import record


def ramp(light, target, rate, label, rate_field=True):
    """Ramp from the current level at `rate` %/s and check the measured rate."""
    start_level = light.value(setup.PROPERTY_TRACKING_VALUE)
    expected_seconds = abs(target - start_level) / rate
    fields = {"target_level": target}
    if rate_field:
        fields["ramp_rate"] = rate
    answer = light.command(RAMP_TO, **fields)
    written_at = time.monotonic()
    record(f"{label}: Lighting_Command rampTo {target:.0f}% is accepted", acked(answer), describe(answer))
    present_value = light.value(setup.PROPERTY_PRESENT_VALUE)
    record(f"{label}: Present_Value is the target {target:.0f}% at once", near(present_value, target, 0.01),
           f"read {present_value}")

    samples = setup.sample_light(light, expected_seconds - 0.2)
    levels = [level for _, level, _, _ in samples]
    record(f"{label}: Tracking_Value moves monotonically toward {target:.0f}%",
           wiretest.monotonic(levels, target > start_level),
           f"samples {[round(level, 1) if isinstance(level, float) else level for level in levels]}")
    # The measured rate: the slope between the first and last part-way samples.
    moving = [(sample_time, level, state, state_time) for sample_time, level, state, state_time in samples if isinstance(level, float)
              and min(start_level, target) + 1 < level < max(start_level, target) - 1]
    measured = None
    if len(moving) >= 3 and moving[-1][0] > moving[0][0]:
        measured = abs(moving[-1][1] - moving[0][1]) / (moving[-1][0] - moving[0][0])
    record(f"{label}: Tracking_Value changes at the ramp rate, {rate:.0f} %/s (within 15%)",
           measured is not None and abs(measured - rate) <= rate * 0.15,
           f"measured {measured:.1f} %/s over {len(moving)} samples" if measured is not None else
           f"{len(moving)} part-way samples")
    # Judge In_Progress only where its own read was answered before the ramp could have ended.
    in_progress = [state for _, _, state, state_time in moving if state_time < written_at + expected_seconds - 0.05]
    record(f"{label}: In_Progress is RAMP_ACTIVE whenever Tracking_Value is part-way",
           in_progress and all(state == RAMP_ACTIVE for state in in_progress), f"read {in_progress}")
    sleep_until(written_at, expected_seconds + SLACK)
    present_value, tracking_value, in_progress = light.state()
    record(f"{label}: after {expected_seconds:.1f} s it has arrived - Tracking_Value {target:.0f}%, In_Progress IDLE",
           near(tracking_value, target, 0.01) and in_progress == IDLE,
           f"read Tracking_Value {tracking_value}, In_Progress {in_progress}")


def step(light, operation, label, expected, **fields):
    answer = light.command(operation, **fields)
    level = light.value(setup.PROPERTY_PRESENT_VALUE)
    tracking_value = light.value(setup.PROPERTY_TRACKING_VALUE)
    record(f"{label}: Present_Value and Tracking_Value {expected:.1f}% at once",
           acked(answer) and near(level, expected, 0.01) and near(tracking_value, expected, 0.01),
           f"{describe(answer)}; read Present_Value {level}, Tracking_Value {tracking_value}")


def main():
    args = setup.parser(__doc__).parse_args()
    example = setup.start_light(args)
    light = setup.Light(args)
    try:
        record("Control: Lighting Output 1 is off and idle", light.state() == (0.0, 0.0, IDLE),
               f"read {light.state()}")
        record("Control: Default_Ramp_Rate 10 %/s and Default_Step_Increment 5 % (main.cpp)",
               (light.value(setup.PROPERTY_DEFAULT_RAMP_RATE), light.value(setup.PROPERTY_DEFAULT_STEP_INCREMENT))
               == (10.0, 5.0))

        ramp(light, 60.0, 30.0, "ramp up 0 -> 60 at 30 %/s")
        answer = light.write(setup.PROPERTY_DEFAULT_RAMP_RATE, setup.application_real(40.0))
        record("Default_Ramp_Rate is writable (40 %/s)",
               acked(answer) and light.value(setup.PROPERTY_DEFAULT_RAMP_RATE) == 40.0, describe(answer))
        ramp(light, 10.0, 40.0, "rampTo 10 with no ramp-rate uses Default_Ramp_Rate", rate_field=False)

        # Steps act on Tracking_Value (10% now) and write the result at once.
        step(light, STEP_UP, "stepUp 10 + 5 (Default_Step_Increment)", 15.0)
        step(light, STEP_UP, "stepUp 15 + 7.5 (step-increment field)", 22.5, step_increment=7.5)
        step(light, STEP_UP, "stepUp 22.5 + 90 is clamped to 100%", 100.0, step_increment=90.0)
        step(light, STEP_DOWN, "stepDown 100 - 100 is clamped to 1.0%, not 0", 1.0, step_increment=100.0)
        step(light, STEP_OFF, "stepOff from 1.0% writes 0.0%", 0.0)
        step(light, STEP_UP, "stepUp from off is ignored", 0.0)
        step(light, STEP_DOWN, "stepDown from off is ignored", 0.0)
        step(light, STEP_ON, "stepOn from off writes 1.0%", 1.0)
        step(light, STEP_ON, "stepOn from 1.0% steps up like stepUp", 6.0)
    finally:
        light.close()
        example.stop()
        if not all(wiretest.results.RESULTS):
            example.keep_log()
    return wiretest.summary()


if __name__ == "__main__":
    sys.exit(main())
