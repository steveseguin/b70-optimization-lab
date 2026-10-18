# Packet130: exact target-head suffix interleave

CPU preparation is in progress. Device quality and speed are unmeasured.
The frozen source is packet124c's bundle7. Only the new `suffix_schedule`
choice differs: `production` or `layer-interleave`. Both retain the same
24/24 layers, 46,080-row suffix, 80,128-row draft prefix and BF16 KV.

Rank0 arms the exact remote request before publishing its command. While that
request is pending, the candidate completes one layer, checks for the verified
rank1 hidden state, and services the suffix immediately when ready. Once it is
serviced, subsequent layers use the ordinary submission path. Late arrival
uses the existing remote-wait fallback. Every service validates sequence,
position and fixture and publishes exactly once. Request resets clear only a
completed schedule. Target observers are suspended during private suffix work.

Early target verification is deliberately deferred for cancellation purposes
until this speculative half returns. The baseline cannot see that verification
before returning because it has not serviced the suffix yet. This preserves
its full speculative work, state-bank swap and miss rollback. Owner/peer aborts
and the explicit launch-cancellation test remain active. No miss optimization
is mixed into this experiment.

All arithmetic kernels and their object files are reused unchanged, except
recompiling the selection parser with the new key. Host tests compare complete
logits, finite argmax and nonfinite refusal under GNU and Intel, and forced
arrival controller scenarios. Numerical full-size startup tests require
identical capture bytes across selection switches. Miniature runtime tests
compare complete target/draft state with the parent and across fresh runs.
They do not establish full-model device equality.

Only `v5/bracket_job.py` is an admitted future device entry. Its two proposed
windows are a candidate 12 × 64 smoke and a conditional one-load A/B/A/B/A
12 × 128 bracket. The old copied eleven-window chain is not a device entry;
its native argument shapes are supplemental CPU regression coverage. All
operational admission, fault checks, drain spacing and getrlimit rules remain.
Nothing here edits a live queue or launches a GPU.

CPU commands run with `nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2`,
`python3 -B`, stdin `/dev/null`. All compilers use packet94's serial turn.
Caps belong only to CPU `__main__` processes. Root free space must remain
at least 25 GB; packet build files must total at most 300 MB.

The build entry is `v5/build_engine.py`. Gates are `head_cpu_gate.py`,
`controller_gate.py`, `test_drain_fix.py`, then the v5 `full_shape.py`,
`reset_gate.py`, `protocol_gate.py`, `test_v5.py`, `test_refusal.py`,
`test_timing_report.py`, `exec_gate.py`, `cpu_seal.py`, `argument_gate.py`,
`legacy_window_gate.py`, `worker_gate.py`, `launch_limit_gate.py`,
`queue_plan.py` and `queue_gate.py`. The CPU seal's operator evidence is
`evidence/head-byte-identity.json`. Pending evidence is never a pass.

The post-release timing report separates hit/miss suffix wait, import,
compute/scalar service, and rank0 speculative-half completion. These are
host elapsed clocks, not summed GPU execution time. All control/candidate
receipts carry the same instrumentation. No missing sample is filled with zero.

[Work note](../../../../notes/2026-10-18-own-runtime-packet130.md).
