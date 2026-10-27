# BACnet B-LS (Lighting Supervisor) — C++ example

A complete, self-contained C++ tutorial that implements the **B-LS (Lighting
Supervisor)** profile from ASHRAE 135 Annex L using the
[CAS BACnet Stack](https://store.chipkin.com/products/stacks/cas-bacnet-stack).

A **B-LS supervises other lights.** In the words of 135-2024 Annex L.11.1, it is
"any device that implements Channel objects and optionally Lighting Output and/or
Binary Lighting Output objects with the ability to forward channel writes to other
BACnet devices". One **WriteGroup** request names a Channel; the Channel writes the
value to every light it lists - its own Lighting Output ("Jade") and a Lighting
Output on **another device** (389016) - and its `Write_Status` says whether every
one of those writes worked. This example is the series' **canonical
implementation of F-CHANNEL, F-EXTWRITE, and F-SCHED-E** - a later example that
needs a Channel object, a cross-device (remote) object reference, or a Schedule
that executes a write copies the relevant section here.

**[Download a prebuilt binary](https://github.com/chipkin/BACnetProfileExample-B-LS-CPP/releases)**
(Windows and Linux x64) - or build it yourself, see [Build](#build) below.

- **[TUTORIAL.md](TUTORIAL.md)** - how to extend this example and how to review
  it for conformance. Read it when you start turning this into your own device.
- **[docs/PICS.md](docs/PICS.md)** - the Protocol Implementation Conformance
  Statement: every object, every property, and who answers it.

> **Versions:** this document describes **example v1.3.0**, built and verified
> against **CAS BACnet Stack 6.0.23** (`6.x` @ `69b6249f`), at
> **Protocol_Revision 30**, with the vendored `common/` helper at **v3.5.0**.
> Running the example prints all three - if what it prints disagrees with this
> line, trust the program and check `CHANGELOG.md`.

> **Requires a stack with the Channel/Schedule engine and Device_Address_Binding**
> (`BACnetStack_AddChannelObject`, `BACnetStack_AddScheduleObject`,
> `BACnetStack_SendWriteGroup`, ...) and **compiled with
> `STACK_OPTION_WRITE_GROUP`** (see [Build](#build)). See
> [TUTORIAL.md](TUTORIAL.md#how-the-remote-write-actually-happens) for how a
> write to a remote device actually happens at this pin.

## The scenario: one WriteGroup, two lights, one of them on another device

Proved by the [Wire Tests](#wire-tests), against a Python Peer that plays device
389016 (a light with Lighting Output 1) and a Python client that sends WriteGroup:

1. **The supervisor finds the other device by itself.** Channel 1 names device
   389016, so the stack's Device_Address_Binding broadcasts a Who-Is for it at
   start-up. The Peer answers with an I-Am, and `Device_Address_Binding` lists
   389016.
2. **One WriteGroup reaches both lights.** The client sends WriteGroup (group 1,
   channel 1, 60.0, priority 8). Channel 1 takes the value and the stack writes it
   to Jade, locally, and sends device 389016 a WriteProperty of Lighting Output 1
   `Present_Value` = 60.0 at priority 8. The Peer acknowledges; `Write_Status` goes
   IN_PROGRESS, then SUCCESSFUL (cl. 12.53.5, 12.53.7).
3. **Failure Mode - the other device goes offline.** The next WriteGroup still
   writes Jade. `Write_Status` stays IN_PROGRESS while the stack waits for 389016
   (a WriteProperty to Channel 1 meanwhile is refused with BUSY, cl. 12.53.5), and
   turns FAILED when the write times out (APDU_Timeout x (Number_Of_APDU_Retries +
   1): 40 s at the stack's defaults, 10 s x 4). The Peer comes back:
   the next WriteGroup reaches it and `Write_Status` is SUCCESSFUL again.
4. **Failure Mode - a light refuses the value.** The Peer answers the write with
   an Error, or Jade refuses 150 % (out of range): `Write_Status` is FAILED, and the
   other light is still written.

The console shows the same thing:

```
RX 21 bytes from 127.0.0.1:64935 (Network Port 1) - Unconfirmed: WriteGroup
WriteGroup: Channel 1 (Garnet) <- 60.00 @ priority 8
Channel 1 (Garnet) Write_Status = in-progress
WriteProperty: Lighting Output 1 <- 60.00 @ priority 8
TX 26 bytes to 127.0.0.1:64934 (Network Port 1) - ConfirmedRequest: WriteProperty Lighting_Output 1.Present_Value
RX 9 bytes from 127.0.0.1:64934 (Network Port 1) - SimpleACK: WriteProperty
Remote member (device 389016, Lighting Output 1): SimpleACK
Channel 1 (Garnet) Write_Status = successful
```

> **Every write to Channel 1 is forwarded.** At this Stack Pin the stack propagates
> a WriteProperty and Schedule 1's write to Channel 1's members exactly as it does a
> WriteGroup (135-2024 cl. 12.53.5), and `Write_Status` follows each of them
> (`main.cpp` section 2e). Schedule 1 writes Channel 1 (100.0 at priority 12) on the
> example's first tick, before device 389016 has answered a Who-Is, so the stack
> cannot address it and skips its write: Jade takes 100 %, and `Write_Status` reads
> FAILED until the next write that reaches both members. BUSY goes out with Error
> Class OBJECT.

### What is Simulation here

**Simulation**, in this series, means non-BACnet scaffolding that stands in for the physical world. Here it
is one thing: **Jade has no lamp.** Its Lighting Output engine (`main.cpp`
section 1b, the same engine as the
[B-LD example](https://github.com/chipkin/BACnetProfileExample-B-LD-CPP)) is real
BACnet: a `fadeTo` or `rampTo` takes time, with `Tracking_Value` moving and
`In_Progress` reporting `fadeActive` / `rampActive`; the step, warn, restore and
toggle operations follow Table 12-67; `NONE` is refused. Only the lamp itself is
simulated: a blink-warn prints a line instead of flashing a light, and a real
driver would dim the hardware to `Tracking_Value`.
Everything the Channel, the WriteGroup, the remote WriteProperty, `Write_Status`
and the Schedule do is real BACnet. Device 389016 is not part of the example: in
the Wire Tests it is a Python Peer; on a real network it is any device with a
Lighting Output 1 - for example the
[B-LD example](https://github.com/chipkin/BACnetProfileExample-B-LD-CPP), whose
default device instance is 389016, running on another host of this subnet on the
same UDP port (a BACnet/IP network is the devices sharing one UDP port, so a
device on another port never hears this one's Who-Is).

## What this example supports

| Required BIBB | What it means | How this example does it |
|---|---|---|
| **DS-RP-B** | Execute ReadProperty | `SERVICE_READ_PROPERTY`; `GetProperty*` callbacks |
| **DS-WP-A** | Initiate WriteProperty | the stack, when a write (WriteGroup, WriteProperty or Schedule 1) reaches Channel 1: its remote reference names device 389016, addressed through the Device_Address_Binding. `main.cpp` never calls `SendWriteProperty`; it follows the answer through the SimpleACK / Error / Reject / Abort / Timeout hooks (Wire Test) |
| **DS-WP-B** | Execute WriteProperty | `SERVICE_WRITE_PROPERTY`; `SetProperty*` callbacks |
| **DS-WG-E-B** | Execute WriteGroup (the defining BIBB) | `SERVICE_WRITE_GROUP`; Channel 1 ("Garnet") fans the write out to Jade and device 389016; `Write_Status` follows it (Wire Test) |
| **DS-ALO-A** | Initiate a write to a remote (lighting) output | the same stack-initiated WriteProperty as DS-WP-A, to device 389016's Lighting Output 1 (Wire Test) |
| **SCHED-E-B** | Execute a Schedule | Schedule 1 ("Saffron") writes Channel 1's Present_Value at priority 12, and the Channel forwards it to Jade and device 389016 (Wire Test) |
| **DM-DDB-A** | Initiate Who-Is | the stack's Device_Address_Binding, for device 389016, at start-up (Wire Test, Linux); also the `'d'` demo key - `BACnetStack_SendWhoIs` |
| **DM-DDB-B** | Answer Who-Is with I-Am | Handled by the stack; plus an unsolicited I-Am on start-up |
| **DM-DOB-B** | Answer Who-Has with I-Have | Handled by the stack |
| **DM-DCC-B** | Execute DeviceCommunicationControl | `SERVICE_DEVICE_COMMUNICATION_CONTROL`; `DeviceCommunicationControl` callback |
| **DM-TS-B / DM-UTC-B** | Execute TimeSynchronization, local AND UTC | `SERVICE_TIME_SYNCHRONIZATION` + `SERVICE_UTC_TIME_SYNCHRONIZATION`; `SetSystemTime` callback |

**Deliberately NOT included** — a B-LS does not require them: ReadPropertyMultiple,
SubscribeCOV, alarms and events, trending, backup/restore.

## The device this example creates

| Object | Instance | Name | Notes |
|---|---|---|---|
| Device | 389017 | Chipkin Example B-LS | Configurable with `--deviceID` and `--deviceName` |
| Analog Input | 1 | Bronze | REAL, °C; read-only; starts at 21.5 |
| Binary Input | 1 | Emerald | active / inactive; read-only |
| Multi-State Input | 1 | Hot Pink | state 1..3; read-only |
| Analog Output | 1 | Chartreuse | REAL setpoint; WRITABLE, commandable |
| Binary Output | 1 | Fuchsia | active / inactive; WRITABLE, commandable |
| Multi-State Output | 1 | Indigo | state 1..3; WRITABLE, commandable |
| Lighting Output | 1 | Jade | REAL 0–100 %; WRITABLE, commandable, `Lighting_Command` (B-LD's Lighting Output engine; the local WriteGroup/Schedule target) |
| **Channel** | **1** | **Garnet** | **BACnetChannelValue REAL; WRITABLE, commandable - fans every write out to Jade AND a remote device (F-CHANNEL / F-EXTWRITE)** |
| **Schedule** | **1** | **Saffron** | **Writes Channel 1's Present_Value on a timer (F-SCHED-E); the Channel forwards the write to its members** |
| **Calendar** | **1** | **Cream** | **A real, independently-readable Calendar object - see [TUTORIAL.md](TUTORIAL.md#troubleshooting) for the one documented gap** |
| Network Port | 1 | Vermilion | The BACnet/IP port (required) |

Three pieces work together to drive a remote write: Channel 1 ("Garnet") holds
one local and one remote object-property reference; an incoming WriteGroup
(DS-WG-E-B) matches the Channel by its `Channel_Number` / `Control_Groups` and
fans the write out to every reference; Schedule 1 ("Saffron") writes the same
Channel's `Present_Value` at 09:00/17:00 daily, and a demo exception event for
today (from 00:00:05) means it is already writing 100 % when the device starts.
The Channel forwards the Schedule's write to its members like any other (see the
note above). The remote write itself is performed by the stack, addressed
through its own Device_Address_Binding, not by application code; the application
keeps `Write_Status` from the answers (`main.cpp` section 2e) - see
[TUTORIAL.md](TUTORIAL.md#how-the-remote-write-actually-happens) for the full
mechanism.

Every required property of every object, and who answers it, is in
[docs/PICS.md](docs/PICS.md).

## Requires the CAS BACnet Stack (licensed product)

This example **builds against the CAS BACnet Stack, which is a commercial Chipkin
product** - it is not free or open source, and there is no public/trial build.
The stack is referenced here as the **private** git submodule
`submodules/cas-bacnet-stack`; you can only fetch and build it once you have a CAS
BACnet Stack license and access to that repository.

**To get the CAS BACnet Stack (and access to build this example), contact
Chipkin:** <https://store.chipkin.com/services/stacks/bacnet-stack> or
sales@chipkin.com.

You do not need a stack licence to *read* this example, or to run a
[prebuilt release binary](https://github.com/chipkin/BACnetProfileExample-B-LS-CPP/releases).
The licence is what lets you *build* it - that is the part the stack submodule
gates.

## What's in this repository

This is a **self-contained** project. It ships:

- `main.cpp` - the example device.
- `common/` - the shared helper (UDP, callbacks, CLI, keyboard) vendored in.
- `CMakeLists.txt` - the build, the same on Windows, Linux, and macOS.
- `docs/PICS.md` - the conformance statement.
- `docs/objects.json` - the input to the objects-and-properties generator.
- `tests/` - the Wire Tests (see [Wire Tests](#wire-tests)), and `wiretest/`, the
  series' shared Python harness they are written against (vendored, like `common/`).
- `submodules/cas-bacnet-stack/` - the **CAS BACnet Stack as a git submodule**
  (private; requires a license - see above). Its sources are compiled into the
  executable, so there is no library or DLL to build, ship, or install.

## Prerequisites

- A C++17 compiler (MSVC, GCC, or Clang).
- CMake >= 3.15.
- Git (to fetch the stack submodule).

### Windows

- **C++ compiler** - install
  [Visual Studio Community](https://visualstudio.microsoft.com/downloads/)
  (free) and select the **"Desktop development with C++"** workload.
- **CMake** - from <https://cmake.org/download/>, or `winget install Kitware.CMake`.

### Linux / macOS

- Debian/Ubuntu: `sudo apt install build-essential cmake git`
- macOS: `xcode-select --install` and `brew install cmake`

## Build

CMake only, and the same two commands on every platform:

```bash
git clone --recursive https://github.com/chipkin/BACnetProfileExample-B-LS-CPP.git
cd BACnetProfileExample-B-LS-CPP

cmake -B build -S .
cmake --build build --config Release
```

Already cloned without `--recursive`? Run `git submodule update --init --recursive`
first - the build needs the stack submodule.

> **The first build takes a few minutes** - it compiles the entire CAS BACnet
> Stack (~600 source files) into the executable. Rebuilds after that are
> incremental and take seconds.

If your CAS BACnet Stack lives somewhere other than the bundled submodule, point
CMake at it: `cmake -B build -S . -D CAS_STACK_DIR=/path/to/cas-bacnet-stack`.

> **WriteGroup must be compiled into the stack.** The stack's default preset
> (`STACK_OPTION_TARGET_FULL`) does not compile the WriteGroup service; only
> `STACK_OPTION_WRITE_GROUP` (or `STACK_OPTION_PROFILE_B_LS`) does. Without it
> the stack can neither execute nor send a WriteGroup, and this example stops at
> start-up with `Error: Failed to enable the WriteGroup service.` The default
> build above compiles the stack from source, and `CMakeLists.txt` defines
> `STACK_OPTION_WRITE_GROUP` for it. If you link a prebuilt stack library
> instead (`-D CAS_BACNET_STACK_LINK=STATIC` or `DLL`), build that library with
> `STACK_OPTION_WRITE_GROUP` defined - for example, on Windows, run the stack's
> MSBuild with the environment variable `CL=-DSTACK_OPTION_WRITE_GROUP` (from Git
> Bash in the example-series folder: `CL=-DSTACK_OPTION_WRITE_GROUP
> tools/build-stack-static.sh BACnetProfileExample-B-LS-CPP`; write `-D`, not `/D`,
> which Git Bash rewrites into a path). Stack issue
> [#3954](https://github.com/chipkin/cas-bacnet-stack/issues/3954).

## Run

```bash
# Linux / macOS
./build/BACnetExampleBLS

# Windows
.\build\Release\BACnetExampleBLS.exe
```

Expected output:

```
BACnet B-LS (Lighting Supervisor) Example - C++ v1.3.0
CAS BACnet Stack version: 6.0.23.0
Common helper (common/) version: 3.5.0
FYI: Listening for BACnet/IP on UDP port 47808 (Network Port 1).
TX 21 bytes to 192.168.3.255:47808 (broadcast) (Network Port 1) - Unconfirmed: I-Am
FYI: Device 389017 ("Chipkin Example B-LS") ready. Vendor ID 389. Press 'h' for help.
FYI: Lighting Output 1 (Jade) starts at 0.0% (off). WriteProperty its
     Lighting_Command to fade/ramp/step/warn it, or its Present_Value to set a level.
FYI: Channel 1 (Garnet) fans every write out to Jade AND remote device 389016.
     Press 'd' to discover it (Who-Is), then 'w' to fire a demo WriteGroup.
     Schedule 1 (Saffron) writes Channel 1 at 09:00/17:00 daily; a demo
     exception for today (from 00:00:05) has it writing 100% now.
RX 21 bytes from 192.168.3.64:47808 (Network Port 1) - Unconfirmed: I-Am
Write: Channel 1 (Garnet) <- 100.00 @ priority 12
FYI: remote device 389016 has not answered a Who-Is (no I-Am yet), so the stack
     cannot address it: its write is skipped and Write_Status will be FAILED.
Channel 1 (Garnet) Write_Status = in-progress
WriteProperty: Lighting Output 1 Present_Value <- 100.00 @ priority 12
TX 20 bytes to 192.168.3.255:47808 (broadcast) (Network Port 1) - Unconfirmed: Who-Is DNET=65535
Channel 1 (Garnet) Write_Status = failed (the remote member's write did not succeed)
```

`Write:` is Schedule 1 writing Channel 1 as soon as the device starts: its demo
exception event covers today from 00:00:05, so it is already in effect. The
Channel forwards it to Jade at once; device 389016 is not known yet, so its write
is skipped and `Write_Status` ends FAILED. The `Who-Is` is the stack's
Device_Address_Binding looking for device 389016. When it answers, the console
prints `I-Am: remote device 389016 is at ... - Channel 1 can write to it now.`,
and the next write to Channel 1 reaches it.

The device listens on UDP **47808** (BACnet/IP). Allow that port through your
firewall. To use a different port, pass `--port` (see below).

> **A wall of red `Error:` lines at start-up is expected and is not your bug** -
> it is the stack's own debug logging. [TUTORIAL.md](TUTORIAL.md#troubleshooting)
> explains it, and the other silent failure modes this example warns about.

### Command-line options

| Option | Default | Meaning |
|--------|---------|---------|
| `--port <n>` | `47808` | UDP port to listen on (BACnet/IP). |
| `--deviceID <n>` | `389017` | The device's BACnet instance number (BACnet requires this to be configurable). |
| `--deviceName <text>` | `Chipkin Example B-LS` | The Device object's `Object_Name`, 1..255 bytes, no control characters. It must be unique across the BACnet internetwork, so give every unit its own (BACnet requires it to be configurable, like the instance). An invalid value prints a warning and keeps the default. |
| `--xml` | off | Print every received and sent BACnet message as an indented XML block instead of a one-line summary (very verbose; for protocol debugging). |
| `--help`, `-h` | - | Show usage and exit. |
| `--version` | - | Print the example, stack, and `common/` helper versions, then exit. |

### Interactive commands

While the example runs, these keys are available:

| Key | Action |
|-----|--------|
| `h` | Show the version information and this command list. |
| `q` | Quit. |
| up arrow | Increase Analog Input 1 (`Bronze`) by 1.1. |
| down arrow | Decrease Analog Input 1 (`Bronze`) by 1.1. |
| `w` | Fire a demo WriteGroup at Channel 1's control group (`SendWriteGroup`). |
| `d` | Send a demo Who-Is so the Device_Address_Binding can resolve the remote device (`SendWhoIs`). |

The up/down keys change the live `Present_Value` of the analog input, so a
client re-reading it sees the new value. The Schedule's demo exception event
(see [Verify](#verify)) is in effect from start-up and needs no key press; `'s'`
does nothing in this example.

> **Windows reads keys from the console only.** The keys work when you type them
> in the example's own console window; they cannot be fed through a pipe, which
> is how the Linux checks in this README's notes were driven.

## Verify

Use a BACnet client such as the
[**CAS BACnet Explorer**](https://store.chipkin.com/products/tools/cas-bacnet-explorer),
and optionally a device 389016 with a Lighting Output 1 on the same subnet and
UDP port (`REMOTE_DEVICE_INSTANCE` in `main.cpp`; see
[What is Simulation here](#what-is-simulation-here)):

1. **Discover** - send a **Who-Is**. The device replies with **I-Am** from
   instance **389017** (vendor **389**). It also broadcasts an I-Am at start-up.
2. **Browse the object model** - the device shows twelve objects, including
   Channel 1 (`Garnet`), Schedule 1 (`Saffron`), and Calendar 1 (`Cream`).
   Reading the Device's `Object_List` returns all twelve.
3. **Read Channel 1** - `Channel_Number` / `Control_Groups` return `1` / `[1]`;
   `List_Of_Object_Property_References` returns two entries, one local
   (Lighting Output 1) and one remote (device 389016's Lighting Output 1);
   `Write_Status` reads `failed` after Schedule 1's start-up write (device 389016
   was not known yet) until the next write that reaches both members.
4. **Write** - a WriteProperty to any writable object (e.g. Analog Output 1's
   `Present_Value`) is accepted; a WriteProperty to a read-only sensor (e.g.
   Analog Input 1) is rejected.
5. **WriteGroup** - send WriteGroup group 1, channel 1, a REAL level (or press
   `'w'` in the example's console): Jade takes the level, device 389016 receives a
   WriteProperty of its Lighting Output 1 at the same priority, and Channel 1's
   `Write_Status` reads `successful` - or `failed` when 389016 is not there (after
   APDU_Timeout x (Number_Of_APDU_Retries + 1), 40 s at the stack's defaults, once
   it has been found; at once if it never answered a Who-Is).
6. **Schedule** - at start-up the console logs Schedule 1 writing Channel 1
   (`Write: Channel 1 (Garnet) <- 100.00 @ priority 12`): the demo exception event
   covers today from 00:00:05. Jade takes 100 % at priority 12; see the note above.
7. A service not in the support table (e.g. SubscribeCOV) is **rejected**.

For the full property-by-property review, the conformance statement, and this
example's documented verification gaps, see [TUTORIAL.md](TUTORIAL.md).

## Wire Tests

Automated, over BACnet/IP, from outside the running example; Python 3 standard
library only. Eight scripts:

- **`channel_fanout_test.py`** - the Profile Function and its Failure Modes, as in
  [the scenario](#the-scenario-one-writegroup-two-lights-one-of-them-on-another-device):
  a Python Peer plays device 389016 (it hears the example's broadcasts on Linux and
  macOS; on Windows it announces itself with an I-Am instead), a Python client sends
  the WriteGroups and WriteProperty requests. 30 counted checks on Linux (29 on
  Windows, which cannot hear a broadcast).
- **`fade_test.py`, `ramp_step_test.py`, `stop_priority_test.py`, `warn_test.py`,
  `refusal_test.py`** - Jade's `Lighting_Command` operations, refusals and
  timing (the B-LD example's Lighting Output tests; see
  [tests/README.md](tests/README.md)).
- **`discovery_test.py`** - what a client such as Explorer does when it discovers a
  device: Who-Is, the Device's `Object_List`, then every object's `Property_List`
  and a ReadProperty of every property it lists. Every read must come back as a value.
- **`configuration_test.py`** - the command line: `--deviceID` and `--deviceName`
  set the Device's instance and Object_Name at start-up (Who-Is, ReadProperty and
  Who-Has see them; a write of the name is refused), invalid names keep the
  default, and `--help` lists exactly the options the example reads.

```bash
python3 tests/run_wire_tests.py --exe build/BACnetExampleBLS          # Linux/macOS
python tests\run_wire_tests.py --exe build\Release\BACnetExampleBLS.exe   # Windows
```

It ends with `ALL WIRE TESTS PASSED` (exit 0) in about a minute and a half (the offline
member's write has to time out). CI runs it on Linux after the smoke test.
[tests/README.md](tests/README.md) says what each check proves and how each was
shown to fail without the feature it checks.

## The BACnet profile example series

<!-- PROFILE-TABLE:BEGIN (generated from cas-bacnet-stack-examples/docs/profile-table.md - do not edit here) -->
There is one example repository per standardized device profile in ASHRAE 135-2024 Annex L. An example marked ⛔ is blocked: the stack cannot yet perform that profile's function through its customer interface, and the example's README says what it does today. Pick the profile your device claims, then the language you build in. "Ask" means the example hasn't been built yet for that language - [contact Chipkin](https://store.chipkin.com/contact-us) if you need one.

### Controllers (Annex L.4)

| Profile | C++ | Node.js | C# | Rust | Python | Go |
|---|---|---|---|---|---|---|
| **B-SS** Smart Sensor | [B-SS-CPP](https://github.com/chipkin/BACnetProfileExample-B-SS-CPP) | [B-SS-Node](https://github.com/chipkin/BACnetProfileExample-B-SS-Node) | [B-SS-CS](https://github.com/chipkin/BACnetProfileExample-B-SS-CS) | [B-SS-Rust](https://github.com/chipkin/BACnetProfileExample-B-SS-Rust) | [B-SS-Python](https://github.com/chipkin/BACnetProfileExample-B-SS-Python) | [B-SS-Go](https://github.com/chipkin/BACnetProfileExample-B-SS-Go) |
| **B-SA** Smart Actuator | [B-SA-CPP](https://github.com/chipkin/BACnetProfileExample-B-SA-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-ASC** Application Specific Controller | [B-ASC-CPP](https://github.com/chipkin/BACnetProfileExample-B-ASC-CPP) | [B-ASC-Node](https://github.com/chipkin/BACnetProfileExample-B-ASC-Node) | Ask | Ask | Ask | Ask |
| **B-AAC** Advanced Application Controller | [B-AAC-CPP](https://github.com/chipkin/BACnetProfileExample-B-AAC-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-BC** Building Controller | [B-BC-CPP](https://github.com/chipkin/BACnetProfileExample-B-BC-CPP) | Ask | Ask | Ask | Ask | Ask |

### Life safety controllers (Annex L.5)

| Profile | C++ | Node.js | C# | Rust | Python | Go |
|---|---|---|---|---|---|---|
| **B-LSC** Life Safety Controller | [B-LSC-CPP](https://github.com/chipkin/BACnetProfileExample-B-LSC-CPP) 🚧 | Ask | Ask | Ask | Ask | Ask |
| **B-ALSC** Advanced Life Safety Controller | [B-ALSC-CPP](https://github.com/chipkin/BACnetProfileExample-B-ALSC-CPP) | Ask | Ask | Ask | Ask | Ask |

### Access control controllers (Annex L.6)

| Profile | C++ | Node.js | C# | Rust | Python | Go |
|---|---|---|---|---|---|---|
| **B-ACC** Access Control Controller | [B-ACC-CPP](https://github.com/chipkin/BACnetProfileExample-B-ACC-CPP) ⛔ blocked on [stack #2150](https://github.com/chipkin/cas-bacnet-stack/issues/2150), [#2044](https://github.com/chipkin/cas-bacnet-stack/issues/2044) | Ask | Ask | Ask | Ask | Ask |
| **B-AACC** Advanced Access Control Controller | [B-AACC-CPP](https://github.com/chipkin/BACnetProfileExample-B-AACC-CPP) | Ask | Ask | Ask | Ask | Ask |

### Lighting controllers (Annex L.11)

| Profile | C++ | Node.js | C# | Rust | Python | Go |
|---|---|---|---|---|---|---|
| **B-LD** Lighting Device | [B-LD-CPP](https://github.com/chipkin/BACnetProfileExample-B-LD-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-LS** Lighting Supervisor | [B-LS-CPP](https://github.com/chipkin/BACnetProfileExample-B-LS-CPP) | Ask | Ask | Ask | Ask | Ask |

### Elevator controllers (Annex L.13)

| Profile | C++ | Node.js | C# | Rust | Python | Go |
|---|---|---|---|---|---|---|
| **B-EM** Elevator Monitor | [B-EM-CPP](https://github.com/chipkin/BACnetProfileExample-B-EM-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-EC** Elevator Controller | [B-EC-CPP](https://github.com/chipkin/BACnetProfileExample-B-EC-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-AEC** Advanced Elevator Controller | [B-AEC-CPP](https://github.com/chipkin/BACnetProfileExample-B-AEC-CPP) | Ask | Ask | Ask | Ask | Ask |

### Authentication and authorization (Annex L.14)

| Profile | C++ | Node.js | C# | Rust | Python | Go |
|---|---|---|---|---|---|---|
| **B-AS** Authorization Server | [B-AS-CPP](https://github.com/chipkin/BACnetProfileExample-B-AS-CPP) ⛔ blocked on [stack #2043](https://github.com/chipkin/cas-bacnet-stack/issues/2043) | Ask | Ask | Ask | Ask | Ask |

### Miscellaneous (Annex L.7, combinable with any one family)

| Profile | C++ | Node.js | C# | Rust | Python | Go |
|---|---|---|---|---|---|---|
| **B-BBMD** Broadcast Management Device | [B-BBMD-CPP](https://github.com/chipkin/BACnetProfileExample-B-BBMD-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-ACDC** Access Control Door Controller | [B-ACDC-CPP](https://github.com/chipkin/BACnetProfileExample-B-ACDC-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-ACCR** Access Control Credential Reader | [B-ACCR-CPP](https://github.com/chipkin/BACnetProfileExample-B-ACCR-CPP) ⛔ blocked on [stack #3934](https://github.com/chipkin/cas-bacnet-stack/issues/3934) | Ask | Ask | Ask | Ask | Ask |
| **B-RTR** Router | [B-RTR-CPP](https://github.com/chipkin/BACnetProfileExample-B-RTR-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-GW** Gateway | [B-GW-CPP](https://github.com/chipkin/BACnetProfileExample-B-GW-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-DAP** Device Address Proxy | [B-DAP-CPP](https://github.com/chipkin/BACnetProfileExample-B-DAP-CPP) ⛔ blocked on [stack #2032](https://github.com/chipkin/cas-bacnet-stack/issues/2032) | Ask | Ask | Ask | Ask | Ask |
| **B-SCHUB** BACnet/SC Hub | [B-SCHUB-CPP](https://github.com/chipkin/BACnetProfileExample-B-SCHUB-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-GENERAL** General device (Annex L.8) | *(satisfied by every example above)* | — | — | — | — | — |

### Operator interfaces and workstations (Annex L.1–L.3, L.9–L.10, L.12)

Client-side profiles.

| Profile | C++ | Node.js | C# | Rust | Python | Go |
|---|---|---|---|---|---|---|
| **B-OD** Operator Display | [B-OD-CPP](https://github.com/chipkin/BACnetProfileExample-B-OD-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-OWS** Operator Workstation | planned | — | — | — | — | — |
| **B-AWS** Advanced Operator Workstation | planned | — | — | — | — | — |
| **B-XAWS** Extended Advanced Operator Workstation | planned | — | — | — | — | — |
| **B-LSAP** Life Safety Annunciator Panel | planned | — | — | — | — | — |
| **B-LSWS** Life Safety Workstation | planned | — | — | — | — | — |
| **B-ALSWS** Advanced Life Safety Workstation | planned | — | — | — | — | — |
| **B-ACSD** Access Control Security Display | planned | — | — | — | — | — |
| **B-ACWS** Access Control Workstation | planned | — | — | — | — | — |
| **B-AACWS** Advanced Access Control Workstation | planned | — | — | — | — | — |
| **B-LOD** Lighting Operator Display | planned | — | — | — | — | — |
| **B-ALWS** Advanced Lighting Workstation | planned | — | — | — | — | — |
| **B-LCS** Lighting Control Station | planned | — | — | — | — | — |
| **B-ALCS** Advanced Lighting Control Station | planned | — | — | — | — | — |
| **B-ED** Elevator Display | planned | — | — | — | — | — |
| **B-EWS** Elevator Workstation | planned | — | — | — | — | — |
| **B-AEWS** Advanced Elevator Workstation | planned | — | — | — | — | — |

🚧 = in progress. ⛔ = Blocked Example (blocked on the named stack gap). "Ask" = not yet built for that language; contact Chipkin if you need it. Profile definitions: ANSI/ASHRAE 135-2024 Annex L. BIBB definitions: Annex K. Get the stack: <https://store.chipkin.com/services/stacks/bacnet-stack>.
<!-- PROFILE-TABLE:END -->

## Versions

| | |
|---|---|
| Example version | 1.3.0 |
| `common/` helper | 3.5.0 |
| CAS BACnet Stack | 6.0.23 — pinned at `6.x` @ `69b6249f`, compiled from source with `STACK_OPTION_WRITE_GROUP` |
| Protocol_Revision | 30 (the stack default at the pin) |
| Verified on | Windows (MSVC, VS 18, SOURCE), 2026-10-27 |

## References

- **ANSI/ASHRAE Standard 135** (BACnet) - the protocol standard. Object model
  (Clause 12), services (Clause 15), BACnet/IP (Annex J), device profiles
  (Annex L). Purchase / preview via the [ASHRAE store](https://www.ashrae.org/technical-resources/standards-and-guidelines).
- **What is BACnet?** - Chipkin's introduction:
  <https://docs.chipkin.com/protocols/bacnet/>.
- **CAS BACnet Stack** - product page and documentation:
  <https://store.chipkin.com/services/stacks/bacnet-stack>.
- **CAS BACnet Explorer** - client for testing this device:
  <https://store.chipkin.com/products/tools/cas-bacnet-explorer>.
- **Shared helper used by this example** - [`common/README.md`](common/README.md).

See also [TUTORIAL.md](TUTORIAL.md), [docs/PICS.md](docs/PICS.md),
[CHANGELOG.md](CHANGELOG.md), and [AGENTS.md](AGENTS.md).

## License

The example source code is dedicated to the public domain under
[CC0-1.0](LICENSE) — copy it into your project freely. The **CAS BACnet Stack is
a separate, commercially licensed product** and is not covered by that
dedication; contact [Chipkin](https://store.chipkin.com/) for licensing.
