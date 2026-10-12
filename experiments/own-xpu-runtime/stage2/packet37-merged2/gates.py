#!/usr/bin/env python3
"""CPU-only real-path gates. Every child inherits nice19, idle IO, OMP=2."""
import argparse,itertools,json,os,random,resource,shutil,subprocess,time,gzip,hashlib
from pathlib import Path
from pipeline import parser,run,sha,P
B=P/'build'
ORACLE=P.parents[2]/'qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective'
def invoke(binary,out,mode='none',script=None,mini=True,count=8,overlap=True,dumps=False,oracle=None):
    args=parser().parse_args(['--binary',str(binary),'--output',str(out),'--tokens',str(count),'--context','256','--draft',mode,'--prompt-overlap','on' if overlap else 'off']+(['--mini'] if mini else ['--input',str(B/'input')])+(['--script',str(script)] if script else [])+(['--oracle',str(oracle)] if oracle else [])+(['--dump-state'] if dumps else []))
    args.dispatch=P/('dispatch-all-new.json' if mini else 'dispatch-p33.json')
    if not mini and 'gnu-host' in str(binary):args.audit_prepare_each=True
    return run(args)
def fixture_hashes(out):
    roots=[out] if not (out/'rank0').exists() else [out/'rank0',out/'rank1']
    return {str(p.relative_to(root)):sha(p) for root in roots for p in root.glob('step*/layer-*.bf16')}
def states(out):
    return {str(p.relative_to(out/'rank0')):sha(p) for p in (out/'rank0').glob('state-*/*.bin')}
