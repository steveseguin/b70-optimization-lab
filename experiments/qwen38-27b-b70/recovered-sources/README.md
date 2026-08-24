# Recovered kernel source: `csrc/moe/fused_moe_prologue.cpp`

**Corrects an earlier claim.** This file was previously recorded as
"absent from the pinned commit's tree and unrecoverable (shallow repo)",
meaning the pinned kernel identity could not be rebuilt by anyone. That was
wrong — the blob is reachable in upstream history and is recovered here.

## The problem

`vllm-xpu-kernels` at the pinned `2dd55f38`:

- `CMakeLists.txt:562` lists `csrc/moe/fused_moe_prologue.cpp`
- that file is **absent** from the tree
- `csrc/moe/fused_moe_prologue.hpp` **is** present
- `csrc/xpu/moe_layerlet.cpp:1186` **calls** `fused_moe_prologue(...)`
- `vllm_xpu_kernels/fused_moe_interface.py:901,2271` probes and calls it
- the shipped `vllm_xpu_kernels/_moe_C.abi3.so` **exports** the symbol

So the installed binary contains the kernel, but the source tree cannot
rebuild it. Cause: upstream commit `bed9504` ("[SYCL] sync innersource kernel
and test updates (#478)") **deleted** both `fused_moe_prologue.cpp` (216 lines)
and `.hpp` (709 lines); our fork took the `.cpp` deletion while keeping the
`.hpp` and the CMake reference.

## Provenance

- recovered from `bed9504a5333708830988c5e5fbdaa8c9c957473^` (the parent, i.e.
  the last upstream tree that still had it)
- `git cat-file -p bed9504a5333708830988c5e5fbdaa8c9c957473^:csrc/moe/fused_moe_prologue.cpp`
- 216 lines, 7920 bytes
- `sha256 b636de3717c5ee2b638bb360037d70d6060ceac86c35b9863a7f11a46be457ad`

## Signature check — it is the right file

The recovered definition, the deployed symbol and the call site all agree:

| source | signature |
| --- | --- |
| `_moe_C.abi3.so` (demangled) | `fused_moe_prologue(at::Tensor, std::optional<at::Tensor> const&, at::Tensor, at::Tensor, at::Tensor, long, long, long, long, long, long)` |
| recovered `.cpp:170` | `torch::Tensor, const c10::optional<torch::Tensor>&, torch::Tensor, torch::Tensor, torch::Tensor` + 6 × `int64_t` |
| `moe_layerlet.cpp:1186` call | 5 tensors + `hidden_size, inter_size, 1, 0, 1, num_experts` |

## Status: build-verified on BMG-G31 (2026-08-24)

The `.hpp` we ship has drifted from the one that paired with this `.cpp`:

- local `csrc/moe/fused_moe_prologue.hpp` → `sha256 89a6591974fa22ea2c39d5a5b641286922e3e191a8dc026d269dcb0f5b51bc88`
- `bed9504^` `.hpp` → `sha256 91be429fc5071f8023fae574429cf8599ef3eef564c71db2a3f70d9f40180063`

The signature agreement above was subsequently confirmed by compilation. The
recovered `.cpp` compiled together with the retained local `.hpp`, linked into
the combined `_xpu_C` module, imported successfully, and completed the Qwen3.6
35B model load plus B1/B64 decode treatment on one B70.

The pinned tree still needs two source-compatibility repairs beyond copying
this file: restore the declaration in `csrc/moe/moe_ops.h`, and align the
grouped W4A16 wrapper with the deployed 11-argument Xe2 ABI. The pinned
grouped-GEMM source does not compile against its current CUTLASS checkout, so
the verified experimental module reused the already deployed grouped library
byte-for-byte instead of claiming a full clean-tree kernel rebuild.

Verified BMG-G31 runtime identities:

- combined `_xpu_C.abi3.so`: `sha256 12a0e730989225195d4068a65a932833b81154a7ebc6edaefee05754ffd32c69`
- rebuilt `libgdn_attn_kernels_xe_2.so`: `sha256 4a7019bd8bba6538dad41d142d24c65b4b11b2dd443a9b00127b0bb95d28398e`
- reused `libgrouped_gemm_xe_2.so`: `sha256 6ca90896b773ec7d93a88f32b69e94893046b8eec01022b5967bc19dee9e49c1`

This verifies the recovered prologue source and the combined module, not the
incompatible grouped-GEMM source subtarget.

## To use

    cp fused_moe_prologue.cpp /home/steve/src/vllm-xpu-kernels/csrc/moe/

then build, and record the outcome here.
