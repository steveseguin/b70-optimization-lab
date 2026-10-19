# Packet156 resource and admission accounting

CPU-only receipt replay under nice19, CPUs 8–15/24–31, closed stdin and a
2 GiB address-space cap. No compile, GPU, service, sudo, settings change or
model payload read. No elapsed-wall timeout; coordinator freezing cannot
turn elapsed time into a failed data proof. Existing packet58ah reservations
remain binding.

The CPU stop remains **27,000,000,000 root-free bytes**. Observed root free
was 29.503 GB at entry and 29.303 GB during smoke replay; final storage receipt
records the later observation. No change to any admission setting was made.

The failed benefit bound closes the arm before copying/building a runtime.
New build bytes, device-stage bytes, duplicate weights/KV and planned device
writes are all **zero**. Therefore no device planner, pin admission, native
preparation-path probe or `rehearse_entry.py` result is claimed. Those gates
would be mandatory before admitting any implementation, including the real
rank argv under a host build with device defines. Neither inherited CPU
results nor this analysis stand in for them.

If reopened, device admission remains the unchanged **25 GB floor plus planned
writes**, approximately 250 MB/view and no more than 3× comparable measured
retention. Both lanes must have packet-local smoke and v5 proposals named
`proposed-p156-smoke-A.txt`, `proposed-p156-smoke-B.txt`,
`proposed-p156-v5-A.txt`, and `proposed-p156-v5-B.txt`. They are deliberately
not generated for a mechanism that failed its benefit admission gate.

Compressed source/receipt snapshots are ordinary CPU evidence, not device
write estimates. [Storage receipt](evidence/storage.json) records actual
retained bytes and peak RSS from each completed replay. No evidence was deleted
from an existing packet; no compiler cache or runtime was copied.
