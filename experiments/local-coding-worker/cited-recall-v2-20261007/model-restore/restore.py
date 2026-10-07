#!/usr/bin/env python3
"""One read-only cold restore. No model launch, settings changes, or retries."""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys,time,traceback
OUT=Path(__file__).resolve().parent
PILOT=Path('/home/steve/llm-optimizations/experiments/local-coding-worker/qwen27b-target-only-pilot-20261007')
MANIFEST=PILOT/'model-manifest.json'
OLD=Path('/home/steve/worker-qwen27b-intake-20261007/model-preservation')
MOUNT=Path('/mnt/usb-models')
UUID='4E0E66ED0E66CD91'
REV='017b9c7af6b5689d5dd426a76e0bc077eb5ca20a'
SOURCE=MOUNT/'worker-models/qwen38-27b-fp8-20261007'/REV
DEST=Path('/dev/shm/qwen38-27b-fp8-worker-20261007')
BYTES=30890049597
FAULT=re.compile(r'I/O error|uas_eh|USB disconnect|reset .*USB|ntfs.*error|Fault response|GPU HANG|timed.out job',re.I)
CURSOR=None

def save(name,obj): (OUT/(name+'.json')).write_text(json.dumps(obj,indent=2)+'\n')
def cmd(args,timeout=15): return subprocess.check_output(args,text=True,timeout=timeout)
def privileged(args):
 with open('/home/steve/SUDOPASSWORD.txt','rb') as password:
  p=subprocess.run(['sudo','-S','-p','',*args],stdin=password,capture_output=True,timeout=45)
 if p.returncode: raise RuntimeError('Privileged command failed: '+str(args)+' '+p.stderr.decode(errors='replace'))
def rows():
 frozen=(OUT/'publisher-manifest.json').read_bytes()
 assert hashlib.sha256(frozen).hexdigest()==json.loads((OUT/'plan.json').read_text())['manifest_sha256']
 m=json.loads(frozen);assert m['revision']==REV
 r=m['lfs_files']+m['small_files'];assert len(r)==80 and sum(x['bytes'] for x in r)==BYTES
 for x in r: assert len(Path(x['path']).parts)==1 and x['path'] not in ('.','..')
 return r

def available(p):
 s=os.statvfs(p);return s.f_bavail*s.f_frsize

def passive():
 processes=[]
 for line in cmd(['ps','-eo','pid=,comm=,args=']).splitlines():
  fields=line.split(None,2)
  if len(fields)<3: continue
  pid,comm,args=fields
  if comm.startswith(('VLLM','llama-server','ollama')) or re.search(r'(?:^| )vllm\.entrypoints\.|-m vllm\.|ComfyUI[^ ]*/main\.py',args):processes.append(line)
 assert not processes,'Model processes present: '+repr(processes)
 nodes=[str(p) for p in Path('/dev/dri').glob('renderD*')]
 assert len(nodes)==4
 p=subprocess.run(['fuser','-v',*nodes],capture_output=True,text=True,timeout=15)
 assert p.returncode==1 and not p.stdout and not p.stderr,'Render holders or failed passive holder check'
 return {'model_processes':processes,'render_nodes':nodes,'render_nodes_idle':True}

def guard(mounted=False):
 log=cmd(['journalctl','-k','-b','--after-cursor',CURSOR,'--no-pager'])
 (OUT/'kernel-during.txt').write_text(log)
 assert not FAULT.search(log),'New kernel fault: stop all restore I/O'
 assert available('/')>=50*1024**3,'Root reserve crossed'
 if mounted:
  assert MOUNT.is_mount()
  m=json.loads(cmd(['findmnt','-J','-o','SOURCE,FSTYPE,OPTIONS',str(MOUNT)]))['filesystems'][0]
  assert Path(m['source']).resolve()==Path('/dev/disk/by-uuid',UUID).resolve(strict=True)
  assert m['fstype']=='fuseblk'
  opts=m['options'].split(',');assert 'ro' in opts and 'rw' not in opts
  assert all(x in opts for x in ['nodev','nosuid','noexec'])
  return m

def hashes(p,want,target=None):
 before=p.lstat();assert p.is_file() and not p.is_symlink() and before.st_size==want['bytes']
 sha=hashlib.sha256();blob=hashlib.sha1(b'blob '+str(before.st_size).encode()+b'\0')
 with p.open('rb') as f:
  while b:=f.read(4*1024*1024):
   sha.update(b);blob.update(b)
   if target is not None:target.write(b)
 after=p.lstat();assert (before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns)
 if 'sha256' in want:assert sha.hexdigest()==want['sha256'],want['path']+' SHA256 mismatch'
 if 'git_blob' in want:assert blob.hexdigest()==want['git_blob'],want['path']+' Git blob mismatch'
 return {'path':want['path'],'bytes':before.st_size,'sha256':sha.hexdigest(),'git_blob':blob.hexdigest()}

