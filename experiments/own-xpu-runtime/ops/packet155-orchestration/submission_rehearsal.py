"""Offline rehearsal of final submission helper on copied REAL packet136 evidence.

Historical replay preserves every measured byte and its original scope/threshold.
It is never emitted as packet155 data. The current-record guard must refuse it.
"""
import copy,gzip,hashlib,importlib.util,json,resource,shutil,sys
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];STAGE=ROOT/'experiments/own-xpu-runtime/stage2';P=STAGE/'packet155-record-bundle9'
def main():
 assert shutil.disk_usage('/').free>=27_000_000_000
 sys.path.insert(0,str(ROOT/'scripts'))
 spec=importlib.util.spec_from_file_location('p155_final_submission',O/'submission_evidence.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 assert m.ROOT==ROOT,'repository-root regression'
 archive=STAGE/'packet136-record-bundle/submission/prepared-a/evidence.json.gz'
 copied=O/'evidence/packet136-chain-evidence.json.gz'
 if not copied.exists():shutil.copy2(archive,copied)
 assert m.sha(copied.read_bytes())==m.sha(archive.read_bytes())
 evidence=m.Evidence(json.loads(gzip.decompress(copied.read_bytes()))['members'])
 # Historical identity only: use this final helper with the matching immutable
 # bundle8 selection functions and historical constants retained in its evidence.
 old='packet136-record-bundle';m.P56_PACKET=old;m.DEFAULT_PACKET=old;m.DYNAMIC_PACKETS=(m.D_PACKET,old);m.LINEAGE[old]=None
 sys.path.insert(0,str(STAGE/old));sys.modules.pop('bundle_selection',None)
 result=m.derive(evidence,old)
 rate=result['primary_metric']['value_tok_s']
 assert abs(rate-58.798109)<.000001 and result['realistic_final_gate']['passed'] is False
 # Same guard used by final write_prepared, checked before eligible output.
 try:m.require_new_record(rate)
 except ValueError:floor_refused=True
 else:raise AssertionError('current-record replay must be refused')
 # A changed output cannot pass after merely rehashing the evidence member.
 broken=m.Evidence(copy.deepcopy(evidence.members));key='WS128/run/summary.json'
 keys=[k for k in broken.members if k.startswith('WS128/') and k.endswith('summary.json')]
 assert keys
 key=keys[0];raw=broken.read(key);requests=raw.get('requests',raw.get('rows',[]))
 assert requests
 requests[0]['passed']=False
 b=m.encoded(raw);broken.members[key].update(raw_base64=m.base64.b64encode(b).decode(),sha256=m.sha(b))
 try:m.derive(broken,old)
 except (ValueError,AssertionError):exact_refused=True
 else:raise AssertionError('modified output admitted')
 row=dict(passed=True,device_executed=False,submitted=False,rehearsal_only=True,final_helper=str((O/'submission_evidence.py').relative_to(ROOT)),final_helper_sha256=m.sha((O/'submission_evidence.py').read_bytes()),copied_evidence=str(copied.relative_to(ROOT)),copied_evidence_sha256=m.sha(copied.read_bytes()),historical_packet=old,historical_rate=rate,strict512=False,current_record_floor=58.798109,current_floor_refusal=floor_refused,tampered_output_refused=exact_refused,scope='Real packet136 bytes replayed unchanged under their historical identity. They are not packet155 measurements; production floor refuses them.')
 (O/'evidence/submission-rehearsal.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row,indent=2))
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main()
