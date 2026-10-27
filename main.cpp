// SPDX-License-Identifier: CC0-1.0
// Public-domain example code (CC0) - see LICENSE. The CAS BACnet Stack itself is
// a separate, commercially licensed product and is not covered by CC0.
// =============================================================================
// BACnet Profile Example - B-LS (BACnet Lighting Supervisor) - C++
//
// This example implements the BACnet "B-LS" (Lighting Supervisor) profile with
// the CAS BACnet Stack. It is seeded from the B-LD (Lighting Device) example -
// same base objects, same Lighting Output "Jade" - plus the three features that
// make a device a SUPERVISOR rather than a single light: Channel (to fan a write
// out to several targets, including a remote device), WriteGroup (the service a
// lighting system uses to command a whole scene at once), and Schedule/Calendar
// (to run a scene automatically, including writing to a remote device on a
// timer). This repo is the series' CANONICAL implementation of those three:
//
//     F-CHANNEL   - Channel object + AddObjectPropertyReferenceToChannel
//     F-EXTWRITE  - a remote (cross-device) object-property reference
//     F-SCHED-E   - a Schedule that executes a write (here, to Channel 1)
//
// ANSI/ASHRAE 135-2024 Annex L.11.1: "A B-LS is any device that implements
// Channel objects and optionally Lighting Output and/or Binary Lighting Output
// objects with the ability to forward channel writes to other BACnet devices."
// That forwarding - one WriteGroup reaching Jade AND device 389016, with
// Write_Status saying whether every write worked - is what tests/ proves.
// A B-LS must support:
//
//     DS-RP-B     - respond to ReadProperty requests,
//     DS-WP-A     - initiate WriteProperty requests (the A-side: the stack's
//                   WriteProperty to device 389016 when Channel 1 fans out),
//     DS-WP-B     - allow other devices to WriteProperty its objects,
//     DS-WG-E-B   - EXECUTE an incoming WriteGroup request (NEW - the defining
//                   BIBB): a client names a Group/Channel and this device fans
//                   the write out to every object in the matching Channel's
//                   List_Of_Object_Property_References.
//     DS-ALO-A    - initiate a write to another device's (lighting) output -
//                   satisfied by the same A-side WriteProperty as DS-WP-A.
//     SCHED-E-B   - EXECUTE a Schedule (NEW): a Schedule object drives a write,
//                   including to a remote device, on a time-of-day/exception basis.
//     DM-DDB-A/B  - initiate AND answer Who-Is/I-Am (the A-side is new: this
//                   device sends Who-Is itself to find the remote target - see
//                   the 'd' key),
//     DM-DOB-B    - answer Who-Has with I-Have   (handled by the stack),
//     DM-DCC-B    - respond to DeviceCommunicationControl,
//     DM-TS-B / DM-UTC-B - accept both local and UTC TimeSynchronization.
//
// It does NOT require COV, alarms, trending, or backup/restore, so this example
// leaves those off.
//
// HOW THE REMOTE WRITE ACTUALLY HAPPENS - READ THIS BEFORE COPYING THE PATTERN.
// Earlier revisions of the CAS BACnet Stack had a pair of exports,
// RegisterCallbackChannelSendWritePropertyToRemote and
// RegisterCallbackScheduleSendWritePropertyToRemote, that asked the APPLICATION
// to perform the outbound WriteProperty by hand. VERIFIED AGAINST THE PIN
// (submodules/cas-bacnet-stack/source/CASBACnetStackDLL.h, "Sprint 82" comment
// just above the debug-message section): both exports were REMOVED. The stack
// now does the remote write itself, automatically, via an internal resolver
// called the Device_Address_Binding (DAB): once AddObjectPropertyReferenceToChannel
// / AddScheduleObjectPropertyReference name a reference with refUseDeviceIdentifier
// = true and a remote refDeviceInstance, the stack fans a WriteGroup or a
// Schedule-driven write out to that remote device on its own, resolving its
// address from whatever I-Am traffic the DAB has seen (fed by a periodic
// Who-Is heartbeat AND by any Who-Is this application sends itself). THIS
// EXAMPLE DOES NOT REGISTER EITHER CALLBACK, because neither exists any more -
// registering a removed export would not compile. The 'd' key below sends a
// manual Who-Is so the DAB can resolve the remote device on demand, for the demo.
//
// The device keeps the same base objects as B-SS and adds a Lighting Output
// (from B-LD), a Channel, a Schedule, and a Calendar. Each object has a colour
// name (the convention shared across this example series):
//
//     Device 389017            "Chipkin Example B-LS"     (instance configurable with --deviceID,
//                                                          Object_Name with --deviceName)
//     Analog Input  1          "Bronze"      (REAL, degrees Celsius; read-only)
//     Binary Input  1          "Emerald"     (active / inactive; read-only)
//     Multi-State Input 1      "Hot Pink"    (state 1..3; read-only)
//     Analog Output 1          "Chartreuse"  (REAL setpoint; WRITABLE, commandable)
//     Binary Output 1          "Fuchsia"     (active / inactive; WRITABLE, commandable)
//     Multi-State Output 1     "Indigo"      (state 1..3; WRITABLE, commandable)
//     Lighting Output 1        "Jade"        (REAL 0-100%; WRITABLE, commandable)
//     Channel 1                "Garnet"      (BACnetChannelValue REAL; WRITABLE,
//                                             commandable - the F-CHANNEL addition;
//                                             fans WriteGroup out to Jade AND a
//                                             remote object - the F-EXTWRITE addition)
//     Schedule 1                "Saffron"     (writes Channel 1 on a timer - the
//                                             F-SCHED-E addition)
//     Calendar 1                "Cream"       (a real, independently-readable Calendar
//                                             object - see the Date_List note in
//                                             TODO.md for the one documented gap)
//     Network Port 1           "Vermilion"   (the BACnet/IP port - required)
//
// Output objects are COMMANDABLE: their Present_Value is driven by a 16-slot
// BACnet Priority_Array. A WriteProperty(Present_Value, value, priority) sets a
// slot; writing NULL relinquishes it; the stack reports the highest-priority
// non-null slot (or Relinquish_Default) as the effective Present_Value. The app
// stores the priority array (see the Commandable struct below) and serves it; the
// stack computes Present_Value from it. Channel 1 uses this SAME mechanism, but
// dispatched differently - see the F-CHANNEL section for the exact callback shape.
//
// To be a conformant BACnet device (Protocol_Revision 30) each object must
// expose its full set of REQUIRED properties. Most are generated by the stack
// (Object_Identifier, Object_Type, Status_Flags, Object_List, Protocol_*).
// Event_State is NOT generated - with no alarming configured it simply reads its
// datatype default of normal(0), correct by coincidence, not because the stack
// computes it. The handful that the application must supply are served by the
// Get*Property callbacks below, and a few are turned on with SetPropertyEnabled.
//
// Interactive keys (handled by the shared helper): h = help, q = quit,
// up/down = nudge Analog Input 1 by +/-1.1, w = manually fire a demo WriteGroup
// (writes Channel 1, which fans out to Jade + the remote reference), d = send a
// demo Who-Is so the DAB can resolve the remote device by address (F-EXTWRITE).
// Command line: --port <n>, --deviceID <n>, --deviceName <text>, --xml.
//
// All the UDP/stack plumbing lives in common/CASExampleHelper so this file can
// stay focused on the BACnet logic.
// =============================================================================

#include "CASExampleHelper.h"
#include "CASBACnetStackExampleConstants.h"
#include "CASBACnetStackAdapter.h" // the CAS BACnet Stack C API (BACnetStack_*); call
                                    // LoadBACnetFunctions() before any BACnetStack_* call -
                                    // see the top of main() below.
#include "CASBACnetStackPackHelpers.h" // CASPropertyBuffer_* - packs the SendWriteProperty /
                                        // SendWriteGroup buffers for the 'w'/'d' demo keys below.

#include <chrono>  // the lighting engine's monotonic clock (section 1b)
#include <math.h>  // fabsf()
#include <stdio.h>
#include <string.h>
#include <string>
#include <time.h>  // F-TIMESYNC: InitSyncedDateTimeFromHost() seeds Local_Date/Local_Time

#if defined(_WIN32)
#include <windows.h> // Sleep()
#else
#include <unistd.h>  // usleep()
#endif

using namespace CASBACnetStackExampleConstants;

// -----------------------------------------------------------------------------
// 0. Lighting constants used only by this example
//
// The shared common/CASBACnetStackExampleConstants.h carries the values every
// example needs. The lighting values below are specific to this profile, so they
// live here - same style, citing the stack header that owns the full enumeration.
// -----------------------------------------------------------------------------

// -- Lighting Output object type (Object_Type enumeration) -------------------
//    Full list: submodules/cas-bacnet-stack/source/BACnetObjectType.h
static const uint16_t OBJECT_TYPE_LIGHTING_OUTPUT = 54;

// -- F-CHANNEL / F-SCHED-E object types - specific to THIS profile, so declared
//    here rather than in the series-wide common/CASBACnetStackExampleConstants.h
//    (verified against submodules/cas-bacnet-stack/source/BACnetObjectType.h at
//    the pin: calendar = 6, channel = 53, schedule = 17).
static const uint16_t OBJECT_TYPE_CALENDAR = 6;
static const uint16_t OBJECT_TYPE_CHANNEL = 53;
static const uint16_t OBJECT_TYPE_SCHEDULE = 17;

// -- WriteGroup service (Services_Supported enumeration) - specific to this
//    profile. Verified against source/BACnetServicesSupported.h at the pin.
static const uint32_t SERVICE_WRITE_GROUP = 40;

// -- Channel property identifiers not already in the series-wide constants ---
//    Full list: submodules/cas-bacnet-stack/source/BACnetPropertyIdentifier.h
static const uint32_t PROPERTY_IDENTIFIER_CHANNEL_NUMBER = 366;
static const uint32_t PROPERTY_IDENTIFIER_CONTROL_GROUPS = 367;
static const uint32_t PROPERTY_IDENTIFIER_LAST_PRIORITY = 369;
static const uint32_t PROPERTY_IDENTIFIER_WRITE_STATUS = 370;

// -- Lighting Output property identifiers (Property_Identifier enumeration) ---
//    Full list: submodules/cas-bacnet-stack/source/BACnetPropertyIdentifier.h
static const uint32_t PROPERTY_IDENTIFIER_TRACKING_VALUE = 164;
static const uint32_t PROPERTY_IDENTIFIER_BLINK_WARN_ENABLE = 373;
static const uint32_t PROPERTY_IDENTIFIER_DEFAULT_FADE_TIME = 374;
static const uint32_t PROPERTY_IDENTIFIER_DEFAULT_RAMP_RATE = 375;
static const uint32_t PROPERTY_IDENTIFIER_DEFAULT_STEP_INCREMENT = 376;
static const uint32_t PROPERTY_IDENTIFIER_EGRESS_TIME = 377;
static const uint32_t PROPERTY_IDENTIFIER_IN_PROGRESS = 378;
static const uint32_t PROPERTY_IDENTIFIER_LIGHTING_COMMAND = 380;
static const uint32_t PROPERTY_IDENTIFIER_LIGHTING_COMMAND_DEFAULT_PRIORITY = 381;
static const uint32_t PROPERTY_IDENTIFIER_EGRESS_ACTIVE = 386;
static const uint32_t PROPERTY_IDENTIFIER_DEFAULT_ON_VALUE = 4194341; // cl. 21: default-on-value (4194341)
static const uint32_t PROPERTY_IDENTIFIER_LAST_ON_VALUE = 4194342;    // cl. 21: last-on-value (4194342)

// -- BACnetLightingOperation - what a Lighting_Command tells the light to DO --
//    Full list: submodules/cas-bacnet-stack/source/BACnetLightingOperation.h
static const uint32_t LIGHTING_OPERATION_NONE = 0;
static const uint32_t LIGHTING_OPERATION_FADE_TO = 1;
static const uint32_t LIGHTING_OPERATION_RAMP_TO = 2;
static const uint32_t LIGHTING_OPERATION_STEP_UP = 3;
static const uint32_t LIGHTING_OPERATION_STEP_DOWN = 4;
static const uint32_t LIGHTING_OPERATION_STEP_ON = 5;
static const uint32_t LIGHTING_OPERATION_STEP_OFF = 6;
static const uint32_t LIGHTING_OPERATION_WARN = 7;
static const uint32_t LIGHTING_OPERATION_WARN_OFF = 8;
static const uint32_t LIGHTING_OPERATION_WARN_RELINQUISH = 9;
static const uint32_t LIGHTING_OPERATION_STOP = 10;
static const uint32_t LIGHTING_OPERATION_RESTORE_ON = 11;
static const uint32_t LIGHTING_OPERATION_DEFAULT_ON = 12;
static const uint32_t LIGHTING_OPERATION_TOGGLE_RESTORE = 13;
static const uint32_t LIGHTING_OPERATION_TOGGLE_DEFAULT = 14;

// -- BACnetLightingInProgress - what the light is doing right now -------------
//    Full list: submodules/cas-bacnet-stack/source/BACnetLightingInProgress.h
static const uint32_t LIGHTING_IN_PROGRESS_IDLE = 0;
static const uint32_t LIGHTING_IN_PROGRESS_FADE_ACTIVE = 1;
static const uint32_t LIGHTING_IN_PROGRESS_RAMP_ACTIVE = 2;

// -- The Lighting Output's ranges (cl. 12.54.4, 12.54.16 - 12.54.18) -----------
static const float LIGHTING_LEVEL_MIN = 0.0f;
static const float LIGHTING_LEVEL_MAX = 100.0f;
static const float LIGHTING_LEVEL_DIMMEST = 1.0f;          // the lowest "on" level (cl. 12.54.4)
static const uint32_t LIGHTING_FADE_TIME_MIN = 100;         // ms
static const uint32_t LIGHTING_FADE_TIME_MAX = 86400000;    // ms (1 day)
static const float LIGHTING_RAMP_RATE_MIN = 0.1f;           // % per second
static const float LIGHTING_RAMP_RATE_MAX = 100.0f;
static const float LIGHTING_STEP_INCREMENT_MIN = 0.1f;      // %
static const float LIGHTING_STEP_INCREMENT_MAX = 100.0f;

// NOTE: ENGINEERING_UNITS_PERCENT and SERVICE_TIME_SYNCHRONIZATION are declared
// in common/CASBACnetStackExampleConstants.h, the series-wide union - declaring
// them here as well would be an ambiguous symbol. Only values genuinely specific
// to THIS profile belong in this block.

// -----------------------------------------------------------------------------
// 1. Example + device configuration
// -----------------------------------------------------------------------------
static const char* APP_NAME = "BACnet B-LS (Lighting Supervisor) Example - C++";
static const char* APP_VERSION = "1.3.0";

// The device instance. BACnet requires this to be configurable, so it defaults
// to 389017 and can be overridden on the command line with --deviceID. Keep it
// configurable in your product: it must be unique across the internetwork.
static uint32_t g_deviceInstance = 389017;

// The remote device this example writes to, for F-EXTWRITE: Channel 1 (Garnet)
// carries a reference to an object on this device. In the Wire Tests it is a
// Python Peer (tests/channel_fanout_test.py). On a real network it is any device
// 389016 with a Lighting Output 1 - a BACnetProfileExample-B-LD-CPP instance is
// the natural target (389016 is its default instance) - on the SAME subnet and
// UDP port: a BACnet/IP network is the devices sharing one UDP port, so a device
// on another port never hears this one's Who-Is. This example's DAB
// (Device_Address_Binding - see the header comment above) resolves its address
// once it sees an I-Am: the answer to the DAB's own Who-Is at start-up, or to
// the 'd' (DiscoverRemote) key's manual one.
static const uint32_t REMOTE_DEVICE_INSTANCE = 389016; // B-LD's device instance
static const uint16_t REMOTE_OBJECT_TYPE = 54;          // OBJECT_TYPE_LIGHTING_OUTPUT
static const uint32_t REMOTE_OBJECT_INSTANCE = 1;        // B-LD's Lighting Output 1 (Jade)

// ---- Device identity: CHANGE ALL OF THIS BEFORE YOU SHIP --------------------
// Everything in this block is read by clients and shown to the operator in every
// discovery tool on the network. Left as-is, your product will appear on a real
// site announcing itself as a Chipkin demo. None of it is cosmetic:
// Object_Name must be unique across the BACnet internetwork, and Model_Name /
// Vendor_Identifier are what a building operator uses to identify your device.
//
// This block is the ship checklist. Every constant below has a note saying what
// to change it to; nothing here is safe to leave at its example value.
// -----------------------------------------------------------------------------

// Your BACnet Vendor Identifier. 389 = Chipkin Automation Systems; change this
// to YOUR company's vendor ID before shipping a product. Vendor IDs are assigned
// by ASHRAE - request one (free) at https://bacnet.org/assigned-vendor-ids/.
// Update VENDOR_NAME below to match.
static const uint32_t VENDOR_IDENTIFIER = 389;

// The Device object's Object_Name - the DEFAULT one.
//
// THIS IS THE ONE THAT WILL BITE YOU. Object_Name must be unique across the
// whole BACnet internetwork (cl. 12.1.1.4): two units that both announce
// "Chipkin Example B-LS" are a spec violation, and nothing on the wire flags
// it. So it must be per-unit configurable, exactly like the instance: this
// example takes it at start-up with --deviceName <text> (common/
// ParseDeviceNameArg, read into g_deviceName in main()); DEVICE_NAME is only
// what a unit announces when nobody configured it. In your product, configure
// the name per unit (a serial number, DIP switches, a config file, or this
// argument) and change the default below to something that says "not
// configured yet".
static const char* DEVICE_NAME = "Chipkin Example B-LS";
static const char* g_deviceName = DEVICE_NAME; // --deviceName, or the default

// The Device object's Description. Change it to what YOUR device actually is;
// this string describes this tutorial and its Channel/Schedule fan-out. Keep it
// under 255 characters: the stack holds at most 255 octets from a callback and
// refuses a longer value, so the property would read as "" (it did, at 270).
static const char* DEVICE_DESCRIPTION =
    "Chipkin CAS BACnet Stack Example - B-LS (Lighting Supervisor) profile. A Channel object "
    "fans an incoming WriteGroup out to a local Lighting Output and a remote device's "
    "light, and a Schedule writes the Channel on a timer.";

// Device identity strings (read by clients, and used to populate I-Am).
//   VENDOR_NAME - your company name; it must match VENDOR_IDENTIFIER above.
//   MODEL_NAME  - your model designation. This is what a building operator reads
//                 to identify your device in a discovery tool.
static const char* VENDOR_NAME = "Chipkin Automation Systems";
static const char* MODEL_NAME = "CAS BACnet Stack Example - B-LS";

// DeviceCommunicationControl password. A management station may include a password
// with a DeviceCommunicationControl (or ReinitializeDevice) request; the device
// accepts the command only if it matches. Set to NULL/empty to accept any request
// (no password required). Change this to your device's secret before shipping -
// it crosses the wire in PLAINTEXT, so treat it as a guard against accidents,
// not a security boundary.
static const char* DCC_PASSWORD = "";  // "" = no password required

// Application_Software_Version (12) is just APP_VERSION - one source of
// truth, so it can never drift from what --version/the startup banner
// prints (it did drift: this used to be a separate hardcoded "1.0.0"
// constant nobody updated across patch releases).
//
// Firmware_Revision (44) is meant to name the underlying platform/stack,
// not this example's own version - built at runtime from the CAS BACnet
// Stack's own BACnetStack_GetAPIMajorVersion()/etc. (the same 4 calls
// common/CASExampleHelper.cpp's PrintVersion() already uses for the
// startup banner's "CAS BACnet Stack version: X.Y.Z.W" line), so it can
// never go stale either - see g_firmwareRevision below, populated once
// right after LoadBACnetFunctions() succeeds (those functions are what
// the version getters themselves are, so they must be loaded first).
static std::string g_firmwareRevision;

// The sensor objects (all instance 1) and their colour names.
static const uint32_t ANALOG_INPUT_INSTANCE = 1;       // "Bronze"
static const uint32_t BINARY_INPUT_INSTANCE = 1;       // "Emerald"
static const uint32_t MULTI_STATE_INPUT_INSTANCE = 1;  // "Hot Pink"
static const uint32_t MULTI_STATE_INPUT_NUMBER_OF_STATES = 3;

// The Network Port object - every BACnet device must have one. It represents
// the BACnet/IP port this device communicates on.
static const uint32_t NETWORK_PORT_INSTANCE = 1;       // "Vermilion"
static const uint32_t MAX_APDU_LENGTH = 1476;          // BACnet/IP APDU length

// BACnet/IP addressing the Network Port reports. The IP address and subnet mask
// are filled in at start-up from the host's primary interface; the gateway is
// left unset (0.0.0.0) for this example. The stack also uses IP_Address +
// BACnet_IP_UDP_Port to build the port's MAC_Address automatically.
static uint8_t g_ipAddress[4] = { 0, 0, 0, 0 };
static uint8_t g_ipSubnetMask[4] = { 0, 0, 0, 0 };
static uint8_t g_ipDefaultGateway[4] = { 0, 0, 0, 0 };
static uint16_t g_bacnetIpUdpPort = 47808;

// Analog Input 1's live present value (degrees Celsius). Starts at 21.5 and is
// nudged by the up/down arrow keys. A real sensor would update this from
// hardware instead.
static float g_analogInput1Value = 21.5f;

// The commandable OUTPUT objects (all instance 1) and their colour names. These
// are what make this a B-SA actuator: clients drive them with WriteProperty.
static const uint32_t ANALOG_OUTPUT_INSTANCE = 1;        // "Chartreuse"
static const uint32_t BINARY_OUTPUT_INSTANCE = 1;        // "Fuchsia"
static const uint32_t MULTI_STATE_OUTPUT_INSTANCE = 1;   // "Indigo"
static const uint32_t MULTI_STATE_OUTPUT_NUMBER_OF_STATES = 3;
static const uint32_t BACNET_PRIORITY_ARRAY_SIZE = 16;

