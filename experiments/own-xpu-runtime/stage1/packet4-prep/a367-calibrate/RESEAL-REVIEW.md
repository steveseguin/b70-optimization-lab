# October 16 A367 dependency decisions

Coordinator approval of preparation checklist items 1–4 is the authority for
these changes. This is CPU preparation, not owner approval of a lower memory
floor or a device launch. Original evidence under
`data/2026-10-16-flash-next-a367-prep/` remains unchanged, including the failed
historical comparison and old seal audit.

| Input | Decision and reason |
| --- | --- |
| Source path | Only calibration `paths()` uses `/home/steve/src/vllm-flashnext-a367-clean-20261016`. All 2,305 Python hashes and certified source commit stay unchanged. Mock dispatch tests use this path too; shared fixture defaults stay frozen. |
| Historical receipt | Supersede only its calibration admission dependency with separately pinned `model-reconciliation.json`. Validate expected/observed historical hashes, retained observed receipt, publisher revision, both manifest identities, fresh-preparation USB receipt hash, 144 file sizes/digests and zero differences. Keep `historical_payload_receipt.passed=false` in the run audit. The original receipt bytes were not recovered. No old receipt becomes fresh. |
| Fresh USB payload | Mandatory independently, at most one hour old. Bind the exact receipt bytes to the owner-window; require the USB path, publisher identity, verifier/producer hashes, full per-file SHA256/size/digest rows and no differences. Recheck immediately before creating the run. |
| `MEMORY-ADMISSION-REVISION.md` | Repin reviewed bytes `1ab81c32d19187036bbe3f1aa05346c37e7fc16713a394ae1698d95f75867531` in both seals. The appended fixed experimental mmap run is historical evidence, not A367 need. Its 77.079 GB peak and missing VRAM admission cannot lower this floor. No document content, proposal (133,542,784 KiB), default (120,000,000 KiB), reserve or memory setting changes. |
| `stage2/packet1b/reference.py` | Preserve fixture expected hash `4e36c7c7890e7df428c7e1d10dc1b536d26ba18b8b7066c07f9dbdea2ff4909b`. Commit `3ebd0d2b1504648be50c122fb7899005d999be4a` changes GDN's SiLU gate to sigmoid; observed hash `e1fb0aa0107c4c3e0e55803b2789ddbb717122194e2a3b00788d73f646a653c8` is NOT accepted as an A367 oracle. |
| `stage2/packet1b/test-receipt.json` | Preserve fixture expected hash `74d14a12cdd289d8e2265fef2831f4a194fff5f298746fc3e5d2dbdb5345845b`. Observed `04b154e762c2ae497d79241478f5cdc40d0d473fd00ed9116570c5abc772de88` adds a synthetic gate test (37 to 38 tests) and changes GDN output hashes; it supplies no A367 qualification. |
| Calibration dependency set | Explicit `calibration_repo_pins` includes all 75 patch/bundle members, frozen launch scripts, runtime stage manifest, placement/map/model contract and reconciliation/verifier inputs. It omits fixture adapters, recorder/common/comparator, prompt/oracle, fixture schema, tensor contract and the two changed packet1b files. Zero generation uses no extraction worker or reference dispatch. The driver preregistration and both active seals bind this set; exclusions are not inferred at launch. |
| Fixture admission | Default `verify_repo()` still checks original `repo_pins` and refuses the two known fixture mismatches. There is no fixture CLI bypass and no changed reference adoption. Zero mismatches refers to the selected calibration dependency set and shared/calibration seals; dormant fixture drift is separately retained in the audit. |

`verify_environment(..., calibration=True)` validates the reconciliation; ordinary
fixture environment checks retain the original receipt rule. The calibration
seal now also binds the driver seal. Changing any shared code requires resealing
both and obtaining new exact owner approval text. Source/stage/model bytes,
graph, MTP1 and every compute selector remain unchanged; tests compare the
command and literal compute exports with the frozen A367 launcher transform.

The prepared exception proposes **114,000,000 KiB** (about 108.72 GiB), slightly
below the owner's approximately 110 GiB available observation. It is a proposed
numeric admission choice, not a measured safe floor. The default remains
120,000,000 KiB and the 12,000,000 KiB live reserve stays fixed. The pending
approval object is outside the seals to avoid a self-referential hash; it cannot
admit anything until the owner signs its exact post-reseal sentence. Choosing
another number requires a newly generated exact sentence and owner decision,
not a silent edit to an approved object.

