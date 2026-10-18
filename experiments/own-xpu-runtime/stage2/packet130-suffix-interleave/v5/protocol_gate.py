"""Real CPU rank IPC, five-view switch/reset, and fresh v4-style output oracle."""
import hashlib,json,subprocess,sys,time,shutil,tempfile
from pathlib import Path
from unittest.mock import patch
from build_engine import P,ROOT,BASE,B,sha,save,limits
sys.path.insert(0,str(P.parents[1]/'packet56-draft-prefix'))
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
            suite.reset(transport,dest/'after-request')
            retained=suite.retained_state(dest/'request')
            byte_rows={name:row['sha256'] for name,row in retained.items()
                       if name.endswith('.bin') or name.endswith('/all-state.json')}
            assert byte_rows and any('draft-final-state' in name for name in byte_rows)
            state_sha=hashlib.sha256(json.dumps(byte_rows,sort_keys=True).encode()).hexdigest()
            rows.append(dict(tokens=result['tokens'],cached_tokens=result['cached_tokens'],boundary=proof,
                             state_bytes_sha256=state_sha,state_files=len(byte_rows)))
        suite.reset(transport,output/'after-suite');transport.close(True)
    except Exception as error:
        if hasattr(transport,'stop_write') and not transport.closed:
            transport.stop(error);transport.close(False)
        raise
    return dict(rows=rows,seconds=time.monotonic()-started)

def gate(config_name,config):
    limits();root=Path(tempfile.mkdtemp(prefix='protocol-',dir=B))
    runs=[]
    # The parent binary and new binary each run fresh single-view CPU references.
    for binary_name,binary in (('parent',BASE/'build/gnu-host/own-rt-iq3'),('v5',B/'gnu-host/own-rt-iq3'),('intel',B/'intel-host/own-rt-iq3')):
        for label,view in (('control',config['views'][0]),('candidate',config['views'][1])):
            if binary_name=='parent':
                row=json.loads(Path(view['selection']).read_text());row['choices'].pop('suffix_schedule')
                target=P/'lineage/parent-reference-selection.json';save(target,row)
                view=dict(view,selection=str(target),selection_sha256=sha(target))
            dest=root/(binary_name+'-'+label)
            row=run(binary,[view],dest);runs.append(dict(binary=binary_name,choice=label,**row))
            shutil.rmtree(dest)
    results=[]
    for mode,repeat in __import__('itertools').product(('gnu-host','intel-host'),(0,1)):
        dest=root/('bracket-'+mode+'-'+str(repeat));row=run(B/mode/'own-rt-iq3',config['views'],dest)
        for index,actual in enumerate(row['rows']):
            choice=config['views'][index]['choice']
            references=[r['rows'][0]['tokens'] for r in runs if r['choice']==choice]
            assert all(actual['tokens']==ref for ref in references),'fresh parent/v5 token mismatch'
            assert all(actual['state_bytes_sha256']==r['rows'][0]['state_bytes_sha256'] for r in runs if r['choice']==choice),'fresh parent/v5 state byte mismatch'
            assert actual['cached_tokens']==0
        results.append(row);shutil.rmtree(dest)
        print('real CPU bracket IPC, parent parity, fresh repeat',repeat,'PASS',flush=True)
    shutil.rmtree(root)
    return dict(passed=True,configuration=config_name,device_executed=False,model_payload_read=False,
        synthetic_miniature=True,no_model_speed_claim=True,fresh_references=runs,brackets=results,
        binaries={str(f.relative_to(ROOT)):sha(f) for f in (BASE/'build/gnu-host/own-rt-iq3',B/'gnu-host/own-rt-iq3',B/'intel-host/own-rt-iq3')},
        sources={str((P/'protocol_gate.py').relative_to(ROOT)):sha(P/'protocol_gate.py')})
def main():
    from mini_selection import prepare
    control,candidate=prepare()
    results=[]
    for name in ('bracket',):
        config=json.loads((P/'configs'/(name+'.json')).read_text())
        for view in config['views']:
            path=control if view['choice']=='control' else candidate
            view.update(selection=str(path),selection_sha256=sha(path))
        results.append(gate(name,config))
        save(P/'evidence'/('protocol-'+name+'.json'),results[-1])
    save(P/'evidence/protocol.json',dict(passed=True,device_executed=False,runs=results,
         fixture_projection='experts=wide64, head=production, suffix_schedule=production; actual production shapes separately qualified by full-shape and selected startup',
         binaries=results[0]['binaries'],sources={**results[0]['sources'],**{str(f.relative_to(ROOT)):sha(f) for f in (P/'mini_selection.py',control,candidate)}}))
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 main()
