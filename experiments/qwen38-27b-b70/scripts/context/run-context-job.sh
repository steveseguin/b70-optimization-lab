#!/usr/bin/env bash
# Common runner: one Harbor job of one agent over a task or dataset directory.
# Called by run-contextbench-clm.sh / run-contextbench-baseline.sh / smoke.sh; can be used directly:
#
#   run-context-job.sh <clm|plain|summary> <out_dir> [extra harbor args...]
#
# Environment (defaults in brackets):
#   API_BASE          OpenAI-compatible endpoint [http://127.0.0.1:8000/v1]
#   MODEL_NAME        served model name [qwen38-27b-fp8]  (litellm gets openai/$MODEL_NAME)
#   CONTEXT_BUDGET    context_budget_tokens [28672]  (the paper's BrowseComp-Plus setting for a
#                     32768-token window: budget + MAX_TOKENS must fit the server window)
#   BUDGET_RESERVE    context_budget_reserve_tokens [2048]  (enforced limit = budget - reserve)
#   MAX_TOKENS        max output tokens per call [4096]
#   TEMPERATURE       [0]      TOP_P [none]   (greedy; "none" omits the field)
#   ENABLE_THINKING   chat_template_kwargs.enable_thinking [true]; SEND_CTK=false omits the field
#   MAX_STEPS         task-step budget [auto: 3 x items + 20 for kvstream tasks, else 64]
#   LM_CALL_CAP       [none = 2*MAX_STEPS+24]
#   OBS_MAX_CHARS     observation_max_chars [60000]  (a 100-SET batch is ~16k chars)
#   TASKS             task dir or dataset dir [<out_dir>/tasks, generated if missing]
#   PRESSURES         kvstream pressures to generate [1 2 4];  SEEDS [0]
#   N_CONCURRENT      parallel trials [1]
#   JOB_NAME          [<agent>-<timestamp>]
#   COST_METRIC       [flops] with FLOPS_MODEL_KEY [27b]  (Qwen3.6-27B geometry; approximate here)
#   SUMMARY_TRIGGER   SummaryAgent trigger fraction of the enforced limit [0.75]
#   EXTRA_KWARGS      extra "k=v k=v" agent kwargs
#   SKIP_ENDPOINT_CHECK=1 to skip the /v1/models probe
set -euo pipefail

AGENT_KIND=${1:?usage: run-context-job.sh <clm|plain|summary> <out_dir> [harbor args...]}
OUT_DIR=${2:?usage: run-context-job.sh <clm|plain|summary> <out_dir> [harbor args...]}
shift 2

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
VENV=${VENV:-/mnt/fast-ai/venvs/clm}
PY="$VENV/bin/python"
HARBOR="$VENV/bin/harbor"

API_BASE=${API_BASE:-http://127.0.0.1:8000/v1}
MODEL_NAME=${MODEL_NAME:-qwen38-27b-fp8}
CONTEXT_BUDGET=${CONTEXT_BUDGET:-28672}
BUDGET_RESERVE=${BUDGET_RESERVE:-2048}
MAX_TOKENS=${MAX_TOKENS:-4096}
TEMPERATURE=${TEMPERATURE:-0}
TOP_P=${TOP_P:-none}
ENABLE_THINKING=${ENABLE_THINKING:-true}
SEND_CTK=${SEND_CTK:-true}
OBS_MAX_CHARS=${OBS_MAX_CHARS:-60000}
N_CONCURRENT=${N_CONCURRENT:-1}
COST_METRIC=${COST_METRIC:-flops}
FLOPS_MODEL_KEY=${FLOPS_MODEL_KEY:-27b}
SUMMARY_TRIGGER=${SUMMARY_TRIGGER:-0.75}
JOB_NAME=${JOB_NAME:-$AGENT_KIND-$(date +%Y%m%d-%H%M%S)}

case "$AGENT_KIND" in
  clm)     AGENT=clm_harness.clm_agent.harness:ClmAgent ;;
  plain)   AGENT=clm_baselines:PlainAgent ;;
  summary) AGENT=clm_baselines:SummaryAgent ;;
  *) echo "unknown agent kind $AGENT_KIND (clm|plain|summary)" >&2; exit 2 ;;
esac

mkdir -p "$OUT_DIR"
OUT_DIR=$(cd "$OUT_DIR" && pwd)
TASKS=${TASKS:-$OUT_DIR/tasks}
if [[ ! -e "$TASKS" ]]; then
  # shellcheck disable=SC2086
  "$PY" "$HERE/make_kvstream_tasks.py" "$TASKS" --pressure ${PRESSURES:-1 2 4} --seeds ${SEEDS:-0}
fi