// A BACnet commandable value: a 16-slot Priority_Array plus a Relinquish_Default.
// Each slot is either null (relinquished) or holds a commanded value. A real
// device would map the resolved Present_Value onto its physical output; here we
// just store the commands. The values are kept as double and cast per object
// type (REAL for AO, 0/1 for BO, state number for MSO).
struct Commandable {
    bool isSet[16];          // is slot i (1..16) commanded?
    double value[16];        // the commanded value at slot i
    double relinquishDefault; // used when every slot is null
};

// The { { false }, { 0 }, default } initializer zero-fills all 16 slots of isSet
// and value (C++ aggregate rules: the remaining elements are value-initialized),
// so every priority slot starts null and Present_Value reports relinquishDefault.
static Commandable g_analogOutput = { { false }, { 0 }, 20.0 }; // setpoint, default 20.0 C
static Commandable g_binaryOutput = { { false }, { 0 }, 0.0 };  // default inactive (0)
static Commandable g_multiStateOutput = { { false }, { 0 }, 1.0 }; // default state 1

// --- The Lighting Output (the B-LD addition) ---------------------------------
static const uint32_t LIGHTING_OUTPUT_INSTANCE = 1;      // "Jade"

// Its Present_Value is commandable exactly like the Analog Output above - a level
// in percent. Relinquish_Default 0.0 means "when nothing commands this light, it
// is off", which is the safe resting state for a luminaire.
static Commandable g_lightingOutput = { { false }, { 0 }, 0.0 };

// The Lighting Output's configuration properties (cl. 12.54.13 - 12.54.18,
// 12.54.27, 12.54.45). The four marked WRITABLE accept WriteProperty, range
// checked as the clause says, so a lighting system - or a Wire Test - can tune
// them:
//   Default_Fade_Time        - ms a fadeTo takes when it omits fade-time   (WRITABLE)
//   Default_Ramp_Rate        - % per second a rampTo omitting ramp-rate uses (WRITABLE)
//   Default_Step_Increment   - % a step omitting step-increment uses       (WRITABLE)
//   Egress_Time              - SECONDS a warnRelinquish / warnOff holds the
//                              light before it goes                        (WRITABLE)
//   Blink_Warn_Enable        - whether a warn blinks and waits (TRUE here)
//   Default_On_Value         - the level a defaultOn command writes
//   Lighting_Command_Default_Priority - the priority a Lighting_Command writes at
//                              when it does not name one (BACnet default is 16)
static uint32_t g_defaultFadeTime = 3000;        // 3.0 s, in milliseconds
static float g_defaultRampRate = 10.0f;          // 10 % per second
static float g_defaultStepIncrement = 5.0f;      // 5 %
static uint32_t g_egressTime = 30;               // 30 s
static const bool LIGHTING_BLINK_WARN_ENABLE = true;
static const float LIGHTING_DEFAULT_ON_VALUE = 100.0f;
static const uint32_t LIGHTING_COMMAND_DEFAULT_PRIORITY = 16;

// --- Channel 1 "Garnet" (F-CHANNEL / DS-WG-E-B) -------------------------------
// Its Present_Value is commandable exactly like the other outputs above - see
// the F-CHANNEL section below for why its GET/SET dispatch looks different.
static const uint32_t CHANNEL_INSTANCE = 1;              // "Garnet"
static Commandable g_channel = { { false }, { 0 }, 0.0 }; // default off (0.0)

// Channel_Number and Control_Groups are REQUIRED *and writable* on a Channel,
// and (per BACnetStack_AddChannelObject's doc) the WriteGroup service reads
// them back through our own callbacks to decide whether THIS Channel matches an
// incoming WriteGroup request. One group is enough for this demo.
static uint16_t g_channelNumber = 1;
static uint32_t g_channelControlGroups[1] = { 1 };
static const uint32_t CHANNEL_CONTROL_GROUPS_COUNT = 1;

// Last_Priority: the priority the most recent successful write to Channel 1
// landed at. Updated in SetPropertyReal / SetPropertyNull below. cl. 12.53.6:
// "The initial value of Last_Priority shall be 16."
static uint32_t g_channelLastPriority = 16;

// Write_Status (cl. 12.53.7), BACnetWriteStatus. The stack does not keep it: it
// performs the Channel's writes to its members and tells this application how
// each one went (the Set callbacks for the local member, the SimpleACK / Error /
// Reject / Abort / Timeout hooks for the remote one), so the application keeps
// it - see section 2e.
static const uint32_t WRITE_STATUS_IDLE = 0;
static const uint32_t WRITE_STATUS_IN_PROGRESS = 1;
static const uint32_t WRITE_STATUS_SUCCESSFUL = 2;
static const uint32_t WRITE_STATUS_FAILED = 3;
static uint32_t g_channelWriteStatus = WRITE_STATUS_IDLE; // "shall be set to IDLE initially"

// cl. 12.53.5: a WriteProperty of Present_Value while Write_Status is IN_PROGRESS
// "shall cause a Result(-) ... 'Error Class' of OBJECT and an 'Error Code' of BUSY".
// Verified against source/BACnetErrorCode.h at the pin: busy (82).
static const uint32_t ERROR_CODE_BUSY = 82;

// --- Schedule 1 "Saffron" and Calendar 1 "Cream" (F-SCHED-E) ------------------
static const uint32_t SCHEDULE_INSTANCE = 1;  // "Saffron"
static const uint32_t CALENDAR_INSTANCE = 1;  // "Cream"

// The last Lighting_Command a client wrote. "The Lighting_Command property shall
// indicate the last written value or NONE if it has not yet been written"
// (cl. 12.54.6), so we remember it, including which optional fields it carried.
// The light's behaviour - the fade, ramp, step or warn it describes - is the
// Lighting Output engine's (section 1b).
struct LightingCommandState {
    uint32_t operation;
    bool useTargetLevel;   float targetLevel;
    bool useRampRate;      float rampRate;
    bool useStepIncrement; float stepIncrement;
    bool useFadeTime;      uint32_t fadeTime;
    bool usePriority;      uint32_t priority;
};

// Starts as `none` - the light has not been commanded yet. `none` is a real
// BACnetLightingOperation value (0), not a placeholder: it is what a Lighting
// Output reports before anything has driven it.
static LightingCommandState g_lightingCommand = {
    LIGHTING_OPERATION_NONE,
    false, 0.0f, false, 0.0f, false, 0.0f, false, 0, false, 0
};

// A WriteProperty to a commandable Present_Value carries a priority 1..16. When a
// client omits it, BACnet uses 16 (the lowest priority) - so normalise anything
// out of range to 16, matching the stack's own behaviour.
static uint8_t EffectivePriority(uint8_t priority) {
    return (priority >= 1 && priority <= BACNET_PRIORITY_ARRAY_SIZE) ? priority : 16;
}

// Store a commanded value at a priority slot (a WriteProperty of a value).
static void CommandWrite(Commandable* c, uint8_t priority, double value) {
    const uint8_t p = EffectivePriority(priority);
    c->isSet[p - 1] = true;
    c->value[p - 1] = value;
}

// Relinquish (clear) a priority slot - i.e. a WriteProperty of NULL.
static void CommandRelinquish(Commandable* c, uint8_t priority) {
    const uint8_t p = EffectivePriority(priority);
    c->isSet[p - 1] = false;
}

// Resolve which Commandable an (objectType, objectInstance) maps to, or NULL.
static Commandable* GetCommandable(uint16_t objectType, uint32_t objectInstance) {
    if (objectType == OBJECT_TYPE_ANALOG_OUTPUT && objectInstance == ANALOG_OUTPUT_INSTANCE) {
        return &g_analogOutput;
    }
    if (objectType == OBJECT_TYPE_BINARY_OUTPUT && objectInstance == BINARY_OUTPUT_INSTANCE) {
        return &g_binaryOutput;
    }
    if (objectType == OBJECT_TYPE_MULTI_STATE_OUTPUT && objectInstance == MULTI_STATE_OUTPUT_INSTANCE) {
        return &g_multiStateOutput;
    }
    // The Lighting Output is commandable in exactly the same way as the Analog
    // Output - a REAL level resolved from the Priority_Array. Adding it here is all
    // it takes to give it the whole commandable mechanism.
    if (objectType == OBJECT_TYPE_LIGHTING_OUTPUT && objectInstance == LIGHTING_OUTPUT_INSTANCE) {
        return &g_lightingOutput;
    }
    // F-CHANNEL: Channel 1's Present_Value is ALSO a REAL resolved from a
    // Priority_Array the application holds - see BACnetStack_AddChannelObject's
    // doc. The GET side reads through this exact same
    // GetCommandable()+ReadPrioritySlot() mechanism as every other commandable
    // object; the SET side has its own arm in SetPropertyReal / SetPropertyNull
    // below (two dispatch shapes, Write_Status, BUSY).
    if (objectType == OBJECT_TYPE_CHANNEL && objectInstance == CHANNEL_INSTANCE) {
        return &g_channel;
    }
    return NULL;
}

// The priority Present_Value is taken from - Current_Command_Priority (cl. 12.54.39)
// - or 0 when every slot is null and Present_Value is Relinquish_Default. The
// stack serves the property itself from the same slots; the engine needs it too.
static uint8_t CurrentCommandPriority(const Commandable* c) {
    for (uint8_t slotPriority = 1; slotPriority <= BACNET_PRIORITY_ARRAY_SIZE; slotPriority++) {
        if (c->isSet[slotPriority - 1]) {
            return slotPriority;
        }
    }
    return 0;
}

// Present_Value, resolved the way the stack does: the highest-priority commanded
// slot, else Relinquish_Default. `skippedPriority` (1..16) leaves one slot out -
// "what would Present_Value be if this slot were relinquished?" (warnRelinquish
// asks that); pass 0 to skip nothing.
static float ResolveLightingLevel(const Commandable* c, uint8_t skippedPriority = 0) {
    for (uint8_t slotPriority = 1; slotPriority <= BACNET_PRIORITY_ARRAY_SIZE; slotPriority++) {
        if (slotPriority != skippedPriority && c->isSet[slotPriority - 1]) {
            return (float)c->value[slotPriority - 1];
        }
    }
    return (float)c->relinquishDefault;
}

// A human-readable name for a BACnetLightingOperation, for the console log.
static const char* LightingOperationName(uint32_t operation) {
    switch (operation) {
        case LIGHTING_OPERATION_NONE:            return "none";
        case LIGHTING_OPERATION_FADE_TO:         return "fadeTo";
        case LIGHTING_OPERATION_RAMP_TO:         return "rampTo";
        case LIGHTING_OPERATION_STEP_UP:         return "stepUp";
        case LIGHTING_OPERATION_STEP_DOWN:       return "stepDown";
        case LIGHTING_OPERATION_STEP_ON:         return "stepOn";
        case LIGHTING_OPERATION_STEP_OFF:        return "stepOff";
        case LIGHTING_OPERATION_WARN:            return "warn";
        case LIGHTING_OPERATION_WARN_OFF:        return "warnOff";
        case LIGHTING_OPERATION_WARN_RELINQUISH: return "warnRelinquish";
        case LIGHTING_OPERATION_STOP:            return "stop";
        case LIGHTING_OPERATION_RESTORE_ON:      return "restoreOn";
        case LIGHTING_OPERATION_DEFAULT_ON:      return "defaultOn";
        case LIGHTING_OPERATION_TOGGLE_RESTORE:  return "toggleRestore";
        case LIGHTING_OPERATION_TOGGLE_DEFAULT:  return "toggleDefault";
        default:                                 return "(proprietary)";
    }
}

// Is this read a single Priority_Array element (Priority_Array[1..16])? If so,
// report whether that slot is commanded (*slotIsSet) and its value (*slotValue).
// The typed Get callbacks use this to serve a commandable object's Priority_Array
// and to let the stack compute Present_Value from the highest non-null slot.
static bool ReadPrioritySlot(const Commandable* c, uint32_t propertyIdentifier,
                             bool useArrayIndex, uint32_t propertyArrayIndex,
                             bool* slotIsSet, double* slotValue) {
    if (propertyIdentifier != PROPERTY_IDENTIFIER_PRIORITY_ARRAY || !useArrayIndex ||
        propertyArrayIndex < 1 || propertyArrayIndex > BACNET_PRIORITY_ARRAY_SIZE) {
        return false;
    }
    *slotIsSet = c->isSet[propertyArrayIndex - 1];
    *slotValue = c->value[propertyArrayIndex - 1];
    return true;
}

// -----------------------------------------------------------------------------
// 1b. The Lighting Output engine - real BACnet behaviour (cl. 12.54)
//
// Everything a client can observe about HOW the light gets to its level lives
// here: Tracking_Value, In_Progress, Egress_Active, Last_On_Value, and the
// Priority_Array writes that fades, steps and warns make over time.
//
//   Present_Value  = the TARGET (the stack resolves it from the Priority_Array).
//   Tracking_Value = "the value at which the physical lighting output is being
//                    controlled ... at all times" (cl. 12.54.5). Equal to
//                    Present_Value whenever In_Progress is IDLE; mid-fade or
//                    mid-ramp it is "the current calculated value of the ramp or
//                    fade algorithm".
//
// "There may only be one lighting command currently in progress at any time"
// (cl. 12.54.6.1), so one struct holds it: a fade, a ramp, or a warn's egress
// timer, and the priority slot it belongs to.
//
// Ported unchanged from BACnetProfileExample-B-LD-CPP (its section 1b), the
// series' reference Lighting Output. ON REAL HARDWARE: keep this engine and feed
// g_engine.trackingValue to your dimming driver; SimulationBlinkWarn below is the
// one line that stands in for hardware.
//
// On this supervisor Jade is also a member of Channel 1: a Channel write, a
// WriteGroup and Schedule 1 reach it through the same Present_Value write
// (SetPropertyReal / SetPropertyNull), so they halt a fade the same way.
// -----------------------------------------------------------------------------
enum class CommandInProgress {
    None,             // nothing running: Tracking_Value == Present_Value
    Fade,             // FADE_TO: proportional over a fade time
    Ramp,             // RAMP_TO: fixed rate in percent per second
    EgressRelinquish, // WARN_RELINQUISH: hold for Egress_Time, then relinquish
    EgressOff         // WARN_OFF: hold for Egress_Time, then write 0.0%
};

struct LightingEngine {
    float trackingValue;               // Tracking_Value
    CommandInProgress command;         // what is running, if anything
    uint8_t commandPriority;           // the Priority_Array slot it belongs to
    float startLevel;                  // fade/ramp: Tracking_Value when it began
    float targetLevel;                 // fade/ramp: where it is going
    uint64_t startMilliseconds;        // fade/ramp: when it began
    uint32_t fadeTimeMilliseconds;     // fade: how long it takes
    float rampRatePercentPerSecond;    // ramp: how fast it moves
    uint64_t egressDeadlineMilliseconds; // warn: when the egress time runs out
    float lastOnValue;                 // Last_On_Value (cl. 12.54.44)
};
// Last_On_Value is 100.0 until Present_Value has ever been >= 1.0 (cl. 12.54.44).
static LightingEngine g_engine = { 0.0f, CommandInProgress::None, 0, 0.0f, 0.0f, 0, 0, 0.0f, 0, 100.0f };

// A monotonic millisecond clock: fades must not jump when the wall clock is set
// (a TimeSynchronization is exactly the kind of thing that sets it).
static uint64_t NowMilliseconds() {
    return (uint64_t)std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}

// In_Progress (cl. 12.54.7, Table 12-68). A warn's egress time is NOT one of the
// listed processes: during it the light is held at Present_Value, so it is IDLE.
static uint32_t LightingInProgress() {
    switch (g_engine.command) {
        case CommandInProgress::Fade: return LIGHTING_IN_PROGRESS_FADE_ACTIVE;
        case CommandInProgress::Ramp: return LIGHTING_IN_PROGRESS_RAMP_ACTIVE;
        default:                      return LIGHTING_IN_PROGRESS_IDLE;
    }
}

// Egress_Active (cl. 12.54.15): TRUE while a warnRelinquish / warnOff egress
// timer is running.
static bool LightingEgressActive() {
    return g_engine.command == CommandInProgress::EgressRelinquish ||
           g_engine.command == CommandInProgress::EgressOff;
}

// Last_On_Value: "the last value of the Present_Value property that was greater
// than or equal to 1.0%" (cl. 12.54.44). Called after every change.
static void UpdateLastOnValue() {
    const float presentValue = ResolveLightingLevel(&g_lightingOutput);
    if (presentValue >= LIGHTING_LEVEL_DIMMEST) {
        g_engine.lastOnValue = presentValue;
    }
}

// Present_Value writes "at a value greater than 0.0% but less than 1.0% shall be
// clamped to 1.0%" (cl. 12.54.4). Lighting commands that write a level go through
// the same Present_Value, so they are clamped the same way.
static float ClampToDimmest(float level) {
    return (level > LIGHTING_LEVEL_MIN && level < LIGHTING_LEVEL_DIMMEST) ? LIGHTING_LEVEL_DIMMEST : level;
}

// Write a level at a priority slot and keep Last_On_Value current.
static void WriteLightingLevel(uint8_t priority, float level) {
    CommandWrite(&g_lightingOutput, priority, (double)ClampToDimmest(level));
    UpdateLastOnValue();
}

// Halt the command in progress, with the effect cl. 12.54.6.1 gives each kind:
//   "When a RAMP_TO or FADE_TO command that is currently in progress is halted, the
//    internal ramp or fade algorithm is halted, and the corresponding slot in the
//    priority array remains unchanged."
//   "When a WARN_RELINQUISH command that is currently in progress is halted, the
//    blink-warn egress timer is immediately expired, and the corresponding value of
//    the priority array is relinquished."
//   "When a WARN_OFF command that is currently in progress is halted, the egress
//    timer is immediately expired, and the value 0.0% is written to the priority
//    array at the specified priority."
static void HaltCommandInProgress(const char* reason) {
    switch (g_engine.command) {
        case CommandInProgress::Fade:
        case CommandInProgress::Ramp:
            printf("Lighting: %s at priority %u halted at %.1f%% (%s)\n",
                   g_engine.command == CommandInProgress::Fade ? "fade" : "ramp",
                   g_engine.commandPriority, g_engine.trackingValue, reason);
            break;
        case CommandInProgress::EgressRelinquish:
            CommandRelinquish(&g_lightingOutput, g_engine.commandPriority);
            printf("Lighting: egress timer at priority %u expired early - relinquished (%s)\n",
                   g_engine.commandPriority, reason);
            break;
        case CommandInProgress::EgressOff:
            WriteLightingLevel(g_engine.commandPriority, 0.0f);
            printf("Lighting: egress timer at priority %u expired early - 0.0%% written (%s)\n",
                   g_engine.commandPriority, reason);
            break;
        case CommandInProgress::None:
        default:
            return;
    }
    g_engine.command = CommandInProgress::None;
    UpdateLastOnValue();
}

// A write at `writePriority` halts the command in progress when it is at a higher
// priority (cl. 12.54.6.1 (a) and (b)) or at the same priority ("A lighting command
// that is in progress is implicitly halted when it is overwritten by another
// lighting command at the same priority or by a write to the Present_Value at the
// same priority"). A lower-priority write leaves it running.
static void HaltIfWriteOverrides(uint8_t writePriority, const char* reason) {
    if (g_engine.command != CommandInProgress::None && writePriority <= g_engine.commandPriority) {
        HaltCommandInProgress(reason);
    }
}

// Begin a fade or ramp from the current Tracking_Value to `targetLevel`.
static void StartTransition(CommandInProgress kind, uint8_t priority, float targetLevel,
                            uint32_t fadeTimeMilliseconds, float rampRatePercentPerSecond) {
    g_engine.command = kind;
    g_engine.commandPriority = priority;
    g_engine.startLevel = g_engine.trackingValue;
    g_engine.targetLevel = targetLevel;
    g_engine.startMilliseconds = NowMilliseconds();
    g_engine.fadeTimeMilliseconds = fadeTimeMilliseconds;
    g_engine.rampRatePercentPerSecond = rampRatePercentPerSecond;
}

// Begin a warnRelinquish / warnOff egress timer of Egress_Time seconds.
static void StartEgress(CommandInProgress kind, uint8_t priority) {
    g_engine.command = kind;
    g_engine.commandPriority = priority;
    g_engine.egressDeadlineMilliseconds = NowMilliseconds() + (uint64_t)g_egressTime * 1000;
}

// SIMULATION, not BACnet: on a PC there is no lamp to blink, so a blink-warn
// prints. ON REAL HARDWARE: flash the light here.
static void SimulationBlinkWarn(uint8_t priority) {
    printf("Simulation: the lamp blinks (blink-warn at priority %u)\n", priority);
}

