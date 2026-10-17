> Historical packet49 review copied as design context. It does not qualify packet49b. See REVIEW-INDEPENDENT.md for the new review.

# Independent orchestration review, packet49

CPU source review only. No device, service, model payload or health query ran.
Reviewed `queue_runner.py`, `WINDOW.md`, `coordinator_windows.sh`,
`oracle/oracle_job.py`, `oracle/suite_check.py`, and the inherited window
prerequisite calls.

The early phase carries no full-model oracle path. Its ordering is K0, K1a,
K1b, K2, W0p. The model phase asks the CPU campaign to validate complete,
hash-bound output before launching KD or a model window. W2m and suite commands
retain the split23/draft-rank1/4K/native-controller identity. WS128 names the
retained WS128x exactness companion. The queue checks both process exit status
and the qualifying device receipt; it does not retry a failed window or start
a resident service. The split phases carry the prior inter-window gap forward.

Findings sent to the coordinator:

1. At review time `run()` checked nice level and CPU affinity but did not check
   its systemd cgroup. A direct interactive launch could therefore pass those
   checks despite the runbook requiring a durable coordinator user unit. Add
   an explicit cgroup admission before journal/device work.
2. The queue's fault regex was narrower than the inherited window supervisor:
   generic `CAT error`, `job … timed out`, and `device coredump` were missing.
   Align its specific signatures with the existing supervisor, including while
   it waits for the CPU oracle. Do not add vague words such as `hang`.
3. The first oracle comparator demanded complete 128-token output and all
   retained steps for every runtime window. That cannot admit W2m's 64-token
   prefix or token-only WS128. The root review independently found this and
   requested explicit prefix and retention scopes. Keep the complete-oracle
   validation strict; scope only the device comparison.

The CPU campaign uses at most two fresh host-only model children concurrently,
then a serial fresh-process repeat of the development prompt. It pins the
admitted model path, checks input hashes, validates each output's token/position
coverage and BF16 fixture hashes, and records old-versus-new outputs as
information. The published suite manifest must remain unavailable to model
windows until its completion receipt and source/build bindings validate.

The root owner added the cgroup admission, aligned the fault signatures, and
made failed CPU oracle campaigns stop the queue rather than remain pending.
The updated queue suite passes ten CPU checks. The retention-aware oracle
comparator remains under the oracle owner's review at this point.

These are source findings, not a device or full-model acceptance.
