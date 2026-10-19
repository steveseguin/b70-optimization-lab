"""Exercise final report writer at512; synthetic extension is NOT a measurement."""
import copy,json,sys,tempfile
from pathlib import Path
P=Path(__file__).resolve().parent;p=P/sys.argv[1];sys.path.insert(0,str(p))
import measurement as M,screen
read=lambda f:json.loads(f.read_text())
rows=[]
for ident in M.IDS:
 raw=read(p/'lineage/parent-requests'/(ident+'.json'));expected=raw['tokens'][:128]
 raw.update(tokens=expected+[42]*384,timing_rows=[dict(completed_monotonic=100+i*.1)for i in range(512)],requested_max_new=512,request_start_monotonic=99.,request_end_monotonic=152.,prefill_ms=1000.)
 tokens=list(map(int,(p/'inputs'/ident/'tokens.txt').read_text().split()));rows.append(M.request(raw,tokens,ident,expected))
pref=copy.deepcopy(raw);pref['tokens']=[42]*511+[248046];pt=list(map(int,(p/'inputs/prefill512/tokens.txt').read_text().split()));pref=M.request(pref,pt,'prefill512')
with tempfile.TemporaryDirectory(prefix='p163-report512-')as td:
 root=Path(td)
 for attempt in ('a','b'):
  out=root/attempt;(out/'run').mkdir(parents=True)
  screen.save(out/'run/report-inputs.json',dict(passed=True,requests=rows,prefill=pref,device_isolation=dict(passed=True)))
  identity=dict(lane='A',bracket=dict(kind='full512'),measurement_identity=dict(test='synthetic-only'),reference=str(root/'a')if attempt=='b'else None)
  result=screen.report_completed(out,dict(device_executed=False),identity,dict(scope='synthetic-CPU'))
  assert result['strict512']and result['realistic_final_gate']['passed']and not result['submission_eligible']
  assert result['prefill']['input_tokens']==512 and not result['quality']['full_output_oracle_exact']
  assert result['quality']['fresh_process_determinism_checked']==(attempt=='b')
 save=dict(passed=True,device_executed=False,synthetic_evidence=True,report_writer='screen.report_completed',coverage='full512 cap, natural EOS prefill, full128 oracle boundary, second fresh-output comparison',not_a_performance_or_quality_measurement=True)
 (p/'evidence/report512-test.json').write_text(json.dumps(save,indent=2)+'\n');print(p.name,'512 report PASS')
