# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""Encode and decode the alarm, event and device-management services a Wire Test needs.

    requests   acknowledge_alarm_request, get_event_information_request,
               device_communication_control_request, time_synchronization,
               event_notification (a Peer's Confirmed/UnconfirmedEventNotification, 0.7.0)
    values     context_date_time (a BACnetTimeStamp as dateTime), destination (one
               BACnetDestination, cl. 21 production); the date / time / bit-string /
               character-string encoders live in codec and are re-exported here
    decoding   EventNotification (Confirmed- or UnconfirmedEventNotification-Request),
               parse_event_summaries (GetEventInformation-ACK), date_time_text

Every production is from ANSI/ASHRAE 135-2024 clause 21 (21.2 confirmed services, 21.3
unconfirmed services, 21.6 base types); service choices from 21.1. Came from B-AAC's
tests/alarm_codec.py (wiretest 0.6.0); event_notification from B-OD's tests/client_peer.py
and the life-safety event state / type from B-LSC (0.7.0).
"""
import struct

from . import codec
from .codec import (application_bit_string, application_date, application_time,  # noqa: F401 (re-exported)
                    closing, confirmed_request, context_bit_string, context_boolean, context_character_string,
                    context_enumerated, context_object_id, context_real, context_unsigned, opening, read_tag,
                    simple_ack)

# BACnetConfirmedServiceChoice / BACnetUnconfirmedServiceChoice (cl. 21).
SERVICE_ACKNOWLEDGE_ALARM = 0
SERVICE_CONFIRMED_EVENT_NOTIFICATION = 2
SERVICE_DEVICE_COMMUNICATION_CONTROL = 17
SERVICE_GET_EVENT_INFORMATION = 29
SERVICE_UNCONFIRMED_EVENT_NOTIFICATION = 3
SERVICE_TIME_SYNCHRONIZATION = 6

# BACnetEventState, BACnetNotifyType, BACnetEventType (cl. 21).
EVENT_STATE_NORMAL = 0
EVENT_STATE_FAULT = 1
EVENT_STATE_OFFNORMAL = 2
EVENT_STATE_HIGH_LIMIT = 3
EVENT_STATE_LOW_LIMIT = 4
EVENT_STATE_LIFE_SAFETY_ALARM = 5
NOTIFY_TYPE_ALARM = 0
NOTIFY_TYPE_EVENT = 1
NOTIFY_TYPE_ACK_NOTIFICATION = 2
EVENT_TYPE_CHANGE_OF_STATE = 1
EVENT_TYPE_OUT_OF_RANGE = 5
EVENT_TYPE_CHANGE_OF_LIFE_SAFETY = 8
EVENT_TYPE_CHANGE_OF_RELIABILITY = 19

# BACnetEventTransitionBits: bit 0 to-offnormal, 1 to-fault, 2 to-normal.
TO_OFFNORMAL, TO_FAULT, TO_NORMAL = 0, 1, 2

# DeviceCommunicationControl 'Enable/Disable' (cl. 21.2; DISABLE (1) is deprecated).
DCC_ENABLE = 0
DCC_DISABLE = 1
DCC_DISABLE_INITIATION = 2

# Error classes and codes (cl. 21 BACnetErrorClass / BACnetErrorCode).
ERROR_CLASS_SECURITY = codec.ERROR_CLASS_SECURITY
ERROR_CLASS_SERVICES = codec.ERROR_CLASS_SERVICES
ERROR_CODE_INVALID_TIMESTAMP = 14
ERROR_CODE_PASSWORD_FAILURE = codec.ERROR_CODE_PASSWORD_FAILURE
ERROR_CODE_SERVICE_REQUEST_DENIED = codec.ERROR_CODE_SERVICE_REQUEST_DENIED

# Properties.
PROPERTY_ACKED_TRANSITIONS = 0
PROPERTY_EVENT_STATE = codec.PROPERTY_EVENT_STATE
PROPERTY_EVENT_TIME_STAMPS = 130
PROPERTY_LOCAL_DATE = 56
PROPERTY_LOCAL_TIME = 57
PROPERTY_RECIPIENT_LIST = 102


# ---------------------------------------------------------------------------
# Values
# ---------------------------------------------------------------------------

def context_date_time(tag, date_time):
    """A BACnetTimeStamp in its dateTime form ([2] BACnetDateTime) inside context tag `tag`.
    `date_time` is the (date octets, time octets) pair EventNotification.time_stamp holds."""
    date_octets, time_octets = date_time
    return opening(tag) + opening(2) + bytes([0xA4]) + date_octets + bytes([0xB4]) + time_octets + closing(2) + closing(tag)


def destination(mac, process_identifier, confirmed, transitions=(True, True, True), network_number=0,
                valid_days=(True,) * 7, from_time=(0, 0, 0, 0), to_time=(23, 59, 59, 99)):
    """One BACnetDestination (cl. 21.6) whose recipient is an ADDRESS (BACnetRecipient [1]):
    `mac` is the 6-octet B/IP address. Concatenate several for a Recipient_List value."""
    mac_body = bytes([0x60 | len(mac)]) + mac if len(mac) < 5 else bytes([0x65, len(mac)]) + mac
    return (application_bit_string(valid_days) + application_time(*from_time) + application_time(*to_time) +
            opening(1) + codec.application_unsigned(network_number) + mac_body + closing(1) +
            codec.application_unsigned(process_identifier) + codec.application_boolean(confirmed) +
            application_bit_string(transitions))


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

def acknowledge_alarm_request(invoke_id, process_identifier, object_type, instance, event_state_acknowledged,
                              time_stamp, source, time_of_acknowledgment):
    """AcknowledgeAlarm-Request (cl. 21.2). Both time stamps are (date octets, time octets)."""
    return confirmed_request(invoke_id, SERVICE_ACKNOWLEDGE_ALARM,
                             context_unsigned(0, process_identifier) + context_object_id(1, object_type, instance) +
                             context_enumerated(2, event_state_acknowledged) + context_date_time(3, time_stamp) +
                             context_character_string(4, source) + context_date_time(5, time_of_acknowledgment))


def get_event_information_request(invoke_id, last_received=None):
    parameters = b"" if last_received is None else context_object_id(0, *last_received)
    return confirmed_request(invoke_id, SERVICE_GET_EVENT_INFORMATION, parameters)


def device_communication_control_request(invoke_id, enable_disable, password=None, minutes=None):
    parameters = b"" if minutes is None else context_unsigned(0, minutes)
    parameters += context_enumerated(1, enable_disable)
    if password is not None:
        parameters += context_character_string(2, password)
    return confirmed_request(invoke_id, SERVICE_DEVICE_COMMUNICATION_CONTROL, parameters)


def time_synchronization(year, month, day, weekday, hour, minute, second=0):
    """An unconfirmed TimeSynchronization-Request APDU (cl. 21.3)."""
    return (bytes([0x10, SERVICE_TIME_SYNCHRONIZATION]) + application_date(year, month, day, weekday) +
            application_time(hour, minute, second))


def event_notification(initiating_device, event_object, to_state, from_state=EVENT_STATE_NORMAL,
                       confirmed=False, invoke_id=0, process_identifier=1, notification_class=1, priority=100,
                       notify_type=NOTIFY_TYPE_ALARM, ack_required=True, message_text=None,
                       time_stamp=(2026, 10, 15, 4, 12, 30, 0), exceeding_value=95.0, exceeded_limit=90.0):
    """An out-of-range (event type 5) Confirmed- or UnconfirmedEventNotification-Request APDU
    (cl. 13.8 / 13.9, productions in cl. 21), as a Peer that reports an alarm sends it.
    `initiating_device` is the Device instance, `event_object` an (object type, instance)
    pair, `time_stamp` (year, month, day, weekday, hour, minute, second) sent as the dateTime
    form; `message_text` is optional. An ACK_NOTIFICATION carries no ack-required, from-state
    or event values. (0.7.0, from B-OD.)"""
    year, month, day, weekday, hour, minute, second = time_stamp
    stamp = (application_date(year, month, day, weekday)[1:], application_time(hour, minute, second)[1:])
    parameters = (context_unsigned(0, process_identifier) +
                  context_object_id(1, codec.OBJECT_TYPE_DEVICE, initiating_device) +
                  context_object_id(2, *event_object) +
                  context_date_time(3, stamp) +
                  context_unsigned(4, notification_class) +
                  context_unsigned(5, priority) +
                  context_enumerated(6, EVENT_TYPE_OUT_OF_RANGE))
    if message_text is not None:
        parameters += context_character_string(7, message_text)
    parameters += context_enumerated(8, notify_type)
    if notify_type != NOTIFY_TYPE_ACK_NOTIFICATION:
        parameters += (context_boolean(9, ack_required) + context_enumerated(10, from_state) +
                       context_enumerated(11, to_state))
        # [12] eventValues, out-of-range choice [5]: exceedingValue, statusFlags, deadband, exceededLimit.
        in_alarm = to_state != EVENT_STATE_NORMAL
        parameters += (opening(12) + opening(5) + context_real(0, exceeding_value) +
                       context_bit_string(1, [in_alarm, False, False, False]) + context_real(2, 1.0) +
                       context_real(3, exceeded_limit) + closing(5) + closing(12))
    else:
        parameters += context_enumerated(11, to_state)
    if confirmed:
        return confirmed_request(invoke_id, SERVICE_CONFIRMED_EVENT_NOTIFICATION, parameters)
    return bytes([codec.PDU_UNCONFIRMED_REQUEST << 4, SERVICE_UNCONFIRMED_EVENT_NOTIFICATION]) + parameters


# ---------------------------------------------------------------------------
# Decoding
# ---------------------------------------------------------------------------

def _skip_constructed(octets, position):
    """Position just after the closing tag that matches an opening tag already read."""
    depth = 1
    while depth:
        number, is_context, kind, body, position = read_tag(octets, position)
        depth += {"open": 1, "close": -1}.get(kind, 0)
    return position


def read_time_stamp_choice(octets, position):
    """One BACnetTimeStamp CHOICE at `position`. Returns ((date octets, time octets) for the
    dateTime form, else None; position just after it)."""
    number, is_context, kind, body, inner = read_tag(octets, position)
    if kind == "open" and number == 2:
        _, _, _, date_octets, after_date = read_tag(octets, inner)
        _, _, _, time_octets, after_time = read_tag(octets, after_date)
        return (date_octets, time_octets), read_tag(octets, after_time)[4]
    if kind == "open":
        return None, _skip_constructed(octets, inner)
    return None, inner


class EventNotification:
    """A Confirmed- or UnconfirmedEventNotification-Request (cl. 21.2 / 21.3), decoded
    from its service parameters. `time_stamp` is the dateTime form's (date, time) octets."""

    def __init__(self, frame):
        self.frame = frame
        self.confirmed = frame.pdu_type == codec.PDU_CONFIRMED_REQUEST
        self.invoke_id = frame.invoke_id if self.confirmed else None
        self.process_identifier = None
        self.initiating_device = None
        self.event_object = None
        self.time_stamp = None
        self.notification_class = None
        self.priority = None
        self.event_type = None
        self.notify_type = None
        self.ack_required = None
        self.from_state = None
        self.to_state = None
        octets = frame.payload[4:] if self.confirmed else frame.payload[2:]
        position = 0
        while position < len(octets):
            number, is_context, kind, body, position = read_tag(octets, position)
            if kind == "open":
                if number == 3:
                    self.time_stamp, position = self._read_time_stamp(octets, position)
                else:
                    position = _skip_constructed(octets, position)
                continue
            if kind != "value" or not is_context:
                continue
            integer = int.from_bytes(body, "big")
            if number == 0:
                self.process_identifier = integer
            elif number in (1, 2):
                raw = struct.unpack(">I", body)[0]
                identifier = (raw >> 22, raw & codec.MAX_INSTANCE)
                if number == 1:
                    self.initiating_device = identifier
                else:
                    self.event_object = identifier
            elif number == 4:
                self.notification_class = integer
            elif number == 5:
                self.priority = integer
            elif number == 6:
                self.event_type = integer
            elif number == 8:
                self.notify_type = integer
            elif number == 9:
                self.ack_required = bool(integer)
            elif number == 10:
                self.from_state = integer
            elif number == 11:
                self.to_state = integer

    @staticmethod
    def _read_time_stamp(octets, position):
        """A BACnetTimeStamp inside an outer context tag: `position` is just after the outer
        opening tag. Returns (stamp, position after the outer closing tag)."""
        stamp, position = read_time_stamp_choice(octets, position)
        return stamp, read_tag(octets, position)[4]

    def describe(self):
        return (f"{'Confirmed' if self.confirmed else 'Unconfirmed'}EventNotification object={self.event_object} "
                f"notify-type={self.notify_type} from={self.from_state} to={self.to_state} "
                f"ack-required={self.ack_required} class={self.notification_class} priority={self.priority} "
                f"event-type={self.event_type}")


def is_event_notification(frame):
    return frame.network_message is None and (
        (frame.pdu_type == codec.PDU_CONFIRMED_REQUEST and frame.service == SERVICE_CONFIRMED_EVENT_NOTIFICATION) or
        (frame.pdu_type == codec.PDU_UNCONFIRMED_REQUEST and frame.service == SERVICE_UNCONFIRMED_EVENT_NOTIFICATION))


def parse_event_summaries(apdu):
    """A GetEventInformation-ACK (cl. 21.2) as (summaries, more_events). Each summary is a
    dict: object (type, instance), event_state, acked_transitions [3 bools],
    time_stamps [3 x (date, time) or None], notify_type, event_enable [3 bools], priorities [3 ints]."""
    octets = apdu[3:]
    summaries = []
    more_events = None
    position = 0
    current = None
    in_list = False
    while position < len(octets):
        number, is_context, kind, body, after = read_tag(octets, position)
        if not in_list:
            if kind == "open" and number == 0:
                in_list = True
            elif kind == "value" and is_context and number == 1:
                more_events = bool(int.from_bytes(body, "big"))
            position = after
            continue
        if kind == "close" and number == 0:
            in_list = False
            position = after
            continue
        if kind == "value" and is_context and number == 0:
            raw = struct.unpack(">I", body)[0]
            current = {"object": (raw >> 22, raw & codec.MAX_INSTANCE)}
            summaries.append(current)
        elif kind == "value" and is_context and number == 1:
            current["event_state"] = int.from_bytes(body, "big")
        elif kind == "value" and is_context and number in (2, 5):
            current["acked_transitions" if number == 2 else "event_enable"] = _bits(body)
        elif kind == "open" and number == 3:
            stamps = []
            position = after
            for _ in range(3):
                stamp, position = read_time_stamp_choice(octets, position)
                stamps.append(stamp)
            current["time_stamps"] = stamps
            position = read_tag(octets, position)[4]   # the [3] closing tag
            continue
        elif kind == "value" and is_context and number == 4:
            current["notify_type"] = int.from_bytes(body, "big")
        elif kind == "open" and number == 6:
            priorities = []
            position = after
            while True:
                number, is_context, kind, body, position = read_tag(octets, position)
                if kind == "close":
                    break
                priorities.append(int.from_bytes(body, "big"))
            current["priorities"] = priorities
            continue
        position = after
    return summaries, more_events


def _bits(body):
    unused = body[0]
    bits = []
    for octet in body[1:]:
        bits.extend(bool(octet & (0x80 >> index)) for index in range(8))
    return bits[:len(bits) - unused] if unused else bits


def date_time_text(date_time):
    if date_time is None:
        return "none"
    date_octets, time_octets = date_time
    if set(date_octets + time_octets) == {0xFF}:   # the initial, never-occurred time stamp
        return "unspecified"
    return (f"{1900 + date_octets[0]}-{date_octets[1]:02}-{date_octets[2]:02} "
            f"{time_octets[0]:02}:{time_octets[1]:02}:{time_octets[2]:02}.{time_octets[3]:02}")
