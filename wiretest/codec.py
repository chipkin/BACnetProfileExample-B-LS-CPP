# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""BACnet/IP frames by hand: BVLC (Annex J), NPDU (clause 6), APDU (clause 20).

Building the octets here, rather than in a BACnet library, is the point: a wire
test says exactly what it put on the wire and checks exactly what came back.
"""
import socket
import struct

# ---------------------------------------------------------------------------
# Numbers (ANSI/ASHRAE 135-2024)
# ---------------------------------------------------------------------------

BVLC_TYPE = 0x81                       # Annex J.2
BVLC_RESULT = 0x00
BVLC_WRITE_BROADCAST_DISTRIBUTION_TABLE = 0x01
BVLC_READ_BROADCAST_DISTRIBUTION_TABLE = 0x02
BVLC_READ_BROADCAST_DISTRIBUTION_TABLE_ACK = 0x03
BVLC_FORWARDED_NPDU = 0x04
BVLC_REGISTER_FOREIGN_DEVICE = 0x05
BVLC_READ_FOREIGN_DEVICE_TABLE = 0x06
BVLC_READ_FOREIGN_DEVICE_TABLE_ACK = 0x07
BVLC_DELETE_FOREIGN_DEVICE_TABLE_ENTRY = 0x08
BVLC_DISTRIBUTE_BROADCAST_TO_NETWORK = 0x09
BVLC_ORIGINAL_UNICAST = 0x0A
BVLC_ORIGINAL_BROADCAST = 0x0B

# The BVLL messages that carry an NPDU (Annex J.2.5, J.2.10, J.2.11, J.2.12).
BVLC_FUNCTIONS_WITH_NPDU = (BVLC_FORWARDED_NPDU, BVLC_DISTRIBUTE_BROADCAST_TO_NETWORK,
                            BVLC_ORIGINAL_UNICAST, BVLC_ORIGINAL_BROADCAST)

# BVLC-Result codes (Annex J.2.1.1).
BVLC_RESULT_SUCCESSFUL_COMPLETION = 0x0000
BVLC_RESULT_WRITE_BDT_NAK = 0x0010
BVLC_RESULT_READ_BDT_NAK = 0x0020
BVLC_RESULT_REGISTER_FOREIGN_DEVICE_NAK = 0x0030
BVLC_RESULT_READ_FDT_NAK = 0x0040
BVLC_RESULT_DELETE_FDT_ENTRY_NAK = 0x0050
BVLC_RESULT_DISTRIBUTE_BROADCAST_TO_NETWORK_NAK = 0x0060

GLOBAL_BROADCAST_NETWORK = 0xFFFF      # cl. 6.2.2

# Network layer message types (cl. 6.2.4).
NL_WHO_IS_ROUTER_TO_NETWORK = 0x00
NL_I_AM_ROUTER_TO_NETWORK = 0x01
NL_REJECT_MESSAGE_TO_NETWORK = 0x03
NL_WHAT_IS_NETWORK_NUMBER = 0x12
NL_NETWORK_NUMBER_IS = 0x13

# PDU types (cl. 20.1.1).
PDU_CONFIRMED_REQUEST = 0x0
PDU_UNCONFIRMED_REQUEST = 0x1
PDU_SIMPLE_ACK = 0x2
PDU_COMPLEX_ACK = 0x3
PDU_ERROR = 0x5
PDU_REJECT = 0x6
PDU_ABORT = 0x7

# Confirmed service choices (cl. 21).
SERVICE_ADD_LIST_ELEMENT = 8
SERVICE_REMOVE_LIST_ELEMENT = 9
SERVICE_READ_PROPERTY = 12
SERVICE_WRITE_PROPERTY = 15
SERVICE_READ_PROPERTY_MULTIPLE = 14
SERVICE_REINITIALIZE_DEVICE = 20

# ReinitializeDevice 'Reinitialized State of Device' (cl. 16.4.1.1.1).
REINITIALIZE_COLDSTART = 0
REINITIALIZE_WARMSTART = 1
REINITIALIZE_ACTIVATE_CHANGES = 7

# Unconfirmed service choices (cl. 21).
SERVICE_I_AM = 0
SERVICE_WHO_IS = 8
SERVICE_WRITE_GROUP = 10             # BACnetUnconfirmedServiceChoice write-group (cl. 21)

OBJECT_TYPE_ANALOG_INPUT = 0
OBJECT_TYPE_ANALOG_OUTPUT = 1
OBJECT_TYPE_BINARY_INPUT = 3
OBJECT_TYPE_BINARY_OUTPUT = 4
OBJECT_TYPE_DEVICE = 8
OBJECT_TYPE_GROUP = 11
OBJECT_TYPE_MULTI_STATE_INPUT = 13
OBJECT_TYPE_NETWORK_PORT = 56

PROPERTY_DESCRIPTION = 28
PROPERTY_DEVICE_ADDRESS_BINDING = 30
PROPERTY_EVENT_STATE = 36
PROPERTY_LIST_OF_GROUP_MEMBERS = 53
PROPERTY_LIST_OF_OBJECT_PROPERTY_REFERENCES = 54
PROPERTY_OBJECT_IDENTIFIER = 75
PROPERTY_OBJECT_LIST = 76
PROPERTY_OBJECT_NAME = 77
PROPERTY_OUT_OF_SERVICE = 81
PROPERTY_PRESENT_VALUE = 85
PROPERTY_PRIORITY_ARRAY = 87
PROPERTY_RELIABILITY = 103
PROPERTY_RELINQUISH_DEFAULT = 104
PROPERTY_STATUS_FLAGS = 111
PROPERTY_PROPERTY_LIST = 371
PROPERTY_NETWORK_NUMBER = 425
PROPERTY_NETWORK_NUMBER_QUALITY = 426
PROPERTY_CURRENT_COMMAND_PRIORITY = 431

ERROR_CLASS_OBJECT = 1
ERROR_CLASS_PROPERTY = 2
ERROR_CLASS_SERVICES = 5
ERROR_CODE_UNKNOWN_OBJECT = 31
ERROR_CODE_UNKNOWN_PROPERTY = 32
ERROR_CODE_VALUE_OUT_OF_RANGE = 37
ERROR_CODE_WRITE_ACCESS_DENIED = 40
ERROR_CODE_LIST_ELEMENT_NOT_FOUND = 81
ERROR_CODE_BUSY = 82

MAX_INSTANCE = 0x3FFFFF

# BACnetReliability (cl. 21) - the two values a gateway reports most.
RELIABILITY_NO_FAULT_DETECTED = 0
RELIABILITY_UNRELIABLE_OTHER = 7
RELIABILITY_COMMUNICATION_FAILURE = 12

# BACnetStatusFlags bit positions (cl. 21): bit 0 is the first bit of the BIT STRING.
STATUS_FLAG_IN_ALARM = 0
STATUS_FLAG_FAULT = 1
STATUS_FLAG_OVERRIDDEN = 2
STATUS_FLAG_OUT_OF_SERVICE = 3

# Application tag numbers (cl. 20.2.1.4).
TAG_NULL = 0
TAG_BOOLEAN = 1
TAG_UNSIGNED = 2
TAG_SIGNED = 3
TAG_REAL = 4
TAG_DOUBLE = 5
TAG_OCTET_STRING = 6
TAG_CHARACTER_STRING = 7
TAG_BIT_STRING = 8
TAG_ENUMERATED = 9
TAG_OBJECT_IDENTIFIER = 12


# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------

def mac(ip, port):
    """A 6-octet BACnet/IP address (B/IP MAC): 4 octets of IPv4, 2 of UDP port (Annex J.1.2)."""
    return socket.inet_aton(ip) + struct.pack(">H", port)


def mac_text(octets):
    if len(octets) == 6:
        return f"{socket.inet_ntoa(octets[:4])}:{struct.unpack('>H', octets[4:])[0]}"
    return octets.hex()


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------

def bvll(function, body=b""):
    """Any Annex J BVLL message: type X'81', `function`, length, then `body`."""
    return struct.pack(">BBH", BVLC_TYPE, function, 4 + len(body)) + body


def bvlc(npdu_octets, broadcast=False):
    return bvll(BVLC_ORIGINAL_BROADCAST if broadcast else BVLC_ORIGINAL_UNICAST, npdu_octets)


def forwarded_npdu(originating_mac, npdu_octets):
    """Forwarded-NPDU (J.2.5): what a BBMD sends its peers and foreign devices."""
    return bvll(BVLC_FORWARDED_NPDU, originating_mac + npdu_octets)


def distribute_broadcast_to_network(npdu_octets):
    """Distribute-Broadcast-To-Network (J.2.10): a foreign device's broadcast, sent to its BBMD."""
    return bvll(BVLC_DISTRIBUTE_BROADCAST_TO_NETWORK, npdu_octets)


