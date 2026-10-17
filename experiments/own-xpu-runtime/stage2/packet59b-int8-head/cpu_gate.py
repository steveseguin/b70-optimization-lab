#!/usr/bin/env python3
"""Lean CPU-only draft determinism and packet56 target fixture identity."""
import hashlib,json,os,subprocess
from pathlib import Path
import build
P=Path(__file__).resolve().parent;ROOT=P.parents[3];BASE=P.parent/'packet56-draft-prefix';F=P/'fixture'
def sha(x):return hashlib.sha256(x.read_bytes()).hexdigest()
def save(x,v):x.write_text(json.dumps(v,indent=2)+'\n')
def run(cmd,log):
 with log.open('w') as f:subprocess.run(list(map(str,cmd)),stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
def main():
 build.guard();F.mkdir(exist_ok=False);commands=[]
 parent=json.loads((P/'parent-binding.json').read_text())
 assert sha(BASE/'build-receipt.json')==parent['seal_sha256']
 unchanged={}
 for name,h in parent['files_sha256'].items():
  if Path(name).suffix in ('.cpp','.hpp','.inc','.bf16') and name!='mtp.hpp':
   assert sha(P/name)==h==sha(BASE/name),name
   unchanged[name]=h
 # Real production INT8 submitter, two fresh CPU processes, small representative
 # full-width fixture; raw bytes retained. No model weights are read.
 for repeat in (0,1):
  dest=F/('draft-'+str(repeat));cmd=[P/'build/gnu-host/p59b-fixtures',dest];commands.append(list(map(str,cmd)));run(cmd,F/('draft-'+str(repeat)+'.log'))
 names=('expected.bin','actual.bin','codes.bin','scales.bin','target.bin','proposal.bin')
 for name in names:assert (F/'draft-0'/name).read_bytes()==(F/'draft-1'/name).read_bytes(),name
 assert (F/'draft-0/expected.bin').read_bytes()==(F/'draft-0/actual.bin').read_bytes()
 # Actual Q6 production target logits against sealed packet56's source.
 ref=P/'build/parent-target-fixture';deps=P/'build/parent-target-fixture.d'
 cmd=['/usr/bin/g++','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-MMD','-MF',str(deps),str(P/'parent_target_fixture.cpp'),'-o',str(ref)]
 commands.append(cmd);run(cmd,F/'parent-target-compile.log');commands.append([str(ref),str(F/'parent-target.bin')]);run(commands[-1],F/'parent-target.log')
 assert (F/'parent-target.bin').read_bytes()==(F/'draft-0/target.bin').read_bytes(), 'Q6 target logits differ from packet56'
 dep_paths=[Path(word) for word in deps.read_text().replace('\\\n',' ').split(':',1)[1].split()]
 parent_reference_sources={str(x.resolve().relative_to(ROOT)):sha(x) for x in dep_paths}
 # Unchanged target engine, full miniature model, all retained layer bytes.
 prompt=F/'prompt.txt';prompt.write_text('2 5 3 7 1 9 4')
 maps=[];tokens=[]
 for label,packet in [('packet56',BASE),('packet59b',P)]:
  dest=F/(label+'-target');cmd=[packet/'build/gnu-host/own-rt-iq3','--mini','--pipeline-mini','--context','256','--max-new','8','--prompt-tokens',prompt,'--output',dest,'--dispatch',packet/'dispatch-speed6.json'];commands.append(list(map(str,cmd)));run(cmd,F/(label+'-target.log'))
  receipt=json.loads((dest/'receipt.json').read_text());assert receipt['passed'] and not receipt['device_executed'];tokens.append(receipt['tokens'])
  files=sorted(dest.glob('step*/layer-*.bf16'));assert files
  maps.append({str(x.relative_to(dest)):sha(x) for x in files})
 assert maps[0]==maps[1] and tokens[0]==tokens[1]
 # Small end-to-end placement check: exercise existing rank0 reverse handoff,
 # INT8 proposals and target verification without writing full scratch dumps.
 import pipeline as pipe
 placement=[]
 for repeat in (0,1):
  dest=F/('placement-'+str(repeat));dest.mkdir()
  argv=['--binary',str(P/'build/gnu-host/own-rt-iq3'),'--output',str(dest),'--mini','--draft','mtp','--draft-rank','1','--tokens','8','--context','256','--controller','native','--dispatch',str(P/'dispatch-speed6.json')]
  args=pipe.parser().parse_args(argv);transport=pipe.Transport.__new__(pipe.Transport)
  try:
   transport.__init__(args,dest)
   result=pipe.request_run(transport,pipe.Draft('mtp'),[2,5,3,7,1,9,4],8)
   transport.close(True)
  except BaseException as error:
   if hasattr(transport,'children'):
    transport.stop(error);transport.close(False)
   raise
  assert result['tokens']==tokens[0] and args.draft_rank==0
  layer_files={str(x.relative_to(dest/f'rank{rank}')):sha(x) for rank in (0,1) for x in sorted((dest/f'rank{rank}').glob('step*/layer-*.bf16'))}
  assert layer_files==maps[0], 'rank0-draft target fixtures differ'
  row=dict(tokens=result['tokens'],stats=result['stats'],guesses=result['guess_rows'],target_fixtures=layer_files)
  # Timing fields differ by design; proposal IDs have their own fixed record.
  proposals=[{k:r[k] for k in ('position','guess','provider_error','actual','hit') if k in r} for r in result.get('draft_rows',[])]
  assert proposals and all(r['provider_error']==0 for r in proposals)
  assert all(r['guess'] is not None for r in proposals if r['position']>=7)
  assert result['stats']['hits']>0 and result['stats']['misses']>0, 'fixture must exercise hit and ordinary miss'
  placement.append(dict(tokens=result['tokens'],stats={k:result['stats'][k] for k in ('guesses','hits','misses','no_guess')},proposals=proposals))
  save(dest/'cpu-result.json',dict(passed=True,device_executed=False,placement=placement[-1]))
 assert placement[0]==placement[1], 'fresh rank0 draft proposals differ'
 from memory_gate import configuration
 memory=configuration(json.loads((P/'memory-plan.json').read_text()),4096,0,23)
 report=dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,model_weights_read=False,
  changed_class='Draft-only row INT8 head: fixed-tree logits and argmax deterministic; unchanged packet56 target miniature layer fixtures byte-identical',
  command=commands,build_receipt_sha256=sha(P/'build-device-receipt.json'),
  host_build_receipt_sha256=sha(P/'build-gnu-host-receipt.json'),
  sources={**parent_reference_sources,str((P/'cpu_gate.py').relative_to(ROOT)):sha(P/'cpu_gate.py'),str((BASE/'build-receipt.json').relative_to(ROOT)):sha(BASE/'build-receipt.json')},
  expected=dict(path='fixture/draft-0/expected.bin',sha256=sha(F/'draft-0/expected.bin')),
  actual=dict(path='fixture/draft-0/actual.bin',sha256=sha(F/'draft-0/actual.bin')),
  fresh_processes=2,rank0_integration=placement,target_fixture_files_sha256=maps[0],target_tokens=tokens[0],
  unchanged_target_sources_sha256=unchanged,fixture_files_sha256={str(x.relative_to(P)):sha(x) for x in sorted(F.rglob('*')) if x.is_file()},
  memory_admitted_ranks=memory['ranks'],scope='CPU synthetic gate only; full-model exactness, device determinism, acceptance and speed pending coordinator')
 save(F/'receipt.json',report);print(json.dumps(dict(passed=True,target_fixtures=len(maps[0]),fresh_draft_processes=2)))
if __name__=='__main__':main()
