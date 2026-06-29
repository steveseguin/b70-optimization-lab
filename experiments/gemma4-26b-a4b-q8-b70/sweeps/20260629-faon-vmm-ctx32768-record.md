# 2026-06-29 FA-on 32K/VMM Record Retest

Status: promoted small improvement for the Gemma 4 26B A4B Q8 realistic-suite
lane. LocalMaxxing: `cmqzq5zu402troe01t774uyox`.

## Why

The long-context diagnostic found that `FLASH_ATTN=on` removes the MTP cliff at
27K-32K context. Because the strict short record had stayed FA-off at 8K, this
needed a fixed realistic-suite retest before changing the promoted recipe.

## Gate

All promoted rows below use:

- fixed realistic suite:
  `repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`;
- one cold response per prompt;
- `cached_tokens=0` for every request;
- no prompt/KV cache reuse, context checkpoints, response reuse, n-gram/history
  acceleration, or warmed repeated prompts;
- UD-Q8_K_XL target/verifier with Q4_0 MTP draft verified by the target;
- 512/512 chat canary rows passing.

## Screen

Initial four-lane screen:

| Lane | Summary | Median 1-100 | p10 | Mean | Full512 | Wall512 | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| FA-off ctx8192 control | `data/gemma4-q8-gpu0-faoff-control-full512-20260629T211437Z/summary.json` | 116.68098820086227 | 102.37342322422433 | 114.90112744326632 | 105.80463745486313 | 102.14180942015426 | hot same-time control |
| FA-on ctx8192 | `data/gemma4-q8-gpu1-faon-ctx8192-full512-20260629T211437Z/summary.json` | 112.31939127173402 | 106.07990972770011 | 114.95734849771549 | 108.38689759270375 | 104.03918478195868 | no short-ctx primary win |
| FA-on ctx32768 VMM0 | `data/gemma4-q8-gpu2-faon-ctx32768-full512-20260629T211437Z/summary.json` | 117.6427742652139 | 104.45400529183729 | 114.3346661421965 | 112.37777240432736 | 106.78411649698535 | candidate |
| FA-on ctx32768 VMM1 | `data/gemma4-q8-gpu3-faon-vmm-ctx32768-full512-20260629T211437Z/summary.json` | **117.91456485086059** | 107.80735938671545 | 118.8805550250879 | 110.957638362282 | 106.80689050225271 | promoted candidate |

Same-identity confirmation batch for FA-on ctx32768 VMM1:

| GPU | Summary | Median 1-100 | p10 | Mean | Full512 | Wall512 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 0 | `data/gemma4-q8-gpu0-faon-vmm-ctx32768-confirm-full512-20260629T211843Z/summary.json` | 116.45776605647993 | 100.52805362848677 | 116.40736141241894 | 112.21083560224112 | 106.58846715929698 |
| 1 | `data/gemma4-q8-gpu1-faon-vmm-ctx32768-confirm-full512-20260629T211843Z/summary.json` | 117.41509141115063 | 102.82580425522343 | 116.89697181871713 | 108.37433815430438 | 104.58702581027498 |
| 2 | `data/gemma4-q8-gpu2-faon-vmm-ctx32768-confirm-full512-20260629T211843Z/summary.json` | 115.08942949119734 | 107.00399050168588 | 116.51674286549678 | 107.47895026970602 | 103.39173316785484 |
| 3 | `data/gemma4-q8-gpu3-faon-vmm-ctx32768-confirm-full512-20260629T211843Z/summary.json` | 117.45737477243767 | 107.32460490342444 | 116.49336180116973 | 110.76279573353797 | 106.13772714309907 |

## Conclusion

Promote `117.91456485086059 tok/s` as a valid realistic-suite record. This is a
small variance-class improvement over the previous `115.8466634928202` row:
3/4 same-identity confirmations beat the previous high, one lane did not. The
change is still useful because it also unifies the short record with the 32K
service profile (`FLASH_ATTN=on`, `CTX_SIZE=32768`,
`GGML_SYCL_ENABLE_VMM=1`) without lowering quality or using warmed/cache reuse.
Server logs for the promoted row and same-identity confirmations are copied to
`data/*.server.log` next to the summaries.

Reproduction:

```bash
cd /home/steve/qwen36-results-main
GPU_INDEX=3 PORT=18533 \
FLASH_ATTN=on CTX_SIZE=32768 GGML_SYCL_ENABLE_VMM=1 \
MAX_TOKENS=512 REALISTIC_GATE=1 CANARY_REPEATS=128 \
LABEL=gemma4-q8-gpu3-faon-vmm-ctx32768-full512-$(date -u +%Y%m%dT%H%M%SZ) \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh
```

Do not infer that FA-on at 8K alone is a primary-metric win; the `ctx8192`
FA-on lane lost the screen. The promoted identity is specifically FA-on plus
32K context plus VMM under the current VDR2 selected-down record stack.
