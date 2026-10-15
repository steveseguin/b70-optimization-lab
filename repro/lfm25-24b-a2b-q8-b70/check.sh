#!/usr/bin/env bash
# Check a running serve.sh server: the lab's 12-prompt suite (six kinds of writing, 512 tokens each, greedy, no
# prompt cache), then a token-by-token comparison.
#
#   repro/lfm25-24b-a2b-q8-b70/check.sh run NAME       writes $RESULTS_DIR/NAME.json (default ./lfm25-check/)
#                                                      and compares it with the lab's reference run
#   repro/lfm25-24b-a2b-q8-b70/check.sh compare A.json B.json [more ...]
#
# The proof that the fast path changes nothing on your machine: start serve.sh reference, `check.sh run ref`, stop
# it, start serve.sh fast, `check.sh run fast`, then `check.sh compare lfm25-check/ref.json lfm25-check/fast.json`.
# Every prompt should say identical. Takes about 2 minutes (fast) or 3 (reference); PORT defaults to 18110.
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
lab_reference=${repo_root}/experiments/lfm25-24b-a2b-b70/data/r0-suite-a.json
compare=${repo_root}/experiments/lfm25-24b-a2b-b70/scripts/compare_arrays.py

case ${1:-} in
  run)
    name=${2:?name for this run, e.g. fast}
    dir=${RESULTS_DIR:-lfm25-check}
    mkdir -p "${dir}"
    python3 "${repo_root}/scripts/bench-openai-realistic-suite.py" --base-url "http://127.0.0.1:${PORT:-18110}" \
      --model "${ALIAS:-lfm25-24b-a2b}" --api-mode native \
      --suite "${repo_root}/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json" \
      --max-tokens 512 --metric-tokens 100 --seed 42 --timeout 900 --return-token-ids \
      --request-extra-json '{"cache_prompt":false,"seed":42,"temperature":0,"top_p":1}' --out "${dir}/${name}.json" >/dev/null
    python3 - "${dir}/${name}.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
gate = d["realistic_final_gate"]
speed = d["summary"]["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"]
print(f"{sys.argv[1]}: {gate['completed_prompt_count']}/12 prompts, {speed:.1f} tok/s (median of the six kinds' medians), "
      f"suite checks {'passed' if gate['passed'] else 'FAILED: ' + ', '.join(gate['promotion_failures'])}")
EOF
    echo "Against the lab's reference run (same tokens expected with the same card and oneAPI 2026.1; another"
    echo "compiler or driver version may legitimately differ, so compare your own reference and fast runs too):"
    python3 "${compare}" "${lab_reference}" "${dir}/${name}.json" || true
    ;;
  compare)
    shift
    [[ $# -ge 2 ]] || { echo 'compare needs at least two result files' >&2; exit 2; }
    python3 "${compare}" "$@"
    ;;
  *)
    sed -n '2,11p' "$0"; exit 2 ;;
esac
