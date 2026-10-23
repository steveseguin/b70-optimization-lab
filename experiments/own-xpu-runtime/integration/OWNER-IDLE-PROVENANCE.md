# Fresh-owner provenance for initial idle timing

## Question and result

The existing conservative timing calculation can recover model-loading time
from the first idle interval, but its input file alone cannot identify its
writer or the running clock implementation. The additive
[owner provenance helper](owner_idle_provenance.py) checks that missing link.
Sixteen CPU checks and [independent review](receipts/independent-owner-idle-provenance-review.json)
pass. They inspect actual pinned ELF metadata and synthetic process observations;
no native owner or device was launched or inspected for this proof.

## Contract

The coordinator calls `prepare_owner_origin(owner_output, environment)` before
its sole launch. The owner output must be absent beneath an owned private0700
parent. The preparation records the parent identity, boot, closed environment
and monotonic time. The caller keeps exclusive ownership of this fresh run.

After native readiness, `prepared.prove(process, admitted_argv=argv,
launch_monotonic=before_popen)` reads bounded process identity, command line,
environment and executable mappings. It requires the direct child, unchanged
start ticks, exact binary and output argument, the admitted single-card device
visibility settings and no loader preload. It reads the native cold-start file
under its current directory identity and verifies executable mappings again.

The clock proof examines the runtime dynamic symbol tables of every observed
executable ELF. Section tables must match `PT_DYNAMIC` through `PT_LOAD`;
SysV and GNU hash extents must cover the inspected symbols. Missing or
unsupported layouts refuse the proof. The only observed dynamic providers of
`steady_clock::now` and `clock_gettime` must be the pinned libstdc++ and libc.
Reads are limited to128 objects,32MiB metadata per object and128MiB in total.
No ELF command or native program executes to collect this information.

The frozen [arithmetic helper](INITIAL-IDLE-ORIGIN.md) then derives a lower bound
for initial activity. Absolute launch time and deadline remain unchanged. The
outer proof records verified provenance separately; it does not rewrite the
frozen helper's conditional flags or grant live admission.

## Review fixes and limits

The first candidate rejected the actual native visibility environment. Review
also found that section tables alone could miss loader-visible clock exports.
Both candidates remain in
[environment-review lineage](lineage/owner-idle-before-device-environment-review/owner_idle_provenance.py)
and [dynamic-table-review lineage](lineage/owner-idle-before-dynamic-table-review/owner_idle_provenance.py).
Regression checks cover production environment drift, output mismatch,
interposition, changed process identity, malformed/shortened dynamic metadata,
out-of-range hash indexes, unsupported executable mappings and symlinked input.

This is a trusted local launch contract. It does not protect against hostile
same-user output mutation, debugger injection or a caller that violates the
single-launch contract. A real owner may have an unsupported mapping layout;
that has not been qualified. A coordinator must preregister whether it uses
this proof or the more conservative launch-time origin. It must not hide a
provenance contradiction by silently falling back to a later timestamp.

## Reproduce

```sh
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  /home/steve/.venvs/vllm-xpu/bin/python -B -m unittest discover \
  -s experiments/own-xpu-runtime/integration -p test_owner_idle_provenance.py -v
```

Next: bind this optional proof into the separately reviewed packet200
coordinator. Keep the existing daily applications and all sealed native sources
unchanged during CPU preparation.
