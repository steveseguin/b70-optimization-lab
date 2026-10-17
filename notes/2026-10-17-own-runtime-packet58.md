# Packet 58: one-card IQ3 engine

## Scope and starting state

Implement a separate packet from packet 56 for one-card target-only greedy
inference with an 18 GB expert LRU cache and exact host-backed misses.
The coordinator runs all GPU windows. CPU preparation runs on steve-b70s,
nice 19, cores 4–15/20–31. Full pinning, GPU measurements, MTP and full-model
exactness remain pending until their gates run.

Initial `git pull --rebase` refused because packet57-attribution had a dirty
README. It was not stashed, edited or committed by this task. `git fetch
origin main` then showed HEAD and origin/main identical (0 ahead, 0 behind).
Root free bytes were 13,573,136,384. This task has a 1.5 GB build ceiling;
no other job's artifacts may be removed. The current memory-fence contract
requires blocks 54/56 offline and records 53/55/57 as best-effort margins.

Parallel assignments cover host memory/window admission, cache and lifetime
CPU gates, and kernel/engine integration. Root owns integration, submission
preparation, review and focused commits. No GPU, service, sudo, model payload
read or host-setting change was made while writing this entry.

The submission ledger has only 2-card own-runtime records for this IQ3
model, no matching submitted 1-card record. Packet 58 uses a new lineage;
no two-card speed threshold is inherited. Strict 512-cap promotion remains
false for the requested 128-token comparison scope.

Credit Niko1221 / Strata for the hot-expert cache idea, without adopting any
external code. See the packet README for the implementation boundary.

## Memory and coordinator admission prepared

The census charges 48,627,712,000 B of pinned experts. The target-only device
bound is 26,409,219,600 B, including the 18 GB cache, expanded nonexpert
weights, full 4K BF16 KV/state, tables and workspace/transfer allowances.
This leaves 4,090,780,400 B beyond the required 1.5 GB reserve against the
conservative 32 GB card capacity. No draft is included.

Host admission requires 118,308,908,048 B available, including a full device
allocation shadow, file-backed nonexperts/lookup tables and an 8 GiB reserve.
The passive CPU snapshot passed; it is not permission to rely on that old
headroom at launch. Window admission checks it again just before starting.
No pinned allocation or model-payload read was made.

Six accounting and twelve window tests pass. Guards retain the failing-memory
54/56 contract, record margin blocks, use PF_EXITING-aware process sensors,
reject future fault-review boundaries, preserve faults and admit one chosen
card only. K1 gets two fresh processes. Full-model windows require both K1
receipts and the preceding successful gate. Each full-suite window has a
one-hour graceful watchdog, never an automatic retry. Commands are in
`experiments/own-xpu-runtime/stage2/packet58-onecard/WINDOW.md`.

## Engine and CPU gates

The single-card engine now holds all 48 target layers. It packs the full
expert bank into pinned host storage only inside an admitted native window,
with exact production byte layouts. All expert kernels use device pointer
tables for either host memory or the 18 GB device arena. The normal path reads
routes after each complete position; the streamed fallback reads each layer's
routes before use. Both use a dedicated copy-only queue with fenced table
publication. Fill waits are included in token latency; overlap is not claimed.

The cache begins empty and survives requests. A persistent suite loop clears
all mutable model state for each request. CPU comparison of a prompt after a
different prompt matches two fresh processes, including 40 retained files.
Request-reset work is included in TTFT. Cold load/pin time and cache fills are
recorded separately. There is no target prompt/KV/response reuse.

Eight fresh CPU cache/expert runs pass, including ASan/UBSan: randomized LRU
and lifetime fences, generation/ABA rejection, failed fills, and 36 complete
expert cases comparing hit/miss/mixed pointers to frozen production kernels.
The production-submit CPU adapter additionally passes 24 placement comparisons
across the three expert grid formats. GPU pointer accessibility and timings
remain unmeasured.

Independent review fixed an untracked DMA error path, required both queues
to drain before propagating errors, corrected pinned-byte reporting, tightened
prerequisite evidence coverage and prevented sibling-window substitution. K1
uses distinct timed host regions so GPU cache cannot masquerade as PCIe speed.
Both device K1 runs must match the CPU golden hash and one another.

A CPU replay of 403,168 retained packet55 route records supports testing global
LRU: 93.64% decode byte hit versus 92.46% for the fixed layer quotas. The replay
uses two-card/speculative observations and layer-by-layer admission, so neither
number is a measured packet58 hit rate. Fragmentation and empty persistent
placement are retained in CACHE-POLICY.md and its compact JSON.

The new offline submission helper reconstructs the primary 99-interval rate
and exactness from original receipts, using only a matching 1-GPU record floor.
It prepares a payload draft and hash-bound quality attestation after device
gates. It never posts. The 128-token scope has strict_512_gate_passed=false;
a two-card external exception is not silently reused for this new lineage.

MTP is deferred: the initial passive snapshot had only 1,953,649,648 B beyond
the conservative target-only host admission floor, less than the 3,354,364,214 B
draft residency alone would add to the reserved shadow. It needs a new admitted
budget and measured serial-draft benefit. No draft weights were read here.

## Final CPU handoff

