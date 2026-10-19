"""CPU adapter for frozen ops' five-view report fixture; runs real six-view report.

Only synthetic input generation and expected request count change. Real packet
entry/parser/driver/analyzer/window/queue publication functions are untouched.
The original ops checker is run separately and its unsupported schema retained.
"""
import importlib.util,inspect,json,sys,tempfile,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];OPS=P.parents[1]/'ops'
sys.path.insert(0,str(OPS))
spec=importlib.util.spec_from_file_location('frozen_entry',OPS/'rehearse_entry.py');R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)
_original=R.synthetic_onecard

def synthetic(driver,views,output,kind,candidate,maintenance):
    manifest=_original(driver,views,output,kind,candidate,maintenance)
    if kind=='smoke':return manifest
    for label,arm in views.bracket(candidate):
        for entry in manifest['prompts']:
            root=output/'run'/label/entry['prompt_id'];f=root/'result.json';r=json.loads(f.read_text());r['tokens']=r['tokens'][:32];r['timing_rows']=r['timing_rows'][:32];r['requested_max_new']=32;f.write_text(json.dumps(r))
            rows=[]
            for i in range(32):
                waits=[dict(kind='compute-or-copy-tail',phase='decode-compute-drain',scope='normal',begin_ns=1000,call_ns=2000,end_ns=2000000)] if arm=='wait-split' else []
                rows.append(dict(generated_index=i+1,token_id=1,wall_ms=33.,wait_ms=21.,prepare_ms=.1,enqueue_loop_ms=.2,publication_split=dict(arm=arm,diagnostic_only=True,calls=1,construction_ms=.04,submit_ms=.02,drain_ms=0. if arm=='drain-only' else .1 if arm=='no-upload' else .5 if arm=='no-scatter' else 1.,repair_ms=1.,retire_host_ms=.01,waits=waits)))
            (root/'timings.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            (root/'prefill-timings.jsonl').write_text(''.join(json.dumps(dict(r,generated_index=0))+'\n' for r in rows[:3]))
    return manifest
R.synthetic_onecard=synthetic
# Mechanical fixture cardinality adaptation, not a packet report bypass.
source=inspect.getsource(R.onecard_report_probe).replace('(60 if kind == \'bracket\' else 12)','(72 if kind == \'bracket\' else 12)')
exec(compile(source,'<six-view-cardinality-adapter>','exec'),R.__dict__)

def main():
 if len(sys.argv)>1 and sys.argv[1]=='--child':
    job=json.loads(Path(sys.argv[2]).read_text());scratch=Path(sys.argv[4]);kind=sys.argv[3]
    result=R.report_probe(job,kind,scratch,ROOT)
    (scratch/'adapter-result.json').write_text(json.dumps(result));return
 job=json.loads(next(x for x in (OPS/'lane-queue/proposed-p58aq-split-A.txt').read_text().splitlines() if x.startswith('{')))
 rows=[]
 for kind in ('smoke','bracket'):
    with tempfile.TemporaryDirectory(prefix='p58aq-report-') as directory:
        d=Path(directory);request=d/'job.json';request.write_text(json.dumps(job))
        from launch_env import environment
        cp=subprocess.run([sys.executable,'-B',str(Path(__file__)),'--child',str(request),kind,str(d)],env=environment(),stdin=subprocess.DEVNULL,capture_output=True,text=True)
        (P/'evidence'/('report-'+kind+'.log')).write_text(cp.stdout+cp.stderr)
        if cp.returncode:raise AssertionError(cp.stderr[-3000:])
        row=json.loads((d/'adapter-result.json').read_text());assert row['passed'];rows.append(row)
 (P/'evidence/report-adapter.json').write_text(json.dumps(dict(passed=True,device_executed=False,synthetic_only=True,records=rows,frozen_ops_sha256=R.digest(OPS/'rehearse_entry.py'),adaptations=['synthetic 32-token streams and split timings','six-view request count 72']),indent=2)+'\n')
 print('PASS real smoke and six-view entry/driver/analyzer/window/queue reports')
if __name__=='__main__':main()
