# BACnet B-LS (Lighting Supervisor) — C++ example

A complete, self-contained C++ tutorial that implements the **B-LS (Lighting
Supervisor)** profile from ASHRAE 135 Annex L using the
[CAS BACnet Stack](https://store.chipkin.com/products/stacks/cas-bacnet-stack).

A **B-LS supervises other lights**: it does not have a Lighting Output of its
own to command by hand (well - it does, "Jade", for the demo - see below) so
much as it commands OTHER devices' lights, in bulk, via a **Channel** object
that a **WriteGroup** request fans out to several targets at once, including a
**remote** device, and a **Schedule** that writes the Channel on a timer. This
example is the series' **canonical implementation of F-CHANNEL, F-EXTWRITE, and
F-SCHED-E** - a later example that needs a Channel object, a cross-device
(remote) object reference, or a Schedule that executes a write copies the
relevant section here.

> **What works at this Stack Pin, and what does not** (checked 2026-10-15 at
> `6.x` @ `64b2cfac5`; details and evidence in [TODO.md](TODO.md)):
>
> - **A WriteGroup fans out to the local Lighting Output.** Pressing `'w'`
>   (Linux) sends a WriteGroup that Channel 1 matches, and Jade goes from 0 % to
>   100 %. This needs the stack compiled with `STACK_OPTION_WRITE_GROUP`, which
>   the stack's default preset leaves out; this example's CMake turns it on (see
>   [Build](#build)).
> - **The remote fan-out has not been seen working.** No test has run a second
>   device yet, and the Who-Is the stack sends to find device 389016 goes to this
>   host's own address rather than the subnet broadcast (a known `common/`
>   defect, stack #3933), so the binding may never resolve.
> - **The Schedule does not drive the fan-out.** It writes Channel 1's
>   Present_Value, but the stack propagates a Channel write to its members only
>   for a WriteGroup. 135-2024 cl. 12.53.5 says any write to Present_Value
>   propagates; that is a stack defect, recorded in TODO.md.
> - **A WriteProperty to Channel 1** is accepted and stored, but for the same
>   reason it is not propagated to Jade or the remote device.

**[Download a prebuilt binary](https://github.com/chipkin/BACnetProfileExample-B-LS-CPP/releases)**
(Windows and Linux x64) - or build it yourself, see [Build](#build) below.

- **[TUTORIAL.md](TUTORIAL.md)** - how to extend this example and how to review
  it for conformance. Read it when you start turning this into your own device.
- **[docs/PICS.md](docs/PICS.md)** - the Protocol Implementation Conformance
  Statement: every object, every property, and who answers it.

> **Versions:** this document describes **example v1.1.0**, built and verified
> against **CAS BACnet Stack 6.0.23** (`6.x` @ `64b2cfac5`), at
> **Protocol_Revision 30**, with the vendored `common/` helper at **v3.3.0**.
> Running the example prints all three - if what it prints disagrees with this
> line, trust the program and check `CHANGELOG.md`.

> **Requires a stack with the Channel/Schedule engine and Device_Address_Binding**
> (`BACnetStack_AddChannelObject`, `BACnetStack_AddScheduleObject`,
> `BACnetStack_SendWriteGroup`, ...), present at this example's pinned commit. See
> [TUTORIAL.md](TUTORIAL.md#how-the-remote-write-actually-happens) for how a
> write to a remote device actually happens at this pin.

## What this example supports

| Required BIBB | What it means | How this example does it |
|---|---|---|
| **DS-RP-B** | Execute ReadProperty | `SERVICE_READ_PROPERTY`; `GetProperty*` callbacks |
| **DS-WP-A** | Initiate WriteProperty | the stack, when a WriteGroup reaches Channel 1 and its remote reference names device 389016 (Device_Address_Binding). `main.cpp` never calls `SendWriteProperty`; the `'w'`/`'d'` keys send a WriteGroup and a Who-Is. Not yet seen on the wire (see above) |
| **DS-WP-B** | Execute WriteProperty | `SERVICE_WRITE_PROPERTY`; `SetProperty*` callbacks |
| **DS-WG-E-B** | Execute WriteGroup (the defining BIBB) | `SERVICE_WRITE_GROUP`; Channel 1 ("Garnet") fans the write out |
| **DS-ALO-A** | Initiate a write to a remote (lighting) output | the same stack-initiated WriteProperty as DS-WP-A; not yet seen on the wire |
| **SCHED-E-B** | Execute a Schedule | Schedule 1 ("Saffron") writes Channel 1's Present_Value at priority 12 (no fan-out at this pin, see above) |
| **DM-DDB-A** | Initiate Who-Is | the `'d'` demo key - `BACnetStack_SendWhoIs` |
| **DM-DDB-B** | Answer Who-Is with I-Am | Handled by the stack; plus an unsolicited I-Am on start-up |
| **DM-DOB-B** | Answer Who-Has with I-Have | Handled by the stack |
| **DM-DCC-B** | Execute DeviceCommunicationControl | `SERVICE_DEVICE_COMMUNICATION_CONTROL`; `DeviceCommunicationControl` callback |
| **DM-TS-B / DM-UTC-B** | Execute TimeSynchronization, local AND UTC | `SERVICE_TIME_SYNCHRONIZATION` + `SERVICE_UTC_TIME_SYNCHRONIZATION`; `SetSystemTime` callback |

**Deliberately NOT included** — a B-LS does not require them: ReadPropertyMultiple,
SubscribeCOV, alarms and events, trending, backup/restore.

## The device this example creates

| Object | Instance | Name | Notes |
|---|---|---|---|
| Device | 389017 | Chipkin Example B-LS | Configurable with `--deviceID` |
| Analog Input | 1 | Bronze | REAL, °C; read-only; starts at 21.5 |
| Binary Input | 1 | Emerald | active / inactive; read-only |
| Multi-State Input | 1 | Hot Pink | state 1..3; read-only |
| Analog Output | 1 | Chartreuse | REAL setpoint; WRITABLE, commandable |
| Binary Output | 1 | Fuchsia | active / inactive; WRITABLE, commandable |
| Multi-State Output | 1 | Indigo | state 1..3; WRITABLE, commandable |
| Lighting Output | 1 | Jade | REAL 0–100 %; WRITABLE, commandable (from B-LD; the local WriteGroup/Schedule target) |
| **Channel** | **1** | **Garnet** | **BACnetChannelValue REAL; WRITABLE, commandable - fans a WriteGroup out to Jade AND a remote device (F-CHANNEL / F-EXTWRITE)** |
| **Schedule** | **1** | **Saffron** | **Writes Channel 1's Present_Value on a timer (F-SCHED-E); at this pin the write is not propagated to Channel 1's members** |
| **Calendar** | **1** | **Cream** | **A real, independently-readable Calendar object - see [TUTORIAL.md](TUTORIAL.md#troubleshooting) for the one documented gap** |
| Network Port | 1 | Vermilion | The BACnet/IP port (required) |

Three pieces work together to drive a remote write: Channel 1 ("Garnet") holds
one local and one remote object-property reference; an incoming WriteGroup
(service 40, DS-WG-E-B) matches the Channel by its `Channel_Number` /
`Control_Groups` and fans the write out to every reference; Schedule 1
("Saffron") writes the same Channel at 09:00/17:00 daily, and a demo exception
event for today (from 00:00:05) means it is already writing 100 % when the
device starts. The Schedule's write is not propagated to the Channel's members
at this pin (see the note at the top). The remote write
itself is performed by the stack's own Device_Address_Binding, not application
code - see [TUTORIAL.md](TUTORIAL.md#how-the-remote-write-actually-happens)
for the full mechanism, including a documented change from this profile's
original design brief.

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
> MSBuild with the environment variable `CL=-DSTACK_OPTION_WRITE_GROUP`.

## Run

```bash
# Linux / macOS
./build/BACnetExampleBLS

# Windows
.\build\Release\BACnetExampleBLS.exe
```

Expected output:

```
BACnet B-LS (Lighting Supervisor) Example - C++ v1.1.0
CAS BACnet Stack version: 6.0.23.0
Common helper (common/) version: 3.3.0
FYI: Listening for BACnet/IP on UDP port 47808 (Network Port 1).
TX 21 bytes to 192.168.3.255:47808 (broadcast) (Network Port 1) - Unconfirmed: I-Am
FYI: Device 389017 ("Chipkin Example B-LS") ready. Vendor ID 389. Press 'h' for help.
FYI: Lighting Output 1 (Jade) starts at 0.0% (off). WriteProperty its
     Lighting_Command to fade/ramp/step it, or its Present_Value to set a level.
FYI: Channel 1 (Garnet) fans a WriteGroup out to Jade AND remote device 389016.
     Press 'd' to discover it (Who-Is), then 'w' to fire a demo WriteGroup.
     Schedule 1 (Saffron) writes Channel 1 at 09:00/17:00 daily; a demo
     exception for today (from 00:00:05) has it writing 100% now.
WriteProperty: Channel 1 (Garnet) <- 100.00 @ priority 12
```

The last line is Schedule 1 writing Channel 1 as soon as the device starts: its
demo exception event covers today from 00:00:05, so it is already in effect.

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
and optionally a second, separately-running
[BACnetProfileExample-B-LD-CPP](https://github.com/chipkin/BACnetProfileExample-B-LD-CPP)
instance on the same subnet on a different port (that is `REMOTE_DEVICE_INSTANCE`
= 389016 in `main.cpp`, the F-EXTWRITE target):

1. **Discover** - send a **Who-Is**. The device replies with **I-Am** from
   instance **389017** (vendor **389**). It also broadcasts an I-Am at start-up.
2. **Browse the object model** - the device shows twelve objects, including
   Channel 1 (`Garnet`), Schedule 1 (`Saffron`), and Calendar 1 (`Cream`).
   Reading the Device's `Object_List` returns all twelve.
3. **Read Channel 1** - `Channel_Number` / `Control_Groups` return `1` / `[1]`;
   `List_Of_Object_Property_References` returns two entries, one local
   (Lighting Output 1) and one remote (device 389016's Lighting Output 1).
4. **Write** - a WriteProperty to any writable object (e.g. Analog Output 1's
   `Present_Value`) is accepted; a WriteProperty to a read-only sensor (e.g.
   Analog Input 1) is rejected.
5. **WriteGroup** - press `'d'` then `'w'` in the console (or send the
   equivalent BACnet requests from an external client): Lighting Output 1
   (Jade) updates locally (checked on Linux at this pin: 0 % -> 100 %). A
   WriteProperty is meant to reach a second running instance's Lighting Output;
   that has not been seen working yet (see the note at the top).
6. **Schedule** - at start-up the console logs a Schedule-driven write to
   Channel 1 (`WriteProperty: Channel 1 (Garnet) <- 100.00 @ priority 12`): the
   demo exception event covers today from 00:00:05. Jade does not change; see
   the note at the top.
7. A service not in the support table (e.g. SubscribeCOV) is **rejected**.

For the full property-by-property review, the conformance statement, and this
example's documented verification gaps, see [TUTORIAL.md](TUTORIAL.md).

## Wire Tests

Discovery, automated: a Python BACnet client drives the running example over
BACnet/IP from outside it, the way a client discovers a device - Who-Is, the
Device's `Object_List`, then for every object its `Property_List` and a
ReadProperty of every property it lists. Every read must come back as a value; an
Error, Reject or Abort fails the run. Python 3 standard library only:

```bash
python3 tests/run_wire_tests.py --exe build/BACnetExampleBLS          # Linux/macOS
python tests\run_wire_tests.py --exe build\Release\BACnetExampleBLS.exe   # Windows
```

It ends with `ALL WIRE TESTS PASSED` (exit 0). CI runs it on Linux after the
smoke test. [tests/README.md](tests/README.md) says what each check proves. It
does not test the WriteGroup fan-out yet.


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
| Example version | 1.1.0 |
| `common/` helper | 3.3.0 |
| CAS BACnet Stack | 6.0.23 — pinned at `6.x` @ `64b2cfac5`, compiled from source with `STACK_OPTION_WRITE_GROUP` |
| Protocol_Revision | 30 (the stack default at the pin) |
| Verified on | Windows (MSVC, VS 18, STATIC) and Linux (g++, WSL Ubuntu 22.04, SOURCE), 2026-10-15 |

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
