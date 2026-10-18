# Packet58r: one-card, one-load kernel bracket

CPU preparation for the tile16 line. No GPU result or speed gain is claimed.
The unchanged model is the **Unsloth UD-IQ3_XXS quantized compressed version**
bound to packet49's `iq3-p49-split32-v1` oracle. Target-only decode, full BF16
KV, context 4096, all 48 layers, 48,627,712,000 pinned expert bytes and the
18,000,000,000-byte device expert cache remain fixed.

The native entry is a new copy of packet58j's checked engine (the binary base
used by 58n and 58p). Its quiescent selection switch is adapted from frozen
packet98c. All linked kernel objects are reused by exact hash. No parent,
screen, existing ops file or live queue is modified.

| View | Route | Recurrence | Down layout |
| --- | --- | --- | --- |
| `tile16` (A) | route-exp32-rank4 | rows4-shared | down-tile16 |
| `route-fast` | route-fast | rows4-shared | down-tile16 |
| `rec-both-plus` | route-exp32-rank4 | rec-both-plus | down-tile16 |
| `route-rec` (proposed B) | route-fast | rec-both-plus | down-tile16 |

HC remains production. **Other-fusion is unavailable** in this one-card
engine: packet109's fused router/shared-activation and shared-down/blend
dispatch are absent. The parser refuses an other-fusion option; this packet
does not silently call an unfused path “fused.” Porting those kernels is a
separate source change and qualification, not an in-process selection here.

## One owner, one load

Two fresh, bounded K1 fixtures select the unchanged zero-copy/streamed miss
policy. The engine then loads once and runs **A0/B0/A1/B1/A2**, twelve fixed
prompts at 128 tokens per view (60 requests). No native child is restarted
between views. The table and all five selection hashes are checked before
model construction. Each switch drains work, validates the restricted domains,
clears captured commands/specs/matrices, returns context extent to 32, and
recaptures the selected kernels. Allocation IDs, addresses, extents, pinned
expert handles and weight layouts must stay unchanged.

Every request resets KV, recurrence, scratch and host histories using the
one-card engine's existing reset. Every generated token is compared immediately
with the packet49 expected sequence; a mismatch or wrong completion length
stops before the next view. The Python consumer independently rechecks every
token, reset receipt, selection, timestamps and the single-owner teardown.

The immutable **weight cache** persists, including its normal expert fills and
evictions. It is distinct from prompt/KV/response caching, which is forbidden.
Each boundary records the cumulative cache-fill bytes and zero weight uploads
**during the switch**, not zero cache traffic during generation. Descriptor
hashes prove storage identity, not weight-content hashes. This repeated-prompt,
one-load screen cannot replace a fresh-process quality repeat or the strict
512-token final performance gate.

Both B repeats must beat **every** control by at least 0.5%; maximum control
drift is 3%. Rates use the median of class medians over 99 intervals between
generated timestamps 1 and 100. TTFT, p10, means, wall rates, cap-limited/natural
completion rates and prompt/output hashes remain in each view's summary.
A completed exact loss is retained and does not retry or start a record chain.

## Coordinator handoff

Only [proposed-p58r-v5-A.txt](../../ops/lane-queue/proposed-p58r-v5-A.txt) is
proposed. It uses physical card 0, lane A, with **whole-host exclusion**.
The coordinator schedules one gap and keeps lane B paused and drained,
including the two internal 90-second gaps. No service or queue is started by
CPU preparation. A new fault review is required at launch; the inherited
newest-kernel-line-minus-two-seconds boundary is retained.

Expected duration: **20–30 minutes** including K1 and gaps, excluding admission
waits. This is a planning estimate, not a measured speed or kill deadline.
Native and model-window watchdogs are **7,200 seconds**, at least four times
the 30-minute upper estimate. Stops are cooperative; there is no retry loop.

| Admission item | Bytes |
| --- | ---: |
| Required whole-host MemAvailable | 118,308,908,048 |
| Host bound excluding reserve | 109,718,973,456 |
| Host reserve | 8,589,934,592 |
| Device/backing bound | 26,409,219,600 |
| Immutable expert cache | 18,000,000,000 |

The bounded K1 admission is separate. The lower exactness-only memory floor
cannot admit this timing screen. Post-load census, pinned-allocation progress,
GPUActive accounting, all-card foreign-client checks and the shared drain
permit remain active. The copied drain gate includes the nonnegative sleep fix.

The unchanged `common-teardown/v1` helper is wired through
`owner_teardown.py` before result reporting. It requires a reaped driver and
observed native descendants, a complete single-owner native drain, a clean
supervisor/journal and the existing client/lane checks. It can release this
owner after a reporting or post-compute error while keeping the experiment
failed. No fault latch, stale marker or foreign owner is recovered. The generic
scanner reports `NOT_VERIFIED` because this is neither its chain nor v4 template;
the retained local integration regressions test this actual one-card adapter.

## CPU reproduction

This is an originating-host lab packet, not a portable published recipe. Keep
the frozen packet58j checked headers and kernel objects, packet94 compiler
admission and packet49 oracle files available. No large model payload is read
by these gates. All native compilation is serialized by packet94's
`compile_turn.py`; device compilation never executes the device binary.

From the repo root, prefix every Python command below with
`nice -n 19 taskset -c 8-15,24-31 python3 -B` and redirect stdin from `/dev/null`:

1. `stage2/packet58r-onecard-v5/build_engine.py` (under `experiments/own-xpu-runtime/`).
2. `cpu_gates.py bytes`, `cpu_gates.py fullshape`, `cpu_gates.py reset`.
3. `startup_gate.py`, `run_cpu_gates.py`, `argument_gate.py`.
4. Commit the checked sources, then `seal.py`, `seal.py --verify`, `plan_queue.py`.

Run scripts 2–4 from the same packet directory or use their full repo paths.
Build and ordinary native fixture processes use an 8 GiB AS cap, installed
only by their CPU CLI. Full-size mocks reserve sparse production virtual
arenas without touching model data; they and intercepted argument tests must
remain uncapped in AS. Their actual peak RSS is checked below 8 GiB. Runtime
imports never install caps; each real Python-to-native launch refuses finite
AS limits or a changed inherited resource limit.

Root free space must stay at least 25 GB; the build is capped at 200 MB.
Generated binaries/objects are ignored; [build evidence](evidence/build.json)
pins actual compiler include dependencies and reused objects. CPU gates are
sealed independently of mutable coordinator output. Never reseal after a
bracket output directory exists.

[Work note](../../../../notes/2026-10-18-own-runtime-packet58r.md),
[CPU closeout](CPU-PREPARATION-CLOSEOUT.md), [boundaries](DO-NOT-REPEAT.md).
