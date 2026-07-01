# Qwen3.6 INT8 N-Gram Hold-Prefill Rejection

Date: 2026-06-10

## Context

I tested vLLM n-gram speculative decode on the accepted Qwen3.6 INT8
no-prefix runtime to see whether we could get single-request decode past
`200 tok/s` without changing model weights or sampling quality.

Runtime constants:

- model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- runtime dtype: BF16
- quantization: Quark W8A8 INT8
- tensor parallelism: TP4
- context cap: 32K
- XPU PIECEWISE graph capture
- clone-safe custom-op all-reduce collectives
- prefix caching disabled
- `--max-num-batched-tokens 8192`
- `--max-num-seqs 48`
- speculative mode: n-gram, five speculative tokens, graph capture includes
  `128`

The source patch is archived as:

- `patches/vllm-qwen36-ngram-holdprefill-gdn-spec-store-guard-rejected-20260610.patch`

## Candidate 1: Hold Spec Decode When Prefill Is Waiting

The first patch held speculative decode for one scheduler step when waiting
prefill work existed. This avoided the earlier mixed prefill/speculative GDN
runtime failure and produced very high speed on high-acceptance synthetic
prompts.

Single request, p512/n512, `vllm-random`, eight repeats:

| metric | result |
| --- | ---: |
| corrected output tok/s after first chunk | `314.2395` |
| output tok/s end-to-end | `298.2047` |
| mean TTFT | `75.42 ms` |

More normal text prompt, p512/n512, eight repeats:

| metric | result |
| --- | ---: |
| corrected output tok/s after first chunk | `108.9392` |
| output tok/s end-to-end | `107.4026` |
| mean TTFT | `75.31 ms` |

Warm concurrency:

| concurrency | aggregate output tok/s wall | aggregate output tok/s from first text | mean per-request output tok/s after TTFT | mean TTFT |
| ---: | ---: | ---: | ---: | ---: |
| 2 | `511.94` | `563.52` | `293.08` | `125.08 ms` |
| 8 | `1323.19` | `1484.31` | `225.39` | `396.81 ms` |

Artifacts:

- `data/qwen36-quark-int8-tp4-ngram5-cg128-holdprefill-single-r8-20260610.json`
- `data/qwen36-quark-int8-tp4-ngram5-cg128-holdprefill-text-single-r8-20260610.json`
- `data/qwen36-quark-int8-tp4-ngram5-cg128-holdprefill-c2-warm-20260610.json`
- `data/qwen36-quark-int8-tp4-ngram5-cg128-holdprefill-c8-warm-20260610.json`

Quality rejected it. The 64-repeat frontdoor quality gate failed repeat
stability, with corrupt outputs such as prompt-tail fragments mixed into the
short deterministic repeat case. This points at recurrent or token-state
contamination under speculative decode.

Artifact:

- `data/qwen36-quark-int8-tp4-ngram5-cg128-holdprefill-frontdoor-quality-rerun64-20260610.json`

## Candidate 2: Store GDN Recurrent State Only For Accepted Draft Tokens

I then guarded `fused_sigmoid_gating` so speculative decoding only stores the
GDN recurrent state for accepted drafted tokens. This fixed the short repeat
contamination: all 64 repeat outputs were the expected `blue, green, orange,
red`.

Single request, p512/n512, `vllm-random`, eight clean sequential repeats:

| metric | result |
| --- | ---: |
| corrected output tok/s after first chunk | `299.6483` |
| output tok/s end-to-end | `287.4952` |
| mean TTFT | `75.34 ms` |

Warm concurrency:

| concurrency | aggregate output tok/s wall | aggregate output tok/s from first text | mean per-request output tok/s after TTFT | mean TTFT |
| ---: | ---: | ---: | ---: | ---: |
| 2 | `509.17` | `610.20` | `305.13` | `166.35 ms` |
| 8 | `1391.06` | `1522.69` | `232.18` | `354.44 ms` |

Artifacts:

- `data/qwen36-quark-int8-tp4-ngram5-cg128-holdprefill-specstoreguard-random-r8-rerun2-20260610.json`
- `data/qwen36-quark-int8-tp4-ngram5-cg128-holdprefill-specstoreguard-c2-warm-rerun2-20260610.json`
- `data/qwen36-quark-int8-tp4-ngram5-cg128-holdprefill-specstoreguard-c8-warm-20260610.json`

The stricter quality rerun still failed exact baseline parity. Intrinsic checks
passed, including the 64-repeat stability check, but the long-context needle
case returned:

`B70_QWEN36_NEEDLE_20260609 Question: what is the exact needle string? Answer only the string.`

The accepted baseline returns only the needle string. Since the optimization
changes exact output on a long-context gate, it is not quality-preserving.

Artifact:

- `data/qwen36-quark-int8-tp4-ngram5-cg128-holdprefill-specstoreguard-frontdoor-quality-rerun64-rerun2-20260610.json`

Two earlier post-guard artifacts were run while another benchmark was active
and should be treated as contaminated, not decision data:

- `data/qwen36-quark-int8-tp4-ngram5-cg128-holdprefill-specstoreguard-random-r8-20260610.json`
- `data/qwen36-quark-int8-tp4-ngram5-cg128-holdprefill-specstoreguard-c2-warm-20260610.json`

## Decision

Reject the current n-gram speculative decode path for production.

It proves there is a high-acceptance speed ceiling above `300 tok/s` on this
hardware, and the GDN accepted-token store guard fixed one real contamination
bug. However, the candidate still fails the no-quality-loss requirement because
long-context exact output diverges from the accepted baseline.

The accepted backend was restored after the test:

- session: `qwen36-tp4-gdn-reusequant-clone-envclean-32k`
- endpoint: `http://127.0.0.1:18080`
- health: pass

## Next Investigation

The next useful target is token-level parity tracing for the long-context case:

- compare accepted non-spec token IDs against n-gram token IDs
- log accepted draft lengths around the point where the answer should stop
- inspect stop/EOS handling and recurrent state after accepted speculative
  tokens
- verify whether the GDN convolution state path already respects accepted
  token counts in the same way as the guarded recurrent state path

Do not promote n-gram speculative decode until exact baseline parity passes on
repeat, exact, and long-context gates.
