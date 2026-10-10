# Stage 1 — one-card Qwen3.8 27B decode core

This is a work plan. Stage 0 ends with owner review; no native implementation,
compilation, launch or weight acquisition is authorized by this document.
The current host halt remains in force. CPU packets can prepare contracts and
fixtures without touching GPUs or the existing lanes.

## Target, available weights and authority

Start with **official `Qwen/Qwen3.8-27B-FP8` revision
`017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`**, unchanged 128×128 block FP8
weights, certified W8A16 arithmetic, FP16 activation/KV profile and FP32 GDN
state. It is dense, not MoE: 64 layers, 48 GDN and 16 full attention layers,
hidden 5120, FFN 17408, one native MTP block. Exact config is in
[data/qwen27-official-config.json](data/qwen27-official-config.json), with
[official metadata provenance](data/qwen27-config-receipt.json).

Neither 27B FP8 nor AutoRound INT4 is present under this four-card host's
`/mnt/fast-ai/llm-models`. [STORAGE](STORAGE.md) records the directory census.
Existing recipes on the other host are not evidence that weights are local.
The [FP8 manifest](../../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/model-direct.json)
and [one-card package](../../packages/qwen38-27b-fp8-tp1-b70/package.json)
provide the identity for a later approved transfer/download. The package's
weight-byte total is 30,866,866,928; admission must include staging and the
free-space reserve, not only that file total.

The historical AutoRound checkpoint is `devan-carlin/Qwen3.8-27B-int4-AutoRound`,
outside the new allowed sources. It is not selected for this plan. An INT4
extension needs an allowed official/Unsloth release, our own quantization from
official bytes with full provenance, or an owner exception. It will have its
own quality authority and cannot inherit FP8's lossless label.

The exact no-MTP output oracle is
[tp1-mtp0-b896-strict-performance.json](../qwen38-27b-b70/data/2026-09-17-fp8-ckpt2/tp1-mtp0-b896-strict-performance.json),
SHA256 `1ee5743c99c1c0057a9dd19ee5d452e48dd282cca893942b7e2c9e2339998283`.
It contains the 12 full `token_ids` arrays and text. Original host-local path:
`/mnt/fast-ai/bench-results/fp8-ckpt2-20260917/tp1-mtp0-b896-strict/performance.json`.
Use the tracked copy; do not rely on that absolute path existing here.

The fixed input suite is
[realistic-suite-v1.json](../../repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json),
SHA256 `df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac`.
Its historical folder name does not change the FP8 harness's use of it.
The [October accepted run](../qwen38-27b-b70/data/2026-10-04-fp8-onecard-chunked-upload/tp1-pkg-32k-strict-performance.json)
and associated second run, identity, canaries and `strict-vs-reference` artifacts
establish the current package check: **54.03648366755944 tok/s** class-balanced
median of two suites on one server at 32,768 capacity, MTP5, target-verified
draft-only INT4 shortlist. This is a within-server repeat, not a fresh-server pair.
The retained [September promotion attestation](../qwen38-27b-b70/data/2026-09-18-fp8-tp1-mtp5-r312d-32k-promotion-attestation.json)
pins the fresh-server frontier at **54.223911840596784 tok/s**
(54.21161759197449 and 54.23620608921908). Keep this higher certified frontier;
diff its launcher/upload/host identity against October and new matched controls.
That draft does not change target weights. A no-draft-quantization variant is
a distinct comparison profile. Do not compare a target-only prototype to a
speculative headline as if its gate were already complete.

## Kernel budget and ordering

The [27B measured profile](../qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md)
is the first budget: 318 W8A16 launches, about 53 ms per step, 25.2 GiB streamed
at approximately 507 GB/s; 1.3 ms GDN, 0.2 ms attention, about 1.5 ms fused
norm/activation work; 74% device busy and 26% gaps in a 78 ms profiled step.
It is a diagnostic at its recorded shapes, not a new speed run or a sum that
predicts the current package rate. The historical LTX 537 GB/s copy/weight-streaming reference
and 9B draft-head 586 GB/s versus 573 GB/s copy result are cross-model context
only; [INVENTORY](INVENTORY.md) links their receipts and caveats.

