# TODO

Defects this example cannot fix itself, and what is still open in it. A defect that
the Wire Tests see is reported as a `[KNOWN GAP]` line by
[`tests/channel_fanout_test.py`](tests/README.md): reported on every run, not counted
as a failure. When one prints `[GAP CLOSED]` instead, the defect is fixed upstream -
turn its check into a counted one and delete the entry here.

Checked at stack `6.x` @ `64b2cfac5` (6.0.23), 2026-10-15. Re-verify every entry
whenever the Stack Pin moves.

## 1. A WriteProperty or a Schedule write to a Channel is not propagated to its members

- **Where:** the CAS BACnet Stack -
  [chipkin/cas-bacnet-stack#3956](https://github.com/chipkin/cas-bacnet-stack/issues/3956).
- **What:** 135-2024 cl. 12.53.5: "When Present_Value is written, the Channel object
  shall propagate that value to each of the members in the
  List_Of_Object_Property_References except those members containing an empty
  reference." The stack propagates only from its WriteGroup processor. A client's
  WriteProperty of Channel 1 Present_Value = 42.0 @ 9 is answered SimpleACK and
  Channel 1 holds it, but neither Jade nor device 389016 is written. Schedule 1's
  write (100.0 @ 12, at start-up) stops at Channel 1 the same way.
- **Effect here:** the WriteGroup fan-out - the Profile Function - works. L.11.1's
  "Ability to schedule output actions, both in the local device and in other devices"
  cannot go through the Channel: the Schedule drives Channel 1 and nothing further.
  Write_Status is left as it was after such a write, because nothing was forwarded.
- **Wire Test:** four `[KNOWN GAP]` lines - "Schedule 1's write to Channel 1 reaches
  Jade (100.0)", "... reaches device 389016 (100.0 @ 12)", "WriteProperty to Channel 1
  (42.0 @ 9) reaches Jade's Priority_Array[9]", "... reaches device 389016".

## 2. Error Code BUSY goes out with Error Class PROPERTY, not OBJECT

- **Where:** the CAS BACnet Stack (stack defect, not filed).
  `source/BACnetBusinessLogic.cpp` `GetErrorClassForCallbackErrorCode()`: a Set
  callback can only name an error code, and the stack picks the class; `busy` (82)
  falls to `default: return BACnetErrorClass::property`.
- **What:** 135-2024 cl. 12.53.5: "Attempts to write to Present_Value using
  WriteProperty service when Write_Status is IN_PROGRESS shall cause a Result(-) to be
  returned with an 'Error Class' of OBJECT and an 'Error Code' of BUSY." Cl. 18.2
  ("Error Class - OBJECT") lists BUSY. `SetPropertyReal` / `SetPropertyNull` refuse the
  write with `ERROR_CODE_BUSY`; the wire shows `Error class=2 code=82`.
- **Effect here:** the write is refused while a fan-out is in progress, as the clause
  requires; only the class a client sees is wrong.
- **Wire Test:** `[KNOWN GAP] ... and with Error Class OBJECT (cl. 12.53.5; BUSY is an
  OBJECT code, cl. 18.2)`. The code itself is a counted check.

## 3. The default preset does not compile WriteGroup (worked around)

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

## 4. A Channel's Present_Value write reaches the application in two shapes (worked around)

- **Where:** [chipkin/cas-bacnet-stack#3955](https://github.com/chipkin/cas-bacnet-stack/issues/3955).
- **What:** `BACnetStack_AddChannelObject`'s doc says the Set callbacks for a Channel's
  Present_Value are called with `propertyIdentifier = PriorityArray`, array index
  1..16. A client WriteProperty, an incoming WriteGroup and (now that Schedule 1
  references Present_Value) the Schedule all arrive as `Present_Value (85)` with the
  `priority` argument instead.
- **Done here:** `SetPropertyReal` and `SetPropertyNull` accept both shapes.

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
  failed 3). It is IDLE at start-up and follows each fan-out (main.cpp section 2e).
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
  remote member (up to 10 s) gets the same BUSY refusal (not checked whether the
  stack's Schedule engine writes it again later). Rare (09:00 / 17:00), and moot while the stack does not forward a
  Schedule write anyway (1).
- **`'s'` does nothing**: `main()` has no `case` for `KeyCommand::DemoAdvance`.
- **Calendar 1 ("Cream")** is added with plain `BACnetStack_AddObject`, so its
  `Date_List` is empty and `Present_Value` is `false`. Stack #2034 and #963 are closed:
  `BACnetStack_AddCalendarObject` now holds a Date_List and a Schedule exception can
  reference a stack-held Calendar. Not adopted yet.
- **Spec text to check (not a defect here):** the extracted 135-2024 cl. 21 ASN.1 reads
  `BACnetGroupChannelValue ::= SEQUENCE { channel [0] Unsigned16, value [1]
  BACnetChannelValue, overriding-priority [2] ... OPTIONAL }`, while cl. 15.11.1.1.3's
  prose names "(channel number, overridingPriority, value)" tuples and the stack (and
  `tests/wiretest_extras.py`) encode channel [0], overriding-priority [1], then the
  untagged value. Needs a look at the printed standard.
