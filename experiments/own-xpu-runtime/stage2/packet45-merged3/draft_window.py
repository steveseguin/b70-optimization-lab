"""Coordinator KD: two fresh owners, complete captured draft rows, byte comparisons."""
import gzip,json,os,shutil,subprocess,sys,time
from pathlib import Path
from pipeline import P,sha,require,save,DeviceOwnerFailure
B=P/'build'
from storage import admit
def failed_owner(child,out,watch,error,stop_w):
 # ENOSPC or a failing journal hook must never skip cooperative shutdown.
 # Receipt writes are attempted first; losing the stop pipe also requests stop.
 for action in (lambda:watch.latch(error),
                lambda:save(out/'failure-before-teardown.json',dict(error=str(error),pid=child.pid))):
  try:action()
  except Exception:pass
 try:os.write(stop_w,b'!')
 except OSError:
  try:os.close(stop_w)
  except OSError:pass
 end=time.monotonic()+65
 while child.poll() is None and time.monotonic()<end:
  try:watch.poll_kernel()
  except Exception:pass
  time.sleep(.1)
 try:save(out/'retained.json',dict(pids=[child.pid] if child.poll() is None else [],signals_sent=0,stop_requested=True))
 except Exception:pass

def archive_host_reference(out):
 # archive_files verifies every retained text byte and binds all raw hashes.
 # The caller alone decides that the CPU producer has exited.
 from storage import archive_files,P as storage_packet
 root=Path(out)/'host-reference'
 require(not root.is_symlink() and root.resolve().is_relative_to(storage_packet),'KD host scratch outside packet')
 archive=archive_files([f for f in root.rglob('*') if f.is_file()],Path(out)/'host-reference.jsonl.gz')
 return archive

def cleanup_failed_host_reference(out,child,error):
 root=Path(out)/'host-reference'
 if not root.exists():return
 disposition=dict(passed=False,device_executed=False,original_error=str(error),scratch_removed=False)
 try:
  # A missing handle cannot establish process exit. Preserve uncertain files.
  if child is None or child.poll() is None:
   disposition.update(status='preserved-live-or-unconfirmed-host',host_pid=getattr(child,'pid',None))
  else:
   disposition.update(status='archived-exited-host',host_pid=child.pid,host_returncode=child.returncode)
   archive=archive_host_reference(out)
   disposition['scratch_archive']=archive
   receipt=root/'receipt.json'
   if receipt.is_file():disposition['host_receipt_sha256']=sha(receipt)
   # Persist evidence before removing only this fixed, exited-host directory.
   save(Path(out)/'host-reference-failure-disposition.json',disposition)
   shutil.rmtree(root)
   disposition['scratch_removed']=True
  save(Path(out)/'host-reference-failure-disposition.json',disposition)
 except Exception as cleanup_error:
  disposition.update(status='cleanup-failed',cleanup_error=str(cleanup_error),scratch_removed=not root.exists())
  try:save(Path(out)/'host-reference-failure-disposition.json',disposition)
  except Exception as receipt_error:print('KD host scratch cleanup receipt failed: '+str(receipt_error),file=sys.stderr)
  print('KD host scratch cleanup failed; original window error preserved: '+str(cleanup_error),file=sys.stderr)

def run(a,out,env,watch,build,*,cpu_rehearsal=False):
 lifecycle={};failure=None
 try:return _run(a,out,env,watch,build,cpu_rehearsal=cpu_rehearsal,host_lifecycle=lifecycle)
 except BaseException as error:
  failure=error
  raise
 finally:
  if failure is not None:
   try:cleanup_failed_host_reference(out,lifecycle.get('child'),failure)
   except Exception as cleanup_error:print('KD cleanup could not inspect scratch; original window error preserved: '+str(cleanup_error),file=sys.stderr)

