#!/usr/bin/env python3
"""Execute the unchanged coordinator shell chain with host-only window children.

BASH_ENV intercepts only the shell's priority/env prefixes and routes window.py
into its internal CPU seam. Window arguments and dependencies come from the real
coordinator, never a copied chain. Hardware admission is mocked, real host child
launchers, receipt gates, retention, and prerequisite checks are not.
"""
import contextlib,gzip,json,os,shlex,shutil,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch
import pipeline as pp,window as w,draft_window as dw,storage
from cpu_merged_gate import assert_host_build
P=Path(__file__).resolve().parent;B=P/'build';ROOT=P.parents[3]
MATRIX=((4096,0),(4096,1),(32768,0))
WINDOWS=('K0','K1a','K1b','K2','W0p','KD','W2m','WS','WSs')
SOURCES=('coordinator_cpu_gate.py','coordinator_windows.sh','fixture_support.py','window.py','draft_window.py','pipeline.py','suite.py','suite_metrics.py','k2_summary.py','storage.py','window_safety.py','merge_dispatch.py')
def save(p,r):p.write_text(json.dumps(r,indent=2)+'\n')
def inspect(root):return {str(f.relative_to(root)):pp.sha(f) for pattern in ('row-*/*.bf16','row-*/*.bin','draft-final-state/*.bin') for f in root.glob(pattern)}
def prohibit_device(event,args):
 if event=='open' and isinstance(args[0],(str,bytes)) and os.fsdecode(args[0]).startswith('/dev/dri'):raise AssertionError('CPU gate cannot open DRM')
 if event=='subprocess.Popen':
  argv=args[1];words=list(map(str,argv)) if isinstance(argv,(list,tuple)) else [str(argv)]
  if any('/device/' in x or x in ('sudo','sycl-ls','ze_info','clinfo') for x in words):raise AssertionError('CPU gate cannot launch device/discovery: '+str(words))
class CpuWatch(w.Watch):
 def postflight(self):self.check()
def entry(case,argv):
 sys.addaudithook(prohibit_device)
 case=Path(case);private=case/'seal';build=case/'build'
 assert argv[:2]==['-B',str(P.relative_to(ROOT)/'window.py')],argv
 argv=['window.py',*argv[2:]]
 if '--input' in argv:argv[argv.index('--input')+1]=str(private/'input')
 baseline=json.loads((case/'baseline.json').read_text())
 def oracle(a,inp,steps):return {k:v for k,v in baseline['fixtures'].items() if int(k.split('/')[0][4:]) in steps},baseline['tokens']
 env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'}
 if 'LD_LIBRARY_PATH' in os.environ:env['LD_LIBRARY_PATH']=os.environ['LD_LIBRARY_PATH']
 with contextlib.ExitStack() as stack:
  for obj,key,value in ((w,'P',private),(w,'B',build),(dw,'P',private),(dw,'B',build),
    (w,'environment_gate',lambda:dict(native=env)),(w,'memory_snapshot',lambda:dict(MemAvailable=128*1024**3)),
    (w,'foreign_engines',lambda:dict(scope='CPU mock; no device discovery')),(w,'journal',lambda *a:('','cpu-cursor')),
    (w,'Watch',CpuWatch),(w,'selected_oracle',oracle),(sys,'argv',argv)):
   stack.enter_context(patch.object(obj,key,value))
  return w.main(cpu_rehearsal=True)
def host(binary,args,log):
 assert binary.parent.name=='gnu-host'
 with log.open('w') as out:r=subprocess.run([str(binary),*map(str,args)],stdout=out,stderr=subprocess.STDOUT,env={**os.environ,'OMP_NUM_THREADS':'2'},timeout=600)
 assert r.returncode==0,(log,log.read_text()[-2000:])
