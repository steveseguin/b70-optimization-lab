# DeepSeek V4 Flash K160 source archive

This folder preserves the exact source history and reviewable combined deltas
for the 80.820052 tok/s record, plus later EAGLE experiment snapshots.

## Promoted record source

| Component | Public base | Record commit | Exact bundle SHA-256 | Combined patch SHA-256 |
| --- | --- | --- | --- | --- |
| vLLM | `61c87db645c256651b5a366f538898485077ad32` | `264c7f2f7df21ddeeab32ecca0353133344f1ac9` | `cebc81bedc22496dc82836b9419428e0377a3eb4e7ac213014a7306c7b30e825` | `9228bccd3e690a9ca06366a21e6c2506fd088176f580eb8355d83a5c6fa71aff` |
| vLLM XPU kernels | `dda91d171fbc3f51d1d65a7f8839714b1efffd42` | `31315673737d95da0f79179c8f755260ef02c1d6` | `4c04c7f501c780dc13f5db69d551e3da52f5cf1103c83cf10f64e57afffdb9d9` | `8be7f7c397258921928c6cf013c54b24866594b03afe908946dd10669ef92981` |
| oneCCL | `66499938b7a8b615e26361c52900e7aec306ce50` | `48fda4f0e074db005596d6899d5227d3f0316c12` | `100d9c7f03e648501e174498a72e9da88751b42acc3a94828ff95db7c1d5849c` | `21a60677051d61da8bf16bb51ac277fb18c678ef008a6db18a6b1f2d723e27cc` |

Use the `.bundle` files to restore the original commits and the `.patch` files
to review the final tree delta. Fetch and worktree commands are in the
[standalone repro](../../repro/deepseek-v4-flash-k160-b70-80tps-20260718/README.md).

The `0001-xpu-add-guarded-K160-EAGLE-*` and
`0002-xpu-stabilize-EAGLE-*` files are later training experiments. Their
filenames and linked notes distinguish retained candidates from rejected
variants; they are not part of the 80.820052 record identity.
