Mixed independent CPU fidelity check:10 reused historical cases +2 fresh contexts

This supersedes the unexecuted12-context preparation in commit9634fb5bf. Its
source and compiled receipt remain untouched. No CPU model has run for either
preparation. The changed wrapper differs only in requiring2 input paths rather
than12; context, batch256, F64 reference arithmetic, F32 KV and output reporting
remain unchanged. It links the same qualified four archives; no library rebuild.

Actual completed GPU generation authority:
  /dev/shm/sc117-gpu-route-seven-plus-twelve-20261028-r1/output
Prepared inputs and complete reuse proofs:
  /dev/shm/sc117-reference-changed-inputs-20261028-r2/inputs.json
Compact authenticated metadata is retained in preparation.json.

Historical reuse requires the ENTIRE prompt+actual newly generated continuation
as identical packed LEi32 bytes, identical score_from/full_rows, complete rows
through the final consumed token, finite top20/argmax validity and exact next
input provenance. Every scored generated token must match historical argmax.
Each historical input/row and binary build metadata is bound to its actual SHA,
committed Git blob and the current snapshot commit. That snapshot is evidence
custody, not an invented original reference-source commit. Original reference
binary71a28e2c... and build-hashes.txt/capture-source-identity are authenticated;
RESULT-F32.md and historical runner provenance remain explicit. Do not infer
unknown historical environment or source identity beyond those records.

Actual classification:10 unchanged cases validate4941 generated-token matches
from historical CPU rows. Two whole changed inputs require new evaluation:
  original suite index2, bug-report-synthesis -> local CPU context0 / case-00
  original suite index11, technical-guide -> local CPU context1 / case-01
These two contexts cover1024 generated-token predictions; no old prefix rows
are substituted for their fresh runs, even before the first changed token.

Root-only launch AFTER all GPU owners drain; no model has been launched here:
  python3 research/pp4-review-2026-10-28/reference-one-row/fresh-changed-cpu/run.py run --inputs /dev/shm/sc117-reference-changed-inputs-20261028-r2/inputs.json --output /dev/shm/sc117-reference-changed-cpu-20261028-r1/model
Optional --preflight-only passed with103033585664 bytes MemAvailable and an
unchanged80GiB floor, exact source/library/model file identity pins. The process
is nice19 cores8–15,8threads, GGML_CPU_EXACT_F64=1, EXACT_KV=f32, no captures or
rounding overrides. One model load,2 fresh sequential contexts. No automatic
retry. No GPU work or service lifecycle is controlled by this helper.

Final receipt schema ownrt.fresh-mixed.cpu-teacherforce.v1 explicitly separates
reused10 references from2 newly computed cases and preserves original suite id /
index plus local context index. If all fresh predictions agree, report
4941 reused +1024 fresh =5965 matched generated positions, NOT12 new CPU runs.
Coverage/lifecycle success and fidelity_all_match are separate. All per-position
argmax/top20 rows, next-token provenance and margins are retained; each final
unconsumed-next row is retained but excluded from the generated-token denominator.
Mismatches are findings and never change runtime inputs or trigger a retry.

Three bounded tests passed: actual wrapper lifecycle through mocked llama APIs,
whole-input token and scoring-boundary mutation rejection, incomplete historical
row refusal, and actual10/2 coverage/mapping. They do not claim model arithmetic.
An initial preparation command used the GPU parent instead of output child and
refused before inputs/model; preparation-refusal-r1.json retains exact tool
provenance. Corrected preparation used a new exclusive output directory.
