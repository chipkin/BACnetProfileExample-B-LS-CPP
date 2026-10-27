# B-LS Wire Tests

Tests that drive the running lighting supervisor over BACnet/IP from outside it, with
Python-simulated Peers - never another example's binary. Two scripts:

- **`channel_fanout_test.py`** - the B-LS Profile Function and its Failure Modes.
  135-2024 Annex L.11.1: "A B-LS is any device that implements Channel objects and
  optionally Lighting Output and/or Binary Lighting Output objects with the ability to
  forward channel writes to other BACnet devices."
- **`discovery_test.py`** - discovery, the way a client such as Chipkin BACnet Explorer
  finds a device and reads everything it says it has.

The tests are written against the series' shared harness in
[`../wiretest/`](../wiretest/README.md) (0.7.0, vendored like `common/`): the
WriteGroup-Request encoder, the WriteProperty request parser and the Peer
(`wiretest.SimulatedServer`, a Python device whose objects take WriteProperty and
which a test can take offline or make refuse writes) all come from there. Python 3
standard library only - nothing to `pip install`.

## Running

Build the example (README "Build"), then from the repository root:

```bash
python3 tests/run_wire_tests.py --exe build/BACnetExampleBLS
```

On Windows, `--exe build\Release\BACnetExampleBLS.exe`. It ends with
`ALL WIRE TESTS PASSED` (exit 0) or the scripts that failed, in about a minute and a
half: one step waits for the stack to give up on an offline device (APDU_Timeout x
(Number_Of_APDU_Retries + 1), read from the example: 40 s at the stack's defaults).
`--port` (default 47840) is the UDP port the test starts the example on; pick another if
something else on the host has it. CI (`.github/workflows/release.yml`) runs it on Linux
after the smoke test.

`[KNOWN GAP]` lines are stack defects ([`../TODO.md`](../TODO.md)): reported on every
run, not counted. A `[RETRY]` line means one of the test's own requests got no answer
and was sent again (seen only on a busy Windows host, where a few datagrams in a
thousand never reach the example's socket); it is shown so it is never silent.

## The setup

```
test client (127.0.0.1, ephemeral UDP port)  - WriteGroup, ReadProperty, WriteProperty
    |  BACnet/IP
BACnetExampleBLS  UDP --port                 - Device 389017: Channel 1 "Garnet",
    |                                          Lighting Output 1 "Jade" (local member)
    |  the stack's WriteProperty, addressed through its Device_Address_Binding
Peer (127.0.0.1, ephemeral UDP port)         - device 389016, Lighting Output 1
                                               (the remote member; CommandablePeer)
```

On Linux/macOS the Peer also listens on the example's broadcast address and port
(`broadcast=`, POSIX `SO_REUSEADDR`), so it hears the example's broadcasts the way a
device on the same network would. Windows cannot share the example's port (`common/`
sets `SO_EXCLUSIVEADDRUSE`), so there the Peer announces itself with an I-Am instead,
as a device does when it starts, and the broadcast check is not made. A short probe run
of the example first reads its broadcast address from its console.

## `channel_fanout_test.py` - one WriteGroup, two lights, and what happens when one fails

1. **Binding.** The Who-Is the stack's Device_Address_Binding sends for device 389016
   reaches the subnet broadcast (Linux/macOS), the Peer answers, and the Device's
   `Device_Address_Binding` lists 389016.
2. **Start-up.** Schedule 1's `List_Of_Object_Property_References` names Channel 1
   `Present_Value`, no array index (a Channel has no Priority_Array, Table 12-62);
   Schedule 1 has written it: Channel 1 `Present_Value` 100.0, `Last_Priority` 12, and
   the Channel has forwarded it to Jade (`Priority_Array[12]` 100.0, cl. 12.53.5).
   `Write_Status` follows that write (cl. 12.53.7): FAILED when device 389016 could not
   be addressed yet - the Schedule writes on the example's first tick, before 389016's
   I-Am binds it, and the stack skips a member it cannot address - and SUCCESSFUL if it
   could; the example's console says which.
3. **The Profile Function.** WriteGroup group 1, channel 1, 60.0, priority 8: the Peer
   receives WriteProperty Lighting Output 1 `Present_Value` 60.0 at priority 8; Jade is
   60.0; Channel 1 is 60.0 with `Last_Priority` 8; `Write_Status` SUCCESSFUL.
4. **Failure Mode - the remote member is offline** (the Peer answers nothing at all).
   A WriteGroup of 30.0 still writes Jade; `Write_Status` is IN_PROGRESS; a WriteProperty
   of Channel 1 `Present_Value` meanwhile gets Error Class OBJECT, Error Code BUSY
   (cl. 12.53.5); after the
   stack's timeout `Write_Status` is FAILED; the Peer did receive the WriteProperty.
   **Recovery:** the Peer back online, WriteGroup 80.0 reaches it and `Write_Status` is
   SUCCESSFUL.
5. **Failure Mode - a member refuses.** The Peer answers Error: FAILED. Jade refuses
   150 % (out of range): FAILED, Jade keeps its level. A valid WriteGroup afterwards:
   SUCCESSFUL.
6. **A WriteProperty is forwarded too.** WriteProperty Channel 1 `Present_Value` 42.0 at
   priority 9 is accepted, reaches Jade's `Priority_Array[9]` and the Peer, and
   `Write_Status` ends SUCCESSFUL; a WriteProperty of 43.0 that the Peer refuses ends
   FAILED (a check that fails on a build that follows only a WriteGroup's fan-out).

7. **DeviceCommunicationControl DISABLE_INITIATION** (cl. 16.1): a WriteProperty to
   Channel 1 is accepted, the Peer receives nothing, and `Write_Status` ends FAILED
   (the stack reports nothing for a write it refuses to send, so the example fails the
   remote member itself); after ENABLE the next write is accepted (not BUSY), reaches
   the Peer and ends SUCCESSFUL.

No `[KNOWN GAP]` lines remain: the stack defects they reported (a WriteProperty or
Schedule write not forwarded, BUSY sent with Error Class PROPERTY) are fixed at the
current Stack Pin (TODO.md "Fixed upstream").

A WriteGroup is unconfirmed, so the test watches the example's console for the line
that says it arrived and sends it once more, with a `[RETRY]` line, if it does not
appear in 2 s. Every check reads its result over the wire.

## The Lighting Output tests - Jade carries out Lighting_Command (DS-LO-B, cl. 12.54)

`fade_test.py`, `ramp_step_test.py`, `stop_priority_test.py`, `warn_test.py` and
`refusal_test.py` are the B-LD example's Lighting Output Wire Tests, aimed at Jade: this
example runs the same Lighting Output engine (`main.cpp` section 1b). Their shared
`lighting_setup.py` starts the example and relinquishes Schedule 1's start-up write to
Jade (100 % at priority 12, through Channel 1), so each test starts with the light off
and idle, as on B-LD.

- `fade_test.py`: a `fadeTo` fades over its fade time (or `Default_Fade_Time`):
  `Present_Value` is the target at once, `Tracking_Value` moves in proportion,
  `In_Progress` is `fadeActive` until it arrives.
- `ramp_step_test.py`: `rampTo` at its ramp rate (or `Default_Ramp_Rate`); `stepUp`,
  `stepDown`, `stepOn`, `stepOff` from `Tracking_Value`, ignored when the light is off.
- `stop_priority_test.py`: `stop` holds the level; a higher-priority write halts a fade,
  a lower one does not.
- `warn_test.py`: `warn`, `warnOff`, `warnRelinquish` and their egress time
  (`Egress_Active`); the `Present_Value` special values -1.0 to -7.0.
- `refusal_test.py`: `NONE`, out-of-range fields, a `fadeTo` without a target level and
  an out-of-range `Present_Value` are refused with VALUE_OUT_OF_RANGE and change
  nothing (part 1 of B-LD's `failure_test.py`; B-LS has no lamp Simulation for parts 2
  and 3).

## `discovery_test.py` - every listed property reads as a value

1. **Who-Is** (for 389017, unicast) -> the device's I-Am.
2. **Device `Object_List`** names exactly the Device, Analog Input 1, Binary Input 1,
   Multi-state Input 1, Analog Output 1, Binary Output 1, Multi-state Output 1,
   Lighting Output 1, Channel 1, Calendar 1, Schedule 1 and Network Port 1. This is the control: a walk
   over nothing would pass.
3. For each object, **`Property_List`** reads, and a ReadProperty of every
   property it lists - plus `Object_Identifier`, `Object_Name`, `Object_Type`
   and `Property_List`, which cl. 12.1.1.4.1 leaves out of the list - returns a
   ComplexACK. An Error, Reject, Abort or no answer prints an `[UNREADABLE]` line
   and fails the check. 135-2024 cl. 12.1.1.4.1: Property_List holds "one
   property identifier for each property that exists within the object".
4. Network Port 1's **`IP_DNS_Server` (406)**, **`FD_BBMD_Address` (418)** and
   **`FD_Subscription_Lifetime` (419)** are each listed and read as a value: the
   three reads Explorer 4.23.2.0 found failing at stack 6.0.21 (reported against
   B-SS-CPP as #20, #21, #22; every example in the series serves the same
   Network Port).
5. The Device's **`Description`** reads as its text, not an empty string. The
   stack holds at most 255 octets from a callback and refuses a longer value,
   which then reads as `""` - a value the walk in 3 still counts as read. The
   270-character description of 1.2.0 failed this check; it is 221 now.

## `configuration_test.py` - the Device's identity is configurable

BACnet requires the Device's Object_Identifier and Object_Name to be
configurable (135-2024 cl. 12.1.1.3, 12.1.1.4); Object_Name must be unique
across the internetwork, so two units cannot share a compile-time name. The
supervisor is started several ways, and its help is checked:

1. **No options (control):** Device 389017 answers Who-Is, and its
   `Object_Name` is the default `Chipkin Example B-LS`.
2. **`--deviceID 389917 --deviceName "Chipkin Example B-LS Unit 2"`:** the
   device answers Who-Is as 389917; `Object_Name` reads the configured name;
   a read of Device 389017 gets Error OBJECT / UNKNOWN_OBJECT; the ready line
   names the configured device; a Who-Has by the configured name gets an
   I-Have from Device 389917 with that name (DM-DOB-B); a WriteProperty of
   the Device's `Object_Name` is refused and changes nothing.
3. **Boundaries:** an empty name and a 256-byte name each print a warning and
   keep the default; a 255-byte name (the limit) reads back whole.
4. **`--help`** lists `--port`, `--deviceID`, `--deviceName` and `--xml`, and
   not `--dcc-password` (the DeviceCommunicationControl password is a source
   constant); with `--xml` each frame prints as an XML block.

## Results

Run 2026-10-26, stack `6.x` @ `69b6249f`, Windows 11, SOURCE build (VS 18): discovery
19/19, configuration 20/20, fade 31/31, ramp_step 24/24, stop_priority 19/19, warn 23/23,
refusal 21/21, channel_fanout 29/29 - ALL WIRE TESTS PASSED. The earlier record follows.

Run 2026-10-15, stack `6.x` @ `64b2cfac5` (6.0.23), example v1.2.0, `common/` 3.4.0,
three runs in a row on each platform:

| Platform | Build | `channel_fanout_test.py` | `discovery_test.py` |
|---|---|---|---|
| Windows 11 | STATIC (stack `ReleaseLib` `x64` built with `CL=-DSTACK_OPTION_WRITE_GROUP`, VS 18, NMake) | 18/18, 5 known gaps - PASS x3 | 18/18 - PASS x3 |
| Linux (WSL Ubuntu 22.04) | SOURCE (g++; `CMakeLists.txt` defines `STACK_OPTION_WRITE_GROUP`) | 19/19, 5 known gaps - PASS x3 | 18/18 - PASS x3 |

Windows has one check fewer: the Peer cannot hear the broadcast Who-Is there.

With the series' standard STATIC library (built without `STACK_OPTION_WRITE_GROUP`)
the example does not start - `Error: Failed to enable the WriteGroup service.` - and
the test fails at "did not reach 'ready'". See TODO.md 1.

## Each check fails without what it checks

Every counted check of `channel_fanout_test.py` was run against a build with one thing
removed, on Linux, and failed; restoring it, it passed. Run 2026-10-15 at the same pin.

| Removed | Checks that failed |
|---|---|
| M1 `common/` 3.4.0's own-address broadcast redirect | Who-Is reaches the broadcast; Device_Address_Binding lists 389016; WriteGroup reaches 389016; SUCCESSFUL; IN_PROGRESS; BUSY; offline member was sent its write; recovery; SUCCESSFUL again (10/19 passed) |
| M2 Channel 1's remote reference | the same nine (10/19) |
| M3 Channel 1's local reference (Jade) | WriteGroup reaches Jade; offline still writes Jade; Jade refuses 150 % (16/19) |
| M4 `Write_Status` always SUCCESSFUL at the end | FAILED on timeout; refusing Peer FAILED; Jade refusing FAILED (16/19) |
| M5 IN_PROGRESS never set | eight `Write_Status` / BUSY checks (11/19) |
| M6 the BUSY refusal | BUSY (18/19) |
| M7 Schedule 1 referencing `Priority_Array[12]` again | Schedule references Present_Value (18/19) |
| M8 `Write_Status` served as the old constant 1 | IDLE at start-up and six more `Write_Status` checks (12/19) |
| M9 `HookTimeout` not registered | FAILED on timeout and five more, all left IN_PROGRESS (13/19) |
| M10 a local member's refusal not noted | Jade refuses 150 % (18/19) |
| M11 `HookError` not registered | refusing Peer FAILED and three more (15/19) |
| M12 `HookIAm` not registered | Device_Address_Binding lists 389016 (with its console line) and five `Write_Status` checks (13/19) |
| M13 `WriteGroupInhibitDelay` not marking the fan-out | eight `Write_Status` / BUSY checks (11/19) |
| M14 Schedule 1's reference to Channel 1 | Schedule references Present_Value; Schedule has written Channel 1 (17/19) |
| M15 `Last_Priority` not updated by a Channel write | Schedule has written Channel 1 (Last_Priority 12); Channel holds the WriteGroup's value (Last_Priority 8) (17/19) |
| M16 Channel accepting only the documented Priority_Array shape (stack #3955) | 15 checks, everything that writes Channel 1 (4/19) |
