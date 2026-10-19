# Packet153 shared build contract

This document is part of every packet152 launch brief. It authorizes future
CPU preparation of the selected mechanism, not a device launch. Packet152
itself performs none of these build/copy steps.

## Why

Packet136 bundle8 is the exact two-card 58.798108759182306 tok/s reference.
Packet150 is a diagnostic split; a boundary above 0.4 ms/cycle is an opportunity
to examine, not measured removable work. Read [PLAN.md](PLAN.md), the selected
segment design, completed packet150 evidence, current lane handoff and all
required repository first reads before changing runtime behavior.

## Do

1. Work on main. Pull first; if unrelated dirty files prevent rebase, fetch
   and verify HEAD equals origin/main or account for concurrent local commits.
   Preserve all unrelated files. Start from packet136's selected
   `miss=banks-batch`, `head=head-split-compute`, fixed 80128 draft prefix,
   unchanged target arithmetic `iq3-p49-split32-v1` and packet49 oracle.

2. Create only the selected `stage2/packet153-<segment>/`. Copy packet136's
   source/configuration with literal symlinks preserved, then vendor its
   **actual resolved compile and Python dependency closure** into this new
   packet. Preserve the original oracle authority link and verify it separately.
   Do not copy weight payloads, build caches, raw device runs or old READY files.
   Do not implement on packet150's mutated probe image. Vendor needed v5
   lifecycle/report support from its proven fixed sources, recording origin
   hashes and import closure; do not inherit its duplicate-work candidate.
   All executable includes/imports must resolve locally or through an explicit
   allowed stable authority. No runtime dependency on mutable sibling packets.
   Audit source links separately from external oracle/fixture authority.

3. Bind packet150 complete report/raw view input hashes and the exact analyzer
   used. Validate all views and original equality gates. Record the segment
   subcause, bound on recoverable work, and selection reason. If only required
   peer/compute work explains the boundary, retain that finding and choose the
   next qualifying design in PLAN; do not spend a device load on an impossible
   removal. Do not turn synthetic CPU or duplicate service into speed evidence.

4. Implement one default-off dimension with exactly two choices: unchanged
   bundle8 control and specified candidate. Allocate the union once, before
   views; no weights/format, full-BF16 KV, context, target split, row counts,
   compiler arithmetic or draft policy changes. Reset all candidate state at
   each request/view, including bank roles, capture generations and private
   staging; preserve six bank captures. Source-seal the actual generated code,
   translation units, binary, selection and wrapper path.

5. Build serially through the existing admitted compiler-turn workflow; no
   bypass while packet58ah holds WS→chain-end. GNU and Intel each run fresh
   miniature correctness repeats, mechanism-specific fixtures, malformed
   state/event refusals, native controller cancellation/redo, full canonical
   state, teardown/drain and host limits tests. Keep same-compiler raw-byte
   comparisons; do not relax NaNs or regenerate an oracle to hide changed
   arithmetic. Use synthetic/metadata shapes only in CPU prep, no model/GGUF
   payload reads. Under the ≤2 GB cap, shard fixtures by independent cases.
   If a required gate cannot fit, mark it pending and READY false; no inherited
   large-fixture claim. Small compile outputs target ≤250 MB (hard ≤300 MB).

6. Prepare **two packet-local proposals**, not ops/live queue edits:
   `proposals/smoke-B.txt` and `proposals/v5-B.txt`. These are JSON queue
   rows compatible with the current lane planner. Use lane B, frozen fixed
   twelve prompts, candidate smoke 12×64 plus separate incident64/reset sanity,
   then one model load C/X/C/X/C with 12×128 per view and incident64 at each
   boundary. Benchmark choices change only the candidate dimension.
   Smoke must pass before bracket admission. All prompts, token hashes,
   proposal sequences, acceptance, six-bank/reset checks and final-state
   equality are mandatory. `cached_tokens=0`, no prompt/KV/response reuse.
   Diagnostic repeat views are not a realistic final gate or a public record.

7. **Prove analyzer data in the smoke's first minute.** Add a small live reader
   invoked by the smoke runner, not a manual end-of-run inspection. Within
   60 seconds of first decode receipt require real rank0 segment records,
   request/epoch/position/sequence IDs, monotone start/end timestamps and
   candidate mechanism counters from the native process. A prompt-end flush
   is allowed only if it occurs inside that deadline. Keep first raw rows,
   hashes, observed byte/row counts and parser output in
   `evidence/smoke-first-minute.json`. Validate the first completed request
   through the actual analyzer/report parser; later require all twelve.
   During the first minute from job start, separately prove live startup/
   load progress, with no false segment claim before decode begins.
   Empty files, missing segment, wrong rank, stale epoch, zero synthetic
   records and no-growth must cooperatively stop new work, drain and fail.
   Never repair missing data by substituting zeros or creating a “passed”
   receipt. Rehearse missing/truncated/wrong-schema failures on CPU.
   One-time bounded rows/counters only; no full every-kernel profiling.
   Run the ordinary endpoint comparison without instrumentation-induced
   extra work, while retaining enough request-bound counters to prove mechanism.

