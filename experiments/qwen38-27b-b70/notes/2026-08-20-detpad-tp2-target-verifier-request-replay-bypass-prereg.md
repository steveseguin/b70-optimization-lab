# Qwen3.8 TP2 target/verifier request-selected replay-bypass preregistration

Status: **preregistered; not launched**. T1 and T2 are authorized only through
the frozen launcher and stop contract below. No GPU or service process was
started while preparing this packet.

## Question and treatment boundary

The completed combined graph-replay-bypass R1/R2 pair was 25/25 repeatable,
but it simultaneously changed target/verifier replay, drafter graph keys and
M6-to-M1 geometry, and startup capture/allocation history. This bounded split
asks whether repeatability remains when only request-selected uniform
target/verifier replay is bypassed while the drafter and startup topology stay
on their incumbent PIECEWISE/M6 identity.

The treatment sets independent effective and expected values:

```text
VALIDATION_DECODE_CUDAGRAPH_REPLAY_EAGER_EVERY_N_REQUESTS=1
VALIDATION_EXPECT_DECODE_CUDAGRAPH_REPLAY_EAGER_EVERY_N_REQUESTS=1
VLLM_XPU_DECODE_CUDAGRAPH_REPLAY_EAGER_EVERY_N_REQUESTS=1
```

Despite the historical `EAGER` spelling, the selected target/verifier rows use
the existing compiled non-cudagraph runnable (`CUDAGraphMode.NONE`), not an
uncompiled eager model path. The umbrella treatment is independently frozen
off:

```text
VALIDATION_DISABLE_SPEC_DECODE_CUDAGRAPH_REPLAY=0
VALIDATION_EXPECT_DISABLE_SPEC_DECODE_CUDAGRAPH_REPLAY=0
VLLM_XPU_DISABLE_SPEC_DECODE_CUDAGRAPH_REPLAY is unset
VLLM_XPU_DRAFT_DISABLE_CUDAGRAPHS=0
```

Under pinned MTP5 source, each fresh request is selected during its
non-uniform prefill. A later uniform six-token target/verifier row for that
request switches from PIECEWISE replay to `NONE` only after normal dispatcher
selection and M6 padding. Therefore:

- target/verifier request-selected uniform M6 rows use the compiled
  non-cudagraph runnable;
- non-uniform prefill and ordinary one-token target decode remain
  graph-eligible;
- drafter graph keys remain enabled and its batch-one path remains
  PIECEWISE/M6; and
- startup still captures both the mixed prefill/decode and uniform decode
  PIECEWISE descriptors.

This is a target/verifier request-selection diagnostic, not a generic meaning
of the environment variable for other speculative widths or scheduler
identities.

## Marker-only source delta

vLLM remains at `44fc8fde09fc311d3099dab10366b672d9142ea4` with exactly
one tracked hunk. The hunk adds one local-scope `logger.info_once` inside the
executed request-selected uniform bypass branch:

- tracked patch:
  [`vllm-target-verifier-request-replay-bypass-marker-20260820.patch`](../../../patches/qwen38-27b-autoround-int4-b70/vllm-target-verifier-request-replay-bypass-marker-20260820.patch);
- authoritative live `git diff --binary` SHA-256:
  `4193f05e8f255cf07de81360eff031fdb2e468218c2660850d69c9f750369683`;
- separately pinned zero-context patch-artifact SHA-256:
  `e2185720388a3f92533e41224ecf9cfa0509a49c45f12f1a10f62a8debdef4ea`;
- expected rendered event:
  `XPU target/verifier request-selected uniform PIECEWISE replay bypass engaged: every_n_requests=1 uniform_decode_query_len=6.`

The marker carries no request ID, tensor value, or dynamic token count. It does
not read a device tensor, synchronize XPU work, recapture a graph, or mutate
model state. It is still a one-time CPU logging and source-diff perturbation,
so the measured treatment includes this engagement probe. Source-backed
selection plus the one marker proves that at least one qualifying branch ran;
with CUDAGraph metrics disabled, it is not a per-call replay-count measure.
The launcher verifies the zero-context artifact forward against the clean vLLM
index and in reverse against the live worktree with `git apply --unidiff-zero`;
the artifact SHA and authoritative live-diff SHA are deliberately distinct.

## Historical context, not a Qwen3.8 prediction

A different Qwen3.6 Quark W8A8/no-spec experiment, with prefill replay disabled
in both arms, previously compared ordinary decode PIECEWISE replay with the
same selector at N=1. The control failed JSON repeat 31 (`42` became `12`)
while the N=1 arm passed JSON and color `96/96`, but median request elapsed
time reportedly worsened about `3.72x` for JSON and `3.16x` for color. The
tracked summaries are:

- [`qwen36-ablation-prefill-safe-int8-sharedexp-fusedactquant-out-tp2-deep-canary-20260619a-summary-20260619175659.json`](../../../data/qwen36-ablation-prefill-safe-int8-sharedexp-fusedactquant-out-tp2-deep-canary-20260619a-summary-20260619175659.json);
- [`qwen36-ablation-prefill-safe-int8-sharedexp-fusedactquant-out-tp2-eager-everyreq-canary-20260619a-summary-20260619180050.json`](../../../data/qwen36-ablation-prefill-safe-int8-sharedexp-fusedactquant-out-tp2-eager-everyreq-canary-20260619a-summary-20260619180050.json).

Those artifacts establish only that the selector has acted as a correctness
diagnostic elsewhere and that severe cost is plausible. Qwen3.8 AutoRound
INT4/MTP5 behavior and performance remain unmeasured.

## Frozen identity and prerequisites

