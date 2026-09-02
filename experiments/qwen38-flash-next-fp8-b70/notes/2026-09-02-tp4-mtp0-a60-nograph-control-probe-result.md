# Qwen3.8 Flash-Next FP8 A60 no-graph control probe result

Date: 2026-09-02 14:59--15:31 EDT, boot `95bac684-...`, GuC 70.72.1
Status: diagnostic complete for depth 256 and six of eight first-step
repeats at 2048; the seventh 2048 request hung the engine (same class as
A59); no host freeze

## Result

Eager server (A59 identity minus the full decode graph; `--enforce-eager`,
`XPU_GRAPH=0`, identity `eager=1 graph=none`), load `~600 s`, healthy at
15:14:48.

| depth | first-step top-5 identical (8 repeats) | top-1 logprob spread | 128-token repeats | first divergence | max top-1 logprob diff before divergence |
|---|---|---|---|---|---|
| 256 | no | `0.2175` nats (`-1.560535 .. -1.342998`); one repeat tied top-1/top-2 | 3 distinct outputs | 71, 15 | `0.453`, `0.104` |
| 2048 | no (6 repeats before the hang) | top-1 `-0.000044 .. -0.000776`; runner-up logits swung `-8.50 .. -11.25` | not reached | | |

The third 256-token output (`79277509...`) is byte-identical to one of the
graph server's A58 outputs at the same depth: the eager and graph lines draw
from the same set of nondeterministic outcomes.

## Interpretation

- The full decode graph is not the source of the jitter; the source is in
  the path both lines share (prefill and first decode step included).
- The top-2 logit gaps step in multiples of `0.125` across repeats, i.e.
  BF16 ulps at logit magnitude 16--32. The jitter is a few BF16 ulps of the
  final logits, the signature of reduction-order nondeterminism (collective
  or split-K accumulation) amplified through the network, not a corrupted
  computation. It is still a hard failure of the lab's bitwise standard.
- The hang class is also graph-independent: the seventh identical 2048
  `max_tokens=1` request stalled (`Running: 1 reqs`, zero throughput from
  15:25:55), the EngineCore died at 15:30:44, and teardown logged GPU page
  faults on `0000:23:00.0`. Postflight failed closed (exit 70), swap and
  ASPM were restored, the four B70s enumerate, root SSD counters remain 0.

## Next

A61: same identity with the public oneCCL preload and `twoshots` removed
(bundled library, as in the deterministic 2026-08-28 eager line), probed at
8, 64, 256, and 2048 tokens.
