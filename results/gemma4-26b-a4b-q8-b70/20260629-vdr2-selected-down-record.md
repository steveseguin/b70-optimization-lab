# 2026-06-29 VDR2 Selected-Down Record

Status: **valid promoted fresh-response record family** for the Gemma 4 26B
A4B `UD-Q8_K_XL` target/verifier lane on one Intel Arc Pro B70. Current
LocalMaxxing headline repeat: `cmqztiqdn02vnoe01egox6q3f`.

2026-06-29 late addendum: the later same-family baseline/control row
`data/gemma4-q8-gpu3-q8lmhead-noreorder-control-full512-20260629T224927Z/summary.json`
superseded the FA-on 32K/VMM `117.91456485086059 tok/s` row with
`121.41411987308553 tok/s` median generated-token throughput for tokens 1-100
after TTFT. The DMMV and no-reorder LM-head experiment flags were unset in the
winning row; keep the default-off LM-head experiments as negative/closed
artifacts, not as the promoted mechanism.

## Result

Primary metric: median generated-token throughput for tokens 1-100 after TTFT
across the fixed realistic cold prompt suite.

| GPU | Summary | Gate | Canary | Median 1-100 | p10 1-100 | Mean 1-100 | Full512 after TTFT | Wall full512 | TTFT median |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | `data/gemma4-q8-gpu0-vdr2-selecteddown-reordervdr2-full512-20260629A/summary.json` | pass | 512/512 | 113.47081786263712 | 102.18997056423927 | 114.81272787275348 | 106.59058008222027 | 102.66882811900274 | 179.7679010196589 ms |
| 1 | `data/gemma4-q8-gpu1-vdr2-selecteddown-reordervdr2-full512-20260629B/summary.json` | pass | 512/512 | **115.72789384447941** | 101.44940713540609 | 113.15845262438565 | 104.6018645861352 | 100.22769693993533 | 181.347543024458 ms |
| 2 | `data/gemma4-q8-gpu2-vdr2-selecteddown-reordervdr2-full512-20260629C/summary.json` | pass | 512/512 | 113.81540554086772 | 104.38170198227209 | 113.37437257944545 | 105.36127337885975 | 101.3641176342222 | 180.47102249693125 ms |
| 3 | `data/gemma4-q8-gpu3-vdr2-selecteddown-reordervdr2-full512-20260629D/summary.json` | pass | 512/512 | 114.8109417270852 | 104.63732760747995 | 115.24650663810468 | 105.60976692576831 | 101.70051321789589 | 180.81690149847418 ms |

Initial promotion basis: GPU1 had the highest passing full512 median. The four
independent one-GPU confirmations all passed the same strict gate, making this
a reliable improvement over the prior `98.34046474459183 tok/s` record.

Same-recipe record repeat on 2026-06-29:

| GPU | Summary | Gate | Canary | Median 1-100 | p10 1-100 | Mean 1-100 | Full512 after TTFT | Wall full512 | TTFT median |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `data/gemma4-q8-gpu1-selecteddown-bf16retest-control-full512-20260629T051323Z/summary.json` | pass | 512/512 | **115.8466634928202** | 102.5726047181403 | 114.57370008916365 | 104.66140955057205 | 100.6396791169625 | 181.16679147351533 ms |

This repeat used the same VDR2 selected-down recipe. It was run as the control
lane beside a BF16-direct retest; the BF16-direct lanes did not beat controls.
Because the repeat passed the current fixed realistic cold gate, it supersedes
the initial `115.72789384447941` headline. LocalMaxxing:
`cmqyrpox4021dqk01co5o4fcw`.

FA-on 32K/VMM retest and confirmation on 2026-06-29:

