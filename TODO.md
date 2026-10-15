# TODO - gaps against the customer-facing API at the pin

Per the series rule: a required property, BIBB or Profile Function step the public API
cannot do is named here, not faked. Re-verify every entry whenever the Stack Pin moves.
Checked at stack `6.x` @ `64b2cfac5` (6.0.23), 2026-10-15.

## Stack defects found at 64b2cfac5 (filed)

These were found while moving the pin and filed after verification:
1 is [#3954](https://github.com/chipkin/cas-bacnet-stack/issues/3954), 2 is [#3955](https://github.com/chipkin/cas-bacnet-stack/issues/3955), 3 is [#3956](https://github.com/chipkin/cas-bacnet-stack/issues/3956).

Verification also showed that this example's Schedule writes the Channel's
`Priority_Array`, a property a Channel does not have. It should write `Present_Value`.
That is this example's own phase-2 work.

### 1. The default preset does not compile WriteGroup

`CASBACnetStackOptions.h` says `STACK_OPTION_TARGET_FULL` "Enables ALL object types, ALL
BIBBs/services", but `STACK_OPTION_WRITE_GROUP` is defined only by
`STACK_OPTION_PROFILE_B_LS` and by `BACNET_STACK_TESTTOOL`, not by
`STACK_OPTION_ENABLE_ALL_BIBBS`. `BACnetInterface::SendWriteGroup` and the WriteGroup
processor are inside `#ifdef STACK_OPTION_WRITE_GROUP`, so a TARGET_FULL customer build
can neither send nor execute WriteGroup (the same was true at `abd4cee1`).

Since stack #3031 (`c00d0cc3`), `BACnetStack_SetServiceEnabled` refuses a service the build
does not execute, so with the series' standard STATIC library this example stopped at
start-up:

```
::CASBACnetStack::BACnetInterface::SetServiceEnabled() ... - Error: service=[40] is not
executed by this build of the CAS BACnet Stack ...
Error: Failed to enable the WriteGroup service.
```

**Done here:** `CMakeLists.txt` defines `STACK_OPTION_WRITE_GROUP` for the default SOURCE
build; README "Build" says to build a prebuilt library with it. The Windows STATIC check
used a library built with `CL=-DSTACK_OPTION_WRITE_GROUP`.

### 2. A Channel's Present_Value write reaches the application on two different shapes

`BACnetStack_AddChannelObject`'s doc comment (`CASBACnetStackDLL.h`) says the Set callbacks
for a Channel's Present_Value "are called with propertyIdentifier = PriorityArray,
useArrayIndex = true, index 1..16". The stack's Schedule writes it that way. A client
WriteProperty and an incoming WriteGroup call `SetPropertyReal` with
`propertyIdentifier = Present_Value (85)` and the `priority` argument instead. Traced with a
printf at the top of `SetPropertyReal`:

```
DBG SetPropertyReal type=53 inst=1 prop=87     <- the Schedule's write (start-up)
RX ... ConfirmedRequest: WriteProperty Channel 1.Present_Value
DBG SetPropertyReal type=53 inst=1 prop=85     <- the client's WriteProperty
```

Following the doc, the example refused the second shape; the stack then falls back to its
own value store, which holds nothing for a Channel, and fails:

```
::SetStoredDBValue() ... - Error: Object does not have values stored in the stack memory
::Process() in file: .../BACnetWritePropertyProcessor.cpp(172) - Error: ...
TX ... Error: WriteProperty                      (class property, code write-access-denied)
::Process() in file: .../BACnetWriteGroupProcessor.cpp(284) - Error: WriteGroup: failed to
set Present_Value for Channel instance=[1] (channelNumber=[1]) at priority=[8]
```

So no WriteProperty and no WriteGroup to Channel 1 worked. Not checked at `abd4cee1`
(WriteGroup was not compiled there anyway, see 1).

**Done here:** `SetPropertyReal` and `SetPropertyNull` accept both shapes. After that, a
client WriteProperty to Channel 1 is accepted, and a WriteGroup (the `'w'` key, Linux) moves
Jade from 0 % to 100 %.

### 3. A WriteProperty or Schedule write to a Channel is not propagated to its members

135-2024 cl. 12.53.5: "When Present_Value is written, the Channel object shall propagate that
value to each of the members in the List_Of_Object_Property_References except those members
containing an empty reference." The stack fans out only from the WriteGroup processor. With
fix 2 in place, WriteProperty Channel 1 Present_Value = 42.0 @ priority 8 returns SimpleACK
and Channel 1 reads 42.0, but Lighting Output 1 (a member) stays at 0.0. The Schedule's
start-up write (100 @ priority 12) does not reach Jade either.

Effect on the Profile Function: "Ability to schedule output actions, both in the local device
and in other devices" (L.11.1) cannot go through the Channel. Phase 2 can point the Schedule
at the members directly instead, or wait for the stack fix. The README says this plainly.

## Open, not stack-owned

- **The remote fan-out has not been seen.** Channel 1's remote reference (device 389016,
  Lighting Output 1) is resolved by the stack's Device_Address_Binding. The Who-Is the stack
  sends for it goes to this host's own unicast address with `broadcast = true`
  (`TX 20 bytes to 192.168.3.64:47834 (broadcast) ... Who-Is DNET=65535`), the `common/`
  `HelperSendMessage` defect tracked with stack
  [#3933](https://github.com/chipkin/cas-bacnet-stack/issues/3933) (open). Fix it in
  `common/` (B-SS-CPP) and sweep; then a Wire Test with a Python peer as device 389016.
- **The Schedule's demo exception** covers today from 00:00:05, so it is in effect from
  start-up; the old "a few seconds after start-up" wording was wrong and is corrected.
- **`'s'` does nothing**: `main()` has no `case` for `KeyCommand::DemoAdvance`. The banner no
  longer mentions it.
- **Calendar 1 ("Cream")** is added with plain `BACnetStack_AddObject`, so its `Date_List` is
  empty and `Present_Value` is `false`. Stack #2034 and #963, which this file used to list as
  blockers, are closed: `BACnetStack_AddCalendarObject` now holds a Date_List in the stack and
  a Schedule exception can reference a stack-held Calendar. Adopting them is phase-2 work.
