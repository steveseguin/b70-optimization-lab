"""Does varying the batch composition reproduce the divergence in a controlled process?

A lockstep batch is deterministic: 64 identical prompts submitted together, same length and same
generation cap, return byte-identical outputs at TP2 both eager and under graph capture, and no
same-position row disagrees at any layer. The ladder differs by letting requests drift, so the row
count and membership of each decode step change as generation proceeds.

This induces that drift deliberately while keeping everything else fixed: the same prompt 64 times,
but with generation caps spread across a range so requests retire at different steps and the
composition shrinks. Every request still computes its first COMPARE tokens, so all 64 are directly
comparable over that prefix - and if composition is what matters, some will differ there.

DRIFT=0 reproduces the lockstep control in the same process, so the two arms differ only in the caps.
"""
import json
import os
from collections import Counter
from pathlib import Path

from vllm import LLM, SamplingParams


def main() -> None:
    n = int(os.environ.get("REQUESTS", "64"))
    drift = os.environ.get("DRIFT", "1") == "1"
    cap_min = int(os.environ.get("CAP_MIN", "32"))
    cap_max = int(os.environ.get("CAP_MAX", "128"))
    # Compare the whole generation by default. Comparing a prefix is how the first five runs of this
    # probe returned a clean pass that meant nothing: they generated 128 tokens and compared 64, while
    # in the ladder data 78% of divergences first appear at position 64 or later and the median first
    # difference sits at token 90. A short window does not weaken this test, it removes it.
    compare = int(os.environ.get("COMPARE", str(cap_max)))
    # A prompt with no near-tie cannot show this effect however the batch is composed, and the
    # divergences in the ladder come from twelve prompts selected for sitting on ties. SUITE points at
    # that suite; without it the probe uses one generic prompt and is only a control.
    suite_path = os.environ.get("SUITE")
    if suite_path:
        prompts = [entry["prompt"] for entry in json.loads(Path(suite_path).read_text())["prompts"]]
    else:
        prompts = [
            "Summarise the operational impact of a cache invalidation rule that fires on every write "
            "to the primary index, for an on-call engineer paged at 3am."
        ]
    if compare < cap_max:
        print(f"WARNING compare={compare} < cap_max={cap_max}: most ladder divergences first appear "
              f"at position >=64 (median 90), so this window will miss them", flush=True)
    llm = LLM(
        model="/model", dtype="float16", quantization="compressed-tensors",
        tensor_parallel_size=int(os.environ.get("TP", "2")),
        max_model_len=int(os.environ.get("MAX_MODEL_LEN", "512")), max_num_seqs=n,
        # The ladder runs 512, which forces prefill to be chunked and interleaved with decode so a
        # step can hold both. 8192 fits all 64 prefills in one step and never mixes them.
        max_num_batched_tokens=int(os.environ.get("MAX_BATCHED_TOKENS", "8192")),
        enable_prefix_caching=False, gpu_memory_utilization=0.90, enforce_eager=True,
    )
    # The oracle is the same request run alone - the comparison the identity ladders actually make.
    # One prompt per call, so the oracle really is computed at a single row. Generating all twelve in
    # one call would make the oracle a 12-row batch, which is not what the identity ladders compare
    # against and would quietly hide any effect that needs more rows than that.
    refs = {}
    for i, one in enumerate(prompts):
        o = llm.generate([one], SamplingParams(temperature=0, max_tokens=cap_max, ignore_eos=True))
        refs[i] = tuple(o[0].outputs[0].token_ids[:compare])

    # Half the batch retires early so the composition shrinks *during* the compared window; the first
    # attempt spread caps from 32 to 128 and compared the first 32 tokens, which is exactly the phase
    # where all 64 are still running and the composition is constant.
    if drift:
        caps = [8 if i % 2 else cap_max for i in range(n)]
    else:
        caps = [cap_max] * n
    batch_prompts = [prompts[i % len(prompts)] for i in range(n)]
    owners = [i % len(prompts) for i in range(n)]
    params = [SamplingParams(temperature=0, max_tokens=c, ignore_eos=True) for c in caps]
    out = llm.generate(batch_prompts, params)

    matching = mismatched = 0
    first_diffs = []
    for o, cap, owner in zip(out, caps, owners):
        if cap != cap_max:
            continue
        got = tuple(o.outputs[0].token_ids[:compare])
        ref = refs[owner]
        if got == ref:
            matching += 1
        else:
            mismatched += 1
            k = next((i for i, (a, b) in enumerate(zip(ref, got)) if a != b), min(len(ref), len(got)))
            first_diffs.append((owner, k))
    total = matching + mismatched
    print(f"RESULT drift={int(drift)} prompts={len(prompts)} compared={total} "
          f"compare_prefix={compare} matching_oracle={matching}/{total} diverged={mismatched}")
    for owner, k in first_diffs[:8]:
        print(f"  prompt {owner} diverged from its oracle at token {k}")


if __name__ == "__main__":
    main()
