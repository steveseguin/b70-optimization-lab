# Packet 51 CPU preparation issues — closeout

<!-- campaign-closeout -->

## Question and identity

On 2026-10-17, prepare the second exact-order kernel round for the own-runtime
IQ3 quantized compressed model on B70. Controls are packet45-merged3 plus
the selected packet48b expert kernels. This record concerns CPU compilation,
direct arithmetic fixtures and a declined scheduling idea only. No GPU or
model payload was used for these checks; no speed result is claimed.

## Outcome

Three preparation problems are corrected: the route launch supplied a missing
`Engine::finish` argument; the standalone test now includes its adapter
dependency and avoids an accidental `std::equal` lookup; the Intel test
runner supplies its compiler-library rpath so `libiomp5.so` can load.

The direct IQ2 decoder's nonfinite-scale implementation is **rejected** after
a real Intel CPU mismatch. Routing exceptional inputs through the old decoder
is a proposed repair; its cross-compiler gates are **pending at this closeout**.
This record does not certify that repair or the complete packet. Current
qualification belongs to the final hash-bound gate receipts and seal.

## What worked

The actual production engine interface exposed the missing `gemv` boolean;
route now calls `finish(..., false)`. Compiling the candidate test independently
exposed a transitive include assumption and the unqualified comparison-helper
collision. The helper is now `byte_equal`. These failures occurred before
device contact and are retained rather than hidden by the final build.

After correcting Intel's runtime search path, its test reached arithmetic
and found a mismatch that GNU-only preparation had not established. Keeping
multiple compiler gates separates a working build from byte agreement.

## What failed or remains uncertain

Intel failed direct IQ2 decode check **276870** with half-scale **0x7e01**,
scale nibble **0**, table index **155** and sign byte **155**. The retained
receipt labels this input as unadmitted: unchanged packet48 repacking already
rejects nonfinite weight scales before writing. That admission rule does not
erase the direct-test failure or justify calling its arithmetic exact.
The proposed old-decoder exceptional fallback still needs fresh compiler
agreement, complete-layer checks and later coordinator device checks.

The HC inject single-workgroup idea was not adopted: its scratch writes and
physical launch count differ from the registered production control. This is
a design rejection, not an observed GPU performance failure. Inject remains
unchanged in this packet.

## Evidence and patches

- [Missing finish argument](evidence-cpu/build-host-initial-refusal.log).
- [Standalone dependency and ADL failures](evidence-cpu/build-host-cpu-test-refusal.log).
- [Intel runtime loading refusal](evidence-cpu/intel-1.log) and
  [corrected compiler invocation](candidate_gate.py).
- [Rejected nonfinite receipt](evidence-cpu/nonfinite-rejected/receipt.json),
  [failure log](evidence-cpu/nonfinite-rejected/intel-failure.log),
  [rejected candidate source](evidence-cpu/nonfinite-rejected/candidate.hpp.txt),
  [test source](evidence-cpu/nonfinite-rejected/candidate_cpu_test.cpp.txt), and
  [build identity](evidence-cpu/nonfinite-rejected/build-layer-host.json.txt).
- [Current candidate](candidate.hpp), [direct test](candidate_cpu_test.cpp)
  and [engine adapter](layer_bench.cpp).
- [Packet48's earlier nonfinite closeout](../packet48-gemv/NONFINITE-CLOSEOUT.md).

The rejection receipt binds retained source bytes, Intel compiler identity
and the rejected binary hash. Its binary path is regenerable local build
scratch, not a public artifact; preserve the tracked rejected source and
receipt if that scratch is removed. Rebuilding requires the recorded compiler
and matching baseline objects, with the archived candidate/test sources.

## When to revisit

Evaluate the exceptional fallback only with fresh byte comparisons across
the registered compilers; retain the original rejection unchanged. Reopen the
HC inject scheduling idea only in a separately registered experiment that
explicitly accounts for scratch state and physical launches. GPU exactness
and timing remain coordinator-owned. These closed preparation issues do not
close the optimization lane.

## Qualification follow-up

The exceptional fallback passes all original-vs-candidate comparisons in both
compilers. Phase hashes isolate the inherited compiler difference to the direct
`0x7e01` NaN weight scale. All admitted phases match across GNU, Intel and
ASan/UBSan, and every full diagnostic output repeats within each compiler.
The unchanged repacker rejects all 2,048 nonfinite FP16 encodings without
writing any destination byte. No NaN is canonicalized and no admitted domain
is changed. [Phase diagnosis](evidence-cpu/compiler-phase-diagnosis.json),
[final operator gate](cpu-candidate-gates.json). Complete-layer and device
qualification have their separate receipts; this addendum does not pass them.

## Production binding follow-up

The first full-layer CPU run refused at 24 comparisons because the new route
validator treated explicit error/active input aliases as illegal. The real
three-input production ABI repeats those controls in the tail argument block.
The corrected guard matches the original route42 contract: tail controls remain
distinct, scratch cannot alias inputs/outputs, and outputs remain disjoint.
This changes admission only, not device arithmetic. The refused owner retired
safely. [Source, build and receipt](evidence-cpu/production-alias-refusal/receipt.json)
are retained with their source snapshots; a complete rerun is required.

The complete production rerun now passes in two fresh CPU processes: 5,472
comparisons each across 36 cases, identical raw comparison hashes, and safe
teardown. [Full-layer receipt](cpu-layer-gates.json). GPU gates remain pending.
