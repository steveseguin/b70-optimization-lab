# Reference-host handoff needed for safe independent replay

The model itself is independently available and fully verified. The remaining
gap is the exact runtime identity and a measured procedure that is safe on the
second lab host, which has 15 GiB of system RAM.

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

Once those gates exist, the source-level queue for >105 tok/s, in order
(details in `experiments/qwen38-27b-b70/notes/`):

0. **Determinism gate (blocks every promotion claim).** Two runtime races
   were found and fixed on the second host, both with staged builds and
   op-level gates:
   - oneDNN int4 GEMM race for prefill chunk M in [129,448] → determinism
     pad (2026-08-20-autoround-int4-runtime-nondeterminism-found-and-pad-fix.md);
   - `gdn_replayssm_commit_pending` double race (in-place shift + pending
     flag) corrupting conv state ~1/4000 calls at decode time
     (2026-08-20-replayssm-commit-pending-race-found-and-fixed.md).
   Triple-fix staged build: `/home/steve/staged-xpu-commitfix-20260820`
   (manifest in `manifests/staged-xpu-commitfix-20260820.sha256`; also
   rebuild from the three patch files under
   `experiments/qwen38-27b-b70/patches/`). Next run: margin-free +
   PERSISTENT_SCRATCH=1 + this build, pinned shared compile cache, two
   arms, 25-prompt suite, token-ID parity 25/25 required. Every decode-path
   op was audited bitwise deterministic and batch/row-invariant
   (2026-08-20-decode-path-determinism-audit.json); if divergence persists,
   sweep GDN chunk prefill (Triton) server-side — its standalone sweep
   fails to compile on the second host.
1. Build and A/B the zero-init GDN scratch fix (`e34e82b05`, kernel note
   2026-08-18). Built and op-level validated on the second host
   (2026-08-19-autoround-int4-gdn-scratch-zero-init-built-ab.md):
   +0.42-0.44 ms/step measured on the real op; strict-25 rerun is the
   remaining proof.
2. **Full-graph capture screen** — assembled but never benchmarked on the
   Qwen3.8 MTP5 record config: graph-safe head256 stage + rebuilt oneCCL
   graph collectives + zero-init persistent scratch are all validated, yet
   the record runs PIECEWISE with DDTREE_FULL_GRAPH=0. The step cost model
   (2026-08-19-autoround-int4-step-cost-model.md) shows ~53% of the 35.3 ms
   step is NOT weight streaming (GEMMs are already at ~90% of the ~608 GB/s
   HBM roofline — no GEMM kernel headroom; split-N is bit-exact but
   slower). This is the largest identified lever.
3. Screen the rerank K=2 draft-top-k candidate (audit
   2026-08-18-autoround-int4-draft-topk-rerank-audit.md); estimated +3–6 tok/s
   from acceptance lift at unchanged verifier cost.
4. The M=4 residual/RMSNorm/INT4 gate-up fusion is **closed NO-GO**: its
   fusible share measured 31.9 µs/layer, below the 0.04 ms/layer threshold;
   see 2026-08-19-autoround-int4-fusion-gonogo-negative.md. Do not build it.

## Why execution is paused on the second host

An exploratory stock-container smoke is already a closed negative result. It
loaded all eight model payloads, reported 8.44 GiB of model memory per rank,
then exceeded a 9 GiB host-memory cgroup during warmup. The worker was killed
by the memory controller and one BCS engine reset. Both GPUs recovered and
report normal, but the stock image must not be retried or given a larger blind
memory allowance. See the linked low-RAM safety note in the main README.

The second host also has only about 12 GiB free on `/mnt/fast-ai`. A full
source/runtime/AOT reconstruction therefore requires a deliberate storage
plan; no protected benchmark or model material should be deleted implicitly.
