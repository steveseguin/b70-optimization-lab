from pathlib import Path
import json,hashlib
R=Path('/dev/shm/sc117-reference-route-pp4-gate-20261028-r1');profile=Path('/dev/shm/sc117-gate-cut16-20261028-r1');proofpath=profile/'comparison/proof.json';assert json.loads(proofpath.read_text())['passed']is True
restorepath=profile/'serial-reference-restore.json';restore=json.loads(restorepath.read_text());assert restore['selected_payloads_sha_verified']is True and len(restore['restored'])==5
archive=json.loads((R/'archive.json').read_text());assert archive['full_tar_bytes_compared']and archive['actual_payload_sha256_matches_all_seals']and archive['archive_sha256']==restore['archive_sha256']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1024**2),b''):h.update(b)
 return h.hexdigest()
def stamp(p):
 s=p.stat();return[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
rows=[]
for row in restore['restored']:
 p=Path(row['path']);identity=stamp(p);assert p.is_relative_to(R/'output')and p.name=='state.bundle'and not p.is_symlink()and 'request-00-serial'in str(p);a=next(x for x in archive['members']if x['path']==str(p));assert a['sha256']==row['sha256']and a['bytes']==row['bytes']==p.stat().st_size;assert sha(p)==row['sha256']and stamp(p)==identity;rows.append(dict(row,identity=identity))
rec=dict(schema='ownrt.verified-serial-reference-release.v1',passed=True,proof_sha256=sha(proofpath),restore_receipt_sha256=sha(restorepath),archive=restore['archive'],verified_archive_sha256=restore['archive_sha256'],HDD_archive_reread=False,fresh_RAM_SHA_verified=True,removed=rows,released_bytes=sum(x['bytes']for x in rows))
p=profile/'serial-reference-release.json';p.write_text(json.dumps(rec,indent=2)+'\n')
for row in rows:
 f=Path(row['path']);assert stamp(f)==row['identity'];f.unlink()
rec.update(removal_completed=True,removed_files_absent=all(not Path(x['path']).exists()for x in rows));p.write_text(json.dumps(rec,indent=2)+'\n');print(json.dumps({'released_bytes':rec['released_bytes'],'removal_completed':True}))
