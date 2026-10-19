# Packet161: exact early-head certification, CPU feasibility

Preregistered 2026-10-19 before any GGUF read. Main at entry:
`46847016d9f35ebd8ce8acc3d304528dd0461086`. Host is `steve-b70s`;
the workload and cost replay concern the two-card bundle8 lane. The active
`packet58-onecard-58aj-a` chain forbids weight reads until inactive.

## Fixed question and schemes

Can upper bounds avoid enough unchanged Q6_K head work to support 3%?
Target has 248,320 rows, split 202,240/46,080 across ranks. Draft uses the
unchanged first 80,128 rows of that same tensor. Hidden width is 2,560.
Do not change `iq3-p49-split32-v1`, prefix, topology, precision or proposals.

Evaluate all five fixed schemes, without corpus-based parameter selection:

1. One Euclidean norm per row (Cauchy–Schwarz).
2. Ten norms per row, one for each contiguous 256-weight block.
3. 160 norms per row, one for each actual Q6 scale group of 16 weights.
4. Scheme 2 plus sequential 256-weight partial dots and remaining-block bounds.
5. Scheme 3 plus the same 256-weight partial dots and remaining scale-group bounds.

Rows can be ordered offline by decreasing row norm, breaking ties by original
ID. For rejection pricing we give every row the **true final maximum for free**,
before reading any weight. This is more favorable than every possible running
maximum/order. The measured fractions are therefore optimistic **lower bounds
on required work**, not a claimed executable early-exit read count. Distinguish
rows touched from full-row-equivalent weight bytes: a partial dot touches a row
even when it avoids most of that row. If this donated oracle still fails the
cost gate, ordering cannot rescue these schemes. It cannot justify admission.

## Data fixed before weight access

Target suite: the 16 retained steps (1–8, 97–104) for all twelve packet49
prompts, plus incident steps9–16 from its all-position capture: 200 distinct
positions. Independent target: all 24 generated positions for each of five
packet132 excerpts from packet114's frozen independent documents: 120 positions.
Use their original bytes, not today's edited documents. Report these separately.

Native draft: 65 distinct incident KD host-reference final.mix inputs; owners
that repeat those inputs do not increase coverage. The current evidence census
has no exact native draft hidden states across all twelve prompts or independent
documents. Packet132's Python draft explicitly lacks native-bit parity and did
not save its hidden inputs. No fabricated or target-as-draft substitutions.
This is a known gap against the requested draft coverage. A model replay is not
admitted without evidence it fits 4 GB and the 45-minute box. The old native
draft allocation ledger is already 3.345 GB before other buffers/scratch.

The final target input is **not** the last layer stream or a simple RMS norm.
Reconstruct the exact final HC mixer using packet49's arithmetic and the existing
hash-verified CPU math bridge. Verify all five stored head logits at every target
position, and the saved prefix winner for each native draft input. A mismatch
refuses analysis; approximate reconstruction is not admitted.

## Prior exclusions

The initial [census](evidence/prior-audit.json) hashes all 226 rg-visible negative
indexes; [head/argmax matches](evidence/prior-matches.txt) preserve 171 matches.
Required files were also read completely:

- [101](../packet101-draft-geometry/DO-NOT-REPEAT.md): no geometry revival;
  3,200 useful bytes differ from the 3,380-byte expanded row stride.
- [105](../packet105-head-split/DO-NOT-REPEAT.md) and
  [105b](../packet105b-head-split/DO-NOT-REPEAT.md): target split is already
  present; preserve current verified hidden state, reset flags and nonfinite refusal.
- [106](../packet106-draft-split/DO-NOT-REPEAT.md) and
  [106b](../packet106b-draft-split/DO-NOT-REPEAT.md): no repeated split/transport arm.
- [114](../packet114-draft-prefix/DO-NOT-REPEAT.md): 80,128 immutable; no
  suite-based prefix tuning or corpus coverage passed off as acceptance.
- [158](../packet158-draft-levers/DO-NOT-REPEAT.md): small draft kernel lever
  closed; the present question avoids reading rows through a mathematical proof.
- [160](../packet160-critical-path/CLOSEOUT.md): draft-head-only ceiling is
  below3%; early target winner remains distinct from an early loser witness.
- [144](../packet144-miss-path/DO-NOT-REPEAT.md),
  [126](../packet126-early-draft/DO-NOT-REPEAT.md),
  [69](../packet69-rank1-head/DO-NOT-REPEAT.md),
  [74](../packet74-packed-dense/DO-NOT-REPEAT.md) and
  [93](../packet93-packed-head2/DO-NOT-REPEAT.md): no inferred isolated head
  time, changed draft format, premature corrected token, or layout/packing revival.

## Arithmetic certificate

