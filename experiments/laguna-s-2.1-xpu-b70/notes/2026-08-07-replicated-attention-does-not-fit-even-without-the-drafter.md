# Replicated attention: what it actually costs, measured on the no-drafter arm

Date: 2026-08-07 America/Toronto

Status: **negative for the tested B70 configurations. The util-0.80 capacity
failure is measured; the util-0.90 failures are host/runtime-confounded and do
not establish a general device-capacity requirement.**

## Why retry it here

Replicating the attention heads on every rank retires the 48 attention-O
all-gathers, half of the 96 collectives, which the 2026-08-04 rendezvous
measurement priced at **-21.7% of step time**. It was blocked on q12 for
memory: the card is 31.9 GiB and the replicated weights did not fit alongside
the drafter.

The no-drafter arm looked like the configuration where it might fit. No DFlash
weights and no DFlash context-KV workspace are resident, and the arm reports
**5.34 GiB of KV headroom against q12's ~2.89 GiB**. It also stands to gain
more: at M=1 the collectives are a larger share of a ~15 ms step than of q12's
~26 ms one.

## The cost, measured rather than estimated

At util 0.80, with replicated attention on, the server reports **1.42 GiB** of
available KV cache where the same arm without it reports **5.34 GiB**.

| quantity | value |
| :--- | ---: |
| KV headroom, baseline | 5.34 GiB |
| KV headroom, replicated attention | **1.42 GiB** |
| **weight cost of replication, per rank** | **3.92 GiB** |

That is larger than the ~3.18 GiB predicted from the attention parameter count
(48 layers x ~11M params x 4 ranks worth, BF16), so replication carries about
0.7 GiB of overhead beyond the raw weights.

And the KV requirement grows at the same time, because replicated attention
leaves the KV unsharded -- each rank now holds all 8 KV heads rather than 2.
vLLM's own refusal states it exactly:

```
ValueError: To serve at least one request with the model's max seq len
(32768), 2.7 GiB KV cache is needed ...
```

against 0.68 GiB for the sharded baseline at the same context.

## Why util 0.80 cannot work

The direct post-replication comparison is the relevant one:

    2.70 GiB required KV - 1.42 GiB available KV = 1.28 GiB short

The earlier `3.92 + (2.70 - 0.68) = 5.94 GiB` arithmetic double-counted the
comparison against baseline headroom. Equivalently, baseline has only
`5.34 - 0.68 = 4.66 GiB` spare after its own minimum KV reservation, again
leaving `5.94 - 4.66 = 1.28 GiB` short. The tested util-0.80 arm therefore
cannot serve 32K, but the deficit is **1.28 GiB**, not 0.6 GiB.

Raising utilisation to 0.90 adds 0.10 x 31.9 = **3.19 GiB**, and that does
clear the KV requirement -- but not the rest.

## util 0.90 fails too, twice over

| arm | KV allocated | outcome |
| :--- | ---: | :--- |
| util 0.90 | 4.45 GiB / 48,104 tokens | **OOM**: "Tried to allocate 340.00 MiB ... 4.81 GiB is free" |
| util 0.90, KV pinned to 3 GiB | 3 GiB / 36,353 tokens | **`RuntimeError: cancelled`** |

The KV is not the first reported constraint at 0.90: 48,104 tokens comfortably
exceeds the 32,768 needed. However, the first failure was a host OOM event and
the pinned-KV run ended only with the causeless `RuntimeError: cancelled` that
the runbook documents for util 0.90 on this machine. Those outcomes do **not**
prove an activation-working-set limit or quantify how much larger a card would
need to be.

Model load is **20.83 GiB** with replication against 16.92 GiB without, which
confirms the 3.92 GiB weight cost independently.

## Verdict

**Replicated attention did not produce a runnable 32K service in any tested
31.9 GiB B70 configuration.** The no-drafter util-0.80 arm is a clean capacity
negative: it is 1.28 GiB short of the required KV allocation after replicated
weights load. The util-0.90 arms are failures, but host/runtime confounding
prevents attributing them specifically to device activation capacity.

The -21.7% collective opportunity remains unavailable in this tested lane.
This evidence does not support the earlier claim that a card roughly 6 GiB
larger is required; establishing a minimum capacity would need a clean device-
memory-controlled run without the host OOM/cancellation confounders.

## Boundaries

Figures are from the servers' own `Available KV cache memory`, `GPU KV cache
size` and `Model loading took` lines and the KV-sizing refusal, across
`20260807-replattn-nospec-u80`, `-u90` and `20260807-replattn-pin3`; qdepth depth 0,
`LAGUNA_NOSPEC_GRAPH=1`, TP4, EP4, M=1. No quantisation change. The protected
`125.4619731637751 tok/s` conventional short-decode record is untouched.
