#!/usr/bin/env bash
# Publish the qualified R308 boundary repair for Qwen3.5 4B/9B fixed-depth TP1.
# This does not change the 27B or dynamic scheduled-draft R306 profile.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
local_ref=${LOCAL_IMAGE:-rebase/r308-state-resume}
expected_id=${EXPECTED_IMAGE_ID:?set EXPECTED_IMAGE_ID to the qualified immutable R308 image ID}
[[ "${expected_id}" =~ ^sha256:[0-9a-f]{64}$ ]] || { echo "invalid immutable image ID" >&2; exit 1; }
summary=${QUALIFICATION_SUMMARY:?set QUALIFICATION_SUMMARY to the completed collector summary.json}
python3 - "${summary}" "${expected_id}" <<'PY_GATE'
import hashlib, json, pathlib, sys
summary_path=pathlib.Path(sys.argv[1]).resolve()
expected=sys.argv[2]
def require(ok, message):
    if not ok: raise SystemExit('QUALIFICATION FAIL: '+message)
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
s=json.loads(summary_path.read_text())
require(s.get('passed') is True and s.get('candidate')=='r308' and s.get('image')==expected, 'candidate/image/status mismatch')
require(s.get('scope',{}).get('tensor_parallel_size')==1 and s['scope'].get('mtp_depth')==3 and s['scope'].get('active_requests')==1 and s['scope'].get('max_num_seqs')==1, 'scope mismatch')
boundary=s.get('boundary',{})
require(set(boundary)=={f'{model}-{arm}' for model in ('4b','9b') for arm in ('oracle','mtp3-a','mtp3-b')}, 'boundary arms missing')
for key,row in boundary.items():
    require(row.get('passed') is True and row.get('actual_numeric_ids_recomputed') is True and row.get('cases')==(20 if key.endswith('-oracle') else 26) and row.get('rows',0)>=(60 if key.endswith('-oracle') else 52), 'boundary gate incomplete')
pairs={'mtp0-a-vs-mtp0-b','mtp3-a-vs-mtp3-b','mtp3-a-vs-mtp0-a','mtp3-b-vs-mtp0-a'}
for model in ('4b','9b'):
    rows=s.get('strict'+model,{})
    require(set(rows)==pairs and all(r.get('passed') is True and r.get('prompts')==12 and r.get('tokens',0)>0 for r in rows.values()), 'strict '+model+' incomplete')
r=s.get('rebuild',{})
require(r.get('recorded') is True and r.get('inventory_equal') is True and r.get('files')==17, 'rebuild gate incomplete')
packet=summary_path.parent
manifest_path=packet/'source-manifest.json'
manifest=json.loads(manifest_path.read_text())
require(isinstance(manifest,list) and bool(manifest), 'source manifest missing')
seen=set()
for item in manifest:
    rel=item.get('path',''); path=(packet/rel).resolve()
    require(rel and path.is_relative_to(packet) and rel not in seen, 'invalid/duplicate evidence path')
    seen.add(rel)
    require(path.is_file() and path.stat().st_size==item['bytes'] and digest(path)==item['sha256'], 'captured evidence hash mismatch: '+rel)
observed=r.get('source_file_hashes_receipt','')
require(observed in seen and digest(packet/observed)==r.get('observed_inventory_sha256'), 'rebuild observed receipt unbound')
inventory=pathlib.Path(s.get('inventory_path','')).resolve()
require(inventory.is_file() and digest(inventory)==r.get('committed_inventory_sha256'), 'candidate contract hash mismatch')
require(any(item['sha256']==r['committed_inventory_sha256'] and item['path'].startswith('evidence/inventory/') for item in manifest), 'candidate contract not captured')
print('QUALIFICATION PASS: r308, both models boundary and strict, rebuilt and hash-bound evidence')
PY_GATE
owner=${GHCR_OWNER:-steveseguin}
remote=ghcr.io/${owner}/vllm-openai-xpu-qwen38-int4:r308-v0290-fixed-depth-state-resume-20260913
[[ "$(docker image inspect "${local_ref}" --format '{{.Id}}')" == "${expected_id}" ]] || { echo "local image id mismatch" >&2; exit 1; }
SKIP_IMAGE_CONTRACT=0 bash "${repo_root}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-image-contract.sh" mtp1-serial-fa-split-gdn "${local_ref}"
gh auth token | docker login ghcr.io -u "${owner}" --password-stdin
docker tag "${local_ref}" "${remote}"
docker push "${remote}"
remote_repo=${remote%:*}
digest=$(docker image inspect "${remote}" --format '{{range .RepoDigests}}{{println .}}{{end}}' | awk -v prefix="${remote_repo}@sha256:" 'index($0, prefix) == 1 {print; exit}')
[[ -n "${digest}" ]] || { echo "pushed image lacks a digest for ${remote_repo}" >&2; exit 1; }
echo "pushed: ${digest}"
echo "Verify anonymous registry access and pull by this digest before recording publication."
