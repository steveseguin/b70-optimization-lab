# Packet55 offline locality accounting

No device query, model payload read, or latency measurement occurs here. The
coordinator first completes the route window and runs `route/convert.py`.
From the repository root, use new output paths:

```sh
nice -n 19 taskset -c 4-15,20-31 python3 -B experiments/own-xpu-runtime/stage2/packet55-feasibility/analysis/locality.py \
  --window /path/to/completed-route-window \
  --trace /path/to/routes.jsonl.gz \
  --output /path/to/locality.json \
  --positions /path/to/locality-positions.jsonl.gz
```

Allow about 2–10 minutes for all twelve cache configurations; this is an
estimate, not a measured full-window runtime. No pinned memory is used. The
analyzer streams the compressed trace twice, retains only bounded cache state,
one prompt's coverage sets, and position totals. It does not materialize the
route trace. Anticipated resident memory is below 256 MB for this 24-prompt
scope; measure actual peak with the first real trace. Its JSON summary includes
48 layer rows for each phase and policy, while the larger resident-ID lists
and position totals are in the gzip companion. Keep full outputs with the
window artifacts rather than committing an uncompressed large summary.

The input requires the converter's `.gz.json` receipt, original window,
tokenized calibration manifest, per-request results, native command timings and
compact native traces.
All are checked against the converter's SHA-256 bindings. Calibration must
match the committed 24 independent prompts, with exactly 12 training and 12
test prompts. The analyzer checks token containment against the bound packet49c
benchmark input bundles independently. It refuses missing/unbound traces,
incomplete committed target/draft position coverage, malformed routes and
record counts that do not match the receipt. An early natural EOS is retained
and listed, but sets `requested_scope_complete=false`: it does not satisfy
the requested full 24 × 256-token collection.

All three policies use fixed per-layer quotas. The cache cap is 8, 12, 18 or
24 **decimal GB**, including 4 KiB-aligned expert slots, 64 bytes per slot,
the 48 × 512 direct 32-bit map, and a 64-byte directory entry per layer.
Accounting matches packet46's 18 GB budget exactly: 9,082 slots and
17,998,372,864 bytes. Equal expert counts are assigned to every layer first;
leftover capacity goes to ordinary layers in ascending ID, then layer 2.
The 24 GB scenario is an accounting comparison and does not establish that
the complete one-card runtime fits.

Training replays all target routes from the twelve training prompts, including
prefill, rejected speculation and repeated visits. LRU evicts the least recently
used resident. LFU counts accesses since admission and breaks ties by recency.
For both, all ten selected IDs are pinned as one known route before admission,
so an early miss cannot evict a later selected hit. Static placement chooses
the most frequent IDs within each layer's quota, breaking ties by ascending
expert ID, and freezes the selection before test data is read. These are cache
metadata simulations independently written from the lab trace format. Credit
Niko1221 / Strata for the hot-expert GPU cache and CPU-miss design idea; no
Strata, llama.cpp or vLLM code is used.

Each held-out prompt starts from the same trained snapshot. Its prefill changes
the adaptive cache, and its decode continues from that state. Test-prompt
updates never carry into the next prompt. Initial resident payload bytes are
charged separately for each prompt as cold preload; prefill and decode demand
are reported separately. The combined cold-start transfer total includes
preload plus both phases' misses. That total is a byte-demand scenario, not a
measured transfer cost or a statement that CPU handling transfers full slabs.

The complete draft is assumed resident outside the target cache. Its route
visits and observed expert selections are reported, with zero target-cache
demand. Target routes remain in actual observed per-layer execution order;
using per-layer quotas removes dependence on which split rank's clock appears
first. This is not a prediction of global eviction order in a future one-card
engine. Arithmetic, route probabilities and emitted tokens are untouched by
this offline analysis.

These bytes describe **observed route demand** under an explicit planned cache
admission policy. A speculative rank-0 command can legitimately
stop after a prefix of its layers. Its last router may be logged just before
cancellation prevents those selected experts from running. The diagnostic D2H
copies also change when cancellation occurs. Every observed selection remains
charged here, and LRU/LFU complete every simulated admission even if its command
is canceled. Those admissions change future cache hits, so the result is not a
strict upper bound for an implementation with a different cancellation policy.
The trace does not measure actual DMA or prove that every selected expert actually
executed, or reproduce the uninstrumented engine's speculative work schedule.
`completed_expert_execution_measured=false` makes this limit explicit in JSON.

A static trained cache directly describes a design that computes every miss on
the CPU and leaves GPU residency unchanged. Adaptive LRU/LFU residency requires
H2D admissions: charge their bytes and latency even when the CPU computes the
current miss. Changing GPU residency is not free in a CPU-miss projection.

For each policy, cap, phase and layer, the output gives packed requested/hit/
miss bytes, byte hit rate, missing-expert totals, and the actual histogram of
0–10 misses per route visit. Position rows aggregate **all** visits to an
observed `(prompt, phase, target position)`, including repeated speculative
work; `route_visits` makes this explicit. Mean/p50/p95/max miss bytes per
observed position use nearest-rank percentiles without interpolation. Decode
miss bytes per generated token divide all measured decode miss demand by the
actual emitted-token count in the bound request receipts. Rejected speculative
positions add demand even when they do not correspond to an emitted token.
No miss latency or one-card tok/s is fabricated.

Small verification:

```sh
nice -n 19 taskset -c 4-15,20-31 python3 -B -m unittest discover \
  -s experiments/own-xpu-runtime/stage2/packet55-feasibility/analysis \
  -p 'test_*.py' -v
```

The [CPU receipt](cpu-test-receipt.json) records nine tests: budget agreement,
LRU/LFU behavior and bounded heap, simultaneous selected-route pinning, frozen
static placement, no benchmark contamination, incomplete/bad-weight rejection,
repeated speculative work with test-prompt reset and resident-draft exclusion,
nearest-rank statistics, and a complete converter-to-analyzer contract check.
The contract test creates 24 temporary synthetic requests with 2,333 native
records, runs the real converter and all twelve cache configurations, checks
known byte demand and draft counts, preserves a canceled speculative command
prefix, and rejects tampering with the gzip trace, manifest, window, calibration
source, request result, native binary or command timings. Its
temporary device flags imitate the converter input format only. All fixtures
are synthetic accounting cases, not model output or device evidence.
