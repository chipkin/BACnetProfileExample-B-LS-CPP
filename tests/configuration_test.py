#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""B-LS Wire Test: the command line - the Device's identity is configurable at start-up
(--deviceID, --deviceName), and --help lists exactly the options the example reads.

    python3 tests/configuration_test.py [--exe build/BACnetExampleBLS] [--port 47840]

BACnet requires a device's Object_Identifier and Object_Name to be configurable
(135-2024 cl. 12.1.1.3, 12.1.1.4; BTL tests 7.3.2.10.9 / 7.3.2.10.10): Object_Name must
be unique across the internetwork, so two units of one product cannot share a
compile-time name. This lighting supervisor takes both on its command line. The test
starts it several times:

    1. with no identity options     -> Device 389017 "Chipkin Example B-LS" (the defaults)
    2. --deviceID 389917 --deviceName "Chipkin Example B-LS Unit 2"
                                    -> Who-Is, ReadProperty and Who-Has all see the
                                       configured instance and name; 389017 is gone;
                                       a WriteProperty of Object_Name is refused (the
                                       name changes only at start-up)
    3. invalid names (empty, 256 bytes) -> a warning, and the default name; a
       255-byte name is accepted whole
    4. --help lists --port, --deviceID, --deviceName and --xml, and not --dcc-password
       (this example's DeviceCommunicationControl password is a source constant, not
       an option); --xml prints each frame as XML

