"""One load: exact native controls plus five isolated body-class probes.

Diagnostic only. Every control and every pre-probe setup request must equal the
registered iq3-p49-split32-v1 oracle prefix. A probe snapshots, skips one class,
restores, repairs exactly and restores again inside the rank; the next request
always begins with a complete native reset. No probe token is ever published.
In-run checks are stream presence/format and exactness only.
"""
import argparse,json,os,signal,time
from pathlib import Path
from common import HERE,read,save,require,sha
from census_contract import ORDER,CONTROLS,CLASSES,IDS,ARITHMETIC,ARM_CODES,TOKENS,REPEATS,PROBE_OP
import exec_limits
EOS=(248044,248046)

def prompt(pid):
    tokens=list(map(int,(HERE/'inputs'/pid/'tokens.txt').read_text().split()))
    require(tokens,'empty prompt '+pid);return tokens
def oracle(pid):return read(HERE/'lineage/oracle128'/(pid+'.json'))['tokens']

def warm_prompt():
    tokens=list(map(int,(HERE/'inputs/prefill512/tokens.txt').read_text().split()))
    require(all(tokens!=prompt(p) for p in IDS),'warm-up must be distinct from every census prompt')
    return tokens

def native_args(pipeline,output):
    args=pipeline.parser().parse_args(['--output',str(output),'--device','--binary',str(HERE/'build/device/own-rt-iq3'),
      '--dispatch',str(HERE/'dispatch.json'),'--controller','native','--draft','mtp','--draft-rank','1','--target-split','0',
      '--context','4096','--tokens','512','--retain-steps','none','--timing','token','--native-nice','0','--card','0',
      '--seconds','7200','--wait-seconds','1200'])
    args.selection_sha256=sha(HERE/'selection.json');args.input=HERE/'inputs';args.census_probe=True
    return args

def control_row(view,pid,dest,result):
    tokens=result['tokens']
    require(tokens==oracle(pid)[:len(tokens)] and len(tokens)==TOKENS,'control/setup oracle mismatch: '+view+'/'+pid)
    resets=[read(dest/f'rank{r}/reset.json') for r in (0,1)]
    require(all(x.get('passed')is True and x.get('allocation_ids_preserved')is True for x in resets),'native complete reset required')
    intervals=result.get('decode_intervals');wall=result.get('decode_wall_ms')
    require(type(intervals)is int and intervals>=TOKENS-2 and isinstance(wall,(int,float)) and wall>0,'decode stream format')
    return dict(view=view,prompt_id=pid,tokens=tokens,arithmetic=ARITHMETIC,cached_tokens=0,full_reset=True,
      repairs_complete=True,interval_ms=wall/intervals,decode_intervals=intervals,decode_wall_ms=wall,
      reset_sha256=[sha(dest/f'rank{r}/reset.json') for r in (0,1)],acceptance=result.get('acceptance'))

class Cursor:
    """Read only rows appended by this probe call (rank output follows each reset)."""
    def __init__(self):self.seen={}
    def take(self,path):
        lines=path.read_text().splitlines() if path.is_file() else []
        start=self.seen.get(path,0);self.seen[path]=len(lines)
        return [json.loads(line) for line in lines[start:]]

def probe_rows(transport,dest,cls,index,cursor):
    rows=[]
    for rank in (0,1):
        transport.call(rank,PROBE_OP,token=ARM_CODES[cls],position=index,fixture=REPEATS)
        got=cursor.take(dest/f'rank{rank}/packet168-probes.jsonl')
        require(len(got)==REPEATS,'probe row count rank'+str(rank))
        for repeat,row in enumerate(got):
            require(row.get('schema')=='packet168.body-probe.v2' and row['rank']==rank and row['arm']==ARM_CODES[cls]
              and row['prompt_index']==index and row['repeat']==repeat,'probe stream identity')
            require(row['restore_exact']is True and row['repair_exact']is True and row['diagnostic_only']is True
              and row['reported_tokens']==0 and row['skipped_sites']>0,'probe restore/repair/format')
        rows+=got
    return rows

