# Laguna width-12 graph-safe attention: matched control

Date: 2026-07-26 America/Toronto

Status: **control invalid on exactness; nested capture gain too small**.

Artifacts:

```text
control=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m12-attngraph-control-20260726T184124Z
candidate=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m12-attngraph3-20260726T183027Z
```

Both legs used the same vLLM commit, kernel commit, attention binary, width 12,
DFlash depth 11, metadata off, fusion selectors off, and all other recorded
identity fields. The sole intended treatment difference was the attention
capture selector.

| | eager attention control | nested attention graphs |
| --- | ---: | ---: |
| scored median tok/s | 97.130796 | **97.659756** |
| exact vs q=1 | **12/13** | **13/13** |
| topology, every rank | 146/145 | 146/145 |
| cached tokens | 0 on 13/13 | 0 on 13/13 |

The control diverged on `structured-extraction` at generated-token index 57,
so it is not a valid promotion control. On the twelve rows whose token streams
match, nested attention capture won 8/12 and the median candidate/control rate
ratio was `1.005294` (+0.529%). This is directionally positive but too small to
close the 1.47% gap from the standing exact result.

The nested implementation deliberately preserves all outer segments and
replaces each eager attention call with a tiny separate graph replay. It
therefore still performs 48 attention-boundary Python calls per target cycle.
Now that the actual paged-decode kernel is graph-recordable, the next candidate
should instead record attention directly into its surrounding outer segment.
That candidate must keep the proven persistent metadata path, retain the 97
collective boundaries, and require exactly 98 outer graphs / 97 eager breaks
on every rank: 146/145 minus the 48 retired attention boundaries.

Both legs cleaned up successfully and left the devices idle.
