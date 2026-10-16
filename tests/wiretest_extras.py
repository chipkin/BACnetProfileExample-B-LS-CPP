# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""Generic additions to the vendored wiretest/ harness (0.5.0, frozen this round).

Nothing here names B-LS: it is kept separate so it can be folded into wiretest/ 0.6.0
as it is.

    write_group_request(...)          - a WriteGroup-Request APDU (cl. 15.11, 21.3)
    parse_write_property_request(apdu)- what a WriteProperty request asks for
    simple_ack(invoke_id, service)    - a SimpleACK APDU (cl. 20.1.4)
    context_values(octets)            - every context-tagged primitive, as (tag, bytes)
    CommandablePeer                   - a SimulatedDevice whose objects take WriteProperty,
                                        and that can be taken offline or made to refuse writes
"""
import struct

import wiretest
from wiretest import codec

SERVICE_WRITE_GROUP = 10           # BACnetUnconfirmedServiceChoice write-group (cl. 21)
ERROR_CODE_BUSY = 82               # cl. 18.3 / 21 BACnetErrorCode busy
PROPERTY_DEVICE_ADDRESS_BINDING = 30
PROPERTY_LIST_OF_OBJECT_PROPERTY_REFERENCES = 54


def write_group_request(group_number, write_priority, change_list, inhibit_delay=None):
    """An Unconfirmed WriteGroup-Request APDU.

    `change_list`: [(channel, value_octets, overriding_priority or None)], value_octets an
    application-tagged BACnetChannelValue such as codec.application_real(60.0). Each entry
    is encoded channel [0], overriding-priority [1] (when given), then the untagged value,
    the (channel number, overridingPriority, value) order cl. 15.11.1.1.3 names and the
    CAS BACnet Stack decodes."""
    change_octets = b""
    for channel, value_octets, overriding_priority in change_list:
        change_octets += codec.context_unsigned(0, channel)
        if overriding_priority is not None:
            change_octets += codec.context_unsigned(1, overriding_priority)
        change_octets += value_octets
    parameters = (codec.context_unsigned(0, group_number) + codec.context_unsigned(1, write_priority) +
                  codec.opening(2) + change_octets + codec.closing(2))
    if inhibit_delay is not None:
        parameters += bytes([0x39, 1 if inhibit_delay else 0])   # [3] BOOLEAN, one octet
    return bytes([codec.PDU_UNCONFIRMED_REQUEST << 4, SERVICE_WRITE_GROUP]) + parameters


def simple_ack(invoke_id, service):
    return bytes([codec.PDU_SIMPLE_ACK << 4, invoke_id, service])


def parse_write_property_request(apdu):
    """A WriteProperty request APDU (cl. 15.9) as a dict - object_type, instance,
    property_identifier, array_index, value_octets (application-tagged), priority - or None."""
    try:
        if apdu[0] >> 4 != codec.PDU_CONFIRMED_REQUEST or apdu[3] != codec.SERVICE_WRITE_PROPERTY:
            return None
        request = {"array_index": None, "priority": None}
        position = 4
        _, _, _, body, position = codec.read_tag(apdu, position)          # [0] object identifier
        raw = struct.unpack(">I", body)[0]
        request["object_type"], request["instance"] = raw >> 22, raw & codec.MAX_INSTANCE
        _, _, _, body, position = codec.read_tag(apdu, position)          # [1] property identifier
        request["property_identifier"] = int.from_bytes(body, "big")
        number, _, kind, body, after = codec.read_tag(apdu, position)
        if number == 2 and kind == "value":                               # [2] array index
            request["array_index"] = int.from_bytes(body, "big")
            position = after
        number, _, kind, _, position = codec.read_tag(apdu, position)     # [3] opening
        start = position
        depth = 1
        while depth:
            tag_start = position
            number, is_context, kind, _, position = codec.read_tag(apdu, position)
            if kind == "open":
                depth += 1
            elif kind == "close":
                depth -= 1
        request["value_octets"] = apdu[start:tag_start]
        if position < len(apdu):
            _, _, _, body, position = codec.read_tag(apdu, position)      # [4] priority
            request["priority"] = int.from_bytes(body, "big")
        return request
    except (IndexError, struct.error):
        return None


def context_values(octets):
    """Every context-tagged primitive in `octets` as (tag number, value bytes), in order -
    e.g. a BACnetDeviceObjectPropertyReference's object [0], property [1], device [3]."""
    values = []
    position = 0
    while octets and position < len(octets):
        number, is_context, kind, body, position = codec.read_tag(octets, position)
        if is_context and kind == "value":
            values.append((number, body))
    return values


