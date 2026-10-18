"""CPU-only miniature equality and actual native attribution-schema checks."""
import json,math,resource,subprocess,tempfile
from pathlib import Path
from build_engine import P,ROOT,limits,save,sha

from attribution_schema import validate,check_request

def main():
    limits();binary=P/'build/gnu-host/own-rt-iq3';records=[]
    with tempfile.TemporaryDirectory(prefix='attribution-cpu-',dir=P/'build') as directory:
        root=Path(directory);signatures=[]
        for mode in ('control','attribution1','attribution2'):
            output=root/mode
            command=[str(binary),'--mini','--pipeline-mini','--memory','resident','--context','32','--tokens','8','--retain-steps','1-8','--output',str(output)]
            if mode!='control':command+=['--attribution','host']
            result=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120,env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2'))
            assert result.returncode==0,result.stderr
            run=json.loads((output/'result.json').read_text())
            signatures.append(dict(tokens=run['tokens'],layers={str(f.relative_to(output)):sha(f) for f in output.glob('step*/*.bf16')}))
            assert signatures[-1]==signatures[0]
            rows=[] if mode=='control' else [json.loads(line) for line in (output/'attribution.jsonl').read_text().splitlines()]
            if rows:
                assert all(validate(row) for row in rows)
                assert check_request(output/'attribution.jsonl',run,full_model=False)['passed']
                generated=[r for r in rows if r['generated_index']>0]
                assert [r['token_id'] for r in generated]==run['tokens']
                assert [r['generated_index'] for r in generated]==list(range(1,len(run['tokens'])+1))
                assert any(r['host_wait_calls']['compute_including_zero_copy_miss']>0 for r in rows)
                assert any(r['host_wait_calls']['readbacks']>0 for r in rows)
                assert all(r['host_wait_calls']['fill_copies']==0 for r in rows)
            records.append(dict(mode=mode,passed=True,rows=len(rows),layer_files=len(signatures[-1]['layers']),tokens=run['tokens']))
        # Refuse profiling rather than silently changing timing semantics.
        result=subprocess.run([*command,'--timing','class'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
        assert result.returncode!=0 and 'preserve unprofiled queues' in result.stderr
    save(P/'evidence/attribution-cpu.json',dict(passed=True,device_executed=False,model_reads=False,
        binary_sha256=sha(binary),records=records,exact_tokens_and_layer_bytes=True,profiling_refused=True,
        max_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024,
        sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'attribution_gate.py',P/'attribution_schema.py',P/'attribution_source.py',P/'native/attribution.hpp']}))
    print('Native CPU attribution: control/two repeats exact; accounting closes; profiling refusal PASS')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
