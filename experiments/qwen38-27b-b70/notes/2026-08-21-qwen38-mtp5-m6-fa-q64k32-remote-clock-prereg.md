# Qwen3.8 MTP5/M6 Q64K32 reference-host clock preregistration

Date: 2026-08-21

Status: **source-only design, blocked and not authorized to launch**. No file
has been transferred to the reference host, no remote stage has been created,
no clock has been changed, and no GPU/operator/model process has been started.
This note does not authorize those actions. The overall campaign-launch and
clock-writer-exclusion switches remain false in both the Python supervisor and
shell driver. Driver environment and active-supervisor ownership gates now
describe implemented CPU-tested source contracts, not launch authorization.

## Bounded question

On reference host `steve-TURIND8-2L2T`, do the stock and exact Q64xK32
MTP5/M6 FlashAttention operators remain correct on both B70s, and does fixing
the active card at 2800 MHz improve their within-card captured timing relative
to the normal 400--2800 MHz range?

This is an operator/clock qualification only. It does not load the 27B model,
start vLLM, authorize a full benchmark, compare no-MTP with MTP, or claim an
endpoint tok/s gain. The 15-GiB host remains unsuitable for the full-model
lane. Absolute timings from this host must not be pooled with local GPU2/3
timings: only within-reference-host stock/candidate and normalized clock-state
effects are admissible.

## Exact operator and fixture identity

The inherited qualifier is
`scripts/qwen38_mtp5_m6_fa_q64k32_operator.py`, SHA-256
`31862ea6a8b9e11a59d643e0d3500179d938261e62b93fb920439c664ce21fbc`;
its base qualifier is SHA-256
`0dd7b945ef35a11ff4d0a1ec085e604920524b996d539e089d89b4a019a5de1f`.
Every fresh worker uses FP16, M6, 12 TP2-local query heads, two local KV heads,
head dimension 256, block size 64, paged causal KV, `is_mix_batch=True`, and
forced chunk decode. It retains 40 graph samples x 100 launches and 32 replay
stability checks per KV length, plus the exact independent CPU oracle and Q/K/V/
sequence-use mutation checks.

Exact fixture seed / fixture SHA / oracle SHA:

| KV | Seed | Fixture SHA-256 | Oracle SHA-256 |
|---:|---:|---|---|
| 128 | 380128 | `0acb368f76405cfab88e47944437d0399bce0866fe9452096d3d5e0a2c9570cd` | `5a9759d1bf2b3eeea8eb4b34ba40e259d7e356285b28f0edcd36bda4a92e2a2e` |
| 1024 | 381024 | `c2ac934353a92c6925a93f75aad559a7c2d2f17c6bd5e4e3b5b2e8b6a2e5324d` | `cb1fff93c03d3b9b266a1fe132cd1d61917613332d1be78b95167f13d8d2aaa8` |
| 1300 | 381300 | `d5044ce346d2b4f97745c42341c85572e205e95d3bee0bc1baa5c84403771c3a` | `9b55fe30569595d19e21222a66bdbe460f8f405174fcab2a4807f3f71af0f4d3` |
| 2048 | 382048 | `d13d102de5b171b6052483b73988537ebfbc70344ea4627372f9445145de39c2` | `715ed4b1b1816431907ae149998d567c4e5a42fcb6018c762bbce75b6b1cd38b` |

## Transfer and stage prerequisite

The remote repo remains `/home/steve/b70-optimization-lab`. A later separately
authorized transfer must place the tracked packet there and create this exact
fresh incoming root:

```text
/home/steve/qwen38-m6-head256-q64k32-remote-transfer-20260821-r1/
  runtime/
  qwen38-m6-head256-q64k32-r2-candidate.graph.sha256
  staged-xpu-commitfix-graphfa-composite-20260820.graph.sha256
  libattn_kernels_xe_2.control.so
```

