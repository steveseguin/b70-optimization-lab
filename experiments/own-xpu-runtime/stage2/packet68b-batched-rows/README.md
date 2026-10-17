# Packet 68b: measure a shared-weight two-row half

Sealed for the coordinator. **No GPU or model ran during preparation.** GNU
and Intel host fixtures each pass **1,308 byte checks**, and both produce the
same expected/output bytes. The native device program compiles. Device row
identity, all thirteen packet49 requests, H(2)/H(1), and speed remain pending.

This packet copies packet64's sources. It does not edit packet68 or the other
frozen trees. Arithmetic remains `iq3-p49-split32-v1`, with full BF16 state/KV.
The selection is packet64 production draft, ordinary rollback, 24/24 layers.

Paired kernels share weight loads and decoded values, with separate ordered
FP32 accumulators and the original adjacent reductions and BF16 stores:

- Expanded Q6/Q8 and F32/BF16 dense projections: GDN qkv/z/a/b, QSA projections,
  attention output, PLE projections, shared expert, router, final HC and head.
- Target HC norm, low/inject and gate/mix, retaining their fused stages.
- Packed IQ2 gate/up and IQ4 down over the stable union of both route lists.
  A common expert's decoded weights feed both rows. Different routes use their
  own expert bytes; repeated and partial fixture routes retain their slots.
- Rounded attention/HC/shared-activation epilogues.

Other operations, including GDN recurrence, conv, QSA attention core, routing,
non-HC norms and any unsupported expert format, retain two serial production
submissions. Every sample lists the actual batched and serial classes. No
serial loop is labeled a shared-weight matrix pass.

At generated fixtures 8, 16 and 32, each rank captures three private images of
the real inputs and mutable state. One executes production M=1; two execute
the paired pass. Both paired outputs and every plan/spare-state buffer must
match the M=1 bytes on device. Original bindings are restored, and ordinary
generation resumes on the original state. No probe result is emitted. The
frozen screen checks incident64 and all twelve 128-token requests against
packet49. Rank0 corrections can produce extra samples at the same fixture.

H1/H2 replay order alternates. Logs include wall time, device span, summed
device time, per-class event time and copy time. Replay excludes preparation,
copying, input lookup and output publication; the analysis states this limit.
Duplicate independent rows are an optimistic route-overlap case, **not a
causal consecutive-position verifier**. This is diagnostic cost evidence,
never a headline speed test or full-chain qualification.

## Coordinator commands

From the repository root, inside the coordinator's admitted `screen-*` user
unit, using its reviewed fault receipt and existing library environment:

```bash
bash experiments/own-xpu-runtime/stage2/packet68b-batched-rows/coordinator_probe.sh "$FAULT_REVIEW"
```

`P49_LDP` must contain the coordinator-approved library path. The job uses
lane B, cards 2+3, and a 3,600-second watchdog (over 4× the estimated 5–8
minutes). No restart or retry is supplied. Its fresh output is
`stage2/screen/v3-packet64-lanes/evidence/packet68b-batched-B-01`.

The packet-local supervisor/worker bridge extends only the frozen wrapper's
placement admission to this audited 24/24 binary. All lane leases, chain
holds, fault checks, drain spacing, memory checks, unit policy, and oracle
checks still run through the frozen wrapper. 23/25 is too tight for the
private images. The memory ledger adds a checked 512 MiB ceiling per rank;
READY census includes these allocations. Private scratch is bounded by the
production write set with an 8 MiB floor; original allocations are unchanged.

After the window:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet68b-batched-rows/analyze_probe.py \
  experiments/own-xpu-runtime/stage2/screen/v3-packet64-lanes/evidence/packet68b-batched-B-01 \
  --output experiments/own-xpu-runtime/stage2/packet68b-batched-rows/evidence/device-analysis.json </dev/null
```

Add `--restore-summary PATH` for packet68's successful `analyze_probe.py`
output, if available. Missing restore cost stays explicit; zero restore is
only a sensitivity, never unconditional adoption approval. The helper
requires all thirteen exact receipts and sample coverage on both halves.
It reports ratios by half/class, a two-token pipeline projection with
`a1=.787`, `a2=.718`, both rejection cases and overlap sensitivity, the +8%
bar against 51.033041 tok/s, and the depth-one batched-redo cost. It does not
reuse packet66's blocking-verifier token reward.

## CPU rebuild and retention

Build serially with nice19, cores 8–15,24–31, OMP2, Python `-B`, stdin
`/dev/null`. `build_engine.py` enforces an 8 GiB address-space ceiling,
12 GiB free disk and a build below 1 GB. It refuses to overwrite a sealed
packet. Reproduction needs a fresh copy/output and preserved parent objects;
the build receipt pins every reused object and source, not a public portable
binary claim. Then run `cpu_gate.py` and `seal_and_plan.py`.

The inherited 4 MiB `rope.bf16` and four roughly 1.2 MB fixture byte files are
intentional retained artifacts. RoPE is a required pinned model constant;
fixture pairs retain expected/actual bytes under each compiler, including
nonfinite and invalid-route cases. Restore RoPE from the pinned packet64
source; regenerate fixtures with the sealed source and recorded compilers.
Build objects/caches stay ignored. The rejected initial plan and seal in
`evidence/unadmitted-*` document the output-root correction and are not usable
launch identities. No device was contacted by that rejected CPU plan.

[Task note](../../../../notes/2026-10-17-own-runtime-packet68b.md),
[CPU receipt](fixture/receipt.json), [admitted plan](evidence/probe-plan.json),
[seal](screen-seal.json).
