# Independent packet49d review — October 17, 2026

This review covers source integration, selection and seal admission, queue and
model argument propagation, K2 evidence coverage, storage policy, and submission
validation. It does not qualify device execution or claim a speed improvement.
The reviewer ran no accelerator program, model load, service operation, or build.
Protected packet49c sources, its chain and the shared packet49 oracle were not edited.

## Source and arithmetic scope

The three banked packet53b winners replace the ordinary resident target engine's
expert gate/up, expert down and small Q6 FFN tuple. Existing compact banks,
production submitter admission and tuple validation remain in use. Both serial
M2 rows reach the same sites. The recurrence fixture restores the production's
rounded BF16 state before the next serial row; it compares state, output and
controls, not just the final token.

The five eligible packet54 alternatives and production controls are compiled
into the same device build. Route, recurrence and HC mix selection resolves to
submitter pointers during engine preparation. Token execution contains no
candidate-name selection branch. The rejected norm and FFN-combine alternatives
are absent from the selectable vocabulary. Model arithmetic remains
`iq3-p49-split32-v1`; the completed packet49 oracle remains the model authority.

## Selection and seal admission

`selection_gate.py` reruns packet54's sealed two-owner decision verifier in a
separate Python namespace. It checks the pinned packet54 seal, recomputes the
common selection, binds the banked packet53b decision, and requires the combined
saving to reach 40 microseconds independently in both timing owners. Packet54's
separate 25-microsecond reporting threshold does not substitute for that rule.

Selection data is excluded from the compiled-source identity. CPU preparation
binds all compiled alternatives and their gates. Fast reseal revalidates these
bindings without compiling or rerunning the gates, then adds the exact selection
and decision hashes to the final seal. It refuses a started device chain or an
existing final seal. Pending CPU preparation cannot admit a device queue.

The queue verifies the final seal before writing or launching. Each window
verifies it again. The window passes the verified selection hash from memory to
the model pipeline; suite argument copies preserve it, and both resident ranks
receive it. KD passes the same verified hash to its CPU reference and both fresh
device owners. The native loader hashes the exact bytes it parses and refuses a
mismatch before engine initialization. Native receipts retain the observed hash.
The transport-only mini canary intentionally omits model selection.

Submission validation requires the observed selection hash on every model
window, both rank teardown receipts per window, both KD device owners and the
KD CPU-reference identity. Any additional bound JSON selection stamp must agree.
This closes the reviewed selection-file mutation gap between preflight and
native initialization without adding token-path hash work.

## K2 and storage

The added K2 owner measures all 16 production/candidate choices across route,
recurrence, both HC sides, and the three banked classes. Its parser requires
10 warmup plus 200 measured samples per choice, byte equality, complete event
counts, unique event endpoints, consistent summed durations, sub-four-second
individual events, and safe owner teardown. The dispatch policy retains the
SPEED6 topology and inherited choices while binding the new measured selection.
The two packet54 timing owners decide selection; K2 is not a replacement speed
verdict from one owner.

The new storage policy removes superseded parent-chain and completed-oracle
future-write reserves, retains the root free-space floor and the new chain's
write budget, and caps CPU build storage at 1.5 GB. The actual build fit and live
free-space receipt remain the preparer's required checks before sealing and
coordinator admission.

## Submission policy and tests

Packet49d uses its own final seal, explicit runtime revision and selection hash
in `scripts/packet49_submission_pins.json`. A pending pin refuses preparation.
The coordinator-updated `scripts/packet49_record_threshold.json` is a monotonic
record ledger; new evidence snapshots its exact bytes. Invalid, nonfinite,
duplicate and lower record updates refuse. The update helper replays the bound
result before accepting the coordinator's returned submission ID. It performs no
network operation. Historical packet49c evidence remains replayable against its
original bound scope and floor. The strict 512-token gate stays false.

Executed serially with nice 19, cores 4–15 and 20–31, and Python `-B`:

