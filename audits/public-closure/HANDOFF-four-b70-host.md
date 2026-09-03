# Public-closure handoff for the four-B70 host

Generated 2026-09-02 from `tools/public-closure-scanner.py` (report: `audits/public-closure/2026-09-02-scan.md`).
The two-B70 host fixed and re-verified the Qwen3.8 27B lanes. The packages below have
recipe scripts that hard-code paths or reference files that exist only on the four-B70
host, so that host should make them portable (env-overridable with fail-closed defaults,
or documented restore/build steps) and re-run the scanner until its package is clean.
Rule: a third party must be able to reproduce every published headline from git-tracked
files plus public release assets; no `/home/<user>`, `/mnt/fast-ai`, or private source tree
on the required route.

Re-run after fixing: `python3 tools/public-closure-scanner.py --package <id>`

## gemma4-26b-a4b-q8-b70-125tps-20260701

- `host_path_hardcoded`: `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf` ← `repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh:48`  
  `EXTRA_LLAMA_ARGS="${EXTRA_LLAMA_ARGS:---parallel 1 --cache-ram 0 --spec-type draft-mtp --spec-draft-model /mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/`

## laguna-s-2.1-int4-b70-125tps-20260731

- `host_path_hardcoded`: `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs` ← `repro/laguna-s-2.1-int4-b70-102tps-20260726/run.sh:24`  
  `readonly run_root=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs`
