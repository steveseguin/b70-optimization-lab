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
FP16 KV, and TP2. The R156 profile (row-invariant W8A16 kernel plus a
mixed-step GDN split) is lab-qualified at **`54.603 tok/s`** MTP1 (unchanged
FP16 target verifier) and **`33.314 tok/s`** MTP0. MTP0 output is byte-identical
to a single request through 64 concurrent users, MTP1 through 16, and both are
repeat-exact at every tested prompt length; deeper dynamic MTP remains a
research lane.

## Mixed-step split R156 profile (qualified 2026-09-03)

R156 is the R139 image plus one Python patch on `vllm/_xpu_ops.py`: when a
GDN step carries prefill rows and decode rows in the same kernel call, the
XPU GDN kernel computes the decode rows on a different arithmetic path (one
float16 unit in the SSM state, found by the R155 operator census). With
`VLLM_XPU_GDN_SPLIT_MIXED=1` the wrapper runs such steps as separate pure
decode, pure prefill, and pure spec calls. One-user steps are never mixed, so
c1 output and speed are unchanged by construction; the patch is default-off
and adds launches only on mixed steps. Clean-boot promotion (`r156f`):

| arm | attempt | class-balanced decode | output gate |
| --- | ---: | ---: | ---: |
| R156 MTP0 | `mtp0-a` | 33.325915 tok/s | oracle |
| R156 MTP0 | `mtp0-b` | 33.301558 tok/s | 12/12 vs mtp0-a |
| R156 MTP1 | `mtp1-a` | 54.499691 tok/s | 12/12 vs sibling and mtp0-a |
| R156 MTP1 | `mtp1-b` | 54.706797 tok/s | 12/12 vs sibling and mtp0-a |
| R156 MTP1 center | **54.603244 tok/s** | — | **qualified** |
| R156 MTP0 center | **33.313736 tok/s** | — | **qualified** |

Determinism scope: five repeats at 100, 168, 200, 224, 250, and 300 prompt
tokens are exact on both profiles; the c1-c64 identity ladder is exact at
every level for MTP0 (64/64 at c64, reproduced on three servers: R156,
R160, R161 ladders and this promotion) and exact through c16 for MTP1 (c32
31/32, c64 56/64). The MTP1 residual is not in any censused kernel; see the
[R151-R162 note](../../experiments/qwen38-27b-b70/notes/2026-09-03-qwen38-fp8-c32-identity-source-census-r151-r162.md).
Aggregate rates are published only where identity holds: MTP0 through c64
(931.4 tok/s at c64), MTP1 through c16 (474.3 tok/s at c16); single server,
one pass per point.

### Build and run R156

