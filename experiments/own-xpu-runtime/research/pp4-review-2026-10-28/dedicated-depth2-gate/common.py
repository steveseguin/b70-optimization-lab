"""Run-specific finished-owner checks; no launches or device calls."""
from pathlib import Path
import hashlib,json
CONTROL=Path('/dev/shm/sc117-dedicated-reset-aba64k-20261028-r1')
CANDIDATE=Path('/dev/shm/sc117-dedicated-reset-depth2-aba64k-20261028-r1')
def need(ok,msg):
 if not ok:raise ValueError(msg)
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def stamp(p):
 s=Path(p).stat();return(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def finished(root):
 t=read(root/'output/terminal.json');need(t['passed']and t.get('error')is None and t['requests']==3 and t['live_pids']==[] and t['returncodes']=={'0':0,'1':0,'2':0,'provider':0},'actual completed three-request/four-owner terminal required')
 p=read(root/'postflight.json');need(p['known_fault_baseline_matches']and not p['holders'],'clean actual passive postflight required')
 receipts={}
 for owner in ['0','1','2','provider']:
  receipt=read(root/f'output/stage{owner}/native/receipt.json');need(receipt['passed']and not receipt.get('error'),'actual native receipt '+owner)
  contact=read(root/f'output/stage{owner}/native/device-contact.json');need(contact.get('device_contact')is True,'actual native device-contact witness '+owner)
  if owner=='provider':need(receipt['schema']=='ownrt.dedicated-provider-process.v1'and receipt['role']=='dedicated-mtp'and receipt['target_stage']is None,'actual provider native receipt schema')
  else:need(receipt['schema']=='packet32.rank.v1'and receipt.get('device_executed')is True,'actual target execution witness '+owner)
  need(receipt['teardown']and all(x['status']=='complete'and x['exit_code']==0 and x['safe_to_exit']and x['idle_marker_complete']and x['backend'].startswith('LevelZero:')and not x['in_flight']and not x['live_bytes']and not x.get('error')for x in receipt['teardown']),'clean complete native teardown '+owner)
  receipts[owner]=sha(root/f'output/stage{owner}/native/receipt.json')
 r=read(root/'output/request-02/repeated-a-proof.json');need(r['passed']and r['actual_output_ids_equal'],'actual within-depth repeated A proof')
 for i in [1,2]:
  c=read(root/f'output/request-{i:02d}/cold-proof.json');need(c['passed']and c['compared_to_startup']and(c['target_canonical_sources'],c['inactive_bank_sources'],c['provider_canonical_sources'])==(2065,27,73),'complete all-owner cold proof')
 return dict(terminal_sha256=sha(root/'output/terminal.json'),postflight_sha256=sha(root/'postflight.json'),native_receipts=receipts)
def first_a(root):return read(root/'output/request-02/repeated-a-proof.json')['initial']
