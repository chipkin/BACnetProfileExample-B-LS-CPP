# BACnet Protocol Implementation Conformance Statement (PICS)

For the **BACnet B-LS (Lighting Supervisor) C++ example** -
see [README.md](../README.md).

> This is the PICS **for the example as shipped**. It describes a tutorial
> device announcing itself as a Chipkin demo, not a product. When you turn this
> example into your own device, this document is one of the things you rewrite:
> the vendor, model and version rows all come from the
> `CHANGE ALL OF THIS BEFORE YOU SHIP` block at the top of `main.cpp`. The
> example has **not** been submitted for BTL certification.

## 1. Product description

| | |
|---|---|
| **Vendor Name** | Chipkin Automation Systems |
| **Vendor Identifier** | 389 |
| **Product Name** | CAS BACnet Stack Example - B-LS |
| **Product Model Number** | CAS BACnet Stack Example - B-LS |
| **Application Software Version** | 1.3.0 |
| **Firmware Revision** | 6.0.23.0 (the CAS BACnet Stack version) |
| **BACnet Protocol Version** | 1 |
| **BACnet Protocol Revision** | 30 |

**Product Description:** a BACnet/IP Lighting Supervisor built on the CAS
BACnet Stack. It presents the B-SA-style read-only sensors and commandable
outputs, a Lighting Output ("Jade"), a Channel ("Garnet") that fans a
WriteGroup out to Jade and to a remote device's Lighting Output
(F-CHANNEL / F-EXTWRITE) and reports in `Write_Status` whether every member
took the value, and a Schedule ("Saffron") that writes the Channel on a timer
(F-SCHED-E), plus a Calendar ("Cream"). The WriteGroup fan-out to both members,
and its Failure Modes, are proved by the Wire Tests. The Schedule's write and
a WriteProperty to the Channel are forwarded to its members the same way, and
`Write_Status` follows each of them. It is a tutorial for
implementers of the B-LS profile and the series' canonical implementation of
F-CHANNEL, F-EXTWRITE and F-SCHED-E.

## 2. BACnet standardized device profile (Annex L)

**B-LS - BACnet Lighting Supervisor.**

This device claims exactly one profile. Because the B-LS requirements are a
superset of B-GENERAL's, a conformant B-LS device also satisfies **B-GENERAL**
(Annex L.8); that is subsumption, not a second claim.

## 3. BIBBs supported (Annex K)

| BIBB | Description |
|---|---|
| DS-RP-B | Data Sharing - ReadProperty - B |
| DS-WP-A | Data Sharing - WriteProperty - A |
| DS-WP-B | Data Sharing - WriteProperty - B |
| DS-WG-E-B | Data Sharing - WriteGroup - Execute - B |
| DS-ALO-A | Data Sharing - Application specific controllers - Lighting Output - A |
| SCHED-E-B | Scheduling - Execute - B |
| DM-DDB-A | Device Management - Dynamic Device Binding - A |
| DM-DDB-B | Device Management - Dynamic Device Binding - B |
| DM-DOB-B | Device Management - Dynamic Object Binding - B |
| DM-DCC-B | Device Management - Device Communication Control - B |

No other BIBBs are supported. In particular this device does **not** support
DS-RPM-B (ReadPropertyMultiple), DS-COV-B, any alarm and event (AE-*) BIBB,
trending (T-*), or backup/restore (DM-BR-*).

TimeSynchronization (`SERVICE_TIME_SYNCHRONIZATION`) and UTCTimeSynchronization
(`SERVICE_UTC_TIME_SYNCHRONIZATION`) are both enabled
(`BACnetStack_SetServiceEnabled`) and served by `SetSystemTime`, matching
DM-TS-B / DM-UTC-B, even though neither has a dedicated BIBB row in the B-LS
requirement table above.

## 4. Application services supported

| Service | Initiate | Execute |
|---|:---:|:---:|
| ReadProperty | no | **yes** |
| WriteProperty | **yes** (`'w'` demo key, via `SendWriteGroup`) | **yes** |
| WriteGroup | **yes** (`'w'` demo key) | **yes** |
| Who-Is | **yes** (`'d'` demo key) | **yes** |
| I-Am | **yes** | **yes** |
| Who-Has | no | **yes** |
| I-Have | **yes** | - |
| DeviceCommunicationControl | no | **yes** |
| TimeSynchronization | no | **yes** |
| UTCTimeSynchronization | no | **yes** |

