# Qwen3.6 27B INT4 — determinism/speed tradeoff, and why token parity is unsatisfiable

Date: 2026-08-18 (America/Toronto)

## Decision

No new LocalMaxxing record. On the full 25-prompt suite the **deterministic
ceiling is `94.710 tok/s`** and the **fastest non-reproducing configuration is
`96.822 tok/s`**.

Those are all-25 numbers and are **not** comparable to the retained July
`95.385`, which was measured on the 12-prompt historical suite. On that suite
the same configurations score `89.766` and `94.103` — see the
[suite-composition correction](#correction--all-25-medians-are-not-comparable-to-the-july-record).
**Nothing in this campaign beats the July record on the suite it was set on**,
so nothing was submitted.

The `94.710` figure supersedes the `92.003` used throughout sections 2 and 3
below, which describe the flag bisect as it stood before the sampler fix. See
the [addendum](#addendum--27-toks-reclaimed-without-weakening-any-gate): a
bounded tie break implemented with two masked `max` reductions instead of
`topk(k=2)` reclaimed `2.7 tok/s`, verified bit-identical to the original, with
quality and reproducibility unchanged. Determinism now costs about `2.1 tok/s`,
not `4.8`.

Three things from this campaign should be adopted regardless: the sampler fix, a
much better reference oracle, and the removal of a gate that cannot be passed.

## 1. The complete-token-parity gate is unsatisfiable, not merely strict

An agreement matrix over 11 configurations and 55 pairings shows one clean rule:

- reruns of an **identical** configuration agree on **24–25 of 25** prompts;
- **every** cross-configuration pairing agrees on **7–16 of 25**, regardless of
  which axis differs — graph capture on/off, capture shape, tie-break margin
  on/off, speculation on/off.

The sharpest control: two *non-speculative eager* references differing **only**
in the deterministic-margin flag agree on `8/25`. A flag intended to increase
determinism is itself a configuration difference, and therefore itself a
divergence source.

So "candidate must be token-identical to a differently-configured reference"
cannot be satisfied on this stack at float16. This is not a defect in the
speculative decoder. Across the prior campaign the speculative path was in fact
the *most* reproducible configuration measured (25/25 over 12,477 tokens, better
than either non-speculative arm).

The mechanism is ordinary: about 1 decision in 400 is an exact float16 logit
tie, and roughly 1 token in 1,000 sits close enough to a boundary that any
change in floating-point reduction order flips it. Once one token flips the rest
of the response diverges. The observed counts match a memoryless per-token
hazard almost exactly — a model fitted to the data predicted 16.1 and 12.9 exact
prompts where 16 and 13 were observed.

**Recommended gate instead:** self-determinism (candidate reproduces itself
across fresh servers and fresh compile caches) plus the existing quality
baseline. Both are strict, both are meaningful, and the speculative
configuration already passes both.

## 2. Determinism is a conjunction of four flag families, and it costs ~4.8 tok/s

Every flag family removed degraded run-to-run reproducibility:

| Configuration | tok/s | Self-determinism | Quality |
| --- | ---: | --- | --- |
| full stack (margin + serial-exact GDN + batch-invariant + oneDNN barriers) | `92.003` | **25/25** | pass |
| drop both batch-invariant flags | `91.789` | 12/25 | pass |
| drop margin + batch-invariant | **`96.822`** | 15/25 | pass |
| drop margin + batch-invariant + oneDNN barriers | `95.926` | 16/25 | pass |
| MTP4, serial-exact GDN disabled | `93.680` | 9/25 | pass |

There is no cheap subset. Determinism requires closing every nondeterminism
channel at once; leaving any one open reintroduces flips. The price is about
`4.8 tok/s`, roughly 5%.

The margin's cost is structural: it requires dense top-two logits, which
disables the argmax fast path.

## 3. MTP4 is not currently worth it

The fourth draft position accepts only **33%** (per-position `1.000, 0.667,
0.667, 0.333`), and average draft acceptance falls from `66.3%` to `60.1%`.
Worse, the serial-exact GDN proof mode is **hardcoded to four verifier rows** —
it raises `exact recurrent proof requires one request with four verifier rows` —
so MTP4 forces that determinism flag off. The depth gain (`+1.9 tok/s`) does not
pay for the determinism lost (25/25 to 9/25).

MTP4 becomes worth revisiting only if the serial-exact path is generalized to
`k+1` rows and draft-head quality lifts position-4 acceptance materially.

## 4. Adopt the shape-pinned reference oracle

Pinning the non-speculative reference's `cudagraph_capture_sizes` to `[4]`
instead of `[1,2,4,8]`:

- raised reference self-consistency from `15/25` to **`24/25`**, matching the
  eager oracle;
- runs at **`46.147 tok/s`** versus the eager oracle's `11.65`, making every
  future validation about 4x cheaper in wall time.

It does **not** improve candidate parity (at constant margin it gave `15/25`
against the eager reference's `16/25`), so adopt it as a cheaper, steadier
yardstick only — not as a parity fix.

The single residual reference flake is `holdout--structured-extraction`, the
same prompt that is the sole flake in eager mode. It is a genuine near-tie, not
a tokenization artifact: one run writes `**Temporal Consistency Check**:` and the
other `**Temporal Consistency:**`, after which the two responses realign.

## 5. Batch invariance is dead code on XPU

This is why the prior campaign's flag sweeps plateaued at 16/25 — the protection
being tuned was never active.

- `vllm/model_executor/layers/linear.py:237` gates the batch-invariant path on
  `current_platform.is_cuda_alike()`, which is false for `PlatformEnum.XPU`.
  `VLLM_XPU_LINEAR_BATCH_INVARIANT` is computed at line 228 and discarded by
  that same conjunct.
- `vllm/model_executor/layers/vocab_parallel_embedding.py:414` carries the same
  gate for the LM head, and the INT8 LM head path returns at line 406 before
  reaching it anyway.
- `vllm/model_executor/layers/layernorm.py:114` places the check in
  `forward_cuda`/`forward_xpu`; under compiled `custom_ops=['none']` dispatch
  goes to `forward_native` and never arrives.
- The INT4 W4A16 projections and INT8 LM head — the bulk of the model — have no
  batch-invariant variant at all.
- `run-arm.sh:348` and `:353` export `VLLM_XPU_INT4_GEMM_FIXED_M4` and
  `VLLM_XPU_INT8_LM_HEAD_FIXED_M4`, which **no code in either tree reads**. The
  consumer was never written. Neither flag, nor
  `VALIDATION_LINEAR_BATCH_INVARIANT`, nor
  `VALIDATION_USE_STAGED_XPU_KERNELS_FOR_TARGET`, appears in any of the 328
  previously sealed runs.

## 6. Operational traps found

- `run-arm.sh:559` defaults `VALIDATION_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT`
  to `1`, so it is silently on unless explicitly set to `0`. An earlier reading
  of a "stripped" arm was wrong for this reason.
- The source-identity guard pins `vllm-xpu-kernels` to `2dd55f38`. Syncing that
  repository with upstream disarms **every** validation arm with exit code 3
  (`kernels source mismatch`). Because the built `.so` files are not rebuilt by
  a source sync, the honest state during validation is a detached checkout of
  the pinned commit.

## Reproduction

See [`../repro/qwen36-27b-autoround-int4-b70-determinism-20260818/README.md`](../repro/qwen36-27b-autoround-int4-b70-determinism-20260818/README.md)
for the full environment, pinned commits, binary hashes, and exact commands.

Structured evidence with per-arm manifest hashes:
[`../data/qwen36-27b-autoround-int4-determinism-speed-20260818.json`](../data/qwen36-27b-autoround-int4-determinism-speed-20260818.json).

## Reopen condition

Do not run further flag sweeps against the complete-token-parity gate; eleven
configurations show it is unsatisfiable. Reopen on either of:

1. **Real XPU batch invariance** — fix the `is_cuda_alike()` gates and implement
   shape-invariant INT4 W4A16 and INT8 LM-head kernels. Only then can two
   different execution paths produce identical bits, and only then does a
   cross-configuration parity gate become meaningful.
2. **Draft-head quality** — acceptance is the dominant throughput lever and is
   untouched. At the measured `32.0 ms` step time, lifting average acceptance
   from `66.6%` to `73.4%` alone reaches `100 tok/s` without weakening any
   determinism flag.

## Addendum — 2.7 tok/s reclaimed without weakening any gate

The deterministic ceiling is no longer `92.003`. A sampler change raises it to
**`94.710 tok/s`** (median of three replicates: `94.321`, `94.710`, `94.791`)
with quality passing on all three and reproducibility unchanged.

### What it was

With a margin configured, `_xpu_deterministic_greedy_sample` took the top two
logits with `torch.topk(k=2)` over the 248320-wide vocabulary. Measured on this
hardware at 4 verifier rows:

| operation | ms/step |
| --- | ---: |
| `argmax` only (no margin) | `0.111` |
| `topk(k=2)` on an fp32 copy (original) | `0.679` |
| `topk(k=2)` on fp16 | `0.480` |
| two masked `max` reductions | `0.089` |

A k=2 topk cost about six times a max reduction. Two masked max passes cost
*less* than a single argmax call, so the bounded tie break is now effectively
free.

### Why it is safe

The near-tie branch resolves to `min(first, second)`, so the result cannot
depend on the order the two largest entries are returned in. The new
implementation was verified bit-identical to the original over 800 sampled
tokens including forced exact ties and forced near ties, then confirmed on
hardware: **B vs C are identical on all 25 prompts across 12,477 tokens**. A vs
B and A vs C differ on one prompt, `holdout--structured-extraction` at token
246 — the same bistable prompt that is the sole flake in both the eager and the
shape-pinned reference oracles, neither of which uses this code path.

Source: `vllm` commits `011713d34b` (drop the full-vocab fp32 copy, worth about
`0.2 ms`) and `44fc8fde09` (the masked-max pair).

### What did not work

- **`VALIDATION_COMPILE_ALLREDUCE_STATIC_INPLACE=1`** — `80.859 tok/s`, about
  11 tok/s worse. It is a correctness-lane tool, not a speed lever.
- **Narrowing `VALIDATION_ONEDNN_INT4_INPUT_DEPENDENCY_SCOPE`** from
  `all_target` to `all_gdn_in` — `91.462`, no gain. The dependency argument is
  cheap at any scope.
- **`VLLM_XPU_SPEC_GREEDY_TOP_IDS`** — a dead end for a different reason: the
  margin gate at `gpu_model_runner.py:8451` disables it, but the flag was never
  enabled in any arm, so the margin was not costing us that fast path.

Determinism now costs about `2.1 tok/s` rather than `4.8` (`96.822` remains the
fastest non-reproducing configuration). Still short of the retained `95.385`
July figure — which was measured on 12 prompts with no determinism gate — so no
submission was made.

## Correction — all-25 medians are not comparable to the July record

An earlier revision of this note described `95.926 tok/s` as "above the
historical `95.385`". **That comparison was wrong** and is retracted.

The July record was measured on the 12-prompt historical suite. Those 12 prompts
survive in the current 25-prompt suite as the `selection--*` rows; the 13
`holdout--*` rows were added later and they run materially faster. Any all-25
median is therefore inflated relative to the record's suite.

Measured on the same 12 prompts the record was set on:

| Configuration | 12-prompt `selection--` median | all-25 median | vs `95.385` |
| --- | ---: | ---: | ---: |
| July record (retained) | **`95.385`** | not measured | — |
| fastest non-reproducing | `94.103` | `96.822` | `-1.282` |
| all barriers stripped | `93.084` | `95.926` | `-2.301` |
| MTP4 | `91.914` | `93.680` | `-3.471` |
| deterministic, masked-max (best) | `89.766` | `94.710` | `-5.618` |
| deterministic, prior stack | `87.847` | `92.558` | `-7.537` |

**Nothing measured in this campaign beats the July record on the suite that
record was set on**, deterministic or not. Suite composition is worth roughly
5 tok/s, which is larger than every optimization difference reported above.

Two consequences:

1. The masked-max sampler gain is still real — it is a same-suite comparison,
   `87.847` to `89.766` on the selection subset and `92.558` to `94.710` on
   all 25. Only the comparison *to the record* was invalid.
2. Any future speed claim in this lane must report the `selection--` subset
   median alongside the all-25 median, or it is not comparable to the retained
   record. The same caveat applies to the earlier `98.766`, `99.798`, and
   `>100` figures, whose all-25 framing carries the same inflation.
