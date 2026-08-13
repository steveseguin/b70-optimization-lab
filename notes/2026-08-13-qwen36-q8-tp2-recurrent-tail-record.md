# Qwen3.6 27B Q8 TP2 recurrent-tail record

## Decision

Promote the default-off recurrent RMS/gate/multiply/Q8-tail fusion on top of
the accepted mndodd-based target-only TP2 stack. The final fresh-server fixed
suite reached `35.699225 tok/s` conventionally (`36.059823` under the
historical helper), with 12/12 complete 512-token output hashes exact and all
cache counts zero. No MTP, DFlash, draft, n-gram, prompt reuse, or other
speculation was present.

This is `+15.065%` over the matched mndodd-fork TP2 baseline of `31.025377`
tok/s. The record-to-record change from `35.494434` is `+0.577%`, but that
comparison contains ordinary run variance. The source contribution is the
pooled matched A/B estimate of **`+0.219%`**.

## Accepted mechanism

`GGML_SYCL_FUSE_EXT` bit 4 joins the exact recurrent tail:

1. RMS normalization and its scale multiplication;
2. the independently precomputed SiLU gate;
3. the final elementwise multiplication; and
4. the reordered-Q8 handoff consumed by MMVQ.

The matcher fires only when the gate projection is already present in the
precomputed-MMVQ set. It preserves the stock FP32 boundaries and the order of
RMS and multiply operations. The source default remains `15`; the promoted
recipe sets `31`, enabling accepted bits 0 through 4.

For a 16-token TP2 census, the new path fired exactly 1,536 times: 48 recurrent
layers × 2 ranks × 16 decode tokens. The scoped
`GGML_SYCL_GDN_RMS_TAIL_POISON=1` red-control changed 3/12 output hashes, while
clean mode was 12/12 exact. Production and repro launchers explicitly unset
the poison variable.

## Matched attribution

| Run | Conventional median | Candidate wins |
| --- | ---: | ---: |
| Same-binary control, mask 15 | `35.461731` | — |
| Clean candidate A, mask 31 | `35.581809` | 11/12 |
| Clean candidate B, mask 31 | `35.493408` | 9/12 |

Candidate A was `+0.28256%`, candidate B was `+0.17646%`, and the pooled
matched estimate was `+0.21865%`. All 24 candidate outputs matched the oracle.

The final no-warmup publication run measured:

- conventional median / p10 / mean: `35.699225` / `35.199488` / `35.610043`;
- full-512 after-TTFT median: `35.715918`;
- full-512 wall median: `35.266336`;
- TTFT median: `179.163 ms`.

## Rejected screens

- Q8 scale broadcast reduced a matched run by about `1.52%` and was removed.
- A `0.98/1.02` tensor split fell to `33.263 tok/s`; it broke the symmetry
  assumptions and multiplied quant launches. Equal `1/1` remains mandatory.
- Swapping the main GPU was neutral to slightly worse.
- A Q8 weight-cache hint was negative in the properly equally warmed full
  crossover: `35.671361` candidate versus `35.690578` control.
- L3 bypass, a streaming scale plane, and L1-streaming/L3-uncached variations
  did not win and were removed.

Both GPUs held 2,800 MHz during live decode at roughly 182–188 W each, below
their 275 W caps. The result was not power- or clock-limited, and no firmware
or power setting was changed.

## Durable identities

- Base: mndodd llama.cpp `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`
- Decoded full patch SHA-256:
  `710b8628f6c94025d9a0516f77bddeeebccdd27d5bd3ebc4f79d2e623b1dd6c7`
- Final `libggml-sycl.so` SHA-256:
  `d667e6f3ccabede45df4f9512024cb1ae8653ab0bbea7827b6baf8599221e2a6`
- Raw publication JSON SHA-256:
  `d98a21f150dbb5b6461a0cc95d84d579cef36084d1f9ed3984d9827cfcf3dbc8`
- Post-deploy service replay: `35.600659 tok/s` conventional, 12/12 exact,
  cache zero; local raw file
  `tail-production-postdeploy-realistic512.json` in the campaign run directory.
- Full raw and patch artifacts are linked from the
  [result packet](../results/qwen36-27b-q8-tp2-asrock-b70/README.md).
