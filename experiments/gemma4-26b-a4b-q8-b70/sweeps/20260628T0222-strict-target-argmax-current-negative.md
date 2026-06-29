# 2026-06-28 Gemma 4 26B Target-Argmax Retest On Current Stack

Purpose: retest exact target/verifier argmax shortcuts after the
`LLAMA_SYCL_F16_P021_SMALL_NCOLS=1` record, because the current node profile
still shows the verifier LM head as the largest single node:
`MUL_MAT:node_2075`, `token_embd.weight`, `q8_0`, avg `1.374 ms/call`.

This was a strict fresh-response screen, not a promoted run:

- fixed realistic suite, each prompt once;
- `cached_tokens=0`;
- `MAX_TOKENS=128`, metric tokens `1-100` after TTFT;
- canary repeats `16` (`64/64` rows per lane);
- same UD-Q8_K_XL target and Q4_0 MTP draft as the current record;
- current record stack including VDR2, route cache, selected-softmax fused,
  weighted-sum, RMS reuse, p021 small-ncols, direct draft argmax unroll, f16 KV.

## Results

Stamp: `20260628T022236Z`

| GPU | Variant | Data dir | Median 1-100 tok/s | p10 | Mean | Full 128 after-TTFT | Wall median | TTFT median ms | Validity |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | control | `../../../data/gemma4-q8-gpu0-strict-vdr2-f16p021-control-n3-nmin2-p00475-ub1024-20260628T022236Z/` | 97.58563658606447 | 87.6963239727767 | 98.39743798491617 | 94.06647019302082 | 82.38759458833343 | 179.67671097721905 | valid |
| 1 | `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` | `../../../data/gemma4-q8-gpu1-strict-vdr2-f16p021-fused_output_argmax-n3-nmin2-p00475-ub1024-20260628T022236Z/` | 87.67811825225914 | 74.1865176898083 | 86.37132340135891 | 88.56003696023194 | 78.43135403799897 | 180.2780344733037 | valid |
| 2 | `LLAMA_SPEC_VERIFY_RAW_ARGMAX=1` | `../../../data/gemma4-q8-gpu2-strict-vdr2-f16p021-raw_argmax-n3-nmin2-p00475-ub1024-20260628T022236Z/` | 97.57278622242288 | 88.91554341802778 | 97.32813004349521 | 95.3876555499982 | 83.29252836062432 | 180.56796304881573 | valid |
| 3 | `LLAMA_SPEC_VERIFY_SOFTCAP_ARGMAX=1` | `../../../data/gemma4-q8-gpu3-strict-vdr2-f16p021-softcap_argmax-n3-nmin2-p00475-ub1024-20260628T022236Z/` | 97.67209740312686 | 87.41987790302787 | 96.84025679127598 | 96.53605807455187 | 83.3868430443107 | 180.5862869368666 | valid |

All lanes had `realistic_final_gate.passed=true` and
`cached_tokens_all_zero=true`.

## Decision

Negative / no promotion.

- Fused output argmax is a large loss on the current stack.
- Raw and softcap argmax are effectively neutral and do not crack 100.
- The #1 LM-head node remains tempting in profiles, but the existing exact
  shortcut implementation does not produce a speed win. Future >100 work should
  focus on the verifier MoE `MUL_MAT_ID` body or a materially different LM-head
  proof, not these existing flags.