// Run one lighting operation of Table 12-67 at `priority`. Shared by
// Lighting_Command writes (section 2c) and the Present_Value special values of
// Table 12-65 (section 2b), which "has the same effect as writing the
// corresponding lighting command". The command's parameters arrive already
// resolved (an omitted fade-time is Default_Fade_Time, and so on) and range
// checked. Returns false, with *errorCode, for an operation that must be refused.
static bool ExecuteLightingOperation(uint32_t operation, uint8_t priority, float targetLevel,
                                     uint32_t fadeTimeMilliseconds, float rampRatePercentPerSecond,
                                     float stepIncrement, uint32_t* errorCode) {
    if (operation == LIGHTING_OPERATION_NONE || operation > LIGHTING_OPERATION_TOGGLE_DEFAULT) {
        // NONE: "This operation shall not be written to the Lighting_Command
        // property. Attempts to write this operation ... shall cause a Result(-) ...
        // PROPERTY ... VALUE_OUT_OF_RANGE". Proprietary operations (256 and up) are
        // not implemented by this device, so it refuses them the same way.
        *errorCode = ERROR_CODE_VALUE_OUT_OF_RANGE;
        return false;
    }

    if (operation == LIGHTING_OPERATION_STOP) {
        // STOP "Stops any FADE_TO or RAMP_TO command in progress at the specified
        // priority and writes the current value of Tracking_Value to that slot in the
        // priority array and sets In_Progress to IDLE. Cancels any WARN_RELINQUISH or
        // WARN_OFF command in progress at the specified priority and cancels the
        // blink-warn egress timer. The value in the priority array at the specified
        // priority remains unchanged. If there is no fade, ramp, or warn command
        // currently executing at the specified priority, then this operation is
        // ignored." STOP is the one command that does NOT halt by priority (cl.
        // 12.54.6.1 (a) says "other than STOP").
        if (g_engine.command == CommandInProgress::None || g_engine.commandPriority != priority) {
            printf("Lighting_Command: stop @ priority %u - nothing running at that priority, ignored\n", priority);
            return true;
        }
        if (g_engine.command == CommandInProgress::Fade || g_engine.command == CommandInProgress::Ramp) {
            WriteLightingLevel(priority, g_engine.trackingValue);
            printf("Lighting_Command: stop @ priority %u - held at %.1f%%\n", priority, g_engine.trackingValue);
        } else {
            printf("Lighting_Command: stop @ priority %u - egress timer cancelled, level unchanged\n", priority);
        }
        g_engine.command = CommandInProgress::None;
        return true;
    }

    // Every other valid command halts a command in progress at a lower or equal
    // priority (cl. 12.54.6.1 (a), and the implicit same-priority halt).
    HaltIfWriteOverrides(priority, LightingOperationName(operation));

    const float trackingValue = g_engine.trackingValue;
    const float presentValue = ResolveLightingLevel(&g_lightingOutput);
    switch (operation) {
        case LIGHTING_OPERATION_FADE_TO:
        case LIGHTING_OPERATION_RAMP_TO: {
            // "The fade operation is implemented by first writing target-level to the
            // specified slot in the priority array then reevaluating the priority
            // array. After the reevaluation of the priority array, if the provided
            // priority is not the current command priority, this fade operation shall
            // not be executed. Otherwise, the fade operation continues by changing the
            // physical lighting output proportionally from its current value to
            // target-level, over a period of time defined by fade-time."
            //
            // RAMP_TO's row is written the same way but reads "if the provided
            // priority is NOT the current command priority, then the ramp operation
            // continues" - which would ramp the light while a higher priority holds
            // it, contradicting Present_Value's own rule (a ramp's target is the
            // level the light is going to). This example treats RAMP_TO exactly as
            // FADE_TO's row does.
            const bool isFade = (operation == LIGHTING_OPERATION_FADE_TO);
            WriteLightingLevel(priority, targetLevel);
            const float target = ClampToDimmest(targetLevel);
            if (CurrentCommandPriority(&g_lightingOutput) != priority) {
                printf("Lighting_Command: %s %.1f%% @ priority %u - written to the slot, not executed "
                       "(priority %u is in control)\n", LightingOperationName(operation), target, priority,
                       CurrentCommandPriority(&g_lightingOutput));
                break;
            }
            StartTransition(isFade ? CommandInProgress::Fade : CommandInProgress::Ramp, priority, target,
                            fadeTimeMilliseconds, rampRatePercentPerSecond);
            if (isFade) {
                printf("Lighting_Command: fadeTo %.1f%% over %u ms @ priority %u (from %.1f%%)\n",
                       target, fadeTimeMilliseconds, priority, trackingValue);
            } else {
                printf("Lighting_Command: rampTo %.1f%% at %.1f%%/s @ priority %u (from %.1f%%)\n",
                       target, rampRatePercentPerSecond, priority, trackingValue);
            }
            break;
        }
        case LIGHTING_OPERATION_STEP_UP:
        case LIGHTING_OPERATION_STEP_ON: {
            // STEP_UP: "writing the Tracking_Value plus step-increment to the specified
            // slot ... If the result of the addition is greater than 100.0%, the value
            // shall be set to 100.0%. If the starting level of Tracking_Value is 0.0%,
            // then this operation is ignored." STEP_ON: "Same as STEP_UP except when
            // Tracking_Value is 0.0%, in which case, 1.0% is written".
            if (trackingValue <= LIGHTING_LEVEL_MIN) {
                if (operation == LIGHTING_OPERATION_STEP_ON) {
                    WriteLightingLevel(priority, LIGHTING_LEVEL_DIMMEST);
                    printf("Lighting_Command: stepOn from off -> 1.0%% @ priority %u\n", priority);
                } else {
                    printf("Lighting_Command: stepUp ignored - the light is off\n");
                }
                break;
            }
            float next = trackingValue + stepIncrement;
            if (next > LIGHTING_LEVEL_MAX) { next = LIGHTING_LEVEL_MAX; }
            WriteLightingLevel(priority, next);
            printf("Lighting_Command: %s %.1f%% -> %.1f%% @ priority %u\n",
                   LightingOperationName(operation), stepIncrement, next, priority);
            break;
        }
        case LIGHTING_OPERATION_STEP_DOWN:
        case LIGHTING_OPERATION_STEP_OFF: {
            // STEP_DOWN: "writing the Tracking_Value minus step-increment ... If the
            // result of the subtraction is less than 1.0%, the value shall be set to
            // 1.0%. If the starting level of Tracking_Value is 0.0%, then this
            // operation is ignored." STEP_OFF: "Same as STEP_DOWN except when
            // Tracking_Value is 1.0%, in which case, 0.0% is written".
            if (trackingValue <= LIGHTING_LEVEL_MIN) {
                printf("Lighting_Command: %s ignored - the light is off\n", LightingOperationName(operation));
                break;
            }
            if (operation == LIGHTING_OPERATION_STEP_OFF && fabsf(trackingValue - LIGHTING_LEVEL_DIMMEST) < 0.001f) {
                WriteLightingLevel(priority, 0.0f);
                printf("Lighting_Command: stepOff from 1.0%% -> off @ priority %u\n", priority);
                break;
            }
            float next = trackingValue - stepIncrement;
            if (next < LIGHTING_LEVEL_DIMMEST) { next = LIGHTING_LEVEL_DIMMEST; }
            WriteLightingLevel(priority, next);
            printf("Lighting_Command: %s %.1f%% -> %.1f%% @ priority %u\n",
                   LightingOperationName(operation), stepIncrement, next, priority);
            break;
        }
        case LIGHTING_OPERATION_WARN:
            // "The blink-warn notification shall only occur if Blink_Warn_Enable is
            // TRUE, the Present_Value is not 0.0%, and the specified priority is the
            // current command priority." The level is unchanged either way.
            if (LIGHTING_BLINK_WARN_ENABLE && presentValue != 0.0f &&
                CurrentCommandPriority(&g_lightingOutput) == priority) {
                SimulationBlinkWarn(priority);
            } else {
                printf("Lighting_Command: warn @ priority %u - no blink (off, or not in control)\n", priority);
            }
            break;
        case LIGHTING_OPERATION_WARN_RELINQUISH:
            // "The blink-warn notification shall not occur, and the value at the
            // specified priority shall be relinquished immediately if any of the
            // following conditions occur: (a) Blink_Warn_Enable is FALSE, or (b) The
            // Present_Value is 0.0%, or (c) The Present_Value would not evaluate to
            // 0.0% after the priority slot is relinquished."
            if (!LIGHTING_BLINK_WARN_ENABLE || presentValue == 0.0f ||
                ResolveLightingLevel(&g_lightingOutput, priority) != 0.0f) {
                CommandRelinquish(&g_lightingOutput, priority);
                UpdateLastOnValue();
                printf("Lighting_Command: warnRelinquish @ priority %u - relinquished at once\n", priority);
                break;
            }
            SimulationBlinkWarn(priority);
            StartEgress(CommandInProgress::EgressRelinquish, priority);
            printf("Lighting_Command: warnRelinquish @ priority %u - holding %.1f%% for %u s (Egress_Active)\n",
                   priority, presentValue, g_egressTime);
            break;
        case LIGHTING_OPERATION_WARN_OFF:
            // "The blink-warn notification shall not occur and the value 0.0% shall be
            // written at the specified priority immediately if any of the following
            // conditions occur: (a) Blink_Warn_Enable is FALSE, or (b) The
            // Present_Value is 0.0%, or (c) The specified priority is not the current
            // command priority."
            if (!LIGHTING_BLINK_WARN_ENABLE || presentValue == 0.0f ||
                CurrentCommandPriority(&g_lightingOutput) != priority) {
                WriteLightingLevel(priority, 0.0f);
                printf("Lighting_Command: warnOff @ priority %u - 0.0%% written at once\n", priority);
                break;
            }
            SimulationBlinkWarn(priority);
            StartEgress(CommandInProgress::EgressOff, priority);
            printf("Lighting_Command: warnOff @ priority %u - holding %.1f%% for %u s (Egress_Active)\n",
                   priority, presentValue, g_egressTime);
            break;
        case LIGHTING_OPERATION_RESTORE_ON:
            // "writing the Last_On_Value to the specified slot in the priority array."
            WriteLightingLevel(priority, g_engine.lastOnValue);
            printf("Lighting_Command: restoreOn -> %.1f%% @ priority %u\n", g_engine.lastOnValue, priority);
            break;
        case LIGHTING_OPERATION_DEFAULT_ON:
            // "writing the Default_On_Value to the specified slot in the priority array."
            WriteLightingLevel(priority, LIGHTING_DEFAULT_ON_VALUE);
            printf("Lighting_Command: defaultOn -> %.1f%% @ priority %u\n", LIGHTING_DEFAULT_ON_VALUE, priority);
            break;
        case LIGHTING_OPERATION_TOGGLE_RESTORE:
        case LIGHTING_OPERATION_TOGGLE_DEFAULT: {
            // "If the priority is numerically higher than the current command priority,
            // then the command shall be considered successful, but the content of the
            // priority array shall not be modified." Otherwise off -> on (Last_On_Value
            // or Default_On_Value), on -> 0.0%. With every slot null, Relinquish_Default
            // is in control and any priority 1..16 is numerically lower than "17".
            const uint8_t controllingPriority = CurrentCommandPriority(&g_lightingOutput);
            if (controllingPriority != 0 && priority > controllingPriority) {
                printf("Lighting_Command: %s @ priority %u - priority %u is in control, no change\n",
                       LightingOperationName(operation), priority, controllingPriority);
                break;
            }
            const float onLevel = (operation == LIGHTING_OPERATION_TOGGLE_RESTORE) ? g_engine.lastOnValue
                                                                                   : LIGHTING_DEFAULT_ON_VALUE;
            const float next = (presentValue == 0.0f) ? onLevel : 0.0f;
            WriteLightingLevel(priority, next);
            printf("Lighting_Command: %s -> %.1f%% @ priority %u\n", LightingOperationName(operation), next, priority);
            break;
        }
        default:
            break;
    }
    return true;
}

// Advance the engine. Called from the main loop on every pass (every ~1 ms), so a
// fade moves smoothly; a slower tick only makes the steps coarser.
static void LightingTick() {
    const uint64_t now = NowMilliseconds();

    // A fade or ramp always belongs to the priority in control: every write that
    // could take control away from it halts it first (HaltIfWriteOverrides), as
    // cl. 12.54.6.1 requires. A new code path that writes the Priority_Array must
    // do the same.

    if (g_engine.command == CommandInProgress::Fade) {
        // "changing the physical lighting output proportionally from its current value
        // to target-level, over a period of time defined by fade-time."
        const uint64_t elapsed = now - g_engine.startMilliseconds;
        if (elapsed >= g_engine.fadeTimeMilliseconds) {
            g_engine.trackingValue = g_engine.targetLevel;
            g_engine.command = CommandInProgress::None;
            printf("Lighting: fade arrived at %.1f%%\n", g_engine.targetLevel);
        } else {
            const float fraction = (float)elapsed / (float)g_engine.fadeTimeMilliseconds;
            g_engine.trackingValue = g_engine.startLevel + (g_engine.targetLevel - g_engine.startLevel) * fraction;
        }
    } else if (g_engine.command == CommandInProgress::Ramp) {
        // "changing the physical lighting output proportionally from its current value
        // to target-level, with a fixed rate of change defined by ramp-rate."
        const float moved = g_engine.rampRatePercentPerSecond * (float)(now - g_engine.startMilliseconds) / 1000.0f;
        const float distance = fabsf(g_engine.targetLevel - g_engine.startLevel);
        if (moved >= distance) {
            g_engine.trackingValue = g_engine.targetLevel;
            g_engine.command = CommandInProgress::None;
            printf("Lighting: ramp arrived at %.1f%%\n", g_engine.targetLevel);
        } else {
            g_engine.trackingValue = g_engine.startLevel +
                (g_engine.targetLevel > g_engine.startLevel ? moved : -moved);
        }
    } else if (LightingEgressActive() && now >= g_engine.egressDeadlineMilliseconds) {
        // "When the egress timer expires ... Egress_Active shall be set to FALSE", and
        // the warn's effect happens: relinquish (WARN_RELINQUISH) or 0.0% (WARN_OFF).
        if (g_engine.command == CommandInProgress::EgressRelinquish) {
            CommandRelinquish(&g_lightingOutput, g_engine.commandPriority);
            printf("Lighting: egress time over - priority %u relinquished\n", g_engine.commandPriority);
        } else {
            WriteLightingLevel(g_engine.commandPriority, 0.0f);
            printf("Lighting: egress time over - 0.0%% written at priority %u\n", g_engine.commandPriority);
        }
        g_engine.command = CommandInProgress::None;
    }

    // "When the value of In_Progress is IDLE, Tracking_Value shall be equal to
    // Present_Value" (cl. 12.54.5). This object has no Transition property, so a
    // relinquish or direct write takes effect at once (cl. 12.54.19: "If this
    // property does not exist, then the transition type shall be assumed to be NONE").
    if (LightingInProgress() == LIGHTING_IN_PROGRESS_IDLE) {
        g_engine.trackingValue = ResolveLightingLevel(&g_lightingOutput);
    }
    UpdateLastOnValue();
}

// -----------------------------------------------------------------------------
// 2. Property "get" callbacks
//
// The stack calls these when a client reads a property. For each data type the
// stack uses a separate callback. We return true (and fill *value) when we
// recognise the (object, property) pair, and false otherwise.
//
// WHAT false ACTUALLY DOES - the most important paragraph in this file, and the
// opposite of what most people assume. Returning false does NOT reliably produce
// a BACnet error. The stack only errors for the handful of properties it refuses
// to invent: Present_Value, Number_Of_States, Relinquish_Default, Local_Date,
// Local_Time, and a Network Port's APDU_Length.
// For EVERYTHING ELSE, a false return means the stack SILENTLY SUBSTITUTES a
// default:
//     Object_Name -> the literal string "undefined"
//     Units       -> no-units (95)
//     otherwise   -> a datatype zero-value
//
// ADDING AN OBJECT? READ THIS FIRST.
// The consequence is the opposite of reassuring. These callbacks are not
// uniformly strict:
//   - GetPropertyReal / GetPropertyEnumerated / GetPropertyUnsignedInteger match
//     on object type AND INSTANCE (directly, or via GetCommandable(), which
//     looks up the exact type+instance pair). A new instance falls through every
//     one of those checks.
//   - GetPropertyBool serves Out_Of_Service on object TYPE ONLY, so a new
//     instance of an existing type gets Out_Of_Service for free.
// So a half-added object does NOT fail loudly. Its Present_Value errors (that
// one is in the list above) - but its Object_Name reads back as "undefined" and
// its Units as no-units, with no error at all. Add two objects that way and BOTH
// report Object_Name "undefined": duplicate object names within one device, which
// is a spec violation and a hard BTL failure, and which every scan tool will show
// you as a healthy object. The device looks fine and is non-conformant.
//
// So: when you add an instance, walk EVERY callback below, then read back every
// required property of the new object and DIFF IT against the existing one. Do
// not trust "it scanned OK" - that is exactly the failure mode.
// -----------------------------------------------------------------------------

// REAL (floating point) - the Analog Input's Present_Value.
bool GetPropertyReal(const uint32_t deviceInstance, const uint16_t objectType,
                     const uint32_t objectInstance, const uint32_t propertyIdentifier,
                     float* value, const bool useArrayIndex,
                     const uint32_t propertyArrayIndex, uint32_t* errorCode) {
    // None of the arms below is an error condition (an unmatched (object, property)
    // just means "let the stack substitute its default" - see the note at the top
    // of this section) - so errorCode is deliberately never set in this callback.
    (void)errorCode;
    if (deviceInstance != g_deviceInstance) {
        return false;
    }
    if (objectType == OBJECT_TYPE_ANALOG_INPUT &&
        objectInstance == ANALOG_INPUT_INSTANCE &&
        propertyIdentifier == PROPERTY_IDENTIFIER_PRESENT_VALUE) {
        // ON REAL HARDWARE: return the live sensor reading here. Read it from a
        // cached variable that your hardware updates (as g_analogInput1Value is),
        // NOT directly from a slow/blocking device (I2C, SPI, ADC conversion):
        // this callback runs on the BACnetStack_Tick() thread, so blocking it
        // delays all BACnet processing. Sample the sensor on a timer/another
        // thread and just hand back the latest value from here.
        *value = g_analogInput1Value;
        return true;
    }
    // Analog Output (commandable): serve its Priority_Array slots and
    // Relinquish_Default. The stack reads each slot to compute Present_Value and
    // to answer a ReadProperty of the whole array. For a null (relinquished) slot
    // we return false - the stack then takes the "slot is null" answer from
    // GetPropertyBool below.
    const Commandable* c = GetCommandable(objectType, objectInstance);
    // The Analog Output, Lighting Output, AND Channel all carry a REAL
    // Present_Value, so all three serve their Priority_Array slots +
    // Relinquish_Default through this one callback - the commandable mechanism
    // does not care what the object is. (Channel's WRITE side is different -
    // see SetPropertyReal below - but its READ side matches this exactly.)
    if (c != NULL && (objectType == OBJECT_TYPE_ANALOG_OUTPUT ||
                      objectType == OBJECT_TYPE_LIGHTING_OUTPUT ||
                      objectType == OBJECT_TYPE_CHANNEL)) {
        bool slotIsSet = false;
        double slotValue = 0.0;
        if (ReadPrioritySlot(c, propertyIdentifier, useArrayIndex, propertyArrayIndex,
                             &slotIsSet, &slotValue)) {
            if (!slotIsSet) {
                return false;
            }
            *value = (float)slotValue;
            return true;
        }
        if (propertyIdentifier == PROPERTY_IDENTIFIER_RELINQUISH_DEFAULT) {
            *value = (float)c->relinquishDefault;
            return true;
        }
    }

    // --- The Lighting Output's REQUIRED REAL properties ----------------------
    if (objectType == OBJECT_TYPE_LIGHTING_OUTPUT && objectInstance == LIGHTING_OUTPUT_INSTANCE) {
        switch (propertyIdentifier) {
            case PROPERTY_IDENTIFIER_TRACKING_VALUE:
                // What the light is being driven at right now (section 1b). It
                // differs from Present_Value (the target) while In_Progress is
                // FADE_ACTIVE or RAMP_ACTIVE.
                *value = g_engine.trackingValue;
                return true;
            case PROPERTY_IDENTIFIER_DEFAULT_RAMP_RATE:
                *value = g_defaultRampRate;
                return true;
            case PROPERTY_IDENTIFIER_DEFAULT_STEP_INCREMENT:
                *value = g_defaultStepIncrement;
                return true;
            case PROPERTY_IDENTIFIER_LAST_ON_VALUE:
                *value = g_engine.lastOnValue;
                return true;
            case PROPERTY_IDENTIFIER_DEFAULT_ON_VALUE:
                *value = LIGHTING_DEFAULT_ON_VALUE;
                return true;
            default:
                break;
        }
    }
    return false;
}

