# 2026-06-29 Packed Gate/Up GEGLU Epilogue Screen

Status: negative / inconclusive. Do not promote or submit.

## Question

Can Gemma4 routed MoE save overhead by preserving the tuned `MUL_MAT_ID`
gate/up matmul, but applying GEGLU directly from the packed merged
`gate_up` tensor instead of creating gate/up views and calling
`ggml_geglu_split(gate, up)`?

This is intentionally narrower than the previously failed direct BF16 routed
gate/up dot kernel:

- keep `build_lora_mm_id(gate_up_exps, cur, selected_experts, up_exps_s)`;
- keep the current VDR2 selected-down weighted-sum backend unchanged;
- default-off flag: `LLAMA_GEMMA4_MOE_GATEUP_GEGLU_EPILOGUE=1`;
- first screen restricted to Gemma4, GELU gate, layer 29, BF16
  `gate_up_exps`, small decode shapes.

Source and harness snapshots:

- source:
  `patches/gemma4-26b-a4b-q8-b70/20260629-packed-gateup-geglu-epilogue-source.patch`
- harness identity:
  `patches/gemma4-26b-a4b-q8-b70/20260629-packed-gateup-geglu-epilogue-harness.patch`
- pre-edit source snapshot:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260629-faon-vmm-pre-packed-geglu.patch`

## Build

Built successfully in the existing AOT VDR2 build tree:

```bash
source /opt/intel/oneapi/setvars.sh --force
cmake --build /home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 --target llama-server -j 12
```

The long SYCL AOT link completed with normal spill warnings.

## Strict128 A/B

All lanes used the current valid record identity:

- llama.cpp `c926ad098` dirty Gemma record stack;
- UD-Q8_K_XL target/verifier, Q4_0 MTP draft;
- `FLASH_ATTN=on`, `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`;
- selected-down VDR2 record stack;
- `MAX_TOKENS=128`, `CANARY_REPEATS=64`;
- fixed realistic suite, each prompt once, `cached_tokens=0`;
- no prompt/KV cache reuse, context checkpoints, response reuse,
  n-gram/history acceleration, or warmed repeated prompts.

Stamp: `20260629T215509Z`.

| Lane | Flag | Summary | Gate | Canary | Median 1-100 | p10 | Mean | Full | Wall | TTFT |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GPU0 control | unset | `data/gemma4-q8-gpu0-packed-geglu-control-strict128-20260629T215509Z/summary.json` | pass | 256/256 | 117.0957110456649 | 102.97544553657588 | 116.65654304267231 | 117.07591948931797 | 98.90359816139198 | 179.29559951880947 |
| GPU1 packed GEGLU | `1` | `data/gemma4-q8-gpu1-packed-geglu-on-strict128-20260629T215509Z/summary.json` | pass | 256/256 | 117.62438637801324 | 106.7987558322018 | 118.49761862900375 | 112.43973249928857 | 94.90644814169266 | 179.8883320298046 |
| GPU2 control | unset | `data/gemma4-q8-gpu2-packed-geglu-control-strict128-20260629T215509Z/summary.json` | pass | 256/256 | 116.61474666064632 | 100.83387262064214 | 114.63967438792008 | 114.66519058365257 | 98.89960218691675 | 179.50600944459438 |
| GPU3 packed GEGLU | `1` | `data/gemma4-q8-gpu3-packed-geglu-on-strict128-20260629T215509Z/summary.json` | pass | 256/256 | 116.20028233678278 | 107.06360295326012 | 116.41504640814402 | 113.34948480327847 | 97.77224980118592 | 179.95171749498695 |

## Decision

Negative / inconclusive. The flag-on lanes were mixed:

- GPU1 beat adjacent control by `+0.5287 tok/s`, below the `+0.75 tok/s`
  strict128 continuation threshold and below the `117.91456485086059 tok/s`
  full512 record.
- GPU3 lost to adjacent control by `-0.4145 tok/s`.
- Full-output and wall medians regressed on both flag-on lanes.
- Quality and validity passed, so the idea is safe as a default-off experiment,
  but it does not justify a full512 promotion run in this narrow BF16-layer form.

Do not submit to LocalMaxxing. If revisiting, the only plausible variant is to
apply packed GEGLU to all merged routed gate/up layers, including Q8 layers,
because the layer-29-only BF16 screen is too small to rise above noise.

## Broad `=all` Follow-Up

Status: negative. Safe/valid, but not faster under the full512 promotion gate.

The broad mode extended the same packed GEGLU graph shortcut to all merged
routed gate/up layers, including Q8 layers:

- flag: `LLAMA_GEMMA4_MOE_GATEUP_GEGLU_EPILOGUE=all`;
- same current record identity: UD-Q8_K_XL verifier, Q4_0 MTP draft,
  FA-on 32K/VMM, VDR2 selected-down, strict realistic cold suite,
  `cached_tokens=0`;
- source snapshot:
  `patches/gemma4-26b-a4b-q8-b70/20260629-packed-gateup-geglu-epilogue-all-source.patch`;
- harness snapshot:
  `patches/gemma4-26b-a4b-q8-b70/20260629-packed-gateup-geglu-epilogue-all-harness.patch`.

Strict128 screen `20260629T220848Z` was mixed:

| Lane | Flag | Summary | Median 1-100 | p10 | Mean | Full | Wall |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| GPU0 control | unset | `data/gemma4-q8-gpu0-packed-geglu-all-control-strict128-20260629T220848Z/summary.json` | 115.36359201087616 | 105.51838617084886 | 116.05306911709694 | 111.08370575299877 | 95.49713609265731 |
| GPU1 `all` | `all` | `data/gemma4-q8-gpu1-packed-geglu-all-on-strict128-20260629T220848Z/summary.json` | 114.51456913459353 | 102.94867560943418 | 114.95891259198055 | 112.816942943214 | 97.4890064805552 |
| GPU2 control | unset | `data/gemma4-q8-gpu2-packed-geglu-all-control-strict128-20260629T220848Z/summary.json` | 117.8021798937828 | 108.14511993865972 | 117.85124628151031 | 112.72554880248433 | 97.41396068487609 |
| GPU3 `all` | `all` | `data/gemma4-q8-gpu3-packed-geglu-all-on-strict128-20260629T220848Z/summary.json` | 119.70078590245942 | 105.45279386388877 | 118.04934833975226 | 114.53586235055363 | 97.75125060786411 |

Cross-over strict128 `20260629T221107Z` kept the idea alive but still looked
variance-heavy:

| Lane | Flag | Summary | Median 1-100 | p10 | Mean | Full | Wall |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| GPU0 `all` | `all` | `data/gemma4-q8-gpu0-packed-geglu-all-on-xover-strict128-20260629T221107Z/summary.json` | 119.89297109093666 | 107.51195604413718 | 117.9259199463953 | 115.69978596328524 | 95.6999604710994 |
| GPU1 control | unset | `data/gemma4-q8-gpu1-packed-geglu-all-control-xover-strict128-20260629T221107Z/summary.json` | 119.5347271072245 | 109.71117043272974 | 119.24045517168885 | 117.3415503044165 | 100.75897548883385 |
| GPU2 `all` | `all` | `data/gemma4-q8-gpu2-packed-geglu-all-on-xover-strict128-20260629T221107Z/summary.json` | 121.6228715661926 | 103.01267204650856 | 119.05377175991143 | 118.19920342805795 | 98.21203236641565 |
| GPU3 control | unset | `data/gemma4-q8-gpu3-packed-geglu-all-control-xover-strict128-20260629T221107Z/summary.json` | 116.1126991250517 | 102.37702527702122 | 114.33801463874316 | 112.78840598258479 | 94.11699931759397 |

Because one strict128 candidate lane reached `121.62 tok/s`, the broad mode
earned a full512 promotion A/B. It failed there:

| Lane | Flag | Summary | Median 1-100 | p10 | Mean | Full512 | Wall |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| GPU0 `all` | `all` | `data/gemma4-q8-gpu0-packed-geglu-all-on-full512-20260629T221338Z/summary.json` | 115.39986817311622 | 105.05530457635551 | 117.6214411594229 | 110.92516002943228 | 105.43002400847689 |
| GPU1 control | unset | `data/gemma4-q8-gpu1-packed-geglu-all-control-full512-20260629T221338Z/summary.json` | 117.56913475871394 | 104.44048718170697 | 116.01295371067509 | 111.26156453851499 | 106.6924078738752 |
| GPU2 `all` | `all` | `data/gemma4-q8-gpu2-packed-geglu-all-on-full512-20260629T221338Z/summary.json` | 115.0369687894787 | 105.13424420501303 | 116.96079024967632 | 109.4327836480729 | 104.98725296353606 |
| GPU3 control | unset | `data/gemma4-q8-gpu3-packed-geglu-all-control-full512-20260629T221338Z/summary.json` | 117.79002928472676 | 107.61009431134823 | 118.98827247458819 | 112.4719286473839 | 106.80626561375718 |

All lanes passed the realistic final gate, canary, and `cached_tokens=0`.
Decision: do not promote and do not submit. The packed GEGLU graph shortcut is
correctness-safe as a default-off experiment, but full512 shows it is a
throughput loss against same-window controls and below the
`117.91456485086059 tok/s` record.
