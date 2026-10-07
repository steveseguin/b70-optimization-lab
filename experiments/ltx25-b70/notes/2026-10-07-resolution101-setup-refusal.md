# First same-size reference setup refusal — October 7, 2026

Packet101 (`a6e7be8a8ef49bda454803e6f22c98c29e37f77aa8d57c1c13518fd82471a636`)
started once at15:58UTC and stopped gracefully at16:05UTC. Its encoder window
probe passed. The second setup request refused in the new resident dtype
inventory at `text_primary/gemma3_12b.logit_scale/torch.float32`, before native
full-residency loading or any reference generation. There were two submissions,
zero native clips, zero candidate clips and no timing result. This is a failed
preparation check, not evidence of GPU instability or a quality regression.

The existing `comfy/sd1_clip.py` constructor creates `logit_scale` from an FP32
scalar. The new all-floating-tensors-BF16 assertion did not account for native
mixed-dtype metadata parameters. Do not cast the original model to satisfy the
assertion. Audit the exact legitimate exceptions, including device ownership,
and keep BF16 checkpoint-weight checks and actual residency admission intact.
The CPU tests lacked this real constructor case; add a direct regression case.

The finite campaign latched the refusal, submitted no retry, proved idle twice,
sent one SIGINT and observed exit. Its stop and failure evidence, source/model
identity and window result are retained in the
[closeout](../data/resume-20261007/resolution101-closeout/summary.json).
All four cards passed [postflight](../data/resume-20261007/postflight-101.json),
with zero GPU fault lines on this boot. No power, host memory, swap, cache,
driver or reboot setting changed.

Keep the original packet, failed request directories and captured evidence.
A corrected101b candidate needs its own sealed source manifest and setup request
names. The original25 native/candidate/timed plan requests were never submitted;
reuse of that unconsumed plan is permissible only after explicit collision
checks, with fresh server identity and independently established references.
No full image/audio capture was generated, so no tensor retirement is needed.
