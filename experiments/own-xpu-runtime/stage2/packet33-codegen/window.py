#!/usr/bin/env python3
"""Coordinator-only K0/K2. This script was prepared, never run on a device here."""
import argparse,hashlib,importlib.util,json,os,re,signal,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent
FAULT=re.compile(r'Fault response|CAT error|engine reset|GPU.*coredump|device.*coredump',re.I)
ALLOWED={'HOME','PATH','LANG','LC_ALL','LC_CTYPE','OMP_NUM_THREADS','LD_LIBRARY_PATH','TMPDIR'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def helper(a):return ['nice','-n','19','ionice','-c','3',*map(str,a)]
def journal(cursor=None):
 a=['journalctl','-k','--no-pager','--show-cursor']+(['--after-cursor',cursor] if cursor else ['-n','1'])
 r=subprocess.run(helper(a),capture_output=True,text=True,timeout=5)
 if r.returncode:raise RuntimeError('journal preflight/read failed')
 lines=r.stdout.splitlines();c=[l[11:] for l in lines if l.startswith('-- cursor: ')]
 if not c and not cursor:raise RuntimeError('missing journal cursor')
 return '\n'.join(l for l in lines if not l.startswith('-- cursor: ')),c[-1] if c else cursor

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--authorized-device-window',action='store_true');ap.add_argument('--window',choices=['K0','K2'],required=True);ap.add_argument('--card',type=int,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--k0',type=Path);a=ap.parse_args()
 if not a.authorized_device_window:raise ValueError('coordinator authorization required')
 if os.getpriority(os.PRIO_PROCESS,0)!=19 or os.environ.get('OMP_NUM_THREADS')!='2':raise ValueError('nice19 OMP2 required')
 if set(os.environ)-ALLOWED:raise ValueError('use documented env -i allowlist; unexpected keys '+str(sorted(set(os.environ)-ALLOWED)))
 for name in ('HOME','TMPDIR'):
  path=Path(os.environ.get(name,'/')).resolve()
  if not path.is_relative_to(P/'build'):raise ValueError(name+' must be below packet33/build')
  path.mkdir(parents=True,exist_ok=True)
 if not 0<=a.card<=3:raise ValueError('card0..3')
 out=a.output.resolve()
 if not out.is_relative_to(P/'build') or out.exists():raise ValueError('fresh output below packet33/build required')
 binaries={name:sha(P/'build'/name) for name in ('p33-k0','p33-timing')}
 seal=json.loads((P/'build-receipt.json').read_text())
 if binaries!=seal['native_binary_sha256']:raise ValueError('native binary changed')
 for name,digest in seal['source_sha256'].items():
  if sha(P/name)!=digest:raise ValueError('sealed source changed '+name)
 boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 if a.window=='K2':
  if not a.k0:raise ValueError('K0 receipt required')
  k0=json.loads(a.k0.read_text())
  if not k0.get('passed') or any(k0.get(k)!=v for k,v in dict(boot_id=boot,card=a.card,native_binary_sha256=binaries,environment=dict(os.environ)).items()):raise ValueError('K0 identity mismatch')
 binary=P/'build'/('p33-k0' if a.window=='K0' else 'p33-timing')
 dep=subprocess.run(helper(['ldd',binary]),capture_output=True,text=True,timeout=15)
 if dep.returncode or 'not found' in dep.stdout:raise ValueError('ldd preflight failed '+dep.stdout+dep.stderr)
 _,cursor=journal();out.mkdir(parents=True);(out/'run').mkdir()
 expected=60 if a.window=='K0' else 180;watchdog=max(300,4*expected)
 row=dict(schema='packet33.window.v1',window=a.window,passed=False,card=a.card,boot_id=boot,native_binary_sha256=binaries,environment=dict(os.environ),expected_seconds=expected,expectation_enforced=False,watchdog_seconds=watchdog,ldd=dep.stdout,device_accessed=True,kernel_execution=a.window=='K2',device_executed=a.window=='K2')
 command=helper([binary,'--authorized-device-window','--card',a.card,'--output',out/'run'])
 command+=['--cards','1'] if a.window=='K0' else ['--repetitions','200','--fixtures',P.parent/'packet29-merged/build/fusion-fixtures']
 row['command']=command;requested=[];sent=None
 for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda s,f:requested.append('coordinator signal'))
 def persist(): (out/'window.json').write_text(json.dumps(row,indent=2)+'\n')
 persist();start=time.monotonic()
 with (out/'stdout.txt').open('w') as log,(out/'kernel.txt').open('w') as kernel:
  child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ));row['pid']=child.pid;persist()
  while child.poll() is None:
   try:
    fresh,cursor=journal(cursor);kernel.write(fresh+'\n');kernel.flush()
    if FAULT.search(fresh):requested.append('new GPU fault; coordinator recovery required')
   except Exception as e:requested.append(str(e))
   if time.monotonic()-start>=watchdog:requested.append('watchdog')
   if requested and sent is None:
    row['stop_reasons']=requested;persist();child.send_signal(signal.SIGTERM);sent=time.monotonic()
   if sent and time.monotonic()-sent>=360:
    row.update(child_retained=True,passed=False);persist();return 1
   time.sleep(.25)
 row['returncode']=child.returncode;row['elapsed_seconds']=time.monotonic()-start
 try:
  fresh,cursor=journal(cursor);(out/'postflight-kernel.txt').write_text(fresh)
  if FAULT.search(fresh):requested.append('postflight fault')
  receipt=json.loads((out/'run/receipt.json').read_text())
  if child.returncode or requested or not receipt.get('passed'):raise ValueError('window failed '+str(requested))
  if a.window=='K2':
   import summarize
   summary=summarize.summarize(out/'run');row['summary_sha256']=sha(out/'run/summary.json')
  row['passed']=True
 except Exception as e:row['error']=str(e)
 persist();return 0 if row['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