The remote seal helper does not transfer or build. It requires both canonical
stage roots to be absent. It rejects symlinks, special nodes, extra top-level
files/directories, and any graph other than the exact 20-file package. It
materializes candidate files onto new inodes so the canonical stage never
aliases the mutable incoming tree, removes every write bit, reconstructs the
remote-canonical build-input and stage JSON, then constructs the control stage
with hardlinks for exactly the 19 shared immutable files and a separate exact
control DSO inode. Both final trees are sealed and revalidated. The canonical
roots are:

```text
/home/steve/qwen38-m6-head256-q64k32-attn-override-20260821-r2
/home/steve/staged-xpu-commitfix-graphfa-composite-20260820
```

The candidate graph is SHA-256
`d662dba3927fac706ff221902f536b67178b6875f66604597a1f2fe98a4defc4`.
The control graph is SHA-256
`47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da`.

The three shared runtime files are exact:

- extension `33938cdd2436684dcb76108a4db43e4ab0314406ad537fcd3732a005f7d23739`;
- Python interface `869c79f5f678252c341cfb8fb5cf9ee34f95c3d2debf4d169b759510da432480`;
- stock DSO `3cbd3ed2ff51a477e6746b3e5860c070d093fd2d29b0b7a58e6dd081e9ad1289`.

Only the selected device DSO differs: control
`604f1b328870f2c41ef1d05c4d6016c34d222033d905877b0f9a2ff0c66b2a0c`,
candidate
`01a5b35b5a9c6321b436b137f95403db9e45ce4aabb44257dc7e4f45c84aecf5`.
Candidate workers require the single invariant Q64K32 engagement marker;
controls require none.

## Frozen plan

Exactly two physical devices, ordinal IDs 0 and 1, participate. Their passive
UUID/BDF expectations are source-pinned and must be revalidated in every
same-boot composite receipt; ordinal identity alone is insufficient. Before
changing either card, the driver records and parses both persistent-service
frequency ranges. Both cards then receive a
recorded default 400--2800 MHz experimental precondition, and the inactive card
remains at that default during the active card's blocks.

- global block 1: GPU0 default A-B-B-A;
- global block 2: GPU1 fixed A-B-B-A;
- global block 3: GPU0 fixed A-B-B-A;
- global block 4: GPU1 default A-B-B-A;
- return the active card to experimental default after every block;
- on every ordinary exit, error, INT, TERM, or HUP, attempt and prove restoration
  of **both cards' exact captured pre-run ranges**, which need not have been
  default; a restoration failure forces exit 97.

The driver now backgrounds exactly one supervisor, records its PID and expected
terminal, and makes cleanup non-reentrant. On ordinary exit or INT/TERM/HUP it
forwards the signal, waits a bounded 30 seconds, and accepts only the deep
cleanup-terminal validator proving the worker group absent. If that proof is
missing or malformed, it exits 99 **without beginning clock restoration**.
The shell enters an explicit `spawning` state immediately before the background
launch. A signal in the launch-to-`$!` publication interval is deferred, then
acted on immediately after the PID becomes owned, so restoration cannot race an
unowned supervisor. Repeated cleanup signals cannot recursively enter
restoration. Restoration accumulates failures without shell `errexit`, always
attempts both devices, and always attempts the immutable restoration terminal;
restore failure and terminal failure remain distinct exits 97 and 98. This
state machine has live CPU tests for timeout, interrupt, the critical shell PID
publication interval, a normally exiting leader with a live descendant,
repeated wait timeout, first-device restore failure, and the publication fence.
It does not override the false overall launch or clock-writer gates.

Here A is the stock control and B is Q64K32. Each of the 16 arms is a fresh
one-device process. Outer arm IDs include the clock state; the inherited
qualifier receives its exact `gpu{0,1}-{a1,b1,b2,a2}` inner ID. The remote
operator comparison is the sole authoritative wrapper result: it validates
the original GPU0/GPU1 packets, maps them only in memory to the inherited
GPU2/GPU3 comparator's chronological convention, and records that virtual map.

