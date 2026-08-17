# Qwen3.8 27B Q8 TP2 recurrent-quad workgroup population

Date: 2026-08-17

Status: accepted; exact, order-balanced service gain and clean-source replay

## Hypothesis

The accepted hardware-derived policy groups eight SG16 subgroups (128 work
items) per fused recurrent GDN-quad workgroup. This quad is launched 192 times
in the diagnostic decode trace and accounts for `19.456 ms` of device time.
The prior shape-scoped subgroup experiment changed only the dominant FFN
pair/down families and tested SG4; it did not touch this recurrent quad.

This trial changes only the recurrent-quad workgroup population from the B70
default SG8 to SG16 (256 work items). Each output row still belongs to one
SG16 subgroup, uses the same Q8 DP4A body, accumulates the same blocks in the
same FP32 order, and uses the same subgroup reduction. The candidate changes
only how independent row subgroups are packed into workgroups.

## Contract

- retain target-only equal TP2, F16 KV, FlashAttention and `b1024/ub256`;
- keep the fixed-shape door off; this isolates launch geometry from the closed
  compiler specialization;
- admit only the observed recurrent local shape
  `K5120/N5120+3072+24+24`;
- retain SG8 in the same binary as the default control;
- announce the SG16 branch on both devices and require
  `VERIFY_MISMATCH=0` before timing;
- use fresh-process, position-balanced direct-decode screens;
- proceed to the full cache-zero endpoint and quality oracle only if the
  performance gain repeats;
- any output-hash or semantic mismatch is a hard reject.

## Result

The mechanism smoke announced the exact SG16 branch on both B70s and ended
with `VERIFY_MISMATCH=0`. An eight-process `p64/n256/r3` screen used order
`A-B-B-A,B-A-A-B` (`A=SG8`, `B=SG16`) and measured `37.047004` versus
`36.719045 tok/s` (`+0.893%`); both halves agreed (`+1.167%`, `+0.621%`).

The corresponding `p64/n512/r3` confirmation pooled `36.902560` versus
`36.736576 tok/s` (`+0.452%`). Its halves disagreed (`-0.097%`, `+0.996%`),
so it was not sufficient by itself to promote.

Two realistic same-binary endpoint pairs were then run in opposite process
orders. Every server used one 8K slot, equal TP2, F16 KV, FlashAttention,
`b1024/ub256`, cache RAM zero, context checkpoints zero, fit off, reasoning
off, and no speculation. Each suite sent 12 unique prompts once with
`cached_tokens=0`.

| Pair | Primary median delta | Full median delta | Full mean delta |
| ---: | ---: | ---: | ---: |
| SG8 then SG16 | `+0.280%` | `+0.804%` | `+0.576%` |
| SG16 then SG8 | `+0.234%` | `+0.161%` | `+0.251%` |
| pooled suite statistics | **`+0.257%`** | **`+0.481%`** | **`+0.413%`** |

All four endpoint suites produced the same 12 complete output hashes. The
candidate also passed all seven semantic canaries, eight-repeat stability,
and the 3,829-token long-context needle with exact baseline hashes
(`pass_all=true`, `baseline_match_all=true`).

The change was then replayed directly on the accepted source, excluding the
closed fixed-shape trial code. Its smoke announced both devices and ended with
zero verification mismatches. A final same-binary `A-B-B-A` clean-build
bracket measured `37.321045` versus `36.978696 tok/s` (`+0.926%`). This bracket
alone has a known middle-position bias, but it is consistent with the earlier
eight-process and two order-balanced service-pair evidence.

## Decision and artifacts

Accept `GGML_SYCL_MMVQ_Q8_QUAD_SG16=1` in the Qwen3.8 Q8 TP2 reproduction.
The historical `36.772932 tok/s` conventional headline remains the highest
valid cold-suite capture; this promotion is based on matched same-binary A/B
improvement and does not inflate that headline.

- incremental patch:
  [`../../../patches/qwen38-27b-q8-tp2-asrock-b70/recurrent-quad-sg16-20260817.diff`](../../../patches/qwen38-27b-q8-tp2-asrock-b70/recurrent-quad-sg16-20260817.diff)
- patch SHA-256:
  `05ce95e18a211deeb20348ad6a2ffd4ca2dee828d7692c4a026f055156e9c86c`
- clean `libggml-sycl.so.0.19.0` SHA-256:
  `0b3cc38ce20fad568976a1ab1db1deda831eb375d49976c217c25fc02d7f3c26`
- clean `llama-bench` SHA-256:
  `ce3ad8809ceca3dcc063ed00e93bfe0744d892b45af9c56e33c061d09c8cbc47`
- clean `llama-server` SHA-256:
  `b26ad789f7372c7a409183aa870dd52589cf9fb654c8324055517b1ff1cfd528`
- semantic JSON SHA-256:
  `bf1eb27fbbd40caa08701594e403669bf9e1b0902057c2957236ffcd06ecc981`
- raw local evidence:
  `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-quad-sg16/`

Both B70s remained normal after the final smoke and performance gate, with no
current-boot Xe/GuC fault, reset, timeout, or hang signature.
