# Qwen3.8 FP8 TP2 draft-only INT4 head R62

Date: 2026-09-01

Status: **all diagnostic gates passed; clean-boot promotion pending**.

R61 found that each MTP1 iteration projected both a one-row draft hidden state
and a two-row target hidden state through the full 124,160-token FP16
vocabulary head. R62 changes only the one-row drafter. It creates a shallow
copy of the already-loaded `ParallelLMHead`, retains the shared target FP16
parameter, and attaches group-128 W4A16 packed buffers only to the draft copy.
The target verifier module receives neither the INT4 marker nor packed buffers.
The feature is default-off and fails closed when the required XPU operation or
head shape is unavailable.

An XPU component smoke test proved that the draft copy was isolated, the target
FP16 weight remained shared, and the patched apply path exactly matched a
direct `int4_gemm_w4a16` invocation. At the production one-row shape, 30
iterations measured `0.572361 ms` for INT4 logits and `0.600596 ms` including
argmax. The R61 FP16 profiler reference was about `2.13 ms`, but that traced
number is diagnostic and is not treated as ordinary endpoint timing.

Two independently started, fresh-cache strict servers then ran the complete
12-prompt/six-class natural-512 suite. They measured `54.507697` and
`53.976404 tok/s`, centered at **`54.242051 tok/s`**. That is `+4.6980%`
against the qualified `51.808087 tok/s` MTP1 headline, with a `0.9795%`
between-server range. Every request reported zero cached tokens, both canary
suites passed, candidate repeat outputs matched 12/12 complete arrays, and all
24 candidate outputs matched the same-image MTP0 oracle exactly. They also
matched the incumbent MTP1 outputs 24/24.

The preregistered real-content depth continuation also passed. Each point is a
direct median across technical prose, Python, and structured documents:

| active context | decode | TTFT | change vs R56 MTP1 |
| ---: | ---: | ---: | ---: |
| 2K | `54.942 tok/s` | `0.589 s` | `+5.598%` |
| 4K | `56.019 tok/s` | `1.151 s` | `+5.886%` |
| 8K | `54.194 tok/s` | `2.351 s` | `+4.361%` |
| 16K | `53.516 tok/s` | `4.888 s` | `+0.719%` |
| 24K | `53.349 tok/s` | `7.651 s` | `+6.719%` |
| 32K | `52.279 tok/s` | `10.613 s` | `+4.375%` |

All 18 depth requests passed their receipts and matched the corresponding MTP0
complete output arrays exactly. Prefix-cache use was zero; before/after
canaries passed; no new Xe/GPU fault appeared. These are measured points only:
no value is interpolated or extrapolated.

R62 is retained but not promoted because this boot contains a GPU reset from
before the candidate campaign. The frozen preregistration requires two
fresh-cache strict servers on a clean boot. Until that user-coordinated replay,
the public `51.808087 tok/s` headline and existing curve remain unchanged and
no LocalMaxxing submission is authorized.

Reproduction inputs are all repository-relative:

- patch: [`vllm-qwen38-fp8-draft-only-int4-lm-head-r62-20260901.patch`](../patches/vllm-qwen38-fp8-draft-only-int4-lm-head-r62-20260901.patch)
- image build: [`build-draft-int4-r62-image.sh`](../../../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-draft-int4-r62-image.sh)
- server wrapper: [`run-20260901-qwen38-fp8-mtp1-draft-int4-r62-server.sh`](../scripts/run-20260901-qwen38-fp8-mtp1-draft-int4-r62-server.sh)
- preregistration: [`2026-09-01-qwen38-fp8-mtp1-draft-int4-r62-prereg.json`](../data/2026-09-01-qwen38-fp8-mtp1-draft-int4-r62-prereg.json)
- structured result: [`2026-09-01-qwen38-fp8-mtp1-draft-int4-r62-diagnostic-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-draft-int4-r62-diagnostic-result.json)
