# Duration108 residency refusal and one resource candidate

The49-frame pilot stopped before its first native clip. The preload equation, evaluated on107b's historical measurements, already predicts that23/25 cannot meet the new8GiB primary reserve. This should have been checked before launch: my earlier recommendation considered postload headroom but missed the inherited additive10% preload margin. This is an admission-design miss, not evidence of a49-frame OOM or output-quality failure.

The actual108b per-card free/missing/required snapshot was lost because the failure handler omitted native-setup adapter receipts. The table below is explicitly historical inference; it does not recover those missing measurements. Root is preserving the refusal and fixing that evidence path.

The source equation in sealed108b `native_adapter.py:330` is `ceil(1.1 * missing) + max(PRE_BYTES, ceil(loader reserve))`. On107b, GPU0 had31.397972GiB free and22.044483GiB missing weights. Raising its reserve from6 to8GiB raises its requirement from30.248931 to32.248931GiB, exceeding historical free memory by0.850959GiB. Other cards pass those historical inputs. This preload obstacle arises from static residency and the stronger allowance; it is not itself a duration-dependent activation measurement.

| Placement | GPU0 required GiB | GPU1 required GiB | GPU0 historical margin GiB | GPU1 historical margin GiB |
| --- | ---: | ---: | ---: | ---: |
|23/25|32.248931|27.806547|−0.850959|3.591581|
|22/26|31.456669|28.598809|−0.058697|2.799319|
|21/27|30.664407|29.391071|0.733565|2.007057|
|20/28|29.872145|30.183333|1.525827|1.214795|

I read only the677,616-byte safetensors header, no tensor payload. Its SHA256 is `641d57ff76ba1bbb2dac09b0110792652675ce83ad78b02b71ef750729995ab0`. All48 blocks have773,349,760 bytes when loaded BF16 (0.720238GiB), exactly matching107b's19,333,744,000 secondary missing bytes divided by25. On-disk per-block bytes are773,546,368 because six scale-table tensors are stored FP32; using raw checkpoint sizes would slightly overstate movement. The JSON binds header details, source bytes, manifests, historical receipts and reviewed notes; the full checkpoint was not rehashed.

Prefer one **20/28 resource-feasibility successor**, retaining every memory guard.22/26 still fails the historical equation.21/27 is feasible on those inputs but has a smaller worst-card margin than20/28 (0.734 versus1.215GiB).20/28 also has stronger recent qualification evidence: [100b](2026-10-07-rebalance100b-results.md) passed128 four-tensor comparisons at256×256/25 frames. Its speed idea was closed after a marginal1.1% screen; it did not fail quality. [100](2026-10-07-rebalance100-setup-failure.md) failed a two-segment/one-secondary host ownership predicate;100b repaired that exact consumer. The older21/27→23/25 result used a different workload/lineage and supports neither a49-frame speed prediction nor skipping new quality gates.

Implementation must port the reviewed100b named `two-way20-28` placement and fixed `shared_identity` handling in both host-node mirrors. Native108's adapter currently requires `two-way`, `split_index:23`, and absence of `segments`; replace these with an exact new segment/owner contract, never a permissive bypass. Its one-secondary unpack remains valid only after checking exact cardinality. `setup_gates.py` currently expects blocks0..22 and23..47; successor coverage must require0..19 and20..47 for both registered workers and all four chains. The graph helper pins the shard source, so update that reviewed hash and manifest/extension closure, preserving the actual graph-node registration wrapper. New plan/QID/environment identities must bind20/28; preserve sealed108b and100b.

This changes device ownership/boundary placement, not the intended transformer operations. It still needs fresh49-frame native repeats and complete exact video latent, audio latent, image and waveform comparisons. Historical256 exactness cannot substitute. Keep BF16,8+3 steps, all first-native/prewrite/storage gates and native8/8/2/9, capture7/7/2/9, decode2/2/10/9, replica8GiB postbuild/2GiB postprobe and2GiB chain margin. Do not try another split or lower thresholds after a refusal.

The weight-only projection would move postload primary/secondary free memory from8.733/12.805 to10.893/10.644GiB. It says nothing conclusive about49-frame graph pools, VAE workspace or concurrent peaks. If the real guarded successor still refuses, bank that boundary and continue useful25-frame reliability/workflow work; do not launch another diagnostic run merely to collect a green admission. No throughput gain is predicted here.

Evidence: [structured audit](../data/resume-20261007/duration108-residency-audit.json). Only this note and its JSON were written; no model loads, GPU/endpoint/process operations, runtime edits or tests.
