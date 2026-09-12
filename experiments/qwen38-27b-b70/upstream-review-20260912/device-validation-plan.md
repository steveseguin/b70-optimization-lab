# Native speculative GDN validation preregistration

Authorized September 12 after the source-level review. Scope: isolated native
speculative convolution and delta-rule operators on one B70; no model server,
service changes, shared-source edits, or production promotion. CPU metadata
validation of PR #51565 is a separate arm.

Pin kernels efc85bc8a0eb3076c861b2e6cb1e1731a93905d5. Build an isolated test
extension from its actual speculative entrypoints and kernel headers, plus
the archived active-width candidate as the sole mathematical treatment.
An explicit registration/queue adapter may exclude unrelated prefill/TLA code;
record it and do not call this a complete production extension build.

Stock must pass the supported full-width control and reject reduced uniform
width with retained cache capacity. Candidate must pass numerical output and
state comparisons for full width and reduced width against a Torch reference.
Exercise width 3→2→3 and different accepted-token histories; check untouched
state where applicable. Ragged lengths require separate treatment: total-row
divisibility alone is insufficient, and no ragged-support claim is authorized.
Do not launch a known out-of-bounds shape merely to demonstrate a failure.

Before devices: verify no Docker/model workload or render-node owner, enough
memory/storage, current boot, and a clean recent kernel journal. Hold host GPU,
benchmark, and all four device locks throughout preflight/test/postflight.
Run a bounded copy/compute check on all four cards; the experiment itself uses
one card and no collectives. Bound each subprocess, stop on first device fault
or failed preflight, retain logs, and always attempt bounded postflight after
device execution. Never reboot or reset hardware as part of this campaign.

No throughput result or full-model quality claim will follow from operator
tests. A failure of the candidate is a retained negative result, not permission
to silently modify the preregistered treatment. Any follow-up fix needs its own
identified patch and control comparison.
