#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
base_url="${BASE_URL:-http://127.0.0.1:18088}"
tokenizer="${TOKENIZER_DIR:-}"
python="${PYTHON:-python3}"
out="${OUT:-${PWD}/qwen38-q8-tp1-quality.json}"
[[ -n "${tokenizer}" ]] || { printf 'Set TOKENIZER_DIR to the pinned Qwen3.8 tokenizer directory.\n' >&2; exit 2; }
[[ "$(sha256sum "${tokenizer}/tokenizer.json" | awk '{print $1}')" == 06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523 ]] || { printf 'tokenizer.json identity mismatch\n' >&2; exit 1; }
[[ "$(sha256sum "${tokenizer}/tokenizer_config.json" | awk '{print $1}')" == 792fa3f0cb88b111e54ef3134c873531008c4df471d108da17903426e308aa7b ]] || { printf 'tokenizer_config.json identity mismatch\n' >&2; exit 1; }
[[ "$(sha256sum "${tokenizer}/config.json" | awk '{print $1}')" == 9a1c29a807e34529bec03cba92b4dc00ba61e37a703b029b08a3142b6dc08cd1 ]] || { printf 'config.json identity mismatch\n' >&2; exit 1; }
curl -fsS "${base_url}/health" >/dev/null
TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 "${python}" -B "${repo_root}/scripts/qwen38-text-quality-suite.py" \
  --base-url "${base_url}" --model qwen38-q8-tp1-b70 --tokenizer "${tokenizer}" \
  --repeat-runs 8 --long-context-tokens 8192 --timeout 900 --output-json "${out}"
"${python}" -B - "${out}" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
rows=d['exact_cases']+d['repeat_case']['runs']+[d['long_context_case']]
cached=[(r.get('usage') or {}).get('prompt_tokens_details',{}).get('cached_tokens') for r in rows]
assert d['pass_all'] and len(rows)==16 and cached==[0]*16
print('service_quality_passed=true cached_tokens_all_zero=true responses=16')
PY
