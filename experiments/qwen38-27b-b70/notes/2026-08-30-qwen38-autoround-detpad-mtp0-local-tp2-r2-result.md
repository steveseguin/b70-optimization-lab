# Qwen3.8 AutoRound INT4 deterministic MTP0 local TP2 R2 result

Date: 2026-08-30

Status: **failed closed; optimized speed rejected on exact-output drift**

The corrected current-runtime image passed the complete eager and compiled-A
arm gates on the two local B70s. Both arms directly verified all 19 model
files, used fresh compile/evidence roots, returned complete token IDs for the
fixed 12-prompt/six-class suite, reported zero cached tokens, passed the
independent canaries, and shut down cleanly.

Compiled execution was materially faster: the class-balanced 99-interval
median rose from `17.967660778331` tok/s eager to `31.827338440757` tok/s
compiled (`+77.137%`). That speed is **not promotable**. Compiled-A matched the
eager oracle on only **4/12** complete token arrays, so the preregistered
campaign stopped before compiled-B.

The four exact prompts matched for all 512 tokens. The other eight first
diverged at generated-token positions 9, 60, 182, 223, 275, 335, 437, and
450. This is compatible with small numerical differences accumulating into a
near-tie token choice; R2 alone does not prove whether either execution mode
is independently repeatable.

Decision: quarantine the compiled speed and run one fresh same-mode repeat of
each arm. Eager-vs-eager and compiled-vs-compiled parity must be measured
before choosing between a TP2 nondeterminism repair and a compiler-semantic
localization. MTP remains unauthorized.

Structured result:
[`../data/2026-08-30-qwen38-autoround-detpad-mtp0-local-tp2-r2-result.json`](../data/2026-08-30-qwen38-autoround-detpad-mtp0-local-tp2-r2-result.json)

Preregistration:
[`2026-08-30-qwen38-autoround-detpad-mtp0-local-tp2-r2-prereg.md`](2026-08-30-qwen38-autoround-detpad-mtp0-local-tp2-r2-prereg.md)
