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

The source implementation and one-load wrapper are now in place. GNU host
and Intel device compilation pass without opening a device. Both views pass
all 22 chain startup paths, including the real CPU canary handshake. Reset
bytes pass twice on each rank. Two fresh native-controller brackets match the
frozen parent, including 63 forced misses per view. The 16 policy tests, five
smoke checks and inherited-limit refusal checks pass. Full canonical GNU/Intel
miss-state repetitions are still running; the final seal and proposals wait
for them. The build is below 160 MB and root free remains above 36 GB.

Test setup corrections are kept in the logs: position zero needed a distinct
"no verification publication" sentinel because production never speculates
there; default CPU threading exceeded the first 300-second byte-test bound,
so the bounded rerun uses one thread. The frozen KD projection correctly
rejected the extra selection key; the local adapter validates the original
choices before restoring that transport key. KD's streaming target shell does
not have resident prepared commands. The tiny MTP produces only hits, so the
native protocol gate now adds explicit wrong guesses instead of pretending
that its ordinary request covered restore. None was a device failure.
