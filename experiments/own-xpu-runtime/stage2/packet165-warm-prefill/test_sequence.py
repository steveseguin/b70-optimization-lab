"""CPU-only real worker sequence with fake transport, actual Python RESET path.

Synthetic token streams test orchestration, not model quality or device speed.
Native reset/stream survival is separately exercised by native_sequence_probe.
"""
import copy,json,sys,tempfile
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent;p=P/sys.argv[1];sys.path.insert(0,str(p))
import worker,measurement as M
read=lambda f:json.loads(f.read_text())
items=worker.entries();order=[e['prompt_id'] for e in items]
assert order==[M.IDS[0],'prefill512',*M.IDS[1:]]
assert len({M.digest(e['tokens']) for e in items})==13
assert [i for i in order if i!='prefill512']==list(M.IDS)
drain=dict(passed=True,device_executed=True,teardown=[dict(safe_to_exit=True,idle_marker_complete=True,live_bytes=0,in_flight=0,exit_code=0)])
def result(e,index):
    oracle=worker.expected(e)
    tokens=(oracle+[42]*512)[:512] if oracle else [42]*512
    start=1000.+index*100
    return dict(passed=True,arithmetic=M.ARITHMETIC,cached_tokens=0,requested_max_new=512,
        tokens=tokens,timing_rows=[dict(completed_monotonic=start+1+i*.1) for i in range(512)],
        request_start_monotonic=start,request_end_monotonic=start+53,prefill_ms=999.)
observed_resets=[]
with tempfile.TemporaryDirectory(prefix='packet165-sequence-') as td:
    root=Path(td);out=root/'run'
    worker.save(root/'window.json',dict(synthetic=True));worker.save(root/'identity.json',dict(lane='A'))
    if p.name=='one-card':
        import composition
        class Child:
            returncode=0
            def __init__(self,argv,**kw):
                assert argv[0]==str(p/'build/device/own-rt-iq3')
                table=Path(argv[argv.index('--suite-inputs')+1])
                lines=[s.split() for s in table.read_text().splitlines()]
                assert [r[0] for r in lines]==order
                for index,e in enumerate(items):
                    assert Path(lines[index][1]).read_text()==(p/'inputs'/e['prompt_id']/'tokens.txt').read_text()
                    dest=out/'native'/e['prompt_id'];dest.mkdir(parents=True)
                    worker.save(dest/'reset.json',dict(passed=True,cached_tokens=0,allocation_ids_preserved=True))
                    for leaf in ('timings.jsonl','prefill-timings.jsonl'):
                        (dest/leaf).write_text(json.dumps(dict(request=e['prompt_id'],sensor='synthetic',reset_index=index))+'\n')
                    worker.save(dest/'result.json',result(e,index));worker.save(dest/'lookup-request-complete.json',{})
                    observed_resets.append(e['prompt_id'])
                worker.save(out/'native/receipt.json',drain);worker.save(out/'native/census.json',{})
            def poll(self):return 0
            def wait(self):return 0
        patches=[patch.object(worker.subprocess,'Popen',Child),patch.object(composition,'check_lookups'),patch.object(composition,'check_census')]
    else:
        import pipeline,suite,storage
        def init(t,args,ranks,env,check):
            t.a=args;t.out=ranks;t.pending=[False,False];t.seq=[0,0];t.mapping=bytearray(pipeline.SHARED)
            t.trace=['dirty'];t.metrics=[{},{}];t.last_complete=[1.,1.];t.closed=False
            t.reset_counts=[0,0];t.children=[]
            for rank in (0,1):(ranks/f'rank{rank}').mkdir()
        def call(t,rank,op):
            assert op==suite.RESET
            metadata=t.out/f'rank{rank}'/f'reset-{t.seq[rank]+1}.txt'
            dest=Path(metadata.read_text().splitlines()[0]);dest.mkdir(parents=True,exist_ok=True)
            worker.save(dest/'reset.json',dict(passed=True,allocation_ids_preserved=True))
            (dest/'timings.jsonl').write_text('')
            t.seq[rank]+=1;t.reset_counts[rank]+=1
            observed_resets.append((dest.parent.name,rank))
        def close(t,success):
            assert success and t.reset_counts==[14,14]
            for rank in (0,1):worker.save(t.out/f'rank{rank}'/'receipt.json',drain)
            t.closed=True
        class Controller:
            def __init__(self,t,*args):self.t=t
            def run(self,tokens,cap,eos):
                t=self.t;index=t.reset_counts[0]-1;e=items[index]
                assert t.reset_counts==[index+1,index+1] and tokens==e['tokens'] and cap==512
                assert t.trace==[] and t.last_complete==[0.,0.] and not any(t.mapping)
                assert all(row==dict(busy_ms=0.,handover_ms=0.,calls=0,gpu_ms=0.) for row in t.metrics)
                for rank in (0,1):
                    f=t.request_output/f'rank{rank}'/'timings.jsonl'
                    assert f.read_text()==''
                    f.write_text(json.dumps(dict(request=e['prompt_id'],sensor='synthetic',reset_index=index))+'\n')
                r=result(e,index);t.work_start=r['request_start_monotonic'];t.work_end=r['request_end_monotonic']
                t.mapping[:4]=b'USED';t.trace=['used'];t.last_complete=[99.,99.]
                return r
        patches=[patch.object(pipeline.Transport,'__init__',init),patch.object(pipeline.Transport,'call',call),
            patch.object(pipeline.Transport,'close',close),patch.object(pipeline,'NativeController',Controller),
            patch.object(suite,'retain_request_state',return_value=dict(synthetic=True)),patch.object(storage,'admit')]
    from contextlib import ExitStack
    with ExitStack() as stack:
        for q in patches:stack.enter_context(q)
        stack.enter_context(patch.object(worker.exec_limits,'check'))
        stack.enter_context(patch.object(sys,'argv',['worker','--output',str(out),'--lane','A']))
        assert worker.main()==0
    report=read(out/'report-inputs.json')
    assert report['execution_order']==order
    assert [r['prompt_id'] for r in report['requests']]==list(M.IDS)
    warm=report['prefill']['prefill']['warmup']
    assert warm['state_reset_before_prefill'] and warm['request_count_before_prefill']==1
    assert warm['prompt_token_sha256']==M.digest(items[0]['tokens'])
    assert report['prefill']['prefill']['cached_tokens']==0
    assert report['prefill']['prefill']['tok_s']==512
    assert report['prefill']['prefill']['prefill_phase_device_ms'] is None
    checked=M.aggregate(report['requests'],report['prefill'])
    assert checked['strict512'] and not checked['quality']['full_output_oracle_exact']
    for e in items:
        dest=out/('native' if p.name=='one-card' else 'requests')/e['prompt_id']
        assert read(dest/'receipt.json')['cached_tokens']==0
    worker.save(p/'evidence/real-arm-sequence.json',dict(passed=True,device_executed=False,synthetic=True,
        execution_order=order,reset_events=observed_resets,actual_worker_main=True,actual_suite_reset=p.name=='two-card',
        native_transport_mocked=True,all_request_streams_checked=True,report_order_checked=True,
        warmup_distinct=True,no_prompt_repeated=True,scope='real Python arm orchestration; native resets covered separately; no arithmetic/performance claim'))
print(p.name,'real worker arm sequence PASS')
