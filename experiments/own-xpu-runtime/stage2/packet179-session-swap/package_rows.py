"""Create proposal, never edit/submit a live queue. READY is a separate last step."""
import hashlib,json,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];OPS=ROOT/'experiments/own-xpu-runtime/ops/lane-queue'
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
for name,lanes in [('one-card','A')]:
 p=P/name
 # Exclude generated receipts and recovery copies. Seal all runtime source,
 # constants, configurations and build executables actually used by the entry,
 # including the patched entry TU and checkpoint.hpp. The 'build' exclusion
 # covers only the packet's own build artifacts; the native-source mirror's
 # 'build/native' sources and frozen 'build/checked' headers are sealed inputs.
 files={str(f.relative_to(p)):sha(f)for f in p.rglob('*')if f.is_file()and not any(x in f.relative_to(p).parts for x in ['evidence','__pycache__'])and f.name not in ['seal.json','READY.json','READY-FOR-DEVICE.json']and (('build'not in f.relative_to(p).parts or 'native-source'in f.relative_to(p).parts)or f==p/'build/device/own-rt-iq3')}
 save(p/'seal.json',dict(arithmetic='iq3-p49-split32-v1',files=files))
 b=json.loads((p/'budget.json').read_text())
 for lane in lanes:
  rows=[]
  reference_output=p/'evidence'/f'device-p179-full512-{lane}-a'
  checkpoint_output=p/'evidence'/f'device-p179-checkpoint-{lane}-b'
  for row_name,kind,output,reference in [
      (f'packet179-{name}-full512-{lane}-a','full512',reference_output,None),
      (f'packet179-{name}-checkpoint-{lane}-b','checkpoint',checkpoint_output,reference_output)]:
   argv=['/usr/bin/python3','-B',str((p/'entry.py').relative_to(ROOT)),'--lane',lane,'--kind',kind,'--output',str(output),'--fault-review','{REVIEW}','--authorized-device-window']
   if reference is not None:argv+=['--reference',str(reference)]
   rows.append(dict(name=row_name,lane=lane,argv=argv,env_extra={},review=str((p/'fault_review.py').relative_to(ROOT)),planned_write_bytes=b['planned_write_bytes'],plan=dict(host_required_available_bytes=b['host_required_available_bytes'],expected_seconds=b['expected_seconds'],watchdog_seconds=7200,entry_rehearsal=dict(binaries=[dict(path=str((p/'build/device/own-rt-iq3').relative_to(ROOT)),sha256=sha(p/'build/device/own-rt-iq3'),args=['--help'],returncode=0,contains='Options:')],preparation_probe_note='Private CPU backend probes of actual device entry, exact launch env, Landlock denial of model/device reads; evidence/preparation-probe.json. Generic shared probe schema cannot admit private4MB rotary constant. Kernel objects relinked byte-identical from packet165; entry-TU checkpoint delta rebuilt.'))))
  proposal=OPS/f'proposed-p179-{name}-{lane}.txt'
  proposal.write_text('# Proposal only; never queued. Row A: two fresh loads discipline inherited as one full512 reference run (incident-retrospective once, reset, prefill512, remaining11 once). Row B: experimental checkpoint gate; three fresh loads of the same binary -- save K=256 on incident-retrospective, two independent restore M=128 continuations; merged K+M stream must equal row A at [0:384).\n'+'\n'.join(json.dumps(r)for r in rows)+'\n')
  rehearsal=P/'evidence'/f'queue-plan-{name}-{lane}';rehearsal.mkdir(exist_ok=True);(rehearsal/f'queue-{lane}.txt').write_text(proposal.read_text())
print('one proposal file and private plan queue written; READY not written')
