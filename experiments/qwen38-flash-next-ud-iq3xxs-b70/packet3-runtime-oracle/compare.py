#!/usr/bin/env python3
"""Validate fixtures and compare independent arithmetic implementations honestly."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OLD=HERE.parent/'packet2-cpu-oracle'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def margin(step,other=None):
    ids,logits=step['top5_ids'],step['top5_logits']
    r=dict(top1_id=ids[0],top2_id=ids[1],top1_logit=logits[0],top2_logit=logits[1],top1_top2_margin=logits[0]-logits[1])
    if other is not None:
        r['other_id']=other
        if other in ids:r['margin_over_other']=logits[0]-logits[ids.index(other)]
        else:r['margin_over_other_lower_bound']=logits[0]-logits[-1]
    return r
def main(run):
    run=Path(run).resolve();directory=run/'incident-retrospective'
    result=json.loads((directory/'result.json').read_text())
    oldpath=OLD/'runs/official-sigmoid-20261011/incident-retrospective/result.json'
    old=json.loads(oldpath.read_text());receipt=json.loads((run/'receipt.json').read_text())
    assert receipt['result_sha256']==sha(directory/'result.json')
    assert json.loads((directory/'arithmetic.json').read_text())==receipt['arithmetic']
    for name,digest in receipt['arithmetic']['arithmetic_sources'].items():assert sha(ROOT/name)==digest,name
    source_validation={}
    for name,digest in receipt['source_hashes'].items():
        current=ROOT/name;snapshot=run/(current.name+'.snapshot')
        chosen=current if sha(current)==digest else snapshot
        assert sha(chosen)==digest,name
        source_validation[name]=str(chosen.relative_to(ROOT))
    token_rows=[json.loads(line) for line in (directory/'tokens.jsonl').read_text().splitlines()]
    assert token_rows==result['steps']
    assert [s['token_id'] for s in token_rows]==result['tokens']
    teardown=json.loads((directory/'teardown.json').read_text())
    assert len(teardown)==1 and teardown[0]['safe_to_exit'] and teardown[0]['live_bytes']==teardown[0]['in_flight']==0
    assert json.loads((directory/'input.json').read_text())['tokens']==json.loads((oldpath.parent/'input.json').read_text())['tokens']
    layers={}
    for d in sorted(directory.glob('step*')):
        records=[json.loads(line) for line in (d/'layers.jsonl').read_text().splitlines()]
        assert [r['layer'] for r in records]==list(range(48)),d
        for r in records:
            f=d/f"layer-{r['layer']:02}.bf16"
            assert f.stat().st_size==20480 and r['shape']==[1,4,2560] and r['sha256']==sha(f),f
            layers[str(f.relative_to(directory))]=sha(f)
    assert len(result['tokens'])>=8 and len(layers)==384
    real=ROOT/'experiments/own-xpu-runtime/stage2/packet13-integrate/evidence/real-layer/layer-00.bf16'
    assert (directory/'step1/layer-00.bf16').read_bytes()==real.read_bytes()
    mismatches=[]
    for i,(a,b) in enumerate(zip(result['tokens'],old['tokens'])):
        if a!=b:mismatches.append(dict(step=i+1,runtime_id=a,blas_id=b,
            same_input_history=not mismatches,runtime=margin(result['steps'][i],b),blas=margin(old['steps'][i],a)))
    comparison=dict(informational_only=True,blas_result=str(oldpath.relative_to(ROOT)),blas_sha256=sha(oldpath),
        runtime_result_sha256=sha(directory/'result.json'),compared_tokens=min(len(result['tokens']),len(old['tokens'])),
        common_prefix_tokens=mismatches[0]['step']-1 if mismatches else min(len(result['tokens']),len(old['tokens'])),
        mismatches=mismatches,first_divergence=mismatches[0] if mismatches else None,
        caveat='After the first divergence, histories differ; later margins are separate autoregressive distributions, not rounding-error estimates. Includes nonlinear/PLE rebase as well as matmul order.')
    save(run/'blas-comparison.json',comparison)
    sys.path.insert(0,str(OLD))
    spec=importlib.util.spec_from_file_location('old_compare',OLD/'compare.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    prior=json.loads((OLD/'runs/official-sigmoid-20261011/baseline-comparison.json').read_text())
    store=mod.Store();tok=mod.Tokenizer(store.meta);store.close()
    prior_row=next(r for r in prior['rows'] if r['id']=='incident-retrospective')
    sources=[Path(prior['baseline'])/'repeat1-incident-retrospective.stdout',Path(prior['baseline_vs_baseline']['left'])]
    digests=[prior_row['baseline_stdout_sha256'],prior['baseline_vs_baseline']['left_sha256']]
    base=dict(informational_only=True,scope='incident-retrospective only',rows=[],onecard_rows=[],retained_stdout=[],
        caveat='llama.cpp stdout is re-tokenized: framing, truncation and exact terminal-token ID cannot be recovered. No baseline logits are available.',
        source_comparison_sha256=sha(OLD/'runs/official-sigmoid-20261011/baseline-comparison.json'),
        comparator_sha256=sha(Path(__file__)),runtime_result_sha256=sha(directory/'result.json'))
    visible=[i for i in result['tokens'] if i not in (248044,248046)]
    for i,p in enumerate(sources):
        dst=run/f'llamacpp-{i+1}.stdout'
        if not dst.exists():dst.write_bytes(p.read_bytes())
        assert sha(dst)==digests[i],dst
        raw,text=mod.visible_stdout(dst);ids=tok.encode(text);common=0
        for a,b in zip(visible,ids):
            if a!=b:break
            common+=1
        row=dict(id='incident-retrospective',card_count=2 if i==0 else 1,source=dst.name,
            baseline_retokenized_ids=ids,agreement_tokens=common,
            baseline_logits_available=False,**mod.text_comparison(tok.decode(visible),text))
        if common<min(len(visible),len(ids)):
            row['first_divergence']=dict(step=common+1,runtime_id=visible[common],baseline_id=ids[common],
                runtime_margin=margin(result['steps'][common],ids[common]))
        else:row['first_divergence']=None
        if i==0:row['baseline_record']=prior_row['baseline_record']
        base['rows' if i==0 else 'onecard_rows'].append(row)
        base['retained_stdout'].append(dict(path=dst.name,original=str(p),sha256=sha(dst)))
    save(run/'baseline-comparison.json',base)
    valid=dict(passed=True,device_executed=False,prompt_tokens=result['prompt_tokens'],generated_tokens=len(result['tokens']),
        fixture_hashes=layers,real_layer0_runtime_reference_sha256=sha(real),
        layer0_bit_identical=True,full_model_fresh_process_repeat=False,
        prefill_seconds=result['prefill_seconds'],decode_seconds_per_token=result['decode_seconds_per_token'],
        max_rss_bytes=result['max_rss_kib']*1024,comparison_producer_sha256=sha(Path(__file__)))
    valid['validated_source_locations']=source_validation
    valid['cpu_allocations_released']=True
    save(run/'validation.json',valid)
    print(json.dumps({k:v for k,v in valid.items() if k!='fixture_hashes'},indent=2))
if __name__=='__main__':main(sys.argv[1])
