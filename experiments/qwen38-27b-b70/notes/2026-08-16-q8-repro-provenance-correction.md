# Qwen3.8 Q8 TP2 reproduction provenance correction

Date: 2026-08-16  
Disposition: public reproduction corrected; headline quality remains valid

## What was wrong

The Qwen3.8 launcher exported three accepted optimization doors:

- `GGML_SYCL_COMM_REDUCE_VEC4=1`;
- `GGML_SYCL_FUSED_QK_NORM_ROPE=1`;
- `GGML_SYCL_FUSED_CONV_SILU_L2=1`.

The source packet and binary hashes initially frozen beside that launcher came
from the earlier direct-Q8 midpoint. Source and binary inspection proved that
the midpoint did not implement those doors. In contrast, the original
36.772932 tok/s result log printed the vec4 selector and reported nonzero Q/K
fusion and conv+SiLU+L2 counters. The result itself used the later full stack;
the reproduction packet had frozen the wrong historical midpoint.

The corrected source is the already versioned pre-DP4A2 full snapshot:
`llama-cpp-mndodd-4302fb599-lab-tp2-conv-silu-l2-20260815.diff.gz.b64`,
decoded SHA-256 `c8ae065cabf9e7b7f6b6a224673498ddf82b07aeb1d16a33d341368b9b3234d7`.
It retains the one-chain Q8 arithmetic intended for Qwen3.8.

## Fresh corrected replay

The corrected one-chain SYCL library (`707ea1b8...`) ran the complete fixed
12-prompt, 512-token endpoint suite:

| Metric | Result |
| --- | ---: |
| conventional 99-interval median | `36.421061 tok/s` |
| historical 100-event median | `36.788950 tok/s` |
| full-output after-TTFT median | `36.471332 tok/s` |
| full-output wall median | `35.938319 tok/s` |
| TTFT median | `177.177 ms` |
| complete output hashes | 12/12 exact |
| cache state | 12/12 `cached_tokens=0` |

The conventional replay is `-0.957%` versus the original `36.772932` result,
inside the host's observed process-state variation. On clean shutdown the
full fusion census reported `fused_conv_silu_l2=567744`,
`fused_qk_norm_rope=189248`, and `VERIFY_MISMATCH=0`. No Xe compute fault,
reset, hang, device-lost, or CAT error appeared.

## Vec4 attribution check

An eight-process same-binary `p64/n256/r3` bracket toggled only vec4. Scalar
means were `36.434819`, `36.426507`, `37.324766`, and `36.406775`; vec4 means
were `36.315544`, `36.705325`, `36.612693`, and `37.476755`. Pooled values
were `36.648217` scalar and `36.777579 tok/s` vec4 (`+0.353%`). Individual
position deltas crossed because of the known fast/slow process states, so this
new bracket is supporting evidence, not an independent promotion claim. The
earlier full Qwen3.6 vec4 gate remains its primary attribution evidence.

Structured evidence and raw hashes are in
[`2026-08-16-q8-repro-provenance-correction.json`](../data/2026-08-16-q8-repro-provenance-correction.json).
