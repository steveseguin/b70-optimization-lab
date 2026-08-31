# Qwen3.8 layer-0 MLP down completion D47 preregistration

Date: 2026-08-31

Status: **preregistered before D47 model requests**

D46 found one hash through activation and four hashes at the M=71 loaded INT4
down projection. D47 repeats the same selected production-shaped call and adds
exactly one `torch.xpu.synchronize()` after down projection returns and before
its output is hashed or consumed.

Across four fresh processes:

- input, gate/up, and activation must remain exact;
- one post-sync down hash means the arithmetic result is stable and the defect
  is missing oneDNN-to-PyTorch completion publication; D48 will build the
  asynchronous event-barrier kernel candidate, without host synchronization;
- more than one post-sync down hash means arithmetic is unstable at M=71 and
  D48 will instead use model-scoped dispatcher-ordered M=512 padding.

No performance or production claim is authorized.
