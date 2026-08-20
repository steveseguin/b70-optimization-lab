# Page-cache weight corruption on the measuring host: analysis and response

2026-08-20. Trigger: the measuring host's harness rejected a run on a model
SHA256 mismatch. Root cause: the fuseblk/NTFS-3G page cache serves
corrupted bytes for `model-00002-of-00007.safetensors`
(manifest `e4ac4e0b…`, cached read `ac86dfcf…`, `dd iflag=direct` returns
the correct bytes). Sticky across repeated cached reads; not memory
pressure (90 GB free). vLLM loads weights through ordinary reads/mmap, so
affected runs compute quietly wrong numbers instead of failing loudly.

## This host (second host) is unaffected

Store is ext4 on local NVMe (`/dev/nvme1n1p1 → /mnt/fast-ai`), not FUSE.
Full payload re-verified twice on 2026-08-20:

- ordinary cached reads: 8/8 LFS SHA256 + 11/11 git blob IDs match
  `repro/qwen38-27b-autoround-int4-b70/manifests/model.json`;
- O_DIRECT reads via the new verifier: 19/19 match.

No action needed locally.

## Interaction with the two kernel races found today

The page-cache finding does **not** subsume or weaken the two fixed kernel
races; they were measured on this host with synthetic GPU-resident tensors
(weights never cross the host page cache in the sweeps) and have
source-level root causes:

1. oneDNN int4 GEMM prefill band race [129,448] — fixed by determinism pad.
2. `gdn_replayssm_commit_pending` double race — fixed by serial ascending
   shift + queue-ordered cursor kernel (0/4000 after fix, 60/60 bitwise vs
   torch reference).

Conversely, page-cache poisoning is a **weak** explanation for the
margin-free 21/25 pairwise arm divergence as observed:

- Sticky corruption + 90 GB free (no eviction pressure) means every arm in
  a poisoned window loads the **same** wrong bytes. Same weights ⇒ arms
  agree with each other; poisoned cache explains an arm-vs-truth error,
  not arm-vs-arm divergence within a shared cache epoch.
- Pairwise divergence requires the served bytes to *change between arm
  loads* (cache churn across the boundary). Possible, but it must be shown
  per arm, not assumed.
- The decode-time `commit_pending` race fires randomly per call regardless
  of cache state and fits within-window divergence exactly.

Where page-cache poisoning is fully sufficient: explaining absolute
wrongness of any post-poisoning result (including the unexplained
GDN-capture hang after ~02:11) and any fresh-load session. Timeline check
needed: if the margin-free three-arm run predates the corruption onset,
page cache is excluded for that result entirely.

The planned TP1 control remains valuable: it removes oneCCL from the
equation (already weakened as a suspect by this host's 400-collective
cross-process bitwise-stability gate), isolating storage vs runtime.

## The cached-read verification blind spot — now closed

The pre-run identity gate hashed with ordinary cached reads. That check
shares the page cache with the subsequent safetensors/mmap load: **both
see the same bytes**, so "all recorded file identities verified" could
pass while loading corrupted weights. It certified cache-consistent
weights, not manifest-consistent weights.

Shipped fix:

- `repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py` —
  hashes all manifest entries bypassing the page cache: O_DIRECT `preadv`
  on page-aligned buffers, `dd iflag=direct` streaming fallback, and
  **fails closed (exit 2)** when neither bypass works. Emits structured
  JSON evidence (`--json`).
- `experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh`
  — new preflight: when `MODEL_MANIFEST` is set (and
  `VERIFY_MODEL_DIRECT` != 0), verifies the model with cache bypass
  *before* server launch and refuses to start on mismatch or on
  unverifiable stores. Unset `MODEL_MANIFEST` prints a loud warning.
  `VERIFY_MODEL_DIRECT=0` is the explicit opt-out.
- Tested locally: good manifest → exit 0 (19/19 via odirect); corrupted
  expected hash → exit 1; runner syntax checked.

Recommendations for the measuring host:

1. Drop caches or remount, re-verify all seven shards with the direct
   verifier, and prefer a non-FUSE store (ext4/XFS/local NVMe) for
   multi-GB weights under sustained load.
2. Re-run the margin-free A/B on the triple-fix build only *after* the
   store is fixed, with the direct gate enabled, so the next determinism
   claim cannot be storage-assisted either way.
3. Consider `drop_caches` between arms as cheap insurance: each arm then
   loads provably fresh bytes.
4. Re-derive which past results sat inside a poisoned cache epoch before
   citing them; the honest margin-free figure (101.170 all-25) stands only
   if its arms predate the corruption onset AND pass the direct gate on
   re-verification.

## Record withdrawal (evidence summary for the user's decision)

- Leaderboard 101.922: margin-assisted determinism claim plus a setting
  that rewrites tokens — fails the strict determinism and quality gates.
- Honest margin-free 101.170 all-25: pending re-validation under the
  direct-I/O gate and the triple-fix runtime.
- Strict standards require the 101.922 entry to be withdrawn or annotated
  invalid; that decision and the submission key belong to the user.
