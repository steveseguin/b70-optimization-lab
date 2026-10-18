# Packet108: draft INT8 load grouping

CPU preparation only. The copied packet103 `mtp36::Dense` keeps WG128, SG32,
one output row per subgroup, all 32 logical sums and the original adjacent
reduction tree. The only changed function is the INT8 raw-load portion of
`lane`: eight codes, one original FP32 scale, and eight BF16 inputs per tile.
There is no weight repack, extra cache, new math, fusion, or new early exit.
Gate/up and DOWN test the same mechanism at K=2560 and K=640.

The load spelling comes from this lab's packet51/packet59. Packet59 combined
it with V8/V16 work assignment, a different workgroup and optional epilogues;
this packet isolates loads using the still-selected mtp36 production geometry.
Packet104 transposed weights; this packet keeps every byte in its old position.
Packet81's target IQ2/IQ4 load-count loss remains closed. These are draft INT8
weights with different reads, arithmetic and one occurrence per draft command.

## First gate

The sole proposed device job is
`ops/lane-queue/proposed-p108-micro-B.txt` under this experiment. It requires
the compiled source receipt, packet100b route provenance, ordinary coordinator
admission, fault review and graceful drain. Plan mode is CPU-only. No existing
queue is modified. The binary is not run during this preparation.

Replay all 384 packet100b route vectors at full 512-expert bank shapes. These
are **captured target routes replayed through draft operators**, not captured
draft routing or a full-model benchmark. Weights and BF16 activations are
deterministic synthetic operator inputs. Both arms share the same weight bank.
Compare full FP32 sums, BF16 outputs and status words outside timing. Use 40
paired samples per route, alternating control/candidate then candidate/control,
with a 512 MiB device buffer scrub before each timed event. The scrub changes
no host page-cache setting and is excluded from the event time.

Each arm must take at most 85% of control time overall, in every route/input
stratum, and in both order halves. Missing routes, equality failures, incomplete
drain or changed source/input hashes refuse qualification. This is the unchanged
packet100/104 **15%** gate, with no waiver and no overall-median shortcut.

## Conditional next gates

Only a measured qualifying arm earns integration. Then copy a fresh engine
view from the frozen packet103 bundle and run repeated GNU/Intel byte checks,
including FP32 intermediates, exceptional values, route guards and statuses.
Exercise **every** chain window's real startup and host-reference argv on CPU,
especially KD; run full-size allocation/VRAM admission and seal the exact view.
Only then prepare B control/candidate/control and conditional A confirmation
proposals. Keep all twelve target outputs, per-prompt acceptance and draft
proposals identical; require independent fresh processes for any speed verdict.
The target oracle remains `iq3-p49-split32-v1` and KV stays full 16-bit.

There is deliberately no model-grid proposal or qualified engine seal before
the micro result. CPU or micro success alone cannot become a speed headline.

## Reproduction

From the repo root, use nice 19, CPUs 8–15/24–31, `python3 -B` and stdin
`/dev/null`. `build_microbench.py` enforces 8 GiB address space and packet94's
shared compiler turn, including the whole-host hold. Run the build, protocol
tests, `run_micro.py --plan` and `queue_plan.py`. `bootstrap.py` is first-copy
provenance and refuses overwriting retained source; `derive_micro.py` documents
the harness derivation. Frozen parents are never edited. Generated build files
are ignored, with the complete source closure/hash receipt retained.

See [budget](../packet108-attribution/BUDGET.md) and
[work note](../../../../notes/2026-10-18-own-runtime-packet108.md).
