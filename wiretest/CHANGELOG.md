# wiretest changelog

The shared Wiretest Harness of the BACnet profile example series. Vendored into each
example; `WIRETEST_VERSION` in `__init__.py` names the version.

## [0.7.0] - 2026-10-16

Folds in the generic helpers the round-3 Profile-functional reworks of B-SS, B-SA,
B-ASC, B-LD, B-EM, B-EC, B-AEC, B-OD, B-LSC and B-ALSC wrote while 0.6.0 was frozen,
deduplicated. Additive: every 0.6.0 call keeps its meaning (B-LS, B-BC and B-AAC's
Wire Tests pass unchanged against it).

### Deduplicated

- ONE quick-retry mechanism: `Client(retries=, timeout=)` and now
  `Workstation(retries=, timeout=)` share `client.send_with_retries` (same invoke id,
  a `[RETRY]` line per resend). It replaces B-SS / B-SA / B-ASC's per-call
  `timeout=` with `retries=3`, B-LD's `Client(retries=2)` with a 1 s per-call timeout,
  B-EM / B-EC's `ask()` (a new invoke id per retry), B-AEC's `RetryingWorkstation` and
  B-LSC / B-ALSC's `request_with_retry()`.
- ONE ReadPropertyMultiple client (`services.read_property_multiple_request`,
  `parse_read_property_multiple_ack`, `decode_result`; `Client` / `Workstation`
  `.read_property_multiple()`), from B-EM / B-EC's `property_multiple.py` (keyed by
  object) and B-AEC's (array indexes): results are
  `{(object_type, instance): {property or (property, index): octets or ('error', class, code)}}`.
  `codec.read_access_specification` takes `(property, index)` pairs.
- ONE ReadRange decoder (`services.read_range_request`, `parse_read_range_ack`,
  `event_log_records`), from B-AEC's `aec_services.py` and B-ALSC's verbatim copy.
- ONE simulation-control client (`control.SimulationControl`: `ask()` -> text or None,
  `send()` raises; visible `[RETRY]`), from B-EM / B-EC's `simulation_control.py` and
  B-LSC / B-ALSC's `wiretest_extras.SimulationControl`.
- ONE BACnetLandingCallStatus encoder / decoder (`services.landing_call_status`,
  `decode_landing_calls`), from B-EC's `landing_call.py` and B-AEC's.
- ONE server: B-OD's `CommandableServer` is folded into `peer.SimulatedServer` as
  options, off by default - `commandable=` (a 16-slot priority array per object,
  cl. 19.2, and cl. 19.2.1's NULL to a non-commandable property), `array_elements=True`
  (an indexed read answers that element; 0.6.0 ignored the index), `failures`
  (scripted Reject / Abort / silent / malformed) and `whole_arrays_refused`.

### Added

- `codec`: `parse_read_property_request(apdu, with_array_index=True)` returns the array
  index as a fourth item (the default 3-tuple is unchanged; B-OD); `reject_pdu`,
  `abort_pdu`, `application_elements` (B-OD); `application_signed`,
  `application_octet_string`, `context_signed` (B-AEC); `context_real` (B-LD, B-OD);
  `context_boolean` (B-EM, B-OD); `context_bit_string` (B-OD); the object types,
  properties, error classes / codes, Reject / Abort reasons, ReinitializeDevice
  backup / restore states, `RELIABILITY_MULTI_STATE_FAULT` and `DEVICE_STATUS_*` those
  helpers name.
- `services` (new): the RPM client, ReadRange, CreateObject / DeleteObject and
  AtomicReadFile / AtomicWriteFile (B-AEC); SubscribeCOVPropertyMultiple and
  `CovNotificationMultiple` (B-EM / B-EC `cov_multiple.py`); LifeSafetyOperation and
  the life-safety enumerations (B-LSC); BACnetLightingCommand `lighting_command` /
  `decode_lighting_command` (B-LD); BACnetLandingCallStatus. Each `parse_*` takes the
  request's `Answer`.
- `client`: `Answer.acked`, `Answer.reject_reason` (B-SS) and `Answer.abort_reason`;
  `Client(timeout=)`; `device_communication_control()` and `Client.who_is()` (B-ASC).
- `workstation`: `retries=`, `timeout=`, `announce()` (B-LSC), and the shared calls.
- `alarm`: `event_notification()` - a Peer's out-of-range Confirmed- /
  UnconfirmedEventNotification (B-OD); `EVENT_STATE_LIFE_SAFETY_ALARM`,
  `EVENT_TYPE_CHANGE_OF_LIFE_SAFETY` (B-LSC), `EVENT_TYPE_CHANGE_OF_STATE`,
  `EVENT_TYPE_CHANGE_OF_RELIABILITY` (B-EM), `DCC_DISABLE`,
  `ERROR_CODE_SERVICE_REQUEST_DENIED` (B-ASC).
- `peer`: `SimulatedDevice.send()` and `simple_acks()` (B-OD).
- `process`: `Program.wait_for_text(text, seconds, after)` (B-OD); `IAmBroadcasts` - a
  device's I-Am heartbeat counted on the wire (POSIX) and in its console (B-ASC's
  `Heartbeats`).
