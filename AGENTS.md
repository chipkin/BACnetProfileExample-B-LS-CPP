# AGENTS.md

Guidance for AI coding agents working in this repository. See
<https://agents.md/> for the format. Human contributors should read
[README.md](README.md) first, then [TUTORIAL.md](TUTORIAL.md).

## What this project is

A **tutorial** C++ example that implements the BACnet **B-LS (Lighting Supervisor)**
profile using the CAS BACnet Stack. It is one of a series - one git repo per
BACnet profile - and is the series' **canonical implementation of F-CHANNEL,
F-EXTWRITE, and F-SCHED-E**. The top priority is that the code reads like a
tutorial a customer can learn from and copy-paste. Favour clarity over
cleverness.

## Layout

This repository is self-contained:

- `main.cpp` - the example device.
- `common/` - the shared helper (vendored).
- `README.md` - what this example is. Keep it short and about THIS example only.
- `TUTORIAL.md` - how to extend and review the example. Long-form material that
  would bloat the README belongs here.
- `docs/PICS.md` - the Protocol Implementation Conformance Statement. Its
  objects-and-properties section is GENERATED from `docs/objects.json`; do not
  hand-edit between the `OBJECTS-PROPERTIES` markers.
- `docs/objects.json` - the input to that generator. Update it in the same change
  as any `main.cpp` change that adds an object or a `GetProperty*` branch.
- `submodules/cas-bacnet-stack/` - the **CAS BACnet Stack** as a git submodule
  (private; compiled from source). After cloning, run
  `git submodule update --init --recursive`.

The `PROFILE-TABLE` block in README.md is also generated, from the example-series
repository's `docs/profile-table.md`. Edit it there, not here.

## Build

Plain CMake, identical on every platform, in the adapter's default SOURCE mode
(the stack's sources are compiled into the executable - no prebuilt library, no
DLL, no per-platform pre-step):

```bash
git submodule update --init --recursive   # once, if not cloned with --recursive
cmake -B build -S .
cmake --build build --config Release
```

The first build compiles the whole stack (~600 files) and takes a few minutes;
rebuilds after that are incremental and fast. Use `-D CAS_STACK_DIR=...` only if
your stack lives outside the bundled submodule. Do not reintroduce a link-mode
flag or a series-root build script into the documented build: a customer
downloads this repository on its own and must be able to build it with the two
commands above.

## Run

```bash
./build/BACnetExampleBLS [--port 47808] [--deviceID 389017]   # Linux/macOS
.\build\Release\BACnetExampleBLS.exe [--port 47808] [--deviceID 389017]   # Windows
```

