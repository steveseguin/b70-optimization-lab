# Ornith 1.5 35B two-row MTP MoE reduction

## Outcome

**RESEARCH POSITIVE; NOT A PACKAGE DEFAULT.** Extending this lab's accepted
Qwen/Ornith ordered expert reduction to exactly two verifier rows removes 240
generic launches per MTP1 verification cycle and preserves the canonical
transcript. Mirrored CLI runs improved by 3.03%, while fresh-server evidence was
positive in aggregate but not independently decisive because the final control
rebounded into the candidate range.

## Candidate and correctness

The default-off `GGML_SYCL_FUSED_ORNITH_SPEC_MOE_ADD_REDUCE=1` path requires an
exact contiguous `[hidden, expert, token]` source with two tokens and the exact
seven-ADD dependency chain. It leaves every weighted expert product
graph-visible, then performs the original seven FP32 additions in the original
order separately for each token.

All four fixed-seed 128-token CLI transcripts had SHA-256
`6a91ba76bb2f032ca38f80f31561b84f111172795d47772927942bba427ff0d4`.
Each candidate run recorded exactly 3,402 two-row fusion hits.

## Measurements

Mirrored CLI A/B/B/A generation rates:

| arm | generation tok/s |
| --- | ---: |
| control A1 | 65.2 |
| candidate B1 | 66.5 |
| candidate B2 | 66.3 |
| control A2 | 63.7 |

Arm means were `64.45 -> 66.40 tok/s` (**+3.03%**); both candidates exceeded
both controls.

Fresh-server A/B/B/A results used 12 unique cold prompts per arm. Every
freshness/finality gate passed and every row reported `cached_tokens=0`:

| arm | median tok/s | mean tok/s | accepted / drafts |
| --- | ---: | ---: | ---: |
| control A1 | 76.911 | 77.998 | 2,219 / 3,908 |
| candidate B1 | 83.507 | 81.730 | 2,209 / 3,914 |
| candidate B2 | 83.198 | 80.942 | 2,263 / 3,860 |
| control A2 | 83.324 | 81.305 | 2,271 / 3,853 |

Pooling the 24 rows per condition gives median `81.945 -> 83.198` (+1.53%)
and mean `79.651 -> 81.336` (+2.11%), with candidate prompt-paired averages
winning 8/12. However, control A2 equals the candidate range, so this does not
meet the stricter evidence pattern used for the user package.

## Decision

Retain
`../patches/llamacpp-ornith15-mtp2row-moe-add-reduce-research-20260823.patch`
as a stackable MTP research component. Do not change the then-current
target-only package or describe this as an accepted serving gain. Its
`129.568 tok/s` figure used legacy 100-event compatibility accounting; the
conventional mean was `128.272782 tok/s`. The complete summary and raw server
rows are under `../data/2026-08-23-ornith35b-mtp2row-*`.
