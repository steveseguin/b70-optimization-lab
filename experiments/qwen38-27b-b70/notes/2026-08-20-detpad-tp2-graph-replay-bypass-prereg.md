# Qwen3.8 TP2 speculative graph-replay-bypass preregistration

Status: implemented and not launched. No result exists yet.

## Question and treatment scope

The bounded question is whether the existing XPU speculative CUDA-graph replay
bypass removes the full-25 TP2 output-family recurrence seen after the INT4
determinism pad, without changing any model, cache, native-kernel, quality,
prompt, or sampling identity.

The treatment sets both the effective flag and its independent harness
expectation to one:

```text
VALIDATION_DISABLE_SPEC_DECODE_CUDAGRAPH_REPLAY=1
VALIDATION_EXPECT_DISABLE_SPEC_DECODE_CUDAGRAPH_REPLAY=1
VLLM_XPU_DISABLE_SPEC_DECODE_CUDAGRAPH_REPLAY=1
```

This is a combined treatment, not a component localization:

- uniform full-width target-verifier speculative rows select
  `CUDAGraphMode.NONE`, so they use the compiled non-cudagraph runnable;
- speculative drafter CUDA-graph keys are disabled, also selecting its
  compiled non-cudagraph path;
- disabling the drafter graph keys changes the drafter geometry from the
  PIECEWISE-padded M6 path to an unpadded M1 path under `NONE`, while the target
  verifier retains M6 geometry;
- ordinary one-token target decode remains graph-eligible; and
- the uniform speculative capture descriptor is removed at startup, changing
  graph capture, graph-memory use, and allocation history before requests run.

Therefore a positive result would implicate this combined replay/topology/
geometry/startup-history treatment. It would not prove that target replay,
drafter replay, drafter M1 geometry, or allocation history was independently
causal. The exact source markers and capture inventory prove configuration and
startup topology engagement; they are not per-call runtime measurements.

## Frozen prerequisites and identity

The campaign is `R1` followed by `R2`, both TP2 on physical GPUs 2,3, one
request at a time, engine seed 0, request seed 1, FP16, AutoRound INT4, MTP5,
greedy sampling, a 512-token generation cap with the existing valid-window
gate, and the same ordered 25-prompt suite.

Both arms bind:

- model `/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan`, the
  tracked model manifest, and the fail-closed ordinary plus O_DIRECT verifier;
- vLLM source `44fc8fde09fc311d3099dab10366b672d9142ea4` and XPU-kernel source
  `2dd55f380df753a10a88fcd9e96192561066e713`, both with empty tracked diffs;
- the 4dd native extension plus 339 graph-safe FlashAttention composite,
  including exact native/core/MoE/FA hashes and its complete graph manifest;
- sealed cache root
  `/mnt/usb-models/llm-runtime/vllm-cache/qwen38-postrecovery-marginfree-mtp5-20260820`,
  outer namespace `b99160ae76`, both recorded AOT keys, and canonical manifest
  SHA-256 `f3582440de9b252cc738648aa5b690fd324bec9afeb8d89e4b73d295071cb0ff`;
- exact outer/AOT direct-load counts, no compile/save markers, and byte-identical
  pre/post canonical cache manifests, including zero total cache-byte delta;
- native GDN on, ReplaySSM speculative path off, persistent scratch on, GDN
  capture on, recurrent-serial-exact explicitly off;
- the all-target INT4 completion/input-dependency repair, exactly one INT4
  determinism-pad marker per TP rank, and the INT8 completion/input dependency;
- target INT8 head, draft INT4 head, both fallback margins zero, and no packet,
  layer, replay-microscope, or post-model-forward synchronization diagnostic;
- validation suite SHA-256
  `292dea6aaf60f53067fb63c9bc5aba15bd1c6e71c2601693e6750239edf9fa0c`
  and quality baseline SHA-256
  `45424f1d2dcbfda0a5ed75552cf799cac0e8fb6b8c5e1ddf2aba540b95c77e95`;
- immutable, snapshotted report-only target-oracle and sane-B2 benchmarks,
  including their pinned enclosing checksum manifests; and
- clean `main`, local `main == origin/main`, current repo HEAD, and exact
  launcher, checker, common runner, top wrapper, serve runner, and campaign
  driver bytes.

The native-GDN raw-op main comparison is a mandatory prerequisite at SHA-256
`61b9f0031e153d4841b139263d8a7afbef6004b8a8da3491affcf8688c329d1d`.
Its frozen pass/identity/native-call fields must still validate before either
arm. That negative narrows the raw native prefill operation; it does not clear
the integrated graph/speculative runtime.

## Treatment evidence and fail-closed negatives

For each arm, the sealed checker must require:

- effective and independently expected replay-bypass identities both equal 1;
- exactly one Worker_TP0-local/rank-0 `Skipping 1 uniform PIECEWISE
  speculative decode CUDA graph captures ...` marker;
- exactly one Worker_TP0-local/rank-0 speculative-drafter graph-key-disable
  marker;
- exact remaining startup capture inventory: only mixed prefill-decode
  PIECEWISE, completed 1/1, with no uniform decode capture category, followed
  by exactly one Worker_TP0-local/rank-0 graph-capture-finished event;
- one or more exactly parsed `SpecDecoding metrics` records, five ordered
  per-position rates, valid counts/ranges, and internally consistent rounded
  mean and aggregate acceptance arithmetic;
- `cudagraph_metrics=False`; no CUDAGraph metrics output is enabled or accepted;
- no traceback, inappropriate/lazy runtime CUDA-graph capture diagnostic, graph
  compile/save, or AOT save diagnostic; and
- all existing model, source, cache, pad, head, freshness, suite, quality (R1),
  supervision, and immutable-input gates.

Because CUDAGraph metrics remain disabled, this campaign deliberately makes no
per-call replay-count claim. Absence of a decode capture category plus the
source-backed selection/disable markers is the preregistered engagement proof.

## Arm order and stop rules

1. Run `check`. Do not create an arm unless every immutable input, the raw-GDN
   prerequisite, the B2 sealed artifact, and the live canonical cache verify.
2. Run `r1` exactly once with quality enabled. Stop permanently on any nonzero
   runner status, sealed-gate failure, quality failure, malformed full-25
   benchmark, cache-byte change, missing treatment evidence, or negative log
   marker. Do not repair or retry R1 in this campaign.
3. Only after an operator independently supplies the SHA-256 of R1's completed
   `SHA256SUMS.pre-manifest` may `r2` start. The driver revalidates that manifest,
   every listed artifact, current harness/checker/driver identity, R1 quality,
   treatment identity, and the current sealed checker before launch. It also
   requires R1 prompt 24 to contain exactly 512 token IDs and rejects the known
   all-zero catastrophe. This is a malformed-output stop, not a requirement to
   match either report-only reference family.
4. R2 runs exactly once, quality off, with immutable R1 as its mandatory peer.
   Complete token arrays for all 25 ordered prompts must be exact. Runner status
   0 is an exact replication; status 14 is a scientifically valid recurrence
   failure. Either outcome is terminal. Any other status invalidates the arm.
5. Target-oracle and B2 are report-only references in both arms; neither is a
   pass condition for R1/R2 parity. No result from this diagnostic is a record
   submission without a separately preregistered performance campaign.

The historical M1 microscope arm remains permanently closed under its original
no-retry preregistration. This campaign neither reuses nor authorizes M1.

Launcher:
`experiments/qwen38-27b-b70/scripts/run-20260820-detpad-tp2-graph-replay-bypass.sh`.