def register_foreign_device(time_to_live):
    """Register-Foreign-Device (J.2.6), Time-to-Live in seconds."""
    return bvll(BVLC_REGISTER_FOREIGN_DEVICE, struct.pack(">H", time_to_live))


def read_broadcast_distribution_table():
    return bvll(BVLC_READ_BROADCAST_DISTRIBUTION_TABLE)


def read_foreign_device_table():
    return bvll(BVLC_READ_FOREIGN_DEVICE_TABLE)


def delete_foreign_device_table_entry(entry_mac):
    """Delete-Foreign-Device-Table-Entry (J.2.9) for the 6-octet B/IP address `entry_mac`."""
    return bvll(BVLC_DELETE_FOREIGN_DEVICE_TABLE_ENTRY, entry_mac)


def write_broadcast_distribution_table(entries):
    """Write-Broadcast-Distribution-Table (J.2.2); `entries` = [(6-octet B/IP address, 4-octet mask)]."""
    return bvll(BVLC_WRITE_BROADCAST_DISTRIBUTION_TABLE, b"".join(address + mask for address, mask in entries))


def npdu(payload, network_message=None, dnet=None, dadr=b"", snet=None, sadr=b"",
         expecting_reply=False, hop_count=255):
    """A clause 6.2 NPDU. `network_message` is the message type of a network layer message;
    otherwise `payload` is an APDU. DLEN = 0 (dadr=b"") with a DNET is a broadcast on DNET."""
    control = 0
    if network_message is not None:
        control |= 0x80
    if dnet is not None:
        control |= 0x20
    if snet is not None:
        control |= 0x08
    if expecting_reply:
        control |= 0x04
    out = bytes([0x01, control])
    if dnet is not None:
        out += struct.pack(">HB", dnet, len(dadr)) + dadr
    if snet is not None:
        out += struct.pack(">HB", snet, len(sadr)) + sadr
    if dnet is not None:
        out += bytes([hop_count])
    if network_message is not None:
        out += bytes([network_message])
    return out + payload