An unsolicited I-Am is broadcast to the local subnet at start-up, as well as in
response to Who-Is. I-Am is also executed (DM-DDB-A): a received I-Am fills the
stack's Device_Address_Binding, which resolves Channel 1's remote member
(device 389016; section 8). Any other confirmed service - including
ReadPropertyMultiple and SubscribeCOV - is rejected. That rejection is part of
the profile boundary, not a limitation to work around.

## 5. Segmentation capability

Segmentation is **supported in both directions**
(`Segmentation_Supported` = `segmented-both`), by the stack: at `6.x` @
`64b2cfac5` the customer build compiles `STACK_OPTION_SEGMENTATION` in (stack
#2992), and this example keeps the stack's defaults for `Max_Segments_Accepted`
and `APDU_Segment_Timeout`. Table 12-13 footnote 1: "These properties are
required if, and shall be present only if, segmentation of any kind is
supported" - they are not rows in section 11 because its generator lists only
unconditionally required properties. (At the previous pin, `abd4cee1`, this
example answered `no-segmentation`.) `Max_APDU_Length_Accepted` is 1476
octets, the BACnet/IP maximum (`MAX_APDU_LENGTH` in `main.cpp`).

## 6. Standard object types supported

No object is dynamically creatable or deletable.

| Object type | Instance | Object_Name | Writable properties | Optional properties supported |
|---|:---:|---|---|---|
| Device | 389017 | Chipkin Example B-LS | - | Description |
| Analog Input | 1 | Bronze | - | - |
| Binary Input | 1 | Emerald | - | - |
| Multi-State Input | 1 | Hot Pink | - | State_Text |
| Analog Output | 1 | Chartreuse | Present_Value | - |
| Binary Output | 1 | Fuchsia | Present_Value | - |
| Multi-State Output | 1 | Indigo | Present_Value | - |
| Lighting Output | 1 | Jade | Present_Value, Lighting_Command | - |
| Channel | 1 | Garnet | Present_Value, Channel_Number, Control_Groups | - |
| Schedule | 1 | Saffron | - | - |
| Calendar | 1 | Cream | - | - |
| Network Port | 1 | Vermilion | - | - |

The device instance is configurable at start-up with `--deviceID`, and the
Device's Object_Name with `--deviceName` (BACnet requires both to be
configurable, cl. 12.1.1.3 and 12.1.1.4). Changing either means restarting
the device; neither is writable over the network. The table shows the
defaults.

## 7. Data link layer options

**BACnet/IP (Annex J)**, UDP port 47808 (0xBAC0) by default, configurable at run
time with `--port`.

BBMD is not supported, Foreign Device registration is not supported, and
BACnet/SC, MS/TP, Ethernet (Annex H) and PTP are not supported.

## 8. Device address binding

