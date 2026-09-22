# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
