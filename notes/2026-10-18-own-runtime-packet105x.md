# Packet105x: why the split head missed a token

CPU-only investigation, within the requested 60-minute box. The first mismatch
is architecture-tradeoff's 31st generated token: the oracle expects 215495 in
rank0's suffix, but the split emits 440 from rank1's prefix. The first 30 match.

Request reset zeros the private suffix active flag and does not restore it.
Both suffix argmax passes then skip their work, leaving index zero. The merge
sees only suffix row 202240. Retained state hashes confirm the zero flag. The
smoke already had this bug but never needed a suffix winner; across the full
12-prompt oracle, token 215495 is the only suffix winner.

The proposed fix restores the private flag before every suffix submission.
The new CPU gate uses the production argmax/pack/merge and the actual extracted
reset loops. GNU and Intel each pass 21 cases in two fresh processes; the
unfixed negative control fails six cases per run, including a missed NaN.
The failing position's hidden bytes were not retained, so no real head-logit
recomputation is claimed. Device equality and speed remain unmeasured.

[Analysis, exact patch and evidence](../experiments/own-xpu-runtime/stage2/packet105x-mismatch/ANALYSIS.md).
Only the new analysis folder and this requested note were written. No frozen
packet, screen, ops file, GPU, service, sudo or setting changed. CURRENT.md is
left to the coordinator under the task's restricted write scope.

The initial `git pull --rebase` refused existing unstaged work. A fetch confirmed
HEAD and origin/main matched; no stash or unrelated edit was made. The task
uses a focused `git commit --only -- <paths>` followed immediately by push.
