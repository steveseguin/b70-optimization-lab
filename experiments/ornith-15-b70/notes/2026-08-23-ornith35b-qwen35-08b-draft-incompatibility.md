# Ornith 1.5 35B-A3B: Qwen3.5-0.8B is not a usable draft

Date: 2026-08-23 EDT

Status: **CLOSED COMPATIBILITY/CORRECTNESS NEGATIVE — no throughput claim**

Ornith 1.5 is Qwen-derived, so the locally available Qwen3.5-0.8B Q8 model was
a reasonable substantially-smaller draft candidate. Unlike Ornith 1.5 9B, it
is small enough to fit beside the target and fast enough to justify checking
the pairing rather than rejecting it from model size alone.

The vocabulary/tokenizer gate passed exactly. A multilingual probe containing
punctuation, accents, CJK text, arithmetic, and the Qwen chat delimiters
produced the same 22 token IDs in both GGUF files. The two archived ID files
are byte-identical.

The draft's standalone one-B70 `tg128` measurement was
**270.750869 ± 0.200258 tok/s** across seven repetitions. This is direct draft
model throughput, not assisted Ornith throughput.

The bounded combined probe used the accepted 11-feature Ornith target, greedy
sampling, a 2K context, a maximum of three draft tokens, and both models on the
same B70. It failed the correctness gate:

- 360 tokens were drafted and only 8 accepted (**2.222%**);
- the runtime repeatedly reported inconsistent M-RoPE sequence positions
  during speculative rollback (`X < Y` was violated);
- the emitted raw-prompt continuation was visibly degenerate.

Because decode repeatedly returned errors, none of that combined run's timing
counters are valid throughput evidence. Do not tune draft depth or publish a
speed row for this pair. Matching token IDs is necessary but not sufficient:
the draft must also predict the retrained Ornith distribution and the runtime
must support correct rollback for the two architectures.

The structured decision is in
`../data/2026-08-23-ornith35b-qwen35-08b-draft-summary.json`. The standalone
draft benchmark, token-ID probes, and complete failed combined transcript/log
are adjacent to it.
