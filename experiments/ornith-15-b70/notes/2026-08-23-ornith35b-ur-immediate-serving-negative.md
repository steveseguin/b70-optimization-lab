# Ornith 1.5 35B-A3B: UR immediate command lists regress serving

Date: 2026-08-23 EDT

Status: **CLOSED SERVING NEGATIVE — keep the setting unset**

Our Qwen B70 recipes often set `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`.
Ornith 1.5 is Qwen-derived and its one-token graph still contains many small,
sequential launches, so the runtime setting was a reasonable transfer
candidate. It changes command submission rather than model arithmetic.

The same accepted binary produced the exact canonical 128-token transcript
with the setting unset and set to `1`:

`d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`

Both runs reported all 1,270 expected Q/K-normalization-plus-RoPE hits.

The mirrored seven-repetition `llama-bench tg128` screen looked modestly
positive:

| Arm | Run means, tok/s | Arm mean |
| --- | --- | ---: |
| unset control | 131.497193, 131.593061 | **131.545127** |
| `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1` | 132.462213, 131.630191 | **132.046202** |

That is **+0.381%**, enough to justify but not replace realistic serving
validation.

The decisive fresh 12-prompt server order was A/B/B/A:

| Arm | Run medians, tok/s | Mean of run medians |
| --- | --- | ---: |
| unset control | 130.088850, 127.999243 | **129.044046** |
| immediate-list candidate | 129.383466, 127.450965 | **128.417216** |

The candidate regressed the primary serving metric by **0.486%**. Across
prompt-matched averages, the candidate won only 4/12 prompts and changed the
grand prompt mean from 125.077583 to 124.465999 tok/s (**-0.489%**). All 24
responses per arm were unique-prompt, uncached, full-window completions and
passed the freshness/finality gates.

Therefore the engine-only signal does not transfer to serving. Keep
`UR_L0_USE_IMMEDIATE_COMMANDLISTS` unset in the Ornith package. The structured
decision, all raw engine/server JSON, exact transcripts, and server logs are
adjacent under `../data/`.
