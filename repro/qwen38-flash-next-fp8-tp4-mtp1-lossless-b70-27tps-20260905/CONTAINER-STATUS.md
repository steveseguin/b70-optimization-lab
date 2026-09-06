# Container route status

**Not built, not replayed** as of 2026-09-06. The `Dockerfile` and
`container-serve.sh` pin the same identities the native gate verifies and are
published so a reader can review the closure, but no image id, registry digest,
or in-container replay exists yet. Until an in-container run reproduces the
record's output pins on four B70s, the delivery of this package is `native`
only. When that replay lands, this file gains the image id, the ghcr.io digest,
the replay attempt number, and its result hashes, and the package gains
`container` delivery.

Known gaps to close before the container replay:

- the base image ships its own vLLM and kernel wheels; the overlay is loaded
  through `PYTHONPATH` in front of them exactly as the native launcher does, and
  the stage's 18 files must shadow the wheel's `vllm_xpu_kernels` (verified by
  the build-time manifest check, not yet by a loaded-module check);
- the host must expose `/dev/dri` for all four cards, allow pinned host memory
  of about 55 GiB per server (13.78 GiB per rank of UVA offload), and provide the
  verified model directory read-only;
- the tuned MoE map folder is copied in; the launch-time verifier
  (`verify-moe-m1-w13-n32-selection.py`) has to be run against the container's
  server before any measurement counts.