def object_id(object_type, instance):
    return struct.pack(">I", (object_type << 22) | instance)


def _unsigned_octets(value):
    for length in (1, 2, 3, 4):
        if value < (1 << (8 * length)):
            return value.to_bytes(length, "big")
    raise ValueError(value)


def context_unsigned(tag, value):
    body = _unsigned_octets(value)
    return bytes([(tag << 4) | 0x08 | len(body)]) + body


def context_object_id(tag, object_type, instance):
    return bytes([(tag << 4) | 0x08 | 4]) + object_id(object_type, instance)


def context_octet_string(tag, octets):
    if len(octets) < 5:
        return bytes([(tag << 4) | 0x08 | len(octets)]) + octets
    return bytes([(tag << 4) | 0x08 | 5, len(octets)]) + octets


def opening(tag):
    return bytes([(tag << 4) | 0x0E])


def closing(tag):
    return bytes([(tag << 4) | 0x0F])


def application_unsigned(value):
    body = _unsigned_octets(value)
    return bytes([0x20 | len(body)]) + body


def application_enumerated(value):
    body = _unsigned_octets(value)
    return bytes([0x90 | len(body)]) + body


def application_null():
    return bytes([0x00])


def application_boolean(value):
    return bytes([0x11 if value else 0x10])   # application BOOLEAN: the value is in the length field


def application_real(value):
    return bytes([0x44]) + struct.pack(">f", value)


def application_object_id(object_type, instance):
    return bytes([0xC4]) + object_id(object_type, instance)


