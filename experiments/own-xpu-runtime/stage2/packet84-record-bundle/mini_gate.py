"""Fresh host-only miniature engines: target, draft bytes and reverse handoff."""
import json,subprocess
from unittest.mock import patch
import pipeline
from build_engine import P,ROOT,B,BASE,sha,save,limits
from bundle_selection import PLACEMENTS,views,choices,selection,placements
import time
MINI=B/'mini'/str(time.time_ns())

def run_one(label,binary,dr,split,v=None):
 links=subprocess.check_output(['readelf','-d',str(binary)],text=True).lower()
 assert not any(x in links for x in ('libsycl','libze_loader','libur_loader','libopencl'))
 dest=MINI/label;adapter=MINI/(label+'-adapter');adapter.mkdir(parents=True,exist_ok=True)
 s=selection(v) if v else json.loads((BASE/'selection.json').read_text());save(adapter/'selection.json',s)
 args=pipeline.parser().parse_args(['--binary',str(binary),'--output',str(dest),'--mini','--context','256','--tokens','24','--seconds','180','--wait-seconds','120','--native-nice','19','--draft','mtp','--draft-rank',str(dr),'--target-split',str(split),'--controller','native','--timing','token','--retain-steps','1-24'])
 args.host_memory='resident';args.selection_sha256=sha(adapter/'selection.json')
 with patch.object(pipeline,'P',adapter):result=pipeline.run(args)
 assert result['passed'],result.get('error')
 fixtures={str(f.relative_to(dest)):sha(f) for rank in ('rank0','rank1') for f in (dest/rank).glob('step*/layer-*.bf16')}
 assert len(fixtures)==96 and len(result['tokens'])==24
 proposals=[r['guess'] for line in (dest/f'rank{dr}/draft-rows.jsonl').read_text().splitlines() if 'guess' in (r:=json.loads(line))]
 state=dest/f'rank{dr}/draft-final-state';states={str(f.relative_to(state)):sha(f) for f in state.rglob('*') if f.is_file() and f.suffix in ('.bin','.bf16','.f32','.u32')}
 identity=dict(tokens=result['tokens'],fixtures=fixtures,proposals=proposals,draft_state=states)
 save(P/'evidence'/('mini-'+label+'.json'),identity)
 return identity,dict(label=label,binary_sha256=sha(binary),draft_rank=dr,target_split=split,choices=v,fixture_count=len(fixtures),proposals=len(proposals),stats=result['stats'],identity_sha256=sha(P/'evidence'/('mini-'+label+'.json')))

def main():
 limits();rows=[]
 expected,row=run_one('parent75',BASE/'build/gnu-host/own-rt-iq3',1,0);rows.append(row)
 tested={}
 for name,v in views().items():
  # All 48 new-choice products on the coordinator baseline, plus all original
  # packet80 choices and placements. Operator product + full-shape cover all.
  if not ((v[1],v[3],v[4],v[5])==('hc-wide','ordered','production','production') or (v[2],v[6],v[7])==('wide64','production','production')):continue
  for placement,(dr,split,_) in placements(v).items():
   if v[-1]=='production' and (v[2]!='wide64' or v[6]!='production') and placement!='1':continue
   repeats=[]
   for repeat in (1,2):
    actual,row=run_one(f'{name}-{placement}-{repeat}',B/'gnu-host/own-rt-iq3',dr,split,v)
    assert actual['tokens']==expected['tokens'] and actual['fixtures']==expected['fixtures'],'target bytes changed: '+row['label']
    if v[-1]=='production':assert actual==expected,'unchanged draft differs'
    repeats.append(actual);rows.append(row);print(row['label'],'target MATCH',flush=True)
   assert repeats[0]==repeats[1],'draft repeat differs'
   tested[name+'--'+placement]=dict(passed=True,target_matches_parent=True,draft_repeated=True)
 for label,value in [('expected',expected),('actual',actual)]:
  (P/'evidence'/('fixture-'+label+'.bin')).write_bytes((json.dumps(value,sort_keys=True)+'\n').encode())
 sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('mini_gate.py','pipeline.py','selection-template.json','rank.hpp','mtp.hpp','native_controller.hpp','bundle_selection.py')}
 save(P/'evidence/cpu-gates.json',dict(passed=True,device_executed=False,model_weights_read=False,rows=rows,views=tested,sources=sources,build_receipt_sha256=sha(P/'build-device-receipt.json'),scope='Synthetic miniature product for all new choices on baseline, all original choices/placements; every composition additionally has factorized dual-compiler proof and full-shape dispatch/memory. Real packet49 output/acceptance pending chain'))
if __name__=='__main__':main()
