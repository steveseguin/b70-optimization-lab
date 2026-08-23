# Ornith 1.5 35B-A3B: disabling Level Zero copy offload improves serving

Date: 2026-08-23 EDT

Status: **ACCEPTED FOR THIS ONE-B70 RECIPE — +1.09% incremental serving**

Ornith 1.5 is Qwen-derived, so a runtime setting already useful in this lab's
Qwen work was screened against the accepted eleven-feature Ornith source
stack. `UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1` keeps copies on the compute
queue instead of allowing Level Zero copy-engine offload. This changes runtime
scheduling, not model arithmetic. `UR_L0_USE_IMMEDIATE_COMMANDLISTS` remained
unset in both arms because its independent Ornith serving screen was negative.

The same accepted binary produced the exact canonical 128-token transcript
with copy offload enabled by default and forcibly disabled:

`d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`

The transcripts were byte-identical and both runs reported all 1,270 expected
Q/K-normalization-plus-RoPE hits.

The mirrored seven-repetition `llama-bench tg128` order was A/B/B/A:

| Arm | Run means, tok/s | Arm mean |
| --- | --- | ---: |
| unset control | 132.201931, 130.868828 | **131.535380** |
| copy offload disabled | 133.157095, 133.219630 | **133.188363** |

That is a directly measured **+1.257%** raw-engine improvement.

The decisive fresh 12-prompt server order was also A/B/B/A:

| Arm | Run medians, tok/s | Mean of run medians |
| --- | --- | ---: |
| unset control | 128.623495, 127.708166 | **128.165830** |
| copy offload disabled | 130.159639, 128.977294 | **129.568467** |

The primary serving metric improved **+1.094%**. Across prompt-matched
averages, the candidate won 9/12 prompts and changed the grand prompt mean
from 124.298526 to 125.727855 tok/s (**+1.150%**). The pooled per-prompt
medians were 128.338155 and 129.373200 tok/s.

All 48 responses were unique-prompt and uncached, and all freshness/finality
gates passed. One control response emitted 506 text chunks and one candidate
response emitted 504 while llama.cpp usage reported 512 completion tokens;
this known informational mismatch still left more than the required 100
timing events and did not invalidate either measurement.

Therefore the Ornith one-B70 launch recipe now sets
`UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1`. This is a recipe-only runtime win:
the complete source patch, its eleven default-off feature doors, and all
binary hashes remain unchanged. It is not promoted as a global default for
other models or devices. The existing 0-32K graph remains a directly measured
profile of the eleven-feature source stack before this setting; no points are
scaled or inferred.

The structured decision, raw engine/server JSON, exact transcripts, and server
logs are adjacent under `../data/` with prefix
`2026-08-23-ornith35b-copy-offload-`.