For every production shape, packet 2 will record actual bytes moved `B`,
operations `F`, launch count and measured time `t`. The planning bandwidth
floor is `B / 507e9` seconds for comparable 27B streaming work. It is a target
derived from the saved measurement, not an achieved kernel time. A compute
floor `F / measured_exact_math_rate` remains **unmeasured** until a matching
native census; no advertised peak FLOPS is substituted. Cache reuse, repeated
KV reads, scales and scratch traffic belong in `B`. Achieving a floor is not
required if fixed arithmetic makes it unattainable; preserve that evidence.

| Kernel or operation | First target / roofline budget | Identity requirement |
| --- | --- | --- |
| FP8 block dequant + M=1/M=2/M=6 GEMV/GEMM: dense gate/up/down and attention projections | Retain current exact oneDNN path initially. Aim at the 507 GB/s measured family budget; only replace a census-proven gap. One 17408×5120 FP8 matrix plus one F32 scale per 128×128 block is 89,150,720 B, giving a **derived 0.176 ms** streaming floor before input/output/scratch traffic, not a measurement. | Fixed K order, casts, scale application, padding and all production shapes exact. |
| Embedding gather | Copy the actual selected rows once; bandwidth floor uses measured source path, currently unmeasured for device-indexed UVA. Count full resident table cost, not row size, for admission. | Exact bytes for sampled IDs; no host callback within replay. |
| GDN conv, gates, normalization, recurrence and output projection | Preserve the measured aggregate ~1.3 ms/step budget at the old profile; per-kernel bandwidth/compute targets await census. Avoid redoing accepted prefix state. | FP32 state and exact serial dependency/reduction, checkpoint and rejection rollback. |
| Full attention Q/K norm, RoPE, KV write/read, multiquery verifier | Preserve the short-context ~0.2 ms aggregate at its old scope; long-context read budget starts at `2 × 16 layers × 4 KV heads × 256 × 2 bytes × T`, before queries/scratch and rereads. No independent long-context bandwidth measurement is asserted. | Preserve one-pass verifier's certified arithmetic and FP16 KV; valid rows only. |
| RMSNorm, residual, SiLU gate/multiply, state copy | Current fused family ~1.5 ms aggregate; reduce launches/extra passes only when exact. Per-op floor is actual read+write bytes divided by measured copy bandwidth, which must be collected for this shape. | No reassociation, changed epsilon, activation approximation or FMA contraction. |
| Target head and stable argmax | Full target vocabulary remains authoritative; use matching head bytes/507 GB/s only as a planning floor. Argmax target is launch reduction, not reduced vocabulary. | Full-vocabulary verifier, deterministic ties; never use the draft shortlist for target acceptance. |
| Native MTP block/draft head | Keep registered shortlist bytes and generation policy. The 9B 0.894 ms M1/0.921 ms M4 head and 0.03 ms argmax are evidence against blind head tuning, not 27B timings. | Every accepted draft checked by unchanged target; explicit first-token and rejection tests. |
| Sampler, accept scan, state commit | One transaction with no per-op CPU dispatch; actual device-time target unmeasured. Optimize the 26% diagnostic gaps only after matching trace attribution. | Stable first rejection, accepted count and correction; atomic commit across all state. |
| MoE routing/experts | **Not in the dense 27B core.** Reserve interface only; Flash-Next kernels and top-10 routing arrive in Stage 2. | No fake MoE work or borrowed MoE benchmark in Stage 1. |

Do not turn a 1–2% component opportunity into a long campaign. Once an
operator arm passes its preregistered gate, test the full decode transaction.
Separate profiled diagnosis from unprofiled speed measurements.

## First ten packets

Each packet produces a focused commit, plan/identity, command receipt, result
and negative-result note. Native packets run only after the owner's halt
decision, storage admission and an exclusive host window. A single runner
owns the preregistered native stages and graceful cleanup; no automatic retry.

