#!/usr/bin/env python3
"""Actual host Engine mini-model equivalence, persistent rank pair, all scripts <=6."""
import argparse, hashlib, itertools, json, random, shutil, time
from pathlib import Path
import pipeline
import suite
P=Path(__file__).resolve().parent

def committed_terminal(path,context):
    """Only cross-position state is observable after discarded terminal guess.
    Preserve raw full hashes separately; never call inactive/scratch bytes exact.
    """
    base=path/'rank0';directory=base/'state-2147483646'
    plan=json.loads((path.parent/'rank0/launch-plan.json').read_text())
    meta=json.loads((directory/'state.json').read_text())
    position=int.from_bytes((directory/'position.bin').read_bytes(),'little',signed=True)
    names={'position','error','active','token_history'};append={}
    for launch in plan['launches']:
        if launch['op'] in ('gdn','conv'):names.add(launch['outputs'][1])
        if launch['op']=='qsa_append_pool':
            for name in launch['outputs']:
                data=(directory/(name+'.bin')).read_bytes()
                rows=context//4 if name.endswith('.pooled') else context
                valid=position//4 if name.endswith('.pooled') else position
                assert len(data)%rows==0 and 0<=valid<=rows
                append[name]=hashlib.sha256(data[:valid*(len(data)//rows)]).hexdigest()
    state={name:pipeline.sha(directory/(name+'.bin')) for name in sorted(names) if (directory/(name+'.bin')).exists()}
    return dict(committed_buffers=state,committed_qsa_prefixes=append,history0=meta['history0'],history1=meta['history1'],position=position)

def signature(path,result,terminal=False,committed=None):
    files={};retained=suite.retained_state(path);bookkeeping=[]
    for rank in (0,1):
        base=path/f'rank{rank}'
        for file in sorted(base.rglob('*.bf16')):files[str(file.relative_to(path))]=pipeline.sha(file)
        files[f'rank{rank}/state']=committed if terminal and rank==0 else json.loads(retained[f'rank{rank}/state-2147483647/state.json']['text'])
        for name,row in retained.items():
            if name==f'rank{rank}/request-state-inventory.json':
                inventory=json.loads(row['text']);logical=inventory.pop('logical_event')
                bookkeeping.append(dict(rank=rank,logical_event=logical,raw_inventory_sha256=row['sha256'],raw_state_sha256=retained[f'rank{rank}/state-2147483647/state.json']['sha256']))
                if not (terminal and rank==0):files[name]=inventory
            elif name.startswith(f'rank{rank}/draft-final-state/'):files[name]=row['sha256']
    return dict(tokens=result['tokens'],guesses=result.get('guess_sequence'),hit_miss_sequence=[{k:r[k] for k in ('position','guess','actual','hit')} for r in result.get('guess_rows',[])],
                stats={k:result['stats'][k] for k in ('guesses','hits','misses','no_guess')},files=files),bookkeeping

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--binary',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--quick',action='store_true');a=ap.parse_args()
    root=P/'build/native-mini-scratch';assert not root.exists();root.mkdir()
    args=pipeline.parser().parse_args(['--binary',str(a.binary.resolve()),'--output',str(root),'--mini','--context','256','--tokens','64','--seconds','7200','--wait-seconds','300','--native-nice','19','--draft','mtp'])
    args.host_memory='resident'
    if not hasattr(args,'controller'):args.controller='python'
    bookkeeping_rows=[]
    transport=None;cases=0;start=time.monotonic();rows=[];failure=None
    try:
        transport=pipeline.Transport.__new__(pipeline.Transport);transport.__init__(args,root)
        counter=0
        suite.reset(transport,root/'case-0')
        def request(controller,prompt,count,mode='none',script=(),eos=()):
            nonlocal counter
            dest=root/f'case-{counter}';counter+=1
            provider=pipeline.Draft(mode,script)
            cls=pipeline.Controller if controller=='python' else pipeline.NativeController
            result=cls(transport,provider,True,False).run(prompt,count,eos)
            terminal=bool(result['tokens'] and result['tokens'][-1] in eos)
            committed=None
            if terminal:
                transport.call(0,pipeline.DUMP,position=2147483646)
                committed=committed_terminal(dest,args.context)
            # One boundary both captures this result and prepares the next request.
            suite.reset(transport,root/f'case-{counter}')
            data,raw=signature(dest,result,terminal,committed);bookkeeping_rows.append(dict(case=counter-1,controller=controller,terminal=terminal,ranks=raw));shutil.rmtree(dest)
            return result,data
        prompt=[2,5,3,7,1];base,_=request('python',prompt,8)
        configs=[]
        for n in range(7 if not a.quick else 3):
            for pattern in itertools.product((0,1,2),repeat=n):
                guesses=[base['tokens'][i] if x==1 else (base['tokens'][i]+1)%16 if x==0 else -1 for i,x in enumerate(pattern)]
                configs.append((prompt,8,'script',guesses,()))
        for seed in range(12 if not a.quick else 2):
            rng=random.Random(seed);pr=[rng.randrange(16) for _ in range(15)];ref,_=request('python',pr,64)
            guesses=[t if rng.randrange(3) else (t+1)%16 for t in ref['tokens'][:-1]]
            configs.append((pr,64,'script',guesses,()))
        for mode in ('none','ngram','mtp'):configs.append((prompt,16,mode,[],()))
        configs.append((prompt,8,'script',[(base['tokens'][0]+1)%16],(base['tokens'][0],)))
        for prompt,count,mode,script,eos in configs:
            left,ls=request('python',prompt,count,mode,script,eos)
            right,rs=request('native',prompt,count,mode,script,eos)
            if ls!=rs:
                failure=dict(passed=False,device_executed=False,case=cases,mode=mode,keys=[k for k in ls if ls[k]!=rs[k]],expected=ls,actual=rs)
                a.output.write_text(json.dumps(failure,indent=2)+'\n')
                raise AssertionError({k:failure[k] for k in ('case','mode','keys')})
            cases+=1
            if cases%100==0:print(f'actual-mini native equivalence {cases}/{len(configs)}',flush=True)
        transport.close(True);transport=None
        result=dict(passed=True,device_executed=False,cases=cases,exhaustive_ternary_patterns=sum(3**n for n in range(7 if not a.quick else 3)),long_random_cases=12 if not a.quick else 2,long_random_tokens=64,
                    bookkeeping_normalization='logical_event excluded only from model parity; raw hash and actual counter recorded per request',raw_inventory_records=bookkeeping_rows,terminal_state_scope='committed active recurrent/conv banks, PLE history, controls and exact valid QSA prefixes; inactive/scratch/tail bytes not claimed identical; rank1 full state',
                    host_memory=args.host_memory,host_path=args.host_path,model='actual Engine mini model, two host ranks',comparison=['tokens','guesses','hit/miss sequence and counts','all target state allocations and alternate banks','all retained fixtures','draft final state'],wall_seconds=time.monotonic()-start,binary_sha256=pipeline.sha(a.binary))
        a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    except (Exception,KeyboardInterrupt) as error:
        a.output.write_text(json.dumps(failure or dict(passed=False,device_executed=False,cases=cases,error=str(error) or type(error).__name__),indent=2)+'\n')
        raise
    finally:
        if transport is not None:
            transport.stop('mini equivalence exception');transport.close(False)
        shutil.rmtree(root)
if __name__=='__main__':main()
