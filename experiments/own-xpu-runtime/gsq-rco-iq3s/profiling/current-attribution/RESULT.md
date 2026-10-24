# Exact sampled expert-format attribution

The current qualified engine passed the fixed target-only request and independent
full-state readback. All128 output tokens and target buffers match the original
baseline; both owners exited normally with empty target descriptors and no new GPU
faults. No arithmetic, weights, precision, routing, verifier or KV policy changed.

The existing recorder captured6,912 routed events across both ranks: eight halves
per rank, fixtures9–16, absolute target positions94–101. These are early generated
steps after the87-token prompt, not prefill. Each actual full label was joined to
its exact graph weight and census format. Event durations were independently summed
as integer nanoseconds with complete expert projection coverage and conservation.
The sample is not a whole-decode average or a speed benchmark.

Total sampled routed event time: **192.148198ms**.

| Class | Actual format | Events | Event ms |
| --- | --- | ---: | ---: |
| expsdown | IQ4_NL | 312 | 31.614377 |
| expsgate | IQ3_XXS | 136 | 27.620520 |
| expsup | IQ3_XXS | 136 | 27.502191 |
| route | none | 1920 | 26.258949 |
| expsup | IQ2_S | 160 | 14.020936 |
| expsgate | IQ2_S | 160 | 13.972286 |
| expsdown | Q2_0 | 72 | 9.240840 |
| gather | none | 768 | 8.884048 |
| expsgate | IQ3_S | 80 | 6.875211 |
| expsup | IQ3_S | 80 | 6.814478 |
| router | BF16 | 384 | 4.533536 |
| ffn.combine | none | 384 | 4.302402 |
| moe | none | 768 | 2.042080 |
| expsact | none | 384 | 1.562698 |
| expsgate.check | none | 384 | 1.525626 |
| expsup | IQ4_XS | 8 | 1.499688 |
| expsgate | IQ4_XS | 8 | 1.497917 |
| expsdown.check | none | 384 | 1.199480 |
| expsup.check | none | 384 | 1.180935 |

IQ3_XXS gate/up together take55.122711ms, the largest combined format cost in this
sample. Select one exact packed block-decoding candidate for these projections.
Hoist repeated block metadata work while retaining the existing lane accumulation
sequence, SG32 reduction and BF16 output. Its benefit is unmeasured until native
comparison. The actual graph uses ten per-slot gathered inputs; those inputs,
all routes and the gather operations remain unchanged. The initial coordinator
suggestion of shared-input mode was corrected from actual source before coding.

The existing expanded-weight GEMV changes lane accumulation order and is not a
drop-in exact replacement. Whole-bank expansion also exceeds the memory budget.
See the [source appraisal](CANDIDATE-APPRAISAL.md). A new weight-cache subsystem is
not part of this selected narrow candidate.

| Identity | SHA256 |
| --- | --- |
| Native binary | `5a8c9d3b58606022e21e2f0347360e4dd9cfdf6a869c8daac145e928fe4d4306` |
| Operational plan | `1c1512c80116979b4e336e2b708c01b63886d1b4c6579cac1a35fd5ceb51f0a5` |
| Full result | `943868c7766990db597e30ff73e79caf3ffa050433d8e41f9e3f98b3aa6899d5` |
| Independent audit | `469fe156e317fc1aa93a56cf2a803d8d0c1cf786e13fe6d391d7eb50c883c7aa` |

[Independent review](evidence/device-a/review.json),
[summary](evidence/device-a/summary.json) and
[artifact index](evidence/device-a/artifact-index.jsonl.gz) bind163 physical artifacts,
718,483,227bytes, including six bundles/6,324 ranges/665,229,504target payload bytes.
Keep the index and raw evidence at
`/mnt/usb-models/own-xpu-runtime-results/gsq-current-attribution-a`; coordinator
receipts are at `/home/steve/own-xpu-runtime-results/gsq-current-attribution-a.control`.
The [bundle reader](../../state-bundle/reader.py) reconstructs all logical hashes.
Initial and warmup semantic comparisons remain informational. Orchestration took
116.821seconds including loading and evidence; this is not an inference rate.
