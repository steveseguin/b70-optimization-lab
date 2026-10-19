"""CPU-only byte copies; no model, device, service or existing-packet writes."""
import hashlib,json,os,resource,shutil
from pathlib import Path
P=Path(__file__).resolve().parent; ROOT=P.parents[3]; STAGE=P.parent
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
assert os.getpriority(os.PRIO_PROCESS,0)==19
assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
def sha(f):
 with Path(f).open('rb') as s:return hashlib.file_digest(s,'sha256').hexdigest()
def save(f,r):f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(r,indent=2)+'\n')
def cp(src,dst):
 assert shutil.disk_usage(P).free-src.stat().st_size>=27_000_000_000,'CPU stop: 27 GB'
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
 return dict(source=str(src.relative_to(ROOT)),sha256=sha(dst),bytes=dst.stat().st_size)
manifest=json.loads((STAGE/'packet49-integrate/oracle/results/suite-manifest.json').read_text())
for name,parent_name in [('two-card','packet136-record-bundle'),('one-card','packet58aj-onecard-resident')]:
 p=P/name;parent=STAGE/parent_name;p.mkdir(exist_ok=True);copies={}
 def copy(src,rel):copies[rel]=cp(src,p/rel)
 two=name=='two-card'
 chain=parent/('build/device-cards01-a/WS128' if two else 'evidence/card0-58aj-a/WS128')
 copy(parent/'build/device/own-rt-iq3','build/device/own-rt-iq3')
 for f in parent.iterdir():
  if f.is_file() and f.suffix in ('.cpp','.hpp','.h','.inc','.py','.json','.tsv'):
   copy(f,'lineage-source/'+f.name)
 if not two:
  for f in (parent/'native').rglob('*'):
   if f.is_file() and not f.is_symlink() and f.suffix in ('.cpp','.hpp','.h','.inc'):
    copy(f,'lineage-source/native/'+str(f.relative_to(parent/'native')))
  copy(parent/'build/preparation/prepare-probe','build/preparation/prepare-probe')
  copy(parent/'evidence/packet58ajb-preparation.json','lineage-source/preparation-receipt.json')
  native=json.loads((chain/'run/receipt.json').read_text())['command'][2:]
 else:
  native=json.loads((chain/'run/ranks/rank0-launch.json').read_text())['argv']
  for n in ['pipeline.py','suite.py','suite_metrics.py','memory_gate.py']:
   copy(parent/n,n)
  copy(parent/'memory-plan.json','memory-plan.json')
  # Source implementation + native args match the record, including banked rollback.
  copy(parent/'chain_pipeline.py','lineage-source/record-chain-pipeline.py')
 for flag,rel in [('--selection','selection.json'),('--dispatch','dispatch.json')]:
  copy(Path(native[native.index(flag)+1]),rel)
 copy(chain/'run/summary.json','evidence/parent-summary.json')
 copy(chain/'window.json','evidence/parent-window.json')
 for e in manifest['prompts']:
  src=chain/'run'/('repeat-1' if two else 'run')/e['prompt_id']/('receipt.json' if two else 'result.json')
  copy(src,'evidence/parent-requests/'+e['prompt_id']+'.json')
  oracle=STAGE/'packet49-integrate/oracle/results'/e['prompt_id']
  copy(oracle/'result.json','oracle128/'+e['prompt_id']+'.json')
  # Input metadata only: never GGUF, safetensors, layer fixtures or weights.
  bundle=ROOT/e['input_bundle']
  for leaf in ('tokens.txt','input.json'):
   copy(bundle/leaf,'inputs/'+e['prompt_id']+'/'+leaf)
 for leaf in ('plan.tsv','identity.tsv'):
  copy(ROOT/manifest['prompts'][0]['input_bundle']/leaf,'inputs/'+leaf)
 for leaf in ('suite-manifest.json','completion.json'):
  copy(STAGE/'packet49-integrate/oracle/results'/leaf,'oracle128/'+leaf)
 for n in ['chain_devices.py','lane_admission.py','drain_gate.py','exec_limits.py','composition.py','supervision.py','p56_head_support.py']:
  source=(STAGE/'packet136-record-bundle' if n in ('chain_devices.py','lane_admission.py','drain_gate.py') else STAGE/'packet58aj-onecard-resident')/n
  copy(source,n)
 copy(ROOT/'experiments/own-xpu-runtime/ops/launch_env.py','launch_env.py')
 copy(STAGE/'packet58aj-onecard-resident/suite_metrics.py','suite_metrics.py')
 copy(STAGE/'packet49-integrate/oracle/suite_check.py','oracle_check.py')
 copy(STAGE/'packet58aj-onecard-resident/oracle-binding.json','oracle-binding.json')
 # Snapshot oracle verifier source, but keep canonical packet49 authority paths.
 src=(STAGE/'packet58aj-onecard-resident/suite_driver.py').read_text()
 start=src.index('def oracle_inputs():');end=src.index('\ndef compare_request',start)
 oracle_header='''import hashlib,importlib.util,json\nfrom pathlib import Path\nHERE=Path(__file__).resolve().parent\nROOT=next(p for p in HERE.parents if (p/'.git').is_dir())\nORACLE=ROOT/'experiments/own-xpu-runtime/stage2/packet49-integrate/oracle'\nARITHMETIC='iq3-p49-split32-v1'\nSUITE_SHA='0ad543d1c1f379a0b6cee88e06236e495c45eee7ba12cfcef062b6e03303e812'\ndef require(ok,message):\n if not ok:raise ValueError(message)\ndef read(p):return json.loads(Path(p).read_text())\ndef sha(p):\n with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()\nspec=importlib.util.spec_from_file_location('packet163_oracle_checker',HERE/'oracle_check.py')\nCHECK=importlib.util.module_from_spec(spec);spec.loader.exec_module(CHECK)\n'''
 (p/'oracle.py').write_text(oracle_header+src[start:end]+'\n')
 # Copy the safety driver source solely for extracting fault signatures.
 copy(ROOT/'experiments/own-xpu-runtime/stage1/packet4-prep/driver/window_driver.py','lineage-source/window_driver.py')
 fault=(STAGE/'packet153-snapshot-host/v5/fault_review.py').read_text().replace("DRIVER = HERE.parent / 'lineage-inputs/vendor/repo/experiments/own-xpu-runtime/stage1/packet4-prep/driver/window_driver.py'","DRIVER = HERE / 'lineage-source/window_driver.py'")
 (p/'fault_review.py').write_text(fault)
 save(p/'parent-native-argv.json',native)
 save(p/'copy-manifest.json',dict(schema='packet163.vendored-record.v1',parent=parent_name,parent_head=__import__('subprocess').check_output(['git','rev-parse','HEAD'],text=True).strip(),files=copies))
 save(p/'identity.json',dict(parent=parent_name,gpu_count=2 if two else 1,arithmetic='iq3-p49-split32-v1',binary_sha256=sha(p/'build/device/own-rt-iq3'),selection_sha256=sha(p/'selection.json'),dispatch_sha256=sha(p/'dispatch.json'),context=4096,kv_dtype='BF16',parent_rate=58.798109 if two else 31.966820,oracle_cap=128,requested_max_new=512,attempts=2,model_loads_per_attempt=1))
 print(name,'copied',len(copies),'files',sum(r['bytes'] for r in copies.values()),flush=True)
