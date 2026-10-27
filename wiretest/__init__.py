# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""wiretest - the BACnet profile example series' shared Wiretest Harness.

Wire Tests drive a running example over BACnet/IP from outside it and fail when the
example's Profile Function is removed. This package is the part every example shares:

    codec     - BVLL (incl. BBMD and foreign-device messages) / NPDU / APDU encode and decode
    endpoint  - UDP sockets that send frames and collect replies; broadcast capture
    client    - Client: confirmed requests with invoke ids, optionally through a router, with an
                opt-in short timeout and visible [RETRY]s; Answer
    services  - ReadPropertyMultiple (client side), ReadRange and Event Log records,
                Create/DeleteObject, AtomicRead/WriteFile, SubscribeCOVPropertyMultiple and
                COV notifications, LifeSafetyOperation, BACnetLandingCallStatus,
                BACnetLightingCommand
    process   - start / stop an example binary, read its console, count its I-Am broadcasts
    control   - SimulationControl and CommandFile, an example's test-only control channels
    peer      - SimulatedDevice, a Python BACnet/IP device to use as a Peer; SimulatedServer,
                one whose objects answer ReadProperty / ReadPropertyMultiple / WriteProperty,
                that can go offline or refuse writes, keep priority arrays, answer array
                elements and script Reject / Abort / silent / malformed answers
    alarm     - alarm, event and device-management services: AcknowledgeAlarm,
                GetEventInformation, DeviceCommunicationControl, TimeSynchronization,
                event-notification encoding and decoding
    workstation - Workstation, a client that is also an event-notification recipient
    wait      - wait_until(), poll the example until it reaches a state; sample() it over time
    results   - record() / known_gap() / summary() bookkeeping

It is VENDORED into each example, like common/: the same files in every repository,
versioned by WIRETEST_VERSION below with its own CHANGELOG.md. Nothing in it is specific
to one profile - profile-specific cases live in the example's tests/ folder. Change it in
one example, bump the version, then copy it to every example that vendors it.

Python 3 standard library only.
"""

WIRETEST_VERSION = "0.7.0"

from . import alarm, client, codec, control, endpoint, peer, process, results, services, wait, workstation  # noqa: E402,F401,E501
from .client import Answer, Client  # noqa: E402,F401
from .codec import *  # noqa: E402,F401,F403
from .control import CommandFile, SimulationControl  # noqa: E402,F401
from .endpoint import Endpoint, broadcast_listener  # noqa: E402,F401
from .peer import SimulatedDevice, SimulatedServer  # noqa: E402,F401
from .process import IAmBroadcasts, Program, broadcast_address, default_exe, start  # noqa: E402,F401
from .results import known_gap, record, summary  # noqa: E402,F401
from .wait import monotonic, sample, sleep_until, wait_until  # noqa: E402,F401
from .workstation import Workstation  # noqa: E402,F401
