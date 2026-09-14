# Native block checkpoint metadata

The [header-only helper](../scripts/inspect-ltx-block-header.py) read 677,616
header bytes from the already verified transformer checkpoint. It allocated no
model tensors, used no GPU and changed no checkpoint or runtime files. The
[receipt](../data/native-block-header-census.json) binds the helper, header and
existing model-verification receipt, with file metadata checked before and after.
It does not rehash the 40 GB tensor payload.

All 48 blocks have the same 84 tensor names, shapes and stored dtypes. Each
contains 386,674,880 elements occupying 773,546,368 stored bytes (737.71 MiB).
Their combined stored state is 34.58 GiB. The video self-attention query matrix
is 4096 by 4096; the audio query matrix is 2048 by 2048. The tiny 32-wide CPU
compiler fixture cannot establish native compiler memory use or GPU latency.

The initial helper rejected the header because it incorrectly assumed every
block tensor was stored as BF16. Inspection found 78 BF16 tensors and six FP32
scale/shift tables per block. The helper now counts each stored dtype's actual
element width; no model data or precision was changed. Stored dtypes alone do
not establish loaded or compute dtypes. The compiler's BF16-state admission
must be checked against the existing loader and actual native runtime before
any GPU qualification; do not cast state merely to satisfy that guard.

Source inspection of the frozen loader supports BF16 runtime state: the native
block constructor creates those six raw parameters with the selected BF16
dtype, and the static model patcher loads them with `assign=False`. PyTorch
copies checkpoint values into the existing parameter storage. This is baseline
loader behavior, not a compiler optimization. The native runtime state census
is still required; checkpoint metadata and source reasoning are not live
measurements.
The [source dtype audit](ltx-block-storage-runtime-dtype.md) records the exact
loader path and reviewed source hashes.

This metadata census is preparation evidence. The pending encoder runtime
packet remains unchanged, and the existing PID24848 server remains in place.
