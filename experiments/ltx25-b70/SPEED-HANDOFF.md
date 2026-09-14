# LTX exact-output latency campaign

User authorized speed optimization on September 13, 2026, while maintaining
lossless quality. Target is first usable clip ideally immediately, otherwise
within a few seconds. Preserve the native BF16, seed, resolution, frame count,
8+3 schedule and all four raw output tensors. Real-time throughput and time to
first usable clip are separate metrics; neither is established yet.

## Measurement and gate

`scripts/profile-clip.py` uses the existing WebSocket node events and records
node-start intervals, submitted graph, history, PID/boot/source/model identity.
These intervals are approximate wall times, not synchronized kernel timings.
The original cache-none server is used for controls. `scripts/compare-clip.py`
independently rehashes all four archives, checks strict deterministic flags,
finite values, sample rate, unique actual executions and history binding, then
requires every output byte to match. Intentional graph deltas are reviewed and
retained separately. No approximate cache or precision reduction is allowed.

## Initial findings

- `speed-control-01`: 58.283 s client wall; exact against original baseline.
  Transformer construction 12.155 s, encoder construction 5.620 s, negative
  encoding including device load 7.613 s, positive encoding 3.090 s. Sampler
  nodes including preparation/transfers totaled 21.052 s.
- `speed-lean-01`: 59.893 s; all four outputs exact, no demonstrated speed win.
  Removes unused CFG1 negative encoding and 25 PNG preview writes, while
  retaining raw tensors and MP4. First sampler time increased in this trial.
- Capturing native reference scenes `speed-oracle-marble` (seed17) and
  `speed-oracle-bird` (seed123) before changing startup behavior. Boat seed42
  remains the primary repeated timing fixture.

## Next bounded stages

1. Retain only the five loaded model components across separate requests;
   recompute text encoding, sampling and decoding every time. Measure first
   initialization separately from resident operation.
2. Place text encoder on XPU2 and VAEs on XPU3 using stock constructors.
   Leave the transformer on XPU0 with its normal offload for a placement screen.
3. Split the exact existing transformer block objects across XPU0/XPU1 through
   normal ModelPatcher ownership and LTX block replacement hooks. Existing
   numerical block implementation remains unchanged; only ownership and
   transfers change. Require CPU ownership/routing tests before any GPU trial.
4. Promote only candidates matching boat/marble/bird references and repeated
   boat outputs, with measured end-to-end and first-output times. Preserve
   mismatches, timing losses, startup cost and all unsupported assumptions.

## Server constraint

The running baseline server (PID11499) cannot load a new extension or change
cache strategy through a supported live API. Its `--cache-none` disables both
loader and result caches. After completing the reference captures and reviewing
the extension, one planned graceful process migration is needed to install the
resident loader and device-routing experiments. All subsequent variants will
use that one new process. No server retry/restart policy, power changes, swap
changes, page-cache drops, driver reset or reboot is permitted. Any device fault
halts new requests. Existing baseline evidence remains unchanged.

New startup path: `scripts/serve-speed.py`; run identity and startup evidence
will be written under the original evidence root's `speed-server/` directory.
The original `scripts/serve.py` and baseline receipts remain frozen. The capture
gate and fault latch remain shared with the original evidence root.
