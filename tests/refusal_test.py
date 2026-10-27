#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""B-LS Wire Test: Lighting Output 1 refuses a bad command and it changes nothing (cl. 12.54).

    python3 tests/refusal_test.py [--exe build/BACnetExampleBLS] [--port 47840]

Part 1 of BACnetProfileExample-B-LD-CPP's tests/failure_test.py, aimed at this device's
Jade (B-LS has no lamp Simulation, so parts 2 and 3 - the burnt-out lamp and the
Out_Of_Service Reliability write - do not apply).

ANSI/ASHRAE 135-2024 cl. 12.54.6: "Lighting commands written with a required or optional
field, explicitly specified for this command, which are outside of the allowable range of
values, shall cause a Result(-) to be returned with an 'Error Class' of PROPERTY and an
'Error Code' of VALUE_OUT_OF_RANGE." Table 12-67 NONE: "This operation shall not be
written to the Lighting_Command property" (same error). Cl. 12.54.4: Present_Value outside
0.0% to 100.0% (other than the special values) - same error. Cl. 12.54.16 / 12.54.17 /
12.54.18: Default_Fade_Time / Default_Ramp_Rate / Default_Step_Increment outside their
ranges - same error.
"""
import sys
import time

import lighting_setup as setup
from lighting_setup import (FADE_TO, IDLE, NONE, RAMP_TO, SLACK, STEP_UP, acked, application_real,
                            application_unsigned, describe, value_out_of_range)
import wiretest
from wiretest import record

def refused_and_unchanged(light, label, write):
    """`write()` must be answered PROPERTY / VALUE_OUT_OF_RANGE and leave the light,
    Priority_Array[16] and Lighting_Command as they were."""
    before = (light.state(), light.value(setup.PROPERTY_PRIORITY_ARRAY, 16),
              light.read(setup.PROPERTY_LIGHTING_COMMAND).value_octets)
    answer = write()
    time.sleep(0.2)   # long enough for a wrongly-accepted fade to have moved the light
    after = (light.state(), light.value(setup.PROPERTY_PRIORITY_ARRAY, 16),
             light.read(setup.PROPERTY_LIGHTING_COMMAND).value_octets)
    record(f"{label}: Error PROPERTY / VALUE_OUT_OF_RANGE", value_out_of_range(answer), describe(answer))
    record(f"{label}: the light, Priority_Array[16] and Lighting_Command are unchanged", before == after,
           f"before {before[:2]}, after {after[:2]}")


def bad_commands(light):
    # A level to compare against: 50% @ 16, idle.
    light.write(setup.PROPERTY_PRESENT_VALUE, application_real(50.0), priority=16)
    record("Control: the light is at 50% @ 16 and idle", light.state() == (50.0, 50.0, IDLE),
           f"read {light.state()}")
    refused_and_unchanged(light, "fadeTo with fade-time 50 ms (range 100..86400000)",
                          lambda: light.command(FADE_TO, target_level=80.0, fade_time=50))
    refused_and_unchanged(light, "fadeTo target-level 150% (range 0..100)",
                          lambda: light.command(FADE_TO, target_level=150.0, fade_time=1000))
    refused_and_unchanged(light, "rampTo ramp-rate 0.05 %/s (range 0.1..100)",
                          lambda: light.command(RAMP_TO, target_level=80.0, ramp_rate=0.05))
    refused_and_unchanged(light, "stepUp step-increment 0 (range 0.1..100)",
                          lambda: light.command(STEP_UP, step_increment=0.0))
    refused_and_unchanged(light, "operation NONE",
                          lambda: light.command(NONE))
    refused_and_unchanged(light, "fadeTo with no target-level (a required field)",
                          lambda: light.command(FADE_TO, fade_time=1000))
    refused_and_unchanged(light, "Present_Value 120 @ 16",
                          lambda: light.write(setup.PROPERTY_PRESENT_VALUE, application_real(120.0), priority=16))
    refused_and_unchanged(light, "Present_Value -8.0 @ 16 (not a special value)",
                          lambda: light.write(setup.PROPERTY_PRESENT_VALUE, application_real(-8.0), priority=16))
    for property_identifier, name, octets, readback in (
            (setup.PROPERTY_DEFAULT_FADE_TIME, "Default_Fade_Time 50 ms", application_unsigned(50), 3000),
            (setup.PROPERTY_DEFAULT_RAMP_RATE, "Default_Ramp_Rate 0 %/s", application_real(0.0), 10.0),
            (setup.PROPERTY_DEFAULT_STEP_INCREMENT, "Default_Step_Increment 101 %", application_real(101.0), 5.0)):
        answer = light.write(property_identifier, octets)
        record(f"{name}: Error PROPERTY / VALUE_OUT_OF_RANGE and the old value kept",
               value_out_of_range(answer) and light.value(property_identifier) == readback,
               f"{describe(answer)}; reads {light.value(property_identifier)}")
    # The light still obeys a good command after all that.
    answer = light.command(FADE_TO, target_level=70.0, fade_time=300)
    time.sleep(0.3 + SLACK)
    record("after the refusals a valid fadeTo 70 still works", acked(answer) and light.state() == (70.0, 70.0, IDLE),
           f"read {light.state()}")


def main():
    args = setup.parser(__doc__).parse_args()
    example = setup.start_light(args)
    light = setup.Light(args)
    try:
        bad_commands(light)
    finally:
        light.close()
        example.stop()
        if not all(wiretest.results.RESULTS):
            example.keep_log()
    return wiretest.summary()


if __name__ == "__main__":
    sys.exit(main())
