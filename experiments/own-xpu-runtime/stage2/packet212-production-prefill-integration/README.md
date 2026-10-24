# P212 production prefill integration — compile-only preparation

This additive P198 overlay connects the two-row schedule to the full production
Engine and the unchanged P208 paired Q6 operator. It has **no executable
qualification**. The public `main` always returns 64, for every argument, before
parsing options, opening model payloads or constructing a device. A separately
named `p212_future_entry` remains compiled and linked for later reviewed work.
P198/P201 executables and their operational entry points are untouched.

The shared [schedule](production_schedule.hpp) is used by both the Engine helper
and the [CPU metadata fixture](schedule_fixture.cpp). Its 97 checks and seven
artifact tests cover the actual recorded 1,486 logical sites: 48 layers, 35 Q6
GDN layers with 70 paired projection commands replacing 140 original commands,
original M1 Q8 projections at layer 2, and 12 original M1 QSA layers. Empty fused
HC follower slots remain in the schedule. This validates selection and traversal,
not device arithmetic or completion. See [authority](AUTHORITY.md).

## Actual integration boundaries

[ProductionChunks](production_runtime.hpp) makes fixed row views before capture,
rebuilds matrices/prepared operations/issue sites for each view, and retains row
streams, token, position, embedding and PLE lookup. The paired layers also retain
separate HC mix/injection and qkv/z allocations. Their exact byte budget is
derived from the actual Engine buffer types/extents and would be recorded in
`p212-row-storage.json`; it is not an assumed approximate constant. The two
4-byte paired workspace handles are distinct ABI bindings, not measured scratch
use. Persistent GDN/QSA/PLE state, selected expert operators, weights and other
scratch remain shared. Captured host metadata and command storage are additional.

The helper consumes the shared ordered steps, staging real lookup/history data
before issue and retaining causal row ordering for shared state. It pairs only
exact selected `p33.dense.segment` Q6 K2560/variant6/split1/stride3380 matrices;
layer 2 Q8 executes its original selected operators. Existing IQ2 diet, IQ4 tiled
down and selected IQ3 fallback paths are not replaced with the P211 tiny F32
adapter. Selected P201 dispatch has no active p25/p27 prepared FP32 consumers;
other dispatch configurations are outside this admission.

[CacheInterval](cache_interval.hpp) freezes the existing 144 published tables and
cache payloads over two rows, retains all 96 row/layer route records with actual
CopyEngine transfers, and replays routes chronologically after completion.
Every issue checks cheap lifecycle/generation state; full retained-allocation
and Cache metadata scans occur at interval boundaries. Metadata comparison is
not a device-table readback. The overlay guards actual fill/publication/capacity,
mode, reset and protected upload paths against active readers and forbids
prepared issue during an update. Route-copy events are consumed before all
three Engine retirement sites. Hidden indirect storage remains owned by the
Engine until drain and close.

This is the explicitly different **serial frozen-two-row cache policy**. Startup
requires zero-copy misses and serial maintenance; it never toggles a live overlap
policy. Existing serial publication performs **144 CopyEngine transfers**, unlike
P201 overlap's single publication kernel. Native qualification and measurement
must decide its performance; this packet makes no gain or speed-readiness claim.
The pair loop adds no per-pair device-status readback. Boundary status checks,
ordinary final-prompt/decode execution and checkpoint disposition remain explicit.

Final streams/token/position are copied to canonical storage only after the
interval and cache update finish. PLE token history is checked before publishing
host history. These copies are ordered, not atomic. Any failure poisons intake;
there is no fallback, partial-chunk checkpoint or rollback claim. The current
helper's update flag is conservative and is not a precise Cache phase mirror.
It can say updating while Cache is still ready when `prepare` refuses before
its final phase transition. It can also remain updating after Cache has already
committed to idle if later `fill_cache` statistics/log saving throws. In either
case `close_failed` can refuse the mismatched phase and retain the owner despite
a completed device drain. P212 does not establish that every failure can
cleanly close; precise transition hooks and both failure cases are required
before full Engine native qualification. Future chunk
progress is recorded once at start and once after successful canonical/cache
publication, including 70 pair commands, 140 skipped originals and elapsed time.
Ordinary `timings.jsonl` covers ordinary steps only; chunk elapsed time lives in
`p212-chunks.jsonl` and is not a measured result in this packet.

## Compile recipe and evidence

The single native compile/link/offline-inspection attempt passed. The
[build receipt](evidence/build-compile-only.json) binds 101 compiler dependencies,
38 inherited objects, the retained future-entry symbol, both Q6 paired kernel
entries and the disabled public entry. The
[main disassembly](evidence/build-1792802843616050951/public-main-disassembly.log)
shows only refusal output followed by return 64. The extracted translation-unit
device bitcode is 36,792 bytes; this is image presence, not execution authority.
No resulting native artifact was invoked.


[Build preparation](evidence/build-preparation.json) retains generated source,
commands, parent hashes and 38 reused native objects. The exact backend source
`single_device.cpp` is linked to the reused object by P181's historical build
receipt and copied build inputs. Source shows an ordered compute queue and a
BCS copy followed by a compute barrier; this is a source-derived ordering
argument, not native execution evidence.

The [build helper](build_native.py) snapshots each attempt before source
generation, checks parents and objects, and enforces a fresh 27 GB root floor
**after reserving 768 MiB**. CPU helpers use nice 19, cores 8–15/24–31, two
OMP/BLAS/MKL threads, a 4 GiB address-space ceiling and the existing compiler
turn lock. It compiles only the new translation unit, links the pinned objects,
and inspects ELF symbols and SYCL image/kernel entries offline. It never invokes
the resulting artifact. Compiled output and Python caches are ignored.

Preparation, with no compiler invocation:

```sh
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  taskset -c 8-15,24-31 nice -n 19 /home/steve/.venvs/vllm-xpu/bin/python -B \
  experiments/own-xpu-runtime/stage2/packet212-production-prefill-integration/build_native.py --prepare-only
```

After independent source/build admission, the same helper with `--compile-only`
performs compilation and offline inspection. No GPU enumeration, model loading,
owner launch, service/queue operation or settings change is part of this packet.
A future separately admitted native comparison must establish actual output and
full checkpoint equality, cache-policy parity, failure retention and timing.

## Retention and next gate

The prepare-only attempt and the single successful compiler attempt retain exact
local/generated source snapshots, commands, compiler output, hashes and offline
inspection logs under `evidence/build-*`. No failed native compiler attempt or
native owner run occurred. The tester separately retained its metadata-helper
precompiler failure and correction. Ignored build binaries/images remain local
artifacts with hashes and a checked-in recipe; no raw model payload or native
execution archive is created or implied.

P213 first needs a matched row-serial frozen-two-row control in the same binary
and precise cache transition/failure-cleanup hooks, including the two retained
cases above. The next native gate is separately admitted selected-native correctness,
not another metadata-only schedule packet: first establish paired Q6 versus
selected serial p33/CPU reference on synthetic full-shape inputs, then compare
this real Engine's two-row path with a matched serial cache-policy control on
the same new binary. That comparison needs actual first-use row captures,
canonical publication, all saved-state bytes, append/pending-token behavior,
route/cache epochs and failure retention before any timing claim. A direct
P201 policy comparison is separate because maintenance cadence changed. Device
availability, fault baseline and resource admission remain external prerequisites;
this packet creates no manifest, launch path or authority to disturb daily apps.
