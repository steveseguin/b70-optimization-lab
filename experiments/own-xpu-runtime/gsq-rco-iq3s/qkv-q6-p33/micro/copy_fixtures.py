#!/usr/bin/env python3
"""Explicit76,800-byte closed-profile copy only; never model payloads."""
from pathlib import Path
import argparse,hashlib,json,os,stat
P=Path(__file__).resolve().parent;Q=P.parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def identity(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def main():
 a=argparse.ArgumentParser();a.add_argument('--copy-after-drain',action='store_true',required=True);a.parse_args()
 plan=json.loads((Q/'selection.json').read_text())
 for p,h in plan['source_sha256'].items():assert sha(p)==h,p
 dest=P/'fixtures';assert not dest.exists(),'one fixed copy only';dest.mkdir();rows=[]
 for case in plan['micro_cases']:
  for role,row in case['fixtures'].items():
   source=Path(row['source']);assert source.resolve()==source
   fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW)
   with os.fdopen(fd,'rb') as f:
    st=os.fstat(f.fileno());assert stat.S_ISREG(st.st_mode) and st.st_size==row['bytes']
    data=f.read(row['bytes']+1);assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
    assert identity(st)==identity(os.fstat(f.fileno()))==identity(source.stat())
   out=dest/f"layer-{case['site']['layer']}-{role}.bin"
   with out.open('xb') as f:f.write(data)
   rows.append(dict(source=str(source),source_identity=identity(st),path=str(out),bytes=len(data),sha256=row['sha256']))
 assert len(rows)==6 and sum(x['bytes'] for x in rows)==76800
 receipt=dict(passed=True,scope='Six closed audited profile payloads; hashes equal original baseline index',selection_sha256=sha(Q/'selection.json'),files=rows,bytes=76800,model_payload_read=False,device_executed=False)
 (Q/'evidence/fixture-copy.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'passed':True,'bytes':76800,'receipt_sha256':sha(Q/'evidence/fixture-copy.json')}))
if __name__=='__main__':main()
