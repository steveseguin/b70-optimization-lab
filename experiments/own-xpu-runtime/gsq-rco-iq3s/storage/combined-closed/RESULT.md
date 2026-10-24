# Closed combined-state archival complete

All27 closed combined-run state groups were compressed, read back byte-for-byte,
then their duplicate raw binaries removed. Every archive was copied to USB and
fully verified again before its temporary NVMe copy was released. The existing
filesystem helper and256MiB per-group quota were retained, with unchanged27GB+64MiB
root reserve and2GiB USB reserve. No GPU work overlapped archival. No retry occurred.

The archives preserve57,051 files /6,248,947,500 raw bytes in2,329,766,168 compressed bytes. All JSON, logs, directories and unindexed files remain; model weights are untouched.

The first nine groups finished before the narrow expert diagnostic; the remaining
eighteen ran after its safe drain. A53,283,990-byte disposable pip HTTP download
cache was removed to restore archive admission headroom; installed packages and
research artifacts were unchanged. Its inventory is retained in
[pip cache cleanup](evidence/pip-download-cache-cleanup.json). No reserve was lowered.

[Complete receipts](evidence/complete.json) bind each four-phase result.
NVMe metadata and restore maps remain under
`/home/steve/own-xpu-runtime-results/gsq-attention-qkv-bin-archive-a/chunk-NN`.
USB archives are at `/mnt/usb-models/own-xpu-runtime-results/` with these names:

| Group | Compressed bytes | Archive SHA256 |
| --- | ---: | --- |
| 00: initial | 1,084,167 | `2983d08ca025492708cbbc12b06e827a47413658b33a55ed8bf4405e41d38d00` |
| 01: warmup-none | 85,462,910 | `ecff239166e5ff7f8a66f05d92a898212b9909db9ff30278aa1d5439aed41f85` |
| 02: warmup-mtp | 85,442,538 | `a41852ebfa837f3025fcdc651b3c13bb31e45ede0161ee55c2bee4549fd4633b` |
| 03: prompt-00-none | 90,041,079 | `0f3d0938b43cfb25b46d94b1cf80acd97976145654879712c2068928ee76a72f` |
| 04: prompt-00-mtp | 90,453,000 | `46128ca3b13efb1ae20ca8553d9a0f15738cf39e68b474ce0ef30225aea18fe0` |
| 05: prompt-01-mtp | 90,547,133 | `b3ad0d7ffa3f7502200ac902d0b4d21882211b5f6971faf3194aee6f2eb090cc` |
| 06: prompt-01-none | 90,145,648 | `ecf293ddcb82cf6909586ba896d5c0f2ffe1f208e93da9ee2a906af989697b4c` |
| 07: prompt-02-none | 89,865,340 | `8afcbd9477e57e0463f91c0758b0393583b003364cca966ca38235ef83c7923c` |
| 08: prompt-02-mtp | 90,262,335 | `ad50be8ca80c1a974d180f7bce09a1b7a126e12daee7a2c32ece55aa5dc2e833` |
| 09: prompt-03-mtp | 90,404,454 | `d92a1af65954e5f947ac1f1f25804d4a85e981a4343c1162f5357e31a09c45bd` |
| 10: prompt-03-none | 90,010,424 | `039a1de33b88f99e704a7475efab40543c333c045d7f1946449e4b7e4c9c950d` |
| 11: prompt-04-none | 89,608,547 | `146d784d2563c14cf173ce760fd2828995d523f5d4b4707efc38e8e2b7086c1d` |
| 12: prompt-04-mtp | 89,991,056 | `e0be47cb7b14409840233cd183a83228dd95bdf55644818031106ad27940c60e` |
| 13: prompt-05-mtp | 89,922,037 | `11ff7206069d5baa35aac1f49891dc0fa0806be7cd3210337b0cd36744a0c020` |
| 14: prompt-05-none | 89,545,144 | `7459f465d4f8633f637865c41172ee6113d15337955e8048774a8d36f142d218` |
| 15: prompt-06-none | 89,572,339 | `1416c03273b89f6af34c95563b6aab37f0ca478edb1bf8eca82feb4395dd412c` |
| 16: prompt-06-mtp | 89,921,620 | `e72d3c7df903db209937022f8146abd600559b0f5f2bae46b9b37e61a6dfbc3d` |
| 17: prompt-07-mtp | 90,153,522 | `3d03aefc129b99898df828b0fa312ae776e262339df8536617d65ed3ad213638` |
| 18: prompt-07-none | 89,773,408 | `d3f6ecf898214300b0b6533f05d0d0eca1d4ce7245a8866c0e7574169922bc0b` |
| 19: prompt-08-none | 89,680,264 | `70ebf4f94cea4ca9b41be8c2553d143add02899eaf2ccbf3a875c716d03c9d9f` |
| 20: prompt-08-mtp | 90,054,537 | `26d5fcd0f7ddd00226c448f30ffd4bc04e05114329a0de0fb28236f540c2120e` |
| 21: prompt-09-mtp | 89,795,544 | `dfb631d2c272af9005784de05c52e44f8f1db965ffde5520338629992eb0d9fd` |
| 22: prompt-09-none | 89,436,277 | `ef1099d65be8e61118f47e1a8679ad6153bafdbce55c59a8bd9365614f651b68` |
| 23: prompt-10-none | 89,556,744 | `9d63dcb9b45e9d9a4cf04fcbcac06f8166b6da6b31bff36c1e3d2029ff6d0985` |
| 24: prompt-10-mtp | 89,926,383 | `a5630a66bc7c2b243f14e6267940a2eabe17f8817b69eab1d5390f927114ebfe` |
| 25: prompt-11-mtp | 89,736,553 | `518e8817c3cf62138878a2a24724df1152b12f9f142057687046840b9f87bfdd` |
| 26: prompt-11-none | 89,373,165 | `708f0a0f622d4e77fdba304667c53cefdb6afa5cd35337a45f20dded99712b03` |

Filenames are `gsq-attention-qkv-state-bins-NN.tar.gz`. To restore, first verify
the archive SHA256 above, extract into a fresh empty directory, and check every
member against its retained manifest and the original independently audited
artifact index. Paths are relative to the original combined-run evidence root.
Do not overwrite existing evidence. Restored binaries plus the preserved JSON/logs
reconstruct the original audit input. The live raw tree's absence markers explain
archived files; the original independently audited index remains unchanged.

Archival frees byte and file-record capacity, not model speed. After two additional
diagnostics the USB still has insufficient space for the next full suite plus its
reserve. Compress closed evidence bundles before that suite; preserve current
attribution bundles until the selected micro fixtures have been extracted.
