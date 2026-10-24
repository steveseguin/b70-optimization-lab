# Combined attention and Q6: all twelve prompt pairs exact

The October24 combined full-engine run passes all24 arms against the original
baseline: every output token and full target-state byte is exact. Independent
readback verified57,701 artifacts /6,338,134,825 bytes. The same persistent pair
served26 fully reset requests: two disjoint excluded warmups and twelve original
prompt pairs. All measured arms reached128 outputs; no cases were discarded.

| Metric | Target-only | Full-head MTP |
| --- | ---: | ---: |
| Decode, interval-weighted tokens/s | 14.853656 | 22.133318 |
| Median prompt decode tokens/s | 14.859250 | 22.200548 |
| Output tokens / decode intervals | 1,536 /1,524 | 1,536 /1,524 |
| Summed decode interval time, ms | 102,601.000 | 68,855.469 |
| Prompt-to-first-output sum, ms | 28,417.012 | 29,567.718 |
| Prompt tokens / boundary seconds | 30.333943 | 29.153417 |

The prompt boundary covers862 input tokens per mode and includes the first
output token; it is not isolated native prefill-kernel time or a512-token prefill
benchmark. Decode counts N−1 intervals per response. MTP is49.01% faster on this
within-run pooled metric, accepting1,160/1,524 guesses (76.12%) and rejecting364.
All emitted tokens retain unchanged target verification, full248,320-token draft
vocabulary, context4096 and full BF16 KV.

Both arm-order groups are retained. Target-first cases measure14.845385 target /
22.093048 MTP tokens/s; MTP-first cases14.861937 /22.173735. Each group contains
six different fixed prompts, so these are descriptive order groups, not matched
causal estimates of order effects.

The original binary's separate baseline measured12.634608 /17.977196 tokens/s.
The new run is descriptively17.56% /23.12% higher. This comparison is between
runs and binaries, not a matched same-owner causal speedup. No isolated-kernel
ratio was multiplied into a model-speed prediction. This short-prompt cap128
screen is not the512-output public performance gate, a long-context result,
an external-engine quality oracle or a new submitted record.

Only48 Q8 attention and22 Q6 GDN-QKV sites switch to existing p33 variant6/split1.
Their exact arithmetic and real-weight micro evidence are retained separately:
[attention](../../../attention-q8-p33/micro/RESULT.md) and [Q6](../../micro/RESULT.md).
Actual logical device allocations match forecast:30,947,490,698 bytes on rank0,
29,824,495,508 on rank1. Total addition versus the original baseline is382,730,240
bytes; no target weights, quantization or KV precision changed.

The run took504.119 seconds including loading, requests and teardown. Both owners
3602010/3602018 returned0 with zero in-flight work/live allocations; no stop
signals or retained owners. Passive records verify target-card drain, unchanged
vision ownership and unchanged historical GPU faults. No service restoration,
restart loop, reset or host-setting change occurred.

- [Independent review](evidence/device-a/review.json), SHA256
  `778ef93e796ec48fdb73c813b78984e8e7354bdd8417bdb53d18e9d06b101b9e`.
- [Compact measured summary](evidence/device-a/summary.json).
- [Exact plan](evidence/operating-plan.json), [storage admission](evidence/storage-admission.json),
  [terminal](evidence/closed-terminal.json) and [native build](../evidence/native-build.json).
- Binary SHA256:`401918bb0fb21db3cd0006dd2ddb7f5047b42e7b8959953050fa60a9ea83f0b4`.
- Raw evidence:`/mnt/usb-models/own-xpu-runtime-results/gsq-attention-qkv-p33-a`.
- Control:`/home/steve/own-xpu-runtime-results/gsq-attention-qkv-p33-a.control`.

Keep the compressed artifact index with the raw data and source auditor. It binds
every physical file's bytes for independent readback, future verified archival
and restoration; it is metadata, not a duplicate payload. Restore missing raw
files only from later explicitly recorded verified archives, checking this index.
The original baseline and earlier attention state files now have separately
recorded archives; their immutable independent hashes remain the oracle.

Retain this combined candidate for further internal work. Next, reduce evidence
file count with a lossless indexed state bundle, preserving the same logical
oracle and repeated RESET/FINISH dumps. Qualify that format change with focused
round trips and one bounded real capture, not another full speed campaign.
