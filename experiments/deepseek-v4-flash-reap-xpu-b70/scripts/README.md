# DeepSeek V4 REAP/XPU Scripts

Add helpers only as their stage begins. There is intentionally no full-model
download script while Stages 0-3.5 are incomplete.

Expected first helpers:

- exact-shape MXFP4/INT4 fused-MoE test;
- heterogeneous dummy-model construction test;
- architecture fixture runner;
- runtime/hardware/storage identity capture.

The Stage 4 downloader must be official-source-only, revision-pinned, and fail
closed unless the ledger contains explicit download authorization.
