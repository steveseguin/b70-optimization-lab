# Packet58ap coordinator handoff

Prepared on CPU only. Nothing is queued or launched. The coordinator must run
`seal.py --verify` and `verify_ready.py --output ready.json` immediately before
launch and require `ready=true`. The queue runner repeats that verification.

`verify_ready.py` reads the output argument from
`../../ops/lane-queue/proposed-p58am-v5-A.txt` at launch. It checks the finished
v5 window's bound binary, raw exact requests and recomputed rates. Both B0/B1
must be >=1.005 times both A1/A2; warm-control max/min drift <=3%; all five
views and all sixty requests must be exact. A0 is warm-up only for speed/drift.
This brief's 0.5% release rule is distinct from packet58am's earlier 2% study
rule; neither is a record claim. Missing evidence leaves READY false.

- Fresh unit: `packet58-onecard-58ap-a`.
- Fresh output: `evidence/card0-58ap-a`, which must not exist.
- Fresh fault review: `evidence/fault-review-58ap-a.json`.
- Order: K1a → K1b → KD → W2m → WS → WS128x → WS128.
- Gaps: exactly 90 seconds between completed windows, no retries.
- Whole-host hold: both lanes paused and drained, retained through all gaps.
- Freeze Codex and compiles for timing windows, at least WS through WS128.

The exact closed-environment command and SHA256 are in the orchestration
`READY-FOR-DEVICE.json`; execute only the recomputed `ready.json` command.
Do not run a resident server afterwards.

Every model window explicitly selects resident lookups, demand transfer,
HC-wide/p60fusion, wide64+halfcache, fused other operations, ordered foreground
retirement, tile16, overlap maintenance, zero-copy misses, 21,552,729,600 bytes
of expert cache, context4096 and BF16 KV. Both K1 runs must qualify zero-copy.
Model operation waits are 300 seconds; K1's core also uses 300-second waits.
The native total deadlines and graceful teardown are unchanged from the chain.

Model windows require **99,119,554,560 bytes** of available host RAM, including
the 8 GiB reserve and the demand staging increment. K1 requires 12 GiB.
Retain the 4 GiB shadow stop. Device admission requires **25 GB free root disk
after reserved writes**. No settings, cache drops or automatic recovery.

In-run checks cover stream presence, format and exactness only. Timing/metric
checks run after completion. No detailed demand profiling is enabled for the
record chain. Retain every failed output and stop gracefully on any fault.

Submission is offline preparation only. It requires every exact gate and
WS128 above **31.966820**, the pinned predecessor and current local ledger.
Notes disclose the actual v5 bracket numbers, warm-up, census supersession,
128-token scope and strict512 false. No speed or quality result is claimed
until the coordinator completes and checks this chain.
