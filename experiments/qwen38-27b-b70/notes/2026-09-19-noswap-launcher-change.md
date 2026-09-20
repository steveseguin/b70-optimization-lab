# The no-swap launcher change: what it costs in pinned evidence, and what still needs a GPU (2026-09-19)

Date: 2026-09-19, after the third and last validation start. This note is the bookkeeping half of
[the container memory cap finding](2026-09-19-container-memory-cap-swap.md): that note establishes
*why* `--memory-swap` should equal `--memory` and proves it over three service starts; this one
records what changing the two launchers did to the repository's byte-pinned evidence, what was
regenerated here on the CPU, and exactly which GPU runs are still owed.

## In plain words

The change itself is one word in each of two files. The work is everything that pins those two files.

Our published evidence packets record the exact bytes of the launcher that produced each measured
number, and the site's CI re-checks those bytes on every push. That is the point of them: a packet
that says "90.24 tokens a second" is worth nothing if the launcher it names has quietly moved since.
So editing `serve.py` is never a one-line change -- the last time it was treated as one it broke the
site build.

**What we did not do is re-stamp the packets.** A fresh acceptance run on the new launcher is the
only thing that can honestly say the new launcher produces the measured result, and that needs the
GPUs. Instead the packet now carries a declaration that names the change, pins both the old and the
new bytes, says in plain words that acceptance is pending, and -- this is the part that makes it more
than a promise -- **proves offline that the change is confined to what it claims.** CI builds the
`docker run` command line from the launcher as it was when the packet was frozen, builds it again
from the launcher as it is today, and requires the two to differ in exactly one token:
`--memory-swap`, `16g` to `12g`. Anything else fails the build. The site stays green, the packet
stays honest, and the pending work is printed by name on every CI run.

Three things are now owed on a GPU, listed at the bottom. None of them is urgent; the service is up
and correct, and the two-card headroom has been measured three times. The one that actually matters
is the one-card measurement, because the one-card profiles carry about 2.4 GB more host-resident
memory than the two-card one and their headroom is still arithmetic rather than a reading.

