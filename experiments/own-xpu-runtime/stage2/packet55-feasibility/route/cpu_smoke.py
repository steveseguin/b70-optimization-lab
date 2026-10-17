#!/usr/bin/env python3
"""Tiny synthetic engine comparison; no model payload or device access."""
import gzip,hashlib,importlib.util,json,os,struct,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;BASE=P.parents[1]/'packet49c-round2'
sys.path.insert(0,str(BASE))
import pipeline as pp
spec=importlib.util.spec_from_file_location('p55_route_window',P/'window.py');window=importlib.util.module_from_spec(spec);spec.loader.exec_module(window)
import convert

def state_identity(root):
    target=0;draft=0
    for rank in (0,1):
        relative=f'request0/rank{rank}/state-2147483647/state.json'
        left=json.loads((root/'baseline'/relative).read_text());right=json.loads((root/'diagnostic'/relative).read_text())
        assert left==right,'target reset-boundary state changed'
        target+=len(left['buffers'])
    for request in (0,1):
        relative=Path(f'request{request}/rank1/draft-final-state')
        for file in (root/'baseline'/relative).iterdir():
            if file.suffix not in ('.bin','.gz'):continue
            peer=root/'diagnostic'/relative/file.name
            left=gzip.decompress(file.read_bytes()) if file.suffix=='.gz' else file.read_bytes()
            right=gzip.decompress(peer.read_bytes()) if peer.suffix=='.gz' else peer.read_bytes()
            assert left==right,'draft mutable bytes changed';draft+=1
    return dict(passed=True,target_reset_boundary_buffers=target,draft_buffers=draft,comparison='target full buffer hashes plus exact decompressed draft bytes')

def main():
    if os.getpriority(os.PRIO_PROCESS,0)!=19 or os.environ.get('OMP_NUM_THREADS')!='2':raise SystemExit('nice19 OMP_NUM_THREADS2 required')
    root=P/'build/cpu-smoke-b';root.mkdir(exist_ok=False)
    runtime=P/'build/runtime';runtime.mkdir(exist_ok=True);pp.P=runtime
    records=[]
    for name,binary in [('baseline',BASE/'build/gnu-host/own-rt-iq3'),('diagnostic',P/'build/gnu-host/own-rt-iq3')]:
        out=root/name;out.mkdir()
        args=pp.parser().parse_args(['--binary',str(binary),'--output',str(out),'--mini','--draft','mtp','--draft-rank','1',
                '--max-new','2','--retain-steps','none','--seconds','120','--wait-seconds','30','--controller','native'])
        transport=pp.Transport.__new__(pp.Transport)
        try:
            transport.__init__(args,out)
            requests=[]
            for ordinal,prompt in enumerate(([2,5],[3,7])):
                destination=out/f'request{ordinal}';window.reset(transport,destination)
                result=pp.request_run(transport,pp.Draft('mtp'),prompt,2,(),True,False)
                pp.save(destination/'result.json',result)
                requests.append(dict(tokens=result['tokens'],guesses=result.get('guess_sequence'),stats={k:v for k,v in result['stats'].items() if not k.endswith('_ms')}))
            transport.close(True)
        except Exception:
            if hasattr(transport,'stop_write'):transport.stop('CPU smoke failed');transport.close(False)
            raise
        routes=[]
        if name=='diagnostic':
            for request in range(2):
                total=0;draft=0;command_layers={}
                for rank in (0,1):
                    file=out/f'request{request}'/f'rank{rank}'/'routes.p55bin';raw=file.read_bytes()
                    assert raw[:8]==convert.MAGIC and (len(raw)-8)%convert.RECORD.size==0
                    for row in convert.RECORD.iter_unpack(raw[8:]):
                        seq,stamp,pos,layer,role,count,command,spec,fixture=row[:9]
                        assert count==10 and command>0
                        if role==1:draft+=1
                        else:command_layers.setdefault((rank,command),[]).append(layer)
                        total+=1
                assert draft==2 and total>=14
                assert all(len(layers)==2 for layers in command_layers.values())
                routes.append(dict(request=request,records=total,draft_records=draft,target_commands=len(command_layers)))
        records.append(dict(name=name,binary_sha256=pp.sha(binary),requests=requests,routes=routes))
    assert records[0]['requests']==records[1]['requests'],'diagnostic synthetic outputs changed'
    receipt=dict(schema='packet55.route-cpu-smoke.v1',passed=True,device_executed=False,model_weight_bytes_read=0,
                 state_identity=state_identity(root),scope='two fresh CPU synthetic engines, each two requests of two prompt and two generated tokens; reset and MTP route hook',records=records)
    (P/'cpu-smoke-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
