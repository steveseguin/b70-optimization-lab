# Qwen3.8 27B INT4 — crossing 100 tok/s, and the uninitialized GDN scratch that hid it

Date: 2026-08-18 (America/Toronto)

## Result

**`100.497 tok/s`** median across three arms on the 25-prompt suite, with
25/25 self-determinism and a quality pass against the model's own baseline.

| Arm | all-25 | selection-12 |
| --- | ---: | ---: |
| A | `101.653` | `96.499` |
| B | `100.497` | `96.627` |
| C | `99.905` | `96.895` |
| **median** | **`100.497`** | **`96.627`** |

- determinism: all three pairwise comparisons 25/25 token-identical;
- quality: `pass_all` and `baseline_match_all` against
  `data/qwen38-27b-autoround-int4-b70-baselines/quality-qwen38-int4-mtp3-fast-20260818.json`,
  15 comparisons;
- every measured row `cached_tokens=0`.

Three caveats travel with this number and must not be dropped:

1. arm C is `99.905`, so the arms are **not unanimously** above 100 — the median
   is;
2. **selection-12 is `96.627`**, so the 12 historical prompts have *not* crossed
   100. Any comparison against a record set on that suite must use this number;
3. validated under a **pinned compile cache**. A fresh-compile arm is still
   outstanding.

## The bug: uninitialized persistent GDN scratch at five verifier rows

MTP4 initially looked like a dead end. It failed 24/25 on every pairing, always
on `holdout--long-rollover-repository-audit`. Four observations turned that into
a diagnosis:

1. **The divergence position moved between pairs** — token 88, then 30, then 30.
   A deterministic arithmetic difference between two builds cannot move; it would
   fail at the same token every time.
2. **The prompt in isolation was identical across runs.** Running just that
   prompt plus a stable control in a two-prompt suite gave byte-identical output.
   So the fault is *history dependent*, not intrinsic to the prompt.
3. Those two together mean state is carrying across requests and its content
   varies per process — the signature of reading memory before writing it.
4. `VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=0` produced 25/25 across all three
   pairs **and was faster**.

The persistent scratch is cached across calls (keyed on the conv-weight pointer)
and a region is read before being written when `total_spec_tokens == 5`. MTP3 at
four rows writes the whole region, which is why MTP3 was always clean and why
this stayed hidden.

Disabling the scratch is a **workaround, not the fix**. The correct repair is to
zero-initialise the scratch, or size and write it correctly for `k+1` rows.
Because disabling it costs an allocation per call, a correct fix should land
*above* `100.497`.

### Warning for the serial-exact MTP4 work

`csrc/xpu/gdn_attn/gdn_attn_interface.cpp` hard-requires
`VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1` whenever
`VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT` is on. **Any MTP4-with-
serial-exact build therefore cannot avoid this uninitialized scratch.** The
scratch must be fixed before that path can be trusted, or it will produce
exactly the intermittent single-prompt failure documented above.

## Two earlier conclusions this overturns

**Nondeterminism was blamed on GDN arithmetic. It was compilation.** Two runs of
the same config with fresh compile caches agree 12/25; a run reusing the first
run's cache agrees **25/25 over 12,413 tokens**. torch.compile emits
different-but-internally-deterministic code per build. The corroboration was
already in the data and was under-weighted: divergent token positions were
byte-identical across two *different* configurations, which random runtime noise
cannot produce.

**Serial-exact GDN was not buying arithmetic determinism.** It forces the op to
an eager graph break, so it is never compiled and never autotuned — it was
avoiding the compiler, and charging `6.3 tok/s` for it.

Consequence: the compiled cache belongs in the recorded run identity, alongside
the `.so` hashes the harness already pins. That tightens the identity
requirement; it does not relax the gate.

## Harness defect fixed along the way

`run-tp2-targetgraph-drafteager-candidate.sh:67` and
`run-tp1-current-candidate.sh:56` used
`${QUALITY_BASELINE_JSON:-<qwen36 baseline>}`. The `:-` form substitutes on
**empty** as well as unset, so omitting the baseline argument silently graded a
Qwen3.8 run against the **Qwen3.6** model's baseline. Changed to `-`, so an
explicitly empty value means no baseline.

