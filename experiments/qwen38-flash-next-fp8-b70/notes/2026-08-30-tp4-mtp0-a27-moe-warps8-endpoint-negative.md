# Qwen3.8 Flash-Next FP8 A27 intended M4 MoE arm result

Date: 2026-08-30
Status: intended speed treatment inert; rejected at exact-4K repeat gate

A27 was the first and only full Flash-Next load in boot
`4a84e582-68ac-4958-8d08-3815fbe7aaf6`. The 131 local-NVMe shards loaded in at
most 80.25 seconds. All ranks retained the exact 11.92 GiB synchronous PLE
placement, and the server emitted a receipt loading the frozen tuned-config
file with SHA-256 `f93b5e1d...bf7f`. That receipt did not identify the
batch-size key selected within the file.

Recovery, the inherited accepted 6/7 semantic boundary, 16/16 short repeat,
exact-4K needle, and both cache-zero transport gates passed. The short rows
retained the protected output hash at `5.561458 / 5.473329 / 5.501703 tok/s`,
median `5.501703 tok/s`. That is 0.255% below the protected `5.515783 tok/s`
median. One fast row is insufficient; the treatment receives no endpoint speed
credit.

Exact-4K row 1 matched the retained authority at `5.105157 tok/s`, but row 2
returned a different hash at `5.302356 tok/s`. The final repeat/authority
assertion failed closed. The endpoint configuration therefore cannot be
promoted as reliable/lossless evidence.

Later A28 traces and source review correct the original interpretation. The
production decode routed kernel receives M1. With TP4/EP4 but DP=PCP=SP=1,
`use_all2all_kernels` is false; there is no per-layer token all-gather before
the Triton experts. Config lookup uses `hidden_states.size(0)`, so A27 selected
the unchanged key `1` (`num_warps=4`), not the modified key `4`. The log proved
the file was loaded, not that its M4 entry was selected.

A27 therefore does not test or reject the 20.2--21.1% real-weight M4 component
gain. Its measured speed is effectively a control-like diagnostic and remains
ineligible because it did not beat the protected median and its exact-4K pair
was not repeatable. Future tuned-config arms must emit the selected key and
effective kernel configuration, and the component screen must be repeated at
the real M1 endpoint shape before any endpoint claim.

Teardown was clean: the listener and model processes disappeared, all four
cards returned to about 43 MiB, and host memory/swap recovered. Four corrected
Samsung-NVMe receive events appeared, one with a nonfatal status bit; there was
no reset, GPU loss, OOM, or freeze. Protected `5.515783 tok/s` target-only and
approximately `20.727 tok/s` MTP4 results remain unchanged.

Structured result:
[`20260830-tp4-mtp0-a27-moe-warps8-endpoint-negative.json`](../data/20260830-tp4-mtp0-a27-moe-warps8-endpoint-negative.json).
