# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""wiretest - the BACnet profile example series' shared Wiretest Harness.

Wire Tests drive a running example over BACnet/IP from outside it and fail when the
example's Profile Function is removed. This package is the part every example shares:

    codec     - BVLL (incl. BBMD and foreign-device messages) / NPDU / APDU encode and decode
    endpoint  - UDP sockets that send frames and collect replies; broadcast capture
    client    - Client: ReadProperty / WriteProperty with invoke ids, optionally through a router
    process   - start / stop an example binary, read its console
    peer      - SimulatedDevice, a Python BACnet/IP device to use as a Peer; SimulatedServer,
                one whose objects answer ReadProperty / ReadPropertyMultiple / WriteProperty
                and that can go offline or refuse writes
    alarm     - alarm, event and device-management services: AcknowledgeAlarm,
                GetEventInformation, DeviceCommunicationControl, TimeSynchronization,
                event-notification decoding
    workstation - Workstation, a client that is also an event-notification recipient
    wait      - wait_until(), poll the example until it reaches a state
    results   - record() / known_gap() / summary() bookkeeping

It is VENDORED into each example, like common/: the same files in every repository,
versioned by WIRETEST_VERSION below with its own CHANGELOG.md. Nothing in it is specific
to one profile - profile-specific cases live in the example's tests/ folder. Change it in
one example, bump the version, then copy it to every example that vendors it.

Python 3 standard library only.
"""

WIRETEST_VERSION = "0.6.0"

from . import alarm, client, codec, endpoint, peer, process, results, wait, workstation  # noqa: E402,F401
from .client import Answer, Client  # noqa: E402,F401
from .codec import *  # noqa: E402,F401,F403
from .endpoint import Endpoint, broadcast_listener  # noqa: E402,F401
from .peer import SimulatedDevice, SimulatedServer  # noqa: E402,F401
from .process import Program, broadcast_address, default_exe, start  # noqa: E402,F401
from .results import known_gap, record, summary  # noqa: E402,F401
from .wait import wait_until  # noqa: E402,F401
from .workstation import Workstation  # noqa: E402,F401
