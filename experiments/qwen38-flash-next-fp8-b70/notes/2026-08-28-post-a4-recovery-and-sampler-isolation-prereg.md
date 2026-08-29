# Flash-Next post-A4 recovery and sampler-isolation preregistration

Date: 2026-08-28
Status: closed; sampler-native candidate rejected at exact-4K repeat gate

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

## A6 pre-model launcher correction

A6 stopped before worker creation or model loading. The descriptive campaign
suffix made its default IPC path exceed the platform's 107-character Unix
socket limit. No sampler, quality, speed, or model result exists. The complete
attempt-6 directory is retained; no protected result changed.

A7 changes only attempt `6` to `7`, port `19678` to `19679`, and the runtime
IPC directory to the short `/tmp/q38-sn-a7-rpc`. The descriptive campaign,
sampler-native treatment, model/runtime/cache selectors, ordered client, gates,
and frozen interpretations are unchanged. Derived launcher SHA-256:
`4cf10e045028f8a079ebf0940395eef51952a3f20eca1fc07ba73827a64bf334`.
Derived client SHA-256:
`718b9493ed44b22ce1b2495dbdd64dcd5f8522af43e1a6af4f9347ef3f309564`.

## A7 result

A7 loaded and passed the established short semantic/repeat and exact-4K needle
boundary. Its two exact-4K rows measured `5.405351634035985` and
`5.346274611630608 tok/s`, a diagnostic median of
`5.375813122833296 tok/s`. That clears the frozen speed floor, but the two
byte-identical requests returned different 128-token hashes. The second
matches the retained authority; the first does not.

Post-result source audit found the intended treatment was not active for these
greedy requests: `temperature=0` takes the `all_greedy` return before either
top-k/top-p implementation is called. The faster rows are therefore
unattributed diagnostics, not sampler-selector causality.

The frozen client rejected the candidate before either 16K request. Sampler
native therefore receives no promotion or speed/quality/deployment credit, and
no protected result changes. The complete result and immutable evidence
binding are in
[`2026-08-28-tp4-mtp0-sampler-native-a7-result.md`](2026-08-28-tp4-mtp0-sampler-native-a7-result.md)
and
[`../data/20260828-tp4-mtp0-sampler-native-a7-4k-repeat-negative.json`](../data/20260828-tp4-mtp0-sampler-native-a7-4k-repeat-negative.json).
