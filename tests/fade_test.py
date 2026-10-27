#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""B-LS Wire Test: a fadeTo fades the light over its fade time (DS-LO-B, cl. 12.54).

    python3 tests/fade_test.py [--exe build/BACnetExampleBLS] [--port 47840]

ANSI/ASHRAE 135-2024 Table 12-67, FADE_TO: "the fade operation continues by changing
the physical lighting output proportionally from its current value to target-level,
over a period of time defined by fade-time. While the fade operation is executing,
In_Progress shall be set to FADE_ACTIVE, and Tracking_Value shall be updated to reflect
the current progress of the fade." Cl. 12.54.4: "When a ramp or fade lighting command
is in progress, the Present_Value shall indicate the target level of the operation and
not the current value." Cl. 12.54.5: "When the value of In_Progress is IDLE,
Tracking_Value shall be equal to Present_Value."

A Python client (the Peer, a lighting supervisor) writes Lighting_Command fadeTo and
samples Tracking_Value and In_Progress every 0.1 s: Present_Value is the target at once,
Tracking_Value climbs monotonically and in proportion to the elapsed time, In_Progress
is FADE_ACTIVE until it arrives, then IDLE with Tracking_Value equal to Present_Value.
A light that snapped to the level - what this example did before its Lighting Output engine - fails every
mid-fade check.
"""
import sys
import time

import lighting_setup as setup
from lighting_setup import FADE_ACTIVE, FADE_TO, IDLE, SLACK, acked, describe, near
from wiretest import sleep_until
import wiretest
from wiretest import record


def fade(light, target, fade_seconds, label, fade_time_field=True):
    """Command a fade from the current level and check it all the way; returns nothing."""
    start_level = light.value(setup.PROPERTY_TRACKING_VALUE)
    fields = {"target_level": target}
    if fade_time_field:
        fields["fade_time"] = int(fade_seconds * 1000)
    answer = light.command(FADE_TO, **fields)
    written_at = time.monotonic()
    record(f"{label}: Lighting_Command fadeTo {target:.0f}% is accepted", acked(answer), describe(answer))

    present_value = light.value(setup.PROPERTY_PRESENT_VALUE)
    record(f"{label}: Present_Value is the TARGET {target:.0f}% at once (cl. 12.54.4)",
           near(present_value, target, 0.01), f"read {present_value}")
    slot = light.value(setup.PROPERTY_PRIORITY_ARRAY, 16)
    record(f"{label}: target written to Priority_Array[16] (Lighting_Command_Default_Priority)",
           near(slot, target, 0.01), f"read {slot}")

    samples = setup.sample_light(light, fade_seconds - 0.15)
    levels = [level for _, level, _, _ in samples]
    rising = target > start_level
    record(f"{label}: Tracking_Value moves monotonically toward {target:.0f}% ({len(levels)} samples)",
           wiretest.monotonic(levels, rising),
           f"samples {[round(level, 1) if isinstance(level, float) else level for level in levels]}")
    low, high = sorted((start_level, target))
    moving = [(sample_time, level, state, state_time) for sample_time, level, state, state_time in samples
              if isinstance(level, float) and low + 1 < level < high - 1]
    record(f"{label}: Tracking_Value passes through intermediate levels (>= 3 distinct between "
           f"{low:.0f}% and {high:.0f}%)", len(set(round(level, 1) for _, level, _, _ in moving)) >= 3,
           f"{len(moving)} intermediate samples")

    # Proportional: at time t the level is start + (target - start) * t / fade_time. A sample's
    # time is known to within its round trip plus the example's 1 ms tick; allow 8 points.
    deviations = [abs(level - (start_level + (target - start_level) * (sample_time - written_at) / fade_seconds))
                  for sample_time, level, _, _ in moving]
    record(f"{label}: Tracking_Value follows the fade time proportionally (within 8 points of "
           f"start + (target - start) * t / {fade_seconds:.1f} s)",
           deviations and max(deviations) <= 8.0,
           f"largest deviation {max(deviations):.1f}" if deviations else "no samples")

    # Judge In_Progress only where its own read was answered before the fade could have ended.
    in_progress = [state for _, _, state, state_time in moving if state_time < written_at + fade_seconds - 0.05]
    record(f"{label}: In_Progress is FADE_ACTIVE whenever Tracking_Value is part-way",
           in_progress and all(state == FADE_ACTIVE for state in in_progress), f"read {in_progress}")

    sleep_until(written_at, fade_seconds + SLACK)
    present_value, tracking_value, in_progress = light.state()
    record(f"{label}: after {fade_seconds:.1f} s Tracking_Value has arrived at {target:.0f}%",
           near(tracking_value, target, 0.01), f"read {tracking_value}")
    record(f"{label}: after {fade_seconds:.1f} s In_Progress is IDLE and Tracking_Value equals Present_Value",
           in_progress == IDLE and tracking_value == present_value,
           f"read In_Progress {in_progress}, Tracking_Value {tracking_value}, Present_Value {present_value}")


def main():
    args = setup.parser(__doc__).parse_args()
    example = setup.start_light(args)
    light = setup.Light(args)
    try:
        # Controls: the light is off, idle, uncommanded, with the defaults main.cpp sets.
        record("Control: Lighting Output 1 is off and idle (Present_Value 0, Tracking_Value 0, In_Progress IDLE)",
               light.state() == (0.0, 0.0, IDLE), f"read {light.state()}")
        command = wiretest.services.decode_lighting_command(light.read(setup.PROPERTY_LIGHTING_COMMAND).value_octets)
        record("Control: Lighting_Command reads NONE before anything has been written (cl. 12.54.6)",
               command == {"operation": setup.NONE}, f"read {command}")

        fade(light, 80.0, 2.0, "fade up 0 -> 80 over 2.0 s")
        fade(light, 20.0, 1.5, "fade down 80 -> 20 over 1.5 s")

        # Default_Fade_Time: a fadeTo without fade-time fades over it (Table 12-66).
        answer = light.write(setup.PROPERTY_DEFAULT_FADE_TIME, setup.application_unsigned(1500))
        record("Default_Fade_Time is writable (1500 ms)",
               acked(answer) and light.value(setup.PROPERTY_DEFAULT_FADE_TIME) == 1500, describe(answer))
        fade(light, 60.0, 1.5, "fadeTo 60 with no fade-time uses Default_Fade_Time", fade_time_field=False)
        command = wiretest.services.decode_lighting_command(light.read(setup.PROPERTY_LIGHTING_COMMAND).value_octets)
        record("Lighting_Command reads back the last command as written (no fade-time field)",
               command == {"operation": FADE_TO, "target_level": 60.0}, f"read {command}")
    finally:
        light.close()
        example.stop()
        if not all(wiretest.results.RESULTS):
            example.keep_log()
    return wiretest.summary()


if __name__ == "__main__":
    sys.exit(main())
