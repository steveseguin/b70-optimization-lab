# A concurrency ladder's exactness is a property of the prompt suite (2026-09-09)

From the 20-pass `f1` arm, one B70, Qwen3.5-4B W4A16, c64, 160 requests per base
prompt per arm.

## The numbers

The small-context ladder suite has eight base prompts, expanded to 64 slots by
appending a case suffix. Divergence against the sequential oracle is not spread
over them:

| base prompt | depth 3 | MTP0 |
| --- | ---: | ---: |
| `cache` | **55.62%** | 1.88% |
| `capacity` | 18.12% | 1.25% |
| `rollback` | 16.25% | 1.25% |
| `index` | 12.50% | 1.25% |
| `benchmark` | 3.75% | 0% |
| `monitoring` | 0% | 0% |
| `testing` | 0% | 0% |
| `evidence` | 0% | 0% |

Three of the eight never diverge, in 160 requests each, in either arm. One
diverges in more than half of them.

## Which prompt is fragile is a property of the model, not the text

Pooling every ladder on disk per lane (mixed concurrencies and configs, so the
totals are not comparable across lanes — only the shape within a lane is):

| base prompt | 4B, c64 depth 3 | 9B, all ladders | 27B, all ladders |
| --- | ---: | ---: | ---: |
| `cache` | **55.62%** | 0.62% | 4.00% |
| `monitoring` | 0% | **19.16%** | 1.22% |
| `index` | 12.50% | 14.39% | 4.87% |
| `rollback` | 16.25% | 9.71% | 5.81% |
| `capacity` | 18.12% | 0.49% | 6.22% |
| `benchmark` | 3.75% | 4.31% | 4.46% |
| `testing` | 0% | 1.64% | 2.05% |
| `evidence` | 0% | 0.37% | 4.17% |

The same eight prompts produce three different profiles. `cache` is the 4B's
worst prompt and among the 9B's quietest; `monitoring` is the reverse. So a
fragile site is not a property of the prompt — it is a point where that
particular model's own decoding is ambiguous, and each model has its own.

Two consequences. A fragile suite must be rebuilt per model; the 9B's cannot be
reused on the 4B. And the 27B's flat profile (1.2% to 6.2%, no dominant prompt)
is a different regime from the other two, matching its site statistics: 126 sites
over 947 divergences, about 7.5 events per site, against the 9B's 102 sites over
2491, about 24 per site.

## Why it matters

Every identity claim this lab has made — the W4A16 row-invariance argument, the
c16 exactness ceiling, the FP8-versus-INT4 comparison, the pad and row-wise
all-reduce evaluations — is a count of divergent requests against **this** suite.
Those counts are dominated by `cache`, and a suite built from `monitoring`,
`testing` and `evidence` would have reported 0/1920 at c64 depth 3 where this one
reports 170/1280: the same server, the same kernel, the same concurrency, and the
opposite verdict.

That does not invalidate any comparison between arms, because every arm ran the
same suite. It does mean:

- "exact at c16" is shorthand for "exact at c16 on the 2026-08-25 small-context
  suite", and the suite belongs in the sentence.
- A new suite is not interchangeable with this one. Swapping it silently changes
  the sensitivity of every gate that uses it, in either direction.
- Comparing a divergence count across lanes that used different suites is not
  meaningful, and the strict realistic suite and this ladder suite are different
  instruments measuring different things.

## Slot position is confounded here and cannot be read from this data

Divergence also varies by slot octant (3.8% to 23.1% across eight octants that
are balanced by base prompt). That looks like a row-position effect but is not
readable as one: the default expansion appends a distinct case suffix per slot,
so every slot is a different prompt text. Position and content cannot be
separated in this data.

Chain 2's `g2` arm is the clean test — the fragile suite run with
`--verbatim-prompts --pin-slots`, so the text is byte-identical across slots and
the slot assignment is fixed. `g3` varies arrival timing at fixed text for the
same reason.

## Practical consequence for the fragile suite

`build-fragile-suite.py` selects on measured rate, so it inherits this: the 4B
c64 fragile suite is seven of the eight `cache` copies plus the higher-rate
`capacity`, `rollback`, `index` and `benchmark` slots. It is a deliberately
biased instrument for comparing interventions at high event rate, and it must
never be used to state an absolute exactness rate for a configuration.
