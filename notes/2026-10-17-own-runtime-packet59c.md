# Packet59c: choose draft kernels without rebuilding

Packet59c is ready for the coordinator. It has 30 draft switches and ten
separate fusion switches. The default is packet56. All choices are in one
binary, and changing a selection takes less than a second for the prepared
screens. No GPU work ran in this task.

[Packet](../experiments/own-xpu-runtime/stage2/packet59c-draft-select/README.md) ·
[Four-screen plan and commands](../experiments/own-xpu-runtime/stage2/packet59c-draft-select/WINDOW.md) ·
[CPU closeout](../experiments/own-xpu-runtime/stage2/packet59c-draft-select/CPU-PREPARATION-CLOSEOUT.md)

## Decisions

- Keep packet56's target choices, full target head, target arithmetic, BF16 KV,
  rank placement and 91,392-row draft prefix. Change only draft dispatch and
  the init-time selection parser. Packet59's candidate kernel headers stay
  byte-identical; packet56's old draft calls remain available.
- Give each projection, norm and fusion its own switch. Gate/up remains one
  paired swap, as it is in both parents. Separate attention/FFN/final HC
  switches prevent one HC site hiding another. A fusion requires its new
  producer; turning the fusion off restores the old separate consumer.
- Use the screen tool's existing lineage seal. No shared screen or screen-v2
  file changes are needed. Fast reseal creates a new immutable configuration
  and hardlinks the same binary. It never overwrites an earlier seal.
- Run four disjoint groups: attention; HC schedules/fusions; experts/route;
  norms and embedding/hidden merge. Together they cover every switch. They
  isolate winning and losing groups; four observations cannot identify all
  forty effects and their interactions. Keep production for losing or
  unresolved groups. A combined winner still needs its own measurement.
- Accept only exact screen outputs. Device determinism and a full model chain
  remain separate gates. No speed or quality promotion follows from CPU tests.

## What the source says

Packet59 lost about 1.01% throughput and added 0.410 ms to the hit cycle against
the second packet56 control. Its earlier 0.38 ms saving was a projection.
The acceptance median stayed the same, but the mean fell slightly: two fewer
accepted proposals across the twelve prompts.

Split32 adds an attention launch while these contexts are short. HC gate/mix
adds a barrier. Fixed256 norms use nine barriers, including their initial
store barrier, and only one or four workgroups. Fused tails put extra work on
the lane finishing the reduction. The draft follows rank1's target half, so
cache state and register pressure can differ from an isolated operator test.
The source strides are multiples of 16 bytes; there is no demonstrated
unaligned-load explanation. These are suspects for the screens, not measured
kernel costs. [Source diagnosis and bound screen numbers](../experiments/own-xpu-runtime/stage2/packet59c-draft-select/SOURCE-DIAGNOSIS.md).

## Checks

Both host and device builds pass; the device binary was compiled only.
Each of 46 choice sets passes two fresh small CPU runs. All 96 target layer
fixtures and 24 target tokens match packet56 in every run. Default draft
proposals match packet56; all-on proposals match packet59. Production-width
route, split32, dense and fusion checks also repeat exactly. Fourteen parser
and selection tests pass, including all profiles and invalid fusion pairs.
The 132 inherited target files and 33 shared compiler inputs are unchanged.

The default seal and all four screen seals pass the unchanged screen tool's
CPU-only plan check. Prepared-profile reseals take 0.86–0.87 seconds. A new
qgate+route combination, including two fresh CPU runs, takes 3.40 seconds.
Overwrite refusal and identical binary hashes/inodes are checked. These
checks do not establish GPU speed or full-model device quality.

The build occupies 125.48 MB. Two 1.62 MB QSA output files are deliberately
retained as raw bytes from separate runs; the packet README records their
consumers, hashes and restoration. No parent evidence was deleted. The first
configuration's missing copied include and the first seal's source-map
bookkeeping error were fixed before sealing; neither reached a device.

## Workspace handling

The first command was `git pull --rebase`. Git refused because other jobs had
staged and unstaged changes. Those changes were preserved, without stashing
or resetting them. A fetch showed no incoming commits at that point; other
jobs subsequently committed on the shared main. This task changes only its
new packet and this requested note. CURRENT.md and other packets are untouched;
no live device state changed. There was no sudo, service, reboot, power,
memory, swap or page-cache change, and no process belonging to another job
was stopped. CPU commands used nice19, cores 8–15 and 24–31, and Python `-B`.

The next device action belongs to the coordinator: run the four screens in
the linked order, with actual fault review and the same conditions as the
controls. No automatic device runner or publication was started here.
