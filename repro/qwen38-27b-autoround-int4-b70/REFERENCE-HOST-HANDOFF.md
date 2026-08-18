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
