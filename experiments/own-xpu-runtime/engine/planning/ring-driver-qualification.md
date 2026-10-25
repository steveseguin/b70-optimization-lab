# Scripted depth-two native qualification

`tools/ring_driver.py` plans and controls the opt-in target-only ring commands
24–26. It deliberately supplies oracle-assisted scripted hypotheses from an
already recorded output sequence. It does not invoke the draft model, train
weights, measure live-draft throughput, or qualify independent CPU-reference
fidelity. The unchanged lifecycle owns passive holder/fault admission, stop
pipes, one process per stage, final DUMP/postflight and cooperative FINISH.

Start from a `ownrt.pipeline-driver-config.v1` target-only configuration with a
current native build receipt and add:

```json
{
  "ring": true,
  "scripted_proposal_tokens": ["replace with all 32 recorded integer output IDs"],
  "force_miss_positions": [87, 88, 90],
  "required_miss_depths": [1, 2],
  "require_two_row_abort": true,
  "verify_restore": true,
  "eos_token_ids": [248044, 248046]
}
```

The first gate uses the existing 87-input/32-output fixture and PP4 boundaries
`[0,13,25,37,48]`. Forced positions refer to generated **input** rows, so position
87 is the first sampled output fed back to the model. Hypotheses retain their
original batch depth when their first guess becomes verified; new guesses never
replace work already issued. The controller requires the configured target
rejections, both rejection depths, and a stage-zero two-row suffix that actually
executes and receives an exact restore acknowledgment. Scheduler timing can make
coverage unavailable; missing coverage refuses qualification rather than
silently accepting a shallower test. The config values above are placeholders
within the existing complete native config, not a standalone runnable config.

CPU planning (no GPU action):

```sh
python3 engine/tools/ring_driver.py --config /absolute/ring-config.json --plan /absolute/ring-plan.json
```

The owning coordinator supplies explicit admission and the established single
systemd unit only after source review, frozen native build, passive hardware
inventory and fault baseline checks. This document does not launch that unit.
`--run --plan ... --admission ... --unit ...` regenerates and compares the whole
plan before calling the same guarded lifecycle used by the accepted proofs.
The plan pins the native receipt/binary, complete compiled source census, model
authentication, new codec/controller/coordinator and all imported lifecycle and
observer helpers. The canonical native flags are `--pipeline-ring`,
`--pipeline-ring-request-sha256 HEX`, and optionally
`--pipeline-ring-verify-restore`. Wavefront, live draft, legacy MTP and persistent
RESET are excluded from this first gate.

The wire bridge authenticates all 224 bytes of each ROW publication, including
its immutable request/prefix/row/parent identity, original ticket and full F32
payload SHA256. Resolution ACKs authenticate owner, epoch, original ROW ticket,
physical and committed cursors, pending count, every discarded suffix ID,
reserved bytes, sticky error and required restore-bytecheck policy. Final stages
only receive verified rows. Accepted rows retain small lineage metadata but
release completed stream payloads; at most three unresolved rows retain streams.

Evidence:

- `ring-result.json`, schema `ownrt.ring-driver-result.v1`, names the actual
  `scripted-target-only-ring` mode and hashes both `plan.json` and the unchanged
  lifecycle `result.json`. The latter's inherited `verified-wavefront` label
  describes the reused lifecycle only. A passed controller result is still
  subject to the independent full-state comparison.
- `ring-coverage.json` records actual rejection depths, issued hypothesis IDs,
  exact discarded IDs and two-row restore acknowledgments even if coverage
  requirements ultimately fail.
- `schedule.jsonl`, `tokens.jsonl`, native ring traces and final full-state dumps
  permit independent comparison to the accepted same-input target-state proof.
- `evidence/ring-wire-cpu.json` records CPU codec/socket/coordinator tests. These
  do not assert GPU execution, speed, portable deployment or the six unresolved
  independent-reference near-ties.

CPU checks, from `engine/tools`:

```sh
PYTHONPATH=../planning python3 -m unittest test_ring_wire test_ring_driver test_ring_coordinator -q
```

The tests include a compiled canonical C++ codec fixture, real fragmented socket
workers for 2/4/6 stages, mutated metadata/payloads, stale/truncated replies,
physical/logical cursor and bytecheck refusals, oldest tentative acceptance,
first/second-depth rejection, two-row suffix rollback, and bounded payload
retention. No native engine build or GPU is required.
