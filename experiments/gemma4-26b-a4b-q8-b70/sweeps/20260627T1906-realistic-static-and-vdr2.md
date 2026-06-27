# 2026-06-27 Realistic Static And VDR2 Strict Sweep

Goal: continue Gemma 4 26B A4B Q8 one-B70 optimization under the realistic
final gate only. Synthetic filled-long and warmed/repeated-prompt scores were
not used for promotion.

Promotion gate for every row below:

- fixed realistic suite `gemma4-26b-a4b-q8-b70-realistic-v1`;
- one cold response per prompt;
- `cached_tokens=0` on every request;
- no prompt/KV/context checkpoint/response reuse, n-gram/history acceleration,
  or warmed repeated prompts;
- UD-Q8_K_XL target/verifier, Q4_0 MTP draft tokens verified by the target;
- primary metric: median generated-token throughput for tokens 1-100 after
  TTFT across the suite.

Prior strict record before this sweep:

- VDR4 `n_max=3`, `n_min=2`, `p_min=0.05`, `UBATCH_SIZE=1024`;
- `87.61145306230438 tok/s` median 1-100 after TTFT;
- LocalMaxxing `cmqwnl2ag03lgqr01ch5bxknq`;
- evidence:
  `data/gemma4-q8-gpu0-vdr4default-mtp-n3-nmin2-p005-ub1024-realistic-gate-repeat-v8/summary.json`.

## Results

| Label | Median 1-100 tok/s | p10 | Mean | Full512 after TTFT | Wall full512 | TTFT ms | Status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gpu0-strict-static-repeat-n3-p005-ub1024-v15` | 83.737254 | 74.243009 | 83.896307 | 80.346207 | 77.650616 | 181.818 | strict pass, below record |
| `gpu1-strict-static-n3-p0045-ub1024-v15` | 81.168079 | 78.139360 | 83.733753 | 80.886772 | 77.775379 | 182.338 | strict pass, below record |
| `gpu2-strict-static-n3-p006-ub1024-v15` | 83.664880 | 73.046647 | 82.808302 | 79.948146 | 77.109988 | 183.546 | strict pass, below record |
| `gpu3-strict-static-n3-nmin1-p005-ub1024-v15` | 84.821346 | 77.387215 | 84.832375 | 79.428941 | 76.801835 | 181.838 | strict pass, below record |
| `gpu0-strict-static-n3-nmin1-p004-ub1024-v16` | 81.556335 | 76.774992 | 82.734233 | 81.610213 | 78.645858 | 181.911 | strict pass, below record |
| `gpu1-strict-static-n3-nmin1-p006-ub1024-v16` | 85.561282 | 75.588309 | 83.514543 | 80.726391 | 77.109985 | 181.587 | strict pass, below record |
| `gpu2-strict-static-n3-nmin1-p005-ub960-v16` | 85.588781 | 79.431355 | 85.733831 | 80.807391 | 78.326951 | 181.512 | strict pass, below record |
| `gpu3-strict-static-n3-nmin1-p005-ub1088-v16` | 80.305023 | 75.493443 | 82.770413 | 80.388420 | 78.115889 | 182.120 | strict pass, below record |
| `gpu0-strict-repeat-record-n3-p005-ub1024-v17` | 84.342243 | 77.680268 | 84.188968 | 81.580046 | 77.751909 | 182.383 | strict pass, below record |
| `gpu1-strict-th6-n3-p005-ub1024-v17` | 81.913042 | 75.477628 | 82.658362 | 78.574419 | 76.487444 | 182.276 | strict pass, below record |
| `gpu2-strict-dth16-n3-p005-ub1024-v17` | 86.225636 | 76.249338 | 85.046822 | 80.312534 | 77.709891 | 182.283 | strict pass, near but below record |
| `gpu3-strict-nmin1-p005-ub960-v17` | 83.479063 | 77.237775 | 84.399235 | 78.429055 | 75.528026 | 181.930 | strict pass, below record |
| `gpu0-strict-vdr2-n3-p005-ub1024-v18` | 87.308002 | 82.854057 | 88.234843 | 84.164545 | 81.190904 | 179.223 | strict pass, VDR2 transfer works |
| `gpu1-strict-vdr2-th6-n3-p005-ub1024-v18` | 87.240185 | 77.994103 | 86.777910 | 83.786668 | 80.951656 | 179.970 | strict pass, VDR2 near-record |
| `gpu2-strict-vdr2-dth16-n3-p005-ub1024-v18` | 87.273715 | 77.706393 | 87.118645 | 84.574511 | 81.775096 | 181.587 | strict pass, VDR2 near-record |
| `gpu3-strict-vdr2-nmin1-p005-ub960-v18` | 84.301627 | 78.612544 | 86.878488 | 84.813283 | 81.699706 | 180.175 | strict pass, n_min=1 not enough |
| `gpu0-strict-vdr2-repeat-n3-p005-ub1024-v19` | 88.905515 | 81.968065 | 89.150555 | 84.893404 | 81.715135 | 180.617 | strict pass, repeat beats old record but not final high |
| `gpu1-strict-vdr2-repeat2-n3-p005-ub1024-v19` | 84.094196 | 77.597114 | 85.631925 | 82.894796 | 79.929671 | 180.494 | strict pass, variance loss |
| `gpu2-strict-vdr2-n3-p00475-ub1024-v19` | 89.455433 | 77.555700 | 87.849492 | 84.451867 | 80.624980 | 181.747 | strict record at the time; superseded by `20260627T2017` |
| `gpu3-strict-vdr2-n3-p0055-ub1024-v19` | 86.307022 | 75.092552 | 86.599448 | 82.267261 | 79.111413 | 179.562 | strict pass, below record |

## Conclusion

The static VDR4 neighborhood and `n_min=1` variants did not beat the prior
`87.611` strict row. The useful transfer was the older Q8 reorder VDR2 build:
at the strict `n_max=3`, `n_min=2`, `UBATCH_SIZE=1024` shape it repeatedly
landed near or above the prior record, then `p_min=0.0475` produced this
note's strict high:

- median 1-100 after TTFT: `89.45543282863798 tok/s`;
- p10: `77.55570003925274`;
- mean: `87.84949240897976`;
- full512 after TTFT: `84.45186668535088`;
- wall full512: `80.62498034849821`;
- LocalMaxxing: `cmqwqzayr03o8qr01j6lgx93n`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-v19-20260627.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-v19-20260627.submit.log`.

VDR2 should remain the strict default for realistic-suite runs. Do not promote
the older synthetic `n_max=7` VDR2 `176+ tok/s` row as real-world throughput;
it is only a diagnostic source of ideas. A later tight `p_min` repeat
(`20260627T2017-vdr2-pmin-tight-repeat.md`) superseded this note's strict high
with `90.32179401019857 tok/s` in the same `p_min=0.0475` family. The
remaining gap toward a fresh-response `>150 tok/s` result likely needs
structural verifier/speculation work, not more isolated `p_min`, `n_min`,
thread, or UBATCH sweeps.
