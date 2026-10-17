# Packet64 in-engine attribution — October 17, 2026

The CPU preparation is complete. The new selection copies packet64's current
engine and adds packet57-style event recording. Default placement is **24/24**,
with the production draft on rank 1 and ordinary rollback copies. The target
arithmetic and packet49 oracle are unchanged. No GPU, service, model-weight
read, host-setting change or reboot ran during this work.

The coordinator can run it on cards **2+3** using the separate `screen/v3-attr`
wrapper. This copies the lane-aware companion so a concurrent packet64 chain
can retain cards 0+1 during exactness work and reserve the whole host for speed
windows. All three frozen packet64 trees and packet61x were left untouched.

## What it measures

A single model load checks incident64, runs all twelve 128-token control
requests without event recording, then all twelve with recording. Mutable
state resets between every request, and every target token must equal packet49.
The same binary and numerical kernels serve both arms. The observation flag
uses the otherwise-unused RESET token field; a one-load CPU test checks
control → attribution → control without changing any target fixture.

Generated indices 9–16 record the full draft, transfers, and target layers
22/23 on rank 0 and 24/27 on rank 1. These give GDN and QSA on each rank for
24/24. Two additional endpoint sites delimit each complete target-layer span.
Subtracting that same-card device duration from its host half-command duration
gives the outside-layer remainder. Cancelled/incomplete halves are excluded;
negative remainders stay visible. This is not a GPU-idle measurement.

The JSON and Markdown reports contain per-class microseconds per layer type
and rank, rank-half times and finish balance, outside-layer time, draft costs,
and a ranked lever table. Raw measured costs remain separate from estimates
scaled by the control/instrumented cycle ratio (draft uses its wall ratio).
Class totals projected from 18 GDN + 6 QSA per half are estimates; fused kernels
retain their surviving launch labels. No speed result is claimed or submitted.

The planned work is about **10 minutes**, with one load and two suites. It is
an estimate, not a device timing, and excludes admission and chain-hold waits.
The extra suite adds roughly three minutes to the existing screen budget;
actual duration and live overlap remain for the coordinator to check.

## CPU evidence

- Four fresh host-only runs: packet64, new control, and two new instrumented
  runs. Each has **96 identical target fixtures and 24 identical target tokens**;
  draft proposals and saved draft state also match.
- Three more requests on one loaded host-only pair, switching control →
  attribution → control: all 96 fixtures and 24 tokens match again.
- **90 wrapper tests and five attribution tests pass.** Tests cover sample
  bounds, event identity/durations, missing classes, paired control scheduling,
  reset flags, duplicate/missing input refusal, and lane-B planning without
  launch or journal access.
- Both host and device builds pass. Only the engine entry translation unit is
  rebuilt; inherited arithmetic objects are unchanged hardlinks. The final
  compiler's peak child RSS is **726,524 KiB**, below the 8 GB limit.
- The final selection seal, wrapper seal and **lane-B `--plan` pass**. The owned
  tree occupied about **128.4 MB**, counting hardlinks once, before final prose.

Final device binary SHA256:
`ea35d7d5f16ddaf00989f7e5b5af0cc8b892d082fa3d7c6b70d15a73c52b00eb`.
Selection seal SHA256:
`fa85134f5f03acc540d22b2bd5da090ed99543899efb5eb214fe195ca0a14bcf`.

[Coordinator commands](../experiments/own-xpu-runtime/stage2/packet64-attribution/WINDOW.md),
[validation](../experiments/own-xpu-runtime/stage2/packet64-attribution/cpu-validation.json),
[seal](../experiments/own-xpu-runtime/stage2/packet64-attribution/selections/1-production-control/screen-seal.json),
[lane-B plan](../experiments/own-xpu-runtime/stage2/packet64-attribution/evidence/plan-B.json),
[closeout](../experiments/own-xpu-runtime/stage2/packet64-attribution/CPU-PREPARATION-CLOSEOUT.md).

All CPU programs used nice19, cores 8–15,24–31, Python `-B`, OMP2 where needed,
and stdin from `/dev/null`. Device execution and measured costs remain pending.
`CURRENT.md` and every existing runtime tree were preserved, as requested;
this task's state and handoff live only in the new folders and this note.

## Device result (coordinator, 2026-10-17 17:48–17:55 UTC, lane B cards 2+3)

The screen `v3-attr/evidence/packet64-attribution-B-a` ran on the device for 397 s with no new fault lines (count 2). The report step refused with `invalid event timestamps`. 1,696 of 21,196 events were small copies (`transfer.*`, `draft.transfer.*`) whose device start and end timestamps were equal at timer resolution. They had zero duration; the data was not corrupt. The validator required `start < end`. It now allows `start == end` only for transfer events (coordinator fix in `summarize.py`); the report was regenerated on CPU from the retained raw evidence.

Current line (packet 64 production 24/24, placement 1), per card-half, control means:
- rank 0 speculative 14.23 ms;
- rank 0 corrected 12.99 ms;
- rank 1 target 14.69 ms.

Rank 1 is still the bottleneck, by about 0.45 ms.

Largest buckets per half (estimates, 18 GDN + 6 QSA layers):

| Bucket | Cost per half |
|---|---|
| GDN attention | 3.55 ms (197 µs/layer) |
| GDN routed experts | 3.35 ms (186 µs/layer) |
| Outside layers | 2.94 ms (rank 1) / 2.24 ms (rank 0 speculative) |
| GDN HC norm/merge | 1.53 ms (85 µs/layer) |
| QSA attention | 1.28 ms (213 µs/layer) |
| QSA routed experts | 1.11 ms |
| QSA HC norm/merge | 0.51 ms |

The draft on rank 1:

| Draft part | Cost |
|---|---|
| Head prefix | 510 µs |
| Attention | 380 µs |
| HC norm/merge | 330 µs |
| Experts | 246 µs |
| Embedding | 60 µs |
| Shared expert | 43 µs |
| Argmax | 21 µs |

**Implied lever order:**
1. GDN attention (the largest single class);
2. routed experts (packet 65 in flight);
3. the outside-layer remainder, especially on rank 1 (unexplained 2.9 ms);
4. HC norm/merge;
5. draft attention and HC.
