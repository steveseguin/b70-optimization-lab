# Packet174: one-card maintenance fill kick

CPU preparation only. No GPU, service, setting or live queue was touched.
Parent: a private `git archive` copy of packet58as at committed HEAD
`244c77853d01` (native sources identical to `dabfc958b`); see
`lineage/packet174-copy.json`.

## Why

On the spin line (28.80 ms/token, 34.573 tok/s), the 8-byte token/error
readback is slow **only on the token whose position-start boundary submitted
maintenance fills**, and its excess is linear in that token's fill bytes:
0.0350 ms/MB with ~0 intercept (packet58as v5 and packet171b v5, every spin
view; `evidence/analyzer-real-parent.json`). The whole fill (about 61 MB per
fill token, 30.63 MB per generated token) therefore drains at ~28.6 GB/s after
compute and before the readback completes, even though it was submitted ~27 ms
earlier, before any kernel. Nothing overlaps. Measured cost: 1.07 ms/token
(3.7%). Packet171b's readout counted the publication token as the fill token;
see `notes/2026-10-19-own-runtime-packet174.md`.

## Change (B arm, `--fill-kick on`)

- After a non-empty fill batch is submitted (and its ticket is owned) at the
  drained position boundary, the owner calls
  `zeCommandListHostSynchronize(maintenance list, 0)` once: a non-blocking
  query that asks the driver to hand the queued fills to the copy engine now.
  It never waits.
- Unchanged: which experts are planned, filled, evicted and published, and at
  which boundary (publication still needs a completed fill at a later drained
  boundary), every kernel and arithmetic, selection, spin policy, resident
  lookups and foreground copies. Tables per position are identical in A and B.
- Host-only readout additions in `cache.jsonl`: `fill_kicks_total`,
  `route_hits_total`, `routes_total` (routed IDs served by published device
  pointers).
- `apply_fillkick_delta.py` is the exact delta; `native-delta.patch` its diff.

## Interface

- Process-wide `--fill-kick off|on`, default `off` (packet58as behaviour),
  listed in `--help`. Accepted with every engine chain window argv (KD, W2m,
  WS, WS128x, WS128); K1a/K1b run the unchanged fixture binary.
- The five-view bracket sets the same `p174::fill_kick` switch per view at the
  drained view boundary (A = `spin`, B = `spin-kick`). Supplying
  `--fill-kick` together with a bracket table is refused.

## Device contract (proposal only; not queued)

- Lane A, whole host, one load: K1a/K1b, then v5 A0/B0/A1/B1/A2,
  12 x 128-token requests per view. No separate smoke.
- Gate: both B views >= +0.5% over every warm A, warm drift <= 3%, 60/60 exact
  vs `iq3-p49-split32-v1`.
- Mechanism readout kept on every outcome (`summary.json` ->
  `mechanism_readout`): slow-readback fraction, readback ms per same-token
  fill MB, fill MB per token, decode hit rate, kicks.
- Proposal: `../../ops/lane-queue/proposed-p174-v5-A.txt` (job `packet174-v5-A`).

## Pricing

`pricing/candidates.json` (labels: measured / transferred / assumed) and the
admission replay `pricing/replay-admission.json`.

## CPU gates (all pass; READY-FOR-DEVICE.json written last)

| Gate | Evidence |
| --- | --- |
| One `ops/compile_turn.py` turn: GNU host, device, Intel host, wait tests, K1 help, preparation probe | `evidence/build.json` (the probe binary from that turn is reused by `preparation_gate.py` after a missing-symlink resume, `probe_reused_from_single_compile_turn`) |
| GNU/Intel byte gates: 120 request resets and 10 view resets byte-equal to packet58aj; oracle refusal; parent poll/spin order refused | `evidence/cpu-exactness.json` |
| `--fill-kick`: on/off/default byte-equal (GNU+Intel); parsed in KD/W2m/WS/WS128x/WS128 argv; the parent binary refuses it (fails on old code); bracket/draft/old-order refusals | `evidence/fill-kick.json` |
| Source-delta test: passes here, fails on the parent source; fill/copy bodies and cache policy untouched | `evidence/fillkick-delta-test.json` |
| Real device-define CPU preparation: 5 view resets, 60 request resets | `evidence/preparation.json` |
| Analyzer on real packet58as and packet171b brackets: old identity refused; readout reproduces the same-token fill-byte law | `evidence/analyzer-real-parent.json` |
| Every native flag in `--help`; queue-runner argument replay | `evidence/flags.json`, `screen/evidence/argument-gate.json` |
| Imports under the closed launch env; temporary `lanequeue plan`; `rehearse_entry --report` (WARN: no shared preparation adapter for an unranked one-card argv); pin guard | `evidence/entry-imports.json`, `evidence/queue-plans.json`, `evidence/shared-entry-report-final.json`, `evidence/pin-guard.json` |

The inherited Python unit suite (`run_cpu_gates.py`) is not a READY input: like packet171b, the record-chain modules it imports were removed.