No storage repair, payload re-read, native import/launch, device health probe,
service change or owner approval occurs in this reseal. Static loader evidence
is in `data/2026-10-16-flash-next-a367-reseal/loader-audit.json`; this is a
DT_NEEDED/import-path review, not runtime ABI qualification. Native startup's
source guard remains mandatory. Existing protected source/archive/RAID paths
were not accessed. No model benchmark or quality claim follows.

## October 16 device attempts 1-2 and the follow-up reseal

Both attempts on boot `2cba7160` stopped before any worker loaded weights, with
zero GPU fault lines and no surviving owners. Evidence is in
`data/2026-10-16-flash-next-a367-reseal/window-20261016T133433Z/` and
`window-20261016T135036Z/`.

1. Attempt 1 (`flashnext-a367-calibrate-20261016T133433Z`): `VLLM_RPC_BASE_PATH`
   is `<output>/scratch/rpc`, and vLLM appends a 36-character uuid. The
   121-character ipc path exceeded the 107-character Unix socket limit, so the
   API server raised `zmq.error.ZMQError` during engine-client setup.
   **Remedy:** the runbook output name is now `a367-$FN_STAMP` (101 characters),
   and the launcher refuses longer paths before any device step. AF_UNIX and pyzmq
   ipc sockets bind correctly on the raid NTFS mount (tested 13:49 UTC).
2. Attempt 2 (`a367-20261016T135036Z`): the 0.5 s sampler calls `os.getsid` on
   every `/proc` entry. A host process that exited during the scan raised
   `ProcessLookupError` (ESRCH). The sampler caught only `FileNotFoundError`,
   so it latched a failure and sent SIGINT to the API server while that server
   was still in `torch.xpu` device enumeration.
   **Remedy:** skip vanished processes, as `window_driver.owned_session_gone`
   already does. Missing rank samples still fail the plateau gate.

Two regression tests were added. Floors, watchdog, reserve, the command and
the environment are unchanged. The seal hash changes, so the memory-floor
exception needs the owner's new hash-bound approval.

## Attempt 3 and the scratch relocation

Attempt 3 (`a367-20261016T142901Z`, seal `0ad3948b`) launched at 14:34:26 UTC.
All four ranks loaded the model in about 673 s, at 29.4-29.6 GiB each.
MemAvailable fell from 113.2 GiB to a minimum of 16.16 GiB, 4.95 GB above the live
reserve. During the first graph-capture warmup, rank 0 raised `FileNotFoundError`
on `<output>/scratch/triton/<hash>/_qsa_merge_splitk_kernel.llir`. The four ranks
compile the same Triton kernels into one shared cache, and Triton publishes
cache files by `os.replace`. On the ntfs-3g output mount, rename-over is not
atomic, so a reader can briefly see the target missing. The engine
failed initialization and the server exited, with zero GPU fault lines and no
surviving owners. Evidence is in `window-20261016T142901Z/`.

**Remedy.** `command_and_environment` now rewrites every
`<output>/scratch/...` environment path to a short local ext4 directory,
`/home/steve/.cache/a367-scratch/<run>/...`. That covers the hf, vllm,
inductor, triton and xdg caches, `TMPDIR` and `VLLM_RPC_BASE_PATH`.
`TORCH_TRACE`, logs, samples and receipts stay on the raid output. The
launcher:

- requires 4 GiB free on the local scratch filesystem;
- requires that the run's scratch directory does not already exist;
- checks the actual rpc path length;
- removes the scratch directory under the same owner-gone condition as before.

Two tests cover the new paths. Floors, watchdog, reserve, the command and every
non-scratch environment value are unchanged. The seal changes again and needs
a new owner approval.

**Loading budget raised to 1800 s.** `load_and_plateau_seconds` was 1200 s
in the preregistration and in the launcher. Attempt 3 took 731 s to load and
reached graph capture at 895 s, compiling from a cold per-run Triton cache.
Running out of budget during capture would send SIGINT to a four-card server
mid-capture. The budget remains a bound on a hung startup. No measurement
changes. The preregistration hash therefore changes too, and the owner sentence
binds both hashes.