- `control` (new): `SimulationControl` (above) and `CommandFile` (B-OD).
- `wait`: `sample()`, `sleep_until()` and `monotonic()` (B-LD).

## [0.6.0] - 2026-10-15

Folds in the generic helpers the phase-2 reworks of B-LS, B-BC and B-AAC wrote while
0.5.0 was frozen, deduplicated, on top of B-BBMD's 0.5.0. Additive: every 0.5.0 call
keeps its meaning.

### Added

- `codec`: `simple_ack` (B-LS and B-AAC each had one), `write_group_request`,
  `parse_write_property_request` and `context_values` (B-LS); `status_flags` and
  `read_property_multiple_ack` (B-BC); `application_bit_string`, `application_date`,
  `application_time`, `context_character_string` and `context_enumerated` (B-AAC);
  constants `SERVICE_WRITE_GROUP`, `SERVICE_READ_PROPERTY_MULTIPLE`, `ERROR_CODE_BUSY`,
  `PROPERTY_DEVICE_ADDRESS_BINDING`, `PROPERTY_EVENT_STATE`,
  `PROPERTY_LIST_OF_OBJECT_PROPERTY_REFERENCES` and `RELIABILITY_UNRELIABLE_OTHER`.
- `peer.SimulatedServer`: one Peer class in place of B-LS's `CommandablePeer` and B-BC's
  `HumidityPeer`. Objects whose values are octets or callables; ReadProperty,
  ReadPropertyMultiple and WriteProperty; `writable`, `check_write()` and `on_write()`
  hooks; `mode` online / offline / refusing; `read_requests`, `write_requests`,
  `requests_while_offline`, `reads()`, `writes_matching()`; `announce()`.
- `alarm` (from B-AAC's `alarm_codec.py`): AcknowledgeAlarm, GetEventInformation and its
  ACK parser, DeviceCommunicationControl, TimeSynchronization, BACnetDestination,
  BACnetTimeStamp, `EventNotification`, `date_time_text`.
- `workstation.Workstation` (from B-AAC): a client that also receives event
  notifications, answering confirmed ones from a background thread unless told not to.
- `wait.wait_until` (from B-BC).

## [0.5.0] - 2026-10-15

Added for B-BBMD's wire tests (foreign devices and peer BBMDs talking Annex J to the
example), on top of B-ACDC's 0.4.0; nothing in it is BBMD-specific. Additive: every
0.4.0 call keeps its meaning.

### Added

- `codec`: every Annex J BVLL message - `bvll()` for any function; builders for
  Register-Foreign-Device, Read-/Write-Broadcast-Distribution-Table,
  Read-Foreign-Device-Table, Delete-Foreign-Device-Table-Entry,
  Distribute-Broadcast-To-Network and Forwarded-NPDU; the BVLC function and
  BVLC-Result code constants (`BVLC_RESULT_*`, J.2.1.1); `reinitialize_device_request`
  with `SERVICE_REINITIALIZE_DEVICE` and `REINITIALIZE_COLDSTART` / `_WARMSTART` /
  `_ACTIVATE_CHANGES`; `context_octet_string`.
- `codec.Frame`: decodes BVLL-only messages (`ok` True, `has_npdu` False), including
  4-octet ones such as an empty Read-Foreign-Device-Table-Ack, which 0.4.0 rejected as
  too short; adds `bvll_data`, `result_code`, `bdt_entries()`, `fdt_entries()` and a
  Forwarded-NPDU's `originating_mac`; `describe()` shows both. A predicate on
  `invoke_id`, `pdu_type`, `service` or `network_message` sees `None` for a BVLL-only
  message, so 0.4.0 tests behave as before.
