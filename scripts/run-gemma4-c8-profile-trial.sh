#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
profile="${1:?usage: run-gemma4-c8-profile-trial.sh PROFILE BASELINE_QUALITY_JSON}"
baseline_quality="${2:?usage: run-gemma4-c8-profile-trial.sh PROFILE BASELINE_QUALITY_JSON}"

prod_profile="${PROD_PROFILE:-gemma4-12b-it-int4-autoround-c8}"
sudo_password="${SUDO_PASSWORD-}"
if [[ -z "$sudo_password" ]]; then
  sudo_password="/'"
fi
base_url="${BASE_URL:-http://127.0.0.1:8000}"
model_dir="${MODEL_DIR:-/mnt/fast-ai/llm-models/gemma4-12b-it-int4-autoround-intel}"
results_dir="${RESULTS_DIR:-/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround}"
venv_python="${VENV_PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
run_dir="$results_dir/profile-trials/$profile-$ts"
mkdir -p "$run_dir"

restore_prod() {
  printf '%s\n' "$sudo_password" | sudo -S -p '' \
    "$repo_dir/scripts/switch-vllm-model-slot.sh" switch "$prod_profile" >/dev/null
}

wait_ready() {
  for _ in $(seq 1 240); do
    if curl -fsS "$base_url/v1/models" >"$run_dir/models.json" 2>/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

run_bench() {
  local name="$1"
  local prompt_tokens="$2"
  local output_tokens="$3"
  local concurrency="$4"
  local warmups="$5"
  "$venv_python" "$repo_dir/scripts/bench-openai-concurrency.py" \
    --base-url "$base_url" \
    --tokenizer "$model_dir" \
    --prompt-tokens "$prompt_tokens" \
    --output-tokens "$output_tokens" \
    --concurrency "$concurrency" \
    --warmups "$warmups" \
    --timeout 1800 \
    --output-json "$run_dir/$name.json" \
    >"$run_dir/$name.stdout"
}

status=failed
trap 'if [[ "$status" != "keep_active" ]]; then restore_prod || true; fi' EXIT

echo "profile=$profile"
echo "run_dir=$run_dir"

switch_started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' "$sudo_password" | sudo -S -p '' \
  "$repo_dir/scripts/switch-vllm-model-slot.sh" switch "$profile" \
  >"$run_dir/switch.log" 2>&1

if ! wait_ready; then
  journalctl -u b70-vllm-slot.service --since "$switch_started" --no-pager \
    >"$run_dir/service-startup.log" || true
  echo "startup_failed"
  exit 1
fi

journalctl -u b70-vllm-slot.service --since "$switch_started" --no-pager \
  >"$run_dir/service-startup.log" || true
curl -fsS "$base_url/status" >"$run_dir/status.json"

"$venv_python" "$repo_dir/scripts/openai-quality-canary.py" \
  --base-url "$base_url" \
  --baseline-json "$baseline_quality" \
  --output-json "$run_dir/quality.json" \
  >"$run_dir/quality.stdout"

run_bench "c8-100p-1o" 100 1 8 5
run_bench "c8-100p-128o" 100 128 8 5
run_bench "c8-32000p-1o" 32000 1 8 0

if [[ "${KEEP_TRIAL_ACTIVE:-0}" == "1" ]]; then
  status=keep_active
else
  status=completed
fi
echo "completed profile=$profile run_dir=$run_dir"
