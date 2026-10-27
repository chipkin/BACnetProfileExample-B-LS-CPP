# VeriBACnet results

The latest VeriBACnet run of this folder's project, summarised by hand from
that run's `report.json`. The run's own Results Folder (reports, packet
captures, wire logs) is not published: it holds the testing machine's network
addresses.

| | |
|---|---|
| Date | 2026-10-27 |
| Example | BACnet B-LS (Lighting Supervisor) Example - C++ v1.2.0 (`common/` 3.5.0), CAS BACnet Stack `6.x` @ `69b6249f` |
| Profile | B-LS (BACnet Lighting Supervisor) |
| Transport | BACnet/IP, UDP port 47840 |
| VeriBACnet | 0.20.0, a later build (its test device uses CAS BACnet Stack 6.0.23.0) |
| Test plan | 114 BTL tests (ANSI/ASHRAE 135.1-2023) selected for the B-LS profile and the options this example claims |
| Result | **58 PASS · 1 FAIL · 0 ERROR · 55 SKIP** |
| Passwords | none (this example requires no DeviceCommunicationControl password) |

**Judged BTL-clean on BACnet/IP, with a star**: the one failed test is a
defect in the test script, not in the example (below, tracked); nothing
errored, and every skipped test has a stated reason. The star means some
functions the example claims were not measured by VeriBACnet in this run
(below). See "What BTL-clean means" in [README.md](README.md). This is not BTL
certification.

**Measured coverage:** 59 of the 114 selected tests ran: 58 passed and 1
failed on the test script. Of the 55 skipped, 36 wait on a test-tool or
test-script fix (tracked), 6 need an operator, 10 do not apply to this device
(it cannot create, delete or rename objects over BACnet, does not execute
WritePropertyMultiple, has no optional-functionality property, and some tests
apply only to older protocol revisions), and 3 need the device to start a
write on its own, which the test tool cannot trigger yet.

**The failed test** (7.3.2.34.1, Last_Priority) expects Channel 1's
Last_Priority to read its initial value, 16. In this example Schedule 1 writes
Channel 1 at priority 12 from start-up, and again whenever the clock crosses
its 09:00 / 17:00 times (the time-synchronization tests move the clock), so
Last_Priority correctly reads 12. The test script does not allow for the
device's own Schedule. The test's owners ruled that the test stays strict
(it still expects 16) and now says in its failure message that the device's
own logic may have written the Channel first, so this test is expected to
keep failing on this example.

**Not measured:**

- **Writing to another device** (DS-WP-A, DS-ALO-A): the Channel forwards
  every write to device 389016's Lighting Output, but the test tool cannot yet
  make the device start a write. The Wire Test `tests/channel_fanout_test.py`
  checks it with a simulated device 389016.
- **The Schedule** (SCHED-E-B): the Schedule and Calendar tests need scenarios
  the test tool cannot set up on this device yet, and one has no script
  (tracked). The Wire Test checks that Schedule 1's write reaches Channel 1 and
  Jade.
- **Who-Is initiation** (DM-DDB-A): the one test needs an operator.
- **DeviceCommunicationControl's disable-initiation**: the four tests skip
  because the test tool has no trigger it can drive (tracked). Checked by hand
  instead: with initiation disabled the device does not send device 389016 its
  write, and it sends it again after enable; `tests/channel_fanout_test.py`
  section 7 covers it.

**Measured now:** the Lighting Output's Lighting_Command operations. The NONE
test and the fade, ramp and step tests (7.3.2.39.3 to 7.3.2.39.9) all pass
with the Lighting Output engine this example now shares with the B-LD
example. The two tracking tests and the nine blink-warn tests are still
operator-guided placeholders in the test tool (tracked); the Wire Tests cover
those.

Compared with the run of 2026-10-26 (56 PASS, 1 FAIL, 57 SKIP): the
Lighting Output special-value test (7.2.2) and the scalar write test (9.22.2.1)
now run and pass, because the test tool takes their targets from this device.
Nothing else moved.

The first published run of this project was 2026-10-26. Compared with the previous
(unpublished) run of 2026-10-24, 98 tests, 48 PASS, 7 FAIL:

- The seven Lighting_Command failures are fixed (the example now carries the
  B-LD Lighting Output engine).
- Channel 1's Write_Status follows every write the Channel forwards, not only
  a WriteGroup's; the WriteGroup support test now runs and passes.
- The example moved to CAS BACnet Stack `6.x` @ `69b6249f`.
- The project declares the test-plan options this example supports, so 16
  more tests are selected.
