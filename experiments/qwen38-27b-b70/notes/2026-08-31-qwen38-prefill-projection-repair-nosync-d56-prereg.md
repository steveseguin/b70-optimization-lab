# D56 preregistration: projection repair without device-wide barriers

Date: 2026-08-31

D53 passed byte-identical 64-layer traces in four fresh processes. D54 and D55
then passed the complete strict suite in separate fresh processes, with all 12
token-ID sequences identical, cached tokens zero, canaries passing, and
class-balanced medians of 24.804756 and 24.801498 tok/s.

D56 removes only the explicit `torch.xpu.synchronize()` calls surrounding the
M=512 padded projections. It retains the exact same zero padding, real-row
copy, projection roles, slicing, GDN image, model, prompt, and runtime flags.
Ordinary XPU stream dependencies should order copy, GEMM, and slice without a
device-wide host barrier. Four fresh TP1 processes will hash every decoder
input/output/residual at prefill call 2 and compare complete token IDs.

Byte-identical traces and responses are required. Any split rejects the
barrier removal and keeps the synchronized baseline. This synchronized tracing
screen is not a performance result; a pass only authorizes a non-tracing strict
speed/quality replay.
