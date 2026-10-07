# Packet100: 20/28 setup refused before measurement — October 7, 2026

The first **20/28 placement candidate failed during component setup**, before
text graph capture, full clip generation or timing. This is an integration bug,
not evidence that the split is slower or changes output quality. The qualified
99b 23/25 control remains the comparison baseline.

The [closeout](../data/resume-20261007/closeout-100.json) binds the exact packet,
server identity, failed request/history, source, logs, incomplete summary,
preregistration and health receipts. Failed packet100 manifest:
`5f156563da17edda65d8e0042a90344de665c5c93d4b61b603fc8ff0f9037bbc`.

## Observed failure and cause

The text-window probe request
`f100-twoway2028w2b1p1dxpu2s256x256-wprobe`, prompt UUID
`9cd737dd-59a8-4ce4-81b1-fdd45d829828`, failed in node420
`LTXHostEmbeddingComponents`. Its history reports no outputs and execution
error `Shard owners do not match the multi-segment placement`. The component
receipt records phase `load-upscaler-and-split` and retained partial owners;
model construction had been attempted. This was not a model-free refusal.

In the preserved packet's
`source/custom_nodes/ltx_host_embedding_lab/__init__.py:85`, `shared_identity`
uses the following predicate whenever a segment identity is present:

```python
len(shards) == len(segments) - 1 and len(shards) >= 2
```

The new layout uses explicit segments `(xpu:0,0,20)` and `(xpu:1,20,48)`.
Its one secondary shard owner satisfies the correct segment/owner cardinality
but fails the historical requirement for at least two secondary owners. The
older two-way installation used the separate `segments is None` identity
branch; adding a valid two-segment placement exposed the untested consumer.

**The CPU review missed this.** Tests checked all48 blocks' route coverage,
device ownership and invalid segment plans, but did not execute the actual
host `shared_identity` function with the new representation. Source-integrity
and placement-plan tests passed without covering this setup integration.
The missing text-window receipt is a consequence of that exception. Likewise,
the later summary's missing probe/timed/context-sentry entries are unexecuted
gates, not observed tensor mismatches.

## Stop and scope of the result

The campaign proved quiescence, issued one SIGINT at **14:17:40 UTC**, and
recorded PID3193292 gone at **14:17:50 UTC**. Campaign exit was11; stop exit
was0. Four-card postflight completed **14:18:58 UTC**, all cards passed with
zero recorded GPU-fault lines this boot. No full clips or timed prompts ran;
there is no throughput value, output-parity verdict or realized speedup.

Keep the failed packet and all request, construction, identity, summary and
log evidence unchanged. The roughly9% placement benefit remains a hypothesis.

## Narrow successor100b correction

Create a separate immutable successor that corrects the host identity owner's
cardinality contract for supported segment representations and updates its
dependent source pins. Preserve the legacy two-way identity and existing
multi-segment behavior; do not merely bypass identity checking. CPU regression
coverage must exercise the actual consuming function with two segments and
one secondary owner, legacy and larger valid layouts, and missing/extra owners
or malformed identities.

Retain 99b's qualified RoPE arithmetic, source/dependency identity except this
explicit integration fix, B1, BF16, 8+3 sampling, fixtures and all output,
memory and health gates. A successor still needs successful setup and full
reference parity before its timing can test the20/28 hypothesis. This note
does not launch or qualify that successor.
