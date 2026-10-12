"""Seal target gates and report causal acceptance; no device work."""
from pathlib import Path
import hashlib,json,math,statistics
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/"build"
NAMES=("incident-retrospective","code-review","customer-email","benchmark-analysis")
SEALED=ROOT/"experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective"
def sha(p):
    with p.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+"\n")
def wilson(h,n):
    if n==0:return [None,None]
    z=1.959963984540054;p=h/n;d=1+z*z/n;c=(p+z*z/(2*n))/d
    a=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0,c-a),min(1,c+a)]
def stats(rows):
    hits=[bool(r["hit"]) for r in rows];h=sum(hits);n=len(hits);longest=run=0
    last=None
    for row in rows:
        if row.get("prompt")!=last:run=0;last=row.get("prompt")
        run=0 if row["hit"] else run+1;longest=max(longest,run)
    deciles=[]
    for d in range(10):
        vals=[r["hit"] for r in rows if r["generated_index"]*10//64==d]
        deciles.append(dict(decile=d+1,hits=sum(vals),misses=len(vals)-sum(vals),count=len(vals)))
    return dict(hits=h,count=n,acceptance=h/n if n else None,wilson95=wilson(h,n),longest_miss_run=longest,deciles=deciles)
def lookups(tokens,p):
    uni={};bi={}
    for i in range(1,p+1):
        uni[tokens[i-1]]=tokens[i]
        if i>=2:bi[tuple(tokens[i-2:i])]=tokens[i]
    u=uni.get(tokens[p],tokens[p]);b=bi.get(tuple(tokens[p-1:p+1]),u)
    return dict(unigram=u,bigram=b,repeat_current=tokens[p])
def main():
    allrows=[];gates={};timing={};preserved={}
    for name in NAMES:
        d=B/name;inp=json.loads((d/"input.json").read_text());n=len(inp["tokens"])
        result=json.loads((d/"result.json").read_text());assert result["arithmetic"]=="iq3-p17-detmath-v2"
        assert len(result["tokens"])==64 and result["status"]=="token-cap"
        predictions=[json.loads(l) for l in (d/"predictions.jsonl").read_text().splitlines()]
        assert len(predictions)==n+64
        assert [r["target_token"] for r in predictions[n-1:n+63]]==result["tokens"]
        inputs=[r["input_token"] for r in predictions];assert inputs==inp["tokens"]+result["tokens"]
        files={f.name:sha(f) for f in sorted(d.glob("streams-*.bf16"))}
        assert len(files)==n+64 and all(f.stat().st_size==20480 for f in d.glob("streams-*.bf16"))
        gate={"generated_tokens":64,"positions":n+64,"streams_shape":[4,2560],"streams_dtype":"BF16 little endian","stream_hashes":files}
        if name=="incident-retrospective":
            sealed=json.loads((SEALED/"result.json").read_text())
            assert result["tokens"]==sealed["tokens"]
            comparisons=[]
            for step in range(1,9):
                fresh=d/f"streams-{n+step-2}.bf16";old=SEALED/f"step{step}/layer-47.bf16"
                assert fresh.read_bytes()==old.read_bytes()
                comparisons.append(dict(step=step,position=n+step-2,sha256=sha(old),exact=True))
            gate.update(sealed_64_tokens_exact=True,layer47_fixtures=comparisons,sealed_result_sha256=sha(SEALED/"result.json"))
        gates[name]=gate
        raw=[json.loads(l) for l in (B/(name+"-draft.jsonl")).read_text().splitlines()]
        assert [r["generated_index"] for r in raw]==list(range(64))
        for r in raw:
            p=r["target_position"];assert r["draft_position"]==p-1 and p==n-1+r["generated_index"]
            assert r["target_token"]==predictions[p]["target_token"] and r["input_token"]==inputs[p]
            r["prompt"]=name;r["next_next_token"]=predictions[p+1]["target_token"]
            exact=r["sources"]["mtp_fp8_iq3"]
            for k,v in lookups(inputs,p).items():r["sources"][k]=dict(draft_token=v,hit=v==r["target_token"],draft_margin=None)
            for k in (2,4):r["sources"][f"mtp_top{k}"]=dict(draft_tokens=exact["top4"][:k],hit=r["target_token"] in exact["top4"][:k],draft_margin=exact["draft_margin"])
            for k in ("mtp_fp8_iq3","mtp_int8_iq3","mtp_fp8_official"):
                s=r["sources"][k];s["copy_current_hit"]=s["draft_token"]==r["input_token"]
                s["next_next_hit"]=s["draft_token"]==r["next_next_token"]
                s["agrees_with_fp8_iq3"]=s["draft_token"]==exact["draft_token"]
            allrows.append(r)
        positions=[json.loads(l) for l in (d/"positions.jsonl").read_text().splitlines()]
        timing[name]=dict(mean_seconds_per_position=statistics.mean(r["seconds"] for r in positions),median_seconds_per_position=statistics.median(r["seconds"] for r in positions),prefill_mean_seconds_per_position=statistics.mean(r["seconds"] for r in positions[:n]),decode_mean_seconds_per_position=statistics.mean(r["seconds"] for r in positions[n:]),positions=len(positions),max_rss_kib=result["max_rss_kib"])
        preserved[name]={"input":inp,"result":result,"predictions":predictions,"positions":positions}
    first=B/"incident-first-draft.jsonl"
    if not first.exists():first=P/"draft-repeat-first.jsonl"
    if first.exists():
        previous=[json.loads(l) for l in first.read_text().splitlines()]
        current=[r for r in allrows if r["prompt"]=="incident-retrospective"]
        assert len(previous)==len(current)==64
        checked=0
        for old,new in zip(previous,current):
            assert old["target_token"]==new["target_token"]
            for source,record in old["sources"].items():
                for key,value in record.items():
                    if source.startswith("shortlist_") and key=="draft_margin":continue
                    assert new["sources"][source][key]==value,(old["generated_index"],source,key)
                    checked+=1
        retained=P/"draft-repeat-first.jsonl"
        if first!=retained:retained.write_bytes(first.read_bytes())
        prior_receipt=B/"first-draft-run-receipt.json"
        if prior_receipt.exists():(P/"draft-repeat-first-receipt.json").write_bytes(prior_receipt.read_bytes())
        save(P/"draft-repeat-gate.json",dict(first_artifact=retained.name,prompt="incident-retrospective",positions=64,
            exact_fields_compared=checked,all_equal=True,first_jsonl_sha256=sha(first),
            repeat_jsonl_sha256=sha(B/"incident-retrospective-draft.jsonl"),
            reason="Fresh CPU draft process after adding shortlist-margin/sample receipts; numerical algorithms unchanged"))
    summary={}
    for source in allrows[0]["sources"]:
        summary[source]={}
        for prompt in (*NAMES,"pooled"):
            rs=[r for r in allrows if prompt=="pooled" or r["prompt"]==prompt]
            rows=[dict(**r["sources"][source],prompt=r["prompt"],generated_index=r["generated_index"]) for r in rs]
            v=stats(rows)
            if "copy_current_hit" in rows[0]:
                v["copy_current_hits"]=sum(r["copy_current_hit"] for r in rows)
                v["next_next_hits"]=sum(r["next_next_hit"] for r in rows)
                v["agreement_with_fp8_iq3"]=sum(r["agrees_with_fp8_iq3"] for r in rows)/len(rows)
            summary[source][prompt]=v
    models=[]
    for source,groups in summary.items():
        # top-k hits require multiple guesses and cannot parameterize a one-guess pipeline.
        if source.startswith("mtp_top"):continue
        for prompt,v in groups.items():
            p=v["acceptance"]
            for T in (42,36,32):
                for m in (3,2,1):
                    ms=p*(T/2+m)+(1-p)*T
                    models.append(dict(source=source,prompt=prompt,acceptance=p,target_ms=T,draft_ms=m,sequential_tps=1000/T,pipelined_ms=ms,pipelined_tps=1000/ms,measured_speed=False))
    save(P/"acceptance.json",dict(schema="own-runtime.mtp-acceptance.v1",scope="CPU draft-semantic reference; development prompts; not a benchmark",summary=summary,positions=allrows))
    save(P/"target-gates.json",gates);save(P/"target-evidence.json",preserved);save(P/"timing-model.json",models);save(P/"target-timing.json",timing)
    print(json.dumps({k:v["pooled"] for k,v in summary.items()},indent=2))
if __name__=="__main__":main()