def _run(a,out,env,watch,build,*,cpu_rehearsal=False,host_lifecycle):
 def cpu_capture(cmd):
  if not cpu_rehearsal:return cmd
  result=[];index=0
  while index<len(cmd):
   if cmd[index]=='--authorized-device-window':index+=1;continue
   if cmd[index] in ('--plan','--identity','--model-dir'):index+=2;continue
   result.append(cmd[index]);index+=1
  return result+['--mini','--pipeline-mini']
 source=json.loads((P/f'capture-run-incident-retrospective-c{a.context}.json').read_text());reference=Path(source['output'])
 # A fixture-only reseal retains historical execution identity explicitly.
 evidence_artifacts=build.get('model_evidence_artifacts_sha256',build['artifacts_sha256'])
 if evidence_artifacts!=build['artifacts_sha256']:
  delta=build['fixture_delta_qualification']
  require(delta['passed'] and delta['fresh_real_cases']==1 and delta['called_by_production_decode'] is False,'KD fixture delta qualification')
 require(source['binary_sha256']==evidence_artifacts['gnu-host/own-rt-iq3'],'KD CPU reference binary identity')
 table=B/'capture-incident-retrospective.tsv'
 require(sha(table)==source['table_sha256'],'KD table identity')
 require(source['table_sha256']==json.loads((P/'capture-input-incident-retrospective.json').read_text())['table_sha256'],'KD sealed table identity')
 inp=json.loads((a.input/'input.json').read_text())
 from fixture_support import ldd_preflight
 ldd_preflight(B/('gnu-host' if cpu_rehearsal else 'device')/'own-rt-iq3')
 sealed=build['draft_capture_fixture_sha256_by_context'][str(a.context)]
 if 'scratch_archive' in source:
  from capture40 import archived_capture
  archive_table,_=archived_capture(source)
  require(sealed==source['fixture_sha256'],'KD CPU fixture manifest changed')
  for name,digest in sealed.items():require(archive_table[name]['sha256']==digest,'KD archived CPU fixture changed')
  reference_bytes=sum(archive_table[name]['bytes'] for name in sealed)
 else:
  # Synthetic wrapper fixtures have no production capture archive.
  for name,digest in sealed.items():require(sha(reference/name)==digest,'KD CPU fixture changed')
  reference_bytes=sum((reference/name).stat().st_size for name in sealed)
 require(sha(P/'capture-input-incident-retrospective.json')==build['draft_capture_input_sha256']['incident-retrospective'],'KD input receipt changed')
 captured=json.loads((P/'capture-input-incident-retrospective.json').read_text())
 for name,digest in captured['streams'].items():require(sha(B/'captured-incident-retrospective'/name)==digest,'KD input stream changed')
 # Recompute the draft-only oracle using exactly this K2 dispatch. Captured
 # target streams stay immutable; the host owner never contacts a device.
 host_reference=out/'host-reference'
 host_binary=B/'gnu-host/own-rt-iq3'
 require(sha(host_binary)==build['artifacts_sha256']['gnu-host/own-rt-iq3'],'KD host reference binary changed')
 stop_r,stop_w=os.pipe()
 host_cmd=[str(host_binary),'--card',str(a.card+getattr(a,'draft_rank',1)),'--rank','1','--stop-fd',str(stop_r),
           '--draft-capture',str(table),'--context',str(a.context),'--plan',str(a.input/'plan.tsv'),
           '--identity',str(a.input/'identity.tsv'),'--model-dir',inp['model_dir'],
           '--output',str(host_reference),'--dispatch',str(a.dispatch),'--seconds','10800']
 admit(reference_bytes+32*1024*1024)
 try:
  with (out/'host-reference.log').open('w') as log:
   child=subprocess.Popen(['nice','-n','19','ionice','-c','3']+cpu_capture(host_cmd),env=env,stdout=log,stderr=subprocess.STDOUT,pass_fds=(stop_r,))
   host_lifecycle['child']=child
   try:
    watch.mark_cpu_child(child)
    while child.poll() is None:
     watch.check()
     try:
      status=Path(f'/proc/{child.pid}/status').read_text()
      anon=int(next((line.split()[1] for line in status.splitlines() if line.startswith('RssAnon:')),'0'))*1024
      require(anon<8*1024**3,'KD host anonymous memory exceeded8GiB')
     except FileNotFoundError:pass
     time.sleep(.1)
    require(child.returncode==0,'KD host reference failed')
   except Exception as error:
    failed_owner(child,out,watch,error,stop_w);raise
 finally:
  for fd in (stop_w,stop_r):
   try:os.close(fd)
   except OSError:pass
 host_result=json.loads((host_reference/'receipt.json').read_text())
 require(host_result.get('passed') is True and host_result.get('device_executed') is False,'KD host reference receipt')
 reference=host_reference
 sealed={str(f.relative_to(reference)):sha(f) for pattern in ('row-*/*.bf16','row-*/*.bin','draft-final-state/*.bin') for f in reference.glob(pattern)}
 require(sealed,'KD empty selected-dispatch host reference')
 save(out/'host-reference-identity.json',dict(passed=True,device_executed=False,binary_sha256=sha(host_binary),dispatch_sha256=sha(a.dispatch),capture_table_sha256=sha(table),fixtures=sealed))
 receipts={'host-reference-identity.json':sha(out/'host-reference-identity.json'),'host-reference/receipt.json':sha(host_reference/'receipt.json')};pids=[]
 for attempt in range(2):
  watch.last=0.;watch.check()
  admit(sum((reference/name).stat().st_size for name in sealed)+16*1024*1024)
  dest=out/f'owner{attempt}';stop_r,stop_w=os.pipe()
  cmd=[str(B/('gnu-host' if cpu_rehearsal else 'device')/'own-rt-iq3'),'--authorized-device-window','--card',str(a.card+getattr(a,'draft_rank',1)),'--rank','1',
       '--stop-fd',str(stop_r),'--draft-capture',str(table),'--context',str(a.context),'--plan',str(a.input/'plan.tsv'),
       '--identity',str(a.input/'identity.tsv'),'--model-dir',inp['model_dir'],'--output',str(dest),
       '--dispatch',str(a.dispatch),'--seconds','10800']
  try:
   with (out/f'owner{attempt}.log').open('w') as log:
    child=subprocess.Popen(['nice','-n','19','ionice','-c','3']+cpu_capture(cmd),env=env,stdout=log,stderr=subprocess.STDOUT,pass_fds=(stop_r,))
    try:
     watch.mark_launched(child.pid);pids.append(child.pid);save(out/'children.json',dict(pids=pids,signals_sent=0))
     while child.poll() is None:
      watch.check()
      try:
       status=Path(f'/proc/{child.pid}/status').read_text()
       anon=int(next((row.split()[1] for row in status.splitlines() if row.startswith('RssAnon:')),'0'))*1024 # an exited, not yet reaped child has no RssAnon line
       require(anon<8*1024**3,'KD anonymous memory exceeded8GiB')
      except FileNotFoundError:pass
      time.sleep(.1)
     if child.returncode != 0:raise DeviceOwnerFailure('KD owner failed with exit '+str(child.returncode), dest)
     result=json.loads((dest/'receipt.json').read_text());require(result['passed'] and result.get('device_executed') is (not cpu_rehearsal) and len(result.get('teardown',[]))==1 and all(t['safe_to_exit'] and not t['in_flight'] and not t['live_bytes'] for t in result['teardown']),'KD native failure/unsafe teardown')
     expected={str(f.relative_to(reference)):sha(f) for pattern in ('row-*/*.bf16','row-*/*.bin','draft-final-state/*.bin') for f in reference.glob(pattern)}
     observed={str(f.relative_to(dest)):sha(f) for pattern in ('row-*/*.bf16','row-*/*.bin','draft-final-state/*.bin') for f in dest.glob(pattern)}
     require(expected and expected==sealed and expected==observed,'KD draft fixture bytes differ')
     save(dest/'fixture-comparison.json',dict(passed=True,files=len(expected),sha256=expected))
     for f,digest in observed.items():receipts[f'owner{attempt}/'+f]=digest
     for f in ('receipt.json','fixture-comparison.json'):receipts[f'owner{attempt}/'+f]=sha(dest/f)
    except Exception as error:
     failed_owner(child,out,watch,error,stop_w)
     raise
  finally:
   for fd in (stop_w,stop_r):
    try:os.close(fd)
    except OSError:pass
  # Retention failure is diagnostic: keep raw bytes and preserve completed gates.
  retention_errors=[]
  for raw in [out/f'owner{attempt}.log',*dest.rglob('*.jsonl')]:
   if not raw.is_file():continue
   try:compress_completed_log(raw)
   except Exception as error:retention_errors.append(dict(path=str(raw),error=str(error),raw_evidence_retained=raw.exists()))
  if retention_errors:
   try:save(out/f'owner{attempt}-retention-errors.json',retention_errors)
   except OSError:pass
 require(len(set(pids))==2,'KD fresh owners')
 # Both fresh owners have compared every byte. Retain exact CPU receipts/logs
 # and fixture hashes in a verified archive; no later gate needs these raw bytes.
 from storage import P as storage_packet
 archive=archive_host_reference(out)
 identity=json.loads((out/'host-reference-identity.json').read_text())
 identity.update(scratch_archive=archive,host_receipt_sha256=sha(host_reference/'receipt.json'),
                 host_receipt_archive_member=str((host_reference/'receipt.json').relative_to(storage_packet)),
                 raw_fixture_retention='hashes only after both complete byte comparisons',scratch_removed=False)
 save(out/'host-reference-identity.json',identity)
 shutil.rmtree(host_reference)
 identity['scratch_removed']=True
 save(out/'host-reference-identity.json',identity)
 receipts.pop('host-reference/receipt.json')
 receipts['host-reference-identity.json']=sha(out/'host-reference-identity.json')
 receipts['host-reference.jsonl.gz']=sha(out/'host-reference.jsonl.gz')
 return receipts,pids


def compress_completed_log(raw):
 admit(raw.stat().st_size+2_000_000)
 compressed=raw.with_suffix(raw.suffix+'.gz')
 with raw.open('rb') as source,compressed.open('wb') as target:
  with gzip.GzipFile(fileobj=target,mode='wb',mtime=0) as archive:shutil.copyfileobj(source,archive,1024*1024)
 with gzip.open(compressed,'rb') as restored,raw.open('rb') as original:
  while True:
   left=original.read(1024*1024);require(left==restored.read(len(left)),'KD compressed log differs')
   if not left:require(restored.read(1)==b'','KD compressed log trailing bytes');break
 raw.unlink()