// ENUMERATED - the Binary Input's Present_Value (0 = inactive, 1 = active) and
// the Analog Input's Units (degrees Celsius).
bool GetPropertyEnumerated(const uint32_t deviceInstance, const uint16_t objectType,
                           const uint32_t objectInstance, const uint32_t propertyIdentifier,
                           uint32_t* value, const bool useArrayIndex,
                           const uint32_t propertyArrayIndex, uint32_t* errorCode) {
    (void)errorCode;
    if (deviceInstance != g_deviceInstance) {
        return false;
    }
    if (objectType == OBJECT_TYPE_BINARY_INPUT &&
        objectInstance == BINARY_INPUT_INSTANCE) {
        if (propertyIdentifier == PROPERTY_IDENTIFIER_PRESENT_VALUE) {
            *value = 1; // active
            return true;
        }
        if (propertyIdentifier == PROPERTY_IDENTIFIER_POLARITY) {
            *value = POLARITY_NORMAL; // required property of a Binary Input
            return true;
        }
    }
    // Binary Output (commandable): Present_Value is an enumerated active/inactive
    // driven through the Priority_Array. Serve the array slots and Relinquish_Default
    // (plus its required Polarity).
    const Commandable* c = GetCommandable(objectType, objectInstance);
    if (c != NULL && objectType == OBJECT_TYPE_BINARY_OUTPUT) {
        bool slotIsSet = false;
        double slotValue = 0.0;
        if (ReadPrioritySlot(c, propertyIdentifier, useArrayIndex, propertyArrayIndex,
                             &slotIsSet, &slotValue)) {
            if (!slotIsSet) {
                return false;
            }
            *value = (uint32_t)slotValue;
            return true;
        }
        if (propertyIdentifier == PROPERTY_IDENTIFIER_RELINQUISH_DEFAULT) {
            *value = (uint32_t)c->relinquishDefault;
            return true;
        }
        if (propertyIdentifier == PROPERTY_IDENTIFIER_POLARITY) {
            *value = POLARITY_NORMAL; // required property of a Binary Output
            return true;
        }
    }
    // Units is REQUIRED on an Analog Input AND on an Analog Output. Serve BOTH.
    // If you only serve the input's, the output does not error - it silently
    // reports no-units(95), because Units is not in the stack's
    // valueShouldBeInitialized list and so falls through to a substituted default
    // (see the note at the top of this section). A setpoint that reads back "no
    // units" next to a degC sensor is the kind of thing nobody notices until
    // commissioning.
    if (propertyIdentifier == PROPERTY_IDENTIFIER_UNITS &&
        ((objectType == OBJECT_TYPE_ANALOG_INPUT && objectInstance == ANALOG_INPUT_INSTANCE) ||
         (objectType == OBJECT_TYPE_ANALOG_OUTPUT && objectInstance == ANALOG_OUTPUT_INSTANCE))) {
        *value = ENGINEERING_UNITS_DEGREES_CELSIUS;
        return true;
    }
    if (objectType == OBJECT_TYPE_NETWORK_PORT &&
        objectInstance == NETWORK_PORT_INSTANCE &&
        propertyIdentifier == PROPERTY_IDENTIFIER_BACNET_IP_MODE) {
        *value = BACNET_IP_MODE_NORMAL; // not foreign-device, not BBMD
        return true;
    }

    // --- The Lighting Output's REQUIRED enumerated properties ----------------
    if (objectType == OBJECT_TYPE_LIGHTING_OUTPUT && objectInstance == LIGHTING_OUTPUT_INSTANCE) {
        if (propertyIdentifier == PROPERTY_IDENTIFIER_IN_PROGRESS) {
            // IDLE / FADE_ACTIVE / RAMP_ACTIVE, from the engine (section 1b).
            *value = LightingInProgress();
            return true;
        }
        // NB: a Lighting Output has NO Units property (its level is a dimensionless
        // percent, and Units is not in the object's required or optional set), so
        // there is deliberately no Units arm here - serving one would be dead code
        // the stack never calls.
    }

    // --- Channel 1's REQUIRED Write_Status (F-CHANNEL) ------------------------
    // BACnetWriteStatus: 0 = idle, 1 = in-progress, 2 = successful, 3 = failed
    // (source/BACnetWriteStatus.h). Kept by section 2e from what happened to the
    // Channel's last writes to its members, local and remote.
    if (objectType == OBJECT_TYPE_CHANNEL && objectInstance == CHANNEL_INSTANCE &&
        propertyIdentifier == PROPERTY_IDENTIFIER_WRITE_STATUS) {
        *value = g_channelWriteStatus;
        return true;
    }
    return false;
}

// UNSIGNED INTEGER - the Multi-State Input's Present_Value, and the Device's
// Vendor_Identifier (the stack also uses Vendor_Identifier to build I-Am).
bool GetPropertyUnsignedInteger(const uint32_t deviceInstance, const uint16_t objectType,
                                const uint32_t objectInstance, const uint32_t propertyIdentifier,
                                uint32_t* value, const bool useArrayIndex,
                                const uint32_t propertyArrayIndex, uint32_t* errorCode) {
    (void)errorCode;
    if (deviceInstance != g_deviceInstance) {
        return false;
    }
    if (objectType == OBJECT_TYPE_MULTI_STATE_INPUT &&
        objectInstance == MULTI_STATE_INPUT_INSTANCE) {
        if (propertyIdentifier == PROPERTY_IDENTIFIER_PRESENT_VALUE) {
            *value = 1; // state 1 (valid range is 1..Number_Of_States)
            return true;
        }
        if (propertyIdentifier == PROPERTY_IDENTIFIER_NUMBER_OF_STATES) {
            *value = MULTI_STATE_INPUT_NUMBER_OF_STATES; // required property
            return true;
        }
        // State_Text is an array. The stack asks for its LENGTH here (array
        // index 0) before reading each element via GetPropertyCharString.
        if (propertyIdentifier == PROPERTY_IDENTIFIER_STATE_TEXT &&
            useArrayIndex && propertyArrayIndex == 0) {
            *value = MULTI_STATE_INPUT_NUMBER_OF_STATES;
            return true;
        }
    }
    if (objectType == OBJECT_TYPE_DEVICE && objectInstance == g_deviceInstance &&
        propertyIdentifier == PROPERTY_IDENTIFIER_VENDOR_IDENTIFIER) {
        *value = VENDOR_IDENTIFIER;
        return true;
    }
    if (objectType == OBJECT_TYPE_NETWORK_PORT && objectInstance == NETWORK_PORT_INSTANCE) {
        if (propertyIdentifier == PROPERTY_IDENTIFIER_APDU_LENGTH) {
            *value = MAX_APDU_LENGTH;
            return true;
        }
        if (propertyIdentifier == PROPERTY_IDENTIFIER_REFERENCE_PORT) {
            *value = NETWORK_PORT_REFERENCE_PORT_NONE;
            return true;
        }
        if (propertyIdentifier == PROPERTY_IDENTIFIER_BACNET_IP_UDP_PORT) {
            *value = g_bacnetIpUdpPort;
            return true;
        }
    }
    // Multi-State Output (commandable): Present_Value is an unsigned state number
    // driven through the Priority_Array. Serve the array slots, Relinquish_Default,
    // and the required Number_Of_States.
    const Commandable* c = GetCommandable(objectType, objectInstance);
    if (c != NULL && objectType == OBJECT_TYPE_MULTI_STATE_OUTPUT) {
        bool slotIsSet = false;
        double slotValue = 0.0;
        if (ReadPrioritySlot(c, propertyIdentifier, useArrayIndex, propertyArrayIndex,
                             &slotIsSet, &slotValue)) {
            if (!slotIsSet) {
                return false;
            }
            *value = (uint32_t)slotValue;
            return true;
        }
        if (propertyIdentifier == PROPERTY_IDENTIFIER_RELINQUISH_DEFAULT) {
            *value = (uint32_t)c->relinquishDefault;
            return true;
        }
        if (propertyIdentifier == PROPERTY_IDENTIFIER_NUMBER_OF_STATES) {
            *value = MULTI_STATE_OUTPUT_NUMBER_OF_STATES;
            return true;
        }
    }

    // --- The Lighting Output's REQUIRED unsigned properties ------------------
    // These are the light's dimming defaults: what it does when a Lighting_Command
    // names an operation but omits that operation's parameter (cl. 12.54.9). E.g. a
    // fadeTo with no fade-time fades over Default_Fade_Time.
    if (objectType == OBJECT_TYPE_LIGHTING_OUTPUT && objectInstance == LIGHTING_OUTPUT_INSTANCE) {
        switch (propertyIdentifier) {
            case PROPERTY_IDENTIFIER_DEFAULT_FADE_TIME:
                *value = g_defaultFadeTime;  // milliseconds
                return true;
            case PROPERTY_IDENTIFIER_EGRESS_TIME:
                *value = g_egressTime;       // seconds - note: NOT milliseconds
                return true;
            case PROPERTY_IDENTIFIER_LIGHTING_COMMAND_DEFAULT_PRIORITY:
                *value = LIGHTING_COMMAND_DEFAULT_PRIORITY;
                return true;
            default:
                break;
        }
    }

    // --- Channel 1's REQUIRED unsigned properties (F-CHANNEL) -----------------
    // Channel_Number and Control_Groups are what let the WriteGroup service MATCH
    // an incoming request to this Channel (see BACnetStack_AddChannelObject's doc
    // comment) - an app that does not serve these two reports channel 0 / an
    // empty group list and the Channel never matches. Last_Priority is the
    // priority the most recent successful write landed at.
    if (objectType == OBJECT_TYPE_CHANNEL && objectInstance == CHANNEL_INSTANCE) {
        if (propertyIdentifier == PROPERTY_IDENTIFIER_CHANNEL_NUMBER) {
            *value = g_channelNumber;
            return true;
        }
        // Control_Groups is an array; the stack asks for element 0 (the count)
        // first, then elements 1..N - the same convention as State_Text above.
        if (propertyIdentifier == PROPERTY_IDENTIFIER_CONTROL_GROUPS && useArrayIndex) {
            if (propertyArrayIndex == 0) {
                *value = CHANNEL_CONTROL_GROUPS_COUNT;
                return true;
            }
            if (propertyArrayIndex >= 1 && propertyArrayIndex <= CHANNEL_CONTROL_GROUPS_COUNT) {
                *value = g_channelControlGroups[propertyArrayIndex - 1];
                return true;
            }
            return false;
        }
        if (propertyIdentifier == PROPERTY_IDENTIFIER_LAST_PRIORITY) {
            *value = g_channelLastPriority;
            return true;
        }
    }
    return false;
}

// BOOLEAN - Out_Of_Service is a required property of every input object and of
// the Network Port. This is a read-only sensor, so nothing is ever out of
// service: always false.
bool GetPropertyBool(const uint32_t deviceInstance, const uint16_t objectType,
                     const uint32_t objectInstance, const uint32_t propertyIdentifier,
                     bool* value, const bool useArrayIndex,
                     const uint32_t propertyArrayIndex, uint32_t* errorCode) {
    (void)errorCode;
    if (deviceInstance != g_deviceInstance) {
        return false;
    }
    // Commandable outputs: the stack asks "is this Priority_Array slot null?" with
    // the boolean getter. Answer true (1) for a relinquished slot, false (0) for a
    // commanded one. This is how the stack knows which slots to skip when computing
    // Present_Value and how it encodes the NULLs in a ReadProperty of the array.
    const Commandable* c = GetCommandable(objectType, objectInstance);
    if (c != NULL && propertyIdentifier == PROPERTY_IDENTIFIER_PRIORITY_ARRAY &&
        useArrayIndex && propertyArrayIndex >= 1 &&
        propertyArrayIndex <= BACNET_PRIORITY_ARRAY_SIZE) {
        *value = !c->isSet[propertyArrayIndex - 1];
        return true;
    }
    // Out_Of_Service is a required property of every input and output object and of
    // the Network Port. This example never takes anything out of service: false.
    if (propertyIdentifier == PROPERTY_IDENTIFIER_OUT_OF_SERVICE &&
        (objectType == OBJECT_TYPE_ANALOG_INPUT ||
         objectType == OBJECT_TYPE_BINARY_INPUT ||
         objectType == OBJECT_TYPE_MULTI_STATE_INPUT ||
         objectType == OBJECT_TYPE_ANALOG_OUTPUT ||
         objectType == OBJECT_TYPE_BINARY_OUTPUT ||
         objectType == OBJECT_TYPE_MULTI_STATE_OUTPUT ||
         objectType == OBJECT_TYPE_LIGHTING_OUTPUT ||
         objectType == OBJECT_TYPE_CHANNEL ||
         objectType == OBJECT_TYPE_SCHEDULE ||
         objectType == OBJECT_TYPE_NETWORK_PORT)) {
        *value = false;
        return true;
    }

    // --- The Lighting Output's REQUIRED boolean properties -------------------
    if (objectType == OBJECT_TYPE_LIGHTING_OUTPUT && objectInstance == LIGHTING_OUTPUT_INSTANCE) {
        if (propertyIdentifier == PROPERTY_IDENTIFIER_BLINK_WARN_ENABLE) {
            // Blink-warn is the "the lights are about to go out" flash that gives
            // people Egress_Time to leave.
            *value = LIGHTING_BLINK_WARN_ENABLE;
            return true;
        }
        if (propertyIdentifier == PROPERTY_IDENTIFIER_EGRESS_ACTIVE) {
            // TRUE only while a warnRelinquish / warnOff egress timer runs (section 1b).
            *value = LightingEgressActive();
            return true;
        }
    }

    // --- Calendar 1's REQUIRED Present_Value (F-SCHED-E) ----------------------
    // Present_Value is "is today in Date_List". See the TODO.md entry: this
    // stack build has no customer-surface callback shape for Date_List itself
    // (a BACnetLIST of BACnetCalendarEntry, a variable-length list of a CHOICE
    // type - none of the typed Get callbacks fit it), so Date_List genuinely
    // stays empty here, and Present_Value is honestly always false as a result.
    if (objectType == OBJECT_TYPE_CALENDAR && objectInstance == CALENDAR_INSTANCE &&
        propertyIdentifier == PROPERTY_IDENTIFIER_PRESENT_VALUE) {
        *value = false;
        return true;
    }
    return false;
}

// OCTET STRING - the Network Port's BACnet/IP addressing. The stack cannot know
// the host's IP, so the application must supply IP_Address and IP_Subnet_Mask
// (and IP_Default_Gateway). Each is four octets. The stack also reads IP_Address
// (with BACnet_IP_UDP_Port) to build the port's six-octet MAC_Address.
bool GetPropertyOctetString(const uint32_t deviceInstance, const uint16_t objectType,
                            const uint32_t objectInstance, const uint32_t propertyIdentifier,
                            uint8_t* value, uint32_t* valueElementCount,
                            const uint32_t maxElementCount, const bool useArrayIndex,
                            const uint32_t propertyArrayIndex, uint32_t* errorCode) {
    (void)useArrayIndex;
    (void)propertyArrayIndex;
    (void)errorCode;
    if (deviceInstance != g_deviceInstance ||
        objectType != OBJECT_TYPE_NETWORK_PORT ||
        objectInstance != NETWORK_PORT_INSTANCE ||
        maxElementCount < 4) {
        return false;
    }
    const uint8_t* source = NULL;
    switch (propertyIdentifier) {
        case PROPERTY_IDENTIFIER_IP_ADDRESS:         source = g_ipAddress; break;
        case PROPERTY_IDENTIFIER_IP_SUBNET_MASK:     source = g_ipSubnetMask; break;
        case PROPERTY_IDENTIFIER_IP_DEFAULT_GATEWAY: source = g_ipDefaultGateway; break;
        default: return false;
    }
    memcpy(value, source, 4);
    *valueElementCount = 4;
    return true;
}

// Small helper: copy a C string into the stack's character-string buffer and
// set the element count + encoding. Returns true (so callers can `return`).
static bool ReturnCharacterString(const char* text, char* value,
                                  uint32_t* valueElementCount,
                                  const uint32_t maxElementCount,
                                  uint8_t* encodingType) {
    uint32_t length = (uint32_t)strlen(text);
    // The stack offers a buffer of maxElementCount octets but holds at most
    // maxElementCount - 1: a value of maxElementCount octets or more is refused
    // and the property reads as an empty string. So truncate to one less.
    if (maxElementCount > 0 && length >= maxElementCount) {
        // Truncate SILENTLY to fit the stack's buffer. maxElementCount is
        // MAX_CHARACTER_STRING_SIZE (256 in this build), and our longest string
        // (DEVICE_DESCRIPTION, 221 characters) fits - so this does not trip here
        // (a 255-byte --deviceName is the longest value it passes whole). But if you build with STACK_OPTION_TARGET_EMBEDDED, that limit drops to
        // 64, and a long Object_Name or Description would be clipped mid-word
        // with nothing on the wire or console to tell you. If you lengthen any
        // served string, check it against MAX_CHARACTER_STRING_SIZE for your
        // target, or make this truncation loud.
        length = maxElementCount - 1;
    }
    memcpy(value, text, length);
    *valueElementCount = length;
    *encodingType = CHARACTER_STRING_ENCODING_UTF8;
    return true;
}

// CHARACTER STRING - Object_Name for each object, and the device Description.
bool GetPropertyCharString(const uint32_t deviceInstance, const uint16_t objectType,
                           const uint32_t objectInstance, const uint32_t propertyIdentifier,
                           char* value, uint32_t* valueElementCount,
                           const uint32_t maxElementCount, uint8_t* encodingType,
                           const bool useArrayIndex, const uint32_t propertyArrayIndex,
                           uint32_t* errorCode) {
    (void)errorCode;
    if (deviceInstance != g_deviceInstance) {
        return false;
    }

    // State_Text (optional) - one label per state of the Multi-State Input. It is
    // a BACnet array, so the stack asks for one element at a time by index
    // (1..Number_Of_States). Present_Value 1 -> "On", 2 -> "Off", 3 -> "Auto".
    if (objectType == OBJECT_TYPE_MULTI_STATE_INPUT &&
        objectInstance == MULTI_STATE_INPUT_INSTANCE &&
        propertyIdentifier == PROPERTY_IDENTIFIER_STATE_TEXT && useArrayIndex) {
        static const char* const stateText[] = { "On", "Off", "Auto" };
        if (propertyArrayIndex >= 1 && propertyArrayIndex <= MULTI_STATE_INPUT_NUMBER_OF_STATES) {
            return ReturnCharacterString(stateText[propertyArrayIndex - 1], value,
                                         valueElementCount, maxElementCount, encodingType);
        }
        return false;
    }

    // Object_Name - the colour name for each object.
    if (propertyIdentifier == PROPERTY_IDENTIFIER_OBJECT_NAME) {
        if (objectType == OBJECT_TYPE_DEVICE && objectInstance == g_deviceInstance) {
            return ReturnCharacterString(g_deviceName, value, valueElementCount, maxElementCount, encodingType);
        }
        if (objectType == OBJECT_TYPE_ANALOG_INPUT && objectInstance == ANALOG_INPUT_INSTANCE) {
            return ReturnCharacterString("Bronze", value, valueElementCount, maxElementCount, encodingType);
        }
        if (objectType == OBJECT_TYPE_BINARY_INPUT && objectInstance == BINARY_INPUT_INSTANCE) {
            return ReturnCharacterString("Emerald", value, valueElementCount, maxElementCount, encodingType);
        }
        if (objectType == OBJECT_TYPE_MULTI_STATE_INPUT && objectInstance == MULTI_STATE_INPUT_INSTANCE) {
            return ReturnCharacterString("Hot Pink", value, valueElementCount, maxElementCount, encodingType);
        }
        if (objectType == OBJECT_TYPE_ANALOG_OUTPUT && objectInstance == ANALOG_OUTPUT_INSTANCE) {
            return ReturnCharacterString("Chartreuse", value, valueElementCount, maxElementCount, encodingType);
        }
        if (objectType == OBJECT_TYPE_BINARY_OUTPUT && objectInstance == BINARY_OUTPUT_INSTANCE) {
            return ReturnCharacterString("Fuchsia", value, valueElementCount, maxElementCount, encodingType);
        }
        if (objectType == OBJECT_TYPE_MULTI_STATE_OUTPUT && objectInstance == MULTI_STATE_OUTPUT_INSTANCE) {
            return ReturnCharacterString("Indigo", value, valueElementCount, maxElementCount, encodingType);
        }
        if (objectType == OBJECT_TYPE_LIGHTING_OUTPUT && objectInstance == LIGHTING_OUTPUT_INSTANCE) {
            return ReturnCharacterString("Jade", value, valueElementCount, maxElementCount, encodingType);
        }
        if (objectType == OBJECT_TYPE_CHANNEL && objectInstance == CHANNEL_INSTANCE) {
            return ReturnCharacterString("Garnet", value, valueElementCount, maxElementCount, encodingType);
        }
        if (objectType == OBJECT_TYPE_SCHEDULE && objectInstance == SCHEDULE_INSTANCE) {
            return ReturnCharacterString("Saffron", value, valueElementCount, maxElementCount, encodingType);
        }
        if (objectType == OBJECT_TYPE_CALENDAR && objectInstance == CALENDAR_INSTANCE) {
            return ReturnCharacterString("Cream", value, valueElementCount, maxElementCount, encodingType);
        }
        if (objectType == OBJECT_TYPE_NETWORK_PORT && objectInstance == NETWORK_PORT_INSTANCE) {
            return ReturnCharacterString("Vermilion", value, valueElementCount, maxElementCount, encodingType);
        }
    }

    // The remaining strings are all on the Device object - its identity, read
    // by clients and used to populate the device's I-Am / object list.
    if (objectType == OBJECT_TYPE_DEVICE && objectInstance == g_deviceInstance) {
        switch (propertyIdentifier) {
            case PROPERTY_IDENTIFIER_DESCRIPTION:
                return ReturnCharacterString(DEVICE_DESCRIPTION, value, valueElementCount, maxElementCount, encodingType);
            case PROPERTY_IDENTIFIER_VENDOR_NAME:
                return ReturnCharacterString(VENDOR_NAME, value, valueElementCount, maxElementCount, encodingType);
            case PROPERTY_IDENTIFIER_MODEL_NAME:
                return ReturnCharacterString(MODEL_NAME, value, valueElementCount, maxElementCount, encodingType);
            case PROPERTY_IDENTIFIER_FIRMWARE_REVISION:
                return ReturnCharacterString(g_firmwareRevision.c_str(), value, valueElementCount, maxElementCount, encodingType);
            case PROPERTY_IDENTIFIER_APPLICATION_SOFTWARE_VERSION:
                return ReturnCharacterString(APP_VERSION, value, valueElementCount, maxElementCount, encodingType);
            default:
                break;
        }
    }

    return false;
}

