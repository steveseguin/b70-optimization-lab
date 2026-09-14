# Current Workspace State

Last reviewed: **2026-09-11 15:50 UTC** (2026-09-11 11:50 EDT); the four-B70 host section below was added then.

## Authority And Update Rule

**Four-B70 host `steve-b70s`, September12:** user selected a new-model native
baseline campaign. MiniCPM5-2B setup completed, but BF16 qualification failed
the strict output-format pilot (4/6); optimization has not started. The campaign
has exited and all four cards passed postflight. No baseline is promoted. See [lane packet](experiments/minicpm5-2b-b70/README.md).
It uses a dedicated environment and original external-drive weights, with
exclusive locks and fresh processes; no permanent listener is planned. Preserve
the older queued lanes and all protected artifacts below. Actual running state
must still be checked before another launch.

This is the sole cross-repository authority for loaded service, active lane,
protected work, and immediate next actions. Verify Git status, relevant
processes, listeners, and the actual endpoint before operational changes.
Update this page when a service starts or stops; keep experiment chronology
in lane notes.

The [archived workspace ledger](CURRENT-history-20260909.md) preserves the
previous 4,577-line page verbatim. Its live-service statements and queued
actions are historical, span multiple hosts, and are not current instructions.

## Local Host And Active Review

**Four-B70 host, September14: kernel incident; GPU requests halted.**
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/FAULT.json` is present.
The first compiler-screen-01 eager control clip completed generation, but client
PID96119 became stuck in a kernel cross-CPU TLB wait during post-request work.
CPU13/CPU6 soft lockups, RCU stalls and blocked system tasks are recorded.
Only eager mode ran: no compiled candidate/block execution or completed oracle
qualification. PID95931 remains present with an empty queue; one client SIGINT
was sent, exit unconfirmed. No reboot/reset/restart or host-setting changes were
performed after the fault. The stale campaign `running` status is superseded by
this incident and the fault latch. **No new GPU requests until recovery and
health are established.** Preserve all failed/current clip files and the earlier
25/25 exact encoder results. [Incident and evidence](experiments/ltx25-b70/notes/compiler-screen-01-kernel-incident.md).

Subsequent source progress: the same boot/client kernel wait persists. One
bounded CPU-stack diagnostic timed out without a captured backtrace; no retry,
reboot or new GPU request. Future compiler packet03 is prepared with explicit
host-fault detection; its copied launcher correctly refuses current FAULT.
Runtime remains on packet02, never migrated to03.
[Preparation and fault revalidation](experiments/ltx25-b70/notes/kernel-fault-source-progress-01.md).

**Four-B70 host, September14: native compiler comparison running.**
PID95931 serves `http://127.0.0.1:8188` from prepared-encoder-compiler-02,
manifest `f1fc467a4620caabac9065e72fb7fd1628db437d1c977c86237bb0378ef8f952`.
Endpoint identity and strict after-import determinism match the startup receipt.
The bounded nine-request compiler-screen-01 is active; inspect its progress
under `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/compiler-screen-01`
before any new GPU request. It checks one native block24 with the original
control encoder, both native stage outputs against eager/repeat calculations,
and every completed clip against all four original raw references. No compiled
speed or correctness result is claimed before those gates finish.
PID78769 exited cleanly after one controlled SIGINT to load this new application
code; the computer was not rebooted. No fault latch at startup. This supersedes
the idle PID78769 statements below. [Preregistration](experiments/ltx25-b70/data/compiler-screen-01-prereg.json)
and [native gate](experiments/ltx25-b70/notes/ltx-block-compile-node-ready.md).

**Four-B70 host, September14: encoder comparison complete; compiler integration next.**
All25 encoder-screen-02 clips passed strict four-output original-reference parity
and all four unload transitions passed. No convincing speed winner: warm medians
6.364s control-before,6.377s crop,6.430s small-state,6.441s combined,6.643s
control-after. Small-state residency fixes the observed loaded-byte accounting
drift, but has no demonstrated full-clip speed gain. PID78769 is idle on control,
generation5, at `http://127.0.0.1:8188`; no fault latch. Preserve this process
while preparing the compiler successor; no competing GPU requests. Next is a
bounded one-native-block exact compilation gate, then full-clip verification if
it passes. [Results](experiments/ltx25-b70/notes/encoder-screen-02-results.md).
This supersedes the active-screen statements immediately below.

