#!/usr/bin/env bash
set -euo pipefail

revision="7c360e1cd4a5168099dbc54d16d929bf6df04990"
model_dir="${1:-/mnt/usb-models/models/deepseek-v4-flash-k160-${revision}}"
expected_shards=46
expected_shard_bytes=103107582016
expected_repo_bytes=103123316384
expected_tensor_bytes=103102758088
manifest="${model_dir}/sha256sums.txt"

test -f "${model_dir}/config.json"
test -f "${model_dir}/model.safetensors.index.json"
test -f "${model_dir}/reap_plan.json"

shard_count="$(find "${model_dir}" -maxdepth 1 -type f -name 'model-*.safetensors' | wc -l)"
shard_bytes="$(find "${model_dir}" -maxdepth 1 -type f -name 'model-*.safetensors' -printf '%s\n' | awk '{sum += $1} END {print sum + 0}')"
repo_bytes="$(find "${model_dir}" -type f ! -path '*/.cache/*' ! -name 'sha256sums.txt' -printf '%s\n' | awk '{sum += $1} END {print sum + 0}')"
tensor_bytes="$(jq -r '.metadata.total_size' "${model_dir}/model.safetensors.index.json")"

jq -e '
  .model_type == "deepseek_v4" and
  .num_hidden_layers == 43 and
  .hidden_size == 4096 and
  .moe_intermediate_size == 2048 and
  .n_routed_experts == 160 and
  .num_experts_per_tok == 6 and
  .expert_dtype == "fp4" and
  .quantization_config.quant_method == "fp8"
' "${model_dir}/config.json" >/dev/null

DEEPSEEK_MODEL_DIR="${model_dir}" \
  "${DEEPSEEK_PYTHON:-/home/steve/.venvs/deepseek-v4-xpu/bin/python}" - <<'PY'
import json
import os
import re
from pathlib import Path

from safetensors import safe_open

root = Path(os.environ["DEEPSEEK_MODEL_DIR"])
plan = json.loads((root / "reap_plan.json").read_text())
index = json.loads((root / "model.safetensors.index.json").read_text())

assert plan["status"] == "experimental_checkpoint_not_ready_for_production"
assert plan["base_model_id"] == "deepseek-ai/DeepSeek-V4-Flash"
assert plan["original_experts_per_layer"] == 256
assert plan["kept_experts_per_layer"] == 160
assert plan["hash_routed_layers"] == [0, 1, 2]
keep = plan["keep_maps"]["keep_by_layer"]
ranked = plan["keep_maps"]["ranked_by_layer"]
assert set(keep) == set(ranked) == {str(i) for i in range(43)}
for layer in range(43):
    layer_key = str(layer)
    assert len(ranked[layer_key]) == len(set(ranked[layer_key])) == 256
    assert set(ranked[layer_key]) == set(range(256))
    assert keep[layer_key] == sorted(ranked[layer_key][:160])

weight_map = index["weight_map"]
assert len(weight_map) == 43843
assert index["metadata"]["total_size"] == 103102758088
assert len(set(weight_map.values())) == 46
pattern = re.compile(
    r"^layers\.(\d+)\.ffn\.experts\.(\d+)\.(w[123])\.(weight|scale)$"
)
per_layer = {layer: set() for layer in range(43)}
for name in weight_map:
    match = pattern.match(name)
    if match:
        layer, expert = int(match.group(1)), int(match.group(2))
        per_layer[layer].add((expert, match.group(3), match.group(4)))
for layer, tensors in per_layer.items():
    assert len(tensors) == 160 * 3 * 2, (layer, len(tensors))
    assert {expert for expert, _, _ in tensors} == set(range(160))

for layer in range(3):
    name = f"layers.{layer}.ffn.gate.tid2eid"
    shard = root / weight_map[name]
    with safe_open(shard, framework="pt", device="cpu") as handle:
        tensor = handle.get_tensor(name)
    assert tuple(tensor.shape) == (129280, 6)
    assert int(tensor.min()) == 0 and int(tensor.max()) == 159
    assert tensor.unique().numel() == 160
PY

test "${shard_count}" -eq "${expected_shards}"
test "${shard_bytes}" -eq "${expected_shard_bytes}"
test "${repo_bytes}" -eq "${expected_repo_bytes}"
test "${tensor_bytes}" -eq "${expected_tensor_bytes}"

if [[ -f "${manifest}" ]]; then
  (
    cd "${model_dir}"
    sha256sum --check --strict --quiet sha256sums.txt
  )
elif [[ "${DEEPSEEK_HF_VERIFY:-1}" != "1" ]]; then
  printf 'refusing non-cryptographic verification without %s\n' "${manifest}" >&2
  exit 1
fi

if [[ "${DEEPSEEK_HF_VERIFY:-1}" == "1" ]]; then
  hf_cli="${HF_CLI:-/home/steve/.venvs/vllm-xpu/bin/hf}"
  token_file="${HF_TOKEN_FILE:-/home/steve/.config/huggingface/token}"
  test -x "${hf_cli}"
  test -s "${token_file}"
  HF_TOKEN="$(<"${token_file}")" "${hf_cli}" cache verify \
    0xSero/DeepSeek-V4-Flash-180B \
    --revision "${revision}" \
    --local-dir "${model_dir}" \
    --fail-on-missing-files \
    --format agent
fi

printf 'revision=%s\n' "${revision}"
printf 'model_dir=%s\n' "${model_dir}"
printf 'shards=%s\n' "${shard_count}"
printf 'shard_bytes=%s\n' "${shard_bytes}"
printf 'repo_bytes=%s\n' "${repo_bytes}"
printf 'tensor_bytes=%s\n' "${tensor_bytes}"

if [[ "${DEEPSEEK_FULL_HASH:-0}" == "1" ]]; then
  (
    cd "${model_dir}"
    find . -type f ! -path './.cache/*' ! -name 'sha256sums.txt' -print0 \
      | sort -z \
      | xargs -0 sha256sum
  ) >"${manifest}"
  (
    cd "${model_dir}"
    sha256sum --check --strict --quiet "$(basename "${manifest}")"
  )
  printf 'sha256_manifest=%s\n' "${manifest}"
fi
