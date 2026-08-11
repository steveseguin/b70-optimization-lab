import json, urllib.request, time, itertools, random
random.seed(20260811)
topics=["a REST API rate limiter","a git bisect helper","an LRU cache","a CSV deduplicator","a log parser","a retry decorator","a task scheduler","a binary search variant","a JSON schema validator","a websocket echo server","a bloom filter","a topological sorter","a token bucket","a trie autocompleter","a diff formatter","a connection pool","a circuit breaker","a merkle tree verifier","a cron expression parser","an interval tree","a priority queue with decrease-key","a rolling hash deduper","a base62 shortener","a semver comparator","a glob matcher","a streaming median tracker","an LFU cache","a rate-limited work queue","a dependency resolver","a state machine for orders"]
langs=["Python","TypeScript","Go","Rust","C++","Java"]
jsonspecs=["a server migration runbook","a release checklist","an incident postmortem timeline","a database backup plan","a CI pipeline definition","a k8s rollout plan","an oncall handover summary","a capacity planning worksheet","a security audit checklist","a data retention schedule","a chaos test scenario list","a service dependency inventory","a feature flag rollout plan","a load test matrix"]
prose=["how B-tree indexes accelerate range queries","how TCP congestion control works","how copy-on-write filesystems snapshot data","how vector clocks order distributed events","how bloom filters trade accuracy for space","how LSM trees absorb write bursts","how consistent hashing rebalances shards","how MVCC databases isolate transactions","how quorum reads tolerate replica lag","how write-ahead logs enable crash recovery","how CRDTs merge concurrent edits","how epoll scales socket readiness","how NUMA affinity affects throughput","how speculative execution leaks became Spectre","how B+ tree page splits amortize","how leader election works in Raft"]
prompts=[]
for t,l in itertools.product(topics,langs): prompts.append(f"Implement {t} in {l}. Include brief comments.")
for j in jsonspecs: prompts.append(f"Produce only a JSON array of 10 objects with fields name, priority, eta_minutes describing {j}. No prose.")
for p in prose: prompts.append(f"Write a clear technical explanation of {p}.")
random.shuffle(prompts)
path="/mnt/fast-ai/bench-results/muse-glimmer-30b/distill/harvest-v3-tokens.jsonl"
have=set()
try:
    for line in open(path): have.add(json.loads(line)["prompt"])
except FileNotFoundError: pass
out=open(path,"a")
def post(url,payload,timeout=900):
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(req,timeout=timeout).read())
done=len(have); fails=0
for p in prompts[:500]:
    if p in have: continue
    try:
        msgs=[{"role":"system","content":"Reasoning strength: low"},{"role":"user","content":p}]
        tp=post("http://127.0.0.1:19470/apply-template",{"messages":msgs},60)
        tok=post("http://127.0.0.1:19470/tokenize",{"content":tp["prompt"],"add_special":True},60)
        r=post("http://127.0.0.1:19470/completion",{"prompt":tp["prompt"],"n_predict":768,"temperature":0,"cache_prompt":False,"return_tokens":True})
        out.write(json.dumps({"prompt":p,"prompt_tokens":tok["tokens"],"gen_tokens":r.get("tokens",[]),"text_head":r["content"][:80]})+"\n"); out.flush()
        done+=1; time.sleep(2)
    except Exception as e:
        fails+=1; time.sleep(20)
print("harvest-v2 complete:",done,"fails:",fails)
