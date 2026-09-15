# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
