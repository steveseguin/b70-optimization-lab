# Packet138 — cross-layer expert prefetch, phase 1

Started 2026-10-18 16:33 UTC. Two-hour CPU preparation/analysis box; capture
proposal is the first milestone, due by 17:48 UTC. No device launch or queue
mutation is authorized. Packet100b and all other existing packets remain frozen.

Preregistered decision: proceed to a phase-2 device design only if a replay of
real independent calibration captures projects at least +3% versus the packet58v
one-card asynchronous-cache control, with all prefetch traffic (including wrong
predictions) fitting the causal per-layer PCIe window. Missing captures cannot
count as a pass. The control and windows are modeled with explicit assumptions;
they are not new device measurements. Failure of the registered projection gate
gets a closeout and DO-NOT-REPEAT row; missing capture evidence remains pending.

Capture plan: copy packet100b's accepted-target diagnostic; retain all 48 target
layers and the first 48 generated tokens of each of packet55's twelve fixed
held-out prompts. Also run one packet49 sanity prompt, excluded from analysis.
Capture top-ten routes, BF16 router inputs, complete BF16 four-stream output
residuals, and actual BF16 router logits for CPU replay validation. Full residuals
matter: this model has four hyperconnection streams, not a single residual.
Every token is compared with packet49 where available and with the pinned
packet55 target output on held-out text. The latter is device reference evidence,
not a newly certified CPU oracle. All arithmetic stays iq3-p49-split32-v1.

Predictors: next-layer unchanged router on current router input; next-layer
router on each of the four output streams (reported separately). Report recall
at widths 10, 12, 16, per layer and prompt/class. No fitting or benchmark prompts.
An output-residual predictor is available only after L finishes; it cannot be
credited the preceding layer's compute window. Same-layer CPU logits/routes must
match the captured oracle before any prediction result qualifies.

Cache replay: 18,000,000,000-byte global LRU, packed expert sizes from GGUF,
packet58v delayed asynchronous fills and one transaction at a time. Charge wrong,
late and evicted prefetches; protect in-flight readers and DMA slots. Report
zero-copy bytes/token, fill bytes, residency lag, overflow and PCIe-window fit.
Timing inputs come from 58g/58p receipts, with unknown per-layer timing explicitly
pending rather than dividing whole-token time and calling it measured. Projected
rates are sensitivities, not device speed or a public benchmark.

Credit: pre-gating / cross-layer expert prediction ideas from MoE-offloading
literature. Implementation is our own, using the lab's existing router arithmetic.
Packet58i frequency prefetch and packet58h MTP remain closed; this studies a
causal hidden-state predictor instead of a frequency policy.

Operational bounds: nice 19, cores 8–15 and 24–31, python3 -B, stdin /dev/null;
CPU-only main processes capped at 4 GiB, no inherited native-launch caps; shared
ops/compile_turn.py for builds; root free >=25 GB, build <=300 MB, device capture
output <=1 GB. Proposals use screen-<job> units, closed environment, native
getrlimit guard, shared oracle binding, and cooperative drain. No services,
sudo, host setting changes, cleanup or foreign-process signals.

Initial pull --rebase refused unrelated dirty files. Fetch confirmed HEAD and
origin/main both 13b53caf65203105b9bac160fd38d46814199502. Root free: 36.08 GB.

Capture preparation: both GNU/Intel entry builds pass; unchanged kernel objects
are reused. Both actual full-size startup mocks pass all 1,152 per-rank slots,
including every router/input/residual extent. Two fresh byte-copy tests per
compiler agree. Twelve Python checks and the real two-rank intercepted launch
pass; lanequeue's actual screen unit and environment are checked. The temporary
proposal plan passes. Build: 66,232,536 bytes. Raw capture plan: 801,036,288 bytes.
Expected device duration: 5–15 minutes; watchdog: 60 minutes. No device launched.
The source seal excludes external oracle resolution and verifies that authority
through its binding. All existing packet trees and live queue files are intact.

Follow-up CPU audit: regenerated held-out input.json prompt paths, text hashes
and nested token-file hashes instead of leaving the copied sanity prompt's
labels. Actual token IDs and native binaries did not change. The validator now
checks those nested metadata bindings too. Both native launch rehearsals,
twelve checks, source seal and temporary queue plan pass again. Capture and
analysis source seals are separate so ongoing CPU analysis cannot invalidate
the prepared capture. During this audit the external coordinator queued
packet138-capture-B; this preparer did not write any live queue. No capture
output directory existed when the audit completed.

CPU analysis preparation (17:06 UTC, before capture): both compilers and fresh
processes produce identical exact-router bytes on real GGUF weights and synthetic
states. Probability ties match the unchanged production top-ten route. The
18 GB cache model matches the actual 58v allocator, eviction order and offsets
on 150 randomized cases. A full-size synthetic layout test covers all 48 layers,
12 prompts, five predictor inputs and three widths; it writes only to temporary
scratch, never to real-capture artifacts.

The 58g/58p receipts lack measured per-layer clocks. The registered sensitivity
uses 25%, 50% and 100% of a 0.645465 ms average remainder per layer, derived from
58p's measured token/cache spans. Effective DMA bandwidth, predictor cost and
publication cost are explicit assumptions. Before seeing capture data, clarify
that this is the requested projection gate: a candidate must clear +3% across
all three scenarios and fit every charged prefetch window. A passing result may
recommend phase-2 design conditionally; actual layer timing and device equality
must then be measured. Missing per-layer measurements alone are not a veto on
a phase-1 projection. No measured 58v rate is invented; its control is modeled.

The external coordinator started the capture at 17:07 UTC. While the GPUs were
busy, the required read-only parallel audit found no arithmetic, LRU or layout
defect. It identified two analysis safeguards, both added before real replay:
positive candidates must still pass with windows shortened by their projected
acceleration, and replay outputs must bind their source/library identity so
simulation rejects stale results after code changes. Capture sources stayed fixed.