**Four-B70 host, September14: strict startup fixed; encoder comparison started.**
PID78769 serves `http://127.0.0.1:8188` from prepared-encoder-03 / encoder-server-02.
Startup identity matches the endpoint and the after-import receipt verifies
strict determinism (enabled, warning-only off). Encoder-screen-02 is running;
reuse this process and inspect its progress before any new GPU request.
The first screen on PID75850 stopped after one completed control clip: all four
outputs matched baseline bytes, but strict-mode qualification failed because
Comfy import reset warning-only mode. The corrected launcher restores the
original import order;11 CPU regression checks passed. Only the launcher differs
between the immutable packets. No quality gate was waived. Evidence and exact
scope: [startup correction](experiments/ltx25-b70/notes/encoder-strict-startup-fix.md).
User clarified that routine application reloads should not cause approval
pauses or stop optimization; the host-reboot/power/restart-chain constraints
remain. This supersedes all earlier pending-approval and process statements below.

**Four-B70 host, September14: authorized LTX replacement completed.**
User approved the restart and clarified that optimization must continue without
an unnecessary application-restart approval pause. Original PID24848
stopped cleanly after one SIGINT. Replacement PID75850 is ready at
`http://127.0.0.1:8188`; endpoint identity matches the encoder-server-01 receipt,
the queue is empty and the fault latch is absent. Host LAN IP is10.0.0.65, but
the application listens on localhost only. The immutable prepared-encoder-02
packet is active. The preregistered encoder-screen-01 comparison is now running
on this process; inspect its live progress before any new GPU work. An initial launcher
preflight exited before Torch import because the old TCP socket was in TIME-WAIT;
after its observed expiry, the bind check passed and the replacement started.
Evidence: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-migration-01.json`
and `encoder-server-01/`. This supersedes pending-replacement statements below.

**Four-B70 host, compiler preparation: routed CPU gates pass; inactive.**
The native block adapter passed its initial 29 checks; the additive ownership
guard passed 51 checks with the compiler callback itself in the full options
registry. Both stage token counts and two seeds matched video/audio outputs
exactly and repeated identically, with two compiled graphs and no graph breaks.
These are tiny CPU fixtures, not native-weight GPU or speed results. The
[checkpoint header census](experiments/ltx25-b70/notes/native-block-header-census.md)
records native block dimensions and mixed stored dtypes without loading weights.
A subsequent [executing-patcher lifecycle gate](experiments/ltx25-b70/notes/ltx-block-compile-pre-run-lifecycle.md)
passed 25 CPU checks for live owner anchoring, late changes, clone behavior and
cleanup. A subsequent [real bound CPU capture](experiments/ltx25-b70/notes/ltx-bound-lifecycle-capture-cpu.md)
passed one 64-video/26-audio-token case with the lifecycle callback present:
both outputs exact and repeatable, one compiled graph and zero graph breaks.
Native GPU correctness/overhead and broader cases remain unqualified. The
cancelled optional CPU compilation attempt is preserved separately. The
[continuation audit](experiments/ltx25-b70/notes/continuation-source-boundary.md)
also records two-stage mask loss and unresolved audio timing before streaming.
PID24848 remains idle, fault-free and unchanged; the encoder v2 maintenance
approval is still pending after multiple goal turns. The prepared launcher again
passed its read-only check. Further measured speed work is waiting on that
decision; do not infer approval from automatic continuation. Compiler work is
separate from that immutable packet.
See the [route gate](experiments/ltx25-b70/notes/ltx-block-compile-route-cpu.md).

**Four-B70 host, encoder runtime v2: GPU screen prepared, maintenance pending.**
Startup, actual placement/unload diagnostics and the 25-request bounded client
are complete. Eight startup, ten diagnostics and eight client CPU tests pass;
the copied launcher's read-only check passed and all 1,214 packet files still
match their hashes. No new GPU request, runtime change or server replacement
occurred. PID24848 remains running and idle, with its original identity and no
fault latch. The new `encoder-server-01` directory does not exist. One deliberate
graceful replacement is needed to load v2; do not start a second process beside
the current server or create a retry/restart chain. The next action is a
maintenance decision for the [concrete launch and screen](experiments/ltx25-b70/notes/encoder-runtime-v2-ready.md).
The source snapshot is `prepared-encoder-02`, manifest SHA256
`920d0e35774f298c9b11f80b3dd5e3708d0541f914e4c1857e96493bfd7282a8`.

**Four-B70 host, encoder integration follow-up: inactive source packet built.**
The four encoder variants now pass 17 CPU lifecycle tests and four integration
tests through tiny real Gemma4/CLIP/LTX projection paths. Review fixed a shared
clone policy bypass; integration also fixed rejection of CLIP's stock compute
dtype setting. Original patches and earlier receipts remain preserved. A new
non-Git source snapshot under `prepared-encoder-01` inventories 1,205 files and
keeps all baseline graph inputs except explicit encoder options. Every staged
file hash and the unchanged loaded-source hashes passed verification. No GPU
job, server restart or runtime edit occurred. PID24848 remains the loaded idle
service; no new speed claim. Next: finish startup identity/client and actual
placement diagnostics before any maintenance decision or the bounded 25-request
comparison. See the [source packet and remaining gates](experiments/ltx25-b70/notes/encoder-runtime-packet.md).

**2026-09-14 UTC, two-B70 host: local coding worker installed, FP8 ready.**
`neural-worker` runs committed source copies in CPU-only, network-disabled containers.
The bounded five-issue trial passed three independent acceptance checks; hardware
listing and zero-cost tasks remain unsolved. Candidate patches are unmerged;
reviews and unsuccessful attempts are retained in the [trial packet](experiments/local-coding-worker/README.md).
One unchanged qualified FP8 TP2/MTP1 server remains healthy at `127.0.0.1:18124`,
33,024 capacity / 4,096 batch / one sequence. Exact helper state/logs:
`/mnt/fast-ai/bench-results/local-worker-20260914/server/`.
All task CPU containers stopped. The ML Bottleneck checkout was untouched;
no generated fix was applied to the lab checkout. No server restart, model
optimization, host-setting change, GPU fault or cloud fallback. Use the existing
endpoint for subsequent worker jobs; do not launch a competing GPU lane.
[Worker commands](worker/README.md). Preserve independent four-card LTX work.


**Four-B70 host, post-stability LTX diagnostics: next runtime candidates prepared.**
One 15-second nonblocking py-spy attachment and one unchanged clip completed on
PID24848; all four output tensors matched baseline-01. The trace points to
repeated CPU copies of tiny encoder RMSNorm weights and layer scalars totaling
only 1.47 MiB. The opt-in small-state residency patch passed 12 real Gemma4 CPU
lifecycle tests; it includes a scoped accounting correction and must not be
stacked with the separate generic accounting patch. It is inactive.
Stock whole-model compilation was rejected by source audit. Default CPU
Inductor changed BF16 values despite deterministic repeats; preserving rounding
passed 6/6 toy cases. An actual native LTXAV block CPU fixture then passed both
stage token counts: two compiled graphs, zero graph breaks, both outputs exact.
These are CPU preparation gates, not GPU speed/quality results. No server restart
or runtime patch occurred; the server is idle and fault-free. Diagnostic media
was pruned after exact verification. Next work is a bounded runtime integration
packet for small-state residency/cropping and one-block compilation; do not use
the unsafe stock compile node or inject code into the live process.
See [profile result](experiments/ltx25-b70/notes/stack-profile-01-results.md),
[small-state candidate](experiments/ltx25-b70/notes/encoder-small-state-audit.md),
and [compiler block gate](experiments/ltx25-b70/notes/ltx-block-compile-cpu.md).

**2026-09-14 UTC, two-B70 host: official FP8 quickstart replay complete.**
The public-source helper ran one R304 TP2/MTP1 server at 33,024 capacity /
4,096 batch / one sequence. Strict 12/12 complete outputs matched the qualified
reference; all six practical requests passed with exact repeated outputs and
zero cached tokens. Single-replay decode 54.201 tok/s; no optimization promoted.
The documented exact-owned stop passed, all owned processes/listeners are gone,
and both GPUs/XCCL plus the full journal postflight passed. State and logs are
under `/mnt/fast-ai/bench-results/qwen-fp8-flagship-20260914`; the hash-bound
[results packet](experiments/qwen38-27b-b70/notes/2026-09-14-fp8-flagship-results.md)
records public commit, image/model checks and remaining installation limits.
No restart chain or power/memory-setting changes; four-card LTX work preserved.

**Four-B70 host, September13, LTX campaign started toward the revised goal.**
User requires one second of new video in **under one second**, at24fps with no
quality/losslessness sacrifice. Final output floor is256x256; <=3s is only an
intermediate marker. Minimal rolling review footage is authorized, including
deleting older verified campaign outputs while preserving compact hashes and
receipts. Existing model/reference artifacts stay protected. The first bounded
work completed [30 sequential requests over10 fixtures](experiments/ltx25-b70/notes/stability-01-results.md)
on the existing PID24848 endpoint: all exact repeats passed, median preview6.515s,
p956.680s, no faults/OOM. Physical memory stayed within observed bounds while
the encoder's reported offload grew690→2718MiB; source/CPU work supports an
accounting defect. Longer soaks remain deferred. Verified pruning reclaimed607MB,
retaining three campaign previews totaling170KB plus compact receipts. Two
inactive candidate patches target accounting and unnecessary hidden-state CPU
copies; no runtime change or further restart occurred. The server is idle.
See the updated [plan](experiments/ltx25-b70/PLAN.md).


**2026-09-13 EDT, two-B70 host: final FP8 prefill pass complete and stopped.**
Official 27B FP8, R304 TP2/MTP1, measured 512/2048 inputs at 2,857/3,679 input
tokens/s with 4096 capacity/batch. All 36 measured outputs repeated exactly;
strict 12/12 original-reference parity, decode −0.13%. Profiling found FP8 matrix
operations dominant and no justified quick candidate; defaults retained and
prefill campaign closed. Owned server stopped, both GPUs/XCCL and journal
postflights passed. [Results](experiments/qwen38-27b-b70/notes/2026-09-14-fp8-prefill-focus-results.md).
Raw root `/mnt/fast-ai/bench-results/qwen-fp8-prefill-focus-20260914`.
No restart chain or power/memory-setting changes; four-card LTX work preserved.

**Four-B70 host, 2026-09-13 22:23 EDT: exact-output LTX speed result.**
User prioritizes first usable clip within a few seconds, while retaining exact
baseline outputs. Baseline PID11499 exited cleanly after one planned SIGINT;
new ComfyUI PID24848 owns `127.0.0.1:8188`, with the same exclusive locks,
strict deterministic mode and cache-none computation. All four small startup
preflights passed, with no device fault. Resident model components and exact
layer placement are startup extensions; generated outputs and prompt encodings
are always recomputed. **Validated warm 256x256/25-frame clips take 6.44–7.10 s
to playable preview**, using all four B70s: transformer split across XPU0/1,
encoder XPU2 and VAEs XPU3. Three boat repeats and marble/bird reference scenes
match all four original tensors bitwise. Exact float media export also passed.
Matched warm boat client medians improved 7.85×; first split initialization took
81.21 s to preview. BasicGuider was exact but neutral and is not selected.
The one-second clip is not yet continuous real time; prolonged operation remains
untested. The transformer stays resident; the encoder still partially offloads.
Server is idle with split components retained. Further variants
use this same process; no restart chains/power/swap/cache-drop/driver changes.
See [speed campaign handoff](experiments/ltx25-b70/SPEED-HANDOFF.md).
The [LTX north star and plan](experiments/ltx25-b70/PLAN.md) now define the next
milestones: bounded stability validation, exact clips under1s, coherent streaming,
then sustained generation above24fps. The later start instruction is recorded above.
Original baseline remains frozen; new process identity is under the original
evidence root's `speed-server/`. Use `profile-clip.py --server-run` pointing there.

**2026-09-13 21:47 EDT, two-B70 host: bounded prefill follow-up complete.**
4B TP2, 9B TP2 and 27B INT4 TP1 measured at 256/512 input tokens, one user,
cache zero; all 108 measured requests repeat exactly and all three strict suites
match their original qualified outputs 12/12. One 4B TP2 profiler trace is
retained; no new runtime candidate or decode record promoted. All three owned
servers are stopped, both GPUs/XCCL and journal postflights passed. [Results](experiments/qwen38-27b-b70/notes/2026-09-14-prefill-followup-results.md),
raw evidence `/mnt/fast-ai/bench-results/qwen-prefill-followup-20260914`.
No restart chain or power/memory-setting changes; four-card LTX work preserved.

**Four-B70 host, 2026-09-13 20:42 EDT: LTX baseline bring-up.** User authorized
a very short native-precision clip and deterministic repeat checks. One local
ComfyUI server (historical PID 11499, `127.0.0.1:8188`) ran with exclusive device
locks; all four cards passed its small copy/compute preflight. **Baseline complete,
original server since replaced as described above:** three fixed-seed 256x256/25-frame generations are bitwise identical
across images, video/audio latents and waveform, with strict determinism and zero
cached nodes. First/repeat server times were 97.590/54.009/52.774 seconds. Exact
float video/audio export passed independent decode round-trip verification.
No GPU fault, OOM or tiled-VAE fallback occurred. This establishes one-prompt,
same-process repeatability, not cross-process or other-model parity. The RAID transformer and encoder failed fresh
SHA-256 checks; rejected bytes and failed receipts are preserved. The transformer
was repaired by replacing 79 damaged bytes, and the encoder by replacing 112.
All five final component files passed publisher/direct-I/O hashes; the generation
gate is now open. Rejected files and partial downloads remain preserved. Preserve the server, source and environment at
`/home/steve/src/ComfyUI-ltx25-baseline` and
`/home/steve/.venvs/ltx25-baseline`; no restart chain or power-setting changes.
See [verified baseline and reuse instructions](experiments/ltx25-b70/README.md). Evidence root:
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.

**Four-B70 host, 2026-09-13 after 20:17 EDT reboot: LTX 2.5 pivot.** User
requested parking the completed Flash-Next campaign, archiving its checkpoint
to USB, then focusing on LTX 2.5. Recent LTX, YuE2 and MiniCPM downloads were
located on the RAID, now mounted read-only. Corsair's read-only mount failed
with an NTFS chkdsk recommendation; Qwen archive verification/reclaim is
pending, and the internal checkpoint remains intact. No GPU workload was
launched. The active task is storage/download review and LTX bring-up planning;
prior queued four-card launch instructions are superseded. See the
[pivot and storage review](notes/2026-09-13-ltx25-focus-and-storage-review.md).

**2026-09-13 20:30 EDT, two-B70 host: short-prefill campaign complete.**
Measured 4B/9B W4A16 and 27B INT4/FP8 at c1 with 128/256/512-token inputs.
All 324 measured requests were cache-zero and output-exact across off/on/off;
each model passed 12/12 full-suite candidate/control and original-reference
parity. A direct-output allocation screen showed +3.0% on 4B, +2.1% on 9B,
and neutral 27B results, with strict decode differences below 0.3%. Existing
serving defaults remain unchanged; this is a single-process screen, not a new
promotion. See the [results and replay](experiments/qwen38-27b-b70/notes/2026-09-13-short-prefill-results.md)
and [complete summary](experiments/qwen38-27b-b70/data/2026-09-13-short-prefill/summary.json).
All four model stages are stopped, optimization flags removed, both GPUs/XCCL
and final journal postflights passed. No power, swap, cache-drop, driver or
reboot changes. Raw evidence remains at
`/mnt/fast-ai/bench-results/qwen-short-prefill-20260913`.

**2026-09-13 19:32 EDT, two-B70 host: R308 work complete.** The optional
single-request repair for Qwen3.5 4B and 9B is published, anonymously pullable,
and verified on the live site. Both models passed 60/60 oracle checks,
52/52 boundary checks on each of two fresh speculative servers, and all four
strict comparisons 12/12. Public-parent reconstruction matched all 17 runtime
hashes. Source/evidence integrity, guide tests, recipe CI and Pages deployment
passed. See the [qualification note](experiments/qwen35-4b-b70/notes/2026-09-13-r308-qualified-single-request.md)
and [completion receipt](experiments/qwen35-4b-b70/data/2026-09-13-r308-single-request-qualification/evidence/publication/completion.json).
All owned model and preview servers are stopped; both GPUs and XCCL passed
final health checks. No power, swap, driver, or reboot changes were made.
Scope is TP1, fixed depth 3, one active request: boundary capacity 256 and strict
capacity 1024. Clean-host certification, concurrent speculation and a new 32K
profile remain outside this qualification. R307 failures and diagnostic roots
remain preserved in the linked evidence; existing defaults retain their
original identities.

**Four-B70 Flash-Next closeout, 2026-09-13:** user requested finishing Fable's
optimization campaign and publishing existing results. A340-A394 is closed:
46.854250 tok/s approved realistic-suite record, +23.87% vs previous line;
A382/A394 repeated 32K depth median 44.052 tok/s with equal output hashes.
[Closeout](results/qwen38-flash-next-fp8-b70/CLOSEOUT-20260913.md) owns the wins,
nonpromoted trials and remaining certification limits. No server or optimization
chain is running. The separate disabled single-session draft is set aside.
User constraints remain: no AI power-setting changes and no repeated restarts.

**Four-B70 host, 2026-09-13 20:10 UTC recovery:** A394 depth repeats pass, but
teardown rc is 143 and another host interruption followed. No workload running;
hold Flash-Next launches pending teardown/host-restoration review. Git damage
restored from the already-pushed A394 commit; evidence USB mounted read-only,
RAID unmounted. See [recovery evidence](notes/2026-09-13-a394-freeze-recovery.md).
Follow-up: full Git fsck passes, NVMe reports zero media/errors; offline audit
found stop-protocol mismatch, stale health receipts and a nested-cleanup race.
See [teardown audit and next gates](notes/2026-09-13-a394-teardown-audit.md).

**2026-09-13 (EDT):** the whole INT4/W4A16 runtime is rebased onto stock vLLM XPU
v0.29.0 as **R304** (`ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:7cd7bb16`,
pushed and anonymously pullable): the R294b overlays ported as net diffs, the kernel
library rebuilt from public sources (vllm-xpu-kernels 0.1.14.1, which carries upstream
GDN fix #544, plus the lab's oneDNN r137a/r137b/r221), and three open upstream vLLM
fixes applied verbatim (#53059 alias guard, #51565 GDN first-chunk, #53542 active width).
It fixes two failures that were live on R294b: every one-token prompt and every
(1+K)-token prompt at depth K degenerated into single-character walls (30/30). Strict
gates 12/12 at published speed on the 4B, 9B and FP8-27B lanes under the recipe contract
(`verify-image-contract.sh` v0290 digest set); the INT4-27B pair is running. The 4B and
9B and both 27B recipes, packages and compose packets now point at R304 (all gates 12/12, long context 18/18,
high concurrency reproduced; kernel library reproduced bit-identically from a clean clone). The 9B scheduled-draft
profile runs on R306 (`@sha256:f124c6fb`, R304 plus its overlays and a contiguous-staging fix for upstream PR #53542). Serve with `VLLM_USE_V2_MODEL_RUNNER=0` (the launchers pin it; v0.29.0
defaults XPU to the V2 runner, which has no draft INT4 head). Details:
`experiments/qwen38-27b-b70/notes/2026-09-12-rebase-onto-vllm-v0290.md`.

**2026-09-11 (EDT):** the Qwen3.5 4B/9B and Qwen3.8 27B INT4 lanes finished the
class-consistent FP16 linear work (R290-R293 overlays, `VLLM_XPU_FP16_LINEAR_CLASSPAD`):
the R224 32-row pieces re-read the vocabulary projection once per 32 rows, 25-56% of
throughput on the 4B/9B and 3-8% on the 27B, removed losslessly. 27B package staged
on R293 (`packages/qwen38-27b-int4-fixed-k-tp2-b70`, rows R295-R298); the R293
image is built locally (`sha256:40d46730`) and awaits the GHCR push
(`repro/qwen38-27b-autoround-int4-b70/scripts/publish-r293-image-ghcr.sh`). No
containers running after 19:03 EDT; both cards passed postflight.

Host: `steve-TURIND8-2L2T`, **two B70s**. At the verification time above,
no Docker containers are running; all PR45 review servers were stopped.
Both GPUs and XCCL passed final postflight. Recheck actual process and endpoint
state before operational changes.

Target-oracle follow-up completed: both fresh compiled target-only strict tests
passed, all five comparisons were 12/12 exact, and 96 additional probes passed.
All owned containers stopped; localhost 18124 is closed and postflight passed. See
[preregistration](community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/target-oracle-20260909.md).
The six-hour soak has not been started.

The active task is correctness and reproducibility review. An isolated
Qwen3.8 27B official-FP8 R50 baseline/candidate comparison completed for PR #45:
normal-suite parity passed, tiny-prompt screens failed, candidate not promoted.
The initial review model containers were stopped; both GPUs and XCCL passed
postflight. Follow-up isolated the fresh one-token GDN routing defect: the
phase-guard candidate passed 120/120 probes, two fresh compiled MTP full suites,
12/12 baseline/fresh-repeat parity and pre/post workload screens. The campaign
is complete and stopped, not a permanent service. See the
[preregistered follow-up](community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/priority-followup-plan.md).
Read the
[maintainer validation record](community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/README.md)
for the candidate identity, completed tests and outstanding gates.

The previous Gemma listener and Qwen3.5 active-lane claims are superseded by
this observation. Preserve the existing Qwen3.5 work listed below. Run one
GPU lane at a time; verify endpoint and health independently of an image tag.

## Working Recipes And Candidates

- **Qwen3.8 27B FP8 TP2:** the [reproduction packet](repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md)
  owns the lab-qualified R187 configuration, exact-output concurrency limits
  and historical results. Its certification remains `candidate-portable-repro`;
  it is not a verified beginner setup. Consult the
  [multi-host handoff](experiments/qwen38-27b-b70/MULTI-HOST-HANDOFF.md) and
  [do-not-repeat index](experiments/qwen38-27b-b70/DO-NOT-REPEAT.md) before work.
- **PR #45 classifier fix:** separate R50 candidate, not promoted into the
  above recipe. Actual-source CPU checks pass against both source copies.
  Normal GPU suite passed 12/12 exact baseline/candidate parity, but both
  failed tiny-prefill screens; compilation-disabled candidate also failed.
  Sustained mixed-session validation remains unperformed; not a verified fix.
  A separate maintainer GDN phase guard fixes the local one-token symptom in
  the [bounded follow-up](community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/priority-20260909/README.md),
  but is not promoted as the contributor's incident resolution.
- **Gemma 4 26B Q8:** [result/handoff](results/gemma4-26b-a4b-q8-b70/HANDOFF.md)
  and [standalone recipe](repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md)
  preserve the measured setup. Their existence does not mean Gemma is loaded.
- Other lane status belongs in the [model effort index](docs/model-effort-index.md)
  and [reproducibility map](docs/current-reproducibility-map.md).
  The [scoreboard](results/scoreboard.md) is historical measurement evidence,
  not service state.

## Known Issues And Next Actions

1. Before promoting the GDN local fix, run the contributor's actual mixed-session
   soak. The matched-image MTP0/MTP1 strict-oracle matrix now passes; the
   multi-hour incident remains unverified. PR #45 is merged as a community
   contribution, not a production promotion.
2. Reproduce one selected recipe end to end: pinned inputs, build, launch,
   quality gate and clean teardown. Correct defects found along that route
   before additional speed tuning.
3. Audit recent changes by affected runtime, shared harness and published
   recipe. The [September 8 review](notes/2026-09-08-targeted-correctness-cleanup.md)
   was bounded: syntax checks are not execution coverage, and commit author
   labels do not establish which model wrote a change.
4. Three promoted Flash-Next replay paths now use exact frozen verifier
   snapshots; four replay clients now stop their servers on failure. Bundle
   chains were restored and verified from the public base. See the
   [audit record](notes/2026-09-09-replay-and-validator-audit.md).
   The broader 229 historical experimental hash mismatches were not blindly
   repinned. Four-card runtime replay remains untested on this two-card host.
5. Keep ML Bottleneck automatic refresh paused. Numerical fixture tests are
   now separated from refreshed-data checks. The ingestion parser correction
   passes 94 tests and resolves the 3060 interpretation in a migration test.
   Publication still blocks on the 4070, nine ambiguous measurements and
   calibration thresholds. Published evidence remains unchanged. Details are in
   that repository's `docs/refresh-review-2026-09-08.md`.

## Other Host: Four-Card Work

MiniMax M2.7 INT4 and Flash-Next TP4 belong to the **four-B70 host**, not
this two-card machine. The [MiniMax post-reboot note](notes/NEXT-minimax-after-reboot.md)
is that host's resume packet; its remount, driver and launch instructions
must not be applied here. It records an unresolved bring-up validation after
a driver wedge, not a successful serving result. On the owning host, avoid
polling `xpu-smi` during initialization, verify the four devices and use its
bounded health checks before continuing.

Flash-Next history and accepted identities live in its
[handoff](results/qwen38-flash-next-fp8-b70/HANDOFF.md) and
[result packet](results/qwen38-flash-next-fp8-b70/README.md).
Historical reboot notices in the archive do not describe this boot.

### Four-B70 host, 2026-09-11: Qwen3.5-9B W4A16 lane closed, Flash-Next next

The Qwen3.5-9B W4A16 one-B70 lane on `steve-b70s` is closed and published: the
static depth-3 headline (113.27 tok/s) stands, and a second operating
configuration - one server for every batch size, draft depth scheduled by
batch size on three pure-Python overlays over R276 - is promoted in the
[guide](repro/qwen35-9b-w4a16-b70/README.md#one-server-for-every-batch-size-campaigns-cudynm1--cudynm1r-2026-09-11),
[package](packages/qwen35-9b-w4a16-b70/package.json) and
[performance index](results/scoreboard.md): 110.7 tok/s at one user, 1,184 at
64 users, exact through 32 users, 18/18 exact 2K-32K. The env-knob ladder for
single-user decode on this lane is exhausted (defaults optimal on every axis);
what remains is kernel work (fused INT4 draft head) recorded in the
[campaign note](experiments/qwen35-9b-b70/notes/2026-09-10-one-server-for-every-batch-size.md).
No lane container is running. The next active lane on this host is Qwen3.8
Flash-Next (its [handoff](results/qwen38-flash-next-fp8-b70/HANDOFF.md)).

### Four-B70 host, 2026-09-13: Flash-Next lossless MTP1 at 46.85 tok/s (record approved)

The Flash-Next lane's step-timing decomposition (A340-A358) put 8.7 ms of the 42.7 ms
two-row verify step in vLLM's Python serial GDN path and showed the cost is in neither its
kernels nor its glue. The kernel extension's own exact serial mode, gated to four verifier rows
by the served build, accepts two when `_xpu_C.abi3.so` is rebuilt from the lane's kernel head
(`bbae3c5` over `e421889`, [series](patches/qwen38-flash-next-fp8-b70/xpu-kernels-gdn-exact-serial-bbae3c5/README.md)).
With that mode selected the verify step is 33.7 ms and every output pin holds (kernel probe
bit-identical; exact-2K `afffd211…`, exact-4K `1d833e5f…` on four servers; 12/12 suite outputs
equal to the 37.83 record). Certified on three servers (A364, A365, A366: short 53.4, exact-2K
48.2, exact-4K 48.5 tok/s) and recorded on a fourth (A367: **46.854250 tok/s** class-balanced,
LocalMaxxing [`cmtzask41000nlq011f16bpbc`](https://www.localmaxxing.com/runs/cmtzask41000nlq011f16bpbc)
approved). Guide [`repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/`](repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md),
package `packages/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/`, narrative in the
[result packet](results/qwen38-flash-next-fp8-b70/README.md). Host notes: two silent freezes hit
launches started 60-90 s after the previous server's teardown (swap toggle); leave five minutes
between a stop and the next launch. Unused models (laguna-s-2.1, muse-glimmer, the 9B pair) were
moved to `/mnt/raid-models` with symlinks left in place; root NVMe at 301 GB free. No lane
server is running.

## Protected Work And Artifacts

Preserve these paths and inspect their status before any build, cleanup, or
service change:

- `/home/steve/src/llama.cpp-muse-100`: preserved source/build used by the inactive Muse fleet;
- `/mnt/fast-ai/src/llama.cpp-q38-q4k-glu-tp2`: accepted Qwen3.8 Q4_K_M source at
  `a4349bcee`; preserve its intentional three-file uncommitted fusion delta;
- `/mnt/fast-ai/src/llama.cpp-q38-q4k-glu-tp2/build-sycl-aot-bmg-g31-oneapi-2026.1.1`:
  accepted oneAPI 2026.1.1 BMG-G31 AOT build;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-gguf/`: accepted Qwen3.8 GGUF targets and MTP sidecars;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-fp8/`: official FP8 artifact retained for the separate vLLM lane;
- `/mnt/fast-ai/bench-results/qwen38-official-fp8-vllm-xpu-20260816/`:
  official FP8 eager/graph/P2P controls, final quality gate, cache-zero result,
  runtime capture, and post-run health evidence;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-gptq-int4-mtp/`: hash-verified
  SergioB GPTQ INT4 target with 15 BF16 MTP tensors; community replay lane;
