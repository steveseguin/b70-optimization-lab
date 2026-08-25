# Qwen3.6 Q4_K_M MTP artifact intake

Date: 2026-08-25. Status: **locally present, checksum-pinned, matrix child
added; exact-depth measurements pending**.

The Qwen 27B family registry omitted a distinct Qwen3.6 GGUF artifact that is
already present on the model drive:

- repository: `unsloth/Qwen3.6-27B-MTP-GGUF`;
- revision: `5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace`;
- file: `Qwen3.6-27B-Q4_K_M.gguf`;
- size: `17,106,773,120` bytes;
- SHA-256: `a7cbd3ecc0e3f9b333edee61ae66bc87ed713c5d49587a8355814722ed329e0f`;
- local path:
  `/mnt/usb-models/models/qwen36-27b-mtp-gguf/Qwen3.6-27B-Q4_K_M.gguf`.

This is not an alias for the repository's `UD-Q4_K_XL` file. The two files
have different quantization formats, sizes, hashes, and runtime dispatch
paths. The Q4_K_M artifact therefore belongs as its own quantized child in
both the llama.cpp target-only MTP0 contract and the embedded-MTP1–4
contract. Adding it creates 28 target cells and 112 speculative cells across
the frozen TP1/context/graph/KV axes. All 140 start as explicit missing cells;
no speed or quality evidence transfers from another quant.
