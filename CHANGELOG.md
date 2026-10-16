# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - unreleased

The example now performs the B-LS Profile Function - Channel 1 forwards a
WriteGroup to its own Lighting Output and to another device's - and proves it,
and its Failure Modes, with Wire Tests (the series' Profile-functional bar,
`docs/GLOSSARY.md` in the example series).

### Added

- **`Write_Status` follows the fan-out** (cl. 12.53.5, 12.53.7; `main.cpp`
  section 2e). It is IDLE at start-up, IN_PROGRESS while the stack writes the
  members, then SUCCESSFUL, or FAILED when a member refuses (Error, Reject,
  Abort), never answers (the stack's Timeout hook, after APDU_Timeout), or cannot
  be addressed (no I-Am yet). The application learns the remote result through
  `BACnetStack_RegisterHookSimpleAck` / `Error` / `Reject` / `Abort` / `Timeout`,
  matched by the address `BACnetStack_RegisterHookIAm` recorded for device 389016.
  The console prints each step.
- **BUSY.** A WriteProperty of Channel 1 `Present_Value` while `Write_Status` is
  IN_PROGRESS is refused with Error Code BUSY (cl. 12.53.5). The stack sends it as
  class PROPERTY, not OBJECT (stack defect, TODO.md).
- **Wire Tests** `tests/channel_fanout_test.py`: a Python Peer plays device 389016.
  The stack's Who-Is reaches it (Linux), it is bound, and one WriteGroup reaches
  both Jade and the Peer, with `Write_Status` SUCCESSFUL. Failure Modes: the Peer
  offline (IN_PROGRESS, BUSY, then FAILED after the timeout, then recovery), the
  Peer refusing the write, Jade refusing 150 %. The stack defects are
  `[KNOWN GAP]` lines. Each check verified to fail with its feature removed
  (`tests/README.md`). Generic helpers for the harness in
  `tests/wiretest_extras.py` (WriteGroup encoding, WriteProperty parsing,
  `CommandablePeer`), kept separate for `wiretest/` 0.6.0.

### Changed

- **`common/` 3.3.0 -> 3.4.0**, copied verbatim from B-SS-CPP branch
  `common-3.4.0-broadcast-to-self`: a broadcast the stack addresses to this
  socket's own address goes to the subnet broadcast. The stack's
  Device_Address_Binding Who-Is for device 389016 used to go to this host only
  (stack #3933), so the remote member was never found.
- APP_VERSION 1.1.0 -> 1.2.0. README rewritten around the scenario (with the
  Profile Function quoted from Annex L.11.1 and what is Simulation), TUTORIAL
  gains "Write_Status: following the fan-out to its end", PICS and TODO.md
  updated.

### Fixed

- **Schedule 1 wrote Channel 1's `Priority_Array`**, a property a Channel does not
  have (Table 12-62). It references `Present_Value` now, written at
  Priority_For_Writing 12.
- **`Write_Status` read as a constant `1`** - IN_PROGRESS, though the comment
  called it "successful" (BACnetWriteStatus: idle 0, in-progress 1, successful 2,
  failed 3).
- **`Last_Priority` started at 0**, not a priority; cl. 12.53.6 says 16.
- The header comment cited "Annex L.12" for B-LS; it is L.11.1.

## [1.1.0] - unreleased

### Changed

- **Stack Pin moves to `6.x` @ `64b2cfac5` (6.0.23)** from `6.x` @ `abd4cee1`
  (6.0.21), per the series rule that a pin moves to the latest `6.x` whenever an
  example is updated.
- **The build compiles WriteGroup into the stack.** The stack's default preset
  (`STACK_OPTION_TARGET_FULL`) leaves WriteGroup out, and since stack #3031
  `BACnetStack_SetServiceEnabled(SERVICE_WRITE_GROUP)` fails on such a build, so
  the example stopped at start-up. `CMakeLists.txt` now defines
  `STACK_OPTION_WRITE_GROUP` for the default SOURCE build; README "Build" says to
  build a prebuilt STATIC/DLL stack library with it. (At `abd4cee1` the default
  build accepted the enable call but had no WriteGroup in it, so the `'w'` demo
  and DS-WG-E-B never worked in that build.)
- **Protocol_Revision 24 -> 30** (the stack's default at the new pin).
- **Segmentation is now supported** (`segmented-both`), by the stack (stack
  #2992). `docs/PICS.md` section 5 updated and the objects block regenerated.
- **`common/` 3.0.0 -> 3.3.0**, copied verbatim from B-SS-CPP `b640a81`.
- README, TUTORIAL, AGENTS.md and PICS version lines: stack 6.0.23, `common/`
  3.3.0, Protocol_Revision 30. README profile table re-synced. APP_VERSION
  1.0.2 -> 1.1.0.

### Fixed

- **WriteProperty and WriteGroup to Channel 1 failed.** At this pin the stack
  hands a client WriteProperty and an incoming WriteGroup to `SetPropertyReal` /
  `SetPropertyNull` on Present_Value with a priority, not on Priority_Array with
  an index as `BACnetStack_AddChannelObject`'s doc says (the stack's Schedule
  still uses the documented shape). The example refused the undocumented shape,
  so both failed (WriteProperty: Error property / write-access-denied). Both
  shapes are now accepted. Result on Linux: the `'w'` WriteGroup moves Jade from
  0 % to 100 %. Recorded as a stack defect in TODO.md.
- **The docs no longer claim what the example does not do:**
  - the Schedule does **not** drive the Channel's fan-out: it writes Channel 1's
    Present_Value, which the stack stores but does not propagate to the members
    (135-2024 cl. 12.53.5 says it should; stack defect, TODO.md). README intro,
    BIBB table (SCHED-E-B), object table, TUTORIAL, PICS and `docs/objects.json`
    corrected;
  - the demo exception event is for today from 00:00:05, so it is in effect
    from start-up, not "a few seconds after start-up" (README, TUTORIAL,
    AGENTS.md, PICS, the `main.cpp` comment and the start-up banner);
  - the banner no longer says to press `'s'`, which does nothing here;
  - DS-WP-A and DS-ALO-A: `main.cpp` never sends a WriteProperty; the `'w'`/`'d'`
    keys send a WriteGroup and a Who-Is. The WriteProperty to the remote device
    is the stack's, from the Channel, and has not been seen on the wire yet;
  - the remote fan-out is described as unverified, with the reason (the
    binding Who-Is goes to this host's own address: the `common/` broadcast
    defect, stack #3933).
- TODO.md: #2034 and #963 are closed upstream and removed as blockers; the
  stack defects found at this pin are recorded with their evidence.

### Added

- **Wire Tests** (`tests/`, README "Wire Tests"): `tests/discovery_test.py`, the
  series' discovery test from B-SS-CPP `da3e96f` with this example's twelve
  objects as its control. CI runs it on Linux after the smoke test. Result:
  18/18 on Windows (STATIC) and Linux (SOURCE), 173 reads, all values.
- `wiretest/` 0.5.0, the series' shared Wiretest Harness, vendored verbatim from
  B-BBMD-CPP `75aedd8`.

## [1.0.2] - unreleased

### Changed

- **Device renamed from the series' colour placeholder "Rainbow" to "Chipkin
  Example B-LS"** so devices from different examples in the series are
  distinguishable from each other on the same BACnet network - every example
  previously announced the identical Object_Name "Rainbow", which made two
  examples on one subnet indistinguishable by name. Sub-object names (Analog
  Input 1 "Bronze", etc.) are unchanged - only the Device object's name
  changed. `docs/colour-table.md` (series root) updated to match. APP_VERSION
  bumped 1.0.1 -> 1.0.2.

## [Unreleased]

### Changed

- **Documentation restructure.** `README.md` is cut down to this example only
  (series-framing, the generic profile explanation, the "Before you ship"
  table, "Get the code", "Link mode", "Troubleshooting", "Extending the
  example", and the "Objects and properties" block moved or removed); the
  long-form material moved to a new `TUTORIAL.md`, and the conformance
  statement moved to a new `docs/PICS.md` (ANSI/ASHRAE 135 Annex A shape),
  regenerated from `docs/objects.json` with a new Device object entry and
  zero ⚠ rows. The per-field "Before you ship" guidance is now inline
  comments in `main.cpp`'s `CHANGE ALL OF THIS BEFORE YOU SHIP` block.
- **Build switched from a prebuilt STATIC library to the adapter's default
  SOURCE mode.** `cmake -B build -S . && cmake --build build --config Release`
  is now the full, single-command build on every platform - no
  `tools/build-stack-static.sh` pre-step. `.github/workflows/release.yml`
  drops the static-library cache/build steps and the matrix `lib:` entries,
  asserts `CAS_BACNET_STACK_LINK=SOURCE`, and packages `TUTORIAL.md` and
  `docs/PICS.md` alongside the binary. The published Footprint numbers are
  still from the STATIC-linked v1.0.0 release; the next release refreshes
  them from the SOURCE build.
- Confirmed the `'s'` (`DemoAdvance`) interactive key is not wired to a `case`
  in this example's key-handling loop, even though the start-up banner and
  earlier documentation said to press it - documented as a known gap in
  `TUTORIAL.md` and `AGENTS.md` rather than carried forward as fact. The
  Schedule's demo exception event fires on its own regardless.

## [1.0.1] - unreleased

### Fixed

- **`Application_Software_Version` (12) and `Firmware_Revision` (44) were
  hardcoded and stale.** Both were separate `static const char*` constants
  set to a literal `"1.0.0"` that nobody would ever update as the example
  moved past that release. Fixed: `Application_Software_Version` now reads
  `APP_VERSION` directly (one source of truth, can't drift from `--version`'s
  own banner again). `Firmware_Revision` is now built at runtime from the CAS
  BACnet Stack's own `BACnetStack_GetAPIMajorVersion()`/`GetAPIMinorVersion()`/
  `GetAPIPatchVersion()`/`GetAPIBuildVersion()` (the same 4 calls
  `common/CASExampleHelper.cpp`'s `PrintVersion()` already uses for the
  startup banner), populated once into `g_firmwareRevision` right after
  `LoadBACnetFunctions()` succeeds. The old separate `FIRMWARE_REVISION` /
  `APPLICATION_SOFTWARE_VERSION` constants are removed entirely. Verified
  with a clean build plus a real ReadProperty against the running device
  (via `bacpypes3`, port 47825, device instance 389017):
  `Application_Software_Version = "1.0.1"`, `Firmware_Revision = "6.0.21.0"`
  - both now match the actual running build instead of a stale hardcoded
  string.

## [1.0.0] - unreleased

### Added

First implementation of this example (previously a plan-only repository). Seeded
from `BACnetProfileExample-B-LD-CPP` (base objects + Lighting Output "Jade"),
`common/` synced verbatim from `BACnetProfileExample-B-SS-CPP` at 2.5.0, CAS
BACnet Stack pinned to `6.x` @ `abd4cee1` (reports 6.0.21), linked as a
prebuilt **STATIC** library.

- **B-LS (Lighting Supervisor) profile.** DS-RP-B, DS-WP-A, DS-WP-B, DS-WG-E-B,
  DS-ALO-A, SCHED-E-B, DM-DDB-A/B, DM-DOB-B, DM-DCC-B, DM-TS-B/DM-UTC-B.
  Services verified against `source/BACnetServicesSupported.h` at the pin:
  readProperty (12), writeProperty (15), writeGroup (40),
  deviceCommunicationControl (17), timeSynchronization (32),
  utcTimeSynchronization (36).
- **Channel 1 "Garnet" (F-CHANNEL, canonical).** `AddChannelObject` (REAL
  Present_Value), `AddObjectPropertyReferenceToChannel` for one local
  reference (Lighting Output 1 "Jade") and one remote reference
  (F-EXTWRITE, canonical - device 389016's Lighting Output, via
  `refUseDeviceIdentifier=true`). `Channel_Number` / `Control_Groups` served
  and writable, required so an incoming WriteGroup can match this Channel.
  `RegisterCallbackWriteGroupInhibitDelay` registered.
- **Schedule 1 "Saffron" / Calendar 1 "Cream" (F-SCHED-E, canonical).**
  `AddScheduleObject`, `AddScheduleWeeklyTimeValue` (09:00 on / 17:00 off
  daily), `SetScheduleDefault`, `SetScheduleEffectivePeriod`,
  `SetSchedulePriorityForWriting`, `AddScheduleObjectPropertyReference`
  pointing at Channel 1, plus a one-off demo exception event via
  `AddScheduleExceptionEventWithCalendarEntry`. Calendar 1 exists as a real,
  independently-readable object; its `Date_List` is a documented gap (see
  `TODO.md` and [chipkin/cas-bacnet-stack#2034](https://github.com/chipkin/cas-bacnet-stack/issues/2034)).
- **New interactive demo keys, claimed in `common/` 2.5.0 and
  `docs/menu-keys.md`:** `w` (`WriteGroupDemo`) fires a real
  `BACnetStack_SendWriteGroup` at Channel 1's control group; `d`
  (`DiscoverRemote`) sends a demo `BACnetStack_SendWhoIs` so the stack's
  Device_Address_Binding can resolve the remote device's address.

### Documented gap

- **The remote-write callbacks named in this profile's original design brief
  do not exist at this pin.** `RegisterCallbackChannelSendWritePropertyToRemote`
  and `RegisterCallbackScheduleSendWritePropertyToRemote` were removed
  ("Sprint 82" in `source/CASBACnetStackDLL.h`); the stack now performs the
  remote write itself via its internal Device_Address_Binding once a
  reference names `refUseDeviceIdentifier=true`. This example registers
  neither removed callback and documents the replacement mechanism in
  `main.cpp`'s header comment and the README.

Verified: builds STATIC and boots clean (`CAS BACnet Stack version: 6.0.21.0`,
`Common helper (common/) version: 2.5.0`). The Schedule's demo exception event
fires spontaneously and is observed writing Channel 1's Priority_Array. A
second, separately-running `BACnetProfileExample-B-LD-CPP` instance exchanged
broadcast I-Am traffic with this device. The `'w'`/`'d'` interactive demo and
the cross-device WriteGroup/DAB fan-out were exercised via the implemented
code paths but not independently confirmed with a live two-instance capture in
this pass - see the README's "Try it" verification note.