T1 then T2 use TP2 on physical GPUs 2,3, one request at a time, engine seed 0,
request seed 1, FP16, AutoRound INT4, MTP5, greedy sampling, the fixed ordered
25-prompt suite, and the 512-token/100-event metric contract.

Both arms bind:

- model `/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan`, its
  tracked manifest, and immediate fail-closed ordinary plus O_DIRECT
  verification;
- vLLM `44fc8fde...` plus only the exact marker patch above, and clean
  XPU-kernel source `2dd55f380df753a10a88fcd9e96192561066e713`;
- the 4dd native-extension plus 339 graph-safe FlashAttention composite and
  complete staged graph manifest;
- sealed b991 cache namespace and canonical manifest SHA-256
  `f3582440de9b252cc738648aa5b690fd324bec9afeb8d89e4b73d295071cb0ff`;
- exact outer `2` and AOT `4` direct loads, no compile/save marker, and
  byte-identical pre/post cache manifests with zero byte delta;
- native GDN on, ReplaySSM off, persistent scratch on, GDN capture on,
  recurrent-serial-exact off, both fallback margins zero, target INT8 head,
  and draft INT4 head;
- all-target INT4 completion/input-dependency repair, two rank-specific INT4
  determinism-pad markers, and INT8 completion/input dependency;
- no packet, layer, replay-microscope, post-forward synchronization, or other
  diagnostic axis;
- validation suite SHA-256
  `292dea6aaf60f53067fb63c9bc5aba15bd1c6e71c2601693e6750239edf9fa0c`
  and quality baseline SHA-256
  `45424f1d2dcbfda0a5ed75552cf799cac0e8fb6b8c5e1ddf2aba540b95c77e95`;
- immutable target-A and B2 benchmarks plus their enclosing checksum
  manifests as report-only references; and
- clean local `main == origin/main`, current lab HEAD, exact launcher/checker/
  wrapper bytes, and the exact marker-only vLLM working diff.

The frozen native-GDN main comparison remains a mandatory prerequisite at
SHA-256 `61b9f0031e153d4841b139263d8a7afbef6004b8a8da3491affcf8688c329d1d`.
It is a bounded direct-op negative, not clearance of the integrated server.

## Fail-closed engagement evidence

Each arm must have:

- effective and independently expected selector values exactly `1`;
- effective and expected umbrella values exactly `0`, drafter graph-disable
  identity exactly `0`, no umbrella skip marker, and no drafter-disable marker;
- exactly one fully parsed marker from Worker_TP0/rank 0 with N=1 and uniform
  query length 6, with no duplicate or trailing payload;
- exactly six startup-capture records: three mixed prefill/decode PIECEWISE and
  three decode PIECEWISE, each with the sealed progress multiset
  `{0/1: 1, 1/1: 2}`;
- exactly one Worker_TP0-local/rank-0 graph-capture-finished event;
- one or more fully parsed five-position `SpecDecoding metrics` rows with
  internally valid arithmetic and positive aggregate drafted and accepted
  counts;
- `cudagraph_metrics=False`, with no CUDAGraph metrics output, traceback,
  inappropriate/lazy runtime capture, compile, graph-store, or AOT-save marker;
  and
- all existing model, source, cache, pad, freshness, suite, quality,
  supervision, and immutable-input gates.

## Two-arm order and terminal rules

1. Run `check`. Do not create an arm unless every immutable input, source
   identity, marker patch, B2 sealed reference, raw-GDN prerequisite, and live
   canonical cache verify.
2. Run T1 exactly once with quality enabled. Any nonzero runner status,
   sealed-gate failure, quality failure, malformed full-25 benchmark,
   prompt-24 all-zero/malformed output, cache change, missing engagement
   evidence, or negative marker terminates the campaign. Do not repair or
   retry T1.
3. T2 is authorized only after an operator independently supplies the SHA-256
   of T1's completed `SHA256SUMS.pre-manifest`. The launcher revalidates every
   T1 artifact, current source/harness bytes, quality result, treatment
   identity, current checker, and the nonzero 512-token prompt-24 sanity gate.
4. Run T2 exactly once with quality off and immutable T1 as the mandatory
   all-25 peer. Status 0 means 25/25 exact token-array replication; status 14
   is the preregistered recurrence outcome. Either is terminal. Any other
   status is invalid. No third arm is authorized.
5. Target A and B2 comparisons are report-only. Neither is a T1/T2 pass
   condition, and no performance result is promotable or submittable from this
   diagnostic.

A positive pair would support only the combined request-selected
target/verifier compiled-non-cudagraph path plus its one-time marker under the
preserved drafter and startup topology. It would not establish target
exactness, lane-wide determinism, pure replay causality, or a speed win.

Launcher:
[`run-20260820-detpad-tp2-target-verifier-request-replay-bypass.sh`](../scripts/run-20260820-detpad-tp2-target-verifier-request-replay-bypass.sh).

Exact operator sequence:

```bash
/home/steve/llm-optimizations/experiments/qwen38-27b-b70/scripts/run-20260820-detpad-tp2-target-verifier-request-replay-bypass.sh check
/home/steve/llm-optimizations/experiments/qwen38-27b-b70/scripts/run-20260820-detpad-tp2-target-verifier-request-replay-bypass.sh t1
sha256sum /mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/qwen38-detpad-composite4dd-marginfree-mtp5-25-target-request-replay-bypass-t1-20260820/SHA256SUMS.pre-manifest
/home/steve/llm-optimizations/experiments/qwen38-27b-b70/scripts/run-20260820-detpad-tp2-target-verifier-request-replay-bypass.sh t2 T1_CHECKSUM_MANIFEST_SHA256
```

The checksum printed by the third command must be reviewed and supplied as an
independent literal argument to the fourth command; do not replace it with an
inline command substitution.
