# Reference-host handoff and safe division of work

The model itself is independently available and fully verified. Full server
measurement belongs on `steve-b70s` (four B70s, about 125 GiB RAM). The second
host, `steve-TURIND8-2L2T` (two B70s, about 15 GiB RAM), is limited to source,
build, and bounded op-level audits; a prior server warmup exceeded its memory
cgroup and reset a GPU. Do not move a full run there merely because its GPUs
are idle.

## Please publish from the measuring host

1. Run the read-only preflight and retain its complete output:

   ```bash
   MODEL_DIR=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan \
     repro/qwen38-27b-autoround-int4-b70/scripts/preflight.sh
   ```

2. Publish a bootstrap script or exact package lock that reconstructs Python
   3.12, PyTorch `2.11.0+xpu`, Triton XPU `3.7.0`, editable vLLM commit
   `44fc8fde09`, and vLLM-XPU-kernels commit `2dd55f380d`. Include the exact
   oneAPI/compiler environment used to build the retained extensions.
3. Publish the source-driven graph-safe FlashAttention rebuild and functional
   validation commands. Do not publish the 3.1 GB AOT binaries merely to match
   their hashes: those hashes are measuring-host provenance, not a portable
   source-build target.
4. Publish the oneCCL build command and both graph oracles used with public
   parent `b52f40c07f` / libccl `4ceafd15c0`.
5. Record peak host RSS, peak swap, and whether model loading/warmup temporarily
   stages weights in host memory. Provide the smallest tested cgroup or systemd
   memory limits and a fail-closed abort condition for a 15 GiB host.
6. Preserve compact raw evidence for the Qwen3.8 baseline: enough rows to
   recompute the all-25, selection-12, and holdout-13 medians, complete prompt
   and output identities, cache telemetry, environment capture, and the
   per-run relative `SHA256SUMS`. The current summary contains only a raw-root
   name and manifest hash, which cannot be independently recomputed.
7. Run and publish a matching B replicate plus a Qwen3.8 target-only quality
   oracle. Qwen3.6 output cannot be used as the correctness baseline for new
   Qwen3.8 weights.

The current source-level queue for >105 tok/s is now:

0. **Protect result identity first.** The launcher at `c8db35513` requires an
   explicit manifest and verifier, hashes every model file through direct I/O,
   then hashes the complete ordinary cached view immediately before vLLM
   starts. Both views must match the manifest and each other. It also records
   the effective draft fallback margin and persistent-scratch value. Do not
   run an older warning-and-continue/direct-only gate.
1. **Create a fresh margin-free target-only oracle**, then re-run the current
   margin-free MTP5 identity on the recovered measuring host. The working
   anchor is `101.170 tok/s` all-25 (`92.851` selection-12), median of three
   arms, but its pairwise parity is only 21/25, 21/25, and 22/25. It is not a
   promotable result.
2. **Run TP1 on the reduced four-prompt divergence suite.** Every serving op
   has now been swept. The audit found and gated an INT4 prefill-band race and
   a ReplaySSM commit race, but the latter is inert when `REPLAYSSM_SPEC=0`
   and the former explains at most one of four divergent prompts. TP1 removes
   the collective and is the cleanest discriminator before another full A/B.
3. **Treat the cheap draft fallback margin as diagnostic-only.** The shipped
   patch replaces costly full-vocabulary work, but its synthetic 40/40 test is
   single-shard and does not bound real TP2 logit error. Add startup/call/row/
   candidate counters and capture real TP2 local and gathered logits versus
   full-FP16 before a 25-prompt performance run. A margin of `0.25` is only an
   equivalence bound if the maximum relevant logit error is below `0.125`.
4. **Keep DFlash 2 separate.** llama.cpp PR #27342 is still open and targets a
   GGUF draft model. Initial reports are single-device and strongly dependent
   on workload, context, width, and concurrency. It is not a drop-in lever for
   the active vLLM AutoRound W4A16 TP2 identity; see the
   [intake note](../../experiments/qwen38-27b-b70/notes/2026-08-20-dflash2-future-lane-intake.md).

Closed or already-banked items:

- draft LM head INT4 was already enabled in every record/baseline arm;
- persistent scratch was already enabled historically despite the published
  command saying `0`; zero-init is correctness work, not new speed headroom;
- spec-greedy top IDs and engaged GDN-core capture each regressed about
  `2.2 tok/s` versus the `101.170` anchor;
- local argmax cannot engage under MTP, RMSNorm batch invariance did not repair
  repeatability, and ReplaySSM fixes are inert in this lane;
- the M=4 residual/RMSNorm/INT4 gate-up fusion remains closed NO-GO.

## Why execution is paused on the second host

An exploratory stock-container smoke is already a closed negative result. It
loaded all eight model payloads, reported 8.44 GiB of model memory per rank,
then exceeded a 9 GiB host-memory cgroup during warmup. The worker was killed
by the memory controller and one BCS engine reset. Both GPUs recovered and
report normal, but the stock image must not be retried or given a larger blind
memory allowance. See the linked low-RAM safety note in the main README.

The second host also had only about 12 GiB free on `/mnt/fast-ai` at the last
audit. A full source/runtime/AOT reconstruction therefore requires a deliberate
storage plan; no protected benchmark or model material should be deleted
implicitly.