Static device binding is **not required** to be pre-configured, but this
device does perform dynamic device binding: Channel 1 (Garnet) carries a
reference to a remote device (`REMOTE_DEVICE_INSTANCE` = 389016 by default),
named with `refUseDeviceIdentifier = true`. The stack's Device_Address_Binding
(DAB) resolves that device's address from I-Am traffic - its own Who-Is for the
device (broadcast at start-up, then hourly; it reaches the subnet since
`common/` 3.4.0), or the `'d'` (DiscoverRemote) demo key's manual
`BACnetStack_SendWhoIs` - lists it in the Device object's
`Device_Address_Binding`, and then sends the remote WriteProperty itself. See
[TUTORIAL.md](../TUTORIAL.md#how-the-remote-write-actually-happens) for the
full mechanism and why this example does **not** register
`RegisterCallbackChannelSendWritePropertyToRemote` or
`RegisterCallbackScheduleSendWritePropertyToRemote` - both were removed from
this stack's customer surface at the pinned commit.

## 9. Networking options

None. The device is not a router, not a BBMD, and does not register as a
foreign device.

## 10. Character sets supported

UTF-8 (ANSI X3.4). Supporting a character set does not imply the device can
handle data in all character sets.

## 11. Objects and properties

<!-- OBJECTS-PROPERTIES:BEGIN (generated by tools/gen-objects-properties.py from docs/objects.json - do not edit here) -->
Every object this example creates, and every REQUIRED property of each (per ANSI/ASHRAE 135-2024 clause 12 and the CAS BACnet Stack's property profiles), plus the optional properties the example turns on. **Served by** says who answers a ReadProperty: the **stack** generates it, or the **app** serves it from a `GetProperty*` callback in `main.cpp`. A ⚠ row is a required property the app does not serve and the stack would fill with a default - that is a defect, not a feature.

### Device 389017 "Chipkin Example B-LS" - the device itself; the instance is configurable with --deviceID and the Object_Name with --deviceName (both at start-up; the heading shows the defaults). The stack rows are device-wide facts only the stack knows - the protocol version and revision it implements, the services and object types it was configured with, the live object list and address-binding table, and Database_Revision, which the stack starts at 0 and increments as the objects are added at start-up: it reads 12 and stays 12, because nothing creates, deletes or renames an object afterwards (a command, a WriteGroup, a Schedule write, a time sync or a DeviceCommunicationControl changes no object). The accepted rows are the stack's configured defaults for APDU limits, segmentation and system status; an application that answered them from its own constants could contradict the stack, so this example does not

| Property | Datatype | Served by | Writable |
|---|---|---|:---:|
| Object_Identifier | BACnetObjectIdentifier | stack | no |
| Object_Name | CharacterString | app | no |
| Object_Type | BACnetObjectType | stack | no |
| System_Status | BACnetDeviceStatus | stack default, accepted (Generic Enumerated default: `0`) | no |
| Vendor_Name | CharacterString | app | no |
| Vendor_Identifier | Unsigned16 | app | no |
| Model_Name | CharacterString | app | no |
| Firmware_Revision | CharacterString | app | no |
| Application_Software_Version | CharacterString | app | no |
| Description *(optional, enabled)* | CharacterString | app | no |
| Protocol_Version | Unsigned | stack | no |
| Protocol_Revision | Unsigned | stack | no |
| Protocol_Services_Supported | BACnetServicesSupported | stack | no |
| Protocol_Object_Types_Supported | BACnetObjectTypesSupported | stack | no |
| Object_List | BACnetARRAY[N] of BACnetObjectIdentifier | stack | no |
| Max_APDU_Length_Accepted | Unsigned | stack default, accepted (`CAS_BACNET_DEVICE_DEFAULT_MAX_APDU_LENGTH_ACCEPTED`) | no |
| Segmentation_Supported | BACnetSegmentation | stack default, accepted (`BACnetSegmentation::segmentedBoth` with `STACK_OPTION_SEGME) | no |
| APDU_Timeout | Unsigned | stack default, accepted (`CAS_BACNET_DEVICE_DEFAULT_APDU_TIMEOUT`) | no |
| Number_Of_APDU_Retries | Unsigned | stack default, accepted (`CAS_BACNET_DEVICE_DEFAULT_NUMBER_OF_APDU_RETRIES`) | no |
| Device_Address_Binding | BACnetLIST of BACnetAddressBinding | stack | no |
| Database_Revision | Unsigned | stack | no |
| Property_List | BACnetARRAY[N] of BACnetPropertyIdentifier | stack | no |

### Analog Input 1 "Bronze" - REAL, degrees Celsius; starts at 21.5

| Property | Datatype | Served by | Writable |
|---|---|---|:---:|
| Object_Identifier | BACnetObjectIdentifier | stack | no |
| Object_Name | CharacterString | app | no |
| Object_Type | BACnetObjectType | stack | no |
| Present_Value | Real | app | no |
| Status_Flags | BACnetStatusFlags | stack | no |
| Event_State | BACnetEventState | stack default, accepted (Generic Enumerated default: `0`) | no |
| Out_Of_Service | Boolean | app | no |
| Units | BACnetEngineeringUnits | app | no |
| Property_List | BACnetARRAY[N] of BACnetPropertyIdentifier | stack | no |

### Binary Input 1 "Emerald" - starts inactive

| Property | Datatype | Served by | Writable |
|---|---|---|:---:|
| Object_Identifier | BACnetObjectIdentifier | stack | no |
| Object_Name | CharacterString | app | no |
| Object_Type | BACnetObjectType | stack | no |
| Present_Value | BACnetBinaryPV | app | no |
| Status_Flags | BACnetStatusFlags | stack | no |
| Event_State | BACnetEventState | stack default, accepted (Generic Enumerated default: `0`) | no |
| Out_Of_Service | Boolean | app | no |
| Polarity | BACnetPolarity | app | no |
| Property_List | BACnetARRAY[N] of BACnetPropertyIdentifier | stack | no |

### Multi-state Input 1 "Hot Pink" - state 1 of 3: On, Off, Auto

| Property | Datatype | Served by | Writable |
|---|---|---|:---:|
| Object_Identifier | BACnetObjectIdentifier | stack | no |
| Object_Name | CharacterString | app | no |
| Object_Type | BACnetObjectType | stack | no |
| Present_Value | Unsigned | app | no |
| Status_Flags | BACnetStatusFlags | stack | no |
| Event_State | BACnetEventState | stack default, accepted (Generic Enumerated default: `0`) | no |
| Out_Of_Service | Boolean | app | no |
| Number_Of_States | Unsigned | app | no |
| State_Text *(optional, enabled)* | BACnetARRAY[N] of CharacterString | app | no |
| Property_List | BACnetARRAY[N] of BACnetPropertyIdentifier | stack | no |

### Analog Output 1 "Chartreuse" - REAL setpoint; commandable via a 16-slot Priority_Array (WriteProperty/DS-WP-B); Present_Value, Priority_Array and Current_Command_Priority are resolved by the stack from the array the app maintains

| Property | Datatype | Served by | Writable |
|---|---|---|:---:|
| Object_Identifier | BACnetObjectIdentifier | stack | no |
| Object_Name | CharacterString | app | no |
| Object_Type | BACnetObjectType | stack | no |
| Present_Value | Real | stack | yes |
| Status_Flags | BACnetStatusFlags | stack | no |
| Event_State | BACnetEventState | stack default, accepted (Generic Enumerated default: `0`) | no |
| Out_Of_Service | Boolean | app | no |
| Units | BACnetEngineeringUnits | app | no |
| Priority_Array | BACnetARRAY[16] of BACnetOptionalReal | stack | no |
| Relinquish_Default | Real | app | no |
| Property_List | BACnetARRAY[N] of BACnetPropertyIdentifier | stack | no |
| Current_Command_Priority | BACnetOptionalUnsigned | stack | no |

### Binary Output 1 "Fuchsia" - active/inactive; commandable via a 16-slot Priority_Array (WriteProperty/DS-WP-B)

| Property | Datatype | Served by | Writable |
|---|---|---|:---:|
| Object_Identifier | BACnetObjectIdentifier | stack | no |
| Object_Name | CharacterString | app | no |
| Object_Type | BACnetObjectType | stack | no |
| Present_Value | BACnetBinaryPV | stack | yes |
| Status_Flags | BACnetStatusFlags | stack | no |
| Event_State | BACnetEventState | stack default, accepted (Generic Enumerated default: `0`) | no |
| Out_Of_Service | Boolean | app | no |
| Polarity | BACnetPolarity | app | no |
| Priority_Array | BACnetARRAY[16] of BACnetOptionalBinaryPV | stack | no |
| Relinquish_Default | BACnetBinaryPV | app | no |
| Property_List | BACnetARRAY[N] of BACnetPropertyIdentifier | stack | no |
| Current_Command_Priority | BACnetOptionalUnsigned | stack | no |

### Multi-state Output 1 "Indigo" - state 1..3; commandable via a 16-slot Priority_Array (WriteProperty/DS-WP-B)

| Property | Datatype | Served by | Writable |
|---|---|---|:---:|
| Object_Identifier | BACnetObjectIdentifier | stack | no |
| Object_Name | CharacterString | app | no |
| Object_Type | BACnetObjectType | stack | no |
| Present_Value | Unsigned | stack | yes |
| Status_Flags | BACnetStatusFlags | stack | no |
| Event_State | BACnetEventState | stack default, accepted (Generic Enumerated default: `0`) | no |
| Out_Of_Service | Boolean | app | no |
| Number_Of_States | Unsigned | app | no |
| Priority_Array | BACnetARRAY[16] of BACnetOptionalUnsigned | stack | no |
| Relinquish_Default | Unsigned | app | no |
| Property_List | BACnetARRAY[N] of BACnetPropertyIdentifier | stack | no |
| Current_Command_Priority | BACnetOptionalUnsigned | stack | no |

### Lighting Output 1 "Jade" - REAL 0-100%; commandable via a 16-slot Priority_Array (WriteProperty/DS-WP-B) AND via the typed Lighting_Command SEQUENCE (DS-LO-B). The lighting engine is B-LD-CPP's (main.cpp section 1b): it runs every Table 12-67 operation over time - Present_Value is the target, Tracking_Value the level being driven, In_Progress fadeActive/rampActive while it moves, Egress_Active TRUE during a warn's egress time; NONE is refused. Jade is also Channel 1's local member, so a Channel write, a WriteGroup or Schedule 1 writes its Present_Value the same way. The dimming defaults and Egress_Time are writable, range-checked. Last_On_Value and Default_On_Value (100.0; required in 135-2024, cl. 12.54.44/45) are served by the app, Current_Command_Priority and Property_List by the stack.

| Property | Datatype | Served by | Writable |
|---|---|---|:---:|
| Object_Identifier | BACnetObjectIdentifier | stack | no |
| Object_Name | CharacterString | app | no |
| Object_Type | BACnetObjectType | stack | no |
| Present_Value | Real | stack | yes |
| Tracking_Value | Real | app | no |
| Lighting_Command | BACnetLightingCommand | app | yes |
| In_Progress | BACnetLightingInProgress | app | no |
| Status_Flags | BACnetStatusFlags | stack | no |
| Out_Of_Service | Boolean | app | no |
| Blink_Warn_Enable | Boolean | app | no |
| Egress_Time | Unsigned | app | yes |
| Egress_Active | Boolean | app | no |
| Default_Fade_Time | Unsigned | app | yes |
| Default_Ramp_Rate | Real | app | yes |
| Default_Step_Increment | Real | app | yes |
| Priority_Array | BACnetARRAY[16] of BACnetOptionalReal | stack | no |
| Relinquish_Default | Real | app | no |
| Lighting_Command_Default_Priority | Unsigned | app | no |
| Property_List | BACnetARRAY[N] of BACnetPropertyIdentifier | stack | no |
| Current_Command_Priority | BACnetOptionalUnsigned | stack | no |
| Last_On_Value | Real | app | no |
| Default_On_Value | Real | app | no |

### Channel 1 "Garnet" - F-CHANNEL / F-EXTWRITE (canonical). BACnetChannelValue REAL, commandable via a 16-slot Priority_Array the application holds. At 64b2cfac5 every write to it (client WriteProperty, WriteGroup, the Schedule) reaches SetPropertyReal/SetPropertyNull on PRESENT_VALUE with a priority, not on PRIORITY_ARRAY with an index as BACnetStack_AddChannelObject's doc says, so both shapes are accepted (stack #3955, TODO.md). List_Of_Object_Property_References and Execution_Delay are stack-held, set with BACnetStack_AddObjectPropertyReferenceToChannel: one local reference to Lighting Output 1 (Jade), one remote reference to device 389016's Lighting Output 1. Every write to Present_Value - a matching WriteGroup (DS-WG-E-B), a WriteProperty or Schedule 1's write - is forwarded to both (cl. 12.53.5): Jade through the Set callbacks, device 389016 with a WriteProperty the stack sends through its Device_Address_Binding (proved by tests/channel_fanout_test.py). Write_Status is kept by the application from those writes' results (main.cpp section 2e): IDLE until the first write, IN_PROGRESS while a member's answer is outstanding, then SUCCESSFUL or FAILED (cl. 12.53.7) - FAILED after Schedule 1's start-up write, which is made before device 389016 is bound; a WriteProperty of Present_Value while IN_PROGRESS is refused with OBJECT / BUSY. Last_Priority starts at 16 (cl. 12.53.6).

| Property | Datatype | Served by | Writable |
|---|---|---|:---:|
| Object_Identifier | BACnetObjectIdentifier | stack | no |
| Object_Name | CharacterString | app | no |
| Object_Type | BACnetObjectType | stack | no |
| Present_Value | BACnetChannelValue | stack | yes |
| Last_Priority | Unsigned | app | no |
| Write_Status | BACnetWriteStatus | app | no |
| Status_Flags | BACnetStatusFlags | stack | no |
| Out_Of_Service | Boolean | app | no |
| List_Of_Object_Property_References | BACnetARRAY[N] of BACnetDeviceObjectPropertyReference | stack | no |
| Execution_Delay | BACnetARRAY[N] of Unsigned | ⚠ stack default (Generic UnsignedInteger default: `0`) | no |
| Channel_Number | Unsigned16 | app | yes |
| Control_Groups | BACnetARRAY[N] of Unsigned32 | app | yes |
| Property_List | BACnetARRAY[N] of BACnetPropertyIdentifier | stack | no |

### Schedule 1 "Saffron" - F-SCHED-E (canonical). Present_Value, Effective_Period and Priority_For_Writing are genuinely served - by the STACK's own Schedule engine, configured through the dedicated API (BACnetStack_AddScheduleObject, AddScheduleWeeklyTimeValue [09:00 on / 17:00 off daily], SetScheduleDefault, SetScheduleEffectivePeriod, SetSchedulePriorityForWriting [12]) rather than a GetProperty callback, which is what this generator's simple app/stack heuristic looks for; they are listed as accepted only because the generator has no third category for 'served by a dedicated stack API, not a callback'. AddScheduleObjectPropertyReference points the Schedule at Channel 1's Present_Value, written at Priority_For_Writing 12 (until v1.2.0 it named the Channel's Priority_Array, which a Channel does not have); one demo AddScheduleExceptionEventWithCalendarEntry covers today from 00:00:05, so it is in effect from start-up. Channel 1 forwards the Schedule's write to its members (cl. 12.53.5). Reliability has no fault condition this example detects, so it is accepted at the generic default (normal), the same pattern as Network Port's Reliability below.

| Property | Datatype | Served by | Writable |
|---|---|---|:---:|
| Object_Identifier | BACnetObjectIdentifier | stack | no |
| Object_Name | CharacterString | app | no |
| Object_Type | BACnetObjectType | stack | no |
| Present_Value | Any | stack default, accepted (Stack-generated if commandable (resolves the priority array)) | no |
| Effective_Period | BACnetDateRange | stack default, accepted (None known - a read fails with `unknown-property` or an empt) | no |
| Schedule_Default | Any | stack | no |
| List_Of_Object_Property_References | BACnetLIST of BACnetDeviceObjectPropertyReference | stack | no |
| Priority_For_Writing | Unsigned(1..16) | stack default, accepted (Generic UnsignedInteger default: `0`) | no |
| Status_Flags | BACnetStatusFlags | stack | no |
| Reliability | BACnetReliability | stack default, accepted (Generic Enumerated default: `0`) | no |
| Out_Of_Service | Boolean | app | no |
| Property_List | BACnetARRAY[N] of BACnetPropertyIdentifier | stack | no |

### Calendar 1 "Cream" - F-SCHED-E support object. Present_Value ("is today in Date_List") is honestly always false: Date_List is a BACnetLIST of BACnetCalendarEntry (a variable-length list of a CHOICE type) and this stack build's customer surface has no Get callback shape that fits it (verified against CASBACnetStackDLL.h at the pin) - see TODO.md. Schedule 1's own exception-event scheduling does not depend on this: it uses the direct date/period form, AddScheduleExceptionEventWithCalendarEntry, confirmed functional in the stack's own doc comment (unlike AddScheduleExceptionEventWithCalendarReference, which the same doc comment says does not yet resolve a Calendar's Date_List - stack issue #963).

| Property | Datatype | Served by | Writable |
|---|---|---|:---:|
| Object_Identifier | BACnetObjectIdentifier | stack | no |
| Object_Name | CharacterString | app | no |
| Object_Type | BACnetObjectType | stack | no |
| Present_Value | Boolean | app | no |
| Date_List | BACnetLIST of BACnetCalendarEntry | stack default, accepted (None known - a read fails with `unknown-property` or an empt) | no |
| Property_List | BACnetARRAY[N] of BACnetPropertyIdentifier | stack | no |

### Network Port 1 "Vermilion" - BACnet/IP; Network_Type and Protocol_Level are set from BACnetStack_AddNetworkPortObject()'s arguments (IPv4, BACnet Application) at start-up, not a GetProperty callback like the object's other app-served rows; Changes_Pending is likewise computed and answered natively by the stack's Network Port object. Reliability has no fault condition this example detects, so it is accepted at the generic default (normal)

| Property | Datatype | Served by | Writable |
|---|---|---|:---:|
| Object_Identifier | BACnetObjectIdentifier | stack | no |
| Object_Name | CharacterString | app | no |
| Object_Type | BACnetObjectType | stack | no |
| Status_Flags | BACnetStatusFlags | stack | no |
| Reliability | BACnetReliability | stack default, accepted (Generic Enumerated default: `0`) | no |
| Out_Of_Service | Boolean | app | no |
| Network_Type | BACnetNetworkType | app | no |
| Protocol_Level | BACnetProtocolLevel | app | no |
| Changes_Pending | Boolean | app | no |
| Property_List | BACnetARRAY[N] of BACnetPropertyIdentifier | stack | no |

<!-- OBJECTS-PROPERTIES:END -->

## 12. References

- ANSI/ASHRAE Standard 135-2024, Annex A (PICS template), Annex K (BIBBs),
  Annex L (device profiles), Clause 12 (object types).
- [README.md](../README.md) - what this example is and how to build it.
- [TUTORIAL.md](../TUTORIAL.md) - how to extend it, and how to keep this
  document honest when you do.