The FP32 decoded weight is `fl32(fl32(half_scale * int8_scale) * code)`;
these are exactly the values in both the packed oracle and expanded kernel.
Per row, each of32 lanes accumulates80 separate rounded products, in eight-wide
tiles. A five-level adjacent tree follows, then BF16 RNE and lowest-index argmax.
Sources: `packet136-record-bundle/p33_candidates.hpp`, `p33_submit.cpp`,
`round2_submit.cpp`; oracle identity `packet49-integrate/oracle/arithmetic.json`.

Let `u=2^-24`, `gamma=86u/(1-86u)`, `S=||w||2 ||x||2` and
`E=gamma*S + 5151*2^-149/(1-86u)`. The longest term path has at most86
roundings (product,80 additions,5 tree levels); there are at most5151 primitive
products/additions. Standard per-operation absolute rounding error induction
gives `|FP32_dot - exact_dot| <= E`, including gradual underflow, provided no
intermediate overflows. Bounds on absolute partial sums by S establish that
precondition for the measured finite states. Add an outward FP64 allowance
`1e-10*max(S,1)` for the norms, products, partial sums and remainder subtraction;
this exceeds the gamma bound for fewer than10,000 FP64 operations on any term
path. FP32 decoded values are exact FP64 inputs. CPU BLAS is used only for
bounded FP64 dot estimates, never as the exact FP32 oracle.

An unread suffix is bounded by its block norm products. Add its exact-dot
partial estimate and E. Convert upward to FP32 and then monotonically through
BF16 RNE. Strict `current_max > upper` is sufficient even with ties; equality
forces more work. For every possible input, nonfinite metadata/input, an
unproven overflow case or an unusable bound must invoke the original full scan,
including its reject-any-nonfinite behavior. Bounds never license changing the
FP32 order of a fully evaluated candidate. This study is a proof of that
contract and cost screen, not a deployed implementation of the fallback.

## Pricing and decision

Use packet158's measured historical draft head0.4453476 ms, clearly labeled a
diagnostic anchor. Packet105b/136 do not supply an isolated current target-half
GPU time: the split is unequal. Packet87 records an older **full** target
head1.403683854 ms. It can support a labeled sensitivity, not a claimed current
half measurement. Packet150's0.310820 ms is enclosing suffix host service.

Apply packet160's exact 1,188-interval replay:
`max(D-d,R+C-c) + max(B-b,A+offset) + G`, then the original within-class and
across-class medians. Ordering/norm arithmetic, metadata reads, additional
launches and discontinuous traffic are nonnegative costs. Show gross/free-cost
ceilings first; do not invent measured GPU overhead from CPU timings. Metadata
alone adds4/40/640 bytes per row for FP32 norm storage (upward-rounded norms),
beside the 3,200 useful baseline bytes. Treat conversion to time as a sensitivity.
No supported3% ceiling means no build brief, proposal or READY. Missing data
cannot be called a measured negative. Preserve the precise coverage gap.

## Operating and reproduction contract

Only new packet161 files and `notes/2026-10-19-own-runtime-packet161.md` change.
No GPU, build, service change, sudo, settings, old packet, screen or ops edits.
All CPU mains: nice19, CPUs8–15/24–31, Python `-B`, stdin `/dev/null`,4 GB
address-space cap. CPU stop27 GB; device floor25 GB applies only to any future
authorized brief. GGUF access checks the one-card unit before every range read.
The existing NumPy environment's `python3` is used; system Python lacks NumPy.

```sh
env OPENBLAS_NUM_THREADS=4 OMP_NUM_THREADS=4 nice -n 19 taskset -c 8-15,24-31 /home/steve/.venvs/vllm-xpu/bin/python3 -B experiments/own-xpu-runtime/stage2/packet161-early-argmax/prepare.py </dev/null
env OPENBLAS_NUM_THREADS=4 OMP_NUM_THREADS=4 nice -n 19 taskset -c 8-15,24-31 /home/steve/.venvs/vllm-xpu/bin/python3 -B experiments/own-xpu-runtime/stage2/packet161-early-argmax/analyze.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet161-early-argmax/price.py </dev/null
env OPENBLAS_NUM_THREADS=4 OMP_NUM_THREADS=4 nice -n 19 taskset -c 8-15,24-31 /home/steve/.venvs/vllm-xpu/bin/python3 -B experiments/own-xpu-runtime/stage2/packet161-early-argmax/test_cpu.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet161-early-argmax/verify.py </dev/null
```

## Recorded outcome

The [closeout](CLOSEOUT.md) records the measured fractions and missing draft
coverage. After the main scan, one bounded independent-draft preparation probe
tested the unresolved memory question with a hard 3.7 GB child address cap,
leaving supervisor room under 4 GB. The existing native loader first refused
missing idle I/O priority before weight reads; a fresh entry with its required
child-only `ionice -c3` then hit `std::bad_alloc` and drained. That is the one
allocation attempt; do not rerun `probe_draft.py` without a new fit argument.
No memory setting or cap was raised. Probe argv, both failures and teardown
receipts are retained. This does not repair the independent-draft coverage gap.