| GPU | Summary | Gate | Canary | Median 1-100 | p10 1-100 | Mean 1-100 | Full512 after TTFT | Wall full512 | TTFT median |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 3 | `data/gemma4-q8-gpu3-faon-vmm-ctx32768-full512-20260629T211437Z/summary.json` | pass | 512/512 | **117.91456485086059** | 107.80735938671545 | 118.8805550250879 | 110.957638362282 | 106.80689050225271 | 180.16915302723646 ms |
| 0 | `data/gemma4-q8-gpu0-faon-vmm-ctx32768-confirm-full512-20260629T211843Z/summary.json` | pass | 512/512 | 116.45776605647993 | 100.52805362848677 | 116.40736141241894 | 112.21083560224112 | 106.58846715929698 | 179.6505789970979 ms |
| 1 | `data/gemma4-q8-gpu1-faon-vmm-ctx32768-confirm-full512-20260629T211843Z/summary.json` | pass | 512/512 | 117.41509141115063 | 102.82580425522343 | 116.89697181871713 | 108.37433815430438 | 104.58702581027498 | 178.85348544223234 ms |
| 2 | `data/gemma4-q8-gpu2-faon-vmm-ctx32768-confirm-full512-20260629T211843Z/summary.json` | pass | 512/512 | 115.08942949119734 | 107.00399050168588 | 116.51674286549678 | 107.47895026970602 | 103.39173316785484 | 180.59724348131567 ms |
| 3 | `data/gemma4-q8-gpu3-faon-vmm-ctx32768-confirm-full512-20260629T211843Z/summary.json` | pass | 512/512 | 117.45737477243767 | 107.32460490342444 | 116.49336180116973 | 110.76279573353797 | 106.13772714309907 | 180.20113703096285 ms |

This is a small confirmed improvement, not a synthetic or warmed-history
headline: every row used the fixed realistic suite, each prompt once, and
`cached_tokens=0`. The confirmation batch is not variance-free (`115.089` is
below the prior `115.8466634928202` high), but 3/4 same-identity confirmations
and the promoted row beat the prior record. LocalMaxxing:
`cmqzq5zu402troe01t774uyox`.

Late same-family baseline/control high:

| GPU | Summary | Gate | Canary | Median 1-100 | p10 1-100 | Mean 1-100 | Full512 after TTFT | Wall full512 | TTFT median |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 3 | `data/gemma4-q8-gpu3-q8lmhead-noreorder-control-full512-20260629T224927Z/summary.json` | pass | 512/512 | **121.41411987308553** | 107.03214367227781 | 120.13610933675466 | 110.39053979324245 | 105.88057667302085 | 179.117635008879 ms |
| 2 | `data/gemma4-q8-gpu2-baseline-recordconfirm-full512-20260629T225215Z/summary.json` | pass | 512/512 | 119.94842631460949 | 107.41526220540041 | 119.37118785029499 | 111.9444876977782 | 106.90864788926861 | 179.77339948993176 ms |

The accepted LocalMaxxing ID for the high row is `cmqztiqdn02vnoe01egox6q3f`.

## Validity

- Fixed suite: `repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`.
- Each prompt sent once as a cold response.
- `cached_tokens=0` for every request in every full512 confirmation.
- No prompt/KV cache reuse, context checkpoints, response reuse,
  n-gram/history acceleration, or warmed repeated prompts.
- Target model and verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`.
- Draft model: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`; accepted speculative
  tokens are verified by the Q8 target.
- `realistic_final_gate.passed=true` and `headline_eligible_for_gemma_q8=true`
  in every promoted summary.

## Winning Change

The win is a source-level verifier MoE reduction: a VDR2-reordered Q8
implementation of `GGML_OP_MOE_SELECTED_DOWN_WEIGHTED_SUM`.

Why it mattered:

- The previous raw-layout fused-down path rejected reordered Q8 expert weights,
  so the current VDR2 record stack could not use it.
- The new path quantizes/reorders the selected hidden rows and computes the
  selected down projection plus weighted sum against VDR2 reordered Q8 weights.
- This removes separate selected-down materialization and the following
  weighted-sum pass in the strict record stack.

Enable flag:

```text
LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1
```

Required surrounding identity is still the prior strict record stack:
`GGML_SYCL_REORDER_Q8_0_VDR_MMVQ=2` build, reordered-Q8 VDR2,
`LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
`LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, `n_max=3`, `n_min=2`,
`p_min=0.0475`, `UBATCH_SIZE=1024`, f16 KV, graph enabled, and
`--ctx-checkpoints 0`. The current promoted repeat additionally uses
`FLASH_ATTN=on`, `CTX_SIZE=32768`, and `GGML_SYCL_ENABLE_VMM=1`.

## Artifacts

- Source patch:
  `patches/gemma4-26b-a4b-q8-b70/20260629-vdr2-selected-down-reordervdr2-source.patch`
  (`sha256=9db3ac4286e3842ece2eebd07060ac73a0e0c548cb15d17333406701576d52c8`).
- Harness patch:
  `patches/gemma4-26b-a4b-q8-b70/20260629-vdr2-selected-down-reordervdr2-harness.patch`
  (`sha256=c36baad905271f2350182372ca62ce6614bb07b87425c28318fb6dca5042cc0d`).
- Pre-experiment source snapshot:
  `patches/gemma4-26b-a4b-q8-b70/20260629-pre-vdr2-selected-down-source-snapshot.patch`.
