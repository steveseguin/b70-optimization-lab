# Qwen3.8 Flash-Next FP8 A54 local-read-cap negative

Date: 2026-09-01
Status: bounded host-policy negative after healthy endpoint; no quality or speed credit

A54 established that A53's rank-1 startup exit was transient. All four ranks
loaded the exact 131-shard external checkpoint in `569.69` to `569.94` seconds
at `31.57 GiB/card`, the engine created a 3,456-token KV cache, full decode
graph capture completed in 51 seconds, and the endpoint became healthy. The
frozen recovery canary passed and the unchanged quality battery began.

The server was then stopped deliberately by the supervisor, not by vLLM or a
GPU failure. A54 inherited a local-NVMe read allowance of 8,388,608 sectors
(4 GiB) from A51. The last passing sample was 8,384,888 sectors above baseline.
One second later the counter was 8,392,640 sectors above baseline: only 4,032
sectors (2,064,384 bytes) beyond the cap. The client consequently observed its
owned endpoint close during the first quality request; that transport exception
is a teardown consequence, not the primary failure.

At the stopping sample:

- `MemAvailable` was `29,244,100 KiB`, above the 16-million loaded-state floor;
- swap remained disabled and memory/full-pressure stayed low (`avg10=0.14`),
  far below the frozen `10.0` limit;
- local-NVMe corrected-event delta was 38, below the frozen allowance of 64;
- root-port corrected-event delta was zero;
- no fatal/recoverable link report, controller-down report, OOM, or B70 fault
  occurred.

The 4-GiB rule was intended to reject an accidental 173-GiB checkpoint load
from the internal drive. A54 shows that it is too low for ordinary runtime,
library, graph-initialization, and first-request reads even when checkpoint
weights come from the external drive. A55 therefore raises only this allowance
to 16,777,216 sectors (8 GiB). This remains less than five percent of the model
artifact, while all model, source, inference, quality, memory, swap, pressure,
corrected-event, root-port, fatal-event, and teardown gates remain unchanged.
No reboot or per-boot load rule applies.

Raw evidence:

- `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-2304-ple-only-r1-attempt54`;
- `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-2304-ple-only-r1-attempt54-supervisor`.
