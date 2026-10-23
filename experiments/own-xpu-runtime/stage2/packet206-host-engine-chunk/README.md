# Two-row prefill inside the host Engine

The real experimental Engine now has an opt-in two-row, layer-major prefill
schedule. The designated synthetic host run passed: 16 serial requests and 16
chunked requests produced identical generated tokens, all 13 corresponding
checkpoints matched across every 20 state blobs plus `tokens.bin`, and six
historical p198 checkpoint references matched. All 108 observed nonfinal
endpoints matched: 100 paired chunks and eight single-row tails. See the
[host proof](evidence/host-proof.json).

This is an integration and ordering proof using the existing HOST_ONLY backend
(`Host` → `LifetimeMock` → `MockDevice`). CPU arithmetic and memory copies
execute; events and queue completion remain simulated. No real-model run,
device compilation, device execution, service change or speed claim is included.

## Change and admission

[source_overlay.py](source_overlay.py) deterministically derives a new main and
checkpoint header from pinned p198 inputs; it never edits the originals.
`--p206-host-chunk2` requires HOST_ONLY, `--mini --pipeline-mini`, resident
memory, one owner/card, parallel non-GEMV execution, context at most 128 and no
retained-step dumps. Legacy, MTP, draft capture, canary, priority probe, record
and bracket modes are refused before `Weights` or Engine construction. The
build helper exposes only a host target. Ten actual early parser refusals
created no owner output.

Without the flag the serial compute path remains unchanged. Final prompt-row
head/sampling, ordinary decode and same-generation resume continue through the
original single-row step. Fresh and appended **nonfinal** prompt rows may use
chunks; odd tails and position 31 before a 32-position capacity boundary remain
single-row steps. The 31→32 append fixture includes the saved pending token.

Both variants use the same new binary and the experimental checkpoint identity
`experimental-host-prefill-chunk` / `v1.2+p206`. Binary identity still gates
restore; old p198 states serve as read-only byte oracles, not restore inputs.

## Actual Engine bindings

[chunk_runtime.hpp](chunk_runtime.hpp) allocates two fixed banks for token,
position, streams, embedding and PLE lookup payloads before prepared captures.
Weights, persistent GDN/QSA/PLE state and ordinary M1 intermediates/workspace
remain shared. The four-layer mini plan contains GDN layers 0/2, QSA layers 1/3
and PLE at layer 1.

Each bank separately rebuilds the Engine's `matrices`, `prepared` and
`issue_sites` caches. Changing only `buffers` would leave captured pointers
stale. Canonical decode captures are preserved while the bank's complete
metadata is selected through a scope. Both row captures are rebuilt at a new
QSA capacity extent; no chunk straddles a 32-position boundary. Storage is
never released between requests, so arena generations remain valid.

The prefix initializes both streams, then each real layer executes row0 before
row1. QSA row0 finishes its consumers before row1 changes that layer's KV/pools.
PLE device history advances once per row at layer1; host lookup history is
temporarily staged for the two immutable row payloads, then restored until the
whole chunk succeeds. Every native operator remains M1: this packet introduces
no arithmetic fusion or paired projection kernel.

## Publication and failure

After a clean chunk drain and sticky-error check, the last row's streams and
token are copied into canonical allocations and canonical position advances
by two. Host history is published and checked against native token history.
Per-row global commit operations are skipped. These updates are ordered, not
atomic: any exception poisons the Engine, with no rollback, checkpoint or
serial retry of a partially executed chunk.

The explicit CPU fixture flag `--p206-host-fail-after-row0` requires chunk mode.
Its designated run refused after layer0 row0, retained the original error,
saved no checkpoint and exited unsuccessfully after safe cleanup. Its healthy
underlying owner could drain normally; that does not make the request pass.
No incident signal, kill or retry was needed.

## Evidence and reproducibility

The [build receipt](evidence/build-compile-only.json) pins the new binary,
99 compiler inputs and 33 inherited GNU host objects. The
[overlay receipt](evidence/source-overlay.json) pins parent inputs and generated
outputs. Per-attempt source snapshots and compile logs preserve the initial
candidate, the observer/admission refinement and the final reporting correction;
only the final candidate was executed by the designated coordinator.

[host_probe.py](host_probe.py) and [fixtures.json](fixtures.json) define the
bounded lifecycle, parser refusals, complete checkpoint comparisons and
intentional partial failure. `--p206-host-observe` adds a separately guarded,
read-only serial endpoint hash record. Every chunk's checkpoint-named state
hashes, plus every single-row tail, match that serial observation. Tiny output
tokens alone are a weak oracle, so the full state and intermediate endpoints
are required gates.

From the repository root, compilation is explicit and host-only:

```sh
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet206-host-engine-chunk/build_engine.py --compile-only
```

The existing compiler lock, helper CPU affinity, nice19 and four-GiB address
space bound apply. The harness has a read-only `--plan` and an explicit
`--run-host-only`; the completed output directory is never overwritten.
Generated binaries and raw synthetic run trees stay under ignored `build/`.

## Limits and next step

Mini mode disables expert caching and the production p25/p27 FP32-input paths.
This proof does not qualify the frozen-chunk cache policy, full-model buffer
sizes, production FP32 conversion reuse or asynchronous device dependencies.
The p204/p205 contracts and byte gates remain relevant prerequisites, not
substitutes for those missing tests.

The next meaningful change is to integrate a selected two-row projection into
this Engine scheduling seam, retaining both rows' attention inputs and outputs
while keeping causal consumers ordered. It requires real production Q6 layout
and arithmetic checks, new live-intermediate bindings and a census of the
changed submit path. No additional device work is authorized by this result.
