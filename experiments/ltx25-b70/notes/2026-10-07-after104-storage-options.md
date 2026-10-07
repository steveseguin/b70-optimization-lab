# Storage options after the104 comparison

Original metadata-only planning, October7 (superseded by the completed operation below).104 completed all71 requests and64 capture
requests according to the coordinator and remains retained idle. Its independent
postcompletion proof is being completed by the coordinator. This audit read
small proof/plan JSON and statted only exact archive paths named in those
receipts. **No tensor archive was content-read or rehashed, and nothing was
retired.** Recorded equal hashes identify candidates; fresh verification is
still required before any removal.104 remains protected until a necessary
controlled application stop, not a stop performed merely to obtain cleanup.

The practical next allowance is5GiB, not7GiB. Consolidate stopped101c/102 first,
then consider20 duplicates from104 after its proof and next necessary reload
stop. That avoids reopening103's already-retired proof set and preserves all
104 native repeats plus its original control block.

## Bounded inventory and estimated reclaim

All counted archives are regular nlink1 files of74,621,016 logical bytes. Counts
exclude unscored fills/setup captures, previews, logs, metadata and failed runs.
Allocated-byte values below come from current `st_blocks *512`; they are not a
guarantee against concurrent writes or shared filesystem extents.

| Completed lane | Present scored archives | Distinct recorded full-archive SHA256s | Existing proof availability |
| --- | ---: | ---: | --- |
|101c, W1 three-fixture qualification |19 |3 |All scored raw paths present; recorded clean stop |
|102, W2 three-fixture qualification |19 |3 |All scored raw paths present; controlled-stop receipt present |
|103, ten-fixture plus continuity |40 |10 |30 continuity archives already absent; restoration required for full replay |
|104, ten-fixture client comparison |50 |10 |All scored raw paths present; application still retained |

The same ten fixture hash values recur across103 and104;101c/102 use the same
three values for boat, marble and bird. This supports byte-duplicate screening,
not an inference that their runtime identities, measurements or evidence classes
are interchangeable.

At the bounded filesystem read, available space was56,309,506,048bytes
(52.442314GiB). Recheck before committing to any new writes.

| Proposed exact subset | Count | Current allocated bytes | GiB |
| --- | ---: | ---: | ---: |
|101c: retain native-p1 for each of3 fixtures; retire other scored duplicates |16 |1,194,061,824 |1.112057 |
|102: same per-fixture native-p1 policy |16 |1,194,045,440 |1.112041 |
|104 after stop: candidate04–13 and timed-fast04–13 only |20 |1,492,557,824 |1.390053 |
|Recommended combined subset |52 |3,880,665,088 |3.614151 |
|Alternative stopped103 subset: native-p2 for10 fixtures and candidate04–13 |20 |1,492,512,768 |1.390011 |

The combined recommended subset would bring the illustrative available space to
56.056465GiB. A50GiB reserve plus5GiB runtime allowance and384MiB source-copy
allowance leaves about0.681465GiB. It does **not** admit7GiB plus source. The
32 older-run duplicates alone bring available space to54.666412GiB, which still
fails the5GiB runtime allowance even before a source copy. These are conditional
figures; the fresh destination-filesystem admission remains authoritative.

## Exact candidate and anchor names

