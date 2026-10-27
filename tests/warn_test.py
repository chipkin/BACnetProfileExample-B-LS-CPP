#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""B-LS Wire Test: blink-warn holds the light for Egress_Time, then lets it go (cl. 12.54).

    python3 tests/warn_test.py [--exe build/BACnetExampleBLS] [--port 47840]

ANSI/ASHRAE 135-2024:
  Table 12-67 WARN_RELINQUISH "Executes a blink-warn notification at the specified
  priority and then relinquishes the value at the specified priority slot after a delay
  of Egress_Time seconds." WARN_OFF "... then writes the value 0.0% to the specified slot
  in the priority array after a delay of Egress_Time seconds." The blink-warn "shall not
  occur, and the value at the specified priority shall be relinquished immediately if
  ... (c) The Present_Value would not evaluate to 0.0% after the priority slot is
  relinquished."
  Cl. 12.54.15 Egress_Active "shall be TRUE whenever the Egress_Time for a
  WARN_RELINQUISH or WARN_OFF lighting operation is in effect and FALSE otherwise."
  STOP "Cancels any WARN_RELINQUISH or WARN_OFF command in progress at the specified
  priority and cancels the blink-warn egress timer. The value in the priority array at
  the specified priority remains unchanged."
  Table 12-65: Present_Value -2.0 "Provides the same functionality as the
  WARN_RELINQUISH lighting command"; "The special value itself is not written to the
  priority array."
  RESTORE_ON writes Last_On_Value ("the last value of the Present_Value property that
  was greater than or equal to 1.0%", cl. 12.54.44); DEFAULT_ON writes Default_On_Value;
  TOGGLE_RESTORE writes Last_On_Value when Present_Value is 0.0%, else 0.0%.

This is the end-of-day office scene of cl. 12.54's own example (Figure 12-14), with a
5 s Egress_Time instead of 10 minutes. The blink itself is the Simulation's and "shall
not be reflected in the priority array or the tracking value"; Egress_Active is what a
client can see.
"""
import sys
import time

import lighting_setup as setup
from lighting_setup import (DEFAULT_ON, IDLE, RESTORE_ON, SLACK, STOP, TOGGLE_RESTORE, WARN, WARN_OFF, WARN_RELINQUISH,
                      acked, application_real, application_unsigned, describe, near)
from wiretest import sleep_until
import wiretest
from wiretest import record

EGRESS_SECONDS = 5


def lights_on_at_9(light):
    """The 7:00 AM write of Figure 12-14: 100% at priority 9."""
    return acked(light.write(setup.PROPERTY_PRESENT_VALUE, application_real(100.0), priority=9))


def main():
    args = setup.parser(__doc__).parse_args()
    example = setup.start_light(args)
    light = setup.Light(args)
    try:
        record("Control: Egress_Active FALSE and Blink_Warn_Enable TRUE",
               (light.value(setup.PROPERTY_EGRESS_ACTIVE), light.value(setup.PROPERTY_BLINK_WARN_ENABLE))
               == (False, True))
        answer = light.write(setup.PROPERTY_EGRESS_TIME, application_unsigned(EGRESS_SECONDS))
        record(f"Egress_Time is writable ({EGRESS_SECONDS} s)",
               acked(answer) and light.value(setup.PROPERTY_EGRESS_TIME) == EGRESS_SECONDS, describe(answer))

        # --- warnRelinquish: hold, then relinquish ------------------------------------
        record("warnRelinquish: lights on - Present_Value 100 @ 9", lights_on_at_9(light))
        answer = light.command(WARN_RELINQUISH, priority=9)
        written_at = time.monotonic()
        record("warnRelinquish @ 9: accepted, Egress_Active TRUE, the light held at 100%",
               acked(answer) and light.value(setup.PROPERTY_EGRESS_ACTIVE) is True and
               light.state() == (100.0, 100.0, IDLE), f"{describe(answer)}; read {light.state()}")
        sleep_until(written_at, 1.0)
        record("warnRelinquish: part-way through Egress_Time - still 100% @ 9, Egress_Active TRUE",
               light.value(setup.PROPERTY_EGRESS_ACTIVE) is True and
               near(light.value(setup.PROPERTY_PRIORITY_ARRAY, 9), 100.0, 0.01))
        sleep_until(written_at, EGRESS_SECONDS + SLACK)
        record("warnRelinquish: after Egress_Time - Priority_Array[9] NULL, the light off, Egress_Active FALSE",
               light.value(setup.PROPERTY_PRIORITY_ARRAY, 9) is None and light.state() == (0.0, 0.0, IDLE) and
               light.value(setup.PROPERTY_EGRESS_ACTIVE) is False, f"read {light.state()}")

        # --- warnOff: hold, then 0.0% ------------------------------------------------
        record("warnOff: lights on - Present_Value 100 @ 9", lights_on_at_9(light))
        answer = light.command(WARN_OFF, priority=9)
        written_at = time.monotonic()
        record("warnOff @ 9: accepted, Egress_Active TRUE, held at 100%",
               acked(answer) and light.value(setup.PROPERTY_EGRESS_ACTIVE) is True and
               light.value(setup.PROPERTY_PRESENT_VALUE) == 100.0)
        sleep_until(written_at, EGRESS_SECONDS + SLACK)
        record("warnOff: after Egress_Time - 0.0% WRITTEN at priority 9 (not relinquished), Egress_Active FALSE",
               light.value(setup.PROPERTY_PRIORITY_ARRAY, 9) == 0.0 and
               light.value(setup.PROPERTY_EGRESS_ACTIVE) is False and light.state() == (0.0, 0.0, IDLE),
               f"read Priority_Array[9] {light.value(setup.PROPERTY_PRIORITY_ARRAY, 9)}")

        # --- stop cancels the egress timer ------------------------------------------
        record("stop: lights on - Present_Value 100 @ 9", lights_on_at_9(light))
        light.command(WARN_RELINQUISH, priority=9)
        written_at = time.monotonic()
        answer = light.command(STOP, priority=9)
        record("stop @ 9 during the egress time: Egress_Active FALSE, Priority_Array[9] still 100",
               acked(answer) and light.value(setup.PROPERTY_EGRESS_ACTIVE) is False and
               near(light.value(setup.PROPERTY_PRIORITY_ARRAY, 9), 100.0, 0.01), describe(answer))
        sleep_until(written_at, EGRESS_SECONDS + SLACK)
        record("stop: past Egress_Time the light is still on at 100% (the relinquish was cancelled)",
               light.state() == (100.0, 100.0, IDLE), f"read {light.state()}")

        # --- condition (c): someone else still holds the light -------------------------
        light.write(setup.PROPERTY_PRESENT_VALUE, application_real(40.0), priority=12)
        answer = light.command(WARN_RELINQUISH, priority=9)
        record("warnRelinquish @ 9 while priority 12 holds 40%: relinquished at once, no egress (cond. (c))",
               acked(answer) and light.value(setup.PROPERTY_EGRESS_ACTIVE) is False and
               light.value(setup.PROPERTY_PRIORITY_ARRAY, 9) is None and
               light.value(setup.PROPERTY_PRESENT_VALUE) == 40.0)
        record("reset: relinquished, off and idle", setup.reset(light))

        # --- the Present_Value special value -2.0 -------------------------------------
        record("special value: lights on - Present_Value 100 @ 9", lights_on_at_9(light))
        answer = light.write(setup.PROPERTY_PRESENT_VALUE, application_real(-2.0), priority=9)
        written_at = time.monotonic()
        record("Present_Value -2.0 @ 9 acts as warnRelinquish: accepted, Egress_Active TRUE, "
               "-2.0 not written (Priority_Array[9] still 100)",
               acked(answer) and light.value(setup.PROPERTY_EGRESS_ACTIVE) is True and
               near(light.value(setup.PROPERTY_PRIORITY_ARRAY, 9), 100.0, 0.01), describe(answer))
        sleep_until(written_at, EGRESS_SECONDS + SLACK)
        record("Present_Value -2.0: after Egress_Time priority 9 is relinquished",
               light.value(setup.PROPERTY_PRIORITY_ARRAY, 9) is None and light.state() == (0.0, 0.0, IDLE))

        # --- restoreOn / defaultOn / toggleRestore / warn ------------------------------
        light.write(setup.PROPERTY_PRESENT_VALUE, application_real(35.0), priority=16)
        light.write(setup.PROPERTY_PRESENT_VALUE, application_real(0.0), priority=16)
        record("Last_On_Value is the last Present_Value >= 1.0% (35, not the 0 after it)",
               light.value(setup.PROPERTY_LAST_ON_VALUE) == 35.0,
               f"read {light.value(setup.PROPERTY_LAST_ON_VALUE)}")
        answer = light.command(RESTORE_ON)
        record("restoreOn writes Last_On_Value: 35% @ 16 at once",
               acked(answer) and light.state() == (35.0, 35.0, IDLE), f"read {light.state()}")
        answer = light.command(TOGGLE_RESTORE)
        record("toggleRestore while on writes 0.0%", acked(answer) and light.state() == (0.0, 0.0, IDLE),
               f"read {light.state()}")
        answer = light.command(TOGGLE_RESTORE)
        record("toggleRestore while off writes Last_On_Value (35%)",
               acked(answer) and light.state() == (35.0, 35.0, IDLE), f"read {light.state()}")
        answer = light.command(DEFAULT_ON)
        record("defaultOn writes Default_On_Value (100%)",
               acked(answer) and light.state() == (100.0, 100.0, IDLE) and
               light.value(setup.PROPERTY_DEFAULT_ON_VALUE) == 100.0, f"read {light.state()}")
        answer = light.command(WARN)
        record("warn leaves the level unchanged and starts no egress timer",
               acked(answer) and light.state() == (100.0, 100.0, IDLE) and
               light.value(setup.PROPERTY_EGRESS_ACTIVE) is False, f"read {light.state()}")
    finally:
        light.close()
        example.stop()
        if not all(wiretest.results.RESULTS):
            example.keep_log()
    return wiretest.summary()


if __name__ == "__main__":
    sys.exit(main())
