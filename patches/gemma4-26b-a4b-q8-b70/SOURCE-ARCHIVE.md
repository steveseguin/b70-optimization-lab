# Gemma 4 26B A4B Q8: restoring archived research source

Storage consolidation, 2026-10-10. No source version, hash or experimental
verdict was discarded. Seventy-two cumulative source snapshots and focused follow-up patches from `source-snapshots/`. The canonical encoded record patch, standalone reproduction inputs, top-level review patches and all `.diffstat` files remain unpacked. The archive retains accepted, rejected and pre-edit states separately.

The [manifest](source-archive-manifest.json) maps every original repository path
to its exact byte count and SHA-256 in [the archive](source-history-20261010.tar.xz).
Historical notes and frozen JSON receipts keep their original paths and hashes:
those paths are restoration destinations, not missing evidence.

## Verify and restore

From the lab repository root, verify every member without extracting:

```bash
python3 tools/restore-source-archives.py patches/gemma4-26b-a4b-q8-b70/source-archive-manifest.json
```

Restore the original directory layout under a separate destination:

```bash
python3 tools/restore-source-archives.py patches/gemma4-26b-a4b-q8-b70/source-archive-manifest.json --destination /tmp/b70-source-history
```

For an external destination, add `--require-mount /mnt/EXPECTED_MOUNT` so
an absent disk cannot redirect writes onto the parent filesystem.

Use `--member ORIGINAL_REPO_RELATIVE_PATH` to select one file. Use
`--destination .` only when a historical command needs the old path inside this
checkout; exact ignore entries keep restored bulk bytes out of new commits.
The helper verifies the archive and every member before writing, enforces the
50 GiB disk reserve, refuses conflicting files or symlink paths, and verifies
the restored bytes. It never executes a patch, build, model or historical runner.

All 76 consolidated files were restored and compared byte-for-byte before
removing their unpacked copies. [The consolidation audit](../../audits/repository-cleanup/2026-10-10/archive-consolidation.md)
records the exact consumer inventory and proof. This restores source evidence;
it does not establish binary identity, clean-host replay or permission to run.

## Inventory

Original bytes: **42,984,043**; archive bytes: **120,716**.
Archive SHA-256: `55e2eabce8d55be714a27391f7b6f983ca019e1e51490224b37da5fbe9121ff2`.

