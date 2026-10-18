# Packet 98: one-load screen brackets (v5)

CPU prepared. No GPU, model load, service, or live queue ran during preparation.
V4, v3 and existing packets are unchanged. This is a copy of v4's wrapper plus
a native switch/reset command in a new binary. Parent kernel objects remain
byte-identical. `v4-copy-provenance.json` pins the copied files.

One bracket owns one lane lease and one TP2 rank pair (one native owner per card)
for its entire life. Target weights and draft load once. There is one shared
drain/teardown permit at the end, including failure paths. Memory admission and
fault review precede the lease. Prelaunch refusal releases its own marker;
unproven device teardown retains ownership as before. All original device masks,
memory fences, cooperative stop, fault postflight and shared drain spacing stay.
Reports run after the lease is released.

Each view switches only routing/recurrence kernels, resets state, checks 64
incident tokens, then runs the twelve packet49 prompts at 128 tokens. Every
request resets again and requires `cached_tokens=0`. No prompt/KV/response data
survives a view. These remain diagnostic screens; full chains still own records.

The native command rebuilds both recurrent-bank captures at a quiescent boundary.
Reset covers target/draft KV, recurrent and spare banks, speculative backup,
unused tails, scratch, FP32 cache, host histories, draft publication, pinned
staging and shared IPC/mailbox bytes. The wrapper clears shared IPC only after
both native acknowledgements. Failure in any view stops the bracket and drains
once. Locked target/draft weight uploads are rejected.

Loaded arena descriptor hashes include allocation ID, pointer, size, label,
category, memory kind and lifetime. Every view must keep both whole-arena and
weight-descriptor hashes unchanged. This proves storage identity, not a device
weight-content checksum; immutable upload guards and byte tests provide the
separate no-write check. The initial loader's weight identity checks are unchanged.
Head transpose, packed-head/dense layout changes, draft settings, dispatch,
placement, and all other unqualified switches refuse and require a reload/v4.
The first qualified family is packet84 control versus packet91 route-fast plus
rec-both-plus, in one binary based on packet82b's existing kernel closure.

## First device use, for the coordinator

1. `ops/lane-queue/proposed-p98-smoke-B.txt`: two packet84 production views (A/A),
   full incident64 plus twelve prompts each. Require exact output and no more
   than 3% difference between class-balanced rates, the preregistered control
   drift bound. This is the small first-use test; it is not skipped.
2. `ops/lane-queue/proposed-p98-bracket-B.txt`: control / candidate / control /
   candidate / control. The entry refuses until the smoke passes with the same
   wrapper and binary. Each of the five views needs all thirteen exact checks.

Both are proposals only; neither is installed in a live queue. Planning uses a
temporary copy of the queue tools and never reads the device journal or starts
services. The coordinator supplies the fresh review and device authorization.
Output paths are `evidence/p98-smoke-B` and `evidence/p98-bracket-B` here.
The 90-second gaps between separate jobs are not inserted between views; the
shared external teardown spacing remains in effect once at the end.

## Receipts and comparison

Per-request `receipt.json` and per-view `summary.json` preserve v4's schema and
metric definitions. Views live at `run/views/00-control`, `01-candidate`, etc.
The parent window contains their hashes and the single owner/drain proof.
`compare.py OUTPUT` is the adapter: it rechecks oracle tokens, timings, cache-zero,
incident64, finished hashes and lease/teardown proof. Its `checked_requests`
function is copied unchanged from packet91's v4 comparison helper. It explicitly
labels the shared process lifetime; it never forges five fresh-server windows.
`bracket-summary.json` reports each rate, all three controls, both candidate
results, control drift, and measured bracket wall time. Device savings stay null
until there is a measured matched v4 wall-time reference.

## CPU evidence and reproduction

Use `nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2`, `python3 -B`, and
stdin from `/dev/null`. Run each command separately from this directory:

- `bracket_config.py`: copy pinned selections and write the fixed manifests.
- `build_engine.py`: GNU host and Intel device compilation, serially under
  packet94's `compile_turn.py`; never executes the device binary.
- `full_shape.py`: real production startup/capture/draft/switch/reset with mock
  payloads and numerical device addresses; check memory admission on both ranks.
- `reset_gate.py`: poison all mutable bytes on the miniature CPU backend, reset,
  compare complete hashes and unchanged weight bytes, twice on each rank.
- `protocol_gate.py`: real CPU rank IPC; two fresh five-view brackets match the
  parent and v5 fresh-process token outputs.
- `seal_native.py`, then `cpu_seal.py` for the complete wrapper/mock suite.
- `cpu_seal.py --verify`, `seal_native.py --verify`, `queue_plan.py`.

Seal creation refuses an existing wrapper seal. A changed closure needs a new
recorded revision; preserve prior receipts. Reproduction retains the sealed
parent checked includes/objects at the paths in `evidence/build.json` and rebuilds
only the entry translation unit; restore/rebuild packet82b's exact dependencies
first if absent. No historical packet is modified by these commands.
Build artifacts are ignored and bounded to 1 GB; CPU processes to 8 GiB; root
free must stay at least 12 GB. No host memory/power/cache settings are changed.
Compact JSON and logs are retained in `evidence/` and `placement-validation/`.
Copied chain patches and old placement examples are historical provenance, not
v5 device-launch instructions.

[CPU closeout](CPU-PREPARATION-CLOSEOUT.md), [task note](../../../../../notes/2026-10-18-own-runtime-packet98.md).
