# Packet71b: repaired packaging and remaining cheap two-row operators

Prepared on steve-b70s, October 17, CPU only. The new packet is a copy of
packet71. Existing packet trees, shared screens, queues, live jobs and host
settings were left untouched. No GPU, service, sudo, process kill or CPU model
run was used. Compilers ran sequentially at nice19, cores 8–15/24–31, OMP2,
with stdin `/dev/null` and an 8 GiB address-space limit.

The requested initial `git pull --rebase` refused a live coordinator's unstaged
ops log. `git fetch origin main` confirmed `0 0` ahead/behind; no stash or edit
of that log. Other workers' later packet73 changes remain outside this commit.

Packet71 smoke-B failed before ranks launched because `suite` imported `storage`,
which read the absent `chain-registration.json`. Its plan never imported that
code. The new screen-only storage module imports without a chain registration
and explicitly refuses chain storage admission. The worker and placement check
also needed the new directory name so the candidate actually enables depth two.

Plans now import the real worker, deferred `pipeline`/`suite`/`storage`, placement
memory gate and packet49 checker in the same closed library environment and lane
mask used for launch. The import audit rejects device opens, child processes,
network connects and filesystem writes; source and read-dependency hashes are
retained. The queue's existing plan mechanism reaches this check through
`run_job.py --plan`. Controls also verify the private wrapper seal. A regression
test reproduces the frozen packet71 failure, and **eleven** import/wrapper tests
pass on the repair.

The remaining operators use production-derived M2:

- HC attention and FFN gates keep p60's gate-plus-four-stream-mix geometry,
  vector weight/input loads, independent ordered sums and BF16 gate boundary.
- Router keeps the production standalone F32 split-four geometry, four global
  partials per output, adjacent reduction and BF16 write. Its shared-up epilogue
  prevents the old small-FFN tuple; an unexpected tuple refuses explicitly.
- Route keeps the selected four-pass exp32/rank4 algorithm. Rows retain separate
  maxima, exponentials, rounded probabilities, rank accumulators and outputs.

GNU and Intel each pass **2,728 byte comparisons**. All four expected/actual
streams hash to `c160a10d2f3c22e3ac00852b50da8cbe1ede60db0f156079d3eefab6d663ceb3`.
The new tests cover router partials and output, route scratch/output/control
bytes at every pass, ties, invalid input, different row routes and independently
inactive/failed rows. Existing dense/expert and HC mixture gates remain included.
Metadata admits all 48 sites for each new class. Host and device builds pass;
the build is about 95 MiB. No CPU model or transaction suite was rerun; copied
packet71 transaction receipts remain inherited evidence only.

The first device compile found a duplicate capture guard through the checked
source mirror; an explicit include guard fixes it. The first seal plan rejected
external oracle-result symlinks in the generic repository source map. Those
stay under the unchanged packet49 validator and audited data hashes; the path
gate was not weakened. Both failed attempts are retained.

Both M2 and all-M1 views are sealed. Five direct plans pass. The four proposed
B jobs—smoke, control, candidate, control repeat—also pass `lanequeue.py plan`
using a temporary queue directory. No `queue-*.txt` was edited. Expected times
are about **3/4/4/4 minutes**, with **3,600-second** watchdogs; these are planning
estimates. Controls use packet64's sealed `1-draft-hc-batch` view.

The coordinator next runs smoke once, then the matched three quick screens.
Full-model device identity and speed remain pending. Packet68c measured
H(2)/H(1) of 1.74/1.66 on consecutive real positions; the owner's approximately
1.43 best case after these additions leaves little margin. This preparation
makes no speed claim and does not open a long qualification campaign.

[Packet and exact commands](../experiments/own-xpu-runtime/stage2/packet71b-depth2-engine/README.md),
[proposed jobs](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p71b-B.txt),
[CPU closeout](../experiments/own-xpu-runtime/stage2/packet71b-depth2-engine/CPU-PREPARATION-CLOSEOUT.md).
