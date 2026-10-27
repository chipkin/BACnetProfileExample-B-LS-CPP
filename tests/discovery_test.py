#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""B-LS discovery: read every property the lighting supervisor says it has, the way a client does.

    python3 tests/discovery_test.py [--exe build/BACnetExampleBLS] [--port 47840]

What a BACnet client such as Chipkin BACnet Explorer does when it discovers a device,
done over the wire from outside the example:

    1. Who-Is   -> the I-Am of Device 389017
    2. ReadProperty Device Object_List
    3. for every object: ReadProperty Property_List, then ReadProperty of every
       property it lists (and of Object_Identifier, Object_Name, Object_Type and
       Property_List itself, which cl. 12.1.1.4.1 leaves out of the list)

Every one of those reads must come back as a value - a ReadProperty ComplexACK. An
Error, Reject or Abort, or no answer, fails the check: Property_List holds "one property
identifier for each property that exists within the object" (135-2024 cl. 12.1.1.4.1),
so a listed property the device cannot read is a defect, whoever owns it.

The three reads named separately are the ones Explorer 4.23.2.0 found failing on
Network Port 1 at stack 6.0.21 (reported against B-SS-CPP as issues #20, #21, #22;
every example in the series serves the same Network Port).

Exit code 0 = every check passed.
"""
import argparse
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY))

import wiretest  # noqa: E402  (the vendored harness at the repository root)
from wiretest import record, summary  # noqa: E402

# Match main.cpp.
OBJECT_TYPE_CALENDAR = 6               # cl. 21 BACnetObjectType
OBJECT_TYPE_MULTI_STATE_OUTPUT = 14    # cl. 21 BACnetObjectType
OBJECT_TYPE_SCHEDULE = 17              # cl. 21 BACnetObjectType
OBJECT_TYPE_CHANNEL = 53               # cl. 21 BACnetObjectType
OBJECT_TYPE_LIGHTING_OUTPUT = 54       # cl. 21 BACnetObjectType
DEVICE_INSTANCE = 389017
DEVICE = (wiretest.OBJECT_TYPE_DEVICE, DEVICE_INSTANCE)
NETWORK_PORT = (wiretest.OBJECT_TYPE_NETWORK_PORT, 1)            # Network Port 1 "Vermilion"
EXPECTED_OBJECTS = [DEVICE,
                    (wiretest.OBJECT_TYPE_ANALOG_INPUT, 1),      # "Bronze"
                    (wiretest.OBJECT_TYPE_BINARY_INPUT, 1),      # "Emerald"
                    (wiretest.OBJECT_TYPE_MULTI_STATE_INPUT, 1), # "Hot Pink"
                    (wiretest.OBJECT_TYPE_ANALOG_OUTPUT, 1),     # "Chartreuse"
                    (wiretest.OBJECT_TYPE_BINARY_OUTPUT, 1),     # "Fuchsia"
                    (OBJECT_TYPE_MULTI_STATE_OUTPUT, 1),         # "Indigo"
                    (OBJECT_TYPE_LIGHTING_OUTPUT, 1),            # "Jade"
                    (OBJECT_TYPE_CHANNEL, 1),                    # "Garnet"
                    (OBJECT_TYPE_CALENDAR, 1),                   # "Cream"
                    (OBJECT_TYPE_SCHEDULE, 1),                   # "Saffron"
                    NETWORK_PORT]

# The four properties cl. 12.1.1.4.1 says Property_List does not contain.
PROPERTY_OBJECT_TYPE = 79
PROPERTY_DESCRIPTION = 28
NOT_IN_PROPERTY_LIST = [wiretest.PROPERTY_OBJECT_IDENTIFIER, wiretest.PROPERTY_OBJECT_NAME,
                        PROPERTY_OBJECT_TYPE, wiretest.PROPERTY_PROPERTY_LIST]

# Network Port properties Explorer could not read at stack 6.0.21 (cl. 12.56; numbers from
# cl. 21 BACnetPropertyIdentifier), with the issue that reported each.
PROPERTY_IP_DNS_SERVER = 406
PROPERTY_FD_BBMD_ADDRESS = 418
PROPERTY_FD_SUBSCRIPTION_LIFETIME = 419
EXPLORER_FAILURES = [(PROPERTY_IP_DNS_SERVER, "IP_DNS_Server", "#20"),
                     (PROPERTY_FD_BBMD_ADDRESS, "FD_BBMD_Address", "#21"),
                     (PROPERTY_FD_SUBSCRIPTION_LIFETIME, "FD_Subscription_Lifetime", "#22")]

OBJECT_TYPE_NAMES = {wiretest.OBJECT_TYPE_ANALOG_INPUT: "Analog Input",
                     wiretest.OBJECT_TYPE_ANALOG_OUTPUT: "Analog Output",
                     wiretest.OBJECT_TYPE_BINARY_INPUT: "Binary Input",
                     wiretest.OBJECT_TYPE_BINARY_OUTPUT: "Binary Output", wiretest.OBJECT_TYPE_DEVICE: "Device",
                     wiretest.OBJECT_TYPE_MULTI_STATE_INPUT: "Multi-state Input",
                     OBJECT_TYPE_MULTI_STATE_OUTPUT: "Multi-state Output",
                     OBJECT_TYPE_LIGHTING_OUTPUT: "Lighting Output",
                     wiretest.OBJECT_TYPE_NETWORK_PORT: "Network Port", OBJECT_TYPE_CHANNEL: "Channel",
                     OBJECT_TYPE_CALENDAR: "Calendar", OBJECT_TYPE_SCHEDULE: "Schedule"}
PDU_NAMES = {wiretest.PDU_ERROR: "Error", wiretest.PDU_REJECT: "Reject", wiretest.PDU_ABORT: "Abort"}


def parser():
    arguments = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    arguments.add_argument("--exe", default=str(wiretest.default_exe(REPOSITORY, "BACnetExampleBLS")),
                           help="path to BACnetExampleBLS (default: build/BACnetExampleBLS)")
    arguments.add_argument("--port", type=int, default=47840,
                           help="the lighting supervisor's UDP port (default 47840)")
    return arguments


def object_text(object_identifier):
    object_type, instance = object_identifier
    return f"{OBJECT_TYPE_NAMES.get(object_type, f'object type {object_type}')} {instance}"


def outcome(answer):
    """What a ReadProperty got back, in words: the value, or why there is none."""
    if not answer.answered:
        return "no answer"
    if answer.frame.pdu_type == wiretest.PDU_COMPLEX_ACK:
        return f"value {answer.value!r}"
    if answer.error is not None:
        return f"Error class={answer.error[0]} code={answer.error[1]}"
    if answer.frame.pdu_type in (wiretest.PDU_REJECT, wiretest.PDU_ABORT) and len(answer.frame.payload) > 2:
        return f"{PDU_NAMES[answer.frame.pdu_type]} reason={answer.frame.payload[2]}"
    return answer.describe()


def is_value(answer):
    return answer.answered and answer.frame.pdu_type == wiretest.PDU_COMPLEX_ACK


def who_is(client, port, attempts=2):
    """Who-Is for this one device, unicast to it (a client that already knows the address
    does this; Explorer broadcasts). Returns the I-Am frame that comes back, or None.
    Who-Is is unconfirmed, so nothing else retries it: if no I-Am comes back it is sent
    once more, with a visible [RETRY] line (the example's UDP receive can drop a datagram
    on Windows - common/ SimpleUDP)."""
    for attempt in range(attempts):
        if attempt:
            print("[RETRY] Who-Is got no I-Am in 3.0 s - sent again", flush=True)
        client.frames.clear()
        client.send(wiretest.bvlc(wiretest.npdu(wiretest.who_is(DEVICE_INSTANCE, DEVICE_INSTANCE))), port)
        frame = client.wait_for(lambda candidate: wiretest.i_am_device_instance(candidate.payload) == DEVICE_INSTANCE,
                                3.0)
        if frame is not None:
            return frame
    return None


def main():
    args = parser().parse_args()
    device = wiretest.start(args.exe, ["--port", args.port], "B-LS")
    client = wiretest.Client(retries=1)
    try:
        i_am = who_is(client, args.port)
        record(f"Who-Is: Device {DEVICE_INSTANCE} answers with an I-Am", i_am is not None,
               "no I-Am" if i_am is None else "")

        object_list_answer = client.read_property(args.port, *DEVICE, wiretest.PROPERTY_OBJECT_LIST, timeout=2.0)
        object_list = wiretest.decoded_values(object_list_answer.value_octets) if is_value(object_list_answer) else []
        # Control: the walk below proves nothing if it walks nothing.
        record("Device Object_List names the Device, Analog Input 1, Binary Input 1, Multi-state Input 1, "
               "Analog Output 1, Binary Output 1, Multi-state Output 1, Lighting Output 1, Channel 1, "
               "Calendar 1, Schedule 1 and Network Port 1",
               sorted(object_list) == sorted(EXPECTED_OBJECTS),
               f"{len(object_list)} objects" if is_value(object_list_answer) else outcome(object_list_answer))

        reads = 0
        unreadable = {}
        property_lists = {}
        for object_identifier in object_list:
            list_answer = client.read_property(args.port, *object_identifier, wiretest.PROPERTY_PROPERTY_LIST,
                                               timeout=2.0)
            property_list = wiretest.decoded_values(list_answer.value_octets) if is_value(list_answer) else []
            property_lists[object_identifier] = property_list
            record(f"{object_text(object_identifier)}: Property_List reads", is_value(list_answer) and property_list,
                   outcome(list_answer) if not is_value(list_answer) else f"{len(property_list)} properties")
            for property_identifier in NOT_IN_PROPERTY_LIST + property_list:
                answer = client.read_property(args.port, *object_identifier, property_identifier, timeout=2.0)
                reads += 1
                if not is_value(answer):
                    unreadable[(object_identifier, property_identifier)] = outcome(answer)
                    print(f"[UNREADABLE] {object_text(object_identifier)} property {property_identifier}: "
                          f"{outcome(answer)}", flush=True)

        record(f"every property of every object reads as a value ({reads} reads)", reads and not unreadable,
               f"{len(unreadable)} unreadable: " + ", ".join(
                   f"{object_text(object_identifier)} {property_identifier}"
                   for object_identifier, property_identifier in unreadable) if unreadable else "")

        # The Device's Description reads as its text: a value of 256 octets or more is refused by the
        # stack and reads as an empty string, which the walk above would still count as a value.
        description = client.read_property(args.port, *DEVICE, PROPERTY_DESCRIPTION, timeout=2.0)
        text = description.value if is_value(description) else None
        record("Device Description reads as its text, not an empty string (the stack holds at most 255 octets)",
               isinstance(text, str) and text.startswith("Chipkin CAS BACnet Stack Example - B-LS"),
               f"read {text!r}" if is_value(description) else outcome(description))

        # The three Explorer reported, by name - listed in Property_List and readable.
        network_port_list = property_lists.get(NETWORK_PORT, [])
        for property_identifier, name, issue in EXPLORER_FAILURES:
            listed = property_identifier in network_port_list
            failure = unreadable.get((NETWORK_PORT, property_identifier))
            record(f"Network Port 1 {name} ({property_identifier}): listed in Property_List and reads as a value "
                   f"(issue {issue})", listed and failure is None,
                   "not in Property_List" if not listed else (failure or ""))
    finally:
        client.close()
        device.stop()
    return summary()


if __name__ == "__main__":
    sys.exit(main())