| Original path relative to this directory | Bytes | Original SHA-256 |
| --- | ---: | --- |
| `source-snapshots/20260629-eogclip-spechead-current-files.patch` | 50943 | `b0b8325698cc68ea921cf8f841f92eba2ac9b52599bd27273700feb97364f3f3` |
| `source-snapshots/20260629-faon-vmm-pre-packed-geglu.patch` | 674959 | `a6b0bd97d853e566da1e6e261fbb7a2cd09d857267e76445f9eac11c4893a355` |
| `source-snapshots/20260629-fused-down-selected-softmax-current-files.patch` | 273244 | `4f526d10a8200dd7af89d00613f52c87e5ea404d4aff45bb2dade19492d991b5` |
| `source-snapshots/20260629-ingraph-bonus-preedit.patch` | 644157 | `a372c39637dba6258e18b6ba0f4caa1ddbf44eb6797f29a65ea7e772c7d546e5` |
| `source-snapshots/20260629-llamacpp-current-stack-before-next.patch` | 612749 | `a5487603fa795a1b977053afa6e0abb8052e4dddf4f8537dd97f42d658dea844` |
| `source-snapshots/20260629-llamacpp-current-stack-before-top1partial.patch` | 616275 | `b050cca32dc3ce58800635abea1ec9d6ec8810db789500f8835268f7e13d8f1b` |
| `source-snapshots/20260629-llamacpp-current-stack-with-top1epilogue.patch` | 616275 | `b050cca32dc3ce58800635abea1ec9d6ec8810db789500f8835268f7e13d8f1b` |
| `source-snapshots/20260630-acceptprefix-parity-source.patch` | 690656 | `930cd21bca541e635a825f0966a0c75df049e2b9b90c23e7de54aa2b8875221c` |
| `source-snapshots/20260701-acceptprefix-preedit-source.patch` | 700539 | `aef9b33160bcf8a1c5472442d34f49746211f8b0f615412ae34e1fa1bd4b2cea` |
| `source-snapshots/20260701-acceptprefix-v2-preedit-source.patch` | 736015 | `a82ffcdc4f7c20447d42e2325e380124bfddd11a7ec324f69e5bfdf7810d08a6` |
| `source-snapshots/20260701-active-record-stack-before-fastmask-source.patch` | 749547 | `c99bdf3941aa766094c49cdf21fdd72031d1c3beb07fe9866e72a3672833798a` |
| `source-snapshots/20260701-candidate-bound-lmhead-proof-preedit-source.patch` | 755549 | `665a818bafd6f7e906b2350f1431e0129edd3507efc459cc1812f8bed1f0a7b3` |
| `source-snapshots/20260701-candidate-proof-profile-preedit-source.patch` | 749547 | `c99bdf3941aa766094c49cdf21fdd72031d1c3beb07fe9866e72a3672833798a` |
| `source-snapshots/20260701-candidate-proof-profile-sampling-abandoned-source.patch` | 752958 | `214edd2937b4f878c5a345b7e10b9df0018d2bca2e075621c0e29a31146bff07` |
| `source-snapshots/20260701-candidate-proof-profile-server-source.patch` | 754740 | `2dab9dce3d6a41cba8edad559eb754088c6f5ca1de6531f408c069e45b7f727a` |
| `source-snapshots/20260701-direct-sampled-egress-backendcopy-prealloc-source.patch` | 762426 | `87a17a7877eccb91bebea2dc376352fa676e1f4c44ed0cd42de6ded74732efe9` |
| `source-snapshots/20260701-direct-sampled-egress-backendcopy-source.patch` | 761494 | `415b5098621547d93efa68f980f80e0f1f991a47e597324b45f84aa6cddf5753` |
| `source-snapshots/20260701-direct-sampled-egress-parity-source.patch` | 761219 | `beb4dec08c49d645dbfa8b7c328daa475c40057e85b2f290d50994c91cfc3049` |
| `source-snapshots/20260701-direct-sampled-egress-preedit-source.patch` | 754740 | `2dab9dce3d6a41cba8edad559eb754088c6f5ca1de6531f408c069e45b7f727a` |
| `source-snapshots/20260701-direct-sampled-egress-strictparity-source.patch` | 761160 | `369bbafda96b88683630943ad7a4c6401b79d54f1f04487a6d3a203ee41e5921` |
| `source-snapshots/20260701-fattn-dv512-gqa-ncols16-source.patch` | 749952 | `5ad8faa912a145ed985155e7dcfc7e49da2fe2509ef792b4c97889ff26160dc5` |
| `source-snapshots/20260701-global-fattn-causal-fastmask-source.patch` | 758540 | `45215c55992e89b9fb5f9bc227936b386ad19200d97f745b34b2f9379addf523` |
| `source-snapshots/20260701-post-consolidation-current-source.patch` | 749411 | `5bf86f0a3fa40264a14f9048b4fa34490c5e7b66ec942b16bd33581dc1e683a7` |
| `source-snapshots/20260701-post-directegress-cleanup-source.patch` | 755549 | `665a818bafd6f7e906b2350f1431e0129edd3507efc459cc1812f8bed1f0a7b3` |
| `source-snapshots/20260701-prefill-ncols16-preedit-source.patch` | 749547 | `c99bdf3941aa766094c49cdf21fdd72031d1c3beb07fe9866e72a3672833798a` |
| `source-snapshots/20260701-swa-left-bound-fast-builder.patch` | 8219 | `9cbd0d65c0036a94975b0e4fdbfb1104a559717018ccdd6b76c5e33fe39a44a7` |
| `source-snapshots/20260701-top2-logging-reopen-preedit-source.patch` | 754740 | `2dab9dce3d6a41cba8edad559eb754088c6f5ca1de6531f408c069e45b7f727a` |
| `source-snapshots/20260701-verifier-top2-margin-profile-source.patch` | 758538 | `3e1652df196135910001ba6518f6ad84d1abf427ade6ca1e09d749f717462e0e` |
| `source-snapshots/20260701-verifier-top2-v2-preedit-source.patch` | 749547 | `c99bdf3941aa766094c49cdf21fdd72031d1c3beb07fe9866e72a3672833798a` |
| `source-snapshots/20260701-verifier-top2-v2-source.patch` | 758781 | `79dd3d1e64ad34fef9deb81ffd263eaeb8a287e89e2be62fe9c942bd7bab4a2f` |
| `source-snapshots/20260701-verifier-v3-preedit-source.patch` | 749547 | `c99bdf3941aa766094c49cdf21fdd72031d1c3beb07fe9866e72a3672833798a` |
| `source-snapshots/20260702-acceptprefix-epilogue-preedit-source.patch` | 764632 | `7220e022ae836b2a885f6e1ba5d73422f1ddd9c74e0c3e4582a0d7066fa295e3` |
| `source-snapshots/20260702-acceptprefix-epilogue-source.patch` | 791154 | `dc875407fa95ad1d0cda91eaeec9017c7cdc727606a5f7f1aa5d2577d4303ede` |
| `source-snapshots/20260702-conditional-bonus-preedit-source.patch` | 755549 | `665a818bafd6f7e906b2350f1431e0129edd3507efc459cc1812f8bed1f0a7b3` |
| `source-snapshots/20260702-conditional-bonus-source.patch` | 771337 | `6af5da9c0367acd807b278430d001536846585f60a9bd37f4e71510cc844cfa8` |
| `source-snapshots/20260702-fattn-dv512-gqa16-nbatchk128-focused.patch` | 538 | `f1a7cfb0b1aef331de614b1f2ba36eb150ccf365524aff07bf3f09179a2b0a80` |
| `source-snapshots/20260702-fattn-dv512-gqa16-nbatchk128-source.patch` | 756017 | `6fac8ef997f583f83c8694649a149647227fc35354784a5c3798d1afaf93fdc4` |
| `source-snapshots/20260702-fattn-dv512-gqa16-nbatchk32-focused.patch` | 538 | `b34c90f72702b6ef1745cdc32bec28e953dbd4481e64f6c985e5fba10a491b14` |
| `source-snapshots/20260702-fattn-dv512-gqa16-nbatchk32-source.patch` | 756017 | `e49d154caae29619cdbbbe6802562f33c965cd17899a4ab6d6bf6249370c8630` |
| `source-snapshots/20260702-fattn-nbatchk-preedit-source.patch` | 755549 | `665a818bafd6f7e906b2350f1431e0129edd3507efc459cc1812f8bed1f0a7b3` |
| `source-snapshots/20260702-global-fattn-dvsplit-preedit-source.patch` | 756020 | `0460562c5fd4bbc27756ee3162b46b3108b2b6b61060ffbf899484c43e3bd690` |
| `source-snapshots/20260702-global-fattn-dvsplit-source.patch` | 19188 | `d21ec2cd5f2803498ff0f9bbb82c80341ad2bd2306d4995a64ed179ea299e999` |
| `source-snapshots/20260702-global-fattn-vecdispatch-preedit-source.patch` | 756020 | `0460562c5fd4bbc27756ee3162b46b3108b2b6b61060ffbf899484c43e3bd690` |
| `source-snapshots/20260702-global-fattn-vecdispatch-source.patch` | 1487 | `e438b20d83f963c7895eea5a8ee2e9c64d2bf29ab86dc82bbacf200fd0ec1f64` |
| `source-snapshots/20260702-global-ncols16-preedit-source.patch` | 755549 | `665a818bafd6f7e906b2350f1431e0129edd3507efc459cc1812f8bed1f0a7b3` |
| `source-snapshots/20260702-global-ncols16-source.patch` | 756656 | `e02faa058e70cfdb95103427e3a5f5472ff2c31e3b16989f351a587c812c27ba` |
| `source-snapshots/20260702-hotglobal-pb1-preedit-source.patch` | 764632 | `7220e022ae836b2a885f6e1ba5d73422f1ddd9c74e0c3e4582a0d7066fa295e3` |
| `source-snapshots/20260702-hotglobal-pb1-source.patch` | 7940 | `28b4706bdeaedc24247b701aa57dad750ea5fd3ac526cdb4af9c21becf2fe7d8` |
| `source-snapshots/20260702-kq-reg-bcast-dkq576-fattn-tile.patch` | 14477 | `47ec19a924e82696f5d2a280973a5ff007d30c4bf86ef893ed4df1ebfee0e1dc` |
| `source-snapshots/20260702-kq-reg-bcast-dkq576-preedit-fattn-tile.patch` | 14461 | `75f6c4fa8f2f49b069e998e408048432e2ae74b1c76328c1739992ddd3b1bab8` |
| `source-snapshots/20260702-kq-reg-bcast-dkq576-preedit-source.patch` | 764616 | `d8817554891c266889c72d39281f1ca191061c98f492ae2e53190ee481d09f41` |
| `source-snapshots/20260702-kq-reg-bcast-dkq576-source.patch` | 764632 | `7220e022ae836b2a885f6e1ba5d73422f1ddd9c74e0c3e4582a0d7066fa295e3` |
| `source-snapshots/20260702-kq-reg-bcast-no-kq-lsm-fattn-tile.patch` | 16663 | `9aee54580cd9a00f19ec2ed5a25576937cdc48bd10efedad36f1578db5f13011` |
| `source-snapshots/20260702-kq-reg-bcast-no-kq-lsm-preedit-fattn-tile.patch` | 14477 | `47ec19a924e82696f5d2a280973a5ff007d30c4bf86ef893ed4df1ebfee0e1dc` |
| `source-snapshots/20260702-kq-reg-bcast-no-kq-lsm-preedit-source.patch` | 764632 | `7220e022ae836b2a885f6e1ba5d73422f1ddd9c74e0c3e4582a0d7066fa295e3` |
| `source-snapshots/20260702-kq-reg-bcast-no-kq-lsm-source.patch` | 766818 | `1ccd0a5f07062d8f33658d089cdced47ae560d05f1cee724547d836b9b85055f` |
| `source-snapshots/20260702-kq-reg-bcast-preedit-source.patch` | 5865 | `2643c5dc28a0791afbc210b6008f5a1a037b6715cd6c35fa8c446da39883782e` |
| `source-snapshots/20260702-kq-reg-bcast-skipbarrier-fattn-tile.patch` | 15880 | `bc3441a6243968c62efdadb821936f40cb8de69e10d60f8ed22978f35eca6d71` |
| `source-snapshots/20260702-kq-reg-bcast-skipbarrier-preedit-source.patch` | 764632 | `7220e022ae836b2a885f6e1ba5d73422f1ddd9c74e0c3e4582a0d7066fa295e3` |
| `source-snapshots/20260702-kq-reg-bcast-skipbarrier-source.patch` | 766035 | `1aa186fdc6234fdd1555939f43de8c70347282b3e80e5213fbb2fa3b498985d4` |
| `source-snapshots/20260702-kq-reg-bcast-source.patch` | 14461 | `75f6c4fa8f2f49b069e998e408048432e2ae74b1c76328c1739992ddd3b1bab8` |
| `source-snapshots/20260702-pre-next-verifier-source.patch` | 755549 | `665a818bafd6f7e906b2350f1431e0129edd3507efc459cc1812f8bed1f0a7b3` |
| `source-snapshots/20260702-q6k-argmax-profile-preedit-source.patch` | 764632 | `7220e022ae836b2a885f6e1ba5d73422f1ddd9c74e0c3e4582a0d7066fa295e3` |
| `source-snapshots/20260702-q6k-argmax-profile-source.patch` | 768964 | `3a58d7eff8a26a4b74a851ee90b483f00702ac0631da3f1fc55714f189d2c8e2` |
| `source-snapshots/20260702-qstaging-preedit-source.patch` | 764632 | `7220e022ae836b2a885f6e1ba5d73422f1ddd9c74e0c3e4582a0d7066fa295e3` |
| `source-snapshots/20260702-qstaging-qglobal-source.patch` | 772965 | `e3568baa166f578fbd763e4afb023cf240fd1b9842ebb63a4f0e6bcb819effb5` |
| `source-snapshots/20260702-tail-only-direct-confidence-source.patch` | 760916 | `27ce8427a21e26ab2d6dffa525740bc2bcc10d6a3b433c9b99f92296be4e0ddc` |
| `source-snapshots/20260702-wg512-preedit-source.patch` | 764632 | `7220e022ae836b2a885f6e1ba5d73422f1ddd9c74e0c3e4582a0d7066fa295e3` |
| `source-snapshots/20260702-wg512-source.patch` | 766389 | `bf8890ff5b678c99f1794b3490bc609b2446485f0de221d4651a02ee18940673` |
| `source-snapshots/20260702T054719Z-pre-global-fattn-right-bound.patch` | 755549 | `665a818bafd6f7e906b2350f1431e0129edd3507efc459cc1812f8bed1f0a7b3` |
| `source-snapshots/20260702T061300Z-global-fattn-right-bound-built.patch` | 767148 | `beda9b6d6af054a84d9ea5fe89db59699398d91c183fb1b6bcf3f56f006095cd` |
| `source-snapshots/20260810-production-binary-source.patch` | 764632 | `7220e022ae836b2a885f6e1ba5d73422f1ddd9c74e0c3e4582a0d7066fa295e3` |