def sequential(binary,out,count):
    cmd=[str(binary),'--mini','--pipeline-mini','--context','256','--max-new',str(count),'--output',str(out),'--dispatch',str(P/'dispatch-all-new.json')]
    with out.with_suffix('.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
    return json.loads((out/'receipt.json').read_text())
def mini(mode):
    binary=B/mode/'own-rt-iq3';root=B/f'gates-{mode}-{time.time_ns()}';root.mkdir();rows=[]
    ref=sequential(binary,root/'reference',8);expected=ref['tokens'];assert len(expected)==8
    control=invoke(binary,root/'none',dumps=True);assert control['tokens']==expected
    fixtures=fixture_hashes(root/'reference');assert fixtures==fixture_hashes(root/'none') and len(fixtures)==32
    state=states(root/'none')
    variants=[('ngram',None,True),('none',None,False)]
    rng=random.Random(3201)
    # Exhaustive hit/miss patterns through length 6; remaining position no-guess.
    if mode in ('host','gnu-host'):
        for length in range(1,7):
            for mask in itertools.product((0,1),repeat=length):
                variants.append(('script',[expected[i] if bit else (expected[i]+1)%16 for i,bit in enumerate(mask)]+[-1]*(7-length),True))
    else:variants += [('script',expected[:7],True),('script',[(x+1)%16 for x in expected[:7]],True),('script',[expected[i] if i%2 else (expected[i]+1)%16 for i in range(7)],True)]
    for index,(draft,values,overlap) in enumerate(variants):
        script=root/f'script-{index}.txt'
        if values is not None:script.write_text(' '.join(map(str,values)))
        out=root/f'case-{index}';r=invoke(binary,out,draft,script if values is not None else None,overlap=overlap,dumps=True)
        assert r['tokens']==expected and fixture_hashes(out)==fixtures,(mode,index,'fixtures')
        assert states(out)==state,(mode,index,'full state differs')
        # Canonical host histories/cache validity also identical; allocation IDs absent.
        for p in (out/'rank0').glob('state-*/state.json'):
            assert json.loads(p.read_text())==json.loads((root/'none/rank0'/p.relative_to(out/'rank0')).read_text()),str(p)
        rows.append(dict(mode=draft,overlap=overlap,pattern=values,tokens=8,fixtures=32,state_files=len(state),stats=r['stats']))
        print(mode,index,'PASS',flush=True)
    # Long realistic control flow: 63 guesses, deterministic randomized hits/misses/no-guess.
    ref64=sequential(binary,root/'reference64',64);assert len(ref64['tokens'])==64
    script=root/'long.txt';values=[ref64['tokens'][i] if (choice:=rng.randrange(3))==0 else (ref64['tokens'][i]+1)%16 if choice==1 else -1 for i in range(63)]
    script.write_text(' '.join(map(str,values)));r=invoke(binary,root/'long', 'script',script,count=64)
    assert r['tokens']==ref64['tokens'] and fixture_hashes(root/'long')==fixture_hashes(root/'reference64')
    rows.append(dict(mode='long-random',tokens=64,fixtures=32,stats=r['stats']))
    result=dict(passed=True,device_executed=False,compiler=mode,binary_sha256=sha(binary),cases=len(rows)+1,rows=rows,reference_tokens=expected,fixture_sha256=fixtures,root=str(root))
    (P/f'mini-{mode}.json').write_text(json.dumps(result,indent=2)+'\n');return result

def real(mode='none',compiler='gnu-host'):
    binary=B/compiler/'own-rt-iq3';root=B/f'real-{compiler}-{mode}-{time.time_ns()}';script=B/f'real-{compiler}-{mode}-script.txt'
    expected=json.loads((ORACLE/'result.json').read_text())['tokens'][:8]
    if mode in ('hit','miss'):script.write_text(' '.join(map(str,expected[:7] if mode=='hit' else [(x+1)%248320 for x in expected[:7]])))
    start=time.monotonic();r=invoke(binary,root,'script' if mode in ('hit','miss') else mode,script if mode in ('hit','miss') else None,mini=False,oracle=ORACLE)
    observed=fixture_hashes(root);oracle={k:sha(ORACLE/k) for k in observed};assert len(observed)==384 and observed==oracle and r['tokens']==expected
    argument_blocks=0;argument_logs=[]
    if compiler=='gnu-host':
        (P/'evidence').mkdir(exist_ok=True)
        for rank in (0,1):
            log=root/f'rank{rank}/argument-equivalence.jsonl'
            for line in log.open():
                row=json.loads(line)
                if 'legacy_argument_hex' in row:
                    assert row['legacy_argument_hex']==row['prepared_argument_hex'];argument_blocks+=1
            packed=P/'evidence'/f'real-{mode}-rank{rank}-arguments.jsonl.gz'
            with log.open('rb') as src,gzip.open(packed,'wb') as dst:shutil.copyfileobj(src,dst)
            check=hashlib.sha256()
            with gzip.open(packed,'rb') as src:
                for chunk in iter(lambda:src.read(1024*1024),b''):check.update(chunk)
            assert check.hexdigest()==sha(log)
            argument_logs.append(dict(path=str(packed.relative_to(P)),sha256=sha(packed),raw_sha256=sha(log)))
        assert argument_blocks>0
    result=dict(prepared_argument_comparisons=argument_blocks,argument_logs=argument_logs,passed=True,device_executed=False,mode=mode,binary_sha256=sha(binary),dispatch_sha256=sha(P/'dispatch-p33.json'),prepared_argument_audit=(compiler=='gnu-host'),token_matches=8,layer_matches=384,layer_total=384,fixture_sha256=observed,stats=r['stats'],seconds=time.monotonic()-start,maxrss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,root=str(root))
    (P/(f'real-{mode}.json' if compiler=='gnu-host' else f'real-{compiler}-{mode}.json')).write_text(json.dumps(result,indent=2)+'\n')
    for rank in range(2):shutil.copyfile(root/f'rank{rank}/launch-plan.json',P/f'launch-plan-rank{rank}.json')
    print(mode,'8/8 tokens 384/384 fixtures PASS',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('kind',choices=('mini','real'));p.add_argument('mode');p.add_argument('--compiler',choices=('gnu-host','icpx-host'),default='gnu-host');a=p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
    if a.mode!='asan':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    mini(a.mode) if a.kind=='mini' else real(a.mode,a.compiler)