The outer supervisor writes immutable before-spawn and
spawned receipts, starts the worker in a new process group, imposes a 900-second
hard timeout, sends TERM then KILL if needed, proves group disappearance, and
atomically publishes a terminal packet. Interrupts observed before terminal
publication are recorded and cannot become success. A leader that exits while
descendants remain triggers nonthrowing TERM/KILL group cleanup rather than
merely being labelled invalid. The watched signal set is blocked before
terminal publication; handlers are replaced while blocked, queued signals are
drained into a separate immutable late-signal receipt, and the late handler is
retained through dedicated-supervisor process exit. Receipt failure exits the
supervisor nonzero. Thus the former drain-to-unmask default/ignore window is
removed. A deeply revalidated frozen worker failure is a valid scientific
negative and stops the campaign; timeout and interruption terminals remain
valid cleanup evidence. The restoration terminal independently proves the
clocks and binds the exact contiguous prefix of arms that actually started, so
an intended early stop is not mislabeled as a clock restoration failure. Full
comparison separately requires all 16 success arms and original exit status
zero. No same-root retry is permitted.

The driver binds each arm terminal to a composite effective-clock receipt that
contains both the selected device's raw `xpu-smi config -d N -t 0 -j` object and
an unfiltered raw `xpu-smi discovery -j` object. A strict parser verifies the
source-pinned structural hash, exact two-entry device inventory `{0,1}`, exact
B70 name, both UUID/BDF identities, and selected min/max paths. The passive
inventory now pins schema SHA
`afb4b7fe6d1ea9847559734fae1b73241f18587f036ae3d18376c146fa6eafba`,
device 0 UUID/BDF `00000000-0000-0003-0000-0000e2238086` /
`0000:03:00.0`, and device 1 UUID/BDF
`00000000-0000-00e3-0000-0000e2238086` / `0000:e3:00.0`. These are
same-boot rechecked expectations: every receipt must reproduce them, while
boot ID, ordinal state, device state, and clock ranges remain dynamic. Each
worker must also emit an immutable `/proc/self/maps` sidecar proving the
source-pinned SHA and unique, non-deleted mapping for every required system
Level Zero/SYCL runtime DSO. That mapped runtime inventory is not yet captured,
so copying files still cannot enable launch.

The management binary is fixed to `/usr/bin/xpu-smi`. Its bytes and exact
version output must be source- and driver-pinned, and every query, set, and
restore invocation must use that absolute path (including through `sudo`).
The passive inventory now pins SHA-256
`01c7b83881e99754642b827ba05418d263aed615933e3df35821af7733eb8d83`
and exact CLI/service version `2.0.0.20250225`, build `8389eee7`, Level Zero
`1.28.6`. The driver uses an absolute `/usr/bin/bash` shebang, source-pinned
absolute paths for Git, env, jq, timeout, sudo, hashing, and file utilities,
and clean-env re-exec before audit/compare or any future authorized run. Every
management Python and `xpu-smi` call receives a second `env -i` boundary;
sysman is explicit only for `xpu-smi`. Caller library/device/order/sysman
selectors, Python activation/startup, Bash startup/CD path, and Git
repository/config overrides are rejected. The clean marker is not sufficient:
the child requires the exact eleven-name exported environment, exact values,
canonical working directory and shell level, and no exported Bash functions.
An adversarial forged-marker test covers both an otherwise unknown exported
variable and an imported/exported Bash function.
Every arm has active-device pre/post readbacks; every four-arm block also has
inactive pre/post plus active post readbacks. Comparison binds their immutable
hashes and global chronology. These detect endpoint-persistent range drift,
but cannot exclude a transient service intervention that changes and restores
the range between readbacks. Launch therefore remains blocked until every
competing clock writer (including any `xe-b70-minfreq` service/timer) is
inventoried, frozen inactive for the campaign, durably evidenced, and restored
to its exact pre-run state.

## Decision and interpretation

