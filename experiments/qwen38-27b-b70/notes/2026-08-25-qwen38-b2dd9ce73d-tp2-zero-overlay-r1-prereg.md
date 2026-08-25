# Qwen3.8 b2dd/1e90 TP2 zero-overlay R1 preregistration

Status: **preregistered, not launched**. This note and its JSON contract add no
performance claim.

The frozen b2dd/1e90 profile already has a quality-clean TP1 strict A and a
qualified TP4 strict pair. TP2 is the one explicit topology hole for that exact
source stack. This packet fills only that hole; it does not rerun the old
96-cell Cartesian matrix and does not transfer a result from another vLLM,
kernel, model, quant, or topology.

The identity is the existing zero-overlay b2dd image: vLLM
`b2dd9ce73dce2ad09007d1db5c171454118981d7`, XPU kernels
`1e90ffa672ba02f17a909da11838a4c55b199783`, base digest `3ee0ec…f876`,
and image ID `059d4b…bc296`. The run is TP2 on GPUs 0 and 1, MTP0, F16 KV,
graph `FULL_AND_PIECEWISE`, one sequence, 32,768 maximum context, and no
source, decision, DSO, compiled, or prior-cache overlay.

The campaign is three atomic arms: fresh-cache ignore-EOS diagnostic, exact
cache natural-EOS strict A with the complete quality battery, then exact-cache
natural-EOS strict B. Speed never stops the later arms when correctness and
infrastructure remain green. Historical `48.8301 / 48.950458800865434`
diagnostic observations, strict floor `49.01965141150585`, and accepted-overlay
`49.05894025767351 / 49.00935245117815` observations remain protected and are
comparison values only.

The measuring-host wrapper must freeze its current boot ID, host kernel,
hardware-gate identity, this contract hash, and all helper hashes before
launch. It must copy those inputs into a fresh result root and preserve every
failed arm. Only a completed zero-overlay packet may open remapping of the 78
preserved TP2 `.best_config` decisions, and those decisions transfer only by
exact relative path plus equal embedded configuration hash.

The complete identity, paths, ports, external TP2 quality baseline and hash,
non-speed gates, protected values, and acknowledgement string are in
[`2026-08-25-qwen38-b2dd9ce73d-tp2-zero-overlay-r1-prereg.json`](../data/2026-08-25-qwen38-b2dd9ce73d-tp2-zero-overlay-r1-prereg.json).
