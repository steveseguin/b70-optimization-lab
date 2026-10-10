#!/usr/bin/env bash
# Run one profiling pass: start a server command as a transient user unit, wait for the endpoint, profile it with
# tools/profile-openai-endpoint.py, then stop the unit. Never leaves a server running.
#
# usage: tools/profile-run.sh --label <id> --model <api model id> [--port 19350] [--users 4] [--canary]
#                             [--load-seconds 40] [--skip-8k] [--no-cache-field] [--env K=V ...] [--ready-timeout 900]
#                             -- <server command and args>
# Output: data/profiles/<date>/<label>.json (+ .canary.json) and <label>.server.log
set -uo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
label=""; model=""; port=19350; users=4; canary=""; load=40; skip8k=""; nocache=""; ready_timeout=900; envs=(); repeat_only=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --label) label=$2; shift 2 ;;
    --model) model=$2; shift 2 ;;
    --port) port=$2; shift 2 ;;
    --users) users=$2; shift 2 ;;
    --canary) canary=--canary; shift ;;
    --load-seconds) load=$2; shift 2 ;;
    --skip-8k) skip8k=--skip-8k; shift ;;
    --repeat-only) repeat_only=--repeat-only; shift ;;
    --no-cache-field) nocache=--no-cache-field; shift ;;
    --ready-timeout) ready_timeout=$2; shift 2 ;;
    --env) envs+=(--setenv="$2"); shift 2 ;;
    --) shift; break ;;
    *) echo "unknown arg $1" >&2; exit 2 ;;
  esac
done
[[ -n $label && -n $model && $# -gt 0 ]] || { echo "need --label, --model and a server command after --" >&2; exit 2; }
day=$(date -u +%Y-%m-%d); out_dir="$repo_dir/data/profiles/$day"; mkdir -p "$out_dir"
unit="profile-${label//[^A-Za-z0-9_-]/-}"
log="$out_dir/$label.server.log"
systemctl --user stop "$unit" 2>/dev/null || true
systemd-run --user --unit="$unit" --collect -p KillMode=mixed -p KillSignal=SIGINT -p TimeoutStopSec=120 \
  --setenv=PROFILE_LABEL="$label" "${envs[@]}" \
  bash -c "exec \"\$@\" > \"$log\" 2>&1" _ "$@" || { echo "[profile] could not start unit" >&2; exit 1; }
t0=$(date +%s)
echo "[profile] $label: unit $unit started, waiting for http://127.0.0.1:$port ..."
while :; do
  if curl -fsS -m 3 "http://127.0.0.1:$port/v1/models" >/dev/null 2>&1; then
    # llama.cpp answers /v1/models while still loading; require a real completion
    if curl -fsS -m 60 -H 'Content-Type: application/json' -d "{\"model\":\"$model\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":1}" "http://127.0.0.1:$port/v1/chat/completions" >/dev/null 2>&1; then
      echo "[profile] ready after $(( $(date +%s) - t0 )) s"; break
    fi
  fi
  if ! systemctl --user is-active --quiet "$unit"; then echo "[profile] server unit died; tail of log:"; tail -n 25 "$log" | cut -c1-200; exit 1; fi
  if (( $(date +%s) - t0 > ready_timeout )); then echo "[profile] timed out waiting for the server"; systemctl --user stop "$unit"; exit 1; fi
  sleep 5
done
mem0=$(timeout 15 xpu-smi stats -d 0 2>/dev/null | grep 'GPU Memory Used' | grep -o 'avg: *[0-9]*' | grep -o '[0-9]*')
python3 "$repo_dir/tools/profile-openai-endpoint.py" --base "http://127.0.0.1:$port" --model "$model" --label "$label" \
  --users "$users" --load-seconds "$load" $canary $skip8k $nocache $repeat_only --out "$out_dir/$label.json"
rc=$?
python3 - "$out_dir/$label.json" "$mem0" "$log" <<'EOF'
import json, sys
p, mem, log = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    d = json.load(open(p)); d["card_memory_used_mib_after_load"] = int(mem) if mem else None; d["server_log"] = log
    json.dump(d, open(p, "w"), indent=1)
except Exception as e:
    print("[profile] could not annotate result:", e)
EOF
systemctl --user stop "$unit" 2>/dev/null || true
echo "[profile] $label done rc=$rc -> $out_dir/$label.json"
exit $rc
