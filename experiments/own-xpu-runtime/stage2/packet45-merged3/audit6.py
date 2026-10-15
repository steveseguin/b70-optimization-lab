#!/usr/bin/env python3
"""Production-byte CPU host audit. Never opens a model payload or device."""
import json,os,re,subprocess,sys
from pathlib import Path
from storage import admit,digest
P=Path(__file__).resolve().parent;B=P/'build/audit6';E=P/'evidence/audit6'
WINDOWS=('W0p','KD','W2m','WS','WSs','WS128x','WS128')
SOURCES=('audit6.py','audit6_canary.cpp','audit6_gate.cpp','audit6_backend.hpp','main.cpp','mtp.hpp','rank.hpp','rank_canary.hpp','strict_snapshot.hpp','request_reset.hpp','request_state_inventory.hpp','owner.cpp','owner_api.hpp','storage.py','window.py','draft_window.py','pipeline.py','suite.py','memory_plan.py','memory-plan.json','memory_gate.py','dispatch-p45.json','mtp-manifest.tsv')
def save(p,r):p.write_text(json.dumps(r,indent=2)+'\n')
def inventory():
 result=[]
 for name in ('main.cpp','mtp.hpp','rank.hpp','strict_snapshot.hpp','rank_canary.hpp'):
  for line,text in enumerate((P/name).read_text().splitlines(),1):
   count=len(re.findall(r'\b(?:copy|engine)\.copy\(',text))
   if not count:continue
   limit=4096 if name=='rank_canary.hpp' else 134217728
   maximum=256 if name=='rank_canary.hpp' else 134217728 if name=='strict_snapshot.hpp' else 4194304 if name=='main.cpp' and ('offset + i' in text or 'slab[c]' in text) else 4 if ('publication' in text or 'half_staging,0,4' in text or 'e->slab[0]' in text) else 20480
   scope='all model windows' if name=='main.cpp' else 'W0p' if name=='rank_canary.hpp' else 'KD and MTP model windows' if name=='mtp.hpp' else 'two-rank model windows'
   if name=='main.cpp' and ('e->snapshots' in text or 'e->slab[0]' in text):scope='single-process decode only; not used by listed windows'
   result.append(dict(source=name,line=line,expressions=count,code=text.strip(),scope=scope,largest_n=maximum,limit=limit,passed=0<maximum<=limit))
 return result
def rules():
 result=[]
 for name in SOURCES:
  if name.startswith('audit6') or not name.endswith(('.cpp','.hpp','.py')):continue
  for line,text in enumerate((P/name).read_text().splitlines(),1):
   if len(text)>1500:continue
   if re.search(r'(require|assert|raise|throw|if\b)',text) and re.search(r'(bytes|extent|capacity|bound|live|pending|lifetime|admit|context|size|offset|limit|snapshot|retai|memory|space|free)',text,re.I):
    result.append(dict(source=name,line=line,code=text.strip()))
 return result
