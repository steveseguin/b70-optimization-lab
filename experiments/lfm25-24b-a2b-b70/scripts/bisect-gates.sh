#!/usr/bin/env bash
# Add one of the lab's SYCL switches at a time to the reference arm r0 and run the realistic suite once per arm.
# Output: $OUT/bisect/<name>/suite-a.json, compared against $OUT/r0/suite-a.json at the end.
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
E=$LAB/experiments/lfm25-24b-a2b-b70/scripts
OUT=${OUT:-/mnt/fast-ai/bench-results/lfm25-24b-a2b}
cd "$LAB"
suite() {
  python3 scripts/bench-openai-realistic-suite.py --base-url http://127.0.0.1:18110 --model lfm25-24b-a2b --api-mode native \
    --suite repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json --max-tokens 512 --metric-tokens 100 --seed 42 \
    --timeout 900 --return-token-ids --request-extra-json '{"cache_prompt":false,"seed":42,"temperature":0,"top_p":1}' \
    --out "$1" >/dev/null 2>&1 || echo "suite rc=$? for $1"
}
ARMS=${ARMS:-"opt:GGML_SYCL_DISABLE_OPT=0
graph:GGML_SYCL_DISABLE_GRAPH=0
vmm_icl:GGML_SYCL_ENABLE_VMM=1,UR_L0_USE_IMMEDIATE_COMMANDLISTS=1
mmid_fast:LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1
q8reorder:GGML_SYCL_DISABLE_OPT=0,LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1
q8reorder_vdr2:GGML_SYCL_DISABLE_OPT=0,LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1,LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_DIRECT_VDR2=1
route_cache:LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1
f16_small:LLAMA_SYCL_F16_P021_SMALL_NCOLS=1"}
names=()
while IFS= read -r line; do
  [[ -z $line ]] && continue
  name=${line%%:*}; envs=${line#*:}
  mkdir -p "$OUT/bisect/$name"
  echo "### $(date +%T) $name: $envs"
  ARM_ENV="${envs//,/ }" "$E/serve-lfm25.sh" r0 "bisect-$name" || { echo "server failed for $name"; continue; }
  suite "$OUT/bisect/$name/suite-a.json"
  names+=("$OUT/bisect/$name/suite-a.json")
done <<< "$ARMS"
systemctl --user stop lfm25-srv
echo "### $(date +%T) done"
python3 "$E/compare_arrays.py" "$OUT/r0/suite-a.json" "${names[@]}"
