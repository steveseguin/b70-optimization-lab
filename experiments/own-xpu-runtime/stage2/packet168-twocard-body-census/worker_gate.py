"""CPU real-arm-sequence gate for census_worker.py. No GPU, no model.

Drives the actual worker, suite.reset, NativeController and analyzer through a
host transport. Probe replies are the REAL rows emitted by the native CPU
lifecycle fixture (both ranks, every registered arm and prompt). Native
requests return the registered oracle prefix with synthetic timing. A
deliberately wrong token and a failed repair must both be refused.
"""
import json,resource,shutil,sys,tempfile
from pathlib import Path
from build_engine import P,save,sha,limits
import census_contract as C

class HostTransport:
    """Implements the transport calls the worker issues; records every command."""
    def __init__(self,args,out,check,real_rows,mutate=None):
        self.a=args;self.out=out;self.check=check;self.device=False;self.closed=False;self.children=[]
        self.seq=[0,0];self.pending=[False,False];self.commands=[];self.trace=[];self.mapping=bytearray(1<<20)
        self.metrics=[{},{}];self.last_complete=[0.,0.];self.work_start=self.work_end=0.
        self.shared_path=out/'shared.bin';self.current=[out/'rank0',out/'rank1'];self.rows=real_rows;self.mutate=mutate
        for d in self.current:d.mkdir(parents=True,exist_ok=True)
        self.census_probe=args.census_probe
    def start(self,rank,op,token=0,position=0,fixture=0,speculative=0):
        assert not self.pending[rank];self.seq[rank]+=1;self.pending[rank]=True
        self.commands.append(dict(rank=rank,op=op,token=token,position=position,fixture=fixture))
        if op==10 and rank==0:self.native()
    def wait(self,rank):
        assert self.pending[rank];self.pending[rank]=False;return dict(token=0,bytes=0,busy_ms=0.)
    def call(self,rank,op,token=0,position=0,fixture=0,speculative=0):
        self.start(rank,op,token,position,fixture,speculative)
        if op==11:self.reset(rank)
        if op==C.PROBE_OP:self.probe(rank,token,position,fixture)
        return self.wait(rank)
    def reset(self,rank):
        prev=self.current[rank];(prev/'request-state-inventory.json').write_text('{"host_gate":true}\n')
        meta=self.out/f'rank{rank}'/f'reset-{self.seq[rank]}.txt'
        dest=Path(meta.read_text().splitlines()[0]);dest.mkdir(parents=True,exist_ok=True)
        (dest/'reset.json').write_text(json.dumps(dict(passed=True,allocation_ids_preserved=True,cached_tokens=0))+'\n')
        self.current[rank]=dest
    def native(self):
        values=list(map(int,(self.shared_path.parent/'native-request.txt').read_text().split()))
        count=values[1];n=values[4];prompt=values[7:7+n]
        pid=next((p for p in C.IDS if (P/'inputs'/p/'tokens.txt').read_text().split()==list(map(str,prompt))),None)
        tokens=json.loads((P/'lineage/oracle128'/(pid+'.json')).read_text())['tokens'][:count] if pid else [1]*count
        if self.mutate=='wrong-token' and pid==C.IDS[3] and len(self.commands)>400:tokens=[tokens[0]^1,*tokens[1:]]
        for rank in (0,1):(self.current[rank]/'timings.jsonl').write_text(''.join(json.dumps(dict(i=i))+'\n' for i in range(count)))
        (self.shared_path.parent/'native-result.json').write_text(json.dumps(dict(tokens=tokens,decode_intervals=count-1,
          decode_wall_ms=17.0*(count-1),rank_trace=[],work_start=0.,work_end=1.,stats=dict(hits=1,guesses=2))))
    def probe(self,rank,arm,index,repeats):
        assert self.census_probe and repeats==C.REPEATS
        rows=[r for r in self.rows[rank] if r['arm']==arm and r['prompt_index']==index]
        assert len(rows)>=repeats,('no real native row',rank,arm,index)
        with (self.current[rank]/'packet168-probes.jsonl').open('a') as f:
            for row in rows[:repeats]:
                row=dict(row)
                if self.mutate=='bad-repair' and arm==C.ARM_CODES['gdn']:row['repair_exact']=False
                f.write(json.dumps(row)+'\n')
    def close(self,success):self.closed=True
    def stop(self,reason):pass