| Order | Packet and concrete deliverable | Exit gate |
| --- | --- | --- |
| 1 | **CPU identity and tensor contract.** Freeze official revision/config/tokenizer requirements, suite/oracle hashes and all 12 token arrays; define typed tensor directory and shape table for 64 layers plus MTP, with checked parser fixtures and explicit unsupported formats. Write provenance per new file. | Deterministic manifest, exact oracle hash/row count, dense-vs-MoE distinction and malformed-header rejection; no weights or devices needed. |
| 2 | Weight admission and loader/shape census. After storage decision acquire/transfer only pinned official bytes; inventory every tensor and exclusion, validate shard hashes and CPU dequant/packing known-value fixtures. Generate full M1/M2/M6 shape list and memory arithmetic. | No missing/duplicate tensors, exact scale conventions, complete source manifest and admitted disk/host budget. Metadata-only preparation may precede acquisition. |
| 3 | Minimal C++/SYCL resource owner. Pin toolchain, establish one compute queue, bounded copies, arenas and cooperative shutdown. No model server. | Native work separately authorized; changing-input copy/queue tests, complete ordered-free receipt, idle and clean postflight. |
| 4 | Exact linear algebra census. Preregister fixture extraction from the pinned certified comparator, including its binary/kernel identities, then save real operator inputs/outputs/state after native authorization. Use a oneDNN baseline and independently written block-loader/dequant glue; only then candidate GEMV kernels on every production shape. | Fixture identity and extraction neutrality checked against full token oracle; same inputs repeat exactly across M and packing; compare certified operator arithmetic, preserve failures; measured bytes/time, no speed gate on identity work. |
| 5 | Dense/GDN layer core. Norm/residual/gates/conv/state and exact serial GDN order, then dense FFN. | Layer outputs and recurrent state exact against bound reference fixtures; reject padded-row state writes and repeat races. |
| 6 | Full attention core and minimal own eager prefill. FP16 KV, rotary, attention, multiquery verify path; implement all text layers and target-only eager decode. | Full no-MTP fixed-suite token arrays exact, plus context points and state reset; stored prefill fixture runs remain diagnostic. |
| 7 | Native MTP and deterministic sampler transaction. Register depth5/shortlist identity, full target verification, first rejection and all state rollback. | Target-only and speculative outputs match oracle; acceptance 0/partial/all, EOS and phantom-first-token tests; no DFlash. |
| 8 | Whole-step capture. First solve embedding residency/UVA without reducing the declared context. Capture fixed graph with stable inputs/output/state; remove CPU dispatch only where supported. | Eager/capture/repeat byte equality and independently mutated inputs; no H2D temporary pointers, host reads or silent segmented replay. Memory peaks within floors. |
| 9 | Unprofiled cold qualification campaign. Two fresh processes, full six-class suite once each, no reuse, natural512; separate operator and prefill diagnostics after primary runs. | All quality gates pass; measured compare against same-identity certified profile, preserve all rows/failures; clean teardown after both runs. |
| 10 | Reviewable Stage 1 result packet. Collate source/build, model identity, output arrays, performance and clean-exit evidence; write lossless decision and promotion attestation. | Owner review; match or beat certified rate on matched workload and capacity, full oracle equality and fresh repeats. No public package/endpoint until its separate stage and publication checks. |

## Stage gate and decisions

Stage 1 is passed only with **12/12 complete outputs identical to the frozen
TP1 FP8 oracle**, repeat/fresh-process determinism, unchanged target verification,
full 16-bit KV, matching fixed-suite/capacity/profile identity, and at least the
certified **54.223911840596784 tok/s** class-balanced decode rate. Use two fresh
processes and matched controls, report variation and do not select one lucky
run. A reduced-context capture or target-only result is useful screening but
does not satisfy this gate. Longer-context and multi-user claims require their
own measured gates; no interpolation. Report prefill separately, never borrow
another model's or topology's number.

Owner decisions: review the Stage 0 spec; choose space for the missing official
27B weights and later Flash quant files (conditional cleanup/external mount);
resolve the host halt and authorize the native window before packet 3;
set quality tolerances before any new quantized target is accepted; choose a
project name when useful. No outside-source exception is needed for this FP8
plan, and none is assumed. Packet 1 can proceed as CPU work after spec review.