# Offline-friendly: cached tiktoken vocab, no litellm price-map download, dummy key.
export TIKTOKEN_CACHE_DIR=${TIKTOKEN_CACHE_DIR:-/mnt/fast-ai/cache/tiktoken}
export LITELLM_LOCAL_MODEL_COST_MAP=True
export OPENAI_API_KEY=${OPENAI_API_KEY:-EMPTY}
export PYTHONPATH="$HERE${PYTHONPATH:+:$PYTHONPATH}"

if [[ "${SKIP_ENDPOINT_CHECK:-0}" != 1 ]]; then
  "$PY" - "$API_BASE" "$MODEL_NAME" "$CONTEXT_BUDGET" "$MAX_TOKENS" <<'PY'
import json, sys, urllib.request
base, name, budget, mx = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
try:
    d = json.load(urllib.request.urlopen(base.rstrip("/") + "/models", timeout=10))
except Exception as e:
    sys.exit(f"endpoint check failed: {base}/models: {e}")
models = {m.get("id"): m for m in d.get("data", [])}
if name not in models:
    sys.exit(f"model {name!r} not served at {base}; served: {sorted(models)}")
win = models[name].get("max_model_len")
print(f"endpoint ok: {name} max_model_len={win}")
if win and budget + mx > int(win):
    sys.exit(f"CONTEXT_BUDGET+MAX_TOKENS={budget + mx} exceeds the server window {win}; "
             "lower one of them or start the server with a larger --max-model-len")
PY
fi

# Step budget: kvstream tasks need ~1 step per item plus compaction/answer turns.
if [[ -z "${MAX_STEPS:-}" ]]; then
  MAX_STEPS=$("$PY" - "$TASKS" <<'PY'
import sys, tomllib, pathlib
p = pathlib.Path(sys.argv[1])
tomls = [p / "task.toml"] if (p / "task.toml").exists() else sorted(p.glob("*/task.toml"))
best = 0
for t in tomls:
    md = tomllib.loads(t.read_text()).get("metadata", {})
    if "n_batches" in md:
        best = max(best, 3 * (int(md["n_batches"]) + 1) + 20)
print(best or 64)
PY
)
fi

KW=(
  --agent-kwarg "api_base=$API_BASE"
  --agent-kwarg "context_budget_tokens=$CONTEXT_BUDGET"
  --agent-kwarg "context_budget_reserve_tokens=$BUDGET_RESERVE"
  --agent-kwarg "max_tokens=$MAX_TOKENS"
  --agent-kwarg "temperature=$TEMPERATURE"
  --agent-kwarg "top_p=$TOP_P"
  --agent-kwarg "enable_thinking=$ENABLE_THINKING"
  --agent-kwarg "send_chat_template_kwargs=$SEND_CTK"
  --agent-kwarg "max_steps=$MAX_STEPS"
  --agent-kwarg "observation_max_chars=$OBS_MAX_CHARS"
  --agent-kwarg "cost_metric=$COST_METRIC"
)
[[ "$COST_METRIC" == flops ]] && KW+=(--agent-kwarg "flops_model_key=$FLOPS_MODEL_KEY")
[[ -n "${LM_CALL_CAP:-}" ]] && KW+=(--agent-kwarg "lm_call_cap=$LM_CALL_CAP")
[[ "$AGENT_KIND" == summary ]] && KW+=(--agent-kwarg "summary_trigger_ratio=$SUMMARY_TRIGGER")
for kv in ${EXTRA_KWARGS:-}; do KW+=(--agent-kwarg "$kv"); done

{
  echo "agent=$AGENT_KIND ($AGENT) api_base=$API_BASE model=openai/$MODEL_NAME"
  echo "budget=$CONTEXT_BUDGET reserve=$BUDGET_RESERVE max_tokens=$MAX_TOKENS temperature=$TEMPERATURE top_p=$TOP_P thinking=$ENABLE_THINKING max_steps=$MAX_STEPS"
  echo "tasks=$TASKS job=$OUT_DIR/jobs/$JOB_NAME"
  echo "clm_commit=$(git -C /mnt/fast-ai/src/context-language-models rev-parse HEAD 2>/dev/null)"
} | tee "$OUT_DIR/$JOB_NAME.settings.txt"

set +e
"$HARBOR" run \
  -p "$TASKS" \
  -e docker \
  -a "$AGENT" \
  -m "openai/$MODEL_NAME" \
  "${KW[@]}" \
  --jobs-dir "$OUT_DIR/jobs" \
  --job-name "$JOB_NAME" \
  -n "$N_CONCURRENT" \
  -y \
  "$@" 2>&1 | tee "$OUT_DIR/$JOB_NAME.log"
rc=${PIPESTATUS[0]}
set -e
"$PY" "$HERE/summarize_results.py" "$OUT_DIR/jobs/$JOB_NAME" | tee "$OUT_DIR/$JOB_NAME.summary.txt" || true
exit "$rc"
