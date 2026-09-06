#!/usr/bin/env bash
# Verify every identity the lossless MTP1 record depends on, without touching
# the GPUs. Environment overrides point at the same verified artifacts elsewhere;
# absent defaults stop with a message naming the variable.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo="$(cd -- "$script_dir/../.." && pwd -P)"
vllm_tree="${REPRO_VLLM_TREE:-/home/steve/src/vllm-current-main}"
stage="${REPRO_KERNEL_STAGE:-/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70}"
oneccl="${REPRO_ONECCL_ROOT:-/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public}"
model="${REPRO_MODEL_ROOT:-/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8}"
venv="${REPRO_VENV_ROOT:-/home/steve/.venvs/vllm-xpu}"
die() { printf 'lossless MTP1 identity: %s\n' "$*" >&2; exit 2; }
[[ -e "$vllm_tree/.git" ]] || die "vLLM tree absent: $vllm_tree (REPRO_VLLM_TREE)"
[[ -d "$stage/vllm_xpu_kernels" ]] || die "kernel stage absent: $stage (REPRO_KERNEL_STAGE)"
[[ -f "$oneccl/lib/libccl.so.1.0" ]] || die "oneCCL build absent: $oneccl (REPRO_ONECCL_ROOT)"
[[ -f "$model/config.json" ]] || die "model absent: $model (REPRO_MODEL_ROOT)"
[[ -x "$venv/bin/vllm" ]] || die "venv absent: $venv (REPRO_VENV_ROOT)"
# 1. overlay source: bundle, tag, tree, and the 55-patch series
REPRO_VLLM_TREE="$vllm_tree" "$repo/patches/qwen38-flash-next-fp8-b70/vllm-lossless-mtp1-1b2a17c1/verify-series.sh" >/dev/null
[[ "$(git -C "$vllm_tree" rev-parse HEAD)" == 1b2a17c1e7c41985d6a5e0eb324ada4775c25e60 ]] || die "vLLM tree is not checked out at 1b2a17c1 (git checkout q38-lossless-mtp1-1b2a17c1)"
[[ -z "$(git -C "$vllm_tree" status --porcelain --untracked-files=no)" ]] || die "vLLM tree is dirty"
# 2. kernel stage: the 18 loadable files of the hosted 2f829747 stage
(cd "$stage/vllm_xpu_kernels" && sha256sum --quiet -c "$repo/repro/qwen38-flash-next-fp8-tp4-mtp3-b70/runtime-stage.sha256") || die "kernel stage bytes differ from the hosted 2f829747 stage"
[[ "$(find "$stage/vllm_xpu_kernels" -type f \( -name '*.py' -o -name '*.so' \) | wc -l)" == 18 ]] || die "kernel stage file set changed"
# 3. collective runtime
(cd "$oneccl" && sha256sum --quiet -c "$repo/patches/qwen38-flash-next-fp8-b70/oneccl-4ceafd1-b70-public/lib.sha256") || die "oneCCL bytes differ"
[[ "$(sha256sum "$venv/lib/ccl/kernels/kernels.spv" | cut -d' ' -f1)" == 0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9 ]] || die "venv kernels.spv differs"
# 4. model: publisher revision contract (config + safetensors index + shard count)
[[ "$(sha256sum "$model/config.json" | cut -d' ' -f1)" == 99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d ]] || die "model config.json differs from revision bcd9f01d"
[[ "$(sha256sum "$model/model.safetensors.index.json" | cut -d' ' -f1)" == 0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6 ]] || die "model safetensors index differs from revision bcd9f01d"
[[ "$(ls "$model"/model-*.safetensors | wc -l)" == 131 ]] || die "model shard count is not 131"
# 5. tuned MoE map, exactness verifier, frozen packet
[[ "$(sha256sum "$repo/experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32/"*.json | sha256sum | cut -d' ' -f1)" != "" ]] || die "tuned map missing"
pin_sha=$(sed -n 's/^sha256=//p' "$script_dir/verifier-pin.txt"); pin_blob=$(sed -n 's/^blob=//p' "$script_dir/verifier-pin.txt"); pin_commit=$(sed -n 's/^lab_commit=//p' "$script_dir/verifier-pin.txt")
git -C "$repo" cat-file -e "$pin_blob" 2>/dev/null || die "the pinned exactness verifier blob $pin_blob is not in this clone's history"
[[ "$(sha256sum "$repo/experiments/qwen38-flash-next-fp8-b70/tools/verify-moe-m1-w13-n32-selection.py" | cut -d' ' -f1)" == "$pin_sha" ]] || die "the exactness verifier has moved on since the record; the frozen packet pins sha $pin_sha (git blob $pin_blob). Replay from a worktree of the lab repository at commit $pin_commit (git worktree add /path/to/replay $pin_commit) or restore that file from the blob before launching"
(cd "$repo/experiments/qwen38-flash-next-fp8-b70/tools" && sha256sum --quiet -c "$script_dir/frozen-a189-packet.sha256") || die "frozen A189 packet drifted"
# 6. python runtime, imported the way the launcher runs the server (kernel stage and overlay
#    first on PYTHONPATH; the venv's own vllm package is shadowed and its version is not the record's)
PYTHONPATH="$stage:$vllm_tree" "$venv/bin/python" - "$vllm_tree" <<'PY' || die "python runtime versions differ from the record"
import sys, importlib.metadata, torch, triton, vllm
assert torch.__version__ == "2.11.0+xpu", torch.__version__
assert triton.__version__ == "3.7.0", triton.__version__
# the record's runtime-versions.txt reads the installed vllm distribution's metadata (the
# launcher records importlib.metadata.version); the overlay tree in front of it is the code
assert importlib.metadata.version("vllm") == "0.20.2rc1.dev2+gc51df4300.d20260523.xpu", importlib.metadata.version("vllm")
assert vllm.__file__.startswith(sys.argv[1]), vllm.__file__
PY
echo "lossless MTP1 identity verified: vLLM 1b2a17c1 over 76cfe1cd, stage 2f829747, oneCCL 4ceafd1 public, model bcd9f01d"
