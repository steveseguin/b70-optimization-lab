# Flash-Next post-A4 recovery and sampler-isolation preregistration

Date: 2026-08-28
Status: Stage A5 passed; sampler-native candidate frozen before execution

## Evidence-driven question

A3 proved that one fresh active-16K request can complete correctly, while its
identical same-server repeat produced repeated text. A4 failed on a distinct
fresh server at 1,600 computed prompt tokens because the output rank did not
return from `sample_tokens` within the frozen 300-second worker bound. The
model execution step itself had completed. This makes the enabled XPU sampler
path a narrower common boundary than request-state clearing.

The current convolution path already receives `has_initial_state=false` for a
fresh request, and the recurrent path explicitly zeroes its gathered initial
state. The older related-Qwen program also found explicit fresh-state clearing
insufficient by itself. That treatment is therefore not repeated here.

## Stage A5: recovery gate

Run exactly
`tools/run-post-a4-recovery-stage-a5.sh`. It requires the unchanged model,
vLLM `1372c62d`, kernel source `ad25aa9f`, current boot, external evidence
mount, 110,100,480-KiB host-memory floor, four idle cards, four isolated-card
checks, all twelve peer links, a four-rank XCCL all-reduce, and no new B70 or
system-memory failure in the bounded journal. It grants no model, speed,
quality, or deployment credit. Failure stops the program.

Frozen helper SHA-256:
`396175754ee32352bdc61bd3e9c6ffc234fbe30701296e0a4ea9541322f1c491`.

Stage A5 passed. All four isolated checks returned `2097152.0`, all twelve
directed peer checks returned true, and ranks 0--3 each returned exact XCCL
all-reduce `4.0`. The bounded journal contained no matching B70, system-memory,
or I/O failure. Its immutable external manifest-file SHA-256 is
`566d3f7a12384c2bd984ff11419307a4999bec4aad3423cbe5bf5a69b7466ac3`.

## Candidate treatment and frozen order

If Stage A5 passes, start one separately identified TP4/EP4/eager/MTP0 server
with every accepted A3/A4 model, source, offload, cache, scheduling, graph,
collective, and decoding selector unchanged except:

```text
VLLM_XPU_USE_SAMPLER_KERNEL=0
```

This selects the existing native PyTorch sampling path. It does not alter the
accepted recipe or any protected result. The server must first pass the exact
active-4K semantic/repeat comparator and retain at least 95% of the protected
`4.7578181021380175 tok/s` conventional median. A slower result, any semantic
failure, any timeout, or a failed teardown rejects the candidate before 16K.

Only after the 4K gate passes may the same server receive two identical
active-16K semantic requests. Required promotion evidence is two semantic
passes, zero reported cache use, matching output and token-ID hashes, no worker
timeout, and a clean bounded teardown. A sole pass, a sole failure, or mixed
behavior remains Grade-D diagnostic evidence. No 24K/32K run is authorized.

Interpretations are frozen:

- stable 4K plus stable repeated 16K supports sampler-path causality and creates
  a deployment-candidate recipe that still needs broader quality replay;
- stable 4K plus a 16K worker timeout rejects the sampler path as the timeout
  cause and moves the next trace to rank progress around `sample_tokens`;
- stable first 16K plus corrupted repeat means the repeated-output mechanism
  remains upstream of or independent from sampler selection;
- any new B70 event stops the lane and requires another health decision.

Frozen candidate launcher SHA-256:
`e7773a62cce32aa5e649bd16b8958789a4ad2a4b0d359d808119863ee1aad616`.
Frozen ordered client SHA-256:
`942e886f1726220f04e706f27a8a63eb252e8b7632b7636f1ea1d2f1c8dc71e1`.
