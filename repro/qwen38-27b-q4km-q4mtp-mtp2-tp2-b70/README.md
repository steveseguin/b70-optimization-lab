# Qwen3.8 27B Q4_K_M + Q4_0 MTP2 on two Arc Pro B70s

> **Lab-validated candidate package.** Two fresh MTP2 servers measured
> `64.180644` and `64.293959 tok/s`; their median is **`64.237301 tok/s`**.
> The matched TP2/MTP0 oracle measured `49.787366 tok/s`, a **29.02%** gain.
> All 24/24 complete candidate arrays matched the unchanged target oracle.
> Clean-host Intel/oneAPI installation and source-build replay remain pending.

This is a separate deployment from both the
[two-card target-only package](../qwen38-27b-q4km-tp2-asrock-b70/README.md)
and the [one-card MTP2 package](../qwen38-27b-q4km-mtp2-tp1-b70/README.md).
Its target is split equally across two B70s; the 1.37 GB draft remains on the
first card. Do not transfer context or concurrency values between those
profiles.

## Exact downloads

```bash
huggingface-cli download ggml-org/Qwen3.8-27B-GGUF \
  Qwen3.8-27B-Q4_K_M.gguf \
  --revision 0669b98607d47046c7c2b3f801011d54a08cfccf \
  --local-dir /path/to/qwen38-target

huggingface-cli download unsloth/Qwen3.8-27B-GGUF \
  MTP/mtp-Qwen3.8-27B-Q4_0.gguf \
  --revision 4ca720788d1e01f1bff70c033e0d0028fd02e502 \
  --local-dir /path/to/qwen38-draft-root
```

Use `TARGET_DIR=/path/to/qwen38-target` and
`DRAFT_DIR=/path/to/qwen38-draft-root/MTP`. The exact target, draft, server,
and SYCL-backend hashes are in [`manifest.sha256`](manifest.sha256). Preflight
checks both model files using direct and ordinary reads.

## Source and required patches

Build into a new directory:

```bash
SOURCE_DIR=/path/to/new/llama.cpp-qwen38-tp2-mtp2 \
  repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/restore-and-build.sh
```

The builder pins the mndodd base at
`4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126` and verifies/applies the complete
measured stack in order:

1. [Full Intel SYCL lab TP2/DP4A2 stack](../../patches/qwen36-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-lab-tp2-dp4a2-20260815.diff.gz.b64).
2. [Qwen3.8 Q4_K_M TP2 increment](../../patches/qwen38-27b-q4km-tp2-asrock-b70/llama-cpp-q4k-mmvq-swiglu-tp2-20260815.diff.gz.b64).
3. [GDN state-I/O widening](../../patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-gdn-state-io-widen-20260821.diff.gz.b64).
4. [Convolution/QK widening](../../patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-conv-qk-widen-20260821.diff.gz.b64).
5. [QK source-shape widening](../../patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-qk-norm-rope-src-widen-20260821.diff.gz.b64).
6. [Memo hardening artifact](../../patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-q8out-rejected-memo320-20260821.diff.gz.b64); its rejected door remains disabled.

The measured `llama-server` and `libggml-sycl.so` hashes are enforced by
default. A clean rebuild may set `ALLOW_REBUILT_BINARIES=1`, but that is a new
runtime identity and must pass the complete paired validation below before its
speed is compared with this package.

## Preflight

```bash
cd /path/to/b70-optimization-lab
export TARGET_DIR=/path/to/qwen38-target
export DRAFT_DIR=/path/to/qwen38-draft-root/MTP
export BUILD_DIR=/path/to/new/llama.cpp-qwen38-tp2-mtp2/build-sycl-aot-bmg-g31

repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/preflight.sh
repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/verify-evidence.sh
```

The measured host maps its B70s with `ONEAPI_DEVICE_SELECTOR=level_zero:1,0`
as `SYCL0,SYCL1`. Do not assume another machine has the same enumeration;
confirm `sycl-ls` and adapt only as a separately validated topology.

## Paired replay: oracle first, then MTP2

Run a fresh target-only oracle:

```bash
MTP_DEPTH=0 PORT=18142 \
  repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/run-server.sh
```

In another terminal, run the complete suite once:

```bash
MTP_DEPTH=0 BASE_URL=http://127.0.0.1:18142 \
OUT_DIR=/path/to/fresh-tp2-mtp0 \
  repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/bench.sh
```

Stop the oracle with Ctrl-C and confirm `pgrep -x llama-server` is empty.
Start a new MTP2 server:

```bash
MTP_DEPTH=2 PORT=18142 \
  repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/run-server.sh
```

Then validate MTP2 against the fresh oracle:

```bash
MTP_DEPTH=2 BASE_URL=http://127.0.0.1:18142 \
OUT_DIR=/path/to/fresh-tp2-mtp2 \
ORACLE_JSON=/path/to/fresh-tp2-mtp0/performance.json \
  repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/bench.sh
```

Success requires the complete 12-prompt/six-class 512-cap suite, every cache
count zero, all four objective canaries, and `target_arrays_exact=12/12`.
Model residency and compiled kernels are valid steady state. Prompt/KV/
response caching, learned drafting, repeated fixtures, subsets, and warmed
continuations are not permitted. A speed printed by a failed gate is not a
result.

## Measured result

| deployment | fresh run | strict tok/s | exact to MTP0 |
| --- | ---: | ---: | ---: |
| TP2 Q4_K_M, no MTP | R1 | 49.787366 | oracle |
| TP2 Q4_K_M + Q4_0 draft, MTP2 | R1 | 64.180644 | 12/12 |
| TP2 Q4_K_M + Q4_0 draft, MTP2 | R2 | 64.293959 | 12/12 |

The primary metric is the median within each of six prompt classes and then
the median across class medians, measured over the 99 intervals between output
events 1–100 after TTFT. Both candidates also matched each other on all 12
complete arrays; candidate rate drift was 0.18%. See the
[result note](../../experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-promoted-result.md),
[R1 comparison](../../experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-screen-r1-result.json),
[R2 comparison](../../experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-replication-r2-result.json),
and [promotion attestation](../../experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-promotion-attestation.json).

## Boundaries and recovery

- This is short-context, single-user evidence with 8K configured context. No
  32K or multi-user value has been measured for this exact MTP2 profile.
- MTP depths above 2 are not authorized by this campaign.
- The tested 16 GiB host used a 13 GiB process cap and swap. Stop competing
  model processes before launch; do not compile while the model is loaded.
- If launch fails, stop the foreground scope, verify both B70s are idle with
  `xpu-smi`, confirm no `llama-server` remains, and rerun preflight. Never
  bypass a model or binary hash failure to recover a headline result.
- A clean-host Intel driver/oneAPI installation, source build, and beginner
  recovery replay remain pending, so package status remains candidate.
