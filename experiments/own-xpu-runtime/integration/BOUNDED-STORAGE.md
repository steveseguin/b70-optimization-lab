# Bounded serving storage and evidence

The [storage audit](receipts/bounded-serving-storage-budget.json) assesses a
proposed sixteen-request session: context4096, at most512 output tokens per
request,512MiB parking and256MiB auxiliary storage. The total768MiB is a
**forecast, not a certified whole-session bound**. The27GB root floor remains
unchanged; `live_admission_ready` is false.

The receipt is bound to exact source bytes and SHA256
`d877c8f1026cbee39b835d155d213f36f90f1b39cb180bf3c3277ded0f76466b`.
Preserve it as this audit's immutable record; a changed admission needs a new
linked receipt.

## What the audit establishes

The admitted request/context limits permit at most65,536 evaluated positions.
For the pinned one-card, token-timing, overlap-cache path, conservative row
sizes give128MiB of timing/prefill logs plus32MiB of cache logs. These160MiB
are source-derived successful-path bounds. They are not extrapolations from
the smaller measured packet199 rows.

The remaining96MiB auxiliary forecast assigns16MiB to other native output,
16MiB to future bounded coordinator evidence and64MiB to driver/stderr/other
diagnostics. The audit does not prove hard limits for those external writers.
Driver cache growth, native stderr, native failure/proc diagnostics and
filesystem allocation overhead still require outer-coordinator admission.
The512MiB parking policy includes replacement reservations and retained or
ambiguous checkpoints; it is not a filesystem quota.

## Using the bounded writer

[bounded_evidence.py](bounded_evidence.py) controls only payload bytes passed
through its API. Supply an existing, real, owner-private0700 directory. It
creates new0600 files exclusively and refuses existing names and symlinks.

```python
from bounded_evidence import BoundedEvidence

# This directory belongs to the separately admitted coordinator.
with BoundedEvidence(private_directory, total_limit_bytes=16 * 1024**2,
                     max_files=16) as evidence:
    evidence.create("guard.jsonl", limit_bytes=1024**2)
    evidence.append("guard.jsonl", b'{"passed":true}\n')
    accounting = evidence.status()
```

An entire append must fit both its file limit and the aggregate limit before
any byte is written. Successful writes are fsynced. A limit refusal or I/O
failure permanently halts that writer; existing data stays in place. A partial
OS write remains present and is charged to accounting. The caller can read
`status()` after failure, but cannot resume writes or adopt the file through
this object. Replacement or external modification is detected before append.

On refusal, the coordinator must halt new work and arrange its own cooperative
drain. The writer does not start, signal, stop or retry an owner, alter resource
limits, truncate evidence or delete files. It exposes no child-process file
descriptor. Native stderr piping would require a separate reviewed drainer
that handles producer output safely after the evidence cap; this module does
not provide that mechanism. Raw native files and driver caches bypass it.

## CPU verification

Eight [temporary-file tests](test_bounded_evidence.py) pass: exact and aggregate
limits, existing files/symlinks, partial-write accounting, external replacement
and append, path/file-count refusal, private-root admission and closed-writer
behavior. See the [CPU receipt](receipts/bounded-evidence-cpu.json).

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover \
  -s experiments/own-xpu-runtime/integration -p test_bounded_evidence.py -v
```

These tests use private temporary directories. They do not execute a native
owner, touch a device, or establish live storage admission. The
[session lifecycle](SESSION-LIFECYCLE.md) and
[session composition](BOUNDED-SERVING-SESSION.md) retain separate responsibilities.
