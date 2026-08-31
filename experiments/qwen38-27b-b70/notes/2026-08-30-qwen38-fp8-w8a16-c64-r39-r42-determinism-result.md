# Qwen3.8 FP8/W8A16 TP2 c64 determinism: r39-r42

The high-concurrency MTP1 optimization remains blocked by target-control
nondeterminism. No MTP1 candidate rate from this sequence is promoted.

## What was established

- r39's two fresh MTP0 servers completed every request with zero cached tokens,
  but matched only 56/64 complete token arrays. Their directly observed rates
  were 818.904338 and 839.902698 aggregate tok/s. MTP1 did not run.
- r40 enabled vLLM global batch invariance, RMS batch invariance, and the
  serial-exact GDN path. Startup failed closed because GDN did not advertise
  batch-invariance support. No endpoint or request existed.
- r41 applied the existing conditional GDN capability advertisement to matched
  MTP0 and MTP1 images. The selector passed, but deterministic Inductor refused
  combo-kernel benchmarking during startup profiling. No endpoint or request
  existed.
- r42 disabled both combo-kernel generation and combo benchmarking in both
  arms. Control A completed 64/64 at 426.460235 tok/s. Fresh control B completed
  64/64 at 433.405519 tok/s but matched only 55/64 token arrays. MTP1 again did
  not run.

## Decision

Reject global batch invariance for this performance lane. It did not repair the
fresh-server output mismatch and roughly halved aggregate throughput. Preserve
it only as negative mechanism evidence.

Continue from the narrower arithmetic/runtime repairs. The current AutoRound
INT4 determinism-padding build is a separate lane: it addresses oneDNN W4A16
prefill row ranges and must not be represented as a repair for this official
FP8/W8A16 c64 control until a matched mechanism test proves that relationship.

Structured result:
[`../data/2026-08-30-qwen38-fp8-w8a16-mtp1-c64-batch-invariant-no-combo-r42-result.json`](../data/2026-08-30-qwen38-fp8-w8a16-mtp1-c64-batch-invariant-no-combo-r42-result.json).