def worker():
 expected=json.loads((OLD/'source.json').read_text())
 # Original receipts and external provenance must bind the same exact model.
 assert expected==json.loads((OLD/'copy.json').read_text())==json.loads((OLD/'readback.json').read_text())
 for name in ['publisher-manifest.json','source.json']:
  f=SOURCE/('PRESERVATION-'+name);assert f.is_file() and not f.is_symlink()
  assert f.read_bytes()==(OLD/name).read_bytes(),name+' external provenance mismatch'
 assert json.loads((SOURCE/'PRESERVATION-publisher-manifest.json').read_text())==json.loads((OUT/'publisher-manifest.json').read_text())
 assert sorted(p.name for p in SOURCE.iterdir())==sorted([r['path'] for r in rows()]+['PRESERVATION-publisher-manifest.json','PRESERVATION-source.json'])
 assert SOURCE.is_dir() and not SOURCE.is_symlink()
 DEST.mkdir(exist_ok=False)
 source=[]
 for row in rows():
  with (DEST/row['path']).open('xb') as target:
   source.append(hashes(SOURCE/row['path'],row,target));target.flush();os.fsync(target.fileno())
  print('copied and source-verified '+row['path'],flush=True)
 assert source==expected;save('source',source)
 dest=[hashes(DEST/row['path'],row) for row in rows()];assert dest==source;save('destination',dest)
 assert sorted(p.name for p in DEST.iterdir())==sorted(r['path'] for r in rows())
 fd=os.open(DEST,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
 print('All80 coldsource and RAMdestination hashes verified',flush=True)

def main():
 global CURSOR
 assert not DEST.exists(),'RAM model already exists; refuse overwrite'
 assert not MOUNT.is_mount() and not list(MOUNT.iterdir()),'Mountpoint unavailable'
 assert Path('/dev/disk/by-uuid',UUID).resolve(strict=True)==Path('/dev/sda2')
 info={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')}
 admission={'root_available_bytes':available('/'),'root_reserve_bytes':50*1024**3,'tmpfs_available_bytes':available('/dev/shm'),'planned_model_bytes':BYTES,'tmpfs_reserve_bytes':24*1024**3,'host_mem_available_bytes':info['MemAvailable'],'required_host_mem_available_bytes':90*1024**3,**passive()}
 save('pre-mount-admission',admission)
 assert admission['root_available_bytes']>=admission['root_reserve_bytes']
 assert admission['tmpfs_available_bytes']>=BYTES+admission['tmpfs_reserve_bytes']
 assert admission['host_mem_available_bytes']>=admission['required_host_mem_available_bytes']
 log=cmd(['journalctl','-k','-b','--since=-10min','--no-pager']);(OUT/'kernel-recent.txt').write_text(log)
 assert not FAULT.search(log),'Recent kernel fault; refuse mount'
 baseline=cmd(['journalctl','-k','-b','-n','0','--show-cursor','--no-pager']);(OUT/'kernel-start-cursor.txt').write_text(baseline);CURSOR=baseline.strip().split('-- cursor: ')[1]
 m=MANIFEST.read_bytes();(OUT/'publisher-manifest.json').write_bytes(m)
 old=json.loads((OLD/'summary.json').read_text());assert old['status']=='verified-cold-copy-complete' and old['revision']==REV and old['post_clean_remount_full_readback'] and old['drive_cleanly_unmounted']
 save('plan',{'source':str(SOURCE),'destination':str(DEST),'revision':REV,'model_files':80,'model_bytes':BYTES,'manifest_path':str(MANIFEST),'manifest_sha256':hashlib.sha256(m).hexdigest(),'old_cold_receipt':str(OLD/'summary.json'),'old_cold_receipt_sha256':hashlib.sha256((OLD/'summary.json').read_bytes()).hexdigest(),'mount_mode':'ro,norecover,nodev,nosuid,noexec','stage_timeout_seconds':900})
 guard();privileged(['mount','-t','ntfs-3g','-o','ro,norecover,nodev,nosuid,noexec,uid=1000,gid=1000','UUID='+UUID,str(MOUNT)]);save('mounted-admission',{'mount':guard(True),'uuid':UUID})
 print('Read-only mount admitted;80-file restore starts',flush=True)
 start=time.monotonic()
 with (OUT/'copy-verify.log').open('xb') as log:
  p=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--worker'],stdout=log,stderr=subprocess.STDOUT)
  try:
   while p.poll() is None:
    time.sleep(3);guard(True)
    assert available('/dev/shm')>=24*1024**3,'Tmpfs reserve crossed'
    assert time.monotonic()-start<900,'Restore exceeded15-minute bound'
   assert p.returncode==0,'Copy/verify worker failed; see log'
  except BaseException:
   if p.poll() is None:p.terminate();p.wait(timeout=15)
   raise
 guard(True);privileged(['umount',str(MOUNT)]);assert not MOUNT.is_mount();guard()
 save('summary',{'status':'verified-cold-restore-complete','repository':'Qwen/Qwen3.8-27B-FP8','revision':REV,'source':str(SOURCE),'destination':str(DEST),'model_files':80,'model_bytes':BYTES,'source_cold_bytes_retained':True,'source_publisher_hashes_verified':True,'ram_destination_hashes_verified':True,'drive_cleanly_unmounted':True,'new_kernel_faults':False,'gpu_operations':False,'old_cold_receipt':str(OLD/'summary.json'),'old_cold_receipt_sha256':hashlib.sha256((OLD/'summary.json').read_bytes()).hexdigest(),'root_available_bytes':available('/'),'tmpfs_available_bytes':available('/dev/shm')})
 print('SUCCESS:80file coldrestore verified;EX400U cleanly unmounted;noGPUactions',flush=True)

if __name__=='__main__':
 if sys.argv[1:]==['--worker']:worker()
 else:
  try:main()
  except BaseException as e:
   save('failure',{'error':str(e),'type':type(e).__name__,'mount_present':MOUNT.is_mount(),'partial_ram_preserved':DEST.exists(),'cold_source_retained':True});traceback.print_exc();sys.exit(1)
