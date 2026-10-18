# Packet121 — miss-path table reuse

Started 10:29 UTC on steve-b70s; 2.5-hour CPU-only box. Pull refused unrelated
dirty orchestration files; fetch confirmed HEAD == origin/main at
`f407c709d47406255bbd29102ad3a389efaebec7`. Those files remain untouched.
Root free was 38.23 GB. Stop below 25 GB; build ceiling 250 MB. CPU work uses
nice19, CPUs 8–15/24–31, Python -B, closed stdin, at most 8 GiB, and packet94's
serial compile turn. No GPU, services, sudo, host settings or live queues.

The [miss budget](../experiments/own-xpu-runtime/stage2/packet121-miss-table/BUDGET.md)
accounts for every command and wait in all 252 miss intervals. Misses take
31.64% of interval time. Rank1 finishes its draft then waits for rank0's
corrected result; that wait cannot be filled with another exact draft whose
inputs do not yet exist. Existing restore/draft overlap and spare-bank omission
are already accounted for. Every DO-NOT-REPEAT ledger was searched before
selecting the lever; its inventory is retained with the attribution.

The selected candidate keeps the capture copy table and uses it backwards
for restore. All original extent checks, restored bytes, fallback restoration,
full-precision KV, arithmetic and target verifier remain. Only the table upload
and reconstruction are removed on a miss. It is a new copy of packet118;
existing packets and screen wrappers remain frozen. The CPU gates and proposed
smoke/bracket will determine preparation status; no gain is claimed.
