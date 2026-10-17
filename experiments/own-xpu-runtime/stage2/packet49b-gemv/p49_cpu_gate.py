"""Fresh CPU execution of the compiled owner/fixture paths; never model weights."""
import json, os, subprocess, time
from pathlib import Path
from storage import digest, archive_files
from cpu_gates import host
import build
P=Path(__file__).resolve().parent
B=P/'build'
def summarize_receipt(receipt):
    result=dict(receipt)
    def item(row):return {k:v for k,v in row.items() if k!='sequence'}|{'sequence_entries':len(row.get('sequence',[]))}
    if isinstance(result.get('teardown'),list):result['teardown']=[item(row) for row in result['teardown']]
    elif isinstance(result.get('teardown'),dict):result['teardown']=item(result['teardown'])
    return result
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(4,16))|set(range(20,32))
    assert os.environ['OMP_NUM_THREADS']=='2'
    mode=json.loads((P/'build-gnu-host-receipt.json').read_text())
    assert mode['compiled_sources_sha256']==build.compiled_sources()
    root=B/('cpu-fixtures-'+str(time.time_ns()));root.mkdir()
    rows=[]
    for name in ('authority-tests','owner-retirement-tests','chain-tests','queue-tests','lifetime-tests','prepared-invalidation-tests'):
        binary=B/'gnu-host'/name;host(binary)
        run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=120)
        assert run.returncode==0,run.stdout+run.stderr
        rows.append(dict(name=name,binary_sha256=digest(binary),stdout=run.stdout,passed=True))
    fixture_rows=[]
    for name in ('p49b-expert-fixtures','p49-qsa-fixtures','p33-linked-fixtures','nongemv-fixtures'):
        binary=B/'gnu-host'/name;host(binary);previous=None
        for repeat in range(2):
            out=root/(name+'-'+str(repeat));cmd=[str(binary),'--output',str(out)]
            if name=='nongemv-fixtures':cmd+=['--context','4096','--fixtures',str(B/'fusion-fixtures'),'--dispatch',str(P/'dispatch-p45.json')]
            with out.with_suffix('.log').open('w') as log:
                run=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
            assert run.returncode==0,str(out.with_suffix('.log'))
            receipt=json.loads((out/'receipt.json').read_text())
            assert receipt['passed'] and receipt['reference_exact'] and not receipt['device_executed']
            value=digest(out/'output.bin');assert value==receipt['output_sha256']
            assert previous is None or value==previous
            previous=value
            fixture_rows.append(dict(name=name,repeat=repeat,output=str(out),binary_sha256=digest(binary),receipt=summarize_receipt(receipt),native_receipt_sha256=digest(out/'receipt.json'),output_sha256=value))
            print(name,repeat,'PASS',flush=True)
    assert mode['compiled_sources_sha256']==build.compiled_sources()
    receipt=dict(passed=True,device_executed=False,model_weights_read=False,
        compiled_sources_sha256=build.compiled_sources(),owner_suites=rows,fixtures=fixture_rows,
        scope='GNU host actual owner fixture paths twice in fresh processes; no device result and no real-model certification')
    (P/'p49-cpu-gates.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
