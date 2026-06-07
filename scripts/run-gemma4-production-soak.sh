#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
venv="${VENV:-/home/steve/.venvs/vllm-xpu}"
base_url="${BASE_URL:-http://127.0.0.1:8000}"
model_dir="${MODEL_DIR:-/mnt/fast-ai/llm-models/gemma4-12b-it-int4-autoround-intel}"
results_root="${RESULTS_ROOT:-/mnt/fast-ai/bench-results/gemma4-12b-it-int4-autoround}"
duration_s="${DURATION_S:-28800}"
interval_s="${INTERVAL_S:-900}"
prompt_tokens="${PROMPT_TOKENS:-100}"
output_tokens="${OUTPUT_TOKENS:-512}"
concurrency="${CONCURRENCY:-8}"

baseline_quality="${BASELINE_QUALITY_JSON:-}"
if [[ -z "$baseline_quality" ]]; then
  baseline_quality="$(ls -1t "$results_root"/prod-c8-quality-baseline-*.json | head -1)"
fi

ts="$(date -u +%Y%m%dT%H%M%SZ)"
run_dir="$results_root/prod-c8-soak-${ts}"
mkdir -p "$run_dir"

summary="$run_dir/summary.tsv"
printf 'cycle\tutc\tquality_expected\tquality_baseline\tprompt_tokens\toutput_tokens\tmean_ttft_s\twall_tok_s\tstatus\n' > "$summary"

started_epoch="$(date +%s)"
deadline_epoch=$((started_epoch + duration_s))
cycle=0

while (( "$(date +%s)" < deadline_epoch )); do
  cycle=$((cycle + 1))
  cycle_ts="$(date -u +%Y%m%dT%H%M%SZ)"
  cycle_dir="$run_dir/cycle-${cycle}-${cycle_ts}"
  mkdir -p "$cycle_dir"
  status="ok"

  curl -fsS "$base_url/status" > "$cycle_dir/status.json" || status="status_failed"
  curl -fsS "$base_url/v1/models" > "$cycle_dir/models.json" || status="models_failed"

  if [[ "$status" == "ok" ]]; then
    if ! "$venv/bin/python" "$repo_dir/scripts/openai-quality-canary.py" \
      --base-url "$base_url" \
      --baseline-json "$baseline_quality" \
      --output-json "$cycle_dir/quality.json" \
      > "$cycle_dir/quality.stdout" 2> "$cycle_dir/quality.stderr"; then
      status="quality_failed"
    fi
  fi

  if [[ "$status" == "ok" ]]; then
    if ! "$venv/bin/python" "$repo_dir/scripts/bench-openai-concurrency.py" \
      --base-url "$base_url" \
      --tokenizer "$model_dir" \
      --prompt-tokens "$prompt_tokens" \
      --output-tokens "$output_tokens" \
      --concurrency "$concurrency" \
      --warmups 0 \
      --timeout 1800 \
      --output-json "$cycle_dir/decode.json" \
      > "$cycle_dir/decode.stdout" 2> "$cycle_dir/decode.stderr"; then
      status="decode_failed"
    fi
  fi

  "$venv/bin/python" - "$cycle_dir" "$summary" "$cycle" "$cycle_ts" "$status" <<'PY'
import json
import pathlib
import sys

cycle_dir = pathlib.Path(sys.argv[1])
summary = pathlib.Path(sys.argv[2])
cycle = sys.argv[3]
cycle_ts = sys.argv[4]
status = sys.argv[5]

quality_expected = ""
quality_baseline = ""
prompt_tokens = ""
output_tokens = ""
mean_ttft_s = ""
wall_tok_s = ""

quality_path = cycle_dir / "quality.json"
if quality_path.exists():
    quality = json.loads(quality_path.read_text())
    quality_expected = str(quality.get("expected_pass_all", ""))
    quality_baseline = str(quality.get("baseline_match_all", ""))

decode_path = cycle_dir / "decode.json"
if decode_path.exists():
    decode = json.loads(decode_path.read_text())
    scenario = next(iter(decode["scenarios"].values()))
    record = scenario["records"][0]
    summary_data = scenario["summary"]
    prompt_tokens = str(record["prompt_tokens"])
    output_tokens = str(record["completion_tokens"])
    mean_ttft_s = str(summary_data["per_request_ttft_s"]["mean"])
    wall_tok_s = str(summary_data["aggregate_output_tok_s_wall"])

with summary.open("a") as fh:
    fh.write(
        "\t".join(
            [
                cycle,
                cycle_ts,
                quality_expected,
                quality_baseline,
                prompt_tokens,
                output_tokens,
                mean_ttft_s,
                wall_tok_s,
                status,
            ]
        )
        + "\n"
    )
print(summary.read_text().splitlines()[-1], flush=True)
PY

  now_epoch="$(date +%s)"
  next_epoch=$((started_epoch + cycle * interval_s))
  if (( next_epoch > now_epoch && next_epoch < deadline_epoch )); then
    sleep $((next_epoch - now_epoch))
  fi
done

echo "$run_dir"
