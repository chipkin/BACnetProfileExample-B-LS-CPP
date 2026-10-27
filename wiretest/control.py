# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""The Wire Tests' hands on an example's TEST-ONLY control channels (never BACnet).

An example with a Simulation (a door contact, a lift car, a smoke detector) or an operator
console (a display) may offer the test a way in that its command line never offers, switched
on by an environment variable the test sets (process.start(..., environment=)):

    SimulationControl   a loopback-only UDP port: each datagram is one plain-text command, and
                        the example answers each with one datagram - "ok", a value, or
                        "error <reason>" (B-GW, B-EM, B-EC, B-LSC, B-ALSC)
    CommandFile         a file the test appends one command per line to, which the example
                        reads and runs (B-OD): it opens no port, and a command cannot be lost

    control = SimulationControl(port)
    control.send("obstruct on")       # the answer; raises RuntimeError if none or "error ..."
    control.ask("state")              # the answer text, or None if the example never answered
    control.close()

Came from B-EM / B-EC's tests/simulation_control.py, B-LSC's tests/wiretest_extras.py and
B-OD's tests/client_peer.py (wiretest 0.7.0).
"""
import os
import socket
import tempfile


class SimulationControl:
    """Client of an example's loopback test control channel. `timeout` is how long one attempt
    waits for the answer; an unanswered command is sent again up to `retries` times, each with a
    visible [RETRY] line (a lost datagram on a busy host - a command whose ANSWER was lost is
    then carried out twice, and the second answer shows it)."""

    def __init__(self, port, ip="127.0.0.1", timeout=2.0, retries=2):
        self.address = (ip, port)
        self.timeout = timeout
        self.retries = retries
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))

    def _drain(self):
        """Drop any late answer to an earlier command, so it is not taken for this one's."""
        self.sock.setblocking(False)
        try:
            while True:
                self.sock.recvfrom(512)
        except (BlockingIOError, ConnectionResetError, OSError):
            pass
        finally:
            self.sock.setblocking(True)

    def ask(self, command):
        """Send one command; the example's answer text, or None if it never answered."""
        self._drain()
        self.sock.settimeout(self.timeout)
        for attempt in range(1 + self.retries):
            if attempt:
                print(f"[RETRY] simulation control '{command}' unanswered after {self.timeout} s - sent again",
                      flush=True)
            self.sock.sendto(command.encode("ascii"), self.address)
            try:
                data, _ = self.sock.recvfrom(512)
            except (socket.timeout, ConnectionResetError):
                continue
            return data.decode("ascii", errors="replace")
        return None

    def send(self, command):
        """Send one command that must succeed; returns the answer, raises RuntimeError otherwise."""
        reply = self.ask(command)
        if reply is None or reply.startswith("error"):
            raise RuntimeError(f"simulation control '{command}': {reply or 'no answer'}")
        return reply

    def close(self):
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *exception):
        self.close()


class CommandFile:
    """An example's TEST-ONLY command file: the test appends one command per line, the example
    (started with the file's path in an environment variable such as BOD_TEST_CONTROL_FILE)
    reads and runs each new line."""

    def __init__(self):
        handle = tempfile.NamedTemporaryFile(prefix="commands-", suffix=".txt", delete=False)
        handle.close()
        self.path = handle.name

    def send(self, command):
        with open(self.path, "a", encoding="ascii", newline="\n") as commands:
            commands.write(command + "\n")

    def close(self):
        try:
            os.unlink(self.path)
        except OSError:
            pass
