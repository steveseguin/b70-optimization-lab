# Laguna M12 inline-gather composition diagnostic

Date: 2026-08-01 America/Toronto

Status: **preregistered component diagnostic only; no model or score is
authorized by this note.**

## Motivation

The protected exact BF16-KV record is `125.4619731637751 tok/s`
conventionally. Reaching 130 requires about `1.13 ms` less verifier-cycle
latency at unchanged acceptance. The target still crosses 96 eager TP4
all-gather boundaries per cycle, so this is one of the few remaining seams
with enough structural scope.

The earlier default-off inline-gather treatment reached its intended target
topology (`50/49` instead of `146/145`) but its first model smoke failed a
combined response-prefix/cache assertion. The response was not persisted, so
that artifact cannot distinguish a token mismatch from a cache-field failure
or localize a first bad layer. The unchanged treatment remains rejected and
will not be rerun.

There is narrower evidence in the opposite direction: the earlier direct XPU
graph probe replayed 97 M8 BF16 all-gathers and literal rank-ordered sums with
changing inputs exactly on all four ranks; only its deliberately included
final ordinary all-reduce failed on sample 2. That component used M8 and one
monolithic graph, whereas the rejected live treatment used M12 and crossed 48
eager attention boundaries. The missing evidence is therefore the actual M12
segmented composition, not another endpoint attempt.

## Frozen diagnostic

Add a new standalone TP4/XCCL fixture that compares two independent buffer
sets on the same four healthy B70s:

1. an eager control;
2. a candidate made from 48 sequential XPU graph segments;
3. each layer segment produces two local contiguous `[1,12,3072]` BF16
   tensors, performs two `all_gather_into_tensor` calls into fixed
   `[4,12,3072]` outputs, and applies literal rank-0 plus rank-1 plus rank-2
   plus rank-3 BF16 sums;
4. a fixed-output eager elementwise "attention stand-in" executes between
   graph segments so the next layer consumes a value written across the same
   graph/eager scheduling boundary as the live target;
5. every graph segment is materialized during capture before the following
   eager boundary or graph is captured; and
6. changed root inputs drive multiple complete replays.

The control and candidate use identical XPU arithmetic and distinct storage.
The diagnostic compares raw `uint8` views of all 96 gathers, all 96 sums,
every layer result, every eager-boundary result, and the final output on every
rank. It records the first mismatch by sample, layer, and stage. Values remain
bounded; there is no CPU floating-point oracle. The known-bad final ordinary
all-reduce is excluded.

## Gates and stop rules

1. The source must validate TP4, rank/local-rank identity, exactly four visible
   XPUs, internal NVMe/ext4 output, absent output root, and bounded repetition
   counts. It must leave immutable per-rank and aggregate JSON or an explicit
   failure marker.
2. Run static compilation and source inspection before device execution.
3. With the host idle, run exactly one bounded fixture invocation. A result is
   a pass only if all four ranks finish, every raw comparison is exact, every
   changed-input transition changes the final output, and teardown is clean.
4. Any raw mismatch, hang, timeout, device error, missing rank result, or dirty
   teardown stops this route. Do not retry unchanged code, reset, reload,
   unbind, FLR, clear shared memory, or reboot.
5. A component pass authorizes only a new default-off model diagnostic with
   persistent raw response capture and layer-local parity evidence. It does
   not authorize a score-bearing leg or promotion.
6. A component failure closes direct target gather capture on this stack. The
   125.461973 record and its protected worktrees remain untouched.

No target/draft/KV precision, model revision, width/depth, teacher, sampling,
prompt, cache, topology, benchmark metric, or scoring window changes are
authorized here.
