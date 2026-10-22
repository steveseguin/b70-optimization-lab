"""Create the proposal, never edit/submit a live queue. READY is a separate last step.

Order: CPU gates -> package_rows.py (seal + proposal) -> validate_flags.py -> check_queue_rows.py
(plan + rehearse, refuses a stale seal or an existing READY) -> final_checks.py ->
final_checks.py --ready (writes READY last and re-runs the real pin guard on the full closure).
Admission settings are packet179's rows exactly (whole-host lane A, fault review, 98.99 GB host
memory, 25 GB device floor, 7200 s screen watchdog); only planned_write_bytes (400 MB, row b
writes three checkpoints) and the per-row informational expected_seconds differ.
"""
import hashlib,json,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];OPS=ROOT/'experiments/own-xpu-runtime/ops/lane-queue'
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
for name,lanes in [('one-card','A')]:
 p=P/name
 assert not any((d/'READY-FOR-DEVICE.json').exists() for d in (P,p)),'withdraw READY before resealing; final_checks --ready rewrites it last'
 # Seal all runtime source, constants, configurations and build executables actually used by
 # the entry, including the patched entry TU, checkpoint.hpp, tokenizer identity, lifecycle
 # spec and the packet179 reference copies. 'build' excludes only the packet's own build
 # artifacts; the native-source mirror's build/native sources are sealed inputs.
 files={str(f.relative_to(p)):sha(f)for f in p.rglob('*')if f.is_file()and not any(x in f.relative_to(p).parts for x in ['evidence','__pycache__'])and f.name not in ['seal.json','READY.json','READY-FOR-DEVICE.json']and (('build'not in f.relative_to(p).parts or 'native-source'in f.relative_to(p).parts)or f==p/'build/device/own-rt-iq3')}
 save(p/'seal.json',dict(arithmetic='iq3-p49-split32-v1',files=files))
 b=json.loads((p/'budget.json').read_text())
 for lane in lanes:
  rows=[]
  for row_name,kind,output in [
      (f'packet180-{name}-full512-{lane}-a','full512',p/'evidence'/f'device-p180-full512-{lane}-a'),
      (f'packet180-{name}-lifecycle-{lane}-b','lifecycle',p/'evidence'/f'device-p180-lifecycle-{lane}-b')]:
   argv=['/usr/bin/python3','-B',str((p/'entry.py').relative_to(ROOT)),'--lane',lane,'--kind',kind,'--output',str(output),'--fault-review','{REVIEW}','--authorized-device-window']
   rows.append(dict(name=row_name,lane=lane,argv=argv,env_extra={},review=str((p/'fault_review.py').relative_to(ROOT)),planned_write_bytes=b['planned_write_bytes'],
    plan=dict(host_required_available_bytes=b['host_required_available_bytes'],expected_seconds=b['expected_seconds_by_kind'][kind],watchdog_seconds=7200,
     entry_rehearsal=dict(binaries=[dict(path=str((p/'build/device/own-rt-iq3').relative_to(ROOT)),sha256=sha(p/'build/device/own-rt-iq3'),args=['--help'],returncode=0,contains='Options:')],
      preparation_probe_note='Private CPU backend probes of actual device entry, exact launch env, Landlock denial of model/device reads; evidence/preparation-probe.json. Generic shared probe schema cannot admit private4MB rotary constant. Kernel objects relinked byte-identical from packet165; entry-TU checkpoint v2 delta rebuilt.'))))
  proposal=OPS/f'proposed-p180-{name}-{lane}.txt'
  proposal.write_text('# Proposal only; never queued. Row A (~8-15 min; packet179 row a took 499 s): one fresh load, full512 suite (incident-retrospective once, reset, prefill512, remaining 11 once); every output must equal packet179 row a. '
   'Row B (~19-40 min; five model loads of ~210 s each): experimental checkpoint lifecycle -- save S1 at K=256 on incident-retrospective; restore S1 + append the 126-token turn T + decode 128 + save S2; resume S2 + decode 64; one-shot fresh reference of P+gen+T decoding 192; repeat append into S2b. '
   'Gates: append == reference[0:128], resume of S2 == reference[128:192], repeat identical, S2b blobs == S2 blobs, save == packet179 row a [0:256]; a divergence FAILS with the first index and both streams.\n'
   +'\n'.join(json.dumps(r)for r in rows)+'\n')
  rehearsal=P/'evidence'/f'queue-plan-{name}-{lane}';rehearsal.mkdir(parents=True,exist_ok=True);(rehearsal/f'queue-{lane}.txt').write_text(proposal.read_text())
print('seal, one proposal file and private plan queue written; READY not written')