Interactive keys: `h` help, `q` quit, up/down nudge Analog Input 1, `w` fire a
demo WriteGroup at Channel 1, `d` send a demo Who-Is to discover the remote
device. (`common/`'s `KeyCommand::DemoAdvance` / `'s'` is not wired to a `case`
in this `main.cpp`'s key-handling loop - pressing it is currently a no-op; the
Schedule's demo exception event fires on its own by wall clock regardless. See
[TUTORIAL.md](TUTORIAL.md#troubleshooting).)

## The stack pin is not optional here

This example **requires** a stack with the Channel/Schedule engine and the
Device_Address_Binding (DAB) resolver, present at the pinned commit
(`submodules/cas-bacnet-stack` @ `abd4cee1`, `6.x`, 6.0.21). It does **not**
register `RegisterCallbackChannelSendWritePropertyToRemote` or
`RegisterCallbackScheduleSendWritePropertyToRemote` - **verify before assuming
they exist**: at this pin they were removed (see the "Sprint 82" comment in
`submodules/cas-bacnet-stack/source/CASBACnetStackDLL.h`, just above the debug
message section) and replaced by the automatic DAB. Re-pinning forward past a
release that reintroduces or further changes this shape needs a re-read of
that comment, not an assumption this file is still accurate.

## Conventions

- Device is named "Rainbow"; objects use the series' colour names (Channel is
  "Garnet", Schedule "Saffron", Calendar "Cream", the seeded Lighting Output
  "Jade"); vendor id 389; device instance **389017**.
- Implement **only** what B-LS requires - DS-RP-B, DS-WP-A, DS-WP-B, DS-WG-E-B,
  DS-ALO-A, SCHED-E-B, DM-DDB-A/B, DM-DOB-B, DM-DCC-B, DM-TS-B/DM-UTC-B - but
  expose **every required property** of each object for Protocol_Revision 24.
- Do **not** add COV, alarms, trending, or backup/restore - a B-LS does not
  require them.
- **Every service number is verified against
  `submodules/cas-bacnet-stack/source/BACnetServicesSupported.h` at the pin**,
  never remembered or copied from a plan doc: readProperty=12, writeProperty=15,
  writeGroup=40, deviceCommunicationControl=17, timeSynchronization=32,
  utcTimeSynchronization=36.
- **Channel 1's WRITE dispatch is NOT the usual shape.** Every other
  commandable object in this file (Analog/Binary/Multi-State/Lighting Output)
  is written via `PROPERTY_IDENTIFIER_PRESENT_VALUE` + the callback's
  `priority` argument. A Channel's Present_Value write arrives on
  `PROPERTY_IDENTIFIER_PRIORITY_ARRAY` with `useArrayIndex=true` and the index
  AS the priority - see `BACnetStack_AddChannelObject`'s doc comment and the
  Channel-specific branches in `SetPropertyReal`/`SetPropertyNull`/`GetPropertyReal`.
  Copying the standard pattern for a new commandable object onto Channel
  silently never fires.
- `Channel_Number` and `Control_Groups` must be served (`GetPropertyUnsignedInteger`)
  and writable, or an incoming WriteGroup never matches this Channel at all -
  see the `BACnetStack_AddChannelObject` doc's "IMPORTANT" note.
- Calendar 1's `Date_List` is a genuine, documented gap (see [TODO.md](TODO.md)
  and stack issue [#2034](https://github.com/chipkin/cas-bacnet-stack/issues/2034)) -
  do not attempt to "fix" it by inventing a callback shape that does not exist;
  extend `TODO.md` instead if a future stack version adds one.
- **Never edit `common/` in this repo alone** - it is a vendored copy shared by
  every example, with its own version and changelog. To change it: edit, bump the
  version, add a changelog entry, then re-copy into every example repository.

## How to verify a change

There are no unit tests; verification is behavioural:

1. Build, then run one instance on a clear UDP port. If any `AddObject`,
   `AddChannelObject`, `AddScheduleObject`, or `SetPropertyWritable` call
   failed, the process exits non-zero.
2. With a BACnet client, **Who-Is** → confirm **I-Am** from device 389017.
3. **ReadProperty** every required property of every object; confirm
   `Protocol_Revision` is 24 and `Object_List` lists all twelve objects.
4. Run a second, separate `BACnetProfileExample-B-LD-CPP` instance on another
   port (that is `REMOTE_DEVICE_INSTANCE` in `main.cpp`). Press `'d'` then
   `'w'` in this example's console (or send the equivalent BACnet requests
   from an external client, since `_kbhit`/`_getch` read the real console, not
   an automated/piped stdin): confirm Lighting Output 1 (Jade) updates
   locally, and watch for a WriteProperty reaching the second instance.
5. Confirm the Schedule's demo exception event fires a few seconds after
   start-up and writes Channel 1 - this one is easy to observe without a
   second instance or an external client, and does not depend on the `'s'`
   key (see the Conventions note above).
6. Confirm services that are not enabled (e.g. ReadPropertyMultiple, SubscribeCOV)
   are rejected.
7. If you changed the objects or their properties, regenerate `docs/PICS.md`
   (`python tools/gen-objects-properties.py BACnetProfileExample-B-LS-CPP` from
   the series root) and confirm no row comes out flagged with ⚠. Check it is
   current with `... --check` before committing.

## Releasing

Bump `APP_VERSION` in `main.cpp` and add an entry to [CHANGELOG.md](CHANGELOG.md),
then tag `vX.Y.Z`. The GitHub Actions workflow builds and publishes the release.

## License

See [LICENSE](LICENSE). The CAS BACnet Stack is a separate, commercially
licensed product and is not covered by it.
