# Reproduce official Qwen3.8 27B FP8 TP2 on two B70s

> **Certification: `candidate-portable-repro`, not a starter guide.** The
> model, image, launch, and validation identities are pinned and the model has
> been verified on this host. A fresh pinned source rebuild and empty-cache
> strict replay also pass here. The remaining gates are a tested Intel
> driver/Docker installation path, beginner recovery guidance, and an
> independent supported-host replay. See the
> [guide catalog](../guide-catalog.json) and
> [certification standard](../../docs/reproduction-guide-certification.md).

This is a quality-gated vLLM/XPU reproduction packet for two ASRock Intel Arc
Pro B70 32 GiB cards. It uses Qwen's official block-scaled FP8 target, native
FP16 KV, and TP2. Static publisher MTP1 is lab-qualified at
**`51.808087 tok/s`**; deeper dynamic MTP remains a research lane.

## Strict MTP1 qualification

Four fresh servers with separate empty compile caches passed the complete fixed
12-prompt/six-class, natural 512-token suite. MTP0 and MTP1 deliberately used
the same content-verified R50 image; only speculative decoding changed:

| arm | attempt | class-balanced decode | output gate |
| --- | ---: | ---: | ---: |
| MTP0 | `r54a-r50` | 33.722035 tok/s | 12/12 vs sibling |
| MTP0 | `r54c-r50` | 33.745004 tok/s | 12/12 vs sibling |
| MTP1 | `r53a` | 51.796549 tok/s | 12/12 vs sibling and both targets |
| MTP1 | `r53b` | 51.819625 tok/s | 12/12 vs sibling and both targets |
| MTP1 two-attempt center | **51.808087 tok/s** | — | **qualified** |

All four attempts reported `cached_tokens=0`, passed the independent canaries,
and used natural EOS with a 512-token cap. The metric is the median of six
prompt-class medians over the 99 intervals between streamed output events
1-100 after TTFT. The candidate is `53.5804%` faster than the matched-image
MTP0 center (`33.733520 tok/s`) with no observed token change. See the
[audit note](../../experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-public-reproduction-audit.md).

The repository build path was then exercised from a new pinned source checkout.
That R55C image measured `51.579521 tok/s` with a new compile cache, passed the
same workload and canaries, and matched 12/12 complete arrays against both R53A
MTP1 and R54A MTP0. Its rebuilt libraries use portable `$ORIGIN` RUNPATHs; the
builder verifies whole-file and code/data section hashes. See the
[clean-rebuild result](../../experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-clean-rebuild-r55c-result.json).

### Refresh older clones before benchmarking

The public build chain published before September 1, 2026 stopped at the R31
MTP1 image. It did not contain the later serial-attention build stage, rebuilt
split-GDN stage, or the final R50 GDN patch used by the qualified 51.8 tok/s
profile. Those files are now tracked in this repository. An old checkout can
therefore run successfully yet measure a different profile.

Refresh and verify the complete public source closure before building:

```bash
git pull --ff-only origin main
repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-public-source-closure.sh
```

The verifier checks that all final Dockerfiles, builders, and custom-op patches
are present and tracked, then verifies the three final patch hashes. The full
builder below applies every stage in order and the image-contract verifier
checks the installed libraries. Do not substitute the older R31 image for the
final R50 image.

The 51.808087 tok/s qualification is a single-sequence, 1K allocation profile
(`MAX_MODEL_LEN=1024`), not a full-262K-context measurement. A server launched
with a 262K maximum context is useful, but it is not a like-for-like reproduction
of that headline. The separately measured historical 32K MTP1 point was
46.636241 tok/s and is explicitly Grade-C shape evidence.

Build the full dependency chain and launch the qualified profile with portable
caller-selected paths:

```bash
BUILD_ROOT=/path/to/empty-build-root \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-pinned-mtp1-stack.sh

MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-empty-runtime-cache \
MAX_MODEL_LEN=1024 MAX_NUM_SEQS=1 MAX_NUM_BATCHED_TOKENS=1024 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-mtp1-strict-server.sh
```

In another terminal, run the actual strict natural-512 workload—not the older
128-token concurrency screen:

```bash
OUT_DIR=/path/to/new-strict-attempt \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh
```

The script fails unless the full workload, cache-zero policy, and independent
canaries pass. It deliberately reports target/repeat parity as unevaluated for
a single attempt. A qualifying audit needs two new MTP1 attempts and two new
MTP0 attempts, all compared with
[`compare-strict-attempt-outputs.py`](../../scripts/compare-strict-attempt-outputs.py).

Launch the matched-image MTP0 control with the same final image and compiler
contract:

```bash
PORT=18124 MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/another-new-empty-runtime-cache \
MAX_MODEL_LEN=1024 MAX_NUM_SEQS=1 MAX_NUM_BATCHED_TOKENS=1024 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-mtp0-strict-server.sh

OUT_DIR=/path/to/new-mtp0-attempt BASE_URL=http://127.0.0.1:18124 \
MODEL_NAME=qwen38-fp8 PROFILE_LABEL=mtp0-target \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-strict.sh
```

The wrapper verifies the installed image contents and pins all
correctness-relevant graph, GDN, RMS, W8A16, and MTP settings. A local Docker
image ID is not portable across rebuilds, so content hashes and the kernel
commit are authoritative. See the
[structured R54 result](../../experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-explicit-deterministic-matrix-r54-result.json).

## Historical strict MTP0 baseline

The deterministic GDN/oneCCL patches and graph-off compiled launcher passed the
full promotion contract on two fresh servers with empty compile caches:

