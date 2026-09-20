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
Two cards have been measured three times at 8.94-8.95 GiB anon with `oom_kill` 0. **One card has
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
allowance, 12,646 / 12,964 / **16,117** without one. The cgroup still hits its ceiling constantly
while streaming a 29 GB file; it now reclaims clean file cache every time instead of spending swap.
`oom_kill` is the number that must stay 0.

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

## What is still owed, on a GPU

In the order they should be done. None of them is urgent and none should be a restart made for its
own sake -- rules 1 and 2 of the lane still apply, and the service is up and correct.

**GPU run 1 -- two-card acceptance on the new launcher.** Retires two of the three drift entries and
re-freezes the packet CI gates.

```
python3 experiments/qwen38-27b-b70/scripts/run-fp8-tp2-acceptance-session.py \
    --commit <the pushed commit of this change> \
    --out /mnt/fast-ai/bench-results/fp8-tp2-acceptance-noswap-<date>
python3 experiments/qwen38-27b-b70/scripts/collect-fp8-tp2-acceptance-evidence.py \
    --raw /mnt/fast-ai/bench-results/fp8-tp2-acceptance-noswap-<date> \
    --out experiments/qwen38-27b-b70/data/<date>-fp8-two-card-noswap
```

Then repoint `DEFAULT` in the collector at the new packet and delete `source-drift.json` from the old
one (the old packet keeps its own frozen truth; it is simply no longer the current recipe).
Roughly **35-45 minutes**: an anonymous source download, a model verify, an image pull by digest, one
server start (~2.5 min), the strict suite, six practical requests, one graceful stop and two health
probes. It needs the commit to be **pushed** first -- the session downloads the repository from
codeload at that sha. Refreshes: the two-card acceptance packet, and with it the `launcher_sha256`
the two-card LocalMaxxing attestation and queue payload should then be rebuilt from
(`build-fp8-tp2-allgather-localmaxxing.py`, CPU-only, run *after* this).
**Also check:** `runtime-comparison.json` now records `host_memory_plus_swap_bytes` as
`[12884901888, 17179869184]` against the September 16 qualified container. That pair is **recorded,
not gated** -- the `runtime_matches_qualified_depth5` gate compares image, arguments and environment,
none of which changed -- so it is expected and not a failure.

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
