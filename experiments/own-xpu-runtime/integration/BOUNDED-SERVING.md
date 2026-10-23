# Reusable bounded serving components

## Question and identity

Can the tested real-model chat path be assembled into a reusable bounded local
session without changing its native engine or inheriting benchmark assumptions?
These components retain the packet198/p199 baseline binary, context 4096, full
BF16 state and 21,552,729,600-byte expert cache. They do not use the later max23
expert-diet record configuration.

## Outcome

The [profile](bounded_serving_profile.py),
[session composition](BOUNDED-SERVING-SESSION.md) and
[evidence writer](BOUNDED-STORAGE.md) pass 37 combined CPU tests: 10 profile,
19 composition and 8 writer checks. The profile verifies actual historical
source, binary, interpreter, dependency and model-stat identity. Socket tests
use explicitly synthetic native components with the real adapter, parking,
chat and lifecycle layers. No native process or device was run for this batch.

The profile always reports `live_admission_ready=false`. It is a reproducible
CPU description, not permission to start a model. The existing live evidence is
[packet199's six-turn pilot](../stage2/packet199-chat-parking/RESULT.md), and the
separate [tiny host-only lifecycle proof](SESSION-LIFECYCLE.md).

## What worked

The proposed session fixes 16 requests, at most 512 new tokens each, 512 MiB of
parking and the existing 256 MiB peak reservation per SAVE. Only three native
argv values differ from packet199: output directory, checkpoint root and
request count. Native idle 300 seconds and total 7200 seconds remain unchanged;
soft limits are 240 and 4800 seconds. Timing provenance must come from the
coordinator, and construction never resets native activity.

A profile binds the complete new component stack, actual packet199 device
audit and reviewed storage-budget receipt. Fresh paths must be disjoint and
local; attachment checks private directories, open root identity, the held
binary, exact argv, fresh owner counters and module origins. The composition
accepts only an already admitted owner and store. It exposes serial loopback
HTTP, guarded RUN/SAVE/RELEASE and metadata operations, and terminal receipts.

The writer exclusively creates small evidence files and checks per-file and
aggregate payload limits before append. Full, failed, replaced or ambiguous
writes halt that writer while preserving existing bytes. It does not truncate
files, set a filesystem quota or signal an owner.

## What failed or remains uncertain

Review fixed held-file identity checks and concurrent receipt reads. Failed
test fixtures and earlier reviewed candidates remain in the linked component
lineage. Receipts refuse while serving or closing, avoiding a race with mutable
parking state.

Sixteen maximum-context requests can evaluate 65,536 positions. Source analysis
bounds successful-path timing/cache rows at 160 MiB. The total 768 MiB forecast
also allocates parking, other native output, routed evidence and driver/cache
diagnostics. Some of those categories remain estimates. The
[storage audit](receipts/bounded-serving-storage-budget.json) does not certify
an aggregate cap for driver caches, native stderr, all failures or filesystem
allocation overhead; no live readiness follows from this forecast.

The outer coordinator still owns startup, reservations, fault monitoring,
memory/disk admission, diagnostic capture, any incident action and physical
drain. There is no launch CLI, service installer, indefinite daemon, restart
recovery, streaming, concurrency or authentication in this batch. Launch time
is a safe conservative initial activity timestamp, but a 215-second model load
uses 215 seconds of the 240-second soft idle period. A later timing origin needs
separate evidence; a received ready event must not silently reset it.

## Evidence and patches

- [Combined CPU receipt](receipts/bounded-serving-combined-cpu.json) and
  [test log](receipts/bounded-serving-combined-cpu.log).
- [Profile tests](test_bounded_serving_profile.py),
  [session tests](test_bounded_serving_session.py),
  [writer tests](test_bounded_evidence.py).
- [Storage source audit](receipts/bounded-serving-storage-budget.json).

```sh
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  /home/steve/.venvs/vllm-xpu/bin/python -B -m unittest discover \
  -s experiments/own-xpu-runtime/integration -p 'test_bounded*.py' -v
```

## When to revisit

Complete a reviewed coordinator around these components, including conservative
native timing evidence and bounded diagnostic handling. Recheck the full storage
forecast and preserve the 27 GB floor before any operational transition. Keep
all existing application restorations, benchmark packages and sealed native
sources unchanged during CPU preparation. A later live session needs separate
admission and receipts; this batch queues no GPU work.