- Repro script:
  `repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh`.

## Next Work

The reliable `>100` barrier is now broken. The next optimization should keep
this exact recipe as the baseline and only pursue source-level verifier cost
work. Best next targets:

- exact LM-head candidate-vs-max or compact argmax;
- head-only bonus token path that preserves the current bonus pipeline;
- row-adaptive verifier output rows;
- verifier MoE boundary/kernel reduction beyond the selected-down fusion.

Keep prompt processing and long-context optimization separate from the short
decode record lane, and rerun this short suite afterward to prove no regression.

## 2026-06-29 Follow-Up Screens

These are post-record screens against the same VDR2 selected-down stack. Treat
strict128 results as diagnostic only; full512 is required before promotion or
LocalMaxxing submission.

### MTP Depth Retest: Negative

Rationale: older `n_max > 3` tests predated the selected-down verifier win, so
deeper MTP needed one fresh check on the current stack.

Strict128 paired screen, all valid fresh-response (`cached_tokens=0`, fixed
suite, each prompt once):

| Lane | Summary | Median 1-100 | p10 1-100 | Mean 1-100 | Full128 after TTFT | Wall full128 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| control `n_max=3` | `data/gemma4-q8-gpu0-selecteddown-depth-control-n3-strict128-20260629T124941Z/summary.json` | 116.33568692588463 | 104.89058924253862 | 114.14305965671014 | 112.26257751498565 | 96.81017927788454 |
| `n_max=4` | `data/gemma4-q8-gpu1-selecteddown-depth-n4-strict128-20260629T124941Z/summary.json` | 103.46481323047499 | 95.47779842736264 | 104.28796054493681 | 105.04689964432404 | 90.9986053062178 |
| `n_max=5` | `data/gemma4-q8-gpu2-selecteddown-depth-n5-strict128-20260629T124941Z/summary.json` | 100.43230800604314 | 92.29559714995177 | 101.08652490737596 | 100.17771457016522 | 87.85595957452232 |
| `n_max=6` | `data/gemma4-q8-gpu3-selecteddown-depth-n6-strict128-20260629T124941Z/summary.json` | 93.90769841294549 | 82.18749613674814 | 94.37496785088634 | 92.8871375259663 | 80.25682090606395 |

Conclusion: keep `n_max=3`, `n_min=2`, `p_min=0.0475` for the promoted recipe.
On this stack, deeper draft length increases verifier/draft cost faster than it
adds accepted fresh-response tokens.

### Skip Stateless Sampler Accept: Noisy / Not Promoted

`LLAMA_SPEC_VERIFY_SKIP_STATELESS_ACCEPT=1` produced one high strict128 screen
but did not hold consistently across GPUs or prior full512 repeats.

Strict128 paired screen:

| Lane | Summary | Median 1-100 | p10 1-100 | Mean 1-100 | Full128 after TTFT |
| --- | --- | ---: | ---: | ---: | ---: |
| control GPU0 | `data/gemma4-q8-gpu0-skipstateless-pair-control-strict128-20260629T124457Z/summary.json` | 108.04191928813023 | 104.7755022386352 | 113.1853597785455 | 112.80654193318901 |
| skipstateless GPU1 | `data/gemma4-q8-gpu1-skipstateless-pair-on-strict128-20260629T124457Z/summary.json` | 117.68045890705352 | 104.42808236961972 | 115.36583191419878 | 116.04310796465757 |
| control GPU2 | `data/gemma4-q8-gpu2-skipstateless-pair-control-strict128-20260629T124457Z/summary.json` | 116.92216788973741 | 102.60078092439963 | 114.63675193846426 | 115.4808203348982 |
| skipstateless GPU3 | `data/gemma4-q8-gpu3-skipstateless-pair-on-strict128-20260629T124457Z/summary.json` | 110.71755588164166 | 105.0374643745801 | 114.44868382524521 | 114.95282261551321 |

Conclusion: do not submit or promote. The idea may still be useful if the
server-side sampler clone is removed under a stricter stateless-greedy guard,
but the existing accept-skip flag alone is not a reliable record improvement.

### Duplicate Full-Accept Hidden Copy: Negative

Patch artifact:
`patches/gemma4-26b-a4b-q8-b70/20260629-skip-duplicate-full-accept-hcopy-experiment.patch`.

