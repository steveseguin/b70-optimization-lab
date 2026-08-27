# Certified Qwen3.8 Flash-Next kernel source series

This directory is the complete kernel source sequence used to build the
`_C` and `_moe_C` components in the TP4/MTP3 certified staged runtime.

- Base commit: `0fd18a7c08a64d2645bf083cfa5576200b61b02c`
- Certified commit: `2f829747503c77d4814834dffd0840fb1dd9f75a`
- Required resulting tree: `d8c4318a0f0d71c3c36867253ad92b377906fec9`

Apply `0001` through `0007` in lexical order. `series.sha256` freezes both
the order and bytes. The adjacent historical `../vllm-xpu-kernels/` directory
is not an alternative series: it is preserved evidence and is incomplete for
this certified source identity.

The later `ad25aa9f` exact-GDN proof change is intentionally excluded. The
certified MTP3 process observed that checkout in the source directory but
loaded the staged runtime built at `2f829747`.

Verify both vLLM and kernel source reconstruction without builds or GPU access:

```bash
python3 ../verify-certified-source-series.py \
  --vllm-source /path/to/vllm \
  --kernel-source /path/to/vllm-xpu-kernels
```

This closes the source history only. The exact hybrid native runtime archive,
model download manifest, and clean-host deployment package remain separate
publication work.