def run():
 sys.addaudithook(prohibit_device)
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 storage.admit(100_000_000)
 sources={n:pp.sha(P/n) for n in SOURCES};binary=B/'gnu-host/own-rt-iq3';assert_host_build(binary)
 original=json.loads((P/'build-receipt.json').read_text())
 rows=[];root=Path(tempfile.mkdtemp(prefix='coordinator-cpu-',dir=B));archive=P/'evidence/sequential-owner-fix/coordinator-chains.jsonl.gz';archive.parent.mkdir(parents=True,exist_ok=True)
 for context,rank in MATRIX:
  storage.admit(100_000_000);case=root/f'c{context}-dr{rank}';case.mkdir();private=case/'seal';private.mkdir();build=case/'build';build.mkdir()
  for name in ('gnu-host','fusion-fixtures'):(build/name).symlink_to(B/name,target_is_directory=True)
  for name in ('mtp-manifest.tsv','memory-plan.json'):(private/name).write_bytes((P/name).read_bytes())
  inp=private/'input';inp.mkdir();save(inp/'input.json',dict(tokens=[2,5,3,7,1],files={},model_dir='mini-unused'))
  baseline=case/'baseline'
  args=pp.parser().parse_args(['--binary',str(binary),'--mini','--output',str(baseline),'--max-new','64','--context',str(context),'--draft-rank',str(rank),'--controller','native','--retain-steps','1-8'])
  result=pp.run(args)
  fixtures={str(f.relative_to(baseline/f'rank{r}')):pp.sha(f) for r in (0,1) for f in (baseline/f'rank{r}').glob('step*/layer-*.bf16')}
  save(case/'baseline.json',dict(tokens=result['tokens'],fixtures=fixtures));storage.discard(baseline)
  captured=build/'captured-incident-retrospective';captured.mkdir();stream=captured/'streams.bf16';stream.write_bytes(bytes(128));table=build/'capture-incident-retrospective.tsv'
  table.write_text(''.join(f'{pos} {token} 1 {stream}\n' for pos,token in enumerate([2,5,3])))
  reference=case/'capture-reference'
  host(binary,['--mini','--pipeline-mini','--draft-capture',table,'--rank','1','--context',str(context),'--dispatch',P/'dispatch-p45.json','--output',reference,'--seconds','300'],case/'capture.log')
  save(private/'capture-input-incident-retrospective.json',dict(table_sha256=pp.sha(table),streams={'streams.bf16':pp.sha(stream)}))
  save(private/f'capture-run-incident-retrospective-c{context}.json',dict(output=str(reference),binary_sha256=pp.sha(binary),table_sha256=pp.sha(table)))
  # Private pre-seal identity: real current host binaries and current harness
  # sources, with miniature inputs only. It cannot authorize a device window.
  receipt=dict(original,sources={str((P/n).relative_to(ROOT)):v for n,v in sources.items()},
   artifacts_sha256={n:h for n,h in original['artifacts_sha256'].items() if n.startswith('gnu-host/')},
   input_sha256=pp.sha(inp/'input.json'),draft_capture_fixture_sha256_by_context={str(context):inspect(reference)},
   draft_capture_input_sha256={'incident-retrospective':pp.sha(private/'capture-input-incident-retrospective.json')})
  save(private/'build-receipt.json',receipt)
  manifest=case/'suite.json';save(manifest,dict(arithmetic='iq3-p17-detmath-v2',token_cap=128,context=context,complete=False,prompts=[dict(prompt_id=name,input_bundle='mini-unused',mini_tokens=tokens,mini_count=128) for name,tokens in [('code-review',[2,5,3,7,1]),('customer-email',[1,2,1])]]))
  bootstrap=case/'bash-env'
  bootstrap.write_text('nice() { [[ "$1 $2" == "-n 19" ]] || return 92; shift 2; "$@"; }\nionice() { [[ "$1 $2" == "-c 3" ]] || return 93; shift 2; "$@"; }\nenv() { [[ "$1" == "-i" ]] || return 94; shift; [[ "$1" == "PATH=/usr/bin:/bin" ]] || return 95; shift; [[ "$1" == LD_LIBRARY_PATH=* ]] || return 96; local packet45_ld="$1"; shift; [[ "$1" == python3 ]] || return 97; shift; command /usr/bin/env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 "$packet45_ld" /usr/bin/python3 -B '+shlex.quote(str(P/'coordinator_cpu_gate.py'))+' --entry '+shlex.quote(str(case))+' "$@"; }\n')
  output=build/'chain';command=['bash',str(P/'coordinator_windows.sh'),'0',str(context),str(rank),str(manifest),str(output)]
  with (case/'coordinator.log').open('w') as log:r=subprocess.run(command,cwd=ROOT,env={**os.environ,'BASH_ENV':str(bootstrap),'LD_LIBRARY_PATH':os.environ.get('LD_LIBRARY_PATH','')},stdout=log,stderr=subprocess.STDOUT)
  assert r.returncode==0,(case,(case/'coordinator.log').read_text()[-3000:])
  windows=[]
  for name in WINDOWS:
   path=output/name/'window.json';row=json.loads(path.read_text());assert row['passed'] and row['cpu_rehearsal'] and row['device_executed'] is False,(name,row.get('error'))
   assert (row['context'],row['draft_rank'])==(context,rank)
   if name=='K2':assert row['device_timing_qualified'] is False
   try:w.prerequisites(path,name,row)
   except ValueError as error:assert 'CPU rehearsal cannot authorize device work' in str(error)
   else:raise AssertionError('CPU chain admitted device prerequisite')
   windows.append(dict(window=name,sha256=pp.sha(path),passed=True,device_executed=False))
  assert not (build/'FAULT.json').exists()
  rows.append(dict(context=context,draft_rank=rank,passed=True,windows=windows,command=command))
  print('PASS coordinator',context,rank,','.join(WINDOWS),flush=True)
 # Preserve all window/native receipts and logs, verify archive before removing
 # only this newly-created scratch. Binary outputs remain hash-bound in archive.
 retained=storage.archive_files([f for f in root.rglob('*') if f.is_file() and not f.is_symlink()],archive)
 assert sources=={n:pp.sha(P/n) for n in SOURCES}
 report=dict(passed=True,device_executed=False,rows=rows,source_sha256=sources,archive=retained,
  host_binary_sha256=pp.sha(binary),scope='exact coordinator_windows.sh; real host children and unmocked receipt/prerequisite/summary gates',
  limitations=['Hardware admission mocks and private miniature input/seal','K0 structural shim; no JIT executed','K1/K2 validate-only; arithmetic gates separate','CPU K2 zero timestamps must fail device timing','Miniature model suites; no device quality or speed claim'])
 save(P/'coordinator-chain-gates.json',report);shutil.rmtree(root)
 return report
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='--entry':raise SystemExit(entry(sys.argv[2],sys.argv[3:]))
 run()
