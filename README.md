# BACnet B-LS (Lighting Supervisor) — C++ example

A complete, self-contained C++ tutorial that implements the **B-LS (Lighting
Supervisor)** profile from ASHRAE 135 Annex L using the
[CAS BACnet Stack](https://store.chipkin.com/products/stacks/cas-bacnet-stack).

A **B-LS supervises other lights**: it does not have a Lighting Output of its
own to command by hand (well - it does, "Jade", for the demo - see below) so
much as it commands OTHER devices' lights, in bulk, via a **Channel** object
that a **WriteGroup** request fans out to several targets at once, including a
**remote** device on another BACnet subnet, and a **Schedule** that fires the
same fan-out automatically on a timer. This example is the series' **canonical
implementation of F-CHANNEL, F-EXTWRITE, and F-SCHED-E** - a later example
that needs a Channel object, a cross-device (remote) object reference, or a
Schedule that executes a write copies the relevant section here.

**[Download a prebuilt binary](https://github.com/chipkin/BACnetProfileExample-B-LS-CPP/releases)**
(Windows and Linux x64) - or build it yourself, see [Build](#build) below.

- **[TUTORIAL.md](TUTORIAL.md)** - how to extend this example and how to review
  it for conformance. Read it when you start turning this into your own device.
- **[docs/PICS.md](docs/PICS.md)** - the Protocol Implementation Conformance
  Statement: every object, every property, and who answers it.

> **Versions:** this document describes **example v1.0.0**, built and verified
> against **CAS BACnet Stack 6.0.21** (`6.x` @ `abd4cee1`), at
> **Protocol_Revision 24**, with the vendored `common/` helper at **v2.5.0**.
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
| **DS-WP-A** | Initiate WriteProperty | the `'w'`/`'d'` demo keys - `BACnetStack_SendWriteGroup` / `SendWhoIs` |
| **DS-WP-B** | Execute WriteProperty | `SERVICE_WRITE_PROPERTY`; `SetProperty*` callbacks |
| **DS-WG-E-B** | Execute WriteGroup (the defining BIBB) | `SERVICE_WRITE_GROUP`; Channel 1 ("Garnet") fans the write out |
| **DS-ALO-A** | Initiate a write to a remote (lighting) output | the same A-side WriteProperty/WriteGroup path as DS-WP-A |
| **SCHED-E-B** | Execute a Schedule | Schedule 1 ("Saffron") drives the same fan-out on a timer |
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
| Device | 389017 | Rainbow | Configurable with `--deviceID` |
| Analog Input | 1 | Bronze | REAL, °C; read-only; starts at 21.5 |
| Binary Input | 1 | Emerald | active / inactive; read-only |
| Multi-State Input | 1 | Hot Pink | state 1..3; read-only |
| Analog Output | 1 | Chartreuse | REAL setpoint; WRITABLE, commandable |
| Binary Output | 1 | Fuchsia | active / inactive; WRITABLE, commandable |
| Multi-State Output | 1 | Indigo | state 1..3; WRITABLE, commandable |
| Lighting Output | 1 | Jade | REAL 0–100 %; WRITABLE, commandable (from B-LD; the local WriteGroup/Schedule target) |
| **Channel** | **1** | **Garnet** | **BACnetChannelValue REAL; WRITABLE, commandable - fans a WriteGroup out to Jade AND a remote device (F-CHANNEL / F-EXTWRITE)** |
| **Schedule** | **1** | **Saffron** | **Drives a write to Channel 1 on a timer, including the remote fan-out (F-SCHED-E)** |
| **Calendar** | **1** | **Cream** | **A real, independently-readable Calendar object - see [TUTORIAL.md](TUTORIAL.md#troubleshooting) for the one documented gap** |
| Network Port | 1 | Vermilion | The BACnet/IP port (required) |

Three pieces work together to drive a remote write: Channel 1 ("Garnet") holds
one local and one remote object-property reference; an incoming WriteGroup
(service 40, DS-WG-E-B) matches the Channel by its `Channel_Number` /
`Control_Groups` and fans the write out to every reference; Schedule 1
("Saffron") drives the same Channel automatically at 09:00/17:00 daily, plus a
one-off demo exception event a few seconds after start-up. The remote write
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

## Run

```bash
# Linux / macOS
./build/BACnetExampleBLS

# Windows
.\build\Release\BACnetExampleBLS.exe
```

Expected output:

```
BACnet B-LS (Lighting Supervisor) Example - C++ v1.0.0
CAS BACnet Stack version: 6.0.21.0
Common helper (common/) version: 2.5.0
FYI: Listening for BACnet/IP on UDP port 47808 (Network Port 1).
TX 21 bytes to 192.168.3.255:47808 (broadcast) (Network Port 1)
FYI: Device 389017 ("Rainbow") ready. Vendor ID 389. Press 'h' for help.
FYI: Lighting Output 1 (Jade) starts at 0.0% (off). WriteProperty its
     Lighting_Command to fade/ramp/step it, or its Present_Value to set a level.
FYI: Channel 1 (Garnet) fans a WriteGroup out to Jade AND remote device 389016.
     Press 'd' to discover it (Who-Is), then 'w' to fire a demo WriteGroup.
     Schedule 1 (Saffron) does the same automatically at 09:00/17:00 daily,
     plus a one-off demo exception a few seconds after start-up - or press
     's' to jump straight to it.
```

> The banner above says to press `'s'` to jump to the Schedule's exception
> event - that is what the binary actually prints, but at this pin `'s'` is
> not wired to a `case` in `main()`'s key-handling loop, so pressing it does
> nothing. The exception event fires on its own a few seconds after start-up
> regardless. See [TUTORIAL.md](TUTORIAL.md#troubleshooting).

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
(see [Verify](#verify)) fires on its own a few seconds after start-up and does
not need a key press - see [TUTORIAL.md](TUTORIAL.md#troubleshooting) for a
documented gap around the `'s'` key some earlier notes in this series describe.

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
   (Jade) updates locally, and a WriteProperty should reach a second running
   instance's Lighting Output.
6. **Schedule** - wait for the demo exception event a few seconds after
   start-up: the console logs a Schedule-driven WriteProperty to Channel 1.
7. A service not in the support table (e.g. SubscribeCOV) is **rejected**.

For the full property-by-property review, the conformance statement, and this
example's documented verification gaps, see [TUTORIAL.md](TUTORIAL.md).


## The BACnet profile example series

<!-- PROFILE-TABLE:BEGIN (generated from cas-bacnet-stack-examples/docs/profile-table.md - do not edit here) -->
The CAS BACnet Stack supports every standardized device profile in ASHRAE 135-2024 Annex L, and there is one example repository per profile. Pick the profile your device claims, then the language you build in. "Ask" means the example hasn't been built yet for that language - [contact Chipkin](https://store.chipkin.com/contact-us) if you need one.

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
| **B-ACC** Access Control Controller | [B-ACC-CPP](https://github.com/chipkin/BACnetProfileExample-B-ACC-CPP) | Ask | Ask | Ask | Ask | Ask |
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
| **B-AS** Authorization Server | [B-AS-CPP](https://github.com/chipkin/BACnetProfileExample-B-AS-CPP) | Ask | Ask | Ask | Ask | Ask |

### Miscellaneous (Annex L.7, combinable with any one family)

| Profile | C++ | Node.js | C# | Rust | Python | Go |
|---|---|---|---|---|---|---|
| **B-BBMD** Broadcast Management Device | [B-BBMD-CPP](https://github.com/chipkin/BACnetProfileExample-B-BBMD-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-ACDC** Access Control Door Controller | [B-ACDC-CPP](https://github.com/chipkin/BACnetProfileExample-B-ACDC-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-ACCR** Access Control Credential Reader | [B-ACCR-CPP](https://github.com/chipkin/BACnetProfileExample-B-ACCR-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-RTR** Router | [B-RTR-CPP](https://github.com/chipkin/BACnetProfileExample-B-RTR-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-GW** Gateway | [B-GW-CPP](https://github.com/chipkin/BACnetProfileExample-B-GW-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-DAP** Device Address Proxy | [B-DAP-CPP](https://github.com/chipkin/BACnetProfileExample-B-DAP-CPP) | Ask | Ask | Ask | Ask | Ask |
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

🚧 = in progress. "Ask" = not yet built for that language; contact Chipkin if you need it. Profile definitions: ANSI/ASHRAE 135-2024 Annex L. BIBB definitions: Annex K. Get the stack: <https://store.chipkin.com/services/stacks/bacnet-stack>.
<!-- PROFILE-TABLE:END -->

## Versions

| | |
|---|---|
| Example version | 1.0.0 |
| `common/` helper | 2.5.0 |
| CAS BACnet Stack | 6.0.21 — pinned at `6.x` @ `abd4cee1`, compiled from source |
| Protocol_Revision | 24 (the stack default — the highest it supports) |
| Verified on | Windows (MSVC 2022, C++17) |

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
