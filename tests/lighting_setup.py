# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""What B-LS's Lighting Output Wire Tests share: Jade's numbers, and starting it.

Ported from BACnetProfileExample-B-LD-CPP's tests/ld_setup.py with its Lighting Output
engine (main.cpp section 1b); fade_test.py, ramp_step_test.py, stop_priority_test.py and
warn_test.py are B-LD's tests, aimed at this device.

The setup, all on one host:

    test client (127.0.0.1, ephemeral UDP port) - the Peer: a Python BACnet client
        |  BACnet/IP, unicast
    BACnetExampleBLS   UDP --port   Lighting Output 1 "Jade"

The Peer plays the part of whatever commands the light on a real site - a lighting
controller, a wall-station gateway, an operator workstation. It writes Lighting_Command
and Present_Value and reads the light back over the wire exactly as those would; nothing
reaches into the example any other way.

One difference from B-LD: on this supervisor Jade is a member of Channel 1, and Schedule 1
writes Channel 1 at priority 12 from start-up, so Jade starts at 100.0 % at priority 12.
start_light() relinquishes that slot (and every other) so each test starts from the
light off and idle, as on B-LD.

The BACnetLightingCommand encoder and decoder, sample() and monotonic() are wiretest 0.7.0's
(wiretest.services.lighting_command / decode_lighting_command, wiretest.sample,
wiretest.monotonic); this file keeps what is about this light.
"""
import argparse
import sys
import time
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY))

import wiretest  # noqa: E402  (the vendored harness at the repository root)
from wiretest import application_boolean, application_enumerated, application_null  # noqa: E402,F401
from wiretest import application_real, application_unsigned  # noqa: E402,F401

# Match main.cpp.
DEVICE_INSTANCE = 389017
OBJECT_TYPE_LIGHTING_OUTPUT = 54
LIGHT = (OBJECT_TYPE_LIGHTING_OUTPUT, 1)      # Lighting Output 1 "Jade"
DEFAULT_PORT = 47840                          # this example's own port (series allocation)

# Lighting Output properties (cl. 12.54; numbers from cl. 21 BACnetPropertyIdentifier).
PROPERTY_PRESENT_VALUE = wiretest.PROPERTY_PRESENT_VALUE
PROPERTY_PRIORITY_ARRAY = wiretest.PROPERTY_PRIORITY_ARRAY
PROPERTY_CURRENT_COMMAND_PRIORITY = wiretest.PROPERTY_CURRENT_COMMAND_PRIORITY
PROPERTY_OUT_OF_SERVICE = 81
PROPERTY_RELIABILITY = 103
PROPERTY_STATUS_FLAGS = 111
PROPERTY_TRACKING_VALUE = 164
PROPERTY_BLINK_WARN_ENABLE = 373
PROPERTY_DEFAULT_FADE_TIME = 374
PROPERTY_DEFAULT_RAMP_RATE = 375
PROPERTY_DEFAULT_STEP_INCREMENT = 376
PROPERTY_EGRESS_TIME = 377
PROPERTY_IN_PROGRESS = 378
PROPERTY_LIGHTING_COMMAND = 380
PROPERTY_LIGHTING_COMMAND_DEFAULT_PRIORITY = 381
PROPERTY_EGRESS_ACTIVE = 386
PROPERTY_DEFAULT_ON_VALUE = 4194341
PROPERTY_LAST_ON_VALUE = 4194342

# BACnetLightingOperation, BACnetLightingInProgress, BACnetReliability (cl. 21).
NONE, FADE_TO, RAMP_TO, STEP_UP, STEP_DOWN, STEP_ON, STEP_OFF = 0, 1, 2, 3, 4, 5, 6
WARN, WARN_OFF, WARN_RELINQUISH, STOP, RESTORE_ON, DEFAULT_ON = 7, 8, 9, 10, 11, 12
TOGGLE_RESTORE, TOGGLE_DEFAULT = 13, 14
IDLE, FADE_ACTIVE, RAMP_ACTIVE = 0, 1, 2
NO_FAULT_DETECTED, LAMP_FAILURE = 0, 16

# BACnetStatusFlags bit positions (cl. 21): {in-alarm, fault, overridden, out-of-service}.
STATUS_FLAG_FAULT = 1
STATUS_FLAG_OUT_OF_SERVICE = 3

ERROR_CLASS_OBJECT, ERROR_CLASS_PROPERTY = 1, 2
ERROR_CODE_UNKNOWN_OBJECT = 31
ERROR_CODE_VALUE_OUT_OF_RANGE = 37
ERROR_CODE_WRITE_ACCESS_DENIED = 40

REQUEST_TIMEOUT, RETRIES = 1.0, 2   # a confirmed request unanswered after 1 s is sent again, up to twice (as Light does)

SLACK = 0.35        # seconds allowed for the example's tick and the round trip
LEVEL_TOLERANCE = 1.0   # percent: a sample's timestamp is only known to within one round trip



def parser(description):
    arguments = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    arguments.add_argument("--exe", default=str(wiretest.default_exe(REPOSITORY, "BACnetExampleBLS")),
                           help="path to BACnetExampleBLS (default: build/BACnetExampleBLS)")
    arguments.add_argument("--port", type=int, default=DEFAULT_PORT,
                           help=f"the lighting supervisor's UDP port (default {DEFAULT_PORT})")
    return arguments


def start_light(args, label="light", environment=None):
    """Start the example, then relinquish Schedule 1's start-up write to Jade (via Channel 1,
    priority 12) so the light is off and idle."""
    example = wiretest.start(args.exe, ["--port", args.port], label, environment)
    light = Light(args)
    try:
        if not reset(light):
            print(f"[NOTE] Jade was not off and idle after start-up and reset: {light.state()}", flush=True)
    finally:
        light.close()
    return example


class Light:
    """Lighting Output 1 as the Peer sees it: a wiretest.Client aimed at the device.
    Up to two retries after 1 s each, as a BACnet client makes (it prints [RETRY] when
    one is needed): a lost datagram must not eat a fade's sampling window."""

    def __init__(self, args):
        self.client = wiretest.Client(retries=2, timeout=1.0)
        self.port = args.port

    def read(self, property_identifier, array_index=None):
        return self.client.read_property(self.port, *LIGHT, property_identifier, array_index)

    def value(self, property_identifier, array_index=None):
        """The decoded value (NULL -> None), or 'no answer' / 'error' so a comparison with
        an expected value fails readably."""
        answer = self.read(property_identifier, array_index)
        if not answer.answered:
            return "no answer"
        if not answer.ok:
            return "error"
        return answer.value

    def write(self, property_identifier, value_octets, priority=None):
        return self.client.write_property(self.port, *LIGHT, property_identifier, value_octets, priority)

    def command(self, operation, **fields):
        """WriteProperty Lighting_Command."""
        return self.write(PROPERTY_LIGHTING_COMMAND, wiretest.services.lighting_command(operation, **fields))

    def state(self):
        """(Present_Value, Tracking_Value, In_Progress)."""
        return (self.value(PROPERTY_PRESENT_VALUE), self.value(PROPERTY_TRACKING_VALUE),
                self.value(PROPERTY_IN_PROGRESS))

    def close(self):
        self.client.close()


