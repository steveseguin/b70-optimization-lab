# Packet71c: coherent standalone router for the depth-two screen

CPU-only repair copied from frozen packet71b. The candidate changes exactly one
dispatch value: `fusions.small.ffn` becomes `packet18`. That disables the four-way
router/shared-gate/shared-up tuple. The router can then use its existing M=2
implementation; shared projections use their unchanged standalone kernels.
Other epilogue selections remain intact. Target arithmetic stays
`iq3-p49-split32-v1`, with full 16-bit KV/state. Controls still use the untouched
packet64 `1-draft-hc-batch` selection and binary.

This is option (b): a dispatch-only repair costs less implementation and review
than adding another fused kernel. Device cost is unmeasured. The candidate
prepares 72 more target commands per rank (three per layer) than the control;
paired router work may offset part of that. No speed claim is made.

The real full-shape native setup passes on both ranks for smoke, candidate,
all-M1 diagnostic and both controls. The test preserves native argument parsing,
Engine construction, allocations, command preparation, draft setup, two row
banks and rank-0 future rows. It captures every M=2 site, including all 48
routers. Only payload loading and the device backend are mocked; no model runs.
The original packet71b dispatch must reproduce its router refusal. Actual
allocation censuses pass the existing memory admission checks. Each `--plan`
also imports the real worker in its closed launch environment and runs the
hash-bound startup mock for that view, so this refusal now fails on CPU.

GNU and Intel each pass 2,728 inherited operator checks plus 80 new full-shape
checks comparing grouped and standalone FFN outputs for both Q6 and Q8 shared
experts, two different rows and five input patterns. Expected/actual streams
agree across compilers. These are CPU operator/setup checks; full-model device
identity, determinism and speed await the coordinator's screen.

Proposed lane-B order: smoke, control, candidate, control repeat. Jobs are in
[proposed-p71c-B.txt](../../ops/lane-queue/proposed-p71c-B.txt); no live queue is
changed. Estimated durations remain 3/4/4/4 minutes with 3,600-second watchdogs.

```bash
OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet71c-depth2-engine/run_job.py smoke-B --plan </dev/null
```

The coordinator supplies its valid lane-B admission and fault review to the
same command without `--plan`, with `--fault-review REVIEW_PATH`, under its
usual screen unit. Run smoke once before the matched three quick screens.

Rebuild in an unsealed copy: `build_engine.py`, `batch_cpu_gate.py`,
`unfused_gate.py`, `metadata_gate.py` (save its JSON in
`evidence/metadata-gate.json`), `fullshape_gate.py`, then `seal_and_plan.py`.
Use the nice/affinity/OMP/stdin settings above; one compiler at a time.
The build reuses hash-checked parent objects. This remains an originating-host
experiment, not a publicly reproducible release.

[Full-shape gate](evidence/fullshape.json), [unfused byte gate](evidence/unfused.json),
[M2 byte gate](fixture/m2-receipt.json), [build](build-device-receipt.json),
[queue planning](evidence/lanequeue-plan.jsonl), [closeout](CPU-PREPARATION-CLOSEOUT.md),
[retention](RETENTION.md).