8. **Write budget from measured retained bytes.** Read an equivalent completed
   view's regular-file sizes as metadata (do not hash model files). The brief's
   guide is approximately 250,000,000 bytes/view. Initial per-view plan therefore
   must be ≤750,000,000 bytes, five-view plan ≤3,750,000,000 bytes; use actual
   measured comparable size if different, and explicitly document retained
   overhead. Ensure `planned_writes ≤ 3 × measured` for the same scope,
   including smoke diagnostics. Do not inherit p150's 1.1 GB/view constant.
   If expected output cannot fit this bound, shrink redundant telemetry before
   READY, never delete quality evidence or understate the plan. Budget builds
   and temporary duplication separately; retain ≥25 GB root free after peak
   writes and obey current coordinator's stronger reserve if applicable.
   Record source of byte measurement, units and plan calculation in BUDGET.md.

9. Use the **real** entry path and `ops/launch_env.py` closed environment;
   no hand-built approximation. Invoke read-only shared rehearsal:
   `python3 -B experiments/own-xpu-runtime/ops/rehearse_entry.py <proposal> --report --json`
   for both proposals, saving output under the new packet. It must exercise
   actual smoke and bracket report dispatch, duplicate-import detection,
   native loader/parser, allowed environment, wrong unit and source-pin
   negatives. Vendor support when needed; ops remains unchanged. Use actual
   expected `screen-<name>.service` names in tests. Run native getrlimit
   refusal checks separately from capped CPU mocks: finite CPU-entry limits
   must never leak into native device launch. Read the actual ops contract
   before assembling argv; do not run device-entry binaries as a “CPU check.”

10. Run real lane planner on disposable queue copies, bind its current pin guard,
    require both proposals pass. No live `queue-*.txt` edit and no enqueuing.
    Preserve original drain-clock regression, event-owner refusal, abort
    propagation and all safety checks. Default planned smoke 240–360 seconds,
    v5 720–1200 seconds; revise from measured comparable loads. Set watchdog
    to at least 4× the admitted upper estimate unless current coordinator
    preregistration explicitly requires a stricter bound. It must stop
    cooperatively, never group-kill a busy GPU. No automatic retry.

11. Save source/evidence/pins, design delta, lossless status and a short note.
    Commit with explicit paths and `git commit --only -- <your paths>`;
    push immediately. Then write `READY-FOR-DEVICE.json` **last**, binding
    the pushed source commit, new binary/selection/report/data-schema hashes,
    CPU checks, proposals, measured storage plan and unresolved gates.
    CPU preparation readiness is not device output qualification. If any
    required CPU gate failed, READY is false. Commit the marker and push.
    Give the coordinator paths and exact outstanding device steps, not a claim
    of a new record. No source mutation after READY without a new seal.

## Device decision in the proposed campaign

Smoke failure ends admission; no bracket/retry. One-load bracket compares both
candidate views to all three controls, recomputes the established per-class
metric, reports drift and lower-tail/TTFT/natural-length limits, and requires
all exact output/proposal/state gates. Predeclare exploratory success at
≥2% over the fastest control in both candidate views with ≤1% control
max/min drift. A smaller exact result is recorded, not silently adopted.
A single load is a screen: repository rules require at least two fresh
servers before a speed verdict/promotion. The coordinator schedules that
confirmation if warranted; no duplicate job is queued here. Strict512 and
promotion attestation remain separate and false for these 128-token screens.

## Rules

CPU preparation only: nice19, cores 8–15/24–31, python3 -B, stdin /dev/null,
≤2 GB RAM, no GPU/services/sudo/settings/model payloads. One model lane per
host and all packet58ah reservations bind. Never print secrets. Existing
packets, stage2/screen and ops are read-only; proposals live in the new packet.
No borrowed compute overlap: one CCS on B70; BCS overlap needs explicit
producer/consumer dependencies and actual evidence. Unchanged full 16-bit KV,
target/verifier and oracle; no numerical tolerance, learned history or prompt
reuse. Decide without permission round trips. Commit messages end with:

Co-Authored-By: Codex <noreply@openai.com>
