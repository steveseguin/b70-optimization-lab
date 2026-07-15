# DeepSeek V4 K160 MTP2 reuse deadlock closure

Date: 2026-07-15

Status: closed without a throughput result or submission.

## Experiment

The K160 checkpoint contains one attached MTP layer. vLLM permits two draft
tokens by executing that layer twice. This changes target verification from
M=2 to M=3. The row-exact compressor diagnostic was generalized from exactly
two rows to narrow verifier widths 2-4 in vLLM commit
`4e47b18c97f359e8973e7069c6d2eb0f2d68bf7a`; larger prefill matrices are
untouched.

Run:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mtp2-rowexact-graph-oneccl1712-20260715T1900Z`

Identity: `--spec-method mtp --spec-tokens 2`, row-exact compressor enabled,
otherwise the promoted MTP1 graph/collective/fusion identity.

## Evidence

- model loading and M=3 graph capture passed;
- ten initial ordered exact captures passed 10/10, all cached-zero;
- realistic traffic showed first-position acceptance around 73-81%;
- second-position acceptance was only about 0.5-2.2%;
- cumulative metrics at termination were 724 accepted of 1,796 drafted token
  positions (40.31% position-average acceptance);
- one realistic request stopped making progress;
- the engine reported no available shared-memory broadcast block after 60,
  120, and 180 seconds;
- the benchmark was interrupted and produced no valid suite JSON.

The exact pre-hang gate proves that the generalized compressor route handles
M=3 arithmetic for short sequences. It does not make repeated use of the
single MTP layer economically useful, and it does not repair the later engine
deadlock.

## Decision

Close MTP2 and all larger repeated-single-layer MTP widths. Do not report a
throughput number and do not submit. The second draft contributes virtually
no accepted tokens on the realistic suite while doubling draft positions and
introducing a hang. Restore MTP1 as the live endpoint.

The next credible speed work is inside the qualified MTP1 cycle: remove the
cost of its row-exact M=2 compressor repair without changing the two-M=1
arithmetic boundary, or reduce verifier/sampler overhead. Any candidate still
requires the 20-capture sustained replay gate.
