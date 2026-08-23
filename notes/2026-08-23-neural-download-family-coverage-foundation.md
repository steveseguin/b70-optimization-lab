# 2026-08-23 — neural.download family-coverage foundation

## Goal

Make website completeness mean family-level coverage rather than more isolated
decode rows. A useful cell is measured, screened, estimated with a versioned
engine, closed by a recorded gate, quarantined, unsupported, or explicitly
missing. Quantized artifacts are variants of a model revision, not separate
models, and decode is one metric beside prefill, TTFT, active context,
acceptance, memory, quality evidence, model interest, and packet maturity.

## Qwen deep-coverage slice

`families/qwen-27b.json` now treats Qwen3.6 27B and Qwen3.8 27B as two weight
revisions with the same pinned AutoRound tensor geometry. Shape-dependent
implementation work may transfer; weights, hashes, prompts, outputs, quality,
acceptance, determinism, and measured speed do not.

The generated `models/qwen-27b.html` contains:

- separate strict and diagnostic TP1/2/4 graph views, retaining the diagnostic
  `30.2178–30.2569 / 48.8301–48.9505 / 71.5488–71.6741 tok/s` values and the
  strict natural-EOS `30.310675 / 49.019651 / 71.293263–71.398430` values;
- a current-nightly TP × MTP0–3 decision map with TP3 unsupported, MTP2 TP2
  labeled as boot/canary-only, graph+MTP quarantined, and every cell linked to
  evidence;
- scoped e4m3 quality and e5m2 support closures, which account for the other
  two KV slabs in the 96-cell bounded nightly matrix;
- separate Qwen3.6 MTP1–4 and older Qwen3.8 TP2/MTP5 research views so runtime
  families are not merged;
- measured Qwen3.8 Q4 F16/Q8-KV and weight-quant curves through active 32K,
  the Q5 flagship Q8-KV curve through active 32K, and Qwen3.6 Q8 target/MTP3
  long-context support points;
- distinct B70 fit, current-Qwen3.8 deployment-quality evidence, dated-interest
status, evidence count, stored estimates, live projected OPT grade, and
packet maturity signals.

The preregistered nightly matrix covered MTP0–3. MTP4 is therefore not inferred
as a nightly closure or blank; it remains represented by separately scoped
Qwen3.6 evidence and by the family-wide dimension.

## Site-wide family assignment

Every one of the 13 published packages is now assigned to exactly one of eight
family manifests: Gemma 4, Laguna S, LFM2.5, MiniMax M2.7, Muse-Glimmer,
Nemotron 3.5, Ornith 1.5, and Qwen 27B. The non-Qwen pages expose existing
context, prefill, TTFT, topology, speculation, acceptance, quality, and
historical evidence where it exists, with missing axes left explicit rather
than estimated. Ornith's dense 9B and MoE 35B-A3B artifacts remain
architecture-distinct siblings inside the publisher release line.

The family generator fails if a public package has no family, belongs to more
than one family, or its family packet ID disagrees with its package manifest.
Research-only and superseded packets can remain visible without pretending to
be promoted packages.

## Packet promoted from existing evidence

The previously hidden Qwen3.8 Q4_K_M TP2 result is now a candidate packet at
exactly `49.71750333219927 tok/s`, `173.574 ms` TTFT, 12/12 exact output hashes,
and cache zero. No benchmark was rerun. Its preflight checks B70 device IDs,
source ancestry and patch markers, decoded patch hashes, the direct model hash,
and exact evidence-binary hashes by default. Rebuilt binaries require an
explicit override and then the full output oracle.

The headline launcher pins `GGML_SYCL_MMVQ_SG32=0` and clears the optional
prefill reorder flags unless `QWEN38_PREFILL_MODE=1`. This prevents a caller's
shell from silently applying the measured `-0.28%` decode tradeoff to a later
headline run.

## Projection boundary

The Q5 256K/vision/MTP packet still shows its measured `26.668277 tok/s`, but
its ML Bottleneck projection is intentionally omitted: the packet does not
encode the draft depth, and the former `mtp:3` mapping was an unsupported
inference. The Q8 TP2 packet likewise retains its measured `36.772932 tok/s`
while omitting a projection whose reasoning/workload identity does not match
the packet launcher. Live OPT grades remain labeled projections and do not
count as stored gap estimates, model quality, or packet evidence.

## Verification

- eight family pages generate and pass the drift check;
- 24 reproduction guides validate;
- 13 package pages and the models index regenerate from source;
- 9 unit tests and 11 claims pass;
- JavaScript and packet shell syntax pass;
- 34 public HTML pages have valid local links and no duplicate IDs;
- no pre-existing package featured metric changed.

## Remaining coverage work

1. Deepen non-Qwen combination coverage where existing ledgers can classify
   TP, speculation, context, graph, KV, memory, and power cells without new
   runs.
2. Store dated official/derived-repository popularity snapshots; unavailable
   is not zero and popularity never substitutes for quality evidence.
3. Materialize typed estimates only after pinning engine version, evidence
   snapshot, input identity, and uncertainty. Estimates must never close a
   packet gate or join a measured curve.
4. Promote more already-measured blanks into lower-maturity packets before
   burning GPUs, especially missing prefill, TTFT, VRAM, power, and active
   context fields.
5. Treat the Qwen nightly target-only TP1/2/4 graph lane as the completed TP4
   coverage anchor. Do not lower or replace the `71.7` diagnostic ceiling;
   retain the unsupported/experimental graph and cross-boot disclosures.
