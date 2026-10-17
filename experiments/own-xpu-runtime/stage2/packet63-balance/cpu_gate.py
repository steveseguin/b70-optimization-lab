#!/usr/bin/env python3
"""Lean host-only target, draft repeat and strict selection gates."""
import copy,hashlib,json,os,subprocess
from pathlib import Path
import pipeline
from build_engine import limits,sha,save
from prepare_selections import configs,CHOICES
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build';E=P/'evidence'
def canonical(v):return (json.dumps(v,sort_keys=True,indent=2)+'\n').encode()
def host(binary):
 links=subprocess.check_output(['readelf','-d',str(binary)],text=True).lower()
 assert not any(s in links for s in ('libsycl','libze_loader','libur_loader','libopencl'))
def run_one(label,binary,selection=None):
 host(binary);dest=B/('cpu-'+label)
 pipeline.P=P if selection is None else P/'selections'/selection
 args=pipeline.parser().parse_args(['--binary',str(binary),'--output',str(dest),'--mini','--context','256','--tokens','24','--seconds','180','--wait-seconds','120','--native-nice','19','--draft','mtp','--draft-rank','1','--controller','native','--timing','token','--retain-steps','1-24'])
 args.host_memory='resident';args.draft='mtp'
 if selection:args.selection_sha256=sha(pipeline.P/'selection.json')
 result=pipeline.run(args);assert result['passed'],result.get('error')
 fixtures={str(f.relative_to(dest)):sha(f) for rank in ('rank0','rank1') for f in (dest/rank).glob('step*/layer-*.bf16')};assert len(fixtures)==96
 target=dict(tokens=result['tokens'],fixtures=fixtures);assert len(target['tokens'])==24
 proposals=[row['guess'] for line in (dest/'rank1/draft-rows.jsonl').read_text().splitlines() if 'guess' in (row:=json.loads(line))];assert len(proposals)>=24
 states={str(f.relative_to(dest/'rank1/draft-final-state')):sha(f) for f in (dest/'rank1/draft-final-state').rglob('*') if f.is_file()}
 # State raw bytes only: metadata may contain monotonic timestamps or path names.
 states={k:v for k,v in states.items() if k.endswith(('.bin','.bf16','.f32','.u32'))}
 choices=json.loads((dest/'rank1/draft-kernel-choices.json').read_text())
 if selection:assert choices['choices']==configs()[selection]['draft'] and choices['selection_sha256']==args.selection_sha256
 identity=dict(target=target,proposals=proposals,draft_state=states)
 save(E/(label+'.json'),identity)
 if selection:save(E/(label+'-choices.json'),choices)
 return identity,dict(label=label,binary_sha256=sha(binary),target_fixture_count=len(fixtures),target_token_count=len(target['tokens']),draft_proposal_count=len(proposals),draft_state_files=len(states),identity_sha256=sha(E/(label+'.json')))
