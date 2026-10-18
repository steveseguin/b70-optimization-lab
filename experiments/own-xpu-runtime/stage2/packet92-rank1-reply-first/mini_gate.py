"""Fresh host-only miniature engines: target, draft bytes and reverse handoff."""
import json,subprocess,shutil
from unittest.mock import patch
import pipeline
from build_engine import P,ROOT,B,BASE,sha,save,limits
from bundle_selection import views,choices,selection
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
 return identity,dict(timing_fields=sorted(json.loads((dest/'rank1/timings.jsonl').read_text().splitlines()[0])),label=label,binary_sha256=sha(binary),draft_rank=dr,target_split=split,choices=v,fixture_count=len(fixtures),proposals=len(proposals),stats=result['stats'],identity_sha256=sha(P/'evidence'/('mini-'+label+'.json')))

def main():
 limits();rows=[];expected,control=run_one('parent84',BASE/'build/gnu-host/own-rt-iq3',1,0);rows.append(control)
 shutil.rmtree(MINI)
 for name in views():
  for repeat in (1,2):
   actual,row=run_one(name+'-'+str(repeat),B/'gnu-host/own-rt-iq3',1,0,name)
   assert actual==expected,'target/draft/state differs'
   dest=MINI/row['label'];host=[json.loads(x) for x in (dest/'rank1/p92-host.jsonl').read_text().splitlines()]
   halves=[json.loads(x) for x in (dest/'rank1/timings.jsonl').read_text().splitlines()]
   assert len(host)==len(halves) and len(host)>=24
   for h in host:assert h['reply_first']==(name=='reply-first') and h['result_ready_to_reply_ms']>=0 and h['bookkeeping_ms']>=0
   parent_fields=set(control['timing_fields'])
   for h in halves:assert set(h)==parent_fields
   row['half_receipts']=len(halves);row['host_receipts']=len(host);rows.append(row)
   save(P/'evidence'/('host-'+row['label']+'.json'),host)
   shutil.rmtree(MINI)
   print(row['label'],'target/draft/full-state MATCH; all half receipts retained',flush=True)
 raw=(json.dumps(expected,sort_keys=True)+'\n').encode();(P/'evidence/mini-expected.bin').write_bytes(raw);(P/'evidence/mini-candidate.bin').write_bytes(raw)
 sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('mini_gate.py','pipeline.py','suite_metrics.py','selection-template.json','rank.hpp','mtp.hpp','native_controller.hpp','reply_first.hpp','bundle_selection.py')}
 save(P/'evidence/mini-gate.json',dict(passed=True,device_executed=False,model_weights_read=False,rows=rows,sources=sources,build_receipt_sha256=sha(P/'build-device-receipt.json')))
if __name__=='__main__':main()
