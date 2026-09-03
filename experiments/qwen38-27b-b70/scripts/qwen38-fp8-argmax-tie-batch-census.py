import torch, json, sys
DEV=torch.device("xpu:0"); V=248320; NSEQ=64
torch.manual_seed(1)
logits=torch.randn((NSEQ,V),dtype=torch.float16,device=DEV)*4
# plant exact two-way ties in every row at two positions (low index and high index), and a three-way tie in some rows
ties=[]
for i in range(NSEQ):
    a=int(torch.randint(0,V,(1,))); b=int(torch.randint(0,V,(1,)))
    while b==a: b=int(torch.randint(0,V,(1,)))
    m=float(logits[i].max())+1.0
    logits[i,a]=m; logits[i,b]=m
    if i%4==0:
        c=int(torch.randint(0,V,(1,))); logits[i,c]=m
    ties.append(sorted([a,b]))
ref=[int(torch.argmax(logits[i:i+1],dim=-1)[0]) for i in range(NSEQ)]
ref_first=[min(t) for t in ties]
rows=[]
for B in [1,2,4,8,16,24,31,32,33,40,48,64]:
    am=torch.argmax(logits[:B],dim=-1).tolist()
    mx=torch.max(logits[:B],dim=-1).indices.tolist()
    tk=torch.topk(logits[:B],k=1,dim=-1).indices[:,0].tolist()
    rows.append({"B":B,"argmax_equal_single":am==ref[:B],"argmax_is_lowest_tied_index":all(am[i]==ref_first[i] or logits[i].eq(logits[i,am[i]]).sum()>2 for i in range(B)),
                 "max_indices_equal_argmax":mx==am,"topk1_equal_argmax":tk==am,"first_mismatch_row":next((i for i in range(B) if am[i]!=ref[i]),None)})
    print(rows[-1],flush=True)
print(json.dumps({"single_call_picks_lowest_index":all(r==f for r,f in zip(ref,ref_first)), "any_batch_differs_from_single":any(not r["argmax_equal_single"] for r in rows)}))
json.dump({"rows":rows,"vocab":V,"note":"float16 logits with planted exact ties; per-row reference is the B=1 argmax"},open(sys.argv[1],"w"),indent=1)
