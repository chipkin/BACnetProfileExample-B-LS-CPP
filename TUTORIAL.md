# Tutorial - extending and reviewing the B-LS example

[README.md](README.md) says what this example *is*. This document is the *how*:
how to extend it into your own device, who serves which property, how the
Channel/WriteGroup/Schedule fan-out actually reaches a remote device, how to
review the result for conformance, and what goes wrong when you get it subtly
right.

- [Extending the example](#extending-the-example)
- [How Channel + WriteGroup + Schedule drive a remote write](#how-channel--writegroup--schedule-drive-a-remote-write)
- [How the remote write actually happens](#how-the-remote-write-actually-happens)
- [Write_Status: following the fan-out to its end](#write_status-following-the-fan-out-to-its-end)
- [What each object type needs you to serve](#what-each-object-type-needs-you-to-serve)
- [Who serves what: the application or the stack?](#who-serves-what-the-application-or-the-stack)
- [Reviewing your device](#reviewing-your-device)
- [Troubleshooting](#troubleshooting)

## Extending the example

The example is intentionally as small as a B-LS can be, so it's easy to change.

**Change a sensor's value or name** - edit the constants / callbacks in
`main.cpp` (e.g. the initial value of `g_analogInput1Value`, or the `"Bronze"`
string in `GetPropertyCharString`).

**Change the device identity before you ship** - vendor ID, vendor name, model
name, description, firmware revision and device name are all in the
`CHANGE ALL OF THIS BEFORE YOU SHIP` block at the top of `main.cpp`, with a
per-field note on each saying what to change it to. The device name there is
only the default: each unit takes its own with `--deviceName` at start-up, as
it takes its instance with `--deviceID`. That block is the
authoritative checklist; it is in the source rather than here so it cannot be
skipped by someone who only reads the code.

**Point the remote reference at a different device** - `REMOTE_DEVICE_INSTANCE`,
`REMOTE_OBJECT_TYPE` and `REMOTE_OBJECT_INSTANCE` near the top of `main.cpp`
name the device and object Channel 1 and Schedule 1's remote references point
at. The default targets a `BACnetProfileExample-B-LD-CPP` instance's Lighting
Output 1.

## How Channel + WriteGroup + Schedule drive a remote write

Three pieces work together, and the example exercises all three end-to-end:

**1. Channel 1 ("Garnet")** holds a `List_Of_Object_Property_References` - one
LOCAL reference (Lighting Output 1 "Jade"'s `Present_Value`) and one REMOTE
reference (a second device's Lighting Output, named by device instance -
`BACnetStack_AddObjectPropertyReferenceToChannel(..., refUseDeviceIdentifier=true,
refDeviceInstance=<remote>, ...)`). Channel 1 also serves `Channel_Number` and
`Control_Groups`, which is how an incoming WriteGroup request MATCHES this
Channel at all.

**2. WriteGroup (service 40, DS-WG-E-B)** is the service that actually fans a
value out. This device both EXECUTES an incoming WriteGroup (the profile's
defining BIBB - entirely stack-internal: matching `Channel_Number`/
`Control_Groups`, then writing every reference) and, for the demo, ORIGINATES
one with `BACnetStack_SendWriteGroup` (the `'w'` key) - broadcasting a request
that this device's own Channel 1 matches, so pressing `'w'` exercises the full
receive-side path too.

**3. Schedule 1 ("Saffron")** points at Channel 1's own `Present_Value`
(`BACnetStack_AddScheduleObjectPropertyReference(..., PROPERTY_IDENTIFIER_PRESENT_VALUE,
false, 0)`, written at Priority_For_Writing 12; before v1.2.0 it named the
Channel's `Priority_Array`, a property a Channel does not have) and writes it automatically
at 09:00/17:00 daily (`AddScheduleWeeklyTimeValue`), plus a demo exception
event for today from 00:00:05, which is already in effect when the device
starts. A Schedule-driven write to Channel 1 goes through the same mechanism as
a direct WriteProperty to Channel 1, and **both are propagated to the Channel's
members** like a WriteGroup: 135-2024 cl. 12.53.5 says "When Present_Value is
written, the Channel object shall propagate that value to each of the members in
the List_Of_Object_Property_References" (the stack did this only for a WriteGroup
before the `6.x` @ `4238a39f` Stack Pin; [TODO.md](TODO.md) "Fixed upstream"). Combine
a Schedule with a WriteGroup by having the Schedule target a Channel that a
WriteGroup ALSO targets, same as this example does with Channel 1 itself, via
the `'w'` key's demo.

> **The demo exception event fires on its own; no key press is required.** The
> `'s'` (`DemoAdvance`) key exists in the shared `common/` keyboard helper (and
> is mentioned in this example's start-up banner), but this example's `main()`
> does not have a `case` for `KeyCommand::DemoAdvance` in its key-handling
> `switch` - pressing `'s'` is currently a no-op here. The exception event
> is in effect from start-up regardless (it is a wall-clock exception event
> for today from 00:00:05, not something the key triggers) - that is what
> step 6 of the README's Verify section and step 5 of
> [Reviewing your device](#reviewing-your-device) rely on. Do not rely on the
> key working until `main.cpp` adds the missing `case`.

## How the remote write actually happens

Earlier CAS BACnet Stack builds had a pair of exports,
`RegisterCallbackChannelSendWritePropertyToRemote` and
`RegisterCallbackScheduleSendWritePropertyToRemote`, that asked the
**application** to perform an outbound WriteProperty by hand whenever a
Channel or Schedule referenced a remote device. **Verified against this
example's pinned commit** (`submodules/cas-bacnet-stack/source/CASBACnetStackDLL.h`,
the "Sprint 82" comment): **both exports were removed.** The stack now does the
remote write itself, automatically, via an internal resolver called the
**Device_Address_Binding (DAB)**. Once a reference names
`refUseDeviceIdentifier = true` and a remote `refDeviceInstance`, the DAB
resolves that device's address from whatever I-Am traffic it has seen - either
its own Who-Is (sent at start-up for a device it has not found, then hourly), or a
manual one (the `'d'` key, `BACnetStack_SendWhoIs`) - and the stack sends the
WriteProperty on its own. An unbound device is skipped: a WriteGroup does not keep
the write for later.

> **The DAB's Who-Is needs `common/` 3.4.0 or later.** The stack sends it with
> `broadcast = true` and, as the address, a template copied from the last I-Am it
> heard - at start-up that is this device's own I-Am, looped back. `common/` up to
> 3.3.0 sent such a frame unicast to this host, so no other device ever heard it
> and the remote member was never found (stack
> [#3933](https://github.com/chipkin/cas-bacnet-stack/issues/3933)). 3.4.0 sends a
> broadcast addressed to its own socket to the subnet broadcast. If you write your
> own send callback, do the same.
This example registers **neither** removed callback (they do not exist any
more; registering them would not compile) - see `main.cpp`'s header comment
for the full writeup and the citation.

**If you are copying this pattern into a new example or a real product**, do
not add `RegisterCallbackChannelSendWritePropertyToRemote` or
`RegisterCallbackScheduleSendWritePropertyToRemote` calls - they do not exist
at this pin and the build will fail. Re-verify this section against
`CASBACnetStackDLL.h`'s "Sprint 82" comment whenever the stack pin moves
forward past a release that might reintroduce or further change this shape.

## Write_Status: following the fan-out to its end

`Write_Status` is required on a Channel, and the stack does not keep it. cl.
12.53.5: "During the writing of values to members, Write_Status shall be
IN_PROGRESS. At the end of writing all values, Write_Status shall change to
SUCCESSFUL or FAILED based on the results of these writes." The application can
see every one of those writes, so `main.cpp` section 2e keeps it:

- **The start.** Every write to Channel 1 - a WriteGroup, a WriteProperty or
  Schedule 1's - reaches `SetPropertyReal` / `SetPropertyNull` for the Channel, and the
  stack then writes each member, all inside one `BACnetStack_Tick()`. The Channel's
  Set callback sets `Write_Status` = IN_PROGRESS; the main loop closes the fan-out
  after the tick. (For a WriteGroup the stack also calls `WriteGroupInhibitDelay`
  first; that only labels the console line.)
- **The local member.** Jade's Set callback accepts the value or refuses it (a level
  outside 0..100 %). A refusal marks the fan-out failed.
- **The remote member.** The stack sends a confirmed WriteProperty. Its answer comes
  back through `HookSimpleAck`, `HookError`, `HookReject`, `HookAbort`, or - when
  device 389016 never answers - `HookTimeout`, after APDU_Timeout x
  (Number_Of_APDU_Retries + 1) (10 s x 4 = 40 s with the stack's defaults at
  6.x 4238a39f, which retries a confirmed request 3 times). The hooks
  match the answer by the address `HookIAm` recorded for 389016. If 389016 has never
  sent an I-Am, the stack skips it, and the fan-out is failed at once.
- **The end.** Once no answer is outstanding, `Write_Status` is SUCCESSFUL, or
  FAILED if any write failed.
- **BUSY.** A WriteProperty of Channel 1 `Present_Value` while IN_PROGRESS is refused
  with Error Class OBJECT, Error Code BUSY (cl. 12.53.5).

At start-up Schedule 1 writes Channel 1 before device 389016 has answered a Who-Is,
so its write to 389016 is skipped and `Write_Status` reads FAILED until the next
write that reaches both members.

## What each object type needs you to serve

The application must serve every REQUIRED property the stack does not generate.
It differs per type — this is the checklist, so you do not have to infer it:

| Object type | You must serve | Plus |
|---|---|---|
| Analog Input | `Present_Value` (Real), `Object_Name`, `Units` | — |
| Binary Input | `Present_Value` (Enumerated), `Object_Name` | `Polarity` |
| Multi-State Input | `Present_Value` (Unsigned), `Object_Name` | `Number_Of_States` |
| Analog/Binary/Multi-State Output | `Object_Name`, `Relinquish_Default` | `Units`/`Polarity`/`Number_Of_States`; `Present_Value`/`Priority_Array`/`Current_Command_Priority` are resolved by the stack from the Priority_Array the app maintains |
| Lighting Output | `Object_Name`, `Tracking_Value`, `Lighting_Command`, `In_Progress`, the dimming defaults (`Blink_Warn_Enable`, `Egress_Time`, `Egress_Active`, `Default_Fade_Time`, `Default_Ramp_Rate`, `Default_Step_Increment`, `Lighting_Command_Default_Priority`), `Last_On_Value`, `Default_On_Value`, `Relinquish_Default` | `Present_Value`/`Priority_Array` resolved by the stack; the Lighting Output engine (`main.cpp` section 1b) carries out each `Lighting_Command` over time |
| Channel | `Object_Name`, `Last_Priority`, `Write_Status`, `Channel_Number`, `Control_Groups` | `List_Of_Object_Property_References` set with `BACnetStack_AddObjectPropertyReferenceToChannel`, not a callback |
| Schedule | `Object_Name`, `Out_Of_Service` | everything else configured through the dedicated `BACnetStack_AddScheduleObject*` API, not a callback |
| Calendar | `Object_Name`, `Present_Value` | `Date_List` is a documented gap - see [Troubleshooting](#troubleshooting) |

## Who serves what: the application or the stack?

The single most common question when reading this file is "who answers this
property?" For the Device object, the whole picture:

| Property | Served by | How |
|---|---|---|
| `Object_Identifier` | **stack** | generated from the device you added |
| `Object_Type` | **stack** | generated |
| `Object_List` | **stack** | generated (all twelve objects) |
| `Property_List` | **stack** | generated |
| `Vendor_Name` / `Vendor_Identifier` / `Model_Name` / `Firmware_Revision` / `Application_Software_Version` | **you** | `GetPropertyCharString` / `GetPropertyUnsignedInteger` |
| `Description` *(optional)* | **you** | `GetPropertyCharString`, and `SetPropertyEnabled` (see the warning below) |
| `Protocol_Version` / `Protocol_Revision` / `Protocol_Services_Supported` / `Protocol_Object_Types_Supported` / `Device_Address_Binding` | **stack** | generated from what you configured with `SetServiceEnabled` / `AddObject` / the DAB's observed I-Am traffic |
| `Max_APDU_Length_Accepted` / `Segmentation_Supported` / `APDU_Timeout` / `Number_Of_APDU_Retries` / `System_Status` / `Database_Revision` | **stack default, accepted** | the stack's configured defaults; this example does not override them |

> **An optional property needs `SetPropertyEnabled`, not just a callback
> branch.** The stack checks `IsPropertyEnabled` BEFORE it ever reaches the
> callbacks, and for an optional property that check falls back to "is it
> required?" - which is false. So a `Description` branch in
> `GetPropertyCharString` without a matching `BACnetStack_SetPropertyEnabled`
> call is DEAD CODE, and the client reads back `Error: unknown-property`. This
> example shipped exactly that bug once; it was caught by a reviewer tracing
> the stack source, not by running it - a plausible-looking callback branch
> that never executes. `main.cpp`'s comment right above the Device's
> `SetPropertyEnabled(..., PROPERTY_IDENTIFIER_DESCRIPTION, ...)` call tells
> the same story.

Every object, not just the Device, is in [docs/PICS.md](docs/PICS.md).

### The Channel's write dispatch is not the usual shape

`BACnetStack_AddChannelObject`'s doc comment says a Channel's `Present_Value`
write arrives on `PROPERTY_IDENTIFIER_PRIORITY_ARRAY` with `useArrayIndex=true`
and the array index AS the priority. At stack `6.x` @ `64b2cfac5` every write this
example sees - a client WriteProperty, a WriteGroup, and Schedule 1's write -
arrives the usual way instead, on `PROPERTY_IDENTIFIER_PRESENT_VALUE` with the
`priority` argument (stack
[#3955](https://github.com/chipkin/cas-bacnet-stack/issues/3955)). The
Channel-specific branches in `SetPropertyReal` / `SetPropertyNull` accept both, so
a new Channel copied from them works whichever the stack sends.

`Channel_Number` and `Control_Groups` must be served (`GetPropertyUnsignedInteger`)
and writable, or an incoming WriteGroup never matches this Channel at all - see
`BACnetStack_AddChannelObject`'s doc's "IMPORTANT" note.

## Reviewing your device

After you have changed anything, review it against the conformance statement
rather than against "it looked fine in the explorer":

1. Regenerate [docs/PICS.md](docs/PICS.md) after editing `docs/objects.json`
   (see [Keeping the PICS honest](#keeping-the-pics-honest) below). A ⚠ row is a
   required property nothing serves.
2. Read **every** property listed for **every** object with a BACnet client, and
   compare the value against the PICS.
3. Confirm the services you do **not** implement are still rejected - for B-LS,
   ReadPropertyMultiple and SubscribeCOV.
4. Run the Wire Tests (`python3 tests/run_wire_tests.py`): they play device
   389016 and a WriteGroup client, and check the fan-out, `Write_Status` and the
   Failure Modes. By hand: run a device 389016 with a Lighting Output 1 on another
   host of this subnet, same UDP port, then send a WriteGroup (or press `'w'` in
   this example's console - Windows `_kbhit`/`_getch` read the real console, not a
   piped stdin), and confirm Jade and the other device's Lighting Output both take
   the value and Channel 1's `Write_Status` reads `successful`.
5. Confirm the Schedule's demo exception event (today from 00:00:05) is writing
   Channel 1's `Present_Value` from start-up (console:
   `Write: Channel 1 (Garnet) <- 100.00 @ priority 12`) - this one is
   easy to observe without a second instance or an external client, and does
   **not** depend on the `'s'` key (see the note above).

### Keeping the PICS honest

`docs/PICS.md` is partly generated. `docs/objects.json` describes each object and
who serves which property; the series tool regenerates the object tables from it
plus the stack's own `docs/property-profile-reference.md` at the pinned commit:

```bash
python tools/gen-objects-properties.py BACnetProfileExample-B-LS-CPP            # rewrite
python tools/gen-objects-properties.py BACnetProfileExample-B-LS-CPP --check    # fail if stale
```

(That tool lives in the example-series repository, not in this one. If you only
have this repository, edit the generated block by hand and keep it matching the
callbacks in `main.cpp`.)

When you add an object or a property to `main.cpp`, update `docs/objects.json`
in the same change and regenerate. The `app` list is what the callbacks serve;
`accepted` is for a required property you deliberately leave to the stack's
default, and each one needs a justification. Anything required, not in `app` and
not in `accepted`, comes out as a ⚠ row - that is a defect, not a feature.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| On start-up the app prints a wall of red `Error:` lines but the device works | **Expected — this is not your bug.** This is the stack's own debug logging: the device receives its **own** broadcast I-Am and logs a decode cascade, and a one-time UUID notice for the BACnet/SC datalink this IP-only example never configures. On a healthy start-up roughly half the output is these lines. |
| Pressing `'s'` does nothing | This is a real gap, not a misunderstanding - see the note in [How Channel + WriteGroup + Schedule drive a remote write](#how-channel--writegroup--schedule-drive-a-remote-write). The demo exception event (today from 00:00:05) is in effect from start-up anyway. |
| The example exits at start-up with `Error: Failed to enable the WriteGroup service.` | The stack was built without `STACK_OPTION_WRITE_GROUP`; its default preset leaves WriteGroup out. Use the default SOURCE build (`CMakeLists.txt` defines it), or rebuild your prebuilt stack library with it (README "Build"). |
| `Write_Status` reads `failed` right after start-up | Schedule 1 wrote Channel 1 on the first tick, before device 389016 answered a Who-Is, so the stack could not address it and skipped its write (cl. 12.53.7). The next write to Channel 1 (a WriteProperty, `'w'`, or the Schedule's next transition) reaches both members once 389016 is known. |
| Calendar 1 ("Cream")'s `Date_List` always reads empty / `Present_Value` always reads `false` | This example adds Calendar 1 with plain `BACnetStack_AddObject` and puts nothing in its `Date_List`, so it is empty and `Present_Value` is `false`. The stack has since gained a stack-held Calendar (`BACnetStack_AddCalendarObject` and its `AddCalendarDateList*` exports; stack issues [#2034](https://github.com/chipkin/cas-bacnet-stack/issues/2034) and [#963](https://github.com/chipkin/cas-bacnet-stack/issues/963) are closed), which this example does not use yet. Schedule 1's exception event uses the direct date form (`AddScheduleExceptionEventWithCalendarEntry`), so it does not depend on the Calendar. |
| A WriteGroup / remote write does not seem to reach the second device | The stack's Device_Address_Binding must have resolved the remote device's address first: the console prints `I-Am: remote device 389016 is at ...` when it has. The stack's own Who-Is goes out at start-up (then hourly); `'d'` sends another. The second device must be on the same subnet AND the same UDP port - a device on another port never hears a broadcast. `Write_Status` reads `failed` after a WriteGroup that could not reach it. See [How the remote write actually happens](#how-the-remote-write-actually-happens). |
| CMake error: *"CAS BACnet Stack adapter not found under: ..."* | Submodules not initialized. Run `git submodule update --init --recursive` (or pass `-D CAS_STACK_DIR=...`). |
| `CASBACnetStackDLL.h: No such file or directory` | Same - submodules not checked out. |
| Windows: *"No CMAKE_CXX_COMPILER could be found"* | Install Visual Studio with the "Desktop development with C++" workload, then re-run from a fresh terminal. |
| First build seems stuck for minutes | Normal - it's compiling ~600 stack files. Only the first build is slow. |
| App prints *"Failed to bind UDP port 47808"* | Another BACnet program is already using 47808. Stop it, or run with `--port <n>`. |
| Client sends Who-Is but sees no I-Am | Firewall is blocking UDP 47808, or the client and device are on different subnets (Who-Is is a broadcast). Allow the port; test on the same subnet first. |
| Replies show an unexpected device instance or vendor | Another BACnet device is already answering on this host/port. Stop the other device, or use `--port`. |
