# Packet101b setup namespace

Packet101 passed its window setup and refused native preparation on the
resident FP32 scalar guard. The owner reports clean shutdown and no submitted
native, candidate, timed or capture request. Its sealed packet and failed-run
evidence remain immutable. The native-adapter correction is reviewed separately.

This authored successor uses packet directory
`prepared-resolution-reference-101b` and run name
`encoder-server-resolution-reference-101b-two-way-w1-b1-p1-dxpu2-s640x384`.
Its seven setup requests use prefix `resolution-ref101b-20261007`:
window-probe, prepare-native, pin0, capture0, coverage, decode-probe and freeze.
Integration's exact setup-name gates follow that prefix. The transition keeps
the `ltx.resolution101.transition.v1` schema family and explicitly records
`packet_revision: "101b"`; STATUS identifies the successor and claims no GPU
qualification. Qualified packet99b remains the source parent.

The 25 unconsumed plan names, indices, payloads and qualification ID are
unchanged. Plan semantic SHA remains
`307ff7547b8275c75d7f642673174cac11a45e0d7bc0041958a834544faa8745`.
New canonical inner setup-schedule SHA, pinned by the request client, is
`76a9770531366fe0149ded953fb84d52231bb3079f384e836c9c8b9e3bc4f82c`.
Comparing against sealed packet101's setup schedule established exactly the
seven setup-name substitutions, their dependency references and derived graph
hashes; geometry, arithmetic inputs and capture index 99900030 are unchanged.

Read-only namespace admission on 2026-10-07 checked direct entries under
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/requests`,
`output/validation`, and `output`. None matched any of the 32 names exactly
or with artifact suffix separators `.`, `_`, or `-`. This is a point-in-time
collision check, not a reservation; exclusive runtime writes remain required.

CPU validation: `python3 -B -m unittest discover -s
experiments/ltx25-b70/recovery/20261007-resolution-runtime -p TEST_FILENAME`
passes for `test_schedule.py` (9), `test_integration.py` (16),
`test_runtime_packet.py` (10), and `test_request_client.py` (22).
These tests do not materialize a packet, contact an endpoint or execute models.
No qualification, launch admission or measured result follows from this change.
