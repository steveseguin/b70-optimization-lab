# Xe2 verifier v2 joint-N pack artifact

Implemented the safe disk/RAM artifact boundary for a future multi-token Xe2
verifier in `scripts/qwen27-iteration-artifacts.py`. This is iteration
infrastructure, not decode-speed evidence.

The `q4-pack` command consumes one **extracted** row-major GGML Q4_0 tensor
payload. It does not modify or parse the source GGUF. The concrete
`q4_0-joint-n-v1` transform walks K blocks first and groups N rows. Each group
stores its fp16 scales contiguously, then transposes the 16 packed-nibble bytes
to byte-position-major order across N. A partial final N tile is zero padded.
The transform is byte-exact reversible.

Artifacts are published atomically below the external artifact root at
`xe2-verifier-packs/<key>/`. The canonical key covers:

- source model SHA256;
- tensor name and extracted tensor SHA256;
- logical tensor shape and full layout description;
- packer revision;
- llama.cpp build/compiler fingerprint;
- device identity.

The loader-facing `manifest.json` records the payload path, byte count, SHA256,
layout, lookup key, and mandatory admission checks. `q4-verify` recomputes the
canonical identity key and payload checksum/size before admission. Existing
keys are immutable: `q4-pack` only reuses one after those checks pass.

Synthetic validation used a 5x64 Q4_0 tensor with N tile 4, deliberately
exercising final-tile padding. Pack, exact internal unpack/round-trip, manifest
generation, and independent `q4-verify` all passed. The 180-byte row-major
source became a 288-byte padded joint-N artifact as specified.

Example (payload extraction is intentionally outside this command):

```bash
python3 scripts/qwen27-iteration-artifacts.py q4-pack \
  --tensor-payload /external/path/tensor.q4_0.bin \
  --tensor-name blk.0.ffn_down.weight --rows 5120 --k 17408 --n-tile 8

python3 scripts/qwen27-iteration-artifacts.py q4-verify \
  --pack-key <key-printed-by-q4-pack>
```

Still required before runtime use: a checksum-aware GGUF tensor extractor, a
kernel ABI decision for the winning DPAS tile, and llama.cpp loader binding.
