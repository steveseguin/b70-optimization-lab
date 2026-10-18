# Packet58m: one-card port record-chain preparation

Prepared on CPU only. **Do not launch until `verify_ready.py` passes.** It
requires packet58k's completed production / port / production receipts,
12/12 exact outputs in each arm, and at least **0.5%** over **each** control.
The existing screen requirements also remain: matching miss paths, one boot,
fresh owners, controls within 3%, and a candidate above the saved one-card
record. The checker rereads native output and receipt hashes through 58k's
sealed verifier. A saved `ready: true` flag cannot bypass it.

Port is exactly 58k's `down-tile16 + route-fast + rec-both-plus` selection.
The five retained binaries are byte-identical copies, totaling 72,734,584
bytes. No native compilation was needed. [Copy provenance](copy-manifest.json),
[build seal](build-receipt.json), [submission pins](submission-pins.json).

The chain runs K1a → K1b → KD → W2m → WS → WS128x → WS128, with 90-second
gaps. It preserves the packet58g arithmetic `iq3-p49-split32-v1`, packet49
oracle, twelve prompts, 128-token cap, BF16 KV at 4096, plain decode and 18 GB
immutable expert-weight cache. Fresh K1s choose the fallback miss path.
The output is fixed at `evidence/card0-58m-a`; existing output refuses reuse.

Every window holds the whole host. Lane B must be drained and excluded.
K1 needs 12 GiB available; model exactness windows retain 58g's 85,565,068,816
byte admission. WS128 needs **118,308,908,048 bytes available**, including
the unchanged 8 GiB reserve. Its peak host bound is 109,718,973,456 bytes.
These are allocation/admission bounds, not a newly measured peak or a claim
of current free memory. [All seven budgets](evidence/budget-cpu.json).

Only WS128 supplies timing: six class medians, then their median, using
99 intervals between token events 1 and 100. WS128x now reserves the whole
host too, but remains exactness-only under the inherited protocol. A second
timing run remains necessary for a speed verdict. The strict 512-token gate
stays false; standard 512-token prefill and natural completion are unmeasured.
Preparing this chain does not authorize publishing a result.

## CPU evidence

- [Ten full-size startup/submit checks](evidence/fullshape-submit-cpu.json):
  all five model windows × both miss paths, 3,446 allocation rows, 1,486 sites,
  contexts 32 and 4096, and the old p28 refusal reproduced before the repair.
- [Actual parser and host-reference checks](evidence/startup-cpu.json): commands
  come from the real suite driver. The copied GNU binary runs its production
  parser through `--priority-probe`, before loading any weights. Device
  authorization is removed and native priority is changed to nice19 for this
  CPU test. Full-size initialization is then exercised by the mock backend.
  This one-card chain has no separate host-reference process: `oracle_inputs`
  verifies packet49's existing CPU oracle, and `compare_request` replays each
  window against completed 58g outputs. That is not port device parity.
- [Fresh K1 byte checks](k1-cpu.json): 48 exact checks, both DOWN layouts.
  [Inherited GNU/Intel byte proof](evidence/inherited-byte-gates.json) is copied
  and hash-checked against the sealed 58j receipt, not counted as a new run.
- [Python regressions](evidence/python-cpu-gates.json), including a mocked
  seven-stage chain, no retry after KD failure, whole-host exclusion, changed
  receipts, wrong views, fault overlap, and offline submission/API projection.
- [Synthetic winner and loser](evidence/readiness-rule-cpu.json) and
  [existing 58g replay](evidence/submission-58g-dry-run.json).

## Coordinator handoff

Run from `/home/steve/llm-optimizations`. These first checks use no GPU:

```bash
P=experiments/own-xpu-runtime/stage2/packet58m-onecard-record
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal.py" --verify < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/verify_ready.py" --output "$P/ready.json" < /dev/null
```

The second command exits nonzero while receipts are missing or losing. It
prints the exact systemd command in [ready.json](ready.json). Before launching,
the coordinator captures a fresh fault review in the fixed new path:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/fault_review.py" --output "$P/evidence/fault-review-58m.json" < /dev/null
```

The chain validates that capture and derives the boundary from its newest
kernel timestamp minus exactly 2,000,000 microseconds. It never substitutes
wall time. It then rechecks readiness and the boot before starting any child.
The exact launch command is also in [WINDOW.md](WINDOW.md). CPU preparation
has not executed either the fault capture or launch command.

## Submission preparation after a completed chain

The tool, shared API projection and validation dependencies are local copies
finished before sealing. `submission-pins.json` binds their hashes to the
final build seal without a circular hash dependency. Never edit or reseal
after the chain starts. `seal.py` refuses once the registered output exists.

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/packet58_submission.py" --chain "$P/evidence/card0-58m-a" --output "$P/submission/card0-58m-a" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/submission_cli.py" --payloads "$P/submission/card0-58m-a/payload-queue.json" --dry-run < /dev/null
```

These commands prepare and inspect locally; they do not submit. The payload
discloses physical card0, host-pinned expert weights, the 18 GB cache, the port
levers, BF16 KV, no draft/MTP, and the distinction between whole-host admission
and timing eligibility. `specNumTokens` is omitted, not set to zero. The live
one-card threshold must be beaten; the existing record is not overwritten.

For the requested historical parser rehearsal:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/packet58_submission.py" --dry-run-existing-result experiments/own-xpu-runtime/stage2/packet58s-onecard-submission/submission/card0-58g-a-v3/result.json < /dev/null
```

This mode admits only that pinned old result, validates its captured chain,
and reports `submission_eligible=false`. Its historical threshold does not
weaken any check on the new port result.

## Retention and restoration

`build/` is ignored. `restore_build.py` copies and verifies the five original
58j/58k binaries; it never compiles or starts them. Original source paths and
hashes live in the copied compiler receipts and copy manifest. Completed
historical receipts are copied or pinned by exact identity. No changing parent
readiness, live queue, orchestration decision or submission threshold is a
build-seal input. The live threshold is checked separately at submission time.

No existing evidence was deleted. No new tracked file is 1 MiB or larger.
The build remains below 150 MB, and the chain retains its 8 GB disk floor and
2,952,790,016-byte planned output allowance. [CPU closeout](CPU-PREPARATION-CLOSEOUT.md),
[boundaries](DO-NOT-REPEAT.md), [work note](../../../../notes/2026-10-18-own-runtime-packet58m.md).
