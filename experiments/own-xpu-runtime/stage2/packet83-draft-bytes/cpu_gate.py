"""Fresh host-only miniature engines: target, draft bytes and reverse handoff."""
import json,subprocess
from unittest.mock import patch
import pipeline
from build_engine import P,ROOT,B,BASE,sha,save,limits
from bundle_selection import views,selection
import time
MINI=B/"mini"/str(time.time_ns())

def run_one(label,binary,name,parent=False):
 dr=1;split=0;hc="production"
 links=subprocess.check_output(['readelf','-d',str(binary)],text=True).lower()
 assert not any(x in links for x in ('libsycl','libze_loader','libur_loader','libopencl'))
 dest=MINI/label;adapter=MINI/(label+'-adapter');adapter.mkdir(parents=True,exist_ok=True)
 s=json.loads((BASE/'selection.json').read_text()) if parent else selection(name);save(adapter/'selection.json',s)
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
 return identity,dict(label=label,binary_sha256=sha(binary),draft_rank=dr,target_split=split,hc=hc,fixture_count=len(fixtures),proposals=len(proposals),stats=result['stats'],identity_sha256=sha(P/'evidence'/('mini-'+label+'.json')))

def main():
 limits();rows=[];all_views={}
 expected,row=run_one('parent75',BASE/'build/gnu-host/own-rt-iq3','production',True);rows.append(row)
 for name in views():
  repeats=[]
  for repeat in (1,2):
   actual,row=run_one(f'{name}-{repeat}',B/'gnu-host/own-rt-iq3',name)
   assert actual['tokens']==expected['tokens'] and actual['fixtures']==expected['fixtures'],'target bytes changed'
   if name=='production':assert actual==expected,'control draft changed'
   repeats.append(actual);rows.append(row);print(row['label'],'target MATCH',flush=True)
  assert repeats[0]==repeats[1],'draft fresh repeat changed'
  all_views[name]=dict(passed=True,identical_fresh_repeats=True,target_matches_parent=True,identity_sha256=row['identity_sha256'])
 for label,value in [('expected',dict(tokens=expected['tokens'],fixtures=expected['fixtures'])),('actual',dict(tokens=actual['tokens'],fixtures=actual['fixtures']))]:
  (P/'evidence'/('fixture-'+label+'.bin')).write_bytes((json.dumps(value,sort_keys=True)+'\n').encode())
 sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('cpu_gate.py','pipeline.py','selection.json','rank.hpp','mtp.hpp','native_controller.hpp','bundle_selection.py','p83_head.hpp','p59c_select.hpp')}
 save(P/'evidence/cpu-gates.json',dict(passed=True,device_executed=False,model_weights_read=False,rows=rows,views=all_views,sources=sources,build_receipt_sha256=sha(P/'build-device-receipt.json'),scope='Synthetic miniature; target byte identity and draft repeat identity. Real packet49 output/acceptance pending screens'))
if __name__=='__main__':main()
