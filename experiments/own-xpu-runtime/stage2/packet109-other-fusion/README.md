# Packet109: exact fusion of small per-layer operations

This candidate removes three launches per layer, 72 per half, from the copied
packet103 selected bundle. It is CPU-qualified only until the proposed lane B
screen completes. Device output and speed are unmeasured; there is no promotion.

`other_fusion=production|fused` selects both paths in one binary. All other
target and draft choices stay fixed. The parent source copy retains packet100's
down-tile16, packet103's selected recurrence, HC and halfcache choices, and the
packet59 split32 draft attention arithmetic.

The first kernel appends shared-expert activation to the selected single-work-
group router, after its existing phases and a global/local fence. Gate/up is
already produced by the preceding small-FFN launch. The second kernel appends
mixture and shared-expert blend to the Q8 K640 shared-down reduction, one
subgroup per output row. It preserves all intermediate BF16 stores, the ten
expert additions in their original order, runtime multiplication by one, the
existing sigmoid/SiLU functions, and the existing 32-lane reduction tree.
There is no cross-work-group phase dependency or generic device interpreter.

See [CENSUS.md](CENSUS.md) for every launch, binding extent and dependency;
[LAYOUT-AUDIT.md](LAYOUT-AUDIT.md) for arithmetic, allocation and switch rules;
and [DO-NOT-REPEAT.md](DO-NOT-REPEAT.md) for rejected variants. Captured CPU
command counts are expanded with source-proven device finish kernels: production
636/628 becomes 564/556 on rank0/rank1. These are counts, not speed measurements.

Preparation uses GNU for native CPU execution and Intel for the device build.
The small fused-site fixture executes with both compilers. All compilation uses
packet94's shared compiler lock. Run the following sequentially from this
directory, with `nice -n 19 taskset -c 8-15,24-31 python3 -B SCRIPT </dev/null`:

1. `restore_rope.py`, `bracket_config.py`, `build_engine.py`.
2. `cpu_gate.py`, `full_shape.py`, `startup109.py`, `reset_gate.py`, `protocol_gate.py`.
3. `census.py`, `audit_sources.py`, `seal_native.py`, `cpu_seal.py`.
4. `queue_plan.py` (writes only the new proposal and plans a temporary queue).

The checked sources are committed copies, not generated from mutable parent
outputs. `prepare_sources.py` records the original import transformation and
is intentionally one-shot. `source-copy-provenance.json` pins original checked
files; `native-overlay.patch` shows the integration changes. Unchanged parent
objects are immutable hash-bound build dependencies, audited against the copied
bundle. Generated sources and binaries are sealed locally and rebuilt as above.

The final byte reference compiles the actual production NgHost operation in a
separate translation unit with runtime shapes, matching the engine boundary.
GNU uses its original full CPU blend loop to preserve vectorized NaN behavior;
Intel tests the fused per-row body used by the device source. Early fixtures
specialized the reference at their call sites and are retained as diagnostics.
The final check uses GNU O3/native and Intel O2 with strict floating-point flags.

The proposed v5 bracket is production/fused/production/fused/production in one
loaded rank pair, with real native reset and command recapture between views.
Every view runs incident64 and all 12 fixed prompts at 128 tokens, once each,
requiring every token to match `iq3-p49-split32-v1` and cached tokens to be zero.
The existing wrapper records accepted/rejected paths, TTFT, whole-request and
decode timing. Judge the complete engine; a launch estimate is not a result.
Expected elapsed time is at most 15 minutes; watchdog is 60 minutes (4×).
The queue proposal requests lane B only. No device has been used by preparation.