// -----------------------------------------------------------------------------
// 2e. Channel 1's fan-out, followed to its end: Write_Status (cl. 12.53.5/.7)
//
// When anything writes Channel 1 - a WriteProperty, a WriteGroup, or Schedule 1 -
// the stack writes the Channel's Present_Value
// and then "propagate[s] that value to each of the members in the
// List_Of_Object_Property_References" (cl. 12.53.5): Jade, locally, through
// SetPropertyReal / SetPropertyNull below, and the Lighting Output on device
// 389016 with a confirmed WriteProperty it sends itself. Write_Status is
// IN_PROGRESS while those writes are under way, then SUCCESSFUL, or FAILED if
// any of them "received an error, reject, or abort" (cl. 12.53.7). A member that
// never answers is a failure too: the stack reports it through the Timeout hook
// once APDU_Timeout x (Number_Of_APDU_Retries + 1) has passed (10 s x 4 = 40 s
// here, the stack's defaults: it retries a confirmed request 3 times), and a member the stack cannot address - no I-Am from
// 389016 yet - is skipped by the stack, so it is failed at once.
//
// Every one of those writes reaches SetPropertyReal / SetPropertyNull's Channel
// arm, and the stack writes the members straight after it, inside the same
// BACnetStack_Tick(), so the Channel arm starts the fan-out and the main loop
// closes it after the tick. (The stack also calls WriteGroupInhibitDelay just
// before a WriteGroup's write; that only labels the console line and lets the
// WriteGroup through while IN_PROGRESS.) At start-up Schedule 1 writes Channel 1
// before device 389016 has answered a Who-Is, so Write_Status reads FAILED until
// the next write that reaches both members.
// -----------------------------------------------------------------------------
static bool g_writeGroupExecuting = false;  // WriteGroupInhibitDelay ran for Channel 1 this tick
static bool g_fanOutStartedThisTick = false; // a write to Channel 1 is being propagated this tick
static bool g_fanOutLocalFailed = false;     // a local member (Jade) refused its write
static bool g_fanOutRemoteFailed = false;    // the remote member's write failed / was not sent
static uint32_t g_remoteWritesOutstanding = 0; // remote writes sent, answer not yet seen

// The remote member's address, from its I-Am (HookIAm). The stack's own
// Device_Address_Binding is bound by the same I-Am; this copy is how the
// application recognises the answer to the stack's WriteProperty.
static bool g_remoteDeviceKnown = false;
static uint8_t g_remoteDeviceAddress[6] = { 0 };
static const uint8_t REMOTE_DEVICE_ADDRESS_LENGTH = 6; // BACnet/IP: 4 IP octets + 2 port octets

static const char* WriteStatusName(uint32_t writeStatus) {
    switch (writeStatus) {
        case WRITE_STATUS_IDLE:        return "idle";
        case WRITE_STATUS_IN_PROGRESS: return "in-progress";
        case WRITE_STATUS_SUCCESSFUL:  return "successful";
        case WRITE_STATUS_FAILED:      return "failed";
        default:                       return "(other)";
    }
}

// A WriteGroup has just written Channel 1: its writes to the members follow, in
// this same tick.
// DeviceCommunicationControl DISABLE_INITIATION (DM-DCC-B, section 2e's DCC
// callback): while it holds, the device must not initiate requests (135-2024 cl.
// 16.1), so the stack refuses to send the remote member's WriteProperty - and
// tells the application nothing: no SimpleACK, Error or Timeout hook ever comes for
// it. Without this, Write_Status would stay IN_PROGRESS for good and every later
// WriteProperty to Channel 1 would be refused with BUSY. The callback records the
// state (and the stack's own re-enable time, for a request with a duration).
static bool g_initiationDisabled = false;
static bool g_initiationDisabledUntilSet = false;
static uint64_t g_initiationDisabledUntilMs = 0;

static bool InitiationDisabledNow() {
    if (g_initiationDisabled && g_initiationDisabledUntilSet && NowMilliseconds() >= g_initiationDisabledUntilMs) {
        g_initiationDisabled = false; // the duration ran out; the stack re-enables on its own
    }
    return g_initiationDisabled;
}

static void BeginChannelFanOut() {
    g_fanOutStartedThisTick = true;
    g_fanOutLocalFailed = false;
    g_fanOutRemoteFailed = false;
    g_channelWriteStatus = WRITE_STATUS_IN_PROGRESS;
    if (g_remoteDeviceKnown && InitiationDisabledNow()) {
        // DISABLE_INITIATION: the stack will not send the remote member its write,
        // and no hook reports that, so it is failed at once (cl. 12.53.7, 12.53.9).
        g_fanOutRemoteFailed = true;
        printf("FYI: DeviceCommunicationControl has disabled initiation, so the stack does not send\n"
               "     remote device %u its write: Write_Status will be FAILED.\n", REMOTE_DEVICE_INSTANCE);
    } else if (g_remoteDeviceKnown) {
        ++g_remoteWritesOutstanding; // the stack sends it a WriteProperty now
    } else {
        // The stack only writes to a device it has an address for; it skips this
        // member. cl. 12.53.9 calls that a communication failure.
        g_fanOutRemoteFailed = true;
        printf("FYI: remote device %u has not answered a Who-Is (no I-Am yet), so the stack\n"
               "     cannot address it: its write is skipped and Write_Status will be FAILED.\n",
               REMOTE_DEVICE_INSTANCE);
    }
    printf("Channel 1 (Garnet) Write_Status = %s\n", WriteStatusName(g_channelWriteStatus));
}

// A local member's write, as the fan-out made it: accepted (true) or refused.
static bool NoteLocalMemberWrite(bool accepted) {
    if (g_fanOutStartedThisTick && !accepted) {
        g_fanOutLocalFailed = true;
    }
    return accepted;
}

// Once no member's answer is outstanding, Write_Status says how the writes went.
static void FinishChannelFanOutIfDone() {
    if (g_channelWriteStatus != WRITE_STATUS_IN_PROGRESS || g_remoteWritesOutstanding > 0) {
        return;
    }
    g_channelWriteStatus = (g_fanOutLocalFailed || g_fanOutRemoteFailed) ? WRITE_STATUS_FAILED
                                                                          : WRITE_STATUS_SUCCESSFUL;
    printf("Channel 1 (Garnet) Write_Status = %s%s%s\n", WriteStatusName(g_channelWriteStatus),
           g_fanOutLocalFailed ? " (a local member refused its write)" : "",
           g_fanOutRemoteFailed ? " (the remote member's write did not succeed)" : "");
}

// The answer to the stack's WriteProperty to the remote member arrived (or the
// stack gave up waiting for it).
static void NoteRemoteMemberAnswer(const uint8_t* connectionString, uint8_t connectionStringLength,
                                   bool succeeded, const char* what) {
    if (!g_remoteDeviceKnown || g_remoteWritesOutstanding == 0 ||
        connectionStringLength != REMOTE_DEVICE_ADDRESS_LENGTH ||
        memcmp(connectionString, g_remoteDeviceAddress, REMOTE_DEVICE_ADDRESS_LENGTH) != 0) {
        return; // not an answer from the remote member
    }
    --g_remoteWritesOutstanding;
    if (!succeeded) {
        g_fanOutRemoteFailed = true;
    }
    printf("Remote member (device %u, Lighting Output %u): %s\n",
           REMOTE_DEVICE_INSTANCE, REMOTE_OBJECT_INSTANCE, what);
    FinishChannelFanOutIfDone();
}

// -----------------------------------------------------------------------------
// 2b. Property "set" callbacks - the heart of B-SA (DS-WP-B)
//
// The stack calls these when a client sends WriteProperty to a commandable
// output's Present_Value. The value arrives already decoded into the matching
// data type, together with the priority (1..16) the client wrote at. We store it
// in the object's Priority_Array; the stack recomputes Present_Value from the
// array on the next read. A WriteProperty of NULL relinquishes a slot and arrives
// through SetPropertyNull instead.
//
// Return true when we accept the write; return false (optionally setting
// *errorCode) to reject it, and the stack answers with a BACnet Error-PDU.
// -----------------------------------------------------------------------------

// The Present_Value special values of Table 12-65: "-1.0 Provides the same
// functionality as the WARN lighting command", -2.0 WARN_RELINQUISH, -3.0
// WARN_OFF, -4.0 RESTORE_ON, -5.0 DEFAULT_ON, -6.0 TOGGLE_RESTORE, -7.0
// TOGGLE_DEFAULT. They let a device that cannot write a BACnetLightingCommand -
// a Schedule, or a Channel carrying a REAL, say - still blink-warn the room.
// Returns NONE for any other value.
static uint32_t SpecialValueOperation(float value) {
    static const uint32_t operations[] = {
        LIGHTING_OPERATION_WARN, LIGHTING_OPERATION_WARN_RELINQUISH, LIGHTING_OPERATION_WARN_OFF,
        LIGHTING_OPERATION_RESTORE_ON, LIGHTING_OPERATION_DEFAULT_ON,
        LIGHTING_OPERATION_TOGGLE_RESTORE, LIGHTING_OPERATION_TOGGLE_DEFAULT };
    for (uint32_t specialIndex = 0; specialIndex < sizeof(operations) / sizeof(operations[0]); specialIndex++) {
        if (value == -(float)(specialIndex + 1)) {
            return operations[specialIndex];
        }
    }
    return LIGHTING_OPERATION_NONE;
}

// REAL write - Analog Output 1 (Chartreuse) Present_Value, and Lighting Output 1
// (Jade)'s Present_Value, Default_Ramp_Rate and Default_Step_Increment.
bool SetPropertyReal(const uint32_t deviceInstance, const uint16_t objectType,
                     const uint32_t objectInstance, const uint32_t propertyIdentifier,
                     const float value, const bool useArrayIndex,
                     const uint32_t propertyArrayIndex, const uint8_t priority,
                     uint32_t* errorCode) {
    if (deviceInstance != g_deviceInstance) {
        return false;
    }
    Commandable* c = GetCommandable(objectType, objectInstance);
    // F-CHANNEL: BACnetStack_AddChannelObject's doc comment says a Channel's
    // Present_Value write arrives on PROPERTY_IDENTIFIER_PRIORITY_ARRAY with an
    // array index (1..16) that IS the priority, and that is how the stack's own
    // Schedule writes it. At stack 6.x @ 64b2cfac5 a client WriteProperty and an
    // incoming WriteGroup arrive on PROPERTY_IDENTIFIER_PRESENT_VALUE with the
    // `priority` argument instead (stack defect, see TODO.md). Accept both forms:
    // refusing the second makes the stack fall back to its own value store, which
    // holds nothing for this Channel, so every WriteProperty and WriteGroup to
    // Channel 1 failed and nothing fanned out.
    const bool channelPriorityArrayForm = propertyIdentifier == PROPERTY_IDENTIFIER_PRIORITY_ARRAY && useArrayIndex &&
        propertyArrayIndex >= 1 && propertyArrayIndex <= BACNET_PRIORITY_ARRAY_SIZE;
    const bool channelPresentValueForm = propertyIdentifier == PROPERTY_IDENTIFIER_PRESENT_VALUE;
    if (c != NULL && objectType == OBJECT_TYPE_CHANNEL && (channelPriorityArrayForm || channelPresentValueForm)) {
        if (!g_writeGroupExecuting && g_channelWriteStatus == WRITE_STATUS_IN_PROGRESS) {
            // cl. 12.53.5: not while the last value is still being written out.
            *errorCode = ERROR_CODE_BUSY;
            return false;
        }
        const uint8_t channelPriority = channelPriorityArrayForm ? (uint8_t)propertyArrayIndex : EffectivePriority(priority);
        CommandWrite(c, channelPriority, (double)value);
        g_channelLastPriority = channelPriority;
        printf("%s: Channel %u (Garnet) <- %.2f @ priority %u\n",
               g_writeGroupExecuting ? "WriteGroup" : "Write", objectInstance, value, channelPriority);
        BeginChannelFanOut(); // the stack writes the members next, this tick (section 2e)
        return true;
    }
    (void)useArrayIndex;
    (void)propertyArrayIndex;
    if (c != NULL && propertyIdentifier == PROPERTY_IDENTIFIER_PRESENT_VALUE &&
        objectType == OBJECT_TYPE_ANALOG_OUTPUT) {
        CommandWrite(c, priority, (double)value);
        printf("WriteProperty: Analog Output %u <- %.2f @ priority %u\n",
               objectInstance, value, EffectivePriority(priority));
        return true;
    }
    if (objectType == OBJECT_TYPE_LIGHTING_OUTPUT && objectInstance == LIGHTING_OUTPUT_INSTANCE) {
        if (propertyIdentifier == PROPERTY_IDENTIFIER_PRESENT_VALUE) {
            // Jade's Present_Value is written by a client, and by Channel 1's fan-out
            // (a WriteProperty or WriteGroup to the Channel, or Schedule 1). A
            // refusal here is also how the fan-out learns that its local member
            // failed (NoteLocalMemberWrite, section 2e).
            const uint8_t writePriority = EffectivePriority(priority);
            // A special value runs its lighting command; "The special value itself is
            // not written to the priority array" (cl. 12.54.4).
            const uint32_t specialOperation = SpecialValueOperation(value);
            if (specialOperation != LIGHTING_OPERATION_NONE) {
                printf("WriteProperty: Lighting Output %u Present_Value special value %.1f = %s @ priority %u\n",
                       objectInstance, value, LightingOperationName(specialOperation), writePriority);
                return NoteLocalMemberWrite(ExecuteLightingOperation(specialOperation, writePriority, 0.0f,
                                                                     g_defaultFadeTime, g_defaultRampRate,
                                                                     g_defaultStepIncrement, errorCode));
            }
            // "The valid range of values for the Present_Value is 0.0% to 100.0%" and
            // "Writes to Present_Value of values outside of the valid range of values
            // shall cause a Result(-) to be returned with an 'Error Class' of PROPERTY
            // and an 'Error Code' of VALUE_OUT_OF_RANGE" (cl. 12.54.4). Written as
            // !(in range) so a NaN is refused too.
            if (!(value >= LIGHTING_LEVEL_MIN && value <= LIGHTING_LEVEL_MAX)) {
                *errorCode = ERROR_CODE_VALUE_OUT_OF_RANGE;
                return NoteLocalMemberWrite(false);
            }
            // "If a lighting command is currently in progress and the Present_Value is
            // written at a higher or equal priority, the lighting command shall be
            // halted" (cl. 12.54.4).
            HaltIfWriteOverrides(writePriority, "Present_Value written");
            WriteLightingLevel(writePriority, value);
            printf("WriteProperty: Lighting Output %u Present_Value <- %.2f @ priority %u\n",
                   objectInstance, ClampToDimmest(value), writePriority);
            return true;
        }
        if (propertyIdentifier == PROPERTY_IDENTIFIER_DEFAULT_RAMP_RATE ||
            propertyIdentifier == PROPERTY_IDENTIFIER_DEFAULT_STEP_INCREMENT) {
            // cl. 12.54.17 / 12.54.18: 0.1 to 100.0 inclusive; "Values written outside
            // of the allowable range shall cause a Result(-) ... VALUE_OUT_OF_RANGE."
            const bool isRampRate = (propertyIdentifier == PROPERTY_IDENTIFIER_DEFAULT_RAMP_RATE);
            const float minimum = isRampRate ? LIGHTING_RAMP_RATE_MIN : LIGHTING_STEP_INCREMENT_MIN;
            const float maximum = isRampRate ? LIGHTING_RAMP_RATE_MAX : LIGHTING_STEP_INCREMENT_MAX;
            if (!(value >= minimum && value <= maximum)) {
                *errorCode = ERROR_CODE_VALUE_OUT_OF_RANGE;
                return false;
            }
            (isRampRate ? g_defaultRampRate : g_defaultStepIncrement) = value;
            printf("WriteProperty: Lighting Output %u %s <- %.1f\n", objectInstance,
                   isRampRate ? "Default_Ramp_Rate" : "Default_Step_Increment", value);
            return true;
        }
    }
    return false;
}

// ENUMERATED write - Binary Output 1 (Fuchsia) Present_Value (0/1).
bool SetPropertyEnumerated(const uint32_t deviceInstance, const uint16_t objectType,
                           const uint32_t objectInstance, const uint32_t propertyIdentifier,
                           const uint32_t value, const bool useArrayIndex,
                           const uint32_t propertyArrayIndex, const uint8_t priority,
                           uint32_t* errorCode) {
    (void)useArrayIndex;
    (void)propertyArrayIndex;
    if (deviceInstance != g_deviceInstance) {
        return false;
    }
    Commandable* c = GetCommandable(objectType, objectInstance);
    if (c != NULL && objectType == OBJECT_TYPE_BINARY_OUTPUT &&
        propertyIdentifier == PROPERTY_IDENTIFIER_PRESENT_VALUE) {
        // A Binary Output's Present_Value is 0 (inactive) or 1 (active). Reject
        // anything else with value-out-of-range - validating the written value is
        // part of being a conformant DS-WP-B device.
        if (value > 1) {
            *errorCode = ERROR_CODE_VALUE_OUT_OF_RANGE;
            return false;
        }
        CommandWrite(c, priority, (double)value);
        printf("WriteProperty: Binary Output %u (Fuchsia) <- %s @ priority %u\n",
               objectInstance, value ? "active" : "inactive", EffectivePriority(priority));
        return true;
    }
    return false;
}

// UNSIGNED write - Multi-State Output 1 (Indigo) Present_Value (state 1..3).
bool SetPropertyUnsignedInteger(const uint32_t deviceInstance, const uint16_t objectType,
                                const uint32_t objectInstance, const uint32_t propertyIdentifier,
                                const uint32_t value, const bool useArrayIndex,
                                const uint32_t propertyArrayIndex, const uint8_t priority,
                                uint32_t* errorCode) {
    if (deviceInstance != g_deviceInstance) {
        return false;
    }
    Commandable* c = GetCommandable(objectType, objectInstance);
    if (c != NULL && objectType == OBJECT_TYPE_MULTI_STATE_OUTPUT &&
        propertyIdentifier == PROPERTY_IDENTIFIER_PRESENT_VALUE) {
        // A Multi-State Output's Present_Value is a state number in 1..Number_Of_States.
        // Reject anything outside that range with value-out-of-range.
        if (value < 1 || value > MULTI_STATE_OUTPUT_NUMBER_OF_STATES) {
            *errorCode = ERROR_CODE_VALUE_OUT_OF_RANGE;
            return false;
        }
        CommandWrite(c, priority, (double)value);
        printf("WriteProperty: Multi-State Output %u (Indigo) <- state %u @ priority %u\n",
               objectInstance, value, EffectivePriority(priority));
        return true;
    }

    // Lighting Output 1 (Jade)'s Default_Fade_Time and Egress_Time.
    if (objectType == OBJECT_TYPE_LIGHTING_OUTPUT && objectInstance == LIGHTING_OUTPUT_INSTANCE) {
        if (propertyIdentifier == PROPERTY_IDENTIFIER_DEFAULT_FADE_TIME) {
            // cl. 12.54.16: "100 ms to 86400000 ms (1 day) inclusive. Values written
            // outside of the allowable range shall cause a Result(-) ... VALUE_OUT_OF_RANGE."
            if (value < LIGHTING_FADE_TIME_MIN || value > LIGHTING_FADE_TIME_MAX) {
                *errorCode = ERROR_CODE_VALUE_OUT_OF_RANGE;
                return false;
            }
            g_defaultFadeTime = value;
            printf("WriteProperty: Lighting Output %u Default_Fade_Time <- %u ms\n", objectInstance, value);
            return true;
        }
        if (propertyIdentifier == PROPERTY_IDENTIFIER_EGRESS_TIME) {
            // cl. 12.54.14 gives Egress_Time no range; it is seconds. A new value applies
            // to the next warn, not to an egress timer already running.
            g_egressTime = value;
            printf("WriteProperty: Lighting Output %u Egress_Time <- %u s\n", objectInstance, value);
            return true;
        }
    }

    // Channel 1 (Garnet)'s Channel_Number and Control_Groups (F-CHANNEL). These
    // are not commandable - a plain scalar/array write, no priority involved.
    if (objectType == OBJECT_TYPE_CHANNEL && objectInstance == CHANNEL_INSTANCE) {
        if (propertyIdentifier == PROPERTY_IDENTIFIER_CHANNEL_NUMBER) {
            g_channelNumber = (uint16_t)value;
            printf("WriteProperty: Channel %u (Garnet) Channel_Number <- %u\n",
                   objectInstance, g_channelNumber);
            return true;
        }
        if (propertyIdentifier == PROPERTY_IDENTIFIER_CONTROL_GROUPS && useArrayIndex &&
            propertyArrayIndex >= 1 && propertyArrayIndex <= CHANNEL_CONTROL_GROUPS_COUNT) {
            g_channelControlGroups[propertyArrayIndex - 1] = value;
            printf("WriteProperty: Channel %u (Garnet) Control_Groups[%u] <- %u\n",
                   objectInstance, propertyArrayIndex, value);
            return true;
        }
    }
    return false;
}

