# wiretest changelog

The shared Wiretest Harness of the BACnet profile example series. Vendored into each
example; `WIRETEST_VERSION` in `__init__.py` names the version.

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
