# B-LS Wire Tests

Tests that drive the running lighting supervisor over BACnet/IP from outside it. For now
there is one: discovery, the way a client such as Chipkin BACnet Explorer finds a
device and reads everything it says it has. It does not test the B-LS
Profile Function. That needs a Python peer standing in for
the remote device 389016 and a headless WriteGroup trigger: phase-2 work (see
TODO.md for what blocks the remote fan-out today).

The tests are written against the series' shared harness in
[`../wiretest/`](../wiretest/README.md) (vendored, like `common/`); everything
specific to this example is here. Python 3 standard library only - nothing to
`pip install`.

## Running

Build the example (README "Build"), then from the repository root:

```bash
python3 tests/run_wire_tests.py --exe build/BACnetExampleBLS
```

On Windows, `--exe build\Release\BACnetExampleBLS.exe`. It ends with
`ALL WIRE TESTS PASSED` (exit 0) or the scripts that failed. `--port` (default
47821) is the UDP port the test starts the example on. It takes a few seconds.
CI (`.github/workflows/release.yml`) runs it on Linux after the smoke test.

## The setup

```
test client (127.0.0.1, ephemeral UDP port)  - the Peer
    |  BACnet/IP, unicast
BACnetExampleBLS  UDP --port                 - Device 389017
```

The Peer is a Python BACnet client (`wiretest.Client`), never another example's
binary. It plays a BACnet client such as Chipkin BACnet Explorer.

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

## Results

Run 2026-10-15, stack `6.x` @ `64b2cfac5` (6.0.23), example v1.1.0:

| Platform | Build | Result |
|---|---|---|
| Windows 11 | STATIC (stack `ReleaseLib` `x64` built with `CL=-DSTACK_OPTION_WRITE_GROUP`, VS 18, NMake) | 18/18 - PASS x3, 173 reads, all values |
| Linux (WSL Ubuntu 22.04) | SOURCE (g++; `CMakeLists.txt` defines `STACK_OPTION_WRITE_GROUP`) | 18/18 - PASS x3, 173 reads, all values |

With the series' standard STATIC library (built without `STACK_OPTION_WRITE_GROUP`)
the example does not start - `Error: Failed to enable the WriteGroup service.` - and
the test fails at "did not reach 'ready'". See TODO.md, stack defect 1.
