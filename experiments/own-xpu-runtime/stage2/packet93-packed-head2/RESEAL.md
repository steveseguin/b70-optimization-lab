# Packet93 restored-tool reseal, October 18

Packet93 originally sealed packet84's temporary submission-tool edit
(`b0a3f28c1c3e212be59315bd8b2d18d69b9fecea433daedf4c8b4659fbc783db`).
Packet84 restored its original in `6470679d0`; the current SHA256 is
`bc7480f11c2e62c30147f4042e254977f9f1dd3be6cb936aa8e090340eee5347`.
Packet84 itself was not edited by this reseal.

The submission tool is a Python consumer-test dependency, absent from the
engine and microbenchmark compiler inputs. The engine build receipt and all
native binaries are unchanged. The micro build receipt refreshes only the
runner, qualification and test source hashes for the new output identity;
all other inputs and artifacts were verified. Per-view build receipts state
that no native rebuild occurred and bind the provenance record. Byte fixture
receipt links, screen seals and the screen-jobs seal were regenerated after
rerunning the Python gates: 80 wrapper tests and 24 packet tests passed.

The original `evidence/micro-B/` is unchanged, verified against
`evidence/micro-B-original-hashes.json`. It measured head-transpose at about
1.032 ms versus 1.416 ms production, ratio 0.729 in both orders; head-plane
did not qualify. These are synthetic kernel diagnostics, not engine speed.
The historical qualification binds the old screen seal and cannot be reused.
The old Python/receipt closure is retained in
`evidence/pre-reseal-6470679d0.tar.gz`; its hash and unchanged binary hashes are
in `evidence/reseal-provenance.json`.

The coordinator's new proposal files, relative to the repository root, are:

- `experiments/own-xpu-runtime/ops/lane-queue/proposed-p93-micro-B2.txt`
- `experiments/own-xpu-runtime/ops/lane-queue/proposed-p93-B-grid-B2.txt`
- `experiments/own-xpu-runtime/ops/lane-queue/proposed-p93-A-confirm-B2.txt`

They run in that order. The fresh micro output is `evidence/micro-B2/` and
does not exist at handoff. Both engine screens require its newly bound
qualification, and A confirmation still requires the exact improving B winner.
The old micro job name must not be requeued. No proposal was installed into a
live queue and no device, service, sudo command or setting change ran here.

Validation uses `final_check.py` and `queue_plan.py`. The latter copies each
new proposal into a temporary queue directory and runs the unchanged queue
planner. Both commands use `nice -n 19 taskset -c 8-15,24-31 python3 -B` with
stdin from `/dev/null`. Results are `evidence/final-check.json`,
`evidence/queue-plans.json` and `evidence/queue-plan-*-B2.log` (plus
`evidence/queue-plan-micro-B2.log`). Plans are CPU evidence only; fresh device
qualification and full engine comparisons remain pending.

The requested `git pull --rebase` refused unrelated dirty work. A fetch found
HEAD and origin/main already equal at `1a9d755c2`; no stash or reset was used.
