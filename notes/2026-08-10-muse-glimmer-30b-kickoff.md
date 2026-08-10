# 2026-08-10 Muse Glimmer 30B Kickoff (And Gemma Quad Stop)

## Gemma quad production interlude

- 11:42 EDT: `install-gemma4-26b-q8-quad-service.sh --start` deployed the quad
  service (four service-profile backends 19350-19353, frontdoor :8000).
- Validation (quick pass, operator-requested, no soak): frontdoor health ok
  with `cached_tokens=0`; two c8 non-streaming smokes at `439.7` and
  `445.0 tok/s` aggregate wall (beats the stored non-streaming reference
  `298.1 tok/s`; consistent with the `556 tok/s` streaming benchmark);
  sticky cache probe `11101` prompt tokens `8.537s -> 0.071s` with `11100`
  cached tokens. Artifact:
  `data/gemma4-26b-quad-frontdoor-relaunch-validation-20260810T154700Z.json`.
- ~18:20 EDT: operator directed the switch to a new model effort; both quad
  units stopped and disabled, `b70-openai-frontdoor` left disabled, ports
  8000/19350-19353 free, no llama-server survivors. Gemma remains restorable
  via `docs/gemma4-26b-q8-service-runbook.md`.
- Separately: the exact dirty source state of the pinned Gemma production
  binary is now durably captured at
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260810-production-binary-source.patch`
  (verified byte-identical to the live tree; commit `daefa929c`).

## New lane: Meta Muse Glimmer 30B

Released today (Meta Superintelligence Lab, Apache 2.0): dense 29.6B agentic
multimodal model with DFlash block-diffusion drafter; llama.cpp support merged
upstream same day (PR #26841, `62bf73d25`).

Operator directive: maximum quality first (lossless or very near lossless),
then maximum speed; 4 B70s, one replica per card or per two cards.

Decision (fit math in `experiments/muse-glimmer-30b-b70/README.md`):

- Arm A lossless reference: unsloth BF16 2-part GGUF, one model per two B70s.
- Arm B near-lossless production candidate: unsloth UD-Q8_K_XL per two B70s,
  quality-gated against Arm A.
- Single-card near-lossless is fit-blocked (Q8_0 + drafter ~33.7 GB vs
  ~32.6 GB envelope); UD-Q6_K_XL and official kquant-dynamic kept only as
  fallback/comparator arms.
- DFlash drafter used in all arms (exact target verification preserves
  output identity).

Runtime: fresh clean-master clone `/home/steve/src/llama.cpp-muse-glimmer`
(`030ebb558`, version 10358), SYCL AOT bmg-g31 build completed 18:29 EDT,
`--spec-type draft-dflash` confirmed present.

Downloads staged as one prioritized aria2 queue (drafter -> UD-Q8_K_XL ->
BF16 mmproj -> BF16 target -> comparators), NVMe for serving artifacts, USB
for the BF16 target and comparators; `sha256.txt` written at queue end.

## Next

1. Smoke Arm B (2-card UD-Q8_K_XL + DFlash) as soon as its file lands:
   no-spec baseline vs DFlash `n_max` ladder, `-sm layer` vs `-sm row`.
2. Same for Arm A BF16 on the other card pair; establish the lossless
   reference decode number.
3. Exact-match and canary quality gates for Arm B vs Arm A before any
   production claim.
