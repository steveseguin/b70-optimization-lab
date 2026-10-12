#!/usr/bin/env python3
"""Actual host Engine mini-model equivalence, persistent rank pair, all scripts <=6."""
import argparse, hashlib, itertools, json, random, shutil, time
from pathlib import Path
import pipeline
import suite
P=Path(__file__).resolve().parent

def signature(path,result):
    files={};retained=suite.retained_state(path)
    for rank in (0,1):
        base=path/f'rank{rank}'
        for file in sorted(base.rglob('*.bf16')):files[str(file.relative_to(path))]=pipeline.sha(file)
        files[f'rank{rank}/state']=json.loads(retained[f'rank{rank}/state-2147483647/state.json']['text'])
        for name,row in retained.items():
            if name.startswith(f'rank{rank}/draft-final-state/') or name==f'rank{rank}/request-state-inventory.json':files[name]=row['sha256']
    return dict(tokens=result['tokens'],guesses=result.get('guess_sequence'),hit_miss_sequence=[{k:r[k] for k in ('position','guess','actual','hit')} for r in result.get('guess_rows',[])],
                stats={k:result['stats'][k] for k in ('guesses','hits','misses','no_guess')},files=files)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--binary',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--quick',action='store_true');a=ap.parse_args()
    root=P/'build/native-mini-scratch';assert not root.exists();root.mkdir()
    args=pipeline.parser().parse_args(['--binary',str(a.binary.resolve()),'--output',str(root),'--mini','--context','256','--tokens','64','--seconds','7200','--wait-seconds','300','--native-nice','19','--draft','mtp'])
    args.host_memory='resident'
    if not hasattr(args,'controller'):args.controller='python'
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
            # One boundary both captures this result and prepares the next request.
            suite.reset(transport,root/f'case-{counter}')
            data=signature(dest,result);shutil.rmtree(dest)
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