Every name below denotes only
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/output/validation/NAME/tensors.safetensors`.
No containing directory is eligible for removal.

For101c, retain `resolution-ref101c-20261007-native-p1-{boat,marble,bird}`.
Candidate duplicates are native-p2 for the same three fixtures,
`resolution-ref101c-20261007-candidate-check-03` through`-05`, and
`resolution-ref101c-20261007-timed-03` through`-12` (16 files total). Each maps
by its verified emitted fixture to the retained native-p1 archive, not by the
submitted prompt's current fixture, because the pipeline emits an earlier job.

For102, retain `resolution-w2-20261007-native-p1-{boat,marble,bird}`.
Candidates are native-p2 for those three fixtures,
`resolution-w2-20261007-candidate-check-04` through`-06`, and
`resolution-w2-20261007-timed-04` through`-13` (16 total). Preserve all other
paths, including the captures/fills excluded from exact scored receipts.

For104, retain all20 `resolution-client-20261007-native-p{1,2}-FIXTURE`
archives and all10 `resolution-client-20261007-timed-04` through`-13`
control archives. After stopped proof, the proposed20 candidates are
`resolution-client-20261007-candidate-check-04` through`-13` and
`resolution-client-20261007-timed-fast-04` through`-13`. Map each directly to
its same-fixture retained control archive. This preserves the measured fast
block's request histories, timestamps, client-policy receipts and tensor hashes;
its full original-path verifier would require restoring its raw copies later.

**Protect every existing103 restoration anchor:**
`resolution-full-20261007-timed-04` through`-13`. The existing30-file restore
map already depends on them. Do not replace these anchors with hardlinks,
repoint the old map, or introduce a chain of mutually retired restoration
sources. Keeping per-run local anchors also avoids making all historical proof
restoration depend on one cross-run directory, although none is an independent
backup on this same filesystem.

## Proof and operational requirements

For101c/102, first rerun each unchanged sealed native/candidate/timed verifier
against its own complete tree and exact source identity. Then construct a
small fixed-path ledger containing successful proof hashes, stopped process
identity, candidate and keeper full-file SHA/size/stat/nlink, per-tensor hashes,
fixture and prompt/execution associations. Recheck whole bytes, not just the
stored JSON hash or tensor payload equality. A changed archive/header or missing
proof excludes that candidate. Preserve all failed101/101b and upstream99
research artifacts; they are outside this proposal.

For104, finish the existing postcompletion proof before a new heavy hash pass.
Its application may remain idle during readonly planning, but apply must await
the coordinator's actual controlled-stop receipt and PID absence. Preserve the
complete native/candidate/control/fast proof before retiring any of these paths.
No new endpoint call, device probe or server stop belongs in a retirement helper.

Use the same narrow safeguards as the reviewed103 operation: concrete ledger
review, exact-file unlink, immediate keeper/stat rechecks, exclusive fsynced
restore map and per-file intent/completion records, no automatic retry. Restore
by exclusive ordinary copies with hash verification and file/directory fsync;
never hardlink or overwrite. Mark every affected dataset “verified before
retirement; restore raw paths for unchanged full replay.” No symlink, missing-file
exception, proof bypass or new verifier claim is justified by this plan.

## If104 must stay live: the103 alternative costs a restoration cycle

The stopped103 native-p2 plus candidate subset above would reclaim another
1.390011GiB while retaining its native-p1 originals and existing timed anchors.
However,103 already lacks30 continuity archives. Its successful stored receipt
is historical evidence, not a currently replayable full proof. The existing
restore consumes about2.085GiB plus overhead before any new full verification.
Retiring the32 older-run duplicates first creates room for that temporary write
above50GiB. A new fixed consolidation ledger must then verify all restored103
paths and retire50 files: the30 restored continuity copies plus20 new duplicates.
The net additional gain is only20 files, not50.

Do not reuse the old apply plan after restoration: original inode/ctime records
will differ. Preserve the old plan/receipt and create a linked new exact ledger;
both maps keep the same timed04–13 anchors. The original helper's restore also
requires all30 destinations absent; partial failures need explicit reviewed
recovery. This extra copy/hash cycle is why the104 subset after its already-needed
reload is preferable. Do not silently waive the50GiB floor to restore proof.

## Evidence pointers

The inventory uses `data/resume-20261007/resolution101c-closeout/`,
`resolution102-closeout/`, `resolution103-closeout/` and the exact104 run
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-client-compare-104-two-way-w2-b1-p1-dxpu2-s640x384/`.
The three receipt names are `same-size-native-references.json`,
`same-size-candidate-check.json`, and`same-size-timed.json`;104 additionally has
`same-size-timed-fast.json`. Its control receipt is **same-size-timed.json**,
not a nonexistent `same-size-timed-control.json`.

Recorded receipt hashes at this audit:

| Lane | Native receipt SHA256 | Timed receipt SHA256 |
| --- | --- | --- |
|101c |`bbe9d4c2b447c127b44268ccb6b121a19f194fd6c36a644372ce1188fb30120c` |`a3804cb63327f3a8181b5f373870990f67258b27292e009773a4509a7538cc27` |
|102 |`d3c2abee55e1893832de16e21f22fae3fc98b3a9b46a139ea89490b7973a066c` |`c147121f0ba71c0076a622dfb138dcb67e33d2b6ba2f4c93bb3469843229b572` |
|103 |`736704207429540b36153dd988d8c5882b6b833902f41fc1ccb4634c8b91f0f7` |`e697d042a32640c4eea2c98ef428063309b14f1444f8c9b2765e23ea6b3ad0e9` |
|104 |`57d6d1c0b4d897a181d1c9336b6e11429bc63ef00841c2ab7eada5495095c59f` |`cfeaec2c0559d07b6bcb2d65bc9470bcf2690e514d25ed0e7b741611f1c51b5c` |

104 fast receipt SHA256:
`a90217927526c928e0d63ecb253e3414bb2e899be67471bf26c255641763b853`.
Existing103 protection/restore map:
`data/resume-20261007/resolution103-retirement-plan.json`, with completed
`resolution103-retirement-applied.json` and adjacent intent/events. This audit
creates no helper, deletion plan approval, new proof, or cleanup operation.

## Completed retirement for105 admission

After104 stopped cleanly for its necessary105 reload, the reviewed helper
reconstructed all three full sealed proofs twice: once for the concrete plan
and again immediately before apply. All52 exact whole-file duplicates were
retired, reclaiming3,880,665,088 allocated bytes (3.614151GiB). Sixteen direct
keepers remain, along with all103 restoration anchors. No103 path was changed.
Fresh storage admission after the105 build passed with55.940208GiB available
for the5GiB allowance above50GiB reserve.

[Plan](../data/resume-20261007/post104-retirement-plan.json),
[completed receipt](../data/resume-20261007/post104-retirement-applied.json),
[reviewed helper and restoration procedure](../recovery/20261007-post104-retirement/README.md).
The affected101c/102/104 full verifiers now require restoring the mapped ordinary
copies first. Existing successful proof receipts describe the pre-retirement
state; keeper copies on this same filesystem are not independent backups.
