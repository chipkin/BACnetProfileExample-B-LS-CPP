# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""Start and stop an example binary, and read what its console says."""
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .codec import i_am_device_instance
from .endpoint import broadcast_listener

# common/'s console line for every frame it sends, e.g.
#   TX 21 bytes to 192.168.3.255:47808 (broadcast) (Network Port 1) - Unconfirmed: I-Am
TX_BROADCAST = re.compile(r"TX \d+ bytes to (\d+\.\d+\.\d+\.\d+):(\d+) \(broadcast\)")


class Program:
    """A running example: console captured to a file, stdin a pipe (the examples quit on 'q')."""

    def __init__(self, exe, arguments, label, environment=None):
        """`environment`: extra environment variables for the example (added to this process's
        own), e.g. a test-only switch that the example reads and its command line never offers."""
        self.label = label
        self.log = tempfile.NamedTemporaryFile(prefix=f"{label}-", suffix=".log", delete=False)
        variables = dict(os.environ, **{name: str(value) for name, value in (environment or {}).items()})
        # Absolute: Windows' CreateProcess does not resolve a relative path written with "/".
        self.process = subprocess.Popen([str(Path(exe).resolve())] + [str(argument) for argument in arguments],
                                        stdin=subprocess.PIPE, stdout=self.log, stderr=subprocess.STDOUT,
                                        env=variables)

    def wait_for_output(self, text, seconds=20):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if text in self.output():
                return True
            if self.process.poll() is not None:
                return text in self.output()
            time.sleep(0.1)
        return False

    def wait_for_text(self, text, seconds, after=0):
        """Wait until `text` appears in the console after offset `after`; return the offset just
        past it, or None. Pass the returned offset as the next `after` so each check only matches
        output produced after the previous one (0.7.0, B-OD)."""
        deadline = time.monotonic() + seconds
        while True:
            found = self.output().find(text, after)
            if found >= 0:
                return found + len(text)
            if time.monotonic() >= deadline or self.process.poll() is not None:
                return None
            time.sleep(0.1)

    def wait_ready(self, seconds=20):
        """Every example prints a line containing 'ready' once it is on the network."""
        return self.wait_for_output("ready", seconds)

    def output(self):
        with open(self.log.name, "r", errors="replace") as handle:
            return handle.read()

    def press(self, keys):
        """Type `keys` on the example's keyboard (its stdin pipe). The examples read keys
        with common/'s PollKey(), which sees a pipe on Linux/macOS but not on Windows
        (_kbhit() only reads a console), so this drives an example on POSIX only."""
        self.process.stdin.write(keys.encode("ascii"))
        self.process.stdin.flush()

    def stop(self):
        if self.process.poll() is None:
            try:
                self.process.stdin.write(b"q")
                self.process.stdin.flush()
                self.process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                self.process.kill()
                self.process.wait()

    def keep_log(self):
        print(f"      ({self.label} console: {self.log.name})")


def start(exe, arguments, label, environment=None):
    """Start an example and wait for its 'ready' line; exits the test if it never comes."""
    program = Program(exe, arguments, label, environment)
    if not program.wait_ready():
        print(program.output())
        program.stop()
        sys.exit(f"{label} did not reach 'ready' - see its console above")
    return program


class IAmBroadcasts:
    """Counts a device's unsolicited I-Am broadcasts (a heartbeat) from a mark onwards - on the
    wire where a second socket can share the example's port (Linux/macOS, through
    endpoint.broadcast_listener), and on every platform in the example's console, whose
    common/ TX line is printed for each datagram actually sent and never for one the stack
    refused. `counts()` is (on the wire, or None on Windows; in the console).
    (0.7.0, B-ASC's Heartbeats.)"""

    def __init__(self, program, port, device_instance):
        self.program = program
        self.device_instance = device_instance
        self.console_line = re.compile(rf"TX \d+ bytes to [\d.]+:{port} \(broadcast\)[^\n]*I-Am")
        broadcast_ip = broadcast_address(program.output(), port)
        self.listener = broadcast_listener(broadcast_ip, port) if os.name != "nt" and broadcast_ip else None
        self.mark()

    def mark(self):
        self.console_offset = len(self.program.output())
        if self.listener is not None:
            self.listener.clear()

    def counts(self):
        console = len(self.console_line.findall(self.program.output()[self.console_offset:]))
        if self.listener is None:
            return None, console
        self.listener.collect(0.05)
        wire = sum(1 for frame in self.listener.frames if i_am_device_instance(frame.payload) == self.device_instance)
        return wire, console

    def watch(self, seconds):
        """Mark, wait `seconds`, and return counts()."""
        self.mark()
        time.sleep(seconds)
        return self.counts()

    def close(self):
        if self.listener is not None:
            self.listener.close()


def broadcast_address(output, port):
    """The local broadcast address an example sends to on `port`, from its own TX line."""
    for found in TX_BROADCAST.finditer(output):
        if int(found.group(2)) == port:
            return found.group(1)
    return None


def default_exe(repository, name):
    """build/<name> (single-config generators) or build/Release/<name>.exe (Visual Studio)."""
    repository = Path(repository)
    for candidate in (repository / "build" / name, repository / "build" / "Release" / f"{name}.exe",
                      repository / "build" / f"{name}.exe"):
        if candidate.exists():
            return candidate
    return repository / "build" / name
