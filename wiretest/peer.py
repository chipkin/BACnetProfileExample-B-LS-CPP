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