def acked(answer):
    return answer.acked


def value_out_of_range(answer):
    return answer.error == (ERROR_CLASS_PROPERTY, ERROR_CODE_VALUE_OUT_OF_RANGE)


def near(value, expected, tolerance=LEVEL_TOLERANCE):
    return isinstance(value, float) and abs(value - expected) <= tolerance


def sample_light(light, seconds, interval=0.1, slowest=0.25):
    """Sample the light every `interval` s for `seconds`: [(t, Tracking_Value, In_Progress,
    t_in_progress)], t the time.monotonic() half-way through the Tracking_Value read's round
    trip and t_in_progress the time the In_Progress read (which follows it) was answered.
    A sample whose Tracking_Value read took longer than `slowest` s (a [RETRY]) is dropped:
    its time is not known well enough to judge a fade by."""
    def read():
        sent = time.monotonic()
        tracking_value = light.value(PROPERTY_TRACKING_VALUE)
        received = time.monotonic()
        in_progress = light.value(PROPERTY_IN_PROGRESS)
        return (sent + received) / 2, tracking_value, in_progress, time.monotonic(), received - sent
    return [(midpoint, level, state, state_time) for midpoint, level, state, state_time, round_trip
            in wiretest.sample(read, seconds, interval) if round_trip <= slowest]


def reset(light):
    """Relinquish every Priority_Array slot (which also halts any command in progress)
    and wait until the light is off and idle. True when it got there."""
    for priority in range(1, 17):
        light.write(PROPERTY_PRESENT_VALUE, application_null(), priority=priority)
    return wiretest.wait_until(lambda: light.state() == (0.0, 0.0, IDLE), 2.0)


def describe(answer):
    return answer.describe()
