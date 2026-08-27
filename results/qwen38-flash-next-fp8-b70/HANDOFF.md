# Qwen3.8 Flash-Next FP8 B70 handoff

The current result is a bounded research screen, not a promoted deployment.
Attempt 19 is the first diagnostic-free healthy TP4/EP4 server and must remain
intact while later matrix cells are added.

## Resume identity

- Model: `/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8`.
- Model revision: `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`.
- Current vLLM source checkout: `/home/steve/src/vllm-current-main` at
  `1372c62d975c554f4b465c8299bc5f3295301ceb`. Attempt 19 used
  `658965050f259999e635b52a850004a3771cd644`; the later changes are the MTP
  tests and fail-closed legacy speculative adapter, while the MTP0 target route
  is unchanged.
- Current XPU-kernel source checkout: `/home/steve/src/vllm-xpu-kernels` at
  `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`.
- Preserved runtime used by MTP0 and the accepted untreated MTP1 control:
  `/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70`, built from
  kernel source `2f829747503c77d4814834dffd0840fb1dd9f75a`.
- Launcher:
  `experiments/qwen38-flash-next-fp8-b70/tools/launch-tp4-ep4-eager-mtp0-512.sh`.
- Attempt-19 evidence root:
  `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-512-r1-attempt19`.

Apply vLLM patches `0001`–`0010`, `0012`, and `0014`–`0018` in order on base
`76cfe1cd88d30d525eec8be5bff75f8b77471c88`. Do not apply diagnostic patches
`0011` or `0013` to a qualification or timing tree. Apply all five kernel
patches on base `0fd18a7c08a64d2645bf083cfa5576200b61b02c`. Patch `0005` is the
paused exact-runtime treatment and is not present in the accepted preserved
stage. The authoritative
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

The first configured-3K arm passed an exact cache-zero 2K needle and reported
6,144 cache tokens, but one open-choice repeat differed. The frozen gate
stopped before speed; that quarantine remains retained. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp0-3072-context-screen.json`.

The repeat-v2 retry changed no server setting. Its prescribed canary passed
32/32 first tokens and 16/16 full outputs, the formal exact-2K row passed, and
three comparable rows had a `5.228429 tok/s` median after first text. The 2K
selector is research-screened; the known 5/7 short boundary remains. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp0-3072-context-repeat-v2-screen.json`.

The additive configured-4,352 arm passed exact baseline agreement, 16/16
fixed-set repeats, the exact cache-zero 4K needle, and the formal depth gate.
Its formal rate was `4.456026 tok/s`; three legacy-comparable exact-4K rows had
a `5.233665 tok/s` after-first-text median. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp0-4352-context-screen.json`.

The additive configured-8,448 arm passed exact baseline agreement, 16/16
fixed-set repeats, the exact cache-zero 8K needle, and the formal p8192/o128
gate at `3.979729 tok/s` with `386.534332 s` TTFT. Two legacy-comparable rows
completed at `5.170404 / 5.182353 tok/s` with identical output; the runtime
stopped during row 3, so no legacy median or curve point is authorized. Commit
`08a865143` makes the helper fail closed on incomplete streamed responses.
Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp0-8448-context-screen.json`.

Next, qualify MTP3 at configured maximum 4,352 with its exact 25-block fixed
cache, then fill MTP2/MTP4 and deeper MTP1 cells. Audit the XPU host-lookup
overlap separately. Defer 16K+ until the 8K repeated-serving boundary and
larger fixed-cache requirement have a bounded design. TP1/TP2 need a new memory design
and are not simple launch variants. Never overwrite the 512 or 1,536 attempts,
remove the accepted runtime, or replace a captured rate with an estimate.

## TP4 MTP1/512 closeout

The performance-preserving speculative adapter is complete at vLLM
`1372c62d975c554f4b465c8299bc5f3295301ceb`. The matched untreated-runtime arm
at attempt 3 passed all 26 MTP0 baseline comparisons once both clients used
`enable_thinking=false`, held the fixed-set repeat at one hash for 16/16 runs,
passed the small cache-zero needle, and measured `9.773841 / 9.372254 /
8.107468 tok/s`, median `9.372254 tok/s` after first text. It accepted 503/505
drafts in cumulative endpoint metrics. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp1-512-attempt3-result.json`.

Attempt 2 remains preserved as a client-identity mismatch, not a runtime
parity failure. The exact-runtime candidate and its component gates remain
preserved but are paused because the unchanged runtime passed. Next qualify
MTP1 at deeper context and audit whether the current XPU UVA lookup overlaps
host-row transfer like the official NVIDIA PLE-prefetch design. Keep MTP0 and
MTP1 as separate Grade-C cells; neither is deployment- or record-eligible.
The deployment audit and bounded replacement gate are in
`experiments/qwen38-flash-next-fp8-b70/notes/2026-08-27-ple-deployment-audit.md`.

## TP4 MTP3/512 closeout

Attempt 4 is the first valid configured-512 MTP3 arm. It retained the MTP1
source, staged runtime, selective host placement, TP4/EP4, eager/graph-off, and
client identity, while using the independently sized 20-block fixed cache
(`235356160` bytes). It became healthy with 568 cache tokens, matched all 26
bounded MTP0 comparisons, held 16/16 fixed-set repeats to one hash, passed the
small cache-zero needle, and completed all 24 audited quality requests without
cache reuse. The inherited strict boundary remains 5/7; the 317-token needle
is not evidence of 4K MTP3 quality.

Three p146/o256/c1 rows measured `17.473321 / 14.888790 / 12.538689 tok/s`,
median `14.888790 tok/s` after first text, with the exact MTP0 target hash. The
post-session endpoint reported 768/768 cumulative draft tokens accepted. The
rows declined monotonically and span 33.14% of the median, so this is a Grade-C
research cell rather than a stable ceiling or record. MTP0 remains primary and
the MTP1 cell is unchanged. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp3-512-attempt4-result.json`.

The user has selected roughly 4K as the practical deployment ceiling for now.
The next launch should therefore use configured maximum 4,352 and exactly
`294195200` cache bytes (25 blocks) for a 4,096-token prompt plus 256 output
tokens. Preserve the current host placement: the PLE/input-embedding shards are
resident in pinned system RAM during service, not streamed from the USB model
tree. Do not describe MTP3 as 4K-qualified until that separate gate passes.