def real_rows():
    native=json.loads((P/'evidence/native-lifecycle.json').read_text())
    assert native['final_arm_sequence_passed'] is True
    out={}
    for r in native['results']:
        run=Path(r['output']);rows=[json.loads(l) for l in (run/'packet168-probes.jsonl').read_text().splitlines()]
        assert rows and all(x['rank']==r['rank'] for x in rows);out[r['rank']]=rows
    return out

def drive(mutate=None):
    import census_worker
    rows=real_rows()
    with tempfile.TemporaryDirectory(prefix='p168-worker-gate-',dir=P/'build') as tmp:
        output=Path(tmp)/'run';output.mkdir()
        made=[]
        def factory(args,ranks,check):
            t=HostTransport(args,ranks,check,rows,mutate);made.append(t);return t
        from unittest.mock import patch
        # The gate itself runs under a 4 GiB RLIMIT_AS (CPU rule); the device
        # worker's real exec_limits.check() refuses any finite limit. Stub it
        # here and prove the worker still calls it before the transport.
        limit_calls=[]
        try:
            with patch.object(census_worker.exec_limits,'check',side_effect=lambda:limit_calls.append(len(made))):
                doc=census_worker.run(output,transport_factory=factory)
            assert limit_calls==[0],'exec_limits.check must run once before the transport starts'
        except ValueError as error:return dict(mutate=mutate,refused=True,error=str(error))
        from analyze import write_report
        report=write_report(doc,Path(tmp)/'report')
        ops=[(c['rank'],c['op'],c['token'],c['position'],c['fixture']) for c in made[0].commands if c['op']==C.PROBE_OP]
        expected=[(rank,C.PROBE_OP,C.ARM_CODES[v],i,C.REPEATS) for v in C.ORDER if v in C.CLASSES for i in range(len(C.IDS)) for rank in (0,1)]
        assert ops==expected,('probe command sequence differs from registered order',ops[:3],expected[:3],len(ops),len(expected))
        resets=sum(1 for c in made[0].commands if c['op']==11)
        return dict(mutate=mutate,refused=False,report_passed=report['passed'],observations=len(doc['observations']),
          probe_commands=len(ops),resets=resets,native_requests=sum(1 for c in made[0].commands if c['op']==10 and c['rank']==0),
          ranked=[r['kernel_class'] for r in report['ranked']],residual_present='residual' in report)

def main():
    limits();sys.path.insert(0,str(P))
    good=drive();assert good['refused'] is False and good['report_passed'] is True,good
    assert good['observations']==len(C.ORDER)*len(C.IDS) and good['native_requests']==1+len(C.ORDER)*len(C.IDS),good
    assert sorted(good['ranked'])==sorted(C.CLASSES) and good['residual_present'],good
    bad=[drive('wrong-token'),drive('bad-repair')]
    assert all(b['refused'] for b in bad),bad
    save(P/'evidence/worker-gate.json',dict(passed=True,device_executed=False,
      scope='actual worker/suite.reset/NativeController/analyzer over host transport; probe rows are real native CPU lifecycle rows',
      good=good,refusals=bad,source_digests=[dict(name=n,sha256=sha(P/n)) for n in
        ('census_worker.py','worker_gate.py','analyze.py','census_contract.py','suite.py','pipeline.py','evidence/native-lifecycle.json')]))
    print('PASS worker real-arm-sequence gate',good,[b['error'] for b in bad])
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main()
