# Packet58as: one-card bounded spin wait, CPU preparation

The one-card packet58aj engine now has a private A/B wait switch. The candidate
reimplements the two-card packet56x bounded-spin policy: spin for at most 250 µs,
yield periodically, then sleep for at most 20 µs or the remaining deadline.
It checks asynchronous errors on every iteration and retains completion error
propagation. The original millisecond poll remains the A control; the separate
DMA failure-recovery sleep stays unchanged. Packet58ar and all existing packet
trees are untouched. No GPU, service, settings or live queue changed.

Both compilers pass the wait tests and full miniature byte comparisons against
packet58aj. The two compiler runs cover 120 actual request resets; a separate
CPU probe compiled with the device defines exercises the real launch arguments,
production plan, five view transitions and sixty request resets. All 130
memory-sensor samples are present in that probe. Peak child RSS was 1,144,070,144
bytes; compilation, including the probe and both wait tests, used one shared
compiler turn. These are CPU checks, not device exactness or a speed result.

The analyzer replayed all sixty packet58aj and seventy-two packet58aq requests,
including their cold first views. The complete timing streams are preserved as
byte-identical private snapshots. The largest measured cold phase supports the
600-second operation wait at more than four times its duration. Tests reject
old evidence as a new wait-policy result, wrong tokens, an under-threshold
candidate and excessive drift. Threshold fixtures are labeled synthetic.

The proposal is `proposed-p58as-v5-A.txt`: one fresh whole-host lane-A job.
**No separate smoke:** K1a/K1b and an exact A0 control open the one-load
A0/B0/A1/B1/A2 bracket. Every view keeps resident lookups, the full packet58aj
composition, 21,552,729,600 cache bytes and BF16 KV. All sixty responses must
match `iq3-p49-split32-v1`; both B views must beat every warm A by at least 0.5%,
with at most 3% control drift. A0 is excluded only from speed/drift. Each view
also reports owner-thread CPU time as a percentage of one core. Actual CPU
utilization and device speed remain unmeasured.

Every native flag was checked against --help; actual entry imports and loaders
were checked in the real closed launch environment. Temporary lanequeue planning
and the shared `ops/rehearse_entry.py --report` pass. The shared tool's unranked
one-card preparation warning is covered by the separate real device-define CPU
probe, not hidden. Its generic synthetic smoke-report exercise is not a smoke
launch or prerequisite. The initial argument rehearsal found missing private
admission dependencies; the failed receipts remain, the dependencies were
restored byte-for-byte, and final entry checks pass. Queue pin review also
required private copies of the real-data replay and inherited admission inputs;
those are now included and sealed.

In-run checks cover stream presence/format and exactness only. There is no
wall-clock data-proof cutoff. The CPU stop floor is 27 GB and the device floor
25 GB. Model readers retain idle-class ionice. No fresh-process qualification,
record submission or publication is claimed by this screen.

The private 4 MiB rotary table and measured/admission snapshots are retained
because they are necessary for exact local rebuild and replay; restore their
original bytes from Git. Compiled objects are ignored, hash-bound and restored
from the frozen packet58aj inputs using the packet's restore manifest. This is
a local research packet, not a public deployment recipe.

[Packet and coordinator contract](../experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/README.md),
[final readiness](../experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/READY-FOR-DEVICE.json),
[native delta](../experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/native-delta.patch).

## Packet58asc — record-chain preparation blocked by the unchanged native interface

The completed card-0, whole-host `packet58as-v5-A` bracket (08:37–08:51 UTC,
Codex frozen) is exact for all 60 requests. A0/B0/A1/B1/A2 measured
31.901 / 34.577 / 31.838 / 34.568 / 31.807 tok/s. A0 is excluded warm-up;
warm-control drift is 0.096%, and both spin views beat every warm poll control,
with a minimum gain of +8.58%. Owner-thread CPU was 42.7 / 33.0 / 25.1 / 32.9 /
24.5 percent of one core. These are bracket results, not fresh-chain records.
The [packet58aq diagnostic](2026-10-19-own-runtime-packet58aq-result.md) measured
1.108 ms/token for publication plus drain; other hot-path waits also used the
millisecond poll. No arithmetic, governor or host setting changed.

The new private orchestration contains packet58aj's seven-window chain,
90-second gaps, 300-second operation waits, fault review, whole-host admission,
exact `iq3-p49-split32-v1` checks, full resident lookups, BF16 KV, max cache,
overlap and full fusion composition. Submission preparation is vendored and
rehearsed offline from its final location. It refuses an equal or lower matching
record, pins 31.966819787781944 tok/s (`cmveqsmsl00ebrf014yvrsosx`), checks the
live ledger too, and discloses the 128-token scope, strict512 false, bounded
spin CPU cost, resident copies, diagnostic and bracket numbers. No submission
was made.

**The requested no-rebuild launch is impossible with the bracket binary.**
A sandboxed native parser check confirms `--wait-policy spin` is an unknown
option, and `--hc spin` fails the HC dimension check. The existing single-view
path puts `a.hc` (only `production` or `p60fusion`) into the view selector, then
sets `spin_enabled = (view.hc == "spin")`. It therefore selects poll. Spin can
only be selected through the bracket table, which requires either one 64-token
S0 or five 128-token A/B views, twelve prompts and no retained steps. It cannot
express KD/W2m's eight-token captures or WS's retained layer checks. Adding an
unsupported flag to a Python launcher would not make this binary launchable.
A native interface change and rebuilt/qualified binary would be needed; that is
outside this brief's explicit no-rebuild constraint.

The native binary remains byte-identical to the completed bracket. Its original
screen seal is preserved byte for byte in `lineage/packet58asc-before/`; the
active screen closure points explicitly at historical root-file snapshots so
pin admission does not confuse changed chain files with original screen inputs.
The coordinator's `evidence/source-delta.json` provenance records are untouched.
No native source, object or executable was changed.

