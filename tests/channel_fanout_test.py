#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""B-LS Profile Function: Channel 1 forwards a WriteGroup to a local light AND another device.

    python3 tests/channel_fanout_test.py [--exe build/BACnetExampleBLS] [--port 47840]

135-2024 L.11.1: "A B-LS is any device that implements Channel objects and optionally
Lighting Output and/or Binary Lighting Output objects with the ability to forward channel
writes to other BACnet devices."

The Peer is a Python BACnet/IP device standing in for remote device 389016, a light
(Lighting Output 1). The client is a Python BACnet client that sends WriteGroup. Checks:

  1. The example finds 389016 by itself: the Who-Is its Device_Address_Binding sends
     reaches the subnet broadcast (Linux/macOS, where a test can hear a broadcast), the
     Peer answers, and Device_Address_Binding lists 389016. On Windows the Peer announces
     itself with an I-Am instead.
  2. Start-up: Schedule 1 references Channel 1's Present_Value and has written it (100.0
     at priority 12); the Channel has propagated it to Jade, and Write_Status records how
     that write went: FAILED when device 389016 could not be addressed yet (the Schedule
     writes on the example's first tick, before 389016's I-Am binds it, and the stack
     skips a member it cannot address - cl. 12.53.7), SUCCESSFUL if it could.
  3. Profile Function: a WriteGroup (group 1, channel 1, 60.0, priority 8) reaches BOTH
     members - Jade (local) and the Peer's Lighting Output 1 as a WriteProperty at
     priority 8 - and Write_Status ends SUCCESSFUL.
  4. Failure Mode (cl. 12.53.5 / 12.53.7): the Peer goes offline. A WriteGroup still writes
     Jade, Write_Status is IN_PROGRESS while the stack waits for the Peer (a WriteProperty
     of Present_Value meanwhile is refused with Error Class OBJECT, Error Code BUSY), then
     FAILED when the
     Peer's write times out. The Peer comes back: the next WriteGroup reaches it and
     Write_Status is SUCCESSFUL again.
  5. Failure Mode: the Peer refuses the write (Error) -> FAILED; Jade refuses the value
     (150 % is out of range) -> FAILED.
  6. A WriteProperty to Channel 1 (42.0 at priority 9) is propagated too (cl. 12.53.5):
     it reaches Jade's Priority_Array[9] and the Peer, and Write_Status ends SUCCESSFUL;
     one the Peer refuses (43.0) ends FAILED.
  7. DeviceCommunicationControl DISABLE_INITIATION (DM-DCC-B, cl. 16.1): a WriteProperty to
     Channel 1 still writes the Channel, the device does not send the Peer its write, and
     Write_Status ends FAILED (the stack reports nothing for a write it refuses to send);
     after ENABLE the next write reaches the Peer and ends SUCCESSFUL, not BUSY.

