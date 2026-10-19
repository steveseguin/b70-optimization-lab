# Packet165 — measure warm prompt reading, then build exact batching

Prepared [private one- and two-card packets](../experiments/own-xpu-runtime/stage2/packet165-warm-prefill/README.md)
for the same 512-token request as packet163, after one different request has
warmed the runtime. No GPU, model read, service, sudo, settings change or live
queue action was performed. Work ran on the assigned CPU cores at nice19.
Compilation and native CPU probes use the shared compiler turn and wait through
protected timing windows. Existing packets and shared operations code remain
frozen.

The first registered suite prompt, `incident-retrospective`, now runs once
before prefill. The full reset then clears request state before the 512-token
prose prompt. The remaining eleven suite prompts each run once. The warm-up is
still part of the suite report, including its actual cold first-request cost;
no request is repeated or discarded. The prefill receipt asserts zero cached
tokens and binds the warm-up and reset receipts by hash.

Prefill is reported as 512 input tokens divided by request TTFT. One-card TTFT
starts before its native reset; two-card TTFT starts after both rank resets.
Those existing boundaries are disclosed rather than silently changed. The
native prompt-loop wall time is also retained. An isolated prefill device time
is unavailable in this unchanged token-timing build and is reported as such.
**Warm 512-token speeds remain unmeasured.**

Each topology has two fresh-load rows with full-output repeat comparisons.
Two-card lane A and lane B are alternatives; one-card uses A and reserves the
whole host. All six names and output paths are fresh. The 25 GB device floor,
request caps, budgets, prompt bytes, target arithmetic, full-precision KV and
oracle gates remain unchanged. The 128-token oracle still does not certify
longer outputs; beyond128 remains determinism-only after the second load.
No result here is submission-eligible.

The queue check initially caught copied native constant paths pointing at the
old packet. Both entry wrappers were rebuilt with private paths, reusing every
original kernel object. Source reversal checks prove that there is no native
semantic change. The two rotary constants are retained with explicit restore
hashes because private runtime dependencies are required by the queue.

The real Python arm-sequence gates pass, including request ordering, reset
receipts, stream checks and correctly named report rows. The analyzer reproduces
packet163's real two-card full512 rates of 58.6097358073 and 58.6252334250 tok/s
and keeps their prefill labeled cold. Historical one-card/two-card accounting,
synthetic512 reports, cache/stream/oracle/repeat refusal cases, every launch flag
against built help, and all six queue plans pass. All three shared
`rehearse_entry --report` runs pass; their generic preparation subcheck still
warns because no compatible shared preparation adapter is declared. The
independent native preparation/reset gate is required separately.

The native CPU gates pass 42 target resets across the three owners and 168
stream checks, plus 28 separate draft-method resets on a synthetic facade.
They check sampled mutable bytes, all allocation identities and stream survival,
including rank1's deferred timing writes. Peak observed memory was 1.173 GB.
These are preparation/reset checks with CPU marker transports, not device
arithmetic or driver tests. Fixture-order, sandbox-directory and fixture-protocol
refusals are retained alongside the corrected passing receipts. READY is written
last after all seals and checks; no device measurement has occurred.

The [batched-prefill study](../experiments/own-xpu-runtime/stage2/packet165-warm-prefill/BATCHED-PREFILL.md)
checked every DO-NOT-REPEAT for prefill/batch first and records source lines.
The runtime still walks prompt tokens individually. Paired dense/expert kernels,
M=2 attention primitives and a sequential-across-tokens GDN primitive exist,
but there is no complete causal batched-prefill engine to enable.

Using the brief's provisional 90 tok/s only as a planning input, ideal M=2
batching gives a conditional 120–164 tok/s when 50–90% of time scales, with an
all-work-scales bound of180. These are analytical calculations, not measured
points or a forecast. Expert route overlap may offer little weight reuse.
The next exact build should start with one Q8 projection over two rows, then
add causal attention and sequential BF16 GDN state updates. Larger chunks wait
for exact operator and full-model gates plus measured benefit. Packet151's
discarded-sibling policy stays closed.

The pre-existing dirty `CURRENT.md` was preserved. No live host state changed;
the packet and this note record the new CPU preparation without committing
unrelated work.

Packet documentation links and repository hygiene pass. Hygiene reports only
the two deliberately retained 4 MiB constants. Manifest paths also pass. The
broader all-tracked documentation check still reports 458 broken links outside
packet165; this task leaves those unrelated files untouched.
The whitespace check flags preserved parent prompt/source bytes and required
blank context lines in the generated patch; those identity bytes were kept.

## Packet165b — repair READY pin paths and retain their files

The missing analyzer file was a path error: both reports already lived under
`evidence/`, while READY named them relative to the topology directory.
Rerunning `test_measurement.py one-card` and `test_measurement.py two-card`
reproduced the original hashes exactly (`f4d1772b…` and `8c1f2acd…`).
The reports were already tracked. The READY writer now emits actual paths for
every check, the seals, and the two child READY files.

Following those corrected paths exposed 193 native-test source pins into the
older packet163 tree. `repair165b.py` checks their original hashes and retains
exact private copies under each topology's `lineage/packet165b-sources/`.
The original native receipts are preserved byte for byte in lineage; current
receipts point at the retained source bytes. Commands, outcomes and native
arithmetic did not change. This was retention, not a new native test run.

All three proposals passed `lanequeue.py plan --lane A/B --directory TEMP`
and `ops/rehearse_entry.py TEMP/queue-A/B.txt --report --json`, using separate
temporary copies. The six passing logs are in the packet's
`evidence/packet165b/` directory and are pinned by the final READY files.
The shared preparation-adapter and conditional gate warnings remain disclosed;
the overall report rehearsals pass. An initial rehearsal failed because a
decimal 2 GB address-space hard limit prevented the shared sandbox from setting
its fixed 2 GiB limit; the failed report is retained. Repeating with that
existing 2 GiB sandbox limit passed, without changing shared code or settings.

Every current pin is checked and retained in Git, including the previously
ignored native fixture sources and two already-built device binaries (about
40 MiB combined). Those larger artifacts are deliberately retained because
the existing seals require their exact bytes and this repair forbids compiling.
Restore them from this commit; do not replace them with a fresh build under
the old hashes. READY is written last, after evidence and this note.

CPU only: nice19, cores 8–15 and 24–31, Python `-B`, stdin `/dev/null`.
No GPU, model read, compile, service, sudo, setting, live queue or frozen tree
changed. Proposal contents are unchanged. The pre-existing dirty workspace
is preserved; this commit includes only packet165 and this note.
