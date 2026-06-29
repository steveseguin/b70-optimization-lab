# 2026-06-29 Gemma Q8 context threshold: MTP vs no-spec

Purpose: after the short-context `115.8466634928202 tok/s` fresh-response
record, characterize the safe service/context split for Gemma 4 26B A4B
UD-Q8_K_XL on one B70. This is diagnostic context work, not a LocalMaxxing
headline throughput lane.

All rows used:

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft when enabled: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- synthetic unique prompt mode (`filled-long-unique`), requested prompt `8192`
  tokens, actual prompt `11076` tokens;
- output `64` tokens;
- `cached_tokens=0`;
- no prompt/KV/response/history reuse;
- `CANARY_REPEATS=2` (`8` canary rows), all canaries passed.

These numbers are **not** fixed realistic-suite headline results and must not be
submitted to LocalMaxxing as fresh-response records. They are service/context
diagnostics.

## 32K no-spec UBATCH/flash screen

Aggregate:
`data/gemma4-ctx32k-nospec-ubatch-flash-screen-20260629T205432Z.json`

| Lane | Context | Spec | UBATCH | Flash | Decode tok/s after TTFT | TTFT | Wall tok/s | Decision |
| --- | ---: | --- | ---: | --- | ---: | ---: | ---: | --- |
| `gpu0-ub1024-faoff` | 32768 | no-spec | 1024 | off | `54.9579` | `7.507s` | `7.380` | stable control |
| `gpu1-ub512-faoff` | 32768 | no-spec | 512 | off | `56.4630` | `9.836s` | `5.834` | slightly faster decode, worse TTFT |
| `gpu2-ub2048-faoff` | 32768 | no-spec | 2048 | off | `54.8168` | `7.528s` | `7.360` | no win |
| `gpu3-ub1024-faon` | 32768 | no-spec | 1024 | on | `58.1179` | `11.152s` | `5.223` | best decode, worse TTFT |

Conclusion: the 32K no-spec fallback is stable and around `55-58 tok/s` decode
after TTFT for an ~11K actual prompt. Flash attention improves short decode a
little but hurts TTFT/wall for this one-row screen; keep it as a service-lane
tunable, not a short-record change.

## MTP context threshold screen

Aggregate:
`data/gemma4-context-threshold-mtp-vs-nospec-20260629T205608Z.json`

| Lane | Context | Spec | Decode tok/s after TTFT | TTFT | Wall tok/s | Result |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| `gpu0-mtp-ctx16384` | 16384 | MTP n3/n2/p0.0475 | `94.2030` | `7.788s` | `7.559` | excellent |
| `gpu1-mtp-ctx24576` | 24576 | MTP n3/n2/p0.0475 | `72.7155` | `12.659s` | `4.727` | useful |
| `gpu2-mtp-ctx28672` | 28672 | MTP n3/n2/p0.0475 | `12.5037` | `12.678s` | `3.596` | cliff |
| `gpu3-nospec-ctx32768-faon` | 32768 | no-spec | `57.8802` | `11.208s` | `5.197` | stable 32K fallback |

This confirms the earlier 32K finding: the catastrophic long-context issue is
MTP/context-size interaction, not the Q8 target alone. MTP at 16K is much faster
than no-spec. MTP at 28K is worse than no-spec 32K.

## 24K-27K MTP refinement

Aggregate:
`data/gemma4-context-refine-mtp-24k-27k-20260629T205750Z.json`

| Lane | Context | Decode tok/s after TTFT | TTFT | Wall tok/s | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| `gpu0-mtp-ctx24576` | 24576 | `73.6826` | `16.888s` | `3.604` | repeat confirms useful |
| `gpu1-mtp-ctx25600` | 25600 | `73.3232` | `16.604s` | `3.662` | practical upper MTP context |
| `gpu2-mtp-ctx26624` | 26624 | `67.6844` | `15.356s` | `3.926` | degraded but still service-usable |
| `gpu3-mtp-ctx27648` | 27648 | `12.0790` | `14.811s` | `3.183` | cliff |

## Practical service split

- Short/small context record lane remains unchanged:
  `CTX_SIZE=8192`, MTP n3/n2/p0.0475, fixed realistic cold suite,
  `115.8466634928202 tok/s` median tokens 1-100 after TTFT.
- With flash attention off, medium/long context with MTP is usable through
  `CTX_SIZE=24576` or `25600`; `26624` is a warning zone and `>=27648` cliffs.
- For long-context service, turn flash attention on. The follow-up below shows
  that `FLASH_ATTN=on` removes the MTP draft-context cliff through true 32K.

Next context work should either:

1. isolate the MTP-at-large-context cliff in `ggml_sycl_mul_mat_id` /
   draft-context memory behavior; or
2. build a service recipe that switches profiles by requested context:
   short record stays FA-off, long context uses MTP with FA-on.

Do not change the short-decode record recipe until a candidate has rerun the
fixed realistic cold suite and proven no regression.

## Follow-up: flash attention fixes the 27K-32K MTP cliff

Aggregate:
`data/gemma4-context-mtp-faon-longctx-20260629T210754Z.json`

Hypothesis: the cliff was draft-context memory pressure from non-FA V-cache
padding. The FA-off logs warned that variable V-cache layers were padded to
2048, and the `ctx27648` FA-off run spent `3199.785 ms` cumulatively in MTP
draft generation versus `362-410 ms` at `ctx24576/26624`.

Follow-up lanes used the same Q8 target, Q4_0 MTP draft, record MTP flags,
f16 KV, `FLASH_ATTN=on`, one synthetic unique ~11K-token prompt, output `64`,
`cached_tokens=0`, and 8/8 canary rows passing. These remain diagnostic
service-context results, not LocalMaxxing headline rows.

| Context | VMM | Decode tok/s after TTFT | TTFT | Wall tok/s | MTP draft-generation cumulative |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 27648 | 0 | `102.781` | `11.183s` | `5.421` | `152.239 ms` |
| 28672 | 0 | `102.728` | `11.285s` | `5.375` | `151.791 ms` |
| 32768 | 0 | `102.828` | `11.118s` | `5.451` | `152.694 ms` |
| 32768 | 1 | `103.225` | `11.155s` | `5.435` | `151.450 ms` |

Conclusion: flash attention, not VMM, is the important service switch. It
removes the draft-generation cliff and makes MTP viable at true `CTX_SIZE=32768`
for this long-context diagnostic shape. Keep the short-context record recipe
unchanged (`FLASH_ATTN=off`) unless a fixed realistic final-gate retest proves
FA-on is not a short-decode regression.
