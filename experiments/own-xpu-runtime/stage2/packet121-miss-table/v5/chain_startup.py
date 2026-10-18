"""All eleven inherited chain argument paths for both prepared views, CPU only.

Parent helpers read their frozen inputs. Every output and mock endpoint is
redirected into this packet. No parent prepare/build/seal entry is called.
"""
import gzip,hashlib,json,os,resource,shutil,subprocess,sys,time
from pathlib import Path
from types import SimpleNamespace
P=Path(__file__).resolve().parent;ROOT=P.parents[4];BASE=P.parents[1]/'packet118-record-bundle';OUT=P/'build/chain-startup'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage('/').free>=25_000_000_000
 os.environ['OMP_NUM_THREADS']='2';OUT.mkdir(exist_ok=True)
 # Fresh interpreter: never import the parent generator under the v5 builder.
 sys.path.insert(0,str(BASE))
 import startup103 as parent
 parent.S=OUT
 import window as w
 from kd_reference import project,command
 parent_inputs={str(f.relative_to(ROOT)):sha(f) for f in BASE.glob('*.py')}
 def native(cmd):
  cmd=list(map(str,cmd));cmd[0]=str(P/'build/full-shape/fixture');cmd.insert(1,'--startup109')
  if '--authorized-device-window' in cmd:cmd.remove('--authorized-device-window')
  dest=Path(cmd[cmd.index('--output')+1]);assert dest.is_relative_to(OUT)
  r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
  if r.returncode:raise RuntimeError(r.stderr)
  result=json.loads((dest/'result.json').read_text());assert result['passed']
  # KD intentionally uses the bounded layer-streaming target shell; only its
  # DraftRuntime executes. It has no resident prepared target command list.
  if '--draft-capture' not in cmd:assert result.get('prepared',True)
  files={f.name:sha(f) for f in dest.iterdir() if f.is_file()}
  if (dest/'draft-kernel-choices.json').exists():
   draft=json.loads((dest/'draft-kernel-choices.json').read_text());draft.pop('selection_sha256');result['draft_kernel_identity']=draft
  if (dest/'census.json').exists():result['allocation_bytes']=json.loads((dest/'census.json').read_text())['totals']['device']
  shutil.rmtree(dest);return dict(command=cmd,result=result,artifacts=files)
 shared=parent.shared_fixtures();runs=[];started=time.monotonic()
 for label in ('selection','candidate'):
  target=P/'lineage'/(label+'.json')
  selected=json.loads(target.read_text());legacy=json.loads(target.read_text())
  restore=legacy['choices'].pop('restore_table')
  assert restore in ('production','p121')
  projected=project(legacy) # frozen parent still validates every original choice
  projected['choices']['restore_table']=restore
  assert projected['draft']==selected['draft']
  ref=OUT/'draft-reference-selection.json';ref.write_text(json.dumps(projected,indent=2)+'\n')
  binding=dict(reference_selection_sha256=sha(ref),target_selection_sha256=sha(target))
  # Real shared-memory W0p handshake uses the actual CPU native rank entry.
  dest=OUT/('canary-'+label);dest.mkdir()
  args=parent.model_args('W0p',target,dest);args.device=False;args.binary=P/'build/gnu-host/own-rt-iq3'
  watch=SimpleNamespace(check=lambda:None,mark_launched=lambda pid:None,latch=lambda error:None)
  w.concurrency_canary(args,dest,{'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'},watch)
  shared['W0p-protocol-'+label]=dict(files={str(f.relative_to(dest)):sha(f) for f in dest.rglob('*') if f.is_file()})
  shutil.rmtree(dest)
  inp=json.loads((BASE/'build/input/input.json').read_text())
  a=SimpleNamespace(card=0,draft_rank=1,context=4096,input=BASE/'build/input',dispatch=BASE/'dispatch-speed6.json')
  for name in parent.WINDOWS:
   parent.window_options(name);row=dict(view=label,window=name)
   if name in shared:row['shared_fixture']=name
   elif name=='KD':
    row['host']=native(command(OUT/'unused',a,BASE/'oracle/results/capture-incident-retrospective.tsv',inp,OUT/'scratch',ref,binding['reference_selection_sha256'],-1))
    row['device_arguments_on_cpu']=native(command(OUT/'unused',a,BASE/'oracle/results/capture-incident-retrospective.tsv',inp,OUT/'scratch',ref,binding['reference_selection_sha256'],-1,device=True))
   else:row['ranks']=[native(cmd) for cmd in parent.rank_commands(name,target)]
   runs.append(row)
  kd=next(r for r in runs if r['view']==label and r['window']=='KD')['host']['result']['draft_kernel_identity']
  for row in runs:
   if row['view']!=label:continue
   for rank in row.get('ranks',[]):
    if 'draft_kernel_identity' in rank['result']:assert rank['result']['draft_kernel_identity']==kd
  print(label,'all eleven actual startup argument paths PASS',flush=True)
 assert len(runs)==22
 assert all(sha(ROOT/n)==h for n,h in parent_inputs.items()),'frozen parent changed'
 result=dict(passed=True,device_executed=False,total_windows=len(runs),views=2,windows_per_view=11,shared_fixtures=shared,runs=runs,seconds=time.monotonic()-started,sources={**parent_inputs,**{str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),P/'build/full-shape/fixture',P/'build/gnu-host/own-rt-iq3',P/'lineage/selection.json',P/'lineage/candidate.json']}},scope='real inherited chain parsers/argv, CPU owner fixtures, W0p native handshake and production-shape target/draft constructors; numerical allocations and weight payloads mocked')
 raw=json.dumps(result,sort_keys=True).encode();archive=P/'evidence/chain-startup.json.gz';archive.write_bytes(gzip.compress(raw,mtime=0))
 (P/'evidence/chain-startup.json').write_text(json.dumps(dict(passed=True,device_executed=False,total_windows=22,archive=str(archive.relative_to(ROOT)),archive_sha256=sha(archive),sources=result['sources']),indent=2)+'\n')
if __name__=='__main__':main()
