#!/usr/bin/env python3
"""One bounded additive cold copy; sources retained; no runtime/device probes."""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys,time,traceback
OUT=Path(__file__).resolve().parent
SOURCE=Path('/dev/shm/qwen35-4b-worker-20261007')
MANIFEST=Path('/home/steve/llm-optimizations/repro/qwen35-4b-w4a16-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json')
LOG=Path('/home/steve/worker-small-model-pilot-20261007/qwen4b-download.log')
MOUNT=Path('/mnt/usb-models')
UUID='4E0E66ED0E66CD91'
REV='7a613872f394578b0b52b683ff4ac47516b4bcaf'
BASE=MOUNT/'worker-models/qwen35-4b-w4a16-20261007'
DEST=BASE/REV
STAGE=BASE/(REV+'.incomplete')
FAULT=re.compile(r'I/O error|uas_eh|USB disconnect|reset .*USB|ntfs.*error|Fault response|GPU HANG|timed.out job',re.I)

def receipt(name,value):
 (OUT/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')

def command(args,timeout=15):
 return subprocess.check_output(args,text=True,timeout=timeout)

def privileged(args):
 # File descriptor stdin only: password never becomes argv, output, or an artifact.
 with open('/home/steve/SUDOPASSWORD.txt','rb') as password:
  done=subprocess.run(['sudo','-S','-p','',*args],stdin=password,capture_output=True,timeout=45)
 if done.returncode: raise RuntimeError('Privileged command failed: '+str(args)+' '+done.stderr.decode(errors='replace'))

def rows():
 m=json.loads(MANIFEST.read_text())
 assert m['revision']==REV
 r=m['lfs_files']+m['small_files']; assert len(r)==12
 for row in r:
  p=Path(row['path']); assert len(p.parts)==1 and p.name not in ('.','..')
 return r

def verify(root):
 result=[]
 for row in rows():
  p=root/row['path']; s=p.lstat(); assert p.is_file() and not p.is_symlink()
  assert s.st_size==row['bytes'], str(p)+' size mismatch'
  sha=hashlib.sha256(); blob=hashlib.sha1(b'blob '+str(s.st_size).encode()+b'\0')
  with p.open('rb') as f:
   while chunk:=f.read(4*1024*1024): sha.update(chunk); blob.update(chunk)
  after=p.stat(); assert (s.st_ino,s.st_size,s.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns)
  if 'sha256' in row: assert sha.hexdigest()==row['sha256'], str(p)+' sha mismatch'
  if 'git_blob' in row: assert blob.hexdigest()==row['git_blob'], str(p)+' Git blob mismatch'
  result.append({'path':row['path'],'bytes':s.st_size,'sha256':sha.hexdigest(),'git_blob':blob.hexdigest()})
 return result

def worker(phase):
 if phase=='source': result=verify(SOURCE)
 elif phase=='copy':
  BASE.mkdir(parents=True,exist_ok=True)
  assert not DEST.exists(); STAGE.mkdir(exist_ok=False)
  expected=json.loads((OUT/'source.json').read_text())
  for row in expected:
   with (SOURCE/row['path']).open('rb') as source,(STAGE/row['path']).open('xb') as target:
    while chunk:=source.read(4*1024*1024): target.write(chunk)
    target.flush(); os.fsync(target.fileno())
  result=verify(STAGE); assert result==expected
  for name in ('publisher-manifest.json','source.json'):
   with (STAGE/('PRESERVATION-'+name)).open('xb') as target:
    target.write((OUT/name).read_bytes()); target.flush(); os.fsync(target.fileno())
  fd=os.open(STAGE,os.O_RDONLY|os.O_DIRECTORY)
  try: os.fsync(fd)
  finally: os.close(fd)
  STAGE.rename(DEST)
  fd=os.open(BASE,os.O_RDONLY|os.O_DIRECTORY)
  try: os.fsync(fd)
  finally: os.close(fd)
 elif phase=='readback':
  result=verify(DEST); assert result==json.loads((OUT/'source.json').read_text())
  for name in ('publisher-manifest.json','source.json'):
   assert (DEST/('PRESERVATION-'+name)).read_bytes()==(OUT/name).read_bytes()
 else: raise ValueError(phase)
 receipt(phase,result)
 print(phase+' verified '+str(len(result))+' files',flush=True)

CURSOR=None

def guard(mode=None):
 log=command(['journalctl','-k','-b','--after-cursor',CURSOR,'--no-pager'])
 (OUT/'kernel-during.txt').write_text(log)
 assert not FAULT.search(log),'New kernel fault: stop backup I/O'
 if mode:
  assert MOUNT.is_mount()
  mount=json.loads(command(['findmnt','-J','-o','SOURCE,FSTYPE,OPTIONS',str(MOUNT)]))['filesystems'][0]
  expected=Path('/dev/disk/by-uuid')/UUID
  assert Path(mount['source']).resolve()==expected.resolve(strict=True)
  assert mount['fstype']=='fuseblk'
  options=mount['options'].split(',')
  assert mode in options and all(x in options for x in ('nodev','nosuid','noexec'))
  available=os.statvfs(MOUNT).f_bavail*os.statvfs(MOUNT).f_frsize
  assert available>50*1024**3
  return {'mount':mount,'available_bytes':available,'uuid':UUID}

def run_worker(phase,mode=None):
 guard(mode); started=time.monotonic()
 with (OUT/(phase+'.log')).open('xb') as log:
  p=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--worker',phase],stdout=log,stderr=subprocess.STDOUT)
  try:
   while p.poll() is None:
    time.sleep(3); guard(mode)
    assert time.monotonic()-started<600,phase+' exceeded10min bound'
   assert p.returncode==0,phase+' worker failed; see log'
  except BaseException:
   if p.poll() is None:
    p.terminate(); p.wait(timeout=15)
   raise
 guard(mode)

def main():
 global CURSOR
 assert not MOUNT.is_mount(),'Mountpoint already mounted; refuse ownership ambiguity'
 assert not list(MOUNT.iterdir()),'Unmounted mountpoint not empty'
 assert Path('/dev/disk/by-uuid',UUID).resolve(strict=True)==Path('/dev/sda2')
 baseline=command(['journalctl','-k','-b','-n','0','--show-cursor','--no-pager'])
 (OUT/'kernel-start-cursor.txt').write_text(baseline)
 CURSOR=baseline.strip().split('-- cursor: ')[1]
 (OUT/'publisher-manifest.json').write_bytes(MANIFEST.read_bytes())
 start=time.monotonic(); progress=[]
 while True:
  complete='downloaded; now verify the bytes' in LOG.read_text()
  live=[pid for pid in (2959775,2959780,2959793) if Path('/proc',str(pid)).exists()]
  partial=list(SOURCE.glob('*.aria2'))
  observed={'elapsed_seconds':round(time.monotonic()-start),'downloader_pids':live,'partial_files':[p.name for p in partial],'completed_marker':complete}
  if Path('/proc/2959793/io').exists(): observed['aria2_io']=Path('/proc/2959793/io').read_text()
  progress.append(observed); receipt('download-wait',progress)
  if complete and not live and not partial: break
  assert time.monotonic()-start<300,'Download incomplete after bounded5min wait; no mount attempted'
  guard(); time.sleep(10)
 assert sorted(p.name for p in SOURCE.iterdir())==sorted(r['path'] for r in rows())
 run_worker('source')
 privileged(['mount','-t','ntfs-3g','-o','rw,norecover,nodev,nosuid,noexec,uid=1000,gid=1000','UUID='+UUID,str(MOUNT)])
 admitted=guard('rw'); planned=sum(r['bytes'] for r in rows())
 assert admitted['available_bytes']>50*1024**3+planned
 receipt('write-admission',admitted|{'planned_model_bytes':planned})
 run_worker('copy','rw')
 privileged(['umount',str(MOUNT)]); assert not MOUNT.is_mount(); guard()
 privileged(['mount','-t','ntfs-3g','-o','ro,norecover,nodev,nosuid,noexec,uid=1000,gid=1000','UUID='+UUID,str(MOUNT)])
 receipt('read-admission',guard('ro'))
 run_worker('readback','ro')
 privileged(['umount',str(MOUNT)]); assert not MOUNT.is_mount(); guard()
 receipt('summary',{'status':'verified-cold-copy-complete','repository':json.loads(MANIFEST.read_text())['repository'],'revision':REV,'source':str(SOURCE),'destination':str(DEST),'model_files':12,'model_bytes':planned,'source_retained':True,'source_verification':'ordinary full reads of tmpfs; publisher LFS SHA256/small-file Git blob; source SHA256 for every file','post_clean_remount_full_readback':True,'drive_cleanly_unmounted':True,'new_kernel_faults':False,'long_term_drive_reliability_qualified':False})
 print('SUCCESS: full source/copy/remount readback verified; drive unmounted; RAM source retained',flush=True)

if __name__=='__main__':
 if len(sys.argv)==3 and sys.argv[1]=='--worker': worker(sys.argv[2])
 else:
  try: main()
  except BaseException as e:
   receipt('failure',{'error':str(e),'type':type(e).__name__,'mount_present':MOUNT.is_mount(),'source_retained':True})
   traceback.print_exc(); sys.exit(1)
