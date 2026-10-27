# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""A Python-simulated operator workstation: a client that is ALSO an event recipient.

wiretest.Client waits for one answer at a time and drops what else arrives, so it cannot
be a notification recipient: the device's ConfirmedEventNotification has to be answered
within the device's APDU_Timeout whatever the test is doing at that moment. Workstation
owns one UDP socket and, in a background thread:

  - keeps every Confirmed/UnconfirmedEventNotification it receives (`notifications`) and
    answers each confirmed one with a SimpleACK (cl. 13.8.2) - unless `answer_notifications`
    is False, which plays a recipient that has gone silent;
  - hands every other answer (SimpleACK / ComplexACK / Error / Reject / Abort) to the
    request waiting for its invoke id.

`request()` / `read_property()` / `write_property()` / `read_property_multiple()` /
`device_communication_control()` work as wiretest.Client's do, and return the same
wiretest.Answer. `retries=` and `timeout=` work as Client's too (0.7.0, from B-AEC's
RetryingWorkstation and B-LSC's request_with_retry): an unanswered request is sent again
with the SAME invoke id, with a visible [RETRY] line. `announce()` sends an I-Am for a
device instance the workstation plays, unicast, so a device whose Recipient_List names that
instance can bind the workstation's address (0.7.0, B-LSC). Came from B-AAC's
tests/workstation.py (wiretest 0.6.0).
"""
import select
import socket
import threading
import time

from . import alarm, codec
from .client import DEFAULT_TIMEOUT, Answer, ConfirmedServices, send_with_retries  # noqa: F401 (Answer: 0.6.0 name)

RESPONSE_TYPES = (codec.PDU_SIMPLE_ACK, codec.PDU_COMPLEX_ACK, codec.PDU_ERROR, codec.PDU_REJECT, codec.PDU_ABORT)


class Workstation(ConfirmedServices):
    def __init__(self, bind_ip="127.0.0.1", port=0, answer_notifications=True, retries=0,
                 timeout=DEFAULT_TIMEOUT):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((bind_ip, port))
        self.ip, self.port = self.sock.getsockname()
        self.answer_notifications = answer_notifications
        self.retries = retries
        self.timeout = timeout
        self.notifications = []      # every EventNotification received, in order (alarm.EventNotification)
        self._responses = []
        self._invoke_id = 0
        self._lock = threading.Lock()
        self._arrived = threading.Condition(self._lock)
        self._running = True
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    @property
    def mac(self):
        """This workstation's 6-octet B/IP address - what a Recipient_List entry names."""
        return codec.mac(self.ip, self.port)

    def close(self):
        self._running = False
        self._thread.join(timeout=2)
        self.sock.close()

    # -- receiving -----------------------------------------------------------

    def _serve(self):
        while self._running:
            try:
                ready, _, _ = select.select([self.sock], [], [], 0.1)
            except (OSError, ValueError):
                return
            if not ready:
                continue
            try:
                data, source = self.sock.recvfrom(2048)
            except ConnectionResetError:
                continue   # Windows: ICMP port-unreachable for an earlier send (see endpoint.py)
            except OSError:
                return
            frame = codec.Frame(data, source)
            if not frame.ok or frame.network_message is not None:
                continue
            if alarm.is_event_notification(frame):
                notification = alarm.EventNotification(frame)
                with self._arrived:
                    self.notifications.append(notification)
                    self._arrived.notify_all()
                if notification.confirmed and self.answer_notifications:
                    self.sock.sendto(codec.bvlc(codec.npdu(codec.simple_ack(
                        frame.invoke_id, alarm.SERVICE_CONFIRMED_EVENT_NOTIFICATION))), source)
            elif frame.pdu_type in RESPONSE_TYPES:
                with self._arrived:
                    self._responses.append(frame)
                    self._arrived.notify_all()

    def wait_for_notification(self, predicate, seconds, after=0):
        """The first notification at index >= `after` that matches, waiting up to `seconds`; or None."""
        deadline = time.monotonic() + seconds
        with self._arrived:
            while True:
                for notification in self.notifications[after:]:
                    if predicate(notification):
                        return notification
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._arrived.wait(remaining)

    def notifications_since(self, after):
        with self._lock:
            return list(self.notifications[after:])

    def mark(self):
        """An index to pass as `after`: only notifications that arrive from now on."""
        with self._lock:
            return len(self.notifications)

    # -- requesting ----------------------------------------------------------

    def request(self, build_apdu, port, ip="127.0.0.1", timeout=None):
        with self._lock:
            self._invoke_id = (self._invoke_id + 1) % 256
            invoke_id = self._invoke_id
            self._responses = [frame for frame in self._responses if frame.invoke_id != invoke_id]
        octets = codec.bvlc(codec.npdu(build_apdu(invoke_id), expecting_reply=True))

        def attempt(seconds):
            self.sock.sendto(octets, (ip, port))
            deadline = time.monotonic() + seconds
            with self._arrived:
                while True:
                    for frame in self._responses:
                        if frame.invoke_id == invoke_id:
                            self._responses.remove(frame)
                            return frame
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return None
                    self._arrived.wait(remaining)
        return send_with_retries(invoke_id, attempt, self.retries, self.timeout if timeout is None else timeout)

    def send_unconfirmed(self, apdu, port, ip="127.0.0.1"):
        self.sock.sendto(codec.bvlc(codec.npdu(apdu)), (ip, port))

    def announce(self, device_instance, port, ip="127.0.0.1", vendor_identifier=389):
        """Send an I-Am for `device_instance` from this workstation's socket to one device. A
        device whose Recipient_List names `device_instance` learns the workstation's address
        from it - the way a workstation's start-up I-Am reaches a panel, without relying on
        broadcasts (which do not reach a 127.0.0.1 socket)."""
        self.send_unconfirmed(codec.i_am(device_instance, vendor_identifier), port, ip)
