# The collective is not broken; the volume is

Date: 2026-08-04 America/Toronto

Status: **measured. Corrects the "6.85 GB/s fabric ceiling" framing in
[`2026-08-04-collective-latency-floor-and-remaining-upside.md`](2026-08-04-collective-latency-floor-and-remaining-upside.md)
and removes a false lead from the next-steps list.**

## The standalone benchmark now reproduces the trace

The earlier benchmark swept 72 KiB, the payload a 12-row decode step would move
if the MoE dispatch sent one copy per token. It does not; it sends one copy per
routed expert. Re-run at the size the warm trace actually shows:

| payload | standalone | in-situ (trace p50) |
| ---: | ---: | ---: |
| 1,440 KiB | **225.0 us** | **205 us** |
| 2,880 KiB | 434.2 us | -- |

Within 10%. The standalone harness and the serving path agree once the payload
is right, which retires the "2.7x unexplained in-situ gap" that the earlier note
posed as an open question. There was no gap; the benchmark was measuring the
wrong size.

## The fabric is running near PCIe speed, not far below it

The earlier note quoted a **6.85 GB/s** ceiling and called it "far below what
PCIe should deliver", listing an investigation of that gap as a next step. That
number is payload divided by time, which undercounts: in a four-rank allgather
each rank receives `world - 1` peer payloads.

```
payload per rank         1,440 KiB
bytes into a rank        4,320 KiB   (3 peers)
time                       225 us
real ingress bandwidth   19.66 GB/s
measured PCIe H2D        28.70 GB/s
                      => 69% of PCIe
```

**69% of PCIe for a four-way allgather is respectable, not broken.** oneCCL is
not leaving 4x on the table, and the nine configuration arms that changed
nothing were not failing to unlock anything. Re-testing the two most promising
knobs at the correct 1.4 MB payload confirms it: 225.0 us baseline against
223.5 us with `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0`, a 0.7% difference.

**Remove "investigate the fabric ceiling" from the work list.** It was my own
accounting error and would have cost someone a day.

## What this leaves

If the transport is near hardware limits and the knobs are exhausted, the only
way to spend less time in collectives is to move fewer bytes. That is the volume
argument from the warm trace, unchanged and now better supported:

| scheme | per step | at 19.66 GB/s ingress |
| :--- | ---: | ---: |
| EP all2all (today) | ~70.8 MB modelled, 24.7 ms measured | -- |
| TP all-reduce | 3.54 MB | ~0.2 ms |

Two routes, neither of which is a configuration change:

1. **Reduce volume** -- TP-shard the experts so each layer all-reduces a 74 KB
   hidden state instead of dispatching 1.44 MB to ten experts. Blocked by five
   interlocking contracts
   ([`2026-08-04-expert-parallelism-is-unmeasurable-five-contracts.md`](2026-08-04-expert-parallelism-is-unmeasurable-five-contracts.md)),
   so it is real kernel work on shared-elementwise, batched-exact MoE and the
   BF16 router top-k.
2. **Hide the time** -- overlap dispatch and combine with expert compute. Does
   not touch the expert layout, so it dodges all five contracts, and the trace
   says there is ~24.7 ms of communication to hide behind ~2.2 ms of compute.
   The ratio is unfavourable: overlapping perfectly still leaves ~22.5 ms, so
   this is worth far less than reducing volume. Worth stating explicitly,
   because it looked like the cheap option.

Route 2 being weak is itself a result: **there is no cheap version of this
work.** The 24.7 ms is real bytes over a near-saturated link, and only sending
fewer of them helps.

## Boundaries

Standalone benchmark: four ranks, no model, no profiler, no quantisation
involved. The in-situ 205 us comes from the warm trace at 2.7% perturbation. The
PCIe figure is a measured H2D copy on the same devices. The protected
`125.4619731637751 tok/s` conventional short-decode record is untouched.