- `host_path_hardcoded`: `/mnt/fast-ai/llm-models/laguna-s-2.1/int4/config.json` ← `repro/laguna-s-2.1-int4-b70-102tps-20260726/run.sh:149`  
  `check_hash /mnt/fast-ai/llm-models/laguna-s-2.1/int4/config.json \`
- `host_path_hardcoded`: `/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4/config.json` ← `repro/laguna-s-2.1-int4-b70-102tps-20260726/run.sh:151`  
  `check_hash /mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4/config.json \`
- `host_path_hardcoded`: `/mnt/fast-ai/llm-models/laguna-s-2.1/.verification/source-files.sha256` ← `repro/laguna-s-2.1-int4-b70-102tps-20260726/run.sh:153`  
  `manifest_a=/mnt/fast-ai/llm-models/laguna-s-2.1/.verification/source-files.sha256`
- `host_path_hardcoded`: `/mnt/fast-ai/llm-models/laguna-s-2.1/.verification/nvme-files.sha256` ← `repro/laguna-s-2.1-int4-b70-102tps-20260726/run.sh:154`  
  `manifest_b=/mnt/fast-ai/llm-models/laguna-s-2.1/.verification/nvme-files.sha256`
- `host_path_hardcoded`: `/mnt/fast-ai/llm-models/laguna-s-2.1` ← `repro/laguna-s-2.1-int4-b70-102tps-20260726/run.sh:159`  
  `"$model_restore" --verify /mnt/fast-ai/llm-models/laguna-s-2.1 >/dev/null`
- `host_path_hardcoded`: `/mnt/fast-ai/llm-models/laguna-s-2.1` ← `repro/laguna-s-2.1-int4-b70-102tps-20260726/run.sh:163`  
  `--target /mnt/fast-ai/llm-models/laguna-s-2.1`
- `host_path_hardcoded`: `/mnt/fast-ai/llm-models/laguna-s-2.1` ← `repro/laguna-s-2.1-int4-b70-102tps-20260726/restore-models.sh:7`  
  `readonly default_root=/mnt/fast-ai/llm-models/laguna-s-2.1`
- `host_path_hardcoded`: `/home/steve` ← `repro/laguna-s-2.1-int4-b70-102tps-20260726/restore-sources.sh:24`  
  `[[ "$destination" != / && "$destination" != /home && "$destination" != /home/steve ]] \`
- `host_path_hardcoded`: `/home/steve/llm-optimizations` ← `repro/laguna-s-2.1-int4-b70-125tps-20260731/run-record-gate.sh:5`  
  `readonly repo_root=/home/steve/llm-optimizations`
- `host_path_hardcoded`: `/home/steve/src/laguna-vllm-shared-elementwise-m12-20260731` ← `repro/laguna-s-2.1-int4-b70-125tps-20260731/run-record-gate.sh:6`  
  `readonly vllm_root=/home/steve/src/laguna-vllm-shared-elementwise-m12-20260731`
- `host_path_hardcoded`: `/home/steve/src/laguna-xpu-kernels-shared-elementwise-m12-20260731` ← `repro/laguna-s-2.1-int4-b70-125tps-20260731/run-record-gate.sh:7`  
  `readonly kernel_root=/home/steve/src/laguna-xpu-kernels-shared-elementwise-m12-20260731`
- `host_path_hardcoded`: `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-shared-elementwise-m12-repro-$(date` ← `repro/laguna-s-2.1-int4-b70-125tps-20260731/run-record-gate.sh:9`  
  `readonly run_dir="/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-shared-elementwise-m12-repro-$(date -u +%Y%m%dT%H%M%SZ)"`
- `host_path_hardcoded`: `/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public` ← `experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_replemb_measurement_leg.sh:222`  
  `readonly public_oneccl_root="/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public"`
- `host_path_hardcoded`: `/mnt/fast-ai/*` ← `experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_replemb_measurement_leg.sh:512`  
  `[[ -f "$path" && "$(realpath -e -- "$path")" == /mnt/fast-ai/* ]] \`
- `host_path_hardcoded`: `/mnt/fast-ai/llm-models/laguna-s-2.1` ← `experiments/laguna-s-2.1-xpu-b70/tools/laguna_nvme_paths.sh:7`  
  `readonly LAGUNA_NVME_MODEL_ROOT=/mnt/fast-ai/llm-models/laguna-s-2.1`
- `host_path_hardcoded`: `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1` ← `experiments/laguna-s-2.1-xpu-b70/tools/laguna_nvme_paths.sh:10`  
  `readonly LAGUNA_NVME_ARTIFACT_ROOT=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1`
- `host_path_hardcoded`: `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs` ← `experiments/laguna-s-2.1-xpu-b70/tools/capture_laguna_m8_idle_snapshot.py:20`  
  `RUN_ROOT = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs")`

## minimax-m27-b70-89tps-20260520

- `missing_path`: `scripts/00-install-system-deps.sh` ← `packages/minimax-m27-int4-autoround-b70/README.md:39`
- `missing_path`: `scripts/01-download-model.sh` ← `packages/minimax-m27-int4-autoround-b70/README.md:46`
- `missing_path`: `scripts/02-build-stack.sh` ← `packages/minimax-m27-int4-autoround-b70/README.md:47`
- `missing_path`: `scripts/03-verify-runtime.sh` ← `packages/minimax-m27-int4-autoround-b70/README.md:48`
- `missing_path`: `scripts/04-run-quality-gate.sh` ← `packages/minimax-m27-int4-autoround-b70/README.md:49`
- `missing_path`: `scripts/05-run-benchmark.sh` ← `packages/minimax-m27-int4-autoround-b70/README.md:50`
- `missing_path`: `scripts/06-summarize-result.sh` ← `packages/minimax-m27-int4-autoround-b70/README.md:51`
- `host_path_hardcoded`: `/mnt/fast-ai/llm-cache/hf` ← `repro/minimax-m27-b70-89tps-20260520/scripts/01-download-model.sh:9`  
  `mkdir -p "$(dirname "$MODEL_DIR")" /mnt/fast-ai/llm-cache/hf`
- `host_path_hardcoded`: `/home/steve/src/llm-scaler/vllm/custom-esimd-kernels-vllm/python` ← `scripts/run-vllm-minimax-quality-check.py:784`  
  `"/home/steve/src/llm-scaler/vllm/custom-esimd-kernels-vllm/python",`
- `host_path_hardcoded`: `/home/steve/.venvs/vllm-xpu/lib` ← `scripts/run-vllm-minimax-quality-check.py:786`  
  `prepend_env_path("LD_LIBRARY_PATH", "/home/steve/.venvs/vllm-xpu/lib")`
- `host_path_hardcoded`: `/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib` ← `scripts/run-vllm-minimax-quality-check.py:789`  
  `"/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib",`
- `host_path_hardcoded`: `/mnt/fast-ai/vllm-cache-exp/minimax-strict-${LABEL}-${ts}` ← `scripts/run-minimax-strict-quality-gated-candidate.sh:59`  
  `CACHE_ROOT="/mnt/fast-ai/vllm-cache-exp/minimax-strict-${LABEL}-${ts}"`


## Resolution (four-B70 host, 2026-09-02 23:05 EDT)

All three packages scan clean (`2026-09-02-scan-after-four-b70-fix.{md,json}`;
0 of 17 packages with gaps). Recipe scripts now take `REPRO_*` /
`MTP_DRAFT_MODEL` / `LLM_SCALER_KERNELS` / `VENV` / `CACHE_ROOT_PARENT` /
`HF_HOME` overrides with the lab values as defaults and fail closed with a
message naming the variable when a default root is absent; the MiniMax
package README's script links are repo-root-relative. Two lab-only inputs
were copied into their packages: the Laguna q1 canonical teacher
(`repro/laguna-s-2.1-int4-b70-125tps-20260731/teacher-q1-canonical-bench.json`)
and the pinned Laguna `.verification` manifest
(`repro/laguna-s-2.1-int4-b70-102tps-20260726/manifests/model-directory-verification.sha256`).
The Laguna 102tps `run.sh` re-pins the SHA-256 of the five edited helpers, so
a future 125tps replay records the new leg hash rather than the sealed
record's; the README says rebuilt harnesses are a new environment.

Still open, not closable from this host without an identity change: 86 of
118 entries in the Laguna `.verification` manifest are HF download-cache
metadata a fresh download does not reproduce; the pinned venv binaries,
kernel 7.0.0-28, cluster IP, PCI BDFs, and the public oneCCL build have no
public builder. Sealed historical gates outside these packages still pin
the pre-edit helper hashes and were left as sealed.
