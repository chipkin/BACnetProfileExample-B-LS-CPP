# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""A BACnet/IP client for wire tests: confirmed requests with the bookkeeping done.

Client is an Endpoint that numbers its own invoke ids, wraps each APDU in an NPDU and
BVLC, optionally addresses it THROUGH a router (DNET/DADR - a device on another network,
e.g. a virtual device behind a gateway), and waits for the answer with the matching
invoke id. Each call returns an Answer: the decoded frame plus what it says.

Retries (the one quick-retry mechanism, shared with workstation.Workstation): give a client
`timeout=` (seconds per attempt) and `retries=` (resends) when it is made, and an unanswered
request is sent again with the SAME invoke id, printing a [RETRY] line each time - what a
BACnet client does (Number_Of_APDU_Retries; TimeoutUnsegmented, cl. 5.4.4). A short timeout
with a few visible retries keeps a test that samples a moving value on time when a busy
host drops the odd loopback datagram. Leave retries at 0 where "no answer" is the thing
being tested.
"""
from . import alarm, codec, services
from .endpoint import Endpoint

DEFAULT_TIMEOUT = 3.0


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
    def acked(self):
        """A SimpleACK (0.7.0)."""
        return self.frame is not None and self.frame.pdu_type == codec.PDU_SIMPLE_ACK

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

    @property
    def reject_reason(self):
        """The reason of a Reject PDU (cl. 20.1.8: type, invoke id, reason), or None (0.7.0, B-SS)."""
        if self.frame is None or self.frame.pdu_type != codec.PDU_REJECT or len(self.frame.payload) < 3:
            return None
        return self.frame.payload[2]

    @property
    def abort_reason(self):
        """The reason of an Abort PDU (cl. 20.1.9), or None (0.7.0)."""
        if self.frame is None or self.frame.pdu_type != codec.PDU_ABORT or len(self.frame.payload) < 3:
            return None
        return self.frame.payload[2]

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


def send_with_retries(invoke_id, attempt, retries, timeout):
    """The retry loop every wiretest client shares: `attempt(timeout)` sends the request (the
    same octets, the same invoke id) and returns the answering frame or None; it is called up
    to 1 + `retries` times, with a [RETRY] line before each resend. Returns an Answer."""
    frame = None
    for attempt_number in range(1 + retries):
        if attempt_number:
            print(f"[RETRY] invoke id {invoke_id} unanswered after {timeout} s - sent again", flush=True)
        frame = attempt(timeout)
        if frame is not None:
            break
    return Answer(frame)


class ConfirmedServices:
    """The confirmed-service calls Client and Workstation share; each builds the APDU and
    hands it to the class's own request(build_apdu, port, ...). Every call returns an Answer
    and accepts request()'s keywords (timeout=, and for Client ip= / dnet= / dadr=)."""

    def read_property(self, port, object_type, instance, property_identifier, array_index=None, **keywords):
        return self.request(lambda invoke_id: codec.read_property_request(
            invoke_id, object_type, instance, property_identifier, array_index), port, **keywords)

    def write_property(self, port, object_type, instance, property_identifier, value_octets,
                       priority=None, array_index=None, **keywords):
        return self.request(lambda invoke_id: codec.write_property_request(
            invoke_id, object_type, instance, property_identifier, value_octets, priority, array_index),
            port, **keywords)

    def read_property_multiple(self, port, specifications, **keywords):
        """ReadPropertyMultiple (cl. 15.7), `specifications` as services.read_property_multiple_request
        takes them; decode the Answer with services.parse_read_property_multiple_ack (0.7.0)."""
        return self.request(lambda invoke_id: services.read_property_multiple_request(invoke_id, specifications),
                            port, **keywords)

    def device_communication_control(self, port, enable_disable, password=None, minutes=None, **keywords):
        """DeviceCommunicationControl (cl. 16.1); alarm.DCC_* name `enable_disable` (0.7.0, B-ASC)."""
        return self.request(lambda invoke_id: alarm.device_communication_control_request(
            invoke_id, enable_disable, password, minutes), port, **keywords)


class Client(Endpoint, ConfirmedServices):
    """An Endpoint that sends confirmed requests to one device and waits for the answers.

    `timeout` (default 3.0 s) is how long one attempt waits; `retries` (default 0) how many
    times an unanswered request is sent again, with the SAME invoke id, before it counts as
    unanswered. See the module text."""

    def __init__(self, port=0, bind_ip="127.0.0.1", retries=0, timeout=DEFAULT_TIMEOUT):
        super().__init__(port, bind_ip)
        self._invoke_id = 0
        self.retries = retries
        self.timeout = timeout

    def _next_invoke_id(self):
        self._invoke_id = (self._invoke_id + 1) % 256
        return self._invoke_id

    def request(self, build_apdu, port, ip="127.0.0.1", dnet=None, dadr=b"", timeout=None):
        """Send the APDU `build_apdu(invoke_id)` makes; return the Answer with that invoke id.
        With `dnet`, the request is addressed to DNET/DADR through the device at ip:port.
        `timeout` overrides the client's own for this request."""
        invoke_id = self._next_invoke_id()
        self.frames.clear()
        octets = codec.bvlc(codec.npdu(build_apdu(invoke_id), dnet=dnet, dadr=dadr, expecting_reply=True))

        def attempt(seconds):
            self.send(octets, port, ip)
            return self.wait_for(lambda candidate: candidate.network_message is None and
                                 candidate.pdu_type in (codec.PDU_COMPLEX_ACK, codec.PDU_SIMPLE_ACK, codec.PDU_ERROR,
                                                        codec.PDU_REJECT, codec.PDU_ABORT) and
                                 candidate.invoke_id == invoke_id, seconds)
        return send_with_retries(invoke_id, attempt, self.retries, self.timeout if timeout is None else timeout)

    def who_is(self, port, device_instance, ip="127.0.0.1", attempts=None, timeout=None):
        """A unicast Who-Is for `device_instance` (low = high = the instance); the I-Am frame that
        answers it, or None. Sent up to 1 + retries times (or `attempts` times), with a visible
        [RETRY] line before each resend (0.7.0, B-ASC)."""
        attempts = 1 + self.retries if attempts is None else attempts
        seconds = self.timeout if timeout is None else timeout
        for attempt_number in range(attempts):
            if attempt_number:
                print(f"[RETRY] Who-Is got no I-Am in {seconds} s - sent again", flush=True)
            self.frames.clear()
            self.send(codec.bvlc(codec.npdu(codec.who_is(device_instance, device_instance))), port, ip)
            frame = self.wait_for(lambda candidate: codec.i_am_device_instance(candidate.payload) == device_instance,
                                  seconds)
            if frame is not None:
                return frame
        return None

