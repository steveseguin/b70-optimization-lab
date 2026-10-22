"""CPU payload, selection and instrumentation boundaries. No model/device reads."""
import ast,json,resource,subprocess,sys
from pathlib import Path
from p183_v5_build_engine import P,LOCAL,ROOT,sha,save,limits

def main():
 limits()
 row=json.loads((LOCAL/'payload-sizes.json').read_text())
 assert len(row['layers'])==24 and len(row['rows'])==96
 assert all(x['exchanges']==4 for x in row['layers'])
 for r in row['rows']:
  assert r['input_scalar']=='BF16' and r['input_bytes']==2*r['input_elements']
  assert r['rank0_to_rank1_bytes']==r['input_bytes']+r['expert_ids_bytes']
  assert r['rank1_to_rank0_bytes']==sum(x['elements'] for x in r['outputs'])+4
  assert all(x['elements']%2==0 and x['received_half_bytes']==x['elements'] for x in r['outputs'])
  assert max(r['rank0_to_rank1_bytes'],r['rank1_to_rank0_bytes'])<=65536
 from bracket import compatible,load_config
 off=json.loads((P/'lineage/off/selection.json').read_text());on=json.loads((P/'lineage/split/selection.json').read_text())
 assert compatible([off,on,off,on,off])
 for kind,n in [('smoke',1),('bracket',5)]:assert len(load_config(P/'configs'/('split-'+kind+'.json'))['views'])==n
 bad=json.loads(json.dumps(on));bad['choices']['probe']='bogus'
 try:compatible([off,bad])
 except ValueError:pass
 else:raise AssertionError('unknown probe accepted')
 bad=json.loads(json.dumps(on));bad['choices']['miss']='control'
 try:compatible([off,bad])
 except ValueError:pass
 else:raise AssertionError('changed arithmetic/storage accepted')
 rank=(P/'native-src/rank.hpp').read_text();probe=(P/'native/probe_exchange.hpp').read_text()
 assert 'if(completing_redo&&engine->sealed_selection.choices.at("probe")=="split")' in rank
 assert 'e.correction_exchange&&(l.op=="gemv"||l.op=="routed_gemv"||l.op=="expert_gate_up")' in rank
 assert '"p149 corrected-half exchange census"' in rank
 assert 'e.probe_auxiliary.insert(scratch)' in probe and 'e.head_auxiliary.insert' not in probe
 assert 'copy(scratch,staging,m)' in probe and 'p105::CopyScope scope(false)' in probe
 assert 'copy(staging,input.id,activation)' in probe and 'copy(staging,routes.id,route_bytes,activation)' in probe
 assert 'probe.serve_correction(' in rank and 'native38::load(peer.abort)' in probe
 # All active source files compile as Python text without writes/imports.
 scripts=list(P.glob('*.py'))
 for f in scripts:compile(f.read_bytes(),str(f),'exec')
 tests=[]
 for leaf in ('test_timing_report.py','test_report_retained.py'):
  cp=subprocess.run([sys.executable,'-B',str(P/leaf)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
  log=P/'evidence'/('probe-'+leaf+'.log');log.write_text(cp.stdout+cp.stderr);assert cp.returncode==0,log.read_text()
  tests.append(dict(name=leaf,passed=True,log=str(log.relative_to(ROOT)),log_digest=sha(log)))
 sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'probe_cpu.py',P/'native/probe_exchange.hpp',P/'native-src/rank.hpp',LOCAL/'payload-sizes.json',P/'bracket.py',P/'timing_report.py',P/'test_timing_report.py',P/'test_report_retained.py')}
 save(P/'evidence/probe-cpu.json',dict(passed=True,device_executed=False,model_read=False,full_model_quality_pending=True,sources=sources,tests=tests,payload_sites=96,layers=24,max_payload_bytes=max(max(r['rank0_to_rank1_bytes'],r['rank1_to_rank0_bytes']) for r in row['rows']),resident_extra_per_rank=dict(device_bytes=65536,pinned_bytes=65536),shared_extra_bytes=65600,python_sources=len(scripts),peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
 print('Probe CPU census, selectors, isolation boundaries and retained report PASS')
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