| attempt | class-balanced decode | cache | complete output match |
| --- | ---: | ---: | ---: |
| `workwait-r15-A` | 34.025180 tok/s | zero on 12/12 | 12/12 |
| `workwait-r15-B` | 34.038013 tok/s | zero on 12/12 | 12/12 |
| two-attempt median | **34.031596 tok/s** | — | **qualified** |

Both attempts used the complete fixed 12-prompt/six-class suite, the natural
512-token cap, raw streamed token IDs, and independent repeat, arithmetic,
copy, and JSON canaries. Apply the repository-contained
[deterministic GDN patch](../../experiments/qwen38-27b-b70/patches/vllm-qwen38-xpu-deterministic-gdn-ba-state-20260828.patch),
[compiled-state/oneCCL patch](../../experiments/qwen38-27b-b70/patches/vllm-qwen38-xpu-compiled-gdn-state-ccl-wait-20260828.patch),
build the overlay described below, and launch:

```bash
BUILD_ROOT=/path/to/empty-build-root \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-deterministic-compiled-image.sh

IMAGE=neural-download/vllm-openai-xpu:qwen38-fp8-collective-work-wait-r15 \
IMAGE_CONTRACT_PROFILE=mtp0 PORT=18124 GPU_MEMORY_UTILIZATION=0.95 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false}}' \
VLLM_XPU_FP8_BLOCK_W8A16=1 VLLM_XPU_ENABLE_XPU_GRAPH=0 CCL_P2P_ACCESS=1 \
TORCHINDUCTOR_DETERMINISTIC=1 PYTHONHASHSEED=0 \
VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE=0 \
VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING=0 \
VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1 \
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-runtime-cache \
MAX_MODEL_LEN=1024 MAX_NUM_SEQS=1 MAX_NUM_BATCHED_TOKENS=1024 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-server.sh
```

Then run the same strict natural-512 workload used for the MTP1 audit:

```bash
OUT_DIR=/path/to/new-mtp0-attempt MODEL_NAME=qwen38-fp8 \
PROFILE_LABEL=mtp0-target BASE_URL=http://127.0.0.1:18124 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-strict.sh
```

The validated image ID is
`sha256:d19f802ba702a9cb94b155f807a4674a0100702aee838323372f740d7168e34e`.
See the [result note](../../experiments/qwen38-27b-b70/notes/2026-08-28-qwen38-fp8-deterministic-eager-baseline-and-compiled-closure.md)
and [structured summary](../../experiments/qwen38-27b-b70/data/2026-08-28-qwen38-fp8-deterministic-compiled-work-wait.json).

The eager r5 image remains a historical fallback at `18.910242 tok/s`; its
build script is retained for recovery and compiler regression isolation.

## Earlier MTP matrix — measured, output gate failed

Two full fresh-server attempts were completed for each main single-user
profile. W8A16 MTP0 measured `34.772270`/`34.740755 tok/s`, static MTP1
measured `55.760069`/`55.782147 tok/s`, and dynamic MTP8 measured
`68.049727`/`62.432362 tok/s`. Each used all 12 varied prompts, six prompt
classes, a 512-token natural-completion cap, the first 100 streamed token
events, and zero cached tokens. All workload and objective-canary gates passed.

Those original faster profiles did not qualify: each pair matched only `8/12`
complete token arrays. Later work stabilized the GDN B/A prefill reduction,
bound compiler-visible recurrent state, and made oneCCL completion explicit
with `async_op=True` plus `Work.wait()`. That repaired compiled MTP0 to 12/12
without enabling XPU Graph. The later packed-RMS plus deterministic-Inductor
r32 treatment made static MTP1 exact inside that historical campaign; it does
not retroactively qualify the original matrix or dynamic-MTP rows, and the
2026-09-01 audit now withholds its package headline. See the [strict matrix result](../../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-fp8-strict-profile-matrix-result.md)
and [machine-readable summary](../../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-fp8-strict-profile-matrix-summary.json).
A one-B70 eager/default-dispatch control subsequently matched only `8/12` too,
so TP2 and cross-rank oneCCL are not required; see the
[TP1 result](../../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-fp8-tp1-strict-target-control-result.md).

The subsequent bounded R34-R38b repair campaign did not leave that failure
untested. Serial native GDN made rebuilt static MTP1 exact, while dynamic MTP8
still diverged at token 128. Serial packed block-FP8 moved the first sentinel
divergence to token 441; declaring global batch invariance was neutral; and
progressive serial FlashAttention, with and without its redundant causal mask,
returned the divergence to token 128. All sentinels were cache zero and fired
their required mechanism markers. The dynamic lane is therefore rejected, not
merely missing, and none of its diagnostic rates is public evidence. See the
[R34-R38b structured closeout](../../experiments/qwen38-27b-b70/data/2026-08-28-qwen38-fp8-dynamic-exactness-r34-r38b-summary.json).

Dynamic-MTP promotion cells stay blank in the research record, and that
rejected route is omitted from the landing-page chooser. The historical R32
deterministic MTP1 profile directly measured all six exact depths from 2K
through 32K and
matched the MTP0 target arrays 6/6. Its 32K point is `46.636241 tok/s` with
`10.487 s` HTTP TTFT. This is Grade-C repeated-token shape evidence, not a
strict natural-prompt headline; see the [R33 result](../../experiments/qwen38-27b-b70/notes/2026-08-28-qwen38-fp8-w8a16-mtp1-exact-depth-r33-result.md).

## Dynamic MTP8-to-MTP1 screening profile — not a headline

