# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""Encode the confirmed services, and decode the ACKs and constructed values, that a Wire
Test needs beyond ReadProperty / WriteProperty (codec) and the alarm services (alarm).

    ReadPropertyMultiple   read_property_multiple_request, parse_read_property_multiple_ack,
                           decode_result (cl. 15.7) - the CLIENT side; codec has the server's
    ReadRange              read_range_request, parse_read_range_ack, event_log_records (cl. 15.8;
                           BACnetEventLogRecord, cl. 21)
    object access          create_object_request, created_object_identifier, delete_object_request
                           (cl. 15.3, 15.4)
    files                  atomic_read_file_request, parse_atomic_read_file_ack,
                           atomic_write_file_request, parse_atomic_write_file_ack (cl. 14.1, 14.2,
                           stream access)
    COV                    subscribe_cov_property_multiple_request, is_cov_notification_multiple,
                           CovNotificationMultiple (cl. 13.16, 13.17 / 13.18)
    life safety            life_safety_operation_request (cl. 13.13) and the life-safety enumerations
    values                 landing_call_status / decode_landing_calls (BACnetLandingCallStatus),
                           lighting_command / decode_lighting_command (BACnetLightingCommand)

Every parse_* function takes the wiretest.Answer of the request and returns None unless that
answer is the ComplexACK it decodes. Productions are from ANSI/ASHRAE 135-2024 clause 21
(21.2 confirmed services, 21.3 unconfirmed services, 21.6 base types). Each one is a plain
BACnet encoding; nothing here knows what an example does with it. Came from B-EM / B-EC
(property_multiple.py, cov_multiple.py, landing_call.py), B-AEC (aec_services.py), B-LSC /
B-ALSC (wiretest_extras.py) and B-LD (ld_setup.py) (wiretest 0.7.0).
"""
import struct

from . import codec
from .codec import (application_object_id, application_octet_string, application_signed,  # noqa: F401
                    application_unsigned, closing, confirmed_request, context_boolean, context_character_string,
                    context_enumerated, context_object_id, context_real, context_unsigned, opening, read_tag)

# BACnetConfirmedServiceChoice / BACnetUnconfirmedServiceChoice (cl. 21).
SERVICE_ATOMIC_READ_FILE = 6
SERVICE_ATOMIC_WRITE_FILE = 7
SERVICE_CREATE_OBJECT = 10
SERVICE_DELETE_OBJECT = 11
SERVICE_READ_RANGE = 26
SERVICE_LIFE_SAFETY_OPERATION = 27
SERVICE_SUBSCRIBE_COV_PROPERTY_MULTIPLE = 30
SERVICE_CONFIRMED_COV_NOTIFICATION_MULTIPLE = 31
SERVICE_UNCONFIRMED_COV_NOTIFICATION_MULTIPLE = 11

# BACnetLifeSafetyOperation (cl. 21).
LIFE_SAFETY_OPERATION_NONE = 0
LIFE_SAFETY_OPERATION_SILENCE = 1
LIFE_SAFETY_OPERATION_SILENCE_AUDIBLE = 2
LIFE_SAFETY_OPERATION_SILENCE_VISUAL = 3
LIFE_SAFETY_OPERATION_RESET = 4
LIFE_SAFETY_OPERATION_RESET_ALARM = 5
LIFE_SAFETY_OPERATION_RESET_FAULT = 6
LIFE_SAFETY_OPERATION_UNSILENCE = 7

# BACnetLifeSafetyState (cl. 21), the values the examples use.
LIFE_SAFETY_STATE_QUIET = 0
LIFE_SAFETY_STATE_ALARM = 2
LIFE_SAFETY_STATE_FAULT = 3

# BACnetSilencedState (cl. 21).
SILENCED_UNSILENCED = 0
SILENCED_AUDIBLE = 1
SILENCED_VISIBLE = 2
SILENCED_ALL = 3

# BACnetLiftCarDirection (cl. 21).
LIFT_CAR_DIRECTION_UNKNOWN = 0
LIFT_CAR_DIRECTION_NONE = 1
LIFT_CAR_DIRECTION_STOPPED = 2
LIFT_CAR_DIRECTION_UP = 3
LIFT_CAR_DIRECTION_DOWN = 4
LIFT_CAR_DIRECTION_UP_AND_DOWN = 5

# BACnetLightingOperation and BACnetLightingInProgress (cl. 21).
LIGHTING_OPERATION_NONE = 0
LIGHTING_OPERATION_FADE_TO = 1
LIGHTING_OPERATION_RAMP_TO = 2
LIGHTING_OPERATION_STEP_UP = 3
LIGHTING_OPERATION_STEP_DOWN = 4
LIGHTING_OPERATION_STEP_ON = 5
LIGHTING_OPERATION_STEP_OFF = 6
LIGHTING_OPERATION_WARN = 7
LIGHTING_OPERATION_WARN_OFF = 8
LIGHTING_OPERATION_WARN_RELINQUISH = 9
LIGHTING_OPERATION_STOP = 10
LIGHTING_OPERATION_RESTORE_ON = 11
LIGHTING_OPERATION_DEFAULT_ON = 12
LIGHTING_OPERATION_TOGGLE_RESTORE = 13
LIGHTING_OPERATION_TOGGLE_DEFAULT = 14
LIGHTING_IN_PROGRESS_IDLE = 0
LIGHTING_IN_PROGRESS_FADE_ACTIVE = 1
LIGHTING_IN_PROGRESS_RAMP_ACTIVE = 2


def _complex_ack(answer, service=None):
    """The ComplexACK APDU in `answer` (of `service`, if given), or None."""
    frame = answer.frame if answer is not None else None
    if frame is None or frame.pdu_type != codec.PDU_COMPLEX_ACK:
        return None
    if service is not None and frame.service != service:
        return None
    return frame.payload


def _object_identifier(body):
    raw = struct.unpack(">I", body)[0]
    return raw >> 22, raw & codec.MAX_INSTANCE


def _constructed_end(octets, position):
    """`position` is just after an opening tag: the position just after its closing tag."""
    depth = 1
    while depth:
        _, _, kind, _, position = read_tag(octets, position)
        depth += {"open": 1, "close": -1}.get(kind, 0)
    return position


def _constructed_body(octets, position):
    """`position` is just after an opening tag: (the octets inside it, position after its closing tag)."""
    start = position
    depth = 1
    while True:
        tag_start = position
        _, _, kind, _, position = read_tag(octets, position)
        depth += {"open": 1, "close": -1}.get(kind, 0)
        if depth == 0:
            return octets[start:tag_start], position


# ---------------------------------------------------------------------------
# ReadPropertyMultiple (cl. 15.7) - one consistent snapshot of several properties
# ---------------------------------------------------------------------------

def read_property_multiple_request(invoke_id, specifications):
    """ReadPropertyMultiple-Request. `specifications`: [(object_type, instance, [reference, ...])],
    each reference a property identifier or a (property identifier, array index) pair."""
    parameters = b"".join(codec.read_access_specification(object_type, instance, references)
                          for object_type, instance, references in specifications)
    return confirmed_request(invoke_id, codec.SERVICE_READ_PROPERTY_MULTIPLE, parameters)


def parse_read_property_multiple_ack(answer):
    """A ReadPropertyMultiple-ACK (cl. 21.2: ReadAccessResult, cl. 21.6) as
    {(object_type, instance): {reference: result}}, or None. `reference` is the property
    identifier, or (property identifier, array index) when the result carried an index; `result`
    is the application-tagged value octets, or ('error', error class, error code) for a
    property-access-error. One RPM is ONE answer, so its values are a consistent snapshot."""
    apdu = _complex_ack(answer, codec.SERVICE_READ_PROPERTY_MULTIPLE)
    if apdu is None:
        return None
    results = {}
    current = None
    property_identifier = None
    array_index = None
    position = 3
    try:
        while position < len(apdu):
            number, is_context, kind, body, position = read_tag(apdu, position)
            if kind == "value" and is_context and number == 0:
                current = results.setdefault(_object_identifier(body), {})
            elif kind == "value" and is_context and number == 2:
                property_identifier, array_index = int.from_bytes(body, "big"), None
            elif kind == "value" and is_context and number == 3:
                array_index = int.from_bytes(body, "big")
            elif kind == "open" and number in (4, 5) and current is not None:
                inner, position = _constructed_body(apdu, position)
                reference = property_identifier if array_index is None else (property_identifier, array_index)
                if number == 4:
                    current[reference] = inner
                else:
                    current[reference] = ("error",) + tuple(int.from_bytes(value, "big")
                                                            for _, value in codec.application_values(inner)[:2])
    except (IndexError, struct.error):
        return None
    return results


def decode_result(result):
    """One RPM result decoded: value octets -> codec.decode_application(); an ('error', class,
    code) tuple, or None (not in the ACK), passes through unchanged."""
    if result is None or isinstance(result, tuple):
        return result
    return codec.decode_application(result)


# ---------------------------------------------------------------------------
# ReadRange (cl. 15.8) and the Event Log's records
# ---------------------------------------------------------------------------

def read_range_request(invoke_id, object_type, instance, property_identifier, reference_index=None, count=None):
    """ReadRange-Request; with reference_index and count, the by-position range [3];
    without, no range (the whole list)."""
    parameters = context_object_id(0, object_type, instance) + context_unsigned(1, property_identifier)
    if reference_index is not None:
        parameters += opening(3) + application_unsigned(reference_index) + application_signed(count) + closing(3)
    return confirmed_request(invoke_id, SERVICE_READ_RANGE, parameters)


def parse_read_range_ack(answer):
    """A ReadRange-ACK as {result_flags, item_count, item_data (the octets inside [5])}, or None."""
    apdu = _complex_ack(answer, SERVICE_READ_RANGE)
    if apdu is None:
        return None
    result = {"result_flags": None, "item_count": None, "item_data": b""}
    position = 3
    try:
        while position < len(apdu):
            number, is_context, kind, body, after = read_tag(apdu, position)
            if is_context and kind == "value" and number == 3:
                result["result_flags"] = codec.decode_application(bytes([0x80 | len(body)]) + body)
            elif is_context and kind == "value" and number == 4:
                result["item_count"] = int.from_bytes(body, "big")
            elif is_context and kind == "open" and number == 5:
                result["item_data"], after = _constructed_body(apdu, after)
            elif kind == "open":
                after = _constructed_end(apdu, after)
            position = after
    except (IndexError, struct.error):
        return None
    return result


def _notification_fields(octets):
    """The top-level context-tagged primitives of an EventNotification-Request's parameters
    (cl. 21.2), as {tag number: value bytes}; constructed ones are skipped."""
    fields = {}
    position = 0
    while position < len(octets):
        number, is_context, kind, body, position = read_tag(octets, position)
        if kind == "open":
            position = _constructed_end(octets, position)
        elif is_context and kind == "value":
            fields[number] = body
    return fields


def event_log_records(item_data):
    """BACnetEventLogRecords (cl. 21) from a ReadRange-ACK's item data, each as a dict:
    timestamp (the raw octets), kind 'status' / 'notification' / 'time-change', and for a
    notification its process_identifier, initiating_device, event_object, from_state,
    to_state and the raw notification octets."""
    records = []
    position = 0
    while position < len(item_data):
        number, is_context, kind, _, position = read_tag(item_data, position)    # [0] timestamp open
        if not (is_context and number == 0 and kind == "open"):
            break
        timestamp_start = position
        position = _constructed_end(item_data, position)
        record = {"timestamp": item_data[timestamp_start:position]}
        number, is_context, kind, _, position = read_tag(item_data, position)    # [1] log-datum open
        number, is_context, kind, body, inner = read_tag(item_data, position)    # the CHOICE
        if number == 0 and kind == "value":                                     # log-status [0] BIT STRING
            record["kind"] = "status"
            record["log_status"] = body
            position = inner
        elif number == 1 and kind == "open":                                    # notification [1] SEQUENCE
            record["kind"] = "notification"
            end = _constructed_end(item_data, inner)
            notification = item_data[inner:end]
            fields = _notification_fields(notification)
            record["notification"] = notification
            record["process_identifier"] = int.from_bytes(fields.get(0, b"\x00"), "big")
            record["initiating_device"] = _object_identifier(fields[1]) if 1 in fields else None
            record["event_object"] = _object_identifier(fields[2]) if 2 in fields else None
            record["from_state"] = int.from_bytes(fields[10], "big") if 10 in fields else None
            record["to_state"] = int.from_bytes(fields[11], "big") if 11 in fields else None
            position = end
        else:
            record["kind"] = "time-change"
            position = inner
        position = read_tag(item_data, position)[4]                             # [1] log-datum close
        records.append(record)
    return records


# ---------------------------------------------------------------------------
# CreateObject / DeleteObject (cl. 15.3, 15.4)
# ---------------------------------------------------------------------------

def create_object_request(invoke_id, object_type, instance=None, initial_values=()):
    """CreateObject-Request. With `instance`, the object-specifier is the object-identifier
    choice [1]; without, the object-type choice [0] (the device picks the instance).
    `initial_values`: [(property identifier, application-tagged value octets)]."""
    if instance is None:
        specifier = context_unsigned(0, object_type)
    else:
        specifier = context_object_id(1, object_type, instance)
    parameters = opening(0) + specifier + closing(0)
    if initial_values:
        parameters += opening(1)
        for property_identifier, value_octets in initial_values:
            parameters += context_unsigned(0, property_identifier) + opening(2) + value_octets + closing(2)
        parameters += closing(1)
    return confirmed_request(invoke_id, SERVICE_CREATE_OBJECT, parameters)


def created_object_identifier(answer):
    """(object type, instance) from a CreateObject-ACK (an application BACnetObjectIdentifier), or None."""
    apdu = _complex_ack(answer)
    if apdu is None:
        return None
    value = codec.decode_application(apdu[3:])
    return value if isinstance(value, tuple) else None


def delete_object_request(invoke_id, object_type, instance):
    return confirmed_request(invoke_id, SERVICE_DELETE_OBJECT, application_object_id(object_type, instance))


# ---------------------------------------------------------------------------
# AtomicReadFile / AtomicWriteFile, stream access (cl. 14.1, 14.2)
# ---------------------------------------------------------------------------

def atomic_read_file_request(invoke_id, file_instance, start, requested_count):
    return confirmed_request(invoke_id, SERVICE_ATOMIC_READ_FILE,
                             application_object_id(codec.OBJECT_TYPE_FILE, file_instance) + opening(0) +
                             application_signed(start) + application_unsigned(requested_count) + closing(0))


def parse_atomic_read_file_ack(answer):
    """(end_of_file, file_start_position, file_data) from a stream-access AtomicReadFile-ACK, or None."""
    apdu = _complex_ack(answer)
    if apdu is None:
        return None
    try:
        _, _, _, eof_body, position = read_tag(apdu, 3)
        number, is_context, kind, _, position = read_tag(apdu, position)
        if not (is_context and number == 0 and kind == "open"):
            return None
        _, _, _, start_body, position = read_tag(apdu, position)
        _, _, _, data, position = read_tag(apdu, position)
        return bool(eof_body[0]), int.from_bytes(start_body, "big", signed=True), data
    except (IndexError, struct.error):
        return None


def atomic_write_file_request(invoke_id, file_instance, start, data):
    return confirmed_request(invoke_id, SERVICE_ATOMIC_WRITE_FILE,
                             application_object_id(codec.OBJECT_TYPE_FILE, file_instance) + opening(0) +
                             application_signed(start) + application_octet_string(data) + closing(0))


def parse_atomic_write_file_ack(answer):
    """The file-start-position [0] of an AtomicWriteFile-ACK, or None."""
    apdu = _complex_ack(answer)
    if apdu is None:
        return None
    number, is_context, kind, body, _ = read_tag(apdu, 3)
    if not (is_context and number == 0 and kind == "value"):
        return None
    return int.from_bytes(body, "big", signed=True)


# ---------------------------------------------------------------------------
# SubscribeCOVPropertyMultiple and COVNotificationMultiple (DS-COVM)
# ---------------------------------------------------------------------------

def subscribe_cov_property_multiple_request(invoke_id, process_identifier, confirmed, lifetime, specifications,
                                            max_notification_delay=0):
    """SubscribeCOVPropertyMultiple-Request (cl. 21.2): subscriber-process-identifier [0],
    issue-confirmed-notifications [1], lifetime [2], max-notification-delay [3],
    list-of-cov-subscription-specifications [4]. `specifications`: [(object_type, instance,
    [property identifier, ...])], each property subscribed whole (no array index, no COV
    increment, not timestamped). Cl. 13.16.1.1.3/.4: Lifetime and Max Notification Delay "shall
    be present if the request is a subscription, or re-subscription, and absent if the request
    is a cancellation" - pass lifetime=None for a cancellation and both are left out.
    Notifications go to the address the subscription came from: subscribe with the socket that
    will collect them."""
    parameters = context_unsigned(0, process_identifier) + context_boolean(1, confirmed)
    if lifetime is not None:
        parameters += context_unsigned(2, lifetime) + context_unsigned(3, max_notification_delay)
    parameters += opening(4)
    for object_type, instance, properties in specifications:
        parameters += context_object_id(0, object_type, instance) + opening(1)
        for property_identifier in properties:
            parameters += (opening(0) + context_unsigned(0, property_identifier) + closing(0) +
                           context_boolean(2, False))
        parameters += closing(1)
    parameters += closing(4)
    return confirmed_request(invoke_id, SERVICE_SUBSCRIBE_COV_PROPERTY_MULTIPLE, parameters)


def is_cov_notification_multiple(frame):
    return ((frame.pdu_type == codec.PDU_UNCONFIRMED_REQUEST and
             frame.service == SERVICE_UNCONFIRMED_COV_NOTIFICATION_MULTIPLE) or
            (frame.pdu_type == codec.PDU_CONFIRMED_REQUEST and
             frame.service == SERVICE_CONFIRMED_COV_NOTIFICATION_MULTIPLE))


class CovNotificationMultiple:
    """One Confirmed- or UnconfirmedCOVNotificationMultiple-Request (cl. 21.2 / 21.3), decoded:
    process_identifier [0], initiating_device [1], time_remaining [2], and `values` -
    [(monitored object, property identifier, array index or None, value octets)] from
    list-of-cov-notifications [4]."""

    def __init__(self, frame):
        self.frame = frame
        self.confirmed = frame.pdu_type == codec.PDU_CONFIRMED_REQUEST
        self.process_identifier = None
        self.initiating_device = None
        self.time_remaining = None
        self.values = []
        octets = frame.payload[4:] if self.confirmed else frame.payload[2:]
        position = 0
        depth = 0
        monitored = None
        property_identifier = None
        array_index = None
        while position < len(octets):
            number, is_context, kind, body, position = read_tag(octets, position)
            if kind == "open" and depth == 2 and number == 2:   # property-value [2]
                value, position = _constructed_body(octets, position)
                self.values.append((monitored, property_identifier, array_index, value))
                array_index = None
                continue
            if kind == "open":
                depth += 1
                continue
            if kind == "close":
                depth -= 1
                continue
            if not is_context:
                continue
            if depth == 0 and number == 0:
                self.process_identifier = int.from_bytes(body, "big")
            elif depth == 0 and number == 1:
                self.initiating_device = _object_identifier(body)
            elif depth == 0 and number == 2:
                self.time_remaining = int.from_bytes(body, "big")
            elif depth == 1 and number == 0:
                monitored = _object_identifier(body)
            elif depth == 2 and number == 0:
                property_identifier = int.from_bytes(body, "big")
            elif depth == 2 and number == 1:
                array_index = int.from_bytes(body, "big")

    def value(self, object_identifier, property_identifier):
        """The decoded value of `property_identifier` in this notification, or None."""
        for monitored, identifier, _, octets in self.values:
            if monitored == object_identifier and identifier == property_identifier:
                return codec.decode_application(octets)
        return None


# ---------------------------------------------------------------------------
# LifeSafetyOperation (cl. 13.13)
# ---------------------------------------------------------------------------

def life_safety_operation_request(invoke_id, process_identifier, source, operation, object_reference=None):
    """LifeSafetyOperation-Request (cl. 21.2): requestingProcessIdentifier [0], requestingSource [1],
    request [2], objectIdentifier [3] OPTIONAL. `object_reference` is (type, instance) or None
    ("all applicable objects", cl. 13.13.1.1.4)."""
    parameters = (context_unsigned(0, process_identifier) + context_character_string(1, source) +
                  context_enumerated(2, operation))
    if object_reference is not None:
        parameters += context_object_id(3, *object_reference)
    return confirmed_request(invoke_id, SERVICE_LIFE_SAFETY_OPERATION, parameters)


# ---------------------------------------------------------------------------
# BACnetLandingCallStatus (cl. 21) - Landing_Call_Control (12.58.10), Landing_Calls (12.58.9),
# and the same tags in BACnetAssignedLandingCalls (Assigned_Landing_Calls, 12.59.11)
# ---------------------------------------------------------------------------

def landing_call_status(floor, direction=None, destination=None, floor_text=None):
    """The value octets of one BACnetLandingCallStatus ::= SEQUENCE { floor-number [0] Unsigned8,
    command CHOICE { direction [1] BACnetLiftCarDirection, destination [2] Unsigned8 },
    floor-text [3] CharacterString OPTIONAL }. Give exactly one of direction / destination."""
    if (direction is None) == (destination is None):
        raise ValueError("a landing call has a direction or a destination, not both")
    octets = context_unsigned(0, floor)
    octets += context_enumerated(1, direction) if direction is not None else context_unsigned(2, destination)
    if floor_text is not None:
        octets += context_character_string(3, floor_text)
    return octets


def decode_landing_calls(octets):
    """Every BACnetLandingCallStatus (or BACnetAssignedLandingCalls entry) in `octets`, in order,
    as dicts with 'floor' and 'direction' or 'destination' (and 'floor_text' if present).
    Opening/closing tags (an array element's list) are skipped."""
    calls = []
    position = 0
    while octets and position < len(octets):
        number, is_context, kind, body, position = read_tag(octets, position)
        if kind != "value" or not is_context:
            continue
        if number == 0:
            calls.append({"floor": int.from_bytes(body, "big")})
        elif calls and number == 1:
            calls[-1]["direction"] = int.from_bytes(body, "big")
        elif calls and number == 2:
            calls[-1]["destination"] = int.from_bytes(body, "big")
        elif calls and number == 3:
            calls[-1]["floor_text"] = body[1:].decode("utf-8", errors="replace")
    return calls


# ---------------------------------------------------------------------------
# BACnetLightingCommand (cl. 21) - a Lighting Output's Lighting_Command (cl. 12.54)
# ---------------------------------------------------------------------------

def lighting_command(operation, target_level=None, ramp_rate=None, step_increment=None, fade_time=None,
                     priority=None):
    """A BACnetLightingCommand as the value of a WriteProperty: operation [0], then each
    optional field given - target-level [1], ramp-rate [2], step-increment [3], fade-time [4],
    priority [5]."""
    octets = context_enumerated(0, operation)
    if target_level is not None:
        octets += context_real(1, target_level)
    if ramp_rate is not None:
        octets += context_real(2, ramp_rate)
    if step_increment is not None:
        octets += context_real(3, step_increment)
    if fade_time is not None:
        octets += context_unsigned(4, fade_time)
    if priority is not None:
        octets += context_unsigned(5, priority)
    return octets


def decode_lighting_command(octets):
    """A read BACnetLightingCommand as a dict of the fields it carries (operation,
    target_level, ramp_rate, step_increment, fade_time, priority), or None."""
    if not octets:
        return None
    names = {0: "operation", 1: "target_level", 2: "ramp_rate", 3: "step_increment", 4: "fade_time",
             5: "priority"}
    decoded = {}
    for tag, body in codec.context_values(octets):
        if tag in (1, 2, 3):
            decoded[names[tag]] = struct.unpack(">f", body)[0]
        elif tag in names:
            decoded[names[tag]] = int.from_bytes(body, "big")
    return decoded
