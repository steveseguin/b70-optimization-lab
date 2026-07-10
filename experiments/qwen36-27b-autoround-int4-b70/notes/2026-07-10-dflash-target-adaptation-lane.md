# Target-matched DFlash adaptation lane (2026-07-10)

## Status

Implementation and corrected-corpus collection in progress. This is draft
research, not endpoint throughput, not a quality claim, and not LocalMaxxing
eligible.

## Why reopen DFlash

The corrected public Qwen3.6-27B DFlash checkpoint is mechanically functional,
but on the fixed realistic chat suite it produced only `1.731579` accepted
drafts (`2.731579` visible tokens/step) and `52.03 tok/s`. That correctly closed
blind Intel kernel porting around the public checkpoint. It does not close a
target-matched adaptation: the public draft was trained against the original
BF16 target while this lane verifies against the Webhie AutoRound INT4 target
and runtime INT8 LM head.

Upstream DFlash still states that its training recipe will be released later,
so this project implements a bounded local offline adaptation from the paper's
published contract:

- random response anchors;
- one clean target-owned token followed by masked block positions;
- parallel block prediction with target hidden features injected as KV;
- frozen target embedding and LM head;
- exponentially decayed token loss, with `gamma=4` for block size 8;
- exact longest-prefix acceptance as the pre-gate metric.

Primary references:

- <https://github.com/z-lab/dflash>
- <https://arxiv.org/abs/2602.06036>

## Corrected conditioning corpus

The earlier five-aux corpus used layers `1,16,31,46,61`. The corrected vLLM
DFlash extraction uses effective hidden-state indices `2,17,32,47,62`; using
the old corpus would adapt the wrong interface. A fresh four-GPU collection is
therefore running against the separate v6b context suite:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/
qwen27-dflash-aux-v8-corrected5-v6b-4gpu-20260710T040000Z
```

The fixed realistic final suite is not part of training. Endpoint candidates
must still run each final prompt once, cold, with `cached_tokens=0`.

## Implementation

`scripts/train-qwen27-dflash-offline.py` reconstructs the actual DFlash block
from target-owned sequence traces and records per-anchor accepted-prefix rows
for paired prompt/family analysis. It supports:

- evaluation only;
- FC / FC+norm adaptation;
- transformer-layer adaptation matching the paper's scope;
- full-draft adaptation for bounded comparison;
- uniform, paper-style position-decay, and accept-until-fail loss support;
- safetensors export of only the trained draft parameters.

The first four-GPU smoke matrix is reproducible through
`scripts/run-dflash-adaptation-smoke-4gpu.sh` in this experiment folder. It
compares FC, transformer-layer, full-draft paper-decay, and full-draft
accept-until-fail variants on the same heldout anchors.

## Advancement rule

Do not use a fixed scalar acceptance cutoff. Retain paired per-anchor rows and
use prompt/family-clustered confidence intervals. A candidate advances only if
its lower confidence bound improves accepted depth and its candidate-specific
target+draft step-cost projection has material headroom toward `100 tok/s`.
Offline acceptance is never a throughput or target-quality claim. A promoted
candidate still needs the strict fresh endpoint suite, card/order crossover,
repeat64 baseline-quality match, exact identity capture, and a new record above
`68.236263 tok/s` before LocalMaxxing submission.
