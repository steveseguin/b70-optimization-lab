# Qwen3.8 FP8: deterministic eager baseline and compiled-path closure

## Promoted result

The official-FP8/W8A16 TP2 target now has a strict single-user baseline. Two
fresh-server eager attempts used the complete fixed 12-prompt, six-class suite,
the natural 512-token cap, raw streamed token IDs, and no prompt/KV/response
cache reuse. Every row reported `cached_tokens=0`; both workload gates and both
independent canary batteries passed; all 12 complete token arrays matched.

| attempt | class-balanced decode |
| --- | ---: |
| `detstate-r5-tp2-A` | 18.850167 tok/s |
| `detstate-r5-tp2-B` | 18.970316 tok/s |
| two-attempt median | **18.910242 tok/s** |

The validated container is
`neural-download/vllm-openai-xpu:qwen38-fp8-deterministic-state-r5`, image ID
`sha256:47507a8ca2a78e83666a6f300ec94c5b5c5915740f147bf9d1565c938de8f25b`.
It is based on vLLM `ac7509e2b`, XPU kernels `1e90ffa672`, official checkpoint
revision `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`, W8A16 enabled, XPU Graph
disabled, TP2, FP16 activations/KV, MTP0, and direct oneCCL P2P.

The source delta is archived at
`../patches/vllm-qwen38-xpu-deterministic-gdn-ba-state-20260828.patch`. It pads
the small GDN B/A prefill projection into stable 256-row reductions and makes
the recurrent conv/SSM cache mutations explicit custom-op arguments. The patch
is byte-identical to the files in the validated image.

## Fast compiled path remains withheld

No compiled or XPU-Graph rate is promoted. Each candidate below passed its
workload and objective-canary gates, but failed the required full-array repeat
gate:

| candidate | rates (A/B) | exact prompts | disposition |
| --- | ---: | ---: | --- |
| r7, final-layer synchronization | 33.751 / 33.596 | 9/12 | reject |
| r8, synchronization after each GDN | startup deadlock | — | reject |
| r9, GDN captured inside XPU Graph | 35.07 screen | canaries failed | reject |
| r10, compiler-visible bound state buffers | 33.844 / 33.881 | 9/12 | reject |
| r11, XPU Graph off but Inductor retained | 34.669 / 34.690 | 7/12 | reject |
| r12, r11 + `TORCHINDUCTOR_DETERMINISTIC=1` | 34.675 / 34.682 | 5/12 | reject |

The r11 result proves XPU Graph is not the only source: TP2 Inductor itself is
not fresh-server exact on this stack. This is consistent with vLLM's explicit
warning that XPU Graph currently supports only single-GPU execution, but the
remaining compiled issue is narrower and still open. The next investigation is
the compiled TP2 collective boundary; it must not weaken the output oracle.

## Evidence

Raw evidence is retained on the lab NVMe under
`/mnt/fast-ai/evidence/qwen38-fp8-detstate-r5-tp2-{A,B}` and the r7-r12
candidate directories. The repository summary is
`../data/2026-08-28-qwen38-fp8-deterministic-eager-baseline.json`.
