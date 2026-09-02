# Qwen3.8 Flash-Next W13-N32 config-folder qualification A1: pass (2026-09-02)

Date: 2026-09-02 04:22--04:27 EDT (boot `d0024575-835a-4584-a0e0-1db665a88534`,
root SSD at the Gen3 discriminator state under the validated Gen3 clearance)
Status: pass; the A2 W13-N32 result survives the real deployment selection
mechanism

The frozen runner (`tools/run-q38-w13-m1-config-folder-qualification-a1.sh`,
derived runner `656524e1...`, adapter `ec9e8c3f...`, summarizer
`52e798b9...`) ran eight matched fresh-process control/candidate/control cells
on layers 0/47 and EP ranks 0--3 with seed 20260827. Every process set
`VLLM_TUNED_CONFIG_FOLDER` (controls `configs/moe-warps8-m1`, candidates
`configs/moe-m1-w13-n32`), invoked the live vLLM tuned-map resolver, and
receipted the selected key and phase configs before the unchanged A2
real-weight component gate.

| gate | value |
|---|---|
| folder-selection receipts passed | 24 / 24 |
| all 8 cells exact (eager and captured, 100 changing inputs) | true |
| positive cells | 8 / 8 |
| median matched reduction | `22.223121%` |
| worst cell reduction | `21.515070%` |
| control drift within 2% | true |
| health receipt | pass; corrected-event delta 0, root port 0, 8 sectors read |

Evidence:
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260902-moe-m1-w13-n32-config-folder-qualification-a1/`
(`summary.json`, `health-receipt.json`, `identity.txt`, 24 cell JSONL files,
SHA256SUMS). The run was executed by the concurrent Codex session while the
BIOS update was being prepared; this note records it from the evidence.
A later attempt to re-run the runner at 10:02 EDT in the BIOS 2.4a boot
stopped at its no-clobber gate ("evidence root already exists") without GPU
work, which is the intended behaviour.

Together with the A2 confirmation this closes the component chain for the
tuned M1 map: the retained selection mechanism resolves key 1 to W13 N32 /
W2 N64 at eight warps, and the endpoint arm (A56) may proceed.