// NULL write - relinquish a commandable output's Present_Value at a priority. The
// stack routes a WriteProperty of NULL here (one callback for every data type).
bool SetPropertyNull(const uint32_t deviceInstance, const uint16_t objectType,
                     const uint32_t objectInstance, const uint32_t propertyIdentifier,
                     const bool useArrayIndex, const uint32_t propertyArrayIndex,
                     const uint8_t priority, uint32_t* errorCode) {
    (void)errorCode;
    if (deviceInstance != g_deviceInstance) {
        return false;
    }
    Commandable* c = GetCommandable(objectType, objectInstance);
    // F-CHANNEL: the same two dispatch forms as SetPropertyReal's Channel arm
    // above (Priority_Array[index] or Present_Value + priority) - see that comment.
    if (c != NULL && objectType == OBJECT_TYPE_CHANNEL &&
        ((propertyIdentifier == PROPERTY_IDENTIFIER_PRIORITY_ARRAY && useArrayIndex &&
          propertyArrayIndex >= 1 && propertyArrayIndex <= BACNET_PRIORITY_ARRAY_SIZE) ||
         propertyIdentifier == PROPERTY_IDENTIFIER_PRESENT_VALUE)) {
        if (!g_writeGroupExecuting && g_channelWriteStatus == WRITE_STATUS_IN_PROGRESS) {
            *errorCode = ERROR_CODE_BUSY; // cl. 12.53.5, as in SetPropertyReal
            return false;
        }
        const uint8_t channelPriority = propertyIdentifier == PROPERTY_IDENTIFIER_PRIORITY_ARRAY
            ? (uint8_t)propertyArrayIndex : EffectivePriority(priority);
        CommandRelinquish(c, channelPriority);
        g_channelLastPriority = channelPriority;
        printf("%s: relinquished Channel %u (Garnet) @ priority %u\n",
               g_writeGroupExecuting ? "WriteGroup" : "Write", objectInstance, (unsigned)channelPriority);
        BeginChannelFanOut(); // a Null is propagated too (cl. 12.53.5, 15.11.2)
        return true;
    }
    (void)useArrayIndex;
    (void)propertyArrayIndex;
    if (c != NULL && propertyIdentifier == PROPERTY_IDENTIFIER_PRESENT_VALUE &&
        objectType == OBJECT_TYPE_LIGHTING_OUTPUT) {
        const uint8_t writePriority = EffectivePriority(priority);
        // A relinquish is a write to Present_Value too: at the priority of the
        // command in progress (or above) it halts it (section 1b).
        HaltIfWriteOverrides(writePriority, "Present_Value relinquished");
        CommandRelinquish(c, writePriority);
        UpdateLastOnValue();
        printf("WriteProperty: relinquished Lighting Output %u @ priority %u\n", objectInstance, writePriority);
        return true;
    }
    if (c != NULL && propertyIdentifier == PROPERTY_IDENTIFIER_PRESENT_VALUE) {
        CommandRelinquish(c, priority);
        printf("WriteProperty: relinquished %s %u @ priority %u\n",
               objectType == OBJECT_TYPE_ANALOG_OUTPUT ? "Analog Output" :
               objectType == OBJECT_TYPE_BINARY_OUTPUT ? "Binary Output" :
               "Multi-State Output",
               objectInstance, EffectivePriority(priority));
        return true;
    }
    return false;
}

// -----------------------------------------------------------------------------
// F-LIGHT - canonical implementation (B-LD is the reference for this feature:
// Lighting Output 1 "Jade", OBJECT_TYPE_LIGHTING_OUTPUT = 54. A later series repo
// that needs a commandable Lighting Output copies this section plus the
// Present_Value/Priority_Array wiring in SetPropertyReal/GetPropertyReal above,
// then renames the instance/label).
// 2c. Lighting_Command callbacks - the heart of B-LD (DS-LO-B)
//
// Lighting_Command is a CONSTRUCTED property: a BACnetLightingCommand SEQUENCE
// carrying an operation plus the optional parameters that operation needs.
// Encoding and decoding it is the STACK's job - the application only ever handles
// plain numbers, through the two callbacks below. That is why there is no BACnet
// byte-twiddling anywhere in this file.
//
//     operation      - fadeTo / rampTo / stepUp / stepDown / warn / stop / ...
//     target-level   - REAL 0.0..100.0   (optional)
//     ramp-rate      - REAL % per second (optional)
//     step-increment - REAL %            (optional)
//     fade-time      - Unsigned ms       (optional)
//     priority       - Unsigned 1..16    (optional)
//
// Each optional field has a use* flag. On the GET side, setting it false omits
// the field from the SEQUENCE. On the SET side, false means the WRITER OMITTED IT
// - and the accompanying value is meaningless, so you must apply your own default
// instead (cl. 12.54.9). That distinction is the whole reason the flags exist: a
// fadeTo with no fade-time means "fade over Default_Fade_Time", NOT "fade in 0 ms".
// -----------------------------------------------------------------------------

// GET - report the last command this light was given.
bool GetPropertyLightingCommand(const uint32_t deviceInstance, const uint16_t objectType,
                                const uint32_t objectInstance, const uint32_t propertyIdentifier,
                                uint32_t* operation,
                                bool* useTargetLevel, float* targetLevel,
                                bool* useRampRate, float* rampRate,
                                bool* useStepIncrement, float* stepIncrement,
                                bool* useFadeTime, uint32_t* fadeTime,
                                bool* usePriority, uint32_t* priority,
                                uint32_t* errorCode) {
    if (deviceInstance != g_deviceInstance ||
        objectType != OBJECT_TYPE_LIGHTING_OUTPUT ||
        objectInstance != LIGHTING_OUTPUT_INSTANCE ||
        propertyIdentifier != PROPERTY_IDENTIFIER_LIGHTING_COMMAND) {
        // Not a match - same "let another registered callback try" convention as
        // every other Get/Set callback in this file (see SetPropertyReal above).
        // errorCode is deliberately left untouched here.
        (void)errorCode;
        return false;
    }

    // Hand back exactly what was last written - including which optional fields it
    // carried. The stack assembles the SEQUENCE from these.
    *operation = g_lightingCommand.operation;
    *useTargetLevel = g_lightingCommand.useTargetLevel;     *targetLevel = g_lightingCommand.targetLevel;
    *useRampRate = g_lightingCommand.useRampRate;           *rampRate = g_lightingCommand.rampRate;
    *useStepIncrement = g_lightingCommand.useStepIncrement; *stepIncrement = g_lightingCommand.stepIncrement;
    *useFadeTime = g_lightingCommand.useFadeTime;           *fadeTime = g_lightingCommand.fadeTime;
    *usePriority = g_lightingCommand.usePriority;           *priority = g_lightingCommand.priority;
    return true;
}

// SET - a client commands the light. This is what a lighting controller sends.
bool SetPropertyLightingCommand(const uint32_t deviceInstance, const uint16_t objectType,
                                const uint32_t objectInstance, const uint32_t propertyIdentifier,
                                const uint32_t operation,
                                const bool useTargetLevel, const float targetLevel,
                                const bool useRampRate, const float rampRate,
                                const bool useStepIncrement, const float stepIncrement,
                                const bool useFadeTime, const uint32_t fadeTime,
                                const bool usePriority, const uint32_t priority,
                                const uint8_t priorityForWriting, uint32_t* errorCode) {
    if (deviceInstance != g_deviceInstance ||
        objectType != OBJECT_TYPE_LIGHTING_OUTPUT ||
        objectInstance != LIGHTING_OUTPUT_INSTANCE ||
        propertyIdentifier != PROPERTY_IDENTIFIER_LIGHTING_COMMAND) {
        return false;
    }

    // Validate before accepting - a conformant device refuses a bad command rather
    // than obeying it, and a refused command changes nothing. The stack range-checks
    // the fields the operation uses before it calls this callback (out of range ->
    // PROPERTY / VALUE_OUT_OF_RANGE, cl. 12.54.6); the checks below are this
    // device's own: operation NONE (in ExecuteLightingOperation), a missing
    // target-level, and the priority field.
    if (usePriority && (priority < 1 || priority > BACNET_PRIORITY_ARRAY_SIZE)) {
        *errorCode = ERROR_CODE_VALUE_OUT_OF_RANGE;
        return false;
    }
    // fadeTo and rampTo REQUIRE a target level (Table 12-67 syntax:
    // "<operation = FADE_TO> <target-level> [priority] [fade-time]"). Refuse the
    // write if it is missing rather than recording a command that never moves the
    // light.
    if ((operation == LIGHTING_OPERATION_FADE_TO || operation == LIGHTING_OPERATION_RAMP_TO) &&
        !useTargetLevel) {
        *errorCode = ERROR_CODE_VALUE_OUT_OF_RANGE;
        return false;
    }

    // Resolve the omitted optionals to this light's defaults - this is where the
    // use* flags earn their keep. A fadeTo that omitted fade-time fades over
    // Default_Fade_Time; it does NOT snap instantly because `fadeTime` arrived as 0.
    const uint32_t effectiveFadeTime = useFadeTime ? fadeTime : g_defaultFadeTime;
    const float effectiveRampRate = useRampRate ? rampRate : g_defaultRampRate;
    const float effectiveStepIncrement = useStepIncrement ? stepIncrement : g_defaultStepIncrement;
    // "If the priority field is not included with the command, the priority
    // specified in Lighting_Command_Default_Priority shall be used" (cl. 12.54.6).
    const uint8_t effectiveCommandPriority =
        (uint8_t)(usePriority ? priority : LIGHTING_COMMAND_DEFAULT_PRIORITY);

    // The Lighting Output engine (section 1b) carries the command out over time.
    if (!ExecuteLightingOperation(operation, effectiveCommandPriority, targetLevel, effectiveFadeTime,
                                  effectiveRampRate, effectiveStepIncrement, errorCode)) {
        return false;
    }

    // Accepted: remember the command so a read of Lighting_Command reports it back.
    g_lightingCommand.operation = operation;
    g_lightingCommand.useTargetLevel = useTargetLevel;     g_lightingCommand.targetLevel = targetLevel;
    g_lightingCommand.useRampRate = useRampRate;           g_lightingCommand.rampRate = rampRate;
    g_lightingCommand.useStepIncrement = useStepIncrement; g_lightingCommand.stepIncrement = stepIncrement;
    g_lightingCommand.useFadeTime = useFadeTime;           g_lightingCommand.fadeTime = fadeTime;
    g_lightingCommand.usePriority = usePriority;           g_lightingCommand.priority = priority;

    (void)priorityForWriting; // the command's own priority field is what drives the light
    return true;
}

// -----------------------------------------------------------------------------
// F-TIMESYNC - canonical implementation (B-LD is the reference for this feature;
// later series repos that need DM-TS-B copy this block verbatim, then adjust only
// the printf label). 2d. TimeSynchronization callback - the other B-LD addition
// (DM-TS-B)
//
// A lighting system broadcasts the time so every luminaire's scheduled scenes line
// up. The stack decodes the request and hands us the wall-clock fields.
//
// ONLY TimeSynchronization is registered below (BACnetStack_SetServiceEnabled,
// SERVICE_TIME_SYNCHRONIZATION, in main()) - NOT UTCTimeSynchronization. B-LD's
// profile allows DM-TS-B *or* DM-UTC-B (not both required); this example does
// local time only. Confirmed by wire test: an UTCTimeSynchronization request
// against a running instance is rejected by the stack itself with "Services is
// not supported service=[9]" before this callback is even reached. A later repo
// that needs DM-UTC-B instead (or as well) must additionally call
// BACnetStack_SetServiceEnabled(..., SERVICE_UTC_TIME_SYNCHRONIZATION, true) -
// the stack routes both services through this SAME SetSystemTime callback, so no
// second callback is needed, only the extra enable call.
//
// Local_Date / Local_Time: this callback ALSO stores the synced value into
// g_syncedDateTime (below), which GetPropertyDate/GetPropertyTime (next) serve
// back. Until the first TimeSynchronization arrives, g_syncedDateTime starts
// seeded from the real host clock (see InitSyncedDateTimeFromHost, called once at
// start-up) so a ReadProperty of Local_Date/Local_Time before any sync still
// succeeds instead of erroring value-not-initialized.
// -----------------------------------------------------------------------------
struct SyncedDateTime {
    bool valid = false;
    uint8_t yearMinus1900 = 0, month = 1, day = 1, weekday = 1;
    uint8_t hour = 0, minute = 0, second = 0, hundredthSecond = 0;
};
static SyncedDateTime g_syncedDateTime;

// Seed g_syncedDateTime from the host OS clock at start-up, so Local_Date /
// Local_Time answer something sane even before a client ever sends
// TimeSynchronization. ON REAL HARDWARE this would read the device's own RTC
// instead.
static void InitSyncedDateTimeFromHost() {
    const time_t now = time(NULL);
    struct tm parts;
#if defined(_WIN32)
    localtime_s(&parts, &now);
#else
    localtime_r(&now, &parts);
#endif
    g_syncedDateTime.yearMinus1900 = (uint8_t)parts.tm_year;
    g_syncedDateTime.month = (uint8_t)(parts.tm_mon + 1);
    g_syncedDateTime.day = (uint8_t)parts.tm_mday;
    // BACnet weekday is 1=Monday..7=Sunday; struct tm's tm_wday is 0=Sunday..6=Saturday.
    g_syncedDateTime.weekday = (uint8_t)(parts.tm_wday == 0 ? 7 : parts.tm_wday);
    g_syncedDateTime.hour = (uint8_t)parts.tm_hour;
    g_syncedDateTime.minute = (uint8_t)parts.tm_min;
    g_syncedDateTime.second = (uint8_t)parts.tm_sec;
    g_syncedDateTime.hundredthSecond = 0;
    g_syncedDateTime.valid = true;
}

bool SetSystemTime(const uint32_t deviceInstance, const uint8_t year, const uint8_t month,
                   const uint8_t day, const uint8_t weekday, const uint8_t hour,
                   const uint8_t minute, const uint8_t second, const uint8_t hundrethSeconds) {
    if (deviceInstance != g_deviceInstance) {
        return false;
    }
    // ON REAL HARDWARE: set your RTC here too. `year` is an offset from 1900, per
    // BACnet. This example instead remembers the value so Local_Date/Local_Time
    // (served below) read it back - see the block comment above.
    g_syncedDateTime.yearMinus1900 = year;
    g_syncedDateTime.month = month;
    g_syncedDateTime.day = day;
    g_syncedDateTime.weekday = weekday;
    g_syncedDateTime.hour = hour;
    g_syncedDateTime.minute = minute;
    g_syncedDateTime.second = second;
    g_syncedDateTime.hundredthSecond = hundrethSeconds;
    g_syncedDateTime.valid = true;
    printf("TimeSynchronization: %u-%02u-%02u %02u:%02u:%02u (Local_Date/Local_Time now read this back)\n",
           (unsigned)(1900 + year), month, day, hour, minute, second);
    return true;
}

// GET - Local_Date / Local_Time, from g_syncedDateTime (see the block comment
// above). Required Device properties; without this callback a ReadProperty of
// either fails value-not-initialized (confirmed by wire test before this was
// added).
bool GetPropertyDate(const uint32_t deviceInstance, const uint16_t objectType,
                     const uint32_t objectInstance, const uint32_t propertyIdentifier,
                     uint8_t* yearMinus1900, uint8_t* month, uint8_t* day, uint8_t* weekday,
                     const bool useArrayIndex, const uint32_t propertyArrayIndex,
                     uint32_t* errorCode) {
    (void)useArrayIndex;
    (void)propertyArrayIndex;
    (void)errorCode;
    if (deviceInstance != g_deviceInstance || objectType != OBJECT_TYPE_DEVICE ||
        objectInstance != g_deviceInstance ||
        propertyIdentifier != PROPERTY_IDENTIFIER_LOCAL_DATE || !g_syncedDateTime.valid) {
        return false;
    }
    *yearMinus1900 = g_syncedDateTime.yearMinus1900;
    *month = g_syncedDateTime.month;
    *day = g_syncedDateTime.day;
    *weekday = g_syncedDateTime.weekday;
    return true;
}

bool GetPropertyTime(const uint32_t deviceInstance, const uint16_t objectType,
                     const uint32_t objectInstance, const uint32_t propertyIdentifier,
                     uint8_t* hour, uint8_t* minute, uint8_t* second, uint8_t* hundredthSecond,
                     const bool useArrayIndex, const uint32_t propertyArrayIndex,
                     uint32_t* errorCode) {
    (void)useArrayIndex;
    (void)propertyArrayIndex;
    (void)errorCode;
    if (deviceInstance != g_deviceInstance || objectType != OBJECT_TYPE_DEVICE ||
        objectInstance != g_deviceInstance ||
        propertyIdentifier != PROPERTY_IDENTIFIER_LOCAL_TIME || !g_syncedDateTime.valid) {
        return false;
    }
    *hour = g_syncedDateTime.hour;
    *minute = g_syncedDateTime.minute;
    *second = g_syncedDateTime.second;
    *hundredthSecond = g_syncedDateTime.hundredthSecond;
    return true;
}

// -----------------------------------------------------------------------------
// 2e. DeviceCommunicationControl callback - inherited from B-ASC (DM-DCC-B)
//
// A management station sends DeviceCommunicationControl to tell a device to stop
// or resume communicating - useful to quiet a noisy device during commissioning.
// The CAS BACnet Stack runs the actual enable/disable state machine (and the
// optional re-enable timer) for us; this callback's job is to (a) validate the
// optional password and (b) let the application know what was asked.
//
//   enableDisable: 0 = enable (resume), 1 = disable (stop initiating AND
//                  responding), 2 = disable-initiation (keep responding).
//   useTimeDuration/timeDuration: if set, the device auto-re-enables after
//                  timeDuration minutes. The stack handles that timer.
//
// Return true to accept (the stack then applies the new communication state), or
// false with *errorCode = password-failure to reject a bad password.
//
// NOTE (Protocol_Revision >= 20): the plain "disable" value (1) is DEPRECATED.
// Even if this callback accepts it, the stack rejects the request with
// service-request-denied - the standard now expects "disable-initiation" (2)
// (the device keeps answering reads but stops initiating). So at rev 24 only
// enable (0) and disable-initiation (2) actually take effect.
// -----------------------------------------------------------------------------
bool DeviceCommunicationControl(const uint32_t deviceInstance, const uint8_t enableDisable,
                                const char* password, const uint8_t passwordLength,
                                const bool useTimeDuration, const uint16_t timeDuration,
                                uint32_t* errorCode) {
    if (deviceInstance != g_deviceInstance) {
        // Not our device. Set *errorCode even here - see the note at the end of
        // this function: a false return with *errorCode unset ships
        // "Error Code = success(84)", which is meaningless on the wire.
        *errorCode = ERROR_CODE_OPTIONAL_FUNCTIONALITY_NOT_SUPPORTED;
        return false;
    }

    // Check the password if this device requires one. A device with no configured
    // password (DCC_PASSWORD == "") accepts any request.
    //
    // Compare by LENGTH FIRST, then bytes. The reason is not buffer safety - the
    // stack hands us a null-terminated string - it is that a BACnet
    // CharacterString may legitimately contain embedded NULs, and strcmp would
    // silently compare only up to the first one. Never strcmp a wire string.
    //
    // On a mismatch we set *errorCode = password-failure, and the stack pairs
    // that specific code with Error Class = SECURITY (clause 16.1.1.3.1).
    //
    // NOTE ON SECURITY, because this is a tutorial and the honest answer matters:
    // a DCC password crosses the wire in PLAINTEXT. This is not a security
    // boundary - it is a guard against accidents. Anyone who can time this
    // compare can simply sniff the password instead. If you need real protection,
    // use BACnet/SC. (Do not read the accumulator loop below as a constant-time
    // compare: the printf on the reject path dwarfs any timing signal it removes.)
    const size_t requiredLength = strlen(DCC_PASSWORD);
    if (requiredLength > 0) {
        bool matches = (password != NULL) && (passwordLength == requiredLength);
        if (matches) {
            for (size_t i = 0; i < requiredLength; ++i) {
                if (password[i] != DCC_PASSWORD[i]) {
                    matches = false;
                    break;
                }
            }
        }
        if (!matches) {
            printf("DeviceCommunicationControl: REJECTED (password failure)\n");
            *errorCode = ERROR_CODE_PASSWORD_FAILURE;
            return false;
        }
    }

    // NOTE: the stack applies the deprecation rule AFTER this callback. For the
    // deprecated plain "disable" (1) at Protocol_Revision >= 20 it overrides our
    // acceptance and answers service-request-denied - so the line we print for
    // that case reflects the request received, not a state the device entered.
    const char* action = (enableDisable == DCC_ENABLE) ? "enable (resume communication)" :
                         (enableDisable == DCC_DISABLE) ? "disable (1) - DEPRECATED, the stack will reject this" :
                         (enableDisable == DCC_DISABLE_INITIATION) ? "disable-initiation (keep responding)" :
                         "unknown";
    if (useTimeDuration) {
        printf("DeviceCommunicationControl: %s for %u minute(s)\n", action, timeDuration);
    } else {
        printf("DeviceCommunicationControl: %s (indefinitely)\n", action);
    }
    // Section 2e follows initiation for Channel 1's remote member: the stack refuses
    // to send it a write while initiation is disabled and reports nothing.
    if (enableDisable == DCC_DISABLE_INITIATION) {
        g_initiationDisabled = true;
        g_initiationDisabledUntilSet = useTimeDuration;
        g_initiationDisabledUntilMs = NowMilliseconds() + (uint64_t)timeDuration * 60000;
    } else if (enableDisable == DCC_ENABLE) {
        g_initiationDisabled = false;
    }
    // Accept. Nothing to write to *errorCode on the success path.
    //
    // IMPORTANT, AND IT IS NOT WHAT YOU WOULD GUESS: this callback MUST set
    // *errorCode on EVERY `false` return. The DCC path has no default. The stack
    // pre-initialises errorCode to BACnetErrorCode::success (which is 84, NOT 0)
    // and then, on a false return, does:
    //     if (errorCode == passwordFailure) -> Error Class SECURITY
    //     else                              -> Error Class SERVICES, code = errorCode
    // So returning false without setting *errorCode puts the literal nonsense
    // "Error Class = SERVICES, Error Code = success(84)" on the wire.
    //
    // This differs from the SetProperty* callbacks, which DO have a sensible
    // fallback (writeAccessDenied) - so do not carry the habit across.
    return true;
}

// -----------------------------------------------------------------------------
// 2d. F-CHANNEL / F-EXTWRITE / F-SCHED-E - canonical implementation.
//
// This repo (B-LS) is the series' canonical example for all three of these
// features; a later example that needs any of them copies this section.
// -----------------------------------------------------------------------------