def run(output,transport_factory=None):
    import pipeline,suite,storage
    adapter=output/'adapter';adapter.mkdir();(adapter/'build').mkdir()
    (adapter/'selection.json').write_bytes((HERE/'selection.json').read_bytes())
    # Census plan = parent plan + measured rank1 diagnostic snapshot backing.
    (adapter/'memory-plan.json').write_bytes((HERE/'memory-plan-census.json').read_bytes())
    pipeline.P=adapter;storage.P=output
    args=native_args(pipeline,output)
    ranks=output/'ranks';ranks.mkdir();stopped=[]
    handlers={s:signal.signal(s,lambda n,f:stopped.append(n))for s in(signal.SIGINT,signal.SIGTERM)}
    def check():require(not stopped,'coordinator stop')
    transport=None;observations=[];cursor=Cursor();setups=[]
    previous=[]
    def streams(dest):
        # Presence/format only: the reset after a request flushes its streams.
        for rank in (0,1):
            stream=dest/f'rank{rank}/timings.jsonl'
            require(stream.is_file(),'missing timing stream '+str(stream))
            require(all(isinstance(json.loads(l),dict) for l in stream.read_text().splitlines() if l.strip()),'timing stream format')
    def request(dest,tokens,count):
        check();suite.reset(transport,dest)
        if previous:streams(previous.pop())
        result=pipeline.NativeController(transport,pipeline.Draft('mtp'),True,False).run(tokens,count,EOS)
        previous.append(dest)
        return result
    try:
        exec_limits.check()
        if transport_factory:transport=transport_factory(args,ranks,check)
        else:
            transport=pipeline.Transport.__new__(pipeline.Transport)
            pipeline.Transport.__init__(transport,args,ranks,dict(os.environ),check)
        # Opening: one distinct excluded warm-up, then exact C0 on all 12 prompts.
        warm=request(output/'requests/warmup',warm_prompt(),2)
        require(len(warm['tokens'])==2,'warm-up incomplete')
        for view in ORDER:
            for index,pid in enumerate(IDS):
                dest=output/'requests'/view/pid
                result=request(dest,prompt(pid),TOKENS)
                row=control_row(view,pid,dest,result)
                if view in CONTROLS:observations.append(row)
                else:
                    # The setup request is an exact unchanged run; only its end
                    # state is probed. It is never a reported control view.
                    setups.append(dict(view=view,prompt_id=pid,interval_ms=row['interval_ms'],exact=True))
                    probes=probe_rows(transport,dest,view,index,cursor)
                    observations.append(dict(view=view,prompt_id=pid,tokens=row['tokens'],diagnostic_only=True,
                      reported_tokens=0,setup_exact=True,arm_code=ARM_CODES[view],probes=probes))
                save(output/'census-progress.json',dict(view=view,prompt_id=pid,observations=len(observations)))
        suite.reset(transport,output/'requests/after-census');streams(previous.pop());transport.close(True)
        receipts=[read(ranks/f'rank{i}/receipt.json') for i in (0,1)] if transport_factory is None else []
        for row in receipts:
            owners=row.get('teardown',[])
            require(row.get('passed')is True and len(owners)==1 and owners[0].get('safe_to_exit')is True,'native drain incomplete')
        save(output/'teardown.json',dict(drained=True,owner_count=2))
    except BaseException as error:
        if transport is not None and hasattr(transport,'stop_write')and not transport.closed:
            transport.check=lambda:None
            try:transport.stop(error);transport.close(False)
            finally:
                while any(p.poll()is None for p in transport.children):time.sleep(.25)
        raise
    finally:
        for s,h in handlers.items():signal.signal(s,h)
    doc=dict(schema='packet168.census.v2',diagnostic_only=True,model_loads=1,order=list(ORDER),
      report_classes=list(__import__('census_contract').REPORT_CLASSES),engine_identity='packet136-bundle8',
      measurement_scope='native_exact_controls_plus_isolated_body_class_probes',tokens_per_request=TOKENS,
      repeats_per_probe=REPEATS,observations=observations,setup_requests=setups)
    save(output/'census-input.json',doc)
    return doc

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--lane',choices=('A','B'),required=True);a=ap.parse_args()
    require((a.output.parent/'window.json').is_file(),'outer admitted window required')
    identity=read(a.output.parent/'identity.json');require(identity['lane']==a.lane,'lane binding')
    a.output.mkdir();run(a.output);return 0
if __name__=='__main__':raise SystemExit(main())
