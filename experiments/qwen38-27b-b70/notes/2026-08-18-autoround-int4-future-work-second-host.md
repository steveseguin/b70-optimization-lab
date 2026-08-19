# Future work: items blocked on the 15 GiB second host

Date: 2026-08-18
Status: parked. Each item names its unblocking condition and the host class
that can execute it. This host (15 GiB RAM) cannot run vLLM servers: weight
load stages >12 GiB of driver-pinned host memory in ~6 s, collapsing the
desktop (two contained incidents on 2026-08-18; see
2026-08-18-autoround-int4-smoke-host-staging-collapse-contained-unsafe.md).

## A. Host-staging-free model loading (unblocks everything below here)

vLLM already streams safetensors lazily via mmap from local ext4; the
collapse is NOT disk reads. It is host-side pinned/committed memory during
the H2D weight staging phase. Candidate mitigations, in order:

1. Measure the staging peak properly on a big-RAM host (reference-host
   handoff item 5: peak host RSS, peak swap, staging behavior, smallest
   tested cgroup MemoryMax, fail-closed abort). The stock-container incident
   shows a 9 GiB memcg DID kill the worker, so memcg likely accounts the
   staging — a `systemd-run --scope -p MemoryMax=10G` probe is the cheapest
   bounded experiment once someone can tolerate a possible freeze.
2. Chunked/pinned-bounded H2D staging in the XPU loader path (source patch;
   `--max-parallel-loading-workers` exists at 44fc8fde0 but is a parsed
   no-op — do not rely on it).
3. Bound oneCCL host buffers (`CCL_SYCL_SCALEOUT_HOST_BUF_SIZE`,
   `CCL_SYCL_TMP_BUF_SIZE`; plain decimal bytes, no minimums) — only after
   re-running both graph collectives with the exact candidate env. Worth
   ~1.75+ GiB pinned. Secondary to the load spike.
4. More host RAM.

## B. Draft INT4 top-K rerank screen (measuring host)

Patch audited and ready:
2026-08-18-autoround-int4-draft-topk-rerank-audit.md. Start K=2. Screen the
previously divergent holdout prompt + one control across two cold runs for
token-ID parity and draft acceptance before any strict-25.

## C. GDN scratch zero-init build + measure (measuring host)

Patch reviewed:
2026-08-18-autoround-int4-gdn-scratch-zero-init-review.md
(vllm-xpu-kernels `0ab8205`, branch `fix/gdn-scratch-zero-init`). Build
needs >14.2 GiB RAM for the GDN TU and ~2.3+ GB disk. If it passes the
adoption gate in the review note and beats 101.922, supersede the
LocalMaxxing row.

## D. Fresh-compile determinism arm (measuring host)

The approved 101.922 record ran on a pinned compile cache; its queue JSON
carries no PYTHONHASHSEED / inductor-autotune control metadata.
Requirement: describe fresh-compile behavior separately (fresh compile A/B,
same-cache replay, restart replay). Candidate controls are in
2026-08-18-autoround-int4-inductor-autotune-determinism-candidate.md
(`PYTHONHASHSEED=0`, `VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE=0`,
`VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING=0`).

## E. Second-host role once A lands

This host's value is independent replay and preflight/hash verification.
With a bounded loader it can re-run smoke and quality arms; without it,
keep it launch-free.
