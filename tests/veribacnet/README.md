# VeriBACnet Project

This folder is the **VeriBACnet Project** for the BACnet B-LS (Lighting Supervisor) C++
example. VeriBACnet is Chipkin's BACnet conformance tool; it runs the BTL
test plan (ANSI/ASHRAE 135.1) against a running BACnet device. The files here
describe this example the way VeriBACnet's desktop app saves a project: which
device to test, what that device is, and which tests apply to it. You can open
the project in the app, or run it from the command line.

Nothing in here is needed to build or run the example itself.

## What is in the project

| File | What it is |
|---|---|
| `b-ls-cpp.project.json` | The project: its name and id, the device to test (address 127.0.0.1, UDP port 47840, device instance 389017), the profile (B-LS), and the list of selected tests. It names the other files. |
| `b-ls-cpp.iut-description.json` | What the tests expect the device to be: its identity strings, the services and object types it supports, its segmentation and maximum APDU size, its objects, and the BIBBs it claims. Written from this example's `docs/PICS.md`, `docs/objects.json` and `main.cpp`. |
| `b-ls-cpp.device-model.json` | The desktop app's view of the same device: the claimed BIBBs, the EPICS header (profile, product description), and the test settings. |
| `b-ls-cpp.tpi` | The EPICS (the device's capabilities statement), consistent with `docs/PICS.md`. |
| `b-ls-cpp.device-snapshot.json` | What VeriBACnet read from the running example (its objects and properties). The device's own network settings (IP address, subnet mask, gateway, DNS server, MAC address and the like) are replaced by the text `host-specific (not recorded)`. |

The files contain no machine names and no absolute paths, and the target is
always `127.0.0.1`. In the EPICS, a property shown as `?` is one the tool could
not decode from the device.

If you change what the example does (a new object, a new service, a different
identity string), change these files to match, the same way you would update
`docs/PICS.md`.

## How to re-run it

1. Build the example (see the top-level README).
2. Start it on UDP port 47840 with device instance 389017, from the root of
   this repository:

   ```
   build\Release\BACnetExampleBLS.exe --port 47840 --deviceID 389017
   ```

   Wait until it prints `FYI: Device 389017 ("Chipkin Example B-LS") ready.`
   Use port 47840, not the standard 47808, so the test does not collide with
   other BACnet software on the machine. Leave it running.
3. In a second terminal, from the root of this repository:

   ```
   VeriBACnet.exe --cli run --project tests/veribacnet/b-ls-cpp.project.json
   ```

4. Stop the example when the run has finished.

VeriBACnet does not start or stop the example; you do.

## Where the results go

Each run writes its own **Results Folder**: the report (`report.md` and
`report.json`), the findings (`findings.json`), a summary of the run
(`run.json`), and the evidence for every test (a packet capture and a decoded
wire log). By default it is a new, time-stamped folder under
`tests/veribacnet/veribacnet-output/`, which git ignores. Pass
`--out-dir <folder>` to put it somewhere else. The evidence holds the IP
addresses of the machine that ran the test, so do not commit it or publish it.

## What "BTL-clean" means

A run executes the BTL tests that apply to this example's profile and BIBBs.
The example is **BTL-clean** when, on the transport tested, no failure or error
is the example's own fault, every other failure or error is tracked, and every
skipped test has a stated reason (for example, it needs hardware the example
does not simulate). Each failure, error or coverage gap is recorded as a
**Finding**, so a result that is not clean tells you exactly what to look at.

BTL-clean is a statement about this tool's test run. It is not BTL
certification, which is granted by a BACnet Testing Laboratory; the example
has not been submitted for certification.