> **Audit correction:** the table below used the varied fixed suite and was
> cache-zero, but the response cap was 128 tokens. It therefore does not pass
> the 512-cap final gate and is retained only as screening evidence. The old
> benchmark harness incorrectly called it final. There is currently no
> promotion-grade single-user headline for this package.

| Fresh server | conventional 99-interval median | p10 | wall median | TTFT median |
| --- | ---: | ---: | ---: | ---: |
| realistic R1 | 58.537756 | 48.117648 | 55.436231 | 108.094 ms |
| realistic R2 | 58.244309 | 47.896683 | 55.270330 | 107.450 ms |
| diagnostic two-server center | **58.391033** | **48.007166** | **55.353281** | **107.772 ms** |

Both independently cold-started servers passed all 12 unique prompts, returned
128/128 tokens per prompt, and reported `cached_tokens=0` for every request.
Container-to-ready time was 165.327/164.822 seconds with empty compile caches.
The first inference paid three additional EAGLE-kernel JIT compilations and
829/743 ms TTFT. Reproduce one fresh attempt after launching the service with:

```bash
OUT=/path/to/new-realistic-suite.json \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-dynamic-mtp-realistic.sh
```

See the [result note](../../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-fp8-w8a16-mtp8-realistic-cold-result.md)
and [structured summary](../../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-fp8-w8a16-mtp8-realistic-cold-summary.json).
The first chronological run was submitted prematurely and is approved on
[LocalMaxxing](https://www.localmaxxing.com/runs/cmtb5n45n0021qq01n13vly2h).
Withdrawal is recommended.

The earlier high-acceptance 40-prompt-token fixture is a selected diagnostic,
not realistic performance evidence:

Two separately preregistered fresh-server attempts measured:

| Active users | R15 tok/s | R16 tok/s | two-attempt median |
| ---: | ---: | ---: | ---: |
| 1 | 146.808244 | 146.820592 | **146.814418** |
| 64 | 1,095.553649 | 1,093.075885 | **1,094.314767** |

Do not copy the one-user value into a headline, comparison table, projection,
or external submission. The one-user shape requests eight speculative tokens by serially reusing the
checkpoint's one publisher MTP layer. At two through 128 active requests the
same service uses one speculative token. R15 and R16 each passed 512/512
synchronized c64 exact-answer requests, 7/7 sequential cases, 8/8 repeat
stability, exact frozen-baseline comparison, complete token capture,
cache-zero, and cross-task output isolation.

The selected service requires both the active-width GDN kernel patch and the
active-lookahead Mamba allocation patch. Build the existing MTP1 kernel and
W8A16 image first, then:

```bash
BUILD_ROOT=/path/to/new-active-width-build \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-dynamic-mtp-active-width-kernel-image.sh

repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-w8a16-dynamic-mamba-image.sh
```

Launch and validate it with new cache/result directories:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-dynamic-mtp-cache \
MAX_MODEL_LEN=1024 MAX_NUM_SEQS=1 MAX_NUM_BATCHED_TOKENS=1024 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-dynamic-mtp-server.sh

OUT_DIR=/path/to/new-dynamic-mtp-attempt \
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-dynamic-mtp.sh
```

The lab-validated overlay image ID is
`sha256:2b79af686423379e4418aafa92d72e2248e8d09fabe609284dc7e29190cb8cd6`.
If a local rebuild produces a different image ID, inspect and preserve its
labels and pass that exact value as `EXPECTED_IMAGE_ID`; do not disable the
patch/source checks. See the
[replication result](../../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-fp8-w8a16-dynamic-mtp8-r16-replication-result.md)
and [structured summary](../../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-fp8-w8a16-mtp8-dynamic-mtp1-r16-summary.json).

This is a 256-token short-context service. No 32K dynamic-MTP result is
claimed, inferred, or extrapolated.

MTP9 was also measured directly at `158.602110 tok/s` for one user, but the
same service fell to `889.607586 tok/s` at c64 and failed its preregistered
aggregate-retention gate. It is preserved as a negative rather than spliced
into the selected MTP8 profile; see the
[MTP9 result](../../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-fp8-w8a16-dynamic-mtp9-r17-negative.md).
An exact 64-slot recovery treatment retained the same 4,062-token KV capacity
and fell further to `806.950345 tok/s` at c64; see the
[p64 negative](../../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-fp8-w8a16-dynamic-mtp9-p64-r18-negative.md).

## Optimized block-W8A16 profile

The lab's default-off block-W8A16 overlay is now the fastest quality-qualified
official-FP8 profile in this guide. It uses the FP8 weights unchanged while
keeping activations in FP16 for the existing XPU W8A16 GEMM primitive.

| Measured profile | Default-off | W8A16 overlay | Patch-only change |
| --- | ---: | ---: | ---: |
| one fresh user, 40 prompt + 128 output tokens | 21.872717 tok/s | **35.011369 tok/s** | **+60.07%** |
| 128 active users, aggregate decode | 860.460981 tok/s | **1,112.570323 tok/s** | **+29.30%** |

The c128 headline is the median of conditioned repeats 2-5 on one server. All
four included repeats returned 16,384 completion tokens with cache zero and
passed output isolation. The same endpoint passed 7/7 sequential exact cases,
eight identical sequential repeats, and 1,024/1,024 concurrent semantic
canaries. Greedy token identity varies with batch shape, so this is an
output-isolation-qualified shape variant, not a universal token-exact claim.

This short-context p128 profile has a 256-token service limit. It is separate
from the directly measured one-slot W8A16 2K-32K profile below; no workload is
inferred between the two services.

### Build the exact overlay

The build helper creates a dedicated checkout at vLLM commit
`ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9`, applies the
[repository patch](../../experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-block-w8a16-20260826.patch),
and overlays only the modified integration file onto the pinned upstream XPU
image:

```bash
BUILD_ROOT=/path/to/dedicated-build-root \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-w8a16-image.sh
```

The locally validated overlay image ID was
`sha256:ced02d013fe356faac513f2598b4da1f11fd8e20a9bb8fb9a443564fda460556`.
Docker rebuild identities can vary with builder metadata, so verify that the
installed `xpu.py` SHA-256 is
`7c36e4a8dab4bfc06b1d5be2d8466e8cdc94099dd5409424fecc6dd8ffc2c208`.

### Launch and validate the p128 profile

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-w8a16-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-concurrency-server.sh

OUT_DIR=/path/to/new-w8a16-attempt \
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-concurrency.sh
```

The benchmark wrapper captures a fresh single-user row, one excluded c128
conditioning batch, five measured c128 batches, the sequential suite, and
1,024 concurrent semantic cases. It refuses to overwrite an existing result
directory. See the [result note](../../experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-block-w8a16-tp2-p128-result.md),
[structured summary](../../experiments/qwen38-27b-b70/data/2026-08-26-qwen38-fp8-block-w8a16-tp2-p128-summary.json),
and [raw receipts](../../experiments/qwen38-27b-b70/data/qwen38-fp8-block-w8a16-tp2-p128-20260826-r1/).

## Legacy publisher-MTP1 high-concurrency profile

Qwen's official checkpoint includes `mtp.safetensors`. With one speculative
token, the W8A16 dispatch, and the corrected mixed-batch XPU GDN kernel, the
separate MTP1 service measures:

| concurrent users | aggregate tok/s | per-user tok/s | samples |
| ---: | ---: | ---: | ---: |
| 8 | 351.033829 | 43.879229 | 1 |
| 16 | 585.525296 | 36.595331 | 1 |
| 32 | 800.459961 | 25.014374 | 1 |
| 64 | **1,091.642460** | 17.056913 | median of 3 |
| 128 | 1,075.634155 | 8.403392 | median of 3 |

This scoped service improves the same-c64 MTP0 median by `19.67%`. MTP0
remains `3.32%` faster at its separate c128 optimum, so these are two
deployment modes, not values to splice into one unnamed profile. The old
single-response 61.699580 tok/s observation is intentionally omitted here: it
is not the varied-prompt strict headline. The historical 51.918757 tok/s R32
result remains historical; the current independently qualified strict headline
is 51.808087 tok/s. This concurrency profile has a 256-token service limit and
no measured 32K point.

The old kernel aborts when continuous batching mixes MTP decode with new
prefills. The selected kernel commit
[`1e90ffa672`](https://github.com/vllm-project/vllm-xpu-kernels/commit/1e90ffa672ba02f17a909da11838a4c55b199783)
contains upstream mixed-path fixes
[`4054175`](https://github.com/vllm-project/vllm-xpu-kernels/commit/40541752f4f7fdef3cab471038c775e3f8d42838)
and [`1d5b4f5`](https://github.com/vllm-project/vllm-xpu-kernels/commit/1d5b4f5e5ddd8da96ea23c76d7e7421b00083fdb).
Build the exact kernel image and then the W8A16 overlay:

```bash
BUILD_ROOT=/path/to/dedicated-kernel-build \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-mtp1-kernel-image.sh

BUILD_ROOT=/path/to/dedicated-w8a16-build \
BASE_IMAGE=neural-download/vllm-openai-xpu:f01e-kernel-1e90-r13 \
IMAGE=neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-r122 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-w8a16-image.sh
```

The kernel helper downloads and digest-checks the exact successful upstream
wheel from the lab's durable GitHub release. It uses `curl` and requires no
GitHub CLI authentication. The mirror records the upstream run/artifact
provenance and does not claim authorship. Its pinned image definition is
[`Dockerfile.fp8-kernel-1e90-r13`](../../experiments/qwen38-27b-b70/docker/Dockerfile.fp8-kernel-1e90-r13).
Launch and validate MTP1:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-mtp1-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-mtp1-server.sh

OUT_DIR=/path/to/new-mtp1-attempt \
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1.sh
```

The selected service uses `max_num_batched_tokens=512`. The exact validation
passed 7/7 sequential semantic cases, 8/8 repeat stability, and a 512/512 c64
concurrent semantic canary. See the [result note](../../experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-block-w8a16-mtp1-tp2-result.md)
and [structured summary](../../experiments/qwen38-27b-b70/data/2026-08-26-qwen38-fp8-block-w8a16-mtp1-tp2-summary.json).

### Fixed MTP2 one-layer reuse is superseded

The checkpoint has one publisher MTP layer. Asking vLLM for two speculative
tokens serially reuses that layer; it is not a native MTP2 checkpoint. The
bounded screen measured `83.646518 tok/s` for one user, but only `737.190110
tok/s` at c64 versus MTP1's `1,091.642460`, and MBT768 fell to `712.790232`.
The fixed-width result remains useful negative evidence, but the selected
dynamic launcher above uses MTP8 for one user and falls back to MTP1 under
concurrency. The exact positive and negative boundaries are in the
[MTP2-reuse result](../../experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-block-w8a16-mtp2-reuse-result.md).

## Captured result

- median decode after TTFT: **`21.708532 tok/s`**
- median wall rate: `19.624649 tok/s`
- median TTFT: `626.227 ms`
- five unique p512/g128 requests; all completed 128 tokens and reported
  `cached_tokens=0`
- decode CV: `0.0738%`
- eager control: `17.097358 tok/s`; the captured size-one graph improved it
  by about `26.97%`

This is slower than the repository's GGUF Q8_0 TP2 record (`36.772932 tok/s`)
and Q4_K_M record (`49.717503 tok/s`). Its value is a working, pinned official
FP8/vLLM baseline and a clean starting point for XPU GDN and collective work.

## Quality boundary

The final graph run passed all seven exact semantic cases, eight identical
repeat runs, and a 3,829-token needle test. Every checked output hash matched
the established Q8_0 oracle, including the Python-result canary (`14`). Prefix
caching was disabled and every quality/benchmark request reported zero cached
tokens.

Longer free-form benchmark continuations were not byte-identical between the
eager and graph modes, so this packet does **not** claim universal token-exact
equivalence for arbitrary prompts. The official FP8 target is quantized and
should not be described as lossless BF16.

## Exact identities

- model: [`Qwen/Qwen3.8-27B-FP8`](https://huggingface.co/Qwen/Qwen3.8-27B-FP8/tree/017b9c7af6b5689d5dd426a76e0bc077eb5ca20a)
- revision: `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`
- 66 Safetensors files, `30,866,866,928` bytes
- aggregate basename-sorted `sha256sum` manifest:
  `82fb8f84fa117c81c3e8639c4675709dfb667d70ddaa2fd097d35fc37d95453a`
- image: `vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f`
- vLLM: `0.27.2rc1.dev77+gac7509e2b`
- Torch: `2.13.0+xpu`

The image selected `XPUFp8BlockScaledMMKernel`. It used Qwen Triton kernels
for the Qwen3.8 GDN path; that fallback is the principal source-level
optimization opportunity.

## Exact 2K–32K service profile

A separate one-slot W8A16 service raised the configured capacity to 33,024
tokens and measured six exact prompt depths. It retained the same model,
overlay image, TP2 topology, FP16 activations/KV, target-only/MTP0 policy, and
size-one PIECEWISE decode graph; only the service capacity, active prompt
depth, one slot, and 4,096-token chunked-prefill batch identify this operating
profile. The default-off values are the earlier same-shape control.

| Exact prompt tokens | Default-off decode | W8A16 decode | W8A16 TTFT ms | W8A16 prompt proxy tok/s |
| ---: | ---: | ---: | ---: | ---: |
| 2,048 | 21.835160 | **35.201648** | 1,011.401 | 2,024.915 |
| 4,096 | 21.673278 | **34.756821** | 1,635.189 | 2,504.909 |
| 8,192 | 21.270146 | **33.592729** | 3,219.230 | 2,544.708 |
| 16,384 | 20.927452 | **32.830415** | 6,549.952 | 2,501.392 |
| 24,576 | 20.650133 | **32.046666** | 10,072.020 | 2,440.027 |
| 32,768 | 20.389854 | **31.489587** | 13,739.776 | 2,384.901 |

All six receipts passed exact prompt usage, 128 returned token IDs, cache-zero,
no-truncation, and no-context-shift gates. This is one fresh-server sample per
point using a grade-C repeated-token shape fixture; no point is interpolated or
extrapolated. The effective prompt proxy is `exact prompt tokens / measured
HTTP TTFT seconds`, including scheduling and first-token work. It is not a
server-only or kernel-only prefill rate.

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-w8a16-depth-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-depth-server.sh

PORT=18119 OUT_DIR=/path/to/new-w8a16-depth-result \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-depth.sh
```

See the [W8A16 structured evidence](../../experiments/qwen38-27b-b70/data/qwen38-fp8-block-w8a16-tp2-http-depth-20260826-r2/summary.json),
[combined result note](../../experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-block-w8a16-tp2-p128-result.md), and
[default-off control](../../experiments/qwen38-27b-b70/data/qwen38-fp8-tp2-http-depth-20260826-r1-attempt1/summary.json).

## Exact output-audited concurrency profile

A separate target-only/MTP0 service profile retained the same model, image,
TP2 topology, FP16 KV, prefix-cache policy, and size-one graph while fixing
maximum model length 4,096, maximum active sequences 64, and maximum batched
tokens 256. Its concurrency wrapper enables direct oneCCL P2P access; the
single-slot and depth profiles retain their captured P2P-off identity. Two
preregistered fresh-server attempts measured each point:

| concurrent HTTP users | aggregate tok/s | per-user tok/s | TTFT p50 / p95 ms | queued |
| ---: | ---: | ---: | ---: | :---: |
| 1 | 21.557059 | 21.557059 | 95.048 / 95.048 | no |
| 2 | 41.424196 | 20.712098 | 122.743 / 170.950 | no |
| 4 | 81.299381 | 20.324845 | 211.000 / 211.286 | no |
| 8 | 157.990884 | 19.748860 | 267.133 / 267.680 | no |
| 16 | 293.363030 | 18.335189 | 262.556 / 391.232 | no |
| 32 | 504.387101 | 15.762097 | 426.066 / 728.501 | no |
| 64 | 774.394144 | 12.099908 | 768.749 / 1,525.973 | no |

All responses returned 128 complete raw token IDs and zero cached prompt
tokens; no generated digest collided with a frozen sequential oracle belonging
to another base task. The worst aggregate range was `0.525%` and the worst
latency range was `4.404%`. Greedy output may vary with batch shape, so the
gate proves completion and output isolation rather than sequential token
identity.

The service scales through c64, and every published point is within its
configured active-slot limit. Reproduce one attempt with:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/vllm-concurrency-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-concurrency-server.sh

OUT_DIR=/path/to/new-attempt \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-concurrency.sh
```

Stop it with `docker stop -t 20 qwen38-fp8-tp2-concurrency`, launch a fresh
one, and use a different `OUT_DIR` for the second attempt. The
[qualified result](../../experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-confirmation-r10-result.md),
[structured aggregate](../../experiments/qwen38-27b-b70/data/2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-confirmation-r10-result.json),
[frozen preregistration](../../experiments/qwen38-27b-b70/data/2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-confirmation-r10-prereg.json),
[compact oracle](../../experiments/qwen38-27b-b70/data/qwen38-fp8-tp2-http-concurrency-oracle-pilot-20260826-r1-attempt1/oracle-digests.json),
and exact [request suite](../../experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json)
are all in this repository. No point is interpolated or extrapolated.

## Dependency closure

| Component | Status and exact dependency |
| --- | --- |
| Host platform | **Incomplete.** Observed on Ubuntu 24.04.4, kernel `7.0.0-28-generic`, Docker `29.1.3`, `intel-opencl-icd 26.22.38646.7-1~24.04~ppa1`, and `libze1 1.28.6-1~24.04~ppa1`. This records the working host; it is not yet a tested clean-host installer. |
| Accelerator toolchain | Supplied inside the digest-pinned vLLM XPU image named below; host Level Zero compatibility is still part of the missing platform gate. |
| Runtime source/image | `vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f`; vLLM and Torch versions are recorded below. |
| Project patches | **None.** This baseline intentionally uses the pinned upstream image without a repository patch. |
| Model | Publisher repository and immutable revision below; all 66 weight files are pinned in [`model-direct.json`](model-direct.json). |
| Configuration | [`run-server.sh`](run-server.sh) pins the two-card topology, precision, KV policy, graph size, context, cache behavior, memory bounds, and collective settings. |
| Execution | Run [`preflight.sh`](preflight.sh), launch with [`run-server.sh`](run-server.sh), exercise with [`bench.sh`](bench.sh), and stop with the command below. The image must already be pulled. |
| Validation | The [experiment note](../../experiments/qwen38-27b-b70/notes/2026-08-16-official-fp8-vllm-graph-tp2.md) and [structured result](../../experiments/qwen38-27b-b70/data/2026-08-16-official-fp8-vllm-graph-tp2.json) preserve the fixed quality and benchmark boundaries. Clean-host replay remains open. |

Intel's current host-side references are the
[Client GPU Linux installation guide](https://dgpu-docs.intel.com/driver/client/overview.html)
and [oneAPI 2026.1 system requirements](https://www.intel.com/content/www/us/en/developer/articles/release-notes/oneapi-toolkit/2026.html).
They are linked as upstream prerequisites, not claimed as a lab-tested install
recipe. Use the exact observed package versions above for comparison and keep
the clean-host gate open until the full preflight/server/strict-suite sequence
has been replayed on that installation.

The 2026-08-21 host/model preflight is preserved as
[`preflight-evidence-20260821.json`](preflight-evidence-20260821.json). It is
evidence for prerequisites and model identity only; it does not claim that the
container was relaunched or that clean-host certification passed.

## Download and verify

Download the exact Hugging Face revision into one directory. For example,
with a recent `huggingface-cli`:

```bash
huggingface-cli download Qwen/Qwen3.8-27B-FP8 \
  --revision 017b9c7af6b5689d5dd426a76e0bc077eb5ca20a \
  --local-dir /path/to/qwen3.8-27b-fp8

repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-model.sh \
  /path/to/qwen3.8-27b-fp8
```

First pull the exact runtime image if it is not already present:

```bash
docker pull vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f
```

Run the non-mutating preflight before serving:

```bash
IMAGE=neural-download/vllm-openai-xpu:qwen38-fp8-collective-work-wait-r15 \
IMAGE_CONTRACT_PROFILE=mtp0 MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/preflight.sh
```

The preflight checks the observed OS boundary, Docker access, groups, two DRM
render devices, memory, pinned image, and model. Model verification reads all
30.9 GB twice: once with `O_DIRECT` (or `dd iflag=direct`) and once through the
ordinary page-cache path. Every publisher LFS SHA-256, byte size, and the two
read paths must agree. It fails closed if cache bypass is unavailable. The
older [`verify-model.sh`](verify-model.sh) aggregate check remains for
diagnostics, but the launcher now requires direct verification.

## Start and benchmark

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/vllm-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-server.sh
```

The first start compiles 51 artifacts and took about 88 seconds locally. A
warm cache starts much faster, but reloading it briefly exceeded an 8 GiB host
cgroup; the launcher therefore uses the validated 9 GiB RAM / 12 GiB
RAM-plus-swap bounds. Do not remove the bounds on a 16 GB host.

After `/health` succeeds, benchmark from another terminal:

```bash
OUT=/path/to/result.json \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench.sh
```

To reproduce the distinct exact-depth profile, use:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/vllm-depth-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-depth-server.sh

OUT_DIR=/path/to/depth-result \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-depth.sh
```

The wrapper fixes the measured 33,024-token/one-slot/4,096-prefill profile.
Changing those values creates another operating profile and must not be
compared as though it were the same measurement.

For the current real-content depth audit, first create a matched-image MTP0
oracle. The fixture contains unrepeated technical prose, Python code, and
structured documentation at every measured depth; it is stronger than the
older single repeated-token shape fixture.

```bash
IMAGE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-fa-split-gdn-r50 \
EXPECTED_IMAGE_ID=sha256:41aec5da9b124497a9b5dbc6b38f17175bf923d930d5702b9913589f107802d4 \
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-mtp0-depth-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-mtp0-depth-server.sh

ARM=mtp0 OUT_DIR=/path/to/new-mtp0-real-content-depth-result \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-real-content-depth.sh
```

Stop that server, launch MTP1 from a separate empty cache, and require all 18
complete output-token arrays to match the MTP0 oracle:

```bash
IMAGE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-fa-split-gdn-r50 \
EXPECTED_IMAGE_ID=sha256:41aec5da9b124497a9b5dbc6b38f17175bf923d930d5702b9913589f107802d4 \
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-mtp1-depth-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-mtp1-depth-server.sh

ARM=mtp1 ORACLE_DIR=/path/to/new-mtp0-real-content-depth-result \
OUT_DIR=/path/to/new-mtp1-real-content-depth-result \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-real-content-depth.sh
```

Both launchers inherit the fail-closed final-image and deterministic
compiler/RMS/GDN/oneCCL settings, then fix 33,024 tokens, one slot, and
4,096-token chunked-prefill batches. The MTP1 depth launcher raises only its
container cgroup bounds to 12 GiB RAM / 16 GiB RAM-plus-swap; the 9/12 GiB
short-profile bounds caused measured swap thrashing while its second TP worker
loaded. Every 2K/4K/8K/16K/24K/32K value is
directly measured. The script performs cache-zero request gates and canaries
before and after the matrix; it refuses to pass MTP1 if any complete token
array differs from MTP0. The older `bench-w8a16-mtp1-depth.sh` remains only for
replaying historical R33 Grade-C shape evidence. The current audit contract is
frozen in the [R56 preregistration](../../experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-real-content-depth-r56-prereg.json).

The first diagnostic R56 matrix passed all 36 requests and all 18 MTP1/MTP0
complete-array comparisons. Median MTP1 decode remained between `49.990` and
`53.134 tok/s` across 2K-32K, versus `30.331`-`33.735 tok/s` for MTP0;
draft-token acceptance was `88.482%`. It is not yet a public replacement curve
because that boot contains an earlier GPU reset. See the
[diagnostic result](../../experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-real-content-depth-r56-diagnostic.md);
clean-boot fresh-server repeats remain mandatory. `MAX_NUM_BATCHED_TOKENS`
may be overridden for preregistered scheduler screens, but its default remains
the measured 4,096-token profile.

An R57 screen tested an 8,192-token scheduler/prefill budget across the same
18 cases. Exactness and decode non-inferiority passed, but the preregistered
8K-32K TTFT median improved only `0.231%` (required: `3%`) and the cgroup
recorded 2,811 memory-ceiling events. The candidate was rejected; keep 4,096.

A later size-one PIECEWISE XPU Graph screen remained 12/12 exact against the
matched MTP0 oracle, but measured `51.229844 tok/s`: 1.12% below the selected
graph-off headline and just below its preregistered 99% floor. It was rejected
before the long-depth stage. A bounded graph-off profiler then attributed
roughly 50-51% of device-kernel time to TP all-reduce and 45% to GEMM on both
ranks; profiler timings are diagnostic, not performance evidence. The next
implementation target is W8A16 GEMM/collective overlap or a lower-latency
two-card all-reduce, not another graph or scheduler toggle. See the [R58 negative](../../experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-xpugraph-r58-negative.md)
and [R59 profiler note](../../experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-profiler-r59.md).
See the [R57 result](../../experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-prefill-budget-r57-result.json).

R60 then kept compiled all-reduce opaque while preserving the accepted clone
and explicit completion wait. It passed 12/12 strict and 18/18 depth exactness,
but measured `51.756541 tok/s` short and a `-0.014%` median change across
2K-32K. The treatment is robust but neutral, so it remains default-off. See the
[R60 result](../../experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-compiled-allreduce-r60-negative.md).

R61 recorded exact operator shapes on the accepted image. Every TP collective
was FP16 `[2,5120]` (20 KiB). Three isolated repeats found no benefit from
raising the oneCCL low-latency threshold, while two-shots was consistently
slower, so neither setting was promoted. The same trace identified separate
full-vocabulary FP16 projections for the one-row drafter and two-row verifier;
the next candidate targets only the drafter and leaves verifier computation
unchanged. See the [R61 shape report](../../experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-shape-profiler-r61.md).

R62 then quantized only the one-row MTP draft vocabulary projection to
group-128 W4A16. It leaves the two-row FP16 target verifier projection
unchanged and is default-off. Two fresh-cache diagnostic servers measured
`54.507697` and `53.976404 tok/s`; all 24 complete arrays matched the MTP0
oracle, candidate repeat determinism was 12/12, cache use was zero, and
canaries passed. An 18-case prose/code/document depth matrix remained exact
through 32K and measured `52.279 tok/s` there. This is a retained candidate,
not a new public headline: the boot contained an earlier GPU reset, so the
preregistered two-server clean-boot replay is still required. Build with
[`build-draft-int4-r62-image.sh`](build-draft-int4-r62-image.sh), launch with
the repository wrapper documented in the [R62 report](../../experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-draft-int4-r62-diagnostic.md), and run
`./verify-public-source-closure.sh` first.

The complete third-party build path is explicit. First build the public pinned
stack under the exact base tag R62 expects:

```bash
FINAL_IMAGE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-fa-split-gdn-r50-reprocheck-r55c \
BUILD_ROOT=/path/to/new-pinned-stack-build \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-pinned-mtp1-stack.sh

docker image inspect \
  neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-fa-split-gdn-r50-reprocheck-r55c \
  --format '{{.Id}}'
```

Use the printed ID as `EXPECTED_BASE_IMAGE_ID`; this admits an independently
built image only after the existing content/label contract passes:

```bash
EXPECTED_BASE_IMAGE_ID=sha256:replace-with-the-id-printed-above \
BUILD_ROOT=/path/to/new-r62-build \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-draft-int4-r62-image.sh

docker image inspect \
  neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-draft-only-int4-r62 \
  --format '{{.Id}}'
```

Then launch with the candidate ID printed by the second command and a genuinely
new cache directory:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-r62-runtime-cache \
EXPECTED_IMAGE_ID=sha256:replace-with-the-r62-id-printed-above \
  experiments/qwen38-27b-b70/scripts/run-20260901-qwen38-fp8-mtp1-draft-int4-r62-server.sh
```

In another terminal, use the same strict workload as the qualified lane:

```bash
OUT_DIR=/path/to/new-r62-strict-result \
PROFILE_LABEL=mtp1-draft-int4-r62 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh
```

These placeholders are intentional user-selected paths, not references to this
lab machine. R62 remains opt-in and does not affect the qualified launcher when
its environment flag is absent.

R63 then tested that candidate at c1-c64. It cleared the requested aggregate
floor (`1,080.851 tok/s` at c64), but only 55/64 complete c64 outputs matched
their sequential oracle. The identical FP16-draft control also first diverged
at c2 and matched 54/64 at c64, so R62 inherited rather than created the
underlying MTP1 batch-shape limitation. This does not waive correctness: R62
has no output-identical concurrency claim. When using
`bench-openai-concurrency-oracle.py` for an optimization qualification, pass
`--require-output-identity`; output isolation alone is not quality
equivalence. See the [R63 negative](../../experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-draft-int4-r63-concurrency-negative.md).

R64-R67 then localized that inherited limitation without relaxing the gate.
Global batch-invariant mode is unsupported by Qwen's GDN backend. A
target-head-only persistent kernel made c2 exact but cut median c2 throughput
to 36.003 tok/s. A cheaper local-shard near-tie repair passed a small c2 screen
but failed the full ladder (54/64 exact and 753.077 tok/s at c64). The decisive
logprob probe found an exactly tied global top two split across TP vocabulary
shards, which a per-rank margin cannot see. These are diagnostic, unpromoted
experiments; the qualified single-user recipe and headline remain unchanged.
See the [R67 report](../../experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-selective-head-batch-repair-r67-negative.md).

R68-R72 then tested the global repair directly. R68 changed a full-logits path
that greedy serving does not consume. R69 repaired the actual local-argmax
path, R70 forced ordinary M1 replay for every row, R71 used the proven
batch-invariant dot product for selected rows, and R72 forced that exact repair
for every target row. The same c2 token-96 mismatch survived every arm; the
forced exact path measured only about 12.758 tok/s. The production-shape drift
therefore begins before the target vocabulary head. These patches and results
are retained as diagnostic evidence, not as recipe dependencies. The public
R50/R62 launch chains and the qualified single-user value remain unchanged.
See the [R72 report](../../experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-global-exact-head-repair-force-r72-negative.md).

The launcher binds the endpoint to loopback, maps both `/dev/dri` devices, and
uses `ZE_AFFINITY_MASK=0,1`. Verify device enumeration before copying that
selector to a different host. Stop with `docker stop -t 20 qwen38-fp8-tp2`;
never interrupt the engine while graph initialization is still in progress.

## Deliberate settings

- `--tensor-parallel-size 2`
- `--dtype float16 --quantization fp8 --kv-cache-dtype auto`
- context 4,096; block size 64; max sequences 4; max batched tokens 256
- prefix caching disabled; text-only model path
- PIECEWISE graph capture limited to request size 1
- oneCCL direct send/receive, TCP loopback OFI, pidfd IPC, simple collective
  thresholds pinned high
- `CCL_TOPO_P2P_ACCESS=0` for the single-slot/depth identities; the concurrency
  wrapper selects `1`, which raised qualified c64 aggregate throughput 11.30%
- `FULL_DECODE_ONLY` was quality-clean but `1.618%` slower; retain PIECEWISE

The 2026-08-16 nightly (`8efa13b70`, XPU kernels `0.1.13.2`) was also
quality-clean at `21.723631 tok/s`, only `+0.070%` versus this pinned image.
That is noise-level, so the reproduction digest remains unchanged.
Enabling XPU's supported Q/K RMSNorm+RoPE compiler fusion was also neutral:
two medians bracketed the control at `+0.150%` and `-0.083%` while preserving
the oracle. It is intentionally absent from the launcher.
Native BF16 activation/KV arithmetic was oracle-clean but decode-neutral at
`21.708409 tok/s` (`-0.0006%`) with slower TTFT, so the captured FP16 setting
remains the reproducible performance identity.
Reducing maximum sequences to one was also neutral (`21.717535 tok/s`,
`+0.041%`), and omitting the RNG seed from otherwise identical temperature-zero
requests was slightly slower (`21.659428 tok/s`, `-0.268%` against its loaded
seeded control). Keep the default capacity of 4 and explicit benchmark seeds.

vLLM warns that XPU Graph is officially supported only for single-GPU use.
This TP2 graph result is therefore experimental and stays fail-closed behind
the exact local quality gate. See the
[full experiment note](../../experiments/qwen38-27b-b70/notes/2026-08-16-official-fp8-vllm-graph-tp2.md)
and [structured result](../../experiments/qwen38-27b-b70/data/2026-08-16-official-fp8-vllm-graph-tp2.json).
