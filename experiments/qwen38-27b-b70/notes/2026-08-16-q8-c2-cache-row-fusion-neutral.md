# Qwen3.8 Q8 c2 cache-row fusion experiment

Status: **closed, endpoint-neutral and not promoted**.

## Why this was tested

With two active server slots, Qwen3.8 keeps two persistent convolution and GDN
state rows. The accepted one-request fusion matchers required the complete
cache to contain only one row, so both state-I/O fusions switched off at c2.
The candidate admits only a complete, row-aligned view inside the exact
multi-row cache selected by `GET_ROWS`. It does not read or alter the row
selector and does not change kernel arithmetic.

## Mechanism and synthetic result

The graph census found selected convolution cache shape `[15360,1]` inside
`[15360,2]`, and selected GDN cache shape `[393216,1]` inside `[393216,2]`.
The candidate then recorded `73,728` convolution and `73,728` GDN state-I/O
fusion hits in the full batched run; the same-binary disabled control recorded
zero. Both reported `VERIFY_MISMATCH=0`.

At `pp64/tg256`, `b1024/ub256`:

| Arm | npl1 | npl2 aggregate |
| --- | ---: | ---: |
| cache-row fusion on | `31.685406` | `35.757645` |
| same binary, both state-I/O doors off | `30.135370` | `33.940235` |

The synthetic npl2 gain was `+5.3547%`. This is useful mechanism evidence,
not a serving record.

## Real endpoint result

Two synchronized cache-zero requests generated 512 tokens each against a
`--parallel 2` server. Three warmed repetitions measured:

- candidate: `55.660044`, `56.437742`, `56.872184 tok/s` aggregate;
- control: `54.562921`, `55.771039`, `56.864596 tok/s` aggregate.

The medians differ by `+1.195%`, but both arms converge to the same roughly
`56.87 tok/s` plateau. The candidate therefore has no robust endpoint gain.

## Quality boundary

Candidate-on and same-binary-off outputs were token/content exact whenever
the same scheduling outcome was compared. However, repeated c2 service runs
alternated between two stable greedy-output hash pairs in **both** arms. The
candidate did not add an output variant, but ordinary c2 scheduling is not
strictly invariant to the c1/sequential output on this lane.

That does not establish semantic corruption, but it fails the repository's
strong no-quality-loss gate for a new headline. The earlier Qwen3.6 canonical
per-vector Q8 crossover already activated successfully and did not remove the
same class of c2 forced-tail divergence, so that closed control is not being
repeated here.

## Reproduce the source delta

Apply the accepted DP4A2 packet first, then decode the incremental patch:

```bash
base64 -d \
  experiments/qwen38-27b-b70/patches/q8-c2-cache-row-fusion-neutral-20260816.diff.gz.b64 \
  | gzip -dc > /tmp/q8-c2-cache-row.patch
sha256sum /tmp/q8-c2-cache-row.patch
git apply --check /tmp/q8-c2-cache-row.patch
git apply /tmp/q8-c2-cache-row.patch
```

The decoded SHA-256 must be
`b76b93ba730909713f8d8f59f2d0916434a23d836e22239de6a73eb19361aa59`.
The complete measurements and raw-log hashes are in
[`2026-08-16-q8-c2-cache-row-fusion-neutral.json`](../data/2026-08-16-q8-c2-cache-row-fusion-neutral.json).

## Decision

Do not enable this delta in the Qwen3.8 Q8 reproduction package and do not add
the c2 rate to the promoted model board. Preserve it as a useful graph-matcher
and negative endpoint result. Continue optimizing the strict c1 target-only
route; any future concurrency score must separately label aggregate throughput
and pass an explicit cross-batch quality gate.