- `/mnt/fast-ai/bench-results/qwen38-q4km-asrock-b70-20260815-pass2/`:
  accepted Q4_K fusion A/B and cold-suite evidence;
- `/mnt/fast-ai/bench-results/qwen38-gptq-int4-asrock-b70-20260816/`:
  SergioB target-only eager/graph validation, failed conservative-U graph
  attempt, logs, inspect records, prompts, and raw SSE evidence;
- `/mnt/fast-ai/bench-results/qwen38-gptq-quality-20260816/`: native/FP8 KV,
  semantic quality, MTP runtime-dtype, Q8/Q4 controls, and reset-window evidence;
- `/mnt/fast-ai/src/llama.cpp-q8-tp2-directq8-isolated`: current accepted Qwen TP2 source;
- `/mnt/fast-ai/src/llama.cpp-q38-tp2-distributed-greedy-directq8`: closed
  exact distributed-argmax candidate; preserve for mechanism reuse only;
- `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-distributed-greedy/`:
  position-balanced reasoning-off controls/candidates and exact output oracle;
- `/mnt/fast-ai/src/llama.cpp-mndodd-intel-sycl`: prior accepted Qwen TP2 source; preserve as control;
- `/mnt/fast-ai/llm-models/qwen3.6-27b-q8_0-gguf/`: accepted Qwen model;
- `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260813-tp2-fusion/`:
  promoted Qwen evidence and bounded negatives;
