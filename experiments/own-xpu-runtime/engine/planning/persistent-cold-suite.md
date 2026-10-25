# One resident pipeline, twelve cold requests

The next benchmark loads each stage once, clears request state between prompts,
and keeps weights, allocations and runtime caches resident. It does not launch
one process set per prompt, reuse a prompt/KV prefix, train a draft, or restart a
service. “Cold” means uncached request state; it does not mean cold disk/page,
compiler or immutable weight caches.

The isolated implementation is `tools/persistent_live_suite.py`, with CPU fake
workers in `tools/test_persistent_live_suite.py`. The explicit
`tools/persistent_wavefront_driver.py` CLI validates the pinned suite, derives
reset capability from the pinned native receipt, and defaults to CPU planning.
This benchmark CLI currently inherits the lab live-plan adapter; it is separate
from the portable deployment controller. An outer admitted `wavefront_driver.execute` owns process creation, passive
monitoring, cooperative fault shutdown and final exit. The suite callback reuses
the exact `LiveStage` objects and `live_wavefront_driver.drive` implementation.
It refuses before changing any worker unless both capability and sequence hook
are explicitly available. Current successful one-shot runs do not prove reset.

## Native boundary contract

The opt-in is `--pipeline-persistent-requests` and the build receipt must contain
`pipeline/request_reset.hpp`. The admitted plan must carry
`persistent_reset_protocol: "ownrt.pipeline-reset.v1"` and the source capability
hash. `enable_reset_plan` derives these from the already pinned build receipt and
adds the opt-in to each live-stage argv; `run_suite` checks both. These are required in
addition to existing live-draft/wavefront admission; a plan string alone is not
proof that a binary implements reset.

All stages must have no queued wire bytes, unread partial reply or pending
command. The native side independently requires no candidate, active checkpoint,
pending target ledger ticket, provider submission or sticky error. A failed reset
halts the process set; it never falls back to process relaunch or a warm prefix.

For stage `i`, the controller writes the next global wire command's metadata at
its **original** `stageN/native/reset-<sequence>.txt`. The two lines are an
absolute fresh destination and an empty oracle path. The destination is strictly
beneath the original native output: `requests/request-00-<prompt-id>`. Controller
schedule/token/result logs remain in the outer run's `request-00-<prompt-id>`.
The metadata location does not move when `Engine::a.output` changes.

RESET is operation 11, with token/position/fixture/speculative all zero and the
existing stage/final identity. The successful reply has token and stream bytes
zero. Global request/reply wire sequence never resets. Before starting work the
controller checks destination `wavefront-reset.json`:

- schema `ownrt.pipeline-reset.v1`, passed true, stage ID and global sequence;
- target position zero; draft position zero on first stage, null elsewhere;
- pending ticket false, sticky error zero, allocation IDs preserved;
- both context extents 32; counters and trace reset true.

Native reset must clear both target banks, provider mutable and pinned transport
state, shared handoff/header/reverse/publication state and stale host metadata.
It must restore canonical bank ownership and both attention extents, reset the
wavefront ledger and live-draft sequence, and reopen per-request traces. Preserve
weights and allocation identities. The existing generic reset zeroes wavefront
copy tables, so the native checkpoint must rebuild/re-upload its checked capture
and restore descriptors before the next speculative operation. A fresh stage
layout/checkpoint sidecar in each destination enables state comparison.

## Python wire sequence contract

`live_wavefront_driver.drive` now accepts `initial_sequences`. Immediately after
creating the fresh `Wavefront`, it checks these seeds against the actual
`LiveStage.sequence` values and seeds each scheduler before issuing commands. `seed_model_sequences` validates a genuinely unused
scheduler and every bounded integer seed atomically. The next scheduled command
must be exactly current sequence + 1. Target row positions, row counters,
known-prefix map and canonical draft sequence start fresh at every request.

Do not overwrite a live module's globals or restart Stage objects to accomplish
this. The isolated harness checks the callback signature and refuses a driver
without the explicit hook. Each request resets every stage, captures the new wire
seeds, invokes the same drive function, and rejects leftover pending wire state.
A reset or output mismatch preserves partial evidence and ends the suite.

## Timing and qualification

The baseline is the retained `review-2026-10-25/normal-service-suite.json`:
12 uncached requests, 5,965 generated IDs, max 512, target F32. Its conventional
median service decode rate is about 47.97 tokens/s. The source suite, service
plan and local model-identity hashes accompany the derived prompt/ID fixture.
The historical text-output hash is retained as provenance, not relabeled as a
token hash. New token hashes are SHA256 of consecutive unsigned little-endian
32-bit IDs; exact ID lists must also match.

Report these separately for each prompt:

- TTFT: first committed output timestamp minus prompt-drive start;
- decode: `(N-1)/(last committed output timestamp - first timestamp)`, only when
  N is at least two and the interval is positive;
- full response: drive completion minus start, including prompt and final draft
  drain, plus `N/full_response_seconds`;
- reset maintenance time outside those intervals.

The baseline `customer-email` ends at 333 outputs with token 248046. Existing
one-shot live plans stop only at 248044. The live scheduler now accepts an
explicit EOS set; the full-suite configuration must admit both profile IDs. The harness rejects an early-stop
reference whose terminal token is absent from the admitted EOS set; it must not
force an artificial 333-token cap to hide this protocol difference.

The controller's output-commit timing and the service's native output timing are
different timestamp sources. Both use the full generated interval numerator,
but topology, prefill, logging, restore diagnostics and controller overhead must
be recorded before interpreting a comparison. The harness labels observations
uncertified, computes the conventional median, and never promotes a speed claim.
State dumps are optional per prompt and always outside measured response time.
For the first two-request reset qualification, dump each final state and compare
against matching independent cold request references. For the twelve-prompt
measurement, use the already-qualified reset path, preserve exact outputs and
one final outer-lifecycle dump; do not create twelve process startup chains.

CPU validation:

```bash
python3 -m unittest discover \
  -s experiments/own-xpu-runtime/engine/tools \
  -p 'test_persistent_live_suite.py'
```
