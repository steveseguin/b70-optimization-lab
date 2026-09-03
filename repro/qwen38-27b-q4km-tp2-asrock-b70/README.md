# Reproduce Qwen3.8 27B Q4_K_M target-only TP2 on two B70s

> **Certification: `lab-replay`.** This replays the result on a host where the
> lab's source trees, binaries, caches, models, and topology already exist. It
> is not a portable install guide; see its `missing` entry in
> [`repro/guide-catalog.json`](../guide-catalog.json).

This recipe reproduces the 2026-08-15 two-card ASRock Arc Pro B70 result. It
uses Q4_K_M target weights with no MTP, DFlash, draft model, prompt reuse, or
other speculation.

## Promoted result

- Conventional 99-interval median: **`49.717503 tok/s`**
- Conventional p10: `49.122833 tok/s`
- Historical 100-event compatibility median: `50.219700 tok/s`
- Full-output after-TTFT median: `49.734644 tok/s`
- Full-output wall median: `48.802352 tok/s`
- TTFT median: `173.574 ms`
- Quality gate: 12/12 complete output hashes exact against the matched route,
  every `cached_tokens=0`, and both realistic/fresh-response gates passed.
- LocalMaxxing: approved as
  [`cmsy530c70cpwms01bl1sjk6g`](https://www.localmaxxing.com/en/runs/cmsy530c70cpwms01bl1sjk6g)
  on 2026-08-18.

The promoted increment fuses each device-local Q4_K dense gate and up mat-vec
with its SwiGLU consumer. A same-binary p64/n256/r5 A/B measured
`49.460273` off versus `50.271708 tok/s` on (`+1.6406%`); the cold endpoint
gain over the prior promoted route is `+1.7010%`. The result also retains the
previously accepted TP2 recurrent, attention, collective, and launch-fusion
stack transferred to Qwen3.8's unchanged Qwen3.5-family tensor shapes.

## Model and source

- model repository: <https://huggingface.co/ggml-org/Qwen3.8-27B-GGUF>
- revision: `0669b98607d47046c7c2b3f801011d54a08cfccf`
- file: `Qwen3.8-27B-Q4_K_M.gguf`
- bytes: `18,973,870,432`
- SHA-256:
  `31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34`

Restore the accepted source using
[`patches/qwen36-27b-q8-tp2-asrock-b70/README.md`](../../patches/qwen36-27b-q8-tp2-asrock-b70/README.md).
The required base remains mndodd commit
`4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`. Then apply the incremental
Q4_K TP2 fusion in
[`patches/qwen38-27b-q4km-tp2-asrock-b70/`](../../patches/qwen38-27b-q4km-tp2-asrock-b70/README.md).
Its decoded patch SHA-256 is
`0a27858525f6a402cf9c92d1b93daee0a80e2ffaef9137bf7bce784a549b58b6`.

Build with Intel oneAPI DPC++/C++ `2026.1.1.20260724` using the Release/BMG-G31
configuration in the linked patch packet. Never overlap an AOT build with a
loaded model on a 15–16 GiB host; retain `-j2` and the 6/8 GiB build scope.

## Run

Check the host, two-card access, decoded patch identities, matching binaries,
and model hash before launching:

```bash
cd /path/to/b70-optimization-lab
QWEN38_SOURCE_DIR=/path/to/patched/llama.cpp \
QWEN38_BUILD_DIR=/path/to/patched/llama.cpp/build-sycl-aot-bmg-g31-oneapi-2026.1.1 \
QWEN38_MODEL=/path/to/Qwen3.8-27B-Q4_K_M.gguf \
repro/qwen38-27b-q4km-tp2-asrock-b70/preflight.sh
```

By default the preflight requires the exact evidence binary hashes. A clean
source rebuild may set `QWEN38_ALLOW_REBUILT_BINARIES=1`, but that explicitly
changes the binary identity and therefore requires the complete benchmark and
12/12 output-oracle gate before its speed is compared with the headline.

Start the endpoint:

```bash
cd /path/to/b70-optimization-lab
QWEN38_SOURCE_DIR=/path/to/patched/llama.cpp \
QWEN38_BUILD_DIR=/path/to/patched/llama.cpp/build-sycl-aot-bmg-g31-oneapi-2026.1.1 \
QWEN38_MODEL=/path/to/Qwen3.8-27B-Q4_K_M.gguf \
repro/qwen38-27b-q4km-tp2-asrock-b70/run-server.sh
```

Then run the fixed cold suite from another terminal:

```bash
OUT=/path/to/result.json \
repro/qwen38-27b-q4km-tp2-asrock-b70/bench.sh
```

The reference host maps its two B70s as `level_zero:1,0` and addresses them as
`SYCL0,SYCL1`. Confirm enumeration before changing the selector. The launcher
uses equal TP2, F16 KV, FlashAttention, batch 1024, ubatch 256, one slot, cache
RAM zero, context checkpoints zero, and a bounded 8/10 GiB host-memory scope.

For prefill-heavy service work, Matthew Dodd's current settings compose with
this build and improved a p64 probe by `20.68%`, while reducing decode by
`0.28%`. They are optional and are not the decode record:

```bash
QWEN38_PREFILL_MODE=1 QWEN38_BATCH=8192 QWEN38_UBATCH=2048 \
  repro/qwen38-27b-q4km-tp2-asrock-b70/run-server.sh
```

The launcher unsets both prefill exports unless `QWEN38_PREFILL_MODE=1`, so a
previous shell cannot silently lower a later decode-record run.

The structured promoted result and exact output oracle are in
[`2026-08-15-q4km-tp2-q4k-glu-summary.json`](../../experiments/qwen38-27b-b70/data/2026-08-15-q4km-tp2-q4k-glu-summary.json).
The prior route remains preserved in
[`2026-08-15-q4km-tp2-target-summary.json`](../../experiments/qwen38-27b-b70/data/2026-08-15-q4km-tp2-target-summary.json).

## Exact active-context HTTP profile

The same exact package identity was subsequently measured through one native
HTTP slot at 2K/4K/8K/16K/24K/32K active prompt tokens. At 32K it delivered
**`44.437281 tok/s`** decode with **`35,058.738 ms`** TTFT. All six points
returned 128 token IDs, were cache-zero, and passed exact-length and context
gates. The fixture is grade C repeated-token shape evidence, not natural
prose; no point is interpolated or extrapolated. See the
[result note](../../experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-q4km-tp2-http-depth-r1-result.md)
and [complete evidence](../../experiments/qwen38-27b-b70/data/qwen38-q4km-tp2-http-depth-20260825-r1-attempt1/).

## Output-audited HTTP concurrency profile

Two preregistered fresh-server attempts measured 1/2/4/8/16/32/64 native
HTTP users on the same TP2 package. The median aggregate curve was
**`42.694 / 61.885 / 87.566 / 108.372 / 109.147 / 127.500 / 165.387 tok/s`**.
Every response returned all 128 raw token IDs with cache reuse disabled, and
no response collided with a frozen sequential oracle for another base task.
The worst pointwise run-to-run relative range was `1.717%`.

This qualifies output isolation and aggregate service capacity, not
batch-invariant text. Greedy token identity becomes batch-shape-dependent for
some requests. The pilot rates were excluded, every published point is the
median of exactly two new attempts, and no point is interpolated or
extrapolated. See the
[result note](../../experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-q4km-tp2-http-concurrency-r2-result.md)
and [structured result](../../experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-concurrency-r2-result.json).

### Exact-cache c64 increment

The original 1→64 curve above remains a single, internally consistent profile.
A later default-off, exact-arithmetic cache improved its c64 endpoint without
changing the one-user route. Two fresh candidate servers measured
`168.344562` and `167.933317 tok/s`; their **`168.138940 tok/s`** center was
`+4.45%` above same-binary controls centered at `160.981046 tok/s` and `+1.66%`
above the earlier public c64 result. Each candidate matched the frozen
64-request batch oracle 64/64 with prompt caching disabled.

After applying the prerequisite TP2 patches above, apply the
[exact Q4_K F16 cache patch](../../experiments/qwen38-27b-b70/patches/llama-qwen38-q4k-f16-exact-weight-cache-candidate-20260830.patch).
The [fixed-cohort admission patch](../../experiments/qwen38-27b-b70/patches/llama-server-fixed-inference-cohort-admission-20260830.patch)
is a validation aid: it makes the complete 64-request batch visible before GPU
work begins, so output identity can be replayed against a stable batch shape.
It is default-off and is not the source of the throughput gain.

For the qualified c64 validation profile, launch through
[`repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/run-server.sh`](../qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/run-server.sh)
with:

```bash
MTP_DEPTH=0 PARALLEL_SLOTS=64 CTX_SIZE=32768 \
BATCH_SIZE=2048 UBATCH_SIZE=256 FUSE_EXT_OVERRIDE=31 \
Q4K_F16_CACHE_FILTER=ffn_down \
QUEUE_SETTLE_MS=1000 QUEUE_SETTLE_TARGET=64 \
TARGET_DIR=/path/to/qwen3.8-27b-gguf \
DRAFT_DIR=/path/to/unused-draft-directory \
BUILD_DIR=/path/to/patched/build \
repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/run-server.sh
```

The cache uses approximately 6.5 GiB of additional device memory per B70. It
did not improve the cold 12-prompt single-user suite, which remained 12/12
output-exact, so it must not replace the package's one-user headline. Complete
preregistration, artifact hashes, controls, candidates, and qualification gates
are in the [result note](../../experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-q4km-tp2-exact-f16-cache-c64-result.md).

The subsequently qualified two-family setting is now the c64 record:

```bash
Q4K_F16_CACHE_FILTER=ffn_down,ffn_gate
```

Fresh candidates measured `175.798577` and `175.449010 tok/s`, for a
**`175.623794 tok/s`** center. Both matched the fixed batch oracle 64/64 with
cache zero. This is `+4.45%` over the one-family record and `+9.10%` over the
matched cache-off controls. Apply the
[comma-filter increment](../../experiments/qwen38-27b-b70/patches/llama-qwen38-q4k-f16-cache-comma-filter-20260830.patch)
after the base cache patch. The pair uses approximately 13 GiB of additional
device memory per card; exact peak VRAM remains to be captured. See the
[pair result](../../experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-q4km-tp2-exact-f16-cache-pair-c64-result.md).

### Exact-cache c96 endpoint

The same two-family cache was then measured at 96 pinned users. Two fresh
servers returned **`192.350949`** and **`192.332958 tok/s`**, for a qualified
**`192.341954 tok/s`** center. Each matched a separately frozen same-shape c96
control-batch oracle 96/96 with all 128 token IDs present, prompt caching off,
and no cross-base collision.

Use the c64 command above with these replacements:

```bash
PARALLEL_SLOTS=96 CTX_SIZE=32768 \
QUEUE_SETTLE_MS=1000 QUEUE_SETTLE_TARGET=96 \
Q4K_F16_CACHE_FILTER=ffn_down,ffn_gate
```

llama.cpp rounded the requested context pool to 49,152 tokens (96x512). Peak
used VRAM was approximately 30,480 MiB on GPU 0 and 30,354 MiB on GPU 1, so
this is a near-capacity profile. The control batch matched isolated sequential
references only 50/96; the result proves the cache changed no same-shape c96
outputs, not that greedy text is batch-invariant. See the
[c96 result](../../experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-q4km-tp2-exact-f16-cache-c96-result.md)
and [frozen batch oracle](../../experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-tp2-c96-batch-oracle-r14.json).
