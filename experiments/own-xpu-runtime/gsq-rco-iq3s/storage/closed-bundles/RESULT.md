# Twelve closed diagnostic bundles archived

The six state bundles from format qualification and six from the current class
profile were losslessly compressed, fully read back, and copied to USB with another
full verification before duplicate source/local archive removal. All12 batches and
four phases passed; no retry occurred. 1,330,459,008 raw bytes occupy
356,844,376 archived bytes. Current attribution bundles are untouched.

All original state indices, seals, state JSON, draft files and other evidence remain.
The exact fixed-path validator is the sole private adapter change; existing Job
methods are unchanged. The128MiB quota fits each individual bundle and preserves
the27GB+64MiB NVMe floor and2GiB USB reserve. No GPU work or compilation overlapped.

[Complete receipt](evidence/complete.json) binds every phase and archive. Files are
under `/mnt/usb-models/own-xpu-runtime-results/` as
`gsq-closed-state-bundle-NN.tar.gz`. Metadata stays under
`/home/steve/own-xpu-runtime-results/gsq-closed-bundle-archive-a/chunk-NN`.

| Batch | Original run | Original relative bundle | Archive SHA256 |
| --- | --- | --- | --- |
| 00 | gsq-state-bundle-a | `rank0/state-2147483647/state.bundle` | `65cc1e88da03aefa8147f0c64a1ccb24bcab574c2d4350e1251f648c6d1d5f2c` |
| 01 | gsq-state-bundle-a | `rank1/state-2147483647/state.bundle` | `a16dea6b0cb5b8bdd6b6b8c14daa80308950b3d3e57e727316ff0f3399138120` |
| 02 | gsq-state-bundle-a | `prompt-00-none/rank0/state-2147483647/state.bundle` | `f3dcc1ee61eb49274cfbfa445b66df53d3c95af5c89e06d35f85287b8f65a96a` |
| 03 | gsq-state-bundle-a | `prompt-00-none/rank1/state-2147483647/state.bundle` | `1d555fe727dd408b0b08f20671c4b15a20c0ad0f2131383b16f0805f9a052794` |
| 04 | gsq-state-bundle-a | `prompt-00-mtp/rank0/state-2147483647/state.bundle` | `f662b92c47197dae4b75b78701a9cee76291d51c25812b3a63997f89e3c77cc9` |
| 05 | gsq-state-bundle-a | `prompt-00-mtp/rank1/state-2147483647/state.bundle` | `7019efdb7242732df7d26dfd27c9090f032b23a8b864ce658799a4cc5d50d56c` |
| 06 | gsq-current-class-a | `rank0/state-2147483647/state.bundle` | `d12c3dc62c0c905266e482042b61ce5792cfb7e57890bdca9b17f9c906104ed9` |
| 07 | gsq-current-class-a | `rank1/state-2147483647/state.bundle` | `9963e1f78a354cdfce16f3ec062f6bc2a0f777ba1ee3c24e417f2fb9cda1f9ad` |
| 08 | gsq-current-class-a | `warmup-none/rank0/state-2147483647/state.bundle` | `5b74a749548a9f99bcb5df6e8bc3f86a274f874ce82b1657a82fcf79688c4624` |
| 09 | gsq-current-class-a | `warmup-none/rank1/state-2147483647/state.bundle` | `511b9123e02bcc508ec2f8af72df887dd8f86a9fb16d5b2fa139f9245fc7aea6` |
| 10 | gsq-current-class-a | `prompt-00-none/rank0/state-2147483647/state.bundle` | `6005f138b3b9f1f0beedce5b275acc27d723383e1bcc9404434d1782660fa550` |
| 11 | gsq-current-class-a | `prompt-00-none/rank1/state-2147483647/state.bundle` | `5556829341d982ff3cbcf1ad9a908d203b4fd7774b0c05c901b68390b735fde6` |

To restore, verify the archive hash, extract its single member into a fresh empty
directory, and check its size/hash against the original independent artifact index.
Place it only at the corresponding missing relative path under the source run above;
never overwrite existing evidence. Keep its index, seal and state JSON alongside it,
and use the original bundle reader for complete logical range verification. Generic
inherited receipts mention .bin files, but these exact members are state.bundle;
the adapter authority and restore instructions bind their correct paths.

This recovers storage only. It adds no speed result and does not permit a run whose
own live byte forecast and reserves fail. Remaining attribution bundles can be
archived only after needed micro fixtures are independently extracted and retained.
