"""No-rank regression for synthetic, distinct suite kernel warmup selection."""
import ast,hashlib,json
from types import SimpleNamespace
from unittest.mock import patch
import suite
from pathlib import Path
from suite import select_warmup
P=Path(__file__).resolve().parent

def main():
    seed=[2,5,3,7,1];rows=[]
    def check(name,prompts):
        warm=select_warmup(prompts,256,248320)
        assert len(warm)==5 and all(1<=t<=15 for t in warm)
        assert all(warm!=prompt for prompt in prompts)
        assert all(warm!=prompt[i:i+5] for prompt in prompts for i in range(max(0,len(prompt)-4)))
        assert select_warmup(list(reversed(prompts)),32,16)==warm
        assert select_warmup(prompts*2,256,248320)==warm
        rows.append(dict(case=name,warmup=warm,distinct=True,order_independent=True))
    check('first-measured-prompt-is-old-warmup',[seed,[1,2,1],[3,5,7,2]])
    check('old-warmup-is-long-prompt-prefix',[seed+[9,10,11],[1,3,5,7,9]])
    check('old-warmup-is-long-prompt-interior',[[8,8]+seed+[9,10]])
    check('short-suite-prompts',[[1],[2,5],[3,7,1]])
    blocked=[seed]
    for _ in range(32):blocked.append(select_warmup(blocked,32,16))
    check('thirty-three-consecutive-collisions',blocked)
    refused=0
    for prompts,context,vocab in (([],256,248320),([[]],256,248320),([seed],5,248320),([seed],256,15)):
        try:select_warmup(prompts,context,vocab)
        except ValueError:refused+=1
        else:raise AssertionError('invalid selection admitted')
    source=(P/'suite.py').read_text();tree=ast.parse(source)
    assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='select_warmup' for n in ast.walk(tree))
    assert 'warm_prompt=[2,5,3,7,1] if args.mini' not in source
    # No rank launch: capture the controller boundary and simulate first-token
    # EOS termination. Ordinary real requests retain the exact EOS tuple.
    args=SimpleNamespace(mini=False,draft='mtp',script=None,prompt_overlap='on',dump_state=False,
        device=False,controller='native',binary=P/'suite.py',timing='none')
    transport=SimpleNamespace(trace=[],metrics=[dict(busy_ms=0.),dict(busy_ms=0.)],work_end=1.,work_start=0.)
    calls=[]
    def first_eos(_transport,_provider,_prompt,count,eos,_overlap,_dumps):
        tokens=[];head_calls=0
        for token in (suite.EOS[0],7)[:count]:
            if tokens:head_calls+=1
            tokens.append(token)
            if token in eos:break
        calls.append(dict(eos=list(eos),tokens=tokens,draft_decode_head_calls=head_calls))
        return dict(tokens=tokens,timing_rows=[dict(token_id=t,completed_monotonic=.1+i*.1) for i,t in enumerate(tokens)])
    with patch.object(suite.storage,'admit'),patch.object(suite.pipeline,'request_run',side_effect=first_eos):
        warm=suite.run_request(transport,args,seed,2,kernel_warmup=True)
        normal=suite.run_request(transport,args,seed,2)
    assert warm['tokens']==[suite.EOS[0],7] and calls[0]['draft_decode_head_calls']==1 and calls[0]['eos']==[]
    assert normal['tokens']==[suite.EOS[0]] and calls[1]['eos']==list(suite.EOS)
    rows.append(dict(case='first-token-eos-warmup-only',warmup_completed_two=True,normal_eos_unchanged=True,controller_boundary_calls=calls))
    result=dict(passed=True,device_executed=False,rank_processes_started=0,gates=len(rows)+refused+1,
        rows=rows,guards=refused,real_and_mini_vocabulary_checked=True,
        source_sha256={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in ('suite.py','test_suite_warmup.py')},
        scope='selection, source wiring, mocked controller EOS boundary only; integrated order/window/suite gates run separately')
    (P/'suite-warmup-gates.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
