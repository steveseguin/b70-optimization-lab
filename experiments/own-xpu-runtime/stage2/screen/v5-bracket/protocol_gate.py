"""Real CPU rank IPC, five-view switch/reset, and fresh v4-style output oracle."""
import json,subprocess,sys,time,shutil,tempfile
from pathlib import Path
from unittest.mock import patch
from build_engine import P,ROOT,BASE,B,sha,save,limits
sys.path.insert(0,str(P.parent.parent/'packet56-draft-prefix'))
import pipeline,suite,storage
sys.path.insert(0,str(P))
from bracket import switch_reset

def run(binary, views, output):
    output.mkdir(parents=True,exist_ok=False)
    args=pipeline.parser().parse_args(['--binary',str(binary),'--output',str(output),
         '--mini','--context','256','--tokens','8','--draft','mtp','--draft-rank','1',
         '--controller','native','--retain-steps','none','--seconds','180'])
    args.host_memory='resident';args.selection_sha256=views[0]['selection_sha256']
    pipeline.P=output/'adapter';pipeline.P.mkdir();storage.P=pipeline.P;storage.B=pipeline.P/'build'
    storage.admit=lambda *a,**kw: limits()
    popen=subprocess.Popen
    def launch(cmd,**kw):
        # Miniature transport omits --selection by design; this CPU gate binds
        # the same real selection parser used by production before startup.
        cmd=[*cmd,'--selection',views[0]['selection'],'--selection-sha256',views[0]['selection_sha256']]
        return popen(cmd,stdin=subprocess.DEVNULL,**kw)
    ranks=output/'ranks';ranks.mkdir();transport=pipeline.Transport.__new__(pipeline.Transport)
    rows=[];started=time.monotonic()
    try:
        with patch.object(pipeline.subprocess,'Popen',side_effect=launch):
            pipeline.Transport.__init__(transport,args,ranks,{'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'})
        for i,view in enumerate(views):
            dest=output/str(i);dest.mkdir()
            if len(views)>1:proof=switch_reset(transport,view,dest/'boundary',suite)
            else:proof=None
            suite.reset(transport,dest/'request')
            result=suite.run_request(transport,args,[1,2,3],8)
            rows.append(dict(tokens=result['tokens'],cached_tokens=result['cached_tokens'],boundary=proof))
        suite.reset(transport,output/'after-suite');transport.close(True)
    except Exception as error:
        if hasattr(transport,'stop_write') and not transport.closed:
            transport.stop(error);transport.close(False)
        raise
    return dict(rows=rows,seconds=time.monotonic()-started)

def main():
    limits();root=Path(tempfile.mkdtemp(prefix='protocol-',dir=B))
    config=json.loads((P/'configs/bracket.json').read_text());runs=[]
    # The parent binary and new binary each run fresh single-view CPU references.
    for binary_name,binary in (('parent',BASE/'build/gnu-host/own-rt-iq3'),('v5',B/'gnu-host/own-rt-iq3')):
        for label,view in (('control',config['views'][0]),('candidate',config['views'][1])):
            dest=root/(binary_name+'-'+label)
            row=run(binary,[view],dest);runs.append(dict(binary=binary_name,choice=label,**row))
            shutil.rmtree(dest)
    results=[]
    for repeat in (0,1):
        dest=root/('bracket-'+str(repeat));row=run(B/'gnu-host/own-rt-iq3',config['views'],dest)
        for index,actual in enumerate(row['rows']):
            choice=config['views'][index]['choice']
            references=[r['rows'][0]['tokens'] for r in runs if r['choice']==choice]
            assert all(actual['tokens']==ref for ref in references),'fresh parent/v5 token mismatch'
            assert actual['cached_tokens']==0
        results.append(row);shutil.rmtree(dest)
        print('real CPU bracket IPC, parent parity, fresh repeat',repeat,'PASS',flush=True)
    save(P/'evidence/protocol.json',dict(passed=True,device_executed=False,model_payload_read=False,
        synthetic_miniature=True,no_model_speed_claim=True,fresh_references=runs,brackets=results,
        binaries={str(f.relative_to(ROOT)):sha(f) for f in (BASE/'build/gnu-host/own-rt-iq3',B/'gnu-host/own-rt-iq3')},
        sources={str((P/'protocol_gate.py').relative_to(ROOT)):sha(P/'protocol_gate.py')}))
if __name__=='__main__':main()
