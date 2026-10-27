#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""B-LS Wire Test: stop holds a fade; priorities arbitrate fades and writes (cl. 12.54).

    python3 tests/stop_priority_test.py [--exe build/BACnetExampleBLS] [--port 47840]

ANSI/ASHRAE 135-2024:
  Table 12-67 STOP "Stops any FADE_TO or RAMP_TO command in progress at the specified
  priority and writes the current value of Tracking_Value to that slot in the priority
  array and sets In_Progress to IDLE. ... If there is no fade, ramp, or warn command
  currently executing at the specified priority, then this operation is ignored."
  Table 12-67 FADE_TO "After the reevaluation of the priority array, if the provided
  priority is not the current command priority, this fade operation shall not be
  executed."
  Cl. 12.54.6.1: a command in progress "shall be halted under the following conditions:
  ... (b) The Present_Value is written at a higher priority than the command in
  progress." and "When a RAMP_TO or FADE_TO command that is currently in progress is
  halted, the internal ramp or fade algorithm is halted, and the corresponding slot in
  the priority array remains unchanged."
  "A lighting command that is in progress is implicitly halted when it is overwritten
  by another lighting command at the same priority or by a write to the Present_Value at
  the same priority."
  Cl. 12.54.19: with no Transition property, the transition "shall be assumed to be
  NONE": a relinquish takes effect at once.

