"""Greedy repeat probe: same prompt, same pipeline, several generations; then a second pipeline."""
import hashlib, os, sys
import openvino_genai as og
MAIN=os.environ["OV_MAIN"]; DEV=os.environ.get("OV_DEV","GPU.0")
P={"tech":"Explain how speculative decoding speeds up LLM inference. Be precise and technical.",
   "code":"Write a Python function that merges two sorted lists into one sorted list without using sort(). Include a short docstring."}
def cfg(n):
    c=og.GenerationConfig(); c.max_new_tokens=n; c.do_sample=False; return c
def h(t): return hashlib.sha256(t.encode()).hexdigest()[:8]
warm = os.environ.get("WARM","1")=="1"
for inst in (1,2):
    pipe=og.LLMPipeline(MAIN,DEV)
    if warm: pipe.generate("warmup",cfg(32))
    for name,pr in P.items():
        hs=[h(pipe.generate([pr],cfg(256)).texts[0]) for _ in range(5)]
        print(f"instance{inst} warm={warm} {name}: {' '.join(hs)}", flush=True)
    del pipe
