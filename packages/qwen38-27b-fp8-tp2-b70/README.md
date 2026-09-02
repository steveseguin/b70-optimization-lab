# Qwen3.8 27B FP8 — two-B70 candidate package

This package uses Qwen's official FP8 model and digest-pinned vLLM XPU
containers on two Intel Arc Pro B70 32 GiB cards.

> **Strict MTP1 qualified: `51.808087 tok/s`.** Two fresh-server attempts
> measured `51.796549` and `51.819625 tok/s`. Two matched-image MTP0 controls
> measured `33.722035` and `33.745004 tok/s`, making the MTP1 gain `53.5804%`.
> Every attempt ran the complete 12-prompt/six-class natural-512 workload with
> cache zero and independent canaries; both within-arm comparisons and all
> four target/candidate comparisons matched all 12 complete token arrays. A
> clean-source rebuild then replayed at `51.579521 tok/s` from a new image and
> empty compile cache, with 12/12 exact arrays against both MTP1 and MTP0. The
> package remains `candidate` until an independent host-driver/Docker
> installation replay. See the
> [fresh-cache audit](../../experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-public-reproduction-audit.md).

> **Determinism boundary:** the exactness result above is scoped to the fixed
> suite's 48-78-token prompts. A later operator sweep and endpoint probe found
> repeat-nondeterministic W8A16 logprobs when a prefill step contains roughly
> 168-256 rows; five repeats at each of 168, 200, 224, and 250 prompt tokens
> produced five distinct logprob arrays. Token IDs happened to remain stable
> for the tested 64-token completions, which is not a universal determinism
> guarantee. Greedy concurrent output also remains batch-shape-dependent. See
> the [CR1 review](../../experiments/qwen38-27b-b70/notes/2026-09-02-qwen38-fp8-mtp1-c2-identity-review-kernel-census-cr1.md).