def application_character_string(text):
    body = b"\x00" + text.encode("utf-8")   # character set 0 = UTF-8 (cl. 20.2.9)
    if len(body) < 5:
        return bytes([0x70 | len(body)]) + body
    return bytes([0x75, len(body)]) + body


def confirmed_request(invoke_id, service, parameters):
    # 0x00 = unsegmented, segmented response not accepted; 0x05 = max APDU 1476 octets.
    return bytes([0x00, 0x05, invoke_id, service]) + parameters


def read_property_request(invoke_id, object_type, instance, property_identifier, array_index=None):
    parameters = context_object_id(0, object_type, instance) + context_unsigned(1, property_identifier)
    if array_index is not None:
        parameters += context_unsigned(2, array_index)
    return confirmed_request(invoke_id, SERVICE_READ_PROPERTY, parameters)


def write_property_request(invoke_id, object_type, instance, property_identifier, value_octets,
                           priority=None, array_index=None):
    """WriteProperty (cl. 15.9). `value_octets` is application-tagged (application_real(),
    application_null() to relinquish a commandable property, ...); `priority` 1..16 or None."""
    parameters = context_object_id(0, object_type, instance) + context_unsigned(1, property_identifier)
    if array_index is not None:
        parameters += context_unsigned(2, array_index)
    parameters += opening(3) + value_octets + closing(3)
    if priority is not None:
        parameters += context_unsigned(4, priority)
    return confirmed_request(invoke_id, SERVICE_WRITE_PROPERTY, parameters)


def reinitialize_device_request(invoke_id, state, password=None):
    """ReinitializeDevice (cl. 16.4): [0] reinitialized-state-of-device, [1] password (optional)."""
    parameters = context_unsigned(0, state)   # ENUMERATED: same octets as an unsigned
    if password is not None:
        body = b"\x00" + password.encode("utf-8")
        parameters += (bytes([0x18 | len(body)]) if len(body) < 5 else bytes([0x1D, len(body)])) + body
    return confirmed_request(invoke_id, SERVICE_REINITIALIZE_DEVICE, parameters)


def read_property_ack(invoke_id, object_type, instance, property_identifier, value_octets):
    return (bytes([0x30, invoke_id, SERVICE_READ_PROPERTY]) +
            context_object_id(0, object_type, instance) + context_unsigned(1, property_identifier) +
            opening(3) + value_octets + closing(3))


def error_pdu(invoke_id, service, error_class, error_code):
    return bytes([0x50, invoke_id, service]) + application_enumerated(error_class) + application_enumerated(error_code)


def who_is(low=None, high=None):
    out = bytes([0x10, SERVICE_WHO_IS])
    if low is not None:
        out += context_unsigned(0, low) + context_unsigned(1, high)
    return out


def i_am(device_instance, vendor_identifier, max_apdu=1476, segmentation=3):
    return (bytes([0x10, SERVICE_I_AM]) + application_object_id(OBJECT_TYPE_DEVICE, device_instance) +
            application_unsigned(max_apdu) + application_enumerated(segmentation) +
            application_unsigned(vendor_identifier))


def read_access_specification(object_type, instance, property_identifiers):
    """One BACnetReadAccessSpecification (cl. 21) - e.g. an element of List_Of_Group_Members."""
    out = context_object_id(0, object_type, instance) + opening(1)
    for property_identifier in property_identifiers:
        out += context_unsigned(0, property_identifier)
    return out + closing(1)


def list_element_request(invoke_id, service, object_type, instance, property_identifier, elements):
    """AddListElement / RemoveListElement (cl. 15.1 / 15.2)."""
    return confirmed_request(invoke_id, service,
                             context_object_id(0, object_type, instance) +
                             context_unsigned(1, property_identifier) +
                             opening(3) + b"".join(elements) + closing(3))


def simple_ack(invoke_id, service):
    """A SimpleACK APDU (cl. 20.1.4) for confirmed service `service`."""
    return bytes([PDU_SIMPLE_ACK << 4, invoke_id, service])