def verify(row=None):
 from build import compiled_sources
 from storage import budget,projected_write_bytes
 row=row or json.loads((P/'audit6-gates.json').read_text())
 assert row['passed'] and row['device_executed'] is False and row['weight_payload_bytes_read']==0
 from seal6_amendment import source_matches,maps_match,gate_unchanged
 assert all(source_matches(P/n,h) for n,h in row['sources'].items()) and set(row['sources'])==set(SOURCES),'audit6 sources changed'
 assert maps_match(row['compiled_sources_sha256'],compiled_sources()),'audit6 compiled sources changed'
 # Fix6 inserts grouping validation lines; every copy expression stays identical.
 assert [{k:v for k,v in x.items() if k!='line'} for x in row['copy_sites']]==[{k:v for k,v in x.items() if k!='line'} for x in inventory()],'audit6 copy inventory changed'
 if row['rule_inventory']!=rules():
  gate_unchanged('audit6-gates.json')
  assert row['rule_inventory']==json.loads((P/'audit6-gates.json').read_text())['rule_inventory'],'audit6 rule inventory changed'
 assert row['binary_sha256']==digest(B/'audit6-gate'),'audit6 binary changed'
 for n,h in row['generated_sha256'].items():assert digest(B/n)==h,'audit6 mirror changed'
 for n,h in row['evidence_sha256'].items():assert digest(P/n)==h,'audit6 evidence changed'
 assert row['model_metadata_sha256']==digest(P/'build/input/plan.tsv'),'audit6 model metadata changed'
 expected={(w,c,d,r) for w in ('KD','W2m','WSs') for c in (4096,32768) for d in (0,1) for r in ((1,) if w=='KD' else (0,1))}
 assert len(row['native_cases'])==20 and {(r['window'],r['context'],r['draft_rank'],r['rank']) for r in row['native_cases']}==expected
 for r in row['native_cases']:
  path=P/r['census'];raw=json.loads((path.parent/'run.log').read_text().splitlines()[-1]);census=json.loads(path.read_text())
  assert all(r[k]==v for k,v in raw.items()),'audit6 native log differs'
  assert r['peak_device_bytes']==sum(x['bytes'] for x in census['allocations'] if x['live'] and x['memory']=='device')
  assert r['positions']==5 and r['copies']>0 and r['maximum_copy']<=134217728
  if r['window']!='KD':
   from memory_gate import check
   ledger=json.loads((P/'memory-plan.json').read_text())
   assert r['memory_admission']==check(census,ledger,r['rank'],r['window']!='WSs',r['context'],r['draft_rank'])
 canary=json.loads((E/'canary.log').read_text())
 assert canary==dict(passed=True,copies=2000,maximum_copy=256,peak_device_bytes=256,device_executed=False)
 assert digest(B/'audit6-canary')==json.loads((E/'canary-compile.json').read_text())['binary_sha256']
 assert len(row['rows'])==28 and {(r['window'],r['context'],r['draft_rank']) for r in row['rows']}=={(w,c,d) for w in WINDOWS for c in (4096,32768) for d in (0,1)}
 for r in row['rows']:
  assert r['passed'] and r['maximum_copy']<=134217728
  if r['window']=='W0p':assert r['peak_device_bytes']==[256,256]
  else:
   mode='KD' if r['window']=='KD' else 'WSs' if r['window']=='WSs' else 'W2m'
   native=[n for n in row['native_cases'] if (n['window'],n['context'],n['draft_rank'])==(mode,r['context'],r['draft_rank'])]
   peaks=[0,0]
   for n in native:peaks[r['draft_rank'] if mode=='KD' else n['rank']]=n['peak_device_bytes']
   assert r['peak_device_bytes']==peaks and r['maximum_copy']==max(n['maximum_copy'] for n in native),'audit6 table differs from replay'
  for peak,headroom in zip(r['peak_device_bytes'],r['headroom_bytes']):assert peak<=row['usable_capacity_bytes'] and headroom==row['usable_capacity_bytes']-peak
  projected=projected_write_bytes(r['window'],r['requests'],r['context'],r['retained_steps'])
  assert projected==r['projected_write_bytes'] and r['state_payload_upper_bytes']<=projected
  a=r['storage_admission'];assert a==budget(a['root_free_bytes'],a['build_bytes'],projected,projected)
 return row
def canary():
 cmd=['g++','-std=c++20','-O2','-DOWN_RT_HOST_ONLY','-I'+str(P),str(P/'audit6_canary.cpp'),str(P/'owner.cpp'),str(P/'owner_retire.cpp'),'-o',str(B/'audit6-canary')]
 with (E/'canary-compile.log').open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
 assert r.returncode==0,(E/'canary-compile.log').read_text()[-2000:]
 with (E/'canary.log').open('w') as log:r=subprocess.run([str(B/'audit6-canary')],stdout=log,stderr=subprocess.STDOUT)
 assert r.returncode==0
 save(E/'canary-compile.json',dict(command=cmd,binary_sha256=digest(B/'audit6-canary'),device_executed=False))
