"""ROOT RELEASE ONLY: restore four receipt-selected first-A control members once.
No archive I/O occurs on import. No control/archive modification or raw deletion.
"""
import argparse,hashlib,json,os,shutil,subprocess,tarfile,threading
from pathlib import Path
from common import CONTROL,CANDIDATE,need,read,sha,stamp,finished,first_a

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--control-root',type=Path,default=CONTROL);parser.add_argument('--candidate-root',type=Path,default=CANDIDATE);parser.add_argument('--destination',type=Path,required=True);a=parser.parse_args()
 # Deliberately no polling: active/incomplete candidate refuses before archive I/O.
 checks={str(root):finished(root)for root in [a.control_root,a.candidate_root]}
 receipt_path=a.control_root/'state-archive.json';receipt=read(receipt_path)
 need(receipt['full_tar_bytes_compared']and receipt['actual_payload_sha256_matches_all_seals']and receipt['removal_completed'],'completed verified control archive authority')
 states=first_a(a.control_root);selected={}
 for owner,s in states.items():
  matches=[m for m in receipt['members']if m['role']=='first-A:owner'+owner]
  need(len(matches)==1 and matches[0]['path']==str(Path(s['path'])/'state.bundle'),'exact first-A receipt role/path')
  selected[matches[0]['member']]=(owner,matches[0],Path(s['path']))
 need(len(selected)==4,'exact four first-A members')
 archive=Path(receipt['archive']);before=stamp(archive);need(before[2]==receipt['archive_bytes'],'archive extent')
 need(not a.destination.exists(),'fresh exclusive restore output');a.destination.mkdir(mode=0o700)
 for owner,m,source in selected.values():
  dest=a.destination/owner;dest.mkdir()
  for name,expected in [('state-index.tsv',m['index_sha256']),('state.json',m['state_json_sha256'])]:
   old=stamp(source/name);need(sha(source/name)==expected,'control metadata seal '+name);shutil.copyfile(source/name,dest/name);need(stamp(source/name)==old and sha(dest/name)==expected,'stable control metadata copy')
  seal=source/'state-seal.txt';old=stamp(seal);shutil.copyfile(seal,dest/'state-seal.txt');need(stamp(seal)==old,'stable control seal')
  fields=(dest/'state-seal.txt').read_text().splitlines();need(fields==['GSQ_STATE_SEAL_V1',str(m['bytes']),m['sha256'],m['index_sha256'],m['state_json_sha256']],'exact archive member seal')
 proc=subprocess.Popen(['zstd','-dc'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
 feed={'error':None,'sha256':None}
 def feeder():
  try:
   h=hashlib.sha256()
   with archive.open('rb')as source:
    for b in iter(lambda:source.read(1024*1024),b''):h.update(b);proc.stdin.write(b)
   proc.stdin.close();feed['sha256']=h.hexdigest()
  except Exception as e:
   feed['error']=repr(e)
   try:proc.stdin.close()
   except Exception:pass
 thread=threading.Thread(target=feeder);thread.start();restored=[]
 try:
  with tarfile.open(fileobj=proc.stdout,mode='r|')as tar:
   for expected in receipt['members']:
    member=tar.next();need(member and member.isfile()and member.name==expected['member']and member.size==expected['bytes'],'exact complete archive member inventory')
    if member.name not in selected:continue
    owner,row,source=selected[member.name];target=a.destination/owner/'state.bundle';h=hashlib.sha256();count=0
    with target.open('xb')as dest:
     data=tar.extractfile(member)
     for b in iter(lambda:data.read(1024*1024),b''):dest.write(b);h.update(b);count+=len(b)
     dest.flush();os.fsync(dest.fileno())
    need(count==row['bytes']and h.hexdigest()==row['sha256'],'restored exact first-A payload seal')
    restored.append(dict(owner=owner,member=member.name,path=str(target),bytes=count,sha256=h.hexdigest()))
   need(tar.next()is None,'no unregistered archive members')
 finally:
  proc.stdout.close();thread.join();rc=proc.wait()
 need(rc==0 and not feed['error']and feed['sha256']==receipt['archive_sha256']and stamp(archive)==before,'compressed archive digest/stable identity')
 need(len(restored)==4,'all four first-A controls restored')
 result=dict(schema='ownrt.depth-control-first-A-restoration.v1',passed=True,archive=str(archive),archive_receipt=str(receipt_path),archive_receipt_sha256=sha(receipt_path),compressed_archive_sha256=feed['sha256'],members=restored,finished_checks=checks,scope='One compressed archive read; four full payloads restored/sealed. Other members skipped without repeat raw checks; original archive full-byte verification receipt remains authority. No deletions or weakened source scope.')
 (a.destination/'restoration.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