Every Qwen3.8 quality result recorded before that fix — including the
`pass_all` values reported for the 91.926, 96.616 and early MTP4 arms — was
measured that way. Those runs did pass, which is an interesting cross-model
observation, but it was never a model-specific gate and should not have been
reported as one. The result at the top of this note is the first Qwen3.8 quality
pass against a genuine Qwen3.8 baseline.

## Reproduction

Config: MTP4 (`num_speculative_tokens=4`), `cudagraph_capture_sizes [5]`,
serial-exact GDN **off**, batch-invariant **off**, persistent GDN scratch
**off**, tie-break margin `0.03125`, oneDNN INT4/INT8 barriers on, INT8 LM head,
`--dtype float16`, TP2.

Full command form and host/source identity:
[`../repro/qwen38-27b-autoround-int4-b70/README.md`](../repro/qwen38-27b-autoround-int4-b70/README.md).
Per-arm manifests and the complete ladder:
[`../data/qwen38-27b-autoround-int4-baseline-20260818.json`](../data/qwen38-27b-autoround-int4-baseline-20260818.json).

## Next

1. Fix the scratch properly instead of disabling it; expected to land above
   `100.497` and it unblocks the serial-exact path.
2. Run a fresh-compile arm to close the third caveat.
3. Depth 5 — MTP4 gained about 4 tok/s and the scratch fault is now understood.
4. Attack selection-12 at `96.627`; that subset is what any record comparison
   actually rests on.

## Addendum — depth swept, and the proper scratch fix written

### Depth is exhausted at MTP5

Persistent scratch disabled throughout, all arms cold:

| depth | all-25 | selection-12 |
| --- | ---: | ---: |
| MTP3 | `96.616` | `94.037` |
| MTP4 | `100.497` | **`96.627`** |
| **MTP5** | **`101.922`** | `95.167` |
| MTP6 | `99.464` | `93.592` |

MTP5 is the all-25 optimum and MTP6 turns over. Note the split: **MTP4 is
better on the 12 historical prompts** (`96.627` against MTP5's `95.167`). Depth
helps the newer holdout prompts and hurts the historical ones, so the right
configuration depends on which suite a comparison is against. Both are
submitted: MTP4 `cmszarna10e0nms0103hv0tve`, MTP5 `cmszbkxco0e11ms01l2rixxbt`.

MTP5 was validated on three cold arms (`100.896` / `102.042` / `101.922`), all
three pairwise comparisons 25/25 token-identical, quality passing against this
model's own baseline.

### The proper fix, written but not yet built here

`get_gdn_spec_decode_scratch` allocated **every** buffer with `torch::empty`.
The fix replaces those twelve allocations with `torch::zeros`/`zeros_like`,
leaving the intentional `torch::ones` for `has_initial_state` and
`torch::arange` for `exact_query_start_loc` alone.

Zeroing is correct rather than disabling the scratch: allocation happens once
per `(owner, shape, dtype)` and is cached, so it is a single memset off the hot
path, whereas `PERSISTENT_SCRATCH=0` reallocates on **every call**. The current
`101.922` is therefore paying an allocation per call that the fix removes.

- kernel commit `0ab8205` on branch `fix/gdn-scratch-zero-init`, pushed to
  `https://github.com/steveseguin/vllm-xpu-kernels.git`;
- flat patch:
  [`../experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-gdn-scratch-zero-init-20260818.patch`](../experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-gdn-scratch-zero-init-20260818.patch).

**It has not been built or measured.** The kernel build path is a full
`setup.py bdist_wheel` with SYCL ahead-of-time compilation, and this host has
only ~4.7 GB free on `/` while a previous build tree measured 2.3 GB. There are
7.4 GB of untracked `.so.pre-*` rollback snapshots in the kernel repo that would
cover it, but those are deliberate rollback points and were left alone.

The kernel checkout was returned to the pinned `2dd55f38` with a clean tree, so
the validation harness still runs; the fix lives only on the branch.

### Why this matters beyond speed

`gdn_attention_spec_decode` hard-requires `PERSISTENT_SCRATCH=1` whenever
`VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT` is set. Any serial-exact build
at a depth other than 3 therefore inherits these uninitialized reads and cannot
be trusted until this lands.