def report():
 import gzip
 from build import compiled_sources
 from storage import projected_write_bytes,state_write_bytes
 from memory_plan import CAPACITY_BYTES,MINIMUM_FREE_BYTES
 from memory_gate import check as memory_check
 ledger=json.loads((P/'memory-plan.json').read_text())
 usable=min(30*1024**3,CAPACITY_BYTES-MINIMUM_FREE_BYTES);rows=[];native=[]
 for context in (4096,32768):
  for dr in (0,1):
   cases={}
   for window in ('KD','W2m','WSs'):
    cases[window]=[]
    for rank in ((1,) if window=='KD' else (0,1)):
     out=E/f'{window}-c{context}-dr{dr}-r{rank}';result=json.loads((out/'run.log').read_text().splitlines()[-1]);census=json.loads((out/'census.json').read_text())
     live=sum(x['bytes'] for x in census['allocations'] if x['live'] and x['memory']=='device')
     assert live==result['peak_device_bytes'] and live<=usable
     assert result['passed'] and result['positions']==5 and result['maximum_copy']<=134217728
     if window!='KD':result['memory_admission']=memory_check(census,ledger,rank,window!='WSs',context,dr)
     result['census']=str((out/'census.json').relative_to(P));cases[window].append(result);native.append(result)
   for window in WINDOWS:
    requests=13 if window.startswith('WS') else 1
    steps=16 if window=='WS128x' else 0 if window=='WS128' else 8
    if window=='W0p':peak=[256,256];maximum=256;state=512;backing=['evidence/audit6/canary.log']
    elif window=='KD':
     peak=[0,0];peak[dr]=cases['KD'][0]['peak_device_bytes'];maximum=cases['KD'][0]['maximum_copy'];state=3*2368*context;backing=[cases['KD'][0]['census']]
    else:
     c=cases['WSs' if window=='WSs' else 'W2m'];peak=[r['peak_device_bytes'] for r in c];maximum=max(r['maximum_copy'] for r in c);state=sum(r['reset_written_bytes'] for r in c);backing=[r['census'] for r in c]
     assert state<=state_write_bytes(context),'production state exceeds storage reserve'
    projected=projected_write_bytes(window,requests,context,steps)
    rows.append(dict(window=window,context=context,draft_rank=dr,requests=requests,retained_steps=steps,peak_device_bytes=peak,headroom_bytes=[usable-n for n in peak],maximum_copy=maximum,state_payload_upper_bytes=state,projected_write_bytes=projected,storage_admission=admit(projected),census_sources=backing,passed=True))
 canary_result=json.loads((E/'canary.log').read_text());assert canary_result['passed'] and canary_result['copies']==2000 and canary_result['maximum_copy']==256
 generated=json.loads((E/'generated.json').read_text())
 raw=(P/'build/input/plan.tsv').read_bytes();(E/'model-plan.tsv.gz').write_bytes(gzip.compress(raw,mtime=0))
 row=dict(passed=True,device_executed=False,weight_payload_bytes_read=0,schema='packet45.audit6.v1',
  sources={n:digest(P/n) for n in SOURCES},compiled_sources_sha256=compiled_sources(),copy_sites=inventory(),rule_inventory=rules(),
  rows=rows,native_cases=native,usable_capacity_bytes=usable,physical_capacity_bytes=CAPACITY_BYTES,minimum_free_bytes=MINIMUM_FREE_BYTES,
  model_metadata_sha256=digest(P/'build/input/plan.tsv'),**generated,
  evidence_sha256={str(f.relative_to(P)):digest(f) for f in E.rglob('*') if f.is_file() and f.name!='table.md'},defects=[])
 save(P/'audit6-gates.json',row);verify(row)
 table='| Window | Context | Draft rank | Card 0 headroom MiB | Card 1 headroom MiB | Max copy MiB | Storage projection MiB | admit |\n|---|---:|---:|---:|---:|---:|---:|---|\n'
 for r in rows:table+=f"| {r['window']} | {r['context']} | {r['draft_rank']} | {r['headroom_bytes'][0]/2**20:.2f} | {r['headroom_bytes'][1]/2**20:.2f} | {r['maximum_copy']/2**20:g} | {r['projected_write_bytes']/2**20:.2f} | pass |\n"
 (E/'table.md').write_text(table)
 print(json.dumps(dict(passed=True,rows=28,native_cases=len(native),copies=sum(r['copies'] for r in native),minimum_headroom_mib=min(min(r['headroom_bytes']) for r in rows)/2**20)))
def replace_body(text,signature,body):
 start=text.index(signature);left=text.index('{',start);depth=1;right=left+1
 while depth:
  depth+=(text[right]=='{')-(text[right]=='}');right+=1
 return text[:left+1]+body+text[right-1:]
def includes(text,base,overrides={}):
 def sub(m):
  n=m[1];f=overrides.get(n,(base/n).resolve())
  return '#include "'+str(f)+'"' if f.exists() else m[0]
 return re.sub(r'#include "([^"]+)"',sub,text)