The 137 Python policy tests pass (peak RSS below 65 MB). The real seven-window
entry rehearsal intercepts native execution and checks all 28 wrong-unit and
wrong-environment refusals; this validates Python plumbing, not native support
for the proposed flag. Native help/parser diagnosis is separately fail-closed.
Temporary lanequeue planning, oracle replay and submission CLI dry-run pass.
Initial checks exposed missing inherited test fixtures and a rehearsal address
space cap incompatible with the launcher's deliberate unlimited-AS check; the
small fixtures were copied, tests rerun with measured RSS, and production limits
were left unchanged. The generic shared entry scanner assumes a `screen-*`
unit and cannot certify this fixed `packet58-onecard-*` unit; the direct entry
rehearsal tests the actual unit instead.

Both final READY markers and `ready.json` say **not ready**, with the native
interface reason. `verify_ready.py` refuses before any device launch. The generic
waiter's `--check` validates paths and the seal but does not check the readiness
boolean; a successful structural check must not be read as launch authorization.
No GPU, service, sudo, setting, model/full-shape read, compile, live queue write,
chain attempt or external submission occurred. `CURRENT.md` and every other
packet/ops tree were left to their owners.

Evidence: [coordinator contract](../experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/WINDOW.md),
[native interface proof](../experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/evidence/chain-native-interface.json),
[submission rehearsal](../experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/evidence/submission-rehearsal.json),
[temporary plan](../experiments/own-xpu-runtime/ops/packet58as-orchestration/queue-plan.log),
[final readiness](../experiments/own-xpu-runtime/ops/packet58as-orchestration/READY-FOR-DEVICE.json).

## Packet58asd — one rebuild exposes the spin wait to the record chain

The p58asc blocker is removed with one native interface change. `own-rt-iq3`
now takes a process-wide `--wait-policy poll|spin` option. **Poll is the
default**, so every existing caller is unchanged. In a single-view run the
policy is applied at the view boundary through the same `p58as::wait()` that
the bracket's B views used (`spin_enabled = bracket_inputs.empty() ? policy ==
spin : view.hc == spin`). Model load therefore keeps the default poll, exactly
as in the bracket. The bracket table still selects per view. If a supplied
policy conflicts with a bracket view, the run is refused. A supplied policy is
also refused for a draft-capture or rank owner, which bypasses the view loop.
Nothing else changed: arithmetic, selection, kernels and `single_device.cpp`
are as before (the recompiled `single_device.o` is byte-identical).

| | sha256 |
|---|---|
| bracket device own-rt-iq3 (kept in `build/bracket/`) | `83abf236dcfe73bc9da6309fdc1a0c523aab104faa3adcabee3d5589f0b0b1d2` |
| chain device own-rt-iq3 | `4f957f34ae11011fa9a2caba6a79e981559e9f9fa0fa3958e20a90460d1b745e` |
| chain GNU / Intel host | `00d1baf8…7487` / `6f12f944…708e` |
| source diff `chain-interface.patch` | `57ba0ba08651da94630c7888a3bd435d5e7d3cfde4ecb32c6d5331c187c46b73` |

**K1a/K1b are unchanged.** The abandoned Codex draft added `--wait-policy spin`
to K1 by `#include`-ing the packet58j fixture source into the g++ help wrapper.
That would not compile (it needs SYCL), and the fixture's waits never read
`p58as::spin_enabled`, so the flag would have been inert. It was reverted. K1
is the inherited, non-qualifying fixture byte and zero-copy check. It still runs
the unchanged fixture wrapper and core with no flag, as it did in the bracket.
Every model window (KD/W2m/WS/WS128x/WS128) passes `--wait-policy spin`.

Gates (CPU only, nice19, CPUs 8–15/24–31, one `ops/compile_turn.py` turn):
- GNU and Intel builds and both wait tests pass.
- The [wait-policy gate](../experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/evidence/wait-policy.json) passes:
  - GNU and Intel runs with spin, poll and no flag reproduce packet58aj's miniature step bytes and tokens (6/6).
  - The real argv of all five chain model windows parses as spin, and parses as poll without the flag.
  - An unknown value is refused.
  - The bracket binary refuses the same argv (`unknown option --wait-policy`) and accepts it without the flag. This is the test that fails on the old binary.
  - Bracket conflict and draft-capture refusals pass.
- The existing 120-reset GNU/Intel bracket byte gate passes on the new binaries (`evidence/chain-cpu-exactness.json`).
- The native parser gate (35 composition refusals), the flags gate, the seven-window argument gate and 137 Python tests pass.
- The sandboxed device-binary interface proof passes.
- The submission dry-run passes, with both binary hashes and the diff hash in the notes (1,894 of 2,000 characters).
- The temporary-copy `lanequeue plan` passes.

The shared `rehearse_entry --report` still fails only on its known generic
`screen-*` unit assumption and on the absence of a preparation probe. Both
binaries' ldd/help checks, storage and deadline checks pass, as in p58asc.

Minimal reseal: the bracket's evidence (`cpu-exactness.json`, `flags.json`) and
original screen seal stay byte-identical. The active screen closure now points
at the `lineage/packet58asd-before/` native copies and the retained bracket
executable. Three ignored `entry-main.o` intermediates were recompiled; they
are listed with their bracket digests. The device-define preparation probe was
not rerun: it is bracket-binary evidence, and no full-shape reads were allowed.
`verify_ready.py` now binds the bracket identity through `bracket_native`. It
requires the chain binary to be the recorded rebuild and returns ready=true.
Both READY markers were written last. No GPU, service, sudo, setting, live
queue write or chain launch occurred.
