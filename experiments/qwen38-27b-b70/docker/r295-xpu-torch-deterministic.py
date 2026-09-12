# R295: env-gated torch.use_deterministic_algorithms on the XPU worker. The 2026-09-12 census found the default oneDNN
# fp16 GEMM run-to-run NONDETERMINISTIC for small-N shapes at 129+ rows (split-K classes; e.g. 2560x5120 at M=129-212,
# 1280x5120 at M=193-512), and that torch's deterministic mode removes it at no measurable cost on the vocabulary
# projection and a few percent on the small shapes at M=256. vLLM never enables that mode. VLLM_XPU_TORCH_DETERMINISTIC=1
# enables it in every worker at device init (warn_only, so unsupported ops warn rather than fail). Off by default.
import hashlib, pathlib
p = pathlib.Path("/opt/venv/lib/python3.12/site-packages/vllm/v1/worker/xpu_worker.py")
s = p.read_text()
old = '''        device = self.device_config.device
        if (
            isinstance(device, torch.device)
            and device.type == "xpu"
'''
new = '''        device = self.device_config.device
        if __import__("os").environ.get("VLLM_XPU_TORCH_DETERMINISTIC", "0") == "1":
            torch.use_deterministic_algorithms(True, warn_only=True)
            __import__("logging").getLogger("vllm").info(
                "R295: torch.use_deterministic_algorithms(True) enabled on this worker")
        if (
            isinstance(device, torch.device)
            and device.type == "xpu"
'''
assert s.count(old) == 1, "anchor"
s = s.replace(old, new)
p.write_text(s)
print("R295 inserted; xpu_worker.py sha256", hashlib.sha256(s.encode()).hexdigest())