Each clock state must independently pass the inherited eight-packet Q64K32
operator comparison on devices 0 and 1, including correctness, mutation,
mapping, marker, graph stability, paired confidence intervals, the KV128
regression ceiling, and the 21.844 us/call KV1300 Q64 saving hurdle.

Clock effects are then computed separately for every device, role, and KV
shape from its two fresh-process 40-sample arms per state. The point estimate is
the mean of the two arm medians. A deterministic 10,000-resample hierarchical
bootstrap first resamples the two process arms, then samples within each chosen
arm; the 80 timings are never treated as IID. The packet also reports the
clock-by-policy interaction distribution. The narrow clock gate requires the
KV1300 lower 95% bound to exceed zero for stock and candidate on both devices.
Because each device has only one sequential block per state, hierarchical
resampling cannot remove state-order, thermal, or time drift confounding;
opposite state order across devices reduces but does not eliminate it. A pass
is therefore a DVFS-sensitivity diagnostic only. It is neither a clock-lock
recommendation nor direct endpoint authorization, though it may inform a later
separately preregistered endpoint question after independent evidence.

Do not compare or average the resulting microseconds with local GPU2 evidence.
No-MTP versus MTP is not part of this packet and is not worth the model/runtime
transfer cost on the limited-memory host.

## Artifacts and current blockers

- campaign/supervisor: `scripts/qwen38_mtp5_m6_fa_q64k32_remote_clock_campaign.py`
  (`95c026766a6a51442766be15b7142600cb195ea00ca3590cc73dc394de2a9d31`);
- transfer/seal helper:
  `scripts/prepare-qwen38-m6-head256-q64k32-remote-stage-20260821.sh`
  (`e20b1f09363b3361e5a90fa868f1a8dffced87b482dc1e9ebb016e9d945a4ea8`);
- blocked driver:
  `scripts/run-20260821-qwen38-mtp5-m6-fa-q64k32-remote-clock-abba.sh`
  (`ccd54de8f0125fee8f00846ad7ee06d6b775dab5e98c718ecb77871f6f8cf0d5`,
  mode 0755);
- CPU tests:
  `scripts/test_qwen38_mtp5_m6_fa_q64k32_remote_clock_campaign.py`
  (`253445c6f35b39864eddd8d04b954baccd4fb03d6eb4323907b3f7e7f45721ac`).

Former prerequisites 7, 9, and the numeric/testing portion of 10 are now closed
in source: active-supervisor ownership precedes restoration; cleanup is
nonthrowing and final-fence signals are durable; management uses clean-env
re-exec plus exact paths; and live process/signal/timeout/descendant tests plus
positive, zero, negative, nonconstant percentile, and interaction numeric
fixtures pass. These closures do not imply launch authorization. The frozen
packet passes 41 CPU tests plus Ruff lint/format and shell syntax checks without
importing Torch or touching an XPU.

Missing prerequisites, all mandatory:

1. explicit authorization to transfer the packet, candidate runtime, control
   DSO, and both exact graph manifests;
2. canonical remote control and candidate stages plus newly sealed remote stage
   JSON/build-input hashes;
3. clean remote `main == origin/main` HEAD frozen in source;
4. same-boot recapture of the now-source-pinned UUID/BDF mapping proving exactly
   devices 0 and 1, plus dynamic boot/device-state/range evidence (the reference
   host did not undergo the measuring host's xe recovery);
5. launch-time composite `xpu-smi config` plus unfiltered `discovery`
   revalidation against the pinned schema, two-device identities, field paths,
   binary SHA, and exact version;
6. source-pinned mapped Level Zero/SYCL runtime basenames and SHA-256 values,
   with the driver inventory SHA equal to the Python source-derived inventory;
7. frozen exclusion and exact pre/post restoration of all competing clock
   writers/services/timers; endpoint readbacks alone are insufficient;
8. a final reviewed replacement of the overall literal false campaign/clock
   gates and remaining repo/stage/runtime placeholders only after items 1--7
   are evidenced.

Until every item is satisfied, only CPU/static review is allowed.