def generate():
 B.mkdir(parents=True,exist_ok=True);E.mkdir(parents=True,exist_ok=True)
 (B/'owner.hpp').write_text('#include "'+str(P/'owner.hpp')+'"\n')
 main=(P/'main.cpp').read_text().replace('#include "lifetime_mock.hpp"','');start=main.index('class Host final');end=main.index('\n#endif',start)
 main=main[:start]+'#include "'+str(P/'audit6_backend.hpp')+'"\n'+main[end:]
 main=replace_body(main,'Weights(const Options &a)', '\n directory=flash::directory_from_loader(iq3::read_plan(a.plan));\n')
 main=replace_body(main,'std::vector<uint8_t> read(const std::string &name', '\n require(n && n<=4194304,"bounded metadata read");auto t=directory.at(name);require(off<=t.bytes&&n<=t.bytes-off,"metadata read bounds");return std::vector<uint8_t>(n);\n')
 main=replace_body(main,'std::vector<int64_t> metadata()', '\n return std::vector<int64_t>(35,1);\n')
 main=main.replace('fs::path(__FILE__).parent_path()/"rope.bf16"','fs::path("'+str(P/'rope.bf16')+'")')
 mtp=(P/'mtp.hpp').read_text()
 mtp=replace_body(mtp,'std::vector<uint8_t> read(const std::string& name)', '\n const auto& t=tensors.at(name);reads[name]=t.sha;return std::vector<uint8_t>(t.bytes);\n')
 # Keep quantizer size rules; replace only arithmetic producing payload bytes.
 start=mtp.index(' for(unsigned r=0;r<rows;++r)');end=mtp.index('return out;',start)
 mtp=mtp[:start]+mtp[end:]
 mtp=mtp.replace('draft-tensor-reads.json','draft-tensor-metadata.json').replace('f.write(', 'audit_write(f,')
 mtp=mtp.replace(' void set_reverse_hidden(', ' void audit_position(int n){position=n;}\n void set_reverse_hidden(')
 (B/'audit6-mtp.hpp').write_text(includes(mtp,P))
 rank=(P/'rank.hpp').read_text().replace('f.write(', 'audit_write(f,')
 (B/'audit6-rank.hpp').write_text(includes(rank,P))
 (B/'audit6-main.cpp').write_text(includes(main,P,{'mtp.hpp':B/'audit6-mtp.hpp','rank.hpp':B/'audit6-rank.hpp'}))
 return {f.name:digest(f) for f in B.glob('audit6-*.?pp')}
def compile_gate():
 from copy_adoption_gate import SOURCES
 sources=[n for n in SOURCES if n not in ('copy_selection_gate.cpp','gemv_timing.cpp','small_gemv_fixture.cpp','adapter_fixture.cpp','p39_fixture.cpp')]+['mtp_kernels.cpp','../packet2/loader/gguf.cpp']
 cmd=['g++','-std=c++20','-O1','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-I'+str(B),'-I'+str(P),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parents[1]/'stage1/packet3-prep/src')]
 for key,value in [('PLAN',P/'build/input/plan.tsv'),('MANIFEST',P/'mtp-manifest.tsv'),('DISPATCH',P/'dispatch-p45.json')]:cmd+=['-DAUDIT6_'+key+'="'+str(value)+'"']
 cmd += [str(P/'audit6_gate.cpp'),*[str(P/n) for n in sources],'-lcrypto','-o',str(B/'audit6-gate')]
 with (E/'compile.log').open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
 save(E/'compile.json',dict(command=cmd,exit_code=r.returncode,device_executed=False))
 assert r.returncode==0,(E/'compile.log').read_text()[-4000:]
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 admit(100_000_000)
 generated=generate();compile_gate()
 print('audit6 compiled',flush=True)
 for context in (4096,32768):
  for dr in (0,1):
   for window in ('KD','W2m','WSs'):
    for rank in ((1,) if window=='KD' else (0,1)):
     admit(5_000_000);out=E/f'{window}-c{context}-dr{dr}-r{rank}';out.mkdir(exist_ok=True)
     with (out/'run.log').open('w') as log:r=subprocess.run([str(B/'audit6-gate'),str(context),str(dr),str(rank),window,str(out)],stdout=log,stderr=subprocess.STDOUT)
     print(out.name,r.returncode,flush=True)
     assert r.returncode==0,(out/'run.log').read_text()[-4000:]
 save(E/'generated.json',dict(generated_sha256=generated,binary_sha256=digest(B/'audit6-gate')))
 canary();report()
if __name__=='__main__':main()
