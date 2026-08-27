# Qwen3.8 Flash-Next FP8 B70 handoff

The current result is a bounded research screen, not a promoted deployment.
Attempt 19 is the first diagnostic-free healthy TP4/EP4 server and must remain
intact while later matrix cells are added.

## Resume identity

- Model: `/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8`.
- Model revision: `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`.
- vLLM: `/home/steve/src/vllm-current-main` at
  `658965050f259999e635b52a850004a3771cd644`.
- XPU kernels: `/home/steve/src/vllm-xpu-kernels` at
  `2f829747503c77d4814834dffd0840fb1dd9f75a`.
- Runtime: `/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70`.
- Launcher:
  `experiments/qwen38-flash-next-fp8-b70/tools/launch-tp4-ep4-eager-mtp0-512.sh`.
- Attempt-19 evidence root:
  `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-512-r1-attempt19`.

Apply vLLM patches `0001`–`0010`, `0012`, and `0014`–`0016` in order on base
`76cfe1cd88d30d525eec8be5bff75f8b77471c88`. Do not apply diagnostic patches
`0011` or `0013` to a qualification or timing tree. Apply all four kernel
patches on base `0fd18a7c08a64d2645bf083cfa5576200b61b02c`. The authoritative
checksums are in `patches/qwen38-flash-next-fp8-b70/README.md`.

The exact pre-upstream-sync kernel tree also has a verified self-contained
bundle at
`/mnt/usb-models/qwen38-build/source-backups/vllm-xpu-kernels-pre-gdn-sync-2f829747.bundle`
with SHA-256
`be14c05473a77ea908282dc62478dc6fe5f5b55dedd3477f1de0b4f6c21fc149`.
Do not merge the newer upstream GDN refactor casually: it overlaps retained
serving optimizations and needs a deliberate forward port plus parity and
speed qualification.

## Current boundary

Attempt 19 measured 5.142647219 / 5.221849709 / 5.289933931 tok/s after first
text on p146/o256/c1. Both short batteries passed 5/7 strict cases and one of
16 greedy repeats diverged. This is Grade-C research evidence and a
`lab-screened` operating point. It is not record-eligible.

The additive TP4/EP4/eager/MTP0 1,536-token-cap arm is complete. It passed the
987-token needle, 16/16 repeats, and the formal realistic-suite validity gate;
three exact-1K samples had a `5.133588 tok/s` median after first text. The same
5/7 short-quality boundary remains, so the cell is research-only. Its receipt
is `experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp0-1536-context-screen.json`.

Next, use the reported 3,949-token capacity to add a separate configured-3K
arm for the 2K context point without changing the 192-MiB cache. First verify
that the configured maximum leaves enough capacity for the exact request and
output budget. Then
forward-port the speculative runtime for MTP1. TP1/TP2 need a new memory design
and are not simple launch variants. Never overwrite the 512 or 1,536 attempts,
remove the accepted runtime, or replace a captured rate with an estimate.
