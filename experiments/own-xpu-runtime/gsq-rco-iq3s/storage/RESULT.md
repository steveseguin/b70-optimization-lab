# Closed baseline storage consolidation

All27 closed baseline request-state batches are losslessly archived. The original6,248,947,500 bytes are retained in27 gzip/tar archives totaling2,329,771,702 bytes. After full member/hash readback,57,045 original `.bin` files were removed; all JSON records and six52,224-byte micro input/output files remain. No model weights were changed. USB free data space is11,205,922,816 bytes after completion.

The [completion manifest](evidence/complete.json) binds every archive path, byte count, SHA256, original request prefix, removal count and retained per-batch metadata directory. Every batch has copy/readback, prune, external-offload/readback and local-release receipts in `evidence/`. The [source review](evidence/independent-review.json) and17 tiny tests cover the fixed path/authority, quota, mutation, symlink, archive corruption and wrong-filesystem refusals. Local NVMe archives were released only after full USB archive readback; small restore maps and source-stat manifests remain under `/home/steve/own-xpu-runtime-results/gsq-baseline-bin-archive-a/chunk-NN`.

This resolves the observed NTFS file-record capacity failure by replacing thousands of files with a small number of archives. It is not a filesystem-repair or hardware-health claim. [Post-archive observation](evidence/post-archive-host.json) shows only the unchanged vision owner, both target cards empty and the original GPU fault baseline. [NTFS observation](evidence/post-archive-ntfs.json) records no new daemon messages during archive creation/readback. No service, power, swap, page-cache, filesystem setting, reset or reboot action occurred. The interrupted attention candidate remains incomplete; it was not automatically relaunched.

## Restoring or reviewing state bytes

The immutable original authority is [the baseline artifact index](../baseline/evidence/independent-a/artifact-index.jsonl.gz), SHA256 `e8137dddb0929d5476d27a8a774539a77d595aeb296e9d0ec778ceec066a6982`. Each tar member is the original relative `.bin` path under `/mnt/usb-models/own-xpu-runtime-results/gsq-baseline-a`; no source paths were renamed. The archived state bytes can be streamed and verified without restoring thousands of files. To restore, first hash the archive against the completion manifest, inspect/verify all regular members against the original index, and restore only missing paths under the fixed original root. Preserve existing files; compare their hashes instead of overwriting them. Recheck restored payload hashes. Recreating all57,045 files needs a new record-capacity assessment, so prefer one requested state or streamed verification.

Each archive is `/mnt/usb-models/own-xpu-runtime-results/gsq-baseline-a-state-bins-NN.tar.gz`:

| Batch | Original request | Compressed bytes | SHA256 |
| --- | --- | ---: | --- |
| 00 | initial | 1,084,159 | `d6b0a32edbfc06e611d5d9bada67ae92e723a4c2717b922f9ef30f1a9ea342ca` |
| 01 | warmup-none | 85,462,789 | `b0b3baca0bd5ee37d2709f3201cc81e9795ca8a10311e4bb5891051ae38e0ad7` |
| 02 | warmup-mtp | 85,442,630 | `5b6e63b2aa679673ad3f2d4ed2748b30775419b2753585a3099d88eb887b0636` |
| 03 | prompt-00-none | 90,040,912 | `a9b2a2e5238df9bf069ced56e1a6a818ac75df49c3f261c8a5aa3e759c32cbd6` |
| 04 | prompt-00-mtp | 90,452,892 | `54525a78eb4188fd8e7fca487fad0c400e3fef0821109965cd310f1714110cc7` |
| 05 | prompt-01-mtp | 90,551,354 | `fb646911740f6884f3a2c34150b4ede87b5065db541312896725716fe00cb43f` |
| 06 | prompt-01-none | 90,144,699 | `d832f9db6fa64fea97e3f5fc61df0c5b5f834914067e237477bf93abc86dfa07` |
| 07 | prompt-02-none | 89,864,823 | `e1cadf72df0978baf1220e757f7a6a5c3f28e7ac270415793756b5234c9e536b` |
| 08 | prompt-02-mtp | 90,262,488 | `516a013af6ef31383a61267ec89177163062944910e844d4e5ef99798aa46f41` |
| 09 | prompt-03-mtp | 90,404,468 | `3501838205d1d4680ade75c9047d2063c58144f368506e3cf823c0da939ff574` |
| 10 | prompt-03-none | 90,010,300 | `0dde9d9bf6cc3d1f287099f91f8af450a2de5557de986e9e49b0a162e3a2e8b8` |
| 11 | prompt-04-none | 89,609,143 | `3f25e52be5ede628cfd219594b78c928de411f492a52604d967030a7e143b39f` |
| 12 | prompt-04-mtp | 89,991,183 | `5f10853152af8103a7952306347daf0b89411944f85c9a6cc83760c79721f916` |
| 13 | prompt-05-mtp | 89,922,825 | `a92b8e25c4e7225251df9d25e586203eebc291f9914ec345ec1ed08c527c8bb9` |
| 14 | prompt-05-none | 89,544,822 | `f2c486aa37e50995bf37055a90d64bfdb4854eb1d95efb52d7af736a397c23b1` |
| 15 | prompt-06-none | 89,571,704 | `8f8d6cbc2ab5f7922345b1d1d3a50990654b44572f3df1a9faa261b3a2c4de42` |
| 16 | prompt-06-mtp | 89,921,612 | `f57cfca66b77fe7d32df6ef297afe02b2eef419bccb3e58e63f6cf8ac6d9ecba` |
| 17 | prompt-07-mtp | 90,153,971 | `cf9ba8cd469d7bafde798a888ae74c80dac95ac63beaf75518f71bf2e003492a` |
| 18 | prompt-07-none | 89,772,679 | `7401f8b3dab8be118ca710cfbc9702dd68cfbd9371e8b9d2ec538cb47fef45f4` |
| 19 | prompt-08-none | 89,681,197 | `3548321df8c0c514fdcb1f157c8f5c6f70b90f3df04f01419c022c9c4ca3219e` |
| 20 | prompt-08-mtp | 90,055,379 | `852abed2b55f5477621c27963509338d71914a8e12c8194f0c48c2593ef01615` |
| 21 | prompt-09-mtp | 89,795,798 | `3e7c0bc2cb87b7ac856dc228c8fc7bb94f89dca7808109cabd43ad551bef7493` |
| 22 | prompt-09-none | 89,436,414 | `1b599aecdfa934388333ee97c21ce33de16b456f5f402f5e00efea196ddcbcb4` |
| 23 | prompt-10-none | 89,557,144 | `ec356a9be71559ddc191cf4e19f22aa4eb809c2696b7a0328c895f353fad33d4` |
| 24 | prompt-10-mtp | 89,926,364 | `8698fc9265dfd69d9a12c2919aea7f67093c82718091c1351c5c11d496f1ab8e` |
| 25 | prompt-11-mtp | 89,736,537 | `3515f2de948bb32b63a177132562db7680ee09a18377672e896145411ce83ee9` |
| 26 | prompt-11-none | 89,373,416 | `9f8b5985f529d73f65e014fe9b295fe6aabd7200f13923b6192eb28d52f27517` |