def application_bit_string(bits):
    """BIT STRING (cl. 20.2.10), bit 0 first."""
    octets = bytearray((len(bits) + 7) // 8)
    for index, bit in enumerate(bits):
        if bit:
            octets[index // 8] |= 0x80 >> (index % 8)
    body = bytes([len(octets) * 8 - len(bits)]) + bytes(octets)
    return bytes([0x80 | len(body)]) + body


def status_flags(bits):
    """An application-tagged BACnetStatusFlags: [in-alarm, fault, overridden, out-of-service]
    (cl. 21; STATUS_FLAG_* name the positions)."""
    return application_bit_string(list(bits))


def application_date(year, month, day, weekday):
    """Date (cl. 20.2.12): year - 1900, month, day, weekday 1 = Monday .. 7 = Sunday."""
    return bytes([0xA4, year - 1900, month, day, weekday])


def application_time(hour, minute, second, hundredths=0):
    return bytes([0xB4, hour, minute, second, hundredths])


def context_character_string(tag, text):
    body = b"\x00" + text.encode("utf-8")
    if len(body) < 5:
        return bytes([(tag << 4) | 0x08 | len(body)]) + body
    return bytes([(tag << 4) | 0x08 | 5, len(body)]) + body


def context_enumerated(tag, value):
    return context_unsigned(tag, value)   # same octets: a context tag carries no type


def read_property_multiple_ack(invoke_id, results):
    """A ReadPropertyMultiple-ACK (cl. 15.7). `results`: [(object_type, instance,
    [(property_identifier, value_octets or None)])]; None answers that property with
    [5] Error PROPERTY / UNKNOWN_PROPERTY, as a device without it does."""
    body = b""
    for object_type, instance, properties in results:
        body += context_object_id(0, object_type, instance) + opening(1)
        for property_identifier, value_octets in properties:
            body += context_unsigned(2, property_identifier)
            if value_octets is None:
                body += (opening(5) + application_enumerated(ERROR_CLASS_PROPERTY) +
                         application_enumerated(ERROR_CODE_UNKNOWN_PROPERTY) + closing(5))
            else:
                body += opening(4) + value_octets + closing(4)
        body += closing(1)
    return bytes([PDU_COMPLEX_ACK << 4, invoke_id, SERVICE_READ_PROPERTY_MULTIPLE]) + body


def write_group_request(group_number, write_priority, change_list, inhibit_delay=None):
    """An Unconfirmed WriteGroup-Request APDU (cl. 15.11).

    `change_list`: [(channel, value_octets, overriding_priority or None)], value_octets an
    application-tagged BACnetChannelValue such as application_real(60.0). Each entry is
    encoded channel [0], overriding-priority [1] (when given), then the untagged value,
    the (channel number, overridingPriority, value) order cl. 15.11.1.1.3 names and the
    CAS BACnet Stack decodes."""
    change_octets = b""
    for channel, value_octets, overriding_priority in change_list:
        change_octets += context_unsigned(0, channel)
        if overriding_priority is not None:
            change_octets += context_unsigned(1, overriding_priority)
        change_octets += value_octets
    parameters = (context_unsigned(0, group_number) + context_unsigned(1, write_priority) +
                  opening(2) + change_octets + closing(2))
    if inhibit_delay is not None:
        parameters += bytes([0x39, 1 if inhibit_delay else 0])   # [3] BOOLEAN, one octet
    return bytes([PDU_UNCONFIRMED_REQUEST << 4, SERVICE_WRITE_GROUP]) + parameters


# ---------------------------------------------------------------------------
# Decoding
# ---------------------------------------------------------------------------

class Frame:
    """One received BACnet/IP datagram, decoded down to the APDU or network layer message."""

    def __init__(self, data, source):
        self.raw = data
        self.source = source           # (ip, udp port) the datagram came from
        self.bvlc_function = None
        self.bvll_data = b""           # what follows the 4-octet BVLC header (J.2)
        self.originating_mac = b""     # a Forwarded-NPDU's B/IP Address of Originating Device (J.2.5)
        self.has_npdu = False          # False for BVLL-only messages (BVLC-Result, table reads, ...)
        self.snet = None
        self.sadr = b""
        self.dnet = None
        self.dadr = b""
        self.expecting_reply = False
        self.network_message = None
        self.payload = b""             # the APDU, or the network layer message's data
        self.ok = self._decode(data)

    def _decode(self, data):
        if len(data) < 4 or data[0] != BVLC_TYPE:
            return False
        self.bvlc_function = data[1]
        self.bvll_data = data[4:]
        if self.bvlc_function not in BVLC_FUNCTIONS_WITH_NPDU:
            return True                # a BVLL-only message: read it with result_code / bdt_entries / fdt_entries
        offset = 4
        if self.bvlc_function == BVLC_FORWARDED_NPDU:
            self.originating_mac = data[4:10]
            offset += 6
        octets = data[offset:]
        if len(octets) < 2 or octets[0] != 0x01:
            return False
        self.has_npdu = True
        control = octets[1]
        self.expecting_reply = bool(control & 0x04)
        position = 2
        if control & 0x20:
            self.dnet, length = struct.unpack(">HB", octets[position:position + 3])
            position += 3
            self.dadr = octets[position:position + length]
            position += length
        if control & 0x08:
            self.snet, length = struct.unpack(">HB", octets[position:position + 3])
            position += 3
            self.sadr = octets[position:position + length]
            position += length
        if control & 0x20:
            position += 1  # hop count
        if control & 0x80:
            self.network_message = octets[position]
            position += 1
            if self.network_message >= 0x80:
                position += 2  # vendor id
        self.payload = octets[position:]
        return True

    @property
    def pdu_type(self):
        return self.payload[0] >> 4 if self.network_message is None and self.payload else None

    @property
    def invoke_id(self):
        if self.pdu_type in (PDU_SIMPLE_ACK, PDU_COMPLEX_ACK, PDU_ERROR, PDU_REJECT, PDU_ABORT):
            return self.payload[1]
        if self.pdu_type == PDU_CONFIRMED_REQUEST and len(self.payload) > 2:
            return self.payload[2]
        return None

    @property
    def service(self):
        if self.pdu_type in (PDU_SIMPLE_ACK, PDU_COMPLEX_ACK, PDU_ERROR):
            return self.payload[2]
        if self.pdu_type == PDU_CONFIRMED_REQUEST and len(self.payload) > 3:
            return self.payload[3]
        if self.pdu_type == PDU_UNCONFIRMED_REQUEST and len(self.payload) > 1:
            return self.payload[1]
        return None

    @property
    def result_code(self):
        """A BVLC-Result's result code (J.2.1.1), else None."""
        if self.bvlc_function == BVLC_RESULT and len(self.bvll_data) >= 2:
            return struct.unpack(">H", self.bvll_data[:2])[0]
        return None

    def bdt_entries(self):
        """A Read-Broadcast-Distribution-Table-Ack's entries (J.2.4) as [(B/IP address text, mask text)]."""
        if self.bvlc_function != BVLC_READ_BROADCAST_DISTRIBUTION_TABLE_ACK:
            return None
        return [(mac_text(self.bvll_data[offset:offset + 6]), socket.inet_ntoa(self.bvll_data[offset + 6:offset + 10]))
                for offset in range(0, len(self.bvll_data) - 9, 10)]

    def fdt_entries(self):
        """A Read-Foreign-Device-Table-Ack's entries (J.2.8) as [(B/IP address text, time-to-live, seconds remaining)]."""
        if self.bvlc_function != BVLC_READ_FOREIGN_DEVICE_TABLE_ACK:
            return None
        return [(mac_text(self.bvll_data[offset:offset + 6]),) + struct.unpack(">HH", self.bvll_data[offset + 6:offset + 10])
                for offset in range(0, len(self.bvll_data) - 9, 10)]

    def networks(self):
        """The network numbers an I-Am-Router-To-Network lists (cl. 6.4.2)."""
        return [struct.unpack(">H", self.payload[offset:offset + 2])[0] for offset in range(0, len(self.payload) - 1, 2)]

    def describe(self):
        text = f"from {self.source[0]}:{self.source[1]}"
        if not self.has_npdu:
            return text + f" BVLL function=0x{self.bvlc_function:02X} data={self.bvll_data.hex()}"
        if self.originating_mac:
            text += f" Forwarded-NPDU originating={mac_text(self.originating_mac)}"
        if self.snet is not None:
            text += f" SNET={self.snet} SADR={mac_text(self.sadr)}"
        if self.dnet is not None:
            text += f" DNET={self.dnet}"
        if self.network_message is not None:
            text += f" network-message=0x{self.network_message:02X} data={self.payload.hex()}"
        else:
            text += f" APDU={self.payload.hex()}"
        return text


def read_tag(data, position):
    """One clause 20.2.1 tag. Returns (number, is_context, kind, value_bytes, next_position);
    kind is 'open', 'close' or 'value'."""
    first = data[position]
    number = first >> 4
    is_context = bool(first & 0x08)
    length_value = first & 0x07
    position += 1
    if number == 0x0F:
        number = data[position]
        position += 1
    if is_context and length_value == 6:
        return number, True, "open", b"", position
    if is_context and length_value == 7:
        return number, True, "close", b"", position
    if length_value == 5:
        length_value = data[position]
        position += 1
        if length_value == 254:
            length_value = struct.unpack(">H", data[position:position + 2])[0]
            position += 2
        elif length_value == 255:
            length_value = struct.unpack(">I", data[position:position + 4])[0]
            position += 4
    if not is_context and number == 1:  # application BOOLEAN keeps its value in the length field
        return number, False, "value", bytes([length_value]), position
    return number, is_context, "value", data[position:position + length_value], position + length_value


def i_am_device_instance(apdu):
    """The Device instance an I-Am APDU (cl. 16.10.2) announces, or None if `apdu` is not an I-Am."""
    if len(apdu) < 7 or apdu[0] >> 4 != PDU_UNCONFIRMED_REQUEST or apdu[1] != SERVICE_I_AM:
        return None
    number, is_context, kind, body, _ = read_tag(apdu, 2)
    if is_context or number != 12 or len(body) != 4:   # application tag 12 = BACnetObjectIdentifier
        return None
    identifier = struct.unpack(">I", body)[0]
    return identifier & MAX_INSTANCE if identifier >> 22 == OBJECT_TYPE_DEVICE else None


def read_property_value(apdu):
    """The value octets inside a ReadProperty ComplexACK's [3] opening/closing tags, or None."""
    position = 3
    while position < len(apdu):
        number, is_context, kind, _, position = read_tag(apdu, position)
        if is_context and number == 3 and kind == "open":
            depth = 1
            start = position
            while depth:
                tag_start = position
                number, is_context, kind, _, position = read_tag(apdu, position)
                if kind == "open":
                    depth += 1
                elif kind == "close":
                    depth -= 1
                    if depth == 0:
                        return apdu[start:tag_start]
    return None


def parse_read_property_request(apdu):
    """(object_type, instance, property_identifier) from a ReadProperty request APDU, or None."""
    try:
        position = 4
        _, _, _, body, position = read_tag(apdu, position)
        raw = struct.unpack(">I", body)[0]
        _, _, _, property_octets, position = read_tag(apdu, position)
        return raw >> 22, raw & MAX_INSTANCE, int.from_bytes(property_octets, "big")
    except (IndexError, struct.error):
        return None


def application_values(octets):
    """Every application-tagged primitive in `octets` as (tag number, value bytes)."""
    values = []
    position = 0
    while position < len(octets):
        number, is_context, kind, body, position = read_tag(octets, position)
        if kind == "value" and not is_context:
            values.append((number, body))
    return values


def character_string(value):
    """The text of an application-tagged CharacterString, or None."""
    if not value:
        return None
    number, is_context, kind, body, _ = read_tag(value, 0)
    if is_context or number != 7 or not body:
        return None
    return body[1:].decode("utf-8", errors="replace")


def read_access_specifications(value):
    """A BACnetLIST of ReadAccessSpecification as {(object_type, instance): [property identifiers]}."""
    members = {}
    position = 0
    current = None
    while position < len(value):
        number, is_context, kind, body, position = read_tag(value, position)
        if kind == "value" and is_context and number == 0 and len(body) == 4 and current is None:
            raw = struct.unpack(">I", body)[0]
            current = (raw >> 22, raw & MAX_INSTANCE)
            members[current] = []
        elif kind == "value" and is_context and number == 0 and current is not None:
            members[current].append(int.from_bytes(body, "big"))
        elif kind == "close" and number == 1:
            current = None
    return members


def decode_application(octets):
    """The first application-tagged primitive in `octets` as a Python value, or None if it
    is not one: NULL -> None, BOOLEAN -> bool, Unsigned/Enumerated -> int, Signed -> int,
    REAL/Double -> float, CharacterString -> str, BIT STRING -> list of bool (bit 0 first),
    ObjectIdentifier -> (type, instance), anything else -> the raw bytes.
    Use application_tag() to tell an Unsigned from an Enumerated."""
    if not octets:
        return None
    number, is_context, kind, body, _ = read_tag(octets, 0)
    if is_context or kind != "value":
        return None
    if number == TAG_NULL:
        return None
    if number == TAG_BOOLEAN:
        return bool(body[0])
    if number in (TAG_UNSIGNED, TAG_ENUMERATED):
        return int.from_bytes(body, "big")
    if number == TAG_SIGNED:
        return int.from_bytes(body, "big", signed=True)
    if number == TAG_REAL:
        return struct.unpack(">f", body)[0]
    if number == TAG_DOUBLE:
        return struct.unpack(">d", body)[0]
    if number == TAG_CHARACTER_STRING:
        return body[1:].decode("utf-8", errors="replace")
    if number == TAG_BIT_STRING:
        unused = body[0]
        bits = []
        for octet in body[1:]:
            bits.extend(bool(octet & (0x80 >> position)) for position in range(8))
        return bits[:len(bits) - unused] if unused else bits
    if number == TAG_OBJECT_IDENTIFIER:
        raw = struct.unpack(">I", body)[0]
        return raw >> 22, raw & MAX_INSTANCE
    return body


def decoded_values(octets):
    """EVERY application-tagged primitive in `octets`, each decoded as decode_application()
    does - for a property whose value is a list or a whole array (Property_List, a
    Priority_Array read without an index). Context-tagged and constructed data is skipped."""
    values = []
    position = 0
    while octets and position < len(octets):
        start = position
        number, is_context, kind, _, position = read_tag(octets, position)
        if kind == "value" and not is_context:
            values.append(decode_application(octets[start:position]))
    return values


def application_tag(octets):
    """The application tag number of the first primitive in `octets`, or None."""
    if not octets:
        return None
    number, is_context, _, _, _ = read_tag(octets, 0)
    return None if is_context else number


def error_class_and_code(apdu):
    """(error class, error code) from an Error PDU (cl. 20.1.7), or None."""
    values = application_values(apdu[3:])
    if len(values) < 2:
        return None
    return int.from_bytes(values[0][1], "big"), int.from_bytes(values[1][1], "big")


def parse_write_property_request(apdu):
    """A WriteProperty request APDU (cl. 15.9) as a dict - object_type, instance,
    property_identifier, array_index, value_octets (application-tagged), priority - or None."""
    try:
        if apdu[0] >> 4 != PDU_CONFIRMED_REQUEST or apdu[3] != SERVICE_WRITE_PROPERTY:
            return None
        request = {"array_index": None, "priority": None}
        position = 4
        _, _, _, body, position = read_tag(apdu, position)          # [0] object identifier
        raw = struct.unpack(">I", body)[0]
        request["object_type"], request["instance"] = raw >> 22, raw & MAX_INSTANCE
        _, _, _, body, position = read_tag(apdu, position)          # [1] property identifier
        request["property_identifier"] = int.from_bytes(body, "big")
        number, _, kind, body, after = read_tag(apdu, position)
        if number == 2 and kind == "value":                         # [2] array index
            request["array_index"] = int.from_bytes(body, "big")
            position = after
        number, _, kind, _, position = read_tag(apdu, position)     # [3] opening
        start = position
        tag_start = position
        depth = 1
        while depth:
            tag_start = position
            number, is_context, kind, _, position = read_tag(apdu, position)
            if kind == "open":
                depth += 1
            elif kind == "close":
                depth -= 1
        request["value_octets"] = apdu[start:tag_start]
        if position < len(apdu):
            _, _, _, body, position = read_tag(apdu, position)      # [4] priority
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
        number, is_context, kind, body, position = read_tag(octets, position)
        if is_context and kind == "value":
            values.append((number, body))
    return values
