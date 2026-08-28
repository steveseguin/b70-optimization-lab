#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
supervisor="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/supervise-tp4-mtp0-current-piecewise-graph-a1.sh"
state=/tmp/q38-mtp0-current-piecewise-graph-a1
stop_file="${state}.stop"
failure_file="${state}.failed"
run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt1
server_log="${run_dir}/server.log"
base_url=http://127.0.0.1:19674
model=qwen38-flash-next-fp8-tp4
tokenizer=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
python=/home/steve/.venvs/vllm-xpu/bin/python
quality="${repo}/scripts/qwen38-text-quality-suite.py"
short_harness="${repo}/scripts/bench-openai-concurrency.py"
eager_oracle=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt4/quality-current.json
completed=0

write_atomic() {
  local path=$1 value=$2 tmp="${1}.tmp.$$"
  printf '%s\n' "$value" >"$tmp"
  mv "$tmp" "$path"
}
fail_sentinel() {
  local rc=$?
  (( completed == 1 )) || write_atomic "$failure_file" "FAIL current PIECEWISE MTP0 client rc=${rc}"
}
trap fail_sentinel EXIT

[[ $# == 0 ]] || { printf 'FAIL: client takes no arguments\n' >&2; exit 2; }
[[ -d "$run_dir" ]] || { printf 'FAIL: run directory is absent\n' >&2; exit 1; }
printf '%s  %s\n' 8e18afee22a0fda4b44583ca55e3a43aef5f86fe8387a1bd28c533d1534bd3de "$quality" | sha256sum -c -
printf '%s  %s\n' d590c63c87b1e664417b4198dbbb873cbe4f252509fa8f9fc50830efca2b4cf4 "$short_harness" | sha256sum -c -
printf '%s  %s\n' c0c76ab19bb93963fd2817930b0ce4a3edfd73861bdab75377ad03f6a5be5c83 "$eager_oracle" | sha256sum -c -
for artifact in health-before-client.json models-before-client.json metrics-before-client.prom \
  journal-before-client.log recovery-canary.json quality-short.json quality-short.log quality-short.rc \
  graph-replay-96x2.json graph-replay.log graph-replay.rc graph-evidence.txt \
  compile-cache-manifest.sha256 \
  bench-short-r1.json bench-short-r1.log bench-short-r1.rc \
  bench-short-r2.json bench-short-r2.log bench-short-r2.rc \
  bench-short-r3.json bench-short-r3.log bench-short-r3.rc \
  piecewise-graph-summary.json client-gates-passed.txt; do
  [[ ! -e "${run_dir}/${artifact}" ]] || { printf 'FAIL: refusing to overwrite %s\n' "$artifact" >&2; exit 1; }
done

compile_dir=/tmp/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt1-compile

supervisor_pid=$(cat "${state}.pid" 2>/dev/null || true)
[[ "$supervisor_pid" =~ ^[1-9][0-9]*$ && -e "/proc/${supervisor_pid}" ]] || { printf 'FAIL: supervisor absent\n' >&2; exit 1; }
supervisor_command=$(tr '\0' ' ' <"/proc/${supervisor_pid}/cmdline")
[[ "$supervisor_command" == *"${supervisor}"* ]] || { printf 'FAIL: supervisor identity mismatch\n' >&2; exit 1; }
deadline_epoch=$(cat "${state}.deadline-epoch" 2>/dev/null || true)
[[ "$deadline_epoch" =~ ^[1-9][0-9]*$ ]] || { printf 'FAIL: supervisor deadline absent\n' >&2; exit 1; }
(( deadline_epoch - $(date +%s) >= 3900 )) || { printf 'FAIL: less than 3900 seconds remain\n' >&2; exit 1; }
server_pid=$(cat "${run_dir}/server.pid" 2>/dev/null || true)
[[ "$server_pid" =~ ^[1-9][0-9]*$ && -e "/proc/${server_pid}" ]] || { printf 'FAIL: owned server absent\n' >&2; exit 1; }
server_command=$(tr '\0' ' ' <"/proc/${server_pid}/cmdline")
[[ "$server_command" == *"vllm serve /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"* && \
   "$server_command" == *"--port 19674"* && "$server_command" == *"--max-model-len 4352"* && \
   "$server_command" == *"--cudagraph-metrics"* && "$server_command" == *"--compilation-config"* && \
   "$server_command" != *"--enforce-eager"* && "$server_command" != *"--speculative-config"* && \
   "$server_command" != *"--reasoning-parser"* ]] || { printf 'FAIL: server command identity mismatch\n' >&2; exit 1; }
for receipt in \
  'vllm_head=1372c62d975c554f4b465c8299bc5f3295301ceb' \
  'kernels_head=ad25aa9f69a2171612b9c6b83dfa82c69559f9e4' \
  'runtime_stage_build_head=2f829747503c77d4814834dffd0840fb1dd9f75a' \
  'tp=4 ep=4 all2all=allgather_reducescatter' \
  'moe_backend=triton eager=0 graph=PIECEWISE mtp=0 max_model_len=4352 max_num_batched_tokens=64' \
  'graph_enable_env=VLLM_XPU_ENABLE_XPU_GRAPH=1' \
  'compilation_config={"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1}' \
  'cudagraph_metrics=1' 'kv_cache_memory_bytes=201326592' 'kv_cache_layout=BLHNC' \
  'reasoning_parser=absent' 'diagnostics=none'; do
  grep -Fxq "$receipt" "${run_dir}/identity.txt" || { printf 'FAIL: identity receipt missing: %s\n' "$receipt" >&2; exit 1; }
done
grep -aFq "enforce_eager=False" "$server_log"
grep -aFq "'cudagraph_mode': <CUDAGraphMode.PIECEWISE: 1>" "$server_log"
grep -aFq "'cudagraph_capture_sizes': [1]" "$server_log"
grep -aFq "cudagraph_metrics=True" "$server_log"
grep -aFq 'Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)' "$server_log"

curl --connect-timeout 5 --max-time 20 -fsS "${base_url}/health" >"${run_dir}/health-before-client.json"
curl --connect-timeout 5 --max-time 20 -fsS "${base_url}/v1/models" >"${run_dir}/models-before-client.json"
curl --connect-timeout 5 --max-time 20 -fsS "${base_url}/metrics" >"${run_dir}/metrics-before-client.prom"
jq -e --arg model "$model" '.data | any(.id == $model and .max_model_len == 4352)' "${run_dir}/models-before-client.json" >/dev/null
"$python" - "${run_dir}/metrics-before-client.prom" <<'PY'
import pathlib, re, sys
line = next((x for x in pathlib.Path(sys.argv[1]).read_text().splitlines() if x.startswith('vllm:cache_config_info{')), None)
assert line is not None
labels = dict(re.findall(r'(\w+)="([^"]*)"', line))
assert labels.get('kv_cache_memory_bytes') == '201326592', labels
assert labels.get('enable_prefix_caching') == 'False', labels
assert int(labels.get('kv_cache_size_tokens', '0')) >= 4224, labels
PY
journal_start=$(cat /mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt1-supervisor/journal-start-epoch.txt)
journalctl -k --since "@${journal_start}" --no-pager >"${run_dir}/journal-before-client.log"
! grep -Eqi 'xe 0000:(23|27|43|47):00\.0.*(reset|fault|timeout|timed out|fatal|wedged|failed)' "${run_dir}/journal-before-client.log"

"$python" - "$base_url" "$model" "${run_dir}/recovery-canary.json" <<'PY'
import hashlib, json, pathlib, sys, urllib.request
base_url, model, output = sys.argv[1:]
payload = {'model': model, 'messages': [{'role':'user','content':'Reply with exactly: OK'}],
           'chat_template_kwargs': {'enable_thinking': False}, 'temperature': 0,
           'top_p': 1.0, 'seed': 20260609, 'max_tokens': 8, 'stream': False}
req = urllib.request.Request(base_url + '/v1/chat/completions', data=json.dumps(payload).encode(),
    headers={'Content-Type':'application/json','X-Request-Id':'q38-piecewise-a1-recovery'}, method='POST')
with urllib.request.urlopen(req, timeout=180) as response:
    assert response.status == 200
    result = json.load(response)
content = result['choices'][0]['message']['content'].strip(); usage = result['usage']; details = usage['prompt_tokens_details']
assert content == 'OK' and hashlib.sha256(content.encode()).hexdigest() == '565339bc4d33d72817b583024112eb7f5cdf3e5eef0252d6ec1b9c9a94e12bb3'
assert result['choices'][0]['finish_reason'] == 'stop'
assert (usage['prompt_tokens'], usage['completion_tokens'], usage['total_tokens']) == (17,2,19)
assert details.get('cached_tokens') == 0 and details.get('created_cache_tokens') == 0
pathlib.Path(output).write_text(json.dumps({'status':'passed','response':result}, indent=2) + '\n')
PY

set +e
timeout --signal=TERM --kill-after=10s 600s "$python" "$quality" --base-url "$base_url" \
  --model "$model" --tokenizer "$tokenizer" --timeout 300 --seed 20260609 --repeat-runs 1 \
  --skip-long-context --baseline-json "$eager_oracle" --require-baseline \
  --chat-template-kwargs-json '{"enable_thinking":false}' --request-id-prefix q38-piecewise-a1-quality \
  --output-json "${run_dir}/quality-short.json" >"${run_dir}/quality-short.log" 2>&1
quality_rc=$?
set -e
write_atomic "${run_dir}/quality-short.rc" "$quality_rc"
[[ "$quality_rc" == 1 ]] || { printf 'FAIL: expected frozen sole semantic miss rc=1, got %s\n' "$quality_rc" >&2; exit 1; }
jq -e '.baseline_status == "passed" and .baseline_match_all == true and
  ([.exact_cases[]|select(.pass==true)]|length)==6 and
  ([.exact_cases[]|select(.pass==false)]|length)==1 and
  ([.exact_cases[]|select(.pass==false)][0]|.name=="code_execution" and .normalized=="30") and
  .repeat_case.pass==true and .repeat_case.unique_hashes==["3b0b3192cd70de9c19caf7a6f6f69a4dda63cc4e66049c2cf9c15633103896b7"] and
  ([.exact_cases[].usage,.repeat_case.runs[].usage]|all(.prompt_tokens_details.cached_tokens==0 and .prompt_tokens_details.created_cache_tokens==0))' \
  "${run_dir}/quality-short.json" >/dev/null

set +e
timeout --signal=TERM --kill-after=10s 1800s "$python" - "$base_url" "$model" "${run_dir}/graph-replay-96x2.json" \
  >"${run_dir}/graph-replay.log" 2>&1 <<'PY'
import hashlib, json, os, pathlib, re, sys, time, urllib.request
base_url, model, output = sys.argv[1:]
cases = [
 {'name':'color','prompt':'Sort exactly these four color words alphabetically and reply with only the comma-separated lowercase list: yellow, red, green, blue','max_tokens':16,'expected':'blue, green, red, yellow','sha':'3b0b3192cd70de9c19caf7a6f6f69a4dda63cc4e66049c2cf9c15633103896b7','usage':(37,8,45)},
 {'name':'json','prompt':'Return only compact JSON with keys answer and unit. Question: 12 plus 30. Unit: widgets.','max_tokens':64,'expected':'{"answer": 42, "unit": "widgets"}','sha':'250a25b051da4e7e82761d80134aea4bd17bac1d4644cda1c5df3be93d4e3a91','usage':(36,14,50)},
]
records=[]
for index in range(96):
  for case in cases:
    payload={'model':model,'messages':[{'role':'user','content':case['prompt']}], 'max_tokens':case['max_tokens'],
      'temperature':0,'top_p':1.0,'seed':20260609,'chat_template_kwargs':{'enable_thinking':False},'stream':False}
    request_id=f'q38-piecewise-a1-{case["name"]}-{index:03d}'
    req=urllib.request.Request(base_url+'/v1/chat/completions',data=json.dumps(payload).encode(),
      headers={'Content-Type':'application/json','X-Request-Id':request_id},method='POST')
    started=time.perf_counter()
    with urllib.request.urlopen(req,timeout=180) as response:
      assert response.status==200
      result=json.load(response)
    text=re.sub(r'\s+',' ',result['choices'][0]['message']['content'].strip())
    usage=result['usage']; details=usage['prompt_tokens_details']
    assert result['model']==model and result['choices'][0]['finish_reason']=='stop'
    assert text==case['expected'] and hashlib.sha256(text.encode()).hexdigest()==case['sha']
    assert (usage['prompt_tokens'],usage['completion_tokens'],usage['total_tokens'])==case['usage']
    assert details.get('cached_tokens')==0 and details.get('created_cache_tokens')==0
    records.append({'request_id':request_id,'case':case['name'],'index':index,'normalized':text,'sha256':case['sha'],'usage':usage,'elapsed_s':time.perf_counter()-started})
summary={'schema':'qwen38-piecewise-replay-gate-v1','status':'passed','protocol':'alternating color/json; 96 exact calls per family',
 'counts':{name:sum(r['case']==name for r in records) for name in ('color','json')},'records':records}
dest=pathlib.Path(output); tmp=dest.with_name(dest.name+f'.tmp.{os.getpid()}'); tmp.write_text(json.dumps(summary,indent=2)+'\n'); os.replace(tmp,dest)
PY
replay_rc=$?
set -e
write_atomic "${run_dir}/graph-replay.rc" "$replay_rc"
(( replay_rc == 0 )) || exit "$replay_rc"
jq -e '.status=="passed" and .counts=={"color":96,"json":96} and (.records|length)==192' "${run_dir}/graph-replay-96x2.json" >/dev/null
grep -aE "CUDAGraph Config Settings|Mode: CUDAGraphMode.PIECEWISE|CUDAGraph Stats|CUDAGraphMode.PIECEWISE|Capturing CUDA graphs \(mixed prefill-decode, PIECEWISE\)" \
  "$server_log" >"${run_dir}/graph-evidence.txt"
grep -aFq 'Mode: CUDAGraphMode.PIECEWISE' "${run_dir}/graph-evidence.txt"
grep -aFq '| CUDAGraphMode.PIECEWISE' "${run_dir}/graph-evidence.txt"

for row in 1 2 3; do
  warmups=0; [[ "$row" == 1 ]] && warmups=1
  set +e
  timeout 360s "$python" "$short_harness" --base-url "$base_url" --tokenizer "$tokenizer" \
    --prompt-tokens 128 --output-tokens 256 --concurrency 1 --warmups "$warmups" --timeout 300 \
    --seed 20260828 --output-json "${run_dir}/bench-short-r${row}.json" \
    >"${run_dir}/bench-short-r${row}.log" 2>&1
  rc=$?
  set -e
  write_atomic "${run_dir}/bench-short-r${row}.rc" "$rc"
  (( rc == 0 )) || exit "$rc"
done

(cd "$compile_dir" && find . -type f -print0 | sort -z | xargs -0 -r sha256sum) \
  >"${run_dir}/compile-cache-manifest.sha256"
[[ -s "${run_dir}/compile-cache-manifest.sha256" ]] || { printf 'FAIL: graph compile-cache manifest is empty\n' >&2; exit 1; }

"$python" - "$run_dir" <<'PY'
import hashlib,json,os,pathlib,statistics,sys
root=pathlib.Path(sys.argv[1]); replay=json.loads((root/'graph-replay-96x2.json').read_text())
short=[json.loads((root/f'bench-short-r{i}.json').read_text()) for i in range(1,4)]
records=[x['scenarios']['c1']['records'][0] for x in short]
for r in records:
 assert (r['prompt_tokens'],r['completion_tokens'],r['total_tokens'])==(146,256,402)
 assert r['sha256']=='5f40744644b98ddd58a0c202fe855af324c0b1c33e1a6275afd74c12488f89f0'
summary={'schema':'qwen38-current-piecewise-graph-anchor-v1','status':'passed','recovery_canary':'passed','identity':{
 'model_revision':'bcd9f01ddc9cff2316eb84281bebcd5b058bddce','vllm_head':'1372c62d975c554f4b465c8299bc5f3295301ceb',
 'kernel_head':'ad25aa9f69a2171612b9c6b83dfa82c69559f9e4','stage_build_head':'2f829747503c77d4814834dffd0840fb1dd9f75a',
 'tp':4,'ep':4,'mtp':0,'graph':'PIECEWISE','capture_sizes':[1],'max_model_len':4352,'kv_cache_memory_bytes':201326592},
 'quality':{'semantic':'6/7; sole frozen miss code_execution=30','eager_a4_exact_comparator':'passed','color_replay':'96/96 exact','json_replay':'96/96 exact','runtime_piecewise_evidence':'passed'},
 'graph_evidence':{'compile_cache_manifest':'retained by relative-path SHA-256 before bounded scratch cleanup'},
 'short':{'protocol':'a4 p146/o256/c1: conditioned row1 then two zero-warmup rows','rates_tok_s_after_ttft':[r['tok_s_out_after_ttft'] for r in records],
 'median_tok_s_after_ttft':statistics.median(r['tok_s_out_after_ttft'] for r in records),'output_sha256':records[0]['sha256']},
 'authority':'bounded current-runtime TP4 PIECEWISE MTP0 short classification only','protected_results_changed':False,
 'interpretation':'Additive graph classification; never replaces or lowers eager a4 or any retained speed.'}
for name in ['recovery-canary.json','quality-short.json','graph-replay-96x2.json','graph-evidence.txt','compile-cache-manifest.sha256','bench-short-r1.json','bench-short-r2.json','bench-short-r3.json']:
 summary.setdefault('sha256',{})[name]=hashlib.sha256((root/name).read_bytes()).hexdigest()
dest=root/'piecewise-graph-summary.json'; tmp=dest.with_name(dest.name+f'.tmp.{os.getpid()}'); tmp.write_text(json.dumps(summary,indent=2)+'\n'); os.replace(tmp,dest)
PY
write_atomic "${run_dir}/client-gates-passed.txt" 'PASS recovery eager-parity color96 json96 PIECEWISE-evidence short3'
write_atomic "$stop_file" 'STOP after passed current PIECEWISE MTP0 graph anchor'
completed=1
