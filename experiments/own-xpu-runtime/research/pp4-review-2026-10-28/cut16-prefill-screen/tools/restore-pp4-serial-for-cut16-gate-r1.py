from pathlib import Path
import hashlib,json,subprocess,tarfile,shutil
R=Path('/dev/shm/sc117-reference-route-pp4-gate-20261028-r1')
P=Path('/dev/shm/sc117-gate-cut16-20261028-r1')
terminal=json.loads((P/'gate-output/terminal.json').read_text())
assert terminal['passed'] and not terminal.get('error') and not terminal['live_pids'] and all(v==0 for v in terminal['returncodes'].values())
a=json.loads((R/'archive.json').read_text())
assert a['full_tar_bytes_compared'] and a['actual_payload_sha256_matches_all_seals']
rows=[x for x in a['members'] if 'request-00-serial/' in x['member']]
assert len(rows)==5 and all(not Path(x['path']).exists() for x in rows)
assert shutil.disk_usage('/dev/shm').free>sum(x['bytes'] for x in rows)+2147483648
byname={x['member']:x for x in rows};done=[]
proc=subprocess.Popen(['zstd','-dc',a['archive']],stdout=subprocess.PIPE)
with tarfile.open(fileobj=proc.stdout,mode='r|') as t:
 for member in t:
  if member.name not in byname:continue
  row=byname[member.name];assert member.isfile() and member.size==row['bytes']
  path=Path(row['path']);assert path.is_relative_to(R/'output') and path.name=='state.bundle'
  h=hashlib.sha256();n=0
  with path.open('xb') as out:
   source=t.extractfile(member)
   for b in iter(lambda:source.read(1024**2),b''):out.write(b);h.update(b);n+=len(b)
  assert n==row['bytes'] and h.hexdigest()==row['sha256'];done.append(row)
proc.stdout.close();assert proc.wait()==0 and len(done)==5
receipt=dict(schema='ownrt.verified-serial-reference-restore.v1',archive=a['archive'],archive_sha256=a['archive_sha256'],restored=done,selected_payloads_sha_verified=True)
(P/'serial-reference-restore.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(dict(restored=len(done),bytes=sum(x['bytes']for x in done))))
