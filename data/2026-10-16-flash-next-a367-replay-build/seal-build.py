"""CPU build helper; never called by execute. Rebuild approval after any reseal."""
from pathlib import Path
import hashlib, json, sys
p=Path('experiments/own-xpu-runtime/stage1/packet4-prep'); new=p/'a367-replay'
f=json.loads((p/'a367-calibrate/seal.json').read_text())['files']
f[str(p/'a367-calibrate/seal.json')]=hashlib.sha256((p/'a367-calibrate/seal.json').read_bytes()).hexdigest()
repro=Path('repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913')
files=list(new.glob('*.py'))+list(new.glob('*.md'))+[new/'preregistration.json']
files += [repro/n for n in ('identity.json','frozen-a367-packet.sha256','README.md','check-replay-result.py','wait-and-run-client.sh')]
for line in (repro/'frozen-a367-packet.sha256').read_text().splitlines():
    files.append(Path('experiments/qwen38-flash-next-fp8-b70/tools') / line.split(maxsplit=1)[1])
files += [Path('experiments/qwen38-flash-next-fp8-b70/tools/launch-tp4-ep4-eager-mtp0-long-context-base.sh'),Path('scripts/bench-openai-realistic-suite.py'),Path('repro/rapid-model-snapshots-b70/realistic-suite-v1.json')]
ident=json.loads((repro/'identity.json').read_text())['record']
files += [Path(ident[k]) for k in ('performance_evidence','attestation')]
for path in files:
    f[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
(new/'seal.json').write_text(json.dumps({'schema':'own-xpu-runtime.packet4.a367-replay-seal.v1','files':dict(sorted(f.items()))},indent=2)+'\n')
sys.path.insert(0,str(new))
import a367_replay as c
(new/'owner-approval.pending.json').write_text(json.dumps({'status':'PENDING OWNER APPROVAL; CPU build only; no launch authorized','replay_memory_exception':{'approved':False,'approved_by':'owner','minimum_mem_available_kib':114840824,'owner_approval_text':c.replay_approval_text()}},indent=2)+'\n')
