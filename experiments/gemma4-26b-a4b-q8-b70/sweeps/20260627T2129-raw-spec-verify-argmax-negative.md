# 2026-06-27: Raw Spec-Verify Argmax Negative

Status: valid strict realistic-suite loss. Do not promote or submit to
LocalMaxxing.

## Context

Current strict record:

- `90.32179401019857 tok/s` median generated-token throughput for tokens
  1-100 after TTFT;
- run:
  `../../data/gemma4-q8-gpu2-strict-vdr2-n3-p00475-repeat-ub1024-v21-20260627T201757Z/summary.json`;
- one B70, llama.cpp `c926ad098`, UD-Q8_K_XL target/verifier, Q4_0 MTP draft,
  VDR2 reordered Q8 MoE-ID, `n_max=3`, `n_min=2`, `p_min=0.0475`,
  `UBATCH_SIZE=1024`, `cached_tokens=0` for every request.

This experiment kept the record-family launch identity and added a default-off
target-verifier shortcut:

```text
LLAMA_SPEC_VERIFY_RAW_ARGMAX=1
```

The idea is exact for greedy Gemma verification when suppress-token bias is
absent: Gemma's final-logit softcap is monotonic, so the argmax of raw LM-head
logits is the same as the argmax after softcap. The patch publishes a
`ggml_argmax()` sampled-row tensor after the LM head and before final softcap,
instead of materializing the final transformed logits.

## Patch

Saved under:

- `../../patches/gemma4-26b-a4b-q8-b70/20260627T2129-raw-spec-verify-argmax-negative.patch`.

The patch artifact is a focused patch sketch against the local dirty Gemma
llama.cpp research stack. It is not a clean upstream patch. The source flag is
default-off, and the harness now records `LLAMA_SPEC_VERIFY_RAW_ARGMAX` in
both launcher stdout and `summary.json` launcher identity.

## Results

All rows below used the fixed realistic prompt suite, sent each prompt once as
a cold first response, reported `cached_tokens=0` on every request, disabled
history/ngram/context-checkpoint reuse, and kept the UD-Q8_K_XL target/verifier
unchanged.

Control after the code change, raw flag unset:

| Run | Median 1-100 tok/s | p10 | Mean | Full512 after TTFT | Wall full512 | TTFT ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/gemma4-q8-gpu0-strict-vdr2-control-postraw-n3-p00475-ub1024-20260627T212929Z/summary.json` | `90.17664351534023` | `79.52860550317845` | `89.57200521790803` | `86.18500994203876` | `82.9722208696096` | `180.85426004836336` |

Initial raw-argmax screen:

| Run | Median 1-100 tok/s | p10 | Mean | Full512 after TTFT | Wall full512 | TTFT ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/gemma4-q8-gpu1-strict-vdr2-rawargmax-n3-p00475-ub1024-20260627T212929Z/summary.json` | `90.61464067224665` | `81.68921721151233` | `91.20625472987204` | `86.63016906679928` | `83.88594788126281` | `179.2410350171849` |
| `data/gemma4-q8-gpu2-strict-vdr2-rawargmax-repeat-n3-p00475-ub1024-20260627T212929Z/summary.json` | `87.89059643839522` | `80.13911170001289` | `87.44232368436398` | `83.8349350179233` | `81.32885135089546` | `180.7560125598684` |
| `data/gemma4-q8-gpu3-strict-vdr2-rawargmax-n3-p004625-ub1024-20260627T212929Z/summary.json` | `84.19942997745622` | `80.98664814055678` | `87.55289778437073` | `82.61357351144176` | `80.28235645883578` | `180.076913558878` |

The GPU1 row slightly exceeded the current record, so it was immediately
retested with four same-config confirmation lanes:

| Run | Median 1-100 tok/s | p10 | Mean | Full512 after TTFT | Wall full512 | TTFT ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/gemma4-q8-gpu0-strict-vdr2-rawargmax-confirm-n3-p00475-ub1024-20260627T213217Z/summary.json` | `85.38010810396247` | `82.2355167995076` | `88.1271755000531` | `84.6779565143749` | `81.57039536902914` | `181.54604051960632` |
| `data/gemma4-q8-gpu1-strict-vdr2-rawargmax-confirm-n3-p00475-ub1024-20260627T213217Z/summary.json` | `86.06270410755482` | `80.73104009048383` | `87.57157844273121` | `85.9443237473533` | `82.86847995443006` | `180.2855459973216` |
| `data/gemma4-q8-gpu2-strict-vdr2-rawargmax-confirm-n3-p00475-ub1024-20260627T213217Z/summary.json` | `88.22852366375129` | `78.3001143833146` | `87.88691925561966` | `83.03899429627498` | `80.67293505815681` | `181.2411454739049` |
| `data/gemma4-q8-gpu3-strict-vdr2-rawargmax-confirm-n3-p00475-ub1024-20260627T213217Z/summary.json` | `87.95831897318453` | `78.91293601676759` | `87.39393552556528` | `83.33742040005906` | `80.8638688207906` | `182.9994940198958` |

## Decision

Valid but not a reproducible win. The first GPU1 observation at
`90.61464067224665 tok/s` did not confirm; the four confirmation lanes ranged
from `85.38` to `88.23 tok/s`. Do not submit or promote.

The patch is still useful as a documented, default-off exact shortcut. It
proved that skipping Gemma final softcap after the LM head is not enough to
move the strict suite materially; the dominant cost remains the target verifier
MoE and full LM-head work. A future verifier candidate-vs-max design would
need to avoid computing the whole vocabulary projection, not just skip the
post-LM-head softcap.
