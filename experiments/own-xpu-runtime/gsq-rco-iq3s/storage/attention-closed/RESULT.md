# Closed attention state archival complete

All27 fixed groups completed archive, full member readback, original-file hash
verification and prune, USB offload/readback, and local release after another
full archive verification. The27 archives preserve6,113,156,852 raw bytes in
2,326,406,928 compressed bytes. Exactly56,981 duplicate `.bin` files were removed.
Fourteen groups belong to the interrupted run's audited target-state prefix;
thirteen belong to the separately completed five-pair run. All JSON, logs,
failure metadata, unindexed partial/auxiliary bins and model files remain.

USB free space is11,984,883,712 bytes afterward; root free is27,429,044,224 bytes.
No new NTFS messages appeared since07:18 UTC. No service, device, model weight,
filesystem setting or power/memory setting was changed.

The final four groups use a reviewed256MiB temporary quota, retaining the same
27GB+64MiB free-space floor. The prior384MiB quota refused batch09 before creating
its destination after the native build used disk space. That admission refusal
is preserved; no source changed. The explicit new policy fits the full231MB raw
payload plus a conservative container allowance, independent of compression.
See [quota review](evidence/finish-256-independent-review.json) and
[original refusal](evidence/batch09-admission-refusal.json).

[Completion receipt](evidence/complete.json) binds all27 archives and every phase
receipt. Temporary local archives were released only after verified USB copies;
metadata and restore maps remain under the recorded per-batch NVMe anchors.
The independent original indices remain the byte authorities. Future raw audits
need restoration or archive-aware reads; original JSON hash maps remain intact.

For restoration, choose the profile's exact source root from archive-start.json
and prune-start.json. Tar member paths are relative to that source. Verify each
member against the immutable profile index and restore only missing files; never
overwrite existing files silently. The inherited copy receipt's historical phrase
“baseline root/index” means its explicitly bound profile, not the original model
baseline root. [Preparation and fixed roots](README.md) give these identities.

| Profile | Batch | Archive bytes | SHA256 |
| --- | ---: | ---: | --- |
| prefix | 0 | 89984328 | `3f624f3a5737b093a18457c1fde9a5e9fc43c8fdf1e03336d4423bf4ca470e5b` |
| prefix | 1 | 89984336 | `ae7b3943c3f7a03ff2890fc9c7b0ce90749e582deb9a0012cd49860bcfff813e` |
| prefix | 2 | 90107251 | `85313b2e77fe0cc1efaeea7c578b951e1fd1427302e118479b6c2ee7a4167e74` |
| prefix | 3 | 90107635 | `ab806a00a6a200ead2eff7bd80bfd356fe3c93a932d6101b550d428bd4e2fbf5` |
| prefix | 4 | 89822911 | `6ae37b22d8dcdb0e5c2b65b24e3489499b87f6135bf7858413d97e2fc0721153` |
| prefix | 5 | 89823687 | `61484b40573a9a2cd31a6f9148d3f4e71f5010c1156bde9deb9cf8590a66f7f5` |
| prefix | 6 | 89958617 | `1f99c8734864a82909dde77b4d164e852c66521973474cd099b63596af4e37e6` |
| prefix | 7 | 89958492 | `1968facf0d5e5b9994462424655893538811ebc3d395e3039a6d852629292745` |
| prefix | 8 | 89567204 | `99947fac5625dbec9d3e3afb113d1b9df185ff0837f26ac7a72cf6edf49ec2a5` |
| prefix | 9 | 89567216 | `caea0369bac4186c7fedd28ca9d4eb6dea4b2433a3b7a9bcd21dac6856de0212` |
| prefix | 10 | 89510171 | `54ff72d44a9a4e72d7efb1cba33879c884fad61931502ee26bb4dec611f2243e` |
| prefix | 11 | 89509272 | `fe387eabf0f4ce61deea0918b5e72a701081952f8c7ec37b6653c49b955894b1` |
| prefix | 12 | 89514762 | `02e24da9530f32aedc529b7e7ea8b28b68ac78304f1ed8e96a5dd0eab31e501a` |
| prefix | 13 | 89514055 | `d05c0d2e0eea6b279db2e861a6c029968763b7f4d047f47f60506f7129cd10f6` |
| completion | 0 | 1084219 | `2ea09945c0278c37ae9cc246b1c91ff33ec02dbdfd3690faebb549953d0a8359` |
| completion | 1 | 85462336 | `2e54fa9550965559a11ddaa090970099ca70321cdc11b644ec55b0097c34100a` |
| completion | 2 | 85442696 | `4b880501b89f0d8edc798e41420249cd4de549a9f1e062c4c94e1ccd349ed59e` |
| completion | 3 | 90153549 | `9ed0a35fbf460ac6f3db6acafb7f4f1f06ab8d96ba96a069da8d41e8a6a05f2d` |
| completion | 4 | 89772923 | `a669596bcbbbac4bcfc5d4e7d7d0551067f7b17e1a2960402c4c4f7129081b20` |
| completion | 5 | 89680985 | `3b11233a60e70ed8296b2726794a2d33c2ac759c304115aa111fc2875db2813f` |
| completion | 6 | 90055382 | `7b275e471e53a49b015379f3b04862dd9c00c3c54ff9efbf3e068cc5d259fbed` |
| completion | 7 | 89796124 | `23a211a89678d3705edfabf64c605892b3536f201c75a238916d47f7ab89a840` |
| completion | 8 | 89436342 | `0f326df8aa52c192045aae637bce9b4885ac0cd821881aade29cb2f27644a3bf` |
| completion | 9 | 89557122 | `462c015a435fc579a282532e6f72380eb8d27bcc57c6bca9c1545b19c3629ec1` |
| completion | 10 | 89925695 | `32f332b92667719b1a04d2e00961c0479fcfe79ad50c915f0566c855f9742dbf` |
| completion | 11 | 89736588 | `ec0a1fbfdcc5acac5bdc08d721bf117b7ef33e35ae4f511695b86bd159a48551` |
| completion | 12 | 89373030 | `4c29057a9fa46bbd75a1d9732d6767781add54b78fa8d79a0ece99ad9e5dace1` |

Each archive is `/mnt/usb-models/own-xpu-runtime-results/gsq-attention-PROFILE-state-bins-NN.tar.gz`.
Keep the receipts, restore metadata and immutable audit indices permanently.
The file-capacity estimate for the next run counts observed removals and later
writes; it is not an MFT quota. Any write failure still halts new requests.
