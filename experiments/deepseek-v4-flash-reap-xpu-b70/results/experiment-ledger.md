# DeepSeek V4 REAP/XPU Experiment Ledger

Preserve every meaningful attempt, including failures.

| Date | Label | Status | Evidence | Decision |
| --- | --- | --- | --- | --- |
| 2026-07-13 | investment-red-team | complete | `../data/fit-audit-20260713.json`, `../../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md` | Strategic go; reject direct K180 commitment. Run Stages 0-3.5 before download, build K160 first, and climb only after quality/warm-memory gates. |
| 2026-07-13 | storage-runtime-download-start | active | `../scripts/download-k160.sh`, `../scripts/capture-stage0.sh`, clean worktrees under `/home/steve/src/deepseek-v4-*` | Archived 170 GiB of reviewed inactive artifacts with compatibility symlinks; internal free space rose from 11 to about 180 GiB. Prioritize frozen public uniform-K160 as the first runnable checkpoint. |
| 2026-07-13 | k160-provenance-audit | complete | `../quality/calibration-v1-plan.json`, `../quality/suite-v1.json` | Public K160 is valid for smoke/performance bring-up but not quality-certified: hash layers are pruned and published observations are not true REAP. Preserve the official-source teacher and hash-preserved final-pack lanes. |
| 2026-07-13 | exact-shape-test-scaffold | implemented | XPU-kernel commit `552c9ce`, `../scripts/run-exact-shape-gates.sh` | Added low-level H4096/I2048/top-k6/M1,4,8 correctness coverage for MXFP4 and INT4 controls at E=40/64. This is not yet the Stage-1 performance, selector, replay, fallback, or TP4/EP gate. |
| 2026-07-13 | runtime-build-j16 | loss | resumable build/cache under `/home/steve/src/deepseek-v4-xpu-kernels-clean` | The Xe2 grouped-GEMM translation unit was killed under 16-way SYCL compilation. Preserve completed objects/ccache and resume at the durable eight-job default; this is host build-memory pressure, not a kernel result. |
| 2026-07-14 | runtime-build-j8 | pass | `../data/runtime-pin-20260714.json`, `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/stage0-20260714T044033Z.txt` | Incremental eight-job Xe2/SYCL-TLA build completed in 10m40s; pinned vLLM/kernel imports resolve to clean worktrees and all four B70s enumerate. The selector fix prevents `-k 40` from also matching E=64 via dimension 4096. |
| 2026-07-14 | exact-shape-scaffold-preflight | infrastructure-fail | `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/stage1-20260714T044101Z` | Clean environment lacked pytest; no GPU case ran. Installed and pinned pytest 9.0.2 before retrying. |
| 2026-07-14 | exact-shape-scaffold | scaffold-pass | `../data/exact-shape-scaffold-20260714.json`, `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/stage1-20260714T044200Z` | All 12 exact M=1/4/8, E=40/64 MXFP4/INT4 low-level reference cases passed on four B70s. This does not clear Stage 1A/1B; performance, metrics, selector, fallback, replay, and TP4+EP evidence remain. |
| 2026-07-14 | four-card-xccl-preflight | pass | `../data/runtime-pin-20260714.json`, `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/xccl-preflight-20260714T044502Z.log` | All four per-device smokes, four-rank XCCL init/barrier, and allreduce passed over oneCCL/OFI on `eno1`; topology correctly reports PCIe/NODE rather than direct fabric. |
| 2026-07-14 | k160-download-resume | active | `../data/k160-download-start-20260713.json`, `../scripts/download-k160.sh` | Five completed shards survived the 16-way host-memory event. The frozen revision resumed through the external Xet cache after constraining compilation to eight jobs; final HF/SHA-256 verification remains mandatory. |
| 2026-07-14 | k160-artifact-promotion | pass | `../../../data/deepseek-v4-k160-tp4-bringup-20260714.json`, `/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu/current-k160` | All 46 shards, 43,843 index entries, safetensor headers, HF metadata, and SHA-256 values passed. Archive and hot copy are verified; K160 remains an experimental smoke checkpoint, not a quality promotion. |
| 2026-07-14 | k160-tp4-eager-construction | pass | `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-smoke-20260714T132607Z` | TP4+EP assigned 40/160 experts per rank and selected `XPUExpertsMxFp4`. The 2K/95% configuration fits at 24.95 GiB model plus 2.11 GiB KV per rank; the arithmetic canary returned 1073. Earlier 8K/90% and 2K/98% memory attempts remain preserved as failures. |
| 2026-07-14 | k160-tp4-eager-decode | performance-fail | `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-smoke-20260714T132607Z/steady-long-128.json`, `../../../data/deepseek-v4-k160-tp4-bringup-20260714.json` | The second warm 128-token diagnostic row reached only 2.616225 tok/s after TTFT. This is about 19x below the 50 tok/s gate; speculation remains prohibited. |
| 2026-07-14 | k160-breakable-xpu-graph | infrastructure-fail | `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-smoke-20260714T133502Z/server.log` | Capture fails when sparse FP8 decode executes `combined_lens.max().item()`, causing a prohibited host wait on a Level Zero command-graph event. Remove or make that scalar graph-safe before another graph performance run. |

## Entry Template

```md
## YYYY-MM-DD label

- Stage:
- Status: `failed|passed|rejected|promoted|inconclusive`
- Source/model/manifest revisions:
- vLLM/XPU-kernel commits and diffs:
- Command and environment:
- Hardware/topology:
- Result and profile paths:
- Correctness/quality artifacts:
- Memory/backend/graph trace:
- Decision and next gate:
```
