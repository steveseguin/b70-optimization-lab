# Replicated attention: what it actually costs, measured on the no-drafter arm

Date: 2026-08-07 America/Toronto

Status: **closed. It does not fit, and this was the most favourable
configuration that exists on this machine.**

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

## Why util 0.80 cannot work, in one line

    3.92 GiB more weights  +  (2.7 - 0.68) GiB more KV  =  ~5.94 GiB

against **5.34 GiB** of headroom. It is short by roughly 0.6 GiB -- which is
why this was never going to fit at the campaign's standard utilisation, and why
the earlier q12 attempts, with a drafter also resident, failed by a wider
margin.

Raising utilisation to 0.90 adds 0.10 x 31.9 = **3.19 GiB**, and that does
clear the KV requirement -- but not the rest.

## util 0.90 fails too, twice over

| arm | KV allocated | outcome |
| :--- | ---: | :--- |
| util 0.90 | 4.45 GiB / 48,104 tokens | **OOM**: "Tried to allocate 340.00 MiB ... 4.81 GiB is free" |
| util 0.90, KV pinned to 3 GiB | 3 GiB / 36,353 tokens | **`RuntimeError: cancelled`** |

The KV is not the binding constraint at 0.90: 48,104 tokens comfortably exceeds
the 32,768 needed, and pinning it down to 36,353 to hand 1.45 GiB back to the
activation working set did not help either. `RuntimeError: cancelled` is the
bare, causeless failure the runbook already documents for util 0.90 on this
machine.

Model load is **20.83 GiB** with replication against 16.92 GiB without, which
confirms the 3.92 GiB weight cost independently.

## Verdict

**Replicated attention does not fit on a 31.9 GiB B70**, and the no-drafter arm
is the most favourable configuration that exists here -- no DFlash weights, no
DFlash workspace, the largest KV headroom this campaign has ever measured. It
fails below the KV minimum at util 0.80 and fails on the activation working set
at util 0.90.

The -21.7% that the rendezvous measurement priced remains real and remains
unavailable. It is a device-capacity conclusion, not an engineering one: the
lever needs a card with roughly 6 GiB more, exactly as the q12 attempts
implied, and removing the drafter does not buy enough of it back.

## Boundaries

Figures are from the servers' own `Available KV cache memory`, `GPU KV cache
size` and `Model loading took` lines and the KV-sizing refusal, across
`20260807-replattn-nospec-u80`, `-u90` and `20260807-replattn-pin3`; qdepth depth 0,
`LAGUNA_NOSPEC_GRAPH=1`, TP4, EP4, M=1. No quantisation change. The protected
`125.4619731637751 tok/s` conventional short-decode record is untouched.
