# 27B usefulness trial: no completed repairs, incomplete recall

This run did not qualify a local coding worker or source-recall assistant.
Both coding attempts produced empty patches, and the single recall request
expired before returning all ten answers. No failed attempt was rerun, repaired
afterward or dropped from the result. The other six coding cases remain unused.

| Attempt | Recorded outcome | Independent review |
| --- | --- | --- |
| Catalog pending headlines | 14 requests, 234.8 s; request 14 exceeded its unchanged 120-second stream limit while generating a large replacement command; no edit executed | Rejected; [packet](results/catalog-packet/summary.json) |
| Context number boundaries | 40 requests, 446.7 s; step budget exhausted after reading the correct parser and repeatedly searching related files; no edit or acceptance attempt | Rejected; [packet](results/context-packet/summary.json) |
| Five-document recall | 14,008 input tokens; one request stopped at the 420-second total limit; no complete response, finish marker or usage receipt | Incomplete; [bound diagnostic review](results/memory/semantic-review.json) |

The recall stream contains 4,000 observed token IDs and seven complete JSON
answer-object prefixes, with the eighth cut mid-citation and the last two absent.
Those prefixes are not a scored or repaired answer. The partial content uses
relevant source material, but long quotations nearly consumed the 4,096-token
output cap. Emitted citations changed source indentation; other partial ranges
were incomplete or exceeded the 20-line bound. Semantic and citation scores
remain unassigned. Extending the timeout alone would not establish usefulness.

## Runtime and preservation

The [first arm](../qwen27b-target-only-pilot-20261007/README.md) passed finite
runtime checks but could not admit the coding sandbox's 24 GiB host-RAM floor.
This separate arm changed only cache allocation to 2 GiB per GPU. Full FP16 KV,
33,024-token context, FP8 revision, TP2 R276 target-only runtime and the frozen
task profile stayed fixed. Startup reported 59,904-token cache capacity and
about 39 GiB available host RAM, versus about 23.5 GiB with automatic allocation.
All eight boundary diagnostics and the original worker-format canary passed;
these are finite controls, not general model-correctness qualification.

After both coding archives were verified, the recall helper's hidden
120-second inner deadline was corrected to honor its already planned 420-second
total limit. Other callers retained their 120-second default. All six focused,
107 worker and 15 existing stream tests passed before the first recall request.
The [application receipt](recall-timeout-correction/application.json) preserves
the timing and source identities; the failed coding attempts stayed unchanged.

One SIGINT stopped the smaller-cache server, exit zero, no OOM or new kernel
fault. All four cards passed postflight and render nodes were idle. The two task
archives were independently verified, fsynced and retained before removing their
disposable source copies. All 80 staged model files were rehashed before their
30,890,049,597-byte RAM copy was released. The full verified model remains on
EX400U, which is cleanly unmounted. No host power, memory, swap or page-cache
setting changed. [Shutdown](results/server/shutdown.json),
[model release](results/model-scratch-release.json), and
[complete result inventory](result-inventory.json).

## Next decision

Do not connect this worker to long-context memory or leave it serving. Preserve
the two distinct coding failures: oversized responses hit a fixed deadline,
while the second task failed to move from investigation to an edit. No single
timeout increase fixes both. A later coding revision needs fresh tasks and an
explicitly identified protocol/budget change, not hints or retries on these cases.

For recall, prepare a smaller interface offline: the model supplies concise
answers and document line ranges; deterministic code copies exact quotations
from the pinned corpus. This can remove quote-copying errors and reduce model
output, but it cannot prove that the selected evidence supports the answer.
Keep semantic review separate and require fresh questions before claiming a
quality improvement. No additional GPU run is queued by this closeout.
