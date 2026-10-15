# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""UDP sockets that send BACnet/IP frames and collect what comes back."""
import socket
import time

from .codec import Frame, mac


class Endpoint:
    """A UDP socket (127.0.0.1, ephemeral port by default) that sends frames and keeps every reply."""

    def __init__(self, port=0, bind_ip="127.0.0.1", reuse=False):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if reuse:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.bind((bind_ip, port))
        self.ip, self.port = self.sock.getsockname()
        self.frames = []

    @property
    def mac(self):
        """This socket's 6-octet B/IP address (Annex J.1.2) - meaningful when bound to a real address."""
        return mac(self.ip, self.port)

    def clear(self):
        """Forget every frame kept so far (and any already queued), so the next wait_for sees only new ones."""
        self.collect(0.05)
        self.frames = []

    def send(self, frame, port, ip="127.0.0.1"):
        self.sock.sendto(frame, (ip, port))

    def _receive(self, timeout):
        self.sock.settimeout(timeout)
        try:
            data, source = self.sock.recvfrom(2048)
        except socket.timeout:
            return False
        except ConnectionResetError:
            # Windows reports an ICMP port-unreachable for an earlier send as an error
            # on the NEXT receive (WSAECONNRESET). It says nothing about this datagram.
            return True
        self.frames.append(Frame(data, source))
        return True

    def collect(self, seconds):
        """Keep every datagram arriving in the next `seconds`; returns all frames so far."""
        deadline = time.monotonic() + seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not self._receive(remaining):
                return self.frames

    def wait_for(self, predicate, seconds):
        """The first decoded frame (already kept, or arriving within `seconds`) that matches, or None."""
        deadline = time.monotonic() + seconds
        seen = 0
        while True:
            for frame in self.frames[seen:]:
                if frame.ok and predicate(frame):
                    return frame
            seen = len(self.frames)
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not self._receive(remaining):
                for frame in self.frames[seen:]:
                    if frame.ok and predicate(frame):
                        return frame
                return None

    def close(self):
        self.sock.close()


def broadcast_listener(broadcast_ip, port):
    """Receives what an example BROADCASTS on one UDP port, and nothing it is sent unicast.

    Bound to the broadcast address itself (not 0.0.0.0), so unicast datagrams for the
    example's own socket on the same port still reach the example - only datagrams
    addressed to broadcast_ip:port are delivered here too. Both sockets set SO_REUSEADDR,
    which is what lets a second socket share the port; that sharing is POSIX behaviour,
    so broadcast checks run on Linux/macOS (Windows' SO_EXCLUSIVEADDRUSE, which common/
    sets deliberately, refuses it)."""
    return Endpoint(port, bind_ip=broadcast_ip, reuse=True)
