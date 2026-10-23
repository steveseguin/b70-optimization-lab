import time, sys, openvino_genai as og
MAIN="/home/bosd/ov-models/qwen25-7b-int4"
DRAFT="/home/bosd/ov-models/qwen25-1.5b-int4"
DEV="GPU.1"
PROMPTS={
 "tech":"Explain how speculative decoding speeds up LLM inference. Be precise and technical.",
 "code":"Write a Python function that merges two sorted lists into one sorted list without using sort(). Include a short docstring.",
}
MAXTOK=256
def run(pipe, prompt, spec):
    cfg=og.GenerationConfig(); cfg.max_new_tokens=MAXTOK; cfg.do_sample=False
    if spec: cfg.num_assistant_tokens=5
    res=pipe.generate([prompt],cfg)
    pm=res.perf_metrics
    return dict(tput=pm.get_throughput().mean, ttft=pm.get_ttft().mean,
               tpot=pm.get_tpot().mean, ntok=pm.get_num_generated_tokens(),
               txt=res.texts[0][:120])
def bench(label, spec):
    print(f"\n=== {label} (device {DEV}) ===", flush=True)
    if spec:
        pipe=og.LLMPipeline(MAIN, DEV, draft_model=og.draft_model(DRAFT, DEV))
    else:
        pipe=og.LLMPipeline(MAIN, DEV)
    # warmup
    c=og.GenerationConfig(); c.max_new_tokens=32; c.do_sample=False
    if spec: c.num_assistant_tokens=5
    pipe.generate("warmup",c)
    for name,pr in PROMPTS.items():
        r=run(pipe,pr,spec)
        print(f"[{name}] tput={r['tput']:.1f} tok/s  ttft={r['ttft']:.0f}ms  tpot={r['tpot']:.1f}ms  ntok={r['ntok']}", flush=True)
        print(f"       out: {r['txt']!r}", flush=True)
    del pipe
if __name__=="__main__":
    arm=sys.argv[1] if len(sys.argv)>1 else "both"
    if arm in("nospec","both"): bench("OV INT4 no-spec", False)
    if arm in("spec","both"):   bench("OV INT4 + spec(draft 1.5B, k=5)", True)