// WriteGroup execution delay (DS-WG-E-B). The stack asks, per Channel, whether
// to honour that Channel's own Execution_Delay (added alongside each reference
// in AddObjectPropertyReferenceToChannel) or skip straight to writing. This
// example has no reason to delay a demo write, so it always answers "do not
// inhibit" (false) - i.e. respect whatever delay was configured (here, zero).
// A real device might return true while, say, a manual override is active.
bool WriteGroupInhibitDelay(const uint32_t deviceInstance, const uint32_t channelInstance,
                            const bool inhibitDelay) {
    (void)inhibitDelay; // this is the CALLER's inhibit-delay flag on the incoming request
    if (deviceInstance != g_deviceInstance || channelInstance != CHANNEL_INSTANCE) {
        return false;
    }
    // The stack asks this just before it writes Channel 1 for a WriteGroup, so it
    // also marks the writes that follow, this tick, as the WriteGroup's fan-out
    // (section 2e).
    g_writeGroupExecuting = true;
    return false; // never inhibit - respect each reference's configured Execution_Delay
}

// The remote member's I-Am (DM-DDB-A: this device's Who-Is, or the remote
// device announcing itself). The stack binds the device's address from the same
// I-Am; the application keeps a copy to recognise the answers to the stack's
// WriteProperty to it (section 2e).
void HookIAm(const uint32_t deviceIdentifier, const uint32_t maxApduLengthAccepted,
             const uint8_t segmentationSupported, const uint16_t vendorIdentifier,
             const uint8_t* connectionString, const uint8_t connectionStringLength,
             const uint32_t networkPortInstance, const uint16_t sourceNetwork,
             const uint8_t* sourceAddress, const uint8_t sourceAddressLength) {
    (void)maxApduLengthAccepted;
    (void)segmentationSupported;
    (void)vendorIdentifier;
    (void)networkPortInstance;
    (void)sourceAddress;
    (void)sourceAddressLength;
    if (deviceIdentifier != REMOTE_DEVICE_INSTANCE || sourceNetwork != 0 ||
        connectionStringLength != REMOTE_DEVICE_ADDRESS_LENGTH) {
        return; // not the remote member, or not on this network
    }
    if (!g_remoteDeviceKnown || memcmp(g_remoteDeviceAddress, connectionString, REMOTE_DEVICE_ADDRESS_LENGTH) != 0) {
        memcpy(g_remoteDeviceAddress, connectionString, REMOTE_DEVICE_ADDRESS_LENGTH);
        g_remoteDeviceKnown = true;
        printf("I-Am: remote device %u is at %u.%u.%u.%u:%u - Channel 1 can write to it now.\n",
               REMOTE_DEVICE_INSTANCE, connectionString[0], connectionString[1], connectionString[2],
               connectionString[3], (unsigned)((connectionString[4] << 8) | connectionString[5]));
    }
}

// The answers to the stack's WriteProperty to the remote member (section 2e). A
// SimpleACK is success; an Error, Reject or Abort - or no answer at all, which
// the stack reports through HookTimeout - is a failure (cl. 12.53.7).
void HookSimpleAck(const uint8_t originalInvokeId, const uint32_t serverAckChoice,
                   const uint8_t* connectionString, const uint8_t connectionStringLength,
                   const uint32_t networkPortInstance, const uint16_t sourceNetwork,
                   const uint8_t* sourceAddress, const uint8_t sourceAddressLength) {
    (void)originalInvokeId; (void)networkPortInstance; (void)sourceNetwork; (void)sourceAddress; (void)sourceAddressLength;
    if (serverAckChoice == SERVICE_WRITE_PROPERTY) {
        NoteRemoteMemberAnswer(connectionString, connectionStringLength, true, "SimpleACK");
    }
}

void HookError(const uint8_t originalInvokeId, const uint32_t errorChoice, const uint32_t errorClass,
               const uint32_t errorCode, const uint8_t* connectionString, const uint8_t connectionStringLength,
               const uint32_t networkPortInstance, const uint16_t sourceNetwork, const uint8_t* sourceAddress,
               const uint8_t sourceAddressLength, const bool useObjectProperty, const uint16_t objectType,
               const uint32_t objectInstance, const uint32_t propertyIdentifier) {
    (void)originalInvokeId; (void)networkPortInstance; (void)sourceNetwork; (void)sourceAddress; (void)sourceAddressLength;
    (void)useObjectProperty; (void)objectType; (void)objectInstance; (void)propertyIdentifier;
    if (errorChoice == SERVICE_WRITE_PROPERTY) {
        char what[64];
        snprintf(what, sizeof(what), "Error (class %u, code %u)", errorClass, errorCode);
        NoteRemoteMemberAnswer(connectionString, connectionStringLength, false, what);
    }
}

void HookReject(const uint8_t originalInvokeId, const uint32_t rejectReason,
                const uint8_t* connectionString, const uint8_t connectionStringLength,
                const uint32_t networkPortInstance, const uint16_t sourceNetwork,
                const uint8_t* sourceAddress, const uint8_t sourceAddressLength) {
    (void)originalInvokeId; (void)rejectReason; (void)networkPortInstance; (void)sourceNetwork; (void)sourceAddress;
    (void)sourceAddressLength;
    NoteRemoteMemberAnswer(connectionString, connectionStringLength, false, "Reject");
}

void HookAbort(const uint8_t originalInvokeId, const bool sentByServer, const uint32_t abortReason,
               const uint8_t* connectionString, const uint8_t connectionStringLength,
               const uint32_t networkPortInstance, const uint16_t sourceNetwork,
               const uint8_t* sourceAddress, const uint8_t sourceAddressLength) {
    (void)originalInvokeId; (void)sentByServer; (void)abortReason; (void)networkPortInstance; (void)sourceNetwork;
    (void)sourceAddress; (void)sourceAddressLength;
    NoteRemoteMemberAnswer(connectionString, connectionStringLength, false, "Abort");
}

void HookTimeout(const uint8_t originalInvokeId, const uint8_t* connectionString,
                 const uint8_t connectionStringLength, const uint32_t networkPortInstance,
                 const uint16_t sourceNetwork, const uint8_t* sourceAddress, const uint8_t sourceAddressLength) {
    (void)originalInvokeId; (void)networkPortInstance; (void)sourceNetwork; (void)sourceAddress; (void)sourceAddressLength;
    NoteRemoteMemberAnswer(connectionString, connectionStringLength, false, "no answer (timeout)");
}

// 'd' key (DiscoverRemote): a manual Who-Is so the stack's Device_Address_Binding
// resolver (see the header comment's "HOW THE REMOTE WRITE ACTUALLY HAPPENS")
// can learn the remote device's address on demand, for the demo - normally the
// DAB's own periodic heartbeat would eventually find it without this.
static void SendDiscoverRemoteWhoIs() {
    const uint8_t bcast[6] = { 255, 255, 255, 255,
                               (uint8_t)((g_bacnetIpUdpPort >> 8) & 0xFF),
                               (uint8_t)(g_bacnetIpUdpPort & 0xFF) };
    if (BACnetStack_SendWhoIs(bcast, 6, NETWORK_PORT_INSTANCE, true, 0, NULL, 0)) {
        printf("SendWhoIs: broadcast, looking for device %u (the remote target).\n",
               REMOTE_DEVICE_INSTANCE);
    } else {
        printf("Error: SendWhoIs failed.\n");
    }
}

// 'w' key (WriteGroupDemo): originate a REAL WriteGroup service request (DS-WG-E-B
// is what this device EXECUTES when it *receives* one - this key exercises that
// same execution path end-to-end by broadcasting one naming Channel 1's own
// Control_Groups entry). Any device on the subnet with a matching Channel -
// including, typically, this one, since a broadcast reaches the sender's own
// socket too - fans the value out to every reference added with
// AddObjectPropertyReferenceToChannel: Lighting Output 1 (Jade) locally, and the
// remote object on REMOTE_DEVICE_INSTANCE via the stack's own DAB-resolved
// outbound WriteProperty (see the header comment).
static void SendWriteGroupDemo() {
    static float g_demoLevel = 0.0f;
    g_demoLevel = (g_demoLevel < 50.0f) ? 100.0f : 0.0f; // alternate 0% / 100% each press

    uint8_t buffer[32];
    CASPropertyBuffer pb;
    CASPropertyBuffer_Init(&pb, buffer, sizeof(buffer));
    // WriteGroup values are RAW BINARY (see BACnetStack_SendWriteGroup's "VALUE
    // ENCODING" block) - a Real is 4 bytes IEEE-754 little-endian, not text.
    if (!CASPropertyBuffer_AppendWriteGroupEntry(&pb, (uint16_t)g_channelControlGroups[0],
                                                 8 /*overridingPriority*/, 4 /*Real*/,
                                                 &g_demoLevel, sizeof(g_demoLevel))) {
        printf("Error: failed to pack the demo WriteGroup change-list.\n");
        return;
    }
    const uint8_t bcast[6] = { 255, 255, 255, 255,
                               (uint8_t)((g_bacnetIpUdpPort >> 8) & 0xFF),
                               (uint8_t)(g_bacnetIpUdpPort & 0xFF) };
    if (BACnetStack_SendWriteGroup(g_channelControlGroups[0], 8, pb.count, pb.buffer, pb.length,
                                   false /*useInhibitDelay*/, false /*inhibitDelay*/,
                                   bcast, 6, NETWORK_PORT_INSTANCE, true /*broadcast*/,
                                   0, NULL, 0)) {
        printf("SendWriteGroup: control group %u <- %.1f%% @ priority 8 (broadcast).\n"
               "     Watch for Channel 1 (Garnet) and Lighting Output 1 (Jade) to update,\n"
               "     and for a WriteProperty to reach the remote device (%u).\n",
               g_channelControlGroups[0], g_demoLevel, REMOTE_DEVICE_INSTANCE);
    } else {
        printf("Error: SendWriteGroup failed.\n");
    }
}