**Update, 20:14 EDT: the two-card acceptance run was tried and the packet still cannot be frozen.**
The run itself went perfectly -- twelve of twelve prompts exactly right, all six practical requests
right with identical repeats, a clean stop, clean health probes either side, and the container once
again swapped nothing at all with no out-of-memory kills. But the run compared itself against the
wrong yardstick. There are two reference servers on this machine and the command we wrote down left
out the one-line setting that picks the right one, so the run measured itself against a September 16
server that predates a setting the current recipe uses. Every direct comparison of the two containers
matches -- same image, same command line, same settings -- but the comparison the run recorded for
itself does not, and that is a gate. **The honest remedy is one more run with the setting in place;
nothing was worked around.** No packet was written, nothing was repointed, the three pending
declarations stay exactly where they were, and no published number moved. What the run *does* leave
behind is worth having: the first memory receipt from a container the shipped launcher itself started
with no swap, confirming for the fourth time that the working set is about 9 GB with about 3 GB to
spare and no out-of-memory kills. See
[GPU run 1, attempt 1](#gpu-run-1-attempt-1-2026-09-19-2008-2014-edt----the-session-was-clean-and-the-packet-still-cannot-be-frozen).

## The change

Both launchers, in `docker_argv`, with a comment block at the call site citing the finding note:

```
-            '--memory', '12g', '--memory-swap', '16g',
+            '--memory', '12g', '--memory-swap', '12g',
```

| File | Line (before) | New sha256 |
| --- | --- | --- |
| `packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py` | 222 | `9668a6baea99833d852ece012d202b75f19806e90a652f6ab2eb3e6c359f9baa` (was `9f509e97...`) |
| `packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py` | 221 | `cd954ea1846a96280a69b444be5ccac14d035b5b18235ad1e9dcae97e05ff45a` (was `27f589a5...`) |

Nothing else in either `docker_argv` changed, which CI now proves for the two-card launcher (see
"The declared-drift mechanism" below) and the unit tests assert for both
(`tools/test_fp8_serve.py`: `--memory-swap` must equal `--memory`, on the two-card `recommended` and
`depth-1` profiles and on all three one-card profiles).

## Every artifact that pins a launcher hash, and what regenerates it

Found by hashing both launchers and grepping the repository for those digests, then by tracing each
hit back to the tool that writes it. Five artifacts pin a launcher's bytes; three more are generated
*from* a launcher without pinning it.

### A. Pinned, gated by CI -- handled without a GPU, marked pending

**1. `experiments/qwen38-27b-b70/data/2026-09-17-fp8-two-card-allgather/manifest.json`**

The only launcher pin that `guides.yml` actually exercises. Its `sources` list pins eleven repository
files, three of which this work changed: the two-card `serve.py`, the collector itself, and the
acceptance session runner. `collect-fp8-tp2-acceptance-evidence.py` (a guides.yml step) asserts each
one still matches the working tree, so the launcher edit failed the build immediately:

```
AssertionError: packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py
```

* **Generator:** `collect-fp8-tp2-acceptance-evidence.py --raw <session> --out <new packet dir>`,
  which refuses to overwrite an existing packet. Its input is a raw session from
  `run-fp8-tp2-acceptance-session.py`. **Needs a GPU.**
* **Done here, without a GPU:** the packet gained `source-drift.json`, which declares all three
  files, pins the frozen and the current digest of each, states `"acceptance": "pending"` with a
  reason and a `retire_by`, and carries a machine-checked proof for each (below). The packet's
  `summary.json`, `evidence.tar.gz` and every gate are **untouched** -- they still recompute from
  the frozen bytes exactly as before.
* **Still owed:** a fresh acceptance session on the new launcher. See GPU run 1.

Note that the same `manifest.json` also pins `source/packages/.../serve.py` and
`downloaded-source/packages/.../serve.py` at the old digest. Those are the bytes *inside*
`evidence.tar.gz` -- the launcher as it was when the session ran. They are correct as they stand and
must never be rewritten; they are the record.

**2. `packages/catalog.json`**

Generated. Regenerated with `python3 tools/validate-repro-guides.py --write-package-catalog`.
**No GPU.** Done -- two added lines, from the package-dependency declaration below.

**3. `packages/qwen38-27b-fp8-tp1-b70/package.json` and `.../tp2-b70/package.json`**

Not a hash pin, but `validate-repro-guides.py` follows every repository path reachable from a package
command and requires it to be declared in `dependencies`. The new comment blocks cite the finding
note by path, so both manifests now declare
`experiments/qwen38-27b-b70/notes/2026-09-19-container-memory-cap-swap.md`. One line each, in the
file's own indentation. **No GPU.** Done.

### B. Generated from a launcher, no hash pin

**4. `packages/qwen38-27b-fp8-tp2-b70/compose.yaml`**

Rendered from the launcher's own `docker run` argv by
`packages/qwen38-27b-fp8-tp2-b70/scripts/render-compose.sh` (which calls
`serve.py render --profile recommended`, a pure argv build -- no image, no weights, no GPU).
**No GPU.** Re-rendered.

Re-rendering alone changed nothing, and that turned out to be a hole worth closing:
`tools/render-container-compose.py` **hardcoded** `mem_limit: 12g` and `memswap_limit: 20g` rather
than taking them from the argv it renders. So the packet was handing compose users an 8 GiB swap
allowance -- more than the 4 GiB the launcher used to give, and a configuration nobody has ever
measured. The renderer now takes `MEM_LIMIT`/`MEMSWAP_LIMIT` from the environment with the old values
as defaults, and this packet's `render-compose.sh` sets `12g`/`12g`. Net effect: a one-line diff in
this packet's `compose.yaml`, and the four other packets that use the renderer
(`qwen35-4b-w4a16-b70`, `qwen35-9b-w4a16-b70`, `qwen35-9b-fp8-b70`,
`qwen38-27b-int4-fixed-k-tp2-b70`) are byte-identical, because their launchers were not part of this
validation. **Those four still advertise `memswap_limit: 20g` and should be revisited**; it is
recorded here rather than changed blind.

**5. `index.html`, `models/*.html`, `learn/hardware.html`**

Built by `tools/build-model-pages.py`; `git diff --exit-code` over them is a CI step. **No GPU.**
Ran it: no diff. No site page quotes a launcher digest.

### C. Pinned, not gated by CI -- deliberately left at the old digest

These are attestations *of a measurement*. Their `launcher_sha256` names the launcher that produced
the recorded tokens per second. Re-running their generators would stamp today's bytes onto numbers
measured with yesterday's, which is precisely the dishonest move. **They stay as they are until a new
strict run on the new launcher gives them something true to say.**

| Artifact | Pins | Generator | Needs a GPU? |
| --- | --- | --- | --- |
| `data/2026-09-17-fp8-tp2-mtp5-r310-allgather-promotion-attestation.json` | tp2 `9f509e97...` | `build-fp8-tp2-allgather-localmaxxing.py` (line 60 recomputes `launcher_sha256` from the working tree) | The script is CPU-only and idempotent, but **the numbers it carries need a fresh strict run**, so re-running it now would be a lie told by a CPU |
| `data/localmaxxing-qwen38-27b-fp8-tp2-mtp5-shortlist-allgather-r310-strict-20260917.queue.json` | tp2 `9f509e97...` | the same script (writes attestation and queue together), then `finish-localmaxxing-fp8-tp2-payload.py` | same |
| `data/2026-09-18-fp8-tp1-mtp5-r312d-32k-promotion-attestation.json` | tp1 `27f589a5...` | `build-fp8-tp1-r312d-localmaxxing.py` (line 97) | same, for the one-card record |
| `data/localmaxxing-qwen38-27b-fp8-tp1-mtp5-shortlist-r312d-32k-strict-20260918.queue.json` | tp1 `27f589a5...` | the same script, then `finish-localmaxxing-fp8-tp1-payload.py` | same |

The two-card LocalMaxxing record is submitted; the one-card R312d payload is written but held until
its image is public (`docs/localmaxxing.md`). **Until the runs below are done, a reader who downloads
the package gets a launcher whose digest does not match the submitted record's `launcher_sha256`.**
That is the honest state of things and it is what `source-drift.json` says out loud.

### D. Already-drifted packets, untouched

`collect-fp8-flagship-evidence.py` verifies `data/2026-09-16-fp8-flagship` and
`data/2026-09-14-fp8-flagship` the same way, and both already pinned a pre-`f26a886c1` `serve.py`
before this change -- their `verify` has been failing on that assertion for days. They are **not** in
`guides.yml`, which is why nobody noticed. This change does not make them worse and does not fix
them; they are frozen records of older recipes and the right resolution is to leave them frozen.
Worth knowing before someone runs that verifier and blames the no-swap edit.

## The declared-drift mechanism

`source-drift.json` sits beside `manifest.json` in the packet. It is optional: with no such file,
every source must match byte for byte, exactly as before. With it, a source that has moved must be
declared -- both digests, a reason, a `retire_by`, and `"acceptance": "pending"` -- **and carry a
proof that CI can check offline**. Undeclared drift still fails the build. The three proof kinds:

| Kind | Used for | What it actually checks |
| --- | --- | --- |
| `docker_argv` | the two-card `serve.py` | Imports the frozen launcher out of `evidence.tar.gz` and the current one from the working tree, builds `docker_argv` from both for the `recommended` and `depth-1` profiles, and requires the argv lists to differ in exactly the declared flags. One extra changed token fails. |
| `unchanged_definitions` | the collector itself | Requires the named top-level definitions to be byte-identical in the frozen and current source. `derive` -- the function that computes every gate -- plus `EXPECTED_IMAGE`, `CONFIGURATION`, `SOURCE_PATHS` and `DOWNLOADED_MUST_MATCH`. Only `verify` changed, and this proves it. |
| `additive` | the acceptance session runner | Requires the change to be pure insertion: every top-level definition byte-identical except those declared additive, and each of those must reduce back to its frozen text by deleting inserted lines alone. A rewritten or deleted line produces a `replace`/`delete` opcode and fails. |

CI prints one `ACCEPTANCE PENDING` line per entry on every run, naming the file, the change and the
command that retires it. Four new unit tests in `tools/test_fp8_tp2_acceptance_evidence.py` cover the
mechanism: that the declared drift is proved and reported, that removing any declaration fails, that
a declaration cannot hide a second change, and that the additive proof rejects a rewritten line.

This is a mechanism, not a loophole: an entry can only be retired by a fresh acceptance session, the
packet's own gates are untouched, and nothing about the recorded result changed.

## The headroom receipts (so the next acceptance run proves the margin)

With no swap allowance the entire safety story is anonymous memory against the 12 GiB ceiling. A
cgroup with nothing left to reclaim OOM-kills inside the container and the server is dead at load.
Two cards have now been measured four times at 8.94-8.99 GiB anon with `oom_kill` 0 -- three through
the helper and, since the 20:08 acceptance attempt, once from the shipped launcher's own bytes, with
`anon_headroom_bytes` **3,230,273,536 (3.01 GiB)**. **One card has
not**: `B70_CPU_EMBED=1` puts 2.368 GiB of embeddings permanently in host memory and the
`no-quantization` profile builds an FP16 draft-head copy that has never been weighed, so the estimate
is 8.3-8.8 GiB anon and 3.2-3.7 GiB of headroom -- arithmetic, close enough to the cap that
arithmetic is not good enough.

So the acceptance runners now leave a receipt instead of an argument:

* `run-20260918-fp8-onecard-r312d-campaign.py` gained `cgroup_memory()`, called **per profile** just
  before the stop (the counters die with the container), recording into `results.json` under
  `cgroup_memory`: `memory.events` in full plus `oom_kill`/`oom`/`max`, `memory.peak`,
  `memory.current`, `memory.max`, `memory.swap.max`/`peak`, and from `memory.stat` the `anon`,
  `file`, `file_dirty`, `pswpout`, `pswpin` and `pgscan_direct` -- with `anon_headroom_bytes` and a
  `passed` flag that is `oom_kill == 0`. Each profile is read separately because `no-quantization`
  is the one carrying the unweighed FP16 copy. The per-profile line also goes to the campaign log.
* `run-fp8-tp2-acceptance-session.py` gained the same function and one line in `main` that dumps
  `cgroup-memory.json` just before the graceful stop. Recorded, not gated -- the acceptance gates are
  unchanged, which is what the `additive` proof checks.

Read `memory.events max` going **up** as the mechanism working, not as a problem: 2,005 with a swap
allowance, 12,646 / 12,964 / **16,117** without one, and 11,198 on the acceptance attempt (lower
because the model had just been hash-verified, so there was less to fault back in). The cgroup still
hits its ceiling constantly while streaming a 29 GB file; it now reclaims clean file cache every time
instead of spending swap. `oom_kill` is the number that must stay 0, and it has, four times.

## The helper is superseded

`scripts/apply-container-noswap.sh` no longer has to be armed beside every start -- its header now
says so at the top. It is kept, not deleted, for two jobs it still does: applying or checking the
setting on a container started from older bytes (the evidence packets carry the previous
`--memory-swap 16g` launcher until the acceptance runs below re-freeze them), and re-running the same
experiment with a different cap via `--memory`. Run beside a current start it is a harmless no-op: it
finds the container already at `memory.swap.max=0`.

## CI, run in full locally

Every step of `.github/workflows/guides.yml` in order, plus
`validate-repro-guides.py --write-package-catalog`: **all green.** Baseline was taken first on the
unmodified tree, so the green is a comparison and not a hope. `collect-fp8-tp2-acceptance-evidence.py`
passes and prints the three `ACCEPTANCE PENDING` lines.

Run in full again after the 2026-09-19 acceptance attempt was written up: **still all green, and
still printing all three `ACCEPTANCE PENDING` lines**, which is the correct state -- that attempt
retired nothing. Note that the guides step runs the collector in `verify` mode, which reads the
qualified container out of the packet's own `evidence.tar.gz` rather than from `QUALIFIED_CONTAINER`,
so the environment variable that the attempt needed matters only when *collecting* a packet, never in
CI.

## What is still owed, on a GPU

In the order they should be done. None of them is urgent and none should be a restart made for its
own sake -- rules 1 and 2 of the lane still apply, and the service is up and correct.

**GPU run 1 -- two-card acceptance on the new launcher.** Retires two of the three drift entries and
re-freezes the packet CI gates. **Attempted once, 2026-09-19 20:08-20:14 EDT. The session was clean
and the packet still could not be frozen** -- see the section below for why and for the one-line fix.

```
QUALIFIED_CONTAINER=/mnt/fast-ai/bench-results/fp8-comm2-20260917/tp2-ag-mtp5/container-final.json \
python3 experiments/qwen38-27b-b70/scripts/run-fp8-tp2-acceptance-session.py \
    --commit <the pushed commit of this change> \
    --out /mnt/fast-ai/bench-results/fp8-tp2-acceptance-noswap-<date>
QUALIFIED_CONTAINER=/mnt/fast-ai/bench-results/fp8-comm2-20260917/tp2-ag-mtp5/container-final.json \
python3 experiments/qwen38-27b-b70/scripts/collect-fp8-tp2-acceptance-evidence.py \
    --raw /mnt/fast-ai/bench-results/fp8-tp2-acceptance-noswap-<date> \
    --out experiments/qwen38-27b-b70/data/<date>-fp8-two-card-noswap
```

**`QUALIFIED_CONTAINER` is not optional and the command above was missing it.** Both the session
runner and the collector default it to the September 16 review campaign's depth-5 server, which
predates the allgather overlay and therefore does not carry `B70_ALLGATHER_ALLREDUCE=1`. The current
recipe does. The qualified receipt for the current recipe is the comm-2 allgather server, which is
what the September 17 packet was frozen against (`reference_inspect` inside its `evidence.tar.gz`
reads `/mnt/fast-ai/bench-results/fp8-comm2-20260917/tp2-ag-mtp5/container-final.json`). It must be
set on **both** commands: on the session, because the session writes `runtime-comparison.json` and a
gate reads it; on the collector, because the collector copies the receipt into the packet.

Then repoint `DEFAULT` in the collector at the new packet and delete `source-drift.json` from the old
one (the old packet keeps its own frozen truth; it is simply no longer the current recipe).
Roughly **35-45 minutes**: an anonymous source download, a model verify, an image pull by digest, one
server start (~2.5 min), the strict suite, six practical requests, one graceful stop and two health
probes. It needs the commit to be **pushed** first -- the session downloads the repository from
codeload at that sha. Refreshes: the two-card acceptance packet, and with it the `launcher_sha256`
the two-card LocalMaxxing attestation and queue payload should then be rebuilt from
(`build-fp8-tp2-allgather-localmaxxing.py`, CPU-only, run *after* this).
**Also check:** `runtime-comparison.json` will record `host_memory_plus_swap_bytes` as
`[12884901888, 17179869184]`, because the right-hand number is the **qualified reference container's**
`HostConfig.MemorySwap`, frozen when that server ran on 2026-09-17 with the old `--memory-swap 16g`
launcher. It can never become `12884901888` and a run that produced `[12884901888, 12884901888]`
would mean the reference had been re-measured, which is not something that happens. That pair is
**recorded, not gated** -- the `runtime_matches_qualified_depth5` gate compares image, arguments and
environment, none of which the no-swap edit changed -- so the mismatch is expected and is not a
failure.

### GPU run 1, attempt 1 (2026-09-19 20:08-20:14 EDT) -- the session was clean and the packet still cannot be frozen

Run as prescribed against commit `fc48856e6`, out
`/mnt/fast-ai/bench-results/fp8-tp2-acceptance-noswap-20260919`, rc 0, with
`scripts/measure-swap-during-start.sh` beside it. Receipts copied into
[`../data/2026-09-19-fp8-tp2-acceptance-noswap-attempt/`](../data/2026-09-19-fp8-tp2-acceptance-noswap-attempt/),
which reads each one.

**Eleven of the twelve gates pass. One does not, and it has nothing to do with the launcher edit.**

| Gate | |
| --- | --- |
| `strict_12_no_mtp_reference_outputs_exact` | **pass** -- 12/12 complete token arrays exact |
| `strict_natural_quality_gate` | pass |
| `strict_cache_zero` | pass |
| `strict_canaries` | pass |
| `practical_six_pass` | **pass** -- six requests, three tasks x two repeats |
| `practical_cache_zero` | pass |
| `practical_token_repeat_exact` | pass -- both repeats identical in text and token ids |
| `runtime_matches_qualified_depth5` | **FAIL** |
| `owned_clean_stop` | pass |
| `public_source_bytes` | pass -- anonymous download of `fc48856e6023bbc603a05111febb980e90bf6ddc`, archive `7d10f9f0ed5b12bf6fbba40d89dc2764516765fb596e46a2ff4263dca9e51683` |
| `post_stop_absent` | pass |
| `pre_post_health` | pass -- preflight and postflight rc 0, `gpu_faults: []` |

Strict decode **89.867 tok/s** against the same-image no-MTP reference's 33.035, a 2.720x speedup.
Practical HTTP TTFT 124-150 ms across the six. Ready 151 s after the start command (00:10:08.65Z ->
00:12:39.58Z); `Loading weights took 9.06 seconds` for the first shard set. Every stage rc 0.

The failing gate is a single sub-condition. Taking it apart against the *correct* reference, the
comm-2 allgather container:

* `actual['Image'] == qualified['Image'] == EXPECTED_IMAGE` -- **true**
* the vLLM command line, with the model alias normalised -- **identical**
* `sorted(Config.Env)` on both containers -- **identical**, including `B70_ALLGATHER_ALLREDUCE=1`
* `num_speculative_tokens == 5` -- **true**
* `not runtime['environment_differences']` -- **false**

Only the last one fails, and it fails on a file the *session* wrote, not on anything the collector
can recompute: the session runner compared its container against its own default reference, the
September 16 depth-5 server, and recorded
`environment_differences: {"B70_ALLGATHER_ALLREDUCE": ["1", null]}`. The server under test is right;
the yardstick it was measured against is the wrong one. Setting `QUALIFIED_CONTAINER` on the
collector alone does not help -- it fixes `reference/qualified/container-inspect.json`, and the three
direct comparisons above then pass, but the gate also reads the session's own
`runtime-comparison.json`, which is already written.

**So the only honest remedy is another session, with `QUALIFIED_CONTAINER` set on the session
command.** Editing the raw session's `runtime-comparison.json` would be forging a receipt, and
re-freezing the packet from a summary with a failed gate is what the collector's
`assert summary['passed']` exists to prevent. Nothing was worked around:

* **No packet was written.** `experiments/qwen38-27b-b70/data/2026-09-19-fp8-two-card-noswap` does
  not exist; the collector raised on `assert summary['passed']` and refused.
* **`DEFAULT` still points at `2026-09-17-fp8-two-card-allgather`.**
* **All three `source-drift.json` entries stay.** CI keeps printing the three `ACCEPTANCE PENDING`
  lines, which is the true state: acceptance on the new launcher is still pending.
* **No package number, attestation or queue payload was regenerated.** Both
  `publish-fp8-tp2-allgather-package.py` and `build-fp8-tp2-allgather-localmaxxing.py` assert
  `summary['passed']` on the packet they are given, so neither can run, and neither should.

For the record, had the packet frozen, the headline would have moved **down**: the featured metric is
the median of the comm-2 fresh server (90.370) and the acceptance replay, so 90.476 tok/s would have
become **90.118** (90.370 / 89.867). The two-card LocalMaxxing value moves the same way. **That is a
0.4 % drop, not an improvement, so no new submission is proposed and the existing approved record
`cmu5qk0kz07zglq01eh1opkhx` remains the public record** -- as it would whatever the next session
measures, unless that session beats 90.476.

**What the session did establish, and it is the part worth keeping.** This was the first no-swap
container started by the shipped launcher's own bytes, with no `apply-container-noswap.sh` armed
beside it, and its `cgroup-memory.json` is the receipt the runner was taught to leave:

| | 17:20 baseline (swap allowed) | starts 1-3 (helper) | **this session (launcher)** |
| --- | ---: | ---: | ---: |
| `memory.swap.max` / `swap.peak` | 4 GiB / 4 GiB | 0 / 0 | **0 / 0** |
| container `pswpout` / `pswpin` | 3.94 GiB / 2.09 GiB | 0 / 0 | **0 / 0** |
| `memory.events` `oom_kill` | 0 | 0 / 0 / 0 | **0** |
| `memory.events` `max` | 2,005 | 12,646 / 12,964 / 16,117 | **11,198** |
| `memory.peak` | 12 GiB (= `max`) | 12 GiB | **12 GiB (= `max`)** |
| `anon` | 6.91 GiB | 8.95 / 8.94 / 8.94 GiB | **8.99 GiB (9,654,628,352 B)** |
| `anon_headroom_bytes` | -- | ~3 GiB | **3.01 GiB (3,230,273,536 B)** |
| `file` / `file_dirty` | 3.88 GB / 0 | 2.70-2.88 GB / 0 | **2.42 GiB / 0** |
| `pgscan_direct` | 2.17 M pages | 5.70 / 5.79 / 6.82 M | **4.84 M pages** |
| host swap-out over the window | 4,514 MiB | 293 / 288 / 275 MiB | **1,106 MiB** |

Four independent readings of the two-card working set now land at 8.95 / 8.94 / 8.94 / **8.99 GiB**,
the fourth taken without the helper in the picture at all. `oom_kill` is 0 for the fourth time and
the ~3 GiB of headroom is confirmed as a property of the workload.

**The one number that moved is host swap-out: 1,106 MiB, against 275-293 MiB on the three validation
starts.** It is not the container -- its `pswpout` is 0 -- and it is not the serving phase: every one
of the 66 samples with swap-out falls between 20:09:41 and 20:12:39, with a 630 MiB peak in a single
0.5 s sample at 20:11:10, and the host swapped nothing once the server was ready. The difference
against the validation starts is what else was running in the window: those followed a quiet resume,
this session did an anonymous codeload download and a full 29 GB model verify before the start, so
host page cache (peak `Cached` 10.48 GiB, minimum `MemAvailable` 3.01 GiB, peak PSI 4.04) pushed other
resident pages out. Worth watching on the next session rather than treated as a regression: the pages
the card's copy engine reads are the container's, and the container swapped nothing. No `xe` fault
lines either side.

**GPU run 2 -- one-card acceptance on the new launcher. The one that matters.** This is the run that
turns the 8.3-8.8 GiB estimate into a reading, for all three profiles including the unweighed FP16
draft-head copy.

```
SERVICE_STATE=<the running two-card service state dir> \
CAMPAIGN_OUT=/mnt/fast-ai/bench-results/fp8-onecard-noswap-<date> \
python3 experiments/qwen38-27b-b70/scripts/run-20260918-fp8-onecard-r312d-campaign.py
```

Roughly **55-70 minutes** (the 2026-09-18 run was 05:02-05:58 UTC): it stops the two-card service,
runs `recommended` / `max-context` / `no-quantization` through the shipped launcher with strict,
ladder, context and quality checks, then restores the two-card service on 18124 and re-checks it
against the comm-2 no-MTP reference. **Read `cgroup_memory` for each profile in `results.json`
first**: `oom_kill` must be 0 and `anon` should land near 8.3-8.8 GiB. If `no-quantization` comes
back thin on headroom, that profile -- not the change -- is what needs revisiting. Refreshes: the
one-card package numbers via `publish-fp8-tp1-r312d-package.py`, and afterwards
`build-fp8-tp1-r312d-localmaxxing.py` for the attestation and queue payload.

**GPU run 3 -- nothing, if 1 and 2 are clean.** There is no third run. Listed only so it is explicit
that the flagship packets in section D are deliberately left frozen and are not waiting on a run.

**Keep the sampler in the loop.** The fault question is not closed by this change. Every start should
still be recorded with `scripts/measure-swap-during-start.sh` beside it, so the next fault, if it
comes, has a swap trace next to it.

## Related

[The container memory cap finding](2026-09-19-container-memory-cap-swap.md) (the mechanism, the three
validation starts, the risks), [the fifth GPU fault](2026-09-19-gpu-fault-service-start.md) (the
fault history this hypothesis belongs to), [the host oomd incident](2026-09-18-host-oomd-incident.md)
(the same mistake with a 4 GiB cap), and the `2026-09-19` rows in [DO-NOT-REPEAT.md](../DO-NOT-REPEAT.md).
