# wiretest - the series' Wiretest Harness

A Python 3 package (standard library only) for **Wire Tests**: tests that drive a
running example over BACnet/IP from outside it, with Python-simulated Peers, and
fail when the example's Profile Function is removed. See the series glossary
(`docs/GLOSSARY.md` in the example-series folder) for the vocabulary.

| Module | What it gives a test |
|---|---|
| `codec` | Build and parse BVLL (Annex J, including the BBMD and foreign-device messages), NPDU (clause 6: DNET/DADR, SNET/SADR, network layer messages) and APDU (clause 20) octets; Reject / Abort PDUs; `parse_read_property_request(apdu, with_array_index=True)` keeps the index |
| `endpoint` | `Endpoint` - a UDP socket that sends frames and collects replies (`clear()` to start fresh, `mac` for its B/IP address); `broadcast_listener` - capture what an example broadcasts (Linux/macOS) |
| `client` | `Client` - confirmed requests with invoke ids (`read_property`, `write_property`, `read_property_multiple`, `device_communication_control`, `who_is`), optionally through a router (`dnet=`, `dadr=`), with a short `timeout=` and visible `retries=`; `Answer` (`ok`, `acked`, `value`, `error`, `reject_reason`, `abort_reason`) |
| `services` (0.7.0) | ReadPropertyMultiple client side, ReadRange and Event Log records, CreateObject / DeleteObject, AtomicReadFile / AtomicWriteFile, SubscribeCOVPropertyMultiple and COV notifications, LifeSafetyOperation, BACnetLandingCallStatus, BACnetLightingCommand |
| `process` | `start(exe, arguments, label, environment=None)` - run an example until its `ready` line; `Program.press(keys)` (menu keys, POSIX); `Program.wait_for_text(text, seconds, after)`; `Program.stop()`; `broadcast_address(console, port)`; `IAmBroadcasts` - count a device's I-Am heartbeat on the wire and in its console |
| `control` (0.7.0) | `SimulationControl` - the client of an example's loopback test control channel; `CommandFile` - an example's test-only command file |
| `peer` | `SimulatedDevice` - a Python BACnet/IP device (ReadProperty of its Device object, Who-Is/I-Am) that answers back through a router; `broadcast=(ip, port)` also makes it hear its network's broadcasts (Linux/macOS); `send()`, `simple_acks()` |
| `peer` (0.6.0) | `SimulatedServer` - a Peer whose objects answer ReadProperty, ReadPropertyMultiple and WriteProperty, with `mode` online / offline / refusing, write hooks and request bookkeeping; 0.7.0 options `commandable=` (priority arrays), `array_elements=True`, `failures` (Reject / Abort / silent / malformed) and `whole_arrays_refused` |
| `alarm` | AcknowledgeAlarm, GetEventInformation, DeviceCommunicationControl, TimeSynchronization; `EventNotification` decoding; `event_notification()` encoding (a Peer's alarm) |
| `workstation` | `Workstation` - a client that is also an event-notification recipient, with the same `timeout=` / `retries=` as `Client`, and `announce()` |
| `wait` | `wait_until(check, seconds)`; `sample(read, seconds, interval)`, `sleep_until(start, seconds)`, `monotonic(values, rising)` |
| `results` | `record` (a counted check), `known_gap` (a reported defect outside the example), `summary` (exit code) |

```python
import wiretest

example = wiretest.start("build/BACnetExampleBRTR", ["--port", 47880], "router")
client = wiretest.Endpoint()
client.send(wiretest.bvlc(wiretest.npdu(
    wiretest.read_property_request(1, wiretest.OBJECT_TYPE_DEVICE, 389018, wiretest.PROPERTY_OBJECT_NAME),
    expecting_reply=True)), 47880)
answer = client.wait_for(lambda frame: frame.invoke_id == 1, 3)
wiretest.record("Device answers", answer is not None and answer.pdu_type == wiretest.PDU_COMPLEX_ACK)
example.stop()
raise SystemExit(wiretest.summary())
```

## Vendoring

This folder is the same in every example that has Wire Tests, like `common/`.
Nothing in it names one profile; profile-specific cases live in the example's
`tests/` folder. To change it: edit it, bump `WIRETEST_VERSION` in
`__init__.py`, add a `CHANGELOG.md` entry, and copy the folder to every
example that vendors it.