```bash
PYTHONPATH=scripts nice -n 19 taskset -c 4-15,20-31 \
  /home/steve/.venvs/vllm-xpu/bin/python3 -B -m pytest -q \
  scripts/tests/test_packet49_submission.py \
  scripts/tests/test_localmaxxing_speed6_scope.py
```

Result: **109 passed, 12 subtests passed**, 3.35 seconds. These include native
selection-stamp mutation/refusal checks, current-floor changes, malformed and
lowered thresholds, pending/mutated lineage pins, complete packet49d preparation,
portable historical replay, and unchanged SPEED6 scope validation.

From the packet directory:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B -m unittest test_p49d_k2
```

Result: **1 test passed**, including complete synthetic coverage and rejection
subcases. Its synthetic timing values are protocol fixtures, never measurements.

## Remaining qualification

The initial recurrence negative-input fixture issue is resolved by the
682-check GNU run recorded below. It required a fixture-only allocation
correction, with no production runtime-guard change. All remaining preparation
gates must still pass before the CPU preparation seal is complete.

Packet54 device selection, final fast reseal, all packet49d device windows,
full-model parity and integrated timing remain coordinator work. No device
qualification, final selected seal, record improvement or submission is asserted
by this review.

### Resolution of the recurrence negative-input fixture

The recurrence issue above is resolved. The negative test supplied the wrong
allocation extent; it was a fixture-only error, not a production runtime-guard
defect. The corrected GNU run passes all **682 checks**, including the short-QKV
rejection, all selectable submitter byte comparisons and serial M2 cases, with
safe teardown and no device execution. The root preparer executed the run; the
independent reviewer inspected its receipt.

Receipt: `build/p49d-first-gnu-corrected/receipt.json`; log:
`build/p49d-first-gnu-corrected.log`. Receipt SHA256:
`dc3fad0aee922c8f0050b211ee3e7f78923b4685c4952396855cb86bba7740fd`. Canonical output SHA256:
`14bc87455add73a2dd92bba670da41d6bdf286f6724621c8028c5201d36a57e4`.

The remaining full CPU/engine/sanitizer gates and compilation checks still belong
to the preparation closeout; coordinator device and model qualification remain
pending as stated above.

### Final audit findings closed

The final read-only audit identified four closure issues. The root preparer
made the following changes before final CPU sealing:

- Removed the obsolete `build.py seal` stage. Only `p49_seal.py` creates seals,
  so the old shortcut cannot write a CPU-only receipt over a selected final seal.
- Corrected the protected identifiers in `WINDOW.md` to the exact
  `device-cards01-a` chain and `p49c-model-cards01-e` unit names.
- Added `scripts/packet49_submission.py` and `scripts/receipt_qualification.py`
  to the CPU seal's source bindings. Mutable submission pins and the coordinator's
  record ledger remain outside that closure, avoiding circular sealing and
  permitting the explicitly authorized record update.
- Added independent verification of packet54's complete source inventory against
  its pinned seal before starting the subprocess that imports its decision
  verifier. A changed verifier cannot bypass its own source check. A new refusal
  test covers verifier mutation before import; its execution belongs to the
  root preparer's final test pass.

The scoped ASAN build retains all five targets used by actual sanitizer gates:
`own-rt-iq3`, `p49-qsa-fixtures`, `p49b-expert-fixtures`, `p49c-fixtures`, and
`p49d-fixtures`. GNU and device builds retain all targets. The mode receipt
records requested and actual artifact targets, and the seal checks the exact
ASAN set. Removing regenerable object files after their engine-gate bindings
is documented through the cleanup receipt; exact executed sanitizer binaries
remain recoverable from verified archives. This scope does not drop a consumed
sanitizer gate.

No unresolved source/protocol blocker remains from this independent audit.
The root preparer owns final CPU, engine, sanitizer, source-binding and storage
checks. Their authoritative final results are recorded in the
[packet49d task note](../../../../notes/2026-10-17-own-runtime-packet49d.md),
rather than inferred from this intermediate review. The last audit update was
documentation-only; no additional test, compile or device operation was run by
the reviewer while the serial ASAN build occupied the CPU slot.
