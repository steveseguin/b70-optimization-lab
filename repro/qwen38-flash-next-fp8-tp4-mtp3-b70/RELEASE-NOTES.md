# Qwen3.8 Flash-Next FP8 B70 hybrid runtime stage `2f829747` (v1)

Exact Grade-C research artifact for the `Qwen/Qwen3.8-Flash-Next-FP8`
four-B70 TP4/EP4 eager MTP3 lane. This release hosts native runtime bytes
only. It is not a deployment-ready package and does not alter the measured
benchmark claim.

## Hybrid-runtime disclosure

- Loaded stage build head: `2f829747503c77d4814834dffd0840fb1dd9f75a`.
- Exact payload: 18 files and 1,968,222,999 payload bytes.
- Only `_moe_C.abi3.so` was freshly rebuilt at `2f829747`; the other 17 files
  are unchanged bytes retained from the prior known-loadable stage.
- This is not a claim that all 18 files were freshly built from `2f829747` or
  that a clean rebuild is byte-identical.

## Assets

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `qwen38-flash-next-runtime-stage-2f829747.tar.part-0000` | 1,073,741,824 | `ea8d91b4a184b26a04d18f9f4ac58fb6e116c9fc750e8532fb1ad0cc27f46ca1` |
| `qwen38-flash-next-runtime-stage-2f829747.tar.part-0001` | 894,509,056 | `38ba225d4908ad976b2b08b0ac945f6d95cd4528143ebe231d58c075068b88b4` |
| `qwen38-flash-next-runtime-stage-2f829747.tar.receipt.json` | 4,401 | `ac6cddf7bc193b6ccd3d837c0b461c099e7f0c8fc97a1997ab1c7bb736f088b5` |
| `runtime-stage.sha256` | 1,564 | `9fa443fdb7a6d0042cf04f859cc6fd6a7bdc09943e16cafb4ea084573c892d2b` |

Concatenate part 0000 and then part 0001. The resulting uncompressed tar is
1,968,250,880 bytes with SHA-256
`6bf1b547e3887c86007f5ef5ad7c67be365ce4888f0e2c0a1f360dde7a7b13c3`.
Use the repository's frozen `prepare-runtime.py` installer; do not extract
unverified members directly.

## Evidence boundary

The historical MTP3 result remains Grade C. Its `15.501565 tok/s` value is an
after-first-text screen with `187.899 s` median TTFT and `1.246260` wall output
tok/s. The conventional p4096/o128 99-interval rate is `4.669548 tok/s`.
Public hosting closes artifact availability only, not dependency, clean-host,
startup, quality-replay, or deployment readiness.

Frozen references:

- [reproduction foundation](https://github.com/steveseguin/b70-optimization-lab/blob/qwen38-flash-next-runtime-2f829747-20260827/repro/qwen38-flash-next-fp8-tp4-mtp3-b70/README.md)
- [runtime contract](https://github.com/steveseguin/b70-optimization-lab/blob/qwen38-flash-next-runtime-2f829747-20260827/repro/qwen38-flash-next-fp8-tp4-mtp3-b70/runtime-contract.json)
- [certified source series](https://github.com/steveseguin/b70-optimization-lab/blob/qwen38-flash-next-runtime-2f829747-20260827/patches/qwen38-flash-next-fp8-b70/README.md)
- [historical result](https://github.com/steveseguin/b70-optimization-lab/blob/qwen38-flash-next-runtime-2f829747-20260827/experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp3-4352-attempt1-result.json)