def parser_tests():
 # Link the actual new parser object and inherited host support, no GPU library.
 source=B/'selection-fixture.cpp';source.write_text('#include "p49d_submit.hpp"\n#include <iostream>\nint main(int argc,char**argv){try{if(argc!=3 || !*argv[2])return 2;p49d::Selection s;s.load(argv[1],argv[2]);return 0;}catch(const std::exception&e){std::cerr<<e.what();return 1;}}\n')
 commands=json.loads((P/'engine-commands.json').read_text());cc=next(r['command'] for r in commands if r['name']=='gnu-host-entry-main');cc=cc[:cc.index('-o')]+['-o',str(B/'selection-fixture.o'),'-c',str(source)]
 link=list(next(r['command'] for r in commands if r['name']=='gnu-host-link'))
 link=[x for x in link if not x.endswith('own-rt-iq3-entry.cpp.o')]
 link=[str(B/'selection-fixture.o') if x==str(B/'gnu-host/entry-main.o') else x for x in link];link[link.index('-o')+1]=str(B/'selection-fixture')
 for cmd in (cc,link):
  r=subprocess.run(cmd,text=True,capture_output=True);assert r.returncode==0,r.stderr
 host(B/'selection-fixture');rows=[]
 good=configs()['draft-hc']
 cases=[('control',json.dumps(configs()['control']),None,True),('draft-hc',json.dumps(good),None,True)]
 for name,change in [('target',lambda x:x['choices'].update(route='production')),('missing',lambda x:x['draft'].pop('hc_a_low')),('unknown',lambda x:x['draft'].update(surprise='production')),('bad-value',lambda x:x['draft'].update(hc_a_low='fast')),('fusion',lambda x:x['draft'].update(hc_a_low='production'))]:
  bad=copy.deepcopy(good);change(bad);cases.append((name,json.dumps(bad),None,False))
 raw=json.dumps(good);cases.extend([('duplicate',raw.replace('"hc_a_low": "packet59"','"hc_a_low": "packet59", "hc_a_low": "production"'),None,False),('trailing',raw+'x',None,False),('wrong-hash',raw,'0'*64,False),('missing-hash',raw,'',False)])
 path=B/'selection-test.json'
 for name,text,digest,valid in cases:
  path.write_text(text);r=subprocess.run([str(B/'selection-fixture'),str(path),sha(path) if digest is None else digest],capture_output=True,text=True,timeout=10)
  assert (r.returncode==0)==valid,(name,r.stderr);rows.append(dict(name=name,accepted=valid))
 save(E/'selection-tests.json',dict(passed=True,device_executed=False,cases=rows,binary_sha256=sha(B/'selection-fixture'),source_sha256=sha(source),compile_command=cc,link_command=link))
def main():
 limits();assert not list((P/'selections').glob('*/screen-seal.json'))
 build=json.loads((P/'build-device-receipt.json').read_text());assert build['passed']
 for n,h in build['artifacts'].items():assert sha(P/n)==h
 baseline,base_row=run_one('packet56',P.parent/'packet56-draft-prefix/build/gnu-host/own-rt-iq3')
 parent,parent_row=run_one('packet61x',P.parent/'packet61x-spin-hcfusion-wait/build/gnu-host/own-rt-iq3')
 assert baseline['target']==parent['target'];rows=[base_row,parent_row]
 for name in CHOICES:
  values=[]
  for suffix in ('a','b'):
   value,row=run_one(name+'-'+suffix,B/'gnu-host/own-rt-iq3',name)
   assert value['target']==baseline['target'],'packet56 target fixture/token mismatch'
   values.append(value);rows.append(row)
  assert values[0]==values[1],'fresh-process draft nondeterminism'
  if name=='control':assert values[0]==parent,'control changes packet61x draft/target'
  (E/(name+'-expected.bin')).write_bytes(canonical(values[0]))
  (E/(name+'-actual.bin')).write_bytes(canonical(values[1]))
  print(name,'96 target fixtures + 24 tokens exact; fresh draft repeat PASS',flush=True)
 for suffix in ('a','b'):
  subprocess.run([str(B/'draft-fixture'),str(E/('draft-production-'+suffix+'.bin'))],check=True,timeout=60)
 assert sha(E/'draft-production-a.bin')==sha(E/'draft-production-b.bin')
 parser_tests()
 sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'cpu_gate.py',P/'prepare_selections.py',P/'pipeline.py',P/'p59_fixture.cpp',P/'p59c_dense_fixture.cpp',P.parent/'packet59c-draft-select/selections/screen2-hc.json')}
 for f in E.iterdir():
  if f.is_file() and f.name not in ('cpu-gates.json',):sources[str(f.relative_to(ROOT))]=sha(f)
 save(E/'cpu-gates.json',dict(schema='packet63.lean-cpu-gates.v1',passed=True,device_executed=False,model_weights_read=False,build_receipt_sha256=sha(P/'build-device-receipt.json'),selections=list(CHOICES),rows=rows,sources=sources,draft_production_fixture_sha256=sha(E/'draft-production-a.bin'),limitations='Small BF16 target fixture + synthetic production-width draft arithmetic. Full model device parity, repeat determinism, acceptance and speed pending coordinator screen/chain.'))
 print('All lean CPU gates PASS',flush=True)
if __name__=='__main__':main()
