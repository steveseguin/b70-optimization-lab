# Packet 3: runtime-order CPU oracle, arithmetic identity v1

This is the oracle for the separate Unsloth UD-IQ3_XXS **quantized compressed
version**, revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`. It uses the
admitted published bytes, full BF16 state/KV and no speculative decoding.
It implements the [arithmetic authority decision](../../../notes/2026-10-11-iq3-arithmetic-authority-decision.md).
The earlier [BLAS-order oracle](../packet2-cpu-oracle/README.md) remains
information, not this runtime's hidden-state gate. No device was accessed.

## Frozen identity and implementation

[arithmetic.json](arithmetic.json) names **arithmetic identity v1**:
`iq3-p13-r234-sg32-split4-bf16-v1`. Its defining header is
[packet13/arithmetic.hpp](../../own-xpu-runtime/stage2/packet13-integrate/arithmetic.hpp),
SHA256 `5fa871445c0bef63f60ce6bf06e5a2102e4c71fd8ec350e7b4b46ffd7e22dde7`.
The identity also binds the complete header/source map consumed by Packet 13;
the top header hash alone would not cover changes in included decoders or trees.
[Build receipt](build-receipt.json) and [environment](environment.json) pin the
compiler, flags, host libraries and CPU-only binary identities.

The production checkpoint contains F32, BF16, Q8_0, Q6_K, IQ2_S, IQ3_S and
IQ4_NL tensors; **no tensor is IQ3_XXS despite the release name**. Packed
dequantization uses the lab's packet1b format equations, via packet2 `math.hpp`
and the packet6/8 shared decoders. Weights widen directly to FP32, without an
intermediate BF16 weight rounding. Scale products retain their written order.

- Dense projections use the measured packet9 `(type, rows, columns, experts)`
  dispatch table through Packet 13's selector, including declared fallbacks.
- Expert gate/up/down use the measured fused-expert constant SG32 arithmetic.
  Each lane consumes eight adjacent products, then advances 256 columns.
- SG32 reduces adjacent lane pairs. Split4 partitions contiguous 256-column
  tiles, applies that same lane tree, then reduces the four partials in an
  adjacent-pair tree. Constant/SLM decode variants share this arithmetic.
- Every product and add rounds separately to FP32; contraction and fast math
  are disabled. Projection results round to BF16, round-to-nearest-even.
  Expert down rows round before ordered slot-0-through-9 weighted accumulation;
  the mixture rounds once. No tensor silently falls back to a BLAS reduction.

[matmul.cpp](matmul.cpp) exposes that header directly through a small C ABI.
[linear.py](linear.py) is the Python adapter for the old oracle's `Store`,
streaming at most 128 packed output rows and selecting by the **full production
shape**, not the temporary tile shape. It accepts only CPU BF16 activations.

The complete fixture producer, [oracle.cpp](oracle.cpp), reuses our own
Packet 13 CPU graph/loader and Packet 4 nonlinear core. A matmul-only replacement
would not reproduce the runtime: Python used vector-library transcendental
functions and `rsqrt`; the runtime uses scalar FP32 libm and `1/sqrt`. PLE's
dilation-three convolution also rounds its accumulator to BF16 **before** SiLU
in the runtime, unlike the old Python path. These are explicit changes from
the BLAS oracle, not a claim that any token difference comes only from dot order.
Future arithmetic changes require a new identity and regenerated fixtures.

The only generated CPU scheduling overlay adds an OpenMP parallel loop over
independent output rows. It never splits an individual row's reduction.
The exact one-line transformation and before/after source hashes are in the
build receipt; shared repository runtime files are unchanged. The numerical
process runs at nice 19 with eight threads; preparation uses two threads.
`OWN_RT_HOST_ONLY` is mandatory, and dynamic dependency inspection rejects
accelerator libraries. Host adapter names such as `Device` and `Memory::device`
refer to ordinary CPU allocations in this build, not accelerator access.

One layer's dense weights and only the selected ten experts are read through
bounded read-only mappings and released after the layer. There is no expanded
expert bank, whole-model mapping, checkpoint copy or host-cache control.
An explicit 38 GB address-space cap bounds RSS below 40 GB. Intermediate
prefill predictions skip the unused final mixer/head/argmax, while preserving
every layer, recurrent state, PLE history and position commit. The full head
is evaluated at the last prompt position and every decode position.

## Exactness proof

[proof.json](proof.json) and [adapter-proof.json](adapter-proof.json) record:

- **1,944 bit-identical FP32 values** from the C ABI against independently
  decoded NumPy FP32 lane/tree reductions, across all 27 hash-bound packet2
  real/random fixtures, six variants, three activation mutations and batching.
  The C ABI accepts BF16; historical F16 fixture activations are converted to
  derived BF16 inputs for these checks.
- The original packet8 host test, repeated in a fresh process, checks the
  **unaltered** F16/BF16 fixtures: **2,832 row comparisons**, **200 extended
  shape comparisons**, **551,424 decoded values**, and **409,600 special-scale
  checks**, including signed zero, nonfinite scales and uneven split bounds.
- Packet 13's independent scalar/recursive-tree test passes **75 production
  shape comparisons**. All **918 matrix-shaped production tensor bindings**
  resolve, including expert overrides; unknown shapes are rejected.
- The Python adapter checks dense matrices, expert IDs 0/511, 128-row tiles,
  batch-versus-single equality and invalid expert rejection.
- Two fresh CPU executions, serial and parallel, process all 87 prompt tokens
  through real layer 0 and reproduce Packet 13's existing reference **byte for
  byte**: SHA256
  `1b7f914b9ef1834a72aea1cb186b74c8dbecddff743fa529fe8e916e1352d82e`.
  [Retained proof and fixture](evidence/real-layer/proof.json).

These establish exact CPU reference arithmetic and adapter behavior. Shared
source does not establish device transcendental parity or full-model quality.

## Run, coverage and fixture contract

The [parallel run](runs/arithmetic-v1-parallel-20261011/receipt.json) saves
evidence incrementally. Its first eight-token checkpoint is `pilot8.json`;
each generated token records its ID, top-five logits, full BF16-logit hash and
timing in `tokens.jsonl`. `result.json` records actual coverage and the decoded
text. [Validation](runs/arithmetic-v1-parallel-20261011/validation.json) passes:

| Covered prompt | Input tokens | Generated tokens | Prompt pass | Mean decode | Peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| incident-retrospective | 87 | 64 | 545.977 s | 9.16685 s/token | 1.08137 GB |

The first eight-token checkpoint averaged **7.81804 s/token** over seven decode
calls. The complete numeric run took **1,123.731 seconds**. All 384 fixtures
(48 layers × 8 steps), 64 token records, source hashes and CPU allocation
teardown checks pass. The other eleven prompts and a fresh full-model CPU
repeat were not run. This is coverage of one prompt, not full-suite qualification.

[BLAS comparison](runs/arithmetic-v1-parallel-20261011/blas-comparison.json):
the first 17 tokens agree. At **token 18** (one-based), runtime token 18, **"3"**,
beats token 19, **"4"**, by **0.375 logits** (21.500 versus 21.125); the BLAS
oracle picks "4" by **0.250** (21.375 versus 21.125). The generated incident
year therefore begins 2023 versus 2024. This is a near-tie reversal; the
comparison includes all **28 differing positions** and their available margins.
After the first difference, histories differ, so later margins cannot isolate
rounding effects. These differences include the stated nonlinear/PLE changes.

[llama.cpp comparison](runs/arithmetic-v1-parallel-20261011/baseline-comparison.json):
both the one-card and two-card outputs share **56 characters**, then also choose
"4" where this oracle chooses "3". Re-tokenized text identifies the same token
18 divergence, with this oracle's **0.375** margin. Baseline logits and precise
terminal-token framing are unavailable; neither baseline is the arithmetic
authority. Both small stdout inputs are retained, hash-bound, and reused on
comparison replay without the historical untracked directories.

Fixtures live under
`runs/arithmetic-v1-parallel-20261011/incident-retrospective/stepN/`.
For N=1 through 8, `layer-00.bf16` through `layer-47.bf16` contain exactly
20,480 bytes each: `[1,4,2560]` BF16, little-endian. `layers.jsonl` binds every
file's shape, dtype and SHA256. Step 1 is the **last prompt position** (index
86), predicting the first generated token; it is not the first prompt token.
The prompt directory's `arithmetic.json`, `input.json`, `result.json` and
`stepN` layout are directly consumable by Packet 13's `--oracle` checks.
Packet 4's comparison helper can read the `step1` directory.

**Device gate:** on exactly these 87 input tokens, require bit-identical BF16
layer bytes/hashes for every retained step/layer, and exactly the saved greedy
token IDs through the covered continuation, including EOS behavior. Require
same-process and fresh-process deterministic repeats. No tolerance, speed
result, BLAS match, or llama.cpp agreement substitutes for this gate. Packet
13's current eight-step window checks only the eight-step prefix; longer saved
token coverage requires a correspondingly extended device check. Uncovered
prompts remain uncovered, and a full CPU model repeat is not yet claimed.

Decode cost is the mean of completed autoregressive forward calls after the
first generated token. It includes layer weight reads, CPU calculations and
incremental per-site logging; it excludes top-five sorting and result-file
persistence after each forward. Prefill includes initialization and all 87
prompt positions through the first complete vocabulary prediction. These are
CPU reference costs, never model-serving throughput headlines.

The serial pilot was stopped cooperatively before completing prefill when
independent-row parallelism was ready. Its [partial evidence](runs/arithmetic-v1-20261011/receipt.json)
is retained separately and is not prompt coverage. Its original numerical
source is saved beside it as `serial-oracle.cpp.txt`.

The complete packet is below 50 MB and its results are retained in Git.
[Retention and restoration](RETENTION.md) records the larger log artifacts.

## Reproduction

From the repository root, with no GPU/server/container work:

```bash
P=experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle
PY=/home/steve/.venvs/vllm-xpu/bin/python
BUILD=$(mktemp -d -u /tmp/iq3-oracle-build-XXXXXX)
INPUT=$(mktemp -d -u /tmp/iq3-oracle-input-XXXXXX)
nice -n 19 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  "$PY" -B "$P/build.py" "$BUILD"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  "$PY" -B experiments/own-xpu-runtime/stage2/packet13-integrate/prepare.py --output "$INPUT"
nice -n 19 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  "$PY" -B "$P/test.py" "$BUILD"
nice -n 19 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  "$PY" -B "$P/test_adapter.py" "$BUILD"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  "$PY" -B "$P/run.py" --build "$BUILD" --input "$INPUT" \
  --out "$P/runs/NEW-RUN-NAME" --seconds 8000 --tokens 64
nice -n 19 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  "$PY" -B "$P/compare.py" "$P/runs/NEW-RUN-NAME"
rm -r -- "$BUILD" "$INPUT"
```

The runner sets eight threads only for its numerical child. No automatic
retry occurs. SIGTERM is cooperative between operator sites; partial results
are preserved and labeled. Output directories must be new. The builder checks
the frozen Packet 13 source hashes before execution; use this commit's source
identity when replaying, rather than silently accepting a future header.

The measured run's orchestration source is retained as `run.py.snapshot` with
the hash in its receipt. After it started, `run.py` gained stricter checks of
compiled-source hashes and forwarding of launcher stop signals to its child;
neither change affects numerical code. For the measured launcher, cooperative
stop targeted the native PID recorded in `receipt.json`.
