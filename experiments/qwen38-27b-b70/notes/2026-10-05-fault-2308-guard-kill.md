# 2026-10-05 23:08 EDT: host memory guard killed the server; the kill logged copy-engine fault lines on both cards

**What happened.** During the eleventh context run (the keep-everything agent with its window shown, ledger seed 1,
context near 200K), free host memory fell from 2.17 GiB to 1.65 GiB within half a second (guard threshold 2.0 GiB)
and the research launcher's memory guard killed the server container (cgroup kill). Within the same second the
kernel logged, on both cards, `Fault response: Unsuccessful -EINVAL`, a `bcs` (copy engine) `CAT error` and an
engine reset. The campaign's fault check then halted the run (`FAULT-HALT.json`). Evidence:
`data/2026-10-05-context/fault-20261005-2308/`.

**Reading.** This is the teardown pattern seen before when a container is killed mid-transfer, not the load-time
fault of 2026-10-04 (that one was fixed by the chunked-upload overlay and has not recurred since) and not a fault
under load. The health probe that ran at 23:09 while the dying container was still being torn down failed; the one
at 23:09:48 passed; no fault line has been logged since. First fault event on this boot. By the owner's rule (one
fault does not end the session; a second on the same boot does) the work continues.

**Why the host memory dipped.** The two-card server leaves about 3.2 GiB free; the agent harness (harbor + sandbox
container) takes about 0.6 GiB; that leaves roughly 0.3 GiB above the guard line. The dip coincided with helper
processes doing CPU work (unit tests and web reading) beside the run. Rule from here: no helper python or stub run
while a server is up; such work happens in the gaps between runs, which I set explicitly.

**What was lost.** The keep-everything-with-window trial (seed 1) ended without a result; the remaining blocks of
the run (second seeds of the files, summarise and improved arms, thinking-off arms, key-values) did not run and are
queued again. A one-card cache test that was waiting on the run started into the teardown and failed for that
reason; it is queued again too.
