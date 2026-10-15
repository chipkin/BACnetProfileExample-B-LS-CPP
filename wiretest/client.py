# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""A BACnet/IP client for wire tests: ReadProperty / WriteProperty with the bookkeeping done.

Client is an Endpoint that numbers its own invoke ids, wraps each APDU in an NPDU and
BVLC, optionally addresses it THROUGH a router (DNET/DADR - a device on another network,
e.g. a virtual device behind a gateway), and waits for the answer with the matching
invoke id. Each call returns an Answer: the decoded frame plus what it says.
"""
from . import codec
from .endpoint import Endpoint


class Answer:
    """What came back for one confirmed request (frame is None if nothing did)."""

    def __init__(self, frame):
        self.frame = frame

    @property
    def answered(self):
        return self.frame is not None

    @property
    def ok(self):
        """A ComplexACK (ReadProperty) or SimpleACK (WriteProperty)."""
        return self.frame is not None and self.frame.pdu_type in (codec.PDU_COMPLEX_ACK, codec.PDU_SIMPLE_ACK)

    @property
    def value_octets(self):
        """The application-tagged value of a ReadProperty ComplexACK, or None."""
        if self.frame is None or self.frame.pdu_type != codec.PDU_COMPLEX_ACK:
            return None
        return codec.read_property_value(self.frame.payload)

    @property
    def value(self):
        """The ReadProperty value decoded by codec.decode_application(), or None."""
        octets = self.value_octets
        return codec.decode_application(octets) if octets is not None else None

    @property
    def error(self):
        """(error class, error code) of an Error PDU, or None."""
        if self.frame is None or self.frame.pdu_type != codec.PDU_ERROR:
            return None
        return codec.error_class_and_code(self.frame.payload)

    def describe(self):
        if self.frame is None:
            return "no answer"
        if self.error is not None:
            return f"Error class={self.error[0]} code={self.error[1]}"
        if self.frame.pdu_type == codec.PDU_COMPLEX_ACK:
            return f"value={self.value!r}"
        if self.frame.pdu_type == codec.PDU_SIMPLE_ACK:
            return "SimpleACK"
        return self.frame.describe()


class Client(Endpoint):
    """An Endpoint that sends confirmed requests to one device and waits for the answers.

    `retries` (default 0): how many times an unanswered request is sent again, with the
    SAME invoke id, before it counts as unanswered - what a BACnet client does
    (Number_Of_APDU_Retries; TimeoutUnsegmented in the client state machine, cl. 5.4.4).
    Each retry prints a [RETRY] line, so a device that needed one is visible in the test
    output rather than silently tolerated. Leave it at 0 where "no answer" is the thing
    being tested."""

    def __init__(self, port=0, bind_ip="127.0.0.1", retries=0):
        super().__init__(port, bind_ip)
        self._invoke_id = 0
        self.retries = retries

    def _next_invoke_id(self):
        self._invoke_id = (self._invoke_id + 1) % 256
        return self._invoke_id

    def request(self, build_apdu, port, ip="127.0.0.1", dnet=None, dadr=b"", timeout=3.0):
        """Send the APDU `build_apdu(invoke_id)` makes; return the Answer with that invoke id.
        With `dnet`, the request is addressed to DNET/DADR through the device at ip:port."""
        invoke_id = self._next_invoke_id()
        self.frames.clear()
        octets = codec.bvlc(codec.npdu(build_apdu(invoke_id), dnet=dnet, dadr=dadr, expecting_reply=True))
        frame = None
        for attempt in range(1 + self.retries):
            if attempt:
                print(f"[RETRY] invoke id {invoke_id} unanswered after {timeout} s - sent again", flush=True)
            self.send(octets, port, ip)
            frame = self.wait_for(lambda candidate: candidate.network_message is None and
                                  candidate.pdu_type in (codec.PDU_COMPLEX_ACK, codec.PDU_SIMPLE_ACK, codec.PDU_ERROR,
                                                         codec.PDU_REJECT, codec.PDU_ABORT) and
                                  candidate.invoke_id == invoke_id, timeout)
            if frame is not None:
                break
        return Answer(frame)

    def read_property(self, port, object_type, instance, property_identifier, array_index=None, **routing):
        return self.request(lambda invoke_id: codec.read_property_request(
            invoke_id, object_type, instance, property_identifier, array_index), port, **routing)

    def write_property(self, port, object_type, instance, property_identifier, value_octets,
                       priority=None, array_index=None, **routing):
        return self.request(lambda invoke_id: codec.write_property_request(
            invoke_id, object_type, instance, property_identifier, value_octets, priority, array_index),
            port, **routing)