// -----------------------------------------------------------------------------
// 3. main()
// -----------------------------------------------------------------------------
int main(int argc, char** argv) {
    // Show printf output immediately, even when stdout is piped to a file.
    setvbuf(stdout, NULL, _IONBF, 0);

    // F-TIMESYNC: seed Local_Date/Local_Time from the host clock so they read
    // back something valid even before any TimeSynchronization arrives.
    InitSyncedDateTimeFromHost();

    // --- Load the CAS BACnet Stack -------------------------------------------
    // Required in every link mode (source/static/DLL) before any other
    // BACnetStack_* call - see CASBACnetStackAdapter.h. In DLL mode this is the
    // step that actually resolves the symbols; skipping it there is a null-pointer
    // call, not a silent no-op, so it comes before even --version (which calls
    // BACnetStack_GetAPIMajorVersion() to print the linked stack's version).
    if (!LoadBACnetFunctions()) {
        fprintf(stderr, "Error: failed to load the CAS BACnet Stack: %s\n",
                CASBACnetStackAdapter_LastError());
        return 1;
    }

    // g_firmwareRevision (Device object property 44) - see its own doc
    // comment above for why this is the STACK's version, not this example's
    // own (that's Application_Software_Version/APP_VERSION instead). Must
    // happen after LoadBACnetFunctions() (these getters ARE some of the
    // functions it loads) and before the Device object is ever readable.
    {
        char buf[32];
        snprintf(buf, sizeof(buf), "%u.%u.%u.%u",
                 BACnetStack_GetAPIMajorVersion(), BACnetStack_GetAPIMinorVersion(),
                 BACnetStack_GetAPIPatchVersion(), BACnetStack_GetAPIBuildVersion());
        g_firmwareRevision = buf;
    }

    // --- Command line + version --------------------------------------------
    // --help / --version print and exit, so handle them before we bind a socket
    // or touch the stack.
    // The help lists only the options this example reads: no --dcc-password (the
    // DeviceCommunicationControl password is DCC_PASSWORD in this file, not a
    // command-line option), and --deviceName (read below).
    if (CASExampleHelper::HandleHelpAndVersionArgs(argc, argv, APP_NAME, APP_VERSION,
                                                   false,   // no --dcc-password
                                                   true)) { // --deviceName
        return 0;
    }
    const uint16_t port = CASExampleHelper::ParsePortArg(argc, argv, 47808);
    g_deviceInstance = CASExampleHelper::ParseDeviceIdArg(argc, argv, g_deviceInstance);
    g_deviceName = CASExampleHelper::ParseDeviceNameArg(argc, argv, DEVICE_NAME);
    CASExampleHelper::ParseXmlLogArg(argc, argv); // --xml: dump every RX/TX frame as XML instead of one line (off by default)
    CASExampleHelper::PrintVersion(APP_NAME, APP_VERSION);

    // --- Bind the BACnet/IP socket -----------------------------------------
    if (!CASExampleHelper::SetupUDP(port)) {
        return 1;
    }

    // Capture the BACnet/IP addressing the Network Port object will report.
    g_bacnetIpUdpPort = port;
    if (!CASExampleHelper::GetLocalIPv4(g_ipAddress, g_ipSubnetMask)) {
        printf("FYI: could not read a local IPv4 address; Network Port IP_Address "
               "will report 0.0.0.0.\n");
    }

    // --- Register callbacks -------------------------------------------------
    // The transport + time callbacks are shared boilerplate.
    CASExampleHelper::RegisterCommonCallbacks();
    // The property callbacks are specific to this example.
    BACnetStack_RegisterCallbackGetPropertyReal(GetPropertyReal);
    BACnetStack_RegisterCallbackGetPropertyEnumerated(GetPropertyEnumerated);
    BACnetStack_RegisterCallbackGetPropertyUnsignedInteger(GetPropertyUnsignedInteger);
    BACnetStack_RegisterCallbackGetPropertyCharacterString(GetPropertyCharString);
    BACnetStack_RegisterCallbackGetPropertyBool(GetPropertyBool);
    BACnetStack_RegisterCallbackGetPropertyOctetString(GetPropertyOctetString);
    // F-TIMESYNC: Local_Date / Local_Time, served from g_syncedDateTime.
    BACnetStack_RegisterCallbackGetPropertyDate(GetPropertyDate);
    BACnetStack_RegisterCallbackGetPropertyTime(GetPropertyTime);
    // The "set" callbacks accept WriteProperty (DS-WP-B) to the commandable
    // outputs. One callback per written data type, plus the NULL callback that
    // relinquishes a priority slot.
    BACnetStack_RegisterCallbackSetPropertyReal(SetPropertyReal);
    BACnetStack_RegisterCallbackSetPropertyEnumerated(SetPropertyEnumerated);
    BACnetStack_RegisterCallbackSetPropertyUnsignedInteger(SetPropertyUnsignedInteger);
    BACnetStack_RegisterCallbackSetPropertyNull(SetPropertyNull);
    // The DeviceCommunicationControl callback makes this a B-ASC (DM-DCC-B).
    BACnetStack_RegisterCallbackDeviceCommunicationControl(DeviceCommunicationControl);
    // The Lighting_Command callbacks make this a B-LD (DS-LO-B). These are typed
    // callbacks: the stack assembles / decodes the BACnetLightingCommand SEQUENCE
    // and we deal only in plain numbers. See section 2c.
    BACnetStack_RegisterCallbackGetPropertyLightingCommand(GetPropertyLightingCommand);
    BACnetStack_RegisterCallbackSetPropertyLightingCommand(SetPropertyLightingCommand);
    // TimeSynchronization (DM-TS-B / DM-UTC-B) - a lighting system tells us what
    // time it is, local or UTC; the stack routes both through this one callback.
    BACnetStack_RegisterCallbackSetSystemTime(SetSystemTime);
    // F-CHANNEL / DS-WG-E-B: the only application hook into WriteGroup execution -
    // see the WriteGroupInhibitDelay comment above. Everything else about
    // executing an incoming WriteGroup (matching Channel_Number/Control_Groups,
    // fanning the write out to List_Of_Object_Property_References, including the
    // remote reference via the DAB) is entirely stack-internal.
    BACnetStack_RegisterCallbackWriteGroupInhibitDelay(WriteGroupInhibitDelay);
    // Section 2e: the remote member's I-Am, and the answers to the stack's
    // WriteProperty to it, which is how Write_Status learns how the fan-out went.
    BACnetStack_RegisterHookIAm(HookIAm);
    BACnetStack_RegisterHookSimpleAck(HookSimpleAck);
    BACnetStack_RegisterHookError(HookError);
    BACnetStack_RegisterHookReject(HookReject);
    BACnetStack_RegisterHookAbort(HookAbort);
    BACnetStack_RegisterHookTimeout(HookTimeout);

    // --- Create the device --------------------------------------------------
    if (!BACnetStack_AddDevice(g_deviceInstance)) {
        printf("Error: Failed to add the Device %u.\n", g_deviceInstance);
        return 1;
    }

    // Enable the three services a B-ASC must execute: ReadProperty (DS-RP-B),
    // WriteProperty (DS-WP-B), and DeviceCommunicationControl (DM-DCC-B). We set
    // them explicitly to make the profile requirements obvious.
    //
    // We deliberately do NOT enable ReadPropertyMultiple, SubscribeCOV, or any
    // alarm/event service: an Application Specific Controller does not require
    // them, so a faithful B-ASC example leaves them off.
    if (!BACnetStack_SetServiceEnabled(g_deviceInstance, SERVICE_READ_PROPERTY, true)) {
        printf("Error: Failed to enable the ReadProperty service.\n");
        return 1;
    }
    if (!BACnetStack_SetServiceEnabled(g_deviceInstance, SERVICE_WRITE_PROPERTY, true)) {
        printf("Error: Failed to enable the WriteProperty service.\n");
        return 1;
    }
    if (!BACnetStack_SetServiceEnabled(g_deviceInstance, SERVICE_DEVICE_COMMUNICATION_CONTROL, true)) {
        printf("Error: Failed to enable the DeviceCommunicationControl service.\n");
        return 1;
    }
    // TimeSynchronization (DM-TS-B / DM-UTC-B) - the profile requires both here.
    if (!BACnetStack_SetServiceEnabled(g_deviceInstance, SERVICE_TIME_SYNCHRONIZATION, true) ||
        !BACnetStack_SetServiceEnabled(g_deviceInstance, SERVICE_UTC_TIME_SYNCHRONIZATION, true)) {
        printf("Error: Failed to enable the TimeSynchronization / UTCTimeSynchronization services.\n");
        return 1;
    }
    // WriteGroup (DS-WG-E-B, service 40) - this device EXECUTES incoming
    // WriteGroup requests against Channel 1 (Garnet). Verified against
    // source/BACnetServicesSupported.h at the pin.
    if (!BACnetStack_SetServiceEnabled(g_deviceInstance, SERVICE_WRITE_GROUP, true)) {
        printf("Error: Failed to enable the WriteGroup service.\n");
        return 1;
    }

    // Discovery: Who-Is/I-Am (DM-DDB-B) and Who-Has/I-Have (DM-DOB-B).
    //
    // These need enabling even though the device already ANSWERS them. The
    // stack's service defaults are whoIs + whoHas + readProperty only
    // (BACnetDBDevice.cpp) - iAm and iHave are left FALSE. Who-Is is answered and
    // the start-up I-Am is sent regardless, because neither is gated on the bit;
    // but Protocol_Services_Supported is emitted verbatim from that bitstring, so
    // without these calls the device DOES I-Am and I-Have while telling every
    // client it supports neither. The README claims DM-DDB-B and DM-DOB-B; this
    // is what makes the claim true on the wire.
    if (!BACnetStack_SetServiceEnabled(g_deviceInstance, SERVICE_WHO_IS, true) ||
        !BACnetStack_SetServiceEnabled(g_deviceInstance, SERVICE_I_AM, true) ||
        !BACnetStack_SetServiceEnabled(g_deviceInstance, SERVICE_WHO_HAS, true) ||
        !BACnetStack_SetServiceEnabled(g_deviceInstance, SERVICE_I_HAVE, true)) {
        printf("Error: Failed to enable the discovery services (Who-Is/I-Am, Who-Has/I-Have).\n");
        return 1;
    }
    // --- Add the read-only sensor objects -----------------------------------
    // Every stack setup call returns a bool; a real device should always check
    // it, so this example does too.
    if (!BACnetStack_AddObject(g_deviceInstance, OBJECT_TYPE_ANALOG_INPUT, ANALOG_INPUT_INSTANCE)) {
        printf("Error: Failed to add Analog Input %u (Bronze).\n", ANALOG_INPUT_INSTANCE);
        return 1;
    }
    if (!BACnetStack_AddObject(g_deviceInstance, OBJECT_TYPE_BINARY_INPUT, BINARY_INPUT_INSTANCE)) {
        printf("Error: Failed to add Binary Input %u (Emerald).\n", BINARY_INPUT_INSTANCE);
        return 1;
    }
    if (!BACnetStack_AddObject(g_deviceInstance, OBJECT_TYPE_MULTI_STATE_INPUT, MULTI_STATE_INPUT_INSTANCE)) {
        printf("Error: Failed to add Multi-State Input %u (Hot Pink).\n", MULTI_STATE_INPUT_INSTANCE);
        return 1;
    }

    // --- Add the commandable OUTPUT objects (the B-SA additions) -------------
    // These accept WriteProperty. We make each one commandable below.
    if (!BACnetStack_AddObject(g_deviceInstance, OBJECT_TYPE_ANALOG_OUTPUT, ANALOG_OUTPUT_INSTANCE)) {
        printf("Error: Failed to add Analog Output %u (Chartreuse).\n", ANALOG_OUTPUT_INSTANCE);
        return 1;
    }
    if (!BACnetStack_AddObject(g_deviceInstance, OBJECT_TYPE_BINARY_OUTPUT, BINARY_OUTPUT_INSTANCE)) {
        printf("Error: Failed to add Binary Output %u (Fuchsia).\n", BINARY_OUTPUT_INSTANCE);
        return 1;
    }
    if (!BACnetStack_AddObject(g_deviceInstance, OBJECT_TYPE_MULTI_STATE_OUTPUT, MULTI_STATE_OUTPUT_INSTANCE)) {
        printf("Error: Failed to add Multi-State Output %u (Indigo).\n", MULTI_STATE_OUTPUT_INSTANCE);
        return 1;
    }

    // --- Add the Lighting Output (from B-LD; the supervised local target) ----
    if (!BACnetStack_AddObject(g_deviceInstance, OBJECT_TYPE_LIGHTING_OUTPUT, LIGHTING_OUTPUT_INSTANCE)) {
        printf("Error: Failed to add Lighting Output %u (Jade).\n", LIGHTING_OUTPUT_INSTANCE);
        return 1;
    }

    // --- Add Channel 1 "Garnet" (F-CHANNEL) - the profile-defining object ----
    // presentValueDatatype = Real (4): Channel 1 fans a REAL level out to Jade's
    // REAL Present_Value and to the remote object's (also REAL) Present_Value.
    // See BACnetStack_AddChannelObject's doc: this call creates the stack-held
    // Present_Value datatype selector + an initially-empty
    // List_Of_Object_Property_References; the object itself still needs the
    // plain AddObject first.
    if (!BACnetStack_AddObject(g_deviceInstance, OBJECT_TYPE_CHANNEL, CHANNEL_INSTANCE)) {
        printf("Error: Failed to add Channel %u (Garnet).\n", CHANNEL_INSTANCE);
        return 1;
    }
    if (!BACnetStack_AddChannelObject(g_deviceInstance, CHANNEL_INSTANCE, 4 /*Real*/)) {
        printf("Error: Failed to configure Channel %u (Garnet)'s Present_Value datatype.\n",
               CHANNEL_INSTANCE);
        return 1;
    }
    // Reference 1: LOCAL - Lighting Output 1 (Jade)'s Present_Value. A WriteGroup
    // matching this Channel writes here directly (no DAB involved - it's local).
    if (!BACnetStack_AddObjectPropertyReferenceToChannel(
            g_deviceInstance, CHANNEL_INSTANCE, OBJECT_TYPE_LIGHTING_OUTPUT, LIGHTING_OUTPUT_INSTANCE,
            PROPERTY_IDENTIFIER_PRESENT_VALUE, false, 0, false, 0, 0 /*executionDelay*/)) {
        printf("Error: Failed to add Channel %u's local reference to Jade.\n", CHANNEL_INSTANCE);
        return 1;
    }
    // Reference 2: REMOTE (F-EXTWRITE) - REMOTE_DEVICE_INSTANCE's Lighting
    // Output's Present_Value. refUseDeviceIdentifier = true names an explicit
    // remote device; per the doc this ALSO registers it with the stack's
    // Device_Address_Binding, starting background resolution for it (see the
    // header comment's "HOW THE REMOTE WRITE ACTUALLY HAPPENS").
    if (!BACnetStack_AddObjectPropertyReferenceToChannel(
            g_deviceInstance, CHANNEL_INSTANCE, REMOTE_OBJECT_TYPE, REMOTE_OBJECT_INSTANCE,
            PROPERTY_IDENTIFIER_PRESENT_VALUE, false, 0, true, REMOTE_DEVICE_INSTANCE, 0)) {
        printf("Error: Failed to add Channel %u's remote reference to device %u.\n",
               CHANNEL_INSTANCE, REMOTE_DEVICE_INSTANCE);
        return 1;
    }

    // --- Add Schedule 1 "Saffron" and Calendar 1 "Cream" (F-SCHED-E) ---------
    // Calendar 1 is a real, independently-readable object (ReadProperty of its
    // Object_Name / Object_Type / Property_List all work); see the header
    // comment + TODO.md for the one documented Date_List gap. The Schedule's
    // OWN exception-event scheduling below does NOT depend on that gap - it
    // uses the direct date/period form, AddScheduleExceptionEventWithCalendarEntry,
    // which the stack docs confirm is fully functional (unlike
    // AddScheduleExceptionEventWithCalendarReference - stack issue #963).
    if (!BACnetStack_AddObject(g_deviceInstance, OBJECT_TYPE_CALENDAR, CALENDAR_INSTANCE)) {
        printf("Error: Failed to add Calendar %u (Cream).\n", CALENDAR_INSTANCE);
        return 1;
    }
    if (!BACnetStack_AddObject(g_deviceInstance, OBJECT_TYPE_SCHEDULE, SCHEDULE_INSTANCE)) {
        printf("Error: Failed to add Schedule %u (Saffron).\n", SCHEDULE_INSTANCE);
        return 1;
    }
    if (!BACnetStack_AddScheduleObject(g_deviceInstance, SCHEDULE_INSTANCE)) {
        printf("Error: Failed to configure Schedule %u (Saffron).\n", SCHEDULE_INSTANCE);
        return 1;
    }
    // What the Schedule writes: a daily 09:00 "on" (100%) / 17:00 "off" (0%)
    // Weekly_Schedule, every day of the week (dayOffset 0..6 = Mon..Sun).
    for (uint8_t dayOffset = 0; dayOffset < 7; ++dayOffset) {
        if (!BACnetStack_AddScheduleWeeklyTimeValue(g_deviceInstance, SCHEDULE_INSTANCE, dayOffset,
                                                    9, 0, 0, 0, 4 /*Real*/, 0, 100.0f) ||
            !BACnetStack_AddScheduleWeeklyTimeValue(g_deviceInstance, SCHEDULE_INSTANCE, dayOffset,
                                                    17, 0, 0, 0, 4 /*Real*/, 0, 0.0f)) {
            printf("Error: Failed to add Schedule %u's Weekly_Schedule entries.\n", SCHEDULE_INSTANCE);
            return 1;
        }
    }
    if (!BACnetStack_SetScheduleDefault(g_deviceInstance, SCHEDULE_INSTANCE, 4 /*Real*/, 0, 0.0f)) {
        printf("Error: Failed to set Schedule %u's Schedule_Default.\n", SCHEDULE_INSTANCE);
        return 1;
    }
    if (!BACnetStack_SetScheduleEffectivePeriod(g_deviceInstance, SCHEDULE_INSTANCE,
                                                0, 1, 1, 0, 12, 31)) { // any year, Jan 1 .. Dec 31
        printf("Error: Failed to set Schedule %u's Effective_Period.\n", SCHEDULE_INSTANCE);
        return 1;
    }
    // Priority_For_Writing: the priority the Schedule's driven writes land at.
    // Chosen below Channel 1's own demo priority (8) so a manual 'w' key press
    // can override the Schedule's own commands, and above 16 (relinquish) so it
    // is never accidentally the lowest.
    if (!BACnetStack_SetSchedulePriorityForWriting(g_deviceInstance, SCHEDULE_INSTANCE, 12)) {
        printf("Error: Failed to set Schedule %u's Priority_For_Writing.\n", SCHEDULE_INSTANCE);
        return 1;
    }
    // What the Schedule drives: Channel 1 (Garnet)'s Present_Value, at
    // Priority_For_Writing (12). A Channel has no Priority_Array property
    // (Table 12-62), so the reference names Present_Value, the property a
    // Schedule writes with a priority (cl. 12.24.11, as a WriteProperty would).
    // cl. 12.53.5: the Channel then propagates the value to its members, Jade and
    // device 389016, and Write_Status follows those writes (section 2e).
    if (!BACnetStack_AddScheduleObjectPropertyReference(
            g_deviceInstance, SCHEDULE_INSTANCE, g_deviceInstance, OBJECT_TYPE_CHANNEL,
            CHANNEL_INSTANCE, PROPERTY_IDENTIFIER_PRESENT_VALUE, false, 0)) {
        printf("Error: Failed to point Schedule %u at Channel %u.\n",
               SCHEDULE_INSTANCE, CHANNEL_INSTANCE);
        return 1;
    }
    // A demo exception event for TODAY, from 00:00:05 until midnight, so the
    // Schedule is already writing 100% to Channel 1 when the device starts,
    // whatever the time of day, without waiting for a real 09:00/17:00. (It is
    // not "a few seconds after start-up": the time is 00:00:05 of today's date.)
    // The direct date/period form (periodType 0 = a specific calendar Date).
    {
        time_t nowT = time(NULL);
        struct tm nowTm;
#if defined(_WIN32)
        localtime_s(&nowTm, &nowT);
#else
        localtime_r(&nowT, &nowTm);
#endif
        uint32_t exceptionIndex = 0;
        if (!BACnetStack_AddScheduleExceptionEventWithCalendarEntry(
                g_deviceInstance, SCHEDULE_INSTANCE, 0 /*periodType: Date*/,
                (uint16_t)(nowTm.tm_year + 1900), (uint8_t)(nowTm.tm_mon + 1), (uint8_t)nowTm.tm_mday,
                255 /*any weekday*/, 0, 255, 255, 255, 1 /*eventPriority*/, &exceptionIndex) ||
            !BACnetStack_AddScheduleExceptionTimeValue(g_deviceInstance, SCHEDULE_INSTANCE, exceptionIndex,
                                                       0, 0, 5, 0, 4 /*Real*/, 0, 100.0f)) {
            printf("Error: Failed to add Schedule %u's demo exception event.\n", SCHEDULE_INSTANCE);
            return 1;
        }
    }

    // --- Add the Network Port object ----------------------------------------
    // Every BACnet device (Protocol_Revision 17+) must have at least one Network
    // Port object describing the port it talks on. This one is the BACnet/IP
    // application port; it is the lowest layer, so its reference port is "none".
    // networkNumber 0 with quality "unknown" describes a local port that has not
    // learned its network number - the right answer for a device that is not a
    // router and has not been told one.
    if (!BACnetStack_AddNetworkPortObject(
            g_deviceInstance, NETWORK_PORT_INSTANCE,
            NETWORK_PORT_NETWORK_TYPE_IPV4,
            NETWORK_PORT_PROTOCOL_LEVEL_BACNET_APPLICATION,
            0,  // networkNumber: not configured
            NETWORK_NUMBER_QUALITY_UNKNOWN,
            NETWORK_PORT_REFERENCE_PORT_NONE)) {
        printf("Error: Failed to add Network Port 1 (Vermilion).\n");
        return 1;
    }

    // --- Enable the OPTIONAL properties we choose to expose ------------------
    // The stack automatically enables an object's REQUIRED properties when the
    // object is added (AddObject / AddNetworkPortObject) - so Units, Polarity,
    // Number_Of_States, Out_Of_Service, and the Network Port's BACnet/IP
    // addressing (IP_Address, IP_Subnet_Mask, BACnet_IP_UDP_Port, ...) are
    // already enabled; our Get* callbacks just supply their values. Only
    // OPTIONAL properties need SetPropertyEnabled. State_Text is optional on a
    // Multi-State Input, so we enable it here (and serve it in GetPropertyCharString).
    //
    // The Device's Description is optional too, and it is an easy one to get
    // wrong: serving it from a Get callback is NOT enough. The stack checks
    // IsPropertyEnabled BEFORE it ever reaches the callbacks, and for an optional
    // property that check falls back to "is it required?" - which is false. So a
    // Description branch in the callback without this enable is DEAD CODE, and
    // the client reads back Error: unknown-property. (This example shipped
    // exactly that bug; it was caught by a reviewer tracing the stack source, not
    // by running it - a plausible-looking callback branch that never executes.)
    if (!BACnetStack_SetPropertyEnabled(g_deviceInstance, OBJECT_TYPE_DEVICE,
                                        g_deviceInstance, PROPERTY_IDENTIFIER_DESCRIPTION, true)) {
        printf("Error: Failed to enable Description on the Device object.\n");
        return 1;
    }

    if (!BACnetStack_SetPropertyEnabled(g_deviceInstance, OBJECT_TYPE_MULTI_STATE_INPUT,
                                        MULTI_STATE_INPUT_INSTANCE, PROPERTY_IDENTIFIER_STATE_TEXT, true)) {
        printf("Error: Failed to enable State_Text on Multi-State Input 1 (Hot Pink).\n");
        return 1;
    }

    // --- Make the output objects commandable --------------------------------
    // A commandable object's Present_Value is resolved from a 16-slot
    // Priority_Array plus a Relinquish_Default: a WriteProperty sets a slot,
    // writing NULL relinquishes it, and the highest-priority non-null slot (or
    // Relinquish_Default) wins.
    //
    // WORTH KNOWING BEFORE YOU COPY THIS: for ANALOG/BINARY/MULTI-STATE OUTPUT
    // the three calls below are effectively NO-OPS. They reproduce the
    // stack's own defaults. Verified in the stack source:
    //   - Present_Value on an Analog Output already defaults to required AND
    //     writable (BACnetDBPropertyProfile.cpp: presentValue -> SetProperty(
    //     true, true, Real)), and Priority_Array / Relinquish_Default default to
    //     required - so AddObject already enabled all three; and
    //   - IsPropertyCommandable() (BACnetBusinessLogic.cpp) returns true for
    //     analogOutput / binaryOutput / multiStateOutput Present_Value
    //     UNCONDITIONALLY - it consults no enable at all.
    // Delete this loop and these objects still accept WriteProperty. Nothing
    // here "flips the object into commandable mode"; the stack already did.
    //
    // So why keep it? Because it states the commandable contract in one visible
    // place, and because it becomes LOAD-BEARING the moment you copy this pattern
    // to an optionally-commandable type - Analog Value, Binary Value, Multi-State
    // Value. There Priority_Array / Relinquish_Default default to OPTIONAL (not
    // enabled), and IsPropertyCommandable() explicitly requires BOTH to be
    // enabled before it will treat the object as commandable. Omit these calls on
    // an Analog Value and it silently is not commandable.
    //
    // Carry the INSTANCE alongside the type rather than assuming instance 1. On
    // these output types the distinction is benign (see above) - but it is fatal
    // on a Value type, where the enable must land on the exact object you mean.
    // Say what you mean, so the pattern stays correct when it is copied.
    struct CommandableObject { uint16_t type; uint32_t instance; };
    const CommandableObject outputs[] = {
        { OBJECT_TYPE_ANALOG_OUTPUT,      ANALOG_OUTPUT_INSTANCE },
        { OBJECT_TYPE_BINARY_OUTPUT,      BINARY_OUTPUT_INSTANCE },
        { OBJECT_TYPE_MULTI_STATE_OUTPUT, MULTI_STATE_OUTPUT_INSTANCE },
        { OBJECT_TYPE_LIGHTING_OUTPUT,    LIGHTING_OUTPUT_INSTANCE },
    };
    for (size_t i = 0; i < sizeof(outputs) / sizeof(outputs[0]); ++i) {
        if (!BACnetStack_SetPropertyEnabled(g_deviceInstance, outputs[i].type, outputs[i].instance,
                                            PROPERTY_IDENTIFIER_PRIORITY_ARRAY, true) ||
            !BACnetStack_SetPropertyEnabled(g_deviceInstance, outputs[i].type, outputs[i].instance,
                                            PROPERTY_IDENTIFIER_RELINQUISH_DEFAULT, true) ||
            !BACnetStack_SetPropertyWritable(g_deviceInstance, outputs[i].type, outputs[i].instance,
                                             PROPERTY_IDENTIFIER_PRESENT_VALUE, true)) {
            printf("Error: Failed to make object type %u instance %u commandable.\n",
                   outputs[i].type, outputs[i].instance);
            return 1;
        }
    }

    // --- Make Lighting_Command writable (the B-LD addition) ------------------
    // Lighting_Command is REQUIRED *and WRITABLE* on a Lighting Output (cl. 12.54.9)
    // - writing it is what commands the light, so DS-LO-B is not satisfied without
    // this. The stack already enabled the property on AddObject (it is required);
    // marking it writable is what lets a client write it and routes the write to
    // our SetPropertyLightingCommand callback.
    //
    // The dimming defaults and Egress_Time are this device's choice (Table 12-64
    // lists them "R", which allows writable), so a lighting system can tune them;
    // each Set callback range-checks what it accepts.
    const uint32_t lightingWritableProperties[] = {
        PROPERTY_IDENTIFIER_LIGHTING_COMMAND,
        PROPERTY_IDENTIFIER_DEFAULT_FADE_TIME,
        PROPERTY_IDENTIFIER_DEFAULT_RAMP_RATE,
        PROPERTY_IDENTIFIER_DEFAULT_STEP_INCREMENT,
        PROPERTY_IDENTIFIER_EGRESS_TIME,
    };
    for (size_t propertyIndex = 0;
         propertyIndex < sizeof(lightingWritableProperties) / sizeof(lightingWritableProperties[0]);
         ++propertyIndex) {
        if (!BACnetStack_SetPropertyWritable(g_deviceInstance, OBJECT_TYPE_LIGHTING_OUTPUT,
                                             LIGHTING_OUTPUT_INSTANCE, lightingWritableProperties[propertyIndex],
                                             true)) {
            printf("Error: Failed to make property %u of Lighting Output 1 (Jade) writable.\n",
                   lightingWritableProperties[propertyIndex]);
            return 1;
        }
    }

    // --- Make Channel_Number and Control_Groups writable (F-CHANNEL) ---------
    // Per BACnetStack_AddChannelObject's doc, these two are REQUIRED and
    // writable on a Channel, served entirely by the application (the stack does
    // not auto-enable Channel-specific properties the way it does for the
    // standard input/output types above). Channel 1's Present_Value is already
    // writable - AddChannelObject configures that as part of setting up the
    // datatype selector.
    if (!BACnetStack_SetPropertyEnabled(g_deviceInstance, OBJECT_TYPE_CHANNEL, CHANNEL_INSTANCE,
                                        PROPERTY_IDENTIFIER_CHANNEL_NUMBER, true) ||
        !BACnetStack_SetPropertyWritable(g_deviceInstance, OBJECT_TYPE_CHANNEL, CHANNEL_INSTANCE,
                                         PROPERTY_IDENTIFIER_CHANNEL_NUMBER, true) ||
        !BACnetStack_SetPropertyEnabled(g_deviceInstance, OBJECT_TYPE_CHANNEL, CHANNEL_INSTANCE,
                                        PROPERTY_IDENTIFIER_CONTROL_GROUPS, true) ||
        !BACnetStack_SetPropertyWritable(g_deviceInstance, OBJECT_TYPE_CHANNEL, CHANNEL_INSTANCE,
                                         PROPERTY_IDENTIFIER_CONTROL_GROUPS, true)) {
        printf("Error: Failed to make Channel 1 (Garnet)'s Channel_Number/Control_Groups writable.\n");
        return 1;
    }

    // Who-Is is answered automatically. The spec also requires a device to
    // announce itself on start-up, so broadcast an unsolicited I-Am now (to the
    // local subnet broadcast - the Network Port's own network).
    CASExampleHelper::SendIAm(g_deviceInstance);

    printf("FYI: Device %u (\"%s\") ready. Vendor ID %u. Press 'h' for help.\n",
           g_deviceInstance, g_deviceName, VENDOR_IDENTIFIER);
    printf("FYI: Lighting Output 1 (Jade) starts at %.1f%% (off). WriteProperty its\n"
           "     Lighting_Command to fade/ramp/step/warn it, or its Present_Value to set a level.\n",
           ResolveLightingLevel(&g_lightingOutput));
    printf("FYI: Channel 1 (Garnet) fans a WriteGroup out to Jade AND remote device %u.\n"
           "     Press 'd' to discover it (Who-Is), then 'w' to fire a demo WriteGroup.\n"
           "     Schedule 1 (Saffron) writes Channel 1 at 09:00/17:00 daily; a demo\n"
           "     exception for today (from 00:00:05) has it writing 100%% now.\n",
           REMOTE_DEVICE_INSTANCE);

    // --- Run the stack ------------------------------------------------------
    // BACnetStack_Tick() processes incoming messages and timers. LightingTick()
    // moves Jade's fades and ramps and runs its egress timers (section 1b). Call
    // both continuously, and poll the keyboard for interactive commands.
    bool running = true;
    while (running) {
        BACnetStack_Tick();
        LightingTick();
        // Section 2e: a write to Channel 1 (WriteProperty, WriteGroup or Schedule 1)
        // fanned out inside that tick. The local member has answered; the remote one
        // answers later, through the hooks.
        g_writeGroupExecuting = false;
        if (g_fanOutStartedThisTick) {
            g_fanOutStartedThisTick = false;
            FinishChannelFanOutIfDone();
        }

        switch (CASExampleHelper::PollKey()) {
            case CASExampleHelper::KeyCommand::Help:
                CASExampleHelper::PrintHelp(APP_NAME, APP_VERSION);
                break;
            case CASExampleHelper::KeyCommand::Quit:
                running = false;
                break;
            case CASExampleHelper::KeyCommand::ArrowUp:
                g_analogInput1Value += 1.1f;
                printf("Analog Input 1 (Bronze) = %.1f C\n", g_analogInput1Value);
                break;
            case CASExampleHelper::KeyCommand::ArrowDown:
                g_analogInput1Value -= 1.1f;
                printf("Analog Input 1 (Bronze) = %.1f C\n", g_analogInput1Value);
                break;
            case CASExampleHelper::KeyCommand::WriteGroupDemo: // 'w' - F-CHANNEL / DS-WG-E-B
                SendWriteGroupDemo();
                break;
            case CASExampleHelper::KeyCommand::DiscoverRemote: // 'd' - F-EXTWRITE
                SendDiscoverRemoteWhoIs();
                break;
            case CASExampleHelper::KeyCommand::None:
            default:
                break;
        }

#if defined(_WIN32)
        Sleep(1); // 1 ms - be a good citizen, don't spin the CPU
#else
        usleep(1000);
#endif
    }

    CASExampleHelper::RestoreInput();
    CASExampleHelper::ShutdownUDP();
    return 0;
}