Exit code 0 = every check passed.
"""
import argparse
import os
import sys
import time
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY))

import wiretest  # noqa: E402  (the vendored harness at the repository root)
from wiretest import alarm, codec, record, summary  # noqa: E402

# Match main.cpp.
DEVICE_INSTANCE = 389017
OBJECT_TYPE_SCHEDULE = 17
OBJECT_TYPE_CHANNEL = 53
OBJECT_TYPE_LIGHTING_OUTPUT = 54
CHANNEL = (OBJECT_TYPE_CHANNEL, 1)               # "Garnet"
JADE = (OBJECT_TYPE_LIGHTING_OUTPUT, 1)          # the local member
SCHEDULE = (OBJECT_TYPE_SCHEDULE, 1)             # "Saffron"
CHANNEL_NUMBER = 1
CONTROL_GROUP = 1
SCHEDULE_PRIORITY = 12                           # Priority_For_Writing
PROPERTY_LAST_PRIORITY = 369
PROPERTY_WRITE_STATUS = 370
WRITE_STATUS_IDLE, WRITE_STATUS_IN_PROGRESS, WRITE_STATUS_SUCCESSFUL, WRITE_STATUS_FAILED = 0, 1, 2, 3
WRITE_STATUS_NAMES = {0: "idle", 1: "in-progress", 2: "successful", 3: "failed"}

# The remote member, played by the Peer.
REMOTE_DEVICE_INSTANCE = 389016
REMOTE_LIGHT = (OBJECT_TYPE_LIGHTING_OUTPUT, 1)

# The stack gives up on an offline member after APDU_Timeout x (Number_Of_APDU_Retries + 1):
# the test reads both from the example (stack defaults: 10 s x (3 + 1) = 40 s)
# and allows this much more.
REMOTE_TIMEOUT_MARGIN_SECONDS = 5
PROPERTY_APDU_TIMEOUT = 11
PROPERTY_NUMBER_OF_APDU_RETRIES = 73
# How long to wait for Write_Status to settle after a WriteGroup whose members answer at once:
# long enough for one of this test's own ReadProperty requests to need its retry (2 x 3 s).
SETTLE_SECONDS = 8



def main():
    arguments = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    arguments.add_argument("--exe", default=str(wiretest.default_exe(REPOSITORY, "BACnetExampleBLS")))
    arguments.add_argument("--port", type=int, default=47840, help="the lighting supervisor's UDP port (default 47840)")
    args = arguments.parse_args()
    hears_broadcasts = os.name != "nt"   # wiretest.broadcast_listener needs POSIX SO_REUSEADDR

    broadcast = None
    if hears_broadcasts:
        probe = wiretest.start(args.exe, ["--port", args.port], "bls-probe")
        try:
            broadcast_ip = wiretest.broadcast_address(probe.output(), args.port)
        finally:
            probe.stop()
        if broadcast_ip is None:
            sys.exit("could not find the example's broadcast address in its console")
        broadcast = (broadcast_ip, args.port)
        time.sleep(0.5)

    peer = wiretest.SimulatedServer(REMOTE_DEVICE_INSTANCE, "Simulated Light 389016",
                                   {REMOTE_LIGHT: {codec.PROPERTY_PRESENT_VALUE: codec.application_real(0.0)}},
                                   broadcast=broadcast)
    example = wiretest.start(args.exe, ["--port", args.port], "bls")
    client = wiretest.Client(retries=1)
    try:
        run(args, example, peer, client, hears_broadcasts)
    finally:
        example.stop()
        peer.stop()
        client.close()
        example.keep_log()
    return summary()


def read(client, args, target, property_identifier, array_index=None):
    return client.read_property(args.port, target[0], target[1], property_identifier, array_index)


def read_value(client, args, target, property_identifier):
    answer = read(client, args, target, property_identifier)
    return answer.value if answer.ok else None


def wait_for(condition, seconds):
    deadline = time.monotonic() + seconds
    while True:
        result = condition()
        if result or time.monotonic() >= deadline:
            return result
        time.sleep(0.1)


def write_status(client, args):
    return read_value(client, args, CHANNEL, PROPERTY_WRITE_STATUS)


def wait_write_status(client, args, expected, seconds):
    seen = wait_for(lambda: write_status(client, args) == expected, seconds)
    return seen, WRITE_STATUS_NAMES.get(write_status(client, args), "unreadable")


def send_write_group(client, args, example, value, priority=8):
    """Send a WriteGroup and wait (2 s) for the example's console to show it arrived.

    WriteGroup is unconfirmed, so a datagram lost on the way (seen on a busy Windows host,
    where a few test requests in a thousand never reach the example's socket) would fail
    the checks that follow with no clue why. If the console does not show it, it is sent
    once more, with a visible [RETRY] line - the same value at the same priority, so a
    duplicate changes nothing. The console is used only to decide that; every check reads
    the result over the wire."""
    apdu = codec.write_group_request(CONTROL_GROUP, priority, [(CHANNEL_NUMBER, codec.application_real(value), None)])
    shown = f"WriteGroup: Channel 1 (Garnet) <- {value:.2f} @ priority {priority}"
    before = example.output().count(shown)
    for attempt in range(2):
        if attempt:
            print(f"[RETRY] WriteGroup {value} @ {priority} did not reach the example in 2 s - sent again", flush=True)
        client.send(codec.bvlc(codec.npdu(apdu)), args.port)
        if wait_for(lambda: example.output().count(shown) > before, 2):
            return


def remote_write(peer, value, priority, seconds=3.0):
    """The Peer's WriteProperty of its Lighting Output's Present_Value with this value/priority, if one arrives."""
    def found():
        for write in peer.writes_matching(REMOTE_LIGHT[0], REMOTE_LIGHT[1], codec.PROPERTY_PRESENT_VALUE):
            if codec.decode_application(write["value_octets"]) == value and write["priority"] == priority:
                return write
        return None
    return wait_for(found, seconds)


def remote_timeout_seconds(client, args):
    """How long the stack waits for an offline member: APDU_Timeout x (Number_Of_APDU_Retries + 1), plus a margin."""
    device = (codec.OBJECT_TYPE_DEVICE, DEVICE_INSTANCE)
    apdu_timeout_ms = read_value(client, args, device, PROPERTY_APDU_TIMEOUT)
    retries = read_value(client, args, device, PROPERTY_NUMBER_OF_APDU_RETRIES)
    if not isinstance(apdu_timeout_ms, int) or not isinstance(retries, int):
        apdu_timeout_ms, retries = 10000, 3   # the stack defaults, if either read fails
    return apdu_timeout_ms / 1000.0 * (retries + 1) + REMOTE_TIMEOUT_MARGIN_SECONDS


def is_close(value, expected):
    return isinstance(value, float) and abs(value - expected) < 0.001


def run(args, example, peer, client, hears_broadcasts):
    # --- 1. The example finds the remote member itself ----------------------------
    if hears_broadcasts:
        heard = wait_for(lambda: [frame for frame in list(peer.received_on_broadcast)
                                  if frame.ok and frame.pdu_type == codec.PDU_UNCONFIRMED_REQUEST and
                                  frame.service == codec.SERVICE_WHO_IS], 5)
        record("The Who-Is the stack sends to bind device 389016 reaches the subnet broadcast",
               heard, f"on {args.port} at the broadcast address" if heard else
               "no Who-Is on the broadcast socket (common/ before 3.4.0 sent it to this host's own address, stack #3933)")
    else:
        peer.announce(args.port)
    bound = wait_for(lambda: "I-Am: remote device 389016" in example.output(), 5)
    binding = read(client, args, (codec.OBJECT_TYPE_DEVICE, DEVICE_INSTANCE), codec.PROPERTY_DEVICE_ADDRESS_BINDING)
    listed = binding.ok and (codec.OBJECT_TYPE_DEVICE, REMOTE_DEVICE_INSTANCE) in codec.decoded_values(binding.value_octets)
    record("Device_Address_Binding lists device 389016 (the Peer's I-Am bound it)", bound and listed,
           binding.describe() if not listed else "")

    # --- 2. Start-up state ---------------------------------------------------------
    # Schedule 1 writes Channel 1 on the example's first tick. Whether device 389016 had been
    # bound by then decides the outcome; the example's console says which (section 2e).
    skipped = "cannot address it" in example.output()
    expected = WRITE_STATUS_FAILED if skipped else WRITE_STATUS_SUCCESSFUL
    seen, status = wait_write_status(client, args, expected, SETTLE_SECONDS)
    record(f"Channel 1 Write_Status follows Schedule 1's start-up write: {WRITE_STATUS_NAMES[expected]} "
           f"({'389016 was not bound yet, so its write was skipped' if skipped else 'both members took it'}; "
           "cl. 12.53.7)", seen, status)
    references = read(client, args, SCHEDULE, codec.PROPERTY_LIST_OF_OBJECT_PROPERTY_REFERENCES)
    reference_fields = dict(codec.context_values(references.value_octets or b""))
    referenced = (reference_fields.get(0) == codec.object_id(*CHANNEL) and
                  int.from_bytes(reference_fields.get(1, b""), "big") == codec.PROPERTY_PRESENT_VALUE and
                  2 not in reference_fields)
    record("Schedule 1 references Channel 1's Present_Value (a Channel has no Priority_Array, Table 12-62)",
           referenced, references.describe())
    channel_value = read_value(client, args, CHANNEL, codec.PROPERTY_PRESENT_VALUE)
    last_priority = read_value(client, args, CHANNEL, PROPERTY_LAST_PRIORITY)
    record("Schedule 1 has written Channel 1: Present_Value 100.0, Last_Priority 12",
           is_close(channel_value, 100.0) and last_priority == SCHEDULE_PRIORITY,
           f"Present_Value={channel_value!r} Last_Priority={last_priority!r}")
    jade_slot = read(client, args, JADE, codec.PROPERTY_PRIORITY_ARRAY, SCHEDULE_PRIORITY).value
    record("Schedule 1's write to Channel 1 reaches Jade: Priority_Array[12] 100.0 (cl. 12.53.5)",
           is_close(jade_slot, 100.0), f"Jade Priority_Array[12]={jade_slot!r}")

    # --- 3. The Profile Function: one WriteGroup, both members ----------------------
    send_write_group(client, args, example, 60.0)
    arrived = remote_write(peer, 60.0, 8)
    record("WriteGroup 60.0 @ 8 reaches device 389016: WriteProperty Lighting Output 1 Present_Value 60.0 @ 8",
           arrived is not None, "no such WriteProperty at the Peer" if arrived is None else "")
    jade_value = read_value(client, args, JADE, codec.PROPERTY_PRESENT_VALUE)
    record("WriteGroup 60.0 @ 8 reaches Jade (local member): Present_Value 60.0", is_close(jade_value, 60.0),
           f"Jade={jade_value!r}")
    channel_value = read_value(client, args, CHANNEL, codec.PROPERTY_PRESENT_VALUE)
    last_priority = read_value(client, args, CHANNEL, PROPERTY_LAST_PRIORITY)
    record("Channel 1 holds the WriteGroup's value: Present_Value 60.0, Last_Priority 8",
           is_close(channel_value, 60.0) and last_priority == 8,
           f"Present_Value={channel_value!r} Last_Priority={last_priority!r}")
    seen, status = wait_write_status(client, args, WRITE_STATUS_SUCCESSFUL, SETTLE_SECONDS)
    record("Write_Status is SUCCESSFUL once both members have taken the value", seen, status)

    # --- 4. Failure Mode: the remote member is offline, then comes back --------------
    peer.mode = "offline"
    send_write_group(client, args, example, 30.0)
    jade_value = read_value(client, args, JADE, codec.PROPERTY_PRESENT_VALUE)
    record("Remote member offline: the WriteGroup (30.0) still writes Jade", is_close(jade_value, 30.0),
           f"Jade={jade_value!r}")
    status = write_status(client, args)
    record("Write_Status is IN_PROGRESS while the stack waits for the offline member (cl. 12.53.5)",
           status == WRITE_STATUS_IN_PROGRESS, WRITE_STATUS_NAMES.get(status, "unreadable"))
    busy = client.write_property(args.port, CHANNEL[0], CHANNEL[1], codec.PROPERTY_PRESENT_VALUE,
                                 codec.application_real(42.0), priority=9)
    record("A WriteProperty of Channel 1 Present_Value meanwhile is refused with Error Code BUSY (cl. 12.53.5)",
           busy.error is not None and busy.error[1] == codec.ERROR_CODE_BUSY, busy.describe())
    record("... and with Error Class OBJECT (cl. 12.53.5; BUSY is an OBJECT code, cl. 18.2)",
           busy.error is not None and busy.error[0] == codec.ERROR_CLASS_OBJECT, busy.describe())
    seen, status = wait_write_status(client, args, WRITE_STATUS_FAILED, remote_timeout_seconds(client, args))
    record("Write_Status is FAILED when the offline member's write times out (cl. 12.53.7)", seen, status)
    record("The stack did send the offline member its WriteProperty (30.0 @ 8)",
           remote_write(peer, 30.0, 8, 0.5) is not None)

    peer.mode = "online"
    send_write_group(client, args, example, 80.0)
    arrived = remote_write(peer, 80.0, 8)
    seen, status = wait_write_status(client, args, WRITE_STATUS_SUCCESSFUL, SETTLE_SECONDS)
    record("Recovery: the member is back; WriteGroup 80.0 reaches it and Write_Status is SUCCESSFUL",
           arrived is not None and seen, f"remote write {'arrived' if arrived else 'missing'}, Write_Status {status}")

    # --- 5. Failure Mode: a member refuses the value ---------------------------------
    peer.mode = "refusing"
    send_write_group(client, args, example, 55.0)
    seen, status = wait_write_status(client, args, WRITE_STATUS_FAILED, SETTLE_SECONDS)
    record("The remote member answers the write with an Error: Write_Status is FAILED", seen, status)
    peer.mode = "online"
    send_write_group(client, args, example, 150.0)
    seen, status = wait_write_status(client, args, WRITE_STATUS_FAILED, SETTLE_SECONDS)
    jade_value = read_value(client, args, JADE, codec.PROPERTY_PRESENT_VALUE)
    record("Jade refuses 150 % (out of range): Write_Status is FAILED and Jade keeps its level",
           seen and not is_close(jade_value, 150.0), f"Write_Status {status}, Jade={jade_value!r}")
    send_write_group(client, args, example, 70.0)
    seen, status = wait_write_status(client, args, WRITE_STATUS_SUCCESSFUL, SETTLE_SECONDS)
    record("A valid WriteGroup afterwards is SUCCESSFUL again", seen, status)

    # --- 6. A WriteProperty to the Channel is forwarded too (cl. 12.53.5) ------------
    written = client.write_property(args.port, CHANNEL[0], CHANNEL[1], codec.PROPERTY_PRESENT_VALUE,
                                    codec.application_real(42.0), priority=9)
    record("WriteProperty Channel 1 Present_Value 42.0 @ 9 is accepted", written.ok, written.describe())
    jade_value = read_value(client, args, JADE, codec.PROPERTY_PRESENT_VALUE)
    # Priority 9 is below the WriteGroups' 8, so Jade's Present_Value stays 70.0: look at the slot.
    jade_slot = read(client, args, JADE, codec.PROPERTY_PRIORITY_ARRAY, 9).value
    record("WriteProperty to Channel 1 (42.0 @ 9) reaches Jade's Priority_Array[9]", is_close(jade_slot, 42.0),
           f"Jade Priority_Array[9]={jade_slot!r}, Present_Value={jade_value!r}")
    record("WriteProperty to Channel 1 (42.0 @ 9) reaches device 389016", remote_write(peer, 42.0, 9) is not None)
    seen, status = wait_write_status(client, args, WRITE_STATUS_SUCCESSFUL, SETTLE_SECONDS)
    record("Write_Status follows the WriteProperty's propagation and ends SUCCESSFUL (cl. 12.53.7)", seen, status)
    # A WriteProperty's propagation is followed, not only a WriteGroup's: the Peer refuses this one.
    peer.mode = "refusing"
    written = client.write_property(args.port, CHANNEL[0], CHANNEL[1], codec.PROPERTY_PRESENT_VALUE,
                                    codec.application_real(43.0), priority=9)
    seen, status = wait_write_status(client, args, WRITE_STATUS_FAILED, SETTLE_SECONDS)
    record("A WriteProperty to Channel 1 (43.0 @ 9) that the remote member refuses: Write_Status is FAILED",
           written.ok and seen, f"{written.describe()}; Write_Status {status}")
    peer.mode = "online"

    # --- 7. DeviceCommunicationControl DISABLE_INITIATION (cl. 16.1) ------------------
    answer = client.device_communication_control(args.port, alarm.DCC_DISABLE_INITIATION)
    record("DeviceCommunicationControl DISABLE_INITIATION is accepted", answer.acked, answer.describe())
    written = client.write_property(args.port, CHANNEL[0], CHANNEL[1], codec.PROPERTY_PRESENT_VALUE,
                                    codec.application_real(22.0), priority=9)
    seen, status = wait_write_status(client, args, WRITE_STATUS_FAILED, SETTLE_SECONDS)
    record("Initiation disabled: a WriteProperty to Channel 1 (22.0 @ 9) is accepted and Write_Status ends FAILED "
           "(the remote member's write is not sent)", written.ok and seen, f"{written.describe()}; Write_Status {status}")
    record("Initiation disabled: device 389016 receives no WriteProperty (cl. 16.1)",
           remote_write(peer, 22.0, 9, 2.0) is None)
    answer = client.device_communication_control(args.port, alarm.DCC_ENABLE)
    record("DeviceCommunicationControl ENABLE is accepted", answer.acked, answer.describe())
    written = client.write_property(args.port, CHANNEL[0], CHANNEL[1], codec.PROPERTY_PRESENT_VALUE,
                                    codec.application_real(33.0), priority=9)
    arrived = remote_write(peer, 33.0, 9)
    seen, status = wait_write_status(client, args, WRITE_STATUS_SUCCESSFUL, SETTLE_SECONDS)
    record("Re-enabled: the next WriteProperty (33.0 @ 9) is accepted (not BUSY), reaches device 389016 and "
           "Write_Status ends SUCCESSFUL", written.ok and arrived is not None and seen,
           f"{written.describe()}; remote write {'arrived' if arrived else 'missing'}; Write_Status {status}")


if __name__ == "__main__":
    sys.exit(main())
