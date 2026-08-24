# Ornith 1.5 35B-A3B: UR single-thread mode is serving-negative

Date: 2026-08-23 EDT

Status: **CLOSED SERVING NEGATIVE — keep the setting unset**

`UR_L0_SINGLE_THREAD_MODE=1` removes some Unified Runtime synchronization for
applications that can guarantee single-threaded runtime access. Ornith's
Qwen-derived one-token graph has many sequential submissions, making it a
plausible low-overhead screen, but `llama-server` has multiple host threads and
the setting cannot be accepted from a CLI microbenchmark alone.

Both arms retained the accepted
`UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1` setting and kept immediate command
lists unset. The same binary produced a byte-identical canonical 128-token
transcript in the control and candidate arms (SHA-256
`d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`),
with all 1,270 Q/K fusion hits in each.

The mirrored seven-repetition raw-engine A/B/B/A screen was weakly positive:

| Arm | Run means, tok/s | Arm mean |
| --- | --- | ---: |
| unset control | 132.875860, 132.732812 | **132.804336** |
| single-thread candidate | 133.369302, 133.056952 | **133.213127** |

That is **+0.308%**, a drift-sized signal that required serving validation.

The decisive fresh 12-prompt server sequence reversed the result:

| Arm | Run medians, tok/s | Mean of run medians |
| --- | --- | ---: |
| unset control | 131.473903, 128.653411 | **130.063657** |
| single-thread candidate | 129.423814, 130.408452 | **129.916133** |

The candidate changed the primary serving metric by **-0.113%**. Its
prompt-matched grand mean regressed from 126.222048 to 125.646807 tok/s
(**-0.456%**) and it won only 3/12 prompt pairs. All 48 responses were
unique-prompt, uncached, and passed the freshness/finality gates.

Therefore the engine-only result does not transfer to serving. Keep
`UR_L0_SINGLE_THREAD_MODE` unset; the accepted Ornith recipe and its
then-current result remain unchanged. The historical `129.568467 tok/s`
headline used legacy 100-event compatibility accounting; the conventional mean
was `128.272782 tok/s`. The structured decision, raw engine/server JSON, exact
transcripts, and server logs are adjacent under `../data/` with prefix
`2026-08-23-ornith35b-ur-single-thread-`.