- `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260814-40tps/`:
  Qwen pass-1/pass-2 evidence and current clean result;
- `experiments/qwen27_graphsafe_flash_attention/`: graph-safe INT4 source and
  generated research state;
- `experiments/qwen36-27b-autoround-int4-b70/`: INT4/MTP research packet and
  diagnostic artifacts.

Large ignored Qwen artifacts may be archived only after a complete inventory,
hash verification, and a recorded restore path. Never use broad `git clean` or
delete tracked experiment material to make the tree look tidy.

## Additional Preserved Work And Operational Guards

Pre-existing dirty Qwen3.5 work at review start; inspect and preserve:

- `experiments/qwen35-9b-b70/probes/drift-reproduction.py`
- `experiments/qwen35-9b-b70/scripts/analyze-admission-composition.py`
- `experiments/qwen35-9b-b70/scripts/run-20260908-drift-reproduction.sh`

The prior ledger also protects the dirty Flash-Next source tree; do not
reuse or modify it for the Qwen3.8 R50 review. Root-NVMe/BIOS work remains
paused. Retain the existing frozen-runner guards: no bulk reads/scans of
`/mnt/fast-ai` or `/mnt/usb-models`; do not start
`generate-q38-root-nvme-link-clearance-v1.py` or any `w13`/`hc` runner.
Do not run process-search commands containing
`w13-m1-xpu-graph-gate.py` or the A2 result path: frozen health checks can
mistake the search itself for a surviving runner. See the
[archived ownership notice](CURRENT-history-20260909.md#immediate-manager-actions)
for the original guard and its recorded false positives.

Do not place new model downloads on NVMe based on an old free-space report.
Verify current capacity, mount identity and lane ownership first. Follow
[AGENTS.md](AGENTS.md) for main-only Git, secrets, runtime isolation,
quality gates and exact publication requirements.