- `endpoint.Endpoint`: `ip`, `mac` (the socket's B/IP address) and `clear()`.

### Fixed

- `endpoint.Endpoint` no longer raises on Windows when an earlier send drew an ICMP
  port-unreachable (`ConnectionResetError` on the next receive); the receive goes on.
- `peer.SimulatedDevice` no longer stops answering on Windows for the same reason: its
  receive loop treated `ConnectionResetError` (an `OSError`) as "socket closed" and
  ended silently.

## [0.4.0] - 2026-10-14

Added for B-ACDC's wire tests (a client that commands a door and reads it back), on top
of B-GW's 0.3.0; nothing in it is door-specific. Additive: every 0.3.0 call keeps its
meaning (the `Client` retry is off unless asked for).

### Added

- `client.Client(..., retries=N)`: an unanswered request is sent again with the same
  invoke id, up to N times (cl. 5.4.4 TimeoutUnsegmented), each retry printing a
  `[RETRY]` line. Default 0.
- `codec`: `application_boolean`; `decoded_values` (every application primitive in a
  value - a Property_List, a whole Priority_Array); `PROPERTY_OUT_OF_SERVICE`,
  `PROPERTY_PROPERTY_LIST`, `PROPERTY_CURRENT_COMMAND_PRIORITY`,
  `ERROR_CODE_VALUE_OUT_OF_RANGE`.
- `process`: `Program.press(keys)` - type menu keys on an example's stdin (POSIX only:
  common/'s `PollKey()` reads a pipe there, not on Windows).

### Fixed

- `process.Program` starts the example by its absolute path: on Windows a relative
  `--exe build/Release/X.exe` (forward slashes) was not found by `CreateProcess`.

(B-ACDC first numbered these additions 0.2.0, then 0.3.0, before B-RTR's 0.2.0 and
B-GW's 0.3.0 were known; neither of those B-ACDC copies was ever published.)

## [0.3.0] - 2026-10-14

Added for B-GW's wire tests; nothing in it is gateway-specific. Additive: every 0.2.0
call keeps its meaning.

### Added

- `client`: `Client` (an `Endpoint` that numbers invoke ids and waits for the matching
  answer) with `request`, `read_property` and `write_property`, each optionally addressed
  through a router (`dnet=`, `dadr=`); `Answer` (`ok`, `value`, `value_octets`, `error`).
- `codec`: `write_property_request` (priority, array index), `read_property_request`
  takes an optional `array_index`; `application_null`, `application_real`;
  `decode_application` (NULL, BOOLEAN, Unsigned, Signed, REAL, Double,
  CharacterString, BIT STRING, Enumerated, ObjectIdentifier), `application_tag`,
  `error_class_and_code`; constants for Analog/Binary Output, Description, Object_List,
  Priority_Array, Reliability, Relinquish_Default, Status_Flags, the
  BACnetReliability values a gateway reports, the Status_Flags bit positions and the
  application tag numbers.
- `process`: `start(..., environment=)` / `Program(..., environment=)` - extra
  environment variables for the example, for a test-only switch an example reads and
  its command line never offers.

## [0.2.0] - 2026-10-14

### Added

- `peer.SimulatedDevice(..., broadcast=(broadcast_ip, udp_port))`: a second socket, bound
  to that broadcast address with SO_REUSEADDR (POSIX), so the Peer hears the broadcasts on
  the network it stands on - a Who-Is a router re-broadcasts there - and answers them from
  its own socket like any other request. `received_on_broadcast` lists the frames that
  arrived on it. Without the argument the Peer is unchanged.
- `codec.i_am_device_instance(apdu)`: the Device instance an I-Am announces.

## [0.1.0] - 2026-10-14

First cut, written for B-RTR's wire tests and kept free of anything router-specific.

### Added

- `codec`: BVLC (Original-Unicast/Broadcast, Forwarded-NPDU decode), NPDU encode/decode
  with DNET/DADR, SNET/SADR, hop count and network layer messages, APDU builders
  (ReadProperty request/ComplexACK, Error, Who-Is, I-Am, AddListElement /
  RemoveListElement, ReadAccessSpecification), tag reader and value helpers.
- `endpoint`: `Endpoint` (send, collect, wait_for) and `broadcast_listener` (POSIX).
- `process`: `Program` / `start` for an example binary, `broadcast_address` from
  common/'s TX console line, `default_exe`.
- `peer`: `SimulatedDevice`, a Python BACnet/IP device that answers ReadProperty and
  Who-Is and addresses answers back through a router (DNET/DADR from SNET/SADR).
- `results`: `record`, `known_gap`, `summary`.
