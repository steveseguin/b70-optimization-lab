"""Reference-lab copy of reported/ov-bench.py.

Same prompts, config and arms as the contributor's harness; paths and device
come from the environment so the file carries no host paths, and each prompt
is repeated REPS times so the record has a mean and spread. Run with the venv
described in lab-run.md:

    OV_MAIN=... OV_DRAFT=... OV_DEV=GPU.0 python ov-bench-lab.py both
"""
import json
import os
import statistics
import sys
import time

import openvino_genai as og

MAIN = os.environ["OV_MAIN"]
DRAFT = os.environ.get("OV_DRAFT", "")
DEV = os.environ.get("OV_DEV", "GPU.0")
REPS = int(os.environ.get("OV_REPS", "3"))
PROMPTS = {
    "tech": "Explain how speculative decoding speeds up LLM inference. Be precise and technical.",
    "code": "Write a Python function that merges two sorted lists into one sorted list without using sort(). Include a short docstring.",
}
MAXTOK = 256


def run(pipe, prompt, spec):
    cfg = og.GenerationConfig()
    cfg.max_new_tokens = MAXTOK
    cfg.do_sample = False
    if spec:
        cfg.num_assistant_tokens = 5
    t0 = time.perf_counter()
    res = pipe.generate([prompt], cfg)
    wall = time.perf_counter() - t0
    pm = res.perf_metrics
    return dict(tput=pm.get_throughput().mean, ttft=pm.get_ttft().mean,
                tpot=pm.get_tpot().mean, ntok=pm.get_num_generated_tokens(),
                wall_s=wall, text=res.texts[0])


def bench(label, spec, record):
    print(f"\n=== {label} (device {DEV}) ===", flush=True)
    if spec:
        pipe = og.LLMPipeline(MAIN, DEV, draft_model=og.draft_model(DRAFT, DEV))
    else:
        pipe = og.LLMPipeline(MAIN, DEV)
    c = og.GenerationConfig()
    c.max_new_tokens = 32
    c.do_sample = False
    if spec:
        c.num_assistant_tokens = 5
    pipe.generate("warmup", c)
    arm = {"label": label, "device": DEV, "prompts": {}}
    for name, pr in PROMPTS.items():
        reps = [run(pipe, pr, spec) for _ in range(REPS)]
        tputs = [r["tput"] for r in reps]
        same = len({r["text"] for r in reps}) == 1
        print(f"[{name}] tput={statistics.mean(tputs):.1f} tok/s "
              f"(sd {statistics.pstdev(tputs):.1f}, {REPS} reps)  "
              f"ttft={reps[0]['ttft']:.0f}ms  tpot={reps[0]['tpot']:.1f}ms  "
              f"ntok={reps[0]['ntok']}  identical_text={same}", flush=True)
        print(f"       out: {reps[0]['text'][:120]!r}", flush=True)
        arm["prompts"][name] = {"reps": reps, "identical_text": same}
    record["arms"].append(arm)
    del pipe


if __name__ == "__main__":
    arm = sys.argv[1] if len(sys.argv) > 1 else "both"
    out = os.environ.get("OV_OUT", "")
    record = {"openvino_genai": og.__version__, "arms": []}
    if arm in ("nospec", "both"):
        bench("OV INT4 no-spec", False, record)
    if arm in ("spec", "both") and DRAFT:
        bench("OV INT4 + spec(draft 1.5B, k=5)", True, record)
    if out:
        with open(out, "w") as f:
            json.dump(record, f, indent=1)
