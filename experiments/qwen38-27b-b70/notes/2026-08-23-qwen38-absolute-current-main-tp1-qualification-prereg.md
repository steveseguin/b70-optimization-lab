# Absolute-current-main Qwen3.8 TP1 qualification preregistration

Date: 2026-08-23 local / 2026-08-24 UTC. This is the first runtime gate for
the custom images built from literal upstream `main`. It is an attribution and
preservation campaign, not permission to replace historical records, discard
accepted overlays, or call a stale rolling image current.

## Active identity roll-forward: 2026-08-24

The arm order, launch/runtime configuration, quality contract, and protected
floors below remain frozen. The only permitted roll-forward is the
upstream/build identity when a freshness gate detects that `main` advanced.
The next campaign is bound
to tracked receipt
`experiments/qwen38-27b-b70/data/2026-08-23-qwen38-absolute-current-main-build.json`
and its byte-identical archived copy, currently:

- vLLM `702e1d718646b5290f17533c04932d58bf03dad6`;
- XPU kernels `4543b580fecca68a7dd54ddaf6e444dc5f11a6a4`;
- official nightly base index
  `sha256:d3f5daa1552a231471a5ec5097475d282e07788db336819ed9e932f9193b0e35`;
- current-vLLM/stock-kernel image
  `sha256:d7372613500de2c823becd2364b322b7d7f7827b6fd0705500b14328f1eacdda`;
- both-current image
  `sha256:eaa0f2c7a2ea5db677945d29e664f105e38a661446caea9d3e212fd0e118ff0a`.

The older identities in the original goal section below are historical
preregistration evidence, not authorization to launch stale images. If any of
the three live upstream identities differs before an arm, the runner stops and
the identity rolls forward again without weakening any optimization or gate.

## Original preregistration identity (dated evidence)

The original protocol targeted vLLM
`2ec6f0d71ea3b350952630e310efcda1c744ff4d` first with the stock kernel from
the official-image base and then with XPU kernels
`4543b580fecca68a7dd54ddaf6e444dc5f11a6a4`. The immutable image IDs are:

- current vLLM / stock kernel:
  `sha256:f8a740ce23034ca4278b66aa8cd9ac75df10726e05fe964f6bacb5a55a0c4ef4`;
- current vLLM / current kernel:
  `sha256:79820a7ec6258f08b070e00aa0fc872b7671704a30651364de068cd892c64986`.

Both are zero lab source-overlay builds. Before and after every arm, resolve
the live upstream vLLM and kernel `main` heads. If either differs from the
receipt, the images become dated evidence only and must be rebuilt before they
can be described as current. The lab repository must also be clean `main` and
equal the live remote `main`, not merely a stale local remote-tracking ref.

## What is and is not being preserved

The certified target-only MTP0 curve, TP1/2/4
`30.2 / 48.8 / 71.7 tok/s`, used unmodified upstream source. Its accepted
optimization layer is the model identity, launch/topology contract, XPU graph,
fresh ext4 cache and autotune decisions, and the full correctness/quality
contract. Those remain mandatory. A zero-source-overlay result therefore does
not mean zero optimization; it isolates whether current upstream still
supports the accepted runtime layer.

The accepted TP2/TP4 `.best_config` decision overlays are not copied into this
TP1 source-attribution run. They remain versioned artifacts and must be
graph/config-hash remapped and requalified before judging TP2/TP4 preservation.
Compiled binaries and outer caches are never copied across code identities.

Two historical source behaviors remain absent upstream and are retained as
separate default-off forward ports after the target-only TP curve is gated:

1. target INT8 LM head with BF16 scales;
2. role-explicit draft group-128 INT4 LM head with BF16 scales and no target
   head sharing.

They are not silently abandoned, and they are not mixed into this control.
Rejected persistent GDN scratch, global force-chunk behavior, and obsolete
collective flags are preserved as evidence but are not accepted overlays.

## Frozen six arms

For each image lane, run exactly three arms on GPU 0, TP1, MTP0, F16 model/KV,
32K maximum context, one sequence, 1024 batched tokens, memory utilization
0.90, XPU graph, prefix caching off, chunked prefill on, thinking disabled,
and a topology-local ext4 cache:

