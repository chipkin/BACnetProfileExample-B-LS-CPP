# TODO

Defects this example cannot fix itself, and what is still open in it. A defect that
the Wire Tests see is reported as a `[KNOWN GAP]` line by
[`tests/channel_fanout_test.py`](tests/README.md): reported on every run, not counted
as a failure. When one prints `[GAP CLOSED]` instead, the defect is fixed upstream -
turn its check into a counted one and delete the entry here.

Checked at stack `6.x` @ `69b6249f` (6.0.23), 2026-10-27. Re-verify every entry
whenever the Stack Pin moves.

## 1. The default preset does not compile WriteGroup (worked around)

- **Where:** [chipkin/cas-bacnet-stack#3954](https://github.com/chipkin/cas-bacnet-stack/issues/3954).
- **What:** `CASBACnetStackOptions.h` says `STACK_OPTION_TARGET_FULL` "Enables ALL
  object types, ALL BIBBs/services", but `STACK_OPTION_WRITE_GROUP` is defined only by
  `STACK_OPTION_PROFILE_B_LS` and `BACNET_STACK_TESTTOOL`. Without it
  `BACnetStack_SetServiceEnabled(SERVICE_WRITE_GROUP)` fails (since stack #3031) and
  the example stops at start-up: `Error: Failed to enable the WriteGroup service.`
- **Done here:** `CMakeLists.txt` defines `STACK_OPTION_WRITE_GROUP` for the default
  SOURCE build. A prebuilt library must be built with it; the Windows STATIC library
  used for the Wire Tests was built with `CL=-DSTACK_OPTION_WRITE_GROUP
  tools/build-stack-static.sh BACnetProfileExample-B-LS-CPP` (`-D`, not `/D`: Git Bash
  rewrites `/D...` into a path).

## 2. A Channel's Present_Value write reaches the application in two shapes (worked around)

- **Where:** [chipkin/cas-bacnet-stack#3955](https://github.com/chipkin/cas-bacnet-stack/issues/3955).
- **What:** `BACnetStack_AddChannelObject`'s doc says the Set callbacks for a Channel's
  Present_Value are called with `propertyIdentifier = PriorityArray`, array index
  1..16. A client WriteProperty, an incoming WriteGroup and (now that Schedule 1
  references Present_Value) the Schedule all arrive as `Present_Value (85)` with the
  `priority` argument instead.
- **Done here:** `SetPropertyReal` and `SetPropertyNull` accept both shapes.

## 3. A member write the stack refuses to send reaches no hook (worked around)

- **Where:** [chipkin/cas-bacnet-stack#4603](https://github.com/chipkin/cas-bacnet-stack/issues/4603).
- **What:** under DeviceCommunicationControl DISABLE_INITIATION the stack drops the
  Channel's WriteProperty to device 389016 (correctly, cl. 16.1) but calls no SimpleACK
  / Error / Reject / Abort / Timeout hook for it, so an application that keeps
  `Write_Status` from those hooks never sees the write end.
- **Done here:** the DeviceCommunicationControl callback records DISABLE_INITIATION and
  its duration; `BeginChannelFanOut` fails the remote member at once while it holds
  (`main.cpp` section 2e). `tests/channel_fanout_test.py` section 7.

## Fixed upstream

- **A WriteProperty or a Schedule write to a Channel is propagated to its members**
  ([chipkin/cas-bacnet-stack#3956](https://github.com/chipkin/cas-bacnet-stack/issues/3956),
  fixed by the `6.x` @ `4238a39f` Stack Pin). 135-2024 cl. 12.53.5: "When
  Present_Value is written, the Channel object shall propagate that value to each of
  the members". Schedule 1's write and a client's WriteProperty now reach Jade and
  device 389016 like a WriteGroup; `Write_Status` follows every one of them
  (`main.cpp` section 2e), and the Wire Test's former `[KNOWN GAP]` lines are counted
  checks. Schedule 1's start-up write cannot reach device 389016: it is made on the
  first tick, before 389016's I-Am binds it, and the stack skips a member it cannot
  address, so `Write_Status` reads FAILED until the next write that reaches both
  members.
- **Error Code BUSY goes out with Error Class OBJECT**
  ([#3088](https://github.com/chipkin/cas-bacnet-stack/issues/3088) item CR2-F01-031,
  fixed by the same pin; cl. 12.53.5, cl. 18.2). A counted check now.

## Fixed here

- **The stack's Who-Is for device 389016 now reaches the subnet** (`common/` 3.4.0).
  The Device_Address_Binding sends its Who-Is with `broadcast = true` and an address
  copied from the last I-Am it heard - this device's own start-up I-Am, looped back -
  and `common/` up to 3.3.0 sent it unicast to this host
  (`TX 20 bytes to 192.168.3.64:47834 (broadcast) ... Who-Is`). 3.4.0 sends a
  broadcast addressed to its own socket to the subnet broadcast
  (`TX 20 bytes to 192.168.3.255:47821 (broadcast) ... Who-Is DNET=65535`). Now a
  counted check. The stack side - the undocumented meaning of `broadcast`, and the
  BBMD's two-hop re-broadcast - is still
  [chipkin/cas-bacnet-stack#3933](https://github.com/chipkin/cas-bacnet-stack/issues/3933).
- **Schedule 1 wrote Channel 1's `Priority_Array`**, a property a Channel does not have
  (Table 12-62). It references `Present_Value` now, written at Priority_For_Writing 12.
- **Write_Status was a constant `1`** (which is IN_PROGRESS, not SUCCESSFUL as the old
  comment said; source/BACnetWriteStatus.h: idle 0, inProgress 1, successful 2,
  failed 3). It is IDLE until the first write to Channel 1 and follows each fan-out (main.cpp
  section 2e).
- **Last_Priority started at 0**; cl. 12.53.6 says 16.

## Open, not stack-owned

- **Reliability is not served.** It is optional on a Channel (Table 12-62). cl. 12.53.9
  says that after a FAILED fan-out it should say why (COMMUNICATION_FAILURE for the
  offline member). Write_Status (required) carries the failure today.
- **A Null written through the Channel** (relinquish) that a member answers with
  INVALID_DATATYPE "shall not be treated as a FAILED value" (cl. 12.53.7). The example
  counts any Error as a failure; no member here answers a Null that way.
- **Overlapping WriteGroups.** Write_Status follows the remote answers by count: a
  second WriteGroup sent while the first is still waiting for the remote member takes
  over the pending answer. The clause says nothing about a WriteGroup during
  IN_PROGRESS (only WriteProperty is refused with BUSY).
- **A Schedule write during IN_PROGRESS is refused too.** The Set callback cannot tell
  Schedule 1's write from a client's WriteProperty (both arrive as Present_Value with
  a priority), so a Schedule transition that lands while a fan-out waits for the
  remote member (up to 40 s) gets the same BUSY refusal (not checked whether the
  stack's Schedule engine writes it again later). Rare (09:00 / 17:00).
- **`'s'` does nothing**: `main()` has no `case` for `KeyCommand::DemoAdvance`.
- **Calendar 1 ("Cream")** is added with plain `BACnetStack_AddObject`, so its
  `Date_List` is empty and `Present_Value` is `false`. Stack #2034 and #963 are closed:
  `BACnetStack_AddCalendarObject` now holds a Date_List and a Schedule exception can
  reference a stack-held Calendar. Not adopted yet.
- **Spec text to check (not a defect here):** the extracted 135-2024 cl. 21 ASN.1 reads
  `BACnetGroupChannelValue ::= SEQUENCE { channel [0] Unsigned16, value [1]
  BACnetChannelValue, overriding-priority [2] ... OPTIONAL }`, while cl. 15.11.1.1.3's
  prose names "(channel number, overridingPriority, value)" tuples and the stack (and
  `wiretest/codec.py` `write_group_request`) encode channel [0], overriding-priority [1], then the
  untagged value. Needs a look at the printed standard.

## Conformance rows that stay open (customers quoting support)

- **Channel 1's `Last_Priority` reads 12 where a BTL script expects 16.** Schedule 1
  writes Channel 1 at Priority_For_Writing 12, so `Last_Priority` reads 12 after a
  Schedule write; the BTL test 7.3.2.34.1 verifies 16 after its own WriteGroup. The
  test result is treated as a script limit, not an example defect.
  (ref: `chipkin/chipkin-bacnet-testing-tool#692`)
- **Schedule and Calendar scenarios that need the test harness to configure the
  Schedule are not run** (SCHED-E-B). (ref: `chipkin/chipkin-bacnet-testing-tool#595`)
- **IUT-initiated WriteProperty tests (DS-WP-A, DS-ALO-A) are not run**: they need
  a test harness that plays the remote device. (ref: `chipkin/chipkin-bacnet-testing-tool#691`)
- **DM-DCC-B disable-initiation checks are skipped**; this device initiates the
  Channel's WriteProperty. (ref: `chipkin/chipkin-bacnet-testing-tool#355`)
