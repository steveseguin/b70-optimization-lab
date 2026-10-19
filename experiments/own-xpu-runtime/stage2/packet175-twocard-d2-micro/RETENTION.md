# Retained runtime constant

`rope.bf16.gz` (1,355,545 bytes) is a byte-identical copy of packet166's retained
frozen BF16 rotary table (raw SHA256
`92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390`). The build
restores it to `build/rope.bf16`; `evidence/runtime-assets.json` binds both.
`build/` is ignored. No weights or model checkpoint bytes are retained here; the
device run reads the layer 0 and layer 3 tensors (including the 512-expert banks)
from the pinned GGUF shard under `ionice -c3`, as packet166 did.
