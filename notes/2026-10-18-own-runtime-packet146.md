# Packet146 — request-local prompt lookup, October 18

Closed at the policy check, within ten minutes. The written headline rules
disable n-gram/history acceleration without a within-request exception.
Other text warns specifically about repeated benchmark history, and the
submitter recognizes `freshResponseNgramValidated`, but neither defines an
exception for this proposal. That leaves eligibility at least ambiguous;
the brief requires stopping there.

Keeping every token verified by the unchanged target can protect output
quality. Clearing lookup state between requests avoids warmed answers.
Those properties do not settle the separate headline rule. This is a policy
decision, not evidence that request-local lookup is lossy or slow.

The [analysis and closeout](../experiments/own-xpu-runtime/stage2/packet146-prompt-lookup/ANALYSIS.md)
records the conflicting wording, source lines, limits and revisit condition.
The [source receipt](../experiments/own-xpu-runtime/stage2/packet146-prompt-lookup/policy-evidence.json)
retains hashes and exact excerpts, and the
[DO-NOT-REPEAT entry](../experiments/own-xpu-runtime/stage2/packet146-prompt-lookup/DO-NOT-REPEAT.md)
prevents reopening this arm without a policy resolution.

No acceptance replay or arbitration tuning ran. No calibration or benchmark
token streams were used. Net acceptance and projected speed are unknown;
the +1.5-point gate was not evaluated, and no design note is admitted.
The existing 58.798 tok/s reference in the brief is unchanged.

Validation passed: all five policy-source hashes and every captured excerpt
match the reviewed files; all 17 local document links resolve. The closeout
marker and unmeasured acceptance fields were checked. The bounded validation
process peaked at 15,776 KiB RSS.

Work stayed on main on `steve-b70s`. `git pull --rebase` refused unrelated
dirty orchestration files; `git fetch origin` confirmed both HEAD and
origin/main were `10aff58c871968c4750c56dbc3cf75862d0bf1f5` at entry.
Only the new note and packet146 directory belong to this commit. Existing
packet trees, screen files, ops files, live queues and CURRENT.md were
preserved. No live state changed. No GPU, model, service, sudo or setting was
used. Evidence and documentation checks use nice19, cores 8–15/24–31,
Python `-B`, stdin `/dev/null` and a 4 GiB address-space cap. Commit uses
explicit paths with `git commit --only --`, followed immediately by push.