class CommandablePeer(wiretest.SimulatedDevice):
    """A Python BACnet/IP device with objects a WriteProperty can command.

    `objects`: {(object_type, instance): {property_identifier: value_octets}}. On top of
    SimulatedDevice (Who-Is / I-Am, ReadProperty of its Device object) it answers:
      - ReadProperty of any listed property (the current value octets);
      - WriteProperty of a listed property with a SimpleACK, storing the value. Every
        WriteProperty that arrives, answered or not, is kept in `writes` as the dict
        parse_write_property_request() returns.
    `mode` decides how it answers, and a test may change it at any time:
      "online"   - as above;
      "offline"  - nothing at all, not even Who-Is: the device is gone (requests are
                   still kept in `writes` / `received`, so a test can see they arrived);
      "refusing" - a WriteProperty gets Error PROPERTY / WRITE_ACCESS_DENIED.
    announce(port, ip) sends an I-Am, unicast, the way a device that has just started does."""

    def __init__(self, device_instance, object_name, objects, **keywords):
        self.objects = {key: dict(properties) for key, properties in objects.items()}
        self.writes = []
        self.mode = "online"
        super().__init__(device_instance, object_name, **keywords)

    def announce(self, port, ip="127.0.0.1"):
        self.sock.sendto(codec.bvlc(codec.npdu(codec.i_am(self.device_instance, self.vendor_identifier))), (ip, port))

    def writes_matching(self, object_type, instance, property_identifier):
        with self._lock:
            return [write for write in self.writes if (write["object_type"], write["instance"],
                                                       write["property_identifier"]) ==
                    (object_type, instance, property_identifier)]

    def _answer(self, frame):
        if frame.pdu_type == codec.PDU_CONFIRMED_REQUEST and frame.service == codec.SERVICE_WRITE_PROPERTY:
            request = parse_write_property_request(frame.payload)
            if request is not None:
                with self._lock:
                    self.writes.append(request)
            if self.mode == "offline" or request is None:
                return None
            properties = self.objects.get((request["object_type"], request["instance"]))
            if properties is None:
                return codec.error_pdu(frame.invoke_id, codec.SERVICE_WRITE_PROPERTY,
                                       codec.ERROR_CLASS_OBJECT, codec.ERROR_CODE_UNKNOWN_OBJECT)
            if self.mode == "refusing" or request["property_identifier"] not in properties:
                return codec.error_pdu(frame.invoke_id, codec.SERVICE_WRITE_PROPERTY,
                                       codec.ERROR_CLASS_PROPERTY, codec.ERROR_CODE_WRITE_ACCESS_DENIED)
            properties[request["property_identifier"]] = request["value_octets"]
            return simple_ack(frame.invoke_id, codec.SERVICE_WRITE_PROPERTY)
        if self.mode == "offline":
            return None
        if frame.pdu_type == codec.PDU_CONFIRMED_REQUEST and frame.service == codec.SERVICE_READ_PROPERTY:
            request = codec.parse_read_property_request(frame.payload)
            if request is not None and (request[0], request[1]) in self.objects:
                properties = self.objects[(request[0], request[1])]
                if request[2] in properties:
                    return codec.read_property_ack(frame.invoke_id, request[0], request[1], request[2],
                                                   properties[request[2]])
        return super()._answer(frame)
