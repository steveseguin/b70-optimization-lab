"""Coordinator KD: two fresh owners, complete captured draft rows, byte comparisons."""
import json,os,subprocess,time
from pathlib import Path
from pipeline import P,sha,require,save
B=P/'build'
def run(a,out,env,watch,build):
 source=json.loads((P/'capture-run-incident-retrospective.json').read_text());reference=Path(source['output'])
 require(source['binary_sha256']==build['artifacts_sha256']['gnu-host/own-rt-iq3'],'KD CPU reference binary identity')
 table=B/'capture-incident-retrospective.tsv'
 require(sha(table)==source['table_sha256'],'KD table identity')
 require(source['table_sha256']==json.loads((P/'capture-input-incident-retrospective.json').read_text())['table_sha256'],'KD sealed table identity')
 inp=json.loads((a.input/'input.json').read_text())
 from fixture_support import ldd_preflight
 ldd_preflight(B/'device/own-rt-iq3')
 sealed=build['draft_capture_fixture_sha256']['incident-retrospective']
 for name,digest in sealed.items():require(sha(reference/name)==digest,'KD CPU fixture changed')
 require(sha(P/'capture-input-incident-retrospective.json')==build['draft_capture_input_sha256']['incident-retrospective'],'KD input receipt changed')
 captured=json.loads((P/'capture-input-incident-retrospective.json').read_text())
 for name,digest in captured['streams'].items():require(sha(B/'captured-incident-retrospective'/name)==digest,'KD input stream changed')
 receipts={};pids=[]
 for attempt in range(2):
  watch.last=0.;watch.check()
  dest=out/f'owner{attempt}';stop_r,stop_w=os.pipe()
  cmd=[str(B/'device/own-rt-iq3'),'--authorized-device-window','--card',str(a.card+1),'--rank','1',
       '--stop-fd',str(stop_r),'--draft-capture',str(table),'--context','256','--plan',str(a.input/'plan.tsv'),
       '--identity',str(a.input/'identity.tsv'),'--model-dir',inp['model_dir'],'--output',str(dest),
       '--dispatch',str(a.dispatch),'--seconds','10800']
  with (out/f'owner{attempt}.log').open('w') as log:
   child=subprocess.Popen(['ionice','-c','3']+cmd,env=env,stdout=log,stderr=subprocess.STDOUT,pass_fds=(stop_r,))
   pids.append(child.pid);save(out/'children.json',dict(pids=pids,signals_sent=0))
   try:
    while child.poll() is None:
     watch.check()
     try:
      status=Path(f'/proc/{child.pid}/status').read_text()
      anon=int(next(row.split()[1] for row in status.splitlines() if row.startswith('RssAnon:')))*1024
      require(anon<8*1024**3,'KD anonymous memory exceeded8GiB')
     except FileNotFoundError:pass
     time.sleep(.1)
    require(child.returncode==0,'KD owner failed')
    result=json.loads((dest/'receipt.json').read_text());require(result['passed'] and result.get('device_executed') is True and len(result.get('teardown',[]))==1 and all(t['safe_to_exit'] and not t['in_flight'] and not t['live_bytes'] for t in result['teardown']),'KD native failure/unsafe teardown')
    expected={str(f.relative_to(reference)):sha(f) for pattern in ('row-*/*.bf16','row-*/*.bin','draft-final-state/*.bin') for f in reference.glob(pattern)}
    observed={str(f.relative_to(dest)):sha(f) for pattern in ('row-*/*.bf16','row-*/*.bin','draft-final-state/*.bin') for f in dest.glob(pattern)}
    require(expected and expected==sealed and expected==observed,'KD draft fixture bytes differ')
    save(dest/'fixture-comparison.json',dict(passed=True,files=len(expected),sha256=expected))
    for f,digest in observed.items():receipts[f'owner{attempt}/'+f]=digest
    for f in ('receipt.json','fixture-comparison.json'):receipts[f'owner{attempt}/'+f]=sha(dest/f)
   except Exception as error:
    watch.latch(error);save(out/'failure-before-teardown.json',dict(error=str(error),pid=child.pid))
    os.write(stop_w,b'!') # one cooperative request; no process signal, including load
    end=time.monotonic()+65
    while child.poll() is None and time.monotonic()<end:
     try:watch.poll_kernel()
     except Exception:pass # original failure retained; journal still polled
     time.sleep(.1)
    save(out/'retained.json',dict(pids=[child.pid] if child.poll() is None else [],signals_sent=0))
    raise
   finally:os.close(stop_w);os.close(stop_r)
 require(len(set(pids))==2,'KD fresh owners')
 return receipts,pids
