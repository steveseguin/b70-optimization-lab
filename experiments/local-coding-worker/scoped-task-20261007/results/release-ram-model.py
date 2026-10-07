#!/usr/bin/env python3
"""Release only this trial's verified RAM copy, after explicit operator invocation."""
from pathlib import Path
import datetime,hashlib,json,os,re,stat,subprocess,sys,time,traceback
BASE=Path(__file__).resolve().parent
SERVER=BASE/'server'
MODEL=Path('/dev/shm/qwen38-27b-fp8-worker-20261007')
REV='017b9c7af6b5689d5dd426a76e0bc077eb5ca20a'
COLD='/mnt/usb-models/worker-models/qwen38-27b-fp8-20261007/'+REV
MANIFEST=BASE/'model-restore/publisher-manifest.json'
OLD=Path('/home/steve/worker-qwen27b-intake-20261007/model-preservation')
EXPECTED_CONTAINER='6e6cd967920f9438888927ae765c8e8d2b3291ad2acff1c50173b533034b7d67'
EXPECTED_OWNER='e3773dbddaa545198f4f1592564983e2'
EXPECTED_IMAGE='sha256:521eb277c0733f8c2ce47aea1bb98ed576c6f1ad63bf5baf22d38fc07abf54ad'
BYTES=30890049597
FAULT=re.compile(r'Fault response|CAT error|engine reset|GPU HANG|GuC.*reset|coredump|Timedout job|wedged|Out of memory: Killed process',re.I)

def require(ok,message):
 if not ok:raise RuntimeError(message)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def command(args):return subprocess.check_output(args,text=True,timeout=20)