Build R139 by either route above, then add the Python overlay (no compiler,
no binary change; the release binaries are R139's):

```bash
BUILD_ROOT=/path/to/empty-r156-build \
EXPECTED_BASE_IMAGE_ID=sha256:replace-with-your-r139-image-id \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-gdn-split-mixed-r156-image.sh
```

Launch and benchmark with the R156 wrappers, which export the split flag and
the patched module's digest for the image contract:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-runtime-cache \
EXPECTED_IMAGE_ID=sha256:replace-with-your-r156-image-id \
  experiments/qwen38-27b-b70/scripts/run-20260903-qwen38-fp8-mtp1-split-mixed-r156-server.sh

OUT_DIR=/path/to/new-strict-attempt \
MODEL_NAME=qwen38-fp8-block-w8a16-mtp1-split-mixed-r156 \
PROFILE_LABEL=mtp1-split-mixed-r156 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh

MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/another-new-runtime-cache \
EXPECTED_IMAGE_ID=sha256:replace-with-your-r156-image-id \
  experiments/qwen38-27b-b70/scripts/run-20260903-qwen38-fp8-mtp0-split-mixed-r156-server.sh

OUT_DIR=/path/to/new-mtp0-attempt \
MODEL_NAME=qwen38-fp8-block-w8a16-mtp0-split-mixed-r156 \
PROFILE_LABEL=mtp0-split-mixed-r156 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh
```

`publication-manifest.json` binds the R156 chain (build script, Dockerfile,
patch, validator, wrappers, evidence) by SHA-256. The R139 section below
remains valid: R139 and R156 produce identical c1 output, and the
LocalMaxxing record (`cmtkvle7a0428p701k0ttabyy`, 54.627 tok/s on R139)
stands for both.

## Row-invariant R139 profile (qualified 2026-09-02)

R139 is the R62 image with one file replaced: a rebuilt `_xpu_C.abi3.so`
whose oneDNN `fp8_gemm_w8a16` uses a fixed-K, row-invariant strategy
selector. At the operator level every production shape is bitwise
row-invariant, permutation-invariant, and repeat-exact for batch sizes
1-512. At the endpoint, on a clean boot:

| arm | attempt | class-balanced decode | output gate |
| --- | ---: | ---: | ---: |
| R139 MTP0 | `r147 mtp0-a` | 33.336950 tok/s | oracle |
| R139 MTP0 | `r147 mtp0-b` | 33.313729 tok/s | 12/12 vs mtp0-a |
| R139 MTP0 | `r147c mtp0-c` | 33.289052 tok/s | 12/12 vs mtp0-a |
| R139 MTP1 | `r147 mtp1-a` | 54.312987 tok/s | 12/12 vs sibling and mtp0-a |
| R139 MTP1 | `r147 mtp1-b` | 54.941585 tok/s | 12/12 vs sibling and mtp0-a |
| R139 MTP1 two-attempt center | **54.627286 tok/s** | — | **qualified** |
| R139 MTP0 three-attempt median | **33.313729 tok/s** | — | **qualified** |

Every attempt used the complete fixed 12-prompt/six-class natural-512 suite,
`cached_tokens=0`, canaries before and after, and a fresh empty compile
cache; both MTP1 servers logged the FP16-verifier marker on both ranks. The
same-image MTP0 oracle is regenerated for this kernel (its arithmetic differs
from the natural kernel by late near-tie tokens on 4 of 12 prompts, as any
reduction-order change must). Determinism scope, both profiles:

- five repeats at 100, 168, 200, 224, 250, and 300 prompt tokens: one token
  stream and one logprob array at every length (the R62 profile failed this
  at 168-250);
- c1-c64 identity ladder (64 sequential oracles, then 1, 2, 4, 8, 16, 32, 64
  concurrent users, 128 tokens each): every output byte-identical through
  c16 (R62 first missed at c2); c32 and c64 matched 30/32 and 55-58/64, so
  aggregate rates are published only through c16 (MTP1 497.4 tok/s, MTP0
  421.1 tok/s at c16). Raising the batch budget (R148) and chunking the FP16
  vocabulary head (R149) did not change that; the residual is a per-sequence
  kernel at 32+ sequences and is the next census target.

Evidence: [R147](../../experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-mtp1-fixed-k-regenerated-oracle-r147-result.json),
[R147c](../../experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-mtp0-fixed-k-probe-ladder-r147c-result.json),
[R148](../../experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-fixed-k-ladder-batched-2048-r148-result.json),
[R149](../../experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-lm-head-chunk-rows-r149-result.json),
[note](../../experiments/qwen38-27b-b70/notes/2026-09-02-qwen38-fp8-fixed-k-identity-ladders-r147-r149.md).

### 2K-32K real-content depth on R139 (R150, 2026-09-02)

Same protocol as R56/R62: unrepeated technical prose, Python, and structured
documents at exact active context, three requests per depth (median shown),
128 output tokens, cache zero, canaries before and after. MTP1 matched the
same-image MTP0 oracle on 18/18 complete arrays.

| active context | MTP1 decode | MTP1 TTFT | MTP0 decode | MTP0 TTFT |
| ---: | ---: | ---: | ---: | ---: |
| 2K | `54.811 tok/s` | `0.590 s` | `33.364 tok/s` | `0.587 s` |
| 4K | `55.448 tok/s` | `1.149 s` | `32.976 tok/s` | `1.131 s` |
| 8K | `54.139 tok/s` | `2.348 s` | `32.110 tok/s` | `2.290 s` |
| 16K | `53.048 tok/s` | `4.883 s` | `31.411 tok/s` | `4.773 s` |
| 24K | `52.882 tok/s` | `7.644 s` | `30.625 tok/s` | `7.455 s` |
| 32K | `51.929 tok/s` | `10.599 s` | `29.961 tok/s` | `10.313 s` |

Evidence: [R150](../../experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-fixed-k-real-content-depth-r150-result.json).

### Know your host before benchmarking

The single-user decode rate of this recipe is bound by host submission
latency, not by the cards: with the graph off, each token issues about
3,000 kernel launches and 130 two-card all-reduces one at a time. Two
probes, run inside the R139 image, tell you which host class you are on
before you spend an hour on the strict suite:

```bash
# per-launch host cost (one card)
docker run --rm --device /dev/dri:/dev/dri --group-add render \
  -e ONEAPI_DEVICE_SELECTOR=level_zero:0 --workdir /tmp --entrypoint python3 \
  -v $PWD/experiments/qwen38-27b-b70/scripts/qwen38-fp8-host-submission-latency-probe.py:/tmp/p.py:ro \
  neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-fixed-k-w8a16-r139 /tmp/p.py

# two-card all-reduce latency and exactness (both cards; same flags as run-server.sh)
docker run --rm --ulimit core=0 --device /dev/dri:/dev/dri --group-add render \
  --cap-add SYS_PTRACE --security-opt label=disable --ipc=host --shm-size=8g \
  -e ZE_AFFINITY_MASK=0,1 -e ONEAPI_DEVICE_SELECTOR=level_zero:0,1 -e VLLM_TARGET_DEVICE=xpu \
  -e CCL_ATL_TRANSPORT=ofi -e FI_PROVIDER=tcp -e FI_TCP_IFACE=lo -e CCL_ZE_IPC_EXCHANGE=pidfd \
  -e CCL_SEND=direct -e CCL_RECV=direct -e CCL_TOPO_P2P_ACCESS=1 \
  -e CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 \
  -e CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
  -v $PWD/experiments/qwen38-27b-b70/scripts/qwen38-fp8-tp2-allreduce-census.py:/tmp/ar.py:ro --workdir /tmp \
  --entrypoint python3 neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-fixed-k-w8a16-r139 \
  -m torch.distributed.run --standalone --nproc_per_node=2 /tmp/ar.py /tmp/ar.json
```

| probe value | publishing host (EPYC 9015, PCIe Gen5) | replay host (TR PRO 5955WX, PCIe Gen4) |
| --- | ---: | ---: |
| async launch, us | 3.1 | 5.2-6.2 |
| launch plus sync, us | 26 | 33 |
| two-card all-reduce at 2 rows, us | 13 | 48-51 |
| graph-off MTP1 / MTP0, tok/s | 54.6 / 33.3 | 28.9 / 18.6 |
| graph-on (sizes [1,2]) MTP1 / MTP0, tok/s | 51.2 (R58, MTP1 only) | 51.3 / 31.1 |

Factors that were measured and found to matter or not:

| factor | effect on the c1 rate |
| --- | --- |
| host single-thread speed and submission path (CPU generation, I/O die, PCIe generation) | sets the per-launch cost; the dominant factor with the graph off |
| two-card all-reduce latency (cards on one root complex, PCIe generation) | 130 collectives per token; 13 vs 48 us is the residual gap once the graph is on |
| XPU Graph capture (`VLLM_XPU_ENABLE_XPU_GRAPH=1`, capture sizes `[1,2]`) | removes most launch cost on slow hosts; 1.1% slower on the publishing host; identity ladder not yet run graph-on |
| CPU governor / EPP, pinning to one CCD, `iommu=pt`, ACS redirect, GuC 70.44 vs 70.72, ECC (off) | none to 2% |
| core count, host RAM above the 15 GiB minimum | none; the issue loop is one thread per process |

Outputs are unaffected by any of these: every strict, cache-zero, canary and
identity gate passed on both hosts.

### Independent host replay of R139 (four-B70 host, 2026-09-02)

The chain above was replayed from a fresh full clone on a second lab host
(Supermicro M12SWA-TF, AMD Ryzen Threadripper PRO 5955WX, PCIe Gen4, four
B70s; the launcher selects Level Zero devices 0 and 1). Every closure,
model, image-contract and strict-bench gate passed and the installed
extension digest matched `f912e12d...`. The decode rate did not transfer:
graph-off MTP1 measured `28.94 tok/s` and MTP0 `18.65 tok/s`, 1.8x below
the headline on both profiles, and the factor was uniform across all six
prompt classes. The publishing host is an EPYC 9015 (Zen 5, PCIe Gen5)
whose async kernel launch costs 3.1 us and whose two-card all-reduce costs
13 us; the replay host measured 5.2 us and 48 us. `iommu=pt`, ACS redirect,
the CPU governor, CPU pinning, ECC (off on both hosts) and the GuC firmware
version each changed nothing. On such a host the graph-off profile pays
about 130 exposed host round trips per token.

Enabling XPU Graph recovers most of the gap there: with
`VLLM_XPU_ENABLE_XPU_GRAPH=1` and `cudagraph_capture_sizes` `[1,2]`
(`max_cudagraph_capture_size` 2, so the MTP1 two-row verification step is
captured as well), the replay host measured MTP1 **`51.32 tok/s`** and MTP0
**`31.15 tok/s`** with the same strict workload, cache-zero and canary
gates; with `cudagraph_mode` `FULL_DECODE_ONLY` instead of `PIECEWISE` the
same arms measured `52.05` and `31.53 tok/s`. Those launch settings are
tracked as `run-w8a16-mtp1-strict-server-xpugraph.sh` and
`run-w8a16-mtp0-strict-server-xpugraph.sh`. The manifest-bound R139 launch
wrappers do not switch to them; run a graph variant by exporting the same
environment the R139 wrapper sets (`IMAGE`, `EXPECTED_IMAGE_ID`,
`EXPECTED_KERNEL_HEAD`, `CONTAINER_NAME`, `PORT`, `SERVED_MODEL_NAME`,
`MAX_MODEL_LEN`, `MAX_NUM_SEQS`, `MAX_NUM_BATCHED_TOKENS`,
`EXPECTED_XPU_EXTENSION_SHA256`, and for MTP1 the four
`VLLM_XPU_DRAFT_LM_HEAD_INT4*` values from
`run-20260901-qwen38-fp8-mtp1-draft-int4-r62-server.sh`) and invoking the
variant wrapper directly with `MODEL_DIR` and `VLLM_CACHE_DIR`. The qualified profile ships graph-off because on the publishing
host graph capture measured 1.1% slower (R58) and output identity against
the oracle has only been established there for the graph-off profile. On
the replay host every graph-on arm (MTP0 and MTP1, either capture set)
returned outputs identical to graph-off MTP0 on all 12 strict-suite
prompts; the c1-c64 identity ladder has not been run graph-on, so a
graph-on profile is not yet qualified. Record:
[note](../../experiments/qwen38-27b-b70/notes/2026-09-02-qwen38-fp8-r139-four-b70-host-replay.md),
[data](../../experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-r139-four-b70-host-replay.json).

### Build and run R139

Build the R62 chain exactly as in the R62 section below (public R55C parent
plus the R62 overlay), then add the R139 extension by one of two routes. The
binary route downloads the released `_xpu_C.abi3.so`, verifies its whole-file
digest `f912e12de1d79206221142c9a50af2aba70d2c77c735c9cd2d5d8d9def0740d1`
and its `.text`/`.rodata`/`.data`/`OFFLOAD_DEVICE_CODE` section digests, and
installs it over your R62 image; it needs no compiler:

```bash
BUILD_ROOT=/path/to/empty-r139-build \
EXPECTED_BASE_IMAGE_ID=sha256:replace-with-your-r62-image-id \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-fixed-k-w8a16-r139-published-image.sh
```

The source route clones vllm-xpu-kernels `1e90ffa672`, oneDNN `0e2a5bfeef`,
and sycl-tla `cd763790ad`, applies the four repository patches
(`vllm-xpu-kernels-qwen38-dynamic-active-width-serial-gdn-r35-20260828.patch`,
`vllm-xpu-kernels-qwen38-gdn-split-serial-gates-r50-20260901.patch`,
`onednn-qwen38-w8a16-fixed-k-align16-r137a-20260902.patch`,
`onednn-qwen38-w8a16-c-default-align-r137b-20260902.patch`), and compiles
inside the R62 image with the host's Intel oneAPI 2026.1 mounted read-only
(`/opt/intel/oneapi`, override `HOST_ONEAPI_ROOT`). It prints the same
extension digest when the toolchain matches:

```bash
BUILD_ROOT=/path/to/empty-r139-source-build \
EXPECTED_BASE_IMAGE_ID=sha256:replace-with-your-r62-image-id \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-fixed-k-w8a16-r139-image.sh
```

Launch and benchmark MTP1, then the matched MTP0 control, each with a new
empty cache directory and the served model name the wrapper registers:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-runtime-cache \
EXPECTED_IMAGE_ID=sha256:replace-with-your-r139-image-id \
  experiments/qwen38-27b-b70/scripts/run-20260902-qwen38-fp8-mtp1-fixed-k-r139-server.sh

OUT_DIR=/path/to/new-strict-attempt \
MODEL_NAME=qwen38-fp8-block-w8a16-mtp1-fixed-k-r139 \
PROFILE_LABEL=mtp1-fixed-k-r139 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh

MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/another-new-runtime-cache \
EXPECTED_IMAGE_ID=sha256:replace-with-your-r139-image-id \
  experiments/qwen38-27b-b70/scripts/run-20260902-qwen38-fp8-mtp0-fixed-k-r139-server.sh

OUT_DIR=/path/to/new-mtp0-attempt \
MODEL_NAME=qwen38-fp8-block-w8a16-mtp0-fixed-k-r139 \
PROFILE_LABEL=mtp0-fixed-k-r139 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh
```

Both routes were replayed on 2026-09-02: the binary route from the release
download and the source route from a clean clone of the committed tree each
produced extension digest `f912e12d...` bit for bit
([binary replay](../../experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-r139-public-binary-route-replay-result.json),
[source replay](../../experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-r139-clean-clone-source-rebuild-result.json);
the source build log is a release asset). Image IDs differ between builders;
the contract binds installed file digests.
Binaries, section digests, patches, build scripts, and the host package list
are in GitHub release
[`qwen38-fp8-tp2-r139-20260902`](https://github.com/steveseguin/b70-optimization-lab/releases/tag/qwen38-fp8-tp2-r139-20260902);
`publication-manifest.json` binds every file above by SHA-256 and
`verify-public-source-closure.sh` checks them. TP1 is not a qualified
configuration for this checkpoint; only TP2 on two B70s is published.

## Strict MTP1 qualification

The original four-arm R53/R54 matrix established the exact MTP0 oracle and a
`51.808087 tok/s` MTP1 incumbent. Clean-boot R119 then ran the R62 draft-only
INT4 treatment on two more fresh servers with separate empty compile caches.
Only the one-row draft vocabulary projection is INT4; target verification
remains FP16. Every arm used the complete fixed 12-prompt/six-class, natural
512-token suite:

| arm | attempt | class-balanced decode | output gate |
| --- | ---: | ---: | ---: |
| MTP0 | `r54a-r50` | 33.722035 tok/s | 12/12 vs sibling |
| MTP0 | `r54c-r50` | 33.745004 tok/s | 12/12 vs sibling |
| MTP1 | `r53a` | 51.796549 tok/s | 12/12 vs sibling and both targets |
| MTP1 | `r53b` | 51.819625 tok/s | 12/12 vs sibling and both targets |
| R62 MTP1 | `r119-a` | 54.622918 tok/s | 12/12 vs sibling and MTP0 oracle |
| R62 MTP1 | `r119-b` | 54.226288 tok/s | 12/12 vs sibling and MTP0 oracle |
| R62 two-attempt center | **54.424603 tok/s** | — | **qualified** |

All attempts reported `cached_tokens=0`, passed independent canaries, and used
natural EOS with a 512-token cap. The metric is the median of six prompt-class
medians over the 99 intervals between streamed output events 1-100 after TTFT.
R62 is `5.0504%` faster than the qualified MTP1 incumbent and `61.3369%` faster
than the `33.733520 tok/s` MTP0 center with no observed token change inside the
fixed suite. See the [R119 promotion](../../experiments/qwen38-27b-b70/notes/2026-09-02-qwen38-fp8-mtp1-draft-int4-r62-cleanboot-r119-promotion.md).

This exactness scope is not universal. The suite prompts contain 48-78 tokens.
Five repeated requests at each of 168, 200, 224, and 250 prompt tokens produced
five distinct logprob arrays, and the 168-token case produced two distinct
64-token streams. The 100- and 300-token controls were bitwise repeatable.
Roughly 168-256-row prefills and all token-identity concurrency claims remain
excluded until the W8A16 GEMM is repaired.

The repository build path was then exercised from a new pinned source checkout.
That R55C image measured `51.579521 tok/s` with a new compile cache, passed the
same workload and canaries, and matched 12/12 complete arrays against both R53A
MTP1 and R54A MTP0. Its rebuilt libraries use portable `$ORIGIN` RUNPATHs; the
builder verifies whole-file and code/data section hashes. See the
[clean-rebuild result](../../experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-clean-rebuild-r55c-result.json).

### Public R55C source and binary closure

The immutable
[`qwen38-fp8-tp2-r55c-20260901` release](https://github.com/steveseguin/b70-optimization-lab/releases/tag/qwen38-fp8-tp2-r55c-20260901)
contains the complete final patch chain, clean rebuilt
[`vllm_xpu_kernels` wheel](https://github.com/steveseguin/b70-optimization-lab/releases/download/qwen38-fp8-tp2-r55c-20260901/vllm_xpu_kernels-0.1.14.dev14%2Bg1e90ffa.d20260901-cp38-abi3-linux_x86_64.whl),
exact
[`_xpu_C.abi3.so`](https://github.com/steveseguin/b70-optimization-lab/releases/download/qwen38-fp8-tp2-r55c-20260901/_xpu_C.abi3.so),
exact
[`libgdn_attn_kernels_xe_2.so`](https://github.com/steveseguin/b70-optimization-lab/releases/download/qwen38-fp8-tp2-r55c-20260901/libgdn_attn_kernels_xe_2.so),
successful clean-build log, and oneAPI/runtime package inventories. The tracked
[`publication-manifest.json`](publication-manifest.json) binds every asset by
name, byte size, SHA-256, source commit, portable RUNPATH, and ELF/device-code
section hashes.

This release corrects a September 1 publication defect: the builder required
the split-GDN patch digest `40ca8c3f…`, while the old closure checker blessed a
malformed tracked copy at `08a3de4f…`. Two blank unified-diff context lines had
lost their required leading spaces. The canonical tracked and released patch
now hashes to `40ca8c3f…`, and the validator derives the contract from the build
script so those identities cannot silently disagree again.

For the authoritative clean source build, use `build-pinned-mtp1-stack.sh` as
shown below from the release-bound source commit:

```bash
git clone https://github.com/steveseguin/b70-optimization-lab.git
cd b70-optimization-lab
git checkout 8495574257dda583e19dd39278641477bfaa4e43
```

The publication manifest binds every build entrypoint at that commit by
SHA-256. To build the same public parent chain while avoiding compilation
of only the final GDN/XPU extension stage, use:

```bash
BUILD_ROOT=/path/to/new-r55c-stack \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-pinned-mtp1-published-r55c-stack.sh
```

That helper downloads the two public libraries, verifies their whole-file and
`OFFLOAD_DEVICE_CODE` hashes and `$ORIGIN` RUNPATHs, builds the final overlay,
and runs the image contract. No `/home/steve`, `/mnt/fast-ai`, private image,
or untracked file is required. Verify the entire publication packet at any time
with:

```bash
python3 tools/validate-recipe-publication.py \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/publication-manifest.json \
  --check-remote
```

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

Clone with full history. The verifier binds the manifest's immutable inputs
to source commit `8495574257dda583e19dd39278641477bfaa4e43`, so a
`git clone --depth 1` checkout fails with `absent from source commit`
errors even though every file is present; a normal clone (about 2 GiB of
history) passes.

The verifier checks that all final Dockerfiles, builders, and custom-op patches
are present and tracked, validates build-script digest contracts against the
publication manifest, and verifies the final patch hashes. The full builder
below applies every stage in order and the image-contract verifier checks the
installed libraries. Do not substitute the older R31 image for the final R50
image.

The 54.424603 tok/s qualification is a single-sequence, 1K allocation profile
(`MAX_MODEL_LEN=1024`), not a full-262K-context measurement. A server launched
with a 262K maximum context is useful, but it is not a like-for-like reproduction
of that headline. The separately measured historical 32K MTP1 point was
46.636241 tok/s and is explicitly Grade-C shape evidence.

Build the full dependency chain, then build and launch the selected R62 overlay
with portable caller-selected paths. The full-source
`build-pinned-mtp1-stack.sh` route compiles the final GDN/XPU extension stage
with the host's Intel oneAPI compiler: it requires `/opt/intel/oneapi/setvars.sh`
(override with `HOST_ONEAPI_ROOT`) on the build host, which is mounted read-only
into the build container. The public-binary
`build-pinned-mtp1-published-r55c-stack.sh` route has no host oneAPI
requirement. The base and candidate image IDs are
deliberately supplied by the caller so independently built content is checked
instead of assuming this host's Docker ID:

```bash
FINAL_IMAGE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-fa-split-gdn-r50-reprocheck-r55c \
BUILD_ROOT=/path/to/empty-build-root \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-pinned-mtp1-stack.sh

EXPECTED_BASE_IMAGE_ID=sha256:replace-with-built-base-id \
BUILD_ROOT=/path/to/empty-r62-build-root \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-draft-int4-r62-image.sh

MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-empty-runtime-cache \
EXPECTED_IMAGE_ID=sha256:replace-with-built-r62-id \
  experiments/qwen38-27b-b70/scripts/run-20260901-qwen38-fp8-mtp1-draft-int4-r62-server.sh
```

In another terminal, run the actual strict natural-512 workload—not the older
128-token concurrency screen:

```bash
OUT_DIR=/path/to/new-strict-attempt \
MODEL_NAME=qwen38-fp8-block-w8a16-mtp1-draft-int4-r62 \
PROFILE_LABEL=mtp1-draft-int4-r62 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh
```

`MODEL_NAME` must match the name the R62 wrapper serves
(`qwen38-fp8-block-w8a16-mtp1-draft-int4-r62`); the benchmark's default name
belongs to the older R50 MTP1 launcher and is not registered on an R62 server.
The script fails unless the full workload, cache-zero policy, and independent
canaries pass. It deliberately reports target/repeat parity as unevaluated for
a single attempt. A qualifying audit needs two new MTP1 attempts and two new
MTP0 attempts, all compared with
[`compare-strict-attempt-outputs.py`](../../scripts/compare-strict-attempt-outputs.py).

Launch the matched-image MTP0 control with the same final image and compiler
contract:

```bash
IMAGE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-fa-split-gdn-r50-reprocheck-r55c \
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
is 54.424603 tok/s from R62/R119. This concurrency profile has a 256-token service limit and
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
unchanged and is default-off in the parent image. Two fresh-cache diagnostic servers measured
`54.507697` and `53.976404 tok/s`; all 24 complete arrays matched the MTP0
oracle, candidate repeat determinism was 12/12, cache use was zero, and
canaries passed. An 18-case prose/code/document depth matrix remained exact
through 32K and measured `52.279 tok/s` there. Clean-boot R119 then measured
`54.622918` and `54.226288 tok/s`, centered at **`54.424603 tok/s`**. Both
attempts and both target comparisons were 12/12 exact, both GPU postflights
passed, and no new-boot Xe fault appeared. R62 is therefore the scoped
single-user headline. Build with
[`build-draft-int4-r62-image.sh`](build-draft-int4-r62-image.sh), launch with
the repository wrapper documented in the [R119 promotion](../../experiments/qwen38-27b-b70/notes/2026-09-02-qwen38-fp8-mtp1-draft-int4-r62-cleanboot-r119-promotion.md), and run
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
MODEL_NAME=qwen38-fp8-block-w8a16-mtp1-draft-int4-r62 \
PROFILE_LABEL=mtp1-draft-int4-r62 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh
```

These placeholders are intentional user-selected paths, not references to this
lab machine. The treatment remains default-off unless the R62 wrapper is used;
that wrapper is now the qualified single-user launcher.

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
experiments; at that stage they did not change the qualified single-user recipe.
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

R73-R77 then instrumented the execution path without changing model arithmetic.
R73 established that this production profile has no active XPU CUDAGraph replay
path. Piecewise compiled-segment tracing subsequently located the first
meaningful c1-versus-c2 difference at the output of
`gdn_attention_core_xpu` in decoder layer 1. Embedding, FP8/BA projection,
layer-0 GDN output, and the layer-1 `z` input were exact. Uninitialized
`empty_like` scratch bytes were explicitly excluded. R77 also proved packed
row ownership from token IDs and withdrew the earlier scheduler-based R75/R76
mapping. See the [R77 localization](../../experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-piecewise-boundary-localization-r77.md).

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