Exit code 0 = every check passed.
"""
import argparse
import subprocess
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY))

import wiretest  # noqa: E402  (the vendored harness at the repository root)
from wiretest import codec  # noqa: E402
from wiretest import record as record_check, summary  # noqa: E402

DEFAULT_INSTANCE = 389017
DEFAULT_NAME = "Chipkin Example B-LS"
CONFIGURED_INSTANCE = 389917
CONFIGURED_NAME = "Chipkin Example B-LS Unit 2"
LONGEST_NAME = "N" * 255          # common/ MAX_DEVICE_NAME_LENGTH
TOO_LONG_NAME = "N" * 256
SERVICE_I_HAVE, SERVICE_WHO_HAS = 1, 7
PDU_UNCONFIRMED_REQUEST = 0x10
RETRIES = 2                       # an unanswered request is sent again, with a [RETRY] line


def who_has_by_name(name):
    """A Who-Has APDU naming the object by Object_Name (cl. 16.9.1: context tag 3)."""
    text = b"\x00" + name.encode("utf-8")          # character set 0 = UTF-8
    return bytes([PDU_UNCONFIRMED_REQUEST, SERVICE_WHO_HAS, 0x3D, len(text)]) + text


def is_i_have(apdu, device_instance, name):
    """An I-Have from `device_instance` naming the Device object `name` (cl. 16.8.1)."""
    device_identifier = ((wiretest.OBJECT_TYPE_DEVICE << 22) | device_instance).to_bytes(4, "big")
    name_octets = b"\x00" + name.encode("utf-8")
    return (len(apdu) > 2 and apdu[0] == PDU_UNCONFIRMED_REQUEST and apdu[1] == SERVICE_I_HAVE
            and apdu[2:7] == b"\xC4" + device_identifier and name_octets in apdu)


def record(text, ok, failure_detail):
    """record() with the detail shown only when the check fails."""
    record_check(text, ok, "" if ok else failure_detail)


def send_until(client, port, apdu, matches, what):
    """Send an unconfirmed `apdu` until a frame `matches` (at most 1 + RETRIES times)."""
    for attempt in range(1 + RETRIES):
        if attempt:
            print(f"[RETRY] {what} got no answer - sent again", flush=True)
        client.frames.clear()
        client.send(wiretest.bvlc(wiretest.npdu(apdu)), port)
        found = client.wait_for(lambda frame: matches(frame.payload), 2.0)
        if found is not None:
            return found
    return None


def who_is(client, port, instance):
    return send_until(client, port, wiretest.who_is(instance, instance),
                      lambda apdu: wiretest.i_am_device_instance(apdu) == instance, "Who-Is")


def object_name(client, port, instance):
    answer = client.read_property(port, wiretest.OBJECT_TYPE_DEVICE, instance, wiretest.PROPERTY_OBJECT_NAME)
    if not answer.answered:
        return "no answer"
    return answer.value if answer.ok else answer.describe()


def refused(answer):
    return answer.answered and answer.frame.pdu_type in (wiretest.PDU_ERROR, wiretest.PDU_REJECT)


def start(args, extra_arguments=()):
    return wiretest.start(args.exe, ["--port", args.port] + list(extra_arguments), "bls")


def main():
    arguments = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    arguments.add_argument("--exe", default=str(wiretest.default_exe(REPOSITORY, "BACnetExampleBLS")),
                           help="path to BACnetExampleBLS (default: build/BACnetExampleBLS)")
    arguments.add_argument("--port", type=int, default=47840,
                           help="the lighting supervisor's UDP port (default 47840)")
    args = arguments.parse_args()
    client = wiretest.Client(retries=RETRIES)
    try:
        # 1. The defaults - the control: the configured run below must differ from this.
        supervisor = start(args)
        try:
            record(f"no options: Device {DEFAULT_INSTANCE} answers Who-Is",
                   who_is(client, args.port, DEFAULT_INSTANCE) is not None, "no I-Am")
            name = object_name(client, args.port, DEFAULT_INSTANCE)
            record(f"no options: Object_Name is the default \"{DEFAULT_NAME}\"", name == DEFAULT_NAME, f"read {name!r}")
        finally:
            supervisor.stop()

        # 2. Both configured.
        supervisor = start(args, ["--deviceID", CONFIGURED_INSTANCE, "--deviceName", CONFIGURED_NAME])
        try:
            record(f"--deviceID {CONFIGURED_INSTANCE}: the device answers Who-Is as {CONFIGURED_INSTANCE}",
                   who_is(client, args.port, CONFIGURED_INSTANCE) is not None, "no I-Am")
            name = object_name(client, args.port, CONFIGURED_INSTANCE)
            record(f"--deviceName: Object_Name reads \"{CONFIGURED_NAME}\"", name == CONFIGURED_NAME, f"read {name!r}")
            old = client.read_property(args.port, wiretest.OBJECT_TYPE_DEVICE, DEFAULT_INSTANCE,
                                       wiretest.PROPERTY_OBJECT_NAME)
            record(f"Device {DEFAULT_INSTANCE} no longer exists: Error OBJECT / UNKNOWN_OBJECT",
                   old.error == (codec.ERROR_CLASS_OBJECT, codec.ERROR_CODE_UNKNOWN_OBJECT), old.describe())
            record("the ready line names the configured device",
                   f"Device {CONFIGURED_INSTANCE} (\"{CONFIGURED_NAME}\") ready" in supervisor.output(),
                   "not in the console")
            found = send_until(client, args.port, who_has_by_name(CONFIGURED_NAME),
                               lambda apdu: is_i_have(apdu, CONFIGURED_INSTANCE, CONFIGURED_NAME), "Who-Has")
            record(f"Who-Has \"{CONFIGURED_NAME}\" -> I-Have from Device {CONFIGURED_INSTANCE} with that name",
                   found is not None, "no I-Have")
            # This supervisor executes WriteProperty, but not on its own identity.
            answer = client.write_property(args.port, wiretest.OBJECT_TYPE_DEVICE, CONFIGURED_INSTANCE,
                                           wiretest.PROPERTY_OBJECT_NAME, codec.application_character_string("Renamed"))
            record("WriteProperty Device Object_Name is refused (configurable at start-up only)",
                   refused(answer), answer.describe())
            name = object_name(client, args.port, CONFIGURED_INSTANCE)
            record("Object_Name unchanged by the refused write", name == CONFIGURED_NAME, f"read {name!r}")
        finally:
            supervisor.stop()

        # 3. The boundaries: invalid names keep the default, the longest valid one is kept whole.
        for label, value, expected in (("an empty --deviceName", "", DEFAULT_NAME),
                                       ("a 256-byte --deviceName", TOO_LONG_NAME, DEFAULT_NAME),
                                       ("a 255-byte --deviceName", LONGEST_NAME, LONGEST_NAME)):
            supervisor = start(args, ["--deviceName", value])
            try:
                name = object_name(client, args.port, DEFAULT_INSTANCE)
                shown = name if len(str(name)) < 40 else f"{len(name)} bytes"
                record(f"{label}: Object_Name reads {'the default' if expected == DEFAULT_NAME else 'it whole'}",
                       name == expected, f"read {shown!r}")
                if expected == DEFAULT_NAME:
                    record(f"{label}: the console warns", "invalid --deviceName" in supervisor.output(), "no warning")
            finally:
                supervisor.stop()

        # 4. The help lists the options this example reads, and no other; --xml does what it says.
        shown = subprocess.run([str(Path(args.exe).resolve()), "--help"], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, timeout=20).stdout
        for option in ("--port", "--deviceID", "--deviceName", "--xml"):
            record(f"--help lists {option}", option in shown, "not listed")
        record("--help does not list --dcc-password (the password is a source constant)",
               "--dcc-password" not in shown, "listed, but the example does not read it")
        supervisor = start(args, ["--xml"])
        try:
            object_name(client, args.port, DEFAULT_INSTANCE)
            record("--xml: the console shows each frame as an XML block", "<BACnetMessage" in supervisor.output(),
                   "no <BACnetMessage> block")
        finally:
            supervisor.stop()
    finally:
        client.close()
    return summary()


if __name__ == "__main__":
    sys.exit(main())
