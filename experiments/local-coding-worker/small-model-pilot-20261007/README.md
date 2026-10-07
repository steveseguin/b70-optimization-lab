# Small local model pilot, October 7 UTC

The initial host-venv attempt failed before model loading. Its complete failure
record and the separately admitted existing-container candidate are described in
the [R276 addendum](r276-addendum.md). No inference request was sent by that first
attempt, and all four cards passed its before/after checks.

Preregistered separately from the27B evaluation. Qwen3.5-0.8B BF16 is already
local at Hugging Face revision2fc06364715b967f1860aea9cf38778875588b17.
This is a bounded test of whether the existing installed runtime and coding
worker can complete real work. It cannot stand in for the27B trial or qualify
its package. No new model weights are downloaded.

One server startup, one GPU, TP1/PP1, BF16 weights and16-bit KV, no MTP,
no prefix caching, eager execution,16,384 total context. Existing local vLLM
source44fc8fde09fc311d3099dab10366b672d9142ea4; exact source changes and
installed distribution identities are recorded before launch. No native rebuild
or startup retry is part of this pilot.

After host/resource/health admission, first send one tiny streamed transport
canary through the actual worker adapter, with thinking disabled and64 output
tokens. Require token-count agreement, streamed token identities, zero cache
use and valid action format. Do not execute its proposed action. A failed gate
closes this runtime attempt; preserve the reason and stop gracefully.

If it passes, reuse that same server for the catalog-pending-headlines and
context-number-boundaries tasks, once each, in that order. Each has20 model
steps, ten minutes and three acceptance attempts. No task hints or reruns.
A runtime fault ends new requests and triggers one graceful shutdown. An ordinary
coding failure does not restart the server. After both tasks stop the server.
Report small-model outcomes separately; no broad coding-quality claim.

Use unchanged full source snapshots in the existing /dev/shm filesystem,
one at a time. Require at least10GiB scratch and24GiB available host memory,
plus model/runtime allowance. No mounts, RAM/swap/cache or power settings change.
Keep durable stdout and compact evidence copies during execution. Freeze-check,
archive and verify complete source-hash inventory, patch, requests and receipts
on internal storage before deleting only the owned disposable snapshot.
A crash may still lose the newest unfinished temporary evidence.

The server supervisor holds the established host/device locks, records passive
and four-card health checks, watches new kernel faults, starts once and sends
at most one SIGINT to its own server on completion/fault/deadline. It never
resets a driver, changes settings or escalates to a hard kill. Review receipts
before any subsequent experiment.

## Closed: transport works; command format failed

The final R276 canary completed token accounting, stream identities and zero-cache
checks, but returned an unfenced shell script. The actual worker parser rejected
it with FormatError. No proposed command was executed and neither coding task
ran. This is one failed minimal-prompt format gate, not a coding benchmark.
The server stopped gracefully, exited zero, left all render nodes idle, and all
four postflight card checks passed without a new kernel fault. Complete canary
and shutdown evidence is in [format-gate-closeout](format-gate-closeout/).
Do not tune or retry this 0.8B pilot against its observed response. A separately
preregistered pinned 4B W4A16 pilot will test practical coding usefulness.
