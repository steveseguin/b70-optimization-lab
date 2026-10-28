"""Reuse an exactly equal archived five-bundle state; archive only new host maps."""
import argparse,importlib.util,json,hashlib,shutil,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('lookup_long',HERE/'compare_long.py');M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
def run(root,reference,proof_path,archive):
 proof=M.read(proof_path);M.need(proof['passed']and proof['candidate']==str(root),'actual completed exact proof')
 reg=M.read(HERE/'long-pair-registration.json');M.need(str(root)in reg['roots'] and str(reference)==reg['prior_qualified_3plus1'],'registered roots')
 old=M.L.roles(reference,M.read(reference/'output/plan.json'));new=M.L.roles(root,M.read(root/'output/plan.json'));ar=M.read(reference/'archive.json');oldarchive=Path(ar['archive'])
 M.need(ar['full_tar_compare_passed']and ar['deleted_only_compared_completed_files']and oldarchive.is_file()and oldarchive.stat().st_size==ar['archive_bytes'],'retained verified original archive')
 M.need(not archive.exists()and not(root/'archive-reuse.json').exists()and shutil.disk_usage(archive.parent).free>51*1024**3,'fresh archive and reserve')
 records=[]
 for role,dump in new.items():
  a,b=M.C.sealed(old[role],False),M.C.sealed(dump,False);entry=proof['states'][role];payload=dump/'state.bundle';member=str((old[role]/'state.bundle').relative_to(reference))
  M.need(member in ar['exact_paths']and a['entries']==b['entries']and a['state']==b['state']and a['bundle_sha256']==b['bundle_sha256']==entry['candidate_bundle_sha256']and entry['exact_complete_payload_and_metadata']and payload.stat().st_size==b['bytes'],'exact fully streamed archived counterpart')
  records.append(dict(candidate=str(payload.relative_to(root)),baseline_archive_member=member,bytes=b['bytes'],sha256=b['bundle_sha256']))
 maps=[root/'output'/f'stage{i}'/'prefill.bin'for i in range(3)];stamps={str(p):M.C.identity(p.stat())for p in maps};lst=root/'maps-files.txt';lst.write_bytes(b''.join(str(p.relative_to(root)).encode()+b'\0'for p in maps))
 with archive.open('xb')as f:subprocess.run(['tar','--use-compress-program=zstd -T1 -3','-cf','-','-C',str(root),'--null','-T',str(lst)],stdout=f,check=True)
 h=hashlib.sha256()
 with archive.open('rb')as f:
  while b:=f.read(1024**2):h.update(b)
 subprocess.run(['tar','--use-compress-program=zstd -d','-df',str(archive),'-C',str(root)],check=True)
 M.need(all(M.C.identity(p.stat())==stamps[str(p)]for p in maps),'host maps unchanged')
 record=dict(schema='ownrt.exact-state-archive-reuse.v1',quality_proof=str(proof_path),quality_proof_sha256=M.sha(proof_path.read_bytes()),baseline_archive=ar['archive'],baseline_archive_sha256=ar['sha256'],baseline_archive_previously_fully_verified=True,fully_streamed_candidate_payloads=records,host_maps_archive=str(archive),host_maps_archive_sha256=h.hexdigest(),host_maps_fully_tar_compared=True,host_maps=[str(p.relative_to(root))for p in maps],deleted_only_proven_files=False)
 receipt=root/'archive-reuse.json';receipt.write_text(json.dumps(record,indent=2)+'\n')
 for row in records:(root/row['candidate']).unlink()
 for p in maps:p.unlink()
 record['deleted_only_proven_files']=True;receipt.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(dict(released_state_bytes=sum(x['bytes']for x in records),host_maps_archive=str(archive))))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('reference',type=Path);p.add_argument('proof',type=Path);p.add_argument('archive',type=Path);a=p.parse_args();run(a.root,a.reference,a.proof,a.archive)