The Peer is two lighting systems at once: a scheduler fading the light at priority 16
and an operator overriding at priority 8.
"""
import sys
import time

import lighting_setup as setup
from lighting_setup import FADE_ACTIVE, FADE_TO, IDLE, SLACK, STOP, acked, application_null, application_real, \
    describe, near
from wiretest import sleep_until
import wiretest
from wiretest import record


def main():
    args = setup.parser(__doc__).parse_args()
    example = setup.start_light(args)
    light = setup.Light(args)
    try:
        record("Control: Lighting Output 1 is off and idle", light.state() == (0.0, 0.0, IDLE),
               f"read {light.state()}")

        # --- stop mid-fade holds the level --------------------------------------
        answer = light.command(FADE_TO, target_level=100.0, fade_time=5000, priority=16)
        written_at = time.monotonic()
        sleep_until(written_at, 1.0)
        record("stop: a 5 s fadeTo 100 @ 16 is FADE_ACTIVE at 1.0 s",
               acked(answer) and light.value(setup.PROPERTY_IN_PROGRESS) == FADE_ACTIVE)
        answer = light.command(STOP, priority=12)
        record("stop @ 12 while the fade runs @ 16 is ignored (nothing runs at 12) - still FADE_ACTIVE",
               acked(answer) and light.value(setup.PROPERTY_IN_PROGRESS) == FADE_ACTIVE, describe(answer))
        answer = light.command(STOP, priority=16)
        stopped_level = light.value(setup.PROPERTY_TRACKING_VALUE)
        record("stop @ 16 is accepted and the fade stops part-way (5% < Tracking_Value < 95%)",
               acked(answer) and isinstance(stopped_level, float) and 5.0 < stopped_level < 95.0,
               f"{describe(answer)}; read {stopped_level}")
        present_value, tracking_value, in_progress = light.state()
        record("stop: In_Progress IDLE, and Present_Value / Priority_Array[16] hold the stopped level, not 100",
               in_progress == IDLE and near(present_value, stopped_level, 0.5) and
               near(light.value(setup.PROPERTY_PRIORITY_ARRAY, 16), stopped_level, 0.5),
               f"read In_Progress {in_progress}, Present_Value {present_value}, "
               f"Priority_Array[16] {light.value(setup.PROPERTY_PRIORITY_ARRAY, 16)}")
        sleep_until(written_at, 5.0 + SLACK)
        held = light.value(setup.PROPERTY_TRACKING_VALUE)
        record("stop: past the fade's end the level is still held where it stopped",
               near(held, stopped_level, 0.5), f"read {held}, stopped at {stopped_level}")

        # --- a higher-priority Present_Value write halts a fade --------------------
        record("reset: relinquished, off and idle", setup.reset(light))
        light.command(FADE_TO, target_level=80.0, fade_time=1500, priority=16)
        written_at = time.monotonic()
        sleep_until(written_at, 0.5)
        answer = light.write(setup.PROPERTY_PRESENT_VALUE, application_real(30.0), priority=8)
        present_value, tracking_value, in_progress = light.state()
        record("override: Present_Value 30 @ 8 mid-fade halts the fade @ 16 - In_Progress IDLE, "
               "Tracking_Value 30 at once",
               acked(answer) and in_progress == IDLE and near(tracking_value, 30.0, 0.01) and
               near(present_value, 30.0, 0.01),
               f"{describe(answer)}; read {(present_value, tracking_value, in_progress)}")
        record("override: Priority_Array[16] keeps the halted fade's target (80) and "
               "Current_Command_Priority is 8",
               near(light.value(setup.PROPERTY_PRIORITY_ARRAY, 16), 80.0, 0.01) and
               light.value(setup.PROPERTY_CURRENT_COMMAND_PRIORITY) == 8)
        sleep_until(written_at, 1.5 + SLACK)
        record("override: the halted fade does not move the light afterwards - Tracking_Value still 30",
               near(light.value(setup.PROPERTY_TRACKING_VALUE), 30.0, 0.01),
               f"read {light.value(setup.PROPERTY_TRACKING_VALUE)}")
        answer = light.write(setup.PROPERTY_PRESENT_VALUE, application_null(), priority=8)
        record("override: relinquish @ 8 - Present_Value and Tracking_Value go to priority 16's 80 at once "
               "(no Transition), In_Progress IDLE",
               acked(answer) and light.state() == (80.0, 80.0, IDLE), f"read {light.state()}")

        # --- a write at the SAME priority halts a fade -----------------------------
        record("reset: relinquished, off and idle", setup.reset(light))
        light.command(FADE_TO, target_level=90.0, fade_time=1500, priority=16)
        written_at = time.monotonic()
        sleep_until(written_at, 0.4)
        answer = light.write(setup.PROPERTY_PRESENT_VALUE, application_real(25.0), priority=16)
        record("same priority: Present_Value 25 @ 16 mid-fade @ 16 halts it - In_Progress IDLE, "
               "Present_Value and Tracking_Value 25 at once (cl. 12.54.6.1 \"implicitly halted\")",
               acked(answer) and light.state() == (25.0, 25.0, IDLE), f"read {light.state()}")
        sleep_until(written_at, 1.5 + SLACK)
        record("same priority: and the halted fade never takes the light to 90 afterwards",
               light.state() == (25.0, 25.0, IDLE), f"read {light.state()}")

        # --- a lower-priority write does not halt a fade -------------------------
        record("reset: relinquished, off and idle", setup.reset(light))
        light.command(FADE_TO, target_level=60.0, fade_time=2500, priority=8)
        written_at = time.monotonic()
        sleep_until(written_at, 0.3)
        answer = light.write(setup.PROPERTY_PRESENT_VALUE, application_real(90.0), priority=12)
        record("lower priority: Present_Value 90 @ 12 mid-fade @ 8 is stored but the fade keeps running",
               acked(answer) and light.value(setup.PROPERTY_IN_PROGRESS) == FADE_ACTIVE and
               near(light.value(setup.PROPERTY_PRIORITY_ARRAY, 12), 90.0, 0.01) and
               near(light.value(setup.PROPERTY_PRESENT_VALUE), 60.0, 0.01))
        sleep_until(written_at, 2.5 + SLACK)
        record("lower priority: the fade @ 8 arrives at 60 regardless",
               light.state() == (60.0, 60.0, IDLE), f"read {light.state()}")

        # --- a fade at a priority that is not in control is not executed -----------
        answer = light.command(FADE_TO, target_level=10.0, fade_time=1000, priority=16)
        present_value, tracking_value, in_progress = light.state()
        record("not in control: fadeTo 10 @ 16 while 8 holds 60 is accepted and written to "
               "Priority_Array[16] ...",
               acked(answer) and near(light.value(setup.PROPERTY_PRIORITY_ARRAY, 16), 10.0, 0.01),
               describe(answer))
        record("not in control: ... but not executed - In_Progress IDLE, Present_Value and "
               "Tracking_Value stay 60",
               (present_value, tracking_value, in_progress) == (60.0, 60.0, IDLE),
               f"read {(present_value, tracking_value, in_progress)}")
    finally:
        light.close()
        example.stop()
        if not all(wiretest.results.RESULTS):
            example.keep_log()
    return wiretest.summary()


if __name__ == "__main__":
    sys.exit(main())
