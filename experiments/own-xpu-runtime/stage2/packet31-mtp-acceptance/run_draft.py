"""Consume incremental CPU captures; independently warm every shifted draft row."""
import json,os,time,hashlib,resource
from pathlib import Path
import torch
from draft_reference import P,BF,SafeStore,Draft,Bindings
B=P/"build";names=("incident-retrospective","code-review","customer-email","benchmark-analysis")
torch.set_num_threads(1);torch.set_num_interop_threads(1)
assert os.getpriority(os.PRIO_PROCESS,0)==19

def save(path,value):
    tmp=path.with_suffix(path.suffix+".tmp");tmp.write_text(json.dumps(value,indent=2)+"\n");tmp.replace(path)
def wait_rows(path,n):
    while True:
        if path.exists():
            lines=path.read_text().splitlines()
            try:rows=[json.loads(l) for l in lines]
            except json.JSONDecodeError:rows=[]
            if len(rows)>=n:return rows
        receipt=P/"target-run-receipt.json"
        if receipt.exists():
            r=json.loads(receipt.read_text())
            if any(v.get("returncode",0) for v in r["prompts"].values()):raise RuntimeError("target failed")
        time.sleep(2)

@torch.inference_mode()
def main():
    s=SafeStore();bindings=Bindings(s);bindings.prepare_coarse()
    receipt={"device_executed":False,"torch":torch.__version__,"threads":1,"pid":os.getpid(),"prompts":{}}
    for name in names:
        directory=B/name;inp=json.loads((B/("input-"+name)/"input.json").read_text());n=len(inp["tokens"])
        variants={"mtp_fp8_iq3":Draft(s),"mtp_int8_iq3":Draft(s,True),"mtp_fp8_official":Draft(s)}
        timings={k:[] for k in variants};head_timings={k:[] for k in variants}
        records=[]
        with (B/(name+"-draft.jsonl")).open("w") as out:
            for j in range(n+63):
                target=wait_rows(directory/"predictions.jsonl",j+2)
                x=target[j+1]["input_token"]
                raw=(directory/f"streams-{j}.bf16").read_bytes();assert len(raw)==20480
                streams=torch.frombuffer(bytearray(raw),dtype=BF).reshape(1,4,2560)
                idx=j-(n-2);record={"generated_index":idx,"target_position":j+1,"draft_position":j,"input_token":x,"target_token":target[j+1]["target_token"],"sources":{}}
                for key,model in variants.items():
                    official=key.endswith("official");start=time.monotonic()
                    sample=model(streams,bindings.embedding(x,official),j)
                    timings[key].append(time.monotonic()-start)
                    if 0<=idx<64:
                        sample_bytes=sample.contiguous().view(torch.uint8).numpy().tobytes()
                        (directory/f"sample-{idx}-{key}.bf16").write_bytes(sample_bytes)
                        start=time.monotonic();logits=bindings.logits(sample,official)
                        head_timings[key].append(time.monotonic()-start)
                        assert torch.isfinite(logits).all()
                        order=torch.argsort(logits,descending=True,stable=True)[:4]
                        top=order.tolist();margin=float(logits[top[0]]-logits[top[1]])
                        record["sources"][key]={"draft_token":top[0],"hit":top[0]==record["target_token"],"draft_margin":margin,"top4":top,"top4_logits":logits[order].tolist(),"sample_bf16_sha256":hashlib.sha256(sample_bytes).hexdigest()}
                        if key=="mtp_fp8_iq3":
                            for k,candidate in bindings.shortlists(sample,logits).items():record["sources"]["shortlist_"+k]={**candidate,"hit":candidate["draft_token"]==record["target_token"]}
                if 0<=idx<64:
                    records.append(record);out.write(json.dumps(record)+"\n");out.flush()
                    print(name,idx,{k:v["draft_token"] for k,v in record["sources"].items()},flush=True)
                if j%10==0:print("cache",name,j,flush=True)
        receipt["prompts"][name]={"prompt_tokens":n,"draft_rows":n+63,"layer_seconds":timings,"head_seconds":head_timings,"experts_seen":{k:sorted(v.experts_seen) for k,v in variants.items()}}
        receipt["peak_rss_kib"]=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        save(P/"draft-run-receipt.json",receipt)
        save(P/"tensor-read-receipt.json",s.receipt)
        save(P/"iq3-binding-read-receipt.json",bindings.iq.read_receipt)
    bindings.iq.close()
if __name__=="__main__":main()
