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
#   MAX_STEPS         task-step budget [auto: v2 tasks 4 x items + 40; legacy kvstream 3 x items + 20; else 64]
#   LM_CALL_CAP       [auto: v2 tasks 3 x MAX_STEPS; else none = 2*MAX_STEPS+24]
#   OBS_MAX_CHARS     observation_max_chars [auto: max(60000, 2 x largest item) ]  (a 100-SET batch is ~16k chars)
#   THINK_CAP         improved agent only: per-turn thinking cap in tokens (two-call continue protocol,
#                     see clm_improved.py) [unset = off]
#   SHOW_WINDOW       plain agent: 1 = every tool result ends with "[context: N of M tokens used; K left]"
#                     (M = server window - MAX_TOKENS) and a `next` that cannot fit is refused [0]
#                     (WINDOW_TOKENS overrides the window read from /v1/models)
#   STABLE_RENDER     1 = with dropped thinking, send preserve_thinking=true (earlier thinking is
#                     stripped by the harness, so every earlier turn renders identically; the improved
#                     agent does this by default) [0]
#   THINKING_POLICY   improved agent: always | judgement (thinking off on routine fetch/fold calls)
#                     | never [always]
#   DROP_OLD_THINKING 1 = send chat_template_kwargs.preserve_thinking=false on every call and strip
#                     earlier turns' reasoning from the history (clm -> clm_baselines:ClmAgentT) [0]
#   TASK_TEMPLATE     task_template agent kwarg [unset = terminal_agent_tasks; open_problems = task text only]
#   SUMMARY_MAX_TOKENS SummaryAgent summary cap [unset = 4096; the call uses max(this, MAX_TOKENS)]
#   TASKS             task dir or dataset dir [<out_dir>/tasks, generated if missing]
#   PRESSURES         kvstream pressures to generate [1 2 4];  SEEDS [0]
#   N_CONCURRENT      parallel trials [1]
#   JOB_NAME          [<agent>-<timestamp>]
#   COST_METRIC       [flops] with FLOPS_MODEL_KEY [27b]  (Qwen3.6-27B geometry; approximate here)
#   SUMMARY_TRIGGER   SummaryAgent trigger fraction of the enforced limit [0.75]
#   EXTRA_KWARGS      extra "k=v k=v" agent kwargs
#   SKIP_ENDPOINT_CHECK=1 to skip the /v1/models probe
set -euo pipefail

AGENT_KIND=${1:?usage: run-context-job.sh <clm|plain|summary|improved> <out_dir> [harbor args...]}
OUT_DIR=${2:?usage: run-context-job.sh <clm|plain|summary|improved> <out_dir> [harbor args...]}
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
N_CONCURRENT=${N_CONCURRENT:-1}
COST_METRIC=${COST_METRIC:-flops}
FLOPS_MODEL_KEY=${FLOPS_MODEL_KEY:-27b}
SUMMARY_TRIGGER=${SUMMARY_TRIGGER:-0.75}
JOB_NAME=${JOB_NAME:-$AGENT_KIND-$(date +%Y%m%d-%H%M%S)}

DROP_OLD_THINKING=${DROP_OLD_THINKING:-0}
case "$AGENT_KIND" in
  clm)     AGENT=clm_harness.clm_agent.harness:ClmAgent
           [[ "$DROP_OLD_THINKING" == 1 ]] && AGENT=clm_baselines:ClmAgentT ;;
  plain)   AGENT=clm_baselines:PlainAgent ;;
  summary) AGENT=clm_baselines:SummaryAgent ;;
  improved) AGENT=clm_improved:ClmImprovedAgent ;;   # drops old thinking itself (drop_old_thinking=true default)
  *) echo "unknown agent kind $AGENT_KIND (clm|plain|summary|improved)" >&2; exit 2 ;;
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

