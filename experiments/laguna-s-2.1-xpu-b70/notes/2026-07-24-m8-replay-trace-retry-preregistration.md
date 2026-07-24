# Laguna M8 replay-only PTI trace retry preregistration

Date: 2026-07-24 America/Toronto

Status: **preregistered; not yet run**.

This retry inherits every identity, one-generation rule, trace window, output
exactness check, and decision rule from
`2026-07-24-m8-replay-trace-preregistration.md`, except:

- vLLM is frozen at
  `7118fa20d4e0b606abc764bf4984c6f701ac14dc`;
- both parent and worker temporal-control guards require the exact resume or
  pause acknowledgement plus one exact PID-shaped PTI child-log provenance
  line;
- auxiliary paused child summaries are preserved and inventoried but do not
  count as worker traces;
- fresh RPC bases are `m8rt2-eager` and `m8rt2-graph`; the first attempt's
  sealed RPC state is never removed or reused;
- a passing arm requires exactly four unique PID-bound traces, each containing
  positive Level Zero API, device, and kernel-submission totals;
- the first failed root is immutable and cannot be reused.

The retry remains diagnostic-only and cannot support a throughput or
LocalMaxxing claim.