The old `58.391033 tok/s` dynamic-MTP center used only a 128-token output cap,
and the `146.814418 tok/s` result used a selected 40-token fixture. Neither is
a headline. The LocalMaxxing submission
[`cmtb5n45n0021qq01n13vly2h`](https://www.localmaxxing.com/runs/cmtb5n45n0021qq01n13vly2h)
was premature and withdrawal is recommended. Static MTP1 is now qualified by
the newer fresh-cache audit; deeper dynamic MTP remains withheld.
The replacement strict result is approved on LocalMaxxing as
[`cmtim8s0d04etp401560ene6k`](https://www.localmaxxing.com/runs/cmtim8s0d04etp401560ene6k),
bound to the repository qualification attestation by SHA-256.

That is a tested boundary, not an uninvestigated blank. The bounded R34-R38b
campaign exercised full strict replay, serial native GDN, serial packed
block-FP8, global batch-invariance declaration, and progressive serial
FlashAttention with and without its redundant causal mask. Static MTP1 became
target-exact, but every dynamic-MTP8 treatment still diverged from the
qualified target. None of those diagnostic rates is publishable. The
[structured closeout](../../experiments/qwen38-27b-b70/data/2026-08-28-qwen38-fp8-dynamic-exactness-r34-r38b-summary.json)
preserves the attempts and immutable receipts.

The recipe and independent workload evidence remain useful. The target-only
block-W8A16 service measured `1,112.570323 tok/s` aggregate at 128 active
short requests, with explicit output-isolation and semantic gates. A separate
33,024-token target-only profile measured `31.489587 tok/s` decode at an exact
32K prompt with `13.740 s` TTFT. The historical deterministic-Inductor MTP1 profile
also directly measured 32K at **`46.636241 tok/s`** with `10.487 s` TTFT and
matched all six then-recorded MTP0 depth-oracle token arrays. These are scoped
Grade-C capacity/context results, not replacements for the strict
varied-prompt single-user headline.

The package also retains a separate legacy publisher-MTP1 short-context
aggregate profile at `1,091.642460 tok/s` for 64 active requests. It is not a
substitute for a strict single-user result and uses the older concurrency
service configuration. The MTP1 32K value above comes from the historical
deterministic-Inductor profile and is not borrowed from the MTP0 or concurrency
lane. That compiler setting does not override the W8A16 medium-prefill
determinism boundary above. It is not proof that a fresh third-party build
passes today's exactness gate.

The checkpoint has one publisher MTP layer. Experimental serial reuse to MTP8
is preserved under `experiments/` for mechanism research, but its selected
fixture must not be used as a public speed claim. See the corrected
[screening note](../../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-fp8-w8a16-mtp8-realistic-cold-result.md).

> **Status: candidate, not a beginner install guide.** The exact model,
> container, configuration, commands, and evidence are present. A clean source
> rebuild and strict replay now pass on the lab host. Installation of the Intel
> driver and Docker prerequisites has not yet been replayed on an independent
> host, so this package does not install or modify host drivers.

The technical source of truth is the
[`reproduction guide`](../../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md).
The machine-readable front door is [`package.json`](package.json).

The latest default-off optimization candidate moves only the MTP drafter's
vocabulary projection to INT4 while keeping target verification FP16. It
passed strict and 2K-32K exact-output diagnostics at a `54.242051 tok/s`
two-server center, but it is deliberately not the package headline until the
pre-registered clean-boot replay passes. The complete build, patch, launcher,
and evidence chain is in the [R62 report](../../experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-draft-int4-r62-diagnostic.md).
Its first c64 diagnostic reached `1,080.851 tok/s`, but failed strict
sequential-oracle identity at 55/64. The matched FP16-draft control also failed
(54/64), proving an inherited MTP1 batch-shape limitation rather than an R62
first regression. Neither result changes the public concurrency curve; see the
[R63 negative](../../experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-draft-int4-r63-concurrency-negative.md).

## Who built what

**neural.download lab — integrated and optimized:** B70/XPU integration,
graph and quality validation, direct-I/O model verification, direct-P2P
concurrency tuning, block-W8A16 dispatch, deterministic compiler-visible GDN
state, explicit oneCCL completion ordering, dynamic-width GDN repair, and
active Mamba-state allocation. Against the exact same
overlay image with its environment gate omitted, W8A16 improved fresh
single-user decode from `21.872717` to `35.011369 tok/s` (+60.07%) and c128
aggregate decode from `860.460981` to `1,112.570323 tok/s` (+29.30%). See the
[W8A16 result](../../experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-block-w8a16-tp2-p128-result.md)
and the earlier [baseline evidence](../../experiments/qwen38-27b-b70/notes/2026-08-16-official-fp8-vllm-graph-tp2.md).
The active state allocation and deeper speculative screens remain diagnostic
mechanism evidence. None of their selected-fixture singleton rates is a
package headline. The incomplete 128-cap varied-prompt repeat measured
`58.537756`/`58.244309 tok/s`; it remains a screening result pending the
compliant 512-cap two-server suite and independent quality/determinism gate.
The original compliant matrix measured: W8A16 MTP0
`34.772270`/`34.740755 tok/s`, MTP1 measured
`55.760069`/`55.782147 tok/s`, and dynamic MTP8 measured
`68.049727`/`62.432362 tok/s`. All remain diagnostics because their paired
complete outputs matched only `8/12`. The later deterministic compiled MTP0
repair qualified at `34.025180`/`34.038013 tok/s` with `12/12` exact outputs.
The later packed-RMS and deterministic-Inductor campaign measured MTP1 at
`51.606902`/`52.230611 tok/s`, with `12/12` exact outputs inside that campaign.
The first 2026-09-01 replay showed that result was not stable under the old
compiler contract. The final R53/R54 matrix encoded determinism inside vLLM's
compile configuration and used the same R50 image for target and candidate.
It qualified MTP1 at `51.808087 tok/s` with 12/12 exact arrays in all four
target/candidate comparisons.

A later bounded MTP9 screen reached `158.602110 tok/s` for one user but only
`889.607586 tok/s` at c64, failing its preregistered aggregate-retention gate.
Limiting that treatment to 64 scheduler slots did not change its 4,062-token
KV capacity and reduced c64 further to `806.950345 tok/s`. Both remain measured
negative evidence and are not the packaged default.

**vLLM XPU kernel contributors — upstream mixed-batch fix:** upstream commits
[`4054175`](https://github.com/vllm-project/vllm-xpu-kernels/commit/40541752f4f7fdef3cab471038c775e3f8d42838)
and [`1d5b4f5`](https://github.com/vllm-project/vllm-xpu-kernels/commit/1d5b4f5e5ddd8da96ea23c76d7e7421b00083fdb)
make concurrent MTP safe when speculative decode and newly arriving prefills
share a scheduler step. The old kernel aborts this workload; the integrated
fix reaches `1,091.64 tok/s` at c64. See the
[MTP1 result](../../experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-block-w8a16-mtp1-tp2-result.md).

## What you need

- x86-64 Ubuntu 24.04;
- two accessible Intel Arc Pro B70 render devices;
- at least 15 GiB host RAM and 20 GiB RAM plus swap;
- Docker access for the current user;
- about 31 GB for model weights plus working space for the vLLM cache.

The currently observed working host versions are recorded in the reproduction
guide. They are evidence, not yet a general compatibility promise.

For a clean host, use Intel's current
[Client GPU Linux installation guide](https://dgpu-docs.intel.com/driver/client/overview.html)
and check the [oneAPI 2026.1 system requirements](https://www.intel.com/content/www/us/en/developer/articles/release-notes/oneapi-toolkit/2026.html)
for the supported Ubuntu/client-GPU boundary. The container supplies the pinned
vLLM/Torch userspace, but the host must still expose working Xe/Level Zero
devices. We intentionally do not embed an untested `sudo apt` recipe here:
driver packages change independently, and this package has not yet completed a
clean-host installation replay.

## 1. Download the exact model

Choose paths appropriate for your machine; `/path/to/...` is deliberately not
a hidden lab default.

```bash
huggingface-cli download Qwen/Qwen3.8-27B-FP8 \
  --revision 017b9c7af6b5689d5dd426a76e0bc077eb5ca20a \
  --local-dir /path/to/qwen3.8-27b-fp8
```

Weights remain distributed by the model publisher. This repository stores the
immutable revision and all 66 publisher LFS identities, not a copy of the
weights.

## 2. Acquire the pinned runtime

```bash
docker pull vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f
```

Build the complete pinned kernel -> MTP0 -> MTP1 -> serial-attention -> rebuilt
GDN image chain with one command:

```bash
BUILD_ROOT=/path/to/empty-build-root \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-pinned-mtp1-stack.sh
```

The helper applies the exact
[W8A16 patch](../../experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-block-w8a16-20260826.patch),
[deterministic GDN patch](../../experiments/qwen38-27b-b70/patches/vllm-qwen38-xpu-deterministic-gdn-ba-state-20260828.patch),
and [compiled-state/oneCCL patch](../../experiments/qwen38-27b-b70/patches/vllm-qwen38-xpu-compiled-gdn-state-ccl-wait-20260828.patch),
then builds every repository-local Docker overlay through the exact R50 image
used by the qualifying matrix. The final kernel-only rebuild additionally pins
the oneAPI compiler line and verifies the rebuilt shared-library hashes. The
model weights are not
modified. The upstream kernel wheel is mirrored in a durable lab GitHub
release, retains its exact upstream build provenance, and is checked against
SHA-256 `f3d999060c11ad6db5b4033d50d19c6b665492380075480d041ec4ee58fdfeb6`.
Docker image IDs can vary between builders; the included
[`verify-image-contract.sh`](../../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-image-contract.sh)
checks installed file hashes and the kernel commit instead.

The first MTP1 layer is a small overlay on the MTP0 image. Rebuild that
intermediate layer after its prerequisite images already exist with:

```bash
BUILD_ROOT=/path/to/empty-mtp1-build-root \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-mtp1-rmsnorm-serial-image.sh
```

The helper applies the repository's
[packed Gemma RMSNorm patch](../../experiments/qwen38-27b-b70/patches/vllm-qwen38-xpu-gemma-rmsnorm-mtp1-serial-exact-r30-20260828.patch)
to pinned vLLM `ac7509e2b`, verifies the base image contents, and builds the
overlay. The one-command builder then applies the serial-attention source
overlay and rebuilds the GDN kernel with the two repository patches required
to reach the exact qualified R50 installed-content contract.

The legacy high-concurrency MTP1 profile additionally needs the pinned
upstream XPU-kernel artifact. Build the kernel image, then place the same W8A16
overlay on top:

```bash
BUILD_ROOT=/path/to/dedicated-kernel-build \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-mtp1-kernel-image.sh

BUILD_ROOT=/path/to/dedicated-w8a16-build \
BASE_IMAGE=neural-download/vllm-openai-xpu:f01e-kernel-1e90-r13 \
IMAGE=neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-r122 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-w8a16-image.sh
```

The selected dynamic profile adds two repository patches after that stage:

```bash
BUILD_ROOT=/path/to/new-active-width-build \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-dynamic-mtp-active-width-kernel-image.sh

repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-w8a16-dynamic-mamba-image.sh
```

The first patch makes the GDN kernel honor the active dynamic width; the
second allocates Mamba state from the active FCFS lookahead. Both build helpers
verify exact source and patch hashes before producing their overlays.

The kernel helper downloads the exact successful upstream wheel from the
durable repository release, checks its SHA-256 digest, and installs it over the
pinned official image. It requires `curl`, not GitHub CLI authentication. The
original upstream run and artifact identity remain documented in
[`kernel-wheel-build-info.txt`](../../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/kernel-wheel-build-info.txt).

## 3. Preflight

From the repository root:

```bash
IMAGE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-fa-split-gdn-r50 \
IMAGE_CONTRACT_PROFILE=mtp1-serial-fa-split-gdn \
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/preflight.sh
```

This reads the model twice and fails unless the publisher identities, direct
backing-store reads, and ordinary cache-path reads all agree. It also checks
the OS boundary, memory, Docker, user groups, two render devices, and exact
container contents. The final profile is verified by the installed file hashes
and kernel commit, not by a machine-local Docker image ID.

## 4. Launch, check, and benchmark

To reproduce the qualified MTP1 service:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-runtime-cache \
MAX_MODEL_LEN=1024 MAX_NUM_SEQS=1 MAX_NUM_BATCHED_TOKENS=1024 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-mtp1-strict-server.sh

OUT_DIR=/path/to/new-strict-attempt \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh
```

Run the same command against a second freshly started server and another empty
cache directory, then compare the complete token arrays with
[`compare-strict-attempt-outputs.py`](../../scripts/compare-strict-attempt-outputs.py).
One run alone is measurement evidence, not a promoted reproduction. Compare
two fresh-cache MTP1 attempts to each other and to two fresh-cache MTP0 target
attempts. The lab's R53/R54 matrix passes that gate; a third-party result should
still preserve all four attempts rather than quote a single favorable run.

For the matched-image MTP0 control, use the same R50 image and compilation
contract, with speculative decoding absent:

```bash
PORT=18124 MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-runtime-cache \
MAX_MODEL_LEN=1024 MAX_NUM_SEQS=1 MAX_NUM_BATCHED_TOKENS=1024 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-mtp0-strict-server.sh
```

After the health endpoint passes, capture one complete target attempt with:

```bash
OUT_DIR=/path/to/new-mtp0-attempt MODEL_NAME=qwen38-fp8 \
PROFILE_LABEL=mtp0-target \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-strict.sh
```

The current matched-image strict median is `33.733520 tok/s`. A newly built
image must still pass the same two-fresh-cache complete-output repeat gate
before it becomes a fresh reproduction claim.

To investigate the still-withheld dynamic-MTP lane under the same fixed
varied-prompt gate, launch its 1024-token-cap one-slot profile on another fresh
server with another empty cache directory and run:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-strict-suite-cache \
MAX_MODEL_LEN=1024 MAX_NUM_SEQS=1 MAX_NUM_BATCHED_TOKENS=1024 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-dynamic-mtp-server.sh

OUT=/path/to/new-realistic-suite.json \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-dynamic-mtp-realistic.sh
```

The corrected wrapper sends each of the 12 natural prompts exactly once, uses
a 512-token natural-completion cap, requires streamed token-ID timing, checks the conventional 99-interval
window, and fails unless every request reports `cached_tokens=0`. The prior
128-cap attempts are retained only as a corrected screening result. They do
not satisfy this command's final gate. See the
[audit correction](../../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-fp8-w8a16-mtp8-realistic-cold-result.md).

For the original official-image target-only baseline, in the serving terminal:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/vllm-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-server.sh
```

The first start may spend about 88 seconds compiling. In another terminal:

```bash
curl -fsS http://127.0.0.1:18087/health

OUT=/path/to/result.json \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench.sh
```

Read the reproduction guide before comparing results: its prompt shape,
quality boundary, zero-cache requirement, and experimental TP2 graph warning
are part of the result identity.

To reproduce the optimized 128-slot short-context profile instead, use the
dedicated wrapper and its full quality battery:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-w8a16-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-concurrency-server.sh

OUT_DIR=/path/to/new-w8a16-attempt \
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-concurrency.sh
```

That service is deliberately limited to 256 total tokens. Its 1,112.57 tok/s
aggregate result must not be presented as a 32K-context measurement.

For the distinct MTP1 interactive profile:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-mtp1-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-mtp1-server.sh

OUT_DIR=/path/to/new-mtp1-attempt \
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1.sh
```

This wrapper uses Qwen's bundled `mtp.safetensors`, one speculative token,
the upstream mixed-batch GDN fix, and `max_num_batched_tokens=512`. It records
single-user decode, an output-audited c8-c128 ladder, 7/7 sequential quality,
8/8 repeat stability, and a 512-request c64 semantic canary. Its measured peak
is c64; c128 is lower. It has no measured 32K point.

For the measured 2K through 32K operating profile, launch the distinct
one-slot service and run its exact-token sweep:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/vllm-depth-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-depth-server.sh

OUT_DIR=/path/to/depth-result \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-depth.sh
```

This profile is target-only/MTP0 with official block-FP8 weights, FP16
activations/KV, the W8A16 overlay, one service slot, 33,024-token capacity,
and 4,096-token chunked-prefill batches. Its repeated-token fixture
is shape evidence, not natural-prose latency evidence. The published prompt
rate is explicitly `prompt tokens / HTTP TTFT`; it includes scheduling and
first-token work and is not a kernel-only prefill rate.

For the historical deterministic-Inductor MTP1 2K-through-32K profile, use the dedicated
wrappers and a new empty cache:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-mtp1-depth-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-mtp1-depth-server.sh

OUT_DIR=/path/to/new-mtp1-depth-result \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-depth.sh
```

This fixes TP2, official FP8 plus W8A16, publisher MTP1, FP16/auto KV,
deterministic Inductor, XPU Graph off, 33,024-token capacity, one slot, and
4,096 max batched tokens. R33 measured `44.778323 / 54.932011 / 51.313834 /
51.289810 / 43.715435 / 46.636241 tok/s` at exact 2K/4K/8K/16K/24K/32K and
matched the MTP0 depth oracle 6/6. The 2K observation includes disclosed
one-time draft-kernel JIT; it was not replaced with a warmed retry. See the
[compact evidence](../../experiments/qwen38-27b-b70/data/2026-08-28-qwen38-fp8-w8a16-mtp1-exact-depth-r33-result.json).

For the distinct output-audited concurrency profile, start a new server with
64 active slots:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/vllm-concurrency-cache \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-concurrency-server.sh

OUT_DIR=/path/to/new-attempt \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-concurrency.sh
```

The concurrency wrapper enables direct oneCCL P2P access; the single-slot and
depth launch identities remain P2P-off. The published profile uses two such
attempts on separate fresh servers. Each request uses a unique short prompt,
returns 128 raw token IDs, and must pass cache-zero and cross-task
output-isolation checks. c1-c64 are active-service measurements. At c64,
aggregate throughput is `774.394144 tok/s` with median and p95 TTFT of
`768.749 / 1,525.973 ms`. See the
[qualified result](../../experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-confirmation-r10-result.md)
and [structured evidence](../../experiments/qwen38-27b-b70/data/2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-confirmation-r10-result.json).

## 5. Stop and recover

```bash
docker stop -t 20 qwen38-fp8-tp2
# If you launched the concurrency profile instead:
docker stop -t 20 qwen38-fp8-tp2-concurrency
# If you launched MTP1 instead:
docker stop -t 20 qwen38-fp8-block-w8a16-mtp1-tp2-p128
# If you launched the selected dynamic MTP profile:
docker stop -t 30 qwen38-fp8-w8a16-dynamic-mtp-tp2
```

Do not interrupt graph initialization. If startup fails, preserve the complete
container output and the preflight output before changing settings. Do not
silently reduce precision, context, memory policy, graph mode, or GPU count;
that creates a different lane. Full beginner recovery and clean-host install
instructions remain an explicit certification gap.