def durable(name,obj):
 data=(json.dumps(obj,indent=2)+'\n').encode()
 with (BASE/name).open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 fd=os.open(BASE,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
def identity(s):return (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_size,s.st_mtime_ns,s.st_ctime_ns)

def shutdown_guard():
 require(not (SERVER/'FAULT.json').exists(),'Server FAULT receipt exists')
 shutdown=read(SERVER/'shutdown.json');state=shutdown['container_state']
 require(shutdown.get('container_id')==EXPECTED_CONTAINER,'Wrong shutdown container')
 require(state.get('Status')=='exited' and state.get('Running') is False and state.get('ExitCode')==0 and state.get('OOMKilled') is False,'Server did not exit cleanly without OOM')
 require(shutdown.get('new_kernel_fault') is False and shutdown.get('render_nodes_idle') is True and shutdown.get('four_card_postflight_passed') is True,'Clean shutdown/postflight not established')
 health=read(SERVER/'postflight-health.json')
 require(health.get('passed') is True and health.get('device_count')==4 and len(health.get('cards',[]))==4,'Four-card postflight absent')
 require({c.get('device') for c in health['cards']}=={f'xpu:{i}' for i in range(4)} and all(c.get('pass') is True for c in health['cards']),'Not all four cards passed')
 require(not health.get('journal_fault_lines_during_probe'),'Fault during postflight')
 nodes=sorted(str(p) for p in Path('/dev/dri').glob('renderD*'));require(len(nodes)==4,'Expected four render nodes')
 fuser=subprocess.run(['fuser','-v',*nodes],capture_output=True,text=True,timeout=15)
 require(fuser.returncode==1 and not fuser.stdout and not fuser.stderr,'Render holders or failed holder check')
 own=read(SERVER/'container.json')
 require((own.get('id'),own.get('owner'),own.get('image'))==(EXPECTED_CONTAINER,EXPECTED_OWNER,EXPECTED_IMAGE),'Owned container identity changed')
 running=command(['docker','ps','--no-trunc','--filter','label=lab.local-coding-worker.pilot-owner='+EXPECTED_OWNER,'--format','{{.ID}}']).strip()
 require(not running,'Owned container is running')
 exists=command(['docker','ps','-a','--no-trunc','--filter','id='+EXPECTED_CONTAINER,'--format','{{.ID}}']).strip()
 actual={'absent':not bool(exists)}
 if exists:
  require(exists==EXPECTED_CONTAINER,'Ambiguous actual container identity')
  d=json.loads(command(['docker','inspect',EXPECTED_CONTAINER]))[0]
  require(d['Id']==EXPECTED_CONTAINER and d['Image']==EXPECTED_IMAGE and d['Config']['Labels'].get('lab.local-coding-worker.pilot-owner')==EXPECTED_OWNER,'Actual container owner/image mismatch')
  s=d['State'];require(s.get('Status')=='exited' and s.get('Running') is False and s.get('ExitCode')==0 and s.get('OOMKilled') is False,'Actual container not cleanly stopped')
  actual={'absent':False,'state':s}
 require(not Path('/mnt/usb-models').is_mount(),'External drive must remain unmounted')
 journal=command(['journalctl','-k','-b','--since',health['end_utc'],'--no-pager'])
 require(not FAULT.search(journal),'New fault since postflight')
 return {'shutdown_sha256':sha(SERVER/'shutdown.json'),'postflight_sha256':sha(SERVER/'postflight-health.json'),'container':actual,'render_nodes':nodes,'render_nodes_idle':True,'journal_since_postflight':journal}

def preservation_guard():
 old=read(OLD/'summary.json');restore=read(BASE/'model-restore/summary.json')
 require(old.get('status')=='verified-cold-copy-complete' and old.get('revision')==REV and old.get('destination')==COLD and old.get('model_files')==80 and old.get('model_bytes')==BYTES and old.get('post_clean_remount_full_readback') is True and old.get('drive_cleanly_unmounted') is True and old.get('new_kernel_faults') is False,'Original cold copy proof incomplete')
 require(restore.get('status')=='verified-cold-restore-complete' and restore.get('revision')==REV and restore.get('destination')==str(MODEL) and restore.get('source')==COLD and restore.get('model_files')==80 and restore.get('model_bytes')==BYTES and restore.get('drive_cleanly_unmounted') is True and restore.get('new_kernel_faults') is False and restore.get('source_cold_bytes_retained') is True and restore.get('source_publisher_hashes_verified') is True and restore.get('ram_destination_hashes_verified') is True,'Fresh restore proof incomplete')
 require(restore.get('old_cold_receipt_sha256')==sha(OLD/'summary.json'),'Restore does not bind original cold proof')
 expected=read(OLD/'source.json')
 for p in [OLD/'copy.json',OLD/'readback.json',BASE/'model-restore/source.json',BASE/'model-restore/destination.json']:
  require(read(p)==expected,'Preservation/restore hash receipts disagree: '+str(p))
 manifest=read(MANIFEST)
 require(manifest==read(OLD/'publisher-manifest.json') and manifest['revision']==REV,'Frozen publisher manifest differs')
 rows=manifest['lfs_files']+manifest['small_files']
 require(len(rows)==80 and sum(r['bytes'] for r in rows)==BYTES and len({r['path'] for r in rows})==80,'Unexpected selected model inventory')
 require(all(len(Path(r['path']).parts)==1 and r['path'] not in ('.','..') for r in rows),'Unsafe model path')
 return rows,expected,{'cold_model_preserved':COLD,'cold_summary':str(OLD/'summary.json'),'cold_summary_sha256':sha(OLD/'summary.json'),'restore_summary':str(BASE/'model-restore/summary.json'),'restore_summary_sha256':sha(BASE/'model-restore/summary.json'),'publisher_manifest':str(MANIFEST),'publisher_manifest_sha256':sha(MANIFEST)}

def main():
 require(sys.argv[1:]==['--execute-after-shutdown'],'Explicit --execute-after-shutdown invocation required')
 require(not (BASE/'model-scratch-release.json').exists() and not (BASE/'model-release-intent.json').exists(),'Release evidence already exists; no automatic retry')
 first=shutdown_guard();rows,expected,proof=preservation_guard()
 require(MODEL.is_dir() and not MODEL.is_symlink() and MODEL.resolve()==MODEL,'RAM directory missing or redirected')
 mount=json.loads(command(['findmnt','-J','-T',str(MODEL),'-o','TARGET,FSTYPE']))['filesystems'][0]
 require(mount['target']=='/dev/shm' and mount['fstype']=='tmpfs','Exact model root is not on expected tmpfs')
 fd=os.open(MODEL,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:
  dir_stat=os.fstat(fd)
  require(sorted(os.listdir(fd))==sorted(r['path'] for r in rows),'RAM directory is not exactly the80 pinned files')
  verified=[];file_stats={};start=time.monotonic()
  for row in rows:
   name=row['path'];filefd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
   with os.fdopen(filefd,'rb') as f:
    before=os.fstat(f.fileno());require(stat.S_ISREG(before.st_mode) and before.st_size==row['bytes'],'Wrong source type/size: '+name)
    h=hashlib.sha256();g=hashlib.sha1(b'blob '+str(before.st_size).encode()+b'\0')
    while chunk:=f.read(4*1024*1024):
     h.update(chunk);g.update(chunk)
     require(time.monotonic()-start<300,'Hash phase exceeded5min; no release')
    require(identity(before)==identity(os.fstat(f.fileno())),'Model file changed during hashing: '+name)
   if 'sha256' in row:require(h.hexdigest()==row['sha256'],'Publisher SHA mismatch: '+name)
   if 'git_blob' in row:require(g.hexdigest()==row['git_blob'],'Publisher Gitblob mismatch: '+name)
   verified.append({'path':name,'bytes':before.st_size,'sha256':h.hexdigest(),'git_blob':g.hexdigest()});file_stats[name]=identity(before)
  require(verified==expected,'Current model hashes differ from preserved cold source')
  final=shutdown_guard();preservation_guard()
  require(identity(MODEL.lstat())==identity(dir_stat),'RAM directory identity changed')
  require(sorted(os.listdir(fd))==sorted(file_stats),'RAM inventory changed after hashing')
  for name,want in file_stats.items():require(identity(os.stat(name,dir_fd=fd,follow_symlinks=False))==want,'Model changed before release: '+name)
  # Durable intent exists before deleting any individual verified scratch file.
  durable('model-release-intent.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exact_ram_path':str(MODEL),'verified_files':verified,'model_bytes':BYTES,'preservation':proof,'pre_hash_shutdown':first,'pre_release_shutdown':final,'cold_source_never_opened_or_modified_by_release':True})
  removed=[]
  for name,want in file_stats.items():
   require(identity(os.stat(name,dir_fd=fd,follow_symlinks=False))==want,'Model changed during release: '+name)
   os.unlink(name,dir_fd=fd);removed.append(name)
  os.fsync(fd);require(not os.listdir(fd),'RAM directory no longer empty')
  require((MODEL.lstat().st_dev,MODEL.lstat().st_ino)==(dir_stat.st_dev,dir_stat.st_ino),'RAM directory replaced before rmdir')
  os.rmdir(MODEL)
 finally:os.close(fd)
 parent=os.open('/dev/shm',os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(parent)
 finally:os.close(parent)
 require(not MODEL.exists() and not Path('/mnt/usb-models').is_mount(),'Unexpected post-release path/mount state')
 durable('model-scratch-release.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'removed_owned_temporary_ram_model':str(MODEL),'files_rehashed_before_release':len(verified),'bytes_released':BYTES,'verified_files':verified,'cold_model_preserved':COLD,'cold_copy_full_post_remount_hashes_verified':True,'drive_cleanly_unmounted':True,'server_cleanly_stopped':True,'four_card_postflight_passed':True,'no_host_settings_changed':True,'preservation':proof,'release_intent_sha256':sha(BASE/'model-release-intent.json'),'script_sha256':sha(Path(__file__))})
 print('Released only verified80-file RAM model; cold model retained; EX400U unmounted',flush=True)

if __name__=='__main__':
 try:main()
 except BaseException as error:
  if sys.argv[1:]==['--execute-after-shutdown']:
   name='model-release-failure-'+str(time.time_ns())+'.json'
   durable(name,{'error':str(error),'type':type(error).__name__,'ram_path_present':MODEL.exists(),'cold_source_untouched':True,'automatic_retry':False})
  traceback.print_exc();sys.exit(1)
