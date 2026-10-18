"""Minimal report/import-only reseal; retain original receipts and native hashes."""
import gzip,json
from pathlib import Path
from p145_v5_build_engine import P,LOCAL,ROOT,sha,save
from cpu_seal import GATES

def main():
 archive=LOCAL/'lineage-inputs/pre-142c.json.gz';old=json.loads(gzip.decompress(archive.read_bytes()))
 renamed={n:'p145_v5_'+n for n in ('build_engine','chain_devices','compare','drain_gate','exec_limits','full_shape','lane_admission','placement','queue_plan')}
 changes=[]
 for gate in GATES:
  file=P/'evidence'/(gate+'.json');row=json.loads(old[str(file.relative_to(LOCAL))]);sources={}
  for name,digest in row.get('sources',{}).items():
   path=ROOT/name;new=path
   if path.parent==P and path.stem in renamed:new=path.with_name(renamed[path.stem]+'.py')
   if sha(new)!=digest or new!=path:
    assert path.is_relative_to(LOCAL) and (path.suffix=='.py' or (path.parent==P/'evidence' and path.stem in GATES)),'non-Python input changed: '+name
    import hashlib
    assert hashlib.sha256(old[str(path.relative_to(LOCAL))].encode()).hexdigest()==digest,'original source mismatch: '+name
    changes.append(dict(gate=gate,old=name,new=str(new.relative_to(ROOT)),old_sha256=digest,new_sha256=sha(new)))
   sources[str(new.relative_to(ROOT))]=sha(new)
  row['sources']=sources
  row['report142c_reseal']=dict(original_receipt_archive=str(archive.relative_to(ROOT)),archive_sha256=sha(archive),gate_rerun=False,native_and_numerical_inputs_unchanged=True,reason='unique v5 Python imports and report dispatch only')
  save(file,row)
 save(P/'evidence/reseal142c.json',dict(passed=True,device_executed=False,compiler_executed=False,changes=changes,original_archive_sha256=sha(archive),native_changes=0))
 print('Minimal historical CPU receipt reseal PASS',len(changes))
if __name__=='__main__':main()