# Step / call caps and observation size.
#  legacy kvstream tasks (first comparison): MAX_STEPS = 3 x items + 20, lm_call_cap harness default.
#  v2 tasks (metadata n_items; kvstream v2 and ledger): caps that cannot be the reason a run ends:
#    MAX_STEPS = 4 x items + 40, LM_CALL_CAP = 3 x MAX_STEPS (summary calls count as LM calls),
#    OBS_MAX_CHARS >= 2 x the largest item (no batch is ever cut by observation truncation).
#  summarize_results.py reports which limit ended each run (ended_by) and flags a cap.
read -r AUTO_STEPS AUTO_CAP AUTO_OBS < <("$PY" - "$TASKS" <<'PY'
import sys, tomllib, pathlib
p = pathlib.Path(sys.argv[1])
tomls = [p / "task.toml"] if (p / "task.toml").exists() else sorted(p.glob("*/task.toml"))
steps, cap, obs = 0, 0, 60000
for t in tomls:
    md = tomllib.loads(t.read_text()).get("metadata", {})
    if "n_items" in md:
        s = 4 * int(md["n_items"]) + 40
        steps, cap = max(steps, s), max(cap, 3 * s)
        obs = max(obs, 2 * int(md.get("max_item_chars", 30000)))
    elif "n_batches" in md:
        steps = max(steps, 3 * (int(md["n_batches"]) + 1) + 20)
print(steps or 64, cap or "none", obs)
PY
)
MAX_STEPS=${MAX_STEPS:-$AUTO_STEPS}
LM_CALL_CAP=${LM_CALL_CAP:-$AUTO_CAP}
[[ "$LM_CALL_CAP" == none ]] && LM_CALL_CAP=
OBS_MAX_CHARS=${OBS_MAX_CHARS:-$AUTO_OBS}

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
[[ "$DROP_OLD_THINKING" == 1 ]] && KW+=(--agent-kwarg "drop_old_thinking=true")
if [[ "${SHOW_WINDOW:-0}" == 1 && "$AGENT_KIND" == plain ]]; then   # arm Aw: window line + fetch guard
  WIN=${WINDOW_TOKENS:-$("$PY" - "$API_BASE" "$MODEL_NAME" <<'PY'
import json, sys, urllib.request
d = json.load(urllib.request.urlopen(sys.argv[1].rstrip("/") + "/models", timeout=10))
print({m.get("id"): m.get("max_model_len") for m in d.get("data", [])}.get(sys.argv[2]) or 0)
PY
)}
  KW+=(--agent-kwarg "show_window=true" --agent-kwarg "window_tokens=$WIN")
fi
[[ "${STABLE_RENDER:-0}" == 1 && ( "$DROP_OLD_THINKING" == 1 || "$AGENT_KIND" == improved ) ]] && KW+=(--agent-kwarg "stable_render=true")
[[ -n "${THINKING_POLICY:-}" && "$AGENT_KIND" == improved ]] && KW+=(--agent-kwarg "thinking_policy=$THINKING_POLICY")
[[ -n "${THINK_CAP:-}" && "${THINK_CAP:-0}" != 0 && "$AGENT_KIND" == improved ]] && KW+=(--agent-kwarg "think_cap=$THINK_CAP")
[[ -n "${TASK_TEMPLATE:-}" ]] && KW+=(--agent-kwarg "task_template=$TASK_TEMPLATE")
[[ -n "${SUMMARY_MAX_TOKENS:-}" && "$AGENT_KIND" == summary ]] && KW+=(--agent-kwarg "summary_max_tokens=$SUMMARY_MAX_TOKENS")
set -f; for kv in ${EXTRA_KWARGS:-}; do KW+=(--agent-kwarg "$kv"); done; set +f   # no globbing of regex values

{
  echo "agent=$AGENT_KIND ($AGENT) api_base=$API_BASE model=openai/$MODEL_NAME"
  echo "budget=$CONTEXT_BUDGET reserve=$BUDGET_RESERVE max_tokens=$MAX_TOKENS temperature=$TEMPERATURE top_p=$TOP_P thinking=$ENABLE_THINKING max_steps=$MAX_STEPS lm_call_cap=${LM_CALL_CAP:-default} obs_max_chars=$OBS_MAX_CHARS task_template=${TASK_TEMPLATE:-default} drop_old_thinking=$DROP_OLD_THINKING think_cap=${THINK_CAP:-0}"
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
