# c2 concurrent token-512 endpoint diagnostic

Date: 2026-08-09

## Outcome

The corrected c2 runner passed both real server attestations and completed the
entire sequential oracle phase. The concurrent phase served all requests and
reached its final external canary, but the client then rejected the timed pair
because one row lacked a uniquely alignable token-512 SSE timestamp.

Failed packet:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal1-formal-c2-gpu0-short-fixed-20260809T165506.933484829Z`

The packet sealed `FAIL`. Both fresh servers fully offloaded `65/65` layers,
passed the corrected two-slot/4-GiB-KV attestation, and returned the card to
43 MiB without a fault, forced kill, listener, or survivor.

## What passed

The sequential phase passed:

- both 512-token streams and deterministic replays;
- both selected-band 128-token slot canaries;
- both natural-stop semantic retrieval checks and their forced-row links;
- the fixed external DNN-off canary on slots 0 and 1;
- cache-zero, exact prompt counts, and clean slot turnover.

The concurrent server log shows the synchronized pair completed and both slots
then passed all later requests through the final external canary. The log also
shows the useful performance shape: prompts were prefetched serially, then the
two occupied slots decoded together at roughly 12.7--12.9 tok/s each in steady
state. These live log rates are diagnostic, not the client metric.

## Failure and evidence gap

The capture failed with:

```text
RuntimeError: missing concurrent timing endpoint
```

The full-512 metric is `511 / (t512 - t1)`. The harness correctly refused to
substitute the request-end time or another token's timestamp. A generated token
can be absent as an individual SSE token event when llama.cpp suppresses an
incomplete UTF-8 fragment, and a concurrent-only output or transport difference
is also possible. Either condition requires evidence rather than an invented
rate.

The old exception path wrote only the error type and message. Although the
client had already collected streams, replays, canaries, and semantic rows, it
did not retain which case or token endpoint was missing. The failed packet is
therefore valid fail-closed evidence but insufficient to classify the cause.

## Diagnostic-only harness change

The capture now treats a missing concurrent endpoint as a normal failed result:

- the row, stream/replay alignment, token IDs, canaries, semantic checks, and
  occupancy counters are retained;
- `timing_endpoints_present=false` and the exact missing endpoint/case/slot are
  recorded;
- aggregate timing, throughput, and fairness fields that cannot be computed
  remain `null`;
- overlap and intrinsic gates remain false, and the process still exits 1.

No correctness or performance gate was relaxed. The new regression test removes
one row's `t512` value and requires a retained failed packet with no aggregate
rate. The complete offline suite is now 17 c1 plus 25 c2 tests, all passing;
Python compilation, Ruff, and `git diff --check` also pass.

One fresh short-band c2 rerun is justified solely to retain the missing row and
determine repeatability. If token-512 is missing again, stop repeating the full
run and debug the native streaming boundary or concurrent token sequence. Do
not switch prompts, use request-end time, or weaken exact endpoint rules to make
the scorecard pass.
