# Container route status

**Not built, not replayed** as of 2026-09-06. The `Dockerfile` and
`container-serve.sh` pin the same identities the native gate verifies and are
published so a reader can review the closure, but no image id, registry digest,
or in-container replay exists yet. Until an in-container run reproduces the
record's output pins on four B70s, the delivery of this package is `native`
only. When that replay lands, this file gains the image id, the ghcr.io digest,
the replay attempt number, and its result hashes, and the package gains
`container` delivery.

Build attempts (2026-09-06): the overlay clone, tag and tree check, the hosted
stage install through the frozen installer (18 files verified), and the hosted
oneCCL install all succeed; the build then stops on purpose at the runtime
check because the base image `vllm/vllm-openai-xpu@sha256:f01e24f6…` ships
`torch 2.13.0+xpu`, while the record ran on `torch 2.11.0+xpu` and the kernel
stage's native modules were built against that ABI. The container route needs
a base (or an in-image environment build from an installable lock) that pins
`torch 2.11.0+xpu` and `triton 3.7.0`; until then the image cannot carry the
record's identity and is not built past that check.

Known gaps to close before the container replay:

- a base image or lock that reproduces `torch 2.11.0+xpu` / `triton 3.7.0`
  (the lab's venv receipt is `pip-freeze-observed.txt`, not a hash lock);

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
