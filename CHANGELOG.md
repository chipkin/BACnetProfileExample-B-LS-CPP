# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_No changes yet._

## [1.3.0] - 2026-10-27

Built on CAS BACnet Stack 6.x (`69b6249f`).

### Added

- **`--deviceName <text>`** sets the Device's Object_Name at start-up, like
  `--deviceID` sets its instance (ASHRAE 135-2024 cl. 12.1.1.3 and 12.1.1.4).
  Object_Name must be unique on the internetwork, so two units can now be
  installed together. The default is unchanged (`Chipkin Example B-LS`); a name
  must be 1 to 255 bytes with no control characters, otherwise a warning is
  printed and the default is kept. A WriteProperty of the Device's Object_Name
  is refused.
- **`--xml`** prints each received and sent frame as an XML block.
- **Lighting Output 1 carries out its `Lighting_Command` operations**
  (cl. 12.54, Table 12-67): fade and ramp take their time with `Tracking_Value`
  moving and `In_Progress` set; the step, warn, stop, restore-on, default-on and
  toggle operations follow the table; a write at an equal or higher priority
  halts a command in progress; the `Present_Value` special values -1.0 to -7.0
  run their commands. `Last_On_Value` and `Default_On_Value` (100.0) are served,
  and `Default_Fade_Time`, `Default_Ramp_Rate`, `Default_Step_Increment` and
  `Egress_Time` are writable and range-checked. Channel 1's writes to the
  Lighting Output use the same engine.
- **Automated self-tests** under `tests/` for the command line, fades, ramps and
  steps, stop and priority, warn, and refused commands.

### Changed

- **`Write_Status` on Channel 1 follows every write it forwards**, not only a
  WriteGroup: a WriteProperty to Channel 1 and Schedule 1's write now reach both
  members (Lighting Output 1 and device 389016). Because the Schedule writes
  before device 389016 has answered a Who-Is, `Write_Status` reads FAILED after
  start-up until the next write that reaches both members.
- **`--help` lists only the options the example reads.** It no longer lists
  `--dcc-password`; the DeviceCommunicationControl password is the
  `DCC_PASSWORD` constant in `main.cpp`.
- **Test scripts** under `tests/` default to this example's own port, 47840.
- Vendored `common/` updated to 3.5.0 and `wiretest/` to 0.7.0; see
  `common/CHANGELOG.md`.
- **Documentation**: PICS lists I-Am as executed as well as initiated
  (DM-DDB-A), documents Database_Revision as 12, and lists the Lighting
  Output's `Last_On_Value`, `Default_On_Value`, `Current_Command_Priority` and
  `Property_List`.

### Fixed

- **Channel 1 no longer stays busy after DeviceCommunicationControl disables
  initiation.** Previously `Write_Status` stayed IN_PROGRESS and every later
  WriteProperty to Channel 1 was refused with BUSY, even after initiation was
  re-enabled. The remote member now fails at once while initiation is disabled
  (cl. 12.53.7, 16.1).
- **The Device's Description** read as an empty string because it was too long
  for the stack to hold; it is now shorter and reads correctly.
- **Requests no longer go unanswered on Windows**: a request arriving just as a
  receive timed out could be silently discarded (vendored `common/` 3.4.1).

## [1.2.0] - 2026-10-16

Built on CAS BACnet Stack 6.x (`64b2cfac5`, 6.0.23).

The example now performs the B-LS Profile Function (ANSI/ASHRAE 135-2024 Annex
L.11.1): Channel 1 forwards a WriteGroup to its own Lighting Output and to
another device's. This release also rolls up the earlier 1.0.1 through 1.1.0
work, which was never released separately.

### Added

- **`Write_Status` follows the fan-out** (cl. 12.53.5, 12.53.7): IDLE at
  start-up, IN_PROGRESS while the members are written, then SUCCESSFUL, or
  FAILED if a member refuses, never answers, or cannot be addressed. A
  WriteProperty of Channel 1 `Present_Value` while a write is in progress is
  refused with BUSY.
- **Automated self-tests** under `tests/`: object discovery and a Channel 1
  fan-out test with a simulated remote device, covering an offline member, a
  member that refuses, and a refused out-of-range value.

### Changed

- **Segmentation is supported** (`segmented-both`); `docs/PICS.md` updated.
- **Protocol_Revision** is 30.
- **The build compiles WriteGroup into the stack.** `CMakeLists.txt` defines
  `STACK_OPTION_WRITE_GROUP`; without it the example stopped at start-up. When
  building a prebuilt stack library, build it with this option.
- **Device renamed** from "Rainbow" to "Chipkin Example B-LS" so examples from
  this series can be told apart on one network.
- **Build** uses the stack's source mode by default
  (`cmake -B build -S .` then `cmake --build build --config Release`); no
  prebuilt static library step is needed.
- **Documentation** restructured into README, `TUTORIAL.md` and `docs/PICS.md`;
  the README is built around the scenario and quotes the Profile Function.
- Vendored `common/` updated to 3.4.0 (a broadcast addressed to the socket's
  own address now goes to the subnet broadcast, so the remote member is found).
- Application_Software_Version is 1.2.0.

### Fixed

- **WriteProperty and WriteGroup to Channel 1 failed**; both now work, and a
  WriteGroup moves Lighting Output 1 from 0 % to 100 %.
- **Schedule 1 wrote Channel 1's `Priority_Array`**, which a Channel does not
  have; it now references `Present_Value` at Priority_For_Writing 12.
- **`Write_Status`** read as a constant 1 (IN_PROGRESS); **`Last_Priority`**
  started at 0 instead of 16 (cl. 12.53.6).
- **`Application_Software_Version` and `Firmware_Revision`** were hard-coded
  and stale; they now follow the example and stack versions.
- **Documentation** no longer claims behaviour the example does not have (for
  example the Schedule's demo exception event is in effect from start-up).

## [1.0.0] - 2026-09-15

Built on CAS BACnet Stack 6.x (`abd4cee1`, 6.0.21).

### Added

- **Initial B-LS (Lighting Supervisor) example**: DS-RP-B, DS-WP-A, DS-WP-B,
  DS-WG-E-B, DS-ALO-A, SCHED-E-B, DM-DDB-A/B, DM-DOB-B, DM-DCC-B and
  DM-TS-B / DM-UTC-B.
- **Channel 1** with a local reference (Lighting Output 1) and a remote
  reference (device 389016's Lighting Output).
- **Schedule 1 and Calendar 1**: a daily 09:00 on / 17:00 off schedule that
  writes Channel 1, plus a one-off demo exception event.
- **Demo keys**: `w` sends a WriteGroup to Channel 1's control group; `d`
  sends a Who-Is so the remote device can be found.
- Known gap: Calendar 1's `Date_List` is not yet served.
