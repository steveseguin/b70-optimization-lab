# Draft device-weight accounting

The unchanged P195 MTP loader and its 3,101-entry official manifest require **3,326,953,472 bytes of draft device weights**, excluding the head and all mutable state/workspace/runtime overhead. This is a source-derived allocation count, not measured peak memory or a fit admission. No tensor payload or device was read.

| Allocation | Bytes |
|---|---:|
| 512 gate + 512 up + 512 down expert weights, INT8 with one FP32 scale per16 values | 3,145,728,000 |
| Other dense weights and widened gains | 181,225,472 |
| Base draft weights | 3,326,953,472 |
| Additional rank0 Q6 expanded full-vocabulary head, 248,320 ×3,380 | 839,321,600 |
| Base plus private full-vocabulary head | 4,166,275,072 |

The 1,536 original FP8 expert tensors hold 2,516,582,400 bytes and their source scale tensors another307,200 bytes. `requant()` stores one byte/value plus four bytes/16-value group; source FP8 scale arrays are consumed during conversion, not additional device allocations. Nine BF16 gains occupy88,576 source bytes and become177,152 device bytes with the loader's `1+gain` conversion. The combined640×2560 BF16 index matrix splits into512-row Q and128-row K allocations whose sum remains3,276,800 bytes; counting the full source again would double-count it. There are33 base device-weight allocations (three expert banks, nine F32 gains,21 BF16 dense matrices).

Rank0 is preferable for fit **if** its target placement has more than839,321,600 bytes of additional headroom versus rank1: that covers its private full-head penalty while moving the3.327GB draft away from a heavier rank1 target/head placement. A rank already holding the unchanged expanded target head can share it with zero additional head-weight allocation; a packed-only target head cannot be shared with the existing draft Q6-expanded path. The new integration requires the full248,320-token draft vocabulary: the historical80,128-row prefix (270,832,640 bytes) is recorded only as excluded history, not an admitted GSQ option. Root's actual target placement census must decide this balance. Rank0 requires the existing confirmed reverse-hidden handoff and compatible draft-rank admission; moving rank alone is not a free execution-policy change.

[Planning JSON](draft-weight-accounting.json) includes every nonexpert tensor, exact source pins and exclusions. Reproduce with [the read-only script](draft_weight_accounting.py). Context-dependent KV, scratch, scores/probabilities, logits/head workspace, allocator overhead, temporary host conversion memory, target allocations and actual available memory remain excluded. Nothing here admits a full model or native qualification run.