1. fresh-cache 25-prompt diagnostic, 512 tokens with EOS ignored;
2. exact-cache natural-EOS replay A with the full objective quality battery
   and prior-quality baseline;
3. exact-cache natural-EOS replay B on the same sealed cache.

The effective graph contract is `FULL_AND_PIECEWISE` with capture sizes
`[1,2]` and maximum 2. Async scheduling is enabled. These are the resolved
upstream defaults for the protected TP1 configuration; the runner makes them
explicit and verifies the effective engine log so a default change cannot
silently alter the lane.

This TP1 campaign uses `PYTHONHASHSEED=0`, matching the protected strict TP1
and latest TP1 current-refresh identity. The older diagnostic `30.2178` floor
originated with the variable unset, so it is a protected speed threshold here,
not mislabeled as an exact diagnostic-identity replay. Seed 0 is not claimed
to solve fresh-compile or runtime token nondeterminism.

The stock-kernel control is a coarse comparison screen. Its speed result is
always recorded, but independent fresh autotune realizations and fixed
control-first order mean a small control/both delta is not causal proof about
the kernel. A slow stock control does not veto a fully qualified current
kernel: the active candidate is the both-current image. Any control identity,
correctness, cache, benchmark-shape, or quality failure still stops the
sequence.

## Frozen promotion gates

The both-current lane must satisfy all of the following before TP2 work:

- diagnostic conventional 99-interval median at least `30.2178 tok/s`;
- both strict medians at least `30.31067504052998 tok/s`;
- 25 valid rows per benchmark, 100 metric-token events / 99 intervals, returned
  token IDs, and `cached_tokens=0`;
- code-14 canary, seven exact cases, eight repeat requests, 8K requested needle
  with 7,617 actual prompt tokens, and 24 baseline comparisons;
- direct-plus-ordinary verification of all 19 model files;
- exact GPU ordinal 0 mapping to BDF `0000:23:00.0` and UUID
  `00000000-0000-0023-0000-0000e2238086`, with all four render nodes free of
  pre-existing holders immediately before launch;
- identical cache manifests before and after each replay, measured only after
  the invocation-owned container has been removed;
- read-only, hash-sealed snapshots of the receipt, suite, quality baseline,
  runner, model verifier, benchmark helper, and quality helper for every arm;
- exact image/source/import/label identity and unchanged upstream heads.

Runtime token arrays are compared and reported. They are not a promotion gate:
prior exact-cache TP4 evidence matched only 21/25 full outputs despite an
unchanged 4,421-file cache, while all objective quality gates passed. The
cross-boot/runtime nondeterminism disclosure therefore remains mandatory.

Any slower result is appended as regression evidence and never lowers or
overwrites these protected historical values:

- diagnostic highs: TP1 `30.2569`, TP2 `48.950458800865434`, TP4 `71.6741`;
- strict floors/highs: TP1 `30.31067504052998`, TP2
  `49.01965141150585`, TP4 both at least `71.29326283364946` and one at
  least `71.39843006187554`;
- accepted current-runtime decision-overlay captures: TP2 diagnostic/strict
  `49.05894025767351 / 49.00935245117815`; TP4 diagnostic/strict
  `71.72254506718171 / 71.35287190161719 / 71.45427094575045`.

## Next topology rules

If both-current TP1 passes, create topology-specific runners rather than
loosening this TP1-only runner. TP2 uses GPUs 2,3, memory utilization 0.90,
and the protected hash-seed-unset identity; TP4 uses GPUs 0,1,2,3, memory
utilization 0.60, and its protected hash-seed-unset identity. Each begins with
a fresh current-code cache, then remaps only compatible versioned autotune
decisions and replays the full quality contract. TP4 at 0.90 is forbidden due
to the known 20.13-GiB single-allocation failure. TP3 remains structurally
unsupported because 16 GDN K heads are not divisible by three.

After the target-only curve is current-qualified, matrix expansion returns to
the neural.download coverage goal: canonical contexts 0/2/4/8/16/24/32K,
hierarchical MTP0-4+ expansion, TP1/2/4, quantization as model variants,
versioned estimates for safe gaps, and measured replacements as packets become
available. Performance, correctness, optimization evidence grade, model
quality, and popularity remain separate axes; decode rate alone does not rank
the site.
