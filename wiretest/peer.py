# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""A Python-simulated BACnet/IP device to stand on the far side of the example under test.

Wire tests never use another example's binary as a Peer: a Peer here is a few dozen lines
whose every answer the test controls. SimulatedDevice owns one UDP socket and, in a
background thread:

  - answers ReadProperty of its Device object's Object_Name and Object_Identifier with a
    ComplexACK, and any other property or object with an Error (cl. 15.5);
  - answers Who-Is (cl. 16.10) with I-Am when its instance is in range;
  - addresses every answer back the way cl. 6.5.4 / 6.5.2 require: to the address the
    request came from, and - when the request carried SNET/SADR because a router
    relayed it - with DNET/DADR set to that SNET/SADR, so the router relays it back.

Every frame it receives is kept in `received`, so a test can check what arrived and
from where.

A BACnet/IP network in these tests is the devices sharing one UDP port on one subnet. The
Peer's own socket is on a port of its own (it is reached by its address), so on its own it
never hears a broadcast on its network. Pass `broadcast=(broadcast_ip, network_udp_port)`
to give it a second socket that does - bound to that broadcast address the way
endpoint.broadcast_listener is (POSIX SO_REUSEADDR, shared with the example's own socket on
that port). Frames heard there are kept and answered exactly like the others, from the
Peer's own socket. `received_on_broadcast` tells a test which socket a frame arrived on.
"""
import select
import socket
import threading
import time

from . import codec


class SimulatedDevice:
    def __init__(self, device_instance, object_name, vendor_identifier=389, port=0, bind_ip="127.0.0.1",
                 broadcast=None):
        self.device_instance = device_instance
        self.object_name = object_name
        self.vendor_identifier = vendor_identifier
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((bind_ip, port))
        self.ip, self.port = self.sock.getsockname()
        self.broadcast_sock = None
        if broadcast is not None:
            self.broadcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.broadcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.broadcast_sock.bind(broadcast)
        self.received = []
        self.received_on_broadcast = []   # the frames in `received` that arrived on the broadcast socket
        self._lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    @property
    def mac(self):
        return codec.mac(self.ip, self.port)

    def frames(self):
        with self._lock:
            return list(self.received)

    def stop(self):
        self._running = False
        self._thread.join(timeout=2)
        self.sock.close()
        if self.broadcast_sock is not None:
            self.broadcast_sock.close()

    # -- serving ------------------------------------------------------------

    def _serve(self):
        sockets = [self.sock] + ([self.broadcast_sock] if self.broadcast_sock is not None else [])
        while self._running:
            try:
                ready, _, _ = select.select(sockets, [], [], 0.1)
            except (OSError, ValueError):
                return
            for ready_sock in ready:
                try:
                    data, source = ready_sock.recvfrom(2048)
                except ConnectionResetError:
                    continue   # Windows: an ICMP port-unreachable for an earlier reply (see endpoint.py)
                except OSError:
                    return
                frame = codec.Frame(data, source)
                with self._lock:
                    self.received.append(frame)
                    if ready_sock is self.broadcast_sock:
                        self.received_on_broadcast.append(frame)
                if frame.ok and frame.network_message is None:
                    answer = self._answer(frame)
                    if answer is not None:
                        self._reply(frame, answer)

    def _answer(self, frame):
        if frame.pdu_type == codec.PDU_CONFIRMED_REQUEST and frame.service == codec.SERVICE_READ_PROPERTY:
            return self._read_property(frame)
        if frame.pdu_type == codec.PDU_UNCONFIRMED_REQUEST and frame.service == codec.SERVICE_WHO_IS:
            return self._who_is(frame)
        return None

    def _read_property(self, frame):
        request = codec.parse_read_property_request(frame.payload)
        invoke_id = frame.invoke_id
        if request is None:
            return None
        object_type, instance, property_identifier = request
        if object_type != codec.OBJECT_TYPE_DEVICE or instance not in (self.device_instance, codec.MAX_INSTANCE):
            return codec.error_pdu(invoke_id, codec.SERVICE_READ_PROPERTY,
                                   codec.ERROR_CLASS_OBJECT, codec.ERROR_CODE_UNKNOWN_OBJECT)
        if property_identifier == codec.PROPERTY_OBJECT_NAME:
            value = codec.application_character_string(self.object_name)
        elif property_identifier == codec.PROPERTY_OBJECT_IDENTIFIER:
            value = codec.application_object_id(codec.OBJECT_TYPE_DEVICE, self.device_instance)
        else:
            return codec.error_pdu(invoke_id, codec.SERVICE_READ_PROPERTY,
                                   codec.ERROR_CLASS_PROPERTY, codec.ERROR_CODE_UNKNOWN_PROPERTY)
        return codec.read_property_ack(invoke_id, codec.OBJECT_TYPE_DEVICE, self.device_instance,
                                       property_identifier, value)

    def _who_is(self, frame):
        limits = [int.from_bytes(body, "big") for number, is_context, kind, body, _ in self._tags(frame.payload[2:])
                  if kind == "value"]
        if len(limits) == 2 and not limits[0] <= self.device_instance <= limits[1]:
            return None
        return codec.i_am(self.device_instance, self.vendor_identifier)

    @staticmethod
    def _tags(octets):
        position = 0
        while position < len(octets):
            tag = codec.read_tag(octets, position)
            position = tag[4]
            yield tag

    def _reply(self, request, apdu):
        if request.snet is not None:
            npdu_octets = codec.npdu(apdu, dnet=request.snet, dadr=request.sadr)
        else:
            npdu_octets = codec.npdu(apdu)
        self.sock.sendto(codec.bvlc(npdu_octets), request.source)


class SimulatedServer(SimulatedDevice):
    """A SimulatedDevice with objects a test controls: it answers ReadProperty,
    ReadPropertyMultiple and WriteProperty of them, and can go offline or refuse writes.

    `objects`: {(object_type, instance): {property_identifier: value}}, each value either
    application-tagged octets or a callable returning them (so a test can change what is
    served by changing an attribute). On top of SimulatedDevice (Who-Is / I-Am,
    ReadProperty of its Device object) it:
      - answers ReadProperty of a listed object's property with its value, and an unlisted
        property of a listed object with Error PROPERTY / UNKNOWN_PROPERTY;
      - answers ReadPropertyMultiple (cl. 15.7) the same way, property by property;
      - answers WriteProperty of a writable property with a SimpleACK and stores the value.
        `writable`: None (default) makes every listed property writable, else a set of
        (object_type, instance, property_identifier). An unlisted object gets Error OBJECT /
        UNKNOWN_OBJECT, anything else not writable Error PROPERTY / WRITE_ACCESS_DENIED.
        Override check_write(request) to refuse more (return (error class, error code)) and
        on_write(request) to act on an accepted write.
    Bookkeeping: `read_requests` holds (service, [(object_type, instance, [property ids])])
    for every read of a listed object; `write_requests` every WriteProperty that arrived,
    answered or not, as codec.parse_write_property_request() returns it.
    `mode` decides how it answers, and a test may change it at any time:
      "online"   - as above;
      "offline"  - nothing at all, not even Who-Is: the device is gone (writes are still kept
                   in `write_requests`, and `requests_while_offline` counts the confirmed
                   requests that went unanswered);
      "refusing" - every WriteProperty gets Error PROPERTY / WRITE_ACCESS_DENIED.
    announce(port, ip) sends an I-Am, unicast, the way a device that has just started does:
    how an example on the same host learns this Peer's address (two processes on one host
    never hear each other's broadcasts).
    Came from B-LS's CommandablePeer and B-BC's HumidityPeer (wiretest 0.6.0)."""

    def __init__(self, device_instance, object_name, objects, writable=None, **keywords):
        self.objects = {key: dict(properties) for key, properties in objects.items()}
        self.writable = None if writable is None else set(writable)
        self.mode = "online"
        self.read_requests = []
        self.write_requests = []
        self.requests_while_offline = 0
        super().__init__(device_instance, object_name, **keywords)

    def announce(self, port, ip="127.0.0.1", times=1, interval=0.2):
        frame = codec.bvlc(codec.npdu(codec.i_am(self.device_instance, self.vendor_identifier)))
        for attempt in range(times):
            if attempt:
                time.sleep(interval)
            self.sock.sendto(frame, (ip, port))

    def value(self, object_type, instance, property_identifier):
        """The application-tagged octets this Peer serves, or None if it has no such property."""
        served = self.objects.get((object_type, instance), {}).get(property_identifier)
        return served() if callable(served) else served

    def reads(self, service):
        with self._lock:
            return [specifications for kind, specifications in self.read_requests if kind == service]

    def writes_matching(self, object_type, instance, property_identifier):
        with self._lock:
            return [write for write in self.write_requests if (write["object_type"], write["instance"],
                                                               write["property_identifier"]) ==
                    (object_type, instance, property_identifier)]

    def check_write(self, request):
        """Override to refuse a write the defaults would accept: return (error class, error code)."""
        return None

    def on_write(self, request):
        """Called after a write is accepted and stored. Override to act on it."""

    # -- answering ----------------------------------------------------------

    def _answer(self, frame):
        confirmed = frame.pdu_type == codec.PDU_CONFIRMED_REQUEST
        request = None
        if confirmed and frame.service == codec.SERVICE_WRITE_PROPERTY:
            request = codec.parse_write_property_request(frame.payload)
            if request is not None:
                with self._lock:
                    self.write_requests.append(request)
        if self.mode == "offline":
            if confirmed and frame.service in (codec.SERVICE_READ_PROPERTY, codec.SERVICE_READ_PROPERTY_MULTIPLE,
                                               codec.SERVICE_WRITE_PROPERTY):
                with self._lock:
                    self.requests_while_offline += 1
            return None
        if confirmed and frame.service == codec.SERVICE_WRITE_PROPERTY:
            return self._write(frame, request)
        if confirmed and frame.service == codec.SERVICE_READ_PROPERTY_MULTIPLE:
            return self._read_multiple(frame)
        if confirmed and frame.service == codec.SERVICE_READ_PROPERTY:
            parsed = codec.parse_read_property_request(frame.payload)
            if parsed is not None and (parsed[0], parsed[1]) in self.objects:
                object_type, instance, property_identifier = parsed
                with self._lock:
                    self.read_requests.append((codec.SERVICE_READ_PROPERTY,
                                               [(object_type, instance, [property_identifier])]))
                served = self.value(object_type, instance, property_identifier)
                if served is None:
                    return codec.error_pdu(frame.invoke_id, codec.SERVICE_READ_PROPERTY,
                                           codec.ERROR_CLASS_PROPERTY, codec.ERROR_CODE_UNKNOWN_PROPERTY)
                return codec.read_property_ack(frame.invoke_id, object_type, instance, property_identifier, served)
        return super()._answer(frame)

    def _read_multiple(self, frame):
        specifications = codec.read_access_specifications(frame.payload[4:])
        with self._lock:
            self.read_requests.append((codec.SERVICE_READ_PROPERTY_MULTIPLE,
                                       [(object_type, instance, list(properties))
                                        for (object_type, instance), properties in specifications.items()]))
        return codec.read_property_multiple_ack(frame.invoke_id, [
            (object_type, instance, [(property_identifier, self.value(object_type, instance, property_identifier))
                                     for property_identifier in properties])
            for (object_type, instance), properties in specifications.items()])

    def _write(self, frame, request):
        if request is None:
            return None
        key = (request["object_type"], request["instance"])
        if key not in self.objects:
            return codec.error_pdu(frame.invoke_id, codec.SERVICE_WRITE_PROPERTY,
                                   codec.ERROR_CLASS_OBJECT, codec.ERROR_CODE_UNKNOWN_OBJECT)
        property_identifier = request["property_identifier"]
        allowed = (property_identifier in self.objects[key] if self.writable is None
                   else key + (property_identifier,) in self.writable)
        if self.mode == "refusing" or not allowed:
            refusal = (codec.ERROR_CLASS_PROPERTY, codec.ERROR_CODE_WRITE_ACCESS_DENIED)
        else:
            refusal = self.check_write(request)
        if refusal is not None:
            return codec.error_pdu(frame.invoke_id, codec.SERVICE_WRITE_PROPERTY, refusal[0], refusal[1])
        self.objects[key][property_identifier] = request["value_octets"]
        self.on_write(request)
        return codec.simple_ack(frame.invoke_id, codec.SERVICE_WRITE_PROPERTY)