GNU host and Intel native compilation pass with 173 source hashes per build.
The final tree occupies 147,167,317 bytes. All 44 Python checks, eight fresh
cache/expert runs, the production-submit CPU fixture and the persistent-reset
comparison pass. The final seal binds 232 source files, four binaries and six
gate receipts. The read-only launch build gate, packet49 oracle binding and
queue plan also pass. No device binary ran. The build revision identifies
the implementation commit; the source hashes bind the final documentation
overlay as well.

Pushed preparation commits are `5739a1ef8` (scope), `cca980ed0` (memory and
windows) and `653021460` (engine, gates and submission preparation). The final
handoff commit records the updated authority and refreshed seal. Only this
packet, this note and CURRENT.md were changed by this task.

The coordinator's serial chain plans 6,440 seconds including cooldowns
(about 107 minutes); watchdog allowances total 17,000 seconds including those
cooldowns. These are scheduling bounds, not measured run times. Fresh host
admission remains mandatory. Unsupported host USM fails closed at K1;
supported but slow zero-copy selects the implemented streamed fallback.
Fills are fenced and charged to token timing, with no overlap claim.
No matching submitted one-card IQ3 record was found in the pinned ledger.
Submission output remains an offline draft until device gates and the new
lineage's external 128-token scope review are complete.


## Packet 58b — repair K1 startup (October 17, CPU only)

The card0-a K1a process stopped after 5.29 seconds with Level Zero error 44,
no kernel fault lines, and an empty `run/` directory. `Runner` constructs the
SYCL backend before opening `k1-cases.jsonl`, so this failure precedes every
fixture allocation and kernel. K1 does not load the full model or allocate
the 48,627,712,000-byte expert bank.

Source localization identifies the native copy-queue import in
`single_device.cpp`: `zeCommandQueueCreate` produces a regular
`ze_command_queue_handle_t`, which is passed to `sycl::make_queue`. The
installed SYCL header marks that variant as non-immediate. Intel's UR Level
Zero v2 `urQueueCreateWithNativeHandle` explicitly returns
`UR_RESULT_ERROR_UNSUPPORTED_FEATURE` for it. The installed v2 library also
contains that exact rejection diagnostic. This is a source-based diagnosis;
no GPU tracing or probe was run.

References: [pinned Intel adapter source](https://github.com/oneapi-src/unified-runtime/blob/f6fa8290508657eaf9ab901118c876f2e890258b/source/adapters/level_zero/v2/queue_create.cpp),
[Level Zero immediate command lists](https://oneapi-src.github.io/level-zero-spec/level-zero/latest/core/PROG.html#immediate-command-lists),
and [local evidence and adapter hash](../experiments/own-xpu-runtime/stage2/packet58b-onecard/evidence/root-cause.json).

The separate `packet58b-onecard` copy uses
`ze_command_list_handle_t` + `zeCommandListCreateImmediate` with
`ZE_COMMAND_QUEUE_FLAG_IN_ORDER`, on the same dedicated copy-only ordinal
and in asynchronous mode. Both cleanup paths use `zeCommandListDestroy`.
Copy fences, explicit ownership, arithmetic, kernel order, packed bytes,
cache policy, host allocation and model selection remain unchanged. Neither
chunking nor forcing streaming fixes a constructor import failure, so those
paths were not changed speculatively. The existing two-K1 decision still
selects zero-copy or streamed operation after exact byte gates.

The changed-path CPU fixture compiles the actual constructor fragments with
a mock of the documented import contract: parent returns 44, repaired handle
passes while checking the copy ordinal, native in-order flag, asynchronous
mode, context and ownership. The existing cache/expert gate runs once each,
without sanitizers: 213,816 cache checks and 36 expert cases / 1,522,656 bytes
compared. This is CPU evidence only, not hardware acceptance.

Initial `git pull --rebase` was blocked by the other job's dirty packet59
files; `git fetch origin main` showed no incoming commits. Those files were
not stashed or edited. All work here uses nice 19, cores 8–15/24–31, Python
-B and small local builds. No GPU, sudo, services, model payload, host setting,
reboot or process termination was used. Original sealed packets and
`stage2/screen/` remain untouched.

[58b closeout](../experiments/own-xpu-runtime/stage2/packet58b-onecard/CPU-PREPARATION-CLOSEOUT.md)
and [exact coordinator commands](../experiments/own-xpu-runtime/stage2/packet58b-onecard/WINDOW.md).

Final 58b checks: device and GNU host builds pass, 173 source hashes per
build, retained build 148,319,943 bytes. The host production K1 fixture passes
24 placement comparisons with the unchanged parent golden hash
`8ba3faa72a04985c65ea1b27d9cba2379a0fa91e00ac912334c4d86ab399c303`.
The small reset fixture matches 40 retained files and all 44 Python checks
pass. The original packet58 seal still verifies. Device acceptance is pending.

Exact coordinator command, from repo root inside the existing coordinator-owned
`packet58-*` user unit, using its genuinely reviewed UTC fault boundary and
approved library path. This command was prepared, **not executed** here:

```bash
P=experiments/own-xpu-runtime/stage2/packet58b-onecard
nice -n 19 taskset -c 8-15,24-31 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$P/queue_runner.py" --authorized-device-window --card 0 \
  --output-root "$P/evidence/card0-58b-a" \
  --faults-reviewed-through "$REVIEWED_THROUGH"
```

Order remains K1a → K1b → KD → W2m → WS → WS128x → WS128.
No retry or automatic fallback to another card. K1 failure ends the queue.
