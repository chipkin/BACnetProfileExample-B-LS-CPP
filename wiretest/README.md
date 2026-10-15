# wiretest - the series' Wiretest Harness

A Python 3 package (standard library only) for **Wire Tests**: tests that drive a
running example over BACnet/IP from outside it, with Python-simulated Peers, and
fail when the example's Profile Function is removed. See the series glossary
(`docs/GLOSSARY.md` in the example-series folder) for the vocabulary.

| Module | What it gives a test |
|---|---|
| `codec` | Build and parse BVLL (Annex J, including the BBMD and foreign-device messages), NPDU (clause 6: DNET/DADR, SNET/SADR, network layer messages) and APDU (clause 20) octets |
| `endpoint` | `Endpoint` - a UDP socket that sends frames and collects replies (`clear()` to start fresh, `mac` for its B/IP address); `broadcast_listener` - capture what an example broadcasts (Linux/macOS) |
| `client` | `Client` - ReadProperty / WriteProperty with invoke ids, optionally through a router (`dnet=`, `dadr=`), with an opt-in visible retry (`retries=`); `Answer` (`ok`, `value`, `error`) |
| `process` | `start(exe, arguments, label, environment=None)` - run an example until its `ready` line; `Program.press(keys)` (menu keys, POSIX); `Program.stop()`; `broadcast_address(console, port)` |
| `peer` | `SimulatedDevice` - a Python BACnet/IP device (ReadProperty of its Device object, Who-Is/I-Am) that answers back through a router; `broadcast=(ip, port)` also makes it hear its network's broadcasts (Linux/macOS) |
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
