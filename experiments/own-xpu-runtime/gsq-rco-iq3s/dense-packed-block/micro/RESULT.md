# Dense quantization-block decoding: exact native micro passes

All84 full-output pairs and168 kernel submissions pass. Each candidate output
matches both the unchanged scalar control and saved original-baseline output
byte for byte. Independent readback verifies positive actual backend contact/ACK,
clean zero-live teardown, physical drain and unchanged fault/vision/queue state.
There were no stop signals or retries.

| Fixed case | Format | Control mean µs | Candidate mean µs | B/A | AB B/A | BA B/A |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| layer0 gdn.z, N6144/K2560 | Q4_K | 255.681458 | 50.429667 | 0.197236 | 0.190028 | 0.204885 |
| layer1 gdn.qkv, N10240/K2560 | Q5_K | 466.770875 | 87.222250 | 0.186863 | 0.184399 | 0.189464 |
| layer2 gdn.z, N6144/K2560 | IQ4_XS | 210.707417 | 53.034000 | 0.251695 | 0.249333 | 0.254068 |

Each row retains all24 measured pairs,12 per order; four excluded warmup pairs
per case precede measurement. Measured case position is balanced. Results are
isolated kernel device-event timings on fixed diagnostic inputs, not model
throughput, a cold benchmark, or a public record. No outlier was removed.

The116-site candidate hoists repeated quantization-block metadata conversion,
retaining every original float operation boundary, lane accumulation sequence,
SG32 reduction, BF16 output and weight byte. It adds no resident allocation.
The CPU proof already passed223,685 checks including exceptional values. These
three native cases justify preparing full-engine qualification; they do not
qualify every model request or establish end-to-end speed.

[Independent actual review](operating/evidence/device-a/review.json):
`eb32d725dc99fb16421405b25ef2324f186c100b537044160ce1f534b219a665`.
Binary: `526f869210d28c61d8745c8e573c14604bb1b254d0df8aa7d0791a3c20d2461d`.
Build: `79b6374fd5862535fbbcca7788374ad3ba4bc988876415273d841d6456c24605`.
Plan: `1e7297d13108dbec368a0162761b445caf706afac7f8432df4a9137181036197`.
Coordinator duration1.429seconds includes startup, copies and closure.
