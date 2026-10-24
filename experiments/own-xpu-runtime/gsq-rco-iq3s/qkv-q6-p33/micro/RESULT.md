# Exact Q6 GDN-QKV kernel comparison

On October 24 at 07:26 UTC, one B70 owner completed all84 paired checks and168
kernel submissions. Every full output matched both arms and the original saved
baseline bytes. Independent review passed. Twelve preregistered warmup pairs
are excluded; all72 measured pairs are retained, without filtering.

| Fixed layer | Measured pairs | Control median µs | Candidate median µs | Sum candidate / control |
| --- | ---: | ---: | ---: | ---: |
| 0 | 24 | 222.396 | 69.688 | 0.30330 |
| 24 | 24 | 220.782 | 69.688 | 0.30473 |
| 40 | 24 | 221.615 | 69.427 | 0.30520 |

Both orders improve: all six per-layer AB/BA ratios fall between0.30138 and0.30776.
This compares original packed Q6 p6 SG32 against existing expanded p33 variant6,
split1, at N10240/K2560. Integer codes, exact FP32 scaled weights, BF16 inputs,
ordered eight-element accumulation, SG32 reduction and BF16 output are unchanged.
CPU qualification passed17,915,939 exact comparisons, including every half pattern,
all signed scales for exceptional cases and full10240-row synthetic matrices.
The three real weight tensors contain mostly binary16 subnormal scales; native
whole-output equality passed with their actual values.

This is repeated isolated GPU event latency using three fixed real inputs and
natural cache state. It excludes host enqueue, upload and readback, and is not
model throughput, a cold-response benchmark, a full22-site quality test or a
public speed record. GDN-QKV's earlier aggregate profile includes four formats;
this result must not be applied to that entire aggregate.

The owner exited safely after3.217 seconds, with zero live allocations/in-flight
work and no errors or stop signals. Passive records establish physical drain,
unchanged vision ownership and unchanged historical GPU faults. Device storage
was169,466,880 bytes and transfers171,801,600 bytes, within the192MiB bound.

- [Independent actual-device review](evidence/device-a/review.json), SHA256
  `549fb99606c00e26a0081534152e431e34b2d169bdeb9d20055a1bf0815c17bf`.
- [Admitted plan](evidence/operating-plan.json), with [exact plan join](evidence/device-a/plan-binding.json).
- [Native build](evidence/native-build.json) and [source selection](../selection.json).
- Raw local evidence: `/home/steve/own-xpu-runtime-results/gsq-qkv-q6-micro-a`.

Next is a full-engine candidate limited to the22 identified Q6 GDN-QKV sites,
combined with the separately verified attention change. It adds183,500,800 bytes
on rank0 and104,857,600 on rank1 relative to the attention candidate. Full original
prompt token/state equality remains mandatory before retaining that model change.
Preparation documents keep their original prospective wording and source hashes;
this additive result records the subsequent admitted execution.
