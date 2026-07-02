# Gemma 4 26B Q8: Argmax Tile16 Draft q6_K Screen (No Win)

Date: 2026-07-02

## Purpose

The record-stack node profile showed three MTP draft direct-argmax LM-head
nodes (`mtp_direct_argmax_unroll_token_0/1/2`) at about `0.409 ms` each. Log
detail confirmed those nodes use `q6_K` output weights:

```text
src0{NONE:token_embd.weight type=q6_K ne=[1024,262144,1,1]}
```

Source audit found these three nodes cannot be naively batched because MTP
direct unroll is autoregressive: token 0 feeds draft step 1, and token 1 feeds
draft step 2. Existing `MUL_MAT_ARGMAX` multi-column support therefore does not
apply.

This screen tested the remaining low-risk knob that directly touches the
single-node `q6_K` argmax path:

```bash
LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS=16
```

The prior tile-subgroup negatives were mostly on the rejected verifier-fused
argmax family. This run isolated the knob on the current record recipe where
it mainly affects draft q6_K argmax nodes.

## Command

```bash
cd /home/steve/llm-optimizations
STAMP=20260702T114204Z-argmaxtile16-short-full512-ab \
BASE_PORT=19120 \
ARGMAX_TILE_SUBGROUPS=16 \
MAX_TOKENS=512 \
CANARY_REPEATS=32 \
REALISTIC_METRIC_TOKENS=100 \
READINESS_TIMEOUT_S=900 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-argmaxtile-short-full512-ab.sh
```

Harness:

- `repro/gemma4-26b-a4b-q8-b70/run-vdr2-argmaxtile-short-full512-ab.sh`

Evidence:

- paired analysis:
  `data/gemma4-argmaxtile16-short-full512-ab-20260702T114204Z-argmaxtile16-short-full512-ab.json`
- markdown summary:
  `data/gemma4-argmaxtile16-short-full512-ab-20260702T114204Z-argmaxtile16-short-full512-ab.md`
- aggregate guard summaries:
  - `data/gemma4-short-decode-guard-20260702T114204Z-argmaxtile16-short-full512-ab-waveA-control.json`
  - `data/gemma4-short-decode-guard-20260702T114204Z-argmaxtile16-short-full512-ab-waveA-candidate.json`
  - `data/gemma4-short-decode-guard-20260702T114204Z-argmaxtile16-short-full512-ab-waveB-control.json`
  - `data/gemma4-short-decode-guard-20260702T114204Z-argmaxtile16-short-full512-ab-waveB-candidate.json`
- per-lane run directories:
  `data/gemma4-q8-gpu*-shortguard-*argmaxtile16-short-full512-ab-*`

## Validity

All eight lanes passed:

- fixed realistic prompt suite
- each prompt once as a cold response
- `cached_tokens=0` for every prompt
- canary pass
- realistic final gate pass
- UD-Q8_K_XL target/verifier unchanged; Q4_0 MTP draft unchanged
- `MAX_TOKENS=512`, primary metric generated tokens 1-100 after TTFT

Candidate identity was confirmed in per-run summaries:

- controls: `llama_sycl_mul_mat_argmax_tile_subgroups=<unset>`
- candidates: `llama_sycl_mul_mat_argmax_tile_subgroups=16`

## Results

Control medians:

- GPU0 waveA: `120.80370238109151`
- GPU2 waveA: `119.61301611264857`
- GPU1 waveB: `120.18032374622885`
- GPU3 waveB: `110.98835267662085`

Candidate medians:

- GPU1 waveA: `118.80468958273198`
- GPU3 waveA: `122.4958682470378`
- GPU0 waveB: `117.53416094425046`
- GPU2 waveB: `117.31655097403878`

Paired bootstrap:

- median-ratio CI: `-2.5941585964646476% / 0.0007278466068960654% / 4.021156059964525%`
- mean-ratio CI: `-2.660010106105929% / 0.6769727145804195% / 4.310378330499471%`
- median raw-delta CI: `-3.190208949330862 / -0.005338362104637895 / 4.488487027917171 tok/s`

Analyzer decision: `inconclusive_positive`.

Project decision: **no win / do not promote**. The 95% lower bound is negative,
the median paired effect is effectively zero, and no candidate beat the current
valid record `124.97714084813418 tok/s`.

## Conclusion

`LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS=16` is not a short-decode record
candidate for the current Gemma Q8 record stack.

Together with the read-only source audit, this closes the low-risk draft
q6_K `MUL_MAT_ARGMAX` lane:

- the three draft argmax nodes are autoregressive and cannot be naively
  batched;
- prior `MUL_MAT_ARGMAX` tile/reorder/multi-reuse/top1 variants are negative
  for related verifier paths;
- the one remaining low-risk tile-subgroup screen on the current draft path is
  inconclusive/no-win.

Future q6_K draft argmax work would require a real kernel redesign, such as a
new single-node q6_K top1 epilogue or dot-layout rewrite. That is not a small
safe follow-up and should not be attempted unless the user explicitly chooses a
deeper kernel engineering lane.

No LocalMaxxing submission was made.
