# Isolated rolling coordinator adapter

`coordinator.py` subclasses the unchanged generic ring Coordinator. No active
controller imports it. The proposal copies only the two reservation loops to
add admission fences; target truth, immutable proposal selection, suffix drain,
ACK validation and wire-sequence allocation stay in the base implementation.
Promotion should replace those copied loops with reviewed generic hooks, after
the pending-provider GPU gate closes. There is no native RESET support, runtime
CLI, new GPU execution or speed claim here.

Stage zero reserves op27 through the same `_reserve` allocator as target
commands. The auxiliary operation occupies its actual busy slot. Other owners
can complete their commands while its reply is delayed. Provider completion
checks the exact reservation, serial, restored position and unchanged target
cursors/pending IDs before releasing that slot and publishing actual guesses.
No reference output is supplied to this adapter. The mocked provider computes
guesses from its seed input; expected outputs appear only in test assertions.

Each final ACCEPT must supply a separately wire-validated `Parent` with the
exact immutable row, original ROW ticket and ACCEPT sequence. That record's
lease prevents the next final ROW until the provider reply. The local acceptance
fence prevents native `last_accepted` from advancing past the next canonical
provider seed. Original tentative identity survives acceptance. Old recursive
guesses already issued remain immutable even when fresh canonical guesses
disagree. Normal miss recovery retains its parent lease while all owners drain
and abort the old suffix, then admits the corrected seed before op27.

This first ABI deliberately holds the final owner while op27 runs. With two
stages there is no third owner to compute during that interval; four/six stages
can continue middle-owner work. Mock scheduling is not a throughput prediction.
The adapter currently consumes decoded typed events, not sockets: a later
controller bridge must apply the real final-record/proposal codecs, retain owned
hidden/stream bytes, dispatch all sockets without blocking, and inject the same
guarded lifecycle. Nothing here authorizes bypassing those checks.

## Cancellation findings and fixes

Exhaustive stop tests exposed three integration errors; the fixes exist only in
this isolated adapter:

1. When op27 is the sole outstanding command, its seed may already be locally
   ACCEPTed. A stop cutoff based only on pending ROWs omits this committed prefix.
   Include all local committed cursors before draining downstream owners.
2. An in-flight ACCEPT may refer to an originally tentative row that is now
   verified. Preserve that row in the cutoff even before its ACK; clearing its
   work as cancelled would reject a valid reply after native acceptance.
3. A final-parent lease can exist before op27 is reserved, including while a
   corrected seed is absent during miss drain. Cancellation refuses new provider
   work, so retaining this unused lease deadlocks verified-prefix draining.
   Explicit cancellation abandons it once no op27 is in flight. An existing
   provider command must still reply normally before its lease is released.

Cancellation emits no further generated outputs and schedules no new provider
step. A cancelled request whose canonical provider no longer covers the drained
target prefix is marked `cancelled_provider_incomplete`; it cannot support a
normal completed-request qualification. This abandonment applies only to
explicit cancellation/reset intent, never ordinary miss recovery or normal
EOS/cap completion. The adapter always refuses native RESET.

## CPU evidence

Eleven tests include the six existing arbiter tests plus five complete
coordinator test families. Coverage includes 24 reordered 2/4/6-stage runs with
misses at both depths, fresh-guess disagreement, early EOS, bad provider identity
with sticky refusal, and cancellation at all 295 reply boundaries in three
fixed schedules. Additional targeted stop windows cover a held final record
with local ROW, local ACCEPT, absent corrected seed, and an in-flight provider.
The tests check exact target histories/outputs, complete target drain, bounded
slots and released old stream payloads.

```sh
PYTHONPATH=engine/planning python3 -m unittest discover \
  -s engine/planning/rolling-provider-next -p 'test_*.py' -q
```

The separate `coordinator-cpu.json` pins this proposal and its unchanged core
dependencies. Existing `cpu.json` remains the earlier six-test arbiter receipt.
