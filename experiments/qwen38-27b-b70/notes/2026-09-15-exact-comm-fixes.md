# Exact two-card communication: fixes before retesting on the cards

**Outcome:** the operator's two known bugs are fixed in code and checked on the
CPU. Nothing new has run on a GPU. Two new card tests are ready for the root
agent to run in order; the first decides whether the second may run at all.

## What was wrong and what changed

1. **NaN arithmetic did not match XCCL.** On Native04, when both cards held a
   NaN (`fe02` and `7e03`), the prototype returned `fe02` and XCCL returned
   `7e03`. One element cannot say which rule XCCL follows. A new characterization
   test (`nan-semantics-01`) feeds XCCL every ordered pair of 21 edge values:
   quiet and signaling NaNs of both signs with several payloads, infinities,
   zeros, ±1, ±max and subnormals. It compares XCCL with four candidate
   formulations: FP32 or native half-precision add, each with either card's value
   first. The native library gained an explicit `et_add_mode` entry point; the old
   `et_add` is untouched. That test uses no cross-card memory sharing at all. A
   formulation is chosen only if it matches XCCL on every element on both cards.
2. **A known quality mismatch crashed out like a device failure.** The gate now
   retires shared memory cooperatively on a mutually acknowledged mismatch. It
   closes imports, confirms both sides closed, returns exports, frees memory, shuts
   down the process group, writes a receipt and exits with code 2. The abrupt
   `os._exit(70)` path is kept only for unknown faults. Whether that abrupt exit
   caused the Native04 GPU faults is still unproven.
3. **Launch harness gaps from the host-memory incident.** Both new stages carry the
   five environment variables every qualified FP8 service uses. Before the container
   starts they launch the root host-memory guard (through sudo, baseline measured
   before `docker create`). Guard exit 3 fails the stage and latches the campaign.
   Monitor-loop Docker/journal calls can no longer hang the owner: each has a hard
   deadline and a killed child is never waited on.
4. **Gate coverage.** Every existing test case is kept, and a `nan_matrix` case adds
   NaNs in both positions, both signs, quiet and signaling, with varied payloads
   (16 cases per shape).

Stages 01-04 stay refused. The old campaign root stays closed. The library was
rebuilt for the container's SYCL runtime:
`/mnt/fast-ai/research/exact-tp2-build-20260915-sycl9/libexact_tp2.so`, SHA256
`8ae406395124c84e3b960bf6fb6cb0ce5a52f3dfd0c7c6d2f37ef4068d37a036`. All 70 CPU tests
pass; hashes are in
[cpu-validation-20260915.json](../probes/mtp-exact-tp2-20260914/cpu-validation-20260915.json)
and details in the [probe README](../probes/mtp-exact-tp2-20260914/README.md#stage-05-preparation-2026-09-15).

## Commands for the root agent

Run from `experiments/qwen38-27b-b70/probes/mtp-exact-tp2-20260914`. Each stage is
one-shot: an existing output directory, a campaign `FAULT.json` or another GPU
owner refuses it. There are no retries. The GPUs must be idle, port 18130 must be
free and `/home/steve/SUDO_PASSWORD.txt` must be readable.

### Step 1: NaN semantics (no IPC)

```bash
python3 run-native.py --out /mnt/fast-ai/bench-results/optimization-validation-20260915/nan-semantics-01 --check-only
python3 run-native.py --out /mnt/fast-ai/bench-results/optimization-validation-20260915/nan-semantics-01 --timeout 900
python3 -c "import json;d=json.load(open('/mnt/fast-ai/bench-results/optimization-validation-20260915/nan-semantics-01/DONE.json'));print(d['verdict_status'],d['selected_mode'],d['matching_modes'])"
```

- **Go to step 2** only if the command exits 0 and `verdict_status` is
  `selected`. Use `selected_mode` as `--add-mode`.
- **Stop** if the verdict is `no-single-formulation-matches`. Read
  `distinguishing_table` in `nan-semantics-verdict.json`; the arithmetic needs a
  new reviewed design, and stage 05 will refuse. Also stop on
  `xccl-ranks-disagree`, on `GPU-FAULT.json`, `MEMORY-GUARD-FIRED.json`, a
  campaign `FAULT.json` or `STOP_UNCONFIRMED`, or on any non-zero exit.

### Step 2: exact gate with the selected mode

```bash
MODE=<selected_mode from step 1>
python3 run-native.py --out /mnt/fast-ai/bench-results/optimization-validation-20260915/communication-native-05 --add-mode $MODE --check-only
# check-only must print "nan_semantics_receipt": {"satisfied": true, ...}
python3 run-native.py --out /mnt/fast-ai/bench-results/optimization-validation-20260915/communication-native-05 --add-mode $MODE --timeout 1200
```

- **Quality go:** exit 0 and `DONE.json` `passed: true`. All 16 cases matched XCCL
  bit for bit at all four shapes on both cards, and inputs were unchanged. Speed is
  a separate reading: `qualified_operator_shapes` in `analysis.json` lists shapes
  with at least 5% paired median gain and all five blocks positive. It is still an
  isolated operator result, not a model or service qualification.
- **Clean stop:** `rank*-QUALITY-REJECTED.json` with `CLIENT-FAILED.json`. The
  mismatch was retired cooperatively; inspect the named case. Check that no kernel
  fault followed it: that is the direct test of the teardown suspicion.
- **Hard stop:** `GPU-FAULT.json`, `MEMORY-GUARD-FIRED.json`, a campaign
  `FAULT.json`, `rank*-FAULT.txt`, `STOP_UNCONFIRMED`, or render devices still
  owned afterwards. No further GPU work until reviewed.

## Open risks

- The characterization runs in one process per card. If XCCL's result depends on
  something other than the element pair and position, the verdict shows it as
  position-dependent output, and no mode is selected.
- `sycl::half` addition may be compiled differently from the plain FP32 form; that
  is exactly what m2/m3 test, and only on this driver.
- The pre-launch availability check still uses the shared helper's unbounded
  `subprocess.run`. It runs before any container exists.
- If the memory guard fires, it kills the container abruptly. In stage 05 that means
  live peer imports, the same pattern suspected in Native04.