Rationale: with `LLAMA_MTP_DEFER_TARGET_H_NEXTN=1`, `process()` already copies
the last verifier hidden row into `pending_h`. On full accept,
`accept()` can request that same row again. The experiment adds
`LLAMA_MTP_SKIP_DUP_FULL_ACCEPT_H_COPY=1` to skip only that duplicate copy when
`i_h == n_rows - 1`; partial accepts and rejects still copy the selected row.

Strict128 A/B was valid but noisy:

| Lane | Summary | Median 1-100 | p10 1-100 | Mean 1-100 | Full128 after TTFT |
| --- | --- | ---: | ---: | ---: | ---: |
| control GPU0 | `data/gemma4-q8-gpu0-hcopy-control-strict128-20260629T130113Z/summary.json` | 110.57462228639803 | 102.87362982680462 | 111.91631188690212 | 112.36207105451862 |
| hcopy GPU1 | `data/gemma4-q8-gpu1-hcopy-on-strict128-20260629T130113Z/summary.json` | 113.3775542861014 | 103.71071008154013 | 113.49379061720516 | 114.08028216467035 |
| control GPU2 | `data/gemma4-q8-gpu2-hcopy-control-strict128-20260629T130113Z/summary.json` | 115.27088029375872 | 102.32608430327235 | 115.15466844248215 | 114.5269068791023 |
| hcopy GPU3 | `data/gemma4-q8-gpu3-hcopy-on-strict128-20260629T130113Z/summary.json` | 116.35089940418223 | 104.30782648792547 | 115.61975448981418 | 112.70077341213715 |

Full512 A/B confirmed it is not a record improvement:

| Lane | Summary | Median 1-100 | p10 1-100 | Mean 1-100 | Full512 after TTFT | Wall full512 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| control GPU0 | `data/gemma4-q8-gpu0-hcopy-control-full512-20260629T130420Z/summary.json` | 112.21510580665421 | 102.39687706219802 | 113.807550310799 | 103.90305412348668 | 99.16315687192693 |
| hcopy GPU1 | `data/gemma4-q8-gpu1-hcopy-on-full512-20260629T130420Z/summary.json` | 111.42365779318506 | 103.6723777533772 | 113.49152454131091 | 105.56536083069597 | 100.38875072655891 |
| control GPU2 | `data/gemma4-q8-gpu2-hcopy-control-full512-20260629T130420Z/summary.json` | 110.51420887948717 | 102.56119018639345 | 112.97497287428895 | 106.96122762495051 | 102.48931204090205 |
| hcopy GPU3 | `data/gemma4-q8-gpu3-hcopy-on-full512-20260629T130420Z/summary.json` | 113.17038347073819 | 102.08411761686624 | 113.82889747700256 | 104.59623460774262 | 100.89378061491095 |

Conclusion: do not promote. The duplicate copy exists, but skipping it does not
move the full512 fresh-response metric above the current `121.41411987308553`
record. The source experiment was reverted after recording the patch and
results.

### Current-Stack `p_min` Bracket: Negative

Rationale: the old tight `p_min` sweeps predated the VDR2 selected-down fused
weighted-sum win. A bounded retest checked whether the new verifier cost
profile shifted the best confidence threshold.

Strict128 bracket, all valid fresh-response:

| Lane | Summary | Median 1-100 | p10 1-100 | Mean 1-100 | Full128 after TTFT | Wall full128 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `p_min=0.045` | `data/gemma4-q8-gpu0-selecteddown-pmin00450-strict128-20260629T131753Z/summary.json` | 109.02779917454131 | 102.72262564201866 | 112.11511611934047 | 112.0518061181312 | 96.00730696638817 |
| `p_min=0.0475` control | `data/gemma4-q8-gpu1-selecteddown-pmin00475-control-strict128-20260629T131753Z/summary.json` | 117.46011025132319 | 99.76158707842515 | 115.44622344665821 | 114.53379847486426 | 96.44260947477878 |
| `p_min=0.050` | `data/gemma4-q8-gpu2-selecteddown-pmin00500-strict128-20260629T131753Z/summary.json` | 110.91055854813678 | 102.88674510589247 | 112.018759986235 | 110.04779288047666 | 95.28986601729343 |
| `p_min=0.0525` | `data/gemma4-q8-gpu3-selecteddown-pmin00525-strict128-20260629T131753Z/summary.json` | 113.64529853346951 | 100.05190148151058 | 113.62031317951106 | 110.58948684955283 | 96.05289799131236 |

Conclusion: keep `p_min=0.0475`. This also reinforces that more threshold
roulette around the current record is low value; future attempts need a
source-level verifier/LM-head/MoE change or a new validated draft source.
